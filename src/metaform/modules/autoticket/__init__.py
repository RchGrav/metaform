"""autoticket: watches the project's logs while work goes on and ranks the errors in them by how often they happen.

Entries are grouped by the similarity method of onhold's log viewer, `grouping.py`; the logs are read as they grow and
never kept, `sources.py`; one process at a time reads each log, under a lease, `watch.py`. The orchestrator is sent a
ranked list every `autoticket_interval_minutes`, and, once the first list has set the baseline, a group never seen
before at once, both as signals, BASE-057. A group becomes a ticket only when promoted.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from importlib import resources
from typing import Any

from metaform import prompt_files, settings
from metaform.data import Column, Index, Node, Table, Tables, WorkRecord
from metaform.module import Context, Module, Noun, Status, Stop, Verb, held_role

from . import sources
from .sources import POLL_SECONDS
from .watch import Watch, first_line, make_list, ranked, send_list, shown, state

SUPPORTED_OS = ('linux', 'macos')  # it follows logs as tail -F does and reaches hosts through ssh and a POSIX shell
DEPENDENCIES = ()
SHIPS_DISABLED = True
REMOTE_AGENT = False  # it reads logs on the machine Metaform runs on and through its ssh

HERE = resources.files(__name__)


def _similarity_check(value: Any, folder: Any) -> list[str] | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ['autoticket_similarity is a number above 0 and at most 1, such as 0.45.']
    return None if 0 < number <= 1 else ['autoticket_similarity is a number above 0 and at most 1, such as 0.45.']


settings.number('autoticket_interval_minutes', 15, min=1, max=1440, label='List interval',
                help='How often the orchestrator is sent the ranked list of error groups; the first list sets the '
                     'baseline.')
settings.text('autoticket_similarity', '0.45', check=_similarity_check, label='Similarity',
              help='The Dice coefficient at which two entries are the same kind of error, above 0 and at most 1; '
                   '0.45 is onhold\'s value.')
settings.choice('autoticket_capture', ['errors', 'rules'], 'errors', label='Capture',
                help='What is counted: errors, the level words such as ERROR, FATAL, CRITICAL, Traceback and '
                     'Exception, with the capture rules; or rules, the capture rules alone.',
                choice_help={'errors': 'Level words and the start of a trace, with the capture rules.',
                             'rules': 'Only the entries a capture rule matches.'})


# ------------------------------------------------------------------------------------------------ tables

# autoticket's own tables, STORE-045, in the project's store so a clear of its metaforms keeps the error history.
# groups: one row per kind of error, its fingerprint, one example with secrets masked, its counter, first and last
#   seen, the agents and tickets at work when it was first seen, where it sits on the map with its item number, its
#   counter at the last list and whether the orchestrator knows it, and the ticket it was promoted to. Never the logs.
# logs: one row per watched log, the lease of the process reading it, where it has reached, and its drops.
# rules: the capture rules agents add, each a regular expression.
# state: the baseline, when the last list was made, and whether the project has no logs yet.
TABLES = Tables(version=1, tables=(
    Table('groups', place='project', key=('group_id',),
          columns=(Column('group_id', 'int', required=True), Column('fingerprint', required=True),
                   Column('example', required=True), Column('count', 'int', required=True, default=0),
                   Column('first_seen', required=True), Column('last_seen', required=True),
                   Column('active', required=True, default='{}'), Column('address', required=True, default=''),
                   Column('number', 'int', required=True, default=0), Column('listed', 'int', required=True, default=0),
                   Column('known', 'int', required=True, default=0), Column('work_id', required=True, default='')),
          indexes=(Index(('address', 'number')), Index(('work_id',)))),
    Table('logs', place='project', key=('source',),
          columns=(Column('source', required=True), Column('holder', required=True, default=''),
                   Column('beat', 'real', required=True, default=0.0), Column('identity', required=True, default=''),
                   Column('offset', 'int', required=True, default=-1), Column('drops', 'int', required=True, default=0),
                   Column('reconnects', 'int', required=True, default=0), Column('last_drop', required=True, default=''),
                   Column('added', required=True))),
    Table('rules', place='project', key=('pattern',),
          columns=(Column('pattern', required=True), Column('added', required=True))),
    Table('state', place='project', key=('name',),
          columns=(Column('name', required=True), Column('value', required=True))),
))


def _now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


# ------------------------------------------------------------------------------------------------ verbs

def add(ctx: Context) -> dict[str, Any]:
    """Watch a log: a local file, read from its end now, or ssh://<host>/<path>, read from its end at first connect."""
    store = ctx.require_store()
    try:
        source = sources.parse(str(ctx.nouns['log']))
    except ValueError as error:
        raise Stop(str(error), 'metaform autoticket add <path> or metaform autoticket add ssh://<host>/<path>') from None
    identity, offset = '', -1
    if source.remote is None:
        found = sources.local_identity(source.name)
        if found is not None:
            identity, offset = found
    with store.tables() as tx:
        if tx.get('logs', {'source': source.name}) is not None:
            return {'log': source.name, 'added': False, 'watched': True}
        tx.insert('logs', {'source': source.name, 'identity': identity, 'offset': offset, 'added': _now()})
        if state(tx, 'no_logs'):
            tx.delete('state', {'name': 'no_logs'})
    return {'log': source.name, 'added': True,
            **({'note': 'The file is not there yet; it is read from its start once it appears.'}
               if source.remote is None and offset < 0 else {})}


def remove(ctx: Context) -> dict[str, Any]:
    store = ctx.require_store()
    try:
        source = sources.parse(str(ctx.nouns['log']))
    except ValueError as error:
        raise Stop(str(error), 'metaform autoticket logs') from None
    with store.tables() as tx:
        removed = tx.delete('logs', {'source': source.name})
    if not removed:
        raise Stop(f'{source.name} is not watched.', 'metaform autoticket logs')
    return {'log': source.name, 'removed': True}


def logs(ctx: Context) -> dict[str, Any]:
    """The watched logs, who reads each, where it has reached and its drops, and the capture rules."""
    store = ctx.require_store()
    with store.tables(write=False) as tx:
        found = [{'log': row['source'], 'reader': row['holder'] or None, 'offset': row['offset'],
                  'drops': row['drops'], 'reconnects': row['reconnects'],
                  **({'last_drop': row['last_drop']} if row['last_drop'] else {}), 'added': row['added']}
                 for row in tx.rows('logs', limit=0).results]
        kept = [row['pattern'] for row in tx.rows('rules', limit=0).results]
        none = bool(state(tx, 'no_logs'))
    return {'logs': found, 'rules': kept, **({'no_logs': True} if none else {})}


def no_logs(ctx: Context) -> dict[str, Any]:
    """Record that the project has no logs to watch yet: it is not built, only its intent exists."""
    store = ctx.require_store()
    with store.tables() as tx:
        if tx.rows('logs', limit=1).results:
            raise Stop('This project has watched logs already.', 'metaform autoticket logs')
        if not state(tx, 'no_logs'):
            tx.insert('state', {'name': 'no_logs', 'value': _now()})
    return {'no_logs': True}


def add_rule(ctx: Context) -> dict[str, Any]:
    pattern = str(ctx.nouns['pattern'])
    try:
        re.compile(pattern)
    except re.error as error:
        raise Stop(f'The rule is not a regular expression: {error}.', 'metaform autoticket add-rule <pattern>') from None
    with ctx.require_store().tables() as tx:
        if tx.get('rules', {'pattern': pattern}) is None:
            tx.insert('rules', {'pattern': pattern, 'added': _now()})
    return {'rule': pattern, 'added': True}


def remove_rule(ctx: Context) -> dict[str, Any]:
    pattern = str(ctx.nouns['pattern'])
    with ctx.require_store().tables() as tx:
        removed = tx.delete('rules', {'pattern': pattern})
    if not removed:
        raise Stop('No such capture rule.', 'metaform autoticket logs')
    return {'rule': pattern, 'removed': True}


async def watch_logs(ctx: Context) -> dict[str, Any]:
    """Read every watched log this process can take the lease of, until stopped or for `seconds`."""
    store = ctx.require_store()
    seconds = ctx.nouns.get('seconds')
    ends = None if not seconds else time.monotonic() + float(seconds)
    watching = Watch(ctx, store)
    try:
        while ends is None or time.monotonic() < ends:
            await asyncio.to_thread(watching.tick)
            await asyncio.sleep(POLL_SECONDS)
    finally:
        watching.release()
    totals = watching.totals
    return {'lines': totals.lines, 'captured': totals.captured, 'groups_made': totals.made,
            'reported': totals.reported, 'lists': totals.lists, 'drops': totals.drops}


def listed(ctx: Context) -> dict[str, Any]:
    """The groups now, most counted first, with the change since the last list; it is not a list sent, so the next
    list's changes still run from the last one."""
    store = ctx.require_store()
    with store.tables(write=False) as tx:
        groups = ranked(tx)
        baseline = state(tx, 'baseline')
    limit = ctx.nouns.get('limit')
    return {'baseline': baseline or None, 'groups': groups[:limit] if isinstance(limit, int) and limit > 0 else groups}


def reset(ctx: Context) -> dict[str, Any]:
    """A clean start: the list is made now and sent, and it is the new baseline, so from here a group never seen
    before is reported at once."""
    store = ctx.require_store()
    with store.tables() as tx:
        if state(tx, 'baseline'):
            tx.delete('state', {'name': 'baseline'})
        made = make_list(tx, time.time())
    send_list(ctx, made)
    return {'baseline': made['at'], 'groups': len(made['groups'])}


def promote(ctx: Context) -> dict[str, Any]:
    """Make a group a ticket at its Address, linked back to the group so its counter shows whether the fix held."""
    if (role := held_role(ctx)) is not None:
        raise Stop(f'A {role} does not write tickets here.', 'metaform map work op=edit id=<your work id> note="..."')
    store = ctx.require_store()
    number = int(ctx.nouns['group'])
    with store.tables(write=False) as tx:
        row = tx.get('groups', {'group_id': number})
    if row is None:
        raise Stop(f'No group {number}.', 'metaform autoticket list')
    if row['work_id']:
        return {'group': number, 'work_id': row['work_id'], 'promoted': False}
    if not row['address']:
        raise Stop('The group has no place on the map yet, so it has nowhere for a ticket.', 'metaform map roots')
    title = str(ctx.nouns.get('title') or f'Error group {number}: {first_line(str(row["example"]))}')[:120]
    record = store.add_work(Node('element', str(row['address'])), '', kind='broken', title=title,
                            note=f'autoticket group {number}: {row["count"]} seen from {row["first_seen"]} to '
                                 f'{row["last_seen"]}. Its counter stops rising once the fix holds.',
                            task=f'Find and fix the cause of this error.\n\n{row["example"]}')
    with store.tables() as tx:
        tx.update('groups', {'group_id': number}, {'work_id': record.id})
    return {'group': number, 'work_id': record.id, 'promoted': True}


# ------------------------------------------------------------------------------------------------ hooks

def status(ctx: Context) -> Status:
    """A line with what is watched, and while no log is configured the notice that says to configure one: to an
    intake agent its intake step, to the person's own agent the connect notice. Both texts are read from prompts.xml,
    and nothing is sent while a text is not there."""
    store = ctx.store
    if store is None:
        return Status()
    try:
        with store.tables(write=False) as tx:
            watched = len(tx.rows('logs', limit=0).results)
            groups = len(tx.rows('groups', limit=0).results)
            none = bool(state(tx, 'no_logs'))
    except Exception:  # noqa: BLE001  a store this code cannot read adds nothing to status
        return Status()
    said = (f'Autoticket: {watched} {"log" if watched == 1 else "logs"} watched, {groups} '
            f'{"group" if groups == 1 else "groups"}')
    lines = (said,) if watched or groups else ()
    if watched or none:
        return Status(lines=lines)
    role = os.environ.get('METAFORM_ROLE') or 'none'
    name = 'intake_step' if role == 'intake' else 'connect_notice' if role == 'none' else None
    text = prompt_files.text(HERE, name) if name else None
    return Status(lines=lines, instruction=text or None)


def item_read(ctx: Context, address: str, number: int) -> dict[str, Any] | None:
    """The group numbered `number` at `address`, read as `<address>#<n>`."""
    if ctx.store is None:
        return None
    with ctx.store.tables(write=False) as tx:
        found = tx.rows('groups', {'address': address, 'number': number}, limit=1).results
    if not found:
        return None
    row = found[0]
    group = shown(dict(row))
    active = json.loads(str(row['active']) or '{}')
    return {'kind': 'error group', 'title': f'{group["count"]} × {group["example"]}'[:200],
            'why': f'Seen {group["count"]} times from {group["first_seen"]} to {group["last_seen"]}.',
            'body': str(row['example']), 'links': [f'ticket {row["work_id"]}'] if row['work_id'] else [],
            'group': group['group'], 'count': group['count'], 'first_seen': group['first_seen'],
            'last_seen': group['last_seen'], 'active_at_first_seen': active}


def items_at(ctx: Context, address: str, before: int | None, limit: int) -> list[dict[str, Any]]:
    if ctx.store is None:
        return []
    with ctx.store.tables(write=False) as tx:
        rows = [row for row in tx.rows('groups', {'address': address}, by=('address', 'number'), limit=0).results
                if row['number'] and (before is None or row['number'] < before)]
    return [{'number': int(row['number']), 'kind': 'error group',
             'title': f'{row["count"]} × {first_line(str(row["example"]))}'[:200],
             'why': f'Seen {row["count"]} times, last {row["last_seen"]}.'} for row in reversed(rows)][:limit]


def work_read(ctx: Context, record: WorkRecord) -> dict[str, Any] | None:
    """On a ticket promoted from a group: the group's counter now, so whether the fix held shows on the ticket."""
    if ctx.store is None:
        return None
    with ctx.store.tables(write=False) as tx:
        found = tx.rows('groups', {'work_id': record.id}, limit=1).results
    if not found:
        return None
    row = found[0]
    return {'group': int(row['group_id']), 'count': int(row['count']), 'last_seen': row['last_seen']}


# ------------------------------------------------------------------------------------------------ the declaration

LOG = Noun('log', 'A local log file, or ssh://<host>/<absolute path> read through the system\'s ssh.')

MODULE = Module(
    id='autoticket',
    summary='Watch the project\'s logs and rank the errors in them by how often they happen.',
    purpose='Watches the project\'s logs while work goes on, groups the errors in them by kind, and counts each kind. '
            'The orchestrator is sent a ranked list at each interval and a kind never seen before at once, so a new '
            'error is seen while the change that caused it is fresh, and a counter that stops rising shows a fix '
            'held. Details: metaform help autoticket.',
    details='Watched logs are local files or ssh://<host>/<path>, read through the system\'s own ssh with its config '
            'and keys; Metaform stores no credentials. A log is read as it grows and never kept: each group keeps one '
            'example with secrets masked, its counter, when it was first and last seen, and the agents and tickets at '
            'work when it first appeared. metaform autoticket watch reads them until stopped.',
    verbs=(
        Verb('add', add, 'Watch a log: a local file, or ssh://<host>/<absolute path>.', nouns=(LOG,),
             examples=(('metaform autoticket add /var/log/app.log', 'Watches a local log from its end now.'),
                       ('metaform autoticket add ssh://web1/var/log/app.log', 'Watches a log on the host web1.'))),
        Verb('remove', remove, 'Stop watching a log; its groups are kept.', nouns=(LOG,)),
        Verb('logs', logs, 'List the watched logs, who reads each and their drops, and the capture rules.',
             effect='read'),
        Verb('no-logs', no_logs, 'Record that the project has no logs to watch yet: it is not built, only intent.'),
        Verb('add-rule', add_rule, 'Count the entries a regular expression matches, grouped as errors are.',
             nouns=(Noun('pattern', 'A regular expression one line of an entry matches.'),)),
        Verb('remove-rule', remove_rule, 'Remove a capture rule.',
             nouns=(Noun('pattern', 'The rule as it was added.'),)),
        Verb('watch', watch_logs, 'Read the watched logs and count their errors until stopped.',
             nouns=(Noun('seconds', 'Stop after this many seconds; until stopped when left out.', 'int',
                         required=False),),
             details='Each log is read by one process at a time: another watch takes over a log whose reader has '
                     'stopped, from where it had reached.',
             task=True, open_world=True),
        Verb('list', listed, 'The error groups, most counted first, with the change since the last list.',
             nouns=(Noun('limit', 'How many groups; all when left out.', 'int', required=False),), effect='read'),
        Verb('reset', reset, 'Send the list now as the new baseline, for a clean start such as before a refactor.'),
        Verb('promote', promote, 'Make an error group a ticket at its Address, linked back to the group.',
             nouns=(Noun('group', 'The group\'s number, as autoticket list shows it.', 'int'),
                    Noun('title', 'The ticket\'s title; the group\'s example when left out.', required=False))),
    ),
    status=status,
    default='list',
    tables=TABLES,
    item_read=item_read,
    items_at=items_at,
    item_kinds=('error group',),
    work_read=work_read,
)
