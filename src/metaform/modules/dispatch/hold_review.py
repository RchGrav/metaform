"""Review missing hold reasons once through the existing dispatch event inbox."""
from __future__ import annotations

import json
import secrets
import time
from collections import defaultdict
from typing import Any, cast

from metaform import home
from metaform.data import Column, Index, Store, Table, is_work
from metaform.module import Context

from .board import BOARD
from .signals import announce, own_store
from .signals import record as record_signal

HOLD_REVIEW_TABLES = (
    Table('hold_reviews', place='project', key=('base_id', 'work_id'),
          columns=(Column('base_id', required=True), Column('work_id', required=True),
                   Column('deadline', 'real', required=True), Column('reason', required=True),
                   Column('board', required=True), Column('signal_key')),
          indexes=(Index(('deadline',)), Index(('signal_key',)))),
    Table('hold_review_state', place='project', key=('name',),
          columns=(Column('name', required=True), Column('initialized', 'int', required=True), Column('signal_key'))),
)


def _held(store: Store, ids: list[str]) -> dict[str, dict[str, Any]]:
    """Read only named tickets and their explicit settings, including legacy reasonless holds."""
    from metaform.modules.map.storage import CONVERSATION_TASKS
    bound = store.bound_base()
    if bound is None:
        return {}
    records = store.work(ids=ids, limit=0).results
    settings = Store(store.project_id, base=bound.id, module='map')
    with settings.tables(write=False) as tx:
        kept = {str(row['work_id']): row for row in tx.rows_in('ticket_settings', 'work_id', ids)}
    return {record.id: {'id': record.id, 'map': kept.get(record.id, {})} for record in records
            if record.done is None and record.outcome not in ('cancelled', 'superseded', 'failed')
            and record.task not in CONVERSATION_TASKS and is_work(record.condition, record.task)
            and (record.held or kept.get(record.id, {}).get('hold'))}


def _track(store: Store, base_id: str, ids: list[str], held: dict[str, dict[str, Any]], at: float) -> None:
    changed_keys: set[str] = set()
    with own_store(store).tables() as tx:
        for work_id in ids:
            key = {'base_id': base_id, 'work_id': work_id}
            previous = tx.get('hold_reviews', key)
            record = held.get(work_id)
            if record is None:
                if previous is not None:
                    tx.concern(work_id=work_id, kind='hold-review')
                    tx.delete('hold_reviews', key)
                    if previous['signal_key']:
                        changed_keys.add(str(previous['signal_key']))
                continue
            settings: dict[str, Any] = record.get('map') or {}
            reason = str(settings.get('hold_reason') or '')
            board = str(settings.get('board') or '')
            if previous is not None and previous['reason'] == reason and previous['board'] == board \
                    and (reason or previous['signal_key'] is not None):
                continue
            tx.concern(work_id=work_id, kind='hold-review')
            if previous is None:
                tx.insert('hold_reviews', {**key, 'deadline': at, 'reason': reason,
                                          'board': board, 'signal_key': ''})
            else:
                tx.update('hold_reviews', key, {'reason': reason, 'board': board,
                                                'signal_key': '' if previous['reason'] != reason or previous['signal_key'] is None else previous['signal_key']})
                if previous['signal_key']:
                    changed_keys.add(str(previous['signal_key']))
    for signal_key in changed_keys:
        _refresh_signal(store, signal_key)


def changed(payload: dict[str, Any], ctx: Context) -> None:
    """Reject unrelated events before reads, then update evidence only for named work changes."""
    kinds, tables, ids = payload.get('kinds'), payload.get('tables'), payload.get('work_ids')
    if not isinstance(kinds, list) or 'ticket' not in kinds or not isinstance(tables, list) \
            or not {'work', 'map.ticket_settings'}.intersection(cast(list[str], tables)) or not isinstance(ids, list) or not ids:
        return
    if payload.get('project') != ctx.project or not payload.get('base_id'):
        return
    store = ctx.require_store()
    base_id = str(payload['base_id'])
    named = list(dict.fromkeys(str(work_id) for work_id in cast(list[Any], ids)))
    _track(store, base_id, named, _held(Store(store.project_id, base=base_id), named), time.time())


def ensure(ctx: Context) -> None:
    """Seed hold evidence once per project, preserving delivered review identities."""
    store = ctx.require_store()
    with own_store(store).tables(write=False) as tx:
        if tx.get('hold_review_state', {'name': 'event-seeded'}) is not None:
            return
    at = time.time()
    for base in store.bases(limit=0).results:
        if not home.store_file(store.project_id, base.name).is_file():
            continue
        held = {record['id']: record for record in Store(store.project_id, base=base.id).held_work()}
        _track(store, base.id, list(held), held, at)
    with own_store(store).tables() as tx:
        tx.concern(kind='hold-review')
        if tx.get('hold_review_state', {'name': 'event-seeded'}) is None:
            tx.insert('hold_review_state', {'name': 'event-seeded', 'initialized': 1})
        if tx.get('hold_review_state', {'name': 'seeded'}) is None:
            tx.insert('hold_review_state', {'name': 'seeded', 'initialized': 1})
        else:
            tx.update('hold_review_state', {'name': 'seeded'}, {'initialized': 1})
        old_keys = {str(row['signal_key']) for row in tx.rows('hold_reviews', limit=0).results
                    if row['signal_key']}
    for signal_key in old_keys:
        _refresh_signal(store, signal_key)


def reconcile(ctx: Context) -> None:
    """Review legacy missing reasons once. Justified holds need no recurring model turn.

    Existing dispatch timers and user messages remain available for a meaningful
    deadline or a new release condition. This path never infers readiness.
    """
    if not ctx.setting('dispatch_autostart'):
        return
    ensure(ctx)
    _review(ctx)


def _review(ctx: Context) -> None:
    store = ctx.require_store()
    with own_store(store).tables(write=False) as tx:
        pending = [row for row in tx.rows('hold_reviews', {'signal_key': ''}, limit=0).results
                   if not row['reason']]
        state = tx.get('hold_review_state', {'name': 'seeded'})
        previous_key = str(state['signal_key']) if state and state.get('signal_key') else ''
        previous = tx.get('signals', {'session_id': 'work:', 'name': f'signal:{BOARD}:{previous_key}'}) \
            if previous_key else None
    if pending:
        _, signal_key = _claim(store, pending)
    elif previous_key and previous is None:
        # A crash after claiming but before publishing retries the retained batch.
        signal_key = previous_key
    else:
        return
    if not signal_key:
        return
    members = _members(store, signal_key)
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in members:
        grouped[str(row['base_id'])].append(str(row['work_id']))
    for base_id, ids in grouped.items():
        _track(store, base_id, ids, _held(Store(store.project_id, base=base_id), ids), time.time())
    members = _members(store, signal_key)
    if not members:
        return
    value = record_signal(store, BOARD, key=signal_key, once=True, signal_key=signal_key, actionable=True,
                          tickets=_tickets(members), said=_explanation(members))
    refreshed = _refresh_signal(store, signal_key)
    announced = refreshed or value
    if announced is not None:
        announce(ctx, announced)


def _members(store: Store, signal_key: str) -> list[dict[str, Any]]:
    with own_store(store).tables(write=False) as tx:
        return [row for row in tx.rows_in('hold_reviews', 'signal_key', [signal_key]) if not row['reason']]


def _tickets(members: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{'base_id': row['base_id'], 'work_id': row['work_id'], 'board': row['board'],
             'hold_reason': row['reason']} for row in members]


def _explanation(members: list[dict[str, Any]]) -> str:
    explanation = '\n'.join(f"{row['work_id']} ({row['base_id']}, {row['board'] or 'first board'}): "
                            f"{row['reason'] or 'No explicit hold reason is recorded.'}" for row in members)
    return ('Review unresolved work holds. Recheck each reason and prerequisites. '
            'Resolve what you can. Keep deliberate holds explained on their tickets. '
            'Ask the person only for decisions that require them.\n' + explanation)


def _refresh_signal(store: Store, signal_key: str) -> dict[str, Any] | None:
    """Merge pending review evidence or retire a batch whose last hold was released."""
    with own_store(store).tables() as tx:
        key = {'session_id': 'work:', 'name': f'signal:{BOARD}:{signal_key}'}
        previous = tx.get('signals', key)
        if previous is None:
            return None
        value: dict[str, Any] = json.loads(str(previous['text']))
        if not value.get('active'):
            return None
        members = [row for row in tx.rows_in('hold_reviews', 'signal_key', [signal_key]) if not row['reason']]
        tickets = _tickets(members)
        if value.get('tickets') == tickets and value.get('active') == bool(members):
            return None
        value.update(tickets=tickets, said=_explanation(members), active=bool(members))
        tx.concern(kind='signal')
        tx.update('signals', key, {'text': json.dumps(value, ensure_ascii=False)})
        return value


def _claim(store: Store, due: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    """Give concurrent passes one persisted delivery key without holding map-store locks."""
    with own_store(store).tables() as tx:
        current = [tx.get('hold_reviews', {'base_id': row['base_id'], 'work_id': row['work_id']}) for row in due]
        current = [row for row in current if row is not None and not row['reason'] and not row['signal_key']]
        if not current:
            return [], ''
        state = tx.get('hold_review_state', {'name': 'seeded'})
        signal_key = str(state['signal_key']) if state and state.get('signal_key') else ''
        signal = tx.get('signals', {'session_id': 'work:', 'name': f'signal:{BOARD}:{signal_key}'}) \
            if signal_key else None
        if not signal_key or signal is not None and not json.loads(str(signal['text'])).get('active'):
            signal_key = f'hold-review:{secrets.token_hex(8)}'
            tx.concern(kind='hold-review')
            if state is None:
                tx.insert('hold_review_state', {'name': 'seeded', 'initialized': 0, 'signal_key': signal_key})
            else:
                tx.update('hold_review_state', {'name': 'seeded'}, {'signal_key': signal_key})
        for row in current:
            tx.concern(work_id=str(row['work_id']), kind='hold-review')
            tx.update('hold_reviews', {'base_id': row['base_id'], 'work_id': row['work_id']},
                      {'signal_key': signal_key})
    return current, signal_key
