"""Fixtures shared by the chassis tests in tests/ and each module's own tests, QUAL-006."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def home(tmp_path, monkeypatch):
    """An isolated Metaform home; nothing touches ~/.metaform."""
    path = tmp_path / 'home'
    monkeypatch.setenv('METAFORM_HOME', str(path))
    return path


@pytest.fixture
def run(home, tmp_path):
    """Run the real CLI as a user would, from a chosen folder."""
    def invoke(*args, cwd=None, ok=True, input=None, env=None):
        folder = Path(cwd or tmp_path)
        folder.mkdir(parents=True, exist_ok=True)
        result = subprocess.run([sys.executable, '-m', 'metaform', *args], cwd=folder,
                                env={**os.environ, 'METAFORM_HOME': str(home), **(env or {})},
                                capture_output=True, text=True, encoding='utf-8', input=input)
        if ok and result.returncode != 0:
            raise AssertionError(f'metaform {" ".join(args)} failed ({result.returncode}):\n'
                                 f'{result.stdout}{result.stderr}')
        return result
    return invoke


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
    folder = Path(__file__).parent / 'specifications' / 'spec'
    ids = set()
    for path in folder.glob('0*.md'):
        ids.update(re.findall(r'^### ([A-Z]+-\d{3})\b', path.read_text(encoding='utf-8'), re.MULTILINE))
    return ids


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
