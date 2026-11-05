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
BASES = ('uncached', 'output', 'all')


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


def basis(found: Mapping[str, Any]) -> str:
    """Legacy snapshots retain their original cache-inclusive metric until explicitly changed."""
    value = cast(dict[str, Any], found.get('snapshot') or {}).get('token_basis', 'all')
    return str(value) if value in BASES else 'all'


def tokens(use: Mapping[str, Any], kind: str, token_basis: str = 'all') -> tuple[int, bool]:
    """Normalize reported transport usage, keeping cached input and reasoning from being counted twice."""
    fields = ('prompt_tokens', 'completion_tokens', 'cached_tokens', 'cache_write_tokens')
    reported = {field: value for field in fields if isinstance(value := use.get(field), int)
                and not isinstance(value, bool) and value >= 0}
    if token_basis == 'output':
        return reported.get('completion_tokens', 0), 'completion_tokens' in reported
    if token_basis == 'uncached':
        incoming = reported.get('prompt_tokens', 0)
        incoming += reported.get('cache_write_tokens', 0) if kind == 'acp' else -reported.get('cached_tokens', 0)
        counted = ('prompt_tokens', 'cache_write_tokens', 'completion_tokens') if kind == 'acp' else \
            ('prompt_tokens', 'completion_tokens')
        return max(incoming, 0) + reported.get('completion_tokens', 0), any(field in reported for field in counted)
    counted = fields if kind == 'acp' else ('prompt_tokens', 'completion_tokens')
    return sum(reported.get(field, 0) for field in counted), any(field in reported for field in counted)


def _key(found: Mapping[str, Any]) -> tuple[int, int, str] | None:
    current = phase(found)
    return (int(found['number']), int(found.get('topic') or 0), current) if current is not None else None


def _usage(db: DataConnection, key: tuple[int, int, str]) -> list[dict[str, Any]]:
    return [dict(row) for row in db.execute(
        'SELECT * FROM phase_usage WHERE discussion=? AND topic=? AND phase=? ORDER BY position', key)]


def _add(db: DataConnection, key: tuple[int, int, str], row: Mapping[str, Any], use: Mapping[str, Any],
         reply_id: str, prepared: Prompt | None = None, token_basis: str = 'all') -> None:
    prepared = prepared or Prompt()
    spent, reported = tokens(use, str(row['kind']), token_basis)
    db.execute('INSERT OR IGNORE INTO phase_reply_usage VALUES (?, ?, ?, ?)',
               (key[0], reply_id, row['kind'], json.dumps(dict(use))))
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
        _add(db, key, seated[int(saved['position'])], saved, receipt, token_basis=basis(found))
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
             Prompt(notice=int(held.get('notice', 0)), closing=bool(held.get('closing', False))), basis(found))
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
            _add(db, key, seated[position], cast(dict[str, Any], held.get('use') or {}), receipt,
                 token_basis=basis(found))


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
    return {'limit': maximum, 'basis': basis(found), 'phase': key[2] if key is not None else None,
            'topic': key[1] + 1 if key is not None else None, 'participants': participants, 'notices': notices,
            'closing': bool(maximum and peak >= maximum),
            'forced': bool(maximum and peak * 100 >= maximum * 120)}


def status(found: Mapping[str, Any]) -> dict[str, Any]:
    with store.connect() as db:
        store.fence(db, int(found['number']))
        _initialize(db, found)
        return _status(db, found)


def progress(found: Mapping[str, Any]) -> dict[str, Any]:
    """Read the recorded current-phase counters without seeding history or changing notices."""
    with store.connect() as db:
        return _status(db, found)


def _notice_text(key: tuple[int, int, str], name: str, spent: int, maximum: int, percent: int) -> str:
    fills = {'phase': key[2], 'topic': key[1] + 1, 'seat': name, 'tokens': spent, 'limit': maximum,
             'percent': percent, 'used_percent': spent * 100 // maximum}
    prompt = 'budget_warning' if percent == 50 else f'budget_winddown_{key[2]}' if percent == 80 else \
        f'budget_closing_{key[2]}' if percent == 100 else 'budget_forced'
    return said(prompt, **fills)


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
        name = str(seat['name']) if seat is not None else str(position + 1)
        text = _notice_text(key, name, spent, maximum, percent)
        db.execute('INSERT INTO phase_notices VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                   (*key, percent, position, spent, maximum, text))
        event = {'phase': key[2], 'topic': key[1] + 1, 'percent': percent, 'position': position,
                 'seat': name, 'tokens': spent, 'limit': maximum, 'text': text}
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
        _add(db, key, row, use, reply_id, prepared,
             basis(current if current is not None and _key(current) == key else found))
        current = store.plain(db.execute('SELECT * FROM discussions WHERE number=?', (key[0],)).fetchone())
        if current is not None and _key(current) == key:
            _evaluate(db, current)


def _original_usage(db: DataConnection, found: Mapping[str, Any], receipt: Mapping[str, Any],
                    seated: Mapping[int, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    """Recover old receipts from their original submission or unfinished reply, without guessing token use."""
    raw = db.execute('SELECT kind,usage FROM phase_reply_usage WHERE discussion=? AND reply=?',
                     (found['number'], receipt['reply'])).fetchone()
    if raw is not None:
        return str(raw['kind']), cast(dict[str, Any], json.loads(raw['usage']))
    row = seated[int(receipt['position'])]
    if receipt['recorded'] is not None:
        saved = store.plain(db.execute('SELECT * FROM submissions WHERE discussion=? AND number=?',
                                       (found['number'], receipt['recorded'])).fetchone())
        if saved is not None:
            kind = next((kind for kind in ('acp', 'agent', 'a2a')
                         if str(saved['seat']).startswith(kind + ':')), 'openrouter')
            return kind, saved
    extra = cast(dict[str, Any], row.get('extra') or {})
    for key in ('panel_reply', 'phase_reply'):
        pending = extra.get(key)
        if isinstance(pending, dict):
            held = cast(dict[str, Any], pending)
            if held.get('usage_id') == receipt['reply'] and int(held.get('topic') or 0) == receipt['topic']:
                return str(row['kind']), cast(dict[str, Any], held.get('use') or {})
    pending = found.get('unjudged')
    if receipt['phase'] == 'panel' and isinstance(pending, dict):
        held = cast(dict[str, Any], pending)
        identity = held.get('usage_id') or f'unjudged:{receipt["topic"]}:{receipt["position"]}'
        if held['position'] == receipt['position'] and identity == receipt['reply']:
            return str(row['kind']), cast(dict[str, Any], held.get('use') or {})
    if receipt['reported']:
        raise ValueError(f'Cannot change token accounting: original usage for reply {receipt["reply"]} is missing.')
    return str(row['kind']), {}


def configure(found: Mapping[str, Any], maximum: int, token_basis: str | None = None) -> dict[str, Any]:
    """Atomically change the limit and explicitly rebase only the current phase when its metric changes."""
    from .runner import alive

    with store.connect() as db:
        number = int(found['number'])
        store.fence(db, number)
        current = store.plain(db.execute('SELECT * FROM discussions WHERE number=?', (number,)).fetchone())
        if current is None:
            raise store.Missing(f'No roundtable {number}.')
        previous = basis(current)
        selected = previous if token_basis is None else token_basis
        if selected not in BASES:
            raise ValueError('token_basis is uncached, output, or all.')
        if selected != previous and alive(current):
            raise ValueError('Hold this roundtable and wait until its runner stops before changing token accounting.')
        key = _key(current)
        if selected != previous and key is not None:
            _initialize(db, current)
            seated = {int(row['position']): row for given in db.execute('SELECT * FROM seats WHERE discussion=?',
                                                                       (number,))
                      if (row := store.plain(given)) is not None}
            receipts = [dict(row) for row in db.execute(
                'SELECT * FROM phase_replies WHERE discussion=? AND topic=? AND phase=?', key)]
            totals: dict[int, list[int]] = {}
            for receipt in receipts:
                kind, use = _original_usage(db, current, receipt, seated)
                if receipt['reported'] and not tokens(use, kind)[1]:
                    raise ValueError(f'Cannot change token accounting: original usage for reply '
                                     f'{receipt["reply"]} is missing.')
                spent, reported = tokens(use, kind, selected)
                db.execute('INSERT OR IGNORE INTO phase_reply_usage VALUES (?, ?, ?, ?)',
                           (number, receipt['reply'], kind, json.dumps(use)))
                db.execute('UPDATE phase_replies SET tokens=?,reported=? WHERE discussion=? AND reply=?',
                           (spent, int(reported), number, receipt['reply']))
                own = totals.setdefault(int(receipt['position']), [0, 0, 0])
                own[0] += spent
                own[1] += int(reported)
                own[2] += int(not reported)
            db.execute('DELETE FROM phase_usage WHERE discussion=? AND topic=? AND phase=?', key)
            db.execute('DELETE FROM phase_notices WHERE discussion=? AND topic=? AND phase=?', key)
            for position, counts in totals.items():
                db.execute('INSERT INTO phase_usage(discussion,topic,phase,position,tokens,reported,unreported) '
                           'VALUES (?,?,?,?,?,?,?)', (*key, position, *counts))
            for position, row in seated.items():
                extra = cast(dict[str, Any], row.get('extra') or {})
                changed = False
                for pending_key in ('panel_reply', 'phase_reply', 'collaboration_request'):
                    pending = extra.get(pending_key)
                    if isinstance(pending, dict) and cast(dict[str, Any], pending).get('topic') == key[1]:
                        cast(dict[str, Any], pending).update(notice=0, closing=False)
                        changed = True
                if changed:
                    store.update(db, 'seats', {'discussion': number, 'position': position}, {'extra': extra})
        captured = cast(dict[str, Any], current.get('snapshot') or {})
        snapshot = {**captured, 'token_budget': maximum,
                    **({'token_basis': selected} if token_basis is not None else {})}
        store.update(db, 'discussions', {'number': number}, {'snapshot': snapshot})
        current['snapshot'] = snapshot
        if selected != previous and key is not None:
            state = _status(db, current)
            counts = ', '.join(f'{row["name"]}: {int(row["tokens"]):,}' for row in state['participants'])
            names = {'all': 'input, cached input and output', 'uncached': 'uncached input plus output',
                     'output': 'generated output only'}
            text = said('budget_reconfigured', topic=key[1] + 1, phase=key[2], previous=names[previous],
                        basis=names[selected], limit=f'{maximum:,}', counts=counts)
            seq = int(db.execute('SELECT COALESCE(MAX(number), 0)+1 FROM events WHERE discussion=?',
                                 (number,)).fetchone()[0])
            store.insert(db, 'events', {'discussion': number, 'number': seq, 'kind': 'budget',
                                       'text': json.dumps({'action': 'reconfigured', 'basis': selected,
                                                           'previous_basis': previous, 'phase': key[2],
                                                           'topic': key[1] + 1, 'text': text}),
                                       'created': store.stamp()})
            _evaluate(db, current)
        return current


def delivered_prompt(found: Mapping[str, Any], position: int, prepared: Prompt) -> None:
    """Acknowledge notice text at delivery; a closing statement still needs an actual reply."""
    key = _key(found)
    if key is None or not prepared.text or not prepared.notice:
        return
    with store.connect() as db:
        store.fence(db, key[0])
        _initialize(db, found)
        db.execute('INSERT INTO phase_usage(discussion,topic,phase,position,notice) VALUES (?,?,?,?,?) '
                   'ON CONFLICT(discussion,topic,phase,position) DO UPDATE SET notice=MAX(notice,excluded.notice)',
                   (*key, position, prepared.notice))


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
        if current['forced']:
            return Prompt()
        peak = max(current['participants'], key=lambda row: int(row['tokens']), default=None)
        if peak is None:
            return Prompt()
        spent, maximum = int(peak['tokens']), limit(found)
        crossed = [percent for percent in THRESHOLDS if spent * 100 >= maximum * percent]
        notices = [50] if last < 50 and 50 in crossed else []
        # These are fresh turn instructions. Their operational threshold events remain recorded once.
        if 100 in crossed:
            notices.append(100)
        elif 80 in crossed:
            notices.append(80)
        text = '\n\n'.join(_notice_text(key, str(peak['name']), spent, maximum, percent) for percent in notices)
        return Prompt(text, max(crossed, default=last), bool(current['closing']))


def needs_closing(found: Mapping[str, Any], position: int) -> bool:
    if not limit(found) or phase(found) is None:
        return False
    current = status(found)
    return bool(current['closing'] and any(row['position'] == position and not row['closing']
                                           for row in current['participants']))
