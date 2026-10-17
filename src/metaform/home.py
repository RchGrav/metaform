"""The Metaform home: the chassis database and one folder per project, STORE-001, STORE-002 and PROJ-026.

The chassis database, `metaform.sqlite3`, holds what belongs to no project: module state, what the installer set up,
and the settings of the global scope and of folders outside every project. No database lists the projects.
Each project is one folder under `projects/`, named by its source's path, holding `source.txt`, its own
`project.sqlite3` with its registration, bases and the settings of folders inside its source, one store per
base, and everything else of the project. A project is found by looking where its name says. Nothing is ever
written into a project's own source folder.

Modules use the home through its public names, BASE-004: `home`, `projects`, `project` and `Project`; `to_clear`,
`clear_project` and `Cleared`; `backups`, `restore_project`, `Backup` and `Restored`; `CARRIERS`; and `not_empty`,
`removal_caution` and `remove_project`. Everything else here is private to the chassis.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import stat
import sys
import threading
import uuid
from collections.abc import Callable, Generator, Iterable
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

file_lock, Held = sqlite.file_lock, sqlite.Held  # the lock between processes, for modules, which cannot import sqlite
CHASSIS_SCHEMA_VERSION = '3'  # 2 holds no project; 3 backfills installed harnesses, PROJ-026, MCP-028, STORE-029
CHASSIS_COMPATIBLE_FROM = '3'  # code at 2 would install harnesses without the records 3 backfilled, STORE-029
PROJECT_SCHEMA_VERSION = '2'  # a project's own project.sqlite3, PROJ-026; 2 names its bases, the change order of 2026-10-07
PROJECT_COMPATIBLE_FROM = '2'  # 2 renamed the tables and columns code at 1 reads, STORE-029
# A home made while work was handed by nonce keeps its `nonces` table; nothing reads or writes it now, BASE-050.
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
# The counter of item numbers at each address of a project, `data/numbers.py`: the last number taken there, so a number
# is never reused. A project database made before it is given the table on the first number taken, as with aliases.
NUMBERS = """CREATE TABLE IF NOT EXISTS numbers(
  address TEXT PRIMARY KEY,
  last    INTEGER NOT NULL
);
"""
CHASSIS_SCHEMA = """
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
# A project's own database: its registration, one row; its bases and the active one; and the settings of the
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
CREATE TABLE IF NOT EXISTS bases(
  id         TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(project_id),
  name       TEXT NOT NULL,
  created    TEXT NOT NULL,
  UNIQUE(project_id, name)
);
CREATE TABLE IF NOT EXISTS active_bases(
  project_id TEXT PRIMARY KEY REFERENCES projects(project_id),
  base_id    TEXT NOT NULL REFERENCES bases(id)
);
""" + NUMBERS

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


def chassis_path() -> Path:
    return home() / 'metaform.sqlite3'


def make_private() -> list[str]:
    """Keep the home its owner's alone, at the start of every command. A home that does not exist yet is made 0700;
    its databases are made 0600 as they are created (`sqlite.private`). A home made before this, with access for its
    group or other users, is tightened once: every folder and file in it loses its group and other bits, so folders
    are 0700 and files 0600 (0700 when executable), symbolic links inside it left as they are (a home that is itself
    reached through a link is tightened at the link's target), and `home_private` is recorded once the home is closed
    so a home loosened again on purpose is not walked again. Gives the paths it could not tighten, and records
    nothing then, so the next start tries again. On Windows the home keeps the access its parent folder gives it."""
    if os.name == 'nt':
        return []
    root = home()
    if not root.exists():
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        return []
    root = root.resolve()  # a home reached through a link: the link's target is tightened, never the link
    if not root.stat().st_mode & 0o077 or meta('home_private') is not None:
        return []
    failed: list[str] = []
    try:
        os.chmod(root, stat.S_IMODE(root.stat().st_mode) & ~0o077)
    except OSError:
        failed.append(str(root))
    for folder, _, files in os.walk(root):
        for path in (folder, *(os.path.join(folder, name) for name in files)):
            try:
                found = os.lstat(path)
                if not stat.S_ISLNK(found.st_mode) and found.st_mode & 0o077:
                    os.chmod(path, stat.S_IMODE(found.st_mode) & ~0o077)
            except OSError:
                failed.append(path)
    if not failed and not root.stat().st_mode & 0o077:  # a root still open is tried again at the next start
        set_meta('home_private', now())
    return failed


def is_home_path(path: Path) -> bool:
    """Whether a destination is inside the home, including a home reached through a symbolic link."""
    return path.resolve().is_relative_to(home().resolve())


def mkdir_private(path: Path) -> None:
    """Create missing home folders with owner-only access, including missing parents. Existing modes stay as set."""
    if not path.exists() and path.parent != path:
        mkdir_private(path.parent)
    path.mkdir(mode=0o700, exist_ok=True)


def write_private(path: Path, text: str | bytes) -> None:
    """Write a home file with owner-only access at creation. Windows keeps its inherited access."""
    if os.name == 'nt':
        if isinstance(text, str):
            path.write_text(text, encoding='utf-8')
        else:
            path.write_bytes(text)
        return
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'wb') as handle:
        handle.write(text.encode('utf-8') if isinstance(text, str) else text)


def now() -> str:
    """The current time as ISO 8601 UTC, to the second."""
    return datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')


IGNORE_FILE = '.metaform/ignore.txt'  # what the intake does not read, gitignore patterns


def ignore_patterns(project_path: Path | str) -> list[str]:
    """The patterns in the project's `.metaform/ignore.txt`, one per line, blank lines and `#` comments left out:
    the paths the intake never reads. Absent, none. Exclude was once a judgment the intake made on what it saw, and
    agents acted on it; now the person says up front what is not the project, as gitignore does."""
    try:
        lines = (Path(project_path) / IGNORE_FILE).read_text(encoding='utf-8').splitlines()
    except OSError:
        return []
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith('#')]


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
def _transaction(path: Path, schema: str, version: str, compatible: str, write: bool,
                 upgrade: sqlite.Upgrade | None = None) -> Generator[sqlite3.Connection, None, None]:
    with sqlite.opened(path, schema, write=write, version=version, compatible=compatible, upgrade=upgrade) as db:
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
def chassis(write: bool = False) -> Generator[sqlite3.Connection, None, None]:
    """One transaction on the chassis database. A read of a home with no chassis database creates nothing."""
    with _transaction(chassis_path(), CHASSIS_SCHEMA, CHASSIS_SCHEMA_VERSION, CHASSIS_COMPATIBLE_FROM, write,
                      _upgrade_chassis) as db:
        yield db


def _upgrade_chassis(db: sqlite3.Connection, path: Path, found: str) -> None:
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
            sqlite.stamp(db, CHASSIS_SCHEMA_VERSION, CHASSIS_COMPATIBLE_FROM)
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
    with _transaction(folder / PROJECT_DB, PROJECT_SCHEMA, PROJECT_SCHEMA_VERSION, PROJECT_COMPATIBLE_FROM, write,
                      _upgrade_project) as db:
        yield db


def _upgrade_project(db: sqlite3.Connection, path: Path, found: str) -> None:
    """Version 1 named a project's bases metaforms; version 2 names them bases with `id` as their own identifier, so
    one concept has one name across the stores, the change order of 2026-10-07 item 1."""
    if found != '1':
        raise StoreError(f'{path} has schema version {found}; this Metaform updates only project version 1.',
                         'install the Metaform release that wrote it')
    db.execute('BEGIN IMMEDIATE')
    try:
        if db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone() == ('1',) and db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='metaforms'").fetchone():
            db.execute('ALTER TABLE metaforms RENAME TO bases')
            db.execute('ALTER TABLE bases RENAME COLUMN metaform_id TO id')
            db.execute('ALTER TABLE active_metaforms RENAME TO active_bases')
            db.execute('ALTER TABLE active_bases RENAME COLUMN metaform_id TO base_id')
        # The layer the intake writes is named base now; a folder's layers setting that named it as intake names it
        # as base, so what was in view stays in view, STORE-046.
        db.execute("UPDATE settings SET value='\"base\"' WHERE key='layers' AND value='\"intake\"'")
        sqlite.stamp(db, PROJECT_SCHEMA_VERSION, PROJECT_COMPATIBLE_FROM)
        db.execute('COMMIT')
    except BaseException:
        db.execute('ROLLBACK')
        raise


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
    """Write a project's folder, registration and retained source with immutable provenance, PROJ-026. A folder
    named for the source that holds no registration, one whose project was removed, is taken again, so what it
    kept is the project's again. The source folder itself need not exist here, as when an export is imported. The id
    is held to the rule `add_project` holds a typed one to, whoever registers it, since it names files."""
    if not PROJECT_ID.fullmatch(record.project_id):
        raise StoreError(f'{record.project_id!r} is not a project id: use lowercase letters, digits, - and _.',
                         'metaform list projects')
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
    created = folder is None
    if folder is None:
        numbers = [int(one.name.rsplit('-', 1)[1]) for one in taken]
        folder = projects_dir() / f'{folder_name(record.path)}-{(max(numbers) if numbers else 0) + 1:03d}'
        mkdir_private(projects_dir())
        folder.mkdir(mode=0o700)
        write_private(folder / SOURCE, record.path + '\n')
    registered = now()
    with project_db(folder, write=True) as db:
        db.execute('INSERT INTO projects(project_id, path, path_key, target_type, target_value, registered) '
                   'VALUES (?, ?, ?, ?, ?, ?)',
                   (record.project_id, record.path, key, record.target_type, record.target_value, registered))
    provenance = folder / '.metaform' / 'provenance.json'
    try:
        if not provenance.exists() and Path(record.path).is_dir():
            from .data import history
            history.capture_registration(record.project_id, registered)
    except BaseException:
        # A failed capture is not a registered project. Keep any data a removed project left behind.
        with project_db(folder, write=True) as db:
            db.execute('DELETE FROM projects WHERE project_id=?', (record.project_id,))
        if created:
            shutil.rmtree(folder)
        raise
    changes.note(record.project_id)
    return folder


@_cached
def project_at(path: str) -> str | None:
    """The project registered with this folder. Its project folder is remembered for its id too, so finding the same
    project by id next opens no other project's database, STORE-005."""
    folder = _folder_at(path)
    record = _record_in(folder) if folder is not None else None
    if record is not None and folder is not None:
        _FOUND[(str(projects_dir()), record.project_id)] = folder
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


def project_id_for(folder: Path) -> str:
    """A project id made from a folder's name: lowercase, every run of other characters one -, MCP-009. The MCP
    register tool and `metaform start` name a project with it, so neither asks."""
    made = re.sub(r'[^a-z0-9_-]+', '-', Path(folder).name.lower()).strip('-_')[:64]
    return made if made and PROJECT_ID.fullmatch(made) else 'project'


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
        with chassis(write=write) as db:
            yield db
    else:
        with project_db(folder, write=write) as db:
            yield db


def preload_settings(scopes: Iterable[str], pairs: Iterable[tuple[str, str]]) -> None:
    """Read every value and glue stored at these scopes with one query each, into the registry's cache, as `stored`
    and `glued` would read them one setting at a time; a pair with nothing stored is cached as nothing. A screen that
    describes every setting then opens each scope's database once, not once for each setting and scope. Only inside a
    registry scope, whose cache ends with it."""
    active = _REGISTRY_SCOPE.get()
    if active is None or not active.active:
        return
    pairs = list(pairs)
    for scope in dict.fromkeys(scopes):
        with settings_db(scope) as db:
            rows = db.execute('SELECT owner, key, value FROM settings WHERE scope=? ORDER BY owner, key, position',
                              (scope,)).fetchall()
            glues = {(owner, key) for owner, key in db.execute('SELECT owner, key FROM glue WHERE scope=?', (scope,))}
        found: dict[tuple[str, str], list[Any]] = {}
        for owner, key, value in rows:
            found.setdefault((owner, key), []).append(json.loads(value))
        for pair in pairs:
            stored_here, glued_here = found.get(pair), pair in glues
            registry_cached(('stored', (scope, *pair), ()), lambda value=stored_here: value)
            registry_cached(('glued', (scope, *pair), ()), lambda value=glued_here: value)


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
    _settings_changed(scope, owner)  # a glue changes what the screens show, so an open one reads again


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
    with chassis() as db:
        row = db.execute('SELECT enabled FROM module_state WHERE module_id=?', (module_id,)).fetchone()
    return None if row is None else bool(row[0])


def set_module_state(module_id: str, enabled: bool | None) -> None:
    with chassis(write=True) as db:
        if enabled is None:
            db.execute('DELETE FROM module_state WHERE module_id=?', (module_id,))
        else:
            db.execute('INSERT INTO module_state(module_id, enabled) VALUES (?, ?) '
                       'ON CONFLICT(module_id) DO UPDATE SET enabled=excluded.enabled', (module_id, int(enabled)))


# Meta values ------------------------------------------------------------------

def meta(key: str) -> str | None:
    with chassis() as db:
        row = db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
    return None if row is None else str(row[0])


def set_meta(key: str, value: str) -> None:
    with chassis(write=True) as db:
        db.execute('INSERT INTO meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                   (key, value))


# Bases, in each project's own database, STORE-041 and PROJ-026 ----------------------------------------------

@dataclass(frozen=True)
class Base:
    """One of a project's bases: the object with a store of its own, of which one is active, STORE-041."""
    id: str
    project_id: str
    name: str
    created: str
    active: bool
    notices: tuple[Any, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_ACTIVE = ('SELECT m.id, m.name, m.created FROM active_bases a '
           'JOIN bases m ON m.id = a.base_id WHERE a.project_id=?')


@contextmanager
def _bases_db(project_id: str, write: bool = False) -> Generator[sqlite3.Connection, None, None]:
    with project_db(_folder_of_project(project_id), write=write) as db:
        yield db


def bases(project_id: str) -> tuple[Base, ...]:
    folder = project_folder(project_id)
    if folder is None:
        return ()
    with project_db(folder) as db:
        active = db.execute('SELECT base_id FROM active_bases WHERE project_id=?', (project_id,)).fetchone()
        rows = db.execute('SELECT id, name, created FROM bases WHERE project_id=? ORDER BY rowid',
                          (project_id,)).fetchall()
    return tuple(Base(row[0], project_id, row[1], row[2], active is not None and row[0] == active[0])
                 for row in rows)


def _read_only(path: Path) -> sqlite3.Connection:
    """A read-only connection to a database file. The path goes in as a proper file URI, so a home under a folder
    whose name holds `#`, `?` or `%` opens the file named rather than another one, which SQLite would create."""
    return sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)


def intake_exists() -> bool:
    """Whether any base store of any project in the home holds an intake, finished or not, MCP-028. Read only;
    a store that cannot be read is passed over."""
    root = projects_dir()
    for path in sorted(root.glob(f'*/*{STORE_SUFFIX}')) if root.is_dir() else ():
        try:
            with closing(_read_only(path)) as db:
                if db.execute("SELECT 1 FROM ops WHERE kind='layer' AND op='add' AND "
                              "json_extract(data, '$.kind') IN ('base', 'intake') LIMIT 1").fetchone():
                    return True
        except sqlite3.Error:
            continue
    return False


@_cached
def active_base(project_id: str) -> Base | None:
    folder = project_folder(project_id)
    if folder is None:
        return None
    with project_db(folder) as db:
        row = db.execute(_ACTIVE, (project_id,)).fetchone()
    return None if row is None else Base(row[0], project_id, row[1], row[2], True)


def ensure_base(project_id: str) -> Base:
    """The active base, creating `main` on the first write to a project that has none, STORE-041."""
    current = active_base(project_id)
    if current is not None:
        return current
    with _bases_db(project_id, write=True) as db:
        row = db.execute(_ACTIVE, (project_id,)).fetchone()
        if row is not None:
            return Base(row[0], project_id, row[1], row[2], True)
        return _create_base(db, project_id, 'main')


def _create_base(db: sqlite3.Connection, project_id: str, name: str, base_id: str | None = None,
                     created: str | None = None, activate: bool = True) -> Base:
    record = Base(base_id or uuid.uuid4().hex, project_id, name, created or now(), activate)
    db.execute('INSERT INTO bases(id, project_id, name, created) VALUES (?, ?, ?, ?)',
               (record.id, project_id, name, record.created))
    if activate:
        db.execute('INSERT INTO active_bases(project_id, base_id) VALUES (?, ?) '
                   'ON CONFLICT(project_id) DO UPDATE SET base_id=excluded.base_id',
                   (project_id, record.id))
    changes.note(project_id)  # the project's bases changed; announced when the command ends, VIEW-018
    return record


def add_base(project_id: str, name: str, *, activate: bool = True) -> Base:
    """A new, empty base for the project, made active unless asked not to; the old one is kept whole, STORE-041.

    A name the project already has is stored with `-2`, or the next free number, added; the caller compares the
    returned name with the one it asked for to say so, BASE-044.
    """
    if not NAME.fullmatch(name) or ID.fullmatch(name):
        raise StoreError(f'{name!r} is not a base name: use letters, digits, ., _ and -.',
                         'metaform map add-base <name>')
    with _bases_db(project_id, write=True) as db:
        chosen, number = name, 1
        while db.execute('SELECT 1 FROM bases WHERE project_id=? AND name=?', (project_id, chosen)).fetchone():
            number += 1
            chosen = f'{name}-{number}'
        if db.execute('SELECT 1 FROM active_bases WHERE project_id=?', (project_id,)).fetchone() is None:
            _create_base(db, project_id, 'main')
        return _create_base(db, project_id, chosen, activate=activate)


@_cached
def base_by_id(project_id: str, base_id: str) -> Base | None:
    folder = project_folder(project_id)
    if folder is None:
        return None
    with project_db(folder) as db:
        row = db.execute('SELECT id, name, created FROM bases WHERE id=? AND project_id=?',
                         (base_id, project_id)).fetchone()
        active = db.execute('SELECT base_id FROM active_bases WHERE project_id=?', (project_id,)).fetchone()
    if row is None:
        return None
    return Base(row[0], project_id, row[1], row[2], active is not None and active[0] == row[0])


def withdraw_base(project_id: str, base_id: str) -> None:
    """Undo a base created in this operation whose first write failed: its row and its store file go."""
    path = store_path(project_id, base_id)
    with _bases_db(project_id, write=True) as db:
        db.execute('DELETE FROM active_bases WHERE project_id=? AND base_id=?', (project_id, base_id))
        db.execute('DELETE FROM bases WHERE id=? AND project_id=?', (base_id, project_id))
    remove_store(path)
    changes.note(project_id)


@dataclass(frozen=True)
class Removed:
    """A base taken out of a project, with the copy of its store kept, STORE-041."""
    project_id: str
    name: str
    base_id: str
    kept: str
    notices: tuple[Any, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def __str__(self) -> str:
        return f'Removed base {self.name} from {self.project_id}; its store is kept at {self.kept}'


def remove_base(project_id: str, name: str) -> Removed:
    """Take one base out of a project: its row goes, and its store file goes after a copy is kept under
    `backups/remove-base/<project>/<stamp>/`. The active base is refused: activate another first. A project's bases
    are never removed any other way but clearing the project, STORE-041. What a module keeps of the project outside
    the map, the conversations with its agents, is carried out of the store first, `CARRIERS`."""
    carry_out(project_id)
    with _bases_db(project_id, write=True) as db:
        row = db.execute('SELECT id FROM bases WHERE project_id=? AND name=?', (project_id, name)).fetchone()
        if row is None:
            raise StoreError(f'No base {name} in {project_id}.', 'metaform list bases')
        active = db.execute('SELECT base_id FROM active_bases WHERE project_id=?', (project_id,)).fetchone()
        if active is not None and active[0] == row[0]:
            raise StoreError(f'{name} is the active base of {project_id}; it is not removed while it is active.',
                             'metaform activate base <another>')
        base_id = str(row[0])
        path = store_path(project_id, base_id)
        kept = home() / 'backups' / 'remove-base' / project_id / now().replace(':', '').replace('-', '')
        mkdir_private(kept)
        if path.exists():
            sqlite.private(kept / path.name)
            copy = sqlite3.connect(kept / path.name)
            try:
                with closing(sqlite3.connect(path)) as source:
                    source.backup(copy)
            finally:
                copy.close()
        db.execute('DELETE FROM bases WHERE id=? AND project_id=?', (base_id, project_id))
    remove_store(path)
    changes.note(project_id)
    return Removed(project_id, name, base_id, str(kept / path.name))


def activate_base(project_id: str, name: str) -> Base:
    with _bases_db(project_id, write=True) as db:
        row = db.execute('SELECT id, created FROM bases WHERE project_id=? AND name=?',
                         (project_id, name)).fetchone()
        if row is None:
            raise StoreError(f'No base {name} in {project_id}.', 'metaform list bases')
        db.execute('INSERT INTO active_bases(project_id, base_id) VALUES (?, ?) '
                   'ON CONFLICT(project_id) DO UPDATE SET base_id=excluded.base_id', (project_id, row[0]))
    changes.note(project_id)
    return Base(row[0], project_id, name, row[1], True)


def import_base(project_id: str, base_id: str, name: str, created: str, *, activate: bool) -> bool:
    """Record an imported base unless its id exists. Returns whether it was added, STORE-027."""
    with _bases_db(project_id, write=True) as db:
        return import_base_in(db, project_id, base_id, name, created, activate=activate)


def import_base_in(db: sqlite3.Connection, project_id: str, base_id: str, name: str, created: str, *,
                       activate: bool) -> bool:
    """Record an imported base inside an open transaction on its project's database, unless its id exists. It
    becomes active when asked, or when its project has no active base."""
    if db.execute('SELECT 1 FROM bases WHERE id=?', (base_id,)).fetchone() is not None:
        return False
    has_active = db.execute('SELECT 1 FROM active_bases WHERE project_id=?', (project_id,)).fetchone()
    _create_base(db, project_id, name, base_id, created,
                     activate=activate or has_active is None)
    return True


def base_owner(base_id: str) -> str | None:
    """The project a base id belongs to in this home, if any."""
    for folder, record in _registered():
        with project_db(folder) as db:
            if db.execute('SELECT 1 FROM bases WHERE id=?', (base_id,)).fetchone() is not None:
                return record.project_id
    return None


# What a module keeps of a project that is not its map and must not go with a base's store: each module's function
# carrying what the project's base stores still hold of it into the module's project-level store, which no clear,
# restore or removal of a base touches, STORE-045. Run before a clear or the removal of a base takes stores away and
# after a restore brings stores back, so nothing of it is lost and a restored backup's is merged with what was said
# since. Dispatch carries the conversations with agents this way, PROJ-026. A module registers its own under its id.
CARRIERS: dict[str, Callable[[str], None]] = {}


def carry_out(project_id: str) -> None:
    """Run every module's carrier on the project; the first that fails raises."""
    for carrier in list(CARRIERS.values()):
        carrier(project_id)


KEPT = 'Its registration, folder, settings, origins, variants and conversations with agents stay.'


@dataclass(frozen=True)
class Cleared:
    """What clearing a project removed, PROJ-025, and each path it could not remove with the system's reason."""
    project_id: str
    bases: tuple[str, ...]
    reports: int
    not_removed: tuple[tuple[str, str], ...] = ()
    backup: str | None = None  # the backup made before anything was removed, PROJ-030

    def to_dict(self) -> dict[str, Any]:
        found: dict[str, Any] = {'project': self.project_id, 'bases': list(self.bases),
                                 'reports': self.reports}
        if self.backup:
            found['backup'] = self.backup
            found['restore'] = self.restore
        if self.not_removed:
            found['not_removed'] = [{'path': path, 'reason': reason} for path, reason in self.not_removed]
        return found

    def _bases(self, stores: bool) -> str:
        """The metaforms by name, and with their stores when `stores`; a clause set off by commas when named."""
        count = len(self.bases)
        if not count:
            return counted(0, 'base', 'bases')
        held = (' with its store,' if count == 1 else ' with their stores,') if stores else ''
        return f'{counted(count, "base", "bases")}, {listed(self.bases)},{held}'

    @property
    def caution(self) -> str:
        """What `clear project` removes, said before it does."""
        return (f'Clearing {self.project_id} removes {self._bases(True)} and '
                f'{counted(self.reports, "report file", "report files")}. {KEPT}')

    @property
    def said(self) -> str:
        """What `clear project` removed, said after it did."""
        return (f'Cleared {self.project_id}: {self._bases(False)} and '
                f'{counted(self.reports, "report file", "report files")}. {KEPT}')

    @property
    def restore(self) -> str:
        """The one command that brings back what the clear removed."""
        return f'metaform restore project {self.project_id}'

    @property
    def held(self) -> str:
        """What the project held, as a backup and a restore say it."""
        return f'{self._bases(False)} and {counted(self.reports, "report file", "report files")}'

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
    """What `clear project` would remove: the project's bases by name, in creation order, and its report files."""
    names = tuple(form.name for form in bases(project_id))
    folder = project_folder(project_id)
    reports = folder / 'reports' if folder is not None else None
    count = sum(1 for path in reports.iterdir() if path.is_file()) if reports is not None and reports.is_dir() else 0
    return Cleared(project_id, names, count)


def clear_project(project_id: str) -> Cleared:
    """Remove every base of the project with its store and its report files, PROJ-025.

    The registration, the settings, the history, the conversations with agents and everything else in the project's
    folder stay, PROJ-026. The rows go whatever happens to the files; a file or folder that cannot be removed is named
    in the result.
    """
    found = to_clear(project_id)
    # What the stores still hold that is not the map, a conversation written there before it had a store of its own,
    # is carried out first, and nothing goes when it cannot be: a clear starts the map again and nothing else, PROJ-026.
    try:
        carry_out(project_id)
    except (OSError, sqlite3.Error, Stop) as error:
        reason = error.strerror if isinstance(error, OSError) and error.strerror else str(error)
        raise StoreError(f'{project_id} was not cleared, since the conversations with its agents could not be kept '
                         f'first: {reason}.', 'metaform dispatch sessions thread=false') from error
    # It is backed up before anything goes, and nothing goes when it cannot be: what a clear removes cannot be made
    # again by an intake, and a clear without its backup is a loss the person learns of when they need it, PROJ-030.
    try:
        saved = backup_project(project_id)
    except (OSError, sqlite3.Error) as error:
        reason = error.strerror if isinstance(error, OSError) and error.strerror else str(error)
        raise StoreError(f'{project_id} was not cleared, since it could not be backed up first: {reason}.',
                         'metaform list backups') from error
    folder = _folder_of_project(project_id)
    stores = _stores(folder)
    with project_db(folder, write=True) as db:
        db.execute('DELETE FROM active_bases WHERE project_id=?', (project_id,))
        db.execute('DELETE FROM bases WHERE project_id=?', (project_id,))
    failed: list[tuple[str, str]] = []
    for store in stores:
        _remove_files(store, failed)
    _remove_tree(folder / 'reports', failed)
    changes.note(project_id)
    return Cleared(found.project_id, found.bases, found.reports, _innermost(failed),
                   saved.name if saved is not None else None)


@dataclass(frozen=True)
class Backup:
    """What a project held when it was cleared, kept so it can be brought back, PROJ-030."""
    project_id: str
    name: str
    bases: tuple[str, ...]
    reports: int

    @property
    def held(self) -> str:
        return Cleared(self.project_id, self.bases, self.reports).held

    def to_dict(self) -> dict[str, Any]:
        return {'project': self.project_id, 'name': self.name, 'bases': list(self.bases),
                'reports': self.reports, 'held': self.held}


def _backups(project_id: str) -> Path:
    return home() / 'backups' / 'clear' / project_id


def _copied(source: Path, target: Path) -> None:
    """A folder copied whole. A store is copied through SQLite's own backup, so one another program holds open is
    copied as it stands, with what its write-ahead log holds."""
    for path in sorted(source.rglob('*')):
        to = target / path.relative_to(source)
        if path.is_dir():
            mkdir_private(to)
        elif path.suffix == '.sqlite3':
            mkdir_private(to.parent)
            sqlite.private(to)
            # closed on the way out whatever happens; a connection's `with` only commits, it never closes
            with closing(_read_only(path)) as read, \
                    closing(sqlite3.connect(to)) as write:
                read.backup(write)
        elif not path.name.endswith(('.sqlite3-wal', '.sqlite3-shm')):
            mkdir_private(to.parent)
            write_private(to, path.read_bytes())
            found = path.stat()
            if os.name == 'nt':
                shutil.copystat(path, to)
            else:
                to.chmod(stat.S_IMODE(found.st_mode) & ~0o077)
                os.utime(to, ns=(found.st_atime_ns, found.st_mtime_ns))


def backup_project(project_id: str) -> Backup | None:
    """Save what a clear would remove, or nothing when the project holds nothing."""
    found = to_clear(project_id)
    if not found.bases and not found.reports:
        return None
    stamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
    mkdir_private(_backups(project_id))
    name, number = stamp, 1
    while (_backups(project_id) / name).exists():
        number += 1
        name = f'{stamp}-{number}'
    kept = _backups(project_id) / name
    kept.mkdir(mode=0o700)
    forms = bases(project_id)
    rows = {'bases': [{'id': form.id, 'name': form.name, 'created': form.created}
                          for form in forms],
            'active': next((form.id for form in forms if form.active), None), 'reports': found.reports}
    folder = _folder_of_project(project_id)
    try:
        (kept / 'stores').mkdir(mode=0o700)
        for store in _stores(folder):
            try:
                _copied_store(store, kept / 'stores' / store.name)
            except sqlite3.Error as error:  # named, since SQLite's own message does not say which file it read
                raise sqlite3.DatabaseError(f'{store} cannot be read ({error})') from error
        if (folder / 'reports').is_dir():
            _copied(folder / 'reports', kept / 'reports')
        else:
            (kept / 'reports').mkdir(mode=0o700)
        if (folder / 'modules').is_dir():  # the modules' project-level stores, which a clear keeps, STORE-045
            _copied(folder / 'modules', kept / 'modules')
        write_private(kept / 'rows.json', json.dumps(rows, indent=2) + '\n')
    except BaseException:
        # This call made the folder and it holds no whole backup: none lists or restores it, so it would only be
        # clutter beside the real backups.
        shutil.rmtree(kept, ignore_errors=True)
        raise
    return Backup(project_id, name, found.bases, found.reports)


def backups(project_id: str) -> tuple[Backup, ...]:
    """The project's backups, the newest first."""
    found: list[Backup] = []
    folder = _backups(project_id)
    for kept in sorted((path for path in folder.iterdir() if (path / 'rows.json').is_file()),
                       key=lambda path: path.name, reverse=True) if folder.is_dir() else ():
        rows = json.loads((kept / 'rows.json').read_text(encoding='utf-8'))
        found.append(Backup(project_id, kept.name, tuple(row['name'] for row in rows.get('bases', rows.get('metaforms', ()))),
                            int(rows.get('reports', 0))))
    return tuple(found)


@dataclass(frozen=True)
class Restored:
    """A backup brought back, and the backup of what the project held before, when it held anything."""
    backup: Backup
    held_before: str | None = None

    @property
    def said(self) -> str:
        return (f'Restored {self.backup.project_id} from {self.backup.name}: {self.backup.held}. The conversations '
                'with agents were kept, with everything said since the backup.')

    def to_dict(self) -> dict[str, Any]:
        return {**self.backup.to_dict(), 'said': self.said, 'held_before': self.held_before}


def restore_project(project_id: str, name: str | None = None) -> Restored:
    """Bring a backup back, the newest when none is named. A project that holds metaforms or reports is cleared
    first, which backs up what it holds, so a restore loses nothing either, PROJ-030. The conversations with agents
    are never in what a clear removes, so what was said since the backup stays, and what the backup's stores still
    hold of them, kept there before they had a store of their own, is carried into it with them, `CARRIERS`."""
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
        for row in rows.get('bases', rows.get('metaforms', ())):  # a backup made before the rename says metaforms
            db.execute('INSERT INTO bases(id, project_id, name, created) VALUES (?, ?, ?, ?)',
                       (row.get('id') or row['metaform_id'], project_id, row['name'], row['created']))
        if rows.get('active'):
            db.execute('INSERT INTO active_bases(project_id, base_id) VALUES (?, ?)',
                       (project_id, rows['active']))
    changes.note(project_id)
    try:
        carry_out(project_id)
    except (OSError, sqlite3.Error, Stop):
        pass  # the restore stands; what the backup's stores hold of them is still there, carried by the next read
    return Restored(chosen, before)


def removal_caution(project_id: str) -> str:
    """What `remove project` does, said before it does, PROJ-031."""
    return (f'Removing {project_id} takes it off the list of projects and forgets the folder settings that select it. '
            "Its folder, history and backups stay in the home, and its source's folder and files are not touched.")


def _holds_records(path: Path) -> bool:
    """Whether a metaform's store holds anything a clear would lose: a row in any table but its meta. A read of a
    cleared project makes its default metaform again, empty, and that holds nothing."""
    if not path.is_file():
        return False
    try:
        with closing(_read_only(path)) as db:
            tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name <> 'meta' "
                                                   "AND name NOT LIKE 'sqlite_%'")]
            return any(db.execute(f'SELECT 1 FROM "{table}" LIMIT 1').fetchone() for table in tables)
    except sqlite3.Error:
        return True  # what cannot be read is kept, so a clear backs it up first


def not_empty(project_id: str) -> str | None:
    """Why the project cannot be removed yet: it holds what a clear removes and backs up, PROJ-031. None when empty: a
    metaform that holds nothing, as a read after a clear makes again, does not count."""
    found = to_clear(project_id)
    held = tuple(name for name in found.bases if _holds_records(store_file(project_id, name)))
    if not held and not found.reports:
        return None
    forms = counted(len(held), 'base', 'bases') + (f', {listed(held)},' if held else '')
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
    with chassis(write=True) as db:
        db.execute("DELETE FROM settings WHERE key='project' AND value=?", (selecting,))
    for other, _ in _registered():
        with project_db(other, write=True) as db:
            db.execute("DELETE FROM settings WHERE key='project' AND value=?", (selecting,))
    with project_db(folder, write=True) as db:
        db.execute('DELETE FROM active_bases WHERE project_id=?', (project_id,))
        db.execute('DELETE FROM bases WHERE project_id=?', (project_id,))
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
    mkdir_private(target.parent)
    sqlite.private(target)
    with closing(_read_only(source)) as read, \
            closing(sqlite3.connect(target)) as write:  # closed whatever happens; `with` on a connection never closes
        read.backup(write)


def store_file(project_id: str, name: str) -> Path:
    """Where the store of the project's metaform with this name lives: `<name>.metaform.sqlite3` in its folder,
    STORE-003 and PROJ-026."""
    return _folder_of_project(project_id) / f'{name}{STORE_SUFFIX}'


def store_path(project_id: str, base_id: str) -> Path:
    """Where one metaform's store lives, found by its id, STORE-003."""
    found = base_by_id(project_id, base_id)
    if found is None:
        raise StoreError(f'No base {base_id} in {project_id}.', 'metaform list bases')
    return store_file(project_id, found.name)
