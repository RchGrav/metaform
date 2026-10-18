"""What a command changed in the map, so the chassis can announce it when the command ends, VIEW-018 and QUAL-015.

The store notes each committed write to a metaform's store, and the home each metaform added, removed or made
active. After every command, on the command line or over MCP, the chassis takes the notes and fires `map.changed`
on the module event bus once for each metaform changed, BASE-010, so every subscriber, the web GUI's open pages
among them, is told what changed. Each write also names the tables it wrote, so a subscriber can read again only what
a change touches, as a page does for a ticket moved. Nothing polls for a change and no module has to remember to
announce one.
"""
from __future__ import annotations

import contextvars
import sqlite3
import threading
from collections.abc import Callable, Generator
from contextlib import contextmanager
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
# the notes of one call kept apart from the process's, `announced` and `quietly`: each `note` made in its context
_KEPT: contextvars.ContextVar[list[tuple[Any, ...]] | None] = contextvars.ContextVar('metaform_changes_kept',
                                                                                     default=None)
_WRITES = (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE)
# the connections whose writes `watch` records nothing of for now, `unwatched`, by `id`
_UNWATCHED: contextvars.ContextVar[frozenset[int]] = contextvars.ContextVar('metaform_changes_unwatched',
                                                                            default=frozenset())
# the rows a watched connection changed while unwatched, by `id`, so `changed` leaves them out
_INSTALLED: dict[int, int] = {}


def watch(db: sqlite3.Connection) -> set[str]:
    """The tables a write transaction on this connection writes, filled as its statements are prepared. A statement
    prepared that changes no row still names its table, so a change may name a table it left as it was, never the
    reverse. The connection is a write's own, closed after it."""
    written: set[str] = set()
    key = id(db)
    _INSTALLED[key] = 0

    def authorizer(action: int, table: str | None, *_: object) -> int:
        # SQLite's own catalogue, `sqlite_master` and the rest, is never a table a map draws
        if action in _WRITES and table and not table.startswith('sqlite_') and key not in _UNWATCHED.get():
            written.add(table)
        return sqlite3.SQLITE_OK
    db.set_authorizer(authorizer)
    return written


@contextmanager
def unwatched(db: sqlite3.Connection) -> Generator[None, None, None]:
    """Writes on this connection that `watch` records nothing of while the block runs: a module's tables created or
    upgraded and their version recorded in `meta` are not a change anyone draws (UX recheck 2026-10-17, b410f6a5)."""
    key = id(db)
    if key in _UNWATCHED.get():  # inside one already, which counts the rows
        yield
        return
    token = _UNWATCHED.set(_UNWATCHED.get() | {key})
    before = db.total_changes
    try:
        yield
    finally:
        _UNWATCHED.reset(token)
        if key in _INSTALLED:
            _INSTALLED[key] += db.total_changes - before


def changed(db: sqlite3.Connection) -> int:
    """The rows a watched write changed, less those it changed unwatched: a write that only installed a module's
    tables changed none anyone draws, so it notes no change, though a statement it prepared named a table."""
    return db.total_changes - _INSTALLED.pop(id(db), 0)


def note(project_id: str, base_id: str | None = None, tables: set[str] | None = None,
         seq: int | None = None, about: dict[str, set[str]] | None = None) -> None:
    """A change to a project's map: one base's store, or, with no base, the project's bases themselves; with the
    tables it wrote when they are known, and the sequence the base's log reached, so a page applies the ops past the
    one it drew, STORE-046. One change whose tables are not known makes the base's unknown. `about` is what the write
    said it concerns, `Tx.concern`: the tickets, sessions and kinds of change, so a listener reads again only for a
    change of its own, BASE-053. One change that said nothing makes the base's unknown."""
    kept = _KEPT.get()
    if kept is not None:  # one call's own, which it announces itself, `announced`
        kept.append((project_id, base_id, tables, seq, about))
        return
    with _LOCK:
        _add(_NOTED, _SEQS, _ABOUT, project_id, base_id, tables, seq, about)


def _add(noted_in: dict[str, dict[str, set[str] | None]], seqs: dict[tuple[str, str], int],
         abouts: dict[tuple[str, str], dict[str, set[str]] | None], project_id: str, base_id: str | None,
         tables: set[str] | None, seq: int | None, about: dict[str, set[str]] | None) -> None:
    noted = noted_in.setdefault(project_id, {})
    key = base_id or ''
    known = noted.get(key, set())
    noted[key] = None if known is None or not tables else known | tables
    if seq is not None:
        seqs[(project_id, key)] = max(seq, seqs.get((project_id, key), 0))
    held = abouts.get((project_id, key), {})
    abouts[(project_id, key)] = None if held is None or not about else \
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
    return _listed(held)


def announced(folder: Path, surface: Surface, function: Callable[..., Any], *args: Any,
              **kwargs: Any) -> tuple[Any, list[dict[str, Any]]]:
    """Call a function that writes, then fire `map.changed` for what that call alone wrote, as `announce` does for a
    command, BASE-053: what other calls of the process noted, before it or beside it in another thread, stays theirs.
    A long-running process announces each of its writes this way, so one write's event never carries another's tables
    or loses the tickets it said it concerns (UX recheck 2026-10-17). A call that fails leaves what it wrote for the
    process's next `announce`. Returns the function's result and the payloads fired."""
    kept: list[tuple[Any, ...]] = []
    token = _KEPT.set(kept)
    try:
        result = function(*args, **kwargs)
    except BaseException:
        _KEPT.reset(token)
        for one in kept:
            note(*one)
        raise
    _KEPT.reset(token)
    noted: dict[str, dict[str, set[str] | None]] = {}
    seqs: dict[tuple[str, str], int] = {}
    abouts: dict[tuple[str, str], dict[str, set[str]] | None] = {}
    for one in kept:
        _add(noted, seqs, abouts, *one)
    return result, _fire(folder, surface, noted, lambda project, key: seqs.get((project, key)),
                         lambda project, key: _listed(abouts.get((project, key))))


def quietly(function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Call a function that writes, whose change the caller announces itself on an event of its own: what the call
    noted is dropped, so neither the process's next `announce` nor its command's end fires it again, with the tables
    of every such write and nothing of what they concern (UX recheck 2026-10-17)."""
    token = _KEPT.set([])
    try:
        return function(*args, **kwargs)
    finally:
        _KEPT.reset(token)


def announce(folder: Path, surface: Surface) -> list[dict[str, Any]]:
    """Fire `map.changed` for each metaform the command changed; a metaform id of None means the project's metaforms
    changed, such as one added, removed or made active. `tables` names the tables written, as the store names them,
    when they are known; a payload without it may have changed anything. `work_ids`, `session_ids` and `kinds` say what
    the writes concern when every one of them said so, `concerns`; without them that is not known. A subscriber's
    failure never reaches the command, BASE-032. Returns the payloads fired, so a long-running process can follow its
    own changes, BASE-053."""
    return _fire(folder, surface, take(), sequence, concerns)


def _listed(held: dict[str, set[str]] | None) -> dict[str, list[str]]:
    return {} if held is None else {name: sorted(held[name]) for name in ABOUT}


def _fire(folder: Path, surface: Surface, found: dict[str, dict[str, set[str] | None]],
          seq_of: Callable[[str, str], int | None],
          about_of: Callable[[str, str], dict[str, list[str]]]) -> list[dict[str, Any]]:
    from . import events
    from .module import Context
    fired: list[dict[str, Any]] = []
    for project, metaforms in sorted(found.items()):
        source = Context(module='chassis', folder=folder, project=project, surface=surface)
        for metaform, tables in sorted(metaforms.items()):
            payload: dict[str, Any] = {'project': project, 'base_id': metaform or None}
            if tables:
                payload['tables'] = sorted(tables)
            seq = seq_of(project, metaform)
            if seq is not None:
                payload['seq'] = seq
            payload.update(about_of(project, metaform))
            events.publish('map.changed', dict(payload), source)
            fired.append(payload)
    return fired
