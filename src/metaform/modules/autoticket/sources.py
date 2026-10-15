"""Readers: a watched log read line by line as it grows, from a local file or over the system's own ssh. Each runs
in a thread of its own and hands what it reads to the watch as events, in order. Nothing read is kept: a line lives
only until the watch has grouped it.

Every line carries the byte offsets it starts and ends at, so the watch records exactly where it is, and a reader
started again, by this process after a drop or by another that takes the log over, resumes there: nothing still
readable is lost and nothing is read twice.
"""
from __future__ import annotations

import os
import queue
import re
import shlex
import shutil
import subprocess
import threading
from dataclasses import dataclass
from typing import Any

POLL_SECONDS = 0.25  # how often a local file at its end is looked at again, as tail -F does each second
READ_BYTES = 64 * 1024
BACKOFF_FIRST = 1.0  # seconds before the first reconnect of a dropped ssh stream
BACKOFF_MOST = 60.0  # the longest wait between reconnects
SSH = 'ssh'  # the system's own ssh, found on PATH: the person's ~/.ssh/config, keys and agent apply
SSH_OPTIONS = ('-o', 'BatchMode=yes', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3')
SSH_PREFIX = 'ssh://'

# Run on the remote host by its shell: says which file it follows and from which byte, then follows it with tail -F.
# A recorded position on the same file resumes there; a different file, or a first start, begins at its start or end.
REMOTE = ('f=$1; o=$2; i=$3; n=$(ls -di "$f" 2>/dev/null | awk \'{print $1}\'); '
          'if [ "$o" = end ]; then o=$(( $( { wc -c < "$f"; } 2>/dev/null || echo 0) + 1 )); '
          'elif [ -n "$i" ] && [ "$n" != "$i" ]; then o=1; fi; '
          'echo "@autoticket ${n:-none} $o"; exec tail -F -c +"$o" "$f" 2>&1')
HEADER = re.compile(rb'^@autoticket (\S+) (\d+)\r?\n$')
# tail's own notices, merged into the stream in the order tail wrote them: never log lines, never counted
TAIL_NOTICE = re.compile(rb"^tail: .*(?:has been replaced|has appeared|file truncated|has become inaccessible|"
                         rb"cannot open|No such file|no such file|giving up)")
TAIL_RESTARTED = re.compile(rb'^tail: .*(?:has been replaced|has appeared|file truncated)')


@dataclass(frozen=True)
class Source:
    """A watched log: a local path, or `ssh://<host>/<absolute path>`."""
    name: str

    @property
    def remote(self) -> tuple[str, str] | None:
        if not self.name.startswith(SSH_PREFIX):
            return None
        rest = self.name[len(SSH_PREFIX):]
        host, _, path = rest.partition('/')
        return host, '/' + path


def parse(given: str) -> Source:
    """A watched log as given: `ssh://<host>/<path>` with a host and an absolute path, or a local path, made absolute."""
    text = given.strip()
    if text.startswith(SSH_PREFIX):
        host, _, path = text[len(SSH_PREFIX):].partition('/')
        if not host or not path or host.startswith('-') or any(char.isspace() for char in host):
            raise ValueError('An ssh log is ssh://<host>/<absolute path>, the host an alias or name ssh knows.')
        return Source(f'{SSH_PREFIX}{host}/{path.lstrip("/")}')
    if not text:
        raise ValueError('Name the log: a path, or ssh://<host>/<absolute path>.')
    return Source(os.path.abspath(os.path.expanduser(text)))


def local_identity(path: str) -> tuple[str, int] | None:
    """A local file's identity and size now, or None when it is not there."""
    try:
        found = os.stat(path)
    except OSError:
        return None
    return f'{found.st_dev}:{found.st_ino}', found.st_size


Event = tuple[Any, ...]


class Reader(threading.Thread):
    """Reads one log into the events queue: ('file', identity, offset) when it starts on a file, ('line', text, start,
    end) for each complete line, ('drop', reason) and ('reconnect',) for an ssh stream. `stop()` ends it."""

    def __init__(self, source: Source, identity: str, offset: int, events: queue.Queue[tuple[Source, Event]]):
        super().__init__(name=f'autoticket {source.name}', daemon=True)
        self.source, self.identity, self.offset, self.events = source, identity, offset, events
        self.stopping = threading.Event()

    def emit(self, *event: Any) -> None:
        self.events.put((self.source, event))

    def stop(self) -> None:
        self.stopping.set()

    def lines(self, buffer: bytearray, position: int) -> int:
        """Emit each complete line in the buffer, taking it out; returns the offset after the last one."""
        while True:
            cut = buffer.find(b'\n')
            if cut < 0:
                return position
            raw = bytes(buffer[:cut + 1])
            del buffer[:cut + 1]
            self.emit('line', raw.rstrip(b'\r\n').decode('utf-8', 'replace'), position, position + len(raw))
            position += len(raw)


class LocalReader(Reader):
    """A local file followed by name, as tail -F follows it: reopened from its start when it is replaced, after its
    old file is read to the end, and read from the start when it is truncated."""

    def run(self) -> None:
        handle = None
        buffer = bytearray()
        position = 0
        identity, offset = self.identity, self.offset
        try:
            while not self.stopping.is_set():
                if handle is None:
                    try:
                        handle = open(self.source.name, 'rb')  # noqa: SIM115  held open across reads
                    except OSError:
                        self.stopping.wait(POLL_SECONDS)
                        continue
                    found = os.fstat(handle.fileno())
                    now = f'{found.st_dev}:{found.st_ino}'
                    position = found.st_size if offset < 0 else offset if now == identity and offset <= found.st_size \
                        else 0
                    identity, offset = now, position
                    handle.seek(position)
                    buffer.clear()
                    self.emit('file', identity, position)
                chunk = handle.read(READ_BYTES)
                if chunk:
                    buffer += chunk
                    position = self.lines(buffer, position)
                    continue
                named = local_identity(self.source.name)
                held = os.fstat(handle.fileno())
                if named is not None and named[0] != f'{held.st_dev}:{held.st_ino}':
                    # replaced: what the old file still holds is read to its end, its last partial line with it
                    rest = handle.read()
                    if rest:
                        buffer += rest
                        position = self.lines(buffer, position)
                    if buffer:
                        self.emit('line', bytes(buffer).decode('utf-8', 'replace'), position, position + len(buffer))
                    handle.close()
                    handle, identity, offset = None, '', 0
                    continue
                if held.st_size < position:  # truncated: read again from the start
                    handle.seek(0)
                    buffer.clear()
                    position = 0
                    self.emit('file', identity, 0)
                    continue
                self.stopping.wait(POLL_SECONDS)
        finally:
            if handle is not None:
                handle.close()


class SshReader(Reader):
    """A remote file read through `ssh <host> tail -F`, reconnected with backoff when the stream drops, from the byte it
    had reached. Each drop and reconnect is an event the watch records on the log."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.process: subprocess.Popen[bytes] | None = None
        self.lock = threading.Lock()

    def stop(self) -> None:
        super().stop()
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                self.process.kill()

    def command(self, start: str, identity: str) -> list[str]:
        remote = self.source.remote
        assert remote is not None
        host, path = remote
        ssh = shutil.which(SSH) or SSH
        script = ' '.join(shlex.quote(part) for part in ('sh', '-c', REMOTE, 'autoticket', path, start, identity))
        return [ssh, *SSH_OPTIONS, host, script]

    def run(self) -> None:
        identity, offset = self.identity, self.offset
        wait = BACKOFF_FIRST
        first = True
        while not self.stopping.is_set():
            start = 'end' if offset < 0 else str(offset + 1)
            reason = ''
            try:
                with self.lock:
                    if self.stopping.is_set():
                        return
                    self.process = subprocess.Popen(self.command(start, identity), stdin=subprocess.DEVNULL,
                                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                process = self.process
                assert process.stdout is not None
                header = HEADER.match(process.stdout.readline())
                if header is None:
                    reason = 'no stream: ' + _said(process)
                else:
                    if not first:
                        self.emit('reconnect')
                    first = False
                    wait = BACKOFF_FIRST
                    identity = header.group(1).decode() if header.group(1) != b'none' else ''
                    offset = int(header.group(2)) - 1
                    self.emit('file', identity, offset)
                    offset, identity = self.follow(process, offset, identity)
                    reason = 'stream ended: ' + _said(process)
            except OSError as error:
                reason = f'ssh could not start: {error}'
            if self.stopping.is_set():
                return
            self.emit('drop', reason)
            self.stopping.wait(wait)
            wait = min(wait * 2, BACKOFF_MOST)

    def follow(self, process: subprocess.Popen[bytes], offset: int, identity: str) -> tuple[int, str]:
        """Emit each line of the stream until it ends; returns where it had reached."""
        assert process.stdout is not None
        for raw in process.stdout:
            if TAIL_NOTICE.match(raw):
                if TAIL_RESTARTED.match(raw):  # tail started the file again from its start
                    offset, identity = 0, ''
                    self.emit('file', identity, 0)
                continue
            if not raw.endswith(b'\n'):  # a partial last line when the link drops: read again on reconnect
                break
            self.emit('line', raw.rstrip(b'\r\n').decode('utf-8', 'replace'), offset, offset + len(raw))
            offset += len(raw)
        return offset, identity


def _said(process: subprocess.Popen[bytes]) -> str:
    """What a finished ssh said on stderr, its last line, and its exit code."""
    try:
        process.kill()
    except OSError:
        pass
    try:
        _, error = process.communicate(timeout=5)
    except (subprocess.TimeoutExpired, ValueError):
        error = b''
    last = (error or b'').decode('utf-8', 'replace').strip().splitlines()[-1:] or ['']
    return f'exit {process.returncode}' + (f', {last[0][:200]}' if last[0] else '')


def reader(source: Source, identity: str, offset: int, events: queue.Queue[tuple[Source, Event]]) -> Reader:
    return (SshReader if source.remote else LocalReader)(source, identity, offset, events)
