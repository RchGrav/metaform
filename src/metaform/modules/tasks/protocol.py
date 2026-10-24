"""Worker worksheets, peer records and event-driven rendezvous over ordinary project tickets."""
from __future__ import annotations

import os
import uuid
from typing import Any, cast

from metaform.data import Node
from metaform.module import Context, Stop

from .board import Board


def board(ctx: Context) -> Board:
    return Board(ctx.require_store().project_id)


def actor(ctx: Context, supplied: Any = None) -> str:
    return str(ctx.identity.get('METAFORM_TASK') or os.environ.get('METAFORM_TASK') or supplied or '')


def changed(ctx: Context, agents: list[str] | None = None, ticket: str | None = None, *, wake: bool = False) -> None:
    ids = agents or []
    ctx.publish('map.changed', {'project': ctx.project, 'tables': ['tasks.board'],
                'kinds': ['tasks.board'], 'work_ids': [ticket] if ticket else [], 'agent_ids': ids, 'wake': wake})


def view(ctx: Context) -> dict[str, Any]:
    return {'agents': board(ctx).view(actor(ctx) or None)}


def status(ctx: Context) -> dict[str, Any]:
    ident = str(ctx.nouns.get('agent_id') or actor(ctx))
    if not ident:
        raise Stop('Name the worker whose status is being updated.', 'metaform tasks board')
    fields = {key: ctx.nouns[key] for key in ('state', 'nodes', 'current', 'next', 'waiting_for') if key in ctx.nouns}
    board(ctx).patch(ident, fields)
    changed(ctx, [ident])
    return {'agent_id': ident, 'updated': list(fields)}


def ticket(ctx: Context) -> dict[str, Any]:
    store = ctx.require_store()
    name = str(ctx.nouns['node'])
    target = Node('join', name[5:]) if name.startswith('join:') else Node('element', name)
    result = store.add_work(target, None, task=str(ctx.nouns['text']), title=str(ctx.nouns['summary']))
    return {'ticket': result.id, 'summary': ctx.nouns['summary'], 'node': name}


def worksheet(ctx: Context) -> dict[str, Any]:
    ident = str(ctx.nouns['ticket'])
    record = ctx.require_store().ticket(ident).work
    data = board(ctx)
    if 'items' not in ctx.nouns:
        return data.round(ident) or {'ticket': ident, 'items': []}
    holder = str(ctx.nouns.get('holder') or actor(ctx))
    if not holder:
        raise Stop('Give the worksheet holder identifier.', 'metaform tasks board')
    items = cast(list[str | dict[str, Any]], ctx.nouns['items'])
    nodes = cast(list[str], ctx.nouns.get('nodes') or [])
    titles: dict[str, Any] = ctx.require_store().numbers_of('work', [ident])
    title = titles.get(ident, ('', None, None))[1]
    result = data.set_round(ident, str(title or record.task or ''), holder, items, nodes,
                            ctx.nouns.get('partner'))
    if not record.taken and not record.done:
        ctx.require_store().take_work(ident, by=actor(ctx) or holder)
    _sync_progress(ctx, result)
    changed(ctx, [holder], ident)
    return result


def pair(ctx: Context) -> dict[str, Any]:
    ident, partner = str(ctx.nouns['ticket']), str(ctx.nouns['partner'])
    result = board(ctx).pair(ident, partner)
    changed(ctx, [str(result['holder']), partner], ident)
    return result


def check(ctx: Context) -> dict[str, Any]:
    ident = str(ctx.nouns['ticket'])
    result = board(ctx).check(ident, str(ctx.nouns['item']), bool(ctx.nouns.get('done', True)))
    _sync_progress(ctx, result)
    completed = _close(ctx, ident)
    changed(ctx, [str(result['holder']), str(result.get('partner') or '')], ident)
    return {**result, 'completed': completed}


def rate(ctx: Context) -> dict[str, Any]:
    ident = str(ctx.nouns['ticket'])
    data = board(ctx)
    current = data.round(ident)
    if current is None:
        raise Stop(f'No worksheet for ticket {ident}.', 'metaform tasks worksheet')
    reviewer = actor(ctx, ctx.nouns.get('reviewer'))
    target = str(ctx.nouns.get('target') or (current.get('partner') if reviewer == current['holder']
                                           else current['holder']) or '')
    if not reviewer or not target:
        raise Stop('Identify the reviewer and the contribution being rated.', 'metaform tasks board')
    data.rate(ident, reviewer, target, cast(dict[str, float], ctx.nouns['scores']))
    completed = _close(ctx, ident)
    changed(ctx, [reviewer, target], ident)
    return {'ticket': ident, 'reviewer': reviewer, 'target': target, 'recorded': True, 'completed': completed}


def _sync_progress(ctx: Context, round_: dict[str, Any]) -> None:
    items = cast(list[dict[str, Any]], round_['items'])
    total, checked = len(items), sum(bool(item.get('done')) for item in items)
    store = ctx.require_store()
    with store.atomic():
        store.worksheet_progress(str(round_['ticket']), total, checked)
        if total and checked == total:
            _append(ctx, round_)


def _append(ctx: Context, round_: dict[str, Any]) -> None:
    ident = str(round_['ticket'])
    marker = f'Completed worksheet ({ident})'
    store = ctx.require_store()
    record = store.ticket(ident).work
    note = str(record.note or '')
    text = marker + '\n' + '\n'.join('[x] ' + str(item['text']) for item in round_['items'])
    if marker in note:
        # Replace only this worksheet, retaining notes written by other participants.
        before, _, tail = note.partition(marker)
        _, separator, after = tail.partition('\n\n')
        note = before + text + (separator + after if separator else '')
    else:
        note = '\n\n'.join(part for part in (note, text) if part)
    store.edit_work(ident, {'note': note})


def _close(ctx: Context, ident: str) -> bool:
    data = board(ctx)
    round_ = data.round(ident)
    if round_ is None:
        return False
    if round_['completed']:
        return True
    items = cast(list[dict[str, Any]], round_['items'])
    holder, partner = str(round_['holder']), str(round_.get('partner') or '')
    ratings = {(r['reviewer'], r['target']) for r in data.ratings(ident)}
    if not items or not all(item.get('done') for item in items) or not partner or not {
            (holder, partner), (partner, holder)} <= ratings:
        return False
    store = ctx.require_store()
    with store.atomic():
        _append(ctx, round_)
        record = store.ticket(ident).work
        if not record.done:
            store.finish_work(ident, 'Completed the registered worksheet.', 'Both partners submitted their peer ratings.')
    data.complete_round(ident)
    wake_ids: list[str] = []
    for available in (holder, partner):
        for waiter in data.waiters(available):
            waiting = str(waiter['agent_id'])
            data.patch(waiting, {'waiting_for': None})
            data.enqueue(waiting, f'partner:{ident}:{waiting}', f'Your selected partner finished ticket {ident}.')
            wake_ids.append(waiting)
    if any(record.task for record in store.work(open=True, limit=0).results):
        for agent in (holder, partner):
            data.enqueue(agent, f'complete:{ident}:{agent}',
                         f'Ticket {ident} is complete. Follow the agreed turn-taking for new work.')
            wake_ids.append(agent)
    if wake_ids:
        changed(ctx, wake_ids, ident, wake=True)
    drain(ctx)
    return True


def flush(ctx: Context, assignment: dict[str, Any]) -> None:
    from .runtime import transport
    data = board(ctx)
    ident = str(assignment['task_id'])
    for message in data.pending(ident):
        transport(ctx).wake(ctx, assignment, message['key'], message['text'])
        data.delivered(message['key'])


def reconcile(ctx: Context, assignment: dict[str, Any], observed: dict[str, Any]) -> None:
    if assignment['name'] != 'worker':
        return
    data = board(ctx)
    ident = str(assignment['task_id'])
    if observed['state'] in ('completed', 'failed', 'cancelled'):
        data.remove(ident)
        changed(ctx, [ident])
        return
    worker = data.worker(ident)
    if worker is None:
        worker = data.register(ident, str(observed.get('name') or assignment['payload'].get('agent_name') or ident),
                               str(assignment['work_id']), str(observed.get('session_id') or ''))
    fields = {'state': 'idle' if observed.get('idle') else 'working'}
    for key in ('name', 'context', 'session_id'):
        if observed.get(key) is not None:
            fields[key] = observed[key]
    if any(worker.get(key) != value for key, value in fields.items()):
        data.patch(ident, fields)
        changed(ctx, [ident])
    if not drain(ctx):
        flush(ctx, assignment)


def drain(ctx: Context) -> bool:
    """End a finished run, without polling or deciding how workers should select tickets."""
    from .runtime import SERVICE, transport
    data = board(ctx)
    workers = data.workers()
    if not workers or not data.rounds() or any(w['state'] == 'draining' for w in workers):
        return False
    if any(w['state'] not in ('idle', 'waiting') or w.get('current') or w.get('next') for w in workers):
        return False
    if any(record.task for record in ctx.require_store().work(open=True, limit=0).results):
        return False
    # Persist the run transition before delivering its notifications. No role or creator owns this transition.
    for worker in workers:
        data.patch(str(worker['agent_id']), {'state': 'draining'})
    for worker in workers:
        assignment = SERVICE.assignment(ctx, str(worker['agent_id']))
        if assignment is not None:
            transport(ctx).finish(ctx, assignment, 'All project tickets and worker contributions are complete.')
    return True


def event(ctx: Context, payload: dict[str, Any]) -> None:
    from .runtime import SERVICE
    if payload.get('project') != ctx.project or not payload.get('wake') or 'tasks.board' not in payload.get('tables', []):
        return
    for ident in payload.get('agent_ids', []):
        if ident and (assignment := SERVICE.assignment(ctx, str(ident))) is not None:
            try:
                flush(ctx, assignment)
            except (OSError, Stop):
                pass  # the durable outbox remains available after reconnect/startup


def message(ctx: Context) -> dict[str, Any]:
    from .runtime import SERVICE
    ident = str(ctx.nouns['agent_id'])
    if SERVICE.assignment(ctx, ident) is None:
        raise Stop(f'No assigned agent {ident}.', 'metaform tasks board')
    sender = actor(ctx) or ctx.surface
    key = uuid.uuid4().hex
    board(ctx).enqueue(ident, key, f'From {sender}: ' + str(ctx.nouns['text']))
    changed(ctx, [ident], wake=True)
    return {'message': key, 'to': ident, 'from': sender, 'queued': True}
