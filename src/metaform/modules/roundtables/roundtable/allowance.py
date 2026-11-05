"""Private reply credit earned only by PASS or accepted peer messages missed during native work."""
from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from metaform.data import DataConnection

from . import store


@dataclass(frozen=True)
class Offer:
    receipt: str
    limit: int
    offered: int = 0
    through: int = 0


def enabled(found: Mapping[str, Any]) -> bool:
    return bool(cast(dict[str, Any], found.get('snapshot') or {}).get('reply_credits'))


def _topic(found: Mapping[str, Any]) -> int | None:
    return int(found['topic']) if found.get('stage') else None


def _state(extra: Mapping[str, Any], topic: int | None) -> dict[str, Any]:
    saved = cast(dict[str, Any], extra.get('reply_allowance') or {})
    return dict(saved) if saved and saved.get('topic') == topic else {
        'topic': topic, 'credit': 0, 'pending': None, 'last': None}


def _seat(db: DataConnection, number: int, position: int) -> dict[str, Any]:
    found = store.plain(db.execute('SELECT extra FROM seats WHERE discussion=? AND position=?',
                                   (number, position)).fetchone())
    if found is None:
        raise ValueError('No participant in that position.')
    return cast(dict[str, Any], found.get('extra') or {})


def _save(db: DataConnection, number: int, position: int, extra: dict[str, Any], state: dict[str, Any]) -> None:
    store.update(db, 'seats', {'discussion': number, 'position': position},
                 {'extra': {**extra, 'reply_allowance': state}})


def limit(found: Mapping[str, Any], position: int, base: int = 512) -> int:
    """Use the promised limit while a reply awaits judgment, otherwise the next turn's banked credit."""
    if not enabled(found) or position < 0:
        return base
    with store.connect() as db:
        state = _state(_seat(db, int(found['number']), position), _topic(found))
    pending = cast(dict[str, Any], state.get('pending') or {})
    return int(pending['limit']) if pending else base * (1 + int(state['credit']))


def begin(number: int, position: int, base: int = 512) -> Offer:
    """Freeze one physical request's history; a continuation reuses its receipt and promised limit."""
    with store.connect() as db:
        store.fence(db, number)
        found = store.plain(db.execute('SELECT * FROM discussions WHERE number=?', (number,)).fetchone())
        if found is None:
            raise ValueError('No such discussion.')
        through = int(db.execute('SELECT COALESCE(MAX(number),0) FROM submissions WHERE discussion=?',
                                 (number,)).fetchone()[0])
        if not enabled(found):
            return Offer(uuid.uuid4().hex, base, through=through)
        extra = _seat(db, number, position)
        state = _state(extra, _topic(found))
        pending = cast(dict[str, Any], state.get('pending') or {})
        if not pending:
            offered = int(state['credit'])
            pending = {'receipt': uuid.uuid4().hex, 'limit': base * (1 + offered), 'offered': offered,
                       'delivered': False, 'busy': True, 'through': through}
            state['pending'] = pending
            _save(db, number, position, extra, state)
        else:
            # Continue sends the queued history once, against the same durable reply promise.
            state['pending'] = pending = {**pending, 'through': through, 'busy': True}
            _save(db, number, position, extra, state)
        return Offer(str(pending['receipt']), int(pending['limit']), int(pending['offered']), int(pending['through']))


def _mark(number: int, position: int, receipt: str, field: str, value: bool) -> None:
    with store.connect() as db:
        store.fence(db, number)
        extra = _seat(db, number, position)
        state = cast(dict[str, Any], extra.get('reply_allowance') or {})
        pending = cast(dict[str, Any], state.get('pending') or {})
        if pending.get('receipt') != receipt or pending.get(field) == value:
            return
        state['pending'] = {**pending, field: value}
        _save(db, number, position, extra, state)


def delivered(number: int, position: int, receipt: str) -> None:
    _mark(number, position, receipt, 'delivered', True)


def answered(number: int, position: int, receipt: str) -> None:
    """Waiting behind Jev is not native work and cannot earn missed-message credit."""
    _mark(number, position, receipt, 'busy', False)


def completed(number: int, receipt: str, position: int | None = None) -> dict[str, Any] | None:
    """Recover an already committed reply and clear only its matching stale private request."""
    with store.connect() as db:
        if position is not None:
            store.fence(db, number)
        saved = store.plain(db.execute(
            'SELECT s.* FROM phase_replies p JOIN submissions s ON s.discussion=p.discussion '
            'AND s.number=p.recorded WHERE p.discussion=? AND p.reply=?', (number, receipt)).fetchone())
        if saved is not None and position is not None and saved.get('position') == position:
            extra = _seat(db, number, position)
            state = cast(dict[str, Any], extra.get('reply_allowance') or {})
            pending = cast(dict[str, Any], state.get('pending') or {})
            if pending.get('receipt') == receipt:
                state['pending'] = None
                _save(db, number, position, extra, state)
        return saved


def recorded(db: DataConnection, number: int, row: Mapping[str, Any], receipt: str | None = None) -> None:
    """Apply one newly recorded outcome inside store.record's deduplicated submission transaction."""
    found = store.plain(db.execute('SELECT * FROM discussions WHERE number=?', (number,)).fetchone())
    if found is None or not enabled(found):
        return
    peer_message = row['kind'] == 'seat' and bool(row.get('accepted')) and not row.get('unjudged')
    own_outcome = row['kind'] in ('seat', 'pass', 'none')
    key = receipt or f'submission:{row["number"]}'
    for given in db.execute('SELECT position,extra FROM seats WHERE discussion=?', (number,)).fetchall():
        seat = store.plain(given)
        if seat is None:
            continue
        position = int(seat['position'])
        extra = cast(dict[str, Any], seat.get('extra') or {})
        state = _state(extra, _topic(found))
        pending = cast(dict[str, Any], state.get('pending') or {})
        changed = False
        if position == row.get('position') and own_outcome and state.get('last') != key:
            if receipt is not None and pending and pending['receipt'] != receipt:
                continue
            if row['kind'] == 'pass':
                state['credit'] = int(state['credit']) + 1
            elif peer_message:
                state['credit'] = max(0, int(state['credit']) - int(pending.get('offered', 0)))
            state['pending'], state['last'] = None, key
            changed = True
        elif peer_message and position != row.get('position') and pending.get('busy') and \
                state['topic'] == row.get('topic'):
            state['credit'] = int(state['credit']) + 1
            changed = True
        if changed:
            _save(db, number, position, extra, state)


def reset(db: DataConnection, number: int) -> None:
    """Start the next panel's allowance bank in the caller's phase-transition transaction."""
    found = store.plain(db.execute('SELECT * FROM discussions WHERE number=?', (number,)).fetchone())
    if found is None or not enabled(found):
        return
    for given in db.execute('SELECT position,extra FROM seats WHERE discussion=?', (number,)).fetchall():
        seat = store.plain(given)
        if seat is not None:
            extra = cast(dict[str, Any], seat.get('extra') or {})
            _save(db, number, int(seat['position']), extra,
                  {'topic': _topic(found), 'credit': 0, 'pending': None, 'last': None})
