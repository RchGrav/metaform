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
                                capture_output=True, text=True, input=input)
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
