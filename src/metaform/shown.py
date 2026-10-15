"""What one agent session has been shown, so Metaform tells an agent a thing once, MCP-039.

An agent session is the session its runner names in METAFORM_SESSION, for an agent dispatch started and every process
that agent starts, its MCP server among them; otherwise the MCP server process itself, with the client that called it.
A command line with neither has no session and is shown everything each time, as a person at a terminal expects.

What a process session was shown is kept in the process, and ends with it. What a named session was shown is kept in the
home's chassis database, so the agent's MCP server and the commands it runs in its shell share one record; a row
older than a week is dropped when another is written.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from . import home

PROCESS = uuid.uuid4().hex[:16]  # this process's own session, while it serves one
KEEP = timedelta(days=7)
# A home made before this table existed is given it on the first row written.
SHOWN = """CREATE TABLE IF NOT EXISTS shown(
  session TEXT NOT NULL,
  key     TEXT NOT NULL,
  value   TEXT NOT NULL,
  at      TEXT NOT NULL,
  PRIMARY KEY (session, key)
);
"""

_serving = False
_kept: dict[tuple[str, str], str] = {}
_lock = threading.Lock()


def serving() -> None:
    """Make this process one agent session of its own: the MCP server, which one host starts for one conversation."""
    global _serving
    _serving = True


def is_serving() -> bool:
    """Whether this process serves one agent's conversation, so it lives as long as that agent does."""
    return _serving


def session(client: str | None = None) -> str | None:
    """The agent session a call is made in: METAFORM_SESSION, else this serving process with its client, else None."""
    named = os.environ.get('METAFORM_SESSION')
    if named:
        return named
    if _serving:
        return f'process:{PROCESS}' + (f':{client}' if client else '')
    return None


def swap(session: str | None, key: str, value: Any) -> Any:
    """What `session` was last shown under `key`, or None the first time, recording `value` as shown now. With no
    session nothing is kept and the answer is always None, so everything is shown."""
    if session is None:
        return None
    text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    if session.startswith('process:'):
        with _lock:
            before = _kept.get((session, key))
            _kept[(session, key)] = text
        return None if before is None else json.loads(before)
    stamp = home.now()
    cutoff = (datetime.now(UTC) - KEEP).strftime('%Y-%m-%dT%H:%M:%SZ')
    with home.chassis(write=True) as db:
        db.execute(SHOWN)
        row = db.execute('SELECT value FROM shown WHERE session=? AND key=?', (session, key)).fetchone()
        db.execute('INSERT INTO shown(session, key, value, at) VALUES (?, ?, ?, ?) ON CONFLICT(session, key) '
                   'DO UPDATE SET value=excluded.value, at=excluded.at', (session, key, text, stamp))
        db.execute('DELETE FROM shown WHERE at < ?', (cutoff,))
    return None if row is None else json.loads(row[0])
