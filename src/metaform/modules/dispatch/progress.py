"""Persistent, ticket-scoped rework accounting in dispatch's existing line storage, BASE-056."""
from __future__ import annotations

import json
import secrets
import time
from dataclasses import replace
from typing import Any, cast

from metaform.data import Store, StoreError, WorkRecord, on_base
from metaform.module import Context

from .signals import announce, own_store, rows
from .signals import record as record_signal

SOURCE = 'monitor:progress'  # separate from every ACP thread; no table upgrade beneath live runners


def _read(store: Store, work_id: str) -> dict[str, Any] | None:
    with own_store(store).tables(write=False) as tx:
        row = tx.get('lines', {'session_id': SOURCE, 'name': work_id})
    return cast(dict[str, Any], json.loads(row['text'])) if row else None


def _write(store: Store, work_id: str, value: dict[str, Any]) -> None:
    key = {'session_id': SOURCE, 'name': work_id}
    with own_store(store).tables() as tx:
        tx.concern(work_id=work_id, kind='progress')  # a ticket's progress: no page or runner reads for it
        text = json.dumps(value)
        if tx.get('lines', key) is None:
            tx.insert('lines', {**key, 'work_id': work_id, 'kind': 'progress', 'text': text, 'seq': time.time_ns()})
        else:
            tx.update('lines', key, {'text': text})


def _advanced(value: dict[str, Any], record: WorkRecord) -> bool:
    return bool(record.done or record.steps_done > value['steps'])


def _reset(value: dict[str, Any], record: WorkRecord) -> None:
    if _advanced(value, record):
        value.update(steps=record.steps_done, attempts=0, epoch=secrets.token_hex(8))


def begin(store: Store, record: WorkRecord, session_id: str, runner: str) -> None:
    """Capture the baseline inside the successful worker acquisition transaction, including resumes."""
    with store.atomic():
        value = _read(store, record.id) or {'steps': record.steps_done, 'attempts': 0, 'epoch': secrets.token_hex(8)}
        if value.get('runner') == runner:  # a duplicate acquisition never erases execution or completion
            return
        _reset(value, record)
        value.update(runner=runner, session_id=session_id, baseline=record.steps_done, executed=False, ended=False)
        _write(store, record.id, value)


def executed(store: Store, work_id: str, runner: str) -> None:
    """Only a worker actually sending a prompt has attempted the work; opening an idle resume has not."""
    with store.atomic():
        value = _read(store, work_id)
        if value is not None and value['runner'] == runner and not value['ended'] and not value['executed']:
            value['executed'] = True
            _write(store, work_id, value)


def finish(store: Store, work_id: str, runner: str, how: str) -> None:
    """Account once for this runner, in the transaction that ends or recovers it. Late cleanup is ignored."""
    from . import PERSON_ENDS, ticket
    with store.atomic():
        value = _read(store, work_id)
        if value is None or value['runner'] != runner or value['ended']:
            return
        record = ticket(store, work_id)
        _reset(value, record)
        if value['executed'] and not record.done and record.steps_done <= value['baseline'] and how not in PERSON_ENDS:
            value['attempts'] += 1
        value['ended'] = True
        _write(store, work_id, value)


def blocked(ctx: Context, store: Store, record: WorkRecord) -> bool:
    """An observational gate for automatic execution only. A newer completed step immediately frees the ticket."""
    limit = int(ctx.setting('dispatch_rework_limit'))
    if not limit or record.done:
        return False
    value = _read(store, record.id)
    return bool(value and not _advanced(value, record) and value['attempts'] >= limit)


def due(ctx: Context, store: Store, record: WorkRecord) -> bool:
    """Whether `refresh` has anything to write for this ticket, from reads alone: its progress to reset, a streak's
    signal to clear, or one to raise. UX review round 1 (runaway F3): every refresh took the write lock first."""
    from . import ticket
    record = ticket(store, record.id)
    value = _read(store, record.id)
    if value is None:
        return False
    if _advanced(value, record) and (value['attempts'] or record.steps_done > value['steps']):
        return True
    limit = int(ctx.setting('dispatch_rework_limit'))
    reached = bool(limit and not record.done and value['attempts'] >= limit)
    raised = [signal for signal in rows(store, record.id) if signal['signal'] == 'rework-limit' and signal.get('epoch')]
    if any(not reached or signal['epoch'] != value['epoch'] for signal in raised):
        return True
    return reached and not any(signal['epoch'] == value['epoch'] for signal in raised)


def refresh(ctx: Context, store: Store, record: WorkRecord) -> None:
    """Reconcile progress and signal its streak after the accounting transaction commits; read first, so a ticket with
    nothing to reconcile takes no write lock."""
    from . import ticket
    if not due(ctx, store, record):
        return
    notices: list[dict[str, Any]] = []
    with store.atomic():
        record = ticket(store, record.id)  # the caller's snapshot may predate a completed step or another runner
        value = _read(store, record.id)
        if value is None:
            return
        if _advanced(value, record) and (value['attempts'] or record.steps_done > value['steps']):
            _reset(value, record)
            _write(store, record.id, value)
        limit = int(ctx.setting('dispatch_rework_limit'))
        reached = bool(limit and not record.done and value['attempts'] >= limit)
        for signal in rows(store, record.id):
            epoch = signal.get('epoch')
            if signal['signal'] == 'rework-limit' and epoch and (not reached or epoch != value['epoch']):
                cleared = record_signal(store, 'rework-limit', work_id=record.id, key=epoch, active=False, epoch=epoch,
                                        reason='ticket progress advanced, work finished, or the limit was disabled')
                if cleared is not None:
                    notices.append(cleared)
        if reached:
            raised = record_signal(store, 'rework-limit', work_id=record.id, key=value['epoch'],
                                   attempts=value['attempts'], limit=limit, epoch=value['epoch'])
            if raised is not None:
                notices.append(raised)
    bound = store.bound_base()
    with on_base(bound.id if bound else None):
        scoped = replace(ctx, store=own_store(store))
        for notice in notices:
            if notice['active']:
                scoped.publish('dispatch.rework-limit', notice)
            announce(scoped, notice)


def changed(payload: dict[str, Any], ctx: Context) -> None:
    """Ticket writes clear stale streaks through the existing event bus, without a timer or polling. A change that names
    its tickets, `work_ids`, reconciles those alone; a change to the settings, every tracked one."""
    from . import ticket
    tables = payload.get('tables')
    settings_changed = tables is not None and 'dispatch.settings' in tables
    if tables is not None and 'work' not in tables and not settings_changed:
        return
    kinds: Any = payload.get('kinds')
    if not settings_changed and isinstance(kinds, list) and not {'ticket', 'step'} & set(cast(list[Any], kinds)):
        return  # a ticket's words alone, its note, title or links, move no progress: UX review round 1, runaway F3
    named: Any = None if settings_changed else payload.get('work_ids')
    if isinstance(named, list) and not named:
        return
    project = ctx.require_store().project_id
    bases = ([base.id for base in ctx.require_store().bases(limit=0).results]
             if settings_changed else [payload.get('base_id')])
    for base in bases:
        store = Store(project, base=base, module='dispatch')
        with store.tables(write=False) as tx:
            tracked = [tx.get('lines', {'session_id': SOURCE, 'name': str(one)})
                       for one in cast(list[Any], named)] if isinstance(named, list) else \
                tx.rows('lines', {'session_id': SOURCE}, limit=0).results
        for row in (one for one in tracked if one is not None):
            try:
                record = ticket(store, row['work_id'])
            except StoreError:  # a ticket removed with its base has no progress left to reconcile
                continue
            refresh(ctx, store, record)


def requeued(payload: dict[str, Any], ctx: Context) -> None:
    """A public board move can end an attempt before its runner releases it; account for that boundary once."""
    from . import ticket
    store = ctx.require_store()
    with store.atomic():
        record = ticket(store, payload['work_id'])
        if payload['previous'] != 'doing' or record.taken:
            return
        value = _read(store, record.id)
        if value is not None:
            finish(store, record.id, value['runner'], 'the worker ticket was requeued')
    refresh(ctx, store, record)
