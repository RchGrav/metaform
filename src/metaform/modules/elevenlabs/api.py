"""ElevenLabs over HTTP: text to speech, streamed, the voices and models on the person's account, and Scribe.

Everything here runs only while ELEVENLABS_API_KEY is in the environment of the process that calls it. The key is read
for each request and sent only to ElevenLabs, as its `xi-api-key` header; it is never stored, logged, returned or sent
to the page. Text to speak goes to ElevenLabs, and so does audio to transcribe; each setting that chooses it says so.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

KEY = 'ELEVENLABS_API_KEY'
API = 'https://api.elevenlabs.io/v1'
TIMEOUT = 30
CHUNK = 4096
MAX_CHARS = 2500  # one reply spoken; longer text is cut at a sentence and the rest left to the chat
PAGE_FORMATS = ('mp3_44100_128', 'mp3_22050_32', 'pcm_16000', 'pcm_22050', 'pcm_24000')
PHONE_FORMATS = ('ulaw_8000', 'pcm_8000', 'pcm_16000')
FORMATS = tuple(dict.fromkeys((*PAGE_FORMATS, *PHONE_FORMATS)))
TYPES = {'mp3': 'audio/mpeg', 'pcm': 'audio/L16', 'ulaw': 'audio/basic'}
MODELS = ('eleven_flash_v2_5', 'eleven_turbo_v2_5', 'eleven_multilingual_v2', 'eleven_v3', 'eleven_flash_v2',
          'eleven_turbo_v2', 'eleven_monolingual_v1')
_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = threading.Lock()
LISTED_FOR = 600.0  # seconds the account's voices and models are kept before they are asked for again


def available() -> bool:
    """Whether ElevenLabs can be used here: its key is in this process's environment. The key is never returned."""
    return bool(os.environ.get(KEY, '').strip())


def _key() -> str:
    key = os.environ.get(KEY, '').strip()
    if not key:
        raise OSError(f'{KEY} is not in the environment of the process that serves the page.')
    return key


def _refused(error: urllib.error.HTTPError) -> OSError:
    said = error.read()[:300].decode('utf-8', 'replace')
    return OSError(f'ElevenLabs answered {error.code}: {said}')


def _get(path: str, timeout: float = TIMEOUT) -> Any:
    request = urllib.request.Request(f'{API}{path}', headers={'xi-api-key': _key(), 'User-Agent': 'metaform-voice'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as answer:
            return json.loads(answer.read() or b'null')
    except urllib.error.HTTPError as error:
        raise _refused(error) from None


def _kept(name: str, read: Any) -> Any:
    with _cache_lock:
        held = _cache.get(name)
        if held is not None and time.monotonic() - held[0] < LISTED_FOR:
            return held[1]
    found = read()
    with _cache_lock:
        _cache[name] = (time.monotonic(), found)
    return found


def media_type(output: str) -> str:
    return TYPES.get(output.split('_', 1)[0], 'application/octet-stream')


def trimmed(text: str) -> str:
    text = ' '.join(text.split())
    if len(text) <= MAX_CHARS:
        return text
    cut = text[:MAX_CHARS]
    end = max(cut.rfind('. '), cut.rfind('? '), cut.rfind('! '))
    return cut[:end + 1] if end > MAX_CHARS // 2 else cut


def tts(text: str, voice: str, *, model: str = 'eleven_flash_v2_5', output: str = 'mp3_44100_128', latency: int = 0,
        settings: dict[str, Any] | None = None) -> Iterator[bytes]:
    """Text spoken by `voice`, an ElevenLabs voice id, streamed in `output`, one of FORMATS, as ElevenLabs makes it.
    `latency` 0 to 4 is optimize_streaming_latency; `settings` are its voice_settings: stability, similarity_boost,
    style, use_speaker_boost and speed. Raises OSError, with ElevenLabs's own words and never the key, before the
    first chunk when it refuses."""
    if output not in FORMATS:
        raise OSError(f'{output} is not an output format here: {", ".join(FORMATS)}.')
    query = urllib.parse.urlencode({'output_format': output, **({'optimize_streaming_latency': latency} if latency else {})})
    body = {'text': trimmed(text), 'model_id': model, **({'voice_settings': settings} if settings else {})}
    request = urllib.request.Request(f'{API}/text-to-speech/{urllib.parse.quote(voice)}/stream?{query}',
                                     data=json.dumps(body).encode('utf-8'), method='POST',
                                     headers={'xi-api-key': _key(), 'Content-Type': 'application/json',
                                              'Accept': media_type(output), 'User-Agent': 'metaform-voice'})
    try:
        answer = urllib.request.urlopen(request, timeout=TIMEOUT)  # closed by the generator below
    except urllib.error.HTTPError as error:
        raise _refused(error) from None

    def stream() -> Iterator[bytes]:
        with answer:
            while chunk := answer.read(CHUNK):
                yield chunk
    return stream()


def voices() -> list[dict[str, Any]]:
    """The voices on the person's ElevenLabs account, each its id, name, category and labels; kept ten minutes."""
    def read() -> list[dict[str, Any]]:
        found = _get('/voices')
        data = cast(dict[str, Any], found) if isinstance(found, dict) else {}
        listed = [cast(dict[str, Any], one) for one in cast(list[Any], data.get('voices') or []) if isinstance(one, dict)]
        return [{'voice_id': str(one.get('voice_id')), 'name': str(one.get('name')), 'category': one.get('category'),
                 'labels': one.get('labels') or {}} for one in listed]
    return cast(list[dict[str, Any]], _kept('voices', read))


def models() -> list[dict[str, Any]]:
    """The text-to-speech models the person's account can use, each its id, name and languages; kept ten minutes."""
    def read() -> list[dict[str, Any]]:
        found = _get('/models', timeout=5)
        listed = [cast(dict[str, Any], one) for one in cast(list[Any], found if isinstance(found, list) else [])
                  if isinstance(one, dict)]
        return [{'model_id': str(one.get('model_id')), 'name': str(one.get('name')),
                 'languages': [str(cast(dict[str, Any], lang).get('language_id')) for lang in
                               cast(list[Any], one.get('languages') or []) if isinstance(lang, dict)]}
                for one in listed if one.get('can_do_text_to_speech', True)]
    return cast(list[dict[str, Any]], _kept('models', read))


def voice_named(name: str) -> str | None:
    """A voice id from a voice's id or its name on the account, None when neither is there."""
    for one in voices():
        if name in (one['voice_id'], one['name']) or name.lower() == one['name'].lower():
            return str(one['voice_id'])
    return None


def form(fields: dict[str, str], file: Path) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
             for name, value in fields.items()]
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{file.name}"\r\n'
                 f'Content-Type: application/octet-stream\r\n\r\n'.encode() + file.read_bytes() + b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode())
    return b''.join(parts), f'multipart/form-data; boundary={boundary}'


def scribe(path: Path, *, model: str = 'scribe_v1', language: str | None = None) -> dict[str, Any]:
    """An audio file's text from ElevenLabs's Scribe, which receives the audio. Batch: the whole file at once."""
    body, kind = form({'model_id': model, **({'language_code': language} if language else {})}, path)
    request = urllib.request.Request(f'{API}/speech-to-text', data=body, method='POST',
                                     headers={'xi-api-key': _key(), 'Content-Type': kind, 'User-Agent': 'metaform-voice'})
    began = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT * 2) as answer:
            found: Any = json.loads(answer.read() or b'{}')
    except urllib.error.HTTPError as error:
        raise _refused(error) from None
    data = cast(dict[str, Any], found) if isinstance(found, dict) else {}
    return {'text': str(data.get('text') or '').strip(), 'segments': [], 'language': data.get('language_code'),
            'engine': 'elevenlabs', 'model': model, 'took': round(time.perf_counter() - began, 3), 'partial': False}
