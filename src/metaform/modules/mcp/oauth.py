"""The MCP server as an OAuth 2.1 resource server, for a server reached beyond this machine.

A server bound only to loopback and named by no public URL is the local server it always was. One with
`mcp_public_url` set, or bound to any other address, is exposed: it starts only when an authorization server is
there to check its tokens, and then every request to `/mcp` needs a token issued for exactly `<public url>/mcp`
(RFC 8707), every A2A request one issued for `<public url>/a2a`. The pieces are the MCP Python SDK's own:
`AuthSettings` and the bearer middleware, which answers 401 with `WWW-Authenticate: Bearer resource_metadata=...`
and serves Protected Resource Metadata at `/.well-known/oauth-protected-resource/mcp` (RFC 9728). Tokens are checked
by introspection (RFC 7662) at the Node's authorization server on loopback, with a credential of the resource
server's own, so a revoked token stops working at once and no signing key is shared.

A Metaform reached through the cloud broker (the cloud module's tunnel) checks no bearer token from a host at all: the
broker keeps the host's token and sends, for each request, an assertion it signed (`Asserted`), which this side
checks against the key set saved at login, its own resource URL, the account it signed in as, and the request body.

A tool call also needs the scope its tool's effect calls for: `mcp:read` for a read, `mcp:write` for a write or a
removal, `mcp:dispatch` for a tool that starts or steers agents. A call short of it is answered 403
`insufficient_scope` naming the scope, the step-up challenge of the MCP authorization specification of 2026-07-28.
"""
from __future__ import annotations

import base64
import ipaddress
import json
import time
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from mcp.server.auth.provider import AccessToken

from metaform import home
from metaform.module import Stop

READ, WRITE, DISPATCH = 'mcp:read', 'mcp:write', 'mcp:dispatch'
A2A_SCOPE = 'a2a:tickets'
RESOURCE_SERVER = 'metaform-resource-server'
DEFAULT_INTROSPECTION = 'http://127.0.0.1:7435/oauth/introspect'
DISPATCH_MODULES = ('dispatch',)


def loopback(bind: str) -> bool:
    if bind == 'localhost':
        return True
    try:
        return ipaddress.ip_address(bind.strip('[]')).is_loopback
    except ValueError:
        return False


def secret() -> str | None:
    """The introspection credential the Node's authorization server writes on its first start."""
    path = home.home() / 'run' / 'node-introspection'
    try:
        return path.read_text(encoding='utf-8').strip() or None
    except OSError:
        return None


@dataclass(frozen=True)
class Exposure:
    """A server reached from outside: its public origin and where it checks tokens; `path` is its resource's path,
    `/mcp`, or `/mcp/<instance>` for a named instance behind the cloud broker."""
    public: str
    introspection: str
    credential: str
    path: str = '/mcp'

    @property
    def mcp(self) -> str:
        return self.public + self.path

    @property
    def a2a(self) -> str:
        return self.public + '/a2a'

    @property
    def host(self) -> str:
        return urllib.parse.urlsplit(self.public).netloc


def exposure(public_url: str, bind: str, introspection: str = DEFAULT_INTROSPECTION,
             credential: Callable[[], str | None] = secret) -> Exposure | None:
    """None for a local server; the exposure for one reached from outside; Stop for one that would be reached from
    outside with nothing to check who is calling, since nothing anonymous is served beyond this machine."""
    public = public_url.strip().rstrip('/')
    if not public and loopback(bind):
        return None
    if not public:
        raise Stop(f'The MCP server would listen on {bind} with no authorization server to check its callers.',
                   'Serve it as a Metaform Node (metaform node init <domain>), or bind it to 127.0.0.1')
    parts = urllib.parse.urlsplit(public)
    if parts.scheme != 'https' or not parts.hostname or parts.path or parts.query or parts.fragment:
        raise Stop(f'mcp_public_url must be an https origin such as https://metaform.example.com, not {public!r}.',
                   'metaform set --mcp-public-url https://<domain>')
    found = credential()
    if not found:
        raise Stop('The Node\'s authorization server has not started, so no token could be checked.',
                   'Start it first: metaform node auth --node-domain <domain> (compose starts it before this server)')
    return Exposure(public, introspection, found)


def viewer(ctx: Any) -> str | None:
    """Who is calling, as the Node's authorization server named them: its issuer and the account's subject, from the
    token the SDK's bearer middleware checked for this HTTP request; None over stdio or on a local server."""
    request = getattr(ctx, 'request', None)
    user = getattr(request, 'scope', {}).get('user') if request is not None else None
    token = getattr(user, 'access_token', None)
    subject = getattr(token, 'subject', None)
    if not subject:
        return None
    claims: dict[str, Any] = dict(getattr(token, 'claims', None) or {})
    return f'{claims.get("iss") or ""}#{subject}'


def required_scope(name: str, effect: str, open_world: bool) -> str:
    if name.split('_', 1)[0] in DISPATCH_MODULES or (open_world and effect != 'read'):
        return DISPATCH
    return READ if effect == 'read' else WRITE


class Introspection:
    """The SDK's `TokenVerifier`: RFC 7662 at the Node's authorization server, the answer turned into the SDK's
    `AccessToken`, whose `resource` the SDK's bearer middleware compares with this server's resource URL."""

    def __init__(self, found: Exposure, audience: str, transport: Any = None) -> None:
        self.exposure = found
        self.audience = audience
        self.transport = transport

    async def introspect(self, token: str) -> dict[str, Any] | None:
        import httpx
        basic = base64.b64encode(f'{RESOURCE_SERVER}:{self.exposure.credential}'.encode()).decode()
        try:
            async with httpx.AsyncClient(timeout=5, transport=self.transport) as client:
                answer = await client.post(self.exposure.introspection, data={'token': token},
                                           headers={'Authorization': f'Basic {basic}'})
        except httpx.HTTPError:
            return None
        if answer.status_code != 200:
            return None
        body: Any = answer.json()
        if not isinstance(body, dict):
            return None
        claims = cast(dict[str, Any], body)
        return claims if claims.get('active') is True else None

    async def verify_token(self, token: str) -> AccessToken | None:
        claims = await self.introspect(token)
        if claims is None or claims.get('aud') != self.audience or claims.get('iss') != self.exposure.public:
            return None
        return AccessToken(token=token, client_id=str(claims.get('client_id', '')),
                           scopes=str(claims.get('scope', '')).split(), expires_at=int(claims.get('exp') or 0) or None,
                           resource=str(claims['aud']), subject=str(claims.get('sub') or '') or None,
                           claims={'iss': claims.get('iss'), 'username': claims.get('username')})


class Asserted:
    """The SDK's `TokenVerifier` for a Metaform reached through the cloud broker: the bearer is the broker's assertion
    for this one request (typ `mf-assert+jwt`, EdDSA), checked against the broker's key set (`keys`, by key id), its
    issuer, this instance's resource URL, and the account this machine signed in as, so a request meant for another
    account or another machine is refused here even if the broker routed it wrongly. The scopes are capped again by
    what this machine allows (cloud_capability). `check` also matches the body's hash and spends the assertion's id,
    once; the tunnel calls it before the request reaches the app.

    Its times are judged by `clock`, the broker's time as this machine reckons it (the offset measured when the
    tunnel opened), with LEEWAY either side, so a machine whose own clock is off is not refused for it; `late` says
    when a refusal was for the time alone, so the person can be told to look at the clock."""

    TYP = 'mf-assert+jwt'
    LEEWAY = 30

    def __init__(self, issuer: str, audience: str, subject: str, keys: Callable[[str], Any],
                 allowed: tuple[str, ...], clock: Callable[[], float] | None = None) -> None:
        self.issuer = issuer
        self.audience = audience
        self.subject = subject
        self.keys = keys
        self.allowed = allowed
        self.clock = clock or time.time
        self.spent: dict[str, float] = {}
        self.late = 0.0  # how far off the last assertion refused for its time alone was, in seconds

    def claims(self, token: str) -> dict[str, Any] | None:
        import jwt
        self.late = 0.0
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            return None
        if header.get('typ') != self.TYP or header.get('alg') != 'EdDSA':
            return None
        key = self.keys(str(header.get('kid') or ''))
        if key is None:
            return None
        try:
            claims: dict[str, Any] = jwt.decode(token, key, algorithms=['EdDSA'], issuer=self.issuer,
                                                audience=self.audience, options={
                                                    'verify_exp': False, 'verify_iat': False, 'verify_nbf': False,
                                                    'require': ['exp', 'iat', 'iss', 'aud', 'sub', 'jti']})
        except jwt.PyJWTError:
            return None
        if claims.get('sub') != self.subject:
            return None
        try:
            issued, expires = float(claims['iat']), float(claims['exp'])
        except (TypeError, ValueError):
            return None
        now = self.clock()
        if issued > now + self.LEEWAY or expires < now - self.LEEWAY:
            self.late = issued - now
            return None
        return claims

    def check(self, token: str, body: bytes) -> dict[str, Any] | None:
        import hashlib
        claims = self.claims(token)
        if claims is None:
            return None
        hashed = base64.urlsafe_b64encode(hashlib.sha256(body).digest()).decode().rstrip('=')
        if claims.get('bh') != hashed:
            return None
        now = time.time()
        self.spent = {jti: until for jti, until in self.spent.items() if until > now}
        if str(claims['jti']) in self.spent:
            return None
        self.spent[str(claims['jti'])] = now + float(claims['exp']) - float(claims['iat']) + 2 * self.LEEWAY
        return claims

    async def verify_token(self, token: str) -> AccessToken | None:
        claims = self.claims(token)
        if claims is None:
            return None
        scopes = [scope for scope in str(claims.get('scope') or '').split() if scope in self.allowed]
        return AccessToken(token=token, client_id=str(claims.get('client_id') or ''), scopes=scopes,
                           expires_at=int(claims['exp']), resource=str(claims['aud']), subject=str(claims['sub']),
                           claims={'iss': claims['iss'], 'username': claims.get('username'),
                                   'client_name': claims.get('client_name')})


def scopes_up_to(capability: str) -> tuple[str, ...]:
    """The MCP scopes a capability level allows: read, then write, then dispatch."""
    order = (READ, WRITE, DISPATCH)
    level = {'read': 1, 'write': 2, 'dispatch': 3}.get(capability, 1)
    return order[:level]


def transport_security(found: Exposure) -> Any:
    """Host and Origin checks for the public name, as the SDK makes them for loopback: a browser page elsewhere
    cannot reach the server through DNS rebinding, and loopback stays allowed for the health check."""
    from mcp.server.transport_security import TransportSecuritySettings
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[found.host, '127.0.0.1:*', 'localhost:*', '[::1]:*'],
        allowed_origins=[found.public])


def auth_settings(found: Exposure) -> Any:
    """The SDK's resource-server settings: this server's resource URL, the Node as its authorization server, every
    token checked against the resource (RFC 8707), `mcp:read` needed for any request at all."""
    from mcp.server.auth.settings import AuthSettings
    # Validated from strings, so the issuer keeps its exact form with no trailing slash: RFC 8414 compares it as a
    # string, and a client refuses metadata whose issuer differs by a slash.
    return AuthSettings.model_validate({'issuer_url': found.public, 'resource_server_url': found.mcp,
                                        'required_scopes': [READ], 'validate_token_resource': True})


class ScopeGate:
    """Before a tool call reaches the server: a token short of the tool's scope gets 403 `insufficient_scope` with
    the scope it needs and the resource metadata's URL, so the client can step up, RFC 6750 section 3.1."""

    def __init__(self, app: Any, needs: Callable[[str], str | None], metadata_url: str,
                 ceiling: tuple[str, ...] | None = None) -> None:
        self.app = app
        self.needs = needs
        self.metadata_url = metadata_url
        self.ceiling = ceiling  # what this machine allows at most, behind the cloud broker (cloud_capability)

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope['type'] != 'http' or scope.get('method') != 'POST':
            await self.app(scope, receive, send)
            return
        body = b''
        more = True
        while more:
            message = await receive()
            body += message.get('body', b'')
            more = bool(message.get('more_body'))
        needed = self._needed(body)
        auth = scope.get('auth')
        held: set[str] = {str(one) for one in getattr(auth, 'scopes', ()) or ()}
        if needed and scope.get('user') is not None and needed not in held:
            said = f'This tool needs {needed}'
            if self.ceiling is not None and needed not in self.ceiling:  # no sign-in can give it: the owner decides
                said += (f', and this Metaform lets cloud AI tools have {" ".join(self.ceiling) or "nothing"} at most; '
                         'its owner can raise cloud_capability')
            challenge = (f'Bearer error="insufficient_scope", scope="{needed}", '
                         f'resource_metadata="{self.metadata_url}", '
                         f'error_description="{said}"')
            payload = json.dumps({'error': 'insufficient_scope', 'error_description': said + '.',
                                  'scope': needed}).encode()
            await send({'type': 'http.response.start', 'status': 403,
                        'headers': [(b'content-type', b'application/json'), (b'www-authenticate', challenge.encode()),
                                    (b'content-length', str(len(payload)).encode())]})
            await send({'type': 'http.response.body', 'body': payload})
            return
        sent = False

        async def replay() -> dict[str, Any]:
            nonlocal sent
            if sent:
                return await receive()
            sent = True
            return {'type': 'http.request', 'body': body, 'more_body': False}
        await self.app(scope, replay, send)

    def _needed(self, body: bytes) -> str | None:
        try:
            parsed = json.loads(body or b'null')
        except ValueError:
            return None
        messages = cast(list[Any], parsed) if isinstance(parsed, list) else [parsed]
        found: list[str] = []
        for message in messages:
            if isinstance(message, dict) and cast(dict[str, Any], message).get('method') == 'tools/call':
                params: Any = cast(dict[str, Any], message).get('params')
                name = cast(dict[str, Any], params).get('name', '') if isinstance(params, dict) else ''
                one = self.needs(str(name))
                if one:
                    found.append(one)
        order = (DISPATCH, WRITE, READ)
        return next((scope for scope in order if scope in found), None)


def protect(app: Any, found: Exposure, needs: Callable[[str], str | None],
            ceiling: tuple[str, ...] | None = None) -> None:
    """Put the scope gate in front of the `/mcp` route the SDK built, outside its bearer check, and have the
    resource's metadata offer read and write, the scopes an agent's ordinary work needs, so it asks for both at
    once; the authorization server grants what the Node's capability allows of them, and dispatch is asked for only
    when a tool needs it."""
    from mcp.server.auth.handlers.metadata import ProtectedResourceMetadataHandler
    from mcp.server.auth.routes import cors_middleware
    from mcp.shared.auth import ProtectedResourceMetadata
    from starlette.routing import Route
    path = '/.well-known/oauth-protected-resource' + found.path
    metadata_url = found.public + path
    document = ProtectedResourceMetadata.model_validate({
        'resource': found.mcp, 'authorization_servers': [found.public], 'scopes_supported': [READ, WRITE],
        'resource_name': 'Metaform'})
    described = [Route(path, endpoint=cors_middleware(ProtectedResourceMetadataHandler(document).handle,
                                                      ['GET', 'OPTIONS']), methods=['GET', 'OPTIONS'])]
    routes = app.router.routes
    for index, route in enumerate(routes):
        path = getattr(route, 'path', None)
        if path == '/mcp':
            route.app = ScopeGate(route.app, needs, metadata_url, ceiling)
        elif path == '/.well-known/oauth-protected-resource' + found.path:
            routes[index] = described[0]
