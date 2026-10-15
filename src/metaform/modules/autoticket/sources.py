"""Readers: a watched log read line by line as it grows, from a local file or over the system's own ssh. Each runs
in a thread of its own and hands what it reads to the watch as events, in order. Nothing read is kept: a line lives
only until the watch has grouped it. Nothing looks on a timer, QUAL-015: a local reader at its file's end sleeps until
the system says the file or its folder changed (inotify on Linux, kqueue on macOS and BSD, the module's
SUPPORTED_OS), and an ssh reader waits on the stream `tail -F` sends.

Every line carries the byte offsets it starts and ends at, so the watch records exactly where it is, and a reader
started again, by this process after a drop or by another that takes the log over, resumes there: nothing still
readable is lost and nothing is read twice.
"""
from __future__ import annotations

import os
import queue
import re
import select
import shlex
import shutil
import struct
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Any

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

    def __init__(self, source: Source, identity: str, offset: int, events: queue.Queue[tuple[Source | None, Event]]):
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


# ------------------------------------------------------------------------------------------------ change wakers

class Waker:
    """Wakes a reader at the end of a local file when the file, or its name in its folder, changes, or when the reader
    is stopped. While the file's folder is missing, its nearest existing folder above is watched instead."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.folder = ''

    def watched(self) -> str:
        """The folder to watch now: the file's own, else the nearest existing one above it."""
        folder = os.path.dirname(self.path)
        while not os.path.isdir(folder) and os.path.dirname(folder) != folder:
            folder = os.path.dirname(folder)
        return folder

    def follow(self, descriptor: int) -> None:
        """The file the reader has open, so a write to it wakes the reader whatever its name is now."""

    def wait(self) -> None:
        """Until a change that concerns the file, or `wake`."""
        raise NotImplementedError

    def wake(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class Inotify(Waker):
    """Linux: an inotify watch on the open file, which follows it through a rename, and one on its folder, of which
    only the events naming the file count."""

    FOLDER = 0x2 | 0x4 | 0x8 | 0x40 | 0x80 | 0x100 | 0x200 | 0x400 | 0x800  # modify, attrib, close-write, moves,
    # create, delete, and the folder itself deleted or moved
    FILE = 0x2 | 0x4  # IN_MODIFY, IN_ATTRIB
    HEADER = struct.Struct('iIII')  # struct inotify_event: wd, mask, cookie, len, then the name

    def __init__(self, path: str) -> None:
        super().__init__(path)
        import ctypes
        self.libc: Any = ctypes.CDLL(None, use_errno=True)
        self.name = os.fsencode(os.path.basename(path))
        self.fd = self.folder_wd = self.file_wd = self.stop_read = self.stop_write = -1
        if sys.platform != 'linux':
            raise OSError('inotify is a call of Linux.')
        self.libc.inotify_add_watch.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32)
        self.fd = int(self.libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC))
        if self.fd < 0:
            error = ctypes.get_errno()
            raise OSError(error, f'inotify: {os.strerror(error)}')
        self.stop_read, self.stop_write = os.pipe()
        self.arm()

    def _add(self, path: str, mask: int) -> int:
        import ctypes
        wd = int(self.libc.inotify_add_watch(self.fd, os.fsencode(path), mask))
        if wd < 0:
            error = ctypes.get_errno()
            raise OSError(error, f'inotify: {os.strerror(error)}', path)
        return wd

    def arm(self) -> None:
        folder = self.watched()
        if folder != self.folder:
            if self.folder_wd >= 0:
                self.libc.inotify_rm_watch(self.fd, self.folder_wd)
            self.folder_wd, self.folder = self._add(folder, self.FOLDER), folder

    def follow(self, descriptor: int) -> None:
        if self.file_wd >= 0 and self.file_wd != self.folder_wd:
            self.libc.inotify_rm_watch(self.fd, self.file_wd)  # refused once the old file is gone, which is the same
        self.file_wd = self._add(f'/proc/self/fd/{descriptor}', self.FILE)

    def concerns(self, data: bytes) -> bool:
        """Whether the events read name the file: a change to the open file, the file's name in its folder, any
        change in a folder above while its own is missing, or a lost or removed watch."""
        at, end = 0, len(data)
        size, unpack = self.HEADER.size, self.HEADER.unpack_from
        file_wd, folder_wd, own_name = self.file_wd, self.folder_wd, self.name
        own = self.folder == os.path.dirname(self.path)
        while at + size <= end:
            wd, mask, _, length = unpack(data, at)
            name = data[at + size:at + size + length].rstrip(b'\0')
            at += size + length
            if wd == file_wd or wd < 0 or mask & 0x8000 or (wd == folder_wd and (not own or name == own_name
                                                                                 or not name)):
                return True  # 0x8000 IN_IGNORED: a watch went with its file or folder
        return False

    def wait(self) -> None:
        while True:
            ready, _, _ = select.select([self.fd, self.stop_read], [], [])
            if self.stop_read in ready:
                os.read(self.stop_read, 4096)
                return
            data = b''
            try:
                while chunk := os.read(self.fd, 65536):
                    data += chunk
            except BlockingIOError:
                pass
            if self.concerns(data):
                self.arm()
                return

    def wake(self) -> None:
        os.write(self.stop_write, b'.')

    def close(self) -> None:
        for descriptor in (self.fd, self.stop_read, self.stop_write):
            os.close(descriptor)


class Kqueue(Waker):
    """macOS and BSD: kqueue's vnode events on the open file and on its folder, whose entries changing may be the file
    replaced; the folder's events name no entry, so any change of its entries wakes the reader."""

    def __init__(self, path: str) -> None:
        super().__init__(path)
        if sys.platform == 'linux' or sys.platform == 'win32':
            raise OSError('kqueue is a call of macOS and BSD.')
        self.queue = select.kqueue()
        self.stop_read, self.stop_write = os.pipe()
        self.queue.control([select.kevent(self.stop_read, select.KQ_FILTER_READ, select.KQ_EV_ADD)], 0)
        self.folder_fd = -1
        self.arm()

    def _watch(self, descriptor: int, notes: int) -> None:
        if sys.platform == 'linux' or sys.platform == 'win32':
            return
        self.queue.control([select.kevent(descriptor, select.KQ_FILTER_VNODE, select.KQ_EV_ADD | select.KQ_EV_CLEAR,
                                          notes)], 0)

    def arm(self) -> None:
        if sys.platform == 'linux' or sys.platform == 'win32':
            return
        folder = self.watched()
        if folder != self.folder:
            if self.folder_fd >= 0:
                os.close(self.folder_fd)  # its events go with it
            self.folder_fd = os.open(folder, os.O_RDONLY | getattr(os, 'O_EVTONLY', 0))
            self.folder = folder
            self._watch(self.folder_fd, select.KQ_NOTE_WRITE | select.KQ_NOTE_DELETE | select.KQ_NOTE_RENAME)

    def follow(self, descriptor: int) -> None:
        if sys.platform == 'linux' or sys.platform == 'win32':
            return
        self._watch(descriptor, select.KQ_NOTE_WRITE | select.KQ_NOTE_EXTEND | select.KQ_NOTE_ATTRIB
                    | select.KQ_NOTE_DELETE | select.KQ_NOTE_RENAME)  # gone with the descriptor when it closes

    def wait(self) -> None:
        if sys.platform == 'linux' or sys.platform == 'win32':
            return
        fired = self.queue.control(None, 16, None)
        if any(event.ident == self.stop_read for event in fired):
            os.read(self.stop_read, 4096)
        self.arm()

    def wake(self) -> None:
        if sys.platform == 'linux' or sys.platform == 'win32':
            return
        os.write(self.stop_write, b'.')

    def close(self) -> None:
        if sys.platform == 'linux' or sys.platform == 'win32':
            return
        self.queue.close()
        for descriptor in (self.stop_read, self.stop_write, self.folder_fd):
            if descriptor >= 0:
                os.close(descriptor)


def waker(path: str) -> Waker:
    """This system's way of telling a reader that a file changed; OSError when it has none it can give."""
    if sys.platform.startswith('linux'):
        return Inotify(path)
    if hasattr(select, 'kqueue'):
        return Kqueue(path)
    raise OSError(f'{sys.platform} tells no reader that a file changed.')


class LocalReader(Reader):
    """A local file followed by name, as tail -F follows it: reopened from its start when it is replaced, after its
    old file is read to the end, and read from the start when it is truncated. At the file's end, or while it is not
    there, the reader sleeps until its waker says something changed."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.waker: Waker | None = None
        self.unfollowed = ''
        try:
            self.waker = waker(self.source.name)
        except OSError as error:
            self.unfollowed = str(error)

    def stop(self) -> None:
        super().stop()
        if self.waker is not None:
            self.waker.wake()

    def run(self) -> None:
        if self.waker is None:  # said on the log as a drop, so a log no one reads is never taken for a quiet one
            self.emit('drop', f'the file cannot be followed: {self.unfollowed}')
            return
        try:
            self.follow(self.waker)
        finally:
            self.waker.close()

    def follow(self, waker: Waker) -> None:
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
                        waker.wait()  # until its name changes in its folder
                        continue
                    waker.follow(handle.fileno())
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
                waker.wait()
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


def reader(source: Source, identity: str, offset: int, events: queue.Queue[tuple[Source | None, Event]]) -> Reader:
    return (SshReader if source.remote else LocalReader)(source, identity, offset, events)
