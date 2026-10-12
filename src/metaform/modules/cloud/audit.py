"""The record of who called what through the cloud broker, kept on this machine and nowhere else.

One JSON line per request in `<home>/cloud/audit.jsonl`, readable by its owner alone: the time, the account and the AI
client the broker vouched for (from its signed assertion), the JSON-RPC method, the tool, resource or prompt it named,
the project, the outcome (`ok`, `error`, `refused`, `insufficient_scope`), how long it took, and the assertion's id,
which the broker signed and cannot later deny. Arguments are written only with cloud_audit set to `full`; results never
are. At 10 MiB the file moves aside, and five older files are kept.
"""
from __future__ import annotations

import contextlib
import json
import os
import time
from pathlib import Path
from typing import Any, cast

from .login import folder

ROTATE_BYTES = 10 * 1024 * 1024
KEPT = 5


def path() -> Path:
    return folder() / 'audit.jsonl'


def described(body: bytes) -> dict[str, Any]:
    """What a request asked, read from its JSON-RPC body: the method, the name it named, the project, the arguments."""
    try:
        message: Any = json.loads(body or b'null')
    except ValueError:
        return {}
    if not isinstance(message, dict):
        return {}
    said = cast(dict[str, Any], message)
    params: Any = said.get('params') if isinstance(said.get('params'), dict) else {}
    held = cast(dict[str, Any], params)
    arguments: Any = held.get('arguments') if isinstance(held.get('arguments'), dict) else None
    named = held.get('name') or held.get('uri')
    found: dict[str, Any] = {'method': said.get('method') or ('response' if 'result' in said else None)}
    if isinstance(named, str):
        found['name'] = named
    if isinstance(arguments, dict) and isinstance(cast(dict[str, Any], arguments).get('project'), str):
        found['project'] = cast(dict[str, Any], arguments)['project']
    if arguments is not None:
        found['arguments'] = arguments
    return found


def outcome(status: int, seen: bytes) -> str:
    if status == 401:
        return 'refused'
    if status == 403:
        return 'insufficient_scope'
    if status >= 400:
        return 'error'
    text = seen.replace(b' ', b'')
    return 'error' if b'"isError":true' in text or b'"error":{' in text else 'ok'


def write(record: dict[str, Any], full: bool) -> None:
    """One line, appended; the file rotated when it is past its size. Never fails the request it records."""
    kept = {key: value for key, value in record.items() if value is not None and (full or key != 'arguments')}
    line = json.dumps({'time': time.strftime('%Y-%m-%dT%H:%M:%S%z'), **kept}, ensure_ascii=False) + '\n'
    with contextlib.suppress(OSError):
        target = path()
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.stat().st_size > ROTATE_BYTES:
            for number in range(KEPT - 1, 0, -1):
                older = target.with_name(f'audit.{number}.jsonl')
                if older.exists():
                    os.replace(older, target.with_name(f'audit.{number + 1}.jsonl'))
            os.replace(target, target.with_name('audit.1.jsonl'))
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(descriptor, 'a', encoding='utf-8') as handle:
            handle.write(line)


def read(lines: int = 50) -> list[dict[str, Any]]:
    try:
        text = path().read_text(encoding='utf-8')
    except OSError:
        return []
    found: list[dict[str, Any]] = []
    for line in text.splitlines()[-lines:]:
        with contextlib.suppress(ValueError):
            found.append(json.loads(line))
    return found
