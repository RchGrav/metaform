"""`map work` for a project held in the project store (`metaform.project`): its tickets are the `tickets` overlay
records there, the ones the page's board reads, so a ticket an agent writes from the command line is the ticket the
person sees.

Kickoff 2026-11-17, Phase 3: consumers are aligned one capability at a time, and a feature with no place yet in the
project store is refused by name rather than dropped or read from the old store's empty map. The tickets overlay
holds id, title, task, kind, held, taken_by, note, done and outcome at an element. A ticket on a join, a condition, a
hold reason, links, boards, steps, plans, columns, glyphs and dependencies have no field there yet, so the operations
and nouns that need them are refused here. Each change names the record it found (F02), so it never lands on
another ticket.
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any, cast

from metaform import project as project_store
from metaform.module import Stop

SUPPORTED = ('list', 'read', 'add', 'edit', 'take', 'done', 'remove')
# the nouns each supported operation takes here; any other noun given is refused by name, never ignored
TAKES: dict[str, frozenset[str]] = {
    'list': frozenset({'node', 'open', 'kind', 'limit', 'after'}),
    'read': frozenset({'id'}),
    'add': frozenset({'node', 'title', 'task', 'note', 'kind', 'held', 'hold'}),
    'edit': frozenset({'id', 'title', 'task', 'note', 'kind', 'held', 'hold'}),
    'take': frozenset({'id', 'by', 'agent', 'steps', 'model', 'effort', 'fast'}),
    'done': frozenset({'id', 'resolution', 'why'}),
    'remove': frozenset({'id'}),
}
HELP = 'metaform help map work'


def project_work(project: str, op: str, nouns: dict[str, Any]) -> dict[str, Any]:
    """Answer one `map work` operation against the project's tickets in the project store."""
    if op not in SUPPORTED:
        raise Stop(f"op={op} has no place yet in the project store, where {project}'s tickets are kept: it supports "
                   f"op={', '.join(SUPPORTED[:-1])} and remove. The page's board moves cards between columns.", HELP)
    extra = sorted(name for name in nouns if name != 'op' and name not in TAKES[op] and nouns[name] not in (None, ''))
    if extra:
        raise Stop(f"{', '.join(extra)} {'has' if len(extra) == 1 else 'have'} no field yet in the project store's "
                   f"tickets, where {project}'s tickets are kept, so op={op} does not take "
                   f"{'it' if len(extra) == 1 else 'them'}. A ticket there holds id, title, task, kind, held, taken_by, "
                   'note, done and outcome at one element.', HELP)
    if op == 'list':
        return {'results': _listed(project, nouns), 'next': None}
    if op == 'add':
        return _added(project, nouns)
    found = _found(project, str(nouns['id']))
    if op == 'read':
        return _shown(project, found)
    if op == 'remove':
        _done(project_store.run({'delete': {str(found['element']): {'tickets': [found['record']]}}}))
        return {**_shown(project, found), 'removed': True}
    fields: dict[str, object] = {}
    if op == 'edit':
        fields = {name: (nouns[name] if nouns[name] != '' else None) for name in ('title', 'task', 'note', 'kind')
                  if name in nouns}
        if 'held' in nouns or 'hold' in nouns:
            fields['held'] = True if bool(nouns.get('held', nouns.get('hold'))) else None
    elif op == 'take':
        # A claim is exclusive (F09): a ticket another agent holds is refused, and the claim names the revision it
        # read, so of two claims made at once one is taken and the other is refused with RECORD_CHANGED.
        agent = str(nouns.get('by') or nouns.get('agent') or '').strip()
        if not agent:  # an exclusive claim names who claims it; the command line names it with by=
            raise Stop('op=take names who takes the ticket: by=<agent>, such as by=claude.', HELP)
        holder = found.get('taken_by')
        if holder and holder != agent and not found.get('done'):
            raise Stop(f"Ticket {found['id']!r} is taken by {holder}; it is not taken again. Its holder or the person "
                       'releases it on the board first.', f"metaform map work id={found['id']}")
        _done(project_store.run({'update': {str(found['element']): {'tickets': [
            {'position': found['position'], 'record': found['record'], 'revision': found['revision'],
             'taken_by': agent, 'held': None}]}}}))
        return _shown(project, _found(project, str(nouns['id'])))
    elif op == 'done':
        # the tickets overlay has no resolution field: it is added to the note, after what the note already says
        said = ' '.join(f'{label}: {nouns[name]}' for name, label in (('resolution', 'Resolution'), ('why', 'Why'))
                        if nouns.get(name))
        kept = str(found.get('note') or '').strip()
        fields = {'done': datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'), 'outcome': 'completed',
                  'note': ' '.join(part for part in (kept, said) if part) or None}
    if not fields:
        raise Stop(f'op={op} was given no field to change.', HELP)
    _done(project_store.run({'update': {str(found['element']): {'tickets': [
        {'position': found['position'], 'record': found['record'], **fields}]}}}))
    return _shown(project, _found(project, str(nouns['id'])))


def _records(project: str) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], project_store.overlay_records(project, 'tickets') or [])


def _found(project: str, ticket: str) -> dict[str, Any]:
    found = next((record for record in _records(project) if record.get('id') == ticket), None)
    if found is None:
        raise Stop(f"No ticket {ticket!r} in {project}'s tickets.", 'metaform map work op=list')
    return found


def _shown(project: str, record: dict[str, Any]) -> dict[str, Any]:
    """One ticket as `map work` lists it: its fields, the element it is at, and whether it is open or done."""
    address = str(record['element'])[len(project) + 1:]
    return {**{name: value for name, value in record.items() if name != 'element'}, 'node_kind': 'element',
            'node_id': address, 'address': address, 'status': 'done' if record.get('done') else 'open'}


def _listed(project: str, nouns: dict[str, Any]) -> list[dict[str, Any]]:
    node = str(nouns.get('node') or '')
    at = node.partition(':')[2] if node.startswith('element:') else node or None
    rows = [_shown(project, record) for record in _records(project)]
    return [row for row in rows if (at is None or row['address'] == at)
            and (nouns.get('open', True) is False or row['status'] == 'open')
            and (not nouns.get('kind') or row.get('kind') == nouns['kind'])]


def _added(project: str, nouns: dict[str, Any]) -> dict[str, Any]:
    node = str(nouns.get('node') or '')
    kind_of, _, address = node.partition(':')
    if kind_of != 'element' or not address:
        raise Stop("op=add needs node=element:<address>: a ticket in the project store is at one element, and a "
                   'join has no tickets there yet; put it at the join\'s receiver.', HELP)
    task = str(nouns.get('task') or nouns.get('note') or '').strip()
    title = str(nouns.get('title') or task.splitlines()[0] if task else nouns.get('title') or '').strip()
    if not title or not task:
        raise Stop('op=add needs a title and a task: what to do, in full, for an agent that knows nothing else of it.',
                   HELP)
    record: dict[str, object] = {'id': 't-' + secrets.token_hex(4), 'title': title[:120], 'task': task,
                                 **({'kind': nouns['kind']} if nouns.get('kind') else {}),
                                 **({'held': True} if nouns.get('held') or nouns.get('hold') else {}),
                                 **({'note': nouns['note']} if nouns.get('note') and nouns.get('task') else {})}
    _done(project_store.run({'add': {f'{project}.{address}': {'tickets': [record]}}}))
    return _shown(project, _found(project, str(record['id'])))


def _done(answer: dict[str, object]) -> None:
    if answer.get('status') == 'error':
        raise Stop(str(answer.get('message') or 'The ticket was not changed.'),
                   str(answer.get('remediation') or HELP))
