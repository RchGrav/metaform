"""Reported token use per participant and phase, with durable whole-phase notices."""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from metaform.data import DataConnection

from . import store
from .prompts import said

THRESHOLDS = (50, 80, 100, 120)


@dataclass(frozen=True)
class Prompt:
    text: str = ''
    notice: int = 0
    closing: bool = False


def phase(found: Mapping[str, Any]) -> str | None:
    stage = found.get('stage')
    return 'panel' if stage in (None, 'discussion') else 'collaboration' if stage == 'collaboration' else None


def limit(found: Mapping[str, Any]) -> int:
    snapshot = cast(dict[str, Any], found.get('snapshot') or {})
    value = snapshot.get('token_budget', 0)
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def tokens(use: Mapping[str, Any], kind: str) -> tuple[int, bool]:
    """ACP input excludes its separate cache counters; OpenRouter input includes them. Output includes reasoning."""
    fields = ('prompt_tokens', 'completion_tokens', 'cached_tokens', 'cache_write_tokens') \
        if kind == 'acp' else ('prompt_tokens', 'completion_tokens')
    reported = [value for field in fields if isinstance(value := use.get(field), int)
                and not isinstance(value, bool) and value >= 0]
    return sum(reported), bool(reported)


def _key(found: Mapping[str, Any]) -> tuple[int, int, str] | None:
    current = phase(found)
    return (int(found['number']), int(found.get('topic') or 0), current) if current is not None else None


def _usage(db: DataConnection, key: tuple[int, int, str]) -> list[dict[str, Any]]:
    return [dict(row) for row in db.execute(
        'SELECT * FROM phase_usage WHERE discussion=? AND topic=? AND phase=? ORDER BY position', key)]


def _add(db: DataConnection, key: tuple[int, int, str], row: Mapping[str, Any], use: Mapping[str, Any],
         reply_id: str, prepared: Prompt | None = None) -> None:
    prepared = prepared or Prompt()
    spent, reported = tokens(use, str(row['kind']))
    inserted = db.execute('INSERT OR IGNORE INTO phase_replies VALUES (?, ?, ?, ?, ?, ?, ?, NULL)',
                          (key[0], reply_id, key[1], key[2], row['position'], spent, int(reported))).rowcount
    if inserted:
        db.execute('INSERT INTO phase_usage(discussion,topic,phase,position,tokens,reported,unreported,notice,closing) '
                   'VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(discussion,topic,phase,position) DO UPDATE SET '
                   'tokens=tokens+excluded.tokens, reported=reported+excluded.reported, '
                   'unreported=unreported+excluded.unreported, notice=MAX(notice,excluded.notice), '
                   'closing=MAX(closing,excluded.closing)',
                   (*key, row['position'], spent, int(reported), int(not reported), prepared.notice,
                    int(prepared.closing)))


def _initialize(db: DataConnection, found: Mapping[str, Any]) -> None:
    """Seed a historical active phase once from actual saved model responses, never from its context size."""
    key = _key(found)
    if key is None or not db.execute('INSERT OR IGNORE INTO phase_seed VALUES (?, ?, ?)', key).rowcount:
        return
    seated = {int(row['position']): row for given in db.execute('SELECT * FROM seats WHERE discussion=?', (key[0],))
              if (row := store.plain(given)) is not None}
    linked = {int(row['recorded']) for row in db.execute(
        'SELECT recorded FROM phase_replies WHERE discussion=? AND topic=? AND phase=? AND recorded IS NOT NULL', key)}
    pending_handoff = cast(dict[str, Any], found.get('handoff') or {})
    topic = key[1] if found.get('stage') else None
    for given in db.execute('SELECT * FROM submissions WHERE discussion=? AND topic IS ? ORDER BY number',
                            (key[0], topic)):
        saved = store.plain(given)
        if saved is None or saved['position'] is None or int(saved['position']) not in seated:
            continue
        allowed = ('seat', 'pass', 'carry') if key[2] == 'panel' else ('collab',)
        if saved['kind'] not in allowed or int(saved['number']) in linked:
            continue
        receipt = f'saved:{saved["number"]}'
        if saved['kind'] == 'carry' and 'after' in pending_handoff and saved['number'] > pending_handoff['after']:
            receipt = f'carry:{pending_handoff["after"]}:{saved["position"]}'
        _add(db, key, seated[int(saved['position'])], saved, receipt)
        db.execute('UPDATE phase_replies SET recorded=? WHERE discussion=? AND reply=?',
                   (saved['number'], key[0], receipt))
    for position, row in seated.items():
        extra = cast(dict[str, Any], row.get('extra') or {})
        pending = extra.get('panel_reply' if key[2] == 'panel' else 'phase_reply')
        if not isinstance(pending, dict):
            continue
        held = cast(dict[str, Any], pending)
        if int(held.get('topic') or 0) != key[1]:
            continue
        if not held.get('usage_id'):
            held['usage_id'] = f'pending:{key[1]}:{key[2]}:{position}'
            store.update(db, 'seats', {'discussion': key[0], 'position': position}, {'extra': extra})
        _add(db, key, row, cast(dict[str, Any], held.get('use') or {}), str(held['usage_id']),
             Prompt(notice=int(held.get('notice', 0)), closing=bool(held.get('closing', False))))
    unjudged = found.get('unjudged')
    if key[2] == 'panel' and isinstance(unjudged, dict):
        held = cast(dict[str, Any], unjudged)
        position = int(held['position'])
        if position in seated:
            receipt = str(held.get('usage_id') or f'unjudged:{key[1]}:{position}')
            pending = cast(dict[str, Any], seated[position].get('extra') or {}).get('panel_reply')
            if isinstance(pending, dict):
                saved = cast(dict[str, Any], pending)
                if saved.get('original') == (held.get('original') or held.get('text')):
                    receipt = str(saved['usage_id'])
            _add(db, key, seated[position], cast(dict[str, Any], held.get('use') or {}), receipt)


def _status(db: DataConnection, found: Mapping[str, Any]) -> dict[str, Any]:
    key, maximum = _key(found), limit(found)
    usage = _usage(db, key) if key is not None else []
    by_position = {int(row['position']): row for row in usage}
    participants: list[dict[str, Any]] = []
    for seat in db.execute('SELECT position, name FROM seats WHERE discussion=? ORDER BY position',
                           (int(found['number']),)):
        own = by_position.get(int(seat['position']), {})
        participants.append({'position': int(seat['position']), 'name': str(seat['name']),
                             'tokens': int(own.get('tokens', 0)), 'reported': bool(own.get('reported', 0)),
                             'unreported': int(own.get('unreported', 0)), 'closing': bool(own.get('closing', 0))})
    peak = max((int(row['tokens']) for row in participants), default=0)
    notices = [dict(row) for row in db.execute(
        'SELECT percent, position, tokens, token_limit AS "limit", text FROM phase_notices '
        'WHERE discussion=? AND topic=? AND phase=? ORDER BY percent', key)] if key is not None else []
    return {'limit': maximum, 'phase': key[2] if key is not None else None,
            'topic': key[1] + 1 if key is not None else None, 'participants': participants, 'notices': notices,
            'closing': bool(maximum and peak >= maximum),
            'forced': bool(maximum and peak * 100 >= maximum * 120)}


def status(found: Mapping[str, Any]) -> dict[str, Any]:
    with store.connect() as db:
        store.fence(db, int(found['number']))
        _initialize(db, found)
        return _status(db, found)


def _evaluate(db: DataConnection, found: Mapping[str, Any]) -> dict[str, Any]:
    key, maximum = _key(found), limit(found)
    if key is None or not maximum:
        return _status(db, found)
    usage = _usage(db, key)
    peak = max(usage, key=lambda row: (int(row['tokens']), -int(row['position'])), default=None)
    if peak is None:
        return _status(db, found)
    position, spent = int(peak['position']), int(peak['tokens'])
    seat = db.execute('SELECT name FROM seats WHERE discussion=? AND position=?', (key[0], position)).fetchone()
    for percent in THRESHOLDS:
        if spent * 100 < maximum * percent:
            continue
        if db.execute('SELECT 1 FROM phase_notices WHERE discussion=? AND topic=? AND phase=? AND percent=?',
                      (*key, percent)).fetchone() is not None:
            continue
        fills = {'phase': key[2], 'seat': str(seat['name']) if seat is not None else str(position + 1),
                 'tokens': spent, 'limit': maximum}
        text = said('budget_warning', **fills, percent=percent) if percent < 100 else \
            said(f'budget_closing_{key[2]}', **fills) if percent == 100 else said('budget_forced', **fills)
        db.execute('INSERT INTO phase_notices VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                   (*key, percent, position, spent, maximum, text))
        event = {'phase': key[2], 'topic': key[1] + 1, 'percent': percent, 'position': position,
                 'seat': fills['seat'], 'tokens': spent, 'limit': maximum, 'text': text}
        seq = int(db.execute('SELECT COALESCE(MAX(number), 0)+1 FROM events WHERE discussion=?',
                             (key[0],)).fetchone()[0])
        store.insert(db, 'events', {'discussion': key[0], 'number': seq, 'kind': 'budget',
                                   'text': json.dumps(event), 'seat': str(position), 'created': store.stamp()})
    return _status(db, found)


def evaluate(found: Mapping[str, Any]) -> dict[str, Any]:
    with store.connect() as db:
        store.fence(db, int(found['number']))
        _initialize(db, found)
        return _evaluate(db, found)


def record_reply(found: Mapping[str, Any], row: Mapping[str, Any], use: Mapping[str, Any], reply_id: str,
                 prepared: Prompt | None = None) -> None:
    """Count one physical response once, including a PASS or carry-forward note, before any Jev retry."""
    key = _key(found)
    if key is None or int(row['position']) < 0:
        return
    prepared = prepared or Prompt()
    with store.connect() as db:
        store.fence(db, key[0])
        current = store.plain(db.execute('SELECT * FROM discussions WHERE number=?', (key[0],)).fetchone())
        _initialize(db, current if current is not None and _key(current) == key else found)
        _add(db, key, row, use, reply_id, prepared)
        current = store.plain(db.execute('SELECT * FROM discussions WHERE number=?', (key[0],)).fetchone())
        if current is not None and _key(current) == key:
            _evaluate(db, current)


def prompt(found: Mapping[str, Any], position: int) -> Prompt:
    key = _key(found)
    if key is None or not limit(found):
        return Prompt()
    with store.connect() as db:
        store.fence(db, int(found['number']))
        _initialize(db, found)
        current = _status(db, found)
        empty: dict[str, Any] = {}
        own = next((row for row in _usage(db, key) if row['position'] == position), empty)
        last = int(own.get('notice', 0))
        peak = max((int(row['tokens']) for row in current['participants']), default=0)
        notices = [one for one in current['notices'] if last < int(one['percent']) <= 100
                   and peak * 100 >= limit(found) * int(one['percent'])]
        if current['closing'] and not own.get('closing') and not any(one['percent'] == 100 for one in notices):
            notices += [one for one in current['notices'] if one['percent'] == 100]
        return Prompt('\n\n'.join(str(one['text']) for one in notices),
                      max([int(one['percent']) for one in notices], default=last), bool(current['closing']))


def needs_closing(found: Mapping[str, Any], position: int) -> bool:
    if not limit(found) or phase(found) is None:
        return False
    current = status(found)
    return bool(current['closing'] and any(row['position'] == position and not row['closing']
                                           for row in current['participants']))
