"""What the page keeps for each person: whether they came to Metaform new, and that they closed the welcome.

`GET /api/hints` and `POST /api/hints` keep, in the Metaform home, per account behind a Node's gate and the owner's
otherwise, the names the page sends: `newcomer` or `returning`, decided once on the first project the page shows the
person, and `welcome` once they close it. So the welcome closed in one browser stays gone in every one. Any account
keeps its own, so the route is a read for its class.
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from metaform import home

if TYPE_CHECKING:
    from .server import Handler

HINTS = '/api/hints'
HINT_NAME = re.compile(r'[a-z][a-z0-9-]{0,31}')
_hints_lock = threading.Lock()


def answer(handler: Handler, method: str) -> None:
    """Answer one request to /api/hints. The server has checked its Host, token and class."""
    if method == 'POST':
        if not handler.same_origin():
            return handler.send(403, {'error': "A write is taken only from the web GUI's own page."})
        if (handler.headers.get('Content-Type') or '').split(';')[0].strip().lower() != 'application/json':
            return handler.send(415, {'error': 'A write takes a JSON body.'})
        try:
            body: Any = handler.json_body()
        except ValueError:
            return handler.send(400, {'error': 'The body is not JSON.'})
        return keep_hint(handler, cast(dict[str, Any], body) if isinstance(body, dict) else {})
    return handler.send(200, {'dismissed': sorted(_hints().get(_account(handler), []))})


def _account(handler: Handler) -> str:
    """Whose hints these are: the signed-in account behind a Node's gate, else the home's owner."""
    from .server import ACCOUNT_HEADER
    return (handler.headers.get(ACCOUNT_HEADER) or '') if handler.gui.gate is not None else ''


def _hints_file() -> Path:
    return home.home() / 'web' / 'hints.json'


def _hints() -> dict[str, list[str]]:
    try:
        kept: Any = json.loads(_hints_file().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    if not isinstance(kept, dict):
        return {}
    return {str(key): [str(name) for name in cast(list[Any], value)]
            for key, value in cast(dict[Any, Any], kept).items() if isinstance(value, list)}


def keep_hint(handler: Handler, given: dict[str, Any]) -> None:
    """One name kept for good for the person who sent it."""
    name = given.get('hint')
    if not isinstance(name, str) or not HINT_NAME.fullmatch(name):
        return handler.send(400, {'error': 'No hint was named.'})
    account = _account(handler)
    with _hints_lock:
        kept = _hints()
        mine = sorted({*kept.get(account, []), name})
        kept[account] = mine
        home.mkdir_private(_hints_file().parent)
        home.write_private(_hints_file(), json.dumps(kept, indent=1))
    handler.send(200, {'dismissed': mine})
