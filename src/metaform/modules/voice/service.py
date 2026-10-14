"""The voice module's speech for a server-side caller, such as a phone bridge: what it provides as `voice`.

A module never imports voice; it finds this through the public base, and it is there only while voice is enabled:

    from metaform.module import provided

    found = provided(folder, 'voice')            # [('voice', VOICE)] while voice is enabled, else []
    voice = found[0][1]
    for chunk in voice.speak(folder, 'Hello, this is Metaform.', format='phone', character='owl'):
        send_to_the_call(chunk)                   # ulaw_8000 with elevenlabs's default phone format
    for heard in voice.transcribe_stream(folder, chunks_from_the_call, format='ulaw_8000'):
        if heard['final']:
            act_on(heard['text'])

`speak` streams the audio of the engine the person chose in voice_tts, an engine a module brings, such as elevenlabs;
the browser's voices speak only in a page. `transcribe` and `transcribe_stream` hear with the engine in voice_engine:
Whisper on this machine (server, and auto and browser, which have no server side of their own, mean it here) or an
engine a module brings, which then receives the audio. Every refusal is a `Stop` with the next step.

Formats in: 'ulaw_8000', the telephone's 8 kHz mu-law, and 'pcm_<rate>', 16-bit little-endian mono at that rate.
Formats out: 'page', 'phone' (the engine's own setting for each), or one of the engine's own formats.

`speak` takes `voice=`, a voice id of the engine's own, such as an ElevenLabs voice id, for a caller with a voice
setting of its own: it speaks in place of the character's voice with an engine whose speak takes a `voice` keyword;
any other engine speaks with the character's voice. Without it, `speak` is as it was.
"""
from __future__ import annotations

import array
import math
import secrets
import struct
import time
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from metaform import home
from metaform import module as chassis
from metaform.module import Stop

RATES = {'ulaw_8000': 8000, 'pcm_8000': 8000, 'pcm_16000': 16000, 'pcm_22050': 22050, 'pcm_24000': 24000,
         'pcm_44100': 44100, 'pcm_48000': 48000}
PAUSE = 0.8           # seconds of quiet that end an utterance on a call
PARTIAL_EVERY = 1.0   # seconds between partial passes of the utterance so far
LONGEST = 30.0        # seconds: an utterance this long is heard and a new one begun


def _ulaw_table() -> list[int]:
    """G.711 mu-law to 16-bit linear, the 256 values a byte of telephone audio stands for."""
    table: list[int] = []
    for byte in range(256):
        value = ~byte & 0xFF
        sign, exponent, mantissa = value & 0x80, (value >> 4) & 0x07, value & 0x0F
        sample = (((mantissa << 3) + 0x84) << exponent) - 0x84
        table.append(-sample if sign else sample)
    return table


ULAW = _ulaw_table()


def pcm16(chunk: bytes, format: str) -> array.array[int]:
    """One chunk of `format` audio as 16-bit samples: mu-law decoded, or little-endian PCM read as it is."""
    if format == 'ulaw_8000':
        return array.array('h', (ULAW[byte] for byte in chunk))
    samples = array.array('h')
    samples.frombytes(chunk[:len(chunk) - len(chunk) % 2])
    return samples


def wav(samples: array.array[int], rate: int) -> bytes:
    data = samples.tobytes()
    return (b'RIFF' + struct.pack('<I', 36 + len(data)) + b'WAVEfmt '
            + struct.pack('<IHHIIHH', 16, 1, 1, rate, rate * 2, 2, 16) + b'data' + struct.pack('<I', len(data)) + data)


def _voice_verb(folder: Path, name: str, arguments: dict[str, Any]) -> Any:
    """One of voice's own verbs, run as a tool call runs it, so settings and refusals are the command's own."""
    found = next((one for one in chassis.surface(folder) if one.id == 'voice'), None)
    run = next((one for one in found.verbs if one.name == name), None) if found is not None else None
    if run is None:
        raise Stop('Voice is not on here.', 'metaform enable voice')
    nouns, switches, _ = chassis.tool_arguments('voice', run, arguments, folder=folder)
    ctx = chassis.context('voice', folder, nouns=nouns, switches=switches, sink=lambda text: None, surface='web')
    return chassis.call(run.run, ctx)


class Voice:
    """Speak and hear for a caller with no page: each method takes the folder whose settings and modules apply."""

    def speak(self, folder: Path, text: str, *, format: str = 'phone', character: str | None = None,
              engine: str | None = None, voice: str | None = None) -> Iterator[bytes]:
        """`text` spoken as an iterator of audio chunks in `format` by voice_tts's engine, or `engine`. `voice`, a voice
        id of the engine's own, speaks in place of the character's voice when the engine takes one."""
        found = _voice_verb(folder, 'speak', {'text': [text], 'format': format,
                                              **({'character': character} if character else {}),
                                              **({'engine': engine} if engine else {}),
                                              **({'voice': voice} if voice else {})})
        return iter(found['stream'])

    def transcribe(self, folder: Path, path: Path, *, language: str | None = None, engine: str | None = None,
                   partial: bool = False) -> dict[str, Any]:
        """An audio file's `{'text', 'segments', 'engine', ...}`; `{'busy': True}` for a partial while one runs."""
        return dict(_voice_verb(folder, 'transcribe', {'file': str(path), **({'language': language} if language else {}),
                                                       **({'engine': engine} if engine else {}),
                                                       **({'partial': True} if partial else {})}))

    def transcribe_stream(self, folder: Path, chunks: Iterable[bytes], format: str = 'ulaw_8000', *,
                          language: str | None = None, engine: str | None = None,
                          partials: bool = True) -> Iterator[dict[str, Any]]:
        """Hear a stream of audio chunks and yield `{'text', 'final': False}` for each partial while an utterance goes
        on, and `{'text', 'final': True}` when a pause ends it. Silence is never transcribed. Partials come only from
        Whisper here; an engine a module brings is asked once per utterance."""
        if format not in RATES:
            raise ValueError(f'{format} is not a format transcribe_stream reads: {", ".join(RATES)}.')
        rate = RATES[format]
        floor, speaking, quiet = 200.0, False, 0.0
        utterance, last_partial = array.array('h'), 0.0
        for chunk in chunks:
            samples = pcm16(chunk, format)
            if not samples:
                continue
            rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
            floor = floor * 0.7 + rms * 0.3 if rms < floor else floor * 0.995 + rms * 0.005
            if rms > max(floor * 3, 300):
                speaking, quiet = True, 0.0
            elif speaking:
                quiet += len(samples) / rate
            if not speaking:
                continue
            utterance.extend(samples)
            length = len(utterance) / rate
            if quiet >= PAUSE or length >= LONGEST:
                text = self._hear(folder, utterance, rate, language=language, engine=engine, partial=False)
                if text:
                    yield {'text': text, 'final': True}
                utterance, speaking, quiet, last_partial = array.array('h'), False, 0.0, 0.0
            elif partials and time.monotonic() - last_partial > PARTIAL_EVERY and length > 0.6:
                last_partial = time.monotonic()
                text = self._hear(folder, utterance, rate, language=language, engine=engine, partial=True)
                if text:
                    yield {'text': text, 'final': False}
        if speaking and len(utterance) / rate > 0.3:
            text = self._hear(folder, utterance, rate, language=language, engine=engine, partial=False)
            if text:
                yield {'text': text, 'final': True}

    def _hear(self, folder: Path, samples: array.array[int], rate: int, *, language: str | None, engine: str | None,
              partial: bool) -> str | None:
        place = home.home() / 'run' / 'voice' / 'heard'
        home.mkdir_private(place)
        path = place / f'{secrets.token_hex(16)}.wav'
        home.write_private(path, wav(samples, rate))
        try:
            heard = self.transcribe(folder, path, language=language, engine=engine, partial=partial)
        finally:
            path.unlink(missing_ok=True)
        return None if heard.get('busy') else str(heard.get('text') or '') or None


VOICE = Voice()
