"""The Metaform home and its base database.

All Metaform data is global. The home holds one base database: the registered
projects, per-folder context, and settings with their glue state.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def home() -> Path:
    return Path(os.environ.get('METAFORM_HOME') or Path.home() / '.metaform').expanduser()


def _schema(db):
    db.execute('CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, path TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS settings(scope TEXT NOT NULL, key TEXT NOT NULL, '
               'value TEXT NOT NULL, PRIMARY KEY(scope, key))')
    db.execute('CREATE TABLE IF NOT EXISTS glue(scope TEXT NOT NULL, key TEXT NOT NULL, '
               'PRIMARY KEY(scope, key))')


@contextmanager
def base(write=False):
    """Open the base database. Reads never create or change anything."""
    path = home() / 'metaform.sqlite3'
    if not write and not path.exists():
        db = sqlite3.connect(':memory:')
        _schema(db)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path)
        if write:
            _schema(db)
    try:
        yield db
        if write:
            db.commit()
    finally:
        db.close()


def projects() -> dict[str, Path]:
    with base() as db:
        return {row[0]: Path(row[1]) for row in db.execute('SELECT id, path FROM projects ORDER BY id')}


def add_project(identifier: str, path: Path) -> None:
    with base(write=True) as db:
        db.execute('INSERT INTO projects(id, path) VALUES (?, ?) '
                   'ON CONFLICT(id) DO UPDATE SET path=excluded.path', (identifier, str(path)))


def folder_project(folder: Path) -> str | None:
    """The registered project whose folder contains this one, the deepest match."""
    folder = folder.resolve()
    best = None
    for identifier, path in projects().items():
        path = path.resolve()
        if folder == path or path in folder.parents:
            if best is None or len(path.parts) > len(best[1].parts):
                best = (identifier, path)
    return best[0] if best else None


def saved(scope: str, key: str):
    with base() as db:
        row = db.execute('SELECT value FROM settings WHERE scope=? AND key=?', (scope, key)).fetchone()
    return json.loads(row[0]) if row else None


def has_saved(scope: str, key: str) -> bool:
    with base() as db:
        return db.execute('SELECT 1 FROM settings WHERE scope=? AND key=?', (scope, key)).fetchone() is not None


def save(scope: str, key: str, value) -> None:
    with base(write=True) as db:
        db.execute('INSERT INTO settings(scope, key, value) VALUES (?, ?, ?) '
                   'ON CONFLICT(scope, key) DO UPDATE SET value=excluded.value',
                   (scope, key, json.dumps(value)))


def clear(scope: str, key: str) -> None:
    with base(write=True) as db:
        db.execute('DELETE FROM settings WHERE scope=? AND key=?', (scope, key))


def glued(scope: str, key: str) -> bool:
    with base() as db:
        return db.execute('SELECT 1 FROM glue WHERE scope=? AND key=?', (scope, key)).fetchone() is not None


def set_glue(scope: str, key: str, on: bool) -> None:
    with base(write=True) as db:
        if on:
            db.execute('INSERT OR IGNORE INTO glue(scope, key) VALUES (?, ?)', (scope, key))
        else:
            db.execute('DELETE FROM glue WHERE scope=? AND key=?', (scope, key))
