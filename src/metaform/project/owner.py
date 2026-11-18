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
import contextlib
import json
import sys
import threading
from collections import OrderedDict, deque
from collections.abc import Callable, Generator
from concurrent.futures import Future
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any, TypeVar, cast

from metaform import sqlite
from metaform.project import store
from metaform.project.store import Store, StoreError

T = TypeVar('T')

MAX_OPEN = 16  # open project databases in one owner; the least recently used idle one is closed to open another
GROUP = 64  # the most waiting writes committed together as one transaction
READERS = 4  # the most reading connections one database holds; a read waits for one when all are in use


def kept_memory(path: Path) -> Path:
    """Where a cleared project's memory layer waits for its next map: beside the database it was in. Clearing removes
    the map, and a memory whose object is gone is hidden, never deleted, so the memory is kept until the project's
    database is made again and is then put back into it."""
    return path.with_name(f'{path.stem}.memory.json')



def _memory_of(path: Path, said: list[str] | None = None) -> tuple[dict[str, list[list[object]]], bool]:
    """The memory layer of a database about to be removed, kept for the next one, and whether it was read whole.
    Opened unchecked, so a database an earlier version made can still be cleared; one with no memory layer keeps none,
    and says nothing. The entities, then the relations among them, are read each on its own, so what can be read is
    kept; what cannot, the database itself included, never keeps the map from being cleared, and is said to whoever
    cleared it, once for its one cause. A failure to close the database after its reads changes neither."""
    kept: dict[str, list[list[object]]] = {'entities': [], 'relations': []}

    def lost(what: str, error: Exception) -> tuple[dict[str, list[list[object]]], bool]:
        said_here = f"{path.stem}'s {what} could not be read and {'are' if what.endswith('s') else 'is'} not kept: {error}"
        sys.stderr.write(said_here + '\n')
        if said is not None:
            said.append(said_here)
        return kept, False
    try:
        opened = Store(path, checked=False)
    except Exception as error:  # noqa: BLE001  the engine's own errors too: a damaged database is still cleared
        return lost('memory', error)
    try:
        with opened.reading():
            tables = opened.tables()
            if 'MemoryEntity' not in tables:
                return kept, True
            try:
                kept['entities'] = cast(list[list[object]], [[name, kind, observations] for name, kind, observations
                                                             in opened.memory_entities()])
            except Exception as error:  # noqa: BLE001
                return lost('memory', error)
            if 'MemoryRelation' in tables:
                try:
                    kept['relations'] = cast(list[list[object]], [list(one) for one in opened.memory_relations()])
                except Exception as error:  # noqa: BLE001
                    return lost('memory relations', error)
            return kept, True
    except Exception as error:  # noqa: BLE001  opening its read failed: nothing of it was read
        return lost('memory', error)
    finally:
        try:
            opened.close()
        except Exception as error:  # noqa: BLE001  after the reads: what they read stands
            sys.stderr.write(f'{path.stem}: closing it after reading its memory failed: {error}\n')


def _undo(kept: Path, fresh: Path, earlier: Path, placed: bool, moved: bool) -> None:
    """Put a cleared map's kept memory back as it was before its clear: the new copy out of the way, the earlier copy
    back in its place, each step on its own, so one that fails never keeps the other from being tried."""
    with contextlib.suppress(OSError):
        fresh.unlink(missing_ok=True)
    if placed:
        with contextlib.suppress(OSError):
            kept.unlink(missing_ok=True)
    if moved:
        with contextlib.suppress(OSError):
            earlier.replace(kept)


def _put_back(opened: Store) -> bool:
    """Into a database just made, the memory layer its project had when it was last cleared; whether it was put
    back. A copy that cannot be read is said and left where it is, whole, never a reason the map cannot be made."""
    kept = kept_memory(opened.path)
    if not kept.exists():
        return False
    try:
        memory = json.loads(kept.read_text(encoding='utf-8'))
        entities = [(str(name), None if kind is None else str(kind), [str(one) for one in observations])
                    for name, kind, observations in memory['entities']]
        relations = [(str(start), str(end), str(kind))
                     for start, end, kind in cast(list[list[Any]], memory.get('relations') or [])]
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        sys.stderr.write(f'{kept}: the memory a clear kept could not be read and is not put back: {error}\n')
        return False
    for name, kind, observations in entities:
        opened.put_memory_entity(name, kind, observations)
    for start, end, relation_type in relations:
        opened.add_memory_relation(start, end, relation_type)
    return True


class Missing(Exception):
    """The project has no database."""


class Owned(StoreError):
    """Another process owns this home's project databases."""


class Database:
    """One open project database: its writer thread, its queue of writes and its readers."""

    def __init__(self, path: Path, create: str | None = None,
                 committed: Callable[[str, set[str]], None] | None = None) -> None:
        self.path = path
        # told the project's name after each commit that stored a write, with the kinds of what it stored: map, memory
        self._committed = committed
        self.users = 0  # callers holding this database now, counted by the owner under its lock
        self.fresh = create is not None  # made by this process and not yet written to by a command
        self.put_back = False  # whether a cleared project's kept memory was put back into it when it was made
        self._wake = threading.Condition()
        self._jobs: dict[str, deque[tuple[Callable[[Store], Any], Future[Any], str]]] = {}
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

    def write(self, caller: str, work: Callable[[Store], T], kind: str = 'map') -> Future[T]:
        """Queue one write for `caller`. `work` is given the writing connection on the writer thread, inside a
        transaction the writer opens and commits; the future holds its result only after that commit. `kind` says
        what it changes, the map or the memory layer, for the announcement of the commit."""
        future: Future[T] = Future()
        with self._wake:
            if self._closing:
                raise StoreError(f'{self.path.name} is closing')
            waiting = self._jobs.get(caller)
            if waiting is None:
                waiting = self._jobs[caller] = deque()
                self._turn.append(caller)
            waiting.append((work, future, kind))
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
                if create is not None:
                    self.put_back = _put_back(self._writing)
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
                group: list[tuple[Callable[[Store], Any], Future[Any], str]] = []
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
            # Every read already running ends before its connection closes (review of 2026-11-18, F13): none new is
            # admitted once closing, and each read hands its connection back with a notify.
            while len(self._idle) < self._made:
                self._wake.wait()
            for reader in self._readers:
                reader.close()
            self._readers.clear()
            self._writing.close()
            self._writing = None

    def _commit(self, group: list[tuple[Callable[[Store], Any], Future[Any], str]]) -> None:
        """Run the writes that were waiting together as one transaction with one commit, each in its turn and each
        seeing the ones before it, and answer them after that commit. When one of them fails or is refused, the group
        is rolled back and each write runs as a transaction of its own, so one write's failure is only its own. A
        commit that fails leaves the group's writes unknown, and they are not run again."""
        store_ = self._writing
        assert store_ is not None
        if len(group) > 1:
            try:
                with store_.transaction():
                    results = [work(store_) for work, _, _ in group]
            except StoreError as error:
                if error.unknown:
                    for _, future, _ in group:
                        future.set_exception(error)
                    return
            except BaseException:  # noqa: BLE001, S110  one write of the group failed: each is now run alone
                pass
            else:
                for (_, future, _), result in zip(group, results):
                    future.set_result(result)
                self._tell({kind for _, _, kind in group})
                return
        stored: set[str] = set()
        for work, future, kind in group:
            try:
                with store_.transaction():
                    result = work(store_)
            except BaseException as error:  # noqa: BLE001  the caller receives its own failure
                future.set_exception(error)
            else:
                future.set_result(result)
                stored.add(kind)
        if stored:
            self._tell(stored)

    def _tell(self, kinds: set[str]) -> None:
        """Say once that a commit stored writes, and of which kinds: one telling for a group, however many writes it
        held."""
        if self._committed is not None:
            self._committed(self.path.stem, kinds)

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
        self.committed: Callable[[str, set[str]], None] | None = None  # set by the service, to announce each commit
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

    def write(self, project: str, caller: str, work: Callable[[Store], T], *, create: bool = False,
              kind: str = 'map') -> T:
        """Queue one write and wait for it. With `create`, a project that has no database is made by this write; when
        the write fails, the database it made is removed again, so a refused command leaves nothing behind. `kind`
        is what the write changes: the map, or the memory layer."""
        with self._using(project, create=create) as database:
            try:
                result = database.write(caller, work, kind).result()
            except BaseException:
                if database.fresh:
                    self._discard(project, database)
                raise
            if database.fresh and database.put_back:  # the first write stored: the memory put back is held by the
                kept_memory(database.path).unlink(missing_ok=True)  # database now; a copy never put back stays
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
        if not exists:  # a removal that stopped part way may have left the old map's files: never read into the new one
            store.remove(path)
        database = Database(path, create=None if exists else project, committed=self.committed)
        with self._lock:
            database.users = 1
            self._open[project] = database
        return database

    def remove(self, project: str, said: list[str] | None = None) -> bool:
        """Remove the project's database, after the writes already queued for it. False when there is none. What of
        its memory could not be kept is added to `said`."""
        with self._opening:
            with self._lock:
                database = self._open.pop(project, None)
            if database is not None:
                database.close()
            path = store.location(self.home, project)
            if not path.exists():  # files a removal that stopped part way left beside it go too, when they can
                try:
                    store.remove(path)
                except OSError as error:  # never a refusal: a new map at this path removes them first
                    sys.stderr.write(f'{path}: files beside a removed map could not be removed: {error}\n')
                return False
            memory, whole = _memory_of(path, said)
            kept = kept_memory(path)
            fresh, earlier = kept.with_name(kept.name + '.new'), kept.with_name(kept.name + '.earlier')
            # Kept for the next map, LAYER-013: written whole to its own file first, so a write that fails removes
            # nothing and never leaves a torn copy where the next map reads it; then the earlier clear's copy is set
            # aside and the new one put in its place, each by a rename. The earlier copy is withdrawn when this memory
            # was read whole and holds none, so nothing deleted since comes back, and kept after a read that failed,
            # when it may be the one copy left. Any step that fails while the map stands undoes those before it.
            if memory['entities']:
                try:
                    fresh.write_text(json.dumps(memory, ensure_ascii=False), encoding='utf-8')
                except OSError:
                    fresh.unlink(missing_ok=True)
                    raise
            moved = placed = False
            try:
                if kept.exists() and (memory['entities'] or whole):
                    kept.replace(earlier)
                    moved = True
                if memory['entities']:
                    fresh.replace(kept)
                    placed = True
                store.remove(path)
            except OSError:
                if path.exists():  # the map still stands, and so does the copy it was cleared with
                    _undo(kept, fresh, earlier, placed, moved)
                    raise
                sys.stderr.write(f'{path}: files beside the removed map could not be removed; a new map at this path '
                                 'removes them first\n')
            if moved:
                with contextlib.suppress(OSError):
                    earlier.unlink(missing_ok=True)
            return True

    @contextmanager
    def released(self, project: str) -> Generator[Path]:
        """The project's database closed, after the writes already queued for it, and kept closed for the block, which
        is given its path: no command opens it until the block ends, so the block may move its files, as a switch of
        the project's base does (`bases`). The next command opens whatever database is at the path then."""
        with self._opening:
            with self._lock:
                database = self._open.pop(project, None)
            if database is not None:
                database.close()
            yield store.location(self.home, project)

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
