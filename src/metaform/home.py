"""The Metaform home: the chassis database and one folder per project, STORE-001, STORE-002 and PROJ-026.

The chassis database, `metaform.sqlite3`, holds what belongs to no project: module state, what the installer set up,
nonces, and the settings of the global scope and of folders outside every project. No database lists the projects.
Each project is one folder under `projects/`, named by its source's path, holding `source.txt`, its own
`project.sqlite3` with its registration, metaforms and the settings of folders inside its source, one store per
metaform, and everything else of the project. A project is found by looking where its name says. Nothing is ever
written into a project's own source folder.

Modules use the home through its public names, BASE-004: `home`, `projects`, `project` and `Project`; `to_clear`,
`clear_project` and `Cleared`; `backups`, `restore_project`, `Backup` and `Restored`; and `not_empty`,
`removal_caution` and `remove_project`. Everything else here is private to the chassis.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import sys
import threading
import uuid
from collections.abc import Callable, Generator
from contextlib import closing, contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from typing import Any, ParamSpec, TypeVar, cast

from . import changes, sqlite
from .errors import Stop, StoreError
from .wording import counted, listed

BASE_SCHEMA_VERSION = '3'  # 2 holds no project; 3 backfills installed harnesses, PROJ-026, MCP-028, STORE-029
PROJECT_SCHEMA_VERSION = '1'  # a project's own project.sqlite3, PROJ-026
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
_SETTINGS_TABLES = """
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
"""
# The aliases of each folder, CLI-039: one row per module an alias stands for, beside the folder's row. A database made
# before aliases existed is given the table on the first alias written to it.
ALIASES = """CREATE TABLE IF NOT EXISTS aliases(
  path_key TEXT NOT NULL,
  name     TEXT NOT NULL,
  position INTEGER NOT NULL,
  module   TEXT NOT NULL,
  PRIMARY KEY(path_key, name, position)
);
"""
SETTINGS_SCHEMA = _SETTINGS_TABLES + ALIASES
BASE_SCHEMA = NONCES + """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
""" + SETTINGS_SCHEMA + """
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
"""
# A project's own database: its registration, one row; its metaforms and the active one; and the settings of the
# folders inside its source, PROJ-026. The tables keep the chassis database's earlier form, STORE-002 and STORE-041.
PROJECT_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS projects(
  project_id   TEXT PRIMARY KEY,
  path         TEXT NOT NULL,
  path_key     TEXT NOT NULL UNIQUE,
  target_type  TEXT NOT NULL DEFAULT 'path'
               CHECK(target_type IN ('path','url','artifact','inline','inferred')),
  target_value TEXT NOT NULL,
  registered   TEXT NOT NULL
);
""" + SETTINGS_SCHEMA + """
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
SOURCE = 'source.txt'  # the source's resolved path, the truth behind a project folder's name, PROJ-026
PROJECT_DB = 'project.sqlite3'
STORE_SUFFIX = '.metaform.sqlite3'  # a metaform's store is <metaform name>.metaform.sqlite3, STORE-003


def home() -> Path:
    """The Metaform home: METAFORM_HOME when set, otherwise ~/.metaform, STORE-001."""
    return Path(os.environ.get('METAFORM_HOME') or Path.home() / '.metaform').expanduser()


def base_path() -> Path:
    return home() / 'metaform.sqlite3'


def now() -> str:
    """The current time as ISO 8601 UTC, to the second."""
    return datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')


def path_key(path: Path | str) -> str:
    """The comparison key of a folder: resolved and case-folded where the system folds case."""
    return os.path.normcase(str(Path(path).expanduser().resolve()))


@dataclass
class _Registry:
    root: Path
    stamp: tuple[Any, ...]
    values: dict[tuple[Any, ...], Any] = field(default_factory=dict[tuple[Any, ...], Any])
    generation: int = 0
    invalidation: int = 0


@dataclass
class _RegistryScope:
    registry: _Registry
    active: bool = True


_REGISTRIES: dict[Path, _Registry] = {}
_REGISTRY_INVALIDATIONS: dict[Path, int] = {}
_REGISTRY_LOCK = threading.RLock()
_REGISTRY_SCOPE: ContextVar[_RegistryScope | None] = ContextVar('metaform_registry', default=None)
_P = ParamSpec('_P')
_R = TypeVar('_R')


def _file_stamp(path: Path) -> tuple[int, ...] | None:
    try:
        stat = path.stat()
        return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns
    except OSError:
        return None


def _registry_stamp(root: Path) -> tuple[Any, ...]:
    # WAL commits need not touch the database file. Include the WAL and source
    # identities so external commits, replacements and project additions invalidate.
    projects = root / 'projects'
    try:
        folders = sorted(folder for folder in projects.iterdir() if folder.is_dir())
    except OSError:
        folders = []
    paths = [root / 'metaform.sqlite3', root / 'metaform.sqlite3-wal', projects]
    for folder in folders:
        paths.extend((folder / SOURCE, folder / PROJECT_DB, folder / (PROJECT_DB + '-wal')))
    return tuple((str(path), _file_stamp(path)) for path in paths)


def in_registry_scope() -> bool:
    state = _REGISTRY_SCOPE.get()
    return state is not None and state.active and state.registry.root == home().resolve()


def registry_revision() -> tuple[Path, int]:
    """The local commit revision, including home identity, for request-level module refresh."""
    root = home().resolve()
    with _REGISTRY_LOCK:
        return root, _REGISTRY_INVALIDATIONS.get(root, 0)


@contextmanager
def registry_scope(*, fresh: bool = False) -> Generator[None, None, None]:
    """Validate the process registry once per request, sharing nested lookups.

    A fresh scope starts a new request inside a long-lived CLI service. Committed
    local writes invalidate immediately, while other processes are seen at the
    next outer request through the file and WAL stamps.
    """
    root = home().resolve()
    active = _REGISTRY_SCOPE.get()
    if not fresh and active is not None and active.active and active.registry.root == root:
        yield
        return
    with _REGISTRY_LOCK:
        stamp = _registry_stamp(root)
        state = _REGISTRIES.get(root)
        if state is None or state.stamp != stamp:
            state = _Registry(root, stamp, invalidation=_REGISTRY_INVALIDATIONS.get(root, 0))
            _REGISTRIES[root] = state
    scope = _RegistryScope(state)
    token = _REGISTRY_SCOPE.set(scope)
    try:
        yield
    finally:
        scope.active = False
        _REGISTRY_SCOPE.reset(token)


def registry_cached(key: tuple[Any, ...], compute: Callable[[], _R]) -> _R:
    with registry_scope():
        scope = _REGISTRY_SCOPE.get()
        assert scope is not None
        state = scope.registry
        with _REGISTRY_LOCK:
            invalidation = _REGISTRY_INVALIDATIONS.get(state.root, 0)
            if state.invalidation != invalidation:
                # A fresh concurrent request may have replaced the process cache.
                # Local commits also invalidate scopes still using its older instance.
                state.values.clear()
                state.generation += 1
                state.invalidation = invalidation
            found = key in state.values
            generation = state.generation
            value: Any = state.values.get(key)
        if not found:
            # Do not hold the registry lock while opening SQLite: a write holds
            # its file lock and invalidates the registry after committing.
            value = compute()
            with _REGISTRY_LOCK:
                if generation == state.generation and invalidation == _REGISTRY_INVALIDATIONS.get(state.root, 0):
                    state.values[key] = value
        # A caller may edit a returned setting list without editing the registry.
        return cast(_R, deepcopy(value) if type(value) in (dict, list) else value)


def _cached(function: Callable[_P, _R]) -> Callable[_P, _R]:
    @wraps(function)
    def read(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        return registry_cached((function.__name__, args, tuple(sorted(kwargs.items()))),
                               lambda: function(*args, **kwargs))
    return read


def _invalidate_registry() -> None:
    with _REGISTRY_LOCK:
        root = home().resolve()
        _REGISTRY_INVALIDATIONS[root] = _REGISTRY_INVALIDATIONS.get(root, 0) + 1
        state = _REGISTRIES.pop(root, None)
        if state is not None:
            state.values.clear()
            state.generation += 1
        scope = _REGISTRY_SCOPE.get()
        if scope is not None and scope.registry.root == root and scope.registry is not state:
            scope.registry.values.clear()
            scope.registry.generation += 1


@contextmanager
def _transaction(path: Path, schema: str, version: str, write: bool,
                 upgrade: sqlite.Upgrade | None = None) -> Generator[sqlite3.Connection, None, None]:
    with sqlite.opened(path, schema, write=write, version=version, upgrade=upgrade) as db:
        db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        try:
            yield db
        except BaseException:
            db.execute('ROLLBACK')
            raise
        db.execute('COMMIT')
        if write:
            _invalidate_registry()


@contextmanager
def base(write: bool = False) -> Generator[sqlite3.Connection, None, None]:
    """One transaction on the chassis database. A read of a home with no chassis database creates nothing."""
    with _transaction(base_path(), BASE_SCHEMA, BASE_SCHEMA_VERSION, write, _upgrade_base) as db:
        yield db


def _upgrade_base(db: sqlite3.Connection, path: Path, found: str) -> None:
    """Record earlier installations once, so installed harnesses never see the provisioning notice, MCP-028."""
    if found != '2':
        raise StoreError(f'{path} has schema version {found}; this Metaform updates only base version 2.',
                         'install the Metaform release that wrote it')
    from . import harness, install

    db.execute('BEGIN IMMEDIATE')
    try:
        # Another process may have upgraded while this connection waited for its write lock.
        if db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone() == ('2',):
            db.execute(harness.HARNESSES)
            tools = install.tools()
            for name, source, installed in db.execute('SELECT tool, source, installed FROM installs ORDER BY tool'):
                tool = tools.get(name)
                if not source or tool is None or tool.merge or tool.add is None:
                    continue
                # Only the host executable matters here. Discovery would reopen this home's upgrade.
                binary = shutil.which(tool.add(['metaform'])[0])
                if binary is not None and (key := harness.key(binary)) is not None:
                    db.execute('INSERT OR IGNORE INTO harnesses(path_key, binary, done) VALUES (?, ?, ?)',
                               (key, binary, installed))
            db.execute("UPDATE meta SET value=? WHERE key='schema_version'", (BASE_SCHEMA_VERSION,))
        db.execute('COMMIT')
    except BaseException:
        db.execute('ROLLBACK')
        raise


# Project folders, PROJ-026 ------------------------------------------------------------------------------------

def projects_dir() -> Path:
    return home() / 'projects'


def folder_name(path: Path | str) -> str:
    """A source's folder name without its number: its path as the system compares it, every character that is not
    a letter or a digit replaced by `-`, PROJ-026."""
    return re.sub(r'[^A-Za-z0-9]', '-', path_key(path))


def _numbered(path: Path | str) -> list[Path]:
    """The folders under `projects/` named for this path, in number order."""
    root = projects_dir()
    if not root.is_dir():
        return []
    return sorted(found for found in root.glob(f'{folder_name(path)}-[0-9][0-9][0-9]') if found.is_dir())


def _source_of(folder: Path) -> str | None:
    try:
        return (folder / SOURCE).read_text(encoding='utf-8').strip() or None
    except OSError:
        return None


@contextmanager
def project_db(folder: Path, write: bool = False) -> Generator[sqlite3.Connection, None, None]:
    """One transaction on a project folder's own database, PROJ-026."""
    with _transaction(folder / PROJECT_DB, PROJECT_SCHEMA, PROJECT_SCHEMA_VERSION, write) as db:
        yield db


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


@_cached
def _record_in(folder: Path) -> Project | None:
    """The registration a project folder holds, or None when it holds none."""
    if not (folder / PROJECT_DB).is_file():
        return None
    with project_db(folder) as db:
        row = db.execute('SELECT project_id, path, target_type, target_value FROM projects').fetchone()
    return None if row is None else _project(row)


def _registered() -> list[tuple[Path, Project]]:
    """Every project folder of the home with its registration, in folder order: the list of projects is the folders."""
    root = projects_dir()
    found: list[tuple[Path, Project]] = []
    for folder in sorted(root.iterdir()) if root.is_dir() else ():
        record = _record_in(folder) if folder.is_dir() else None
        if record is not None:
            found.append((folder, record))
    return found


def _folder_at(path: Path | str) -> Path | None:
    """The project folder registered for exactly this source path: named for it, and its `source.txt` names it."""
    key = path_key(path)
    for folder in _numbered(path):
        source = _source_of(folder)
        if source is not None and path_key(source) == key and _record_in(folder) is not None:
            return folder
    return None


_FOUND: dict[tuple[str, str], Path] = {}  # (the home's projects folder, a project id): the folder last found for it


@_cached
def _registration(project_id: str) -> tuple[Path, Project] | None:
    """A registered project's folder with its registration. The folder last found for the id is asked first, so
    finding one project opens its own database and no other's; when that folder no longer holds the project, every
    folder is asked again."""
    key = (str(projects_dir()), project_id)
    known = _FOUND.get(key)
    record = _record_in(known) if known is not None else None
    if known is not None and record is not None and record.project_id == project_id:
        return known, record
    found = next(((folder, held) for folder, held in _registered() if held.project_id == project_id), None)
    if found is None:
        _FOUND.pop(key, None)
    else:
        _FOUND[key] = found[0]
    return found


def project_folder(project_id: str) -> Path | None:
    """The folder of a registered project, PROJ-026."""
    found = _registration(project_id)
    return None if found is None else found[0]


def _folder_of_project(project_id: str) -> Path:
    folder = project_folder(project_id)
    if folder is None:
        raise StoreError(f'No project {project_id} is registered.', 'metaform list projects')
    return folder


def projects() -> tuple[Project, ...]:
    return tuple(sorted((record for _, record in _registered()), key=lambda record: record.project_id))


def project(project_id: str) -> Project | None:
    found = _registration(project_id)
    return None if found is None else found[1]


def add_project(project_id: str, path: Path | str, target_type: str | None = None,
                target_value: str | None = None) -> str:
    """Register a project, STORE-031, in a folder of its own named by its source's path, PROJ-026."""
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
    existing = project(project_id)
    if existing is not None:
        if existing == record:
            return f'Project {project_id} is already registered.'
        raise StoreError(f'Project {project_id} is registered with another folder or target.',
                         'metaform list projects')
    register(record)
    return f'Added project {project_id}: {folder} (target {target_type} {target_value})'


def register(record: Project) -> Path:
    """Write a project's folder: `source.txt`, its registration and, once, its provenance, PROJ-026. A folder
    named for the source that holds no registration, one whose project was removed, is taken again, so what it
    kept is the project's again. The source folder itself need not exist here, as when an export is imported."""
    holder = _folder_at(record.path)
    if holder is not None:
        held = _record_in(holder)
        if held is not None and held.project_id != record.project_id:
            raise StoreError(f'{record.path} is already registered as project {held.project_id}.',
                             'metaform list projects')
        return holder
    if project(record.project_id) is not None:
        raise StoreError(f'Project {record.project_id} is registered with another folder.', 'metaform list projects')
    key = path_key(record.path)
    taken = _numbered(record.path)
    folder = next((one for one in taken if (_source_of(one) or '') and path_key(_source_of(one) or '') == key), None)
    if folder is None:
        numbers = [int(one.name.rsplit('-', 1)[1]) for one in taken]
        folder = projects_dir() / f'{folder_name(record.path)}-{(max(numbers) if numbers else 0) + 1:03d}'
        folder.mkdir(parents=True)
        (folder / SOURCE).write_text(record.path + '\n', encoding='utf-8')
    registered = now()
    with project_db(folder, write=True) as db:
        db.execute('INSERT INTO projects(project_id, path, path_key, target_type, target_value, registered) '
                   'VALUES (?, ?, ?, ?, ?, ?)',
                   (record.project_id, record.path, key, record.target_type, record.target_value, registered))
    provenance = folder / '.metaform' / 'provenance.json'
    if not provenance.exists():  # written once and never changed, PROJ-026
        from . import __version__
        provenance.parent.mkdir(exist_ok=True)
        provenance.write_text(json.dumps({'source': record.path, 'registered': registered,
                                          'metaform': __version__}, indent=2) + '\n', encoding='utf-8')
    changes.note(record.project_id)
    return folder


@_cached
def project_at(path: str) -> str | None:
    """The project registered with this folder."""
    folder = _folder_at(path)
    record = _record_in(folder) if folder is not None else None
    return None if record is None else record.project_id


@_cached
def folder_project(folder: Path) -> str | None:
    """The project whose source holds this folder: the folder's own project folder, else its nearest parent's,
    found on the file system alone, PROJ-026."""
    start = Path(folder).expanduser().resolve()
    for candidate in (start, *start.parents):
        found = project_at(str(candidate))
        if found is not None:
            return found
    return None


# Settings ---------------------------------------------------------------------
# A setting of a folder inside a project's source is the project's own, kept in its project.sqlite3; the global
# scope and folders outside every project are the chassis's, PROJ-026.

@_cached
def _project_holding(scope: str) -> Path | None:
    if scope == 'global':
        return None
    found = folder_project(Path(scope))
    return project_folder(found) if found is not None else None


@contextmanager
def settings_db(scope: str, write: bool = False) -> Generator[sqlite3.Connection, None, None]:
    """The database that holds a scope's settings: the project's own for a folder inside its source, else the
    chassis's."""
    folder = _project_holding(scope)
    if folder is None:
        with base(write=write) as db:
            yield db
    else:
        with project_db(folder, write=write) as db:
            yield db


@_cached
def stored(scope: str, owner: str, key: str) -> list[Any] | None:
    """The stored member values of a setting at one scope, in order, or None when nothing is stored."""
    with settings_db(scope) as db:
        rows = db.execute('SELECT value FROM settings WHERE scope=? AND owner=? AND key=? ORDER BY position',
                          (scope, owner, key)).fetchall()
    return [json.loads(row[0]) for row in rows] if rows else None


def save(scope: str, owner: str, key: str, members: list[Any], *, folder: Path | None = None) -> None:
    """Store a setting as one row per member, replacing what was stored. A folder row is written with it."""
    with settings_db(scope, write=True) as db:
        if folder is not None:
            db.execute('INSERT OR IGNORE INTO folders(path_key, path) VALUES (?, ?)', (scope, str(folder)))
        db.execute('DELETE FROM settings WHERE scope=? AND owner=? AND key=?', (scope, owner, key))
        db.executemany('INSERT INTO settings(scope, owner, key, position, value) VALUES (?, ?, ?, ?, ?)',
                       [(scope, owner, key, position, json.dumps(member)) for position, member in enumerate(members)])
    _settings_changed(scope, owner)


def clear(scope: str, owner: str, key: str) -> None:
    with settings_db(scope, write=True) as db:
        db.execute('DELETE FROM settings WHERE scope=? AND owner=? AND key=?', (scope, owner, key))
    _settings_changed(scope, owner)


def _settings_changed(scope: str, owner: str) -> None:
    """Notify related projects after a setting commits, including global and inherited ancestor scopes.

    The owner names its settings in the event. The chassis treats every module alike, BASE-046.
    """
    for record in projects():
        project_path = Path(path_key(record.path))
        if scope == 'global' or project_path.is_relative_to(scope) or Path(scope).is_relative_to(project_path):
            changes.note(record.project_id, tables={f'{owner}.settings'})


@_cached
def glued(scope: str, owner: str, key: str) -> bool:
    with settings_db(scope) as db:
        return db.execute('SELECT 1 FROM glue WHERE scope=? AND owner=? AND key=?',
                          (scope, owner, key)).fetchone() is not None


def set_glue(scope: str, owner: str, key: str, on: bool, *, folder: Path | None = None) -> None:
    with settings_db(scope, write=True) as db:
        if on:
            if folder is not None:
                db.execute('INSERT OR IGNORE INTO folders(path_key, path) VALUES (?, ?)', (scope, str(folder)))
            db.execute('INSERT OR IGNORE INTO glue(scope, owner, key) VALUES (?, ?, ?)', (scope, owner, key))
        else:
            db.execute('DELETE FROM glue WHERE scope=? AND owner=? AND key=?', (scope, owner, key))


def aliases_at(scope: str) -> dict[str, list[str]]:
    """The aliases defined at one folder, each with the modules it stands for in order, CLI-039."""
    with settings_db(scope) as db:
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='aliases'").fetchone() is None:
            return {}
        rows = db.execute('SELECT name, module FROM aliases WHERE path_key=? ORDER BY name, position',
                          (scope,)).fetchall()
    found: dict[str, list[str]] = {}
    for name, module in rows:
        found.setdefault(name, []).append(module)
    return found


def save_alias(folder: Path, name: str, modules: list[str]) -> None:
    """Define an alias at a folder, replacing what the name stood for there. The folder row is written with it."""
    scope = path_key(folder)
    with settings_db(scope, write=True) as db:
        db.execute(ALIASES)
        db.execute('INSERT OR IGNORE INTO folders(path_key, path) VALUES (?, ?)', (scope, str(folder)))
        db.execute('DELETE FROM aliases WHERE path_key=? AND name=?', (scope, name))
        db.executemany('INSERT INTO aliases(path_key, name, position, module) VALUES (?, ?, ?, ?)',
                       [(scope, name, position, module) for position, module in enumerate(modules)])


# Module state -----------------------------------------------------------------

@_cached
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


# Metaforms, in each project's own database, STORE-041 and PROJ-026 ----------------------------------------------

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


@contextmanager
def _metaforms_db(project_id: str, write: bool = False) -> Generator[sqlite3.Connection, None, None]:
    with project_db(_folder_of_project(project_id), write=write) as db:
        yield db


def metaforms(project_id: str) -> tuple[Metaform, ...]:
    folder = project_folder(project_id)
    if folder is None:
        return ()
    with project_db(folder) as db:
        active = db.execute('SELECT metaform_id FROM active_metaforms WHERE project_id=?', (project_id,)).fetchone()
        rows = db.execute('SELECT metaform_id, name, created FROM metaforms WHERE project_id=? ORDER BY rowid',
                          (project_id,)).fetchall()
    return tuple(Metaform(row[0], project_id, row[1], row[2], active is not None and row[0] == active[0])
                 for row in rows)


def intake_exists() -> bool:
    """Whether any metaform store of any project in the home holds an intake, finished or not, MCP-028. Read only;
    a store that cannot be read is passed over."""
    root = projects_dir()
    for path in sorted(root.glob(f'*/*{STORE_SUFFIX}')) if root.is_dir() else ():
        try:
            with closing(sqlite3.connect(f'file:{path.as_posix()}?mode=ro', uri=True)) as db:
                if db.execute("SELECT 1 FROM layers WHERE kind='intake' LIMIT 1").fetchone():
                    return True
        except sqlite3.Error:
            continue
    return False


@_cached
def active_metaform(project_id: str) -> Metaform | None:
    folder = project_folder(project_id)
    if folder is None:
        return None
    with project_db(folder) as db:
        row = db.execute(_ACTIVE, (project_id,)).fetchone()
    return None if row is None else Metaform(row[0], project_id, row[1], row[2], True)


def ensure_metaform(project_id: str) -> Metaform:
    """The active metaform, creating `main` on the first write to a project that has none, STORE-041."""
    current = active_metaform(project_id)
    if current is not None:
        return current
    with _metaforms_db(project_id, write=True) as db:
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
    with _metaforms_db(project_id, write=True) as db:
        chosen, number = name, 1
        while db.execute('SELECT 1 FROM metaforms WHERE project_id=? AND name=?', (project_id, chosen)).fetchone():
            number += 1
            chosen = f'{name}-{number}'
        if db.execute('SELECT 1 FROM active_metaforms WHERE project_id=?', (project_id,)).fetchone() is None:
            _create_metaform(db, project_id, 'main')
        return _create_metaform(db, project_id, chosen, activate=activate)


@_cached
def metaform_by_id(project_id: str, metaform_id: str) -> Metaform | None:
    folder = project_folder(project_id)
    if folder is None:
        return None
    with project_db(folder) as db:
        row = db.execute('SELECT metaform_id, name, created FROM metaforms WHERE metaform_id=? AND project_id=?',
                         (metaform_id, project_id)).fetchone()
        active = db.execute('SELECT metaform_id FROM active_metaforms WHERE project_id=?', (project_id,)).fetchone()
    if row is None:
        return None
    return Metaform(row[0], project_id, row[1], row[2], active is not None and active[0] == row[0])


def withdraw_metaform(project_id: str, metaform_id: str) -> None:
    """Undo a metaform created in this operation whose first write failed: its row and its store file go."""
    path = store_path(project_id, metaform_id)
    with _metaforms_db(project_id, write=True) as db:
        db.execute('DELETE FROM active_metaforms WHERE project_id=? AND metaform_id=?', (project_id, metaform_id))
        db.execute('DELETE FROM metaforms WHERE metaform_id=? AND project_id=?', (metaform_id, project_id))
    remove_store(path)
    changes.note(project_id)


def activate_metaform(project_id: str, name: str) -> Metaform:
    with _metaforms_db(project_id, write=True) as db:
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
    with _metaforms_db(project_id, write=True) as db:
        return import_metaform_in(db, project_id, metaform_id, name, created, activate=activate)


def import_metaform_in(db: sqlite3.Connection, project_id: str, metaform_id: str, name: str, created: str, *,
                       activate: bool) -> bool:
    """Record an imported metaform inside an open transaction on its project's database, unless its id exists. It
    becomes active when asked, or when its project has no active metaform."""
    if db.execute('SELECT 1 FROM metaforms WHERE metaform_id=?', (metaform_id,)).fetchone() is not None:
        return False
    has_active = db.execute('SELECT 1 FROM active_metaforms WHERE project_id=?', (project_id,)).fetchone()
    _create_metaform(db, project_id, name, metaform_id, created,
                     activate=activate or has_active is None)
    return True


def metaform_owner(metaform_id: str) -> str | None:
    """The project a metaform id belongs to in this home, if any."""
    for folder, record in _registered():
        with project_db(folder) as db:
            if db.execute('SELECT 1 FROM metaforms WHERE metaform_id=?', (metaform_id,)).fetchone() is not None:
                return record.project_id
    return None


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
    folder = project_folder(project_id)
    reports = folder / 'reports' if folder is not None else None
    count = sum(1 for path in reports.iterdir() if path.is_file()) if reports is not None and reports.is_dir() else 0
    return Cleared(project_id, names, count)


def clear_project(project_id: str) -> Cleared:
    """Remove every metaform of the project with its store, and its report files, PROJ-025.

    The registration, the settings, the history and everything else in the project's folder stay, PROJ-026. The
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
    folder = _folder_of_project(project_id)
    stores = _stores(folder)
    with project_db(folder, write=True) as db:
        db.execute('DELETE FROM active_metaforms WHERE project_id=?', (project_id,))
        db.execute('DELETE FROM metaforms WHERE project_id=?', (project_id,))
    failed: list[tuple[str, str]] = []
    for store in stores:
        _remove_files(store, failed)
    _remove_tree(folder / 'reports', failed)
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
    folder = _folder_of_project(project_id)
    (kept / 'stores').mkdir()
    for store in _stores(folder):
        _copied_store(store, kept / 'stores' / store.name)
    if (folder / 'reports').is_dir():
        _copied(folder / 'reports', kept / 'reports')
    else:
        (kept / 'reports').mkdir()
    if (folder / 'modules').is_dir():  # the modules' project-level stores, which a clear keeps, STORE-045
        _copied(folder / 'modules', kept / 'modules')
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
    folder = _folder_of_project(project_id)
    for store in sorted((kept / 'stores').glob('*' + STORE_SUFFIX)) if (kept / 'stores').is_dir() else ():
        _copied_store(store, folder / store.name)
    if (kept / 'reports').is_dir() and any((kept / 'reports').iterdir()):
        _copied(kept / 'reports', folder / 'reports')
    with project_db(folder, write=True) as db:
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
            "Its folder, history and backups stay in the home, and its source's folder and files are not touched.")


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
    in its folder is deleted, so registering its source again takes the folder back with what it kept, PROJ-026. A
    project that holds what a clear removes is refused; the caller asks for confirmation first."""
    held = not_empty(project_id)
    if held:
        raise Stop(held, f'metaform clear project {project_id} --confirm')
    forget_project(project_id)


def forget_project(project_id: str) -> None:
    """Delete a project's registration and the folder settings that select it, whatever it holds. Only the chassis
    calls it, to undo a registration it made itself; modules remove a project with `remove_project`."""
    folder = _folder_of_project(project_id)
    selecting = json.dumps(project_id)
    with base(write=True) as db:
        db.execute("DELETE FROM settings WHERE key='project' AND value=?", (selecting,))
    for other, _ in _registered():
        with project_db(other, write=True) as db:
            db.execute("DELETE FROM settings WHERE key='project' AND value=?", (selecting,))
    with project_db(folder, write=True) as db:
        db.execute('DELETE FROM active_metaforms WHERE project_id=?', (project_id,))
        db.execute('DELETE FROM metaforms WHERE project_id=?', (project_id,))
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
    """Remove a store file and its WAL files: only for a store this operation created."""
    sqlite.reset_reads(path)
    for part in sorted(path.parent.glob(path.name + '*')):
        part.unlink(missing_ok=True)


def _stores(folder: Path) -> list[Path]:
    """A project folder's metaform stores."""
    return sorted(folder.glob('*' + STORE_SUFFIX))


def _remove_files(store: Path, failed: list[tuple[str, str]]) -> None:
    """A store and its WAL files, noting each that could not be removed with the system's reason."""
    sqlite.reset_reads(store)
    for part in sorted(store.parent.glob(store.name + '*')):
        try:
            part.unlink()
        except FileNotFoundError:
            pass
        except OSError as error:
            failed.append((str(part), error.strerror or str(error)))


def _copied_store(source: Path, target: Path) -> None:
    """A store copied through SQLite's own backup, so one another program holds open is copied as it stands."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f'file:{source.as_posix()}?mode=ro', uri=True) as read, sqlite3.connect(target) as write:
        read.backup(write)
    read.close()
    write.close()


def store_file(project_id: str, name: str) -> Path:
    """Where the store of the project's metaform with this name lives: `<name>.metaform.sqlite3` in its folder,
    STORE-003 and PROJ-026."""
    return _folder_of_project(project_id) / f'{name}{STORE_SUFFIX}'


def store_path(project_id: str, metaform_id: str) -> Path:
    """Where one metaform's store lives, found by its id, STORE-003."""
    found = metaform_by_id(project_id, metaform_id)
    if found is None:
        raise StoreError(f'No metaform {metaform_id} in {project_id}.', 'metaform list metaforms')
    return store_file(project_id, found.name)
