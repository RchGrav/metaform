"""A project's history: its artifact boundary, origins and variants, and reconstruction, PROJ-010 to PROJ-024.

An origin is the baseline a history starts from: a repository's commit, whose
files git keeps, or a full copy of a plain folder. A variant is one piece of
work against an origin, stored as the files that differ from it: whole when
the variant's changed text is small, as a diff against the origin's file when
it is large, binaries always whole. Every variant is stored against its
origin, never against another variant, so each reconstructs on its own with
Python alone. The rows live in the project's history database and the
payloads under the home's `origins/<mform_sha_id>/`, Q53 and PROJ-023.
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
from collections.abc import Generator, Iterable, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from .. import home, sqlite
from ..errors import StoreError
from .records import Record

HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS origins(
  mform_sha_id  TEXT PRIMARY KEY,
  mform_id      TEXT NOT NULL UNIQUE,
  origin_sha256 TEXT NOT NULL,
  suffix        TEXT NOT NULL,
  kind          TEXT NOT NULL CHECK(kind IN ('repo','folder')),
  commit_id     TEXT,
  source_path   TEXT NOT NULL,
  established   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS origins_by_digest ON origins(origin_sha256);
CREATE TABLE IF NOT EXISTS variants(
  mform_sha_id TEXT NOT NULL REFERENCES origins(mform_sha_id),
  variant_id   TEXT NOT NULL,
  collected    TEXT NOT NULL,
  source_path  TEXT NOT NULL,
  module TEXT, workflow TEXT, prompt TEXT, model TEXT, role TEXT, blinded INTEGER,
  PRIMARY KEY(mform_sha_id, variant_id)
);
CREATE TABLE IF NOT EXISTS variant_files(
  mform_sha_id TEXT NOT NULL,
  variant_id   TEXT NOT NULL,
  path         TEXT NOT NULL,
  change       TEXT NOT NULL CHECK(change IN ('added','modified','removed')),
  storage      TEXT CHECK(storage IN ('whole','diff')),
  sha256       TEXT,
  mode         TEXT,
  PRIMARY KEY(mform_sha_id, variant_id, path),
  FOREIGN KEY(mform_sha_id, variant_id) REFERENCES variants(mform_sha_id, variant_id)
);
"""
WHOLE_LIMIT = 3 * 1024 * 1024  # changed text under this, in total, is kept whole; at or over it, as diffs, PROJ-016
PROVENANCE = ('module', 'workflow', 'prompt', 'model', 'role', 'blinded')


@dataclass(frozen=True)
class Entry:
    """One file of a boundary: its path from the boundary's root, with `/` separators, and its mode."""
    path: str
    mode: str
    file: Path


@dataclass(frozen=True)
class Origin(Record):
    mform_id: str
    mform_sha_id: str
    origin_sha256: str
    suffix: str
    kind: str
    commit_id: str | None
    source_path: str
    established: str
    variants: int = 0


@dataclass(frozen=True)
class VariantFile(Record):
    path: str
    change: str
    storage: str | None
    sha256: str | None
    mode: str | None


@dataclass(frozen=True)
class Variant(Record):
    variant_id: str
    mform_id: str
    collected: str
    source_path: str
    module: str | None = None
    workflow: str | None = None
    prompt: str | None = None
    model: str | None = None
    role: str | None = None
    blinded: bool | None = None
    files: tuple[VariantFile, ...] = field(default=())


# ---------------------------------------------------------------- the boundary, PROJ-011

def _git(folder: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(['git', '-C', str(folder), *args], capture_output=True, check=check)
    except FileNotFoundError:
        raise StoreError('git is not installed, and this folder is a repository.', 'install git') from None


def repository(folder: Path) -> Path | None:
    """The repository the folder is in, or None for a plain folder or when git is missing."""
    try:
        found = subprocess.run(['git', '-C', str(folder), 'rev-parse', '--show-toplevel'], capture_output=True)
    except FileNotFoundError:
        return None
    return Path(found.stdout.decode('utf-8').strip()) if found.returncode == 0 else None


def _mode(path: Path) -> str:
    return '755' if os.stat(path).st_mode & 0o111 else '644'


def boundary(folder: Path) -> list[Entry]:
    """The files of the artifact at the folder: what git tracks or would offer to track in a repository, every file
    of a plain folder; never a `.git` folder. A tracked file's mode is git's, so it is the same on every system."""
    entries: list[Entry] = []
    if repository(folder) is not None:
        listed = _git(folder, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').stdout
        tracked: dict[str, str] = {}
        for record in _git(folder, 'ls-files', '-z', '-s').stdout.split(b'\0'):
            if record:
                info, _, path = record.partition(b'\t')
                tracked[path.decode('utf-8')] = '755' if info.split()[0] == b'100755' else '644'
        for raw in sorted(set(listed.split(b'\0'))):
            path = raw.decode('utf-8')
            file = folder / path
            if path and file.is_file() and '.git' not in Path(path).parts:
                entries.append(Entry(path, tracked.get(path) or _mode(file), file))
        return sorted(entries, key=lambda entry: entry.path)
    for root, folders, files in os.walk(folder):
        folders[:] = sorted(name for name in folders if name != '.git')
        for name in files:
            file = Path(root) / name
            if file.is_file():
                entries.append(Entry(file.relative_to(folder).as_posix(), _mode(file), file))
    return sorted(entries, key=lambda entry: entry.path)


# ---------------------------------------------------------------- identity, PROJ-013

def manifest(files: dict[str, tuple[bytes, str]]) -> bytes:
    """Each file, sorted by path: `<path>\\t<sha256 of the bytes>\\t<mode>\\n`, as UTF-8."""
    return ''.join(f'{path}\t{_sha(data)}\t{mode}\n' for path, (data, mode) in sorted(files.items())).encode('utf-8')


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def origins_folder() -> Path:
    return home.home() / 'origins'


def _unit(mform_sha_id: str) -> Path:
    return origins_folder() / mform_sha_id


# ---------------------------------------------------------------- the history database, Q53

@contextmanager
def _db(project_id: str, *, write: bool = False) -> Generator[sqlite3.Connection, None, None]:
    path = home.home() / 'projects' / project_id / 'history.sqlite3'
    # Connections to the file are opened one at a time in this process, and a write holds its turn to the end of
    # its transaction, STORE-006; a read lets go once its connection is prepared, so it never waits on a writer.
    lock = sqlite.writer_lock(path)
    lock.acquire()
    held = True
    try:
        if not write and not path.exists():
            db = sqlite.memory(HISTORY_SCHEMA)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite.connect(path)
            try:
                sqlite.prepare(db, path, HISTORY_SCHEMA, create=write)
            except BaseException:
                db.close()
                raise
        if not write:
            lock.release()
            held = False
        db.row_factory = sqlite3.Row
        try:
            db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            try:
                yield db
            except BaseException:
                db.execute('ROLLBACK')
                raise
            db.execute('COMMIT')
        finally:
            db.close()
    finally:
        if held:
            lock.release()


def _origin(row: sqlite3.Row, count: int = 0) -> Origin:
    return Origin(row['mform_id'], row['mform_sha_id'], row['origin_sha256'], row['suffix'], row['kind'],
                  row['commit_id'], row['source_path'], row['established'], count)


def origins(project_id: str) -> tuple[Origin, ...]:
    """The project's origins, in the order they were established."""
    with _db(project_id) as db:
        rows = db.execute('SELECT o.*, (SELECT COUNT(*) FROM variants v WHERE v.mform_sha_id = o.mform_sha_id) AS n '
                          'FROM origins o ORDER BY established, rowid').fetchall()
        return tuple(_origin(row, int(row['n'])) for row in rows)


def origin(project_id: str, mform_id: str | None = None) -> Origin:
    """One origin by its short id, or the project's selected origin: the one established last, PROJ-014."""
    found = origins(project_id)
    if mform_id is None:
        if not found:
            raise StoreError(f'Project {project_id} has no origin yet.', 'metaform add origin')
        return found[-1]
    for item in found:
        if mform_id in (item.mform_id, item.mform_sha_id):
            return item
    raise StoreError(f'Project {project_id} has no origin {mform_id}.', f'metaform list origins {project_id}')


# ---------------------------------------------------------------- origins, PROJ-012 and PROJ-014

def _committed(folder: Path, commit: str) -> dict[str, tuple[bytes, str]]:
    """A commit's files under the folder, read from git, as paths from the folder."""
    top = repository(folder)
    assert top is not None
    relative = Path(os.path.relpath(folder.resolve(), top.resolve())).as_posix()
    tree = commit if relative == '.' else f'{commit}:{relative}'
    archive = _git(folder, 'archive', '--format=tar', tree).stdout
    files: dict[str, tuple[bytes, str]] = {}
    with tarfile.open(fileobj=BytesIO(archive)) as tar:
        for member in tar.getmembers():
            if member.isfile():
                handle = tar.extractfile(member)
                assert handle is not None
                files[member.name] = (handle.read(), '755' if member.mode & 0o111 else '644')
    return files


def _read(entries: Iterable[Entry]) -> dict[str, tuple[bytes, str]]:
    return {entry.path: (entry.file.read_bytes(), entry.mode) for entry in entries}


def origin_files(item: Origin) -> dict[str, tuple[bytes, str]]:
    """The origin's files: from git for a repository origin, from the unit's copy for a folder origin."""
    if item.kind == 'repo':
        assert item.commit_id is not None
        return _committed(Path(item.source_path), item.commit_id)
    copy = _unit(item.mform_sha_id) / 'origin'
    modes = _modes(_unit(item.mform_sha_id) / 'manifest.txt')
    return {path: ((copy / path).read_bytes(), modes.get(path, '644')) for path in modes}


def _modes(manifest_file: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in manifest_file.read_text(encoding='utf-8').splitlines():
        path, _, mode = line.split('\t')
        found[path] = mode
    return found


def add_origin(project_id: str) -> Origin:
    """Establish an origin from the project's current state; an origin of the same content is reported, not made
    again. A repository's uncommitted work is collected at once as the unit's first variant, PROJ-012."""
    record = home.project(project_id)
    if record is None:
        raise StoreError(f'No project {project_id} is registered.', 'metaform list projects')
    folder = Path(record.path)
    commit = None
    if repository(folder) is not None:
        commit = _git(folder, 'rev-parse', 'HEAD').stdout.decode('utf-8').strip()
        files = _committed(folder, commit)
    else:
        files = _read(boundary(folder))
    listing = manifest(files)
    digest = _sha(listing)
    staging = origins_folder() / f'.staging-{secrets.token_hex(8)}'
    staging.mkdir(parents=True)
    made: Origin | None = None
    try:
        (staging / 'manifest.txt').write_bytes(listing)
        if commit is None:
            for path, (data, mode) in files.items():
                _write(staging / 'origin' / path, data, mode)
        # One writer at a time for the project, so an origin of the same content found here is not made twice.
        with _db(project_id, write=True) as db:
            same = db.execute('SELECT * FROM origins WHERE origin_sha256=? ORDER BY established DESC LIMIT 1',
                              (digest,)).fetchone()
            if same is not None:
                return _origin(same)
            for number in range(0x10000):
                suffix = f'{number:04x}'
                unit = _unit(digest[:60] + suffix)
                if unit.exists():
                    continue
                try:
                    os.replace(staging, unit)
                except OSError:
                    if unit.exists():  # another project's origin of the same content took this suffix meanwhile
                        continue
                    raise
                made = Origin(digest[:12] + suffix, digest[:60] + suffix, digest, suffix,
                              'repo' if commit else 'folder', commit, str(folder), home.now())
                break
            if made is None:
                raise StoreError(f'Every suffix of origin {digest[:12]} is taken.', 'metaform list origins')
            db.execute('INSERT INTO origins(mform_sha_id, mform_id, origin_sha256, suffix, kind, commit_id, '
                       'source_path, established) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                       (made.mform_sha_id, made.mform_id, digest, made.suffix, made.kind, commit, made.source_path,
                        made.established))
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    if commit is not None and _dirty(folder):
        add_variant(project_id, folder, made.mform_id)
    return made


def _dirty(folder: Path) -> bool:
    """Whether git sees uncommitted work under the folder, by its own rules for line endings and attributes, so a
    file git calls unchanged never makes a first variant, PROJ-012."""
    return bool(_git(folder, 'status', '--porcelain', '--', '.').stdout.strip())


# ---------------------------------------------------------------- variants, PROJ-015 to PROJ-017 and PROJ-023

def _text(data: bytes) -> bool:
    """Text is UTF-8 with no NUL byte, PROJ-016."""
    if b'\0' in data:
        return False
    try:
        data.decode('utf-8')
    except UnicodeDecodeError:
        return False
    return True


def _changes(old: dict[str, tuple[bytes, str]], new: dict[str, tuple[bytes, str]]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in sorted(set(old) | set(new)):
        if path not in old:
            found.append((path, 'added'))
        elif path not in new:
            found.append((path, 'removed'))
        elif old[path] != new[path]:
            found.append((path, 'modified'))
    return found


def _write(path: Path, data: bytes, mode: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if os.name != 'nt':
        path.chmod(0o755 if mode == '755' else 0o644)


def _diff(before: bytes, after: bytes) -> bytes:
    """The unified diff of one file, made by git whether or not the source is a repository, PROJ-016."""
    with tempfile.TemporaryDirectory() as scratch:
        old, new = Path(scratch) / 'a', Path(scratch) / 'b'
        old.write_bytes(before)
        new.write_bytes(after)
        made = subprocess.run(['git', 'diff', '--no-index', '--no-color', '--no-ext-diff', '--full-index', str(old),
                               str(new)], capture_output=True)
    if made.returncode not in (0, 1):
        raise StoreError(f'git diff failed: {made.stderr.decode("utf-8", "replace").strip()}', 'install git')
    return made.stdout


def add_variant(project_id: str, folder: Path, mform_id: str | None = None, *, remove: bool = False,
                provenance: dict[str, object] | None = None) -> Variant:
    """Collect a folder as a variant of an origin: the files that differ from it, stored against it alone. The
    payload is written to a staging folder, the rows committed, then the folder moved into place, PROJ-023."""
    item = origin(project_id, mform_id)
    if remove:
        _removable(folder)  # a refusal collects nothing
    base = origin_files(item)
    entries = boundary(folder)
    current = _read(entries)
    changed = _changes(base, current)
    text_size = sum(len(current[path][0]) for path, change in changed
                    if change != 'removed' and _text(current[path][0]))
    unit = _unit(item.mform_sha_id)
    given = {key: (provenance or {}).get(key) for key in PROVENANCE}
    staging = unit / 'variants' / f'.staging-{secrets.token_hex(4)}'
    staging.mkdir(parents=True)
    try:
        rows: list[tuple[str, str, str | None, str | None, str | None]] = []
        for path, change in changed:
            if change == 'removed':
                rows.append((path, change, None, None, None))
                continue
            data, mode = current[path]
            if change == 'modified' and _text(data) and text_size >= WHOLE_LIMIT and _text(base[path][0]):
                stored = (staging / 'diffs' / f'{path}.diff')
                stored.parent.mkdir(parents=True, exist_ok=True)
                stored.write_bytes(f'base_sha256 {_sha(base[path][0])}\n'.encode('utf-8') + _diff(base[path][0], data))
                rows.append((path, change, 'diff', _sha(data), mode))
            else:
                _write(staging / 'files' / path, data, mode)
                rows.append((path, change, 'whole', _sha(data), mode))
        with _db(project_id, write=True) as db:
            last = db.execute('SELECT MAX(variant_id) FROM variants WHERE mform_sha_id=?',
                              (item.mform_sha_id,)).fetchone()[0]
            variant_id = f'v{int(last[1:]) + 1 if last else 1:06d}'
            collected = home.now()
            blinded = given['blinded']
            db.execute('INSERT INTO variants(mform_sha_id, variant_id, collected, source_path, module, workflow, '
                       'prompt, model, role, blinded) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                       (item.mform_sha_id, variant_id, collected, str(folder), *(given[key] for key in PROVENANCE[:5]),
                        None if blinded is None else int(bool(blinded))))
            db.executemany('INSERT INTO variant_files(mform_sha_id, variant_id, path, change, storage, sha256, mode) '
                           'VALUES (?, ?, ?, ?, ?, ?, ?)', [(item.mform_sha_id, variant_id, *row) for row in rows])
            pending, final = unit / 'variants' / f'.pending-{variant_id}', unit / 'variants' / variant_id
            for stale in (pending, final):  # left by an interrupted write; no row names this id yet
                if stale.exists():
                    shutil.rmtree(stale)
            os.replace(staging, pending)
        # The rows are committed; moving the payload into place finishes the variant, and a read finishes a move a
        # crash left undone, so a variant is either absent or complete, PROJ-023.
        os.replace(pending, final)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    made = variants(project_id, item.mform_id, [variant_id])[0]
    if remove:
        _remove_collected(project_id, folder, made)
    return made


def _removable(folder: Path) -> str:
    """The shared git folder of a linked worktree, which Metaform may remove; any other folder is refused."""
    common = _git(folder, 'rev-parse', '--git-common-dir', check=False).stdout.decode('utf-8').strip() \
        if repository(folder) is not None else ''
    own = _git(folder, 'rev-parse', '--git-dir', check=False).stdout.decode('utf-8').strip() if common else ''
    if not common or Path(folder, common).resolve() == Path(folder, own).resolve():
        raise StoreError(f'{folder} is not a git worktree, so Metaform does not remove it.',
                         f'metaform add variant {folder}')
    return common


def _remove_collected(project_id: str, folder: Path, made: Variant) -> None:
    """Remove a collected git worktree once its variant reconstructs to what it held, PROJ-017."""
    common = _removable(folder)
    rebuilt = reconstruct(project_id, made)
    if rebuilt != _read(boundary(folder)):
        raise StoreError(f'Variant {made.variant_id} does not reconstruct what {folder} holds; the folder was kept.',
                         f'metaform extract {made.variant_id} <empty folder>')
    top = common if Path(common).is_absolute() else str(Path(folder, common).resolve())
    _git(Path(top).parent, 'worktree', 'remove', '--force', str(folder))


def variants(project_id: str, mform_id: str | None = None, ids: Sequence[str] | None = None) -> tuple[Variant, ...]:
    """The variants of an origin, the selected one unless named, each with its changed files."""
    item = origin(project_id, mform_id)
    with _db(project_id) as db:
        rows = db.execute('SELECT * FROM variants WHERE mform_sha_id=? ORDER BY variant_id',
                          (item.mform_sha_id,)).fetchall()
        found: list[Variant] = []
        for row in rows:
            if ids is not None and row['variant_id'] not in ids:
                continue
            files = tuple(VariantFile(file['path'], file['change'], file['storage'], file['sha256'], file['mode'])
                          for file in db.execute('SELECT * FROM variant_files WHERE mform_sha_id=? AND variant_id=? '
                                                 'ORDER BY path', (item.mform_sha_id, row['variant_id'])))
            blinded = row['blinded']
            found.append(Variant(row['variant_id'], item.mform_id, row['collected'], row['source_path'],
                                 row['module'], row['workflow'], row['prompt'], row['model'], row['role'],
                                 None if blinded is None else bool(blinded), files))
    if ids is not None:
        missing = [name for name in ids if name not in {variant.variant_id for variant in found}]
        if missing:
            raise StoreError(f'Origin {item.mform_id} has no variant {missing[0]}.',
                             f'metaform list variants origin={item.mform_id}')
    return tuple(found)


# ---------------------------------------------------------------- reconstruction, PROJ-018

def _lines(data: bytes) -> list[bytes]:
    """Lines as git's diff counts them: split on `\n` alone, each keeping its end."""
    parts = data.split(b'\n')
    return [part + b'\n' for part in parts[:-1]] + ([parts[-1]] if parts[-1] else [])


_HUNK = re.compile(rb'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')


def apply_diff(before: bytes, diff: bytes) -> bytes:
    """Apply a unified diff of one file with Python alone, so extraction needs no git, PROJ-016."""
    source, lines = _lines(before), _lines(diff)
    result: list[bytes] = []
    position = 0
    index = 0
    while index < len(lines) and not lines[index].startswith(b'@@'):
        index += 1
    while index < len(lines):
        match = _HUNK.match(lines[index])
        if match is None:
            index += 1
            continue
        start = int(match.group(1)) - (0 if match.group(2) == b'0' else 1)
        result.extend(source[position:start])
        position = start
        index += 1
        while index < len(lines) and not lines[index].startswith(b'@@'):
            line = lines[index]
            if line.startswith(b'\\'):
                if result and result[-1].endswith(b'\n') and lines[index - 1][:1] in (b'+', b' '):
                    result[-1] = result[-1][:-1]
            elif line[:1] == b' ':
                result.append(source[position])
                position += 1
            elif line[:1] == b'-':
                position += 1
            elif line[:1] == b'+':
                result.append(line[1:])
            index += 1
    result.extend(source[position:])
    return b''.join(result)


def reconstruct(project_id: str, made: Variant, base: dict[str, tuple[bytes, str]] | None = None
                ) -> dict[str, tuple[bytes, str]]:
    """A variant's files: the origin's, with its changes applied and each checked against its recorded hash."""
    item = origin(project_id, made.mform_id)
    files = dict(base if base is not None else origin_files(item))
    payload = _unit(item.mform_sha_id) / 'variants' / made.variant_id
    pending = payload.with_name(f'.pending-{made.variant_id}')
    if not payload.exists() and pending.exists():
        os.replace(pending, payload)  # a crash came between committing the rows and moving the payload in
    for change in made.files:
        if change.change == 'removed':
            files.pop(change.path, None)
            continue
        if change.storage == 'whole':
            data = (payload / 'files' / change.path).read_bytes()
        else:
            stored = (payload / 'diffs' / f'{change.path}.diff').read_bytes()
            header, _, diff = stored.partition(b'\n')
            before = files[change.path][0]
            if header.decode('utf-8') != f'base_sha256 {_sha(before)}':
                raise StoreError(f'The diff of {change.path} in {made.variant_id} is not against this origin\'s file.',
                                 f'metaform list variants origin={item.mform_id}')
            data = apply_diff(before, diff)
        if _sha(data) != change.sha256:
            raise StoreError(f'{change.path} in {made.variant_id} does not match its recorded hash.',
                             f'metaform list variants origin={item.mform_id}')
        files[change.path] = (data, change.mode or '644')
    return files


def extract(project_id: str, ids: Sequence[str], target: Path, mform_id: str | None = None) -> list[Path]:
    """Write each variant's files into its own folder under the target, or into the target for exactly one."""
    item = origin(project_id, mform_id)
    chosen = variants(project_id, item.mform_id, None if list(ids) == ['all'] else ids)
    base = origin_files(item)
    single = len(chosen) == 1 and list(ids) != ['all']
    written: list[Path] = []
    for made in chosen:
        folder = target if single else target / made.variant_id
        if folder.exists() and any(folder.iterdir()):
            raise StoreError(f'{folder} is not empty.', f'metaform extract {made.variant_id} <empty folder>')
        files = reconstruct(project_id, made, base)
        for path, (data, mode) in files.items():
            _write(folder / path, data, mode)
        folder.mkdir(parents=True, exist_ok=True)
        written.append(folder)
    return written
