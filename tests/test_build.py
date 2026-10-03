"""`metaform build` and the directly run wheel, BASE-021 to BASE-026, BASE-041 and BASE-042."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.kind('simulation')

ROOT = Path(__file__).parents[1]


def build(run, *modules_off):
    for module in modules_off:
        run('disable', module)
    out = run('build').stdout
    wheels = [Path(line.split(':', 1)[1].strip()) for line in out.splitlines() if line.startswith('Wheel:')]
    assert len(wheels) == 1, out
    return wheels[0], out


def metadata(wheel):
    with zipfile.ZipFile(wheel) as archive:
        info = next(name for name in archive.namelist() if name.endswith('.dist-info/METADATA'))
        return archive.read(info).decode()


@pytest.mark.req('BASE-026')
def test_a_build_with_no_modules_is_pure_python(run):
    wheel, out = build(run, 'map', 'mcp', 'memory', 'intake', 'web')
    assert wheel.name.endswith('-py3-none-any.whl')
    # BUILD-QUESTIONS Q24: wcwidth, which prompt_toolkit needs, now ships compiled; it must be named, not carried.
    compiled = [line.split(':')[0] for line in out.splitlines() if ': compiled, not carried' in line]
    assert all('needed by' in line for line in out.splitlines() if ': compiled' in line)
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
    assert not any(name.endswith(('.so', '.pyd', '.dylib')) for name in names)
    assert any(name.startswith('metaform/_vendor/prompt_toolkit/') for name in names)
    assert not any(name.startswith(f'metaform/_vendor/{dist}/') for dist in compiled for name in names)


@pytest.mark.req('BASE-026')
def test_the_chassis_depends_only_on_pure_python_packages():
    from metaform import _build_info
    declared = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['dependencies']
    assert list(_build_info.CHASSIS_DEPENDENCIES) == declared
    assert not any(name.split('>')[0].split('=')[0].strip() == 'mcp' for name in declared)


@pytest.mark.req('BASE-041')
@pytest.mark.req('BASE-022')
def test_a_build_carries_only_the_enabled_modules_and_their_dependencies(run, home):
    wheel, _ = build(run, 'mcp', 'memory', 'intake', 'web')
    assert re.fullmatch(r'metaform-.+-py3-none-any\.whl', wheel.name)
    assert wheel.parent.parent == home / 'builds'
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
    modules = {name.split('/')[2] for name in names if name.startswith('metaform/modules/') and name.count('/') > 2}
    assert modules == {'map'}
    assert not [name for name in names if name.startswith('metaform/modules/') and '/tests/' in name]
    requires = [line.split(': ', 1)[1] for line in metadata(wheel).splitlines() if line.startswith('Requires-Dist: ')]
    from metaform import _build_info
    assert requires == list(_build_info.CHASSIS_DEPENDENCIES)
    assert '__main__.py' in names
    entry = zipfile.ZipFile(wheel).read(next(name for name in names if name.endswith('entry_points.txt'))).decode()
    assert 'metaform = metaform.cli:main' in entry and 'map = metaform.modules.map' in entry


@pytest.mark.req('BASE-042')
@pytest.mark.req('BASE-024')
@pytest.mark.req('BASE-025')
@pytest.mark.req('STORE-030')
def test_a_wheel_runs_directly_from_itself(run, home, tmp_path):
    wheel, _ = build(run, 'mcp', 'memory', 'intake', 'web')
    folder = tmp_path / 'proj'
    folder.mkdir()
    env = {k: v for k, v in os.environ.items() if k != 'METAFORM_HOME'}
    env['HOME'] = env['USERPROFILE'] = str(tmp_path / 'user')
    env['PYTHONPATH'] = ''
    (tmp_path / 'user').mkdir()
    status = subprocess.run([sys.executable, '-I', str(wheel)], cwd=folder, env=env, capture_output=True, text=True, encoding='utf-8')
    assert status.returncode == 0, status.stderr
    normal = tmp_path / 'user' / '.metaform'
    assert f'Home: {normal}' in status.stdout.splitlines()
    subprocess.run([sys.executable, '-I', str(wheel), 'add', 'project', 'proj', str(folder)], cwd=folder, env=env,
                   check=True, capture_output=True)
    # Metaform as installed in this environment, run without the wheel, reads the same data folder.
    installed = subprocess.run([sys.executable, '-m', 'metaform', 'list', 'projects'], cwd=tmp_path, env=env,
                               capture_output=True, text=True, encoding='utf-8')
    assert installed.returncode == 0, installed.stderr
    assert 'proj' in installed.stdout.split()
    assert not (normal / 'wheels').exists()
    layers = subprocess.run([sys.executable, '-I', str(wheel), 'query', 'layers'], cwd=folder, env=env,
                            capture_output=True, text=True, encoding='utf-8')
    assert layers.returncode == 0, layers.stderr
    document = tmp_path / 'export.json'
    for args in (('help',), ('set', '--layers', ''), ('export', f'file={document}'), ('import', str(document))):
        done = subprocess.run([sys.executable, '-I', str(wheel), *args], cwd=folder, env=env, capture_output=True,
                              text=True, encoding='utf-8')
        assert done.returncode == 0, (args, done.stderr)
    assert not (home / 'projects').exists() or not any((home / 'projects').iterdir())  # nothing reached this home


@pytest.mark.req('BASE-041')
def test_the_wheel_installs_with_pip(run, tmp_path):
    wheel, _ = build(run, 'mcp', 'memory', 'intake', 'web')
    environment = tmp_path / 'venv'
    subprocess.run([sys.executable, '-m', 'venv', str(environment)], check=True)
    python = environment / ('Scripts' if os.name == 'nt' else 'bin') / ('python.exe' if os.name == 'nt' else 'python')
    result = subprocess.run([str(python), '-m', 'pip', 'install', '--no-deps', '--no-index', str(wheel)],
                            capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
    version = subprocess.run([str(python), '-m', 'metaform', '--version'], capture_output=True, text=True, encoding='utf-8')
    assert version.stdout.startswith('metaform ')


@pytest.mark.req('BASE-041')
def test_a_build_names_the_copy_it_packs(run):
    _, out = build(run)
    import metaform
    assert f'Packed from: {Path(metaform.__file__).parent}' in out.splitlines()


@pytest.mark.req('BASE-041')
def test_an_installed_build_run_in_a_checkout_says_the_checkout_is_not_packed(run, home, tmp_path):
    wheel, _ = build(run, 'mcp', 'memory', 'intake', 'web')
    environment = tmp_path / 'venv'
    subprocess.run([sys.executable, '-m', 'venv', str(environment)], check=True)
    python = environment / ('Scripts' if os.name == 'nt' else 'bin') / ('python.exe' if os.name == 'nt' else 'python')
    result = subprocess.run([str(python), '-m', 'pip', 'install', '--no-deps', '--no-index', str(wheel)],
                            capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
    installed = Path(subprocess.run([str(python), '-c', 'import metaform; print(metaform.__file__)'],
                                    capture_output=True, text=True, encoding='utf-8', check=True).stdout.strip()).parent
    checkout = tmp_path / 'checkout'
    (checkout / 'src').mkdir(parents=True)
    (checkout / 'pyproject.toml').write_text('[project]\nname = "metaform"\n', encoding='utf-8')
    import shutil
    # A checkout as it is in the repository: no _vendor, a tests folder in each module, and modules not carried.
    shutil.copytree(installed, checkout / 'src' / 'metaform', ignore=shutil.ignore_patterns('__pycache__', '_vendor'))
    inside = checkout / 'src' / 'metaform' / 'modules'
    (inside / 'map' / 'tests').mkdir()
    (inside / 'map' / 'tests' / 'test_map.py').write_text('# a test the wheel never carries\n', encoding='utf-8')
    (inside / 'web').mkdir()
    (inside / 'web' / '__init__.py').write_text('# a module this build does not carry\n', encoding='utf-8')

    def installed_build():
        done = subprocess.run([str(python), '-m', 'metaform', 'build'], cwd=inside, capture_output=True, text=True,
                              encoding='utf-8', env={**os.environ, 'METAFORM_HOME': str(home)})
        assert done.returncode == 0, done.stdout + done.stderr
        lines = done.stdout.splitlines()
        wheels = [Path(line.split(':', 1)[1].strip()) for line in lines if line.startswith('Wheel:')]
        assert len(wheels) == 1, done.stdout
        return lines, wheels[0]

    lines, _ = installed_build()
    assert f'Packed from: {installed}' in lines
    assert not [line for line in lines if line.startswith('Not packed:')]
    (checkout / 'src' / 'metaform' / 'cli.py').write_text('# changed in the checkout\n', encoding='utf-8')
    (inside / 'map' / 'added.py').write_text('', encoding='utf-8')
    lines, wheel = installed_build()
    assert f'Packed from: {installed}' in lines
    assert (f'Not packed: the checkout at {checkout} differs from that copy in 2 files. '
            f'To pack the checkout, run uv run metaform build in {checkout}.') in lines
    with zipfile.ZipFile(wheel) as archive:
        assert archive.read('metaform/cli.py') == (installed / 'cli.py').read_bytes()
        assert 'metaform/modules/map/added.py' not in archive.namelist()


@pytest.mark.req('BASE-041')
@pytest.mark.req('BASE-026')
def test_a_compiled_dependency_stays_a_requirement_and_is_named(run):
    wheel, out = build(run)
    with zipfile.ZipFile(wheel) as archive:
        vendored = {name.split('/')[2] for name in archive.namelist() if name.startswith('metaform/_vendor/')}
    assert not any(name.startswith('pydantic_core') for name in vendored)
    assert 'Requires-Dist: mcp>=2.2' in metadata(wheel)
    assert re.search(r'pydantic.core.*mcp', out)


@pytest.mark.req('BASE-041')
@pytest.mark.req('BASE-021')
def test_uvx_runs_the_built_wheel(run, tmp_path):
    import shutil
    uvx = shutil.which('uvx')
    if uvx is None:
        pytest.fail('uvx is required to check the entry points of a built wheel, MCP-013')
    wheel, _ = build(run)
    result = subprocess.run([uvx, '--from', str(wheel), 'metaform', '--version'], capture_output=True, text=True, encoding='utf-8',
                            cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().startswith('metaform ')
    from metaform.probe import probe
    served = probe([uvx, '--from', str(wheel), 'metaform', 'mcp', 'serve'], cwd=tmp_path, limit=180)
    assert served.ok and served.tools > 0, served.reason
