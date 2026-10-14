"""The project archive, BASE-060: one plain zip for a project going out to a remote agent and for its work coming back.

It is the layout of PROJ-027 without the seal, so sealing, when built, seals this one format. Its visible files are
the work: `origin.zip`, the project's files when the build included them, and for work coming back `changes/`, the
remote agent's file changes against that origin as a variation, PROJ-026, and `note.txt`, the agent's note. Its
`.metaform/` folder holds `manifest`, the archive's identity, its two version numbers and a hash of each visible file,
and `data/export.json`, the project's STORE-027 exchange document, which a seal would close inside `metaform.data`.

A project archive carries the whole project. A return archive carries the working layer a project wheel's first run
opened, with every other layer the remote agent made, so `metaform import` adds them as new layers and overwrites
nothing, STORE-027. The file changes are written beside the archive for the person to review; nothing is applied to
the project's folder.

A project wheel carries one project archive and the wrapped prompt under `metaform/_project/`. Run with nothing after
it, it registers and imports the project, opens the working layer and prints what the agent needs; `return` writes
the return archive.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import zipfile
import zlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from . import __version__, home, loader, prompt_files, settings, vary
from .data import Store, export_document, import_document
from .data.history import boundary
from .data.ids import as_list, as_object
from .errors import Stop
from .wording import count, counted

FORMAT = 'metaform.archive'
ARCHIVE_VERSION = 1
COMPATIBLE_FROM = 1  # the oldest archive version whose reader reads this one correctly, STORE-029
FOLDER = '.metaform/'
MANIFEST, DATA = FOLDER + 'manifest', FOLDER + 'data/export.json'
ORIGIN, CHANGES, NOTE = 'origin.zip', 'changes/', 'note.txt'
KINDS = ('project', 'return')
SUFFIX = '.zip'

# Inside a project wheel, BASE-060: the project archive it carries and the wrapped prompt.
CARRIED = 'metaform/_project/'
CARRIED_ARCHIVE, CARRIED_PROMPT = CARRIED + 'archive.zip', CARRIED + 'prompt.md'

# What is never part of a project's files: version control, environments, dependencies and what a build writes.
LEFT_OUT = frozenset({'.git', '.hg', '.svn', 'node_modules', '__pycache__', '.mypy_cache', '.pytest_cache',
                      '.ruff_cache', '.tox', '.nox', '.eggs'})
LEFT_OUT_AT_TOP = frozenset({'build', 'dist'})
LEFT_OUT_SUFFIXES = ('.pyc', '.pyo', '.egg-info')

# The most one zip in an archive unpacks to. A zip states each file's size before it is read; an archive stating more
# than this, or a file that unpacks larger than it states, is refused before it can fill the memory of the machine
# reading it, since an archive comes from another machine.
LARGEST = 2 * 1024 ** 3
# The names Windows gives to devices whatever the extension, which a file written there would reach instead.
DEVICES = frozenset({'con', 'prn', 'aux', 'nul', *(f'com{number}' for number in range(1, 10)),
                     *(f'lpt{number}' for number in range(1, 10))})


# ------------------------------------------------------------------------------------------- the project's files

def _environment(folder: Path) -> bool:
    """A Python virtual environment, found by the file every one holds, whatever it is named."""
    return (folder / 'pyvenv.cfg').is_file()


def is_archive(path: Path) -> bool:
    """Whether a file is a Metaform archive: a zip whose manifest names this format."""
    if path.suffix.lower() != SUFFIX or not zipfile.is_zipfile(path):
        return False
    try:
        with zipfile.ZipFile(path) as held:
            return json.loads(held.read(MANIFEST)).get('format') == FORMAT
    except (KeyError, ValueError, OSError, zipfile.BadZipFile, AttributeError):
        return False


def project_files(folder: Path, *, leave_out: frozenset[Path] = frozenset()) -> dict[str, tuple[bytes, str]]:
    """The project's files with their mode, by path from the folder with forward slashes: what git tracks or would
    offer to track in a repository, every file of a plain folder, PROJ-011; never version control, a virtual
    environment, node_modules or build output, nor a Metaform archive or a file named in `leave_out`, such as the
    wheel being run."""
    root = folder.resolve()
    skipped = {path.resolve() for path in leave_out}
    environments: dict[tuple[str, ...], bool] = {}

    def in_environment(parts: tuple[str, ...]) -> bool:
        for depth in range(1, len(parts)):
            held = parts[:depth]
            if held not in environments:
                environments[held] = _environment(root.joinpath(*held))
            if environments[held]:
                return True
        return False

    found: dict[str, tuple[bytes, str]] = {}
    for entry in boundary(root):
        parts = PurePosixPath(entry.path).parts
        if set(parts[:-1]) & LEFT_OUT or parts[0] in LEFT_OUT_AT_TOP and len(parts) > 1 \
                or any(part.endswith(LEFT_OUT_SUFFIXES) for part in parts) or in_environment(parts):
            continue
        file = root.joinpath(*parts)
        resolved = file.resolve()
        # A link to a file outside the folder is not the project's, and what it reaches is never carried away.
        if resolved in skipped or not resolved.is_relative_to(root) or is_archive(file):
            continue
        found[entry.path] = (file.read_bytes(), entry.mode)
    return found


def _zipped_files(files: Mapping[str, tuple[bytes, str]]) -> bytes:
    """The files as a zip, each at its path with its mode, so the origin unpacks the same on every system."""
    held = io.BytesIO()
    with zipfile.ZipFile(held, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            data, mode = files[name]
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = ((stat.S_IFREG | (0o755 if mode == '755' else 0o644)) << 16)
            archive.writestr(info, data)
    return held.getvalue()


def _safe(name: str) -> str | None:
    """A path from an archive as a relative path with forward slashes, or None when it would reach outside the folder
    it is written into."""
    path = PurePosixPath(name.replace('\\', '/'))
    if not name or '\0' in name or path.is_absolute() \
            or any(part in ('', '.', '..') or ':' in part for part in path.parts):
        return None
    return path.as_posix()


def _target(folder: Path, name: str) -> Path:
    """Where a file from an archive is written in a folder: refused when its name reaches outside the folder, through
    `..`, a drive, or a link already in the folder, and on Windows when it names a device or a name Windows would
    change."""
    root = folder.resolve()
    relative = _safe(name)
    target = root.joinpath(*PurePosixPath(relative).parts) if relative else None
    if target is None or not target.resolve().is_relative_to(root):
        raise Stop(f'{name} would be written outside {folder}.', 'ask for the archive again')
    if os.name == 'nt' and any(part.split('.')[0].strip().lower() in DEVICES or part.endswith(('.', ' '))
                               or any(char in '<>"|?*' or ord(char) < 32 for char in part)
                               for part in PurePosixPath(str(relative)).parts):
        raise Stop(f'{name} cannot be written on Windows, which keeps that name for a device or changes it.',
                   'rename the file on the system the archive came from, then build or return it again')
    return target


def _sized(held: zipfile.ZipFile, what: str) -> None:
    """Refuse a zip that states it unpacks to more than LARGEST, before any of it is read."""
    if sum(info.file_size for info in held.infolist()) > LARGEST:
        raise Stop(f'{what} unpacks to more than {LARGEST // 1024 ** 3} GB, more than an archive may hold.',
                   'leave large files out of the project archive: metaform build kind=archive files=false')


def _member(held: zipfile.ZipFile, info: zipfile.ZipInfo, what: str) -> bytes:
    """One file of a zip, read no further than the size the zip states for it, and refused when its bytes are not
    the ones the zip recorded."""
    try:
        with held.open(info) as source:
            data = source.read(info.file_size + 1)
    except (zipfile.BadZipFile, zlib.error, EOFError):
        data = None
    if data is None or len(data) != info.file_size:
        raise Stop(f'{info.filename} in {what} is not as its zip recorded it.', 'ask for the archive again')
    return data


def _unzipped_files(data: bytes, what: str) -> dict[str, tuple[bytes, str]]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as held:
            _sized(held, what)
            files: dict[str, tuple[bytes, str]] = {}
            for info in held.infolist():
                if info.is_dir():
                    continue
                name = _safe(info.filename)
                if name is None:
                    raise Stop(f'{what} holds {info.filename}, which is not a path inside the project.',
                               'build the archive again: metaform build kind=archive')
                files[name] = (_member(held, info, what), '755' if (info.external_attr >> 16) & 0o111 else '644')
            return files
    except zipfile.BadZipFile:
        raise Stop(f'{what} is not a zip.', 'build the archive again: metaform build kind=archive') from None


# ------------------------------------------------------------------------------------------- writing and reading

@dataclass(frozen=True)
class Archive:
    """One archive as read: its manifest, the project's exchange document, the origin's files when it carries them,
    and for work coming back the variation and the note."""
    manifest: dict[str, Any]
    document: dict[str, Any]
    origin: dict[str, tuple[bytes, str]] | None
    changes: dict[str, bytes]
    note: str

    @property
    def kind(self) -> str:
        return str(self.manifest['kind'])

    @property
    def project(self) -> str:
        return str(self.manifest['project'])


def packed(kind: str, project: str, document: dict[str, Any], *, origin: Mapping[str, tuple[bytes, str]] | None,
           changes: Mapping[str, bytes] | None = None, note: str = '', layer: str | None = None) -> bytes:
    """An archive's bytes: the visible work, then the manifest naming each visible file's hash, then the data."""
    if kind not in KINDS:
        raise ValueError(f'An archive is one of {", ".join(KINDS)}, not {kind}.')
    work: dict[str, bytes] = {}
    if origin is not None:
        work[ORIGIN] = _zipped_files(origin)
    for name, data in (changes or {}).items():
        work[CHANGES + name] = data
    if note:
        work[NOTE] = note.encode('utf-8')
    manifest = {
        'format': FORMAT, 'archive_version': ARCHIVE_VERSION, 'compatible_from': COMPATIBLE_FROM, 'kind': kind,
        'project': project, 'created': home.now(), 'metaform': __version__, 'files': origin is not None,
        **({'layer': layer} if layer is not None else {}),
        'work': [{'path': name, 'sha256': hashlib.sha256(work[name]).hexdigest(), 'size': len(work[name])}
                 for name in sorted(work)]}
    held = io.BytesIO()
    with zipfile.ZipFile(held, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(work):
            archive.writestr(name, work[name])
        archive.writestr(MANIFEST, json.dumps(manifest, indent=1, ensure_ascii=False) + '\n')
        archive.writestr(DATA, json.dumps(document, ensure_ascii=False))
    return held.getvalue()


def _readable(manifest: dict[str, Any], what: str) -> None:
    """Refuse an archive only when this Metaform cannot read it, STORE-029: one whose `compatible_from` is above this
    archive version. An archive without `compatible_from` takes it as its own `archive_version`."""
    version, needed = manifest.get('archive_version'), manifest.get('compatible_from', manifest.get('archive_version'))
    if not isinstance(version, int) or isinstance(version, bool) or not isinstance(needed, int) \
            or isinstance(needed, bool):
        raise Stop(f'{what} does not say which archive version it is.', 'build the archive again')
    if needed > ARCHIVE_VERSION:
        made = manifest.get('metaform')
        raise Stop(f'{what} is archive version {version}, which a Metaform reads from archive version {needed}; this '
                   f'Metaform reads archive version {ARCHIVE_VERSION}.',
                   f'install Metaform {made} or newer' if made else 'install the Metaform release that wrote it')


def read(data: bytes, what: str) -> Archive:
    """An archive from its bytes, once its manifest, its version and the hash of each visible file have been checked;
    `what` names it in what is said."""
    try:
        held = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise Stop(f'{what} is not a zip.', 'metaform import <file>, with a .zip that metaform build or return wrote') \
            from None
    with held:
        _sized(held, what)
        names = set(held.namelist())
        if MANIFEST not in names:
            raise Stop(f'{what} is not a Metaform archive: it has no {MANIFEST}.',
                       'metaform import <file>, with a .zip that metaform build or return wrote')
        try:
            manifest = as_object(json.loads(_member(held, held.getinfo(MANIFEST), what)))
        except ValueError:
            raise Stop(f'The manifest of {what} is not JSON.', 'build the archive again') from None
        if manifest is None or manifest.get('format') != FORMAT:
            raise Stop(f'{what} is not a Metaform archive.', 'metaform import <file>, with a .zip that metaform '
                                                              'build or return wrote')
        _readable(manifest, what)
        if manifest.get('kind') not in KINDS or not isinstance(manifest.get('project'), str):
            raise Stop(f'The manifest of {what} names no kind or no project.', 'build the archive again')
        if not home.PROJECT_ID.fullmatch(manifest['project']):  # the id names files and folders on this machine
            raise Stop(f'The manifest of {what} names {manifest["project"]!r}, which is not a project id.',
                       'build the archive again')
        entries = [as_object(entry) for entry in as_list(manifest.get('work')) or []]
        listed = {str(entry.get('path')): entry for entry in entries if entry is not None}
        work = {name: _member(held, held.getinfo(name), what) for name in names
                if not name.startswith(FOLDER) and not name.endswith('/')}
        for name in sorted(set(listed) | set(work)):
            if name not in work or name not in listed or \
                    hashlib.sha256(work[name]).hexdigest() != listed[name].get('sha256'):
                raise Stop(f'{name} in {what} is not as the archive was written.', 'ask for the archive again')
        if DATA not in names:
            raise Stop(f'{what} holds no project data, {DATA}.', 'build the archive again')
        try:
            document = as_object(json.loads(_member(held, held.getinfo(DATA), what)))
        except ValueError:
            document = None
        if document is None:
            raise Stop(f'The project data of {what} is not a JSON object.', 'build the archive again')
    origin = _unzipped_files(work[ORIGIN], f'The origin in {what}') if ORIGIN in work else None
    changes = {name[len(CHANGES):]: body for name, body in work.items() if name.startswith(CHANGES)}
    return Archive(manifest, document, origin, changes, work.get(NOTE, b'').decode('utf-8', errors='replace'))


# ------------------------------------------------------------------------------------------------- importing

@dataclass(frozen=True)
class Imported:
    """What importing an archive did: the exchange document's report, and for work coming back the layers it brought,
    where its file changes were written for review, and its note."""
    kind: str
    project: str
    report: dict[str, Any]
    layer: str | None = None
    review: Path | None = None
    changed: tuple[str, ...] = ()
    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    note: str = ''
    files: int = 0


def counted_changes(origin: Mapping[str, bytes], changes: Mapping[str, bytes],
                    what: str = 'The changes') -> tuple[tuple[str, ...], ...]:
    """The files a variation changes, adds and removes against its origin, each sorted by path, read by applying it,
    so a line of a file that looks like a diff's header is never taken for one. A variation that does not apply to
    its origin is refused."""
    try:
        work = vary.expanded(origin, changes)
    except (vary.Mismatch, ValueError, IndexError):
        raise Stop(f'{what} do not apply to the origin they were taken from.', 'ask for the archive again') from None
    return (tuple(sorted(name for name in work if name in origin and work[name] != origin[name])),
            tuple(sorted(name for name in work if name not in origin)),
            tuple(sorted(name for name in origin if name not in work)))


def _review_folder(source: Path) -> Path:
    """A new folder beside the archive, named for it, for its changes, made here so no other import takes it; a
    second import of it takes the next number."""
    base = source.with_name(source.name[:-len(SUFFIX)] if source.name.lower().endswith(SUFFIX) else source.name)
    candidate, number = base, 1
    while True:
        try:
            if home.is_home_path(candidate):
                home.mkdir_private(candidate.parent)
                candidate.mkdir(mode=0o700)
            else:
                candidate.mkdir(parents=True)
            return candidate
        except FileExistsError:
            number += 1
            candidate = base.with_name(f'{base.name}-{number}')


def _write_into(folder: Path, files: Mapping[str, bytes]) -> None:
    for name, data in files.items():
        target = _target(folder, name)
        if home.is_home_path(target):
            home.mkdir_private(target.parent)
            home.write_private(target, data)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)


def import_archive(source: Path, project: str | None = None) -> Imported:
    """Import an archive into this home. A project archive's data goes through STORE-027's import. A return
    archive's layers arrive as new layers of a project this home holds, nothing is overwritten, and its file changes
    and note are written into a new folder beside the archive for the person to review; the project's own folder is
    never written."""
    found = read(source.read_bytes(), str(source))
    if found.kind == 'project':
        report = import_document(found.document, project)
        return Imported('project', project or found.project, report, files=len(found.origin or {}))
    target = project or found.project
    if home.project(target) is None:
        raise Stop(f'{source} returns work on the project {target}, which this home does not hold.',
                   'metaform import <file> <project>, naming the registered project it returns to')
    origin = {name: data for name, (data, _) in (found.origin or {}).items()}
    changed, added, removed = counted_changes(origin, found.changes, f'The changes in {source}')  # before any write
    report = import_document(found.document, target)
    review: Path | None = None
    if changed or added or removed or found.note:
        review = _review_folder(source)
        _write_into(review, {**({name: body for name, body in found.changes.items()} if changed or added or removed
                                else {}), **({NOTE: found.note.encode('utf-8')} if found.note else {})})
    return Imported('return', target, report, layer=found.manifest.get('layer'), review=review, changed=changed,
                    added=added, removed=removed, note=found.note)


# ------------------------------------------------------------------------------------------- a project wheel

@dataclass(frozen=True)
class Carried:
    """What a project wheel carries: its own path, the project archive and the wrapped prompt."""
    wheel: Path
    archive: Archive
    prompt: str


def carried() -> Carried | None:
    """The project the running wheel carries, or None when Metaform does not run from a project wheel. Only a direct
    run, BASE-042, sets the wheel's path, so an installed copy of a project wheel carries nothing here."""
    running = os.environ.get('METAFORM_WHEEL')
    if not running:
        return None
    wheel = Path(running)
    try:
        with zipfile.ZipFile(wheel) as held:
            if CARRIED_ARCHIVE not in held.namelist():
                return None
            data, prompt = held.read(CARRIED_ARCHIVE), held.read(CARRIED_PROMPT).decode('utf-8')
    except (OSError, KeyError, zipfile.BadZipFile):
        return None
    return Carried(wheel, read(data, f'the project archive in {wheel.name}'), prompt)


def _needs_carried() -> Carried:
    found = carried()
    if found is None:
        raise Stop('return hands back work from a project wheel, and Metaform is not running from one.',
                   'python <project wheel> return')
    return found


def _counts(report: Mapping[str, Any]) -> str:
    return ', '.join(f'{key.replace("_", " ")}: {count(value)}' for key, value in report.items() if key != 'notices')


def _stamp() -> str:
    return datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')


def _working_layer(project: str, folder: Path) -> str:
    """The folder's working layer, BASE-060: the layer its `write_layer` setting names, opened when there is none, so
    a write that names no layer goes to it and returns with the work."""
    store = Store(project)
    named = settings.value('write_layer', folder)
    if named and any(layer.name == named for layer in store.layers(limit=0).results):
        return str(named)
    name = f'remote_{_stamp().lower()}'
    store.layer(name, 'chassis', prompt_files.chassis('remote_layer'), mutable=True, hideable=True,
                provenance={'module': 'chassis', 'role': 'remote agent'}, ready=True)
    settings.put('write_layer', name, folder)
    return name


def _enable_carried() -> None:
    """Turn on each module the wheel carries that this home has never turned on or off: the person chose to carry it,
    and a module that ships disabled would otherwise stay off."""
    changed = False
    for item in loader.discover():
        if item.place == 'system' and item.declared is not None and item.declared.ships_disabled \
                and home.module_state(item.id) is None:
            home.set_module_state(item.id, True)
            changed = True
    if changed:
        loader.reset()


def first_run(folder: Path, say: Callable[[str], None]) -> None:
    """`python <project wheel>`, BASE-060: register the project at this folder and import it when the home does not
    hold it, unpacking its files into the folder when the wheel carries them and the folder holds none of them; open
    the working layer; then print the wrapped prompt, the modules' instructions, the map's entry and how to return.
    A later run prints the same and imports nothing."""
    from . import module, results
    held = _needs_carried()
    found, project, wheel = held.archive, held.archive.project, held.wheel.name
    folder = folder.resolve()
    record = home.project(project)
    told: list[str] = []
    if record is None:
        holder = home.project_at(str(folder))
        if holder is not None:
            raise Stop(f'{folder} is already registered as the project {holder}.',
                       f'run python {wheel} from an empty folder of its own')
        try:
            source = home.Project(**found.document['projects'][0]['project'])
        except (KeyError, IndexError, TypeError):
            raise Stop(f'The project archive in {wheel} holds no record of its project.',
                       'build the project wheel again: metaform build kind=project') from None
        targets = {name: _target(folder, name) for name in found.origin or {}}  # every name checked before a write
        target = ('path', str(folder)) if source.target_type == 'path' else (source.target_type, source.target_value)
        home.register(home.Project(project, str(folder), *target))
        try:
            report = import_document(found.document, project)
        except BaseException:
            home.forget_project(project)  # registered here a moment ago, so the next run tries again
            raise
        told.append(f'Imported the project {project} at {folder}: {_counts(report)}.')
        if found.origin is None:
            told.append('This wheel carries no project files: the work is on the map alone.')
        else:
            present = sorted(name for name, target_file in targets.items() if target_file.exists())
            if present:
                told.append(f'The folder already holds {len(present)} of the project\'s files, such as {present[0]}, '
                            'so none was unpacked.')
            else:
                for name, (data, mode) in found.origin.items():
                    target_file = targets[name]
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    target_file.write_bytes(data)
                    if mode == '755' and os.name != 'nt':
                        target_file.chmod(target_file.stat().st_mode | 0o111)
                told.append(f"Unpacked the project's {counted(len(found.origin), 'file', 'files')} into {folder}.")
    elif home.path_key(record.path) != home.path_key(folder):
        raise Stop(f'This home holds the project {project} at {record.path}.', f'cd {record.path}, then python {wheel}')
    else:
        told.append(f'The project {project} at {folder} was imported on an earlier run; nothing was imported again.')
    _enable_carried()
    layer = _working_layer(project, folder)
    if settings.state('connect_instructions', folder) == 'default':
        settings.put('connect_instructions', 'full', folder)  # no host trims what a CLI agent reads, MCP-029
    told.append(f'Working layer: {layer}.')
    entry = Store(project).roots(limit=0)
    say('\n'.join([
        f'Metaform {__version__}, running from {wheel}.', *told, '',
        '## Your task', '', held.prompt.strip(), '',
        "## Metaform's instructions", '', module.instructions(folder, project).strip(), '',
        "## The map's entry", '', results.as_text(entry).strip() or '(the map is empty)', '',
        '## Returning your work', '', prompt_files.chassis('remote_return', wheel=wheel, layer=layer)]))


@dataclass(frozen=True)
class Returned:
    path: Path
    layers: tuple[str, ...]
    changed: tuple[str, ...]
    added: tuple[str, ...]
    removed: tuple[str, ...]
    files: bool
    left: int


def _carried_ops(document: Mapping[str, Any], base_id: str) -> tuple[set[str], set[tuple[str, ...]]]:
    """The layer ids and the ops the carried document held for one base."""
    for entry in document.get('projects', []):
        for base in entry.get('bases', []):
            if base['base']['id'] == base_id:
                ops = base.get('ops', [])
                return ({str(op['id']) for op in ops if op['kind'] == 'layer'},
                        {_op_key(op) for op in ops})
    return set(), set()


def _op_key(op: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(str(op.get(key)) for key in ('session_id', 'at', 'op', 'kind', 'id', 'layer_id'))


def write_return(folder: Path, note: str = '', file: Path | None = None) -> Returned:
    """`python <project wheel> return`, BASE-060: one return archive of the working layer and every other layer made
    since the project was carried, the file changes against the carried origin, and the note."""
    held = _needs_carried()
    project = held.archive.project
    record = home.project(project)
    if record is None:
        raise Stop(f'This home does not hold the project {project} yet.', f'python {held.wheel.name}')
    root = Path(record.path)
    layer = settings.value('write_layer', root)
    base = home.active_base(project)
    if not layer or base is None:
        raise Stop(f'The project {project} has no working layer here yet.', f'python {held.wheel.name}')
    carried_layers, carried_ops = _carried_ops(held.archive.document, base.id)
    store = Store(project)
    made = [found for found in store.layers(limit=0).results if found.id not in carried_layers]
    names = tuple(sorted((found.name for found in made), key=lambda name: (name != layer, name)))
    whole = export_document([project], metaform=base.name)
    left = sum(1 for entry in whole['projects'] for each in entry['bases'] for op in each['ops']
               if op['layer_id'] in carried_layers and _op_key(op) not in carried_ops)
    document = export_document([project], metaform=base.name, layers=names)
    changes: dict[str, bytes] = {}
    changed: tuple[str, ...] = ()
    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    if held.archive.origin is not None:
        origin = {name: data for name, (data, _) in held.archive.origin.items()}
        work = {name: data for name, (data, _) in project_files(root, leave_out=frozenset({held.wheel})).items()}
        changes = vary.variation(origin, work)
        changed, added, removed = counted_changes(origin, changes, 'The changes to the project files')
        if not (changed or added or removed):
            changes = {}
    target = file if file is not None else root / f'{project}-return-{_stamp()}{SUFFIX}'
    if target.suffix.lower() != SUFFIX:
        raise Stop(f'{target} does not end in {SUFFIX}; an archive is a zip.', f'python {held.wheel.name} return '
                   f'file=<name>{SUFFIX}')
    body = packed('return', project, document, origin=held.archive.origin, changes=changes, note=note, layer=layer)
    if home.is_home_path(target):
        home.mkdir_private(target.parent)
        home.write_private(target, body)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    return Returned(target.resolve(), names, changed, added, removed, held.archive.origin is not None, left)
