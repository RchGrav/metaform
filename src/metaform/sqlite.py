"""Opening Metaform's SQLite files: pragmas, schema creation and the schema version check.

The base database, every metaform store, the history database and the prompt
database all open through `opened`, so all follow STORE-006 (WAL, foreign keys,
busy timeout, one file opened and prepared inside its lock) and STORE-029 (the
schema version is read before any other access, and an unknown one is refused
before anything is written).
"""
from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path

from .errors import NewerStore, StoreError

SCHEMA_VERSION = '20'  # the metaform store's layout; the base, history and prompt databases keep their own, STORE-029
BUSY_SECONDS = 30  # how long a write waits for another process's write to finish, STORE-006

Upgrade = Callable[[sqlite3.Connection, Path, str], None]  # brings a file at an earlier version up to date

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
def opened(path: Path, schema: str, *, write: bool, version: str,
           upgrade: Upgrade | None = None) -> Generator[sqlite3.Connection, None, None]:
    """A prepared connection to the file, opened inside the file's lock, STORE-006; the caller begins and ends
    the transaction. A write holds the lock until the block ends and creates the file when there is none. A read
    lets go of the lock once its connection is prepared, and reads a file with nothing committed yet, no file, no
    bytes or no tables, as an empty database in memory, without touching a file of no bytes at all."""
    lock = writer_lock(path)
    lock.acquire()
    held = True
    try:
        db: sqlite3.Connection | None = None
        if write:
            path.parent.mkdir(parents=True, exist_ok=True)
            db = connect(path)
            try:
                prepare(db, path, schema, create=True, version=version, upgrade=upgrade)
            except BaseException:
                db.close()
                raise
        else:
            if _has_bytes(path):
                db = connect(path)
                try:
                    if not prepare(db, path, schema, create=False, version=version, upgrade=upgrade):
                        db.close()
                        db = None
                except BaseException:
                    db.close()
                    raise
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


def _has_bytes(path: Path) -> bool:
    try:
        return path.stat().st_size > 0
    except OSError:
        return False


def prepare(db: sqlite3.Connection, path: Path, schema: str, *, create: bool, version: str,
            upgrade: Upgrade | None = None) -> bool:
    """Check the schema version, creating the schema first when the file is new and creation is allowed. False
    when the file holds no tables and creation is not allowed: another process is creating it, and nothing in it
    is committed yet, so the caller reads it as empty. `version` is the version this kind of database is at, STORE-029.
    A file at an earlier version is brought up to it by `upgrade` when this kind of database has one, STORE-029.
    """
    found = _version(db)
    if found is None:
        # The tables and the version are read in one transaction, so a file another connection creates between
        # the two reads is seen whole, with its version, and never taken for an earlier one.
        db.execute('BEGIN')
        try:
            tables = db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
            found = _version(db) if tables else None
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
                             '\nCOMMIT;')
            found = _version(db)
    if found != version and upgrade is not None and found is not None and found.isdigit() and int(found) < int(version):
        upgrade(db, path, found)
        found = _version(db)
    if found != version:
        newer = found is not None and found.isdigit() and int(found) > int(version)
        raise (NewerStore if newer else StoreError)(
            f'{path} has schema version {found}; this Metaform supports version {version}.',
            'install the Metaform release that wrote it')
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA journal_mode=WAL')
    return True


def _version(db: sqlite3.Connection) -> str | None:
    try:
        row = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    except sqlite3.OperationalError:
        return None
    return None if row is None else str(row[0])
