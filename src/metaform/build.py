"""`metaform build`: one wheel of the chassis and the enabled modules, BASE-041 and BASE-022.

The wheel is written with `zipfile` from the installed package, so no source
tree is needed. It carries the chassis, each enabled module as a system module,
a root `__main__.py` that runs it directly, BASE-042, and every pure-Python
dependency under `metaform/_vendor/`. A compiled dependency is not carried: it
stays in `Requires-Dist`, and the build names it with the module that needs it.
"""
from __future__ import annotations

import base64
import hashlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

from . import __version__, _build_info, home, loader
from .errors import Stop

NAME = 'metaform'
COMPILED = ('.so', '.pyd', '.dylib')

BOOTSTRAP = '''"""Run Metaform from this wheel, with its carried dependencies and its own home, BASE-042."""
import os
import sys
from pathlib import Path

WHEEL = os.path.abspath(os.path.dirname(__file__))
VENDOR = os.path.join(WHEEL, 'metaform', '_vendor')


def _provides_metaform(entry):
    try:
        return os.path.isfile(os.path.join(entry, 'metaform', '__init__.py'))
    except (TypeError, ValueError, OSError):
        return False


sys.path[:] = [WHEEL, VENDOR] + [entry for entry in sys.path
                                 if entry not in (WHEEL, VENDOR) and not _provides_metaform(entry)]
if not os.environ.get('METAFORM_HOME'):
    os.environ['METAFORM_HOME'] = str(Path.home() / '.metaform' / 'wheels' / '{name}-{version}')
os.environ['METAFORM_WHEEL'] = WHEEL

from metaform.cli import main  # noqa: E402  the path must be set first

raise SystemExit(main())
'''


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


def _requirements() -> tuple[list[str], dict[str, list[str]]]:
    """The chassis's dependencies, then each carried module's own `DEPENDENCIES`, duplicates removed."""
    per_module: dict[str, list[str]] = {'chassis': list(_build_info.CHASSIS_DEPENDENCIES)}
    for item in loader.discover():
        if item.module is not None and item.declared is not None:
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
        result = subprocess.run([uv, *args], capture_output=True, text=True, timeout=UV_TIMEOUT)
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


def _carry(requirements: list[str], per_module: dict[str, list[str]], work: Path) -> tuple[dict[str, bytes],
                                                                                         list[str]]:
    """Pure-Python distributions under metaform/_vendor/, and one note per compiled distribution left out."""
    if not requirements:
        return {}, []
    _pinned(requirements, work, 'all')
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
            if source.is_file() and '__pycache__' not in Path(path).parts and not path.startswith('..'):
                files[f'metaform/_vendor/{Path(path).as_posix()}'] = source.read_bytes()
    return files, notes


def _digest(data: bytes) -> str:
    return 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()


def build() -> tuple[Path, list[str]]:
    """Write the wheel; returns its path and the notes about compiled dependencies."""
    requirements, per_module = _requirements()
    package = resources.files('metaform')
    files: dict[str, bytes] = {}
    for name, data in _walk(package, 'metaform').items():
        parts = name.split('/')
        if parts[1] == 'modules' and len(parts) > 3:
            continue
        if parts[1] == '_vendor':
            continue
        files[name] = data
    carried = [item for item in loader.discover() if item.module is not None]
    for item in carried:
        files.update({name: data for name, data in _walk(item.path, f'metaform/modules/{item.id}').items()
                      if name.split('/')[3] != 'tests'})
    files['__main__.py'] = BOOTSTRAP.replace('{name}', NAME).replace('{version}', __version__).encode()
    with tempfile.TemporaryDirectory() as temporary:
        vendored, notes = _carry(requirements, per_module, Path(temporary))
    files.update(vendored)
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
    stamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
    folder = home.home() / 'builds' / stamp
    folder.mkdir(parents=True, exist_ok=True)
    wheel = folder / f'{NAME}-{__version__}-py3-none-any.whl'
    with zipfile.ZipFile(wheel, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            archive.writestr(name, files[name])
    home.set_meta('last_build', str(wheel))
    return wheel, notes
