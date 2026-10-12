"""The endpoint engine: a person's own OpenAI-compatible `/audio/transcriptions` URL.

The audio goes to the URL the person set and nowhere else, as multipart form data with the model they named; the key,
when they name an environment variable that holds one, is read from this process's environment and sent as a bearer
token, so it never reaches the page.
"""
from __future__ import annotations

import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, cast

TIMEOUT = 60


def form(fields: dict[str, str], file: Path) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    kind = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{file.name}"\r\n'
                 f'Content-Type: {kind}\r\n\r\n'.encode() + file.read_bytes() + b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode())
    return b''.join(parts), f'multipart/form-data; boundary={boundary}'


def transcribe(path: Path, *, url: str, model: str, key_env: str, language: str | None) -> dict[str, Any]:
    """The endpoint's text for one utterance. Raises OSError with the endpoint's own words when it refuses."""
    fields = {'model': model, 'response_format': 'json', **({'language': language} if language else {})}
    body, kind = form(fields, path)
    headers = {'Content-Type': kind, 'User-Agent': 'metaform-voice'}
    key = os.environ.get(key_env, '') if key_env else ''
    if key:
        headers['Authorization'] = f'Bearer {key}'
    began = time.perf_counter()
    request = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as answer:  # the person's own URL
            found: Any = json.loads(answer.read() or b'{}')
    except urllib.error.HTTPError as error:
        said = error.read()[:400].decode('utf-8', 'replace')
        raise OSError(f'The transcription endpoint answered {error.code}: {said}') from None
    text = str(cast(dict[str, Any], found).get('text') or '') if isinstance(found, dict) else ''
    return {'text': text.strip(), 'segments': [], 'engine': 'endpoint', 'model': model,
            'took': round(time.perf_counter() - began, 3), 'partial': False}
