"""What a command changed in the map, so the chassis can announce it when the command ends, VIEW-018 and QUAL-015.

The store notes each committed write to a metaform's store, and the home each metaform added, removed or made
active. After every command, on the command line or over MCP, the chassis takes the notes and fires `map.changed`
on the module event bus once for each metaform changed, BASE-010, so every subscriber, the web GUI's open pages
among them, is told what changed. Each write also names the tables it wrote, so a subscriber can read again only what
a change touches, as a page does for a ticket moved. Nothing polls for a change and no module has to remember to
announce one.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .module import Surface

# each project's changed metaforms, each with the tables written, or None when what was written is not known
_NOTED: dict[str, dict[str, set[str] | None]] = {}
_LOCK = threading.Lock()
_WRITES = (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE)


def watch(db: sqlite3.Connection) -> set[str]:
    """The tables a write transaction on this connection writes, filled as its statements are prepared. A statement
    prepared that changes no row still names its table, so a change may name a table it left as it was, never the
    reverse. The connection is a write's own, closed after it."""
    written: set[str] = set()

    def authorizer(action: int, table: str | None, *_: object) -> int:
        if action in _WRITES and table:
            written.add(table)
        return sqlite3.SQLITE_OK
    db.set_authorizer(authorizer)
    return written


def note(project_id: str, base_id: str | None = None, tables: set[str] | None = None) -> None:
    """A change to a project's map: one metaform's store, or, with no metaform, the project's metaforms themselves;
    with the tables it wrote when they are known. One change whose tables are not known makes the metaform's unknown."""
    with _LOCK:
        noted = _NOTED.setdefault(project_id, {})
        key = base_id or ''
        known = noted.get(key, set())
        noted[key] = None if known is None or not tables else known | tables


def take() -> dict[str, dict[str, set[str] | None]]:
    """Everything noted since the last take, once."""
    with _LOCK:
        found = {project: dict(metaforms) for project, metaforms in _NOTED.items()}
        _NOTED.clear()
    return found


def announce(folder: Path, surface: Surface) -> list[dict[str, Any]]:
    """Fire `map.changed` for each metaform the command changed; a metaform id of None means the project's metaforms
    changed, such as one added, removed or made active. `tables` names the tables written, as the store names them,
    when they are known; a payload without it may have changed anything. A subscriber's failure never reaches the
    command, BASE-032. Returns the payloads fired, so a long-running process can follow its own changes, BASE-053."""
    from . import events
    from .module import Context
    fired: list[dict[str, Any]] = []
    for project, metaforms in sorted(take().items()):
        source = Context(module='chassis', folder=folder, project=project, surface=surface)
        for metaform, tables in sorted(metaforms.items()):
            payload: dict[str, Any] = {'project': project, 'base_id': metaform or None}
            if tables:
                payload['tables'] = sorted(tables)
            events.publish('map.changed', dict(payload), source)
            fired.append(payload)
    return fired
