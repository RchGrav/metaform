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
import errno
import json
import os
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


# what a filesystem with no hard links may answer: POSIX, FUSE or network filesystems (ENOSYS), and Windows or a
# volume reached like one (EINVAL). The fallback it takes is safe whatever the cause: an exclusive copy, never over
# another file.
_NO_LINKS = {errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EXDEV, errno.EMLINK, errno.ENOSYS, errno.EINVAL}


def held_memory(path: Path) -> Path:
    """Where a new map holds the kept memory it put back until its first write is stored: the copy claimed, by a
    rename, so a clear before then merges it again and nothing else mistakes it for a copy still to put back."""
    return path.with_name(f'{path.stem}.memory.json.held')



def _memory_of(path: Path, said: list[str] | None = None) -> dict[str, list[list[object]]]:
    """The memory layer of a database about to be removed, kept for the next one.
    Opened unchecked, so a database an earlier version made can still be cleared; one with no memory layer keeps none,
    and says nothing. The entities, then the relations among them, are read each on its own, so what can be read is
    kept; what cannot, the database itself included, never keeps the map from being cleared, and is said to whoever
    cleared it, once for its one cause. A failure to close the database after its reads changes neither."""
    kept: dict[str, list[list[object]]] = {'entities': [], 'relations': []}

    def lost(what: str, error: Exception) -> dict[str, list[list[object]]]:
        verb = 'are' if what.endswith('s') else 'is'
        said_here = f"{path.stem}'s {what} could not be read and {verb} not kept: {error}"
        sys.stderr.write(said_here + '\n')
        if said is not None:
            said.append(said_here)
        return kept
    try:
        opened = Store(path, checked=False)
    except Exception as error:  # noqa: BLE001  the engine's own errors too: a damaged database is still cleared
        return lost('memory', error)
    try:
        with opened.reading():
            tables = opened.tables()
            if 'MemoryEntity' not in tables:
                return kept
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
            return kept
    except Exception as error:  # noqa: BLE001  opening its read failed: nothing of it was read
        return lost('memory', error)
    finally:
        try:
            opened.close()
        except Exception as error:  # noqa: BLE001  after the reads: what they read stands
            sys.stderr.write(f'{path.stem}: closing it after reading its memory failed: {error}\n')


def _merged(path: Path, memory: dict[str, list[list[object]]]) -> tuple[dict[str, list[list[Any]]], list[Path]]:
    """A map's memory merged with the copies already kept beside it, the held copy a new map claimed and the kept
    copy, as a union: an entity's observations from every source, each once, its type from the last source that names
    one (the map's, which comes last, when it names one), and each relation once among the entities kept. Also the
    copies that cannot be parsed, to set aside once the merged copy is written. A copy that cannot be read from disk
    raises OSError, so the clear stops and a retry finds it whole."""
    sources: list[dict[str, list[list[Any]]]] = []
    unparsed: list[Path] = []
    for copy in (held_memory(path), kept_memory(path)):
        if not copy.exists():
            continue
        try:
            sources.append(_read_kept(copy))
        except OSError:
            raise
        except Exception:  # noqa: BLE001  a copy that is not a kept memory, however it fails to parse
            unparsed.append(copy)
    sources.append(cast(dict[str, list[list[Any]]], memory))
    kinds: dict[str, Any] = {}
    observed: dict[str, dict[str, None]] = {}  # each name's observations in order, each once
    for source in sources:
        for name, kind, observations in source['entities']:
            key = str(name)
            if kind is not None or key not in kinds:
                kinds[key] = kind
            observed.setdefault(key, {}).update(dict.fromkeys(str(one) for one in observations))
    seen: set[tuple[str, str, str]] = set()
    relations: list[list[Any]] = []
    for source in sources:
        for one in source['relations']:
            key3 = (str(one[0]), str(one[1]), str(one[2]))
            if key3[0] in kinds and key3[1] in kinds and key3 not in seen:
                seen.add(key3)
                relations.append(list(key3))
    entities = [[name, kinds[name], list(observed[name])] for name in kinds]
    return {'entities': entities, 'relations': relations}, unparsed


def _write_kept(path: Path, memory: dict[str, list[list[object]]], said: list[str] | None) -> None:
    """The kept copy beside `path` written as the union of `memory` with the copies already there (`_merged`): whole,
    to its own file renamed into place, the copies that cannot be parsed set aside only once it is written, and the
    held copy withdrawn once merged. A write that fails, or text that cannot be written, changes nothing."""
    kept, held = kept_memory(path), held_memory(path)
    merged, unparsed = _merged(path, memory)
    fresh = kept.with_name(kept.name + '.new')
    try:
        fresh.write_text(json.dumps(merged, ensure_ascii=False), encoding='utf-8')
        for copy in unparsed:
            aside = _set_aside(copy)
            note = f'the memory kept at {copy} could not be read and is set aside as {aside}'
            sys.stderr.write(note + '\n')
            if said is not None:
                said.append(note)
        fresh.replace(kept)
    except (OSError, ValueError):
        with contextlib.suppress(OSError):
            fresh.unlink(missing_ok=True)
        raise
    held.unlink(missing_ok=True)  # merged into the kept copy


def _set_aside(copy: Path) -> Path:
    """A copy that cannot be parsed, moved under the first `.unread-<n>` name no file has: created exclusively, by a
    hard link, or by an exclusive copy where the filesystem has no hard links, so another file of that name is never
    overwritten. Any other failure is raised, with no partial copy left."""
    number = 1
    while True:
        aside = copy.with_name(f'{kept_name(copy)}.unread-{number}')
        try:
            os.link(copy, aside)
        except FileExistsError:
            number += 1
            continue
        except OSError as error:
            if error.errno not in _NO_LINKS:
                raise
            try:
                with aside.open('xb') as written:
                    written.write(copy.read_bytes())
            except FileExistsError:
                number += 1
                continue
            except BaseException:
                aside.unlink(missing_ok=True)
                raise
        copy.unlink()
        return aside


def kept_name(copy: Path) -> str:
    """The kept memory's own name for a copy of it, held or kept."""
    return copy.name.removesuffix('.held')


def _put_back(opened: Store) -> bool:
    """Into a database just made, the memory layer its project had when it was last cleared; whether it was put
    back. A copy that cannot be read, or that the store refuses, is said and left where it is, whole, never a reason
    the map cannot be made."""
    kept = kept_memory(opened.path)
    try:
        if not kept.exists():
            return False
        memory = _read_kept(kept)
    except Exception as error:  # noqa: BLE001  any copy it cannot read, however it fails
        sys.stderr.write(f'{kept}: the memory a clear kept could not be read and is not put back: {error}\n')
        return False
    for name, kind, observations in memory['entities']:
        opened.put_memory_entity(name, kind, observations)
    for seq, (start, end, relation_type) in enumerate(memory['relations']):
        opened.add_memory_relation(start, end, relation_type, seq)
    return True


def _read_kept(kept: Path) -> dict[str, list[list[Any]]]:
    """A kept memory copy, checked down to each value: entities [name, type or null, [observations]] with each
    name once, and relations [from, to, type], every name and observation a text. ValueError when it is not one."""
    found: Any = json.loads(kept.read_text(encoding='utf-8'))
    memory = cast(dict[str, Any], found) if isinstance(found, dict) else {}
    entities = _rows(memory.get('entities'))
    relations = _rows(memory.get('relations') or [])
    for one in entities:
        if not (len(one) == 3 and isinstance(one[0], str) and (one[1] is None or isinstance(one[1], str))
                and isinstance(one[2], list) and all(isinstance(said, str) for said in cast(list[Any], one[2]))):
            raise ValueError(f'an entity of it is not [name, type, [observations]]: {one!r}')
    for one in relations:
        if not (len(one) == 3 and all(isinstance(part, str) for part in one)):
            raise ValueError(f'a relation of it is not [from, to, type]: {one!r}')
    if len({str(one[0]) for one in entities}) != len(entities):
        raise ValueError('it names one entity twice')
    return {'entities': entities, 'relations': relations}


def _rows(value: object) -> list[list[Any]]:
    """A list of lists, or ValueError."""
    if not isinstance(value, list) or not all(isinstance(one, list) for one in cast(list[Any], value)):
        raise ValueError('it is not a kept memory')
    return [list(cast(list[Any], one)) for one in cast(list[Any], value)]


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
        # made by this process and not yet written to: ended on the writer thread when a write commits, or may have,
        # before any caller hears of it, so a discard never removes a database a write reached
        self.fresh = create is not None
        self.discarding = False  # a discard that waits for the callers in it to leave
        self.put_back = False  # whether it holds the kept memory it put back, claimed as `held_memory`
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
            if create is not None:  # in its own transaction: a kept copy the store refuses never stops the map
                try:
                    with self._writing.transaction():
                        put = _put_back(self._writing)
                    if put:  # committed: the copy is claimed by a rename, and withdrawn after the first write
                        try:
                            kept_memory(self.path).replace(held_memory(self.path))
                            self.put_back = True
                        except OSError as error:  # the map holds it, and the copy stays: deleted memory may come back
                            sys.stderr.write(f'{kept_memory(self.path)}: the memory was put back into the new map, but '
                                             f'its kept copy could not be claimed and stays: {error}\n')
                except (StoreError, OSError) as error:  # the copy stays as it was: memory may come back, never lost
                    sys.stderr.write(f'{kept_memory(self.path)}: the memory a clear kept was refused by the new map '
                                     f'and is not put back: {error}\n')
        except BaseException as error:  # noqa: BLE001  handed to the thread that asked for the database
            if self._writing is not None:  # its connection closed, and a database it was making removed again
                with contextlib.suppress(Exception):
                    self._writing.close()
                self._writing = None
                if create is not None:
                    with contextlib.suppress(OSError):
                        store.remove(self.path)
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
                    self._written()  # it may have committed: said as a change, as a commit is
                    for _, future, _ in group:
                        future.set_exception(error)
                    self._tell({kind for _, _, kind in group})
                    return
            except BaseException:  # noqa: BLE001, S110  one write of the group failed: each is now run alone
                pass
            else:
                self._written()
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
                if isinstance(error, StoreError) and error.unknown:
                    self._written()  # it may have committed: said as a change, as a commit is
                    stored.add(kind)
                future.set_exception(error)
            else:
                self._written()
                future.set_result(result)
                stored.add(kind)
        if stored:
            self._tell(stored)

    def _written(self) -> None:
        """A write reached this database: it is no longer fresh, and the copy of memory it put back is held by it now,
        so its claimed copy goes. On the writer thread, while the database is open: a clear closes it, ending this
        thread, before it touches that copy, and no newer map of the project stands while this one is open."""
        if not self.fresh:
            return
        self.fresh = False
        if self.put_back:
            with contextlib.suppress(OSError):  # left, it is merged by the next clear or removed by the next open
                held_memory(self.path).unlink(missing_ok=True)

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
        the write is refused, the database it made is removed again, so a refused command leaves nothing behind. A write
        whose commit outcome is unknown may have landed, so its database is kept. `kind` is what the write changes: the
        map, or the memory layer."""
        with self._using(project, create=create) as database:
            try:
                result = database.write(caller, work, kind).result()
            except BaseException:
                if database.fresh:  # discarded as its last caller leaves (`_leave`), unless a write reaches it first
                    with self._lock:
                        database.discarding = True
                raise
            return result  # the claimed copy is withdrawn by the writer when the write commits (`Database._written`)

    @contextmanager
    def _using(self, project: str, *, create: bool) -> Generator[Database]:
        database = self._take(project)
        if database is None:
            with self._opening:
                database = self._take(project) or self._opened(project, create)
        try:
            yield database
        finally:
            if database.fresh:  # `fresh` only turns false, and a map no longer fresh is never discarded
                with self._opening:
                    self._leave(project, database)
            else:
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
        # The one decision on a claimed copy: beside a map that stands it is already in that map, and goes; with no map,
        # its map was discarded or removed part way, and it goes back into the kept copy, to be put back.
        if held_memory(path).exists():
            if exists:
                with contextlib.suppress(OSError):
                    held_memory(path).unlink()
            else:  # never made without it: the memory it holds would be lost
                try:
                    _write_kept(path, {'entities': [], 'relations': []}, None)
                except (OSError, ValueError) as error:
                    raise StoreError(f'{project} cannot be made: the memory a map discarded or removed part way '
                                     'claimed, at '
                                     f'{held_memory(path)}, could not be kept again first: {error}. Free space or '
                                     'permission there, or move that file aside, and run the command again.') \
                        from error
        if not exists:  # a removal that stopped part way may have left the old map's files: never read into the new one
            try:
                store.remove(path)
            except OSError as error:
                raise StoreError(f'{project} cannot be made: files an earlier map left beside it could not be '
                                 f'removed: {error}') from error
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
            memory = _memory_of(path, said)
            # Kept for the next map, LAYER-013. A clear never loses kept memory: what this map holds is merged as a
            # union with the copies kept beside it (one a new map claimed as `held`, and the kept copy), and written
            # whole to its own file renamed into place, so a torn write never lands where the next map reads it. The
            # next map claims the kept copy by a rename once it has put it back, and withdraws it after its first
            # write. A removal that fails leaves the map standing and the copy at most fuller.
            if memory['entities'] or held_memory(path).exists():
                _write_kept(path, memory, said)
            try:
                store.remove(path)
            except OSError:
                if path.exists():
                    raise
                sys.stderr.write(f'{path}: files beside the removed map could not be removed; a new map at this path '
                                 'removes them first\n')
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

    def _leave(self, project: str, database: Database) -> None:
        """A caller leaves a new map no write has reached yet, with `_opening` held. When a write of it failed and no
        caller is left in it, the map is removed: decided and done under the open lock, so no open, eviction or base
        switch comes between. Closing it serves any write still queued; one that commits ends `fresh`, and the map
        stays. A map the system will not let go of stays, said and never raised, as the caller leaving may be another
        whose own result stands; a clear removes it. A copy of memory the map claimed is given back by the next open."""
        with self._lock:
            database.users -= 1
            if not (database.fresh and database.discarding and not database.users
                    and self._open.get(project) is database):
                return
            del self._open[project]
        try:
            database.close()
            if database.fresh:
                store.remove(database.path)
        except Exception as error:  # noqa: BLE001  said: the map stays, and a clear removes it
            what = 'could not be removed, and stays until the project is cleared' if database.fresh else \
                'was kept, as a queued write reached it, but did not close cleanly'
            sys.stderr.write(f'{database.path}: a new map whose first write failed {what}: {error}\n')

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
