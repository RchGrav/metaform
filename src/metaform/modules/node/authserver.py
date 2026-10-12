"""The Node's own OAuth 2.1 authorization server, with passkeys for the people the owner lets in.

It is the authorization server the MCP authorization specification of 2026-07-28 describes, for the Node's two
protected resources, `https://<domain>/mcp` and `https://<domain>/a2a`, and it is the page's sign-in:

- Protected Resource Metadata (RFC 9728) is the MCP server's, from the MCP SDK; its `authorization_servers` names
  this server, whose Authorization Server Metadata (RFC 8414) is at `/.well-known/oauth-authorization-server`.
- Authorization code with PKCE S256 only; the protocol endpoints are the MCP Python SDK's own handlers
  (`mcp.server.auth.handlers`), so request parsing, PKCE verification, client authentication and error shapes are
  the SDK's. What this module supplies is the provider: storage, the sign-in, the consent and the policy.
- Clients identify themselves with Client ID Metadata Documents, fetched over HTTPS with the guards against
  server-side request forgery the draft asks for; Dynamic Client Registration, which the July specification
  deprecates, answers only when the owner turns `node_dcr` on for an older client.
- Every token names one resource (RFC 8707): the resource the client asked for, or, when it asked for none, the one
  its scopes all belong to. Scopes are capped by the instance's capability level, so a Node at `read` never grants a
  write and only a Node at `dispatch` can grant `mcp:dispatch`.
- The authorization response carries `iss` (RFC 9207), and the metadata says so.
- Access tokens live an hour; refresh tokens are rotated on every use and a reused one revokes its family (OAuth 2.1
  section 4.3.1); revocation is RFC 7009; resource servers check tokens by introspection (RFC 7662) on loopback with
  a credential of their own.
- People sign in with passkeys (WebAuthn Level 3, through Duo's `webauthn` library): there are no passwords. The
  owner's first passkey comes from the one-time link `metaform node init` prints; everyone else is invited with
  `metaform node invite <name>`, so the accounts are the allowlist.
- The page's session is this server's too: Caddy asks `/node/gate` before every page request.

In the broker role (metaform.ing, `Policy.broker`), the same server keeps nothing on disk but accounts and passkeys:
`SignedProvider` issues every code and token as a JWT signed with the Node's key (tokens.py), the key set is published
at `/.well-known/jwks.json`, the local service signs in with the device authorization grant (RFC 8628, device.py), and
each person's instances are resources of their own, `https://<domain>/mcp` for the one named `default` and
`https://<domain>/mcp/<instance>` for the others, reached through the broker (broker.py).
"""
from __future__ import annotations

import base64
import binascii
import hmac
import ipaddress
import json
import os
import secrets
import socket
import time
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, cast

import httpcore
import httpx
import jwt
from mcp.server.auth.handlers.authorize import AuthorizationHandler
from mcp.server.auth.handlers.register import RegistrationHandler
from mcp.server.auth.handlers.revoke import RevocationHandler
from mcp.server.auth.handlers.token import TokenHandler
from mcp.server.auth.middleware.client_auth import ClientAuthenticator
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    RegistrationError,
    TokenError,
    construct_redirect_uri,
)
from mcp.server.auth.settings import ClientRegistrationOptions
from mcp.shared.auth import OAuthClientInformationFull, OAuthMetadata, OAuthToken
from pydantic import AnyUrl
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route, request_response
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from metaform import home

from . import tokens
from .authstore import Account, AuthStore, digest
from .config import KNOWN_SCOPES, LABEL, scopes_for
from .device import DeviceGrants

ACCESS_SECONDS = 3600
REFRESH_SECONDS = 30 * 86400
CODE_SECONDS = 300
SESSION_SECONDS = 7 * 86400
CIMD_MAX_BYTES = 5 * 1024  # the Client ID Metadata Document draft's suggested ceiling
CIMD_TIMEOUT = 5.0
CIMD_MIN_CACHE, CIMD_MAX_CACHE, CIMD_DEFAULT_CACHE = 60, 86400, 600
LOOPBACK_HOSTS = ('127.0.0.1', '[::1]', 'localhost')
RESOURCE_SERVER = 'metaform-resource-server'  # the client id MCP and A2A introspect with
CLI_CLIENT, DEVICE_GRANT, TUNNEL_SCOPE = tokens.CLI_CLIENT, tokens.DEVICE_GRANT, tokens.TUNNEL_SCOPE
BROKER_SESSION_SECONDS = 3600
DEFAULT_INSTANCE = 'default'
DCR_SECONDS = 10 * 365 * 86400  # a registered client's id holds until its signing key leaves the key set


def store_path() -> Path:
    return home.home() / 'node' / 'auth.sqlite'


def introspection_secret_file() -> Path:
    """The resource servers' introspection credential, shared through the home's run folder, owner-readable only."""
    return home.home() / 'run' / 'node-introspection'


def introspection_secret(create: bool = False) -> str | None:
    path = introspection_secret_file()
    if path.exists():
        return path.read_text(encoding='utf-8').strip() or None
    if not create:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    made = secrets.token_urlsafe(32)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        handle.write(made)
    return made


def canonical(uri: str) -> str:
    """A resource URI as RFC 8707 compares it: lowercase scheme and host, no trailing slash, no fragment."""
    parts = urllib.parse.urlsplit(uri.strip())
    return urllib.parse.urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip('/'),
                                    parts.query, ''))


@dataclass(frozen=True)
class Policy:
    """What this instance is and may grant."""
    issuer: str
    capability: str = 'write'
    dcr: bool = False
    broker: bool = False
    member_dispatch: bool = False  # on a broker, whether an account that is not the owner may be granted dispatch

    @property
    def session_seconds(self) -> int:
        return BROKER_SESSION_SECONDS if self.broker else SESSION_SECONDS

    @property
    def tunnel(self) -> str:
        """The tunnel's resource: what the local service's access token is for."""
        return self.issuer + '/cloud/tunnel'

    def instance_resource(self, instance: str) -> str:
        return self.issuer + '/mcp' + ('' if instance == DEFAULT_INSTANCE else '/' + instance)

    def instance_of(self, resource: str) -> str | None:
        """On a broker, the instance a resource URL names: `default` for `/mcp`, `<label>` for `/mcp/<label>`."""
        if not self.broker:
            return None
        base = canonical(self.issuer + '/mcp')
        given = canonical(resource)
        if given == base:
            return DEFAULT_INSTANCE
        rest = given[len(base) + 1:] if given.startswith(base + '/') else ''
        return rest if LABEL.match(rest) and rest != DEFAULT_INSTANCE else None

    @property
    def rp_id(self) -> str:
        return urllib.parse.urlsplit(self.issuer).hostname or ''

    @property
    def resources(self) -> dict[str, str]:
        return {'mcp': self.issuer + '/mcp', 'a2a': self.issuer + '/a2a'}

    @property
    def grantable(self) -> dict[str, tuple[str, ...]]:
        """Scopes by resource URI; on a broker the default instance's, which every instance shares."""
        scoped = scopes_for(self.capability)
        if self.broker:
            return {self.resources['mcp']: scoped['mcp']}
        return {self.resources[name]: scoped[name] for name in self.resources}

    def granted(self, resource: str) -> tuple[str, ...]:
        if self.instance_of(resource) is not None:
            return scopes_for(self.capability)['mcp']
        return self.grantable.get(resource, ())

    @property
    def all_scopes(self) -> list[str]:
        listed = [scope for scopes in self.grantable.values() for scope in scopes]
        return [*listed, TUNNEL_SCOPE] if self.broker else listed

    @property
    def secure(self) -> bool:
        return self.issuer.startswith('https://')

    @property
    def cookie(self) -> str:
        return '__Host-metaform-session' if self.secure else 'metaform-session'

    def resource_for(self, asked: str | None, scopes: list[str] | None) -> str:
        """The one resource a token is for: the one asked, which must be this Node's, or the one the scopes name."""
        known = {canonical(uri): uri for uri in self.grantable}
        if asked and self.instance_of(asked) is not None:
            return self.instance_resource(self.instance_of(asked) or DEFAULT_INSTANCE)
        if self.broker and not asked:  # a host that names no resource reaches the instance named default
            return self.instance_resource(DEFAULT_INSTANCE)
        if asked:
            found = known.get(canonical(asked))
            if found is None:
                raise AuthorizeError('invalid_request', f'This server issues tokens only for {", ".join(known)}.')
            return found
        owners = {uri for uri, granted in self.grantable.items() for scope in (scopes or []) if scope in granted}
        if len(owners) == 1:
            return owners.pop()
        raise AuthorizeError('invalid_request', 'Name the resource the token is for (RFC 8707): '
                                                f'{" or ".join(self.grantable)}.')

    def scopes_for(self, resource: str, asked: list[str] | None) -> list[str]:
        """What a token for `resource` carries: of the scopes asked, those this Node's capability grants, as RFC 6749
        section 3.3 lets a server narrow a request and say so in the token response; with none asked, what the
        resource needs to work, the dispatch scope left for a step-up challenge. Nothing grantable is refused."""
        granted = list(self.granted(resource))
        kept = [scope for scope in granted if scope != 'mcp:dispatch'] if asked is None else \
            [scope for scope in granted if scope in asked]
        if not kept:
            raise AuthorizeError('invalid_scope', f'This Node, at capability {self.capability}, grants none of '
                                                  f'{" ".join(asked or [])} for {resource}.')
        return kept


# ---------------------------------------------------------------------------------------------------- clients

class LoopbackAwareClient(OAuthClientInformationFull):
    """A client whose loopback redirect URIs match on any port, RFC 8252 section 7.3, as native MCP clients pick a
    free port for each sign-in; every other redirect URI must match exactly."""

    def validate_redirect_uri(self, redirect_uri: AnyUrl | None) -> AnyUrl:
        if redirect_uri is not None and redirect_uri.scheme == 'http' and _loopback(redirect_uri.host):
            for registered in self.redirect_uris or []:
                if (registered.scheme == 'http' and registered.host == redirect_uri.host
                        and (registered.path or '/') == (redirect_uri.path or '/')
                        and registered.query == redirect_uri.query):
                    return redirect_uri
        return super().validate_redirect_uri(redirect_uri)


def _loopback(host: str | None) -> bool:
    return (host or '').strip('[]') in ('127.0.0.1', '::1', 'localhost')


def _cimd_url(client_id: str) -> bool:
    parts = urllib.parse.urlsplit(client_id)
    return parts.scheme == 'https' and bool(parts.hostname) and parts.path not in ('', '/') and not parts.fragment \
        and not parts.username and not parts.password


def _public_addresses(host: str, port: int) -> list[str]:
    """The addresses the host resolves to, when every one is on the public internet; none otherwise. A client id may
    not make this server fetch from its own network, the draft's SSRF guard."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        return []
    addresses = list(dict.fromkeys(str(info[4][0]) for info in infos))
    if not addresses or not all(ipaddress.ip_address(one.split('%')[0]).is_global for one in addresses):
        return []
    return addresses


class PublicOnly(httpcore.AsyncNetworkBackend):
    """Connects only to an address it has just checked is public, and to exactly that address: the name is resolved
    once, here, and the connection made to the address resolved, so a name that answers with a public address for
    the check and a private one for the connection (DNS rebinding) never reaches this server's own network. TLS still
    names and verifies the host, as httpcore passes the host name for SNI and the certificate check."""

    def __init__(self, inner: httpcore.AsyncNetworkBackend | None = None) -> None:
        self.inner: httpcore.AsyncNetworkBackend = inner or cast(httpcore.AsyncNetworkBackend, httpcore.AnyIOBackend())

    async def connect_tcp(self, host: str, port: int, timeout: float | None = None, local_address: str | None = None,
                          socket_options: Any = None) -> httpcore.AsyncNetworkStream:
        import anyio
        addresses = await anyio.to_thread.run_sync(_public_addresses, host, port)
        if not addresses:
            raise httpcore.ConnectError(f'{host} is not on a public address.')
        return await self.inner.connect_tcp(addresses[0], port, timeout=timeout, local_address=local_address,
                                            socket_options=socket_options)

    async def connect_unix_socket(self, path: str, timeout: float | None = None,
                                  socket_options: Any = None) -> httpcore.AsyncNetworkStream:
        raise httpcore.ConnectError('A client metadata document is fetched over the network only.')

    async def sleep(self, seconds: float) -> None:
        await self.inner.sleep(seconds)


class PublicTransport(httpx.AsyncHTTPTransport):
    """httpx's own transport over PublicOnly, with no proxy, so the address checked is the address reached."""

    def __init__(self, backend: httpcore.AsyncNetworkBackend | None = None) -> None:
        super().__init__(trust_env=False)
        self._pool = httpcore.AsyncConnectionPool(ssl_context=httpx.create_ssl_context(trust_env=False),
                                                  network_backend=PublicOnly(backend))


def _cache_seconds(header: str | None) -> float:
    for part in (header or '').split(','):
        name, _, value = part.strip().partition('=')
        if name.lower() == 'no-store':
            return CIMD_MIN_CACHE
        if name.lower() == 'max-age' and value.isdigit():
            return float(min(max(int(value), CIMD_MIN_CACHE), CIMD_MAX_CACHE))
    return CIMD_DEFAULT_CACHE


def check_document(client_id: str, document: Any) -> dict[str, Any]:
    """A Client ID Metadata Document this server can use, or ValueError saying why not: JSON with `client_id` equal
    to its URL, `client_name` and `redirect_uris`, each redirect URI loopback http or https, a public client."""
    data = cast(dict[str, Any], document) if isinstance(document, dict) else {}
    if data.get('client_id') != client_id:
        raise ValueError('The client metadata document names another client_id than its URL.')
    if not isinstance(data.get('client_name'), str) or not data['client_name'].strip():
        raise ValueError('The client metadata document has no client_name.')
    uris = data.get('redirect_uris')
    if not isinstance(uris, list) or not uris or not all(isinstance(one, str) for one in cast(list[Any], uris)):
        raise ValueError('The client metadata document has no redirect_uris.')
    for uri in cast(list[str], uris):
        parts = urllib.parse.urlsplit(uri)
        if parts.fragment or not (parts.scheme == 'https' or (parts.scheme == 'http' and _loopback(parts.hostname))):
            raise ValueError(f'Redirect URI {uri} is neither https nor loopback http.')
    method = data.get('token_endpoint_auth_method', 'none')
    if method != 'none':  # a shared secret cannot live in a public document; private_key_jwt is not supported here
        raise ValueError(f'token_endpoint_auth_method {method} is not supported; use none.')
    return data


async def fetch_document(client_id: str, transport: httpx.AsyncBaseTransport | None = None) -> tuple[dict[str, Any],
                                                                                                     float]:
    try:
        async with httpx.AsyncClient(timeout=CIMD_TIMEOUT, follow_redirects=False,
                                     transport=transport or PublicTransport(),
                                     headers={'Accept': 'application/json'}) as client, \
                client.stream('GET', client_id) as answer:
            return await _document(client_id, answer)
    except httpx.ConnectError as error:
        raise ValueError(f'The client metadata document could not be fetched: {error}.') from error


async def _document(client_id: str, answer: httpx.Response) -> tuple[dict[str, Any], float]:
    if answer.status_code != 200:
        raise ValueError(f'The client metadata document answered {answer.status_code}.')
    body = b''
    async for chunk in answer.aiter_bytes():
        body += chunk
        if len(body) > CIMD_MAX_BYTES:
            raise ValueError('The client metadata document is larger than 5 KB.')
    cache = _cache_seconds(answer.headers.get('cache-control'))
    try:
        document = json.loads(body)
    except ValueError as error:
        raise ValueError('The client metadata document is not JSON.') from error
    return check_document(client_id, document), cache


# ---------------------------------------------------------------------------------------------------- the provider

class Provider:
    """The SDK's `OAuthAuthorizationServerProvider`: storage and policy behind the SDK's protocol handlers."""

    def __init__(self, store: AuthStore, policy: Policy, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.store = store
        self.policy = policy
        self.transport = transport

    def _client(self, client_id: str, data: dict[str, Any]) -> OAuthClientInformationFull:
        granted = data.get('grant_types') or ['authorization_code', 'refresh_token']
        return LoopbackAwareClient(
            client_id=client_id, client_name=data.get('client_name'), redirect_uris=data.get('redirect_uris'),
            token_endpoint_auth_method=data.get('token_endpoint_auth_method') or 'none',
            client_secret=data.get('client_secret'), grant_types=granted, response_types=['code'],
            scope=' '.join(KNOWN_SCOPES), client_uri=data.get('client_uri') or None)  # narrowed in authorize

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        kept = self.store.client(client_id)
        if _cimd_url(client_id):
            if kept is not None and kept[1] == 'cimd' and kept[2] > time.time():
                return self._client(client_id, kept[0])
            try:
                document, cache = await fetch_document(client_id, self.transport)
            except (ValueError, httpx.HTTPError):
                return None
            self.store.save_client(client_id, document, 'cimd', time.time() + cache)
            return self._client(client_id, document)
        if kept is not None and kept[1] == 'dcr' and self.policy.dcr:
            return self._client(client_id, kept[0])
        return None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        if not self.policy.dcr:
            raise RegistrationError('invalid_client_metadata', 'Dynamic client registration is off on this Node.')
        for uri in client_info.redirect_uris or []:
            if not (uri.scheme == 'https' or (uri.scheme == 'http' and _loopback(uri.host))):
                raise RegistrationError('invalid_redirect_uri', f'{uri} is neither https nor loopback http.')
        data = client_info.model_dump(mode='json', exclude_none=True)
        self.store.save_client(client_info.client_id, data, 'dcr', float('inf'))

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        resource = self.policy.resource_for(params.resource, params.scopes)
        scopes = self.policy.scopes_for(resource, params.scopes)
        held = self.store.hold(client.client_id, {
            'state': params.state, 'scopes': scopes, 'code_challenge': params.code_challenge,
            'redirect_uri': str(params.redirect_uri), 'explicit': params.redirect_uri_provided_explicitly,
            'resource': resource, 'client_name': client.client_name or client.client_id})
        return f'{self.policy.issuer}/node/consent?request={held}'

    def issue_code(self, record: dict[str, Any]) -> str:
        """The authorization code for an approved request, kept as its hash until used or expired."""
        return self.store.add_code(record, CODE_SECONDS)

    async def load_authorization_code(self, client: OAuthClientInformationFull,
                                      authorization_code: str) -> AuthorizationCode | None:
        found = self.store.code(authorization_code)
        if found is None:
            return None
        record, expires, used = found
        if used:
            self.store.use_code(authorization_code)  # a second use revokes what the first gave
            return None
        return AuthorizationCode(code=authorization_code, scopes=record['scopes'], expires_at=expires,
                                 client_id=record['client_id'], code_challenge=record['code_challenge'],
                                 redirect_uri=AnyUrl(record['redirect_uri']),
                                 redirect_uri_provided_explicitly=record['explicit'], resource=record['resource'],
                                 subject=record['account'])

    def _tokens(self, client_id: str, family: str, account: str, scopes: list[str], resource: str) -> OAuthToken:
        access, _ = self.store.add_token('access', family, client_id, account, scopes, resource, ACCESS_SECONDS)
        refresh, _ = self.store.add_token('refresh', family, client_id, account, scopes, resource, REFRESH_SECONDS)
        return OAuthToken(access_token=access, token_type='Bearer', expires_in=ACCESS_SECONDS,
                          scope=' '.join(scopes), refresh_token=refresh)

    async def exchange_authorization_code(self, client: OAuthClientInformationFull,
                                          authorization_code: AuthorizationCode) -> OAuthToken:
        if not self.store.use_code(authorization_code.code):
            raise TokenError('invalid_grant', 'The authorization code was already used.')
        account = self.store.account(id=authorization_code.subject or '')
        if account is None or account.disabled:
            raise TokenError('invalid_grant', 'The account that approved this code is no longer allowed.')
        return self._tokens(client.client_id, digest(authorization_code.code), account.id,
                            authorization_code.scopes, authorization_code.resource or '')

    async def load_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str) -> RefreshToken | None:
        found = self.store.token(refresh_token)
        if found is None or found.kind != 'refresh' or found.revoked:
            return None
        if found.rotated:
            self.store.rotate(refresh_token)  # a retired refresh token used again revokes its family
            return None
        return RefreshToken(token=refresh_token, client_id=found.client_id, scopes=list(found.scopes),
                            expires_at=int(found.expires), resource=found.resource, subject=found.account)

    async def exchange_refresh_token(self, client: OAuthClientInformationFull, refresh_token: RefreshToken,
                                     scopes: list[str]) -> OAuthToken:
        found = self.store.token(refresh_token.token)
        if found is None or not self.store.rotate(refresh_token.token):
            raise TokenError('invalid_grant', 'The refresh token was already used.')
        account = self.store.account(id=found.account)
        if account is None or account.disabled:
            raise TokenError('invalid_grant', 'The account is no longer allowed.')
        allowed = set(self.policy.grantable.get(found.resource, ()))
        kept = [scope for scope in scopes if scope in allowed]  # a capability lowered since then lowers the grant
        return self._tokens(client.client_id, found.family, found.account, kept, found.resource)

    async def load_access_token(self, token: str) -> AccessToken | None:
        found = self.store.token(token)
        if found is None or found.kind != 'access' or found.revoked or found.expires < time.time():
            return None
        return AccessToken(token=token, client_id=found.client_id, scopes=list(found.scopes),
                           expires_at=int(found.expires), resource=found.resource, subject=found.account)

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        found = self.store.token(token.token)
        if found is not None:
            self.store.revoke_family(found.family)

    def introspect(self, token: str) -> dict[str, Any]:
        """RFC 7662's answer: active with its claims, or only `active: false`."""
        found = self.store.token(token)
        if found is None or found.kind != 'access' or found.revoked or found.expires < time.time():
            return {'active': False}
        account = self.store.account(id=found.account)
        if account is None or account.disabled:
            return {'active': False}
        return {'active': True, 'client_id': found.client_id, 'scope': ' '.join(found.scopes),
                'exp': int(found.expires), 'aud': found.resource, 'sub': account.id, 'username': account.name,
                'iss': self.policy.issuer, 'token_type': 'Bearer'}


class SignedProvider(Provider):
    """The broker's provider: every authorization code and token a signed JWT, so nothing about a grant is written.
    A token is checked by its signature, its audience, its account's generation and, in memory, whether its grant was
    revoked; refresh tokens rotate, and one presented after it was rotated revokes the grant (tokens.Families)."""

    def __init__(self, store: AuthStore, policy: Policy, keys: tokens.Keys, families: tokens.Families | None = None,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        super().__init__(store, policy, transport)
        self.signer = tokens.Signer(keys, policy.issuer)
        self.generations = tokens.Generations(store)
        self.families = families or tokens.Families()
        self.spent = tokens.Replay()  # authorization codes used, each until it expires

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        if client_id == CLI_CLIENT:
            return OAuthClientInformationFull(client_id=CLI_CLIENT, client_name='Metaform', redirect_uris=None,
                                              token_endpoint_auth_method='none',
                                              grant_types=[DEVICE_GRANT, 'refresh_token'], scope=TUNNEL_SCOPE)
        if self.policy.dcr and not _cimd_url(client_id):
            claims = self.signer.read(client_id, tokens.CLIENT_ID, self.policy.issuer)
            registered: Any = claims.get('md') if claims else None
            if isinstance(registered, dict):
                data = dict(cast(dict[str, Any], registered))
                if data.get('token_endpoint_auth_method', 'none') != 'none':
                    data['client_secret'] = self._client_secret(client_id)
                return self._client(client_id, data)
            return None
        return await super().get_client(client_id)

    def _client_secret(self, client_id: str) -> str | None:
        try:
            kid = str(jwt.get_unverified_header(client_id).get('kid') or '')
        except jwt.PyJWTError:
            return None
        return self.signer.keys.derive(kid, 'client-secret:' + client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        """Dynamic client registration with nothing kept (node_dcr, for an AI host that cannot use a metadata
        document): the client id the SDK made is replaced by a signed JWT of the registered metadata, so the broker
        reads the client back from its id after any restart, and a secret, for a client that asked for one, is
        derived from the key that signed the id, never stored. Such a client lives as long as that key: a rotation
        ends it when the retired key leaves the key set, and a revocation at once."""
        if not self.policy.dcr:
            raise RegistrationError('invalid_client_metadata', 'Dynamic client registration is off on this Node.')
        for uri in client_info.redirect_uris or []:
            if not (uri.scheme == 'https' or (uri.scheme == 'http' and _loopback(uri.host))):
                raise RegistrationError('invalid_redirect_uri', f'{uri} is neither https nor loopback http.')
        data = client_info.model_dump(mode='json', exclude_none=True)
        for kept_out in ('client_id', 'client_secret', 'client_id_issued_at', 'client_secret_expires_at'):
            data.pop(kept_out, None)
        client_info.client_id = self.signer.mint(tokens.CLIENT_ID, {'aud': self.policy.issuer, 'md': data},
                                                 DCR_SECONDS)
        if client_info.client_secret is not None:
            client_info.client_secret = self._client_secret(client_info.client_id)

    def issue_code(self, record: dict[str, Any]) -> str:
        """The code as a signed JWT: nothing secret is in it (PKCE protects it), and it names the generation it was
        approved under, so signing out everywhere ends a code not yet exchanged too."""
        found = self.generations.current(str(record.get('account') or ''))
        return self.signer.mint(tokens.CODE, {'aud': self.policy.issuer, 'gen': found[0] if found else -1,
                                              'auth_time': int(time.time()), **record}, CODE_SECONDS)

    def allowed(self, account_id: str) -> Account | None:
        account = self.store.account(id=account_id)
        return account if account is not None and not account.disabled else None

    def issue(self, client_id: str, client_name: str, account: Account, scopes: list[str], resource: str,
              family: str, seq: int, auth_time: int, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        """An access token for `resource` and the grant's next refresh token, as the token endpoint answers them."""
        now = int(time.time())
        found = self.generations.current(account.id)
        claims: dict[str, Any] = {'sub': account.id, 'username': account.name, 'client_id': client_id,
                                  'cname': client_name, 'scope': ' '.join(scopes), 'gen': found[0] if found else 0,
                                  'fam': family, **(extra or {})}
        access = self.signer.mint(tokens.ACCESS, {**claims, 'aud': resource}, tokens.ACCESS_SECONDS, now=now)
        until = min(now + tokens.REFRESH_SECONDS, auth_time + tokens.REFRESH_CAP_SECONDS)
        refresh = self.signer.mint(tokens.REFRESH, {**claims, 'aud': self.policy.issuer, 'resource': resource,
                                                    'seq': seq, 'auth_time': auth_time}, until - now, now=now)
        if seq == 0:
            self.families.start(family, until)
        return {'access_token': access, 'token_type': 'DPoP' if extra and 'cnf' in extra else 'Bearer',
                'expires_in': tokens.ACCESS_SECONDS, 'scope': ' '.join(scopes), 'refresh_token': refresh}

    def live(self, claims: dict[str, Any] | None) -> dict[str, Any] | None:
        """The claims of a token still in force: its account's generation current, its grant not revoked."""
        if claims is None or not self.generations.valid(str(claims.get('sub') or ''), claims.get('gen')):
            return None
        return None if self.families.revoked(str(claims.get('fam') or '')) else claims

    def access(self, token: str, audience: str | None = None) -> dict[str, Any] | None:
        return self.live(self.signer.read(token, tokens.ACCESS, audience))

    def refreshed(self, token: str) -> dict[str, Any] | None:
        """A refresh token's claims when it is live and is the newest of its grant; one already rotated revokes it."""
        claims = self.live(self.signer.read(token, tokens.REFRESH, self.policy.issuer))
        if claims is None:
            return None
        family, seq = str(claims.get('fam') or ''), claims.get('seq')
        mark = self.families.mark(family)
        if not isinstance(seq, int) or (mark is not None and seq < mark):
            self.families.revoke(family, float(claims.get('exp') or time.time()))
            return None
        return claims

    async def load_authorization_code(self, client: OAuthClientInformationFull,
                                      authorization_code: str) -> AuthorizationCode | None:
        claims = self.signer.read(authorization_code, tokens.CODE, self.policy.issuer)
        if claims is None:
            return None
        if self.spent.seen.get(str(claims['jti']), 0) > time.time():  # a second use: what the first gave is revoked
            self.families.revoke(str(claims['jti']), time.time() + tokens.REFRESH_CAP_SECONDS)
            return None
        return AuthorizationCode(code=authorization_code, scopes=list(claims['scopes']), expires_at=float(claims['exp']),
                                 client_id=str(claims['client_id']), code_challenge=str(claims['code_challenge']),
                                 redirect_uri=AnyUrl(str(claims['redirect_uri'])),
                                 redirect_uri_provided_explicitly=bool(claims['explicit']),
                                 resource=str(claims['resource']), subject=str(claims['account']))

    async def exchange_authorization_code(self, client: OAuthClientInformationFull,
                                          authorization_code: AuthorizationCode) -> OAuthToken:
        claims = self.signer.read(authorization_code.code, tokens.CODE, self.policy.issuer) or {}
        family = str(claims.get('jti') or '')
        if not family or not self.spent.first(family, float(claims.get('exp') or 0) + 60):
            raise TokenError('invalid_grant', 'The authorization code was already used.')
        account = self.allowed(authorization_code.subject or '')
        if account is None or not self.generations.valid(account.id, claims.get('gen')):
            raise TokenError('invalid_grant', 'The account that approved this code is no longer allowed.')
        issued = self.issue(client.client_id, str(claims.get('cname') or client.client_id), account,
                            authorization_code.scopes, authorization_code.resource or '', family, 0,
                            int(claims.get('auth_time') or claims['iat']))
        return OAuthToken.model_validate(issued)

    async def load_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str) -> RefreshToken | None:
        claims = self.refreshed(refresh_token)
        if claims is None or claims.get('client_id') != client.client_id:
            return None
        return RefreshToken(token=refresh_token, client_id=str(claims['client_id']),
                            scopes=str(claims.get('scope') or '').split(), expires_at=int(claims['exp']),
                            resource=str(claims.get('resource') or ''), subject=str(claims['sub']))

    def rotate_refresh(self, claims: dict[str, Any], scopes: list[str]) -> dict[str, Any]:
        """Spend a refresh token's place in its grant and issue the next pair, scopes narrowed to what is still
        grantable; TokenError when it was already spent."""
        account = self.allowed(str(claims['sub']))
        if account is None:
            raise TokenError('invalid_grant', 'The account is no longer allowed.')
        if not self.families.advance(str(claims['fam']), int(claims['seq']), float(claims['exp'])):
            raise TokenError('invalid_grant', 'The refresh token was already used.')
        resource = str(claims.get('resource') or '')
        allowed: set[str] = {*self.policy.granted(resource), *([TUNNEL_SCOPE] if resource == self.policy.tunnel else [])}
        kept = [scope for scope in scopes if scope in allowed]
        extra = {key: claims[key] for key in ('cnf', 'inst') if key in claims}
        return self.issue(str(claims['client_id']), str(claims.get('cname') or ''), account, kept, resource,
                          str(claims['fam']), int(claims['seq']) + 1, int(claims['auth_time']), extra)

    async def exchange_refresh_token(self, client: OAuthClientInformationFull, refresh_token: RefreshToken,
                                     scopes: list[str]) -> OAuthToken:
        claims = self.signer.read(refresh_token.token, tokens.REFRESH, self.policy.issuer)
        if claims is None:
            raise TokenError('invalid_grant', 'The refresh token is not valid.')
        return OAuthToken.model_validate(self.rotate_refresh(claims, scopes))

    async def load_access_token(self, token: str) -> AccessToken | None:
        claims = self.access(token)
        if claims is None:
            return None
        return AccessToken(token=token, client_id=str(claims.get('client_id') or ''),
                           scopes=str(claims.get('scope') or '').split(), expires_at=int(claims['exp']),
                           resource=str(claims.get('aud') or ''), subject=str(claims['sub']),
                           claims={'iss': claims['iss'], 'username': claims.get('username')})

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        claims = self.signer.read(token.token, tokens.ACCESS) or self.signer.read(token.token, tokens.REFRESH)
        if claims is not None:
            self.families.revoke(str(claims.get('fam') or ''), time.time() + tokens.REFRESH_CAP_SECONDS)

    def introspect(self, token: str) -> dict[str, Any]:
        claims = self.access(token)
        if claims is None:
            return {'active': False}
        return {'active': True, 'client_id': claims.get('client_id'), 'scope': claims.get('scope'),
                'exp': claims['exp'], 'aud': claims.get('aud'), 'sub': claims['sub'],
                'username': claims.get('username'), 'iss': claims['iss'], 'token_type': 'Bearer'}


# ---------------------------------------------------------------------------------------------------- the server

def metadata_document(policy: Policy) -> dict[str, Any]:
    """RFC 8414's document; a broker adds its key set, the device authorization endpoint (RFC 8628) and DPoP (RFC
    9449), which the SDK's model does not name."""
    made = metadata(policy).model_dump(mode='json', exclude_none=True)
    if policy.broker:
        base = policy.issuer
        made['jwks_uri'] = base + '/.well-known/jwks.json'
        made['device_authorization_endpoint'] = base + '/oauth/device_authorization'
        made['grant_types_supported'] = ['authorization_code', 'refresh_token', DEVICE_GRANT]
        made['dpop_signing_alg_values_supported'] = list(tokens.DPOP_ALGORITHMS)
    return made


def metadata(policy: Policy) -> OAuthMetadata:
    """RFC 8414, validated from strings so the issuer is exactly the identifier clients compare, no slash added."""
    base = policy.issuer
    methods = ['none', 'client_secret_post', 'client_secret_basic'] if policy.dcr else ['none']
    return OAuthMetadata.model_validate({
        'issuer': base, 'authorization_endpoint': base + '/oauth/authorize', 'token_endpoint': base + '/oauth/token',
        'registration_endpoint': base + '/oauth/register' if policy.dcr else None,
        'scopes_supported': policy.all_scopes, 'response_types_supported': ['code'],
        'grant_types_supported': ['authorization_code', 'refresh_token'],
        'token_endpoint_auth_methods_supported': methods, 'revocation_endpoint': base + '/oauth/revoke',
        'revocation_endpoint_auth_methods_supported': methods, 'introspection_endpoint': base + '/oauth/introspect',
        'introspection_endpoint_auth_methods_supported': ['client_secret_basic'],
        'code_challenge_methods_supported': ['S256'], 'client_id_metadata_document_supported': True,
        'authorization_response_iss_parameter_supported': True})


class AddIssuer:
    """Every redirect the authorization endpoint answers with carries `iss`, errors included, RFC 9207 section 2,
    since the metadata says it does; the SDK's error redirects do not add it themselves."""

    def __init__(self, app: ASGIApp, issuer: str) -> None:
        self.app = app
        self.issuer = issuer

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def sending(message: Message) -> None:
            if message['type'] == 'http.response.start' and message['status'] in (302, 303, 307):
                headers = [(name, value) for name, value in message.get('headers', [])]
                for index, (name, value) in enumerate(headers):
                    if name.lower() == b'location':
                        location = str(value.decode('latin-1'))
                        query = urllib.parse.parse_qs(urllib.parse.urlsplit(location).query)
                        if 'iss' not in query and ('code' in query or 'error' in query):
                            headers[index] = (name, construct_redirect_uri(location, iss=self.issuer).encode())
                message = {**message, 'headers': headers}
            await send(message)
        await self.app(scope, receive, sending)


def _page(name: str, **fills: str) -> str:
    text = resources.files('metaform.modules.node').joinpath('resources', name).read_text(encoding='utf-8')
    for key, value in fills.items():
        text = text.replace('{{' + key + '}}', value)
    return text


def _escape(text: str) -> str:
    return (text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
            .replace("'", '&#39;'))


def _safe_next(target: str | None) -> str:
    """Only a path on this server: never another host, so sign-in cannot be made into an open redirect."""
    if not target or not target.startswith('/') or target.startswith('//') or '\\' in target:
        return '/'
    return target


class Node:
    """The authorization server's routes, as one Starlette app."""

    def __init__(self, store: AuthStore, policy: Policy, transport: httpx.AsyncBaseTransport | None = None, *,
                 keys: tokens.Keys | None = None, families: tokens.Families | None = None) -> None:
        self.store = store
        self.policy = policy
        self.keys = keys
        self.provider: Provider = Provider(store, policy, transport) if keys is None else \
            SignedProvider(store, policy, keys, families, transport)
        # On a broker, whether an account's instance is connected now, and what each account has connected; the broker
        # sets these, so the consent and account pages can say so.
        self.connected: Callable[[str, str], bool] = lambda account_id, instance: False
        self.instances: Callable[[str], list[str]] = lambda account_id: []
        self.extra_routes: list[Any] = []
        self.device_grants = DeviceGrants()  # the local service's pending sign-ins, on a broker (device.py)
        self.dpop_seen = tokens.Replay()
        # On a broker, whether a request to the token or revocation endpoint may go ahead, by what it names: a grant
        # the server signed (`key`), or nothing valid (None, charged to the address it came from). The broker sets it.
        self.token_gate: Callable[[Request, str | None], bool] = lambda request, key: True

    @property
    def signed(self) -> SignedProvider:
        if not isinstance(self.provider, SignedProvider):
            raise TypeError('This Node issues stored tokens; signed ones are the broker\'s.')
        return self.provider

    # ------------------------------------------------------------------------------------------------ sessions

    def signed_in(self, request: Request) -> tuple[Account, str] | None:
        session = request.cookies.get(self.policy.cookie)
        return self.store.session(session) if session else None

    def _with_session(self, response: Response, account: Account) -> Response:
        seconds = self.policy.session_seconds
        session, _ = self.store.open_session(account, seconds)
        response.set_cookie(self.policy.cookie, session, max_age=seconds, path='/', secure=self.policy.secure,
                            httponly=True, samesite='lax')
        return response

    def _same_origin(self, request: Request) -> bool:
        origin = request.headers.get('origin')
        return origin is None or origin == self.policy.issuer

    # ------------------------------------------------------------------------------------------------ endpoints

    async def health(self, request: Request) -> Response:
        return JSONResponse({'ok': True, 'owner': self.store.owner_exists()})

    async def gate(self, request: Request) -> Response:
        """Caddy's forward_auth: 200 with the account for a signed-in request, else sign-in for a page load and
        401 for anything else."""
        found = self.signed_in(request)
        if found is not None:
            return Response(status_code=200, headers={'X-Metaform-Account': found[0].name})
        method = request.headers.get('x-forwarded-method', 'GET')
        if method == 'GET' and 'text/html' in request.headers.get('accept', ''):
            target = _safe_next(request.headers.get('x-forwarded-uri'))
            return RedirectResponse(f'/node/signin?next={urllib.parse.quote(target, safe="")}', status_code=302)
        return JSONResponse({'error': 'sign in at /node/signin'}, status_code=401)

    async def signin_page(self, request: Request) -> Response:
        return HTMLResponse(_page('signin.html', next=_escape(_safe_next(request.query_params.get('next')))),
                            headers={'Cache-Control': 'no-store'})

    async def setup_page(self, request: Request) -> Response:
        return HTMLResponse(_page('setup.html'), headers={'Cache-Control': 'no-store'})

    async def script(self, request: Request) -> Response:
        return Response(_page('passkey.js'), media_type='text/javascript', headers={'Cache-Control': 'no-cache'})

    async def _json(self, request: Request) -> dict[str, Any]:
        try:
            body = await request.json()
        except ValueError:
            return {}
        return cast(dict[str, Any], body) if isinstance(body, dict) else {}

    async def login_options(self, request: Request) -> Response:
        if not self._same_origin(request):
            return JSONResponse({'error': 'foreign origin'}, status_code=403)
        options = generate_authentication_options(rp_id=self.policy.rp_id,
                                                  user_verification=UserVerificationRequirement.REQUIRED)
        ceremony = self.store.challenge(options.challenge, 'login', None)
        return JSONResponse({'ceremony': ceremony, 'options': json.loads(options_to_json(options))})

    async def login_verify(self, request: Request) -> Response:
        if not self._same_origin(request):
            return JSONResponse({'error': 'foreign origin'}, status_code=403)
        body = await self._json(request)
        taken = self.store.take_challenge(str(body.get('ceremony', '')), 'login')
        credential = body.get('credential')
        if taken is None or not isinstance(credential, dict):
            return JSONResponse({'error': 'The sign-in expired; try again.'}, status_code=400)
        found = self.store.passkey(str(cast(dict[str, Any], credential).get('id', '')))
        if found is None:
            return JSONResponse({'error': 'This passkey is not enrolled here.'}, status_code=403)
        account, public_key, count = found
        try:
            verified = verify_authentication_response(
                credential=cast(dict[str, Any], credential), expected_challenge=taken[0],
                expected_rp_id=self.policy.rp_id, expected_origin=self.policy.issuer,
                credential_public_key=public_key, credential_current_sign_count=count, require_user_verification=True)
        except (InvalidAuthenticationResponse, ValueError, KeyError, binascii.Error):
            return JSONResponse({'error': 'The passkey could not be verified.'}, status_code=403)
        self.store.used_passkey(bytes_to_base64url(verified.credential_id), verified.new_sign_count)
        return self._with_session(JSONResponse({'next': _safe_next(str(body.get('next') or '/'))}), account)

    async def register_options(self, request: Request) -> Response:
        if not self._same_origin(request):
            return JSONResponse({'error': 'foreign origin'}, status_code=403)
        body = await self._json(request)
        account = self.store.invited(str(body.get('invite', '')))
        if account is None:
            signed = self.signed_in(request)  # a signed-in person may add another passkey to their own account
            account = signed[0] if signed and not body.get('invite') else None
        if account is None:
            return JSONResponse({'error': 'This setup link is used, expired or unknown. Ask the owner for a new one.'},
                                status_code=403)
        options = generate_registration_options(
            rp_id=self.policy.rp_id, rp_name='Metaform', user_name=account.name, user_display_name=account.name,
            user_id=account.id.encode(), authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.REQUIRED, user_verification=UserVerificationRequirement.REQUIRED),
            exclude_credentials=[PublicKeyCredentialDescriptor(id=base64.urlsafe_b64decode(one + '=' * (-len(one) % 4)))
                                 for one in self.store.passkey_ids(account)])
        ceremony = self.store.challenge(options.challenge, 'register', account.id)
        return JSONResponse({'ceremony': ceremony, 'options': json.loads(options_to_json(options))})

    async def register_verify(self, request: Request) -> Response:
        if not self._same_origin(request):
            return JSONResponse({'error': 'foreign origin'}, status_code=403)
        body = await self._json(request)
        taken = self.store.take_challenge(str(body.get('ceremony', '')), 'register')
        credential = body.get('credential')
        if taken is None or not isinstance(credential, dict):
            return JSONResponse({'error': 'The setup expired; open the link again.'}, status_code=400)
        account = self.store.account(id=taken[1] or '')
        invite = str(body.get('invite') or '')
        if account is None or account.disabled or (invite and self.store.invited(invite) != account):
            return JSONResponse({'error': 'This setup link is used, expired or unknown.'}, status_code=403)
        try:
            verified = verify_registration_response(
                credential=cast(dict[str, Any], credential), expected_challenge=taken[0],
                expected_rp_id=self.policy.rp_id, expected_origin=self.policy.issuer, require_user_verification=True)
        except (InvalidRegistrationResponse, ValueError, KeyError, binascii.Error):
            return JSONResponse({'error': 'The passkey could not be verified.'}, status_code=400)
        response: Any = cast(dict[str, Any], credential).get('response')
        transports: Any = cast(dict[str, Any], response).get('transports') if isinstance(response, dict) else None
        listed = [str(one) for one in cast(list[Any], transports)] if isinstance(transports, list) else []
        self.store.add_passkey(account, bytes_to_base64url(verified.credential_id), verified.credential_public_key,
                               verified.sign_count, listed)
        if invite:
            self.store.use_invite(invite)
        return self._with_session(JSONResponse({'next': '/'}), account)

    async def signout(self, request: Request) -> Response:
        if not self._same_origin(request):
            return JSONResponse({'error': 'foreign origin'}, status_code=403)
        session = request.cookies.get(self.policy.cookie)
        if session:
            self.store.close_session(session)
        response = RedirectResponse('/node/signin', status_code=303)
        response.delete_cookie(self.policy.cookie, path='/', secure=self.policy.secure, httponly=True, samesite='lax')
        return response

    async def consent_page(self, request: Request) -> Response:
        held_id = request.query_params.get('request', '')
        held = self.store.held(held_id)
        if held is None:
            return HTMLResponse(_page('message.html', title='This request expired',
                                      text='Start the connection again from your AI tool.'), status_code=400)
        signed = self.signed_in(request)
        if signed is None:
            target = urllib.parse.quote(f'/node/consent?request={held_id}', safe='')
            return RedirectResponse(f'/node/signin?next={target}', status_code=302)
        account, csrf = signed
        client_id, params = held
        redirect = urllib.parse.urlsplit(str(params['redirect_uri']))
        warning = ''
        if _loopback(redirect.hostname):
            warning = ('<p class="warn">This client receives the result on this computer (localhost). Approve only '
                       'if you started this connection from an AI tool on the computer you are using now.</p>')
        scopes = ''.join(f'<li><code>{_escape(scope)}</code></li>' for scope in self._scopes(account, params['scopes']))
        resource = _escape(params['resource'])
        instance = self.policy.instance_of(params['resource'])
        if instance is not None:  # a broker: the machine it reaches, and whether it is there now
            now = 'connected now' if self.connected(account.id, instance) else 'not connected now'
            resource += f'<br><small>Your Metaform named <strong>{_escape(instance)}</strong>, {now}</small>'
        return HTMLResponse(_page(
            'consent.html', client=_escape(str(params['client_name'])), client_id=_escape(client_id),
            redirect_host=_escape(redirect.hostname or ''), resource=resource, scopes=scopes,
            warning=warning, account=_escape(account.name), request=_escape(held_id), csrf=_escape(csrf)),
            headers={'Cache-Control': 'no-store', 'X-Frame-Options': 'DENY',
                     'Content-Security-Policy': "frame-ancestors 'none'"})

    async def consent(self, request: Request) -> Response:
        if not self._same_origin(request):
            return JSONResponse({'error': 'foreign origin'}, status_code=403)
        form = await request.form()
        signed = self.signed_in(request)
        if signed is None or not hmac.compare_digest(str(form.get('csrf', '')), signed[1]):
            return HTMLResponse(_page('message.html', title='Sign in again', text='Your session ended.'),
                                status_code=403)
        held_id = str(form.get('request', ''))
        held = self.store.held(held_id)
        if held is None:
            return HTMLResponse(_page('message.html', title='This request expired',
                                      text='Start the connection again from your AI tool.'), status_code=400)
        self.store.release(held_id)
        client_id, params = held
        if form.get('decision') != 'approve':
            target = construct_redirect_uri(params['redirect_uri'], error='access_denied', state=params['state'],
                                            iss=self.policy.issuer)
            return RedirectResponse(target, status_code=303)
        code = self.provider.issue_code({
            'client_id': client_id, 'account': signed[0].id, 'scopes': self._scopes(signed[0], params['scopes']),
            'resource': params['resource'], 'redirect_uri': params['redirect_uri'], 'explicit': params['explicit'],
            'code_challenge': params['code_challenge'], 'cname': str(params.get('client_name') or client_id)})
        target = construct_redirect_uri(params['redirect_uri'], code=code, state=params['state'],
                                        iss=self.policy.issuer)
        return RedirectResponse(target, status_code=303)

    def _scopes(self, account: Account, scopes: list[str]) -> list[str]:
        """On a broker, dispatch only for the owner unless the operator lets members have it: the account's role is
        the server's cap, as the person's own machine keeps its own (cloud_capability)."""
        if self.policy.broker and account.role != 'owner' and not self.policy.member_dispatch:
            return [scope for scope in scopes if scope != 'mcp:dispatch']
        return scopes

    async def introspect(self, request: Request) -> Response:
        """RFC 7662, for the resource servers on loopback, each request authenticated with their credential."""
        expected = introspection_secret()
        scheme, _, given = request.headers.get('authorization', '').partition(' ')
        try:
            client, _, secret = base64.b64decode(given).decode().partition(':')
        except (ValueError, UnicodeDecodeError, binascii.Error):
            client, secret = '', ''
        if (expected is None or scheme.lower() != 'basic' or client != RESOURCE_SERVER
                or not hmac.compare_digest(secret.encode(), expected.encode())):
            return JSONResponse({'error': 'invalid_client'}, status_code=401,
                                headers={'WWW-Authenticate': 'Basic realm="introspection"'})
        form = await request.form()
        return JSONResponse(self.provider.introspect(str(form.get('token', ''))), headers={'Cache-Control': 'no-store'})

    # ------------------------------------------------------------------------------------------------ the app

    def app(self) -> Starlette:
        authenticator = ClientAuthenticator(self.provider)  # pyright: ignore[reportArgumentType]

        def cors(app: ASGIApp) -> ASGIApp:
            return CORSMiddleware(app, allow_origins='*', allow_methods=['GET', 'POST', 'OPTIONS'],
                                  allow_headers=['mcp-protocol-version'])
        authorize = AddIssuer(request_response(AuthorizationHandler(self.provider).handle),  # pyright: ignore
                              self.policy.issuer)
        token = cors(request_response(TokenHandler(self.provider, authenticator).handle))  # pyright: ignore
        revoke = cors(request_response(RevocationHandler(self.provider, authenticator).handle))  # pyright: ignore
        document = metadata_document(self.policy)

        async def described(_: Request) -> Response:
            return JSONResponse(document, headers={'Cache-Control': 'public, max-age=3600'})
        if self.keys is not None:  # signed tokens: the local service's grants first, the hosts' to the SDK
            from .device import revocation_endpoint, token_endpoint
            token = cors(request_response(token_endpoint(self, TokenHandler(self.provider, authenticator))))  # pyright: ignore
            revoke = cors(request_response(revocation_endpoint(self)))
        routes = [
            Route('/.well-known/oauth-authorization-server', cors(request_response(described)),
                  methods=['GET', 'OPTIONS']),
            Route('/oauth/authorize', authorize, methods=['GET', 'POST']),
            Route('/oauth/token', token, methods=['POST', 'OPTIONS']),
            Route('/oauth/revoke', revoke, methods=['POST', 'OPTIONS']),
            Route('/oauth/introspect', self.introspect, methods=['POST']),
            Route('/node/health', self.health, methods=['GET']),
            Route('/node/gate', self.gate, methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']),
            Route('/node/signin', self.signin_page, methods=['GET']),
            Route('/node/setup', self.setup_page, methods=['GET']),
            Route('/node/passkey.js', self.script, methods=['GET']),
            Route('/node/passkey/login/options', self.login_options, methods=['POST']),
            Route('/node/passkey/login/verify', self.login_verify, methods=['POST']),
            Route('/node/passkey/register/options', self.register_options, methods=['POST']),
            Route('/node/passkey/register/verify', self.register_verify, methods=['POST']),
            Route('/node/signout', self.signout, methods=['POST']),
            Route('/node/consent', self.consent_page, methods=['GET']),
            Route('/node/consent', self.consent, methods=['POST']),
        ]
        if self.policy.dcr:
            options = ClientRegistrationOptions(enabled=True, valid_scopes=self.policy.all_scopes,
                                                default_scopes=self.policy.all_scopes)
            register = cors(request_response(RegistrationHandler(self.provider, options).handle))  # pyright: ignore
            routes.append(Route('/oauth/register', register, methods=['POST', 'OPTIONS']))
        if self.keys is not None:
            from .device import routes as device_routes
            keys = self.keys

            async def jwks(_: Request) -> Response:
                return JSONResponse(keys.jwks(), headers={'Cache-Control': 'public, max-age=300'})
            routes += [Route('/.well-known/jwks.json', cors(request_response(jwks)), methods=['GET', 'OPTIONS']),
                       *device_routes(self)]
        return Starlette(routes=[*routes, *self.extra_routes])


def bootstrap(store: AuthStore, folder: Path) -> str | None:
    """Import the owner's one-time setup record `node init` wrote, once; returns the owner's name when it did."""
    path = folder / 'owner-invite.json'
    if not path.is_file():
        return None
    record = json.loads(path.read_text(encoding='utf-8'))
    account = store.add_account(str(record['account']), 'owner')
    if store.passkey_ids(account):
        return None  # already enrolled: the record has done its work
    store.invite(account, hashed=str(record['sha256']), expires=float(record['expires']))
    return account.name


def keys_folder() -> Path:
    """The broker's signing keys: its identity, owner-readable only, on the home volume."""
    return home.home() / 'node' / 'keys'


def make_broker(policy: Policy, store: AuthStore, *, replay: str = 'memory', limits: Any = None,
                transport: httpx.AsyncBaseTransport | None = None) -> Any:
    """The broker role's one app: the authorization server, the device sign-in and account pages, the key set, the
    hosts' `/mcp` and the machines' `/cloud/tunnel`, in one process, since the generations, the device codes and the
    routing table are shared in memory with no channel between processes. Returns the Broker, whose `app()` serves
    it and whose `server()` runs it."""
    from .broker import Broker
    families = tokens.Families(store if replay == 'durable' else None)
    node = Node(store, policy, transport, keys=tokens.Keys(keys_folder()), families=families)
    return Broker(node, limits)


def serve(policy: Policy, port: int, bootstrap_folder: Path, *, replay: str = 'memory') -> None:
    import uvicorn

    from .authstore import open_store
    store = open_store(store_path(), policy.broker, (replay == 'durable') if policy.broker else None)
    owner = bootstrap(store, bootstrap_folder)
    if owner:
        print(f'Owner {owner} can enrol a passkey with the link metaform node init printed.', flush=True)
    # No access log: what passes is nobody's to keep here, and the broker's paths name instances.
    def config(app: Any) -> Any:
        return uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning', proxy_headers=False,
                              access_log=False, ws_max_size=2 * 1024 * 1024, ws_ping_interval=20, ws_ping_timeout=20)
    if policy.broker:
        carrier = make_broker(policy, store, replay=replay)
        print(f'Metaform broker for {policy.issuer} on 127.0.0.1:{port}', flush=True)
        carrier.server(config(carrier.app())).run()
        return
    introspection_secret(create=True)
    print(f'Metaform Node authorization server for {policy.issuer} on 127.0.0.1:{port}', flush=True)
    uvicorn.Server(config(Node(store, policy).app())).run()


# The page helpers, for device.py's pages.
escape, page, safe_next = _escape, _page, _safe_next
