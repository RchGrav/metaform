"""The local service's sign-in, and the person's account page, on a broker.

`metaform cloud login` uses the OAuth 2.0 device authorization grant (RFC 8628) with the built-in public client
`metaform-cli`: a terminal has no browser redirect to receive a code, so the person approves on this server's page,
with the passkey they use everywhere else, the code the terminal shows. The CLI made a key pair first and signs a DPoP
proof (RFC 9449) with it on every request, so the tokens it receives are bound to that key: its refresh token and its
tunnel token are useless without the key, which never leaves the person's machine.

What a pending sign-in needs (the device code's hash, the code the person types, the instance and device names, the
key's thumbprint) is held in memory for ten minutes and lost on a restart, when the CLI simply asks again.

The account page (`/account`) shows the instances connected now and has "Sign out everywhere", which bumps the
account's generation: every token, session and tunnel of the account ends at once (tokens.py).
"""
from __future__ import annotations

import hmac
import ipaddress
import re
import secrets
import threading
import time
import urllib.parse
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from mcp.server.auth.provider import TokenError
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route

from . import tokens
from .config import LABEL

if TYPE_CHECKING:
    from .authserver import Node

DEVICE_SECONDS = 600
INTERVAL = 5
SLOW_DOWN = 5
USER_ALPHABET = 'BCDFGHJKLMNPQRSTVWXZ'  # RFC 8628 section 6.1: no vowels, so no word is spelled by chance
PENDING_PER_ADDRESS = 5
WRONG_ENTRIES, WRONG_WINDOW, LOCKOUT = 10, 600.0, 900.0
DEVICE_NAME = re.compile(r'[^\w .@-]')


def user_code() -> str:
    picked = ''.join(secrets.choice(USER_ALPHABET) for _ in range(8))
    return picked[:4] + '-' + picked[4:]


def normal_code(given: str) -> str:
    """The code as the person typed it, in any case, with or without its dash or spaces."""
    letters = ''.join(one for one in given.upper() if one.isalpha())
    return letters[:4] + '-' + letters[4:] if len(letters) == 8 else ''


def source(request: Request) -> str:
    """Who is asking, as limits count it: the client Caddy names in X-Forwarded-For when the request came through
    Caddy on loopback, and for IPv6 its /64, the block one subscriber is given, so stepping through the addresses
    of one's own block is still one source. Caddy writes the header itself, ignoring one the client sent, unless told
    to trust a proxy before it."""
    peer = request.client.host if request.client else ''
    forwarded = request.headers.get('x-forwarded-for', '')
    if peer in ('127.0.0.1', '::1') and forwarded:
        peer = forwarded.split(',')[-1].strip()
    return group(peer)


def group(address: str) -> str:
    try:
        parsed = ipaddress.ip_address(address.split('%')[0])
    except ValueError:
        return address
    if isinstance(parsed, ipaddress.IPv6Address):
        mapped = parsed.ipv4_mapped
        return str(mapped) if mapped is not None else str(ipaddress.ip_network(f'{parsed}/64', strict=False))
    return str(parsed)


@dataclass
class Pending:
    user: str
    instance: str
    device: str
    jkt: str
    address: str
    expires: float
    interval: float = INTERVAL
    polled: float = 0.0
    state: str = 'pending'  # approved, denied
    account: str = ''
    approved: float = 0.0


class DeviceGrants:
    """Pending device sign-ins by the device code's hash, with the user codes that name them, and the wrong user codes
    entered, so a code cannot be guessed: the code space is 20^8, and ten wrong ones in ten minutes lock out for
    fifteen both the source (an IPv4 address, an IPv6 /64) and the signed-in account that typed them, so neither new
    addresses nor new browsers buy an attacker more guesses at someone else's pending sign-in."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.by_device: dict[str, Pending] = {}
        self.by_user: dict[str, str] = {}
        self.wrong: dict[str, list[float]] = {}
        self.locked: dict[str, float] = {}

    def _prune(self, now: float) -> None:
        for hashed, held in list(self.by_device.items()):
            if held.expires < now:
                self.by_device.pop(hashed, None)
                self.by_user.pop(held.user, None)

    def start(self, instance: str, device: str, jkt: str, address: str) -> tuple[str, Pending] | None:
        now = time.time()
        with self.lock:
            self._prune(now)
            if sum(1 for held in self.by_device.values() if held.address == address) >= PENDING_PER_ADDRESS:
                return None
            code = secrets.token_urlsafe(32)
            shown = user_code()
            while shown in self.by_user:
                shown = user_code()
            held = Pending(shown, instance, device, jkt, address, now + DEVICE_SECONDS)
            self.by_device[tokens.body_hash(code.encode())] = held
            self.by_user[shown] = tokens.body_hash(code.encode())
            return code, held

    def find(self, typed: str, address: str, account: str = '') -> Pending | None | str:
        """The pending sign-in a typed code names; 'locked' when this source or this account typed too many wrong
        ones."""
        now = time.time()
        counted = [address, *([f'account:{account}'] if account else [])]
        with self.lock:
            if any(self.locked.get(key, 0) > now for key in counted):
                return 'locked'
            self._prune(now)
            for key, until in list(self.locked.items()):
                if until < now:
                    self.locked.pop(key, None)
            hashed = self.by_user.get(normal_code(typed))
            held = self.by_device.get(hashed) if hashed else None
            if held is None or held.state != 'pending':
                for key in counted:
                    misses = [when for when in self.wrong.get(key, []) if when > now - WRONG_WINDOW] + [now]
                    self.wrong[key] = misses
                    if len(misses) >= WRONG_ENTRIES:
                        self.locked[key] = now + LOCKOUT
                        self.wrong.pop(key, None)
                return None
            return held

    def decide(self, held: Pending, account_id: str, approve: bool) -> None:
        with self.lock:
            held.state = 'approved' if approve else 'denied'
            held.account = account_id
            held.approved = time.time()

    def poll(self, code: str) -> Pending | None:
        with self.lock:
            return self.by_device.get(tokens.body_hash(code.encode()))

    def finish(self, code: str) -> None:
        with self.lock:
            held = self.by_device.pop(tokens.body_hash(code.encode()), None)
            if held is not None:
                self.by_user.pop(held.user, None)


def _error(code: str, description: str, status: int = 400) -> JSONResponse:
    return JSONResponse({'error': code, 'error_description': description}, status_code=status,
                        headers={'Cache-Control': 'no-store', 'Pragma': 'no-cache'})


def _issued(made: dict[str, Any]) -> JSONResponse:
    return JSONResponse(made, headers={'Cache-Control': 'no-store', 'Pragma': 'no-cache'})


def token_endpoint(node: Node, sdk: Any) -> Callable[[Request], Awaitable[Response]]:
    """`/oauth/token`: the device code grant and the local service's DPoP-bound refreshes here, every other grant to
    the SDK's handler, which reads the same parsed form."""
    grants: DeviceGrants = node.device_grants
    replay: tokens.Replay = node.dpop_seen
    url = node.policy.issuer + '/oauth/token'

    def grant_key(grant: str, form: Any) -> str | None:
        """What a token request is charged to: the grant a valid signed refresh token or code belongs to, or the
        pending sign-in a device code names; None for anything this server did not issue."""
        signed = node.signed
        if grant == 'refresh_token':
            claims = signed.signer.read(str(form.get('refresh_token') or ''), tokens.REFRESH, node.policy.issuer)
            return f'grant:{claims.get("fam")}' if claims else None
        if grant == 'authorization_code':
            claims = signed.signer.read(str(form.get('code') or ''), tokens.CODE, node.policy.issuer)
            return f'code:{claims.get("jti")}' if claims else None
        if grant == tokens.DEVICE_GRANT:
            code = str(form.get('device_code') or '')
            return f'device:{tokens.body_hash(code.encode())}' if grants.poll(code) is not None else None
        return None

    async def handle(request: Request) -> Response:
        form = await request.form()
        grant = str(form.get('grant_type') or '')
        client = str(form.get('client_id') or '')
        if not node.token_gate(request, grant_key(grant, form)):
            return JSONResponse({'error': 'slow_down', 'error_description': 'Too many requests; try again shortly.'},
                                status_code=429, headers={'Retry-After': '10', 'Cache-Control': 'no-store'})
        if grant != tokens.DEVICE_GRANT and client != tokens.CLI_CLIENT:
            return await sdk.handle(request)
        if client != tokens.CLI_CLIENT:
            return _error('invalid_client', 'The device grant is for the Metaform command line only.', 401)
        signed = node.signed
        if grant == tokens.DEVICE_GRANT:
            code = str(form.get('device_code') or '')
            held = grants.poll(code)
            if held is None or held.expires < time.time():
                return _error('expired_token', 'The sign-in expired or is unknown; run metaform cloud login again.')
            if tokens.dpop_key(request.headers.get('dpop'), 'POST', url, replay) != held.jkt:
                return _error('invalid_dpop_proof', 'The DPoP proof is missing or not from the key that started this.')
            now = time.time()
            if held.state == 'pending':
                if now - held.polled < held.interval:
                    held.interval += SLOW_DOWN
                    held.polled = now
                    return _error('slow_down', f'Poll every {int(held.interval)} seconds.')
                held.polled = now
                return _error('authorization_pending', 'Waiting for you to approve on the page.')
            grants.finish(code)
            if held.state == 'denied':
                return _error('access_denied', 'The sign-in was denied on the page.')
            account = signed.allowed(held.account)
            if account is None:
                return _error('access_denied', 'The account that approved this is no longer allowed.')
            return _issued(signed.issue(tokens.CLI_CLIENT, f'Metaform on {held.device}', account, [tokens.TUNNEL_SCOPE],
                                        node.policy.tunnel, secrets.token_urlsafe(16), 0, int(held.approved),
                                        {'cnf': {'jkt': held.jkt}, 'inst': held.instance}))
        if grant != 'refresh_token':
            return _error('unsupported_grant_type', 'The Metaform command line uses the device code and refresh.')
        # The key first, then the grant: a copied refresh token without its key is refused before anything else is
        # decided, so it cannot even end the machine's sign-in by being presented as a reuse.
        given = str(form.get('refresh_token') or '')
        signature = signed.signer.read(given, tokens.REFRESH, node.policy.issuer)
        if signature is None or signature.get('client_id') != tokens.CLI_CLIENT:
            return _error('invalid_grant', 'The refresh token is not valid; run metaform cloud login again.')
        bound: Any = signature.get('cnf')
        if not isinstance(bound, dict) or tokens.dpop_key(request.headers.get('dpop'), 'POST', url, replay) != \
                cast(dict[str, Any], bound).get('jkt'):
            return _error('invalid_dpop_proof', 'The DPoP proof is missing, not from the key this token is bound to, '
                                                'or made at a time too far from this server\'s clock.')
        claims = signed.refreshed(given)
        if claims is None:
            return _error('invalid_grant', 'The refresh token is not valid; run metaform cloud login again.')
        try:
            return _issued(signed.rotate_refresh(claims, str(claims.get('scope') or '').split()))
        except TokenError as error:
            return _error(error.error, error.error_description or 'The refresh token was already used.')
    return handle


def revocation_endpoint(node: Node) -> Callable[[Request], Awaitable[Response]]:
    """`/oauth/revoke`, RFC 7009, for signed tokens: the grant the token belongs to is revoked, when the client
    revoking it is the one it was issued to. Public clients authenticate by their id alone. The answer is 200 whether
    or not the token was known, as section 2.2 asks, so it tells a caller nothing."""
    async def handle(request: Request) -> Response:
        form = await request.form()
        token, client = str(form.get('token') or ''), str(form.get('client_id') or '')
        if not token or not client:
            return _error('invalid_request', 'Name the token and the client_id.')
        signed = node.signed
        claims = signed.signer.read(token, tokens.ACCESS) or signed.signer.read(token, tokens.REFRESH)
        if not node.token_gate(request, f'grant:{claims.get("fam")}' if claims else None):
            return JSONResponse({'error': 'slow_down'}, status_code=429, headers={'Retry-After': '10'})
        if claims is not None and claims.get('client_id') == client:
            signed.families.revoke(str(claims.get('fam') or ''), time.time() + tokens.REFRESH_CAP_SECONDS)
        return Response(status_code=200, headers={'Cache-Control': 'no-store'})
    return handle


# ---------------------------------------------------------------------------------------------------- the pages

def routes(node: Node) -> list[Route]:
    from .authserver import escape as _escape
    from .authserver import page as _page
    from .authserver import safe_next as _safe_next

    grants: DeviceGrants = node.device_grants
    policy = node.policy
    headers = {'Cache-Control': 'no-store', 'X-Frame-Options': 'DENY', 'Content-Security-Policy': "frame-ancestors 'none'"}

    def message(title: str, text: str, status: int = 200) -> HTMLResponse:
        return HTMLResponse(_page('message.html', title=_escape(title), text=_escape(text)), status_code=status,
                            headers=headers)

    def to_signin(target: str) -> Response:
        return RedirectResponse(f'/node/signin?next={urllib.parse.quote(_safe_next(target), safe="")}',
                                status_code=302)

    async def authorize(request: Request) -> Response:
        """RFC 8628 section 3.1: the CLI asks; it receives the device code, the code to show and where to go."""
        form = await request.form()
        if str(form.get('client_id') or '') != tokens.CLI_CLIENT:
            return _error('invalid_client', 'Only the Metaform command line signs in this way.', 401)
        scope = str(form.get('scope') or tokens.TUNNEL_SCOPE)
        if scope != tokens.TUNNEL_SCOPE:
            return _error('invalid_scope', f'The command line asks for {tokens.TUNNEL_SCOPE} only.')
        instance = str(form.get('instance') or 'default').lower()
        if not LABEL.match(instance):
            return _error('invalid_request', 'The instance is a name of lowercase letters, digits and hyphens.')
        device = DEVICE_NAME.sub('', str(form.get('device_name') or 'a computer'))[:64] or 'a computer'
        jkt = tokens.dpop_key(request.headers.get('dpop'), 'POST', policy.issuer + '/oauth/device_authorization',
                              node.dpop_seen)
        if jkt is None:
            return _error('invalid_dpop_proof', 'A DPoP proof is needed, so the tokens are bound to your machine.')
        made = grants.start(instance, device, jkt, source(request))
        if made is None:
            return _error('slow_down', 'Too many sign-ins are waiting from this address; finish or let them expire.')
        code, held = made
        page = policy.issuer + '/device'
        return _issued({'device_code': code, 'user_code': held.user, 'verification_uri': page,
                        'verification_uri_complete': f'{page}?user_code={held.user}', 'expires_in': DEVICE_SECONDS,
                        'interval': INTERVAL})

    async def device_page(request: Request) -> Response:
        typed = request.query_params.get('user_code', '')
        signed = node.signed_in(request)
        if signed is None:
            return to_signin('/device' + (f'?user_code={urllib.parse.quote(normal_code(typed))}' if typed else ''))
        account, csrf = signed
        if not typed:
            return HTMLResponse(_page('device-code.html', account=_escape(account.name), said=''), headers=headers)
        found = grants.find(typed, source(request), account.id)
        if found == 'locked':
            return message('Too many wrong codes', 'Wait fifteen minutes, then try again.', 429)
        if not isinstance(found, Pending):
            return HTMLResponse(_page('device-code.html', account=_escape(account.name),
                                      said='<p class="warn">That code is unknown or expired. Check the code your '
                                           'terminal shows.</p>'), status_code=400, headers=headers)
        return approval(account.id, account.name, found, csrf)

    def approval(account_id: str, name: str, found: Pending, csrf: str, status: int = 200) -> HTMLResponse:
        """The page that asks. When an instance of that name is connected now, approving moves it: every request
        the person's AI tools send to that name goes to the new machine instead, so the page says so and the
        approval needs the box ticked that says the person means it."""
        replaces = ''
        if node.connected(account_id, found.instance):
            replaces = ('<p class="warn"><strong>Your Metaform named ' + _escape(found.instance) + ' is connected '
                        'now.</strong> Approving disconnects it, and from then on every request your AI tools send to '
                        'it, with whatever you asked them, goes to this new machine instead.</p>'
                        '<p><label><input type="checkbox" name="replace" value="yes" required> Replace the connected '
                        + _escape(found.instance) + ' with this machine</label></p>')
        return HTMLResponse(_page('device.html', account=_escape(name), code=_escape(found.user),
                                  instance=_escape(found.instance), device=_escape(found.device),
                                  url=_escape(policy.instance_resource(found.instance)), csrf=_escape(csrf),
                                  replaces=replaces), status_code=status, headers=headers)

    async def device_decide(request: Request) -> Response:
        if not node._same_origin(request):  # pyright: ignore[reportPrivateUsage]
            return message('Refused', 'This form came from another site.', 403)
        form = await request.form()
        signed = node.signed_in(request)
        if signed is None or not hmac.compare_digest(str(form.get('csrf', '')), signed[1]):
            return message('Sign in again', 'Your session ended.', 403)
        found = grants.find(str(form.get('user_code') or ''), source(request), signed[0].id)
        if not isinstance(found, Pending):
            return message('This sign-in expired', 'Run metaform cloud login again in your terminal.', 400)
        approve = form.get('decision') == 'approve'
        if approve and node.connected(signed[0].id, found.instance) and form.get('replace') != 'yes':
            return approval(signed[0].id, signed[0].name, found, signed[1], 409)
        grants.decide(found, signed[0].id, approve)
        if not approve:
            return message('Denied', 'Nothing was signed in. If you did not start this, someone may be trying to '
                                     'use your account: sign out everywhere on your account page.')
        return message('Approved', f'Your Metaform named {found.instance} is signing in. Return to your terminal.')

    async def account_page(request: Request) -> Response:
        signed = node.signed_in(request)
        if signed is None:
            return to_signin('/account')
        account, csrf = signed
        live = node.instances(account.id)
        listed = ''.join(f'<li><strong>{_escape(name)}</strong> at <code>{_escape(policy.instance_resource(name))}'
                         '</code></li>' for name in live) or \
            '<li>None connected now.</li>'
        return HTMLResponse(_page('account.html', account=_escape(account.name), instances=listed,
                                  passkeys=str(len(node.store.passkey_ids(account))), csrf=_escape(csrf)),
                            headers=headers)

    async def sign_out_everywhere(request: Request) -> Response:
        if not node._same_origin(request):  # pyright: ignore[reportPrivateUsage]
            return message('Refused', 'This form came from another site.', 403)
        form = await request.form()
        signed = node.signed_in(request)
        if signed is None or not hmac.compare_digest(str(form.get('csrf', '')), signed[1]):
            return message('Sign in again', 'Your session ended.', 403)
        node.signed.generations.bump(signed[0].id)
        response = message('Signed out everywhere', 'Every AI tool and every Metaform signed in to this account must '
                                                    'sign in again: metaform cloud login on each machine.')
        response.delete_cookie(policy.cookie, path='/', secure=policy.secure, httponly=True, samesite='lax')
        return response

    return [Route('/oauth/device_authorization', authorize, methods=['POST']),
            Route('/device', device_page, methods=['GET']), Route('/device', device_decide, methods=['POST']),
            Route('/account', account_page, methods=['GET']),
            Route('/account/signout', sign_out_everywhere, methods=['POST'])]
