"""Faults file themselves: every fault Metaform raises reaches this module as a `fault.raised` event, and each new kind
becomes one ticket at once, so a project heals with no one reading logs.

A source publishes what failed and where: `source` (`web`, `page`, `mcp`, `run`, `feedback`), `message`, the one line
saying what failed; `detail`, a traceback, a stack or the text reported; `file`, the failing file when the source knows
it, else the one the detail's trace names; `reproduce`, how to make it happen again; `work_id`, the ticket of the agent
whose call failed, when one did; and `count`, when the source merged repeats of it before sending. A source with several
faults at once, the page's errors of one second, publishes them as one event whose `faults` is the list of them.

Faults are grouped as log entries are, `grouping.py`, among those raised at the same place: the same source, file and
function. So one kind of error is one group however often it repeats, and the words a source puts around every error it
raises never make two errors one. A group never seen before is filed as a ticket of kind broken at the element that owns its file, `watch.file_address`;
a group that recurs while its ticket is open has its count and last seen written in that ticket's note. At most
`autoticket_open_most` filed tickets are open and not held at once: the rest wait as groups, and the oldest is filed
when one of those tickets is done or held. A fault raised by an agent working a ticket autoticket filed is counted on that ticket. Feedback,
whose answer is a design choice, and an error that names deleting or removing data are filed held for the person.

Event rules, CLAUDE.md section 2: the faults that arrive while a pass for the same project runs merge into its next
pass, so a burst costs one pass; and the map.changed subscriber that files a waiting group decides from the event
alone whether a ticket of this module may have closed, so changes that do not concern it cost no read.
"""
from __future__ import annotations

import json
import re
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass
from importlib import resources
from typing import Any, cast

from metaform import events, prompt_files, settings
from metaform.data import Node, Store, StoreError
from metaform.module import Context

from . import entries, grouping
from .watch import active_work, first_line, now_text, place, secret_values, similarity

HERE = resources.files(__package__ or 'metaform.modules.autoticket')
TOPIC = 'fault.raised'
SOURCES = {'web': 'the web server', 'page': 'the web page', 'mcp': 'an MCP tool call', 'run': 'an agent run',
           'feedback': 'a feedback report', 'log': 'a watched log'}
TITLES = {'web': 'Web server fault', 'page': 'Page error', 'mcp': 'MCP tool failure', 'run': 'Agent run failure',
          'feedback': 'Feedback', 'log': 'Log error'}
FILING = 'filing '  # a group's work_id while one process files it: `filing <time>`
FILING_STALE = 60.0  # seconds after which a filing never finished, its process gone, is taken up again
# the words of a message whose fix may delete or remove data, so the ticket waits for the person
REMOVES = re.compile(r'\b(?:delet|remov|drop|purg|wip|truncat|eras)\w*', re.IGNORECASE)


@dataclass
class Fault:
    """One fault as its source said it, with how many times it came while it waited for a pass, and the group a
    pass counted it in."""
    source: str
    message: str
    detail: str
    file: str
    reproduce: str
    work_id: str
    count: int
    first: float
    last: float
    group_id: int = 0


PENDING: dict[str, dict[tuple[str, str, str, str], Fault]] = {}  # by project: faults waiting for a pass
PASSING: set[str] = set()  # the projects a pass runs for now, in some thread of this process
LOCK = threading.Lock()


def fault_of(payload: dict[str, Any]) -> Fault | None:
    message = str(payload.get('message') or '').strip()
    if not message:
        return None
    count = payload.get('count')
    at = time.time()
    return Fault(source=str(payload.get('source') or 'log'), message=message, detail=str(payload.get('detail') or ''),
                 file=str(payload.get('file') or ''), reproduce=str(payload.get('reproduce') or ''),
                 work_id=str(payload.get('work_id') or ''),
                 count=count if isinstance(count, int) and count > 0 else 1, first=at, last=at)


def raised(payload: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """`fault.raised`: the fault, or each of its `faults`, waits with the others of its project, and a pass runs unless
    one runs already, which then takes them in its next turn; the pass ends once nothing waits. A pass it ran returns
    `tickets`, the tickets its faults were filed or counted on, so the caller can name them."""
    given = payload.get('faults')
    each = [cast(dict[str, Any], one) for one in cast(list[Any], given) if isinstance(one, dict)] \
        if isinstance(given, list) else [payload]
    found = [fault for fault in map(fault_of, each) if fault is not None]
    store = ctx.store
    if not found or store is None:
        return {'taken': False}
    project = store.project_id
    with LOCK:
        waiting = PENDING.setdefault(project, {})
        mine: list[Fault] = []
        for fault in found:
            key = (fault.source, fault.message, fault.file, fault.work_id)
            had = waiting.get(key)
            if had is None:
                waiting[key] = fault
            else:
                had.count, had.last = had.count + fault.count, fault.last
            mine.append(waiting[key])
        if project in PASSING:
            return {'taken': True, 'merged': True}
        PASSING.add(project)
    filed = 0
    try:
        while True:
            with LOCK:
                batch = PENDING.pop(project, {})
                if not batch:
                    break
            filed += settle(ctx, store, list(batch.values()))
    finally:
        with LOCK:
            PASSING.discard(project)
    with store.tables(write=False) as tx:
        rows = [tx.get('groups', {'group_id': group_id}) for group_id in dict.fromkeys(f.group_id for f in mine)]
    tickets = [str(row['work_id']) for row in rows
               if row is not None and row['work_id'] and not str(row['work_id']).startswith(FILING)]
    return {'taken': True, 'filed': filed, 'tickets': list(dict.fromkeys(tickets))}


def settle(ctx: Context, store: Store, batch: list[Fault]) -> int:
    """One pass: each fault counted in its group, a new group placed on the map, then told to its ticket or filed.
    Returns how many tickets were filed."""
    threshold, secrets = similarity(ctx.folder), secret_values(ctx.folder)
    touched: set[int] = set()
    by_agent: dict[int, str] = {}
    made: dict[int, Fault] = {}
    with store.tables() as tx:
        known = [(int(row['group_id']), grouping.decode(str(row['fingerprint'])))
                 for row in tx.rows('groups', limit=0).results]
        for fault in batch:
            terms = fingerprint(fault)
            found = matched(terms, known, threshold)
            row = None if found is None else tx.get('groups', {'group_id': found})
            if row is not None:
                group_id = int(row['group_id'])
                tx.update('groups', {'group_id': group_id}, {'count': int(row['count']) + fault.count,
                                                             'last_seen': now_text(fault.last)})
            else:
                row = tx.insert('groups', {
                    'fingerprint': grouping.encode(terms),
                    'example': entries.example(f'{fault.message}\n{fault.detail}'.strip(), secrets),
                    'count': fault.count, 'first_seen': now_text(fault.first), 'last_seen': now_text(fault.last),
                    'active': json.dumps(active_work(store)),
                    'source': fault.source, 'reproduce': entries.mask(fault.reproduce, secrets), 'address': '',
                    'number': 0, 'work_id': ''})
                group_id = int(row['group_id'])
                known.append((group_id, terms))
                made[group_id] = fault
            fault.group_id = group_id
            touched.add(group_id)
            if fault.work_id:
                by_agent[group_id] = fault.work_id
    placed: dict[int, tuple[str, int]] = {}
    for group_id, fault in made.items():
        address = place(ctx, store, f'{fault.message}\n{fault.detail}', fault.file or None)
        if address:
            placed[group_id] = (address, store.number(address))
    if placed:
        with store.tables() as tx:
            for group_id, (address, number) in placed.items():
                tx.update('groups', {'group_id': group_id}, {'address': address, 'number': number})
    return tell(ctx, store, touched, by_agent)


def where(fault: Fault) -> tuple[str, str]:
    """The file and function a fault was raised at: the file its source named, else its trace's innermost frame."""
    found = entries.location(fault.detail)
    if found is None:
        return fault.file, ''
    if fault.file and found[0] != fault.file:
        return fault.file, ''
    return found[0], found[1] or ''


def fingerprint(fault: Fault) -> tuple[int, ...]:
    """A fault's fingerprint: its place, the source, file and function hashed as one term, then its message's words."""
    file, function = where(fault)
    return (grouping.fnv1a_lower(f'{fault.source} {file} {function}'.encode()), *grouping.fingerprint(fault.message))


def matched(terms: tuple[int, ...], known: list[tuple[int, tuple[int, ...]]], threshold: float) -> int | None:
    """The first group raised at the same place whose message the fault's matches; an empty message matches one."""
    same = [(group_id, held[1:]) for group_id, held in known if held and held[0] == terms[0]]
    if len(terms) == 1:
        return next((group_id for group_id, rest in same if not rest), None)
    return grouping.first_match(terms[1:], same, threshold)


def tell(ctx: Context, store: Store, touched: Iterable[int], by_agent: dict[int, str]) -> int:
    """Each group counted: on its open ticket, its count and last seen written in that ticket's note; raised by an
    agent working a ticket autoticket filed, counted on that ticket; seen again after its ticket was done, waiting to
    be filed anew. Then the waiting groups filed while there is room. Returns how many were filed."""
    with store.tables(write=False) as tx:
        rows = {int(group_id): dict(row) for group_id in touched
                if (row := tx.get('groups', {'group_id': group_id})) is not None}
        agents = {work_id for work_id in by_agent.values()
                  if tx.rows('groups', {'work_id': work_id}, limit=1).results}  # tickets autoticket filed
    named = {str(row['work_id']) for row in rows.values() if row['work_id']} | agents
    records = {record.id: record for record in store.work(ids=sorted(named), limit=0).results} if named else {}
    notes: dict[str, list[dict[str, Any]]] = {}
    again: list[int] = []
    for group_id, row in rows.items():
        record = records.get(str(row['work_id']))
        agent = by_agent.get(group_id)
        if record is not None and not record.done:
            notes.setdefault(record.id, []).append(row)
        elif agent in agents and (on := records.get(agent)) is not None and not on.done:
            row['work_id'] = agent
            notes.setdefault(agent, []).append(row)
        elif record is not None:  # its ticket is done and it came back: a new ticket, `file_waiting`
            again.append(group_id)
    with store.tables() as tx:
        for group_id in again:
            tx.update('groups', {'group_id': group_id}, {'work_id': ''})
        for work_id, told in notes.items():
            for row in told:
                tx.update('groups', {'group_id': int(row['group_id'])}, {'work_id': work_id})
    for work_id, told in notes.items():
        note = noted(records[work_id].note or '', told)
        if note != (records[work_id].note or ''):
            events.announced(ctx.folder, ctx.surface, store.edit_work, work_id, {'note': note})
    return file_waiting(ctx, store)


def line(row: dict[str, Any]) -> str:
    count = int(row['count'])
    return (f'autoticket group {int(row["group_id"])}: seen {count} {"time" if count == 1 else "times"}, first '
            f'{row["first_seen"]}, last {row["last_seen"]}: {first_line(str(row["example"]))}')


def noted(note: str, rows: list[dict[str, Any]]) -> str:
    """The note with each group's line written in place of its last, or added at its end."""
    for row in rows:
        start = f'autoticket group {int(row["group_id"])}: '
        lines: list[str] = note.split('\n') if note else []
        at = next((index for index, one in enumerate(lines) if one.startswith(start)), None)
        if at is None:
            lines.append(line(row))
        else:
            lines[at] = line(row)
        note = '\n'.join(lines)
    return note


def file_waiting(ctx: Context, store: Store) -> int:
    """File the waiting groups, oldest first, while fewer than `autoticket_open_most` tickets it filed are open and not
    held: a held ticket waits for the person and starts no agent work, so it takes no slot. Each group is claimed first,
    so two processes never file one group twice. Returns how many were filed."""
    most = int(settings.value('autoticket_open_most', ctx.folder) or 5)
    at = time.time()
    with store.tables(write=False) as tx:
        rows = [dict(row) for row in tx.rows('groups', limit=0).results]
    filed_ids = sorted({str(row['work_id']) for row in rows if row['work_id'] and not filing(row)})
    records = store.work(ids=filed_ids, open=True, limit=0).results if filed_ids else []
    kept = holds(store, [record.id for record in records])
    open_now = sum(not record.held and record.id not in kept for record in records)
    waiting = sorted((row for row in rows if row['address'] and waits(row, at)), key=lambda row: int(row['group_id']))
    filed = 0
    for row in waiting[:max(0, most - open_now)]:
        group_id = int(row['group_id'])
        with store.tables() as tx:
            now = tx.get('groups', {'group_id': group_id})
            if now is None or not waits(dict(now), at):
                continue
            tx.update('groups', {'group_id': group_id}, {'work_id': f'{FILING}{at}'})
        try:
            record = events.announced(ctx.folder, ctx.surface, ticket, store, dict(now))[0]
        except Exception:
            with store.tables() as tx:
                tx.update('groups', {'group_id': group_id}, {'work_id': ''})
            raise
        with store.tables() as tx:
            tx.update('groups', {'group_id': group_id}, {'work_id': record.id})
        filed += 1
    return filed


def holds(store: Store, work_ids: list[str]) -> set[str]:
    """Those of these tickets the person holds, `map_work hold=true`, kept in the map module's own table: a hold keeps
    agents and automatic starts off a ticket as the Backlog's held mark does. Read by key; none without the map module."""
    if not work_ids:
        return set()
    try:
        with Store(store.project_id, module='map').tables(write=False) as tx:
            found = [tx.get('ticket_settings', {'work_id': work_id}) for work_id in work_ids]
    except StoreError:
        return set()
    return {str(row['work_id']) for row in found if row is not None and row['hold']}


def filing(row: dict[str, Any]) -> bool:
    return str(row['work_id']).startswith(FILING)


def waits(row: dict[str, Any], at: float) -> bool:
    """Whether a group waits to be filed: never filed, seen again after its ticket was done, or claimed by a filing
    whose process ended before it finished."""
    work_id = str(row['work_id'])
    if not work_id:
        return True
    if work_id.startswith(FILING):
        try:
            return at - float(work_id[len(FILING):]) > FILING_STALE
        except ValueError:
            return True
    return False


def held_why(row: dict[str, Any]) -> str | None:
    """Why a group's ticket waits for the person: feedback asks how Metaform should work, a design choice; an error
    naming deleting or removing data may be fixed only by deleting or removing data. None when neither."""
    if row['source'] == 'feedback':
        return prompt_files.text(HERE, 'held_design') or 'Feedback asks how Metaform should work: a design choice.'
    if REMOVES.search(first_line(str(row['example']))):
        return prompt_files.text(HERE, 'held_data') or 'Its fix may delete or remove data.'
    return None


def ticket(store: Store, row: dict[str, Any]) -> Any:
    """The ticket for a group: kind broken, at its element, its task the evidence, how to reproduce it and that the fix
    proves itself; held for the person, with why, when its fix is a design choice or removes data."""
    count = int(row['count'])
    example = str(row['example'])
    task = prompt_files.required(
        HERE, 'ticket', message=first_line(example), count=f'{count} {"time" if count == 1 else "times"}',
        first=str(row['first_seen']), last=str(row['last_seen']), sample=example,
        source=SOURCES.get(str(row['source']), str(row['source'])),
        reproduce=str(row['reproduce'] or 'not known; the sample above is all that was seen'))
    why = held_why(row)
    note = '\n'.join([*([f'Held for the person: {why}'] if why else []), line(row)])
    title = f'{TITLES.get(str(row["source"]), "Error")}: {first_line(example)}'[:120]
    return store.add_work(Node('element', str(row['address'])), None, kind='broken', title=title, note=note,
                          task=task, held=why is not None)


def freed(payload: dict[str, Any], ctx: Context) -> None:
    """`map.changed`: a ticket autoticket filed may be done or held, its slot free for a waiting group. Decided from the
    event alone: one naming tables other than `work`, or only words, steps or sessions of tickets, concerns it not; one
    naming tickets reads whether any of them is one it filed and done or held; one that does not say what it concerns
    may have closed any, so the waiting groups are looked at once. A held ticket released takes a slot and files
    nothing; `file_waiting` reads each ticket's held mark when it counts, so the next pass counts it."""
    store = ctx.store
    if store is None or payload.get('project') not in (None, store.project_id):
        return
    tables, kinds, ids = payload.get('tables'), payload.get('kinds'), payload.get('work_ids')
    if tables is not None and (not isinstance(tables, list) or 'work' not in tables):
        return
    if isinstance(kinds, list) and 'ticket' not in kinds:
        return
    if isinstance(ids, list):
        named = [str(one) for one in cast(list[Any], ids)]
        if not named:
            return
        with store.tables(write=False) as tx:
            ours = [work_id for work_id in named if tx.rows('groups', {'work_id': work_id}, limit=1).results]
        if not ours or not any(record.done or record.held for record in store.work(ids=ours, limit=0).results):
            return
    file_waiting(ctx, store)
