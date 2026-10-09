"""Fixtures shared by the chassis tests in tests/ and each module's own tests, QUAL-006."""
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# The whole test process, from collection on, lives in a home of its own: nothing a test or an import does reaches
# ~/.metaform. The `home` fixture gives each test a fresh one inside it. Found 2026-10-07: a read of the registry with
# no METAFORM_HOME set renamed every project's registry in the live home to the branch's layout.
if 'PYTEST_METAFORM_HOME' not in os.environ:
    os.environ['PYTEST_METAFORM_HOME'] = tempfile.mkdtemp(prefix='metaform-tests-')
os.environ['METAFORM_HOME'] = os.environ['PYTEST_METAFORM_HOME']

@pytest.fixture
def home(tmp_path, monkeypatch):
    """An isolated Metaform home; nothing touches ~/.metaform. The loader's cache of modules found, with each one's
    enabled state, starts and ends empty, so the modules one test's home enabled never reach the next."""
    from metaform import loader
    loader.reset()
    path = tmp_path / 'home'
    monkeypatch.setenv('METAFORM_HOME', str(path))
    yield path
    loader.reset()


@pytest.fixture
def run(home, tmp_path):
    """Run the real CLI as a user would, from a chosen folder."""
    from metaform import harness

    def invoke(*args, cwd=None, ok=True, input=None, env=None):
        folder = Path(cwd or tmp_path)
        folder.mkdir(parents=True, exist_ok=True)
        result = subprocess.run([sys.executable, '-m', 'metaform', *args], cwd=folder,
                                env={**os.environ, 'METAFORM_HOME': str(home), **(env or {})},
                                capture_output=True, text=True, encoding='utf-8', input=input, check=False)
        # MCP-028's notice is checked in test_provision; these assertions concern the command's own output.
        # The notice drops its first-run sentence once an intake exists, so both forms are stripped.
        for notice in (harness.NOTICE, harness.NOTICE.removeprefix(harness.FIRST_RUN)):
            result.stderr = result.stderr.removeprefix(f'Notice: {notice}\n')
        if ok and result.returncode != 0:
            raise AssertionError(f'metaform {" ".join(args)} failed ({result.returncode}):\n'
                                 f'{result.stdout}{result.stderr}')
        return result
    return invoke


@pytest.fixture
def dispatch_runners(run):
    """Detached test launches, recorded before assertions; Stop and verify they end even when the test fails."""
    import time

    from metaform.modules.dispatch import end_group
    from metaform.modules.dispatch.tests.test_dispatch import alive, end_agent, gone

    runners = []
    yield runners
    survived = []
    for started, folder, log in runners:
        pid = started['pid']
        try:
            # A start reply precedes session registration, so an early failure can reach Stop before the session.
            deadline = time.monotonic() + 10
            while alive(pid) and time.monotonic() < deadline:
                stopped = run('dispatch', 'stop', started['work_id'], cwd=folder, ok=False)
                if stopped.returncode == 0:
                    break
                time.sleep(0.05)
            deadline = time.monotonic() + 5
            while alive(pid) and time.monotonic() < deadline:
                time.sleep(0.05)
        finally:
            forced = alive(pid)
            if forced:
                end_group(pid)
            if not gone([pid, *end_agent(log, forced)]):
                survived.append(pid)
    assert not survived, f'detached test runners or their children survived: {survived}'


# The command lines of the processes a test home must not leave behind; matching them keeps a PID the system has
# since given to another process, such as an xdist worker with its own listener, from being ended.
SURVIVORS = ('-m metaform.modules.web.server ', '-m metaform dispatch ')


def pytest_sessionfinish(session):
    """No metaform web server or dispatch runner started under a test home outlives the test session: each records
    its PID in its home's run/web.json or run/listeners. One still alive fails the run and is ended, VIEW-002 and
    BASE-052. Under xdist only the controller checks, once every worker has finished."""
    import json
    import time

    if hasattr(session.config, 'workerinput'):
        return
    folder = getattr(getattr(session.config, '_tmp_path_factory', None), '_basetemp', None)
    if folder is None:  # the run made no temporary folder, so it started nothing under a test home
        return
    from metaform.modules.dispatch import command_line, end_group
    from metaform.modules.dispatch.tests.test_dispatch import alive

    pids = set()
    for path in [*folder.glob('**/run/web.json'), *folder.glob('**/run/listeners/*.json')]:
        try:
            pids.add(int(json.loads(path.read_text(encoding='utf-8'))['pid']))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    deadline = time.monotonic() + 5  # a server told to stop by the last teardown can still be exiting
    while True:
        said = {pid: ' '.join(command_line(pid)) for pid in pids if alive(pid)}
        left = {pid: words for pid, words in said.items() if any(one in words for one in SURVIVORS)}
        if not left or time.monotonic() >= deadline:
            break
        time.sleep(0.1)
    if not left:
        return
    for pid in left:
        end_group(pid)
    session.exitstatus = pytest.ExitCode.TESTS_FAILED
    reporter = session.config.pluginmanager.get_plugin('terminalreporter')
    if reporter is not None:
        reporter.write_line('Test homes left these metaform processes running; they are now ended:', red=True)
        for pid, words in left.items():
            reporter.write_line(f'  {pid} {words}', red=True)


@pytest.fixture
def project_folder(home, tmp_path):
    """A registered project named proj, whose folder is empty."""
    from metaform import home as metaform_home
    folder = tmp_path / 'proj'
    folder.mkdir()
    metaform_home.add_project('proj', folder)
    return folder


@pytest.fixture
def store(project_folder):
    """The data access object for the registered project proj."""
    from metaform.data import Store
    return Store('proj')


@pytest.fixture
def traced(monkeypatch):
    """Every SQL statement the data access object issues, with its values bound."""
    statements: list[str] = []
    real = sqlite3.connect

    def connect(*args, **kwargs):
        db = real(*args, **kwargs)
        db.set_trace_callback(statements.append)
        return db
    monkeypatch.setattr(sqlite3, 'connect', connect)
    return statements


@pytest.fixture
def unremovable():
    """Keep a file from being removed for the length of a block: held open on Windows, and elsewhere with write
    permission taken off its folder and given back afterwards. Root removes any file whatever its folder allows."""
    from contextlib import contextmanager
    if os.name != 'nt' and os.geteuid() == 0:
        pytest.skip('root can remove a file whatever its folder allows')

    @contextmanager
    def held(path):
        if os.name == 'nt':
            with open(path, 'rb'):
                yield
            return
        mode = path.parent.stat().st_mode
        path.parent.chmod(mode & ~0o222)
        try:
            yield
        finally:
            path.parent.chmod(mode)
    return held


@pytest.fixture
def user_module(home):
    """Write a module into the user place, `<home>/modules/<name>/__init__.py`."""
    import textwrap

    def write(name, body):
        folder = home / 'modules' / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / '__init__.py').write_text(textwrap.dedent(body))
        return folder
    return write


@pytest.fixture
def module_row(run):
    """One line of `metaform list modules` for a module id: id, state, place, summary or reason."""
    def row(identifier, cwd=None):
        for line in run('list', 'modules', cwd=cwd).stdout.splitlines():
            parts = line.split(None, 3)
            if parts and parts[0] == identifier:
                return parts
        return None
    return row


def _spec_ids():
    import re
    folder = Path(__file__).parent / 'specifications'
    ids = set()
    for path in folder.glob('0*.md'):
        ids.update(re.findall(r'^### ([A-Z]+-\d{3})\b', path.read_text(encoding='utf-8'), re.MULTILINE))
    return ids


@pytest.hookimpl(tryfirst=True)  # before xdist reads the browser groups below
def pytest_collection_modifyitems(config, items):
    """Every test names the requirement it protects and what kind of run it is, QUAL-009, QUAL-014 and E4."""
    known = _spec_ids()
    problems = []
    for item in items:
        requirements = [mark.args[0] for mark in item.iter_markers('req')]
        kinds = [mark.args[0] for mark in item.iter_markers('kind')]
        if not requirements:
            problems.append(f'{item.nodeid}: no @pytest.mark.req')
        problems += [f'{item.nodeid}: {name} is not a record of the spec' for name in requirements if name not in known]
        if not kinds or any(kind not in ('fixture', 'simulation', 'real') for kind in kinds):
            problems.append(f'{item.nodeid}: no @pytest.mark.kind of fixture, simulation or real')
    if problems:
        raise pytest.UsageError('Tests without a traced requirement:\n' + '\n'.join(problems))
    # Each browser test draws WebGL in software, which is heavy on the processor; spread over every core at once
    # they time out, so they run in BROWSERS groups, at most that many at a time, beside everything else.
    # They are also marked browser, and the default run leaves them out (addopts -m "not browser"): they take most of a
    # full run's time, so they run only when the page or the web server changed, with pytest -m browser.
    browsers = [item for item in items if 'browser' in getattr(item, 'fixturenames', ())]
    for number, item in enumerate(browsers):
        item.add_marker(pytest.mark.browser)
        item.add_marker(pytest.mark.xdist_group(f'browser-{number % BROWSERS}'))


BROWSERS = 4
