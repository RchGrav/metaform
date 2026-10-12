"""The page's voice endpoints: speech to text through the voice module's own commands, run in this server's process.

The page holds the microphone; this server holds the engines that run on the person's machine. Each endpoint runs one
of the voice module's verbs as a tool call runs it, so the module's model stays loaded here between utterances and
the module is reached only through its declaration, never by import.

  GET  /api/voice/status         voice status: the engine in use and why, the models and their sizes
  POST /api/voice/transcribe     an utterance's audio as the body, wav or a MediaRecorder's webm/ogg, its text back;
                                 ?partial=1 is a quick pass of the audio so far, answered {busy: true} while another
                                 transcription runs, so partials never queue behind each other
  POST /api/voice/download       {engine, model, variant}: a model, once, into the home; the page asked the person
  POST /api/voice/clip           an utterance's wav kept for a moment, for an agent that takes audio, its id back
  GET  /api/voice/files/<path>   the browser engine's model and runtime files, from the home's models folder
  POST /api/voice/speak          {text, character}: the reply spoken by voice_tts's engine a module brings, such as
                                 elevenlabs, streamed back as it is made, its format, such as pcm_22050, named in
                                 X-Voice-Format;
                                 the key stays in this server's environment and never reaches the page

Partials are re-transcriptions of the growing utterance, sent about once a second while the person speaks: the
standard library server has no WebSocket, and an utterance is bounded, so the cost of sending it again is small next
to the model's own time, and every answer stands alone.
"""
from __future__ import annotations

import re
import secrets
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import unquote

from metaform import home, settings
from metaform import module as chassis
from metaform.module import Stop

if TYPE_CHECKING:
    from .server import Handler

PREFIX = '/api/voice/'
KINDS = {'audio/wav': '.wav', 'audio/x-wav': '.wav', 'audio/wave': '.wav', 'audio/webm': '.webm',
         'audio/ogg': '.ogg', 'audio/flac': '.flac', 'audio/mpeg': '.mp3', 'audio/mp4': '.m4a'}
SERVED = {'.json': 'application/json', '.onnx': 'application/octet-stream', '.wasm': 'application/wasm',
          '.txt': 'text/plain; charset=utf-8'}
CLIP = re.compile(r'^[0-9a-f]{32}$')
CLIP_HOURS = 1  # a clip not sent within the hour is the person's audio left lying about, so it is removed


def answer(handler: Handler, method: str, path: str, query: dict[str, list[str]]) -> None:
    name = path[len(PREFIX):]
    given = {key: values[-1] for key, values in query.items() if key != 't'}
    try:
        if method == 'GET' and name == 'status':  # always answered: voice off or missing is a state, not an error
            try:
                return handler.send(200, {'available': True, **verb(given, 'status', {})})
            except Stop as error:
                return handler.send(200, {'available': False, 'engine': 'off', 'chosen': 'off', 'why': str(error),
                                           'next': error.next_step})
        if method == 'GET' and name.startswith('files/'):
            return files(handler, name[len('files/'):])
        if method != 'POST':
            return handler.send(404, {'error': f'Nothing at {path}.'})
        origin = handler.headers.get('Origin')
        if origin is None or origin.lower() != f'http://{handler.headers.get("Host", "")}'.lower():
            return handler.send(403, {'error': "Voice is taken only from the web GUI's own page."})
        if name == 'download':
            body: Any = handler.json_body()
            asked = cast(dict[str, Any], body) if isinstance(body, dict) else {}
            arguments = {key: str(asked[key]) for key in ('engine', 'model', 'variant') if asked.get(key)}
            return handler.send(200, verb({**given, **({'project': str(asked['project'])} if asked.get('project') else {})},
                                          'download', arguments))
        if name in ('transcribe', 'clip'):
            return audio(handler, name, given)
        if name == 'speak':
            return speak(handler, given)
        return handler.send(404, {'error': f'No voice endpoint {name}.'})
    except Stop as error:
        handler.send(400, {'error': str(error), 'next': error.next_step})
    except ValueError:
        handler.send(400, {'error': 'The body is not what this endpoint takes.'})


def folder_of(given: dict[str, str]) -> tuple[str | None, Path]:
    """The project the page shows, for its folder's surface; voice belongs to no project, so the home stands in."""
    project = home.project(given.get('project', ''))
    return (project.project_id, Path(project.path)) if project is not None else (None, home.home())


def verb(given: dict[str, str], name: str, arguments: dict[str, Any]) -> Any:
    """Run one of the voice module's verbs in this process, its arguments checked as a tool call's are."""
    project, folder = folder_of(given)
    chassis.refresh_modules()
    found = next((one for one in chassis.surface(folder) if one.id == 'voice'), None)
    run = next((one for one in found.verbs if one.name == name), None) if found is not None else None
    if run is None:
        raise Stop('Voice is not on: the voice module is disabled here.', 'metaform enable voice')
    nouns, switches, _ = chassis.tool_arguments('voice', run, arguments, folder=folder)
    ctx = chassis.context('voice', folder, project=project, nouns=nouns, switches=switches, sink=lambda text: None,
                          surface='web')
    return chassis.call(run.run, ctx)


def run_folder() -> Path:
    return home.home() / 'run' / 'voice'


def clip_path(clip: str) -> Path | None:
    """A kept clip's file, for a message to an agent that takes audio; None for anything but a kept clip's id."""
    if not CLIP.match(clip):
        return None
    path = run_folder() / 'clips' / f'{clip}.wav'
    return path if path.is_file() else None


def audio(handler: Handler, name: str, given: dict[str, str]) -> None:
    """Take one utterance's audio, bounded by voice_max_seconds, into a file of its own under the home's run folder;
    transcribe it and remove it, or keep it as a clip."""
    _, folder = folder_of(given)
    chassis.refresh_modules()  # the voice module's settings are declared once it loads
    if 'voice_max_seconds' not in settings.SCHEMA:
        raise Stop('Voice is not on: the voice module is disabled here.', 'metaform enable voice')
    seconds = int(settings.value('voice_max_seconds', folder))
    limit = seconds * 32000 + (1 << 20)  # 16 kHz 16-bit mono, and room for a container's headers
    kind = (handler.headers.get('Content-Type') or '').split(';')[0].strip().lower()
    suffix = KINDS.get(kind)
    if suffix is None or (name == 'clip' and suffix != '.wav'):
        return handler.send(415, {'error': 'Voice takes wav, webm, ogg, flac, mp3 or m4a audio; a clip takes wav.'})
    length = int(handler.headers.get('Content-Length') or 0)
    if length <= 0:
        return handler.send(400, {'error': 'No audio came.'})
    if length > limit:
        handler.close_connection = True
        return handler.send(413, {'error': f'The utterance is longer than voice_max_seconds, {seconds} s.',
                                  'next': f'metaform set --voice-max-seconds {seconds * 2}'})
    body = handler.rfile.read(length)
    place = run_folder() / ('clips' if name == 'clip' else 'heard')
    place.mkdir(parents=True, exist_ok=True)
    if name == 'clip':
        prune(place)
        clip = secrets.token_hex(16)
        (place / f'{clip}.wav').write_bytes(body)
        return handler.send(200, {'clip': clip, 'bytes': length})
    path = place / f'{secrets.token_hex(16)}{suffix}'
    path.write_bytes(body)
    try:
        arguments: dict[str, Any] = {'file': str(path)}
        if given.get('partial') in ('1', 'true'):
            arguments['partial'] = True
        if given.get('language'):
            arguments['language'] = given['language']
        handler.send(200, verb(given, 'transcribe', arguments))
    finally:
        path.unlink(missing_ok=True)


def speak(handler: Handler, given: dict[str, str]) -> None:
    """Stream the voice module's ElevenLabs speech to the page, chunk by chunk, as it arrives."""
    body: Any = handler.json_body()
    asked = cast(dict[str, Any], body) if isinstance(body, dict) else {}
    text = str(asked.get('text') or '').strip()
    if not text:
        return handler.send(400, {'error': 'Nothing to say.'})
    arguments = {'text': [text], **{key: str(asked[key]) for key in ('character',) if asked.get(key)}}
    found = verb(given, 'speak', arguments)
    said = str(found.get('format') or '')
    kind = {'mp3': 'audio/mpeg', 'pcm': 'audio/L16', 'ulaw': 'audio/basic'}.get(said.split('_', 1)[0], 'application/octet-stream')
    handler.send_response(200)
    handler.send_header('Content-Type', kind)
    handler.send_header('X-Voice-Format', said)
    handler.send_header('Transfer-Encoding', 'chunked')
    handler.send_header('Cache-Control', 'no-store')
    handler.send_header('X-Content-Type-Options', 'nosniff')
    handler.end_headers()
    try:
        for chunk in found['stream']:
            handler.wfile.write(f'{len(chunk):x}\r\n'.encode() + chunk + b'\r\n')
            handler.wfile.flush()
        handler.wfile.write(b'0\r\n\r\n')
    except OSError:
        handler.close_connection = True  # the page stopped listening, or ElevenLabs stopped mid-way


def prune(place: Path) -> None:
    now = time.time()
    for old in place.glob('*.wav'):
        try:
            if now - old.stat().st_mtime > CLIP_HOURS * 3600:
                old.unlink()
        except OSError:
            pass


def files(handler: Handler, relative: str) -> None:
    """A file of the browser engine, from the folder the voice module downloads it to: models by repository, and the
    runtime. Only the kinds of file an engine reads are served, and nothing outside that folder."""
    found = verb({}, 'models', {})
    base = Path(str(found.get('browser_folder') or '')).resolve()
    relative = unquote(relative)
    target = (base / relative).resolve()
    kind = SERVED.get(target.suffix.lower())
    if not base.is_dir() or not target.is_relative_to(base) or kind is None or not target.is_file():
        return handler.send(404, {'error': 'Nothing here.'})
    size = target.stat().st_size
    handler.send_response(200)
    handler.send_header('Content-Type', kind)
    handler.send_header('Content-Length', str(size))
    handler.send_header('X-Content-Type-Options', 'nosniff')
    handler.send_header('Cache-Control', 'private, max-age=31536000, immutable')  # a pinned revision never changes
    handler.end_headers()
    if handler.command == 'HEAD':
        return
    with target.open('rb') as source:
        while chunk := source.read(1 << 20):
            handler.wfile.write(chunk)
