"""A harness is known by the parent folder of its binary, and the record of known harnesses lives in the home, MCP-028."""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('MCP-028')]

# Outside the system's temporary folder, where every tmp_path is; nothing is created here.
ROOT = Path(os.path.abspath(os.sep))
VERSIONS = ROOT / 'opt' / 'harness' / 'versions'
OTHER = ROOT / 'opt' / 'other' / 'bin' / 'other'


def dump(home: Path) -> list[str]:
    with sqlite3.connect(home / 'metaform.sqlite3') as db:
        return list(db.iterdump())


def test_a_new_version_in_the_same_folder_is_the_same_harness():
    from metaform import harness
    assert harness.key(VERSIONS / '2.0.1') == harness.key(VERSIONS / '2.0.2')
    assert harness.key(VERSIONS / '2.0.1') != harness.key(OTHER)


def test_the_parent_folder_is_the_harness_not_a_folder_above_it():
    from metaform import harness
    assert harness.key(VERSIONS / '2.0.1') != harness.key(VERSIONS.parent / 'bin' / '2.0.1')
    assert harness.key(VERSIONS / 'agent') == harness.key(VERSIONS / 'agent-helper')


@pytest.mark.skipif(os.path.normcase('A') != 'a', reason='this system does not fold case in paths')
def test_where_the_system_folds_case_the_folder_is_compared_folded():
    from metaform import harness
    assert harness.key(Path(str(VERSIONS).upper()) / '2.0.1') == harness.key(VERSIONS / '2.0.1')


def test_a_binary_under_the_temporary_folder_is_ignored(tmp_path):
    from metaform import harness
    temporary = Path(tempfile.gettempdir())
    assert harness.key(tmp_path / 'bin' / 'agent') is None
    assert harness.key(temporary / 'bin' / 'agent') is None
    assert harness.key(temporary / 'agent') is None
    assert harness.key(Path(str(temporary) + 'x') / 'bin' / 'agent') is not None


def test_a_linked_binary_is_known_by_the_folder_it_links_into(tmp_path, monkeypatch):
    from metaform import harness
    monkeypatch.setattr(tempfile, 'tempdir', str(tmp_path / 'temp'))
    versions = tmp_path / 'share' / 'versions'
    versions.mkdir(parents=True)
    (versions / '2.0.1').write_bytes(b'')
    link = tmp_path / 'bin' / 'agent'
    link.parent.mkdir()
    try:
        link.symlink_to(versions / '2.0.1')
    except OSError:
        pytest.skip('this system does not let the test make a link')
    assert harness.key(link) == harness.key(versions / '2.0.2')


def test_a_harness_is_unknown_until_the_agent_says_it_is_done(home):
    from metaform import harness
    assert not harness.known(VERSIONS / '2.0.1')
    harness.done(VERSIONS / '2.0.1')
    assert harness.known(VERSIONS / '2.0.1') and harness.known(VERSIONS / '2.0.2')
    assert not harness.known(OTHER)


def test_saying_done_again_does_no_harm(home):
    from metaform import harness
    harness.done(VERSIONS / '2.0.1')
    harness.done(VERSIONS / '2.0.2')
    assert harness.known(VERSIONS / '2.0.1')


def test_the_record_lives_in_the_home_and_outlasts_the_process(home, tmp_path):
    from metaform import harness
    harness.done(VERSIONS / '2.0.1')
    check = f'from metaform import harness; print(harness.known({str(VERSIONS / "2.0.1")!r}))'

    def known_in(folder: Path) -> str:
        return subprocess.run([sys.executable, '-c', check], env={**os.environ, 'METAFORM_HOME': str(folder)},
                              capture_output=True, text=True, check=True).stdout.strip()
    assert known_in(home) == 'True'
    assert known_in(tmp_path / 'another') == 'False'


def test_an_ignored_harness_is_never_recorded(home, tmp_path):
    from metaform import harness
    harness.done(VERSIONS / '2.0.1')
    before = dump(home)
    harness.done(tmp_path / 'bin' / 'agent')
    harness.done(Path(tempfile.gettempdir()) / 'agent')
    assert dump(home) == before


def test_a_home_made_before_the_record_reads_as_knowing_none(home):
    from metaform import harness
    from metaform import home as metaform_home
    with metaform_home.base(write=True):
        pass
    assert not harness.known(VERSIONS / '2.0.1')
    harness.done(VERSIONS / '2.0.1')
    assert harness.known(VERSIONS / '2.0.1')
