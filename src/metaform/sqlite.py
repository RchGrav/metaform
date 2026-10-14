"""Opening Metaform's SQLite files: pragmas, schema creation and the schema version check.

The base database, every metaform store, the history database and the prompt
database all open through `opened`, so all follow STORE-006 (WAL, foreign keys,
busy timeout, one file opened and prepared inside its lock) and STORE-029 (the
schema version is read before any other access, and one this code cannot read is
refused before anything is written). Each file records two numbers: its layout,
`schema_version`, and `compatible_from`, the oldest layout whose code still reads
and writes it; code opens a file whose `compatible_from` is at or below its own
layout, a newer one included, and leaves both numbers as they are.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .errors import NewerStore, StoreError

SCHEMA_VERSION = '21'  # the base store's layout, an op log from 21, STORE-046; the chassis, history and prompt databases keep their own, STORE-029
COMPATIBLE_FROM = '21'  # the oldest layout whose code reads the store; 21 replaced its tables with the op log
BUSY_SECONDS = 30  # how long a write waits for another process's write to finish, STORE-006

Upgrade = Callable[[sqlite3.Connection, Path, str], Any]  # brings a file at an earlier version up to date; True when
# it wrote a new file in the old one's place, so the caller connects again

_WRITERS: dict[str, threading.RLock] = {}
_WRITERS_GUARD = threading.Lock()


def writer_lock(path: Path | str) -> threading.RLock:
    """One lock per database file in this process, held while a connection to it is opened and prepared and for
    the whole of a write transaction. Writers take turns here, so SQLite's busy wait, which polls and is not fair,
    settles only writers of other processes, and a thread is never starved past it. Opening is inside it because
    a new file's switch to WAL fails at once, with no busy wait, against any lock another connection holds on the
    file, STORE-006."""
    with _WRITERS_GUARD:
        return _WRITERS.setdefault(str(path), threading.RLock())


def reset_reads(path: Path | str | None = None) -> None:
    """Nothing to reset: every read opens its own connection and closes it, so no connection outlives a removed store.
    Kept for home.py's removal of a store. The 2026-10-05 version that reused read connections across transactions
    corrupted stores under concurrent writers, artifacts/incident-2026-10-05."""


def private(path: Path) -> None:
    """Create a database file that does not exist yet readable and writable by its owner alone, before SQLite opens
    it, so its write-ahead log and shared memory, which SQLite gives the database file's mode, are too. A file that
    exists is left as it is. On Windows the file keeps the default its folder gives it."""
    if os.name == 'nt':
        return
    try:
        os.close(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
    except FileExistsError:
        pass


def connect(path: Path | str) -> sqlite3.Connection:
    """A connection in autocommit mode: every transaction is begun explicitly."""
    db = sqlite3.connect(str(path), isolation_level=None, timeout=BUSY_SECONDS)
    db.execute(f'PRAGMA busy_timeout={BUSY_SECONDS * 1000}')
    return db


def memory(schema: str) -> sqlite3.Connection:
    """An empty in-memory database with the schema, for reads of a file that does not exist."""
    db = sqlite3.connect(':memory:', isolation_level=None)
    db.executescript(schema)
    return db


@contextmanager
def opened(path: Path, schema: str, *, write: bool, version: str, compatible: str | None = None,
           upgrade: Upgrade | None = None) -> Generator[sqlite3.Connection, None, None]:
    """A prepared connection to the file, opened inside the file's lock, STORE-006; the caller begins and ends
    the transaction. A write holds the lock until the block ends and creates the file when there is none. A read
    lets go of the lock once its connection is prepared, and reads a file with nothing committed yet, no file, no
    bytes or no tables, as an empty database in memory, without touching a file of no bytes at all. `compatible` is
    the oldest layout whose code reads this kind of database at `version`, `version` itself when not given."""
    lock = writer_lock(path)
    lock.acquire()
    held = True
    try:
        db: sqlite3.Connection | None = None
        if write:
            from . import home
            if home.is_home_path(path):
                home.mkdir_private(path.parent)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
            private(path)
            db = _prepared(path, schema, create=True, version=version, compatible=compatible, upgrade=upgrade)
            assert db is not None  # a write creates the file
        else:
            if _has_bytes(path):
                db = _prepared(path, schema, create=False, version=version, compatible=compatible, upgrade=upgrade)
            if db is None:
                db = memory(schema)
            lock.release()
            held = False
        try:
            yield db
        finally:
            db.close()
    finally:
        if held:
            lock.release()


class Replaced(Exception):
    """An upgrade wrote a new file in the old one's place; the connection in hand reads the old one."""


def _prepared(path: Path, schema: str, *, create: bool, version: str, compatible: str | None,
              upgrade: Upgrade | None) -> sqlite3.Connection | None:
    """A connection to the file, prepared; connected again when an upgrade replaced the file, STORE-046. None when
    the file holds nothing committed yet and creation is not allowed."""
    db = connect(path)
    try:
        if not prepare(db, path, schema, create=create, version=version, compatible=compatible, upgrade=upgrade):
            db.close()
            return None
        return db
    except Replaced:
        db.close()
    except BaseException:
        db.close()
        raise
    db = connect(path)
    try:
        if not prepare(db, path, schema, create=create, version=version, compatible=compatible, upgrade=None):
            db.close()
            return None
        return db
    except BaseException:
        db.close()
        raise


def _has_bytes(path: Path) -> bool:
    try:
        return path.stat().st_size > 0
    except OSError:
        return False


def prepare(db: sqlite3.Connection, path: Path, schema: str, *, create: bool, version: str,
            compatible: str | None = None, upgrade: Upgrade | None = None) -> bool:
    """Check the schema version, creating the schema first when the file is new and creation is allowed. False
    when the file holds no tables and creation is not allowed: another process is creating it, and nothing in it
    is committed yet, so the caller reads it as empty. `version` is the version this kind of database is at, and
    `compatible` the oldest version whose code reads it, `version` when not given, STORE-029. A file at an earlier
    version is brought up to it by `upgrade` when this kind of database has one; a file at a later version is read
    when its own `compatible_from` is at or below `version`, and its two numbers are left as they are, STORE-029.
    """
    found, needed = _versions(db)
    if found is None:
        # The tables and the version are read in one transaction, so a file another connection creates between
        # the two reads is seen whole, with its version, and never taken for an earlier one.
        db.execute('BEGIN')
        try:
            tables = db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
            found, needed = _versions(db) if tables else (None, None)
        finally:
            db.execute('COMMIT')
        if found is None:
            if tables:
                raise StoreError(f'{path} was written by an earlier Metaform and has no schema version.',
                                 f'rename {path} and run metaform again')
            if not create:
                return False
            # The switch to WAL comes before the schema, so the schema lands under WAL and a reader in another
            # process never waits on it or holds a lock across the switch, STORE-006.
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('BEGIN IMMEDIATE;\n' + schema +
                             f"\nINSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', '{version}');"
                             f"\nINSERT OR IGNORE INTO meta(key, value) VALUES ('compatible_from', "
                             f"'{compatible or version}');"
                             '\nCOMMIT;')
            found, needed = _versions(db)
    at = _number(found)
    if found is not None and at is not None and at < int(version) and upgrade is not None:
        if upgrade(db, path, found):
            raise Replaced
        found, needed = _versions(db)
        at = _number(found)
    if not readable(found, needed, version):
        if at is not None and at > int(version):
            raise NewerStore(f'{path} has schema version {found}, which a Metaform reads from version '
                             f'{needed or found}; this Metaform supports version {version}.',
                             'install the Metaform release that wrote it')
        raise StoreError(f'{path} has schema version {found}; this Metaform supports version {version}.',
                         'install the Metaform release that wrote it')
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA journal_mode=WAL')
    return True


def readable(found: str | None, needed: str | None, version: str) -> bool:
    """Whether code at layout `version` reads and writes a file at layout `found` whose `compatible_from` is `needed`:
    the same layout, or a later one whose `compatible_from` is at or below `version`; a missing `compatible_from` is
    the layout itself, STORE-029. An earlier layout is not read as it is; it is upgraded first."""
    if found == version:
        return True
    at, oldest = _number(found), _number(needed if needed is not None else found)
    return at is not None and oldest is not None and at > int(version) and oldest <= int(version)


def stamp(db: sqlite3.Connection, version: str, compatible: str) -> None:
    """Inside the caller's transaction: record the layout a file is now at and the oldest layout whose code reads
    it, STORE-029. An upgrade writes both, so a breaking change never leaves an earlier layout's `compatible_from`
    behind to let older code in."""
    db.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)", (version,))
    db.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('compatible_from', ?)", (compatible,))


def _number(value: str | None) -> int | None:
    """A layout version as a number, or None when it is not one: ASCII digits only, since `isdigit` also takes
    characters such as `²` that `int` refuses, and a damaged or crafted value is refused rather than raised."""
    return int(value) if value is not None and value.isascii() and value.isdigit() else None


def _versions(db: sqlite3.Connection) -> tuple[str | None, str | None]:
    """The file's `schema_version` and `compatible_from`, read in one statement so both come from one commit."""
    try:
        rows = dict(db.execute("SELECT key, value FROM meta WHERE key IN ('schema_version', 'compatible_from')"))
    except sqlite3.OperationalError:
        return None, None
    found, needed = rows.get('schema_version'), rows.get('compatible_from')
    return (None if found is None else str(found)), (None if needed is None else str(needed))
