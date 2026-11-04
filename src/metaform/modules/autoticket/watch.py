"""The watch: reads the project's watched logs, joins their lines into entries, groups the entries it captures, and
keeps each group's counter. Committed captures are announced as `autoticket.captured`; the separately registered
fault policy decides whether to file tickets. Capturing a log does not import or call the repair policy.

Each log is read by one process at a time, the holder of its lease: a lock on a file of its own in the home, which the
system lets go when the holder ends, by a crash too. A process that wants the log waits on that lock and takes the log
over the moment it is let go. The holder's name is kept in the logs table for `autoticket logs`. The holder writes its
counts and its position in the log together, at most once a second and only after reading something, so a process
that takes the log over resumes from the last position written: an entry is counted by the process that wrote the
position past it, and by no other.

Nothing here wakes on a timer to look for a change, QUAL-015. The watch sleeps on its events queue until a reader hands
it a line, a lease is handed over, a `map.changed` from another process names its tables (a log added or removed, a
rule), or a real deadline comes: an open entry's quiet time, a write batch, a failed reader's retry, or a run's end.
"""
from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import secrets
import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from metaform import home, settings
from metaform import module as chassis
from metaform.data import Store, TableTx
from metaform.module import Context

from . import entries, grouping, sources

BEAT_SECONDS = 1.0  # counts and positions are written at most once a second, after something was read
CONCERNS = {'autoticket.logs', 'autoticket.rules', 'autoticket.state'}  # the tables whose change the watch reads again
EXAMPLE_LINE = 300  # characters of an example's first line in a list or a title


def now_text(at: float | None = None) -> str:
    return datetime.fromtimestamp(time.time() if at is None else at, UTC).strftime('%Y-%m-%dT%H:%M:%SZ')


def holder_id() -> str:
    """This process's name on a lease: its host and pid, and a token so a reused pid is never taken for it."""
    return f'{socket.gethostname()}:{os.getpid()}:{secrets.token_hex(4)}'


def lease_path(project: str, source: str) -> Path:
    """The file whose lock is a watched log's lease, in the home."""
    digest = hashlib.sha256(f'{project}\n{source}'.encode()).hexdigest()[:24]
    return home.home() / 'run' / 'autoticket' / f'{digest}.lock'


class Lease(threading.Thread):
    """A watched log's lease, taken in a thread of its own: at once when no process holds it, else the moment its
    holder lets go or ends. Its taking is an event on the watch's queue; it is held until `let_go`."""

    def __init__(self, project: str, source: str, events: queue.Queue[tuple[sources.Source | None, sources.Event]]):
        super().__init__(name=f'autoticket lease {source}', daemon=True)
        self.project, self.source, self.events = project, source, events
        self.letting = threading.Event()
        self.held = False

    def run(self) -> None:
        path = lease_path(self.project, self.source)
        try:
            home.mkdir_private(path.parent)
            with home.file_lock(path):  # waits in the system on the holder, flock or LockFileEx
                if self.letting.is_set():
                    return
                self.held = True
                self.events.put((None, ('lease', self.source)))
                self.letting.wait()
                self.held = False
        except OSError as error:
            self.events.put((None, ('lease-failed', self.source, str(error))))

    def let_go(self) -> None:
        self.letting.set()


def setting(key: str, folder: Any) -> Any:
    """One of autoticket's settings. The web server holds its services through their module's reloads, and a reload
    withdraws the module's settings until the modules are found again: a setting withdrawn now is read once they are."""
    try:
        return settings.value(key, folder)
    except KeyError:
        chassis.refresh_modules()
        chassis.installed()  # finding the modules declares autoticket's settings again
        return settings.value(key, folder)


def similarity(folder: Any) -> float:
    try:
        return float(setting('autoticket_similarity', folder))
    except (TypeError, ValueError):
        return grouping.THRESHOLD


def secret_values(folder: Any) -> set[str]:
    """The values of the settings whose names say they hold a secret, free text or a list, as the problem report
    finds them."""
    found: set[str] = set()
    for key, setting in list(settings.SCHEMA.items()):
        if setting.kind not in ('str', 'list') or not entries.SECRET_NAME.search(key):
            continue
        try:
            value = settings.value(key, folder)
        except Exception:  # noqa: BLE001, S112  a setting that cannot be read here holds nothing to mask
            continue
        for item in cast(list[Any], value) if isinstance(value, list) else [value]:
            text = str(item or '')
            if len(text) >= 6 and not re.fullmatch(r'[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+', text):
                found.add(text)
    return found


def rules(tx: TableTx) -> list[re.Pattern[str]]:
    kept: list[re.Pattern[str]] = []
    for row in tx.rows('rules', limit=0).results:
        try:
            kept.append(re.compile(str(row['pattern'])))
        except re.error:
            continue
    return kept


def state(tx: TableTx, name: str) -> str:
    row = tx.get('state', {'name': name})
    return '' if row is None else str(row['value'])


def first_line(text: str) -> str:
    line = next((one for one in text.splitlines() if one.strip()), '')
    return line[:EXAMPLE_LINE]


# ------------------------------------------------------------------------------------------------ where a group sits

def top_node(store: Store) -> str | None:
    """The project's top node: its DE, else its first root element; None while the map holds nothing."""
    try:
        roots = store.roots(limit=1)
    except Exception:  # noqa: BLE001  a project with no map yet has no top node
        return None
    found = next((entry.element for entry in roots.entry if entry.element.role == 'DE'), None) \
        or next((entry.element for entry in roots.entry), None) or next(iter(roots.elements), None)
    return None if found is None else found.address


def file_address(store: Store, file: str) -> str | None:
    """The Address that owns a file: the element whose file ref, `path=` in the sources layer, names it, as dispatch
    link writes it; else the element whose ref names a file of the same name ending the path, as the page names its
    parts (`page/app/core/errors.js`); else the nearest owner, the element citing a file in the deepest folder the
    two paths share. None when the file is outside the project or no ref shares a folder with it."""
    root = os.path.realpath(store.project().path)
    path = file.replace('\\', '/')
    if os.path.isabs(file):
        real = os.path.realpath(file)
        if not real.startswith(root + os.sep):
            return None
        path = os.path.relpath(real, root).replace(os.sep, '/')
    try:
        cited = store.citing('path', path, limit=0).results
        found = next((one for one in cited if one.layer == 'sources' and one.address), None) \
            or next((one for one in cited if one.address), None)
        if found is not None:
            return found.address
        refs = [(ref.value, ref.address) for ref in store.refs() if ref.key == 'path' and ref.address]
    except Exception:  # noqa: BLE001  a project with no map yet holds no refs
        return None
    ending = next((address for value, address in refs if value.endswith('/' + path)), None)
    if ending is not None:
        return ending
    folders = path.split('/')[:-1]
    nearest, depth = None, 0
    for value, address in refs:
        shared = 0
        for mine, theirs in zip(folders, value.split('/')[:-1], strict=False):
            if mine != theirs:
                break
            shared += 1
        if shared > depth:
            nearest, depth = address, shared
    return nearest


def place(ctx: Context, store: Store, example: str, file: str | None = None) -> str | None:
    """Where a group sits: the Address that owns the file the source named or its trace names, else the project's top
    node."""
    found = file or (named[0] if (named := entries.location(example)) is not None else None)
    address = file_address(store, found) if found else None
    return address or top_node(store)


def active_work(store: Store) -> dict[str, Any]:
    """The agents and tickets at work now: each taken open ticket, with who took it."""
    try:
        records = store.work(open=True, limit=0).results
    except Exception:  # noqa: BLE001  a project with no map has no tickets
        return {'agents': [], 'tickets': []}
    taken = [record for record in records if record.taken_by]
    return {'agents': sorted({str(record.taken_by) for record in taken}),
            'tickets': [{'id': record.id, 'address': record.address, 'taken_by': record.taken_by,
                         'title': first_line(record.task or record.note or '')[:120]} for record in taken]}


# ------------------------------------------------------------------------------------------------ the groups

def ranked(tx: TableTx) -> list[dict[str, Any]]:
    """Every group, most counted first."""
    found = [dict(row) for row in tx.rows('groups', limit=0).results]
    found.sort(key=lambda row: (-int(row['count']), int(row['group_id'])))
    return [shown(row) for row in found]


def shown(row: dict[str, Any]) -> dict[str, Any]:
    address, number = row.get('address') or None, row.get('number')
    return {'group': int(row['group_id']), 'count': int(row['count']), 'example': first_line(str(row['example'])),
            'address': address, **({'item': f'{address}#{int(number):x}'} if address and number else {}),
            'first_seen': row['first_seen'], 'last_seen': row['last_seen'],
            **({'work_id': row['work_id']} if row.get('work_id') else {})}


# ------------------------------------------------------------------------------------------------ the watch

@dataclass
class Group:
    """A group this process has counted since its last write: an existing one by id, or a new one."""
    terms: tuple[int, ...]
    count: int = 0
    first: float = 0.0
    last: float = 0.0
    example: str = ''
    group_id: int | None = None


@dataclass
class Held:
    """A log this process holds the lease of, its reader, and what it has read since its last write."""
    source: sources.Source
    reader: sources.Reader
    assembler: entries.Assembler = field(default_factory=entries.Assembler)
    identity: str = ''
    offset: int = 0  # the byte after the last line read
    groups: list[Group] = field(default_factory=list[Group])
    drops: int = 0
    reconnects: int = 0
    last_drop: str = ''
    retry_at: float | None = None
    retry_delay: float = sources.BACKOFF_FIRST
    recovering: bool = False

    @property
    def position(self) -> int:
        """Where a reader started again resumes: the start of the entry still open, else after the last line."""
        start = self.assembler.pending_start
        return self.offset if start is None else start


@dataclass
class Totals:
    lines: int = 0
    captured: int = 0
    made: int = 0
    drops: int = 0


class Watch:
    def __init__(self, ctx: Context, store: Store, *, clock: Callable[[], float] = time.time,
                 monotonic: Callable[[], float] = time.monotonic) -> None:
        self.ctx, self.store, self.clock, self.monotonic = ctx, store, clock, monotonic
        self.me = holder_id()
        self.events: queue.Queue[tuple[sources.Source | None, sources.Event]] = queue.Queue()
        self.held: dict[str, Held] = {}
        self.leases: dict[str, Lease] = {}  # every watched log's lease, taken here or waited on
        self.known: list[tuple[int, tuple[int, ...]]] = []  # every group written, in the order made
        self.threshold = similarity(ctx.folder)
        self.mode = str(setting('autoticket_capture', ctx.folder) or 'errors')
        self.secrets = secret_values(ctx.folder)
        self.rules: list[re.Pattern[str]] = []
        self.written_at = 0.0
        self.dirty = False  # read since the last write: counts or a position to write
        self.claim_due = True  # the logs and rules to read again, at the first turn and after a change
        self.touched: set[int] = set()  # the groups counted since the last write, new and known
        self.stopping = False
        self.totals = Totals()

    # -------------------------------------------------------------- leases

    def claim(self) -> None:
        """Read the watched logs and the rules; wait on the lease of each log new here, and let go of each log no
        longer watched."""
        self.claim_due = False
        with self.store.tables(write=False) as tx:
            self.rules = rules(tx)
            names = {str(row['source']) for row in tx.rows('logs', limit=0).results}
        for name in sorted(names - set(self.leases)):
            lease = Lease(self.store.project_id, name, self.events)
            self.leases[name] = lease
            lease.start()
        for name in sorted(set(self.leases) - names):
            self.drop(name)

    def taken(self, name: str) -> None:
        """A lease handed over: the log is read from where its last holder wrote it had reached."""
        lease = self.leases.get(name)
        if lease is None or name in self.held:
            return
        with self.store.tables() as tx:
            row = tx.get('logs', {'source': name})
            if row is not None:
                tx.update('logs', {'source': name}, {'holder': self.me, 'beat': self.clock()})
        if row is None:
            self.drop(name)
            return
        source, identity, offset = sources.Source(name), str(row['identity'] or ''), int(row['offset'])
        reader = sources.reader(source, identity, offset, self.events)
        self.held[name] = Held(source, reader, identity=identity, offset=offset)
        reader.start()

    def drop(self, name: str) -> None:
        """Stop reading a log and let its lease go, what was read since the last write dropped."""
        held = self.held.pop(name, None)
        if held is not None:
            held.reader.stop()
        lease = self.leases.pop(name, None)
        if lease is not None:
            lease.let_go()

    def release(self) -> None:
        """Stop every reader and give back each lease, its position written."""
        for held in self.held.values():
            held.reader.stop()
        try:
            self.write(final=True)
        finally:
            for held in self.held.values():
                held.reader.join(timeout=5)
            self.held.clear()
            for lease in self.leases.values():
                lease.let_go()
            self.leases.clear()

    def heard(self, payload: dict[str, Any]) -> None:
        """A `map.changed` from another process, in the listener's thread: the watch reads its logs, rules and state
        again only when it names one of their tables, or names none, which may have changed anything."""
        if payload.get('project') not in (None, self.store.project_id):
            return
        tables = payload.get('tables')
        if tables is None or (isinstance(tables, list) and CONCERNS & set(cast(list[Any], tables))):
            self.events.put((None, ('changed',)))

    def stop(self) -> None:
        """End `run`, from any thread."""
        self.stopping = True
        self.events.put((None, ('stop',)))

    # -------------------------------------------------------------- reading

    def drain(self, first: tuple[sources.Source | None, sources.Event] | None = None) -> None:
        """Take what the readers and leases have handed over: join lines into entries and group each entry captured.
        `first` is an event already taken from the queue."""
        now = self.monotonic()
        while True:
            if first is not None:
                source, event = first
                first = None
            else:
                try:
                    source, event = self.events.get_nowait()
                except queue.Empty:
                    break
            if source is None:  # the watch's own events
                if event[0] == 'lease':
                    self.taken(str(event[1]))
                    self.dirty = True
                elif event[0] == 'changed':
                    self.claim_due = True
                elif event[0] == 'lease-failed':
                    self.ctx.say(f'autoticket: the lease of {event[1]} could not be taken: {event[2]}')
                continue
            held = self.held.get(source.name)
            if held is None:
                continue
            kind = event[0]
            # something to write: a line read, a drop or a reconnect, or a file started at another place than written
            self.dirty = self.dirty or kind != 'file' or (event[1], event[2]) != (held.identity, held.offset)
            if kind == 'line':
                self.totals.lines += 1
                for entry in held.assembler.feed(event[1], event[2], now):
                    self.take(held, entry)
                held.offset = event[3]
                held.retry_delay = sources.BACKOFF_FIRST
            elif kind == 'file':  # a new file, or the same one from its start: what was open is closed
                for entry in held.assembler.flush():
                    self.take(held, entry)
                held.identity, held.offset = event[1], event[2]
                if held.recovering:
                    held.reconnects += 1
                    held.recovering = False
            elif kind == 'failed':
                held.drops += 1
                held.last_drop = f'{now_text(self.clock())} {event[1]}'
                self.totals.drops += 1
                held.retry_at = now + held.retry_delay
                held.retry_delay = min(held.retry_delay * 2, sources.BACKOFF_MOST)
            elif kind == 'drop':
                for entry in held.assembler.flush():
                    self.take(held, entry)
                held.drops += 1
                held.last_drop = f'{now_text(self.clock())} {event[1]}'
                self.totals.drops += 1
            elif kind == 'reconnect':
                held.reconnects += 1
        for held in self.held.values():
            if held.retry_at is not None:
                continue  # recover the unfinished entry from its persisted start, rather than splitting it
            for entry in held.assembler.idle(now):  # closed by its quiet time: a count to write
                self.dirty = True
                self.take(held, entry)

    def take(self, held: Held, entry: entries.Entry) -> None:
        text = entry.text
        if not entries.captured(text, self.mode, self.rules):
            return
        self.totals.captured += 1
        terms = grouping.fingerprint(text)
        at = self.clock()
        matched = grouping.first_match(terms, self.known, self.threshold)
        if matched is not None:
            group = next((one for one in held.groups if one.group_id == matched), None)
        else:
            fresh = [(index, one.terms) for index, one in enumerate(held.groups) if one.group_id is None]
            index = grouping.first_match(terms, fresh, self.threshold)
            group = held.groups[index] if index is not None else None
        if group is None:
            group = Group(terms=terms, first=at, group_id=matched,
                          example=entries.example(text, self.secrets) if matched is None else '')
            held.groups.append(group)
        group.count += 1
        group.last = at
        if not group.first:
            group.first = at

    def retry_readers(self) -> None:
        """Replace failed readers from committed checkpoints while retaining their log leases."""
        if self.stopping:
            return
        due = [name for name, held in self.held.items()
               if held.retry_at is not None and held.retry_at <= self.monotonic()]
        if not due:
            return
        # Persist completed groups and the start of any unfinished entry together before replacing a reader.
        # A failed commit propagates to service recovery; no replacement can skip uncommitted evidence.
        self.settle(self.write())
        for name in due:
            held = self.held.get(name)
            if held is None:
                continue
            with self.store.tables(write=False) as tx:
                row = tx.get('logs', {'source': name})
            if row is None or row['holder'] != self.me:
                self.drop(name)
                continue
            held.reader.join(timeout=5)
            held.identity, held.offset = str(row['identity'] or ''), int(row['offset'])
            held.assembler = entries.Assembler()
            held.reader = sources.reader(held.source, held.identity, held.offset, self.events)
            held.retry_at = None
            held.recovering = True
            held.reader.start()

    # -------------------------------------------------------------- writing

    def write(self, *, final: bool = False) -> list[dict[str, Any]]:
        """Write each held log's counts, position and beat in one transaction; a log whose lease another process has
        taken is let go, what it read since its last write dropped, since the new holder reads it again. Returns the
        groups made."""
        at = self.clock()
        made: list[dict[str, Any]] = []
        lost: list[str] = []
        with self.store.tables() as tx:
            self.known = [(int(row['group_id']), grouping.decode(str(row['fingerprint'])))
                          for row in tx.rows('groups', limit=0).results]
            for name, held in self.held.items():
                row = tx.get('logs', {'source': name})
                if row is None or row['holder'] != self.me:
                    lost.append(name)
                    continue
                for group in held.groups:
                    made += self.count(tx, group)
                held.groups.clear()
                position = (held.identity, held.position)
                tx.update('logs', {'source': name}, {
                    'holder': '' if final else self.me, 'beat': 0.0 if final else at,
                    'identity': position[0], 'offset': position[1],
                    'drops': int(row['drops']) + held.drops, 'reconnects': int(row['reconnects']) + held.reconnects,
                    **({'last_drop': held.last_drop} if held.last_drop else {})})
                held.drops, held.reconnects, held.last_drop = 0, 0, ''
        for name in lost:
            self.drop(name)
        self.written_at = at
        self.dirty = False
        self.totals.made += len(made)
        return made

    def count(self, tx: TableTx, group: Group) -> list[dict[str, Any]]:
        """Add a group's count: to the group it belongs to, or as a new group, matched again against those another
        process wrote since this one last read them, so both count one kind as one group."""
        group_id = group.group_id
        if group_id is None:
            group_id = grouping.first_match(group.terms, self.known, self.threshold)
        if group_id is not None:
            row = tx.get('groups', {'group_id': group_id})
            if row is not None:
                tx.update('groups', {'group_id': group_id}, {'count': int(row['count']) + group.count,
                                                             'last_seen': now_text(max(group.last, 0))})
                self.touched.add(group_id)
                return []
        row = tx.insert('groups', {'fingerprint': grouping.encode(group.terms), 'example': group.example,
                                   'count': group.count, 'first_seen': now_text(group.first),
                                   'last_seen': now_text(group.last), 'active': json.dumps(active_work(self.store)),
                                   'source': 'log', 'reproduce': '', 'address': '', 'number': 0, 'work_id': ''})
        self.known.append((int(row['group_id']), group.terms))
        self.touched.add(int(row['group_id']))
        return [row]

    def settle(self, made: list[dict[str, Any]]) -> None:
        """Place committed groups on the map and announce capture separately from repair-ticket policy."""
        touched, self.touched = self.touched, set()
        if not touched:
            return
        placed: dict[int, tuple[str, int]] = {}
        for row in made:
            address = place(self.ctx, self.store, str(row['example']))
            if address:
                placed[int(row['group_id'])] = (address, self.store.number(address))
        if placed:
            with self.store.tables() as tx:
                for group_id, (address, number) in placed.items():
                    tx.update('groups', {'group_id': group_id}, {'address': address, 'number': number})
        project = self.store.project_id
        bound = self.store.bound_base()
        self.ctx.publish('map.changed', {'project': project, 'base_id': bound.id if bound else None,
                                        'tables': ['autoticket.groups'], 'kinds': ['log_capture']})
        deliveries = self.ctx.publish('autoticket.captured', {'project': project, 'groups': sorted(touched)})
        failed = [one for one in deliveries if one['status'] != 'completed']
        if failed:
            self.touched.update(touched)
            details = ', '.join(f'{one["module"]}: {one.get("error") or one["status"]}' for one in failed)
            raise RuntimeError(f'autoticket.captured delivery failed: {details}')

    # -------------------------------------------------------------- one turn

    def tick(self, first: tuple[sources.Source | None, sources.Event] | None = None) -> None:
        """One turn: the logs read again when a change asked for it, what was handed over taken, and what was read
        written once its batch is due."""
        self.drain(first)
        if self.claim_due:  # once for a burst of changes, in the turn they arrived in
            self.claim()
        if self.dirty and self.clock() - self.written_at >= BEAT_SECONDS:
            self.settle(self.write())
        self.retry_readers()

    def wait(self) -> float | None:
        """Seconds until the next deadline, an open entry's quiet time or the write batch; None while there is none.
        No wait while the logs are to be read again, at the first turn too."""
        if self.claim_due:
            return 0.0
        now, at = self.monotonic(), self.clock()
        due = [held.assembler.closes_at - now for held in self.held.values()
               if held.retry_at is None and held.assembler.closes_at is not None]
        due.extend(held.retry_at - now for held in self.held.values() if held.retry_at is not None)
        if self.dirty:
            due.append(self.written_at + BEAT_SECONDS - at)
        return max(0.0, min(due)) if due else None

    def run(self, ends: float | None = None) -> None:
        """Turn on each event and at each deadline until `stop`, or until the monotonic time `ends`."""
        while not self.stopping:
            left = self.wait()
            if ends is not None:
                left = max(0.0, ends - self.monotonic() if left is None else min(ends - self.monotonic(), left))
            try:
                first = self.events.get(timeout=left)
            except queue.Empty:
                first = None
            if first is not None and first[0] is None and first[1][0] == 'stop':
                return
            self.tick(first)
            if ends is not None and self.monotonic() >= ends:
                return
