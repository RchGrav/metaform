"""Persistent, ticket-scoped rework accounting in dispatch's existing line storage, BASE-056."""
from __future__ import annotations

import json
import secrets
import time
from typing import Any, cast

from metaform.data import Store, StoreError, WorkRecord, on_base
from metaform.module import Context

from .signals import own_store, publish, rows

SOURCE = 'monitor:progress'  # separate from every ACP thread; no table upgrade beneath live runners


def _read(store: Store, work_id: str) -> dict[str, Any] | None:
    with own_store(store).tables(write=False) as tx:
        row = tx.get('lines', {'session_id': SOURCE, 'name': work_id})
    return cast(dict[str, Any], json.loads(row['text'])) if row else None


def _write(store: Store, work_id: str, value: dict[str, Any]) -> None:
    key = {'session_id': SOURCE, 'name': work_id}
    with own_store(store).tables() as tx:
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


def refresh(ctx: Context, store: Store, record: WorkRecord) -> None:
    """Reconcile progress and signal its streak after the accounting transaction commits."""
    with store.atomic():
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
            publish(ctx, 'rework-limit', work_id=record.id, key=epoch, active=False, epoch=epoch,
                    reason='ticket progress advanced, work finished, or the limit was disabled')
    if reached:
        ctx.publish('dispatch.rework-limit', {'work_id': record.id, 'attempts': value['attempts'],
                                            'limit': limit, 'epoch': value['epoch']})


def changed(payload: dict[str, Any], ctx: Context) -> None:
    """Ticket writes clear stale streaks through the existing event bus, without a timer or polling."""
    from . import ticket
    tables = payload.get('tables')
    if tables is not None and 'work' not in tables:
        return
    store = Store(ctx.require_store().project_id, base=payload.get('base_id'), module='dispatch')
    with store.tables(write=False) as tx:
        tracked = tx.rows('lines', {'session_id': SOURCE}, limit=0).results
    for row in tracked:
        try:
            record = ticket(store, row['work_id'])
        except StoreError:  # a ticket removed with its base has no progress left to reconcile
            continue
        with on_base(payload.get('base_id')):
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
