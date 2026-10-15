"""The watch: reads the project's watched logs, joins their lines into entries, groups the entries it captures, and
keeps each group's counter; it tells the orchestrator a ranked list every interval and a group never seen before at
once, once the first list has set the baseline.

Each log is read by one process at a time, the holder of its lease in the logs table. The holder writes its counts,
its position in the log and its lease's beat together, at most once a second, so another process that takes the log
over when the holder dies resumes from the last position written: an entry is counted by the process that wrote the
position past it, and by no other.
"""
from __future__ import annotations

import json
import os
import queue
import re
import secrets
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

from metaform import settings
from metaform.data import Store, TableTx
from metaform.module import Context, call, surface
from metaform.module import context as call_context

from . import entries, grouping, sources

BEAT_SECONDS = 1.0  # counts, positions and the lease's beat are written at most once a second
LEASE_SECONDS = 15.0  # a lease not beaten for this long is free: its holder is dead, hung or on another machine
CLAIM_SECONDS = 2.0  # how often logs not held here are looked at, to take one whose holder has died
LIST_LIMIT = 20  # groups in the list the orchestrator is sent; the rest are read with autoticket list
EXAMPLE_LINE = 300  # characters of an example's first line in a list or a report


def now_text(at: float | None = None) -> str:
    return datetime.fromtimestamp(time.time() if at is None else at, UTC).strftime('%Y-%m-%dT%H:%M:%SZ')


def holder_id() -> str:
    """This process's name on a lease: its host and pid, and a token so a reused pid is never taken for it."""
    return f'{socket.gethostname()}:{os.getpid()}:{secrets.token_hex(4)}'


def holder_dead(holder: str, beat: float, at: float) -> bool:
    """Whether a lease's holder is gone: a process of this host that no longer runs, or a beat older than
    LEASE_SECONDS."""
    if not holder:
        return True
    host, _, rest = holder.partition(':')
    pid = rest.partition(':')[0]
    if host == socket.gethostname() and pid.isdigit():
        try:
            os.kill(int(pid), 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            pass
    return at - beat > LEASE_SECONDS


def similarity(folder: Any) -> float:
    try:
        return float(settings.value('autoticket_similarity', folder))
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


def put_state(tx: TableTx, name: str, value: str) -> None:
    if tx.get('state', {'name': name}) is None:
        tx.insert('state', {'name': name, 'value': value})
    else:
        tx.update('state', {'name': name}, {'value': value})


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


def code_address(ctx: Context, store: Store, file: str, function: str | None) -> str | None:
    """The Address the code index maps a file and function to, through map's code-context; None when the map module
    is off, has no code index, or maps neither."""
    verb = next((one for module in surface(ctx.folder) if module.id == 'map' for one in module.verbs
                 if one.name == 'code-context'), None)
    if verb is None:
        return None
    root = os.path.realpath(store.project().path)
    path = file.replace('\\', '/')
    if os.path.isabs(file):
        real = os.path.realpath(file)
        if not real.startswith(root + os.sep):
            return None
        path = os.path.relpath(real, root).replace(os.sep, '/')
    for nouns in ([{'file': path, 'symbol': function}] if function else []) + [{'file': path}]:
        try:
            got: Any = call(verb.run, call_context('map', ctx.folder, project=store.project_id,
                                                  nouns={**nouns, 'limit': 5}))
        except Exception:  # noqa: BLE001, S112  no code index, or nothing there: the next try, then the top node
            continue
        found: Any = cast(dict[str, Any], got).get('address') if isinstance(got, dict) else None
        if isinstance(found, list) and found:
            return str(cast(list[Any], found)[0])
        if isinstance(found, str) and found:
            return found
    return None


def place(ctx: Context, store: Store, example: str) -> str | None:
    """Where a group sits: the Address of the file and function its trace names, else the project's top node."""
    found = entries.location(example)
    address = code_address(ctx, store, *found) if found is not None else None
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


# ------------------------------------------------------------------------------------------------ the list

def ranked(tx: TableTx) -> list[dict[str, Any]]:
    """Every group, most counted first, with its change since the last list."""
    found = [dict(row) for row in tx.rows('groups', limit=0).results]
    found.sort(key=lambda row: (-int(row['count']), int(row['group_id'])))
    return [shown(row) for row in found]


def shown(row: dict[str, Any]) -> dict[str, Any]:
    address, number = row.get('address') or None, row.get('number')
    return {'group': int(row['group_id']), 'count': int(row['count']),
            'change': int(row['count']) - int(row['listed'] or 0), 'example': first_line(str(row['example'])),
            'address': address, **({'item': f'{address}#{int(number):x}'} if address and number else {}),
            'first_seen': row['first_seen'], 'last_seen': row['last_seen'],
            **({'work_id': row['work_id']} if row.get('work_id') else {})}


def make_list(tx: TableTx, at: float) -> dict[str, Any]:
    """The list now, written as the last list: each group's counter is remembered for the next change, and the first
    list since a reset sets the baseline, every group in it known."""
    groups = ranked(tx)
    baseline = not state(tx, 'baseline')
    for group in groups:
        tx.update('groups', {'group_id': group['group']}, {'listed': group['count'], 'known': 1})
    if baseline:
        put_state(tx, 'baseline', now_text(at))
    put_state(tx, 'listed_at', str(at))
    logs = [{'log': row['source'], 'drops': int(row['drops']), 'reconnects': int(row['reconnects']),
             **({'last_drop': row['last_drop']} if row['last_drop'] else {})}
            for row in tx.rows('logs', limit=0).results if int(row['drops'])]
    return {'baseline': baseline, 'at': now_text(at), 'groups': groups, 'logs': logs}


def signal(ctx: Context, kind: str, details: dict[str, Any]) -> None:
    """Tell the orchestrator: a signal it reads, BASE-057, kept by dispatch where dispatch is on."""
    ctx.publish('signal.raised', {'signal': kind, 'module': 'autoticket', **details})


def send_list(ctx: Context, listed: dict[str, Any]) -> None:
    signal(ctx, 'autoticket-list', {'baseline': listed['baseline'], 'at': listed['at'],
                                    'groups': listed['groups'][:LIST_LIMIT], 'more': max(0, len(listed['groups'])
                                                                                         - LIST_LIMIT),
                                    **({'logs': listed['logs']} if listed['logs'] else {})})


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
    reported: int = 0
    lists: int = 0
    drops: int = 0


class Watch:
    def __init__(self, ctx: Context, store: Store, *, clock: Callable[[], float] = time.time,
                 monotonic: Callable[[], float] = time.monotonic) -> None:
        self.ctx, self.store, self.clock, self.monotonic = ctx, store, clock, monotonic
        self.me = holder_id()
        self.events: queue.Queue[tuple[sources.Source, sources.Event]] = queue.Queue()
        self.held: dict[str, Held] = {}
        self.known: list[tuple[int, tuple[int, ...]]] = []  # every group written, in the order made
        self.threshold = similarity(ctx.folder)
        self.mode = str(settings.value('autoticket_capture', ctx.folder) or 'errors')
        self.interval = 60.0 * int(settings.value('autoticket_interval_minutes', ctx.folder) or 15)
        self.secrets = secret_values(ctx.folder)
        self.rules: list[re.Pattern[str]] = []
        self.written_at = 0.0
        self.claimed_at = -CLAIM_SECONDS
        self.totals = Totals()

    # -------------------------------------------------------------- leases

    def claim(self) -> None:
        """Take the lease of each watched log that no live process holds, and start reading it where it was left."""
        at = self.clock()
        started: list[tuple[sources.Source, str, int]] = []
        with self.store.tables() as tx:
            self.rules = rules(tx)
            if not state(tx, 'listed_at'):  # the first interval starts with the first watch
                put_state(tx, 'listed_at', str(at))
            for row in tx.rows('logs', limit=0).results:
                name = str(row['source'])
                if name in self.held:
                    continue
                if row['holder'] != self.me and not holder_dead(str(row['holder']), float(row['beat'] or 0), at):
                    continue
                tx.update('logs', {'source': name}, {'holder': self.me, 'beat': at})
                started.append((sources.Source(name), str(row['identity'] or ''), int(row['offset'])))
        for source, identity, offset in started:
            reader = sources.reader(source, identity, offset, self.events)
            self.held[source.name] = Held(source, reader, identity=identity, offset=offset)
            reader.start()

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

    # -------------------------------------------------------------- reading

    def drain(self) -> None:
        """Take what the readers have read: join lines into entries and group each entry captured."""
        now = self.monotonic()
        while True:
            try:
                source, event = self.events.get_nowait()
            except queue.Empty:
                break
            held = self.held.get(source.name)
            if held is None:
                continue
            kind = event[0]
            if kind == 'line':
                self.totals.lines += 1
                for entry in held.assembler.feed(event[1], event[2], now):
                    self.take(held, entry)
                held.offset = event[3]
            elif kind == 'file':  # a new file, or the same one from its start: what was open is closed
                for entry in held.assembler.flush():
                    self.take(held, entry)
                held.identity, held.offset = event[1], event[2]
            elif kind == 'drop':
                for entry in held.assembler.flush():
                    self.take(held, entry)
                held.drops += 1
                held.last_drop = f'{now_text(self.clock())} {event[1]}'
                self.totals.drops += 1
            elif kind == 'reconnect':
                held.reconnects += 1
        for held in self.held.values():
            for entry in held.assembler.idle(now):
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
            held = self.held.pop(name)
            held.reader.stop()
        self.written_at = at
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
                return []
        row = tx.insert('groups', {'fingerprint': grouping.encode(group.terms), 'example': group.example,
                                   'count': group.count, 'first_seen': now_text(group.first),
                                   'last_seen': now_text(group.last), 'active': json.dumps(active_work(self.store)),
                                   'listed': 0, 'known': 0, 'address': '', 'number': 0, 'work_id': ''})
        self.known.append((int(row['group_id']), group.terms))
        return [row]

    def settle(self, made: list[dict[str, Any]]) -> None:
        """Place each group made on the map, and report it at once when the baseline is set."""
        if not made:
            return
        placed: dict[int, tuple[str, int]] = {}
        for row in made:
            address = place(self.ctx, self.store, str(row['example']))
            if address:
                placed[int(row['group_id'])] = (address, self.store.number(address))
        report: list[dict[str, Any]] = []
        with self.store.tables() as tx:
            baseline = bool(state(tx, 'baseline'))
            for row in made:
                group_id = int(row['group_id'])
                address, number = placed.get(group_id, ('', 0))
                changed = {'address': address, 'number': number, **({'known': 1} if baseline else {})}
                now = tx.update('groups', {'group_id': group_id}, changed)
                if baseline and now is not None:
                    # `working`, never `active`: dispatch reads `active` on a signal as its own raised-or-cleared flag
                    report.append({**shown(now), 'working': json.loads(str(now['active']) or '{}')})
        for group in report:
            signal(self.ctx, 'autoticket-new', group)
            self.totals.reported += 1
        project = self.store.project_id
        bound = self.store.bound_base()
        self.ctx.publish('map.changed', {'project': project, 'base_id': bound.id if bound else None})

    def report(self) -> dict[str, Any] | None:
        """The ranked list, when its interval has passed since the last one, claimed so only one process sends it."""
        at = self.clock()
        with self.store.tables() as tx:
            last = state(tx, 'listed_at')
            if last and at - float(last) < self.interval:
                return None
            listed = make_list(tx, at)
        send_list(self.ctx, listed)
        self.totals.lists += 1
        return listed

    # -------------------------------------------------------------- one turn

    def tick(self) -> None:
        if self.monotonic() - self.claimed_at >= CLAIM_SECONDS:
            self.claimed_at = self.monotonic()
            self.claim()
        self.drain()
        if self.clock() - self.written_at >= BEAT_SECONDS:
            self.settle(self.write())
            self.report()
