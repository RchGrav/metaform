"""Opening Metaform's SQLite files: pragmas, schema creation and the schema version check.

Both the base database and every metaform store open through here, so both
follow STORE-006 (WAL, foreign keys, busy timeout) and STORE-029 (the schema
version is read before any other access, and an unknown one is refused before
anything is written).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .errors import StoreError

SCHEMA_VERSION = '1'


def connect(path: Path | str) -> sqlite3.Connection:
    """A connection in autocommit mode: every transaction is begun explicitly."""
    db = sqlite3.connect(str(path), isolation_level=None, timeout=5.0)
    db.execute('PRAGMA busy_timeout=5000')
    return db


def memory(schema: str) -> sqlite3.Connection:
    """An empty in-memory database with the schema, for reads of a file that does not exist."""
    db = sqlite3.connect(':memory:', isolation_level=None)
    db.executescript(schema)
    return db


def prepare(db: sqlite3.Connection, path: Path, schema: str, *, create: bool) -> None:
    """Check the schema version, creating the schema first when the file is new and creation is allowed."""
    version = _version(db)
    if version is None:
        # The tables and the version are read in one transaction, so a file another connection creates between
        # the two reads is seen whole, with its version, and never taken for an earlier one.
        db.execute('BEGIN')
        try:
            tables = db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
            version = _version(db) if tables else None
        finally:
            db.execute('COMMIT')
        if version is None:
            if tables or not create:
                raise StoreError(f'{path} was written by an earlier Metaform and has no schema version.',
                                 f'rename {path} and run metaform again')
            db.executescript('BEGIN IMMEDIATE;\n' + schema +
                             f"\nINSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', '{SCHEMA_VERSION}');"
                             '\nCOMMIT;')
            version = _version(db)
    if version != SCHEMA_VERSION:
        raise StoreError(f'{path} has schema version {version}; this Metaform supports version {SCHEMA_VERSION}.',
                         'install the Metaform release that wrote it')
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA journal_mode=WAL')


def _version(db: sqlite3.Connection) -> str | None:
    try:
        row = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    except sqlite3.OperationalError:
        return None
    return None if row is None else str(row[0])
