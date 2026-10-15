"""The phone bridge's server: a small ASGI app (Starlette, on uvicorn) on its own loopback port.

The web GUI's standard-library server has no websockets, and Twilio's Media Streams need one, so the phone has its
own. It binds 127.0.0.1 by default and is reached from the internet through twilio_public_url: the Metaform Node's
Caddy, which routes /phone/* here, or the person's own tunnel. On a direct route, twilio_bind, it listens on an
address the person's router or firewall forwards a port to, serving TLS itself from twilio_certificate or behind the
person's own TLS terminator; every check below holds the same on every route.

  POST /phone/voice    Twilio's Voice webhook: a call the owner made, or one Metaform placed, answered with TwiML
                       that connects it to /phone/stream with a one-time token, or first asks for the PIN; anyone
                       else hears a refusal
  POST /phone/pin      the keypad PIN a call was asked for, as Twilio's <Gather> posts it
  WS   /phone/stream   the call's bidirectional Media Stream, bridged by `bridge.Call`
  POST /phone/sms      Twilio's Messaging webhook: the owner's text goes to the system agent, its reply is texted back
  GET  /phone/health   200, nothing more
  POST /control/call   the person's own `twilio call`, from this machine only, with the run file's control token
  POST /control/text   the person's own `twilio text`, likewise

Every webhook must carry Twilio's signature of the public URL and its parameters, made with the auth token; a request
without it, or from a number not in twilio_owner_numbers, gets nothing of the agent. Twilio's signature carries no time,
so a signed webhook could be sent again: each CallSid and MessageSid is acted on once, and the ones seen are kept
across restarts. Caller ID can be spoofed, so a call must also prove itself as twilio_caller_proof says: a caller ID its
carrier fully attested (STIR/SHAKEN), or the PIN on the keypad. A stream is accepted only with the token minted for
its call when the TwiML was served, used once, within a minute, for that call's SID. Requests that fail these checks
are counted by source and all together, so a flood of them is answered 429 and not logged line by line; a request that
passes them is never held back, so nobody can shut Twilio out by failing in its name.
"""
from __future__ import annotations

import asyncio
import contextlib
import hmac
import json
import os
import re
import secrets
import threading
import time
import urllib.parse
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from . import api
from .agent import Agent
from .bridge import Call, Log
from .engines import Voice

TICKET_SECONDS = 60.0   # how long the token in a call's TwiML may wait for its stream
START_SECONDS = 10.0    # how long an accepted stream may take to send its start; Twilio sends it at once
BODY_LIMIT = 16_384     # bytes in a webhook body; Twilio's are far smaller
BAD_SIGNATURES = 5      # failed requests from one source within SHUT_SECONDS quiet it for SHUT_SECONDS
SHUT_SECONDS = 600.0
FAILURES_PER_MINUTE = 120  # failed requests from every source together, so rotating the source does not help
TEXTS_PER_MINUTE = 6    # the owner's own texts answered per minute
PIN_SECONDS = 60.0      # how long a call asked for its PIN may take to enter it
WRONG_PINS = 5          # wrong PINs, by call or text, within PIN_SHUT_SECONDS stop the PIN being taken at all
PIN_SHUT_SECONDS = 3600.0
SEEN_LIMIT = 100_000    # CallSids and MessageSids remembered; the oldest go first
LOOPBACK = ('127.0.0.1', '::1', 'localhost')
PIN_NAME = 'METAFORM_TWILIO_PIN'  # the PIN, from the environment of the process that runs the bridge, like the token
PROOFS = ('attested-or-pin', 'pin', 'attested', 'caller-id')
ATTESTED = 'TN-Validation-Passed-A'  # Twilio's StirVerstat for a caller ID its carrier fully attested
CALL_SID = re.compile(r'^CA[0-9a-fA-F]{32}$')
MESSAGE_SID = re.compile(r'^(SM|MM)[0-9a-fA-F]{32}$')


@dataclass
class Lines:
    """What the phone says. Every line is read from the module's prompts.xml (`lines` in __init__.py), filled for this
    person; the empty defaults here only stand in for a test that builds a bridge with no prompts read."""
    greeting: str = ''
    calling: Callable[[str], str] = lambda why: ''
    on_call: str = ''
    on_callback: Callable[[str], str] = lambda why: ''
    on_text: str = ''
    refusal: str = ''
    busy: str = ''
    trouble: str = ''
    pin: str = ''
    pin_wrong: str = ''


@dataclass
class Config:
    public_url: str              # https://host, the base Twilio reaches; /phone/... is under it
    twilio_number: str
    owners: tuple[str, ...]
    auth_token: str
    control_token: str
    lines: Lines = field(default_factory=Lines)
    call_gap: float = 900.0      # seconds between calls Metaform places on its own
    proof: str = 'attested-or-pin'  # twilio_caller_proof: what a call or text must show beyond its caller ID
    pin: str | None = None       # METAFORM_TWILIO_PIN, digits; None when it is not set
    bind: str = '127.0.0.1'      # twilio_bind: the address it listens on, which this machine's own requests come from


@dataclass
class Ticket:
    call_sid: str
    caller: str
    direction: str
    reason: str | None
    expires: float


@dataclass
class Asked:
    caller: str
    expires: float


class Limiter:
    """Requests that failed the bridge's checks, counted by source and all together. A source with BAD_SIGNATURES
    failures within SHUT_SECONDS, or every source together past FAILURES_PER_MINUTE, is answered 429 and no longer
    logged line by line until it calms. Only failures are counted and only failures are answered 429: a request that
    passes the checks is never held back, so whoever shares a source with Twilio, or claims to in X-Forwarded-For,
    cannot shut Twilio out."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self.bad: dict[str, deque[float]] = defaultdict(deque)
        self.shut: dict[str, float] = {}
        self.every: deque[float] = deque()

    def refused(self, source: str) -> bool:
        """Count one failure from `source`; whether it is past the limits, answered 429 and kept out of the log."""
        now = self.clock()
        if len(self.bad) > 4096:  # sources made up by the thousand are forgotten once quiet
            self.bad = defaultdict(deque, {key: held for key, held in self.bad.items() if held[-1] > now - SHUT_SECONDS})
            self.shut = {key: until for key, until in self.shut.items() if until > now}
        held = self.bad[source]
        while held and held[0] <= now - SHUT_SECONDS:
            held.popleft()
        held.append(now)
        while self.every and self.every[0] <= now - 60.0:
            self.every.popleft()
        self.every.append(now)
        if len(held) >= BAD_SIGNATURES:
            self.shut[source] = max(self.shut.get(source, 0.0), now + SHUT_SECONDS)
        return self.shut.get(source, 0.0) > now or len(self.every) > FAILURES_PER_MINUTE


class Seen:
    """Every CallSid and MessageSid the bridge acted on. Twilio's signature has no time in it, so a signed webhook
    would pass again if sent again; each SID is acted on once. Kept in `path` when given, one per line, so a bridge
    started again still knows them."""

    def __init__(self, path: Path | None = None, limit: int = SEEN_LIMIT) -> None:
        self.path, self.limit = path, limit
        self.held: dict[str, None] = {}
        self.lock = threading.Lock()
        if path is not None:
            with contextlib.suppress(OSError):
                for line in path.read_text(encoding='utf-8').splitlines():
                    if line.strip():
                        self.held[line.strip()] = None

    def first(self, key: str) -> bool:
        """Whether `key` is seen for the first time; it is seen from now on."""
        with self.lock:
            if key in self.held:
                return False
            self.held[key] = None
            if len(self.held) > self.limit:
                for old in list(self.held)[:len(self.held) - self.limit // 2]:
                    del self.held[old]
                self._write('\n'.join(self.held) + '\n', 'w')
            else:
                self._write(key + '\n', 'a')
            return True

    def _write(self, text: str, mode: str) -> None:
        if self.path is None:
            return
        with contextlib.suppress(OSError):
            descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | (os.O_APPEND if mode == 'a' else os.O_TRUNC),
                                 0o600)
            with os.fdopen(descriptor, mode, encoding='utf-8') as out:
                out.write(text)


class Phone:
    """The bridge's state: the tickets minted, the call in progress, the calls placed and why."""

    def __init__(self, config: Config, *, agent: Callable[[], Agent], voice: Callable[[], Voice],
                 client: api.Client, log: Log, clock: Callable[[], float] = time.monotonic,
                 seen: Seen | None = None) -> None:
        self.config, self.make_agent, self.make_voice, self.client, self.log = config, agent, voice, client, log
        self.clock = clock
        self.limiter = Limiter(clock)
        self.seen = seen if seen is not None else Seen()
        self.tickets: dict[str, Ticket] = {}
        self.asking: dict[str, Asked] = {}     # call SID -> the call asked for its PIN
        self.wrong_pins: deque[float] = deque()
        self.pin_shut = float('-inf')
        self.placed: dict[str, str] = {}       # call SID -> why Metaform placed it, until its webhook comes
        self.placing = threading.Lock()         # calls are reserved from the signal listener's thread too
        self.texted: dict[str, deque[float]] = {}
        self.active: Call | None = None
        self.calls: list[Call] = []             # every call bridged, for the simulated call to read back
        self.last_placed = float('-inf')
        self.texting = asyncio.Lock()
        self.tasks: set[asyncio.Task[Any]] = set()

    # ------------------------------------------------------------------------------------------- requests

    def source(self, request: Request | WebSocket) -> str:
        """Who sent it, for counting failures only: the address the proxy in front, on this machine, appended last to
        X-Forwarded-For; the hops before it are the client's own say and could be anything. Behind a tunnel that adds
        nothing the last hop is the client's say too, which is why it only ever groups failures and never lets a
        request in or keeps one out."""
        peer = request.client.host if request.client else 'unknown'
        forwarded = request.headers.get('x-forwarded-for', '')
        if peer in LOOPBACK and forwarded:
            return forwarded.split(',')[-1].strip() or peer
        return peer

    def public(self, path: str, query: str = '', scheme: str | None = None) -> str:
        base = self.config.public_url.rstrip('/')
        if scheme is not None:
            base = scheme + base[base.index(':'):]
        return base + path + (f'?{query}' if query else '')

    async def signed(self, request: Request) -> tuple[dict[str, str], str] | Response:
        """The webhook's parameters when Twilio's signature holds, else the response that refuses it."""
        where = self.source(request)
        if 'application/x-www-form-urlencoded' not in request.headers.get('content-type', ''):
            return PlainTextResponse('Unsupported media type.', status_code=415)
        if int(request.headers.get('content-length') or 0) > BODY_LIMIT:
            return PlainTextResponse('Too large.', status_code=413)
        body = await request.body()
        if len(body) > BODY_LIMIT:
            return PlainTextResponse('Too large.', status_code=413)
        pairs = urllib.parse.parse_qsl(body.decode('utf-8', 'replace'), keep_blank_values=True)
        url = self.public(request.url.path, request.url.query)
        if not api.valid(self.config.auth_token, url, pairs, request.headers.get('x-twilio-signature')):
            return self.failed(where, f'a request to {request.url.path}: no valid Twilio signature')
        return dict(pairs), where

    def failed(self, where: str, what: str) -> Response:
        """A request that failed the checks: counted, logged until its source is past the limits, refused."""
        if self.limiter.refused(where):
            return PlainTextResponse('Too many requests.', status_code=429)
        self.log(f'refused {what}, from {where}')
        return PlainTextResponse('Forbidden.', status_code=403)

    def owner(self, number: str) -> bool:
        return number in self.config.owners

    def mint(self, call_sid: str, caller: str, direction: str, reason: str | None) -> str:
        now = self.clock()
        for token in [token for token, held in self.tickets.items() if held.expires <= now]:
            del self.tickets[token]
        token = secrets.token_urlsafe(24)
        self.tickets[token] = Ticket(call_sid, caller, direction, reason, now + TICKET_SECONDS)
        return token

    def redeem(self, token: str, call_sid: str) -> Ticket | None:
        held = self.tickets.pop(token, None) if token else None
        if held is None or held.expires <= self.clock() or not hmac.compare_digest(held.call_sid, call_sid):
            return None
        return held

    # ------------------------------------------------------------------------------------------- voice webhook

    async def voice_hook(self, request: Request) -> Response:
        checked = await self.signed(request)
        if isinstance(checked, Response):
            return checked
        params, _ = checked
        call_sid, direction = params.get('CallSid', ''), params.get('Direction', '')
        lines = self.config.lines
        if not CALL_SID.match(call_sid) or not self.seen.first(f'call:{call_sid}'):
            self.log(f'refused a call webhook for {call_sid[:40] or "no call"}: already answered, so sent again')
            return _xml(api.refuse(''))
        if direction == 'inbound':
            caller = params.get('From', '')
            ours = params.get('To', '') == self.config.twilio_number
            reason = None
        else:  # outbound-api: a call Metaform placed, to the owner, answered; its webhook comes once
            caller = params.get('To', '')
            reason = self.placed.pop(call_sid, None)
            ours = params.get('From', '') == self.config.twilio_number and reason is not None
        if not (ours and self.owner(caller)):
            self.log(f'refused a call ({direction or "no direction"}): not the owner, or not this number')
            return _xml(api.refuse(lines.refusal))
        if self.active is not None:
            return _xml(api.refuse(lines.busy))
        if direction != 'inbound':
            return self.connect(call_sid, caller, 'outbound', reason)
        proof = self.proof(params)
        if proof == 'pin':
            now = self.clock()
            for sid in [sid for sid, held in self.asking.items() if held.expires <= now]:
                del self.asking[sid]
            self.asking[call_sid] = Asked(caller, now + PIN_SECONDS)
            return _xml(api.gather(self.public('/phone/pin'), lines.pin, lines.pin_wrong))
        if proof is None:
            self.log(f'refused a call from an owner number: its caller ID was not attested '
                     f'({params.get("StirVerstat") or "none"}) and twilio_caller_proof takes no PIN now')
            return _xml(api.refuse(lines.refusal))
        return self.connect(call_sid, caller, 'inbound', None)

    def proof(self, params: dict[str, str]) -> str | None:
        """What lets an owner's inbound call through, as twilio_caller_proof says: `caller-id` alone, `attested` when
        its carrier fully attested the caller ID, `pin` when the PIN must be entered first, or None when nothing can."""
        mode = self.config.proof
        if mode == 'caller-id':
            return 'caller-id'
        if mode in ('attested', 'attested-or-pin') and params.get('StirVerstat', '') == ATTESTED:
            return 'attested'
        if mode in ('pin', 'attested-or-pin') and self.config.pin and self.pin_shut <= self.clock():
            return 'pin'
        return None

    async def pin_hook(self, request: Request) -> Response:
        """The digits a call asked for its PIN entered. Right, the call is connected; wrong, it is hung up, and
        WRONG_PINS wrong ones within the hour stop the PIN being taken for an hour."""
        checked = await self.signed(request)
        if isinstance(checked, Response):
            return checked
        params, _ = checked
        lines = self.config.lines
        call_sid = params.get('CallSid', '')
        asked = self.asking.pop(call_sid, None)
        if asked is None or asked.expires <= self.clock() or params.get('From', '') != asked.caller:
            self.log(f'refused a PIN for {call_sid[:40] or "no call"}: no call of it is waiting for one')
            return _xml(api.refuse(''))
        if not self.pin_right(params.get('Digits', '')):
            return _xml(api.refuse(lines.pin_wrong))
        if self.active is not None:
            return _xml(api.refuse(lines.busy))
        return self.connect(call_sid, asked.caller, 'inbound', None)

    def pin_right(self, digits: str) -> bool:
        """Whether `digits` is the PIN, compared in constant time; a wrong one is counted toward the PIN's lockout."""
        pin, now = self.config.pin, self.clock()
        if self.pin_shut > now:
            self.log('a PIN was entered while the PIN is not taken, after too many wrong ones')
            return False
        if pin and hmac.compare_digest(digits.encode(), pin.encode()):
            return True
        while self.wrong_pins and self.wrong_pins[0] <= now - PIN_SHUT_SECONDS:
            self.wrong_pins.popleft()
        self.wrong_pins.append(now)
        if len(self.wrong_pins) >= WRONG_PINS:
            self.wrong_pins.clear()
            self.pin_shut = now + PIN_SHUT_SECONDS
            self.log(f'{WRONG_PINS} wrong PINs within the hour: the PIN is not taken for an hour')
        else:
            self.log('a wrong PIN was entered')
        return False

    def connect(self, call_sid: str, caller: str, direction: str, reason: str | None) -> Response:
        """TwiML that connects the call to the stream, with the one-time token its start must hand back."""
        token = self.mint(call_sid, caller, direction, reason)
        return _xml(api.stream(self.public('/phone/stream', scheme='wss'), {'token': token}))

    # ------------------------------------------------------------------------------------------- the stream

    async def stream(self, socket: WebSocket) -> None:
        where = self.source(socket)
        given = socket.headers.get('x-twilio-signature')
        if given is not None:  # Twilio signs the upgrade request too; a forged one is refused outright
            urls = [self.public(socket.url.path, socket.url.query, scheme) for scheme in ('wss', 'https')]
            if not any(api.valid(self.config.auth_token, url, (), given) for url in urls):
                if not self.limiter.refused(where):
                    self.log(f'refused a stream from {where}: no valid Twilio signature')
                await socket.close(code=1008)
                return
        await socket.accept()
        messages = self._messages(socket)
        ticket: Ticket | None = None
        stream_sid = ''
        try:
            with contextlib.suppress(TimeoutError):
                async with asyncio.timeout(START_SECONDS):
                    async for message in messages:
                        event = message.get('event')
                        if event == 'connected':
                            continue
                        if event != 'start':
                            break
                        start: dict[str, Any] = message.get('start') or {}
                        parameters: dict[str, Any] = start.get('customParameters') or {}
                        stream_sid = str(start.get('streamSid') or message.get('streamSid') or '')
                        ticket = self.redeem(str(parameters.get('token') or ''), str(start.get('callSid') or ''))
                        break
            if ticket is None or not stream_sid:
                if not self.limiter.refused(where):
                    self.log(f'refused a stream from {where}: its start did not match a call this bridge answered')
                await socket.close(code=1008)
                return
            if self.active is not None:  # its own call, raced by another: not a failure, so not counted
                self.log(f'refused the stream of call {ticket.call_sid}: another call is in progress')
                await socket.close(code=1008)
                return
            await self._bridge(socket, messages, ticket, stream_sid)
        except WebSocketDisconnect:
            pass
        finally:
            with contextlib.suppress(Exception):
                await socket.close()

    async def _messages(self, socket: WebSocket) -> AsyncIterator[dict[str, Any]]:
        while True:
            try:
                text = await socket.receive_text()
            except (WebSocketDisconnect, RuntimeError):
                return
            try:
                found: Any = json.loads(text)
            except ValueError:
                continue
            if isinstance(found, dict):
                yield found  # pyright: ignore[reportUnknownArgumentType]

    async def _bridge(self, socket: WebSocket, messages: AsyncIterator[dict[str, Any]], ticket: Ticket,
                      stream_sid: str) -> None:
        lines = self.config.lines

        async def send(message: dict[str, Any]) -> None:
            with contextlib.suppress(Exception):
                await socket.send_text(json.dumps(message))

        if ticket.direction == 'outbound' and ticket.reason:
            opening, framing = lines.calling(ticket.reason), lines.on_callback(ticket.reason)
        else:
            opening, framing = lines.greeting, lines.on_call
        call = Call(send, self.make_voice(), self.make_agent(), stream_sid=stream_sid, opening=opening,
                    framing=framing, trouble=lines.trouble, log=self.log, clock=self.clock)
        self.active = call
        self.calls.append(call)
        self.log(f'{ticket.direction} call {ticket.call_sid} bridged on stream {stream_sid}')
        try:
            await call.run(messages)
        finally:
            self.active = None

    # ------------------------------------------------------------------------------------------- texts

    async def sms_hook(self, request: Request) -> Response:
        checked = await self.signed(request)
        if isinstance(checked, Response):
            return checked
        params, _ = checked
        sender, body = params.get('From', ''), params.get('Body', '').strip()
        message_sid = params.get('MessageSid', '') or params.get('SmsSid', '')
        if not MESSAGE_SID.match(message_sid) or not self.seen.first(f'text:{message_sid}'):
            self.log(f'ignored a text webhook for {message_sid[:40] or "no message"}: already handled, so sent again')
            return _xml(api.empty())
        if not self.owner(sender) or params.get('To', '') != self.config.twilio_number:
            self.log('ignored a text: not from the owner, or not to this number')
            return _xml(api.empty())
        body = self.text_proven(body)
        if body and self.text_allowed(sender):
            self.spawn(self.text_reply(sender, body))
        return _xml(api.empty())

    def text_proven(self, body: str) -> str:
        """The owner's text as the agent hears it, or '' when it does not prove itself: under caller-id the sender's
        number is enough; otherwise the text starts with the PIN, which is taken off. A text has no attestation."""
        if self.config.proof == 'caller-id':
            return body
        if not self.config.pin:
            self.log(f'ignored a text from an owner number: twilio_caller_proof wants the PIN at its start, and '
                     f'{PIN_NAME} is not set')
            return ''
        first, _, rest = body.partition(' ')
        if not first.isdigit():
            self.log('ignored a text from an owner number: it does not start with the PIN')
            return ''
        return rest.strip() if self.pin_right(first) else ''

    def text_allowed(self, sender: str) -> bool:
        """The owner's texts answered at most TEXTS_PER_MINUTE a minute."""
        now = self.clock()
        held = self.texted.setdefault(sender, deque())
        while held and held[0] <= now - 60.0:
            held.popleft()
        if len(held) >= TEXTS_PER_MINUTE:
            return False
        held.append(now)
        return True

    async def text_reply(self, to: str, body: str) -> None:
        """The system agent's reply to the owner's text, texted back through the REST API once it is whole."""
        async with self.texting:
            message = f'{self.config.lines.on_text}\n\n{body}' if self.config.lines.on_text else body
            answer = ''
            try:
                async for so_far in self.make_agent().reply(message):
                    answer = so_far
            except Exception as error:  # noqa: BLE001  the person is told by text that it failed
                self.log(f'text reply failed: {type(error).__name__}: {error}')
            await self.text(to, answer.strip() or self.config.lines.trouble)

    async def text(self, to: str, body: str) -> dict[str, Any]:
        if not self.owner(to):
            raise ValueError('Texts go only to the numbers in twilio_owner_numbers.')
        answer = await asyncio.to_thread(self.client.text, to=to, from_=self.config.twilio_number, body=body)
        self.log(f'texted the owner, message {answer.get("sid", "?")}')
        return answer

    # ------------------------------------------------------------------------------------------- calls placed

    def reserve(self, own: bool = False) -> str | None:
        """Why a call cannot be placed now, or None when it can, its place then taken: no call in progress, and for a
        call Metaform places on its own, twilio_call_gap_minutes since the last. The notifier asks this before it counts
        a signal as told, so a call held back is placed later rather than dropped."""
        with self.placing:
            if self.active is not None:
                return 'a call is in progress'
            now = self.clock()
            if not own and now - self.last_placed < self.config.call_gap:
                return 'a call was placed within twilio_call_gap_minutes'
            self.last_placed = now
            return None

    async def call(self, reason: str, *, to: str | None = None, own: bool = False,
                   reserved: bool = False) -> dict[str, Any]:
        """Ring the owner. A call Metaform places on its own waits twilio_call_gap_minutes after the last; the person's
        own `twilio call` does not wait. `reserved`: `reserve` already took its place."""
        to = to or (self.config.owners[0] if self.config.owners else '')
        if not self.owner(to):
            raise ValueError('Calls go only to the numbers in twilio_owner_numbers.')
        held = None if reserved else self.reserve(own)
        if held is not None:
            return {'placed': False, 'why': held}
        answer = await asyncio.to_thread(self.client.call, to=to, from_=self.config.twilio_number,
                                         url=self.public('/phone/voice'))
        sid = str(answer.get('sid') or '')
        if sid:
            self.placed[sid] = reason
        self.log(f'placed call {sid or "?"} to the owner')
        return {'placed': bool(sid), 'sid': sid or None}

    def spawn(self, work: Any) -> None:
        task = asyncio.ensure_future(work)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    # ------------------------------------------------------------------------------------------- control

    async def control(self, request: Request) -> Response:
        """The person's own `twilio call` and `twilio text`, from this machine: from loopback, or from the address the
        bridge listens on when that is one of this machine's own, never through a proxy, and only with the control
        token from the run file, which only the person's account can read."""
        peer = request.client.host if request.client else ''
        proxied = any(name in request.headers for name in ('x-forwarded-for', 'forwarded', 'x-real-ip'))
        given = request.headers.get('authorization', '').removeprefix('Bearer ').strip()
        own = peer in LOOPBACK or (peer == self.config.bind and self.config.bind not in ('0.0.0.0', '::'))
        if not own or proxied or not given or \
                not hmac.compare_digest(given, self.config.control_token):
            return PlainTextResponse('Not found.', status_code=404)
        try:
            asked: Any = json.loads(await request.body() or b'{}')
        except ValueError:
            return JSONResponse({'error': 'Not JSON.'}, status_code=400)
        asked = cast(dict[str, Any], asked) if isinstance(asked, dict) else {}
        try:
            if request.url.path == '/control/call':
                done = await self.call(str(asked.get('reason') or 'you asked me to call'), to=asked.get('to'), own=True)
            else:
                done = await self.text(str(asked.get('to') or self.config.owners[0]), str(asked.get('text') or ''))
                done = {'sent': True, 'sid': done.get('sid')}
        except (OSError, ValueError, IndexError) as error:
            return JSONResponse({'error': str(error)}, status_code=400)
        return JSONResponse(done)

    def app(self) -> Starlette:
        async def health(request: Request) -> Response:
            return PlainTextResponse('ok')
        return Starlette(routes=[
            Route('/phone/voice', self.voice_hook, methods=['POST']),
            Route('/phone/pin', self.pin_hook, methods=['POST']),
            Route('/phone/sms', self.sms_hook, methods=['POST']),
            Route('/phone/health', health, methods=['GET']),
            WebSocketRoute('/phone/stream', self.stream),
            Route('/control/call', self.control, methods=['POST']),
            Route('/control/text', self.control, methods=['POST']),
        ])


def _xml(twiml: str) -> Response:
    return Response(twiml, media_type='application/xml')
