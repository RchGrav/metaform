"""Roundtables tests use dispatch's real shared participant naming provider."""
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _agent_name_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, run):
    """Enable the shipped provider on each isolated test folder, including unregistered engine homes."""
    from metaform.module import provided

    monkeypatch.chdir(tmp_path)
    if not provided(tmp_path, 'agent.name'):
        run('enable', 'dispatch', cwd=tmp_path)
