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


def test_running_walks_past_shells_launchers_and_wrappers_to_the_first_other_program(monkeypatch):
    from metaform import harness
    wrappers = ('bash', 'uv', 'python3.13', 'sh', 'uvx', 'pythonw.exe', 'cmd.exe', 'pwsh.exe',
                'timeout', 'nice', 'env', 'xargs', 'nohup', 'TIMEOUT.EXE')
    processes = {pid: (pid + 1, ROOT / 'launchers' / name) for pid, name in enumerate(wrappers, 20)}
    end = 20 + len(wrappers)
    processes[end] = (end + 1, VERSIONS / '2.0.1')
    processes[end + 1] = (0, OTHER)
    monkeypatch.setattr(os, 'getppid', lambda: 20)
    monkeypatch.setattr(harness, '_process', lambda pid: processes.get(pid), raising=False)
    assert harness.running() == VERSIONS / '2.0.1'


def test_running_does_not_select_an_ancestor_when_the_nearest_program_cannot_be_read(monkeypatch):
    from metaform import harness
    monkeypatch.setattr(os, 'getppid', lambda: 20)
    monkeypatch.setattr(harness, '_process', lambda pid: None, raising=False)
    assert harness.running() is None


@pytest.mark.skipif(sys.platform != 'linux', reason='BusyBox applet detection uses Linux process arguments')
@pytest.mark.parametrize(('arguments', 'shell'), [(b'busybox\0sh\0-c\0command\0', True),
                                                (b'/bin/sh\0-c\0command\0', True),
                                                (b'-sh\0-c\0command\0', True),
                                                (b'busybox\0timeout\x0060\0command\0', True),
                                                (b'/bin/timeout\x0060\0command\0', True),
                                                (b'busybox\0sleep\x0010\0', False)])
def test_busybox_shells_and_wrappers_are_passed_over_and_other_applets_are_programs(monkeypatch, arguments, shell):
    from metaform import harness
    binary = ROOT / 'usr' / 'bin' / 'busybox'
    processes = {20: (21, binary), 21: (0, OTHER)}
    monkeypatch.setattr(os, 'getppid', lambda: 20)
    monkeypatch.setattr(harness, '_process', lambda pid: processes.get(pid))
    command_lines = {Path('/proc/20/cmdline'): arguments, Path('/proc/21/cmdline'): os.fsencode(OTHER) + b'\0'}
    monkeypatch.setattr(Path, 'read_bytes', lambda path: command_lines[path])
    assert harness.running() == (OTHER if shell else binary)


@pytest.mark.kind('simulation')
def test_native_process_lookup_reads_this_process_binary_and_parent():
    from metaform import harness
    parent, binary = harness._process(os.getpid())
    assert parent == os.getppid()
    assert binary.resolve() == Path(sys.executable).resolve()


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
