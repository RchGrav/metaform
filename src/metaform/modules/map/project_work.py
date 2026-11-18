"""`map work` for a project held in the project store (`metaform.project`): its tickets are the `tickets` overlay
records there, the ones the page's board reads, so a ticket an agent writes from the command line is the ticket the
person sees.

Kickoff 2026-11-17, Phase 3: consumers are aligned one capability at a time, and a feature with no place yet in the
project store is refused by name rather than dropped or read from the old store's empty map. The tickets overlay
holds id, title, task, kind, held, taken_by, note, done and outcome at an element. A ticket on a join, a condition, a
hold reason, links, boards, columns, glyphs and dependencies have no field there yet, so the operations
and nouns that need them are refused here. Each change names the record it found (F02), so it never lands on
another ticket.
"""
from __future__ import annotations

import dataclasses
import json
import secrets
from datetime import UTC, datetime
from typing import Any, cast

from metaform import project as project_store
from metaform.data import Notice, Page, StoreError, Ticket, WorkRecord
from metaform.module import Stop

SUPPORTED = ('list', 'read', 'add', 'edit', 'take', 'plan', 'step', 'done', 'remove')
# the nouns each supported operation takes here; any other noun given is refused by name, never ignored
TAKES: dict[str, frozenset[str]] = {
    'list': frozenset({'node', 'open', 'kind', 'limit', 'after'}),
    'read': frozenset({'id'}),
    'add': frozenset({'node', 'title', 'task', 'note', 'kind', 'held', 'hold'}),
    'edit': frozenset({'id', 'title', 'task', 'note', 'kind', 'held', 'hold'}),
    'take': frozenset({'id', 'by', 'agent', 'steps', 'model', 'effort', 'fast'}),
    'plan': frozenset({'id', 'steps', 'said'}),
    'step': frozenset({'id', 'said'}),
    'done': frozenset({'id', 'resolution', 'why'}),
    'remove': frozenset({'id'}),
}
HELP = 'metaform help map work'
LIST = 50  # a list read's page when no limit is given; limit=0 reads every ticket


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
        return _paged(_listed(project, nouns), nouns)
    if op == 'add':
        return _added(project, nouns)
    found = _found(project, str(nouns['id']))
    if op == 'read':
        return _shown(project, found)
    if op in ('plan', 'step') and not found.get('completed'):  # a worker's count of steps and each it finishes
        try:
            if op == 'plan':
                stored_plan(project, str(found['id']), int(nouns['steps']) if str(nouns.get('steps') or '').isdigit()
                            else None)
            else:
                stored_step(project, str(found['id']), nouns.get('said'))
        except StoreError as error:
            raise Stop(str(error), HELP) from None
        return _shown(project, _found(project, str(found['id'])))
    if found.get('completed'):  # a completed ticket is read by its id; it changes only once it is reopened
        reopen = json.dumps({'update': {found['element']: {'tickets': [
            {'record': found['record'], 'completed': False}]}}})
        raise Stop(f"Ticket {found['id']!r} was completed at {found['completed']} and has left the board; it is read "
                   f'by its id and changes only once reopened, with the project tool: {reopen}',
                   f"metaform map work id={found['id']}")
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
                  'note': '\n\n'.join(part for part in (kept, said) if part) or None}  # its own paragraph, so a
        # writer that refreshes a line of the note, as autoticket refreshes its status line, never drops it
    if not fields:
        raise Stop(f'op={op} was given no field to change.', HELP)
    _done(project_store.run({'update': {str(found['element']): {'tickets': [
        {'position': found['position'], 'record': found['record'], **fields}]}}}))
    return _shown(project, _found(project, str(nouns['id'])))


def _found(project: str, ticket: str) -> dict[str, Any]:
    """One ticket by its id, open or completed: a reference resolves whatever became of the ticket (review of
    2026-11-18, F4), read in the store by the id alone."""
    found = cast('dict[str, Any] | None', project_store.overlay_record(project, 'tickets', 'id', ticket))
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
    held = cast(list[dict[str, Any]], project_store.overlay_records(project, 'tickets', at=at) or [])
    rows = [_shown(project, record) for record in held]  # one element's tickets are selected in the store
    return [row for row in rows if (nouns.get('open', True) is False or row['status'] == 'open')
            and (not nouns.get('kind') or row.get('kind') == nouns['kind'])]


def _paged(rows: list[dict[str, Any]], nouns: dict[str, Any]) -> dict[str, Any]:
    """One page of a list: after= is how many came before, as a previous page's `next` gives it, and limit= how many
    (limit=0 every one). `next` names the page after this one, None at the end (review of 2026-11-18, F11)."""
    after, given = str(nouns.get('after') or '0'), nouns.get('limit')
    if not (after.isascii() and after.isdigit()):
        raise Stop(f'after={after!r} is not a page of this list; read the list again without after.', HELP)
    start = int(after)
    limit = LIST if given is None or given == '' else int(given)
    page = rows[start:start + limit] if limit else rows[start:]
    more = bool(limit) and start + limit < len(rows)
    return {'results': page, 'total': len(rows), 'next': str(start + limit) if more else None}


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


# ---- The map module's work operations on a project held in the project store (review of 2026-11-18, F3) ----
#
# `Store.work`, `ticket`, `take_work`, `move_work`, `finish_work`, `edit_work`, `plan_work` and `step_work` are what
# dispatch, its runner and every other module reach tickets by. For a project held in the project store each acts on
# the tickets overlay there and answers the same record, so a ticket made on the board is the one dispatch starts,
# runs and closes, and no record of the old store is read or made for it.

@dataclasses.dataclass(frozen=True)
class StoredWork(WorkRecord):
    """A ticket of the tickets overlay as a work record. The overlay keeps no time of a take, so `taken` holds who
    took it, and its age is counted from its end alone."""
    title: str = ''

    @property
    def age_seconds(self) -> int | None:
        if self.done is None:
            return None
        ended = datetime.fromisoformat(self.done)
        return max(0, int((datetime.now(UTC) - ended).total_seconds()))


def held_name(project_id: str) -> str | None:
    """The project's name in the project store when its tickets are kept there; None otherwise."""
    name = project_store.stored_name(project_id)
    return name if project_store.holds(name) else None


def as_work(name: str, one: dict[str, Any], notices: tuple[Notice, ...] = ()) -> StoredWork:
    address = str(one['element'])[len(name) + 1:]
    note = cast('str | None', one.get('note')) or None
    steps: Any = one.get('steps')
    done = cast('str | None', one.get('done')) or None
    return StoredWork(
        id=str(one['id']), node_kind='element', node_id=address, address=address, receiver_address=None,
        provider_address=None, condition='', note=note, task=cast('str | None', one.get('task')),
        held=bool(one.get('held')), reviewed=False, created='', done=done,
        resolution=_resolution(note) if done else None, notices=notices,
        steps=int(steps) if isinstance(steps, (int, float)) else None, steps_done=int(cast(Any, one.get('steps_done')) or 0),
        taken=cast('str | None', one.get('taken_by')) or None, taken_by=cast('str | None', one.get('taken_by')) or None,
        position=cast('int | None', one.get('position')), kind=str(one.get('kind') or ''),
        outcome=(cast('str | None', one.get('outcome')) or 'completed') if done else None,
        title=str(one.get('title') or ''))


def _resolution(note: str | None) -> str | None:
    """The resolution `done` writes as the note's last paragraph, 'Resolution: ... Why: ...'."""
    last = (note or '').strip().split('\n\n')[-1]
    if not last.startswith('Resolution: '):
        return None
    return last[len('Resolution: '):].split(' Why: ')[0].strip() or None


def _one(name: str, work_id: str) -> dict[str, Any]:
    found = cast('dict[str, Any] | None', project_store.overlay_record(name, 'tickets', 'id', work_id))
    if found is None:
        raise StoreError(f'No work record has the id {work_id}.', 'metaform map work open=true')
    return found


def _changed(name: str, one: dict[str, Any], fields: dict[str, object], exact: bool = False,
             notices: tuple[Notice, ...] = ()) -> StoredWork:
    """One ticket changed, named by its position and record, and with `exact` by the revision read too, then read
    again by its id."""
    if one.get('completed'):
        raise StoreError(f"Ticket {one['id']!r} was completed and has left the board; reopen it first.",
                         f"metaform map work id={one['id']}")
    answer = project_store.run({'update': {str(one['element']): {'tickets': [
        {'position': one['position'], 'record': one['record'], **({'revision': one['revision']} if exact else {}),
         **fields}]}}})
    if answer.get('status') == 'error':
        raise StoreError(str(answer.get('message') or 'The ticket was not changed.'), HELP)
    return as_work(name, _one(name, str(one['id'])), notices)


def stored_work(name: str, node: Any = None, open: bool | None = None, *, ids: Any = None, kind: str | None = None,
                condition: str | None = None, done_since: str | None = None, done_before: str | None = None,
                limit: int = LIST, after: str | None = None, **_: Any) -> Page[WorkRecord]:
    """`Store.work` on the tickets overlay: by ids (open or completed, each by reference), else the open records,
    selected by element in the store, filtered as the old store filters them, and paged by after and limit."""
    if ids is not None:
        found = [one for ident in dict.fromkeys(str(one) for one in ids)
                 if (one := project_store.overlay_record(name, 'tickets', 'id', ident)) is not None]
    else:
        at = getattr(node, 'id', None) if node is not None and getattr(node, 'kind', 'element') == 'element' else None
        if node is not None and at is None:  # a join holds no ticket in the project store
            return Page((), None)
        found = list(project_store.overlay_records(name, 'tickets', at=cast('str | None', at)) or [])
    rows = [as_work(name, cast(dict[str, Any], one)) for one in found]
    rows = [row for row in rows if (open is None or (row.done is None) == open)
            and (kind is None or row.kind == ('' if kind == 'none' else kind))
            and (condition is None or row.condition == condition)
            and (done_since is None or row.done is None or row.done >= done_since)
            and (done_before is None or (row.done is not None and row.done < done_before))]
    start = int(after) if after and after.isdigit() else 0
    page = rows[start:start + limit] if limit else rows[start:]
    more = bool(limit) and start + limit < len(rows)
    return Page(tuple(page), str(start + limit) if more else None)


def stored_take(name: str, work_id: str, steps: Any = None, by: Any = None) -> StoredWork:
    """`take_work`: the ticket taken by `by`, at the revision read; one already taken keeps its taker, as the old
    store's peer participation does, and a done one is refused."""
    one = _one(name, work_id)
    if one.get('done'):
        raise StoreError(f"This work record was done at {one['done']}.", 'metaform map work open=true')
    if one.get('taken_by'):
        return as_work(name, one, (Notice('taken', 'Peer participation keeps the recorded first taker and progress.'),))
    fields: dict[str, object] = {'taken_by': str(by or 'agent'), 'held': None}
    if isinstance(steps, int) and not isinstance(steps, bool):
        fields['steps'] = steps
    return _changed(name, one, fields, exact=True)


def stored_move(name: str, work_id: str, column: Any, *_: Any, **__: Any) -> StoredWork:
    """`move_work`: backlog holds it, to do frees it, doing takes it and done finishes it; one moved back out of doing
    or done is open and untaken again."""
    one = _one(name, work_id)
    if column == 'done':
        return stored_finish(name, work_id)
    if column == 'doing':
        return stored_take(name, work_id, by=__.get('by'))
    if column not in ('todo', 'backlog'):
        raise StoreError(f'{column!r} is not a column: backlog, todo, doing or done.', HELP)
    return _changed(name, one, {'taken_by': None, 'done': None, 'outcome': None,
                                'held': True if column == 'backlog' else None})


def stored_finish(name: str, work_id: str, resolution: Any = None, why: Any = None, outcome: str = 'completed',
                  **_: Any) -> StoredWork:
    """`finish_work`: done, with how it ended and the resolution and why as the note's last paragraph; one already
    done keeps its first resolution."""
    one = _one(name, work_id)
    if one.get('done'):
        return as_work(name, one, (Notice('id', f"This work record was done at {one['done']}; its resolution was "
                                                'kept.'),))
    said = ' '.join(f'{label}: {value}' for label, value in (('Resolution', resolution), ('Why', why)) if value)
    kept = str(one.get('note') or '').strip()
    return _changed(name, one, {'done': datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'), 'outcome': outcome,
                                'note': '\n\n'.join(part for part in (kept, said) if part) or None})


def stored_edit(name: str, work_id: str, changes: Any, **_: Any) -> StoredWork:
    """`edit_work`: the fields the tickets overlay holds; any other is named in a notice and not kept."""
    given = cast(dict[str, Any], changes) if isinstance(changes, dict) else {}
    fields: dict[str, object] = {key: (value if value != "" else None) for key, value in given.items()
              if key in ('title', 'task', 'note', 'kind', 'held', 'taken_by', 'steps', 'steps_done')}
    left = sorted(set(given) - set(fields))
    notices = (Notice('work', f"{', '.join(left)} {'has' if len(left) == 1 else 'have'} no field in the project "
                              "store's tickets and was not kept."),) if left else ()
    one = _one(name, work_id)
    return _changed(name, one, fields, notices=notices) if fields else as_work(name, one, notices)


def stored_plan(name: str, work_id: str, steps: Any) -> StoredWork:
    """`plan_work`: the count of steps, never below those done."""
    one = _one(name, work_id)
    done = int(cast(Any, one.get('steps_done')) or 0)
    count = max(int(steps), done) if isinstance(steps, int) and not isinstance(steps, bool) else None
    return _changed(name, one, {'steps': count})


def stored_step(name: str, work_id: str, said: Any = None) -> StoredWork:
    """`step_work`: one more step done, the count raised when it goes beyond the plan, and what was said of it added to
    the note."""
    one = _one(name, work_id)
    done = int(cast(Any, one.get('steps_done')) or 0) + 1
    planned = one.get('steps')
    count = max(int(cast(Any, planned)), done) if isinstance(planned, (int, float)) else None
    kept = str(one.get('note') or '').strip()
    line = f'Step {done}: {said}' if said else ''
    return _changed(name, one, {'steps': count, 'steps_done': done,
                                'note': '\n\n'.join(part for part in (kept, line) if part) or None})


def stored_delivered(name: str, work_id: str, landed: bool) -> StoredWork:
    """`complete_delivery`: once dispatch recorded the ticket's delivery as landed, the ticket is closed, completed,
    as the old store closes it; until then it stands as it is. A ticket that is gone is refused as there."""
    one = _one(name, work_id)
    return stored_finish(name, work_id) if landed and not one.get('done') else as_work(name, one)


def stored_ticket(name: str, work_id: str, **_: Any) -> Ticket:
    """`ticket`: the one ticket; the project store's map is read by the project tool, so no old-store node read
    goes with it."""
    return Ticket(as_work(name, _one(name, work_id)), None, ())
