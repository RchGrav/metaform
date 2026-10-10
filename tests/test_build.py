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

from metaform import _build_info

pytestmark = pytest.mark.kind('simulation')

ROOT = Path(__file__).parents[1]


def build(run, *modules_off):
    for module in modules_off:
        run('disable', module)
    out = run('build').stdout
    wheels = [Path(line.split(':', 1)[1].strip()) for line in out.splitlines() if line.startswith('Wheel:')]
    assert len(wheels) == 1, out
    return wheels[0], out


def shared(tmp_path_factory, name, *modules_off):
    """A wheel built once for the whole run with these modules off, and its build output: the first worker to ask
    builds it in a home of its own, and every other test, on any worker, reads the same one. Building it per test
    repeated the same work."""
    import json
    import time
    base = tmp_path_factory.getbasetemp()
    root = base.parent if os.environ.get('PYTEST_XDIST_WORKER') else base  # the folder all workers of this run share
    result, lock = root / f'wheel-{name}.json', root / f'wheel-{name}.lock'
    deadline = time.monotonic() + 600
    while not result.exists():
        try:
            handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            assert time.monotonic() < deadline, f'the shared {name} wheel was never built'
            time.sleep(0.1)
            continue
        said = {}
        try:
            folder = root / f'wheel-{name}'
            folder.mkdir()
            env = {**os.environ, 'METAFORM_HOME': str(folder / 'home')}
            for module in modules_off:
                subprocess.run([sys.executable, '-m', 'metaform', 'disable', module], cwd=folder, env=env,
                               capture_output=True, check=True)
            done = subprocess.run([sys.executable, '-m', 'metaform', 'build'], cwd=folder, env=env,
                                  capture_output=True, text=True, encoding='utf-8', check=False)
            said = {'out': done.stdout, 'error': done.stderr if done.returncode else None}
        finally:
            os.close(handle)
            written = root / f'wheel-{name}.json.part'
            written.write_text(json.dumps(said or {'out': '', 'error': 'the build did not run'}), encoding='utf-8')
            written.replace(result)
    said = json.loads(result.read_text(encoding='utf-8'))
    assert said['error'] is None, said['error']
    wheels = [Path(line.split(':', 1)[1].strip()) for line in said['out'].splitlines() if line.startswith('Wheel:')]
    assert len(wheels) == 1, said['out']
    return wheels[0], said['out']


@pytest.fixture
def every_module(tmp_path_factory):
    """The wheel with every module carried."""
    return shared(tmp_path_factory, 'every')


@pytest.fixture
def map_only(tmp_path_factory):
    """The wheel without mcp, memory, intake and web."""
    return shared(tmp_path_factory, 'fewer', 'mcp', 'memory', 'intake', 'web')


def plain_env():
    """The environment for a separate Python, such as a venv's, without this run's PYTHONPATH, so it imports its own
    copy of Metaform and not the one under test."""
    return {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}


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
    wheel, _ = build(run, 'mcp', 'memory', 'intake', 'web', 'fork')  # fork ships enabled, BASE-017
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
def test_a_wheel_runs_directly_from_itself(home, tmp_path, map_only):
    wheel, _ = map_only
    folder = tmp_path / 'proj'
    folder.mkdir()
    env = {k: v for k, v in os.environ.items() if k != 'METAFORM_HOME'}
    env['HOME'] = env['USERPROFILE'] = str(tmp_path / 'user')
    env['PYTHONPATH'] = ''
    (tmp_path / 'user').mkdir()
    status = subprocess.run([sys.executable, '-I', str(wheel)], cwd=folder, env=env, capture_output=True, text=True, encoding='utf-8', check=False)
    assert status.returncode == 0, status.stderr
    normal = tmp_path / 'user' / '.metaform'
    assert f'Home: {normal}' in status.stdout.splitlines()
    subprocess.run([sys.executable, '-I', str(wheel), 'add', 'project', 'proj', str(folder)], cwd=folder, env=env,
                   check=True, capture_output=True)
    # Metaform as installed in this environment, run without the wheel, reads the same data folder.
    installed = subprocess.run([sys.executable, '-m', 'metaform', 'list', 'projects'], cwd=tmp_path, env=env,
                               capture_output=True, text=True, encoding='utf-8', check=False)
    assert installed.returncode == 0, installed.stderr
    assert 'proj' in installed.stdout.split()
    assert not (normal / 'wheels').exists()
    layers = subprocess.run([sys.executable, '-I', str(wheel), 'query', 'layers'], cwd=folder, env=env,
                            capture_output=True, text=True, encoding='utf-8', check=False)
    assert layers.returncode == 0, layers.stderr
    document = tmp_path / 'export.json'
    for args in (('help',), ('set', '--layers', ''), ('export', f'file={document}'), ('import', str(document))):
        done = subprocess.run([sys.executable, '-I', str(wheel), *args], cwd=folder, env=env, capture_output=True,
                              text=True, encoding='utf-8', check=False)
        assert done.returncode == 0, (args, done.stderr)
    assert not (home / 'projects').exists() or not any((home / 'projects').iterdir())  # nothing reached this home


@pytest.mark.req('BASE-024')
def test_a_wheel_run_on_an_older_python_says_what_it_needs(tmp_path, map_only):
    wheel, _ = map_only
    with zipfile.ZipFile(wheel) as packed:
        bootstrap = packed.read('__main__.py').decode()
    needs = repr(tuple(int(part) for part in _build_info.REQUIRES_PYTHON.removeprefix('>=').split('.')))
    assert f'NEEDS = {needs}' in bootstrap
    # No older Python is at hand on every runner, so the check is shown by raising what it needs.
    script = tmp_path / '__main__.py'
    script.write_text(bootstrap.replace(f'NEEDS = {needs}', 'NEEDS = (99,)'), encoding='utf-8')
    done = subprocess.run([sys.executable, '-I', str(script)], capture_output=True, text=True, encoding='utf-8',
                          check=False)
    assert done.returncode == 1
    assert done.stderr.startswith('Metaform needs Python 99 or newer; this is Python ')
    assert 'Traceback' not in done.stderr


@pytest.mark.req('BASE-041')
def test_a_build_names_the_copy_it_packs(every_module):
    _, out = every_module
    import metaform
    assert f'Packed from: {Path(metaform.__file__).parent}' in out.splitlines()


@pytest.mark.req('BASE-041')
def test_an_installed_build_run_in_a_checkout_says_the_checkout_is_not_packed(home, tmp_path, map_only):
    wheel, _ = map_only
    environment = tmp_path / 'venv'
    subprocess.run([sys.executable, '-m', 'venv', str(environment)], check=True)
    python = environment / ('Scripts' if os.name == 'nt' else 'bin') / ('python.exe' if os.name == 'nt' else 'python')
    result = subprocess.run([str(python), '-m', 'pip', 'install', '--no-deps', '--no-index', str(wheel)],
                            capture_output=True, text=True, encoding='utf-8', env=plain_env(), check=False)
    assert result.returncode == 0, result.stderr  # the wheel installs with pip, BASE-041
    version = subprocess.run([str(python), '-m', 'metaform', '--version'], capture_output=True, text=True,
                             encoding='utf-8', env=plain_env(), check=False)
    assert version.stdout.startswith('metaform ')
    installed = Path(subprocess.run([str(python), '-c', 'import metaform; print(metaform.__file__)'],
                                    capture_output=True, text=True, encoding='utf-8', env=plain_env(),
                                    check=True).stdout.strip()).parent
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
                              encoding='utf-8', env={**plain_env(), 'METAFORM_HOME': str(home)}, check=False)
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
def test_a_compiled_dependency_stays_a_requirement_and_is_named(every_module):
    wheel, out = every_module
    with zipfile.ZipFile(wheel) as archive:
        vendored = {name.split('/')[2] for name in archive.namelist() if name.startswith('metaform/_vendor/')}
    assert not any(name.startswith('pydantic_core') for name in vendored)
    assert 'Requires-Dist: mcp>=2.2' in metadata(wheel)
    assert re.search(r'pydantic.core.*mcp', out)


@pytest.mark.req('BASE-041')
@pytest.mark.req('BASE-021')
def test_uvx_runs_the_built_wheel(tmp_path, every_module):
    import shutil
    uvx = shutil.which('uvx')
    if uvx is None:
        pytest.fail('uvx is required to check the entry points of a built wheel, MCP-013')
    wheel, _ = every_module
    result = subprocess.run([uvx, '--from', str(wheel), 'metaform', '--version'], capture_output=True, text=True, encoding='utf-8',
                            cwd=tmp_path, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().startswith('metaform ')
    from metaform.probe import probe
    served = probe([uvx, '--from', str(wheel), 'metaform', 'mcp', 'serve'], cwd=tmp_path, limit=180)
    assert served.ok and served.tools > 0, served.reason


def _mapped(folder):
    """A registered project proj with a file and a small finished map: a cook whose dish timer serves them."""
    from metaform.data import Store
    store = Store('proj')
    with store.atomic():
        intake = store.layer('intake-1', 'intake', 'The functional map.', kind='intake', mutable=False,
                             hideable=False, provenance={'module': 'intake'}, ready=True)
        store.add_element(intake.name, 'exterior.cook', name_length=1, role='CQU')
        store.add_element(intake.name, 'code.timer.kitchen', name_length=2, role='DE', name='dish timer')
        store.add_join(intake.name, 'exterior.cook', ['code.timer.kitchen'], purpose='Know when food is done.',
                       ef='Counts down.')


@pytest.mark.req('BASE-060')
def test_a_project_wheel_onboards_a_remote_agent_and_its_return_imports_as_a_new_layer(run, home, tmp_path):
    import xml.etree.ElementTree as ET
    folder = tmp_path / 'proj'
    folder.mkdir()
    (folder / 'main.py').write_text('print("hi")\n', encoding='utf-8')
    run('add', 'project', 'proj', str(folder))
    _mapped(folder)
    out = run('build', 'kind=project', 'shape=map', cwd=folder).stdout
    wheel = Path(next(line.split(': ', 1)[1] for line in out.splitlines() if line.startswith('Wheel: ')))
    assert 'Modules: map' in out.splitlines()
    remote, there = tmp_path / 'remote', tmp_path / 'remote-home'
    remote.mkdir()
    env = {**plain_env(), 'METAFORM_HOME': str(there)}

    def wheel_run(*args):
        done = subprocess.run([sys.executable, '-I', str(wheel), *args], cwd=remote, env=env, capture_output=True,
                              text=True, encoding='utf-8', check=False)
        assert done.returncode == 0, done.stdout + done.stderr
        return done.stdout

    first = wheel_run()
    onboarding = ET.parse(ROOT / 'src' / 'metaform' / 'resources' / 'prompts.xml').getroot().find('remote_onboarding')
    assert onboarding is not None and onboarding.text.splitlines()[0] in first
    assert 'Imported the project proj' in first and (remote / 'main.py').read_text(encoding='utf-8') == 'print("hi")\n'
    assert "## The map's entry" in first and 'code.timer.kitchen' in first.split("## The map's entry")[1]
    again = wheel_run()
    assert 'nothing was imported again' in again and 'Imported the project' not in again
    wheel_run('map', 'knowledge', 'op=add-item', 'node=element:code.timer.kitchen', 'value="Rings twice."')
    (remote / 'main.py').write_text('print("hello")\n', encoding='utf-8')
    (remote / 'notes.txt').write_text('new\n', encoding='utf-8')
    returned = wheel_run('return', 'note=Changed the greeting.')
    archive = Path(next(line.split(': ', 1)[1] for line in returned.splitlines() if line.startswith('Archive: ')))
    assert 'Changes: one file changed, one new, no removed.' in returned.splitlines()
    imported = run('import', str(archive), cwd=folder).stdout
    assert 'layers added: one' in imported.splitlines() and 'things added: one' in imported.splitlines()
    from metaform.data import Store
    layers = {layer.name for layer in Store('proj').layers(limit=0).results}
    working = next(name for name in layers if name.startswith('remote_'))
    assert working in imported
    review = archive.with_name(archive.name[:-len('.zip')])
    assert '+print("hello")' in (review / 'changes.diff').read_text(encoding='utf-8')
    assert (review / 'note.txt').read_text(encoding='utf-8') == 'Changed the greeting.'
    assert (folder / 'main.py').read_text(encoding='utf-8') == 'print("hi")\n'  # nothing applied to the project


@pytest.mark.req('BASE-060')
@pytest.mark.req('STORE-029')
def test_an_archive_readable_only_by_a_newer_metaform_is_refused_and_nothing_is_imported(run, home, tmp_path):
    import io
    import json

    from metaform import archive
    from metaform.data import export_document
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    _mapped(folder)
    packed = archive.packed('project', 'proj', export_document(['proj']), origin=None)
    rewritten = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(packed)) as source, zipfile.ZipFile(rewritten, 'w') as target:
        for name in source.namelist():
            data = source.read(name)
            if name == archive.MANIFEST:
                manifest = json.loads(data)
                manifest.update(archive_version=archive.ARCHIVE_VERSION + 1, compatible_from=archive.ARCHIVE_VERSION + 1,
                                metaform='2099.1.1.1')
                data = json.dumps(manifest).encode()
            target.writestr(name, data)
    file = tmp_path / 'newer.zip'
    file.write_bytes(rewritten.getvalue())
    other = tmp_path / 'other-home'
    done = run('import', str(file), ok=False, env={'METAFORM_HOME': str(other)})
    assert done.returncode == 2
    assert f'which a Metaform reads from archive version {archive.ARCHIVE_VERSION + 1}' in done.stderr
    assert 'Next: install Metaform 2099.1.1.1 or newer' in done.stderr
    assert 'proj' not in run('list', 'projects', env={'METAFORM_HOME': str(other)}).stdout.split()


@pytest.mark.req('BASE-060')
def test_a_project_archive_never_carries_what_a_link_reaches_outside_the_project(tmp_path):
    """A project's files go to another machine; a link in the folder to a file outside it, such as a key, is not the
    project's, and what it reaches is never packed."""
    from metaform import archive
    folder, outside = tmp_path / 'proj', tmp_path / 'secret.txt'
    folder.mkdir()
    (folder / 'main.py').write_text('print("hi")\n', encoding='utf-8')
    outside.write_text('private\n', encoding='utf-8')
    try:
        (folder / 'key.txt').symlink_to(outside)
    except OSError:
        pytest.skip('this system does not let the test make a link')
    assert set(archive.project_files(folder)) == {'main.py'}
