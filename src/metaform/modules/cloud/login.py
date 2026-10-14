"""Signing this machine in to an account at a cloud broker (metaform.ing by default), and keeping it signed in.

`metaform cloud login` runs the OAuth 2.0 device authorization grant (RFC 8628) as the built-in client `metaform-cli`:
this machine makes a key pair (P-256) and proves it holds it on every request with DPoP (RFC 9449), the broker shows a
code here and a page there, and the person approves on the page with their passkey. The tokens that come back are
bound to the key, so the refresh token alone, copied out of a log or an error report, is useless.

What is kept, in `<home>/cloud/credentials.json`, readable by its owner alone: the issuer, the account, the instance
name, the refresh token, the DPoP private key, and the broker's key set as fetched over TLS at login, so the
assertions the broker signs for each request can be checked here without asking anyone. Access tokens live in memory
only. A rotated refresh token replaces the file atomically. The key set is replaced whole whenever the broker sends
it (each connection's `ready`), so a key the broker revoked is dropped here too.

This machine's clock need not agree with the broker's: the offset is taken from each answer's `Date` header and from
the broker's time in `ready`, and DPoP proofs and assertion checks use the broker's time, so a laptop or WSL clock a
few minutes off still signs in and connects.
"""
from __future__ import annotations

import base64
import contextlib
import email.utils
import hashlib
import json
import os
import secrets
import socket
import time
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm, OKPAlgorithm

from metaform import home
from metaform.module import Stop

CLIENT = 'metaform-cli'
DEVICE_GRANT = 'urn:ietf:params:oauth:grant-type:device_code'
SCOPE = 'tunnel:connect'
TIMEOUT = 15.0
JWKS_EVERY = 60.0  # an unknown key id fetches the key set again at most this often
LEEWAY = 60  # seconds a token's times may differ from the broker's clock as this machine reckons it


def folder() -> Path:
    return home.home() / 'cloud'


def credentials_file() -> Path:
    return folder() / 'credentials.json'


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip('=')


def check_url(url: str) -> str:
    """The broker's origin: https, or plain http only on this machine (a test broker), never with a path."""
    given = url.strip().rstrip('/')
    parts = urllib.parse.urlsplit(given)
    local = parts.hostname in ('127.0.0.1', 'localhost', '::1')
    if parts.scheme not in ('https', 'http') or (parts.scheme == 'http' and not local) or not parts.hostname \
            or parts.path or parts.query or parts.fragment:
        raise Stop(f'cloud_url must be an https origin such as https://metaform.ing, not {url!r}.',
                   'metaform set --cloud-url https://metaform.ing')
    return given


# ---------------------------------------------------------------------------------------------------- DPoP

def new_key() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


def key_jwk(key: ec.EllipticCurvePrivateKey, private: bool = False) -> dict[str, Any]:
    return dict(ECAlgorithm.to_jwk(key if private else key.public_key(), as_dict=True))


def key_from(jwk: dict[str, Any]) -> ec.EllipticCurvePrivateKey:
    loaded = ECAlgorithm.from_jwk(json.dumps(jwk))
    if not isinstance(loaded, ec.EllipticCurvePrivateKey):
        raise Stop('The saved DPoP key is not a private key.', 'metaform cloud login')
    return loaded


def offset(answer: httpx.Response) -> float | None:
    """How far the broker's clock is ahead of this machine's, from the answer's `Date` header (RFC 9110, to the
    second); None without one."""
    with contextlib.suppress(TypeError, ValueError, IndexError):
        said = answer.headers.get('date')
        if said:
            return email.utils.parsedate_to_datetime(said).timestamp() - time.time()
    return None


def proof(key: ec.EllipticCurvePrivateKey, method: str, url: str, access_token: str | None = None,
          skew: float = 0.0) -> str:
    """A DPoP proof for one request, RFC 9449 section 4.2, dated by the broker's clock (`skew` ahead of this one)."""
    claims: dict[str, Any] = {'jti': secrets.token_urlsafe(16), 'htm': method, 'htu': url,
                              'iat': int(time.time() + skew)}
    if access_token is not None:
        claims['ath'] = b64(hashlib.sha256(access_token.encode()).digest())
    return jwt.encode(claims, key, algorithm='ES256', headers={'typ': 'dpop+jwt', 'jwk': key_jwk(key)})


# ---------------------------------------------------------------------------------------------------- credentials

@dataclass
class Credentials:
    issuer: str
    account: str
    username: str
    instance: str
    resource: str
    refresh_token: str
    dpop: dict[str, Any]
    jwks: dict[str, Any]
    token_endpoint: str
    revocation_endpoint: str
    jwks_uri: str
    fetched: float = field(default=0.0)
    skew: float = field(default=0.0)  # how far the broker's clock is ahead of this machine's; never saved

    @property
    def key(self) -> ec.EllipticCurvePrivateKey:
        return key_from(self.dpop)

    @property
    def tunnel_url(self) -> str:
        return self.issuer + '/cloud/tunnel'

    @property
    def socket_url(self) -> str:
        return ('wss://' if self.issuer.startswith('https://') else 'ws://') + self.issuer.split('://', 1)[1] + \
            '/cloud/tunnel'

    def public_key(self, kid: str) -> Any:
        """The broker's public key by its id, from the key set saved here; None for one not in it."""
        for one in cast(list[Any], self.jwks.get('keys') or []):
            if isinstance(one, dict) and cast(dict[str, Any], one).get('kid') == kid:
                return OKPAlgorithm.from_jwk(json.dumps(one))
        return None

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__ if name not in ('fetched', 'skew')}


def load() -> Credentials | None:
    try:
        data: Any = json.loads(credentials_file().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        return Credentials(**{key: value for key, value in cast(dict[str, Any], data).items()
                              if key in Credentials.__dataclass_fields__})
    except TypeError:
        return None


def save(made: Credentials) -> None:
    """Written whole to a temporary file the owner alone reads, then moved over the old one, so a crash never leaves
    half a file and the refresh token is never readable by anyone else, even for a moment."""
    path = credentials_file()
    home.mkdir_private(path.parent)
    with contextlib.suppress(OSError):
        path.parent.chmod(0o700)
    temporary = path.with_name(f'.credentials.{secrets.token_hex(4)}.tmp')
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        json.dump(made.to_dict(), handle, indent=2)
    os.replace(temporary, path)


def forget() -> bool:
    path = credentials_file()
    if not path.exists():
        return False
    path.unlink()
    return True


# ---------------------------------------------------------------------------------------------------- the grant

def _json(answer: httpx.Response) -> dict[str, Any]:
    try:
        body: Any = answer.json()
    except ValueError:
        body = {}
    return cast(dict[str, Any], body) if isinstance(body, dict) else {}


def metadata(base: str, client: httpx.Client) -> tuple[dict[str, Any], float]:
    """The broker's authorization server metadata, RFC 8414, whose issuer must be exactly the URL asked, and how far
    its clock is ahead of this machine's."""
    try:
        answer = client.get(base + '/.well-known/oauth-authorization-server')
    except httpx.HTTPError as error:
        raise Stop(f'{base} cannot be reached: {error}.', 'check cloud_url and your connection') from None
    found = _json(answer)
    if answer.status_code != 200 or found.get('issuer') != base or not found.get('device_authorization_endpoint'):
        raise Stop(f'{base} is not a Metaform cloud broker (no device sign-in in its metadata).',
                   'metaform set --cloud-url https://metaform.ing')
    return found, _skew(answer, 0.0)


@dataclass
class Started:
    """A device sign-in under way: what to show the person, and what to poll with."""
    meta: dict[str, Any]
    key: ec.EllipticCurvePrivateKey
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires: float
    interval: float
    instance: str
    skew: float = 0.0


def start(base: str, instance: str, client: httpx.Client, device_name: str | None = None) -> Started:
    meta, skew = metadata(base, client)
    key = new_key()
    endpoint = str(meta['device_authorization_endpoint'])
    answer = client.post(endpoint, data={'client_id': CLIENT, 'scope': SCOPE, 'instance': instance,
                                         'device_name': device_name or socket.gethostname()},
                         headers={'DPoP': proof(key, 'POST', endpoint, skew=skew)})
    found = _json(answer)
    if answer.status_code != 200 or 'device_code' not in found:
        raise Stop(f'The broker refused the sign-in: {found.get("error_description") or answer.status_code}.',
                   'metaform cloud login')
    return Started(meta, key, str(found['device_code']), str(found['user_code']), str(found['verification_uri']),
                   str(found.get('verification_uri_complete') or found['verification_uri']),
                   time.time() + float(found.get('expires_in') or 600), float(found.get('interval') or 5), instance,
                   skew)


def finish(started: Started, client: httpx.Client, sleep: Callable[[float], None] = time.sleep,
           confirm: Callable[[str], bool] | None = None) -> Credentials:
    """Poll the token endpoint as RFC 8628 section 3.4 says until the person approves, denies or the code expires;
    then fetch the key set and keep everything in the credentials file. With `confirm`, the person is asked whether
    the account that approved is theirs before anything is kept: a code approved by someone else's account (one who
    guessed it, or who sent it) would connect this machine to theirs. Declined, the sign-in is revoked and nothing is
    kept."""
    endpoint = str(started.meta['token_endpoint'])
    interval = started.interval
    while True:
        if time.time() > started.expires:
            raise Stop('The code expired before it was approved.', 'metaform cloud login')
        answer = client.post(endpoint, data={'grant_type': DEVICE_GRANT, 'device_code': started.device_code,
                                             'client_id': CLIENT},
                             headers={'DPoP': proof(started.key, 'POST', endpoint, skew=started.skew)})
        started.skew = _skew(answer, started.skew)
        found = _json(answer)
        error = found.get('error')
        if answer.status_code == 200 and found.get('refresh_token'):
            break
        if error == 'authorization_pending':
            sleep(interval)
            continue
        if error == 'slow_down':
            interval += 5
            sleep(interval)
            continue
        if error == 'access_denied':
            raise Stop('The sign-in was denied on the page.', 'metaform cloud login, and approve it')
        raise Stop(f'The sign-in did not finish: {found.get("error_description") or error or answer.status_code}.',
                   'metaform cloud login')
    jwks_uri = str(started.meta['jwks_uri'])
    keys = _json(client.get(jwks_uri))
    issuer = str(started.meta['issuer'])
    made = Credentials(issuer=issuer, account='', username='', instance=started.instance, resource='',
                       refresh_token=str(found['refresh_token']), dpop=key_jwk(started.key, private=True), jwks=keys,
                       token_endpoint=endpoint, revocation_endpoint=str(started.meta.get('revocation_endpoint') or ''),
                       jwks_uri=jwks_uri)
    made.skew = started.skew
    claims = read_access(made, str(found['access_token']))
    made.account, made.username = str(claims['sub']), str(claims.get('username') or '')
    made.resource = issuer + '/mcp' + ('' if started.instance == 'default' else '/' + started.instance)
    if confirm is not None and not confirm(made.username):
        revoke(made, client)
        raise Stop(f'Not signed in: the code was approved by the account {made.username}, which you did not '
                   'confirm as yours. That sign-in was revoked and nothing was kept.',
                   'metaform cloud login, and approve it yourself, signed in to your own account')
    save(made)
    return made


def _skew(answer: httpx.Response, known: float) -> float:
    found = offset(answer)
    return known if found is None else found


def read_access(made: Credentials, token: str) -> dict[str, Any]:
    """An access token's claims, checked against the key set just fetched, so the account named is the one the
    broker signed for. Its times are judged by the broker's clock, LEEWAY either side, as this machine's may be
    off."""
    try:
        kid = str(jwt.get_unverified_header(token).get('kid') or '')
        key = made.public_key(kid)
        if key is None:
            raise jwt.PyJWTError('unknown key')
        claims: dict[str, Any] = jwt.decode(token, key, algorithms=['EdDSA'], issuer=made.issuer,
                                            audience=made.tunnel_url, options={
                                                'verify_exp': False, 'verify_iat': False, 'verify_nbf': False,
                                                'require': ['exp', 'iat']})
    except jwt.PyJWTError as error:
        raise Stop(f'The broker\'s token does not check out against its key set: {error}.',
                   'metaform cloud login') from None
    now = time.time() + made.skew
    if float(claims['exp']) < now - LEEWAY or float(claims['iat']) > now + LEEWAY:
        raise Stop('The broker\'s token is out of date by this machine\'s clock, even allowing for the offset '
                   'measured.', 'set this machine\'s clock to update automatically, then metaform cloud login')
    return claims


class Refused(Exception):
    """The broker no longer accepts this machine's refresh token: it was revoked, the account signed out everywhere,
    or it was used elsewhere. Only a new login helps."""


async def refresh(made: Credentials, client: httpx.AsyncClient) -> tuple[str, float]:
    """A fresh access token and when it expires, the refresh token rotated and saved; Refused when the grant is over,
    httpx.HTTPError when the broker cannot be reached. A proof refused for its time, after this machine's clock
    jumped, is made again once on the clock the answer reports."""
    async def ask() -> tuple[httpx.Response, dict[str, Any], float]:
        answer = await client.post(made.token_endpoint, data={'grant_type': 'refresh_token', 'client_id': CLIENT,
                                                              'refresh_token': made.refresh_token},
                                   headers={'DPoP': proof(made.key, 'POST', made.token_endpoint, skew=made.skew)})
        used, made.skew = made.skew, _skew(answer, made.skew)
        return answer, _json(answer), used
    answer, found, used = await ask()
    if found.get('error') == 'invalid_dpop_proof' and abs(made.skew - used) > 10:
        answer, found, _ = await ask()
    if answer.status_code != 200 or not found.get('access_token'):
        if found.get('error') == 'invalid_dpop_proof' and abs(made.skew) > 30:
            raise httpx.HTTPError(f'This machine\'s clock is {abs(made.skew):.0f} seconds off the broker\'s: set it '
                                  'to update automatically.')
        if found.get('error') in ('invalid_grant', 'invalid_dpop_proof', 'invalid_client'):
            raise Refused(str(found.get('error_description') or found.get('error')))
        raise httpx.HTTPError(f'The broker answered {answer.status_code}.')
    made.refresh_token = str(found['refresh_token'])
    save(made)
    return str(found['access_token']), time.time() + float(found.get('expires_in') or 600)


async def fresh_keys(made: Credentials, client: httpx.AsyncClient) -> bool:
    """The key set fetched again, at most once a minute: for an assertion signed by a key this machine has not seen,
    after the broker rotated its key."""
    if time.time() - made.fetched < JWKS_EVERY:
        return False
    made.fetched = time.time()
    try:
        answer = await client.get(made.jwks_uri)
    except httpx.HTTPError:
        return False
    found = _json(answer)
    if answer.status_code != 200 or not isinstance(found.get('keys'), list):
        return False
    made.jwks = found
    save(made)
    return True


def revoke(made: Credentials, client: httpx.Client) -> bool:
    """RFC 7009 for this machine's refresh token; True when the broker took it."""
    if not made.revocation_endpoint:
        return False
    try:
        answer = client.post(made.revocation_endpoint, data={'token': made.refresh_token, 'client_id': CLIENT,
                                                             'token_type_hint': 'refresh_token'})
    except httpx.HTTPError:
        return False
    return answer.status_code == 200
