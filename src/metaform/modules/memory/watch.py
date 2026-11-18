"""The citation watcher: whether each citation of a memory still holds, worked out once each time its file changes and
stored with it, so a read looks the result up and reads no file.

Nothing in Metaform tells a module that a project file changed: `map.changed` follows writes to the map, and an edit
of a source file, by an agent, the person's editor or git, writes nothing there. So the watcher asks the system, as
autoticket's readers do: an inotify watch on each folder that holds a cited file on Linux, a kqueue watch on each such
folder and file on macOS and BSD. A missing folder is watched through the nearest one above it that exists, so its
return is heard. One process per project, `metaform memory watch`, started by `web start` and holding a lock while it
runs; a read asks that lock whether stored results are current. It works out every citation whose file changed while
none ran when it starts, and then sleeps until the system says a watched folder or file changed, or another process's
`map.changed` says citations were written, whose folders it then watches too. Nothing wakes it on a timer, QUAL-015.
"""
from __future__ import annotations

import contextlib
import json
import os
import select
import signal
import struct
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from metaform import events, home
from metaform.data import Store, StoreError
from metaform.module import Context, Stop, child_environment, code_print, context, surface

from .citations import Checker, rework, root_of

WATCH_OS = ('linux', 'macos')  # the systems that say a file changed: inotify, kqueue
KQ: Any = select  # kqueue's calls and names, which select holds on macOS and BSD alone
TABLE = 'memory.citations'  # the citations table as map.changed names it


def run_file(project: str) -> Path:
    """The running watcher's record for a project: its pid, folder and start."""
    return home.home() / 'run' / 'memory' / f'{project}.json'


def lock_file(project: str) -> Path:
    """The file a project's watcher holds locked while it runs; the system lets go of it when the watcher ends, by a
    crash too."""
    return run_file(project).with_suffix('.lock')


def watching(project: str) -> bool:
    """Whether a watcher holds the project's lock, so each citation's stored result is current."""
    path = lock_file(project)
    if not path.exists():
        return False
    try:
        with home.file_lock(path, wait=False):
            return False
    except home.Held:
        return True


def _cited(store: Store) -> set[str]:
    with store.tables(write=False) as tx:
        return {str(row['path']) for row in tx.rows('citations', limit=0).results}


class Folders:
    """The system's word that something changed in a set of folders, or in the files of them that are cited. `wait`
    sleeps until it does, then gives the folders, relative to the root, whose cited files may have changed; `wake`,
    from another thread, ends a wait with none."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.rooted = root.resolve()
        self.wanted: dict[str, set[str]] = {}  # each folder holding cited files, relative to the root: their names
        self.wake_read, self.wake_write = os.pipe()
        # watchers run on Linux and macOS alone (`folders`)
        os.set_blocking(self.wake_read, False)  # type: ignore[attr-defined]

    def want(self, paths: set[str]) -> None:
        """Watch the folders of these cited files, as well as those already watched. A citation whose folder is not
        under the root, an absolute path or one that climbs out with `..`, is not watched: the nearest folder above it
        is another project's, or the folder that holds the projects, whose every write woke the watcher (one watcher
        made 137,473 passes in 28 hours, woken by writes to the home folder, 2026-10-20)."""
        for path in paths:
            folder, _, name = path.replace('\\', '/').rpartition('/')
            if not self.within(folder):
                continue
            self.wanted.setdefault(folder, set()).add(name)
        self.arm()

    def within(self, folder: str) -> bool:
        """Whether a folder named relative to the root stays under it."""
        try:
            return (self.root / folder).resolve().is_relative_to(self.rooted)
        except OSError:
            return False

    def target(self, folder: str) -> str:
        """The folder watched for one that holds cited files: itself, else the nearest one above it that exists."""
        while folder and not (self.root / folder).is_dir():
            folder = folder.rpartition('/')[0]
        return folder

    def wake(self) -> None:
        with contextlib.suppress(OSError):
            os.write(self.wake_write, b'.')

    def arm(self) -> None:
        raise NotImplementedError

    def wait(self) -> set[str]:
        raise NotImplementedError

    def close(self) -> None:
        for descriptor in (self.wake_read, self.wake_write):
            with contextlib.suppress(OSError):
                os.close(descriptor)

    def _woken(self) -> None:
        with contextlib.suppress(BlockingIOError, OSError):
            while os.read(self.wake_read, 4096):
                pass

    def _under(self, watched: set[str]) -> set[str]:
        """The wanted folders a change to these watched ones may concern."""
        return {folder for folder in self.wanted if self.target(folder) in watched or folder in watched}


class Inotify(Folders):
    """Linux: an inotify watch on each wanted folder, or its nearest existing one above."""

    MASK = 0x4 | 0x8 | 0x40 | 0x80 | 0x100 | 0x200 | 0x400 | 0x800  # attrib, close-write, moves, create, delete, and
    # the folder itself deleted or moved
    HEADER = struct.Struct('iIII')  # struct inotify_event: wd, mask, cookie, len, then the name

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        import ctypes
        self.libc: Any = ctypes.CDLL(None, use_errno=True)
        self.libc.inotify_add_watch.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32)
        # Linux alone (`folders`)
        self.fd = int(self.libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC))  # type: ignore[attr-defined]
        if self.fd < 0:
            error = ctypes.get_errno()
            raise OSError(error, f'inotify: {os.strerror(error)}')
        self.watches: dict[int, str] = {}  # each watch: the folder it watches

    def arm(self) -> None:
        held = set(self.watches.values())
        for folder in {self.target(one) for one in self.wanted} - held:
            wd = int(self.libc.inotify_add_watch(self.fd, os.fsencode(self.root / folder), self.MASK))
            if wd >= 0:  # a folder gone between the look and the watch is watched through its parent next time
                self.watches[wd] = folder

    def wait(self) -> set[str]:
        ready, _, _ = select.select([self.fd, self.wake_read], [], [])
        if self.wake_read in ready:
            self._woken()
        changed: set[str] = set()
        size, unpack = self.HEADER.size, self.HEADER.unpack_from
        while True:  # a burst is taken whole, so it costs one pass
            try:
                data = os.read(self.fd, 64 * 1024)
            except BlockingIOError:
                break
            at = 0
            while at + size <= len(data):
                wd, mask, _, length = unpack(data, at)
                at += size + length
                folder = self.watches.get(wd)
                if folder is not None:
                    changed.add(folder)
                if mask & 0x8000:  # the watch is gone with its folder
                    self.watches.pop(wd, None)
        found = self._under(changed)
        self.arm()
        return found

    def close(self) -> None:
        with contextlib.suppress(OSError):
            os.close(self.fd)
        super().close()


class Kqueue(Folders):
    """macOS and BSD: a kqueue watch on each wanted folder, or its nearest existing one above, for names added,
    removed or renamed in it, and one on each cited file, for a write in place."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.queue: Any = KQ.kqueue()
        self.opened: dict[int, tuple[str, str, tuple[int, int]]] = {}  # each fd: its folder, its path, its identity
        self.queue.control([KQ.kevent(self.wake_read, KQ.KQ_FILTER_READ, KQ.KQ_EV_ADD)], 0)

    def _open(self, folder: str, path: str) -> None:
        try:
            descriptor = os.open(self.root / path, getattr(os, 'O_EVTONLY', os.O_RDONLY))
        except OSError:
            return
        stat = os.fstat(descriptor)
        notes = KQ.KQ_NOTE_WRITE | KQ.KQ_NOTE_EXTEND | KQ.KQ_NOTE_ATTRIB | KQ.KQ_NOTE_DELETE | \
            KQ.KQ_NOTE_RENAME
        self.queue.control([KQ.kevent(descriptor, KQ.KQ_FILTER_VNODE, KQ.KQ_EV_ADD | KQ.KQ_EV_CLEAR,
                                          notes)], 0)
        self.opened[descriptor] = (folder, path, (stat.st_dev, stat.st_ino))

    def arm(self) -> None:
        held = {path: (descriptor, identity) for descriptor, (_, path, identity) in self.opened.items()}
        wanted = {self.target(one): self.target(one) for one in self.wanted}
        wanted.update({f'{folder}/{name}' if folder else name: folder
                       for folder, names in self.wanted.items() for name in names})
        for path, folder in wanted.items():
            try:
                stat = (self.root / path).stat() if path else self.root.stat()
            except OSError:
                stat = None
            known = held.get(path)
            if known is not None and stat is not None and known[1] == (stat.st_dev, stat.st_ino):
                continue
            if known is not None:  # replaced or gone: its watch follows the old file
                self.opened.pop(known[0], None)
                os.close(known[0])
            if stat is not None:
                self._open(folder, path)

    def wait(self) -> set[str]:
        changed: set[str] = set()
        for event in self.queue.control(None, 64, None):  # a burst is taken whole, up to 64 at once
            if event.ident == self.wake_read:
                self._woken()
            elif event.ident in self.opened:
                changed.add(self.opened[event.ident][0])
        found = self._under(changed)
        self.arm()
        return found

    def close(self) -> None:
        for descriptor in self.opened:
            with contextlib.suppress(OSError):
                os.close(descriptor)
        self.queue.close()
        super().close()


def folders(root: Path) -> Folders:
    """This system's way of saying a watched folder or file changed; OSError when it has none."""
    if sys.platform.startswith('linux'):
        return Inotify(root)
    if hasattr(select, 'kqueue'):
        return Kqueue(root)
    raise OSError(f'{sys.platform} tells no watcher that a file changed.')


def concerns(payload: dict[str, Any], project: str) -> bool:
    """Whether a map.changed may have written the project's citations: it names their table, or names no tables."""
    tables: Any = payload.get('tables')
    return payload.get('project') == project and (tables is None or TABLE in cast(list[Any], tables))


def _pass(ctx: Context, store: Store, paths: set[str] | None) -> int:
    """One pass: the citations of these files, or of every cited file, worked out again where their file changed, and
    announced when a result changed."""
    with store.tables() as tx:
        tx.concern(kind='citations')
        changed = rework(tx, Checker(ctx), paths)
    if changed:
        events.announce(ctx.folder, ctx.surface)
    return changed


def _now() -> str:
    return datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')


def watch(ctx: Context) -> dict[str, Any]:
    """Work out each citation again whenever its file changes, until stopped."""
    store = ctx.require_store()
    project = str(store.project_id)
    root = root_of(ctx)
    try:
        watcher = folders(root)
    except OSError as error:
        raise Stop(str(error), 'reads work out the citations whose files changed themselves') from None
    home.mkdir_private(run_file(project).parent)
    holding = contextlib.ExitStack()
    listener: Any = None
    previous: Any = None
    passes = 0
    try:
        watcher.want(_cited(store))  # watched first, so a change during the first pass is heard
        passes += 1
        ctx.say(f'{_now()} watching {len(watcher.wanted)} folders; {_pass(ctx, store, None)} results changed')
        try:
            holding.enter_context(home.file_lock(lock_file(project), wait=False))
        except home.Held:
            raise Stop('The citation watcher already runs for this project.', 'metaform memory watch') from None
        home.write_private(run_file(project), json.dumps(
            {'pid': os.getpid(), 'project': project, 'folder': str(ctx.folder), 'started': _now(),
             'code': code_print()}))  # the code it runs, so `web start` on newer code replaces it, `stale`

        def stopped(number: int, frame: Any) -> None:
            raise KeyboardInterrupt  # SIGTERM, from a process manager, stops it as Ctrl-C does
        with contextlib.suppress(ValueError):  # only the main thread can take signals
            previous = signal.signal(signal.SIGTERM, stopped)
        reconfigure = getattr(sys.stdout, 'reconfigure', None)
        if callable(reconfigure):  # its log is a file, so each line is written as it is said, not at exit
            reconfigure(line_buffering=True)
        written: list[bool] = [False]

        def heard(payload: dict[str, Any]) -> None:
            """A map.changed from another process: citations written there may name files in folders not watched."""
            if concerns(payload, project):
                written[0] = True
                watcher.wake()
        listener = ctx.listen(heard)
        while True:
            changed = watcher.wait()
            if written[0]:
                written[0] = False
                watcher.want(_cited(store))
            if changed:
                paths = {path for path in _cited(store) if path.replace('\\', '/').rpartition('/')[0] in changed}
                passes += 1
                count = _pass(ctx, store, paths)
                if count:
                    ctx.say(f'{_now()} {count} results changed in {", ".join(sorted(changed)) or "."}')
    except KeyboardInterrupt:
        pass
    finally:
        if listener is not None:
            listener.close()
        watcher.close()
        with contextlib.suppress(OSError, ValueError):
            if json.loads(run_file(project).read_text(encoding='utf-8')).get('pid') == os.getpid():
                run_file(project).unlink(missing_ok=True)
        holding.close()
        if previous is not None:
            with contextlib.suppress(ValueError):
                signal.signal(signal.SIGTERM, previous)
    return {'state': 'stopped', 'passes': passes}


def stale(project: str) -> int | None:
    """The process of a watcher that runs this project on code older than the code on disk, or None: one that was
    started before an upgrade keeps the old code in memory, reads a store the new code moved on as an error on every
    change it hears, and never works a citation out again (2026-10-20, four watchers a day old). Nothing is read from a
    record with no `code`, written before this; such a watcher is replaced too."""
    if not watching(project):
        return None
    try:
        found: Any = json.loads(run_file(project).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    record = cast(dict[str, Any], found) if isinstance(found, dict) else {}
    pid = record.get('pid')
    return int(pid) if isinstance(pid, int) and record.get('code') != code_print() else None


def _ensure(store: Store, folder: Path) -> int | None:
    """Start a project's watcher, detached, when its memories cite files and none runs: its process id, or None. A
    watcher on code older than the code on disk is ended first, `stale`, and the system's own wait on its lock says when
    it has gone; the new one then runs the new code."""
    project = str(store.project_id)
    old = stale(project)
    if old is not None:
        with contextlib.suppress(OSError):
            os.kill(old, signal.SIGTERM)  # it ends as on Ctrl-C and lets go of its lock
        with contextlib.suppress(OSError), home.file_lock(lock_file(project)):
            pass
    if watching(project) or not _cited(store):
        return None
    log = run_file(project).with_suffix('.log')
    home.mkdir_private(log.parent)
    options: dict[str, Any] = {'start_new_session': True} if os.name != 'nt' else \
        {'creationflags': getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0) | getattr(subprocess, 'DETACHED_PROCESS', 0)}
    descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, 'ab') as output:
        process = subprocess.Popen([sys.executable, '-m', 'metaform', 'memory', 'watch'], cwd=folder,
                                   stdin=subprocess.DEVNULL, stdout=output, stderr=output, env=child_environment(),
                                   **options)
    return process.pid


def web_started(payload: dict[str, Any], ctx: Context) -> dict[str, Any] | None:
    """Start the citation watcher of each registered project with memory whose memories cite files and none runs,
    wherever the web GUI was started, since it serves every project."""
    from metaform.module import current_os
    if current_os() not in WATCH_OS:
        return None
    started: dict[str, int] = {}
    for project in home.projects():
        try:
            there = context('memory', Path(project.path), project=project.project_id)
            if there.store is None or not any(one.id == 'memory' for one in surface(there.folder)):
                continue
            pid = _ensure(there.store, there.folder)
        except (OSError, Stop, StoreError):  # one project's fault leaves the others watched
            continue
        if pid is not None:
            started[project.project_id] = pid
    return {'memory': 'watching', 'started': started} if started else None
