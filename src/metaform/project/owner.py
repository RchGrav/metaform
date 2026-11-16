"""The one owner of a home's project databases.

Only one process may hold a project database open, so one process owns every project of a home: it holds the lock
`<home>/maps/owner.lock` for as long as it lives, and every other process sends its commands to it.

Inside the owner, each open database has one writer thread that holds the database's only writing connection.
Writes wait in a queue for each caller, and the writer takes one job from each caller in turn, so one caller's
writes cannot hold back another's and each caller's own writes run in the order they arrived. The writes that are
waiting when the writer is free are committed together as one transaction, which costs one commit for all of them;
a write is answered only after the commit that holds it. A read runs on the reading thread's own
connection, against the last committed state, and never waits for a write.
"""
from __future__ import annotations

import atexit
import threading
from collections import OrderedDict, deque
from collections.abc import Callable, Generator
from concurrent.futures import Future
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any, TypeVar

from metaform import sqlite
from metaform.project import store
from metaform.project.store import Store, StoreError

T = TypeVar('T')

MAX_OPEN = 16  # open project databases in one owner; the least recently used idle one is closed to open another
GROUP = 64  # the most waiting writes committed together as one transaction
READERS = 4  # the most reading connections one database holds; a read waits for one when all are in use


class Missing(Exception):
    """The project has no database."""


class Owned(StoreError):
    """Another process owns this home's project databases."""


class Database:
    """One open project database: its writer thread, its queue of writes and its readers."""

    def __init__(self, path: Path, create: str | None = None,
                 committed: Callable[[str], None] | None = None) -> None:
        self.path = path
        self._committed = committed  # told the project's name after each commit that stored a write
        self.users = 0  # callers holding this database now, counted by the owner under its lock
        self.fresh = create is not None  # made by this process and not yet written to by a command
        self._wake = threading.Condition()
        self._jobs: dict[str, deque[tuple[Callable[[Store], Any], Future[Any]]]] = {}
        self._turn: deque[str] = deque()  # the callers with writes waiting, in the order they are served
        self._closing = False
        self._readers: list[Store] = []  # every reading connection made, closed with the database
        self._idle: list[Store] = []  # those no read is using now
        self._made = 0
        self._writing: Store | None = None
        self._failed: BaseException | None = None
        opened = threading.Event()
        self._thread = threading.Thread(target=self._serve, args=(create, opened), name=f'writer:{path.stem}',
                                        daemon=True)
        self._thread.start()
        opened.wait()
        if self._failed is not None:
            raise self._failed

    def write(self, caller: str, work: Callable[[Store], T]) -> Future[T]:
        """Queue one write for `caller`. `work` is given the writing connection on the writer thread, inside a
        transaction the writer opens and commits; the future holds its result only after that commit."""
        future: Future[T] = Future()
        with self._wake:
            if self._closing:
                raise StoreError(f'{self.path.name} is closing')
            waiting = self._jobs.get(caller)
            if waiting is None:
                waiting = self._jobs[caller] = deque()
                self._turn.append(caller)
            waiting.append((work, future))
            self._wake.notify_all()
        return future

    def read(self, work: Callable[[Store], T]) -> T:
        """Run one read as one read-only transaction, on one of the database's reading connections. There are at
        most `READERS` of them, made as they are first needed and handed from one read to the next; a read that finds
        them all in use waits for one. A connection for each calling thread was never given back, and a service that
        answers a thread for each caller ran the engine out of memory."""
        with self._wake:
            while not self._idle and self._made >= READERS and not self._closing:
                self._wake.wait()
            if self._writing is None or self._closing:
                raise StoreError(f'{self.path.name} is closed')
            if self._idle:
                reader = self._idle.pop()
            else:
                reader = self._writing.reader()
                self._readers.append(reader)
                self._made += 1
        try:
            try:
                with reader.reading():
                    return work(reader)
            except StoreError:
                # A read that began while a write was changing the tables, as a project's first write and a new
                # overlay do, can fail on what it finds half made. A read changes nothing, so it is made once more,
                # on the state that write committed.
                with reader.reading():
                    return work(reader)
        finally:
            with self._wake:
                self._idle.append(reader)
                self._wake.notify_all()

    def _serve(self, create: str | None, opened: threading.Event) -> None:
        try:
            self._writing = Store(self.path, create=create)
            from metaform.project.writes import give_standing_overlays
            with self._writing.transaction():
                give_standing_overlays(self._writing, self.path.stem)
        except BaseException as error:  # noqa: BLE001  handed to the thread that asked for the database
            self._failed = error
            opened.set()
            return
        opened.set()
        while True:
            with self._wake:
                while not self._turn and not self._closing:
                    self._wake.wait()
                if not self._turn:
                    break  # closing, and every queued write has been served
                group: list[tuple[Callable[[Store], Any], Future[Any]]] = []
                while self._turn and len(group) < GROUP:
                    caller = self._turn.popleft()
                    waiting = self._jobs[caller]
                    group.append(waiting.popleft())
                    if waiting:
                        self._turn.append(caller)  # this caller's next write waits behind the other callers' turns
                    else:
                        del self._jobs[caller]
            self._commit([job for job in group if job[1].set_running_or_notify_cancel()])
        with self._wake:
            for reader in self._readers:
                reader.close()
            self._readers.clear()
            self._writing.close()
            self._writing = None

    def _commit(self, group: list[tuple[Callable[[Store], Any], Future[Any]]]) -> None:
        """Run the writes that were waiting together as one transaction with one commit, each in its turn and each
        seeing the ones before it, and answer them after that commit. When one of them fails or is refused, the group
        is rolled back and each write runs as a transaction of its own, so one write's failure is only its own. A
        commit that fails leaves the group's writes unknown, and they are not run again."""
        store_ = self._writing
        assert store_ is not None
        if len(group) > 1:
            try:
                with store_.transaction():
                    results = [work(store_) for work, _ in group]
            except StoreError as error:
                if error.unknown:
                    for _, future in group:
                        future.set_exception(error)
                    return
            except BaseException:  # noqa: BLE001, S110  one write of the group failed: each is now run alone
                pass
            else:
                for (_, future), result in zip(group, results):
                    future.set_result(result)
                self._tell()
                return
        stored = False
        for work, future in group:
            try:
                with store_.transaction():
                    result = work(store_)
            except BaseException as error:  # noqa: BLE001  the caller receives its own failure
                future.set_exception(error)
            else:
                future.set_result(result)
                stored = True
        if stored:
            self._tell()

    def _tell(self) -> None:
        """Say once that a commit stored writes: one telling for a group, however many writes it held."""
        if self._committed is not None:
            self._committed(self.path.stem)

    def close(self) -> None:
        """Serve every write already queued, then close the database."""
        with self._wake:
            self._closing = True
            self._wake.notify_all()
        self._thread.join()


class Owner:
    """Every project database of one home, in this process."""

    def __init__(self, home: Path) -> None:
        self.home = home
        self.committed: Callable[[str], None] | None = None  # set by the service, to announce each commit
        folder = home / 'maps'
        folder.mkdir(parents=True, exist_ok=True)
        self._held = ExitStack()
        try:
            self._held.enter_context(sqlite.file_lock(folder / 'owner.lock', wait=False))
        except sqlite.Held:
            raise Owned(f'another process owns the project databases of {home}') from None
        self._lock = threading.Lock()  # guards `_open` and each database's `users`
        self._opening = threading.Lock()  # one database is opened or made at a time
        self._open: OrderedDict[str, Database] = OrderedDict()
        self._closed = False

    def projects(self) -> list[str]:
        return store.projects(self.home)

    def read(self, project: str, work: Callable[[Store], T]) -> T:
        with self._using(project, create=False) as database:
            return database.read(work)

    def write(self, project: str, caller: str, work: Callable[[Store], T], *, create: bool = False) -> T:
        """Queue one write and wait for it. With `create`, a project that has no database is made by this write; when
        the write fails, the database it made is removed again, so a refused command leaves nothing behind."""
        with self._using(project, create=create) as database:
            try:
                result = database.write(caller, work).result()
            except BaseException:
                if database.fresh:
                    self._discard(project, database)
                raise
            database.fresh = False
            return result

    @contextmanager
    def _using(self, project: str, *, create: bool) -> Generator[Database]:
        database = self._take(project)
        if database is None:
            with self._opening:
                database = self._take(project) or self._opened(project, create)
        try:
            yield database
        finally:
            with self._lock:
                database.users -= 1

    def _take(self, project: str) -> Database | None:
        with self._lock:
            if self._closed:
                raise StoreError('the owner of the project databases has closed')
            database = self._open.get(project)
            if database is not None:
                database.users += 1
                self._open.move_to_end(project)
            return database

    def _opened(self, project: str, create: bool) -> Database:
        """Open or make the project's database, with `_opening` held, closing the least recently used idle one first
        when the limit is reached. When every open database is in use, the limit is exceeded for a time."""
        path = store.location(self.home, project)
        exists = path.exists()
        if not exists and not create:
            raise Missing(project)
        with self._lock:
            idle = next((name for name, held in self._open.items() if held.users == 0), None) \
                if len(self._open) >= MAX_OPEN else None
            closing = self._open.pop(idle) if idle is not None else None
        if closing is not None:
            closing.close()
        database = Database(path, create=None if exists else project, committed=self.committed)
        with self._lock:
            database.users = 1
            self._open[project] = database
        return database

    def remove(self, project: str) -> bool:
        """Remove the project's database, after the writes already queued for it. False when there is none."""
        with self._opening:
            with self._lock:
                database = self._open.pop(project, None)
            if database is not None:
                database.close()
            path = store.location(self.home, project)
            if not path.exists():
                return False
            store.remove(path)
            return True

    def _discard(self, project: str, database: Database) -> None:
        """Remove a database this process made whose first write failed, unless another caller is using it."""
        with self._lock:
            if database.users > 1 or self._open.get(project) is not database:
                return
            del self._open[project]
        database.close()
        store.remove(database.path)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            databases = list(self._open.values())
            self._open.clear()
        for database in databases:
            database.close()
        self._held.close()


_OWNERS: dict[Path, Owner] = {}
_OWNERS_LOCK = threading.Lock()


def of(home: Path) -> Owner:
    """This process's owner of `home`, made on first use. Raises `Owned` when another process is the owner."""
    key = home.resolve()
    with _OWNERS_LOCK:
        found = _OWNERS.get(key)
        if found is None:
            found = _OWNERS[key] = Owner(key)
        return found


def close_all() -> None:
    with _OWNERS_LOCK:
        owners = list(_OWNERS.values())
        _OWNERS.clear()
    for owner in owners:
        owner.close()


atexit.register(close_all)
