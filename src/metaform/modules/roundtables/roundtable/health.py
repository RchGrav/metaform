"""A seat's availability: `active`, `degraded`, or `unavailable` with the reason, since when and when it is probed next.

A seat's failures are counted in a row by kind (`seat.NoReply.kind`): empty replies, transient failures (a busy or
failing endpoint, a dropped connection), timeouts, refused requests, and each kind apart, so a seat that times out
once between two empty replies starts its count again. `degraded_after` failures of one kind in a row mark it
degraded, still asked every turn; `unavailable_after` make it unavailable, no longer asked until its probe passes.
Some failures make a seat unavailable at once, since asking again cannot help: a 402 for want of credits (that seat
only; the table goes on), a request OpenRouter refused (400, 401, 404, 413), and an ACP session that ended, which
waits for the chair to reseat it. An unavailable seat is probed once `retry_at` comes, `probe_wait` seconds after it
became so (a minute for credits), the wait doubling after each failed probe to an hour. A probe that passes puts the
seat back on its turns, degraded with its count kept, so one more failure makes it unavailable again at once; a turn
answered makes it active.

Every change of availability is told to the chair as an operational event, never to a seat or Jev.
"""
from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from . import config, store
from .prompts import said

ACTIVE, DEGRADED, UNAVAILABLE = store.AVAILABILITY
AT_ONCE = frozenset({'credits', 'refused', 'gone'})  # failures asking again cannot help: unavailable at the first
CREDITS = 60.0  # seconds before a seat out of credits is first probed, free of charge
HOUR = 3600.0


def usable(row: Mapping[str, Any]) -> bool:
    """Whether a seat is asked on its turn: it has not left and is not unavailable."""
    return not row['gone'] and row.get('availability', ACTIVE) != UNAVAILABLE


def returns(row: Mapping[str, Any]) -> bool:
    """Whether a seat not asked now comes back by itself, once a probe passes; a gone seat waits for the chair."""
    return not row['gone'] and row.get('retry_at') is not None


def due(row: Mapping[str, Any], now: float | None = None) -> bool:
    """Whether an unavailable seat's probe is due."""
    return returns(row) and (time.time() if now is None else now) >= float(row['retry_at'])


def failed(row: Mapping[str, Any], kind: str, reason: str,
           now: float | None = None) -> tuple[dict[str, Any], str | None]:
    """The seat's row changes for one more failure of `kind`, and the event it is told to the chair as, `seat_lost`
    or `seat_degraded`, when its availability changed; a seat already unavailable stays so, its wait doubled."""
    now = time.time() if now is None else now
    failures = int(row.get('failures') or 0) + 1 if row.get('failing') == kind else 1
    changes: dict[str, Any] = {'failures': failures, 'failing': kind}
    was = str(row.get('availability') or ACTIVE)
    after = 1 if kind in AT_ONCE else int(config.value('unavailable_after'))
    if failures >= after or was == UNAVAILABLE:
        first = CREDITS if kind == 'credits' else float(config.value('probe_wait'))
        wait = min(HOUR, first * 2 ** max(0, failures - after))
        changes.update(availability=UNAVAILABLE, reason=reason,
                       since=row.get('since') if was == UNAVAILABLE and row.get('since') else store.stamp(),
                       retry_at=None if kind == 'gone' else now + wait)
        return changes, None if was == UNAVAILABLE else 'seat_lost'
    if failures >= int(config.value('degraded_after')) or was == DEGRADED:
        changes.update(availability=DEGRADED, reason=reason)
        return changes, None if was == DEGRADED else 'seat_degraded'
    return changes, None


def probed(row: Mapping[str, Any]) -> dict[str, Any]:
    """The seat's row changes once its probe passed: asked again, degraded, its count kept."""
    return {'availability': DEGRADED, 'retry_at': None}


def answered(row: Mapping[str, Any]) -> dict[str, Any]:
    """The seat's row changes once it answered a turn: active, its failures forgotten; nothing when it was already."""
    if str(row.get('availability') or ACTIVE) == ACTIVE and not row.get('failures'):
        return {}
    return {'availability': ACTIVE, 'failures': 0, 'failing': None, 'reason': None, 'since': None, 'retry_at': None}


def told(event: str, row: Mapping[str, Any], changes: Mapping[str, Any]) -> str:
    """An availability event's text, as the chair reads it."""
    if event == 'seat_degraded':
        return said('event_seat_degraded', seat=row['name'], count=changes['failures'], kind=changes['failing'],
                    reason=changes['reason'])
    if event == 'seat_restored':
        return said('event_seat_probed', seat=row['name'])
    retry = changes.get('retry_at')
    when = said('event_seat_probe', at=time.strftime('%H:%M:%S', time.localtime(float(retry)))) if retry else \
        said('event_seat_reseat')
    return said('event_seat_unavailable', seat=row['name'], reason=changes['reason'], when=when)
