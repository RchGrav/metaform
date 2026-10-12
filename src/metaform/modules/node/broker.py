"""The broker: AI hosts talk MCP to `https://<domain>/mcp`, and each request is carried down the person's own tunnel to
the Metaform on their machine, which runs it.

- An AI host (claude.ai, ChatGPT, any remote MCP client) signs in to the person's account with standard MCP OAuth and
  sends its bearer token here. The broker checks it (signature, audience, generation, grant) and never passes it on:
  the MCP security guidance forbids token passthrough. In its place each request carries an assertion the broker signs
  for that one request, naming the account, the client, the scopes and the instance's resource URL, and a hash of the
  body, valid for 60 seconds; the person's machine checks it against the key set it saved at login and refuses one
  meant for another account, another machine or another body.
- The person's machine dials out to `/cloud/tunnel` (tunnel.py on its side, frames.py for the wire), with its own
  DPoP-bound token from the device grant, so it opens no port. Tunnels are routed by (account, instance), held in
  memory only: a restart costs every machine an automatic reconnect.
- One resource per instance: `/mcp` reaches the instance named `default`, `/mcp/<instance>` a named one, each with its
  own Protected Resource Metadata (RFC 9728), so a token approved for one machine is useless at another.
- Offline: a tool call is answered with an error result the model reads and passes on ("run metaform cloud connect on
  <instance>"), any other request with a JSON-RPC error, a notification or stream with 503. This is the only time the
  broker reads a request body; online it passes through unread.
- Held-open streams (a GET, or a POST to `subscriptions/listen`, which the person's machine refuses unless its
  `Mcp-Method` header says so) are counted per account and client and per tunnel, live an hour at most, and never take
  one of the slots requests wait for, so streams a host leaves open cannot shut out its calls.
- Credit is the broker's to keep: a machine may send a stream only the bytes the broker granted it (256 KiB to
  start, given back as the host reads), and one that sends more is disconnected (4008), so a machine that ignores
  credit can fill no memory but its own streams' windows; what a tunnel holds at once is capped too (`buffered`).
- On the way down the broker tells every machine to come back after its own delay of one to five seconds (`goaway`),
  before the server closes their sockets, so a restart is not followed by every machine at once.
- Nothing about what passes is logged: no bodies, tokens, query strings, tool names or instance names. The record of
  who called which tool is kept on the person's machine.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import random
import time
from collections.abc import AsyncGenerator, AsyncIterable, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, cast

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route, WebSocketRoute
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.websockets import WebSocket, WebSocketDisconnect

from metaform import frames

from . import tokens
from .authserver import DEFAULT_INSTANCE, Node
from .config import LABEL
from .device import source

READ, WRITE, DISPATCH = 'mcp:read', 'mcp:write', 'mcp:dispatch'
MCP_SCOPES = (READ, WRITE, DISPATCH)
OFFLINE_CODE = -32050


@dataclass(frozen=True)
class Limits:
    """What one account, one tunnel and one request may take of the broker."""
    request: int = 1024 * 1024  # a host's request body
    response: int = 8 * 1024 * 1024  # a response that is not a stream
    frame: int = frames.MAX_FRAME_BODY
    credit: int = frames.CREDIT  # what a machine may send on a stream before the broker grants more
    buffered: int = 16 * 1024 * 1024  # answers held at once for one tunnel, beyond which a request is answered 502
    streams: int = 32  # requests open at once per tunnel
    stream_wait: float = 10.0  # how long a request waits for a free stream before 503
    rate: float = 10.0  # requests per second per account, after a burst
    burst: float = 30.0
    streams_per_client: int = 8  # held-open streams per account and client (GET, subscriptions/listen)
    listens: int = 16  # held-open streams per tunnel, apart from the request slots
    stream_seconds: float = 3600.0  # a held-open stream's life; the host opens it again
    instances: int = 5  # connected machines per account
    connect_every: float = 2.0  # seconds between tunnel connections per account
    keepalive: float = 25.0  # an idle SSE stream gets a comment this often, so proxies keep it
    hello_wait: float = 10.0
    watch: float = 20.0  # how often a tunnel's token, its signing key and the generation are checked again
    per_address: float = 20.0  # sign-in pages and device requests per minute per source
    other_per_address: float = 600.0  # any other unauthenticated request per minute per source
    grant_rate: float = 1.0  # token and revocation requests per second per grant the server signed, after a burst
    grant_burst: float = 10.0
    unknown_per_address: float = 120.0  # token and revocation requests naming nothing valid, per minute per source
    global_rate: float = 200.0  # unauthenticated requests per second in all, after each source's own limit


class Buckets:
    """Token buckets by key, in memory."""

    def __init__(self, rate: float, burst: float) -> None:
        self.rate = rate
        self.burst = burst
        self.held: dict[str, tuple[float, float]] = {}

    def take(self, key: str) -> bool:
        now = time.monotonic()
        if len(self.held) > 10000:
            self.held = {k: v for k, v in self.held.items() if now - v[1] < 600}
        level, then = self.held.get(key, (self.burst, now))
        level = min(self.burst, level + (now - then) * self.rate)
        if level < 1:
            self.held[key] = (level, now)
            return False
        self.held[key] = (level - 1, now)
        return True


@dataclass
class Stream:
    """One request on a tunnel: what the machine sent for it not yet passed on, the credit it still holds, and the
    bytes of it the tunnel is holding."""
    number: int
    window: int = frames.CREDIT
    holding: int = 0
    queue: asyncio.Queue[tuple[str, Any]] = field(default_factory=lambda: asyncio.Queue[tuple[str, Any]]())


@dataclass
class Tunnel:
    """One person's machine, connected: the socket, its streams, what it grants and how long its token holds."""
    socket: WebSocket
    account: str
    username: str
    instance: str
    allows: tuple[str, ...]
    jkt: str
    generation: int
    expires: float
    kid: str = ''  # the key that signed its token: revoked, and the tunnel closes
    streams: dict[int, Stream] = field(default_factory=dict[int, Stream])
    next_stream: int = 1
    slots: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(32))
    listening: int = 0
    buffered: int = 0
    sending: asyncio.Lock = field(default_factory=asyncio.Lock)
    closed: bool = False

    async def send(self, header: dict[str, Any], body: bytes = b'') -> None:
        async with self.sending:
            await self.socket.send_bytes(frames.pack(header, body))

    async def close(self, code: int, reason: str = '') -> None:
        if self.closed:
            return
        self.closed = True
        for stream in list(self.streams.values()):
            stream.queue.put_nowait(('end', 'offline'))
        with contextlib.suppress(Exception):
            await self.socket.close(code, reason)


class Held(StreamingResponse):
    """A streamed answer whose `ended` runs however the response ends, even when the host left before its first
    byte and the body was never started, so a stream's slot and counts are always given back."""

    def __init__(self, content: AsyncIterable[bytes], *, status_code: int, headers: dict[str, str],
                 ended: Callable[[], Awaitable[None]]) -> None:
        super().__init__(content, status_code=status_code, headers=headers)
        self.ended = ended

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            await self.ended()


def offline_message(instance: str) -> str:
    return (f'Your Metaform named {instance} is not connected. On that machine run: metaform cloud connect '
            '(or turn on cloud_autoconnect so metaform web start connects it).')


def offline_answer(method: str, body: bytes, instance: str) -> Response:
    """What a host is told while the instance is away: a tool call's error result for the model to read, a JSON-RPC
    error for any other request, 503 for a notification or a stream."""
    if method == 'POST':
        try:
            message: Any = json.loads(body or b'null')
        except ValueError:
            message = None
        if isinstance(message, dict) and 'id' in message and isinstance(cast(dict[str, Any], message).get('method'),
                                                                          str):
            said = cast(dict[str, Any], message)
            text = offline_message(instance)
            if said['method'] == 'tools/call':
                return JSONResponse({'jsonrpc': '2.0', 'id': said['id'], 'result': {
                    'content': [{'type': 'text', 'text': text}], 'isError': True}})
            return JSONResponse({'jsonrpc': '2.0', 'id': said['id'], 'error': {
                'code': OFFLINE_CODE, 'message': text,
                'data': {'reason': 'offline', 'instance': instance, 'next': 'metaform cloud connect'}}})
    return Response(status_code=503, headers={'Retry-After': '30'})


class Throttle:
    """Limits on what is asked before anyone is signed in, each source first, then a global ceiling: the sign-in,
    consent and device pages and the device endpoint at `per_address` a minute per source, anything else at
    `other_per_address`, and all together at `global_rate`. A source (device.source: an address, an IPv6 /64) spends
    only its own allowance, so no single one can use up the ceiling that everyone shares. The token and revocation
    endpoints are not counted here: AI hosts call them from a few addresses for many people, so the broker charges
    each request to the grant it names once its signature checks, and only one naming nothing valid to its source
    (Broker.token_gate)."""

    PAGES = ('/oauth/device_authorization', '/oauth/authorize', '/device', '/node/passkey/', '/node/signin',
             '/node/setup', '/node/consent', '/account')
    COUNTED_BY_GRANT = ('/oauth/token', '/oauth/revoke')

    def __init__(self, app: ASGIApp, limits: Limits) -> None:
        self.app = app
        self.pages = Buckets(limits.per_address / 60.0, limits.per_address)
        self.others = Buckets(limits.other_per_address / 60.0, limits.other_per_address / 6.0)
        self.everyone = Buckets(limits.global_rate, limits.global_rate)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = str(scope.get('path') or '')
        if scope['type'] == 'http' and not path.startswith(('/mcp', '/.well-known/')) and \
                path not in self.COUNTED_BY_GRANT:
            who = source(Request(scope))
            allowed = self.pages.take(who) if path.startswith(self.PAGES) else self.others.take(who)
            if not allowed or not self.everyone.take('*'):
                await Response('Too many requests; try again shortly.', status_code=429,
                               headers={'Retry-After': '10'})(scope, receive, send)
                return
        await self.app(scope, receive, send)


class Broker:
    """The routing table and the two endpoints: `/cloud/tunnel` for machines, `/mcp[/<instance>]` for hosts."""

    def __init__(self, node: Node, limits: Limits | None = None) -> None:
        self.node = node
        self.policy = node.policy
        self.signed = node.signed
        self.limits = limits or Limits()
        self.tunnels: dict[tuple[str, str], Tunnel] = {}
        self.requests = Buckets(self.limits.rate, self.limits.burst)
        self.connects = Buckets(1.0 / self.limits.connect_every, float(self.limits.instances))
        self.grants = Buckets(self.limits.grant_rate, self.limits.grant_burst)
        self.unknown = Buckets(self.limits.unknown_per_address / 60.0, self.limits.unknown_per_address / 2.0)
        self.open_streams: dict[tuple[str, str], int] = {}
        self.loop: asyncio.AbstractEventLoop | None = None
        node.connected = self.connected
        node.instances = self.instances
        node.token_gate = self.token_gate
        self.signed.generations.listeners.append(self.signed_out)
        node.extra_routes += self.routes()

    def connected(self, account: str, instance: str) -> bool:
        return (account, instance) in self.tunnels

    def instances(self, account: str) -> list[str]:
        return sorted(name for (held, name) in self.tunnels if held == account)

    def token_gate(self, request: Request, key: str | None) -> bool:
        """A token or revocation request goes ahead within its grant's allowance when it names a grant this server
        signed, else within its source's: junk from one place spends that place's allowance only, never the refreshes
        of every account."""
        return self.grants.take(key) if key else self.unknown.take(source(request))

    # ------------------------------------------------------------------------------------------------ revocation

    def signed_out(self, account: str) -> None:
        """The account's generation moved: every tunnel it holds closes, 4003, and its machine stops and says why."""
        held = [tunnel for (owner, _), tunnel in self.tunnels.items() if owner == account]
        if not held or self.loop is None:
            return
        for tunnel in held:
            self.loop.call_soon_threadsafe(lambda one=tunnel: asyncio.ensure_future(
                one.close(frames.REVOKED, 'signed out everywhere')))

    # ------------------------------------------------------------------------------------------------ the tunnel

    def _tunnel_claims(self, token: str, proof: str | None) -> tuple[dict[str, Any] | None, int]:
        """A tunnel token's claims and 0, or None and the close code that says why not."""
        read = self.signed.signer.read(token, tokens.ACCESS, self.policy.tunnel)
        if read is None:
            return None, frames.INVALID_TOKEN
        if self.signed.live(read) is None:
            return None, frames.REVOKED
        bound: Any = read.get('cnf')
        if read.get('client_id') != tokens.CLI_CLIENT or tokens.TUNNEL_SCOPE not in str(read.get('scope')).split() \
                or not isinstance(bound, dict) or not LABEL.match(str(read.get('inst') or '')):
            return None, frames.INVALID_TOKEN
        if tokens.dpop_key(proof, 'GET', self.policy.tunnel, self.node.dpop_seen, token) != \
                cast(dict[str, Any], bound).get('jkt'):
            return None, frames.INVALID_TOKEN
        return read, 0

    @staticmethod
    def _kid(token: str) -> str:
        import jwt
        try:
            return str(jwt.get_unverified_header(token).get('kid') or '')
        except jwt.PyJWTError:
            return ''

    async def tunnel(self, socket: WebSocket) -> None:
        self.loop = asyncio.get_running_loop()
        if socket.headers.get('origin') or frames.SUBPROTOCOL not in socket.scope.get('subprotocols', []):
            await socket.close(1008)  # no browser opens a tunnel; refused before the upgrade completes
            return
        scheme, _, token = socket.headers.get('authorization', '').partition(' ')
        claims, code = self._tunnel_claims(token.strip(), socket.headers.get('dpop')) if scheme.lower() == 'dpop' \
            else (None, frames.INVALID_TOKEN)
        await socket.accept(subprotocol=frames.SUBPROTOCOL)
        if claims is None:
            await socket.close(code)
            return
        account, instance = str(claims['sub']), str(claims['inst'])
        if not self.connects.take(account):
            await socket.close(frames.RATE_LIMITED, 'connecting too often')
            return
        try:
            first = await asyncio.wait_for(socket.receive_bytes(), self.limits.hello_wait)
            hello, _ = frames.unpack(first)
        except (TimeoutError, ValueError, KeyError, WebSocketDisconnect, RuntimeError):
            with contextlib.suppress(Exception):
                await socket.close(1002, 'expected hello')
            return
        allows = tuple(scope for scope in MCP_SCOPES if scope in (hello.get('allows') or []))
        if hello.get('type') != 'hello' or hello.get('instance') != instance or not allows:
            await socket.close(1008, 'hello does not match the instance this machine signed in as')
            return
        others = [name for (owner, name) in self.tunnels if owner == account and name != instance]
        if len(others) >= self.limits.instances:
            await socket.close(frames.RATE_LIMITED, f'at most {self.limits.instances} machines per account')
            return
        made = Tunnel(socket, account, str(claims.get('username') or ''), instance, allows,
                      str(cast(dict[str, Any], claims['cnf'])['jkt']), int(claims['gen']), float(claims['exp']),
                      self._kid(token.strip()), slots=asyncio.Semaphore(self.limits.streams))
        replaced = self.tunnels.get((account, instance))
        self.tunnels[(account, instance)] = made
        if replaced is not None:
            await replaced.close(frames.REPLACED, 'a newer connection for this instance')
        # The key set rides along, so the machine checks assertions against the keys in force now, a revoked one
        # gone, and the broker's time, so a machine whose clock is off still judges them on the broker's.
        await made.send({'type': 'ready', 'account': made.username, 'instance': instance,
                         'resource': self.policy.instance_resource(instance), 'now': time.time(),
                         'keys': self.signed.signer.keys.jwks(),
                         'limits': {'request': self.limits.request, 'response': self.limits.response,
                                    'frame': self.limits.frame, 'credit': self.limits.credit,
                                    'streams': self.limits.streams}})
        watcher = asyncio.ensure_future(self._watch(made))
        try:
            await self._read(made)
        finally:
            watcher.cancel()
            if self.tunnels.get((account, instance)) is made:
                self.tunnels.pop((account, instance), None)
            made.closed = True
            for stream in list(made.streams.values()):
                stream.queue.put_nowait(('end', 'offline'))

    async def _watch(self, tunnel: Tunnel) -> None:
        """Every so often: the account still at its generation, the token renewed in time, its key not revoked."""
        while not tunnel.closed:
            await asyncio.sleep(self.limits.watch)
            if not self.signed.generations.valid(tunnel.account, tunnel.generation):
                await tunnel.close(frames.REVOKED, 'signed out everywhere')
            elif tunnel.expires + tokens.CLOCK_LEEWAY < time.time():
                await tunnel.close(frames.INVALID_TOKEN, 'the token expired')
            elif self.signed.signer.keys.public(tunnel.kid) is None:
                await tunnel.close(frames.INVALID_TOKEN, 'the key that signed the token was revoked')

    async def _read(self, tunnel: Tunnel) -> None:
        while not tunnel.closed:
            try:
                message = await tunnel.socket.receive()
            except (WebSocketDisconnect, RuntimeError):
                return
            if message['type'] == 'websocket.disconnect':
                return
            raw: bytes | None = message.get('bytes')
            if raw is None:
                continue
            if len(raw) > self.limits.frame + frames.MAX_HEADER + 4:
                await tunnel.close(frames.TOO_LARGE, 'frame too large')
                return
            try:
                header, body = frames.unpack(raw)
            except ValueError:
                continue
            kind = header['type']
            if kind == 'auth':
                await self._renew(tunnel, header)
                continue
            number: Any = header.get('stream')
            stream = tunnel.streams.get(number) if isinstance(number, int) else None
            if stream is None:
                continue  # a stream already finished: what comes late for it is dropped, never held
            if kind == 'head':
                stream.queue.put_nowait(('head', header))
            elif kind == 'data':
                if len(body) > stream.window:  # past the credit granted: the machine ignores the protocol
                    await tunnel.close(frames.TOO_LARGE, 'data sent past the credit granted')
                    return
                stream.window -= len(body)
                stream.holding += len(body)
                tunnel.buffered += len(body)
                stream.queue.put_nowait(('data', body))
            elif kind in ('end', 'cancel'):
                stream.queue.put_nowait(('end', header.get('error') or header.get('reason')))

    async def _renew(self, tunnel: Tunnel, header: dict[str, Any]) -> None:
        token = str(header.get('token') or '')
        claims, code = self._tunnel_claims(token, str(header.get('proof') or ''))
        if claims is None or claims.get('sub') != tunnel.account or claims.get('inst') != tunnel.instance or \
                cast(dict[str, Any], claims.get('cnf') or {}).get('jkt') != tunnel.jkt:
            await tunnel.close(code or frames.INVALID_TOKEN, 'the renewed token is not valid')
            return
        tunnel.expires = float(claims['exp'])
        tunnel.generation = int(claims['gen'])
        tunnel.kid = self._kid(token)

    # ------------------------------------------------------------------------------------------------ hosts

    def _instance(self, request: Request) -> str | None:
        named = request.path_params.get('instance')
        if named is None:
            return DEFAULT_INSTANCE
        name = str(named)
        return name if LABEL.match(name) and name != DEFAULT_INSTANCE else None

    def _metadata_url(self, instance: str) -> str:
        return self.policy.issuer + '/.well-known/oauth-protected-resource/mcp' + \
            ('' if instance == DEFAULT_INSTANCE else '/' + instance)

    async def resource_metadata(self, request: Request) -> Response:
        """RFC 9728 for one instance's resource."""
        instance = self._instance(request)
        if instance is None:
            return Response(status_code=404)
        return JSONResponse({'resource': self.policy.instance_resource(instance),
                             'authorization_servers': [self.policy.issuer],
                             'scopes_supported': [READ, WRITE], 'bearer_methods_supported': ['header'],
                             'resource_name': 'Metaform' + ('' if instance == DEFAULT_INSTANCE else f' ({instance})')},
                            headers={'Cache-Control': 'public, max-age=3600'})

    def _challenge(self, instance: str, error: str = '', status: int = 401, scope: str = '') -> Response:
        parts = [f'resource_metadata="{self._metadata_url(instance)}"']
        if error:
            parts.insert(0, f'error="{error}"')
        if scope:
            parts.append(f'scope="{scope}"')
        return JSONResponse({'error': error or 'unauthorized'}, status_code=status,
                            headers={'WWW-Authenticate': 'Bearer ' + ', '.join(parts)})

    async def _body(self, request: Request) -> bytes | None:
        held = b''
        async for chunk in request.stream():
            held += chunk
            if len(held) > self.limits.request:
                return None
        return held

    @staticmethod
    def held_open(request: Request) -> bool:
        """A stream a host holds open for notifications: a GET (the 2025 protocol), or a POST to subscriptions/listen
        (2026-07-28). The method is read from the `Mcp-Method` header, never the body; the person's machine refuses a
        2026-07-28 request whose header does not match its body, so a listen cannot pass as a request."""
        return request.method == 'GET' or request.headers.get('mcp-method') == 'subscriptions/listen'

    async def mcp(self, request: Request) -> Response:
        instance = self._instance(request)
        if instance is None:
            return Response(status_code=404)
        scheme, _, token = request.headers.get('authorization', '').partition(' ')
        if scheme.lower() != 'bearer' or not token.strip():
            return self._challenge(instance)
        claims = self.signed.access(token.strip(), self.policy.instance_resource(instance))
        if claims is None:
            return self._challenge(instance, 'invalid_token')
        held = str(claims.get('scope') or '').split()
        if READ not in held:
            return self._challenge(instance, 'insufficient_scope', 403, READ)
        account = str(claims['sub'])
        if not self.requests.take(account):
            return JSONResponse({'error': 'rate_limited'}, status_code=429, headers={'Retry-After': '1'})
        body = await self._body(request)
        if body is None:
            return JSONResponse({'error': 'request_too_large'}, status_code=413)
        tunnel = self.tunnels.get((account, instance))
        if tunnel is None or tunnel.closed:
            return offline_answer(request.method, body, instance)
        if self.held_open(request):
            # Counted per account and client and per tunnel, and never in the request slots: streams left open
            # cannot keep the person's calls waiting.
            key = (account, str(claims.get('client_id') or ''))
            if self.open_streams.get(key, 0) >= self.limits.streams_per_client or \
                    tunnel.listening >= self.limits.listens:
                return JSONResponse({'error': 'too_many_streams'}, status_code=429, headers={'Retry-After': '30'})
            self.open_streams[key] = self.open_streams.get(key, 0) + 1
            tunnel.listening += 1

            def let_go() -> None:
                self.open_streams[key] = max(0, self.open_streams.get(key, 1) - 1)
                if not self.open_streams[key]:
                    self.open_streams.pop(key, None)
                tunnel.listening = max(0, tunnel.listening - 1)
            lifetime = self.limits.stream_seconds
        else:
            try:
                await asyncio.wait_for(tunnel.slots.acquire(), self.limits.stream_wait)
            except TimeoutError:
                return JSONResponse({'error': 'busy'}, status_code=503, headers={'Retry-After': '5'})
            let_go = tunnel.slots.release
            lifetime = float('inf')
        released = False

        def release() -> None:
            nonlocal released
            if not released:
                released = True
                let_go()
        try:
            return await self._forward(request, tunnel, claims, held, body, instance, release, lifetime)
        except BaseException:
            release()
            raise

    async def _forward(self, request: Request, tunnel: Tunnel, claims: dict[str, Any], held: list[str], body: bytes,
                       instance: str, release: Callable[[], None], lifetime: float) -> Response:
        number = tunnel.next_stream
        tunnel.next_stream += 1
        stream = Stream(number, window=self.limits.credit)
        tunnel.streams[number] = stream
        allowed = [scope for scope in held if scope in tunnel.allows]
        assertion = self.signed.signer.mint(tokens.ASSERTION, {
            'sub': tunnel.account, 'username': tunnel.username, 'aud': self.policy.instance_resource(instance),
            'client_id': claims.get('client_id'), 'client_name': claims.get('cname'), 'scope': ' '.join(allowed),
            'stream': number, 'bh': tokens.body_hash(body)}, tokens.ASSERTION_SECONDS)
        headers = {name: value for name, value in request.headers.items() if name.lower() in frames.REQUEST_HEADERS}
        ended = False
        finished = False

        def done() -> None:
            """The stream's end, once, however it came: its entry, the bytes held for it and its slot given back."""
            nonlocal finished
            if finished:
                return
            finished = True
            tunnel.streams.pop(number, None)
            tunnel.buffered = max(0, tunnel.buffered - stream.holding)
            stream.holding = 0
            release()

        async def cancel(reason: str) -> None:
            if not ended and not tunnel.closed:
                with contextlib.suppress(Exception):
                    await tunnel.send({'type': 'cancel', 'stream': number, 'reason': reason})

        async def grant(size: int) -> None:
            """Credit back for bytes passed on; counted before it is sent, so the machine never seems to overrun."""
            stream.window += size
            with contextlib.suppress(Exception):
                await tunnel.send({'type': 'credit', 'stream': number, 'bytes': size})

        try:
            await tunnel.send({'type': 'open', 'stream': number, 'method': request.method, 'path': '/mcp',
                               'query': request.url.query, 'headers': headers, 'assertion': assertion}, body)
        except Exception:  # noqa: BLE001  the socket went as the request came: the instance is away
            done()
            return offline_answer(request.method, body, instance)
        first = await self._next(stream, request)
        if first is None:
            await cancel('host went away')
            done()
            return Response(status_code=499)
        if first[0] != 'head':
            done()
            return offline_answer(request.method, body, instance)
        head = cast(dict[str, Any], first[1])
        given: Any = head.get('headers')
        out = {str(name): str(value) for name, value in cast(dict[str, Any], given).items()
               if frames.response_header(str(name))} if isinstance(given, dict) else {}
        status: Any = head.get('status')
        if not isinstance(status, int) or not 100 <= status <= 599:
            await cancel('a head with no valid status')
            done()
            return JSONResponse({'error': 'bad_gateway'}, status_code=502)
        if 'text/event-stream' in out.get('content-type', ''):
            async def events() -> AsyncGenerator[bytes]:
                nonlocal ended
                started = time.monotonic()
                boundary = True
                while time.monotonic() - started < lifetime:
                    try:
                        kind, value = await asyncio.wait_for(stream.queue.get(), self.limits.keepalive)
                    except TimeoutError:
                        if boundary:
                            yield b': keep-alive\n\n'
                        continue
                    if kind != 'data':
                        ended = True
                        return
                    chunk = cast(bytes, value)
                    yield chunk
                    stream.holding -= len(chunk)
                    tunnel.buffered -= len(chunk)
                    boundary = chunk.endswith((b'\n\n', b'\r\n\r\n'))
                    await grant(len(chunk))

            async def closed() -> None:
                done()
                await cancel('stream closed')
            return Held(events(), status_code=status, headers=out, ended=closed)
        kept = b''
        try:
            while True:
                got = await self._next(stream, request)
                if got is None:
                    await cancel('host went away')
                    return Response(status_code=499)
                kind, value = got
                if kind != 'data':
                    ended = True
                    break
                chunk = cast(bytes, value)
                kept += chunk
                if len(kept) > self.limits.response or tunnel.buffered > self.limits.buffered:
                    await cancel('response too large')
                    largest = self.limits.response if len(kept) > self.limits.response else self.limits.buffered
                    return JSONResponse({'jsonrpc': '2.0', 'id': None, 'error': {
                        'code': -32603, 'message': f'The answer was larger than {largest} bytes.'}},
                        status_code=502)
                await grant(len(chunk))
        finally:
            done()
        return Response(kept, status_code=status, headers=out)

    async def _next(self, stream: Stream, request: Request) -> tuple[str, Any] | None:
        """The stream's next event, or None when the host went away while waiting."""
        while True:
            try:
                return await asyncio.wait_for(stream.queue.get(), 5.0)
            except TimeoutError:
                if await request.is_disconnected():
                    return None

    # ------------------------------------------------------------------------------------------------ the app

    def routes(self) -> list[Any]:
        def cors(app: Any) -> Any:
            return CORSMiddleware(app, allow_origins='*', allow_methods=['GET', 'POST', 'DELETE', 'OPTIONS'],
                                  allow_headers=['authorization', 'content-type', 'accept', 'mcp-protocol-version',
                                                 'mcp-session-id', 'mcp-method', 'mcp-name', 'last-event-id'],
                                  expose_headers=['mcp-session-id', 'www-authenticate'])
        from starlette.routing import request_response
        hosts = cors(request_response(self.mcp))
        described = cors(request_response(self.resource_metadata))
        return [Route('/mcp', hosts, methods=['GET', 'POST', 'DELETE', 'OPTIONS']),
                Route('/mcp/{instance}', hosts, methods=['GET', 'POST', 'DELETE', 'OPTIONS']),
                Route('/.well-known/oauth-protected-resource/mcp', described, methods=['GET', 'OPTIONS']),
                Route('/.well-known/oauth-protected-resource/mcp/{instance}', described, methods=['GET', 'OPTIONS']),
                WebSocketRoute('/cloud/tunnel', self.tunnel)]

    async def goaway(self) -> None:
        """Every machine told to come back after its own delay of one to five seconds, then disconnected (1012), so a
        restart is followed by a spread of reconnections, not all of them at once."""
        for tunnel in list(self.tunnels.values()):
            with contextlib.suppress(Exception):
                await tunnel.send({'type': 'goaway', 'reason': 'restarting',
                                   'reconnect_after_ms': random.randint(1000, 5000)})
            await tunnel.close(frames.RESTARTING, 'restarting')

    @contextlib.asynccontextmanager
    async def lifespan(self, _: Any) -> AsyncGenerator[None]:
        self.loop = asyncio.get_running_loop()
        try:
            yield
        finally:
            await self.goaway()  # for a server that did not send it first (Broker.server does)

    def app(self) -> ASGIApp:
        made: Starlette = self.node.app()
        made.router.lifespan_context = self.lifespan
        return Throttle(made, self.limits)

    def server(self, config: Any) -> Any:
        """A uvicorn server that sends goaway before it closes any connection: uvicorn closes WebSockets with 1012
        as its shutdown begins, before the app's lifespan hears of it, so a goaway sent from the lifespan would
        reach no one."""
        import uvicorn
        carrier = self

        class Server(uvicorn.Server):
            async def shutdown(self, sockets: Any = None) -> None:
                with contextlib.suppress(Exception):
                    await carrier.goaway()
                await super().shutdown(sockets)
        return Server(config)
