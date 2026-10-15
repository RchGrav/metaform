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

# each project's changed bases, each with the tables written, or None when what was written is not known
_NOTED: dict[str, dict[str, set[str] | None]] = {}
_SEQS: dict[tuple[str, str], int] = {}  # the sequence each noted base reached, STORE-046
# what each noted base's writes concern, `work_ids`, `session_ids` and `kinds`; None once one write said nothing
_ABOUT: dict[tuple[str, str], dict[str, set[str]] | None] = {}
_TAKEN: dict[tuple[str, str], dict[str, set[str]] | None] = {}  # what the last take took of it, for `concerns`
ABOUT = ('work_ids', 'session_ids', 'kinds')
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


def note(project_id: str, base_id: str | None = None, tables: set[str] | None = None,
         seq: int | None = None, about: dict[str, set[str]] | None = None) -> None:
    """A change to a project's map: one base's store, or, with no base, the project's bases themselves; with the
    tables it wrote when they are known, and the sequence the base's log reached, so a page applies the ops past the
    one it drew, STORE-046. One change whose tables are not known makes the base's unknown. `about` is what the write
    said it concerns, `Tx.concern`: the tickets, sessions and kinds of change, so a listener reads again only for a
    change of its own, BASE-053. One change that said nothing makes the base's unknown."""
    with _LOCK:
        noted = _NOTED.setdefault(project_id, {})
        key = base_id or ''
        known = noted.get(key, set())
        noted[key] = None if known is None or not tables else known | tables
        if seq is not None:
            _SEQS[(project_id, key)] = max(seq, _SEQS.get((project_id, key), 0))
        held = _ABOUT.get((project_id, key), {})
        _ABOUT[(project_id, key)] = None if held is None or not about else \
            {name: held.get(name, set()) | about.get(name, set()) for name in ABOUT}


def take() -> dict[str, dict[str, set[str] | None]]:
    """Everything noted since the last take, once."""
    with _LOCK:
        found = {project: dict(metaforms) for project, metaforms in _NOTED.items()}
        _NOTED.clear()
        _TAKEN.clear()
        _TAKEN.update(_ABOUT)
        _ABOUT.clear()
    return found


def sequence(project_id: str, base_id: str | None) -> int | None:
    """The sequence a noted base reached, taken once."""
    with _LOCK:
        return _SEQS.pop((project_id, base_id or ''), None)


def concerns(project_id: str, base_id: str | None) -> dict[str, list[str]]:
    """What a base's writes the last `take` took concern, read once: `work_ids`, `session_ids` and `kinds`, each a
    sorted list, or nothing when one write said nothing of what it concerns."""
    with _LOCK:
        held = _TAKEN.pop((project_id, base_id or ''), None)
    return {} if held is None else {name: sorted(held[name]) for name in ABOUT}


def announce(folder: Path, surface: Surface) -> list[dict[str, Any]]:
    """Fire `map.changed` for each metaform the command changed; a metaform id of None means the project's metaforms
    changed, such as one added, removed or made active. `tables` names the tables written, as the store names them,
    when they are known; a payload without it may have changed anything. `work_ids`, `session_ids` and `kinds` say what
    the writes concern when every one of them said so, `concerns`; without them that is not known. A subscriber's
    failure never reaches the command, BASE-032. Returns the payloads fired, so a long-running process can follow its
    own changes, BASE-053."""
    from . import events
    from .module import Context
    fired: list[dict[str, Any]] = []
    for project, metaforms in sorted(take().items()):
        source = Context(module='chassis', folder=folder, project=project, surface=surface)
        for metaform, tables in sorted(metaforms.items()):
            payload: dict[str, Any] = {'project': project, 'base_id': metaform or None}
            if tables:
                payload['tables'] = sorted(tables)
            seq = sequence(project, metaform)
            if seq is not None:
                payload['seq'] = seq
            payload.update(concerns(project, metaform))
            events.publish('map.changed', dict(payload), source)
            fired.append(payload)
    return fired
