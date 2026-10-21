"""Persist explicit-hold review deadlines for the existing automatic-start timer."""
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

REVIEW_SECONDS = 15 * 60
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
            if previous is not None and previous['reason'] == reason and previous['board'] == board:
                continue
            tx.concern(work_id=work_id, kind='hold-review')
            if previous is None:
                tx.insert('hold_reviews', {**key, 'deadline': at + REVIEW_SECONDS, 'reason': reason,
                                          'board': board, 'signal_key': None})
            else:
                tx.update('hold_reviews', key, {'reason': reason, 'board': board})
                if previous['signal_key']:
                    changed_keys.add(str(previous['signal_key']))
    for signal_key in changed_keys:
        _refresh_signal(store, signal_key)


def changed(payload: dict[str, Any], ctx: Context) -> None:
    """Reject unrelated events before reads, then update deadlines only for named work changes."""
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
    """Seed existing holds once per project, preserving previously recorded deadlines across restarts."""
    store = ctx.require_store()
    with own_store(store).tables(write=False) as tx:
        if tx.get('hold_review_state', {'name': 'seeded'}) is not None:
            return
    at = time.time()
    for base in store.bases(limit=0).results:
        if not home.store_file(store.project_id, base.name).is_file():
            continue
        held = {record['id']: record for record in Store(store.project_id, base=base.id).held_work()}
        _track(store, base.id, list(held), held, at)
    with own_store(store).tables() as tx:
        if tx.get('hold_review_state', {'name': 'seeded'}) is None:
            tx.concern(kind='hold-review')
            tx.insert('hold_review_state', {'name': 'seeded', 'initialized': 1})


def _due(store: Store, at: float) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    with own_store(store).tables(write=False) as tx:
        page = tx.rows('hold_reviews', by=('deadline',), limit=1)
        while page.results and float(page.results[0]['deadline']) <= at:
            found.extend(page.results)
            if page.next is None:
                break
            page = tx.rows('hold_reviews', by=('deadline',), limit=1, after=page.next)
    return found


def _next(store: Store) -> float | None:
    with own_store(store).tables(write=False) as tx:
        earliest = tx.rows('hold_reviews', by=('deadline',), limit=1).results
    return float(earliest[0]['deadline']) if earliest else None


def reconcile(ctx: Context) -> float | None:
    """Queue one actionable review batch when due, returning the existing timer's next deadline."""
    if not ctx.setting('dispatch_autostart'):
        return None
    ensure(ctx)
    store, at = ctx.require_store(), time.time()
    due = _due(store, at)
    if not due:
        return _next(store)
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in due:
        grouped[str(row['base_id'])].append(str(row['work_id']))
    # Recheck only due tickets. Missed changes or a removed base cannot create a stale reminder.
    for base_id, ids in grouped.items():
        _track(store, base_id, ids, _held(Store(store.project_id, base=base_id), ids), at)
    due = _due(store, at)
    if not due:
        return _next(store)
    current, signal_key = _claim(store, due, at)
    if not current:
        return _next(store)
    # Persist the batch before advancing deadlines. A crash retries the same signal key.
    members = _members(store, signal_key)
    if not members:
        return _next(store)
    value = record_signal(store, BOARD, key=signal_key, once=True, signal_key=signal_key, actionable=True,
                          tickets=_tickets(members), said=_explanation(members))
    refreshed = _refresh_signal(store, signal_key)
    announced = refreshed or value
    if announced is not None:
        announce(ctx, announced)
    with own_store(store).tables() as tx:
        signal = tx.get('signals', {'session_id': 'work:', 'name': f'signal:{BOARD}:{signal_key}'})
        payload: dict[str, Any] = json.loads(str(signal['text'])) if signal is not None else {}
        confirmed = {(str(ticket['base_id']), str(ticket['work_id']))
                     for ticket in cast(list[dict[str, Any]], payload.get('tickets') or [])}
        for row in current:
            key = {'base_id': row['base_id'], 'work_id': row['work_id']}
            latest = tx.get('hold_reviews', key)
            # An inbox reader may consume an older batch between claiming its key and merging new members.
            # Its retained payload proves which tickets reached that batch, even after consumption.
            if (str(row['base_id']), str(row['work_id'])) in confirmed and latest is not None \
                    and latest['signal_key'] == signal_key and float(latest['deadline']) <= at:
                tx.concern(work_id=str(row['work_id']), kind='hold-review')
                tx.update('hold_reviews', key, {'deadline': at + REVIEW_SECONDS})
    return _next(store)


def _members(store: Store, signal_key: str) -> list[dict[str, Any]]:
    with own_store(store).tables(write=False) as tx:
        return list(tx.rows_in('hold_reviews', 'signal_key', [signal_key]))


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
        members = list(tx.rows_in('hold_reviews', 'signal_key', [signal_key]))
        tickets = _tickets(members)
        if value.get('tickets') == tickets and value.get('active') == bool(members):
            return None
        value.update(tickets=tickets, said=_explanation(members), active=bool(members))
        tx.concern(kind='signal')
        tx.update('signals', key, {'text': json.dumps(value, ensure_ascii=False)})
        return value


def _claim(store: Store, due: list[dict[str, Any]], at: float) -> tuple[list[dict[str, Any]], str]:
    """Give concurrent passes one persisted delivery key without holding map-store locks."""
    with own_store(store).tables() as tx:
        current = [tx.get('hold_reviews', {'base_id': row['base_id'], 'work_id': row['work_id']}) for row in due]
        current = [row for row in current if row is not None and float(row['deadline']) <= at]
        if not current:
            return [], ''
        state = tx.get('hold_review_state', {'name': 'seeded'})
        signal_key = str(state['signal_key']) if state and state.get('signal_key') else ''
        signal = tx.get('signals', {'session_id': 'work:', 'name': f'signal:{BOARD}:{signal_key}'}) \
            if signal_key else None
        if not signal_key or signal is not None and not json.loads(str(signal['text'])).get('active'):
            signal_key = f'hold-review:{secrets.token_hex(8)}'
            tx.concern(kind='hold-review')
            tx.update('hold_review_state', {'name': 'seeded'}, {'signal_key': signal_key})
        for row in current:
            tx.concern(work_id=str(row['work_id']), kind='hold-review')
            tx.update('hold_reviews', {'base_id': row['base_id'], 'work_id': row['work_id']},
                      {'signal_key': signal_key})
    return current, signal_key
