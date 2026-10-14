"""`metaform cloud connect`: this machine's Metaform, reachable by AI hosts through the broker, with no port open.

The local service dials out to the broker over one WebSocket (frames.py), authenticated with its own DPoP-bound token
from `metaform cloud login`, and serves each request the broker sends down it with the same MCP app `metaform mcp
serve --http` serves, run here in-process: nothing listens on any address. Each request carries the broker's signed
assertion of who is calling; it is checked here (oauth.Asserted) against the key set saved at login, this instance's
resource URL, the account this machine signed in as and the request's body, before the app sees it. The app's own
scope gate then holds every tool to the scopes the assertion carries and this machine allows (cloud_capability), and
person-only settings are refused over MCP exactly as for any other client. Each request is written to the audit log
here (audit.py).

The connection renews its token in-band before it expires, answers the broker's pings, and when it drops comes back
with jittered backoff from one second to a minute; after a broker restart (goaway, or 1012 without one) it waits a
random one to five seconds, so machines do not all come back at once. It stops, saying why, when the account signed
out everywhere or the grant was revoked (4003, or a refresh refused), and when a newer connection for the same
instance took its place (4009): the person moved this instance to another machine.

Each connection's `ready` brings the broker's key set, which replaces the one saved (a revoked key is dropped here
too), and the broker's time, from which assertions are judged, so this machine's own clock may be off.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import random
import time
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import httpx

from metaform import frames, home
from metaform.module import Stop, provided

from . import audit
from .login import Credentials, Refused, fresh_keys, proof, refresh, save

RENEW_BEFORE = 60.0  # seconds before the access token expires that a new one is sent
BACKOFF_FIRST, BACKOFF_MOST, STEADY = 1.0, 60.0, 60.0
RESTART_WAIT = (1.0, 5.0)  # after a broker restart with no goaway heard: a random wait in this range
AUDIT_SCAN = 1024 * 1024  # how much of an answer is looked at for its outcome


@dataclass
class Open:
    """A stream the broker opened: its task, the credit left to send, and whether the host went away."""
    task: asyncio.Task[None] | None = None
    credit: int = frames.CREDIT
    more: asyncio.Event = field(default_factory=asyncio.Event)
    gone: asyncio.Event = field(default_factory=asyncio.Event)


def _ignore(record: dict[str, Any]) -> None:
    return None


class Stopped(Exception):
    """The connection ended for good, with the reason and the next step for the person."""

    def __init__(self, reason: str, next_step: str) -> None:
        super().__init__(reason)
        self.next_step = next_step


class Connection:
    """One machine's tunnel to the broker, and the bridge from its frames to the MCP app."""

    def __init__(self, made: Credentials, app: Any, verifier: Any, *, allows: tuple[str, ...], full_audit: bool = False,
                 say: Callable[[str], None] = lambda line: None, state: Callable[[dict[str, Any]], None] | None = None,
                 http: httpx.AsyncClient | None = None) -> None:
        self.made = made
        self.app = app
        self.verifier = verifier
        self.allows = allows
        self.full_audit = full_audit
        self.say = say
        self.state = state or _ignore
        self.http = http
        self.access = ''
        self.expires = 0.0
        self.socket: Any = None
        self.sending = asyncio.Lock()
        self.streams: dict[int, Open] = {}
        self.limits: dict[str, Any] = {}
        self.host = urllib.parse.urlsplit(made.issuer).netloc.encode()

    async def send(self, header: dict[str, Any], body: bytes = b'') -> None:
        async with self.sending:
            await self.socket.send(frames.pack(header, body))

    # ------------------------------------------------------------------------------------------------ connecting

    async def run(self) -> None:
        """Connect, serve, and come back after a drop, until stopped for good (Stopped) or cancelled."""
        from websockets.exceptions import ConnectionClosed, InvalidStatus
        delay = BACKOFF_FIRST
        client = self.http or httpx.AsyncClient(timeout=15)
        try:
            while True:
                began = time.monotonic()
                wait = None
                try:
                    wait = await self.once(client)
                    code = 1000
                except ConnectionClosed as closed:
                    code = closed.rcvd.code if closed.rcvd is not None else 1006
                except (OSError, httpx.HTTPError, InvalidStatus, TimeoutError) as error:
                    code = 1006
                    self.state({'state': 'offline', 'reason': type(error).__name__})
                except Refused as refused:
                    raise Stopped(f'The broker no longer accepts this machine\'s sign-in ({refused}).',
                                  'metaform cloud login') from None
                if code == frames.REVOKED:
                    raise Stopped('The account signed out everywhere, or this machine\'s sign-in was revoked.',
                                  'metaform cloud login')
                if code == frames.REPLACED:
                    raise Stopped(f'Another machine connected as {self.made.instance} and took its place.',
                                  'metaform set --cloud-instance <another name>, then metaform cloud login')
                if time.monotonic() - began > STEADY:
                    delay = BACKOFF_FIRST
                pause = wait if wait is not None else random.uniform(*RESTART_WAIT) if code == frames.RESTARTING \
                    else random.uniform(0, delay)
                self.state({'state': 'reconnecting', 'code': code, 'in_seconds': round(pause, 1)})
                await asyncio.sleep(pause)
                delay = min(BACKOFF_MOST, delay * 2)
        finally:
            if self.http is None:
                await client.aclose()

    async def once(self, client: httpx.AsyncClient) -> float | None:
        """One connection, served until it closes; the delay a goaway asked for, if one came."""
        from websockets.asyncio.client import connect
        self.access, self.expires = await refresh(self.made, client)
        headers = {'Authorization': f'DPoP {self.access}',
                   'DPoP': proof(self.made.key, 'GET', self.made.tunnel_url, self.access, self.made.skew)}
        largest = frames.MAX_FRAME_BODY + frames.MAX_HEADER + 4
        async with connect(self.made.socket_url, additional_headers=headers, subprotocols=[frames.SUBPROTOCOL],  # pyright: ignore[reportArgumentType]
                           ping_interval=20, ping_timeout=20, max_size=largest, open_timeout=15,
                           close_timeout=5) as socket:
            self.socket = socket
            await self.send({'type': 'hello', 'version': frames.VERSION, 'instance': self.made.instance,
                             'allows': list(self.allows), 'max_streams': 32})
            first = await asyncio.wait_for(socket.recv(), 15)
            ready, _ = frames.unpack(first if isinstance(first, bytes) else first.encode())
            if ready.get('type') != 'ready':
                raise OSError('the broker did not say ready')
            self.limits = cast(dict[str, Any], ready.get('limits') or {})
            self.adopt(ready)
            self.say(f'Connected: AI tools reach this Metaform at {ready.get("resource")}')
            self.state({'state': 'connected', 'resource': ready.get('resource'), 'account': ready.get('account')})
            renewer = asyncio.ensure_future(self.renew())
            try:
                return await self.serve()
            finally:
                renewer.cancel()
                for held in list(self.streams.values()):
                    held.gone.set()
                    if held.task is not None:
                        held.task.cancel()
                self.streams.clear()

    def adopt(self, ready: dict[str, Any]) -> None:
        """What `ready` says that this machine keeps: the broker's time, as an offset from this clock, and its key set,
        which replaces the saved one whole, so a key the broker revoked stops being trusted here at once."""
        now: Any = ready.get('now')
        if isinstance(now, int | float):
            self.made.skew = float(now) - time.time()
        keys: Any = ready.get('keys')
        if isinstance(keys, dict) and isinstance(cast(dict[str, Any], keys).get('keys'), list) and \
                keys != self.made.jwks:
            self.made.jwks = cast(dict[str, Any], keys)
            with contextlib.suppress(OSError):
                save(self.made)

    async def renew(self) -> None:
        """A fresh access token sent in-band before the current one expires, so the tunnel never has to drop."""
        client = self.http or httpx.AsyncClient(timeout=15)
        try:
            while True:
                await asyncio.sleep(max(1.0, self.expires - time.time() - RENEW_BEFORE))
                try:
                    self.access, self.expires = await refresh(self.made, client)
                except (httpx.HTTPError, Refused):
                    await asyncio.sleep(10)
                    continue
                await self.send({'type': 'auth', 'token': self.access,
                                 'proof': proof(self.made.key, 'GET', self.made.tunnel_url, self.access,
                                                self.made.skew)})
        finally:
            if self.http is None:
                await client.aclose()

    async def serve(self) -> float | None:
        while True:
            raw = await self.socket.recv()
            if not isinstance(raw, bytes):
                continue
            try:
                header, body = frames.unpack(raw)
            except ValueError:
                continue
            kind = header['type']
            number = int(header.get('stream') or 0)
            if kind == 'open':
                held = Open(credit=int(self.limits.get('credit') or frames.CREDIT))
                self.streams[number] = held
                held.task = asyncio.ensure_future(self.stream(number, header, body, held))
            elif kind == 'credit' and number in self.streams:
                self.streams[number].credit += int(header.get('bytes') or 0)
                self.streams[number].more.set()
            elif kind == 'cancel' and number in self.streams:
                self.streams[number].gone.set()
            elif kind == 'goaway':
                return float(header.get('reconnect_after_ms') or 1000) / 1000.0

    # ------------------------------------------------------------------------------------------------ one request

    async def stream(self, number: int, header: dict[str, Any], body: bytes, held: Open) -> None:
        started = time.monotonic()
        asked = audit.described(body) if header.get('method') == 'POST' else {'method': header.get('method')}
        assertion = str(header.get('assertion') or '')
        await self._known_key(assertion)
        claims: dict[str, Any] | None = self.verifier.check(assertion, body)
        said: dict[str, Any] = claims or {}
        record: dict[str, Any] = {'account': said.get('username'), 'client_id': said.get('client_id'),
                                  'client_name': said.get('client_name'), **asked, 'jti': said.get('jti'),
                                  'stream': number}
        status, seen = 401, b''
        try:
            if claims is None and self.verifier.late:  # signed for this machine, but its time is off by this clock
                status, payload = self.clock_refusal(body, self.verifier.late)
                await self.send({'type': 'head', 'stream': number, 'status': status,
                                 'headers': {'content-type': 'application/json'}})
                await self.send({'type': 'data', 'stream': number}, payload)
                await self.send({'type': 'end', 'stream': number})
                return
            if claims is None:  # not this machine's, not this account's, or not this body: refused, never run
                payload = b'{"error":"invalid_token"}'
                await self.send({'type': 'head', 'stream': number, 'status': 401,
                                 'headers': {'content-type': 'application/json'}})
                await self.send({'type': 'data', 'stream': number}, payload)
                await self.send({'type': 'end', 'stream': number})
                return
            status, seen = await self.bridge(number, header, body, assertion, held)
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001  one request's failure is its own; the tunnel goes on
            with contextlib.suppress(Exception):
                await self.send({'type': 'end', 'stream': number, 'error': type(error).__name__})
            status = 500
        finally:
            self.streams.pop(number, None)
            audit.write({**record, 'outcome': audit.outcome(status, seen),
                         'ms': int((time.monotonic() - started) * 1000)}, self.full_audit)

    def clock_refusal(self, body: bytes, late: float) -> tuple[int, bytes]:
        """A request refused because this machine's clock and the broker's disagree by more than the leeway, though
        the offset was measured at connection: the clock moved since. The person is told, here and through the AI
        tool, in a shape the tool passes on rather than a 401 that would only send it to sign in again; the
        connection then starts over, measuring the offset afresh."""
        text = (f'The Metaform on this machine refused the request: its clock is {abs(late):.0f} seconds off the '
                'broker\'s. Set the clock on that machine to update automatically; the connection measures the '
                'difference again as it reconnects.')
        self.say(text)
        self.state({'state': 'connected', 'warning': text})
        if self.socket is not None:
            asyncio.get_running_loop().call_soon(lambda: asyncio.ensure_future(self.socket.close(1000, 'clock')))
        try:
            message: Any = json.loads(body or b'null')
        except ValueError:
            message = None
        if isinstance(message, dict) and 'id' in message:
            said = cast(dict[str, Any], message)
            if said.get('method') == 'tools/call':
                answer: dict[str, Any] = {'content': [{'type': 'text', 'text': text}], 'isError': True}
                return 200, json.dumps({'jsonrpc': '2.0', 'id': said['id'], 'result': answer}).encode()
            return 200, json.dumps({'jsonrpc': '2.0', 'id': said['id'], 'error': {
                'code': -32051, 'message': text, 'data': {'reason': 'clock'}}}).encode()
        return 503, json.dumps({'error': 'clock', 'error_description': text}).encode()

    async def _known_key(self, assertion: str) -> None:
        """An assertion signed by a key this machine has not seen: the key set fetched again, at most once a minute."""
        import jwt
        with contextlib.suppress(jwt.PyJWTError):
            kid = str(jwt.get_unverified_header(assertion).get('kid') or '')
            if kid and self.made.public_key(kid) is None:
                client = self.http or httpx.AsyncClient(timeout=15)
                try:
                    await fresh_keys(self.made, client)
                finally:
                    if self.http is None:
                        await client.aclose()

    async def bridge(self, number: int, header: dict[str, Any], body: bytes, assertion: str,
                     held: Open) -> tuple[int, bytes]:
        """The request as an ASGI HTTP request to the MCP app, its answer back as head, data and end frames."""
        given = cast(dict[str, Any], header.get('headers') or {})
        headers = [(b'host', self.host), (b'authorization', b'Bearer ' + assertion.encode()),
                   (b'content-length', str(len(body)).encode())]
        headers += [(name.lower().encode(), str(value).encode()) for name, value in given.items()
                    if name.lower() in frames.REQUEST_HEADERS]
        path = '/mcp'
        scope: dict[str, Any] = {
            'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.3'}, 'http_version': '1.1',
            'method': str(header.get('method') or 'POST'), 'scheme': 'https', 'path': path,
            'raw_path': path.encode(), 'query_string': str(header.get('query') or '').encode(), 'root_path': '',
            'headers': headers, 'client': ('127.0.0.1', 0), 'server': ('127.0.0.1', 0), 'state': {}}
        delivered = False
        status = 500
        seen = b''
        ended = False
        frame = int(self.limits.get('frame') or frames.MAX_FRAME_BODY)

        async def receive() -> dict[str, Any]:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': body, 'more_body': False}
            await held.gone.wait()
            return {'type': 'http.disconnect'}

        async def send(message: dict[str, Any]) -> None:
            nonlocal status, seen, ended
            if held.gone.is_set():
                return
            if message['type'] == 'http.response.start':
                status = int(message['status'])
                out = {name.decode('latin-1'): value.decode('latin-1')
                       for name, value in message.get('headers', []) if frames.response_header(name.decode('latin-1'))}
                await self.send({'type': 'head', 'stream': number, 'status': status, 'headers': out})
                return
            if message['type'] != 'http.response.body':
                return
            chunk: bytes = message.get('body', b'')
            if len(seen) < AUDIT_SCAN:
                seen += chunk[:AUDIT_SCAN - len(seen)]
            while chunk:
                while held.credit <= 0 and not held.gone.is_set():
                    held.more.clear()
                    await held.more.wait()
                if held.gone.is_set():
                    return
                part = chunk[:min(frame, held.credit)]
                chunk = chunk[len(part):]
                held.credit -= len(part)
                await self.send({'type': 'data', 'stream': number}, part)
            if not message.get('more_body'):
                ended = True
                await self.send({'type': 'end', 'stream': number})

        app_task = asyncio.ensure_future(self.app(scope, receive, send))
        gone = asyncio.ensure_future(held.gone.wait())
        try:
            await asyncio.wait({app_task, gone}, return_when=asyncio.FIRST_COMPLETED)
            if not app_task.done():  # the host went away: the app is told, then stopped if it does not end
                with contextlib.suppress(TimeoutError, asyncio.CancelledError, Exception):
                    await asyncio.wait_for(asyncio.shield(app_task), 5)
                app_task.cancel()
            else:
                app_task.result()
        finally:
            gone.cancel()
        if not ended and not held.gone.is_set():
            await self.send({'type': 'end', 'stream': number})
        return status, seen


def mcp(folder: Path) -> Any:
    """The mcp module's HTTP serving pieces, as it provides them (`mcp.http`); refused while mcp is off."""
    found = provided(folder, 'mcp.http')
    if not found:
        raise Stop('The mcp module is off on this folder, and the cloud connection serves its tools.', 'metaform enable mcp')
    return found[0][1]


def asserted(made: Credentials, allows: tuple[str, ...], folder: Path | None = None) -> Any:
    """This machine's check of the broker's assertions, against what login saved."""
    return mcp(folder or Path.cwd()).asserted(made.issuer, made.resource, made.account, made.public_key, allows,
                                              clock=lambda: time.time() + made.skew)


def build_app(folder: Path, made: Credentials, verifier: Any) -> Any:
    """The MCP app `metaform mcp serve --http` serves, for this instance's resource URL behind the broker."""
    served = mcp(folder)
    exposed = served.exposure(public=made.issuer, introspection='', credential='',
                              path=urllib.parse.urlsplit(made.resource).path or '/mcp')
    return served.http_app(folder, bind='127.0.0.1', exposed=exposed, verifier=verifier)


async def serve(folder: Path, made: Credentials, allows: tuple[str, ...], *, full_audit: bool = False,
                say: Callable[[str], None] = print, state: Callable[[dict[str, Any]], None] | None = None,
                wrap: Callable[[Any], Any] | None = None) -> None:
    """Run the app's lifespan once, then the connection until it stops for good (Stopped, raised as itself, not
    inside the lifespan's task group). `wrap` puts something in front of the app, as a test watches what reaches it."""
    verifier = asserted(made, allows, folder)
    app = build_app(folder, made, verifier)
    ended: list[Stopped] = []
    async with app.router.lifespan_context(app):
        try:
            await Connection(made, wrap(app) if wrap else app, verifier, allows=allows, full_audit=full_audit, say=say,
                             state=state).run()
        except Stopped as stopped:
            ended.append(stopped)
    if ended:
        raise ended[0]


def state_file() -> Path:
    from .login import folder as cloud_folder
    return cloud_folder() / 'connect.json'


def write_state(record: dict[str, Any]) -> None:
    """What `cloud status` shows: the connection's state and a heartbeat, so a stopped one is seen as stopped."""
    with contextlib.suppress(OSError):
        target = state_file()
        home.mkdir_private(target.parent)
        temporary = target.with_suffix('.tmp')
        home.write_private(temporary, json.dumps({**record, 'beat': time.time()}))
        temporary.replace(target)
