"""Read the real reader implementations against files, notifications and a local SSH-command transport."""
from __future__ import annotations

import io
import os
import queue
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from metaform.modules.autoticket import sources

pytestmark = [pytest.mark.kind('simulation'),
              pytest.mark.skipif(sys.platform == 'win32', reason='autoticket supports Linux and macOS')]


class ObservedWaker:
    """Expose EOF waits to the test; delegate notification and wake behavior to the real OS implementation."""
    def __init__(self, path):
        self.inner = ORIGINAL_WAKER(path)
        self.changed = threading.Condition()
        self.waits = 0

    def follow(self, descriptor):
        self.inner.follow(descriptor)

    def wait(self):
        with self.changed:
            self.waits += 1
            self.changed.notify_all()
        self.inner.wait()

    def await_wait(self, count):
        with self.changed:
            assert self.changed.wait_for(lambda: self.waits >= count, 5), 'reader did not reach EOF'

    def wake(self):
        self.inner.wake()

    def close(self):
        self.inner.close()


ORIGINAL_WAKER = sources.waker


def next_event(events, kind, timeout=8):
    deadline = time.monotonic() + timeout
    seen = []
    while True:
        left = deadline - time.monotonic()
        if left <= 0:
            pytest.fail(f'No {kind} event; saw {seen}')
        try:
            event = events.get(timeout=left)[1]
        except queue.Empty:
            pytest.fail(f'No {kind} event; saw {seen}')
        seen.append(event)
        if event[0] == kind:
            return event
        assert event[0] != 'failed', event


def stop(reader):
    reader.stop()
    reader.join(5)
    assert not reader.is_alive(), 'reader did not stop'


@pytest.mark.parametrize('initial', [b'unfinished old line' * 30, b'ERROR complete\nunfinished old line' * 5])
def test_local_truncation_discards_buffered_partial_line(tmp_path, monkeypatch, initial):
    log = tmp_path / 'app.log'
    log.write_bytes(initial)
    observed = ObservedWaker(str(log))
    monkeypatch.setattr(sources, 'waker', lambda path: observed)
    events = queue.Queue()
    reader = sources.LocalReader(sources.Source(str(log)), '', 0, events)
    reader.start()
    try:
        observed.await_wait(1)
        while not events.empty():
            events.get_nowait()
        at = observed.waits
        log.write_bytes(b'')
        observed.await_wait(at + 1)
        log.write_bytes(b'ERROR new\n')
        event = next_event(events, 'line', 3)
        assert event == ('line', 'ERROR new', 0, 10)
    finally:
        stop(reader)


def test_local_reader_reports_failure_after_closing_waker(tmp_path, monkeypatch):
    closed = []
    def failed(_):
        raise OSError('injected file watch failure')
    fake = SimpleNamespace(follow=failed, close=lambda: closed.append(True), wake=lambda: None)
    monkeypatch.setattr(sources, 'waker', lambda path: fake)
    log = tmp_path / 'app.log'
    log.touch()
    events = queue.Queue()
    reader = sources.LocalReader(sources.Source(str(log)), '', 0, events)
    reader.start()
    reader.join(3)
    assert not reader.is_alive()
    assert closed == [True]
    assert not events.empty(), 'reader failure was not reported to its owner'
    event = events.get_nowait()[1]
    assert event[0] == 'failed' and 'injected file watch failure' in event[1]
    assert events.empty()
    reader.stop()  # stopping an already closed reader must not write into a closed wake pipe


def test_local_initialization_failure_is_reported(tmp_path, monkeypatch):
    def failed(_):
        raise OSError('no watch available')
    monkeypatch.setattr(sources, 'waker', failed)
    events = queue.Queue()
    reader = sources.LocalReader(sources.Source(str(tmp_path / 'app.log')), '', 0, events)
    reader.start()
    reader.join(3)
    event = events.get_nowait()[1]
    assert event[0] == 'failed' and 'no watch available' in event[1]
    reader.stop()


@pytest.mark.skipif(sys.platform != 'linux', reason='inotify resource ownership')
def test_failed_inotify_initialization_releases_descriptors(tmp_path, monkeypatch):
    def failed(_):
        raise OSError('injected arm failure')
    monkeypatch.setattr(sources.Inotify, 'arm', failed)
    before = len(os.listdir('/proc/self/fd'))
    for _ in range(5):
        with pytest.raises(OSError, match='injected arm failure'):
            sources.Inotify(str(tmp_path / 'app.log'))
    assert len(os.listdir('/proc/self/fd')) == before


def test_ssh_generation_notice_stops_before_replacement_data():
    events = queue.Queue()
    reader = sources.SshReader(sources.Source('ssh://test/tmp/log'), 'old-inode', 13, events)
    process = SimpleNamespace(stdout=io.BytesIO(
        b"tail: '/tmp/log' has been replaced; following new file\nERROR replacement\n"))
    result = reader.follow(process, 13, 'old-inode')
    emitted = []
    while not events.empty():
        emitted.append(events.get_nowait()[1])
    assert not any(event[0] == 'line' for event in emitted), 'replacement bytes were read without their identity'
    assert emitted == [('file', '', 0)]
    assert result == (0, '', True)


@pytest.fixture
def local_ssh(tmp_path, monkeypatch):
    """Run SshReader.command's actual remote shell script locally, using exec so stop kills the real tail."""
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    ssh = bin_dir / 'ssh'
    ssh.write_text(f'#!{sys.executable}\n'
                   'import os, shlex, sys\n'
                   'args = sys.argv[1:]\n'
                   'while args and args[0] == "-o":\n'
                   '    args = args[2:]\n'
                   'command = shlex.split(args[1])\n'
                   'os.execvp(command[0], command)\n')
    ssh.chmod(0o755)
    monkeypatch.setenv('PATH', f'{bin_dir}{os.pathsep}{os.environ["PATH"]}')
    monkeypatch.setattr(sources, 'BACKOFF_FIRST', .05)


def test_remote_rotation_then_disconnect_and_replacement_loses_no_line(tmp_path, local_ssh):
    log = tmp_path / 'remote with spaces.log'
    log.touch()
    events = queue.Queue()
    reader = sources.SshReader(sources.Source(f'ssh://test{log}'), '', 0, events)
    reader.start()
    try:
        first = next_event(events, 'file')
        assert first[1]
        with log.open('ab') as handle:
            handle.write(b'ERROR first\n')
        assert next_event(events, 'line')[1] == 'ERROR first'
        log.rename(tmp_path / 'old.1')
        log.write_bytes(b'ERROR replacement\n')
        identities = []
        while True:
            event = events.get(timeout=12)[1]
            if event[0] == 'file':
                identities.append(event[1])
            if event[0] == 'line':
                assert event[1] == 'ERROR replacement'
                break
        assert identities[-1], 'replacement lines must have a nonempty bound file identity'
        assert identities[-1] != first[1]
        # Replace once more while the connection is down. Its old byte offset must not skip the new prefix.
        with reader.lock:
            reader.process.kill()
            log.rename(tmp_path / 'old.2')
            log.write_bytes(b'ERROR B\nERROR C\n')
        assert next_event(events, 'line', 10)[1:] == ('ERROR B', 0, 8)
        assert next_event(events, 'line', 10)[1:] == ('ERROR C', 8, 16)
        # Same-file disconnect must resume at 16, not replay either earlier record.
        with reader.lock:
            reader.process.kill()
        next_event(events, 'reconnect', 10)
        with log.open('ab') as handle:
            handle.write(b'ERROR D\n')
        assert next_event(events, 'line', 10)[1:] == ('ERROR D', 16, 24)
    finally:
        stop(reader)


def test_remote_truncation_rebinds_without_counting_a_connection_drop(tmp_path, local_ssh):
    log = tmp_path / 'remote.log'
    log.touch()
    events = queue.Queue()
    reader = sources.SshReader(sources.Source(f'ssh://test{log}'), '', 0, events)
    reader.start()
    try:
        next_event(events, 'file')
        with log.open('ab') as handle:
            handle.write(b'ERROR long old record\n')
        next_event(events, 'line')
        log.write_bytes(b'ERROR new\n')
        received = []
        while True:
            event = events.get(timeout=10)[1]
            received.append(event)
            if event[0] == 'line':
                assert event[1:] == ('ERROR new', 0, 10)
                break
        assert not any(event[0] in ('drop', 'reconnect') for event in received)
        assert any(event[0] == 'file' and event[1] for event in received)
    finally:
        stop(reader)
