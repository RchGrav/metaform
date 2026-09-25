"""The Metaform home and its base database, STORE-001 and STORE-002.

All Metaform data is global. The home holds the base database, with the
registered projects and their metaforms, per-folder context, settings with
their glue state, module state and what the installer set up, and one store
per metaform under `projects/<project id>/metaforms/<metaform id>/`. Nothing
is ever written into a project's folder.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import sqlite
from .errors import StoreError

BASE_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS projects(
  project_id   TEXT PRIMARY KEY,
  path         TEXT NOT NULL,
  path_key     TEXT NOT NULL UNIQUE,
  target_type  TEXT NOT NULL DEFAULT 'path'
               CHECK(target_type IN ('path','url','artifact','inline','inferred')),
  target_value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS folders(
  path_key TEXT PRIMARY KEY,
  path     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings(
  scope    TEXT NOT NULL,
  owner    TEXT NOT NULL,
  key      TEXT NOT NULL,
  position INTEGER NOT NULL DEFAULT 0,
  value    TEXT NOT NULL,
  PRIMARY KEY(scope, owner, key, position)
);
CREATE TABLE IF NOT EXISTS glue(
  scope TEXT NOT NULL,
  owner TEXT NOT NULL,
  key   TEXT NOT NULL,
  PRIMARY KEY(scope, owner, key)
);
CREATE TABLE IF NOT EXISTS module_state(
  module_id TEXT PRIMARY KEY,
  enabled   INTEGER NOT NULL CHECK(enabled IN (0, 1))
);
CREATE TABLE IF NOT EXISTS installs(
  tool       TEXT PRIMARY KEY,
  source     TEXT NOT NULL,
  skill_path TEXT,
  installed  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metaforms(
  metaform_id TEXT PRIMARY KEY,
  project_id  TEXT NOT NULL REFERENCES projects(project_id),
  name        TEXT NOT NULL,
  created     TEXT NOT NULL,
  UNIQUE(project_id, name)
);
CREATE TABLE IF NOT EXISTS active_metaforms(
  project_id  TEXT PRIMARY KEY REFERENCES projects(project_id),
  metaform_id TEXT NOT NULL REFERENCES metaforms(metaform_id)
);
"""

PROJECT_ID = re.compile(r'^[a-z0-9][a-z0-9_-]{0,63}$')
NAME = re.compile(r'^[A-Za-z0-9._-]{1,128}$')
ID = re.compile(r'^[0-9a-f]{32}$')
TARGET_TYPES = ('path', 'url', 'artifact', 'inline', 'inferred')


def home() -> Path:
    """The Metaform home: METAFORM_HOME when set, otherwise ~/.metaform, STORE-001."""
    return Path(os.environ.get('METAFORM_HOME') or Path.home() / '.metaform').expanduser()


def base_path() -> Path:
    return home() / 'metaform.sqlite3'


def now() -> str:
    """The current time as ISO 8601 UTC, to the second."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def path_key(path: Path | str) -> str:
    """The comparison key of a folder: resolved and case-folded where the system folds case."""
    return os.path.normcase(str(Path(path).expanduser().resolve()))


@contextmanager
def base(write: bool = False) -> Iterator[sqlite3.Connection]:
    """One transaction on the base database. A read of a home with no base database creates nothing."""
    path = base_path()
    if not write and not path.exists():
        db = sqlite.memory(BASE_SCHEMA)
        try:
            yield db
        finally:
            db.close()
        return
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite.connect(path)
    try:
        sqlite.prepare(db, path, BASE_SCHEMA, create=write)
        db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        try:
            yield db
        except BaseException:
            db.execute('ROLLBACK')
            raise
        db.execute('COMMIT')
    finally:
        db.close()


# Projects ---------------------------------------------------------------------

@dataclass(frozen=True)
class Project:
    project_id: str
    path: str
    target_type: str
    target_value: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _project(row: tuple[Any, ...]) -> Project:
    return Project(row[0], row[1], row[2], row[3])


def projects() -> tuple[Project, ...]:
    with base() as db:
        rows = db.execute('SELECT project_id, path, target_type, target_value FROM projects ORDER BY project_id')
        return tuple(_project(row) for row in rows)


def project(project_id: str) -> Project | None:
    with base() as db:
        row = db.execute('SELECT project_id, path, target_type, target_value FROM projects WHERE project_id=?',
                         (project_id,)).fetchone()
    return None if row is None else _project(row)


def add_project(project_id: str, path: Path | str, target_type: str | None = None,
                target_value: str | None = None) -> str:
    """Register a project, STORE-031. Returns the line to report."""
    if not PROJECT_ID.fullmatch(project_id):
        raise StoreError(f'{project_id!r} is not a project id: use lowercase letters, digits, - and _.',
                         'metaform add project <id> <path>')
    folder = Path(path).expanduser().resolve()
    if not folder.is_dir():
        raise StoreError(f'No folder at {folder}.', f'metaform add project {project_id} <existing folder>')
    if target_type is None:
        target_type, target_value = 'path', str(folder)
    if target_type not in TARGET_TYPES:
        raise StoreError(f'{target_type!r} is not a target type: use {", ".join(TARGET_TYPES)}.',
                         f'metaform add project {project_id} {folder} path {folder}')
    if target_value is None:
        target_value = 'inferred' if target_type == 'inferred' else ''
    if target_value == '':
        raise StoreError(f'Target type {target_type} needs a value.',
                         f'metaform add project {project_id} {folder} {target_type} <value>')
    record = Project(project_id, str(folder), target_type, target_value)
    with base(write=True) as db:
        existing = db.execute('SELECT project_id, path, target_type, target_value FROM projects WHERE project_id=?',
                              (project_id,)).fetchone()
        if existing is not None:
            if _project(existing) == record:
                return f'Project {project_id} is already registered.'
            raise StoreError(f'Project {project_id} is registered with another folder or target.',
                             'metaform list projects')
        holder = db.execute('SELECT project_id FROM projects WHERE path_key=?', (path_key(folder),)).fetchone()
        if holder is not None:
            raise StoreError(f'{folder} is already registered as project {holder[0]}.', 'metaform list projects')
        db.execute('INSERT INTO projects(project_id, path, path_key, target_type, target_value) VALUES (?, ?, ?, ?, ?)',
                   (project_id, str(folder), path_key(folder), target_type, target_value))
    return f'Added project {project_id}: {folder} (target {target_type} {target_value})'


def register(record: Project) -> None:
    """Register a project from an exchange document's record, STORE-027. The folder need not exist here."""
    with base(write=True) as db:
        db.execute('INSERT OR IGNORE INTO projects(project_id, path, path_key, target_type, target_value) '
                   'VALUES (?, ?, ?, ?, ?)',
                   (record.project_id, record.path, os.path.normcase(record.path), record.target_type,
                    record.target_value))


def folder_project(folder: Path) -> str | None:
    """The registered project whose folder contains this one, the deepest match, STORE-002."""
    key = path_key(folder)
    best: tuple[int, str] | None = None
    for record in projects():
        root = os.path.normcase(record.path)
        if key == root or key.startswith(root.rstrip(os.sep) + os.sep):
            if best is None or len(root) > best[0]:
                best = (len(root), record.project_id)
    return None if best is None else best[1]


# Settings ---------------------------------------------------------------------

def stored(scope: str, owner: str, key: str) -> list[Any] | None:
    """The stored member values of a setting at one scope, in order, or None when nothing is stored."""
    with base() as db:
        rows = db.execute('SELECT value FROM settings WHERE scope=? AND owner=? AND key=? ORDER BY position',
                          (scope, owner, key)).fetchall()
    return [json.loads(row[0]) for row in rows] if rows else None


def save(scope: str, owner: str, key: str, members: list[Any], *, folder: Path | None = None) -> None:
    """Store a setting as one row per member, replacing what was stored. A folder row is written with it."""
    with base(write=True) as db:
        if folder is not None:
            db.execute('INSERT OR IGNORE INTO folders(path_key, path) VALUES (?, ?)', (scope, str(folder)))
        db.execute('DELETE FROM settings WHERE scope=? AND owner=? AND key=?', (scope, owner, key))
        db.executemany('INSERT INTO settings(scope, owner, key, position, value) VALUES (?, ?, ?, ?, ?)',
                       [(scope, owner, key, position, json.dumps(member)) for position, member in enumerate(members)])


def clear(scope: str, owner: str, key: str) -> None:
    with base(write=True) as db:
        db.execute('DELETE FROM settings WHERE scope=? AND owner=? AND key=?', (scope, owner, key))


def glued(scope: str, owner: str, key: str) -> bool:
    with base() as db:
        return db.execute('SELECT 1 FROM glue WHERE scope=? AND owner=? AND key=?',
                          (scope, owner, key)).fetchone() is not None


def set_glue(scope: str, owner: str, key: str, on: bool, *, folder: Path | None = None) -> None:
    with base(write=True) as db:
        if on:
            if folder is not None:
                db.execute('INSERT OR IGNORE INTO folders(path_key, path) VALUES (?, ?)', (scope, str(folder)))
            db.execute('INSERT OR IGNORE INTO glue(scope, owner, key) VALUES (?, ?, ?)', (scope, owner, key))
        else:
            db.execute('DELETE FROM glue WHERE scope=? AND owner=? AND key=?', (scope, owner, key))


# Module state -----------------------------------------------------------------

def module_state(module_id: str) -> bool | None:
    """The user's stored choice for a module, or None when the module's declaration decides."""
    with base() as db:
        row = db.execute('SELECT enabled FROM module_state WHERE module_id=?', (module_id,)).fetchone()
    return None if row is None else bool(row[0])


def set_module_state(module_id: str, enabled: bool | None) -> None:
    with base(write=True) as db:
        if enabled is None:
            db.execute('DELETE FROM module_state WHERE module_id=?', (module_id,))
        else:
            db.execute('INSERT INTO module_state(module_id, enabled) VALUES (?, ?) '
                       'ON CONFLICT(module_id) DO UPDATE SET enabled=excluded.enabled', (module_id, int(enabled)))


# Meta values ------------------------------------------------------------------

def meta(key: str) -> str | None:
    with base() as db:
        row = db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
    return None if row is None else str(row[0])


def set_meta(key: str, value: str) -> None:
    with base(write=True) as db:
        db.execute('INSERT INTO meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                   (key, value))


# Metaforms --------------------------------------------------------------------

@dataclass(frozen=True)
class Metaform:
    metaform_id: str
    project_id: str
    name: str
    created: str
    active: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_ACTIVE = ('SELECT m.metaform_id, m.name, m.created FROM active_metaforms a '
           'JOIN metaforms m ON m.metaform_id = a.metaform_id WHERE a.project_id=?')


def metaforms(project_id: str) -> tuple[Metaform, ...]:
    with base() as db:
        active = db.execute('SELECT metaform_id FROM active_metaforms WHERE project_id=?', (project_id,)).fetchone()
        rows = db.execute('SELECT metaform_id, name, created FROM metaforms WHERE project_id=? ORDER BY rowid',
                          (project_id,)).fetchall()
    return tuple(Metaform(row[0], project_id, row[1], row[2], active is not None and row[0] == active[0])
                 for row in rows)


def active_metaform(project_id: str) -> Metaform | None:
    with base() as db:
        row = db.execute(_ACTIVE, (project_id,)).fetchone()
    return None if row is None else Metaform(row[0], project_id, row[1], row[2], True)


def ensure_metaform(project_id: str) -> Metaform:
    """The active metaform, creating `main` on the first write to a project that has none, STORE-041."""
    current = active_metaform(project_id)
    if current is not None:
        return current
    with base(write=True) as db:
        row = db.execute(_ACTIVE, (project_id,)).fetchone()
        if row is not None:
            return Metaform(row[0], project_id, row[1], row[2], True)
        return _create_metaform(db, project_id, 'main')


def _create_metaform(db: sqlite3.Connection, project_id: str, name: str, metaform_id: str | None = None,
                     created: str | None = None, activate: bool = True) -> Metaform:
    record = Metaform(metaform_id or uuid.uuid4().hex, project_id, name, created or now(), activate)
    db.execute('INSERT INTO metaforms(metaform_id, project_id, name, created) VALUES (?, ?, ?, ?)',
               (record.metaform_id, project_id, name, record.created))
    if activate:
        db.execute('INSERT INTO active_metaforms(project_id, metaform_id) VALUES (?, ?) '
                   'ON CONFLICT(project_id) DO UPDATE SET metaform_id=excluded.metaform_id',
                   (project_id, record.metaform_id))
    return record


def add_metaform(project_id: str, name: str) -> Metaform:
    """A new, empty metaform for the project, made active; the old one is kept whole, STORE-041."""
    if not NAME.fullmatch(name) or ID.fullmatch(name):
        raise StoreError(f'{name!r} is not a metaform name: use letters, digits, ., _ and -.',
                         'metaform add metaform <name>')
    with base(write=True) as db:
        taken = db.execute('SELECT 1 FROM metaforms WHERE project_id=? AND name=?', (project_id, name)).fetchone()
        if taken is not None:
            raise StoreError(f'Project {project_id} already has a metaform named {name}.', 'metaform list metaforms')
        if db.execute('SELECT 1 FROM active_metaforms WHERE project_id=?', (project_id,)).fetchone() is None:
            _create_metaform(db, project_id, 'main')
        return _create_metaform(db, project_id, name)


def activate_metaform(project_id: str, name: str) -> Metaform:
    with base(write=True) as db:
        row = db.execute('SELECT metaform_id, created FROM metaforms WHERE project_id=? AND name=?',
                         (project_id, name)).fetchone()
        if row is None:
            raise StoreError(f'No metaform {name} in {project_id}.', 'metaform list metaforms')
        db.execute('INSERT INTO active_metaforms(project_id, metaform_id) VALUES (?, ?) '
                   'ON CONFLICT(project_id) DO UPDATE SET metaform_id=excluded.metaform_id', (project_id, row[0]))
    return Metaform(row[0], project_id, name, row[1], True)


def import_metaform(project_id: str, metaform_id: str, name: str, created: str, *, activate: bool) -> bool:
    """Record an imported metaform unless its id exists. Returns whether it was added, STORE-027."""
    with base(write=True) as db:
        if db.execute('SELECT 1 FROM metaforms WHERE metaform_id=?', (metaform_id,)).fetchone() is not None:
            return False
        has_active = db.execute('SELECT 1 FROM active_metaforms WHERE project_id=?', (project_id,)).fetchone()
        _create_metaform(db, project_id, name, metaform_id, created, activate=activate or has_active is None)
    return True


def store_path(project_id: str, metaform_id: str) -> Path:
    """Where one metaform's store lives, STORE-003."""
    return home() / 'projects' / project_id / 'metaforms' / metaform_id / 'store.sqlite3'
