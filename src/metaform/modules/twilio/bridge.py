"""One phone call, bridged: Twilio's Media Streams messages in, the system agent's spoken answers out.

    caller's mu-law frames -> voice.transcribe_stream (its endpointing ends an utterance at a pause)
      -> the system agent (dispatch message) -> its answer, sentence by sentence as it grows
      -> voice.speak(sentence) -> mu-law frames -> Twilio, with a mark after each sentence

Barge-in: while audio is playing, a caller who speaks for BARGE_SECONDS, or whose speech the voice module hears as a
partial, stops it: the bridge sends Twilio's `clear`, which empties the audio Twilio holds, and stops speaking the
answer. The agent itself is never stopped; its whole answer stays in the chat thread. A hang-up, a `stop` message or
an error ends the call and leaves the agent running.

Messages, https://www.twilio.com/docs/voice/media-streams/websocket-messages: Twilio sends `connected`, `start` (with
the stream and call SIDs and the custom parameters), `media` (base64 mu-law, 8 kHz), `mark` (a mark of ours, played),
`dtmf` and `stop`; the bridge sends `media`, `mark` and `clear`, each with the stream's SID.
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import queue
import re
import threading
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import Any

from . import mulaw
from .agent import Agent
from .engines import Voice

Send = Callable[[dict[str, Any]], Awaitable[None]]
Log = Callable[[str], None]

BARGE_SECONDS = 0.2   # voiced audio while the agent speaks that stops it
BARGE_LEVEL = 900.0   # the loudness, after the line's own noise, that counts as voiced for barge-in
SEND_BYTES = mulaw.FRAME * 10  # 200 ms per media message: fine enough that a clear stops it promptly
SENTENCE = re.compile(r'(.+?[.!?](?:["\')\]]+)?)(?=\s)', re.DOTALL)


def spoken(text: str) -> str:
    """Text as it is said: code, markdown marks and link targets left out."""
    text = re.sub(r'```.*?```', ' ', text, flags=re.DOTALL)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'https?://\S+', 'a link', text)
    text = re.sub(r'[`*_#>|]+', '', text)
    return ' '.join(text.split())


def sentences(text: str) -> tuple[list[str], str]:
    """The finished sentences at the start of `text`, and what follows them, not yet finished."""
    found: list[str] = []
    at = 0
    for match in SENTENCE.finditer(text):
        found.append(match.group(1).strip())
        at = match.end()
    return [one for one in found if one], text[at:]


class Call:
    """One call's bridge. `run` takes the stream's messages after `start` and returns when the call ends."""

    def __init__(self, send: Send, voice: Voice, agent: Agent, *, stream_sid: str, opening: str, framing: str,
                 trouble: str, log: Log, clock: Callable[[], float] = time.monotonic) -> None:
        self.send, self.voice, self.agent = send, voice, agent
        self.stream_sid, self.opening, self.framing, self.trouble = stream_sid, opening, framing, trouble
        self.log, self.clock = log, clock
        self.audio_in: queue.Queue[bytes | None] = queue.Queue()
        self.heard: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self.speech: asyncio.Task[None] | None = None   # the answer being spoken, cancelled by barge-in
        self.playing = 0          # marks sent and not yet played back by Twilio
        self.marks = 0
        self.voiced = 0.0         # seconds of voiced caller audio running, while the agent speaks
        self.floor = 200.0        # the line's own noise level, followed as the call goes
        self.last_voiced = 0.0    # when the caller was last heard speaking, by the clock
        self.turns = 0
        self.barge_ins = 0
        self.latencies: list[float] = []  # seconds from the end of the caller's speech to the first audio back
        self.waiting_since: float | None = None
        self.framed = False
        self.ended = False

    # ------------------------------------------------------------------------------------------------ sending

    async def _send(self, message: dict[str, Any]) -> None:
        if not self.ended:
            await self.send({**message, 'streamSid': self.stream_sid})

    async def _media(self, audio: bytes) -> None:
        if self.waiting_since is not None:
            self.latencies.append(self.clock() - self.waiting_since)
            self.waiting_since = None
        await self._send({'event': 'media', 'media': {'payload': base64.b64encode(audio).decode('ascii')}})

    async def say(self, text: str) -> None:
        """Speak `text` to the caller: the voice's audio sent as it is made, then a mark, so the bridge knows when
        Twilio has played it."""
        text = spoken(text)
        if not text:
            return
        chunks: Iterator[bytes] = await asyncio.to_thread(self.voice.speak, text)
        held = b''
        while True:
            chunk = await asyncio.to_thread(next, chunks, None)
            if chunk is None:
                break
            held += chunk
            while len(held) >= SEND_BYTES:
                await self._media(held[:SEND_BYTES])
                held = held[SEND_BYTES:]
        if held:
            await self._media(held)
        self.marks += 1
        self.playing += 1
        await self._send({'event': 'mark', 'mark': {'name': f'said-{self.marks}'}})

    def speaking(self) -> bool:
        """Whether the caller hears the agent now: an answer is being sent, or Twilio has not yet played all of it."""
        return (self.speech is not None and not self.speech.done()) or self.playing > 0

    async def barge(self) -> None:
        """The caller speaks over the agent: Twilio's held audio is cleared and the answer is no longer spoken."""
        if not self.speaking():
            return
        self.barge_ins += 1
        self.log(f'barge-in on stream {self.stream_sid}')
        await self._send({'event': 'clear'})
        self.playing, self.voiced = 0, 0.0
        if self.speech is not None and not self.speech.done():
            self.speech.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self.speech
        self.speech = None

    # ------------------------------------------------------------------------------------------------ the agent

    async def answer(self, words: str) -> None:
        """The agent's answer to the caller's words, spoken a sentence at a time as it comes."""
        message = f'{self.framing}\n\n{words}' if self.framing and not self.framed else words
        self.framed = True
        self.turns += 1
        told = ''
        rest = ''
        try:
            async for so_far in self.agent.reply(message):
                fresh = so_far.removeprefix(told)
                told = so_far
                done, rest = sentences(rest + fresh)
                for sentence in done:
                    await self.say(sentence)
            if rest.strip():
                await self.say(rest)
            if not told:
                await self.say(self.trouble)
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001  the caller hears that it failed; the call goes on
            self.log(f'answer failed on stream {self.stream_sid}: {type(error).__name__}: {error}')
            with contextlib.suppress(Exception):
                await self.say(self.trouble)

    def _speak(self, work: Awaitable[None]) -> None:
        async def run() -> None:
            await work
        self.speech = asyncio.ensure_future(run())

    # ------------------------------------------------------------------------------------------------ hearing

    def _hear(self, loop: asyncio.AbstractEventLoop) -> None:
        def chunks() -> Iterator[bytes]:
            while (chunk := self.audio_in.get()) is not None:
                yield chunk
        try:
            for heard in self.voice.transcribe_stream(chunks()):
                loop.call_soon_threadsafe(self.heard.put_nowait, heard)
        except Exception as error:  # noqa: BLE001  said in the log and to the caller
            self.log(f'hearing failed on stream {self.stream_sid}: {type(error).__name__}: {error}')
            loop.call_soon_threadsafe(self.heard.put_nowait, {'error': str(error)})
        finally:
            loop.call_soon_threadsafe(self.heard.put_nowait, None)

    async def _heard(self) -> None:
        while (heard := await self.heard.get()) is not None:
            if heard.get('error'):
                await self.barge()
                self._speak(self.say(self.trouble))
                continue
            text = str(heard.get('text') or '').strip()
            if not heard.get('final'):
                if text and self.speaking():
                    await self.barge()
                continue
            if not text:
                continue
            await self.barge()  # a new utterance ends whatever was still being said
            self.waiting_since = self.last_voiced or self.clock()
            self._speak(self.answer(text))

    def _level(self, chunk: bytes) -> None:
        """Follow the caller's loudness: when they last spoke, and whether they speak over the agent."""
        level = mulaw.loudness(chunk)
        seconds = len(chunk) / mulaw.RATE
        voiced = level > max(self.floor * 3, BARGE_LEVEL)
        if not voiced:
            self.floor = self.floor * 0.95 + level * 0.05
            self.voiced = 0.0
            return
        self.last_voiced = self.clock()
        if self.speaking():
            self.voiced += seconds

    # ------------------------------------------------------------------------------------------------ the call

    async def run(self, messages: AsyncIterator[dict[str, Any]]) -> None:
        loop = asyncio.get_running_loop()
        hearing = threading.Thread(target=self._hear, args=(loop,), name=f'twilio-hear-{self.stream_sid}', daemon=True)
        hearing.start()
        listening = asyncio.ensure_future(self._heard())
        ready = asyncio.ensure_future(self.agent.prepare())
        if self.opening:
            self._speak(self.say(self.opening))
        try:
            async for message in messages:
                event = message.get('event')
                if event == 'media':
                    media: dict[str, Any] = message.get('media') or {}
                    if media.get('track', 'inbound') != 'inbound':
                        continue
                    try:
                        chunk = base64.b64decode(str(media.get('payload') or ''), validate=True)
                    except ValueError:
                        continue
                    self._level(chunk)
                    self.audio_in.put(chunk)
                    if self.voiced >= BARGE_SECONDS:
                        await self.barge()
                elif event == 'mark':
                    self.playing = max(0, self.playing - 1)
                elif event == 'stop':
                    break
        finally:
            self.ended = True
            self.audio_in.put(None)
            for task in (self.speech, ready):
                if task is not None and not task.done():
                    task.cancel()
            await asyncio.sleep(0)
            listening.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await listening
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await ready
            self.log(f'call on stream {self.stream_sid} ended after {self.turns} turns, {self.barge_ins} barge-ins')
