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
import shutil
import sqlite3
import sys
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import changes, sqlite
from .errors import StoreError
from .wording import counted, listed

BASE_SCHEMA_VERSION = '1'  # the base database's own layout, apart from the store's, STORE-029
# The nonce table, BASE-050. A home made before it existed is given it on the first write of a nonce.
NONCES = """CREATE TABLE IF NOT EXISTS nonces(
  nonce     TEXT PRIMARY KEY,
  module_id TEXT NOT NULL,
  function  TEXT NOT NULL,
  value     TEXT NOT NULL,
  created   TEXT NOT NULL,
  closed    TEXT
);
"""
BASE_SCHEMA = NONCES + """
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


_AT: ContextVar[Path | None] = ContextVar('metaform_home_at', default=None)


def home() -> Path:
    """The Metaform home: METAFORM_HOME when set, otherwise ~/.metaform, STORE-001."""
    chosen = _AT.get()
    if chosen is not None:
        return chosen
    return Path(os.environ.get('METAFORM_HOME') or Path.home() / '.metaform').expanduser()


@contextmanager
def at(folder: Path) -> Generator[None, None, None]:
    """Read another home, such as a directly run wheel's data folder, for the length of the block, BASE-025."""
    token = _AT.set(folder)
    try:
        yield
    finally:
        _AT.reset(token)


def base_path() -> Path:
    return home() / 'metaform.sqlite3'


def now() -> str:
    """The current time as ISO 8601 UTC, to the second."""
    return datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')


def path_key(path: Path | str) -> str:
    """The comparison key of a folder: resolved and case-folded where the system folds case."""
    return os.path.normcase(str(Path(path).expanduser().resolve()))


@contextmanager
def base(write: bool = False) -> Generator[sqlite3.Connection, None, None]:
    """One transaction on the base database. A read of a home with no base database creates nothing."""
    with sqlite.opened(base_path(), BASE_SCHEMA, write=write, version=BASE_SCHEMA_VERSION) as db:
        db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        try:
            yield db
        except BaseException:
            db.execute('ROLLBACK')
            raise
        db.execute('COMMIT')


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
        register_in(db, record)


def register_in(db: sqlite3.Connection, record: Project) -> None:
    """Register a project inside an open base transaction; a folder another project holds is refused by name."""
    key = path_key(record.path)
    holder = db.execute('SELECT project_id FROM projects WHERE path_key=?', (key,)).fetchone()
    if holder is not None and holder[0] != record.project_id:
        raise StoreError(f'{record.path} is already registered as project {holder[0]}.', 'metaform list projects')
    if db.execute('SELECT 1 FROM projects WHERE project_id=?', (record.project_id,)).fetchone() is not None:
        return
    db.execute('INSERT INTO projects(project_id, path, path_key, target_type, target_value) VALUES (?, ?, ?, ?, ?)',
               (record.project_id, record.path, key, record.target_type, record.target_value))


def project_at(path: str) -> str | None:
    """The project registered with this folder, compared through its path key."""
    with base() as db:
        row = db.execute('SELECT project_id FROM projects WHERE path_key=?', (path_key(path),)).fetchone()
    return None if row is None else str(row[0])


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
    notices: tuple[Any, ...] = ()

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
    changes.note(project_id)  # the project's metaforms changed; announced when the command ends, VIEW-018
    return record


def add_metaform(project_id: str, name: str, *, activate: bool = True) -> Metaform:
    """A new, empty metaform for the project, made active unless asked not to; the old one is kept whole, STORE-041.

    A name the project already has is stored with `-2`, or the next free number, added; the caller compares the
    returned name with the one it asked for to say so, BASE-044.
    """
    if not NAME.fullmatch(name) or ID.fullmatch(name):
        raise StoreError(f'{name!r} is not a metaform name: use letters, digits, ., _ and -.',
                         'metaform add metaform <name>')
    with base(write=True) as db:
        chosen, number = name, 1
        while db.execute('SELECT 1 FROM metaforms WHERE project_id=? AND name=?', (project_id, chosen)).fetchone():
            number += 1
            chosen = f'{name}-{number}'
        if db.execute('SELECT 1 FROM active_metaforms WHERE project_id=?', (project_id,)).fetchone() is None:
            _create_metaform(db, project_id, 'main')
        return _create_metaform(db, project_id, chosen, activate=activate)


def metaform_by_id(project_id: str, metaform_id: str) -> Metaform | None:
    with base() as db:
        row = db.execute('SELECT metaform_id, name, created FROM metaforms WHERE metaform_id=? AND project_id=?',
                         (metaform_id, project_id)).fetchone()
        active = db.execute('SELECT metaform_id FROM active_metaforms WHERE project_id=?', (project_id,)).fetchone()
    if row is None:
        return None
    return Metaform(row[0], project_id, row[1], row[2], active is not None and active[0] == row[0])


def withdraw_metaform(project_id: str, metaform_id: str) -> None:
    """Undo a metaform created in this operation whose first write failed: its row and its store file go."""
    with base(write=True) as db:
        db.execute('DELETE FROM active_metaforms WHERE project_id=? AND metaform_id=?', (project_id, metaform_id))
        db.execute('DELETE FROM metaforms WHERE metaform_id=? AND project_id=?', (metaform_id, project_id))
    remove_store(store_path(project_id, metaform_id))
    changes.note(project_id)


def activate_metaform(project_id: str, name: str) -> Metaform:
    with base(write=True) as db:
        row = db.execute('SELECT metaform_id, created FROM metaforms WHERE project_id=? AND name=?',
                         (project_id, name)).fetchone()
        if row is None:
            raise StoreError(f'No metaform {name} in {project_id}.', 'metaform list metaforms')
        db.execute('INSERT INTO active_metaforms(project_id, metaform_id) VALUES (?, ?) '
                   'ON CONFLICT(project_id) DO UPDATE SET metaform_id=excluded.metaform_id', (project_id, row[0]))
    changes.note(project_id)
    return Metaform(row[0], project_id, name, row[1], True)


def import_metaform(project_id: str, metaform_id: str, name: str, created: str, *, activate: bool) -> bool:
    """Record an imported metaform unless its id exists. Returns whether it was added, STORE-027."""
    with base(write=True) as db:
        return import_metaform_in(db, project_id, metaform_id, name, created, activate=activate)


def import_metaform_in(db: sqlite3.Connection, project_id: str, metaform_id: str, name: str, created: str, *,
                       activate: bool, never_active: bool = False) -> bool:
    """Record an imported metaform inside an open base transaction, unless its id exists. It becomes active when
    asked, or when its project has no active metaform, unless it must never be made active, BASE-025."""
    if db.execute('SELECT 1 FROM metaforms WHERE metaform_id=?', (metaform_id,)).fetchone() is not None:
        return False
    has_active = db.execute('SELECT 1 FROM active_metaforms WHERE project_id=?', (project_id,)).fetchone()
    _create_metaform(db, project_id, name, metaform_id, created,
                     activate=not never_active and (activate or has_active is None))
    return True


def free_name(db: sqlite3.Connection, project_id: str, name: str, taken: set[str] | None = None) -> str:
    """The name, or it with `-2` or the next free number, so no two metaforms of a project share one, STORE-041."""
    chosen, number = name, 1
    while chosen in (taken or set()) or db.execute('SELECT 1 FROM metaforms WHERE project_id=? AND name=?',
                                                  (project_id, chosen)).fetchone():
        number += 1
        chosen = f'{name}-{number}'
    return chosen


def metaform_owner(metaform_id: str) -> str | None:
    """The project a metaform id belongs to in this home, if any."""
    with base() as db:
        row = db.execute('SELECT project_id FROM metaforms WHERE metaform_id=?', (metaform_id,)).fetchone()
    return None if row is None else str(row[0])


@dataclass(frozen=True)
class Cleared:
    """What clearing a project removed, PROJ-025, and each path it could not remove with the system's reason."""
    project_id: str
    metaforms: tuple[str, ...]
    reports: int
    not_removed: tuple[tuple[str, str], ...] = ()
    backup: str | None = None  # the backup made before anything was removed, PROJ-030

    def to_dict(self) -> dict[str, Any]:
        found: dict[str, Any] = {'project': self.project_id, 'metaforms': list(self.metaforms),
                                 'reports': self.reports}
        if self.backup:
            found['backup'] = self.backup
            found['restore'] = self.restore
        if self.not_removed:
            found['not_removed'] = [{'path': path, 'reason': reason} for path, reason in self.not_removed]
        return found

    def _metaforms(self, stores: bool) -> str:
        """The metaforms by name, and with their stores when `stores`; a clause set off by commas when named."""
        count = len(self.metaforms)
        if not count:
            return counted(0, 'metaform', 'metaforms')
        held = (' with its store,' if count == 1 else ' with their stores,') if stores else ''
        return f'{counted(count, "metaform", "metaforms")}, {listed(self.metaforms)},{held}'

    @property
    def caution(self) -> str:
        """What `clear project` removes, said before it does."""
        return (f'Clearing {self.project_id} removes {self._metaforms(True)} and '
                f'{counted(self.reports, "report file", "report files")}. Its registration, folder, settings, origins '
                'and variants stay.')

    @property
    def said(self) -> str:
        """What `clear project` removed, said after it did."""
        return (f'Cleared {self.project_id}: {self._metaforms(False)} and '
                f'{counted(self.reports, "report file", "report files")}. Its registration, folder, settings, origins '
                'and variants stay.')

    @property
    def restore(self) -> str:
        """The one command that brings back what the clear removed."""
        return f'metaform restore project {self.project_id}'

    @property
    def held(self) -> str:
        """What the project held, as a backup and a restore say it."""
        return f'{self._metaforms(False)} and {counted(self.reports, "report file", "report files")}'

    def remedy(self, again: str) -> str:
        """What to do about what could not be removed; `again` is how the surface clears the project once more."""
        one = len(self.not_removed) == 1
        return (f'Close any program that has {"it" if one else "them"} open, such as a running web GUI, or fix '
                f'{"its" if one else "their"} permissions, then {again}.')

    @property
    def left(self) -> str:
        """That what could not be removed is still on disk, said once over MCP."""
        return 'It could not be removed and is still on disk.' if len(self.not_removed) == 1 else \
            'They could not be removed and are still on disk.'


def to_clear(project_id: str) -> Cleared:
    """What `clear project` would remove: the project's metaforms by name, in creation order, and its report files."""
    names = tuple(form.name for form in metaforms(project_id))
    reports = home() / 'projects' / project_id / 'reports'
    count = sum(1 for path in reports.iterdir() if path.is_file()) if reports.is_dir() else 0
    return Cleared(project_id, names, count)


def clear_project(project_id: str) -> Cleared:
    """Remove every metaform of the project with its store, and its report files, PROJ-025.

    The registration, the folder rows and settings, and the history under `history.sqlite3` and `origins/` stay. The
    rows go whatever happens to the files; a file or folder that cannot be removed is named in the result.
    """
    found = to_clear(project_id)
    # It is backed up before anything goes, and nothing goes when it cannot be: what a clear removes cannot be made
    # again by an intake, and a clear without its backup is a loss the person learns of when they need it, PROJ-030.
    try:
        saved = backup_project(project_id)
    except OSError as error:
        raise StoreError(f'{project_id} was not cleared, since it could not be backed up first: '
                         f'{error.strerror or error}.', 'metaform list backups') from error
    with base(write=True) as db:
        db.execute('DELETE FROM active_metaforms WHERE project_id=?', (project_id,))
        db.execute('DELETE FROM metaforms WHERE project_id=?', (project_id,))
    failed: list[tuple[str, str]] = []
    for name in ('metaforms', 'reports'):
        _remove_tree(home() / 'projects' / project_id / name, failed)
    changes.note(project_id)
    return Cleared(found.project_id, found.metaforms, found.reports, _innermost(failed),
                   saved.name if saved is not None else None)


@dataclass(frozen=True)
class Backup:
    """What a project held when it was cleared, kept so it can be brought back, PROJ-030."""
    project_id: str
    name: str
    metaforms: tuple[str, ...]
    reports: int

    @property
    def held(self) -> str:
        return Cleared(self.project_id, self.metaforms, self.reports).held

    def to_dict(self) -> dict[str, Any]:
        return {'project': self.project_id, 'name': self.name, 'metaforms': list(self.metaforms),
                'reports': self.reports, 'held': self.held}


def _backups(project_id: str) -> Path:
    return home() / 'backups' / 'clear' / project_id


def _copied(source: Path, target: Path) -> None:
    """A folder copied whole. A store is copied through SQLite's own backup, so one another program holds open is
    copied as it stands, with what its write-ahead log holds."""
    for path in sorted(source.rglob('*')):
        to = target / path.relative_to(source)
        if path.is_dir():
            to.mkdir(parents=True, exist_ok=True)
        elif path.suffix == '.sqlite3':
            to.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(f'file:{path.as_posix()}?mode=ro', uri=True) as read, sqlite3.connect(to) as write:
                read.backup(write)
            read.close()
            write.close()
        elif not path.name.endswith(('.sqlite3-wal', '.sqlite3-shm')):
            to.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, to)


def backup_project(project_id: str) -> Backup | None:
    """Save what a clear would remove, or nothing when the project holds nothing."""
    found = to_clear(project_id)
    if not found.metaforms and not found.reports:
        return None
    stamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
    _backups(project_id).mkdir(parents=True, exist_ok=True)
    name, number = stamp, 1
    while (_backups(project_id) / name).exists():
        number += 1
        name = f'{stamp}-{number}'
    kept = _backups(project_id) / name
    kept.mkdir()
    forms = metaforms(project_id)
    rows = {'metaforms': [{'metaform_id': form.metaform_id, 'name': form.name, 'created': form.created}
                          for form in forms],
            'active': next((form.metaform_id for form in forms if form.active), None), 'reports': found.reports}
    for part in ('metaforms', 'reports'):
        if (home() / 'projects' / project_id / part).is_dir():
            _copied(home() / 'projects' / project_id / part, kept / part)
        else:
            (kept / part).mkdir()
    (kept / 'rows.json').write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
    return Backup(project_id, name, found.metaforms, found.reports)


def backups(project_id: str) -> tuple[Backup, ...]:
    """The project's backups, the newest first."""
    found: list[Backup] = []
    folder = _backups(project_id)
    for kept in sorted((path for path in folder.iterdir() if (path / 'rows.json').is_file()),
                       key=lambda path: path.name, reverse=True) if folder.is_dir() else ():
        rows = json.loads((kept / 'rows.json').read_text(encoding='utf-8'))
        found.append(Backup(project_id, kept.name, tuple(row['name'] for row in rows['metaforms']),
                            int(rows.get('reports', 0))))
    return tuple(found)


@dataclass(frozen=True)
class Restored:
    """A backup brought back, and the backup of what the project held before, when it held anything."""
    backup: Backup
    held_before: str | None = None

    @property
    def said(self) -> str:
        return f'Restored {self.backup.project_id} from {self.backup.name}: {self.backup.held}.'

    def to_dict(self) -> dict[str, Any]:
        return {**self.backup.to_dict(), 'said': self.said, 'held_before': self.held_before}


def restore_project(project_id: str, name: str | None = None) -> Restored:
    """Bring a backup back, the newest when none is named. A project that holds metaforms or reports is cleared
    first, which backs up what it holds, so a restore loses nothing either, PROJ-030."""
    known = backups(project_id)
    chosen = next((one for one in known if name is None or one.name == name), None)
    if chosen is None:
        raise StoreError(f'No backup {name} of {project_id}.' if name else f'{project_id} has no backup.',
                         f'metaform list backups {project_id}')
    before = clear_project(project_id).backup
    kept = _backups(project_id) / chosen.name
    rows = json.loads((kept / 'rows.json').read_text(encoding='utf-8'))
    for part in ('metaforms', 'reports'):
        if any((kept / part).iterdir()):
            _copied(kept / part, home() / 'projects' / project_id / part)
    with base(write=True) as db:
        for row in rows['metaforms']:
            db.execute('INSERT INTO metaforms(metaform_id, project_id, name, created) VALUES (?, ?, ?, ?)',
                       (row['metaform_id'], project_id, row['name'], row['created']))
        if rows.get('active'):
            db.execute('INSERT INTO active_metaforms(project_id, metaform_id) VALUES (?, ?)',
                       (project_id, rows['active']))
    changes.note(project_id)
    return Restored(chosen, before)


def removal_caution(project_id: str) -> str:
    """What `remove project` does, said before it does, PROJ-031."""
    return (f'Removing {project_id} takes it off the list of projects and forgets the folder settings that select it. '
            'Its backups and history stay in the home, and its folder and files are not touched.')


def not_empty(project_id: str) -> str | None:
    """Why the project cannot be removed yet: it holds what a clear removes and backs up, PROJ-031. None when empty."""
    found = to_clear(project_id)
    if not found.metaforms and not found.reports:
        return None
    forms = counted(len(found.metaforms), 'metaform', 'metaforms') + (
        f', {listed(found.metaforms)},' if found.metaforms else '')
    return (f'{project_id} holds {forms} and {counted(found.reports, "report file", "report files")}. Only an empty '
            'project is removed; clearing it backs it up first.')


def remove_project(project_id: str) -> None:
    """Take an empty project off the list, PROJ-031: its registration and the folder settings that select it. Nothing
    in the home is deleted, so its backups can be restored if it is registered again."""
    with base(write=True) as db:
        db.execute('DELETE FROM active_metaforms WHERE project_id=?', (project_id,))
        db.execute('DELETE FROM metaforms WHERE project_id=?', (project_id,))
        db.execute("DELETE FROM settings WHERE key='project' AND value=?", (json.dumps(project_id),))
        db.execute('DELETE FROM projects WHERE project_id=?', (project_id,))
    changes.note(project_id)


def _remove_tree(path: Path, failed: list[tuple[str, str]]) -> None:
    """Remove a folder whole, noting each file and folder that could not be removed with the system's reason."""
    def noted(error: BaseException, name: str) -> None:
        if not isinstance(error, FileNotFoundError):
            reason = error.strerror if isinstance(error, OSError) and error.strerror else str(error)
            failed.append((str(Path(name)), reason))
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=lambda _function, name, error: noted(error, os.fsdecode(name)))
    else:
        shutil.rmtree(path, onerror=lambda _function, name, info: noted(info[1], os.fsdecode(name)))


def _innermost(failed: list[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    """Each path left on disk once: a folder is dropped when something inside it is named, since that is why it
    stayed."""
    paths = [Path(path) for path, _ in failed]
    kept: dict[str, str] = {}
    for path, reason in failed:
        if not any(Path(path) in other.parents for other in paths):
            kept.setdefault(path, reason)
    return tuple(kept.items())


def remove_store(path: Path) -> None:
    """Remove a store file, its WAL files and its folder when empty: only for a store this operation created."""
    for part in sorted(path.parent.glob(path.name + '*')):
        part.unlink(missing_ok=True)
    if path.parent.is_dir() and not any(path.parent.iterdir()):
        path.parent.rmdir()


def store_path(project_id: str, metaform_id: str) -> Path:
    """Where one metaform's store lives, STORE-003."""
    return home() / 'projects' / project_id / 'metaforms' / metaform_id / 'store.sqlite3'
