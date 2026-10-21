"""The runner of a table: one detached process per table, started when the table opens, so a table outlives the MCP
client that opened it. It opens every seat, gives each its turn in a fixed round-robin order through the one seat
interface whatever its kind,
skipping a seat that has left, has Jev judge each submission, enters the chair's comments at the gaps, ends the table
at its limits, and when it ends has the reporter seat write the report and writes the export beside it. What goes
wrong, credits run out, a hold, a seat lost, the runner stopped, it tells the chair as an operational event
(`store.event`), never as a submission, so no seat sees it and Jev never judges it.

Everything the runner knows is in the store, so a runner that stops, and the one started in its place by `continue`,
`comment` or `end`, picks up where the table is: the next seat, a submission Jev did not judge yet. It says it is alive
by its beat every few seconds; one silent for half a minute has stopped. A runner owns its table by the token it
claims, and every write it makes is fenced on that token (`store.claim`), so once another runner has taken the table
this one stops. A server starting gives a runner again to every table left running whose runner has stopped (`sweep`).
On SIGTERM the runner closes every seat, the agent processes' whole groups with them, and stops.

OpenRouter out of credits, HTTP 402, never ends a table. A seat refused is only that seat out: it is unavailable and
probed, free of charge, until credits are back (`health`). Jev, the synthesizer or the host refused holds the table,
says why and tells its chair, and its runner asks OpenRouter every minute, free of charge, whether credits are back,
and goes on by itself once they are.

Each seat is `active`, `degraded` or `unavailable` (`health`), from its failures of one kind in a row; an unavailable
seat's turns are skipped until its probe passes, or the chair reseats it. A reply taken and paid for is judged before
anything else happens to its seat, even when the seat has gone since, and no chair comment is entered while it waits,
so a comment never takes its number. A seat may PASS: the pass is recorded and never judged. A seat that repeats a
submission is told so plainly, and after every REPEATS repeats on a topic its conversation is started again.

When a table ends its report is written in a fresh request holding only the record: by the reporter seat, else by
each other seat that can, else by the `report_model` through OpenRouter; and always, beside it, the mechanical report
from the record (`export.mechanical`), which is the report when no model wrote one, so a report is never null.

A Roundtable 2 table, one with topics, runs the same turns on its open topic, then, once the topic's discussion is
over, its stages (`stages`): the synthesis and the host's summary each in a fresh request, the ranking and the two
explanations from every seat in its own conversation, one seat at a time. Each stage's answer is stored as it comes,
so a runner started again goes on from the seat or the stage that has not answered yet. After the last seat of each
round of a topic, Jev judges whether the topic has collected enough (`round_over`), and the topic goes to synthesis
on the first of its triggers to fire, recorded with it. A seat's conversation is bounded by its topic: begun again
when the seat first comes to a new topic, after its system message.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import secrets
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, cast

from . import config, export, harness, health, judge, openrouter, outside, peers, render, stages, store
from . import seats as seating
from .names import base as named_base
from .prompts import said
from .render import LIMIT
from .seat import Gone, Interrupted, NoReply, Reply, Seat

# Every kind of seat, each behind the one seat interface, `seat.Seat`.
KINDS: dict[str, type[Seat]] = {'acp': harness.AcpSeat, 'openrouter': openrouter.ModelSeat,
                                'agent': outside.AgentSeat, 'a2a': peers.PeerSeat}
USE = ('model', 'prompt_tokens', 'cached_tokens', 'cache_write_tokens', 'completion_tokens', 'reasoning_tokens',
       'finish_reason', 'cost')  # what a turn used, as recorded
COUNTED = ('prompt_tokens', 'cached_tokens', 'cache_write_tokens', 'completion_tokens', 'reasoning_tokens',
           'cost')  # what two calls' use adds up

log = logging.getLogger(__name__)

SETTLED = 2  # the rounds running Jev must find a topic covered with nothing new for it to go to synthesis
POLL = 0.25  # seconds between looks at the table while it is held
BEAT = 5.0
STALE = 30.0
REPORT_WAIT = 900  # seconds the reporter has to write the report
PROBE = 60.0  # seconds between asking OpenRouter whether credits are back, while a table is held for want of them
REPEATS = 3  # after this many repeats on a topic, and each this many more, a seat's conversation is started again


def dollars(amount: float) -> str:
    """US dollars as a person reads them: cents, or four places below a cent."""
    return f'{amount:.2f}' if amount >= 0.01 or amount == 0 else f'{amount:.4f}'


def named(error: BaseException) -> str:
    """An error as a reason names it: its kind and what it says."""
    return f'{type(error).__name__}: {error}'


def added(first: dict[str, Any], then: dict[str, Any]) -> dict[str, Any]:
    """What two calls of one answer used together, the model the later one names and why it stopped."""
    both = {key: (first.get(key) or 0) + (then.get(key) or 0) for key in COUNTED
            if first.get(key) is not None or then.get(key) is not None}
    return {**both, **{key: then.get(key) or first.get(key) for key in ('model', 'finish_reason')
                       if then.get(key) or first.get(key)}}


def alive(row: dict[str, Any]) -> bool:
    return bool(row.get('runner')) and time.time() - float(row.get('beat') or 0) < STALE


def spawn(number: int) -> int | None:
    """Start the table's runner detached, unless one runs; its pid, or None when one was running."""
    found = store.discussion(number)
    if alive(found):
        return None
    logs = config.home() / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    options: dict[str, Any] = ({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}  # type: ignore[attr-defined]
                               if os.name == 'nt' else {'start_new_session': True})
    with (logs / f'table-{number}.log').open('ab') as written:
        child = subprocess.Popen([sys.executable, '-m', __package__ or 'roundtable', 'run', str(number)],
                                 cwd=found['folder'],
                                 stdin=subprocess.DEVNULL, stdout=written, stderr=written, **options)
    return child.pid


def sweep() -> list[int]:
    """Every table left running, or held for want of credits, whose runner has stopped, given a runner again, as a
    server starts; the numbers of those started."""
    return [number for number in store.stale(STALE) if spawn(number) is not None]


class Table:
    """One table's runner."""

    def __init__(self, number: int) -> None:
        self.number = number
        self.token = secrets.token_hex(8)
        self.seated: dict[int, Seat] = {}
        self.stopped = False  # SIGTERM asked this runner to stop, or another runner took the table
        self.asked_credits = 0.0  # when OpenRouter was last asked whether credits are back, by the monotonic clock
        self.retired: list[Seat] = []  # seats the chair reseated, closed with the rest

    def row(self) -> dict[str, Any]:
        return store.discussion(self.number)

    def change(self, **changes: Any) -> dict[str, Any]:
        """The table's row changed; a hold the runner makes is told to the chair with its reason."""
        found = store.change(self.number, **changes)
        if changes.get('state') == 'held' and changes.get('reason'):
            store.event(self.number, 'held', str(changes['reason']))
        return found

    def pay(self, cost: float) -> None:
        store.spend(self.number, cost)

    def ending(self, reason: str) -> None:
        self.change(state='ending', reason=reason)

    def tell(self, kind: str, text: str) -> None:
        """An operational event the chair sees, never through Jev, where the store keeps them."""
        store.event(self.number, kind, text)

    def unpaid(self, error: BaseException) -> None:
        """OpenRouter out of credits, HTTP 402: the table holds with the reason and its chair is told; the runner
        probes and goes on once credits are back. A table never ends on 402."""
        reason = said('held_credits', error=error)
        store.change(self.number, state='held', reason=reason, unpaid=True)  # fenced; told once, as credits
        self.asked_credits = time.monotonic()
        self.tell('credits', reason)

    async def probe(self) -> None:
        """For a table held for want of credits, OpenRouter asked at most once a minute whether they are back; when
        they are, the table runs again from the call that was refused, unless its chair has moved it since."""
        if time.monotonic() - self.asked_credits < PROBE:
            return
        self.asked_credits = time.monotonic()
        try:
            await asyncio.to_thread(openrouter.credited)
        except openrouter.Silent as error:
            log.info('Table %s: still held for want of credits: %s', self.number, error)
            return
        if store.resume_unpaid(self.number):
            log.info('Table %s: OpenRouter has credits again; the table goes on', self.number)
            self.tell('resumed', said('resumed_credits'))

    def stop(self, main: asyncio.Task[Any]) -> None:
        """This runner stopped: its loop cancelled, so its seats are closed and the table let go."""
        self.stopped = True
        main.cancel()

    def failing(self, row: dict[str, Any], error: NoReply) -> None:
        """A seat's failure counted by its kind, on its row as it is now; when its availability changes, the chair is
        told."""
        reason = error.reason()
        row = store.seats(self.number)[int(row['position'])]
        changes, event = health.failed(row, error.kind, reason)
        store.seat_change(self.number, int(row['position']), **changes,
                          **({'gone': reason} if isinstance(error, Gone) else {}))
        if event is not None:
            store.event(self.number, event, health.told(event, row, changes), seat=row['id'])

    def answering(self, row: dict[str, Any]) -> None:
        """A seat answered its turn: active again, its failures forgotten."""
        changes = health.answered(store.seats(self.number)[int(row['position'])])
        if changes:
            store.seat_change(self.number, int(row['position']), **changes)

    async def probed(self, row: dict[str, Any]) -> bool:
        """Whether an unavailable seat is asked on this turn: only once its probe is due and passes, which the chair is
        told; a probe that fails doubles its wait."""
        if not health.due(row):
            return False
        seat = self.seat(row)
        try:
            await seat.probe(str(row['failing'] or 'failed'))
        except NoReply as error:
            self.failing(row, error)
            return False
        changes = health.probed(row)
        store.seat_change(self.number, int(row['position']), **changes)
        store.event(self.number, 'seat_restored', health.told('seat_restored', row, changes), seat=row['id'])
        return True

    # ------------------------------------------------------------------------------------------- the loop

    async def run(self) -> dict[str, Any]:
        found = self.row()
        if not store.claim(self.number, self.token, STALE):
            return {'discussion': self.number, 'state': found['state'], 'runner': 'already running'}
        main = cast(asyncio.Task[Any], asyncio.current_task())
        with contextlib.suppress(NotImplementedError, AttributeError):  # SIGTERM closes the seats, then the runner stops
            asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, self.stop, main)
        beating = asyncio.ensure_future(self.beat(main))
        try:
            found = self.row()
            if found['state'] in ('running', 'held'):
                await self.seat_all()
            while True:
                found = self.row()
                given: Any = found['unjudged']
                waiting = cast(dict[str, Any], given).get('position') if isinstance(given, dict) else None
                if waiting is None or found['state'] not in ('running', 'held'):  # a held reply keeps its number
                    self.enter_comments()
                if found['state'] == 'ended':
                    return self.summary()
                if found['state'] == 'ending':
                    try:
                        await self.finish()
                    except Exception as error:  # the table stays ending and says why; end asks again
                        log.exception('Table %s: the report and export were not finished', self.number)
                        self.change(state='ending', report_error=said('report_failed', error=named(error)))
                    return self.summary()
                if found['state'] == 'held':
                    if found['unpaid']:
                        await self.probe()
                    await asyncio.sleep(POLL)
                    continue
                seated = store.seats(self.number)
                if waiting is None and not any(health.usable(seat) for seat in seated):
                    if not any(health.returns(seat) for seat in seated):
                        self.ending(said('ended_empty'))
                        continue
                    if not any([await self.probed(seat) for seat in seated if health.due(seat)]):
                        await asyncio.sleep(POLL)  # every seat waits for its probe; the table stays where it is
                    continue
                spent, most = float(found['spent'] or 0), float(found['spend'])
                if spent > 0 and spent >= most:
                    self.ending(said('ended_spend', spend=dollars(most), spent=dollars(spent)))
                    continue
                if found['stage'] and found['stage'] != 'discussion':
                    await self.stage(found)
                    continue
                if found['stage'] and found['advance_asked'] and waiting is None and \
                        int(found['round']) > self.fewest(found):  # a held reply is judged first
                    self.discussed(found, 'chair')
                    continue
                if found['stage'] and int(found['position']) >= len(seated):  # a topic's round is over
                    await self.round_over(found)
                    continue
                row = seated[int(found['position'])]
                if row['position'] != waiting and (row['gone'] or (not health.usable(row) and
                                                                   not await self.probed(row))):
                    self.advance()  # a held reply is judged though its seat has gone; an unavailable seat waits
                    continue
                if await self.turn(found, row):
                    self.advance()
        except store.Lost:  # another runner took the table: this one writes nothing more and stops
            log.warning('Table %s: another runner took the table; this one stops', self.number)
            self.tell('runner_stopped', said('event_runner_lost'))
            return {'discussion': self.number, 'runner': 'lost'}
        except asyncio.CancelledError:
            if not self.stopped:
                raise
            main.uncancel()
            log.info('Table %s: the runner was stopped; its seats are closed', self.number)
            self.tell('runner_stopped', said('event_runner_stopped', state=self.row()['state']))
            return {'discussion': self.number, 'runner': 'stopped'}
        except Exception as error:  # any other failure holds the table and names it
            log.exception('Table %s: the runner stopped on an error', self.number)
            with contextlib.suppress(store.Lost):
                self.change(state='held', reason=said('held_error', error=named(error)))
                return self.summary()
            return {'discussion': self.number, 'runner': 'lost'}
        finally:
            beating.cancel()
            await self.unseat()
            with contextlib.suppress(store.Missing):
                store.release(self.number, self.token)

    async def beat(self, main: asyncio.Task[Any]) -> None:
        while True:
            await asyncio.sleep(BEAT)
            try:
                self.change(beat=time.time())
            except store.Lost:  # another runner took the table: this one stops
                log.warning('Table %s: another runner took the table; this one stops', self.number)
                self.stop(main)
                return
            except Exception as error:  # noqa: BLE001  a missed beat is logged, the table goes on
                log.warning('Table %s: the beat was not kept: %s', self.number, error)

    def summary(self) -> dict[str, Any]:
        found = self.row()
        return {'discussion': self.number, 'state': found['state'], 'reason': found['reason'],
                'report': found['report'], 'export': found['export']}

    def advance(self) -> None:
        """The next seat; after the last, the next round, or, once the discussion is over, the end; for a table with
        topics, past the last seat, where Jev judges the round next (`round_over`)."""
        found = self.row()
        position = int(found['position']) + 1
        if position < len(store.seats(self.number)) or found['stage']:
            self.change(position=position)
            return
        why = self.enough(found)
        if why is None:
            self.change(round=int(found['round']) + 1, position=0, round_kept=0)
        elif why == 'round':
            self.change(state='ending', reason=said('ended_round'), position=0)
        else:
            self.change(state='ending', reason=said('ended_rounds', rounds=found['rounds']), position=0)

    def enough(self, found: dict[str, Any]) -> str | None:
        """Why a table without topics' discussion is over after a full round: `round` when the round kept nothing,
        `rounds` when it was the last; None while it goes on."""
        if int(found['round_kept']) == 0:
            return 'round'
        if int(found['round']) >= int(found['rounds']):
            return 'rounds'
        return None

    def fewest(self, found: dict[str, Any]) -> int:
        """The fewest rounds a topic runs before anything but its round cap ends its discussion."""
        return min(int(config.value('min_rounds')), int(found['rounds']))

    def limit(self, found: dict[str, Any], given: dict[str, Any]) -> str | None:
        """Why a topic's discussion is over after a round without asking Jev: `rounds` at its round cap; after its
        fewest rounds, `chair` when the chair asked to advance it, `round` when the round kept nothing and `budget`
        when Jev's state `given` for it has reached the topic's budget; None while it goes on."""
        at = int(found['round'])
        if at >= int(found['rounds']):
            return 'rounds'
        if at < self.fewest(found):
            return None
        if found['advance_asked']:
            return 'chair'
        if int(found['round_kept']) == 0:
            return 'round'
        if judge.tokens(given) >= int(config.value('topic_tokens')):
            return 'budget'
        return None

    async def round_over(self, found: dict[str, Any]) -> None:
        """A topic's round over: Jev is asked `round_added` and `covered` on the topic's state after every full round,
        in a request of its own, and its judgment is written with the decision it causes. The topic goes to synthesis
        at its round cap, or after its fewest rounds at the chair's advance, on a round that kept nothing, at its
        budget, or once Jev finds it `covered` with nothing new (`round_added` below its bar) for SETTLED rounds
        running (`sufficient`); else the next round. The table holds when Jev gives none, never ending for want of
        credits, and continue asks again."""
        at = int(found['round'])
        entered = [one for one in store.submissions(self.number)
                   if one['topic'] == found['topic'] and render.entered(one)]
        given = judge.round_state(self.topic(found), entered, at)
        captured = render.captured(found)
        criteria = captured.get('sufficiency') or judge.questions(store.ENOUGH)
        floors = cast(dict[str, float], captured.get('sufficiency_floors') or (
            {'round_added': float(captured['keep']), 'covered': float(captured['keep'])} if captured else
            {'round_added': config.floor('keep_round_added'), 'covered': config.floor('keep_covered')}))
        asked = await asyncio.to_thread(judge.ask, given, criteria, model=captured.get('jev_model'))
        where = {'topic': found['topic'], 'round': at}
        if asked.nouls is None:
            self.unjudged(asked, asked.row('sufficiency', floors, None, **where))
            return
        settled = asked.nouls['covered'] >= floors['covered'] and asked.nouls['round_added'] < floors['round_added']
        judged = asked.row('sufficiency', floors, 'settled' if settled else 'continue', **where)
        why = self.limit(found, given)
        if why is None and at >= self.fewest(found):
            earlier = {int(one['round']): one['decision'] for one in store.judgments(self.number, int(found['topic']))
                       if one['kind'] == 'sufficiency' and one['decision']}
            running = 0
            while settled and running < SETTLED and (running == 0 or earlier.get(at - running) == 'settled'):
                running += 1
            why = 'sufficient' if running >= SETTLED else None
        if why is None:
            store.decide(self.number, judged, {'round': at + 1, 'position': 0, 'round_kept': 0})
        else:
            self.discussed(found, why, judged)

    def unjudged(self, asked: judge.Asked, judged: dict[str, Any]) -> None:
        """Jev gave no judgment: the table holds and says why, in one transaction with the judgment that failed; when
        OpenRouter is out of credits the chair is told, and a probe that finds credits again resumes it."""
        if asked.unpaid:
            reason = said('held_credits', error=asked.error)
            store.decide(self.number, judged, {'state': 'held', 'reason': reason, 'unpaid': True})
            self.asked_credits = time.monotonic()
            self.tell('credits', reason)
            return
        reason = said('held_jev', error=asked.error)
        store.decide(self.number, judged, {'state': 'held', 'reason': reason})
        self.tell('held', reason)

    def discussed(self, found: dict[str, Any], why: str, judged: dict[str, Any] | None = None) -> None:
        """The open topic's discussion over, and why, `sufficient`, `round`, `budget`, `rounds` or `chair`, recorded
        with the topic and with the judgment that decided it; its synthesis next."""
        store.decide(self.number, judged, {'stage': 'synthesis', 'position': 0, 'advance_asked': False},
                     {'discussed': store.stamp(), 'advanced_by': why,
                      'why': said(f'why_{why}', rounds=found['rounds'], settled=SETTLED,
                                  tokens=config.value('topic_tokens'))})

    def enter_comments(self) -> None:
        """The chair's comments waiting, entered inline in order, unjudged."""
        found = self.row()
        for comment in store.take_comments(self.number):
            store.record(self.number, {'round': found['round'], 'position': None, 'kind': 'chair',
                                       'seat': 'chair', 'name': None, 'text': comment['text'],
                                       'topic': found['topic'] if found['stage'] else None})

    # ------------------------------------------------------------------------------------------- the seats

    def seat(self, row: dict[str, Any]) -> Seat:
        """The seat at a position, made once for the life of this runner, whatever its kind, with its system
        message."""
        held = self.seated.get(int(row['position']))
        if held is not None and held.row.get('reseated') != row.get('reseated'):  # the chair reseated it: afresh
            self.retired.append(held)
            held = None
        if held is None:
            found = self.row()
            held = KINDS[str(row['kind'])](found, row, self.pay)
            held.system = render.system(found, [str(one['name']) for one in store.seats(self.number)],
                                        str(row['name']))
            self.seated[int(row['position'])] = held
        return held

    async def topical(self, found: dict[str, Any], seat: Seat) -> None:
        """The seat's context bounded by the open topic: begun again once, when the seat first comes to a topic its
        context does not hold, so a topic's turns never carry an earlier topic's history."""
        if not found['stage'] or seat.extra.get('topic') == found['topic']:
            return
        if seat.messages:
            await seat.rebuild()
        seat.extra['topic'] = found['topic']
        self.keep(seat, None)

    def settle(self, row: dict[str, Any], original: str, recorded: dict[str, Any]) -> None:
        """The seat's judged reply kept in its conversation as what entered of it, or as one line saying it was
        vetoed, never word for word when it was vetoed or truncated."""
        seat = self.seat(row)
        seat.settled(original, render.own(recorded))
        self.keep(seat, None)

    def keep(self, seat: Seat, seen: int | None, **more: Any) -> None:
        """What the seat holds after its turn, kept in its row; `seen` the last turn it was given, when it was."""
        store.seat_change(self.number, seat.position, **seat.columns(), **({'seen': seen} if seen is not None else {}),
                          **more)

    async def seat_all(self) -> None:
        """Every seat that holds something for the table, an ACP session or an A2A client, opened at once so each is
        ready by its first turn. One that cannot open now is tried again on its turn; an ACP seat whose session cannot
        be taken up again has left the table."""
        async def one(row: dict[str, Any]) -> None:
            seat = self.seat(row)
            try:
                await seat.open()
            except NoReply as error:
                if isinstance(error, Gone) and row['session']:
                    self.failing(row, error)
                else:
                    log.warning('Table %s: seat %s did not open: %s', self.number, seat.id, error)
                return
            self.keep(seat, None)
        await asyncio.gather(*(one(row) for row in store.seats(self.number) if not row['gone']))

    async def unseat(self) -> None:
        for seat in [*self.seated.values(), *self.retired]:
            await seat.close()
        self.seated.clear()
        self.retired.clear()

    # ------------------------------------------------------------------------------------------- a turn

    async def turn(self, found: dict[str, Any], row: dict[str, Any]) -> bool:
        """The turn of the seat whose turn it is, whatever its kind; False when the table holds or ends before it is
        recorded."""
        given: Any = found.get('unjudged')
        unjudged = cast(dict[str, Any], given) if isinstance(given, dict) else {}
        if unjudged and unjudged.get('position') == row['position']:
            original = str(unjudged.get('original') or unjudged['text'])
            use = cast(dict[str, Any], unjudged.get('use') or {})
        else:
            seat = self.seat(row)
            since = store.submissions(self.number, int(row['seen']))
            if found['stage']:
                await self.topical(found, seat)
                view = self.topic_view(found, row, seat, since)
            else:
                # its own kept turns are in its own conversation already, unless that was started again; its vetoed
                # ones it sees as their short lines
                shown = [one for one in since
                         if not (seat.messages and one['position'] == row['position'] and render.entered(one))]
                view = render.seat_view(shown, not seat.messages, links=seat.kind == 'agent')
            mine = [one for one in since if one['position'] == row['position']]
            if not seat.messages and mine and mine[-1].get('repeat_of') is not None:  # started again after repeats
                view = render.tidy(said('repeat_rebuilt', count=REPEATS) + '\n\n' + view)
            latest = max([int(one['number']) for one in since], default=int(row['seen']))
            try:
                reply = await seat.reply(view, float(config.value('agent_wait')))
            except openrouter.Unpaid as error:  # out of credits: only this seat is out, probed until they are back
                failure = NoReply(str(error), kind='credits')
                self.keep(seat, None)
                store.record(self.number, self.entry(found, row, '', kind='none', reason=failure.reason()))
                self.failing(row, failure)
                return True
            except Interrupted:
                return False
            except NoReply as error:
                self.keep(seat, latest if error.delivered else None)
                store.record(self.number, self.entry(found, row, '', kind='none', reason=error.reason()))
                self.failing(row, error)
                return True
            self.keep(seat, latest)
            self.answering(row)
            original, use = reply.text, reply.use
            if render.passed(original):  # a pass is recorded as it came and never judged
                store.record(self.number, self.entry(found, row, original.strip()[:LIMIT], kind='pass',
                                                     **{key: value for key, value in use.items() if key in USE}))
                return True
        # a T### label the seat wrote is taken off, then a turn longer than the limit is cut to it: the cut text is
        # judged and enters; the record keeps the original as the seat gave it
        stripped, label = judge.unlabeled(original)
        text = stripped[:LIMIT]
        kept = {'original': original if original != text else None, 'truncated': len(stripped) > LIMIT,
                'label': label}
        use = {key: value for key, value in use.items() if key in USE}
        # kept before anything that can fail, so a reply taken and paid for is never lost: continue judges it
        self.change(unjudged={'position': row['position'], 'text': text, **kept, 'use': use})
        return await self.verdict(found, row, self.entry(found, row, text, **use, **kept))

    async def verdict(self, found: dict[str, Any], row: dict[str, Any], entry: dict[str, Any]) -> bool:
        """A seat's submission judged and recorded in one transaction with its judgment: a repeat of any earlier
        submission on the topic, or at a table without topics in the discussion, kept or vetoed, is vetoed with no
        call; any other is judged by Jev against what entered, at the bars the table opened with. False when the
        table holds or ends before it is recorded."""
        staged = bool(found['stage'])
        text = str(entry['text'])
        rows = [one for one in store.submissions(self.number) if not staged or one['topic'] == found['topic']]
        where = {'topic': found['topic'] if staged else None, 'round': found['round'], 'position': row['position']}
        earlier = judge.repeat(text, rows)
        if earlier is not None:
            recorded = store.record(self.number, {**entry, 'accepted': False, 'repeat_of': earlier['number']},
                                    judged=True, judgment=judge.dedup(earlier, **where))
            self.settle(row, str(entry.get('original') or text), recorded)
            await self.repeating(found, row)
            return True
        captured = render.captured(found)
        entered = [one for one in rows if render.entered(one)]
        if staged:  # a topic is judged against itself and what entered on it, its seats unnamed
            given = judge.topic_state(self.topic(found), entered, {'position': row['position'], 'text': text})
            criteria = captured['criteria'] if captured.get('floors') else judge.questions(store.VETO)
            floors = render.floors(captured) if captured.get('floors') else (  # a snapshot from before own bars
                {name: float(captured['keep']) for name in store.VETO} if captured else
                {'new_context': config.floor('keep_new'), 'on_topic': config.floor('keep_on_topic')})
        else:
            given = judge.state(str(found['opening']), entered, row['name'], text)
            criteria = captured.get('criteria') or judge.questions()
            floors = render.floors(captured) if captured else {name: config.keep() for name in store.NOULS}
        asked = await asyncio.to_thread(judge.ask, given, criteria, model=captured.get('jev_model'))
        if asked.nouls is None:
            self.unjudged(asked, asked.row('veto', floors, None, **where))
            return False
        accepted = judge.passed(asked.nouls, floors)
        recorded = store.record(self.number, {**entry, 'accepted': accepted, 'jev_cost': round(asked.cost, 6),
                                              **asked.nouls}, judged=True,
                                judgment=asked.row('veto', floors, 'keep' if accepted else 'veto', **where))
        self.settle(row, str(entry.get('original') or text), recorded)
        return True

    async def repeating(self, found: dict[str, Any], row: dict[str, Any]) -> None:
        """After a seat's every REPEATS'th repeat on the topic, its conversation started again: its next turn is a
        first turn, holding everything said so far and why it was started again. A seat no longer asked is left."""
        made = sum(1 for one in store.submissions(self.number)
                   if one['position'] == row['position'] and one.get('repeat_of') is not None
                   and (not found['stage'] or one['topic'] == found['topic']))
        held = store.seats(self.number)[int(row['position'])]
        if made % REPEATS or not health.usable(held):
            return
        seat = self.seat(held)
        await seat.rebuild()
        self.keep(seat, 0)

    def entry(self, found: dict[str, Any], row: dict[str, Any], text: str, **given: Any) -> dict[str, Any]:
        return {'round': found['round'], 'position': row['position'], 'seat': row['id'], 'name': row['name'],
                'kind': 'seat', 'text': text, 'topic': found['topic'] if found['stage'] else None, **given}

    def topic_view(self, found: dict[str, Any], row: dict[str, Any], seat: Seat, since: list[dict[str, Any]]) -> str:
        """A Roundtable 2 seat's discussion turn: the status of its previous contribution, the other seats'
        contributions on the open topic since its last turn, and the topic when its context does not hold it yet: on
        its first turn of a topic, or in a context begun again, after the digest of the topics before it."""
        own = [one for one in since if one['position'] == row['position']]
        others = [one for one in since if one['topic'] == found['topic']  # its own too, once it was started again
                  and (one['position'] != row['position'] or (not seat.messages and render.entered(one)))]
        mine = [one for one in store.submissions(self.number) if one['position'] == row['position']]
        fresh = not seat.messages
        spoken = not fresh and any(one['topic'] == found['topic'] for one in mine)
        digest = '' if spoken else render.digest(self.number, int(found['topic']))
        return render.topic_view(str(self.topic(found)['text']), own[-1] if own else None, others,
                                 fresh and not mine, spoken, digest)

    # ------------------------------------------------------------------------------------------- the stages

    def topic(self, found: dict[str, Any]) -> dict[str, Any]:
        return store.topics(self.number)[int(found['topic'])]

    def staged(self, found: dict[str, Any], stage: str) -> list[dict[str, Any]]:
        return [one for one in store.staged(self.number, int(found['topic'])) if one['stage'] == stage]

    def ideas(self, found: dict[str, Any]) -> list[dict[str, Any]]:
        """The open topic's ideas, as its synthesis numbered them."""
        none: list[dict[str, Any]] = []
        return next((cast(list[dict[str, Any]], one['ideas']) for one in reversed(self.staged(found, 'synthesis'))
                     if one['ideas']), none)

    def stage_row(self, found: dict[str, Any], stage: str, position: int, who: dict[str, Any], text: str,
                  use: dict[str, Any], **more: Any) -> None:
        store.stage_record(self.number, {'topic': int(found['topic']), 'stage': stage, 'position': position,
                                         'seat': who['id'], 'name': who['name'], 'text': text,
                                         **{key: value for key, value in use.items() if key in USE}, **more})

    async def stage(self, found: dict[str, Any]) -> None:
        """One step of the stage the open topic is at after its discussion; after the last topic, the end."""
        stage = str(found['stage'])
        if stage == 'synthesis':
            await self.synthesis(found)
        elif stage == 'host_summary':
            await self.host_summary(found)
        elif stage in stages.EACH:
            await self.each(found, stage)
        else:
            self.ending(said('ended_topics'))

    def fresh(self, found: dict[str, Any], role: str) -> Seat:
        """The synthesizer or the host as a seat of its own for one request, with nothing before it."""
        given = cast(dict[str, Any], found[role])
        row: dict[str, Any] = {**given, 'position': store.SYNTHESIZER if role == 'synthesizer' else store.HOST,
                               'messages': [], 'session': None, 'reported': None, 'extra': None}
        return KINDS[str(given['kind'])](found, row, self.pay)

    async def ask_fresh(self, found: dict[str, Any], role: str, text: str) -> Reply:
        """One answer of the synthesizer or the host, in a fresh request holding only `text`."""
        seat = self.fresh(found, role)
        seconds = max(REPORT_WAIT, float(config.value('agent_wait')))
        try:
            if isinstance(seat, openrouter.ModelSeat):  # room for a whole topic, as a report has
                return await seat.ask(text, int(config.value('report_tokens')), seconds)
            return await seat.exchange(text, seconds)
        finally:
            await seat.close()

    async def synthesis(self, found: dict[str, Any]) -> None:
        """The synthesizer's named ideas, from the topic and what entered its discussion; the ranking next. The table
        holds when it gives none, and continue asks again."""
        if self.ideas(found):
            self.change(stage='ranking', position=0)
            return
        topic = self.topic(found)
        rows = [one for one in store.submissions(self.number) if one['topic'] == found['topic'] and render.entered(one)]
        text = said('synthesis', topic=topic['text'],
                    turns='\n\n'.join(render.entry(one) for one in rows) or said('no_contributions'))
        try:
            reply = await self.ask_fresh(found, 'synthesizer', text)
        except openrouter.Unpaid as error:
            self.unpaid(error)
            return
        except Interrupted:
            return
        except NoReply as error:
            self.change(state='held', reason=said('held_synthesis', error=error))
            return
        listed = stages.ideas(reply.text)
        self.stage_row(found, 'synthesis', store.SYNTHESIZER, cast(dict[str, Any], found['synthesizer']), reply.text,
                       reply.use, ideas=listed or None, error=None if listed else said('synthesis_unread'))
        if not listed:
            self.change(state='held', reason=said('held_synthesis', error=said('synthesis_unread')))
            return
        self.change(stage='ranking', position=0)

    async def each(self, found: dict[str, Any], stage: str) -> None:
        """The next seat's answer to a stage every seat answers in its own conversation, in speaking order; once
        every seat still at the table has answered, the next stage."""
        done = {int(one['position']) for one in self.staged(found, stage)}
        row = next((one for one in store.seats(self.number) if health.usable(one) and int(one['position']) not in done),
                   None)
        if row is None:
            self.change(stage=stages.following(stage), position=0)
            return
        if int(found['position']) != int(row['position']):
            self.change(position=row['position'])
        listed = self.ideas(found)
        ids = [str(one['id']) for one in listed]
        if stage == 'ranking':
            text = said('ranking', ideas=render.idea_lines(listed), example=', '.join(ids))
        else:
            mine = next((one for one in self.staged(found, 'ranking') if one['position'] == row['position']), None)
            text = said(stage, yours=stages.three(mine['ranking'] if mine else None, stage, listed))
        seat = self.seat(row)
        await self.topical(found, seat)
        if not seat.messages:  # a seat whose first turn of the topic is a stage, the chair having advanced before it
            text = render.tidy(said('stage_first', topic=self.topic(found)['text'], stage=text))
        try:
            reply, more = await self.answer(seat, stage, text, ids)
        except openrouter.Unpaid as error:  # out of credits: only this seat is out, and the stage goes on without it
            failure = NoReply(str(error), kind='credits')
            self.keep(seat, None)
            self.stage_row(found, stage, int(row['position']), row, '', {}, error=failure.reason())
            self.failing(row, failure)
            return
        except Interrupted:
            return
        except NoReply as error:
            self.keep(seat, None)
            self.stage_row(found, stage, int(row['position']), row, '', {}, error=error.reason())
            self.failing(row, error)
            return
        self.answering(row)
        limit = stages.LIMITS.get(stage)
        cut = {'original': reply.text, 'truncated': True} if limit and len(reply.text) > limit else {}
        if cut:  # its conversation keeps what entered of its answer
            seat.settled(reply.text, reply.text[:limit])
        self.keep(seat, None)
        self.stage_row(found, stage, int(row['position']), row, reply.text[:limit] if limit else reply.text,
                       reply.use, **more, **cut)

    async def answer(self, seat: Seat, stage: str, text: str, ids: list[str]) -> tuple[Reply, dict[str, Any]]:
        """A seat's answer to a stage; a ranking read, and asked for once more when it is not every id exactly once.
        One still not, or whose repair got no answer, is kept as written, unread, with what was wrong."""
        seconds = float(config.value('agent_wait'))
        reply = await seat.reply(text, seconds)
        if stage != 'ranking':
            return reply, {}
        ranking, problem = stages.ranked(reply.text, ids)
        if problem is None:
            return reply, {'ranking': ranking}
        try:
            again = await seat.reply(said('ranking_repair', problem=problem, ids=', '.join(ids)), seconds)
        except (NoReply, Interrupted):
            return reply, {'ranking': None, 'error': problem, 'repair': reply.text}
        ranking, still = stages.ranked(again.text, ids)
        return Reply(again.text, added(reply.use, again.use)), {'ranking': ranking, 'error': still,
                                                                  'repair': reply.text}

    async def host_summary(self, found: dict[str, Any]) -> None:
        """The host's summary of every seat's ranking and explanations, in a fresh request; the next topic after it.
        The table holds when the host gives none, and continue asks again."""
        if any(one['text'] for one in self.staged(found, 'host_summary')):
            self.next_topic(found)
            return
        rows = store.staged(self.number, int(found['topic']))
        text = said('host_summary', topic=self.topic(found)['text'], ideas=render.idea_lines(self.ideas(found)),
                    rankings=render.stage_lines(rows, 'ranking'), tops=render.stage_lines(rows, 'top_three'),
                    bottoms=render.stage_lines(rows, 'bottom_three'))
        try:
            reply = await self.ask_fresh(found, 'host', text)
        except openrouter.Unpaid as error:
            self.unpaid(error)
            return
        except Interrupted:
            return
        except NoReply as error:
            self.change(state='held', reason=said('held_host', error=error))
            return
        self.stage_row(found, 'host_summary', store.HOST, cast(dict[str, Any], found['host']), reply.text, reply.use)
        self.next_topic(found)

    def next_topic(self, found: dict[str, Any]) -> None:
        """The open topic closed, and the next opened at its first round; after the last, the report."""
        at = int(found['topic'])
        store.topic_change(self.number, at, closed=store.stamp())
        if at + 1 >= len(store.topics(self.number)):
            self.change(stage='report', state='ending', reason=said('ended_topics'), position=0)
            return
        store.topic_change(self.number, at + 1, opened=store.stamp())
        self.change(topic=at + 1, stage='discussion', round=1, position=0, round_kept=0, advance_asked=False)

    # ------------------------------------------------------------------------------------------- the end

    def writers(self, found: dict[str, Any]) -> list[dict[str, Any]]:
        """Who is asked for the report, in turn: the named reporter, every other seat that can write it and has not
        left, an ACP seat first, then the `report_model` through OpenRouter. Never Claude through OpenRouter."""
        seated = [one for one in store.seats(self.number) if seating.able(one)]
        chosen = [one for one in seated if one['id'] == found['reporter'] and not one['gone']]
        others = sorted((one for one in seated if one['id'] != found['reporter'] and health.usable(one)),
                        key=lambda one: one['kind'] != 'acp')
        model = str(config.value('report_model') or '').strip()
        given: dict[str, Any] = {'kind': 'openrouter', 'id': model, 'model': model, 'agent': None}
        extra = [{**given, 'name': named_base(given), 'position': store.REPORTER}] \
            if model and seating.able(given) and all(one['id'] != model for one in seated) else []
        return [*chosen, *others, *extra]

    async def report(self, found: dict[str, Any], record: str) -> str:
        """The report's text: each writer in turn asked in a fresh request holding only the record, never inside its
        long conversation, until one writes it; the chair is told when it was not the first. NoReply naming why each
        failed when none did."""
        failed: list[str] = []
        for given in self.writers(found):
            row: dict[str, Any] = {**given, 'messages': [], 'session': None, 'reported': None, 'extra': None}
            seat = KINDS[str(given['kind'])](found, row, self.pay)
            try:
                text = await seat.report(record, max(REPORT_WAIT, float(config.value('agent_wait'))))
            except Exception as error:  # noqa: BLE001  whatever stopped this writer, the next is asked
                failed.append(f'{given["name"]}: {named(error)}')
                log.warning('Table %s: %s did not write the report: %s', self.number, given['name'], named(error))
                continue
            finally:
                with contextlib.suppress(Exception):
                    await seat.close()
            if text.strip():
                if failed:
                    self.tell('report', said('event_report_by', writer=given['name'], failed='; '.join(failed)))
                return text
            failed.append(f'{given["name"]}: {said("report_empty")}')
        raise NoReply('; '.join(failed) or 'no seat can write the report')

    async def finish(self) -> None:
        """The report and the export: the mechanical report written from the record as <N>-<subject>.record.md, then
        the writers asked in turn for the report from the whole record, saved as <N>-<subject>.md; when none writes it
        the mechanical report is the report, so it is never null. A report already written is not asked for again
        when only the export failed. The record as JSON beside them either way."""
        found = self.row()
        base = config.reports() / f'{self.number}-{found["subject"]}'
        written = Path(f'{base}.record.md')
        written.write_text(export.mechanical(self.number), encoding='utf-8')
        self.change(mechanical=str(written))
        if found['report'] and found['report'] != str(written) and Path(str(found['report'])).is_file():
            report, told = str(found['report']), None
        else:
            try:
                unjudged = store.pending(self.number) if found['unjudged'] else None
                rows = [*store.submissions(self.number), *([unjudged] if unjudged else [])]
                names = [str(one['name']) for one in store.seats(self.number)]
                text = await self.report(found, render.record(found, rows, names, store.topics(self.number),
                                                              store.staged(self.number)))
            except NoReply as error:
                report, told = str(written), said('report_mechanical', error=error)
                log.warning('Table %s: %s', self.number, told)
                self.tell('report', told)
            else:
                Path(f'{base}.md').write_text(text.rstrip() + '\n', encoding='utf-8')
                report, told = f'{base}.md', None
        await self.unseat()
        self.change(state='ended', ended=store.stamp(), report=report, report_error=told)
        Path(f'{base}.json').write_text(json.dumps(export.build(self.number), indent=2, ensure_ascii=False) + '\n',
                                        encoding='utf-8')
        self.change(export=f'{base}.json')


def run(number: int) -> dict[str, Any]:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    return asyncio.run(Table(number).run())
