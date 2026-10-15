"""A whole phone call, simulated on this machine: Twilio's side played by a local client, the bridge real.

The bridge runs as `twilio serve` runs it, uvicorn on a loopback port, with a scripted agent and a scripted voice and a
Twilio client that records what it would send; no network, no credential, no agent. The client does what Twilio does:
it posts a signed Voice webhook, reads the TwiML, opens the Media Stream with the token in it, and sends the caller's
speech as 20 ms mu-law frames in real time, while it plays the audio it receives at the speed a phone would and sends
each mark back once its audio has played. It measures the time from the end of the caller's speech to the first audio
back, speaks over an answer to see the bridge clear it, and checks what must be refused is refused.
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import re
import secrets
import time
import urllib.parse
from typing import Any

from . import api, mulaw
from .agent import ScriptedAgent
from .engines import PAUSE, ScriptedVoice
from .server import Config, Lines, Phone, Serving

OWNER = '+15550100001'
NUMBER = '+15550100002'
STRANGER = '+15550100009'
PUBLIC = 'https://phone.invalid'


class Recorded:
    """Twilio's REST API as the simulation sees it: each request kept, a made-up SID answered, nothing sent."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def __call__(self, url: str, form: dict[str, str], auth: tuple[str, str]) -> dict[str, Any]:
        self.requests.append({'url': url, 'form': dict(form), 'user': auth[0]})
        prefix = 'CA' if url.endswith('/Calls.json') else 'SM'
        return {'sid': prefix + secrets.token_hex(16)}


class Line:
    """Twilio's end of the stream: plays what it receives in real time and sends each mark back when played."""

    def __init__(self, socket: Any, stream_sid: str) -> None:
        self.socket, self.stream_sid = socket, stream_sid
        self.received: list[tuple[float, dict[str, Any]]] = []
        self.played_until = 0.0
        self.pending: list[tuple[float, str]] = []
        self.cleared = 0

    async def listen(self) -> None:
        async for text in self.socket:
            message = json.loads(text)
            now = time.monotonic()
            self.received.append((now, message))
            event = message.get('event')
            if event == 'media':
                seconds = len(base64.b64decode(message['media']['payload'])) / mulaw.RATE
                self.played_until = max(self.played_until, now) + seconds
            elif event == 'mark':
                self.pending.append((max(self.played_until, now), message['mark']['name']))
            elif event == 'clear':
                self.cleared += 1
                self.played_until = now
                for _, name in self.pending:  # Twilio returns the marks of the audio a clear dropped
                    await self.send({'event': 'mark', 'mark': {'name': name}})
                self.pending = []

    async def send(self, message: dict[str, Any]) -> None:
        await self.socket.send(json.dumps({**message, 'streamSid': self.stream_sid}))

    async def tick(self) -> None:
        now = time.monotonic()
        due = [one for one in self.pending if one[0] <= now]
        self.pending = [one for one in self.pending if one[0] > now]
        for _, name in due:
            await self.send({'event': 'mark', 'mark': {'name': name}})

    def audio_after(self, moment: float) -> float | None:
        return next((at for at, message in self.received if message.get('event') == 'media' and at > moment), None)

    def playing(self) -> bool:
        return bool(self.pending) or self.played_until > time.monotonic()

    async def frame(self, chunk: bytes) -> None:
        await self.send({'event': 'media', 'media': {'track': 'inbound', 'payload': base64.b64encode(chunk).decode()}})
        await asyncio.sleep(len(chunk) / mulaw.RATE)
        await self.tick()

    async def speak(self, seconds: float, audio: bytes | None = None) -> float:
        """The caller says something, `audio` in mu-law or a tone `seconds` long; the time their last voiced frame
        went."""
        for chunk in mulaw.frames(audio if audio is not None else mulaw.tone(seconds)):
            await self.frame(chunk)
        return time.monotonic()

    async def quiet_until(self, check: Any, limit: float) -> bool:
        deadline = time.monotonic() + limit
        while time.monotonic() < deadline:
            if check():
                return True
            await self.frame(mulaw.silence(0.02))
        return bool(check())


def sign(token: str, path: str, form: dict[str, str]) -> dict[str, str]:
    return {'X-Twilio-Signature': api.signature(token, PUBLIC + path, form.items()),
            'Content-Type': 'application/x-www-form-urlencoded'}


async def run(*, pause: float = PAUSE, agent_delay: float = 0.0, speech: bytes | None = None) -> dict[str, Any]:
    """One simulated call, end to end; what it measured and what it checked. `speech` is the caller's first
    utterance as 8 kHz mu-law, a tone by default."""
    import httpx
    import uvicorn
    from websockets.asyncio.client import connect

    token = secrets.token_hex(20)  # a made-up auth token for this simulation alone
    recorded = Recorded()
    log: list[str] = []
    agent = ScriptedAgent(['Your board has three tickets waiting. The first is the parser fix. Shall I start it?',
                           'Done. I started it, and I will text you when it lands.'], delay=agent_delay)
    voice = ScriptedVoice(['What is on my board?', 'Wait, stop.'], pause=pause, seconds_per_word=0.12)
    pin = ''.join(secrets.choice('0123456789') for _ in range(6))  # a made-up PIN, entered on the simulated keypad
    config = Config(public_url=PUBLIC, twilio_number=NUMBER, owners=(OWNER,), auth_token=token,
                    control_token=secrets.token_hex(20), proof='attested-or-pin', pin=pin,
                    lines=Lines(greeting="Hi, it's owl.", on_call='(by phone)'))
    phone = Phone(config, agent=lambda: agent, voice=lambda: voice,
                  client=api.Client(post=recorded, creds=lambda: ('AC' + '0' * 32, ('AC' + '0' * 32, 'simulated'))),
                  log=log.append)
    server = Serving(uvicorn.Config(phone.app(), host='127.0.0.1', port=0, ws='websockets-sansio',
                                    log_level='warning', lifespan='off'))
    serving = asyncio.ensure_future(server.serve())
    ready = asyncio.ensure_future(server.ready.wait())
    await asyncio.wait({serving, ready}, return_when=asyncio.FIRST_COMPLETED)
    if not ready.done():  # it ended without listening: its error is the simulation's
        ready.cancel()
        await serving
    port = server.servers[0].sockets[0].getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    checks: dict[str, Any] = {}
    try:
        async with httpx.AsyncClient(base_url=base, timeout=10) as http:
            call = {'CallSid': 'CA' + secrets.token_hex(16), 'From': OWNER, 'To': NUMBER, 'Direction': 'inbound'}
            unsigned = await http.post('/phone/voice', data=call)
            checks['unsigned_refused'] = unsigned.status_code == 403
            stranger = {**call, 'CallSid': 'CA' + secrets.token_hex(16), 'From': STRANGER}  # its own call
            refused = await http.post('/phone/voice', content=urllib.parse.urlencode(stranger),
                                      headers=sign(token, '/phone/voice', stranger))
            checks['stranger_refused'] = '<Hangup/>' in refused.text and '<Stream' not in refused.text
            # the owner's number, but a caller ID its carrier did not attest: it could be faked, so the PIN is asked
            asked = await http.post('/phone/voice', content=urllib.parse.urlencode(call),
                                    headers=sign(token, '/phone/voice', call))
            checks['pin_asked'] = '<Gather' in asked.text and '<Stream' not in asked.text
            again = await http.post('/phone/voice', content=urllib.parse.urlencode(call),
                                    headers=sign(token, '/phone/voice', call))
            checks['replay_refused'] = '<Gather' not in again.text and '<Stream' not in again.text
            entered = {**call, 'Digits': pin}
            answered = await http.post('/phone/pin', content=urllib.parse.urlencode(entered),
                                       headers=sign(token, '/phone/pin', entered))
        twiml = answered.text
        url = re.search(r'<Stream url="([^"]+)"', twiml)
        minted = re.search(r'<Parameter name="token" value="([^"]+)"', twiml)
        checks['twiml_streams'] = bool(url and minted) and url is not None and url.group(1) == 'wss://phone.invalid/phone/stream'
        stream_sid = 'MZ' + secrets.token_hex(16)
        start: dict[str, Any] = {'event': 'start', 'sequenceNumber': '1', 'start': {
            'streamSid': stream_sid, 'callSid': call['CallSid'], 'tracks': ['inbound'],
            'mediaFormat': {'encoding': 'audio/x-mulaw', 'sampleRate': 8000, 'channels': 1},
            'customParameters': {'token': 'not-the-token'}}, 'streamSid': stream_sid}
        async with connect(f'ws://127.0.0.1:{port}/phone/stream') as forged:
            await forged.send(json.dumps({'event': 'connected', 'protocol': 'Call', 'version': '1.0.0'}))
            await forged.send(json.dumps(start))
            try:
                await asyncio.wait_for(forged.recv(), 2)
                checks['forged_stream_refused'] = False
            except Exception:  # noqa: BLE001  closed by the bridge, as it should be
                checks['forged_stream_refused'] = True
        start['start'] = {**start['start'], 'customParameters': {'token': minted.group(1) if minted else ''}}
        async with connect(f'ws://127.0.0.1:{port}/phone/stream') as socket:
            line = Line(socket, stream_sid)
            listening = asyncio.ensure_future(line.listen())
            await socket.send(json.dumps({'event': 'connected', 'protocol': 'Call', 'version': '1.0.0'}))
            await socket.send(json.dumps(start))
            began = time.monotonic()
            checks['greeted'] = await line.quiet_until(lambda: line.audio_after(began) is not None, 3)
            await line.quiet_until(lambda: not line.playing(), 10)
            ended = await line.speak(0.8, speech)
            answered_at = await line.quiet_until(lambda: line.audio_after(ended) is not None, pause + 5)
            first = line.audio_after(ended)
            latency = (first - ended) if answered_at and first else None
            # The caller speaks over the answer while it plays: the bridge must clear it.
            await line.quiet_until(lambda: False, 0.3)
            cleared_before = line.cleared
            await line.speak(0.4)
            await line.quiet_until(lambda: line.cleared > cleared_before, 2)
            checks['barge_in_cleared'] = line.cleared > cleared_before
            await line.quiet_until(lambda: False, pause + 0.5)
            await line.send({'event': 'stop', 'stop': {'callSid': call['CallSid']}})
            await asyncio.sleep(0.2)
            listening.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await listening
        bridged = phone.calls[-1] if phone.calls else None
        checks['agent_heard'] = agent.heard[:1] == ['(by phone)\n\nWhat is on my board?']
        checks['call_ended_cleanly'] = phone.active is None
        result: dict[str, Any] = {
            'ok': all(value for value in checks.values()) and latency is not None,
            'checks': checks,
            'latency_ms': round(latency * 1000) if latency is not None else None,
            'endpointing_pause_ms': round(pause * 1000),
            'bridge_ms': round((latency - pause) * 1000) if latency is not None else None,
            'bridge_latencies_ms': [round(one * 1000) for one in (bridged.latencies if bridged else [])],
            'turns': bridged.turns if bridged else 0, 'barge_ins': bridged.barge_ins if bridged else 0,
            'spoken': voice.spoken, 'heard_by_agent': agent.heard, 'log': log,
            'rest_requests': recorded.requests}
        return result
    finally:
        server.stop()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(serving, 5)
