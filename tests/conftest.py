import os
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
    def invoke(*args, cwd=None, ok=True):
        folder = Path(cwd or tmp_path)
        folder.mkdir(parents=True, exist_ok=True)
        result = subprocess.run([sys.executable, '-m', 'metaform', *args], cwd=folder,
                                env={**os.environ, 'METAFORM_HOME': str(home)},
                                capture_output=True, text=True)
        if ok and result.returncode != 0:
            raise AssertionError(f'metaform {" ".join(args)} failed ({result.returncode}):\n'
                                 f'{result.stdout}{result.stderr}')
        return result
    return invoke
