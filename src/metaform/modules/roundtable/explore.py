"""The seats' time to explore their controls, BASE-066, before the table's first turn.

Every harness seat and every model seat is sent, at once, the message `explore`, "Please take a moment to explore
your controls.", and may turn and look until it answers or roundtable_explore seconds pass, whichever comes first;
a harness seat still busy then is interrupted. Its answer is not a submission and enters nothing. An agent seat is
sent nothing, since it reads only its turns, and may use its controls at any time. The discussion starts when every
seat has answered or the time is up. A table explores once: a table that has had a turn, or explored already, never
does, so a runner started again goes on where the table is.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Any

from metaform.module import Stop

from . import harness, seats, store, toolloop
from .render import said

if TYPE_CHECKING:
    from .runner import Table

log = logging.getLogger(__name__)

GRACE = 15.0  # seconds past the time to explore for a harness seat's interrupted turn to close


def due(found: dict[str, Any], held: Any) -> bool:
    return found['state'] == 'running' and not found['explored'] and not store.submissions(held, int(found['number']))


def explore(table: Table) -> None:
    """The time to explore, for every seat at once, then the table marked explored."""
    found = table.row()
    if not due(found, table.store):
        return
    seconds = int(table.ctx.setting('roundtable_explore'))
    deadline = time.time() + seconds
    if seconds > 0:
        table.change(explore_until=deadline)
        threads = [threading.Thread(target=one, args=(table, found, seat, deadline), daemon=True,
                                    name=f'roundtable-explore-{seat["position"]}')
                   for seat in store.seats(table.store, table.number)
                   if seat['kind'] in ('openrouter', 'acp') and not seat['gone']]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(max(0.0, deadline + GRACE - time.time()))
    table.change(explored=True, explore_until=None)


def one(table: Table, found: dict[str, Any], seat: dict[str, Any], deadline: float) -> None:
    """One seat's time to explore; a seat that fails to take it is logged, and its turns go on as ever."""
    message = said('explore')
    try:
        if seat['kind'] == 'openrouter':
            at = toolloop.At(table.store, table.number, int(seat['position']), table.picture)
            messages = [*seat['messages'], {'role': 'user', 'content': message}]
            _, kept = toolloop.turn(str(seat['id']), at, messages, deadline=deadline, paid=table.pay)
            store.seat_change(table.store, table.number, int(seat['position']), messages=kept)
            return
        row = harness.session_of(table.ctx, table.store, found, seat, deadline, table.ending)
        if row is None:
            return
        found = store.discussion(table.store, table.number)  # with its ticket
        harness.exchange(table.ctx, table.store, found, seat, row, message, deadline, table.ending)
    except (seats.Silent, harness.Silent, harness.Gone, Stop) as error:
        log.info('Roundtable %s: %s explored no further: %s', table.number, seat['name'], error)
