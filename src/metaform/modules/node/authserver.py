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
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, cast

import httpx
from mcp.server.auth.handlers.authorize import AuthorizationHandler
from mcp.server.auth.handlers.metadata import MetadataHandler
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

from .authstore import Account, AuthStore, digest
from .config import KNOWN_SCOPES, scopes_for

ACCESS_SECONDS = 3600
REFRESH_SECONDS = 30 * 86400
CODE_SECONDS = 300
SESSION_SECONDS = 7 * 86400
CIMD_MAX_BYTES = 5 * 1024  # the Client ID Metadata Document draft's suggested ceiling
CIMD_TIMEOUT = 5.0
CIMD_MIN_CACHE, CIMD_MAX_CACHE, CIMD_DEFAULT_CACHE = 60, 86400, 600
LOOPBACK_HOSTS = ('127.0.0.1', '[::1]', 'localhost')
RESOURCE_SERVER = 'metaform-resource-server'  # the client id MCP and A2A introspect with


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

    @property
    def rp_id(self) -> str:
        return urllib.parse.urlsplit(self.issuer).hostname or ''

    @property
    def resources(self) -> dict[str, str]:
        return {'mcp': self.issuer + '/mcp', 'a2a': self.issuer + '/a2a'}

    @property
    def grantable(self) -> dict[str, tuple[str, ...]]:
        """Scopes by resource URI."""
        scoped = scopes_for(self.capability)
        return {self.resources[name]: scoped[name] for name in self.resources}

    @property
    def all_scopes(self) -> list[str]:
        return [scope for scopes in self.grantable.values() for scope in scopes]

    @property
    def secure(self) -> bool:
        return self.issuer.startswith('https://')

    @property
    def cookie(self) -> str:
        return '__Host-metaform-session' if self.secure else 'metaform-session'

    def resource_for(self, asked: str | None, scopes: list[str] | None) -> str:
        """The one resource a token is for: the one asked, which must be this Node's, or the one the scopes name."""
        known = {canonical(uri): uri for uri in self.grantable}
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
        granted = list(self.grantable.get(resource, ()))
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


def _public_address(host: str, port: int) -> bool:
    """Whether every address the host resolves to is on the public internet: a client id may not make this server
    fetch from its own network, the draft's SSRF guard."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        return False
    addresses = {info[4][0] for info in infos}
    return bool(addresses) and all(ipaddress.ip_address(str(one).split('%')[0]).is_global for one in addresses)


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
    parts = urllib.parse.urlsplit(client_id)
    if transport is None and not _public_address(parts.hostname or '', parts.port or 443):
        raise ValueError('The client metadata document is not on a public address.')
    async with httpx.AsyncClient(timeout=CIMD_TIMEOUT, follow_redirects=False, transport=transport,
                                 headers={'Accept': 'application/json'}) as client, \
            client.stream('GET', client_id) as answer:
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


# ---------------------------------------------------------------------------------------------------- the server

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

    def __init__(self, store: AuthStore, policy: Policy, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.store = store
        self.policy = policy
        self.provider = Provider(store, policy, transport)

    # ------------------------------------------------------------------------------------------------ sessions

    def signed_in(self, request: Request) -> tuple[Account, str] | None:
        session = request.cookies.get(self.policy.cookie)
        return self.store.session(session) if session else None

    def _with_session(self, response: Response, account: Account) -> Response:
        session, _ = self.store.open_session(account, SESSION_SECONDS)
        response.set_cookie(self.policy.cookie, session, max_age=SESSION_SECONDS, path='/', secure=self.policy.secure,
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
        scopes = ''.join(f'<li><code>{_escape(scope)}</code></li>' for scope in params['scopes'])
        return HTMLResponse(_page(
            'consent.html', client=_escape(str(params['client_name'])), client_id=_escape(client_id),
            redirect_host=_escape(redirect.hostname or ''), resource=_escape(params['resource']), scopes=scopes,
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
        code = self.store.add_code({'client_id': client_id, 'account': signed[0].id, 'scopes': params['scopes'],
                                    'resource': params['resource'], 'redirect_uri': params['redirect_uri'],
                                    'explicit': params['explicit'], 'code_challenge': params['code_challenge']},
                                   CODE_SECONDS)
        target = construct_redirect_uri(params['redirect_uri'], code=code, state=params['state'],
                                        iss=self.policy.issuer)
        return RedirectResponse(target, status_code=303)

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
        routes = [
            Route('/.well-known/oauth-authorization-server', cors(request_response(
                MetadataHandler(metadata(self.policy)).handle)), methods=['GET', 'OPTIONS']),
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
        return Starlette(routes=routes)


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


def serve(policy: Policy, port: int, bootstrap_folder: Path) -> None:
    import uvicorn
    store = AuthStore(store_path())
    introspection_secret(create=True)
    owner = bootstrap(store, bootstrap_folder)
    if owner:
        print(f'Owner {owner} can enrol a passkey with the link metaform node init printed.', flush=True)
    print(f'Metaform Node authorization server for {policy.issuer} on 127.0.0.1:{port}', flush=True)
    uvicorn.Server(uvicorn.Config(Node(store, policy).app(), host='127.0.0.1', port=port, log_level='warning',
                                  proxy_headers=False)).run()
