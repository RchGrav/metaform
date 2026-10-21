"""An outside agent seat, `agent:<name>`: an agent that reads its turn with the `turn` tool and answers with `submit`.

The runner puts the turns since the seat's last reply on the seat's row as `pending` and waits up to `agent_wait`
seconds for `submit` to put a reply beside it.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from . import store
from .seat import Interrupted, Late, Reply, Seat

POLL = 0.25


class AgentSeat(Seat):
    kind = 'agent'

    async def exchange(self, text: str, seconds: float) -> Reply:
        held = store.seats(self.number)[self.position]
        if not (held['pending'] and held['reply']):  # a reply given while no runner ran is kept for this one
            store.seat_change(self.number, self.position, pending=text, asked=time.time(), reply=None)
        deadline = time.time() + seconds
        reply: Any = None
        while time.time() < deadline:
            reply = store.seats(self.number)[self.position]['reply']
            if reply or store.discussion(self.number)['state'] != 'running':
                break
            await asyncio.sleep(POLL)
        if not reply:
            if store.discussion(self.number)['state'] != 'running':
                raise Interrupted
            store.seat_change(self.number, self.position, pending=None)
            raise Late(seconds, delivered=False)
        store.seat_change(self.number, self.position, pending=None, reply=None)
        return Reply(str(reply['text']))
