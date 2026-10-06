"""A variation is kept as what differs from its origin, PROJ-026, and a packet's own scripts expand it, PROJ-027.

The same cases are expanded by Python, by the bash script and by the PowerShell script, and each must give back the
work byte for byte. The scripts use nothing a system lacks: no git and no patch command.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


class _Vary:
    """The module, imported when a test first uses it. Imported as this file is collected, it would declare the
    packet's setting for every test of the run, and the module ships disabled."""

    def __getattr__(self, name):
        if name.startswith('_') or name in ('pytestmark', 'obj'):  # pytest looking the object over as it collects
            raise AttributeError(name)
        from metaform.modules.packet import vary
        return getattr(vary, name)


vary = _Vary()

pytestmark = pytest.mark.kind('fixture')

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'  # beside the module, found without importing it
ORIGIN = {
    'main.py': b'import sys\n\n\ndef main():\n    print("one")\n    print("two")\n    return 0\n\n\nsys.exit(main())\n',
    'long.txt': ''.join(f'line {number}\n' for number in range(1, 61)).encode(),
    'notes/readme.md': b'# Notes\n\nFirst.\nSecond.\n',
    'no-newline.txt': b'alpha\nbeta\ngamma',
    'windows.txt': b'one\r\ntwo\r\nthree\r\n',
    'gone.txt': b'this file is removed\n',
    'same.txt': b'never touched\n',
    'logo.png': b'\x89PNG\r\n\x1a\n' + bytes(range(256)),
    'same.bin': bytes([0, 1, 2, 3, 0, 255]),
    'spaced name.txt': b'a\nb\n',
}
WORK = {
    'main.py': b'import sys\n\n\ndef main():\n    print("one")\n    print("2")\n    print("three")\n    return 0\n\n\nsys.exit(main())\n',
    'long.txt': ''.join(('changed 3\n' if number == 3 else '' if number == 30 else f'line {number}\n')
                        + ('added after 45\n' if number == 45 else '') for number in range(1, 61)).encode(),
    'notes/readme.md': b'# Notes\n\nFirst.\nSecond.\nThird.\n',
    'no-newline.txt': b'alpha\nBETA\ngamma',
    'windows.txt': b'one\r\n2\r\nthree\r\n',
    'same.txt': b'never touched\n',
    'logo.png': b'\x89PNG\r\n\x1a\n' + bytes(reversed(range(256))),
    'same.bin': bytes([0, 1, 2, 3, 0, 255]),
    'spaced name.txt': b'a\nb\nc',
    'new/made.py': b'print("new")\n',
    'new/empty.txt': b'',
    'new/icon.bin': bytes([9, 0, 9]),
}


def written(folder: Path, files: dict[str, bytes]) -> Path:
    for name, body in files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(body)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def read(folder: Path) -> dict[str, bytes]:
    return {path.relative_to(folder).as_posix(): path.read_bytes() for path in sorted(folder.rglob('*'))
            if path.is_file()}


def powershell() -> str | None:
    return os.environ.get('METAFORM_PWSH') or shutil.which('pwsh') or shutil.which('powershell')


def commands(origin: Path, variation: Path, out: Path) -> dict[str, list[str] | None]:
    shell, bash = powershell(), shutil.which('bash')
    return {'bash': [bash, str(SCRIPTS / 'expand.sh'), str(origin), str(variation), str(out)] if bash else None,
            'powershell': [shell, '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
                           str(SCRIPTS / 'expand.ps1'), '-Origin', str(origin), '-Variation', str(variation),
                           '-Output', str(out)] if shell else None}


@pytest.fixture
def kept(tmp_path):
    """An origin on disk, and the work kept as a variation of it."""
    origin = written(tmp_path / 'origin', ORIGIN)
    variation = written(tmp_path / 'fabba167bafe0001', vary.variation(ORIGIN, WORK))
    return tmp_path, origin, variation


@pytest.mark.req('PROJ-026')
def test_a_variation_holds_a_diff_of_the_text_and_whole_copies_of_the_binaries_that_changed(kept):
    _, _, variation = kept
    held = read(variation)
    assert sorted(name for name in held if name.startswith('files/')) == ['files/logo.png', 'files/new/icon.bin']
    assert held['files/logo.png'] == WORK['logo.png']  # whole, never a diff
    diff = held['changes.diff'].decode('utf-8')
    assert '--- a/main.py' in diff and '+    print("three")' in diff
    assert 'same.txt' not in diff and 'same.bin' not in diff and 'logo.png' not in diff
    assert held['removed.txt'].decode('utf-8').split('\n') == ['gone.txt', '']
    assert 'GIT binary patch' not in diff and 'Binary files' not in diff


@pytest.mark.req('PROJ-026')
def test_python_expands_a_variation_to_the_work_byte_for_byte(kept):
    _, _, variation = kept
    assert vary.expanded(ORIGIN, read(variation)) == WORK


@pytest.mark.req('PROJ-027')
@pytest.mark.parametrize('shell', ['bash', 'powershell'])
def test_the_packets_script_expands_a_variation_to_the_work_byte_for_byte(kept, shell):
    folder, origin, variation = kept
    command = commands(origin, variation, folder / 'out')[shell]
    if command is None:
        pytest.skip(f'{shell} is not on this system')
    done = subprocess.run(command, capture_output=True, text=True, check=False, env={'PATH': os.environ['PATH']})
    assert done.returncode == 0, done.stdout + done.stderr
    assert read(folder / 'out') == WORK
    assert read(origin) == ORIGIN  # the origin is never written to


@pytest.mark.req('PROJ-027')
@pytest.mark.parametrize('shell', ['bash', 'powershell'])
def test_the_script_stops_when_the_origin_is_not_the_one_the_diff_was_taken_from(kept, shell):
    """A diff applies at the lines it names or not at all; the script never searches for a place that fits."""
    folder, origin, variation = kept
    (origin / 'main.py').write_bytes(ORIGIN['main.py'].replace(b'"two"', b'"deux"'))
    command = commands(origin, variation, folder / 'out')[shell]
    if command is None:
        pytest.skip(f'{shell} is not on this system')
    done = subprocess.run(command, capture_output=True, text=True, check=False, env={'PATH': os.environ['PATH']})
    assert done.returncode != 0 and 'main.py' in done.stdout + done.stderr


@pytest.mark.req('PROJ-027')
def test_the_scripts_call_on_no_git_and_no_patch_command():
    for name in ('expand.sh', 'expand.ps1'):
        words = (SCRIPTS / name).read_text(encoding='utf-8').lower().replace('#', ' # ').split()
        code = ' '.join(line.split('#')[0] for line in (SCRIPTS / name).read_text(encoding='utf-8').lower().splitlines())
        assert ' git ' not in f' {code} ' and ' patch ' not in f' {code} ', name
        assert words
