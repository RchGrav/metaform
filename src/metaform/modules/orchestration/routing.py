"""Durable specialist selection, drained by the existing event-driven dispatch starter."""
from __future__ import annotations

import json
from dataclasses import replace
from importlib import resources
from typing import Any

from metaform import home, jev, prompt_files
from metaform.data import Column, Index, StoreError, Table, functional_context, is_work
from metaform.module import Context

TABLE = Table('routing', key=('work_id',), columns=(
    Column('work_id', required=True), Column('state', required=True), Column('fingerprint'),
    Column('role'), Column('reason'), Column('updated', required=True)), indexes=(Index(('state',)),))


def queue(ctx: Context, work_ids: list[str], *, invalidate: bool = False) -> None:
    from .state import own, row_for
    store = own(ctx)
    if not work_ids:
        return
    eligible = {record.id for record in store.work(ids=work_ids, limit=0).results
                if is_work(record.condition, record.task) and not record.done and not record.held}
    with store.tables() as tx:
        for work_id in work_ids:
            if work_id not in eligible or work_id.startswith('conversation-') or row_for(tx, work_id=work_id):
                continue
            prior = tx.get('routing', {'work_id': work_id})
            if prior is None:
                tx.insert('routing', {'work_id': work_id, 'state': 'pending', 'updated': home.now()})
                tx.concern(work_id=work_id, kind='orchestration.routing')
            elif invalidate or prior['state'] == 'held':
                tx.update('routing', {'work_id': work_id}, {'state': 'pending', 'role': None,
                                                          'fingerprint': None, 'updated': home.now()})
                tx.concern(work_id=work_id, kind='orchestration.routing')


def selected(ctx: Context, work_id: str) -> str | None:
    from .state import own, row_for, service
    with own(ctx).tables(write=False) as tx:
        assigned = row_for(tx, work_id=work_id)
        row = tx.get('routing', {'work_id': work_id})
    if assigned:
        # Managed internal responsibilities (Role Creator, assessment) keep their recorded assignment.
        if assigned.get('parent_assignment_id') or assigned.get('reviewed_assignment_id'):
            return str(assigned['authored_role_uri'])
        role = str(assigned['authored_role_uri'])
    else:
        role = str(row['role']) if row and row['state'] == 'selected' else ''
    return role if role in {one['uri'] for one in service(ctx, 'agent.role').specialists(ctx)} else None


def route(ctx: Context, work_id: str, *, refresh: bool = False) -> dict[str, Any]:
    from .state import fingerprint, own
    base = own(ctx).bound_base() or own(ctx).active_base()
    ident = fingerprint(f'{ctx.project}:{base.id if base else ""}:{work_id}')
    lock = home.home() / 'run' / 'specialist-routing' / f'{ident}.lock'
    home.mkdir_private(lock.parent)
    with home.file_lock(lock):
        return _route(ctx, work_id, refresh=refresh)


def _route(ctx: Context, work_id: str, *, refresh: bool) -> dict[str, Any]:
    from .state import SERVICE, fingerprint, own, row_for, service
    ctx = replace(ctx, module='orchestration')
    store = own(ctx)
    role = selected(ctx, work_id)
    with store.tables(write=False) as tx:
        prior = tx.get('routing', {'work_id': work_id})
        assigned = row_for(tx, work_id=work_id)
    if role or assigned:
        status = {'state': 'selected', 'role': role} if role else SERVICE.routing_status(ctx, work_id)
        assert status is not None
        if prior and prior['state'] in ('pending', 'triage'):
            with store.tables() as tx:
                tx.update('routing', {'work_id': work_id}, {**status, 'reason': None, 'updated': home.now()})
                tx.concern(work_id=work_id, kind='orchestration.routing')
        return {'work_id': work_id, **status}
    try:
        record = store.ticket(work_id).work
    except StoreError:
        record = None
    if record is None or record.done or not is_work(record.condition, record.task):
        with store.tables() as tx:
            if tx.get('routing', {'work_id': work_id}):
                tx.update('routing', {'work_id': work_id}, {'state': 'closed', 'updated': home.now()})
                tx.concern(work_id=work_id, kind='orchestration.routing')
        return {'work_id': work_id, 'state': 'closed', 'role': None}
    if record.held or record.taken:
        row = {'work_id': work_id, 'state': 'held' if record.held else 'assigned', 'role': None,
               'reason': 'The ticket is held in Backlog.' if record.held else 'The ticket already has an owner.',
               'updated': home.now()}
        with store.tables() as tx:
            if tx.get('routing', {'work_id': work_id}):
                tx.update('routing', {'work_id': work_id}, row)
            else:
                tx.insert('routing', row)
        return row
    if prior and prior['state'] == 'creating':
        return prior  # Publication, not another classification, continues this ticket.
    specialists = service(ctx, 'agent.role').specialists(ctx)
    graph = functional_context(store, record)
    # The graph's markdown repeats its structured fields; neither role bodies nor unrelated memories are sent.
    numbered = store.numbers_of('work', [work_id]).get(work_id)
    state = {'title': numbered[1] if numbered else None, 'task': record.task, 'note': record.note,
             'function': {key: value for key, value in graph.items() if key != 'markdown'}}
    digest = fingerprint(json.dumps([state, specialists], sort_keys=True))
    cached = bool(prior and prior['fingerprint'] == digest and not refresh)
    if cached and prior and prior['state'] not in ('pending', 'triage'):
        return prior
    # Upgrade old advisory-only decisions without paying to classify the same ticket again.
    legacy = bool(cached and prior and prior['state'] == 'triage')
    cfg = None if legacy else jev.config(ctx.folder, 'orchestration.specialist')
    role = None
    reason = ('Facilitator is selecting expertise.' if legacy else
              'JEV is unavailable; Facilitator is selecting expertise.')
    if cfg:
        with jev.within(jev.DEADLINE):
            balance = jev.openrouter_credits() if cfg.endpoint.name == 'openrouter' else {'status': 'available'}
            if balance['status'] != 'available':
                reason = 'OpenRouter credit is unavailable; Facilitator is selecting expertise.'
            elif not specialists:
                reason = 'No specialist is registered; Facilitator is creating reusable expertise.'
            else:
                options = {one['uri']: one['purpose'] for one in specialists}
                options['none'] = 'No listed specialist has the expertise needed for this ticket.'
                question = prompt_files.served(resources.files('metaform.modules.orchestration'), 'choose_specialist')
                decision = jev.pick_one(ctx.folder, question, options, state,
                                       title='Select specialist expertise', why='Match expertise to the functional work.',
                                       decision='orchestration.specialist')
                if decision and decision.sure and decision.answer in options and decision.answer != 'none':
                    role = str(decision.answer)
                    reason = 'JEV selected matching reusable expertise.'
                elif decision and decision.sure and decision.answer == 'none':
                    reason = 'JEV found no matching specialist; Facilitator is selecting or creating expertise.'
                else:
                    reason = 'JEV could not select expertise confidently; Facilitator is selecting expertise.'
    if not role:
        # The creator names the expertise. The ticket retains its own assignment and continuation.
        SERVICE.claim(replace(ctx, nouns={'work': work_id, 'create': True}))
    row = {'work_id': work_id, 'state': 'selected' if role else 'creating', 'fingerprint': digest,
           'role': role, 'reason': reason, 'updated': home.now()}
    with store.tables() as tx:
        current = tx.get('routing', {'work_id': work_id})
        if current:
            tx.update('routing', {'work_id': work_id}, row)
        else:
            tx.insert('routing', row)
        tx.concern(work_id=work_id, kind='orchestration.routing')
    return row


def pending(ctx: Context, limit: int = 1) -> list[dict[str, Any]]:
    from .state import own
    with own(ctx).tables(write=False) as tx:
        count = max(1, limit)
        rows = list(tx.rows('routing', {'state': 'triage'}, limit=count).results)
        if len(rows) < count:
            rows.extend(tx.rows('routing', {'state': 'pending'}, limit=count - len(rows)).results)
    return [route(ctx, str(row['work_id'])) for row in rows]


def waiting(ctx: Context) -> bool:
    from .state import own
    with own(ctx).tables(write=False) as tx:
        return any(tx.rows('routing', {'state': state}, limit=1).results for state in ('triage', 'pending'))


def roles_changed(payload: dict[str, Any], ctx: Context) -> None:
    if payload.get('project') != ctx.project:
        return
    from .state import own
    store = own(ctx)
    if store.active_base() is None:
        return
    with store.tables(write=False) as tx:
        rows = tx.rows('routing', {'state': 'triage'}, limit=0).results
    queue(ctx, [str(row['work_id']) for row in rows], invalidate=True)
