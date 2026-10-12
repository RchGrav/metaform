"""The voice on the call: speech in and out through the voice module, never duplicated here.

The voice module provides a server-side caller its speech as `voice`, through the public base's `provided`, only while
it is enabled on the folder:

  speak(folder, text, *, format='phone', character=None, engine=None, voice=None) -> Iterator[bytes]
  transcribe_stream(folder, chunks, format='ulaw_8000', *, language=None, engine=None, ...) -> Iterator[dict]

`speak` streams the audio of the engine in voice_tts (ElevenLabs, for a call) as it is made, in twilio_voice when it is
set and the mascot character's voice otherwise; `transcribe_stream` cuts
the caller's audio into utterances at pauses, its endpointing, and yields `{'text', 'final'}` for each partial and each
finished utterance. When voice is off, `twilio status` says so plainly.

`ScriptedVoice` stands in for both in the simulated call: no engine, no network.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, Protocol

from metaform.module import provided

from . import mulaw

FORMAT = 'ulaw_8000'
PAUSE = 0.8  # seconds of quiet that end an utterance, the voice module's own for a call, when it cannot be read


class Voice(Protocol):
    pause: float

    def speak(self, text: str) -> Iterator[bytes]:
        """`text` as 8 kHz mu-law audio, chunk by chunk as it is made."""
        ...

    def transcribe_stream(self, chunks: Iterable[bytes]) -> Iterator[dict[str, Any]]:
        """The caller's mu-law audio heard: `{'text', 'final': False}` partials, `{'text', 'final': True}` at each
        pause that ends an utterance."""
        ...


def voice_module(folder: Path) -> Any | None:
    """The speech the voice module provides, when it is on this folder's surface and offers both halves."""
    for _, found in provided(folder, 'voice'):
        if callable(getattr(found, 'speak', None)) and callable(getattr(found, 'transcribe_stream', None)):
            return found
    return None


class VoicePhone:
    """The voice module's speech, with the person's phone settings: `voice`, twilio_voice, speaks in place of the
    character's voice when it is set."""

    def __init__(self, found: Any, folder: Path, *, character: str | None, language: str | None,
                 hearing: str, voice: str | None = None) -> None:
        self.found, self.folder = found, folder
        self.character, self.language, self.hearing, self.voice = character, language, hearing, voice
        self.pause = float(getattr(found, 'pause', PAUSE))

    def speak(self, text: str) -> Iterator[bytes]:
        chosen = {'voice': self.voice} if self.voice else {}  # only when set, so an older voice module still speaks
        return self.found.speak(self.folder, text, format=FORMAT, character=self.character, **chosen)

    def transcribe_stream(self, chunks: Iterable[bytes]) -> Iterator[dict[str, Any]]:
        return self.found.transcribe_stream(self.folder, chunks, FORMAT, language=self.language, engine=self.hearing)


class ScriptedVoice:
    """Speech with no engine, for the simulated call: an utterance ends after `pause` seconds of quiet, measured in the
    audio itself as the voice module measures it, and is heard as the next line of `heard`; anything spoken is a tone
    as long as the words would take. A partial is given once an utterance has gone on `partial_after` seconds."""

    def __init__(self, heard: list[str] | None = None, *, pause: float = PAUSE, partial_after: float = 0.3,
                 seconds_per_word: float = 0.05) -> None:
        self.heard = list(heard or [])
        self.pause, self.partial_after, self.seconds_per_word = pause, partial_after, seconds_per_word
        self.spoken: list[str] = []

    def speak(self, text: str) -> Iterator[bytes]:
        self.spoken.append(text)
        audio = mulaw.tone(max(0.2, self.seconds_per_word * len(text.split())), 440.0)
        return iter(mulaw.frames(audio, 800))

    def transcribe_stream(self, chunks: Iterable[bytes]) -> Iterator[dict[str, Any]]:
        speaking, quiet, length, partial = False, 0.0, 0.0, False
        for chunk in chunks:
            seconds = len(chunk) / mulaw.RATE
            if mulaw.loudness(chunk) > 500:
                speaking, quiet = True, 0.0
                length += seconds
                if not partial and length >= self.partial_after:
                    partial = True
                    yield {'text': '…', 'final': False}
            elif speaking:
                quiet += seconds
                if quiet >= self.pause:
                    yield {'text': self.heard.pop(0) if self.heard else 'Hello?', 'final': True}
                    speaking, quiet, length, partial = False, 0.0, 0.0, False
