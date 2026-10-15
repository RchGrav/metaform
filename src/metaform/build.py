"""`metaform build`: the four builds of BASE-060, and the wheel of BASE-041 and BASE-022 they are made of.

A wheel is written with `zipfile` from the installed package, so no source
tree is needed. It carries the chassis, each chosen module as a system module,
a root `__main__.py` that runs it directly, BASE-042, and every pure-Python
dependency under `metaform/_vendor/`. A compiled dependency is not carried: it
stays in `Requires-Dist`, and the build names it with the module that needs it.
The build names the copy it packed, and, run inside a Metaform checkout that is
not that copy, says when the checkout differs from it.

The four builds: `installer`, that wheel with the modules chosen, by default the
ones on at home; `full`, the wheel with every module found; `project`, the wheel
with a project archive and the wrapped prompt inside it, `metaform/_project/`,
for a remote agent; and `archive`, the project archive alone, BASE-060. A build
chooses what it carries and never turns a module on or off at home. It reports
each stage it starts through `progress`, so the web GUI shows real progress.

The three wheel builds also write one zip, `metaform-<version>-<kind>.zip`, beside the wheel: the wheel, a project
wheel's `prompt.md`, and a README for a tester, made from the code by `build_readme`, all in one folder of the zip's
own name. That zip is what the web GUI downloads; the wheel stays beside it as what install registers, MCP-010.
"""
from __future__ import annotations

import base64
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import __version__, _build_info, archive, build_readme, home, loader, prompt_files
from .errors import Stop

if TYPE_CHECKING:
    from .data.prompts import PromptVersion

NAME = 'metaform'
COMPILED = ('.so', '.pyd', '.dylib')

def _needs_python() -> tuple[int, ...]:
    """The oldest Python the wheel runs on, checked by its bootstrap before anything is imported."""
    return tuple(int(part) for part in _build_info.REQUIRES_PYTHON.removeprefix('>=').split('.'))


BOOTSTRAP = '''"""Run Metaform from this wheel, with its carried dependencies, BASE-042."""
import os
import sys

NEEDS = NEEDS_PYTHON
if sys.version_info < NEEDS:
    sys.exit('Metaform needs Python %s or newer; this is Python %s.'
             % ('.'.join(map(str, NEEDS)), sys.version.split()[0]))

WHEEL = os.path.abspath(os.path.dirname(__file__))
VENDOR = os.path.join(WHEEL, 'metaform', '_vendor')


def _provides_metaform(entry):
    try:
        return os.path.isfile(os.path.join(entry, 'metaform', '__init__.py'))
    except (TypeError, ValueError, OSError):
        return False


sys.path[:] = [WHEEL, VENDOR] + [entry for entry in sys.path
                                 if entry not in (WHEEL, VENDOR) and not _provides_metaform(entry)]
os.environ['METAFORM_WHEEL'] = WHEEL

from metaform.cli import main  # noqa: E402  the path must be set first

raise SystemExit(main())
'''


def bootstrap() -> str:
    """The wheel's root `__main__.py`, with the oldest Python it runs on written in, BASE-042."""
    return BOOTSTRAP.replace('NEEDS_PYTHON', repr(_needs_python()))


def _walk(root: Any, prefix: str) -> dict[str, bytes]:
    """Every file under a folder or a folder inside a zip, keyed by its path in the wheel."""
    files: dict[str, bytes] = {}
    for child in root.iterdir():
        if child.name == '__pycache__':
            continue
        name = f'{prefix}/{child.name}'
        if child.is_dir():
            files.update(_walk(child, name))
        else:
            files[name] = child.read_bytes()
    return files


def _requirements(carried: Sequence[loader.Found]) -> tuple[list[str], dict[str, list[str]]]:
    """The chassis's dependencies, then each carried module's own `DEPENDENCIES`, duplicates removed."""
    per_module: dict[str, list[str]] = {'chassis': list(_build_info.CHASSIS_DEPENDENCIES)}
    for item in carried:
        if item.declared is not None:
            per_module[item.id] = list(item.declared.dependencies)
    ordered: list[str] = []
    for requirements in per_module.values():
        for requirement in requirements:
            if requirement not in ordered:
                ordered.append(requirement)
    return ordered, per_module


UV_TIMEOUT = 600  # seconds for one uv step, L6


def _uv(*args: str) -> None:
    uv = shutil.which('uv')
    if uv is None:
        raise Stop('metaform build needs uv to carry dependencies.', 'curl -LsSf https://astral.sh/uv/install.sh | sh')
    step = f'uv {args[0]} {args[1]}'
    try:
        result = subprocess.run([uv, *args], check=False, capture_output=True, text=True, timeout=UV_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise Stop(f'{step} did not finish in {UV_TIMEOUT // 60} minutes.', 'metaform build') from None
    if result.returncode != 0:
        tail = result.stderr.strip().splitlines()
        raise Stop(f'{step} failed: {tail[-1] if tail else "it gave no reason"}', 'metaform build')


def _pinned(requirements: list[str], work: Path, label: str) -> list[str]:
    if not requirements:
        return []
    source, pinned = work / f'{label}.in', work / f'{label}.txt'
    source.write_text('\n'.join(requirements) + '\n', encoding='utf-8')
    _uv('pip', 'compile', str(source), '-o', str(pinned), '--no-header', '--python', sys.executable, '--quiet')
    return [line.split('==')[0].strip().lower().replace('_', '-') for line in pinned.read_text().splitlines()
            if line and not line.startswith((' ', '#'))]


def _carry(requirements: list[str], per_module: dict[str, list[str]], work: Path,
           progress: Callable[[str], None] = lambda stage: None) -> tuple[dict[str, bytes], list[str]]:
    """Pure-Python distributions under metaform/_vendor/, and one note per compiled distribution left out: resolved,
    then collected, each stage told to `progress`."""
    progress('resolve')
    if not requirements:
        progress('collect')
        return {}, []
    _pinned(requirements, work, 'all')
    progress('collect')
    target = work / 'target'
    _uv('pip', 'install', '--target', str(target), '--no-deps', '-r', str(work / 'all.txt'), '--python',
        sys.executable, '--quiet')
    needed_by: dict[str, list[str]] = {}
    for module, own in per_module.items():
        for dist in _pinned(own, work, f'module-{module}'):
            needed_by.setdefault(dist, []).append(module)
    files: dict[str, bytes] = {}
    notes: list[str] = []
    for info in sorted(target.glob('*.dist-info')):
        record = (info / 'RECORD').read_text(encoding='utf-8') if (info / 'RECORD').exists() else ''
        paths = [line.split(',')[0] for line in record.splitlines() if line]
        dist = info.name.split('-')[0]
        key = dist.lower().replace('_', '-')
        if any(path.endswith(COMPILED) for path in paths):
            modules = ', '.join(needed_by.get(key, ['chassis']))
            notes.append(f'{dist}: compiled, not carried; needed by {modules}. A direct run of this wheel needs it '
                         'installed.')
            continue
        for path in paths:
            source = target / path
            # RECORD also names what an install puts beside the packages, such as scripts; only what is inside the
            # target is a package's file.
            if source.is_file() and '__pycache__' not in Path(path).parts \
                    and source.resolve().is_relative_to(target.resolve()):
                files[f'metaform/_vendor/{Path(path).as_posix()}'] = source.read_bytes()
    return files, notes


def _digest(data: bytes) -> str:
    return 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()


def _source(root: Any, system: set[str]) -> dict[str, bytes]:
    """The chassis files under a `metaform` package folder and the carried system modules in it, BASE-041."""
    files: dict[str, bytes] = {}
    for name, data in _walk(root, 'metaform').items():
        parts = name.split('/')
        if parts[1] in ('_vendor', '_project'):  # a project wheel's own project is never packed again, BASE-060
            continue
        if parts[1] == 'modules' and len(parts) > 3 and (parts[2] not in system or parts[3] == 'tests'):
            continue
        files[name] = data
    return files


def _checkout(folder: Path) -> Path | None:
    """The root of the Metaform checkout holding a folder: a `pyproject.toml` naming `metaform` beside `src/metaform`."""
    for root in (folder, *folder.parents):
        project = root / 'pyproject.toml'
        if not (project.is_file() and (root / 'src' / NAME / '__init__.py').is_file()):
            continue
        try:
            if tomllib.loads(project.read_text(encoding='utf-8')).get('project', {}).get('name') == NAME:
                return root
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
            continue
    return None


KINDS = ('archive', 'project', 'installer', 'full')
SHAPES = ('remote', 'map', 'home', 'everything')
STAGES: dict[str, tuple[str, ...]] = {
    'archive': ('pack project', 'write'),
    'project': ('resolve', 'collect', 'pack modules', 'pack project', 'write'),
    'installer': ('resolve', 'collect', 'pack modules', 'write'),
    'full': ('resolve', 'collect', 'pack modules', 'write'),
}
WRAPPER, ONBOARDING = 'remote_wrapper', 'remote_onboarding'  # the prompt store's names, BASE-060
WHEEL = f'{NAME}-{__version__}-py3-none-any.whl'


@dataclass(frozen=True)
class Choice:
    """One module a build can carry: whether a remote agent has use for it, BASE-060, and whether it is on at home."""
    id: str
    summary: str
    remote: bool
    home: bool
    place: str


def _packable(item: loader.Found) -> bool:
    """A module found whose declarations read, and that did not fail to load at home: a module off, or on another
    system, or waiting for a dependency the build carries, is packed as it is."""
    if item.declared is None:
        return False
    if item.module is not None or not item.enabled or not item.declared.compatible:
        return True
    return bool(loader.missing_dependencies(item.declared.dependencies))


def _found() -> list[loader.Found]:
    return [item for item in loader.discover() if _packable(item)]


def choices() -> list[Choice]:
    """Every module a build can carry, in module id order, filled from the loader, so a new module needs no change
    here or in the web GUI's build panel."""
    made: list[Choice] = []
    for item in sorted(_found(), key=lambda found: found.id):
        declared = item.declared
        if declared is None:
            continue
        summary = item.module.summary if item.module is not None else declared.summary
        made.append(Choice(item.id, summary or '', declared.remote_agent, item.module is not None, item.place))
    return made


def shape(name: str) -> tuple[str, ...]:
    """The modules a shape ticks: those that declare remote use, map alone, those on at home, or every one."""
    found = choices()
    if name == 'remote':
        return tuple(choice.id for choice in found if choice.remote)
    if name == 'map':
        return tuple(choice.id for choice in found if choice.id == 'map')
    if name == 'home':
        return tuple(choice.id for choice in found if choice.home)
    if name == 'everything':
        return tuple(choice.id for choice in found)
    raise Stop(f'{name} is not a shape; the shapes are {", ".join(SHAPES)}.', 'metaform help build')


@dataclass(frozen=True)
class Request:
    """What one build is asked for. `modules` or `shape` chooses the modules, each for the wheel builds only; with
    neither, an installer carries the modules on at home, a project build the Remote agent shape. `task` is the
    person's task for the remote agent, as written."""
    kind: str = 'installer'
    project: str | None = None
    modules: tuple[str, ...] | None = None
    shape: str | None = None
    files: bool = True
    task: str | None = None


@dataclass(frozen=True)
class Plan:
    """A request with its project and modules decided, before anything is built."""
    kind: str
    project: str | None
    modules: tuple[str, ...]
    files: bool
    task: str | None

    @property
    def stages(self) -> tuple[str, ...]:
        return STAGES[self.kind]


def plan(request: Request, folder: Path | None = None) -> Plan:
    """Decide what a build carries, or stop saying why it cannot be built, before any stage runs. A project build
    with no project named takes the folder's."""
    kind = request.kind
    if kind not in KINDS:
        raise Stop(f'{kind} is not a build; the builds are {", ".join(KINDS)}.', 'metaform help build')
    if request.modules is not None and request.shape is not None:
        raise Stop('A build takes modules= or shape=, not both: a shape is where the modules start.',
                   'metaform help build')
    if kind in ('archive', 'full') and (request.modules is not None or request.shape is not None):
        carried = 'An archive build carries no modules' if kind == 'archive' else 'A full build carries every module found'
        raise Stop(f'{carried}, so it takes no modules= or shape=.', 'metaform help build')
    project = request.project
    if kind in ('archive', 'project'):
        if project is None and folder is not None:
            from . import context
            project = context.project_for(folder)
        if project is None:
            raise Stop(f'A {kind} build needs a project.', f'metaform build kind={kind} project=<id>')
        if home.project(project) is None:
            raise Stop(f'No project {project} is registered.', 'metaform list projects')
    elif project is not None:
        raise Stop(f'{"An" if kind == "installer" else "A"} {kind} build carries no project, BASE-048.',
                   'metaform build kind=project project=<id>')
    if kind == 'archive':
        modules: tuple[str, ...] = ()
    elif kind == 'full':
        modules = shape('everything')
    elif request.modules is not None:
        known = {choice.id for choice in choices()}
        unknown = [name for name in request.modules if name not in known]
        if unknown:
            raise Stop(f'No module {unknown[0]} to carry; the modules are {", ".join(sorted(known))}.',
                       'metaform list modules')
        modules = tuple(dict.fromkeys(request.modules))
    else:
        modules = shape(request.shape or ('remote' if kind == 'project' else 'home'))
    files = request.files if kind in ('archive', 'project') else False
    return Plan(kind, project, modules, files, request.task if kind == 'project' else None)


def remote_prompts() -> tuple[PromptVersion, PromptVersion]:
    """The wrapper and the onboarding as the prompt store serves them now, BASE-060: each made from its shipped text
    when first served, so an edit made in the prompt editor is the text a build uses."""
    from .data import prompts
    for name in (WRAPPER, ONBOARDING):
        prompts.shipped(name, 'markdown', prompt_files.chassis(name))
    return prompts.prompt_version(WRAPPER), prompts.prompt_version(ONBOARDING)


def wrapped(task: str | None, wheel: str, project: str) -> str:
    """The prompt a remote agent is given with a project wheel, BASE-060: the wrapper around the person's task as
    written, or around the onboarding when there is none, with the wheel's file name and the project filled in."""
    wrapper, onboarding = remote_prompts()

    def filled(text: str) -> str:
        return text.replace('{wheel}', wheel).replace('{project}', project)

    given = (task or '').strip()
    inner = given if given else filled(onboarding.text).strip()
    return filled(wrapper.text).replace('{task}', inner).strip() + '\n'


@dataclass(frozen=True)
class Built:
    """What a build wrote: the file, what it carries, the notes to print, for a project wheel the wrapped prompt,
    written beside it as `prompt.md`, and for a wheel build the zip a tester is sent, `bundle`."""
    path: Path
    kind: str
    project: str | None
    modules: tuple[str, ...]
    notes: tuple[str, ...]
    prompt: str | None = None
    bundle: Path | None = None


def _project_archive(project: str, files: bool) -> bytes:
    """The project archive of BASE-060: the project's exchange document and, when chosen, its files as the origin."""
    from .data import export_document
    record = home.project(project)
    if record is None:
        raise Stop(f'No project {project} is registered.', 'metaform list projects')
    origin = None
    if files:
        folder = Path(record.path)
        if not folder.is_dir():
            raise Stop(f"The project's folder {folder} is not here, so its files cannot be included.",
                       f'metaform build kind=archive project={project} files=false')
        origin = archive.project_files(folder)
    return archive.packed('project', project, export_document([project]), origin=origin)


def _folder() -> Path:
    """A new folder under the home's builds, named by the time and made here, so no other build takes it; a second
    build in the same second takes the next number, so no build writes over another, the web GUI's running at once
    included."""
    stamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
    root = home.home() / 'builds'
    home.mkdir_private(root)
    folder, number = root / stamp, 1
    while True:
        try:
            folder.mkdir(mode=0o700)
            return folder
        except FileExistsError:
            number += 1
            folder = root / f'{stamp}-{number}'


def _written(path: Path, write: Callable[[Path], object]) -> None:
    """Write a build's file under a passing name and give it its own name only once it is whole, so a build stopped
    part way, by an error or by the web GUI's server stopping, never leaves a file that looks finished."""
    partial = path.with_name(path.name + '.part')
    try:
        home.write_private(partial, b'')
        write(partial)
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)


def make(request: Request, folder: Path | None = None,
         progress: Callable[[str], None] = lambda stage: None) -> Built:
    """Run one build, telling `progress` each stage as it starts: resolve, collect, pack modules, pack project and
    write, those of its kind. Nothing is asked: what is built is the request."""
    chosen = plan(request, folder)
    if chosen.kind == 'archive':
        assert chosen.project is not None
        progress('pack project')
        data = _project_archive(chosen.project, chosen.files)
        progress('write')
        name = f'{chosen.project}-{datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")}{archive.SUFFIX}'
        path = _folder() / name
        _written(path, lambda part: part.write_bytes(data))
        return Built(path, 'archive', chosen.project, (), ())
    carried = [item for item in _found() if item.id in chosen.modules]
    requirements, per_module = _requirements(carried)
    with tempfile.TemporaryDirectory() as temporary:
        vendored, compiled = _carry(requirements, per_module, Path(temporary), progress)
    progress('pack modules')
    package = resources.files('metaform')
    system = {item.id for item in carried if item.place == 'system'}
    packed = _source(package, system)
    files = dict(packed)
    for item in carried:
        if item.place != 'system':
            files.update({name: data for name, data in _walk(item.path, f'metaform/modules/{item.id}').items()
                          if name.split('/')[3] != 'tests'})
    told = [f'Packed from: {package}']
    checkout = _checkout(folder) if folder is not None else None
    if checkout is not None and isinstance(package, Path) and \
            (checkout / 'src' / NAME).resolve() != package.resolve():
        there = _source(checkout / 'src' / NAME, system)
        differ = sum(packed.get(name) != there.get(name) for name in packed.keys() | there.keys())
        if differ:
            told.append(f'Not packed: the checkout at {checkout} differs from that copy in {differ} '
                        f'file{"" if differ == 1 else "s"}. To pack the checkout, run uv run metaform build in '
                        f'{checkout}.')
    files['__main__.py'] = bootstrap().encode()
    files.update(vendored)
    prompt = None
    if chosen.kind == 'project':
        assert chosen.project is not None
        progress('pack project')
        prompt = wrapped(chosen.task, WHEEL, chosen.project)
        files[archive.CARRIED_ARCHIVE] = _project_archive(chosen.project, chosen.files)
        files[archive.CARRIED_PROMPT] = prompt.encode('utf-8')
    progress('write')
    info = f'{NAME}-{__version__}.dist-info'
    files[f'{info}/METADATA'] = ('Metadata-Version: 2.1\n'
                                 f'Name: {NAME}\n'
                                 f'Version: {__version__}\n'
                                 f'Requires-Python: {_build_info.REQUIRES_PYTHON}\n'
                                 + ''.join(f'Requires-Dist: {requirement}\n' for requirement in requirements)).encode()
    files[f'{info}/WHEEL'] = ('Wheel-Version: 1.0\n'
                              f'Generator: metaform {__version__}\n'
                              'Root-Is-Purelib: true\n'
                              'Tag: py3-none-any\n').encode()
    files[f'{info}/entry_points.txt'] = ('[console_scripts]\nmetaform = metaform.cli:main\n\n[metaform.modules]\n'
                                         + ''.join(f'{item.id} = metaform.modules.{item.id}\n'
                                                   for item in carried)).encode()
    record = ''.join(f'{name},{_digest(data)},{len(data)}\n' for name, data in sorted(files.items()))
    record += f'{info}/RECORD,,\n'
    files[f'{info}/RECORD'] = record.encode()
    target = _folder()
    wheel = target / WHEEL

    def zipped(part: Path) -> None:
        with zipfile.ZipFile(part, 'w', compression=zipfile.ZIP_DEFLATED) as written:
            for name in sorted(files):
                written.writestr(name, files[name])

    _written(wheel, zipped)
    if prompt is not None:
        home.write_private(target / 'prompt.md', prompt)
    readme = build_readme.readme(chosen.kind, WHEEL, carried, chosen.project, prompt is not None)
    bundle = target / f'{NAME}-{__version__}-{chosen.kind}.zip'
    inside = bundle.stem

    def bundled(part: Path) -> None:
        with zipfile.ZipFile(part, 'w', compression=zipfile.ZIP_DEFLATED) as written:
            written.write(wheel, f'{inside}/{WHEEL}')
            if prompt is not None:
                written.writestr(f'{inside}/prompt.md', prompt)
            written.writestr(f'{inside}/README.md', readme)

    _written(bundle, bundled)
    if chosen.kind in ('installer', 'full'):  # what install registers; a project wheel is for a remote agent, MCP-010
        home.set_meta('last_build', str(wheel))
    return Built(wheel, chosen.kind, chosen.project, tuple(item.id for item in carried), tuple(told + compiled),
                 prompt, bundle)


def build(folder: Path | None = None) -> tuple[Path, list[str]]:
    """Write the wheel of the modules on at home, BASE-041; returns its path and the notes to print: the copy packed,
    then a checkout at or above `folder` that differs from it, then the compiled dependencies."""
    built = make(Request(), folder)
    return built.path, list(built.notes)
