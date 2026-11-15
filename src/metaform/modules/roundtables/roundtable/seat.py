"""The one seat interface every kind of seat goes through.

The runner treats every seat alike: it gives the seat the turns since its last reply as one text, takes one reply,
cuts it to the table's reply limit when it is longer, and keeps the seat's running conversation in its row. A kind
supplies only how one prompt reaches its seat and how the reply comes back, `exchange`, and, when it holds something
for the life of the table, `open` and `close`.

Every seat has a system message, fixed for the table's life: the rules, which seat it is, the opening. A kind with a
system role of its own (`system_role`) sends it first in every request; every other kind is given it at the head of
the first prompt of each of its sessions. Within a topic the conversation only grows, except that the seat's own reply,
once judged, is replaced by what entered of it or by a one-line status (`settled`), never kept word for word when it
was vetoed or truncated. A session carries the same conversations across its topics. Independent topics may begin
their conversations again (`rebuild`). Optional native compression retains the native session.

- `acp` (`harness.AcpSeat`): Claude Code, Codex or Antigravity in its own ACP session on the person's own login;
- `openrouter` (`openrouter.ModelSeat`): a model through OpenRouter, its system message and its conversation since
  the topic opened sent each turn;
- `agent` (`outside.AgentSeat`): an outside agent that reads its turn with the `turn` tool and answers with `submit`;
- `a2a` (`peers.PeerSeat`): a remote A2A agent, sent each turn as an A2A message in the table's context.

A turn that gets no reply raises `NoReply`, whose `reason` says why in the words every seat reads; `delivered` says
whether the seat was given the turns anyway, so its next turn carries only what follows, and `kind` is its class, by
which the runner counts a seat's failures in a row (`health`): `empty` for a reply with no text, `transient` for a
busy or failing endpoint or a dropped connection, `refused` for a request asking again cannot help, `failed` for any
other. `Gone` takes the seat away from the table, `Late` is a turn that ran out of time, and `Interrupted` is a table
held or ended while the turn waited, which records nothing.

A seat that has failed until it is unavailable is asked again only after its `probe`, a cheap check that it can
answer, passes; a seat's conversation can be started again with `rebuild`, so its next turn is a first turn.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar

from .prompts import said


@dataclass
class Reply:
    """One reply: its text, whole, and what the turn used (prompt and cached tokens, cost, the model that answered)."""
    text: str
    use: dict[str, Any] = field(default_factory=dict[str, Any])


class NoReply(Exception):
    """The turn passed with no reply."""
    KIND: ClassVar[str] = 'failed'

    def __init__(self, error: str, delivered: bool = False, kind: str | None = None) -> None:
        super().__init__(error)
        self.delivered = delivered
        self.kind = kind or self.KIND

    def reason(self) -> str:
        return said('no_reply_model', error=self)


class Late(NoReply):
    KIND: ClassVar[str] = 'timeout'

    def __init__(self, seconds: float, delivered: bool = True) -> None:
        super().__init__(f'{seconds:.0f} seconds', delivered)
        self.seconds = seconds

    def reason(self) -> str:
        return said('no_reply_time', seconds=int(self.seconds))


class Gone(NoReply):
    """The seat's session ended, or could not be made: it leaves the table."""
    KIND: ClassVar[str] = 'gone'

    def reason(self) -> str:
        return said('seat_gone', how=self)


class Interrupted(Exception):
    """The table was held or ended while the turn waited; nothing is recorded."""


Paid = Callable[[float], None]


class Seat:
    """One seat at one table, for the life of its runner."""
    kind: ClassVar[str] = ''
    system_role: ClassVar[bool] = False  # sends `system` as a system message of its own, first in every request

    def __init__(self, table: dict[str, Any], row: dict[str, Any], paid: Paid) -> None:
        self.table = table
        self.number = int(table['number'])
        self.position = int(row['position'])
        self.id = str(row['id'])
        self.name = str(row['name'])
        self.row = row
        self.messages: list[dict[str, Any]] = list(row.get('messages') or [])
        self.session: str | None = row.get('session')
        self.reported: str | None = row.get('reported')
        self.extra: dict[str, Any] = dict(row.get('extra') or {})
        self.paid = paid
        self.system = ''  # the rules, which seat it is, the opening; given by the runner
        self.on_delivered: Callable[[], None] | None = None
        self.inflight_prompt: str | None = None

    async def open(self) -> None:
        """Make what the seat holds for the life of the table; Gone when it cannot be made."""

    async def exchange(self, text: str, seconds: float) -> Reply:
        """One prompt to the seat and its reply, in its own conversation."""
        raise NotImplementedError

    async def reply(self, text: str, seconds: float) -> Reply:
        """`exchange`, its prompt and reply added to the conversation kept in the seat's row; a prompt the seat was
        given but did not answer is kept too. The first prompt of a conversation opens with the system message, for
        a kind with no system role."""
        if self.system and not self.system_role and not self.messages:
            text = f'{self.system}\n\n{text}'
        self.inflight_prompt = text
        try:
            try:
                got = await self.exchange(text, seconds)
            except NoReply as error:
                if error.delivered:
                    self.delivered()
                raise
            self.delivered()
            self.messages.append({'role': 'assistant', 'content': got.text})
            return got
        finally:
            self.inflight_prompt = None

    def delivered(self) -> None:
        """Keep a prompt once, at its transport's receipt, before waiting for the reply."""
        if self.inflight_prompt is None:
            return
        self.messages.append({'role': 'user', 'content': self.inflight_prompt})
        self.inflight_prompt = None
        if self.on_delivered is not None:
            self.on_delivered()

    def settled(self, original: str, kept: str) -> None:
        """Retain what entered, or remove the rejected reply. Its reason belongs in the next turn prompt only."""
        last = self.messages[-1] if self.messages else {}
        if kept != original and last.get('role') == 'assistant' and last.get('content') == original:
            if kept:
                self.messages[-1] = {**last, 'content': kept}
            else:
                self.messages.pop()

    async def report(self, record: str, seconds: float) -> str:
        """The report, written by this seat from the whole record."""
        return (await self.exchange(record, seconds)).text

    async def compress(self, topic: str, seconds: float) -> bool:
        """Compress this conversation for the selected next topic when its transport supports it."""
        return False

    def busy(self) -> bool:
        """Whether native work must finish before the scheduler gives this seat another request."""
        return False

    async def wait_ready(self) -> None:
        """Wait for native readiness without starting or cancelling work."""

    async def probe(self, kind: str) -> None:
        """A cheap check, after failures of `kind`, that the seat can answer again; NoReply when it cannot yet. By
        default, that what the seat holds for the table can be made: its next turn is then the real test."""
        await self.open()

    async def rebuild(self) -> None:
        """The seat's conversation started again, empty, so its next turn is sent as a first turn."""
        self.messages = []

    async def close(self) -> None:
        """Let go of what the seat holds."""

    def columns(self) -> dict[str, Any]:
        """What the runner keeps in the seat's row after each turn."""
        return {'messages': self.messages, 'session': self.session, 'reported': self.reported, 'extra': self.extra}
