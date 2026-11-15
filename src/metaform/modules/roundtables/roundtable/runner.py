"""One detached runner per table, with persistent turns and fenced writes.

Two complete judged rounds with nothing accepted, voluntary unanimous PASS when judging is off, explicit chair
advancement or a configured participant budget finish discussion. Resource limits and errors hold with a reason. A held runner closes
its seats and stops. Continue explicitly starts it again without changing the table's identity or transcript.

Before context fills, every participant writes an attributed carry-forward note. One fresh editor compacts shared
history. Fresh seat contexts receive that continuation and all intact notes. Notes bypass novelty filtering.
Topic synthesis, rankings, explanations and host summaries follow discussion. Their existing stages remain intact.
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
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from metaform import events

from . import (
    budget,
    config,
    export,
    harness,
    health,
    judge,
    openrouter,
    outside,
    peers,
    render,
    stages,
    store,
    topics,
)
from . import seats as seating
from .names import base as named_base
from .prompts import said
from .seat import Gone, Interrupted, NoReply, Reply, Seat

# Every kind of seat, each behind the one seat interface, `seat.Seat`.
KINDS: dict[str, type[Seat]] = {'acp': harness.AcpSeat, 'openrouter': openrouter.ModelSeat,
                                'agent': outside.AgentSeat, 'a2a': peers.PeerSeat}
USE = ('model', 'prompt_tokens', 'cached_tokens', 'cache_write_tokens', 'completion_tokens', 'reasoning_tokens',
       'finish_reason', 'cost')  # what a turn used, as recorded
COUNTED = ('prompt_tokens', 'cached_tokens', 'cache_write_tokens', 'completion_tokens', 'reasoning_tokens',
           'cost')  # what two calls' use adds up

log = logging.getLogger(__name__)

BEAT = 5.0
STALE = 30.0
REPORT_WAIT = 900  # seconds the reporter has to write the report
# The final session phases retain private scorecards and the shared farewell.
PHASES = {'scoring': 'score', 'farewell': 'farewell'}


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


def stop_runner(number: int) -> int:
    """A hard stop: SIGTERM to every process running table `number`'s runner, `<python> -m <package> run <number>`,
    whose handler closes every seat and its agent's process group at once; how many were signalled."""
    wanted = [__package__ or 'roundtable', 'run', str(number)]
    pids: list[int] = []
    proc = Path('/proc')
    if proc.is_dir():
        for entry in proc.glob('[0-9]*'):
            try:
                words = [one.decode(errors='replace') for one in (entry / 'cmdline').read_bytes().split(b'\0') if one]
            except OSError:
                continue
            if words[-3:] == wanted and '-m' in words:
                pids.append(int(entry.name))
    else:  # no /proc, as on macOS: pgrep reads the same command lines
        found = subprocess.run(['pgrep', '-f', f'-m {wanted[0]} run {number}$'], capture_output=True, text=True,
                               check=False)
        pids = [int(one) for one in found.stdout.split()]
    count = 0
    for pid in pids:
        if pid != os.getpid():
            with contextlib.suppress(OSError):
                os.kill(pid, signal.SIGTERM)
                count += 1
    return count


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




class Table:
    """One table's runner."""

    def __init__(self, number: int) -> None:
        self.number = number
        self.token = secrets.token_hex(8)
        self.seated: dict[int, Seat] = {}
        self.stopped = False  # SIGTERM asked this runner to stop, or another runner took the table
        self.retired: list[Seat] = []  # seats the chair reseated, closed with the rest
        # A session's phases: replies in flight by seat, with the submission each saw last.
        self.working: dict[int, asyncio.Task[tuple[Reply | None, int, str | None]]] = {}
        self.work_phase: dict[int, tuple[str, int]] = {}
        self.panel_work: dict[int, asyncio.Task[bool]] = {}
        self.panel_asking: set[int] = set()
        self.judging = asyncio.Lock()
        self.control = asyncio.Event()
        self.topic_deciding: asyncio.Task[dict[str, Any]] | None = None
        self.topic_choice: tuple[int, dict[str, Any]] | None = None

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
        """A credit failure holds discussion until explicit Continue. It never counts as PASS."""
        reason = said('held_credits', error=error)
        store.change(self.number, state='held', reason=reason, unpaid=True)  # fenced; told once, as credits
        self.tell('credits', reason)

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
        self.change(budget_runner=self.token, collaboration_runner=self.token)
        main = cast(asyncio.Task[Any], asyncio.current_task())
        with contextlib.suppress(NotImplementedError, AttributeError):  # SIGTERM closes the seats, then the runner stops
            asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, self.stop, main)
        beating = asyncio.ensure_future(self.beat(main))
        loop = asyncio.get_running_loop()

        def changed(given: dict[str, Any]) -> None:
            if f'roundtables:control:{self.number}' in given.get('kinds', []):
                loop.call_soon_threadsafe(self.control.set)

        listener = events.listen('roundtables', changed)
        try:
            while True:
                try:
                    self.collect_panel()
                    found = self.row()
                    given: Any = found['unjudged']
                    waiting = cast(dict[str, Any], given).get('position') if isinstance(given, dict) else None
                    if waiting is None or found['state'] not in ('running', 'held'):  # a held reply keeps its number
                        self.enter_comments()
                        found = self.row()
                    if found['state'] == 'ended':
                        return self.summary()
                    if found['state'] == 'ending':
                        if found['reason'] != said('ended_by_chair') and self.has_busy():
                            await self.wait_busy()
                            continue
                        try:
                            await self.finish()
                        except Exception as error:  # the table stays ending and says why; end asks again
                            log.exception('Table %s: the report and export were not finished', self.number)
                            self.change(state='ending', report_error=said('report_failed', error=named(error)))
                        return self.summary()
                    if found['state'] == 'held':
                        if any(row['kind'] == 'acp' for row in store.seats(self.number)):
                            if self.has_busy():
                                await self.wait_busy()
                            else:
                                await self.wait_work([])
                            continue
                        if self.has_busy():
                            await self.wait_busy()
                            continue
                        return self.summary()
                    if await self.enforce_budget(found):
                        continue
                    if found['stage'] == 'collaboration' and render.session(found):
                        self.start_topic_selection(found)
                        continue
                    if found['advance_asked']:
                        self.archive_panel()
                        self.change(handoff=None)
                        self.discussed(found, 'chair')
                        continue
                    seated = store.seats(self.number)
                    if waiting is None and found['stage'] != 'topic_selection' and not any(
                            health.usable(seat) for seat in seated):
                        if not any(health.returns(seat) for seat in seated):
                            self.change(state='held', reason=said('held_empty'))
                            continue
                        if not any([await self.probed(seat) for seat in seated if health.due(seat)]):
                            await self.recover(store.seats(self.number))
                        continue
                    spent, most = float(found['spent'] or 0), float(found['spend'])
                    if spent >= most and self.requires_payment(found):
                        self.change(state='held', reason=said('held_spend', spend=dollars(most), spent=dollars(spent)))
                        continue
                    if found['stage'] and found['stage'] != 'discussion':
                        await self.stage(found)
                        continue
                    pending = any(cast(dict[str, Any], row.get('extra') or {}).get('panel_reply') for row in seated)
                    native_session = bool(render.session(found))
                    if native_session and found.get('handoff'):
                        self.change(handoff=None)
                        continue
                    if waiting is None and not pending and not native_session and (
                            found.get('handoff') or self.context_due(found)):
                        if self.panel_work:
                            await self.wait_work(list(self.panel_work.values()))
                        else:
                            await self.handoff(found)
                        continue
                    await self.panel(found, seated)
                except (store.Lost, asyncio.CancelledError):
                    raise
                except Exception as error:
                    log.exception('Table %s: work stopped on an error', self.number)
                    self.change(state='held', reason=said('held_error', error=named(error)))
                    if any(row['kind'] == 'acp' for row in store.seats(self.number)):
                        self.control.clear()
                        await self.wait_work([])
                        continue  # Hold retains native sessions, including work whose background state is unknown.
                    return self.summary()
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
            listener.close()
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
        """Next seat, then examine the full round without inferring anyone's vote."""
        self.change(position=int(self.row()['position']) + 1)

    async def round_over(self, found: dict[str, Any], *, busy: set[int] | None = None) -> None:
        """A completed round advances its exhaustion streak or the voluntary unjudged PASS decision."""
        store.close_round(self.number, said('why_exhausted' if render.judging(found) else 'why_passes'), busy=busy)
        if render.session(found) and self.row()['stage'] == 'synthesis':
            self.start_topic_selection(self.row())

    def unjudged(self, asked: judge.Asked, judged: dict[str, Any]) -> None:
        """Persist a failed judgment with its hold. Continue retries the saved submission."""
        if asked.unpaid:
            reason = said('held_credits', error=asked.error)
            store.decide(self.number, judged, {'state': 'held', 'reason': reason, 'unpaid': True})
            self.tell('credits', reason)
            return
        reason = said('held_jev', error=asked.error)
        store.decide(self.number, judged, {'state': 'held', 'reason': reason})
        self.tell('held', reason)

    def discussed(self, found: dict[str, Any], why: str) -> None:
        """Finish discussion by unanimous voluntary passes or explicit chair advancement."""
        if not found['stage']:
            self.ending(said(f'why_{why}'))
            return
        store.decide(self.number, None, {'stage': 'synthesis', 'position': 0, 'advance_asked': False},
                     {'discussed': store.stamp(), 'advanced_by': why, 'why': said(f'why_{why}')})
        if render.session(found):
            self.start_topic_selection(self.row())

    async def enforce_budget(self, found: dict[str, Any]) -> bool:
        """A reported participant cap ends the phase, without waiting for another busy agent's DONE or PASS."""
        if not budget.limit(found) or budget.phase(found) is None:
            return False
        current = budget.evaluate(found)
        if not current['forced']:
            return False
        if current['phase'] == 'panel':
            self.archive_panel()
            found = self.row()
            if found['state'] != 'running' or not budget.status(found)['forced']:
                return True
            reason = next(str(one['text']) for one in current['notices'] if one['percent'] == 120)
            if not found['stage']:
                self.change(handoff=None, advance_asked=False)
                self.ending(reason)
                return True
            store.decide(self.number, None, {'handoff': None, 'advance_asked': False},
                         {'discussed': store.stamp(), 'advanced_by': 'budget', 'why': reason})
            if render.session(found):
                self.start_topic_selection(self.row())
            else:
                self.change(stage='synthesis', position=0)
        else:
            self.start_topic_selection(found)
        return True

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
        """Preserve a session's conversation across topics; independent topics start their own context."""
        if not found['stage'] or seat.extra.get('topic') == found['topic']:
            return
        if render.session(found):  # a session's agents keep their conversation from one roundtable to the next
            seat.extra['topic'] = found['topic']
            self.keep(seat, None)
            return
        if seat.messages:
            await seat.rebuild()
        seat.extra['topic'] = found['topic']
        self.keep(seat, None)

    def settle(self, row: dict[str, Any], original: str, recorded: dict[str, Any]) -> None:
        """Retain accepted text without replaying a rejected reply or delivering its feedback early."""
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
        from . import permissions
        tasks: list[asyncio.Task[Any]] = [*self.working.values(), *self.panel_work.values()]
        if self.topic_deciding is not None:
            tasks.append(self.topic_deciding)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*(seat.close() for seat in [*self.seated.values(), *self.retired]),
                             return_exceptions=True)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.working.clear()
        self.work_phase.clear()
        self.panel_work.clear()
        self.panel_asking.clear()
        self.topic_deciding = None
        permissions.cancel_all(self.number)
        self.seated.clear()
        self.retired.clear()

    # ------------------------------------------------------------------------------------------- a turn

    def collect_panel(self) -> None:
        """Finish completed turn tasks before choosing the next ready seat."""
        for position, task in list(self.panel_work.items()):
            if task.done():
                self.panel_work.pop(position)
                if not task.cancelled():
                    task.result()
        found = self.row()
        current = (str(found['stage']), int(found['topic']))
        for position, task in list(self.working.items()):
            if task.done() and self.work_phase.get(position, current) != current:
                self.working.pop(position)
                self.work_phase.pop(position, None)
                if not task.cancelled():
                    task.result()

    def busy(self, row: dict[str, Any]) -> bool:
        position = int(row['position'])
        return position in self.panel_work or position in self.working or self.seat(row).busy()

    def has_busy(self) -> bool:
        return any(not task.done() for task in (*self.panel_work.values(), *self.working.values())) or any(
            self.seated[int(row['position'])].busy() for row in store.seats(self.number)
            if not row['gone'] and int(row['position']) in self.seated)

    async def wait_busy(self) -> None:
        """Wait for native readiness or completed work; cancelling these watchers never cancels native work."""
        tasks: list[asyncio.Task[Any]] = [task for task in (*self.panel_work.values(), *self.working.values())
                                         if not task.done()]
        occupied = {position for position, task in (*self.panel_work.items(), *self.working.items()) if not task.done()}
        rows = {int(row['position']): row for row in store.seats(self.number)}
        watched = {position: asyncio.create_task(seat.wait_ready()) for position, seat in self.seated.items()
                   if not rows[position]['gone'] and seat.busy() and position not in occupied}
        watchers = list(watched.values())
        try:
            if tasks or watchers:
                await self.wait_work([*tasks, *watchers])
                for position, task in watched.items():
                    if task.done() and not task.cancelled():
                        try:
                            task.result()
                        except NoReply as error:
                            self.failing(rows[position], error)
            else:
                await self.recover(store.seats(self.number))
        finally:
            for task in watchers:
                task.cancel()
            await asyncio.gather(*watchers, return_exceptions=True)

    def credit_busy(self) -> None:
        from . import allowance

        for position, seat in self.seated.items():
            allowance.busy(self.number, position, position in self.panel_asking or seat.busy())

    def archive_panel(self) -> None:
        """Retain completed old-topic replies without interrupting any native work still in flight."""
        for row in store.seats(self.number):
            seat = self.seat(row)
            pending = seat.extra.get('panel_reply')
            if isinstance(pending, dict):
                self.archive_reply(seat, row, cast(dict[str, Any], pending))
        unjudged = store.pending(self.number)
        if unjudged is not None:
            store.record(self.number, unjudged, judged=True)

    def archive_reply(self, seat: Seat, row: dict[str, Any], held: dict[str, Any]) -> None:
        found = {**self.row(), 'round': held['round'], 'topic': held['topic'], 'stage': 'discussion'}
        store.record(self.number, self.entry(found, row, str(held['original']), unjudged=True,
                                             reason='The reply arrived after its discussion closed.',
                                             **cast(dict[str, Any], held['use'])),
                     receipt=str(held['usage_id']) if held.get('usage_id') else None)
        seat.extra['panel_reply'] = None
        self.keep(seat, None)

    async def wait_work(self, tasks: list[asyncio.Task[Any]]) -> None:
        """Wait for actual completion or a chair operation, without periodically reading the table."""
        if self.control.is_set():
            self.control.clear()
            return
        changed = asyncio.create_task(self.control.wait())
        try:
            await asyncio.wait([*tasks, changed], return_when=asyncio.FIRST_COMPLETED)
            if changed.done():
                self.control.clear()
        finally:
            changed.cancel()
            await asyncio.gather(changed, return_exceptions=True)

    async def recover(self, seated: list[dict[str, Any]]) -> None:
        """An unavailable seat's actual retry deadline, interrupted immediately by chair control."""
        returning = [row for row in seated if not health.usable(row) and health.returns(row)]
        if not returning:
            self.change(state='held', reason=said('held_empty'))
            return
        deadline = min(float(row['retry_at']) for row in returning)
        retry = asyncio.create_task(asyncio.sleep(max(0.0, deadline - time.time())))
        try:
            await self.wait_work([retry])
        finally:
            retry.cancel()
            await asyncio.gather(retry, return_exceptions=True)

    async def stop_panel(self, *, record: bool = False) -> None:
        """Stop outstanding requests; explicit advancement retains completed replies without asking Jev again."""
        tasks = list(self.panel_work.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.panel_work.clear()
        if record:
            for row in store.seats(self.number):
                seat = self.seat(row)
                pending = seat.extra.get('panel_reply')
                if not isinstance(pending, dict):
                    continue
                held = cast(dict[str, Any], pending)
                original = str(held['original'])
                found = {**self.row(), 'round': held['round'], 'topic': held['topic']}
                store.record(self.number, self.entry(found, row, original, unjudged=True,
                                                     **cast(dict[str, Any], held['use'])),
                             receipt=str(held['usage_id']) if held.get('usage_id') else None)
                seat.extra['panel_reply'] = None
                self.keep(seat, None)
            unjudged = store.pending(self.number)
            if unjudged is not None:
                store.record(self.number, unjudged, judged=True)

    async def panel(self, found: dict[str, Any], seated: list[dict[str, Any]]) -> None:
        """Rotate ready seats, then after two quiet cycles ask only unfinished participants for corrections."""
        given = found.get('unjudged')
        waiting = cast(dict[str, Any], given).get('position') if isinstance(given, dict) else None
        if waiting is not None and waiting not in self.panel_work:
            row = seated[int(waiting)]
            self.panel_work[int(waiting)] = asyncio.create_task(self.turn(found, row))
            return
        rows = [one for one in store.submissions(self.number, int(found['pass_after']))
                if one['round'] == found['round'] and one['topic'] == (found['topic'] if found['stage'] else None)
                and one['kind'] not in ('chair', 'carry', 'handoff')]
        covered = {int(one['position']) for one in rows
                   if one['position'] is not None and one['kind'] in ('seat', 'pass')}
        terminal: set[int] = set()
        if render.judging(found) and int(found['quiet_rounds']) >= 2:
            history = [one for one in store.submissions(self.number)
                       if one['topic'] == (found['topic'] if found['stage'] else None)]
            boundary = max((int(one['number']) for one in history if one['accepted'] or one['kind'] == 'chair'),
                           default=0)
            outcomes: dict[int, str] = {}
            for one in history:
                if one['number'] <= boundary or one['position'] is None or one.get('unjudged'):
                    continue
                if one['kind'] == 'pass' or one['kind'] == 'seat' and not one['accepted']:
                    position = int(one['position'])
                    outcomes[position] = (outcomes.get(position, '') + ('P' if one['kind'] == 'pass' else 'V'))[-2:]
            terminal = {position for position, pair in outcomes.items() if pair in ('PP', 'VV', 'VP')}
            covered.update(terminal)
        pending = [row for row in seated if cast(dict[str, Any], row.get('extra') or {}).get('panel_reply')]
        busy = {int(row['position']) for row in seated if int(row['position']) in self.panel_asking or
                int(row['position']) in self.working or self.seat(row).busy() or not health.usable(row)}
        eligible = [row for row in seated if not row['gone'] and int(row['position']) not in busy]
        judging = set(self.panel_work) - busy
        closing = {int(row['position']) for row in seated
                   if not row['gone'] and int(row['position']) not in busy and
                   budget.needs_closing(found, int(row['position']))}
        if not judging and not pending and not closing and eligible and all(
                int(row['position']) in covered for row in eligible):
            await self.round_over(found, busy=busy)
            return
        at = int(found['position']) % max(1, len(seated))
        ordered = sorted(seated, key=lambda row: (int(row['position']) - at) % max(1, len(seated)))
        for row in ordered:
            position = int(row['position'])
            if self.busy(row) or row['gone']:
                continue
            if position in terminal and position not in closing and not any(
                    int(one['position']) == position for one in pending):
                continue
            if not health.usable(row) and not await self.probed(row):
                continue
            mine = [one for one in rows if one['position'] == position]
            if position in covered and judging:
                continue  # A reply waiting for Jev alone does not extend the speaking round.
            if position not in closing and mine and mine[-1]['kind'] == 'pass' and not any(
                    one['position'] != position and one['number'] > mine[-1]['number'] and one['kind'] == 'seat'
                    for one in rows):
                continue
            self.panel_work[position] = asyncio.create_task(self.turn(found, row))
            self.change(position=(position + 1) % max(1, len(seated)))
            return
        if self.has_busy():
            await self.wait_busy()
            return
        # A healthy participant's PASS cannot stand in for an unavailable participant's missing reply.
        await self.recover(store.seats(self.number))

    def requires_payment(self, found: dict[str, Any]) -> bool:
        if found['stage'] == 'topic_selection' and len(store.seats(self.number)) > 1:
            return True
        if found['stage'] in ('synthesis', 'host_summary'):
            return found['synthesizer' if found['stage'] == 'synthesis' else 'host']['kind'] == 'openrouter'
        return (found['stage'] in (None, 'discussion') and render.judging(found)) or any(
            one['kind'] == 'openrouter' for one in store.seats(self.number)) or any(
            cast(dict[str, Any], found.get(role) or {}).get('kind') == 'openrouter'
            for role in ('host', 'synthesizer'))

    def context_limit(self, found: dict[str, Any]) -> int:
        """The smallest active configured trigger, independent of whether judging is enabled."""
        limits = [int(config.value('context_tokens'))]
        budgets = config.context_budgets()
        participants = [one for one in store.seats(self.number) if health.usable(one)]
        participants += [found[role] for role in ('host', 'synthesizer') if found.get(role)]
        limits += [int(budgets[one['id']]) for one in participants if one['id'] in budgets]
        return min(limits)

    def segment(self, found: dict[str, Any]) -> list[dict[str, Any]]:
        return [one for one in store.submissions(self.number, int(render.continuation(found).get('through', 0)))
                if one['topic'] == (found['topic'] if found['stage'] else None)
                and (one['accepted'] or one['kind'] == 'chair')]

    def editor_view(self, found: dict[str, Any], notes: list[dict[str, Any]]) -> str:
        """One editor sees original instructions, previous continuation, the new segment and intact notes."""
        return said('continuation_editor', opening=found['opening'], previous=render.shared(found),
                    topic=self.topic(found)['text'] if found['stage'] else found['opening'],
                    turns='\n\n'.join(f'{render.who(one)} [{render.outcome(one)}]:\n{one["text"]}'
                                      for one in self.segment(found)),
                    notes='\n\n'.join(f'{one["name"]} (seat {int(one["position"]) + 1}):\n{one["text"]}'
                                       for one in notes), limit=max(256, self.context_limit(found) // 4))

    def context_due(self, found: dict[str, Any]) -> bool:
        """Count native seat history and editor input; Jev independently bounds its request window."""
        limit = render.reply_limit(found)
        # Notes, their request framing and editor output need room before any context reaches its trigger.
        reserve = judge.tokens('x' * (2 * limit * len(store.seats(self.number)))) + 3072
        sizes = [judge.tokens(self.editor_view(found, []))]
        for row in store.seats(self.number):
            if health.usable(row):
                seat = self.seat(row)
                unseen = [one for one in self.segment(found) if one['number'] > row['seen']
                          and not (seat.messages and one['position'] == row['position'] and render.entered(one))]
                sizes.append(self.seat_context_tokens(seat, [render.shared(found) if not seat.messages else '',
                                                            unseen]))
        return max(sizes) + reserve >= self.context_limit(found)

    @staticmethod
    def seat_context_tokens(seat: Seat, prompt: Any) -> int:
        """Estimate what is actually in this conversation; session system text is already in its first message."""
        system = seat.system if seat.system_role or not seat.messages else ''
        return judge.tokens([system, seat.messages, prompt])

    async def handoff(self, found: dict[str, Any]) -> None:
        """Capture every participant's note before one editor compacts history. Failures hold, never finish."""
        pending = cast(dict[str, Any], found.get('handoff') or {'after': max(
            (int(one['number']) for one in store.submissions(self.number)), default=0)})
        if not found.get('handoff'):
            self.change(handoff=pending)
        notes = [one for one in store.submissions(self.number, int(pending['after'])) if one['kind'] == 'carry']
        try:
            for row in store.seats(self.number):
                prior = next((one for one in notes if one['position'] == row['position']), None)
                if prior is not None:
                    budget.record_reply(found, row, prior, f'carry:{pending["after"]}:{row["position"]}')
                    if budget.status(found)['forced']:
                        return
                if any(one['position'] == row['position'] for one in notes):
                    continue
                if self.row()['state'] != 'running' or self.row()['advance_asked']:
                    return
                if not health.usable(row) or row['gone']:
                    raise NoReply(f'{row["name"]} is unavailable. Reseat this participant, then Continue.')
                if float(self.row()['spent']) >= float(found['spend']) and self.requires_payment(found):
                    raise NoReply('The spending limit is reached. Raise the table budget, then Continue.')
                seat = self.seat(row)
                await self.topical(found, seat)
                unseen = [one for one in self.segment(found) if one['number'] > int(row['seen'])]
                latest = max([int(one['number']) for one in unseen], default=int(row['seen']))
                shown = [one for one in unseen if not (seat.messages and one['position'] == row['position'])]
                retry = seat.extra.get('carry_request') == pending['after']
                prompt = said('carry_forward_retry' if retry else 'carry_forward',
                              limit=2 * render.reply_limit(found), turns=render.labeled(shown),
                              continuation=render.shared(found) if not seat.messages else '')
                notice = budget.prompt(self.row(), int(row['position']))
                if notice.text:
                    prompt = notice.text + '\n\n' + prompt
                if self.seat_context_tokens(seat, prompt) + 2048 >= self.context_limit(found):
                    raise NoReply('Seat context cannot fit its carry-forward request. '
                                  'Raise the smallest context budget, then Continue, or choose End discussion.')
                def delivered(delivered_seat: Seat = seat, through: int = latest,
                              prepared: budget.Prompt = notice) -> None:
                    delivered_seat.extra['carry_request'] = pending['after']
                    budget.delivered_prompt(found, delivered_seat.position, prepared)
                    self.keep(delivered_seat, through)
                seat.on_delivered = delivered
                try:
                    reply = await seat.reply(prompt, float(config.value('agent_wait')))
                except NoReply as error:
                    if error.delivered:
                        seat.extra['carry_request'] = pending['after']
                    self.keep(seat, latest if error.delivered else None)
                    self.failing(row, error)
                    raise
                finally:
                    seat.on_delivered = None
                # Delivery happened even if the model's note is empty. Retry only the unfinished instruction.
                seat.extra['carry_request'] = pending['after']
                self.keep(seat, latest)
                if not reply.text.strip():
                    raise NoReply(f'{row["name"]} gave no carry-forward note. Continue to retry.')
                receipt = f'carry:{pending["after"]}:{row["position"]}'
                budget.record_reply(found, row, reply.use, receipt, budget.Prompt(notice.text, notice.notice, False))
                note = store.record(self.number, self.entry(found, row, reply.text, kind='carry',
                                    **{key: value for key, value in reply.use.items() if key in USE}), receipt=receipt)
                notes.append(note)
                self.keep(seat, latest)
                if budget.status(self.row())['forced']:
                    return
            if self.row()['state'] != 'running' or self.row()['advance_asked']:
                return
            if float(self.row()['spent']) >= float(found['spend']) and self.requires_payment(found):
                raise NoReply('The spending limit is reached. Raise the table budget, then Continue.')
            editor = self.editor_view(found, notes)
            if judge.tokens(editor) + 2048 >= self.context_limit(found):
                raise NoReply('Editor context cannot fit the shared history and intact notes. '
                              'Raise the smallest context budget, then Continue, or choose End discussion.')
            reply = await self.ask_fresh(found, 'synthesizer', editor)
            if not reply.text.strip():
                raise NoReply('The continuation editor returned no summary. Continue to retry.')
            compact = {'text': reply.text, 'notes': [
                {'position': one['position'], 'name': one['name'], 'text': one['text']} for one in notes],
                'topic': found['topic']}
            candidate = {**found, 'continuation': compact}
            if judge.tokens([found['opening'], render.shared(candidate)]) + 2048 >= self.context_limit(found):
                raise NoReply('Original instructions, summary and intact notes exceed the context trigger. '
                              'Raise the smallest context budget or reduce reply length, then Continue.')
            store.install_handoff(self.number, compact, int(found['round']),
                                  found['topic'] if found['stage'] else None, said('handoff_marker'))
            await self.unseat()
        except Interrupted:
            return
        except NoReply as error:
            self.change(state='held', reason=said('held_handoff', error=error))

    async def turn(self, found: dict[str, Any], row: dict[str, Any]) -> bool:
        """The turn of the seat whose turn it is, whatever its kind; False when the table holds or ends before it is
        recorded."""
        from . import allowance

        given: Any = found.get('unjudged')
        unjudged = cast(dict[str, Any], given) if isinstance(given, dict) else {}
        seat = self.seat(row)
        pending = seat.extra.get('panel_reply')
        limit = render.reply_limit(found, int(row['position']))
        if unjudged and unjudged.get('position') == row['position']:
            original = str(unjudged.get('original') or unjudged['text'])
            use = cast(dict[str, Any], unjudged.get('use') or {})
            limit = int(unjudged.get('allowance_limit') or limit)
            if unjudged.get('usage_id'):
                receipt = str(unjudged['usage_id'])
                completed = allowance.completed(self.number, receipt, int(row['position']))
                if completed is not None:
                    store.record(self.number, completed, judged=True, receipt=receipt)
                    if isinstance(pending, dict) and cast(dict[str, Any], pending).get('usage_id') == receipt:
                        seat.extra['panel_reply'] = None
                    self.keep(seat, None)
                    return True
                allowance.answered(self.number, int(row['position']), receipt)
        elif isinstance(pending, dict):
            held = cast(dict[str, Any], pending)
            found = {**found, 'round': held['round'], 'topic': held['topic'],
                     'pass_after': held.get('pass_after', found['pass_after'])}
            original, use = str(held['original']), cast(dict[str, Any], held['use'])
            limit = int(held.get('allowance_limit') or limit)
            if not held.get('usage_id'):
                held['usage_id'] = uuid.uuid4().hex
                self.keep(seat, None)
            if allowance.completed(self.number, str(held['usage_id']), int(row['position'])) is not None:
                seat.extra['panel_reply'] = None
                self.keep(seat, None)
                return True
            allowance.answered(self.number, int(row['position']), str(held['usage_id']))
            budget.record_reply(found, row, use, str(held['usage_id']), budget.Prompt(
                notice=int(held.get('notice', 0)), closing=bool(held.get('closing', False))))
        else:
            offer = allowance.begin(self.number, int(row['position']), render.reply_limit(found))
            limit = offer.limit
            since = [one for one in store.submissions(self.number, max(int(row['seen']),
                     int(render.continuation(found).get('through', 0)))) if int(one['number']) <= offer.through]
            if found['stage']:
                await self.topical(found, seat)
                view = self.topic_view(found, row, seat, since)
            else:
                shown = [one for one in since
                         if (render.entered(one) and one['kind'] not in ('carry', 'handoff') or one['kind'] == 'pass')
                         if not (seat.messages and one['position'] == row['position'] and render.entered(one))]
                view = render.seat_view(shown, not seat.messages, links=seat.kind == 'agent',
                                        limit=limit)
            own = [one for one in since if one['position'] == row['position'] and one['kind'] == 'seat']
            feedback = render.status(own[-1], limit) if own and render.outcome(own[-1]) == 'vetoed' else ''
            if feedback and view.startswith(feedback):
                view = view[len(feedback):].lstrip()
            if not seat.messages and render.shared(found):
                view = render.shared(found) + '\n\n' + view
            latest = max([int(one['number']) for one in since], default=int(row['seen']))
            notice = budget.prompt(self.row(), int(row['position']))
            view = '\n\n'.join(part for part in (feedback, said('turn_allowance', limit=limit), notice.text, view) if part)
            self.panel_asking.add(int(row['position']))
            self.control.set()  # Native work now owns this opportunity; reevaluate the remaining ready quorum.
            def delivered() -> None:
                allowance.delivered(self.number, seat.position, offer.receipt)
                budget.delivered_prompt(found, seat.position, notice)
                self.keep(seat, latest)
            seat.on_delivered = delivered
            try:
                reply = await seat.reply(view, float(config.value('agent_wait')))
            except openrouter.Unpaid as error:  # out of credits: only this seat is out, probed until they are back
                failure = NoReply(str(error), kind='credits')
                self.keep(seat, None)
                store.record(self.number, self.entry(found, row, '', kind='none', reason=failure.reason()))
                self.failing(row, failure)
                self.unpaid(error)
                return True
            except Interrupted:
                return False
            except NoReply as error:
                self.keep(seat, latest if error.delivered else None)
                store.record(self.number, self.entry(found, row, '', kind='none', reason=error.reason()))
                self.failing(row, error)
                return True
            finally:
                seat.on_delivered = None
                self.panel_asking.discard(int(row['position']))
            self.answering(row)
            original, use = reply.text, reply.use
            # Every completed reply is durable before it waits behind another seat's Jev request.
            seat.extra['panel_reply'] = {'original': original, 'use': use, 'round': found['round'],
                                         'topic': found['topic'], 'pass_after': found['pass_after'],
                                         'usage_id': offer.receipt, 'notice': notice.notice,
                                         'closing': notice.closing, 'allowance_limit': limit}
            self.keep(seat, latest)
            allowance.answered(self.number, int(row['position']), offer.receipt)
            budget.record_reply(found, row, use, str(seat.extra['panel_reply']['usage_id']), notice)
            if budget.limit(self.row()):
                self.control.set()
        async with self.judging:
            current = self.row()
            if current['stage'] != found['stage'] or current['topic'] != found['topic']:
                held = cast(dict[str, Any], seat.extra.get('panel_reply') or {})
                if held:
                    self.archive_reply(seat, row, held)
                return False
            if current['state'] != 'running' or current['stage'] != found['stage'] or current['topic'] != found['topic']:
                return False
            found = {**found, 'round': current['round']}
            if render.passed(original):  # A voluntary pass stays a pass, never a skipped or failed turn.
                receipt = cast(dict[str, Any], seat.extra.get('panel_reply') or {}).get('usage_id')
                recorded = store.record(self.number, self.entry(
                    found, row, original.strip()[:limit], kind='pass',
                    **{key: value for key, value in use.items() if key in USE}),
                    receipt=str(receipt) if receipt else None)
                if int(current['pass_after']) > int(found['pass_after']):
                    self.change(pass_after=recorded['number'])  # The seat had not seen the new chair instruction.
                seat.extra['panel_reply'] = None
                self.keep(seat, None)
                return True
            return await self.judge_turn(found, row, original, use)

    async def judge_turn(self, found: dict[str, Any], row: dict[str, Any], original: str,
                         use: dict[str, Any]) -> bool:
        """Keep one durable unjudged submission while Jev handles it, with other replies queued on their seats."""
        # a T### label the seat wrote is taken off, then a turn longer than the limit is cut to it: the cut text is
        # judged and enters; the record keeps the original as the seat gave it
        stripped, label = judge.unlabeled(original)
        seat = self.seat(row)
        pending = cast(dict[str, Any], seat.extra.get('panel_reply') or {})
        unjudged = cast(dict[str, Any], found.get('unjudged') or {})
        saved_limit = unjudged.get('allowance_limit') if unjudged.get('position') == row['position'] else None
        limit = int(saved_limit or pending.get('allowance_limit') or render.reply_limit(found, int(row['position'])))
        text = stripped[:limit]
        kept = {'original': original if original != text else None, 'truncated': len(stripped) > limit,
                'label': label}
        use = {key: value for key, value in use.items() if key in USE}
        # kept before anything that can fail, so a reply taken and paid for is never lost: continue judges it
        self.change(unjudged={'position': row['position'], 'text': text, **kept, 'use': use,
                              'usage_id': pending.get('usage_id') or unjudged.get('usage_id'), 'allowance_limit': limit})
        seat.extra['panel_reply'] = None
        self.keep(seat, None)
        return await self.verdict(found, row, self.entry(found, row, text, **use, **kept))

    async def verdict(self, found: dict[str, Any], row: dict[str, Any], entry: dict[str, Any]) -> bool:
        """Judge every substantive reply against bounded accepted context, preserving captured historical criteria."""
        if not render.judging(found):
            self.credit_busy()
            recorded = store.record(self.number, {**entry, 'accepted': True}, judged=True)
            self.settle(row, str(entry.get('original') or entry['text']), recorded)
            return True
        staged = bool(found['stage'])
        text = str(entry['text'])
        rows = [one for one in store.submissions(self.number) if not staged or one['topic'] == found['topic']]
        where = {'topic': found['topic'] if staged else None, 'round': found['round'], 'position': row['position']}
        captured = render.captured(found)
        entered = [one for one in rows if render.entered(one)
                   and one['kind'] not in ('carry', 'handoff')]
        if staged:  # a topic is judged against itself and what entered on it, its seats unnamed
            criteria = captured['criteria'] if captured.get('floors') else judge.questions(store.VETO)
            floors = render.floors(captured) if captured.get('floors') else (  # a snapshot from before own bars
                {name: float(captured['keep']) for name in store.VETO} if captured else
                {'new_context': config.floor('keep_new'), 'on_topic': config.floor('keep_on_topic')})
        else:
            criteria = captured.get('criteria') or judge.questions()
            floors = render.floors(captured) if captured else {name: config.keep() for name in store.NOULS}
        topic = self.topic(found) if staged else {'title': found['subject'], 'text': found['subject']}
        given = judge.windowed_state(str(found['opening']), topic, entered,
                                     {'position': row['position'], 'text': text}, criteria,
                                     model=captured.get('jev_model'))
        asked = await asyncio.to_thread(judge.ask, given, criteria, model=captured.get('jev_model'))
        current = self.row()
        if current['topic'] != found['topic'] or current['stage'] != found['stage']:
            with store.connect() as db:
                store.fence(db, self.number)
                store.judge(db, self.number, asked.row('veto', floors, 'late', **where))
            return False  # Advancement already archived this completed reply and its receipt.
        if asked.nouls is None:
            self.unjudged(asked, asked.row('veto', floors, None, **where))
            return False
        accepted = judge.passed(asked.nouls, floors)
        self.credit_busy()
        recorded = store.record(self.number, {**entry, 'accepted': accepted, 'jev_cost': round(asked.cost, 6),
                                              **asked.nouls}, judged=True,
                                judgment=asked.row('veto', floors, 'keep' if accepted else 'veto', **where))
        self.settle(row, str(entry.get('original') or text), recorded)
        return True

    def entry(self, found: dict[str, Any], row: dict[str, Any], text: str, **given: Any) -> dict[str, Any]:
        return {'round': found['round'], 'position': row['position'], 'seat': row['id'], 'name': row['name'],
                'kind': 'seat', 'text': text, 'topic': found['topic'] if found['stage'] else None, **given}

    def topic_view(self, found: dict[str, Any], row: dict[str, Any], seat: Seat, since: list[dict[str, Any]]) -> str:
        """A Roundtable 2 seat's discussion turn: the status of its previous contribution, the other seats'
        contributions on the open topic since its last turn, and the topic when its context does not hold it yet: on
        its first turn of a topic, or in a context begun again, after the digest of the topics before it."""
        own = [one for one in since if one['position'] == row['position']]
        others = [one for one in since if (render.session(found) or one['topic'] == found['topic'])
                  and render.entered(one) and one['kind'] not in ('carry', 'handoff')
                  and (one['position'] != row['position'] or (not seat.messages and render.entered(one)))]
        mine = [one for one in store.submissions(self.number) if one['position'] == row['position']]
        fresh = not seat.messages
        spoken = not fresh and any(one['topic'] == found['topic'] for one in mine)
        digest = '' if spoken or render.shared(found) else render.digest(self.number, int(found['topic']))
        return render.topic_view(str(self.topic(found)['text']), own[-1] if own else None, others,
                                 fresh and not mine, spoken, digest, limit=render.reply_limit(found, int(row['position'])))

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
        if stage == 'topic_selection':
            await self.select_topic(found)
        elif stage in PHASES:
            await self.collaborate(found)
        elif stage == 'synthesis':
            if render.session(found):
                self.start_topic_selection(found)
            else:
                await self.synthesis(found)
        elif stage == 'host_summary':
            await self.host_summary(found)
        elif stage in stages.EACH:
            await self.each(found, stage)
        else:
            self.ending(said('ended_topics'))

    def fresh(self, found: dict[str, Any], role: str) -> Seat:
        """The synthesizer or the host as a seat of its own for one request, with nothing before it."""
        empty: dict[str, Any] = {}
        given = cast(dict[str, Any], found.get(role) or next(
            (one for one in store.seats(self.number) if seating.able(one)), empty))
        if not given:
            raise NoReply('No participant can edit continuation. Seat an ACP, OpenRouter or A2A participant.')
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
        rows = [one for one in self.segment(found) if render.entered(one)]
        text = said('synthesis', topic=topic['text'],
                    turns=render.shared(found) + '\n\n' + ('\n\n'.join(render.entry(one) for one in rows)
                                                          or said('no_contributions')))
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
                    bottoms=render.stage_lines(rows, 'bottom_three'), writing=render.writing(found))
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
        self.change(topic=at + 1, stage='discussion', round=1, position=0, round_kept=0, quiet_rounds=0,
                    advance_asked=False)

    # ------------------------------------------------------------------------------------------- a session

    def start_topic_selection(self, found: dict[str, Any]) -> None:
        """After a panel, privately select its successor, or start the final scorecards."""
        if self.row()['stage'] in ('topic_selection', 'scoring', 'farewell'):
            return
        held = render.session(found) or {}
        at, total = int(found['topic']) + 1, int(held.get('total') or 1)
        self.change(handoff=None, advance_asked=False)
        if at >= total:
            store.phase(self.number, 'scoring', said('session_scoring', message=str(held.get('score') or ''),
                        seats=', '.join(str(row['name']) for row in store.seats(self.number))))
            return
        topics.seed(found, store.seats(self.number))
        store.phase(self.number, 'topic_selection', said('topic_selection_start', index=str(at), total=str(total)))

    async def select_topic(self, found: dict[str, Any]) -> None:
        """Give each model two chances, then compare the private proposals that actually arrived."""
        for position, task in list(self.working.items()):
            if task.done():
                del self.working[position]
                self.work_phase.pop(position, None)
                if not task.cancelled():
                    task.result()
        seated = store.seats(self.number)
        topics.seed(found, seated)
        topics.recover(found, set(self.working))
        topics.skip(found, {int(row['position']) for row in seated if row['gone']})
        collected = topics.proposals(self.number, int(found['topic']))
        attempted = [row for row in collected if row['receipt']]
        deadline = min((datetime.fromisoformat(str(row['created'])).timestamp() for row in attempted),
                       default=time.time()) + float(config.value('topic_proposal_wait'))
        pending = [proposal for proposal in collected if proposal['state'] == 'pending' and
                   not self.busy(seated[int(proposal['position'])])]
        candidate = any(row['state'] == 'ready' for row in collected)
        if attempted and time.time() >= deadline and candidate:
            topics.skip(found, {int(row['position']) for row in collected if row['state'] in ('pending', 'sent')})
            pending = []
        elif candidate:
            topics.skip(found, {int(row['position']) for row in collected if row['state'] == 'pending' and
                               self.busy(seated[int(row['position'])])})
        elif not pending and any(row['state'] in ('pending', 'sent') for row in collected):
            await self.wait_busy()
            return  # A skipped busy opportunity cannot permanently remove the only possible future proposer.
        if pending:
            at = int(found['position'])
            given = min(pending, key=lambda row: (int(row['position']) - at) % max(1, len(seated)))
            position = int(given['position'])
            row = seated[position]
            receipt = topics.begin_proposal(found, position)
            if receipt is not None:
                self.working[position] = asyncio.create_task(self.propose_topic(found, row, receipt))
                self.work_phase[position] = ('topic_selection', int(found['topic']))
            self.change(position=position + 1)
            return
        current_proposals = [row for row in topics.proposals(self.number, int(found['topic'])) if row['state'] == 'sent']
        if current_proposals:
            cutoff = asyncio.create_task(asyncio.sleep(max(0.0, deadline - time.time())))
            try:
                await self.wait_work([cutoff, *(self.working[int(row['position'])] for row in current_proposals
                                              if int(row['position']) in self.working)])
            finally:
                cutoff.cancel()
                await asyncio.gather(cutoff, return_exceptions=True)
            return
        if self.topic_choice is None or self.topic_choice[0] != int(found['topic']):
            if self.topic_deciding is None:
                self.topic_deciding = asyncio.create_task(asyncio.to_thread(topics.decide, found,
                                                                            str(self.topic(found)['text'])))
            if not self.topic_deciding.done():
                await self.wait_work([self.topic_deciding])
                return
            try:
                self.topic_choice = (int(found['topic']), self.topic_deciding.result())
            except ValueError as error:
                self.change(state='held', reason=said('topic_selection_failed', error=str(error)))
                return
            finally:
                self.topic_deciding = None
        decision = self.topic_choice[1]
        current = self.row()
        if current['state'] != 'running' or current['stage'] != 'topic_selection' or current['topic'] != found['topic']:
            return
        held = render.session(current) or {}
        at = int(found['topic']) + 1
        # An interrupted transition may have added this topic before updating the table cursor.
        if len(store.topics(self.number)) <= at:
            store.add_topic(self.number, said('session_topic', index=str(at + 1),
                            total=str(held.get('total') or 1), topic=str(decision['text'])))
        if held.get('compress_between_topics'):
            due = [row for row in seated if row['kind'] == 'acp' and health.usable(row) and not self.busy(row)
                   and cast(dict[str, Any], row.get('extra') or {}).get('compressed_for_topic') != at]
            if due:
                snapshot = cast(dict[str, Any], current.get('snapshot') or {})
                self.change(snapshot={**snapshot, 'session': {**held, 'compressing_for_topic': at}})
                for row in due:
                    seat = self.seat(row)
                    seat.extra['compressed_for_topic'] = at
                    self.keep(seat, None)
                    self.working[int(row['position'])] = asyncio.create_task(
                        self.compress_topic(row, str(decision['text'])))
                    self.work_phase[int(row['position'])] = ('compression', int(found['topic']))
            if held.get('compressing_for_topic') == at:
                snapshot = cast(dict[str, Any], current.get('snapshot') or {})
                self.change(snapshot={**snapshot, 'session': {**held, 'compressing_for_topic': None}})
        self.next_topic(current)

    async def compress_topic(self, row: dict[str, Any], topic: str) -> tuple[Reply | None, int, str | None]:
        """Optional native compression keeps the same conversation and never blocks topic advancement on failure."""
        seat = self.seat(row)
        try:
            compressed = await seat.compress(topic, float(config.value('agent_wait')))
            self.tell('topic_compression', said('topic_compression_done' if compressed else 'topic_compression_unavailable',
                                               seat=row['name']))
        except store.Lost:
            raise
        except Exception as error:  # noqa: BLE001  optional compression cannot hold the discussion
            self.tell('topic_compression', said('topic_compression_failed', seat=row['name'], error=str(error)))
        finally:
            self.keep(seat, None)
        return None, int(row['seen']), None

    async def propose_topic(self, found: dict[str, Any], row: dict[str, Any], receipt: str
                            ) -> tuple[Reply | None, int, str | None]:
        """One private request in the existing conversation, carrying only newly queued accepted material."""
        seat = self.seat(row)
        accepted = [one for one in store.submissions(self.number, int(row['seen']))
                    if (render.session(found) or one['topic'] == found['topic']) and
                    render.entered(one) and one['kind'] in ('seat', 'chair')]
        latest = max((int(one['number']) for one in accepted), default=int(row['seen']))
        shown = [one for one in accepted if not (seat.messages and one['position'] == row['position'])]
        context = '\n\n'.join(render.entry(one) for one in shown) or said('nothing_since')
        limit = render.reply_limit(found)
        prompt = said('topic_proposal', topic=str(self.topic(found)['text']), discussion=context, limit=str(limit))
        seat.on_delivered = lambda: self.keep(seat, latest)
        try:
            reply = await seat.reply(prompt, float(config.value('agent_wait')))
            valid = topics.finish_proposal(found, int(row['position']), receipt, reply.text[:limit], reply.use)
            if valid:
                self.answering(row)
            else:
                self.failing(row, NoReply(said('proposal_required'), kind='empty'))
            seat.settled(reply.text, said('proposal_received') if valid else said('proposal_required'))
            self.keep(seat, latest)
        except (NoReply, openrouter.Silent) as error:
            failure = error if isinstance(error, NoReply) else NoReply(str(error), kind=error.kind)
            self.failing(row, failure)
            topics.finish_proposal(found, int(row['position']), receipt, None, {'error': str(error)})
            self.keep(seat, None)
            self.tell('topic_proposal_failed', said('topic_proposal_failed', seat=row['name'], error=str(error)))
        finally:
            seat.on_delivered = None
        return None, latest, None

    def chair(self, found: dict[str, Any], text: str) -> None:
        """A message to every seat from the table itself, entered as the chair's, on the open roundtable."""
        store.record(self.number, {'round': found['round'], 'position': None, 'kind': 'chair', 'seat': 'chair',
                                   'name': None, 'text': text, 'topic': found['topic']})

    async def collaborate(self, found: dict[str, Any]) -> None:
        """Scoring and farewell retain their existing private scorecard and explicit completion contracts."""
        stage = str(found['stage'])
        kind = PHASES[stage]
        self.harvest(found, kind)
        found = self.row()
        if found['state'] != 'running' or found['stage'] != stage:
            return
        seated = store.seats(self.number)
        phase = [one for one in store.submissions(self.number, int(found['phase_after']) - 1)
                 if one['topic'] == found['topic'] and one['kind'] in (kind, 'chair')]
        if kind == 'score':
            phase += [{**one, 'kind': 'score', 'number': 0} for one in store.scorecards(self.number)]
        due = [row for row in seated if not row['gone'] and health.usable(row)
               and not self.busy(row) and self.needs(row, phase, kind)]
        if due:
            at = int(found['position'])
            row = min(due, key=lambda one: (int(one['position']) - at) % max(1, len(seated)))
            self.wake(found, row, phase, kind)
            self.change(position=(int(row['position']) + 1) % max(1, len(seated)))
            return
        if self.has_busy():
            await self.wait_busy()
            return
        if any(self.needs(row, phase, kind) for row in seated if health.usable(row)):
            self.change(state='held', reason='Waiting for participants to finish the session.')
            return
        await self.phase_done(found, stage, seated, phase)

    def needs(self, row: dict[str, Any], phase: list[dict[str, Any]], kind: str,
              found: dict[str, Any] | None = None) -> bool:
        mine = [one for one in phase if one['position'] == row['position'] and one['kind'] == kind]
        if not mine:
            return True
        if kind == 'score':
            return not self.scored(row, mine[-1])
        newer = [one for one in phase if int(one['number']) > int(row['seen']) and one['position'] != row['position']
                 and (one['kind'] == 'chair' or not render.said_done(str(one.get('original') or one['text'])))]
        return bool(newer) or not render.said_done(str(mine[-1].get('original') or mine[-1]['text']))

    def wake(self, found: dict[str, Any], row: dict[str, Any], phase: list[dict[str, Any]], kind: str) -> None:
        position = int(row['position'])
        seat = self.seat(row)
        shown = [one for one in phase if int(one['number']) > int(row['seen']) and one['position'] != position
                 and (kind != 'score' or one['kind'] == 'chair')]
        latest = max([int(one['number']) for one in phase], default=int(row['seen']))
        names = [str(one['name']) for one in store.seats(self.number) if int(one['position']) != position]
        text = said('phase_turn', turns='\n\n'.join(render.entry(one) for one in shown) or said('nothing_since'),
                    instruction=said(f'{kind}_instruction', seats=', '.join(names)), limit=str(render.reply_limit(found)))

        async def reply() -> tuple[Reply | None, int, str | None]:
            seat.on_delivered = lambda: self.keep(seat, latest)
            try:
                made = await seat.reply(text, float(config.value('agent_wait')))
                return made, latest, None
            except openrouter.Unpaid as error:
                self.unpaid(error)
                return None, int(store.seats(self.number)[position]['seen']), str(error)
            except Interrupted:
                return None, int(store.seats(self.number)[position]['seen']), None
            except NoReply as error:
                self.failing(row, error)
                return None, latest if error.delivered else int(store.seats(self.number)[position]['seen']), error.reason()
            finally:
                seat.on_delivered = None
        self.working[position] = asyncio.ensure_future(reply())
        self.work_phase[position] = (str(found['stage']), int(found['topic']))

    def harvest(self, found: dict[str, Any], kind: str) -> None:
        for position, task in list(self.working.items()):
            if not task.done() or self.work_phase.get(position, (str(found['stage']), int(found['topic']))) != (
                    str(found['stage']), int(found['topic'])):
                continue
            del self.working[position]
            self.work_phase.pop(position, None)
            reply, latest, failed = task.result()
            row = store.seats(self.number)[position]
            seat = self.seat(row)
            if reply is None:
                self.keep(seat, latest)
                if failed is not None:
                    store.record(self.number, {**self.entry(found, row, '', kind='none', reason=failed)})
                continue
            self.answering(row)
            if kind == 'score':
                store.scorecard_record(self.number, position, reply.text.strip())
                seat.settled(reply.text, said('score_received'))
                self.keep(seat, latest)
                continue
            self.keep(seat, latest)
            original = reply.text.strip()
            text = original[:render.reply_limit(found)]
            use = {key: value for key, value in reply.use.items() if key in USE}
            cut = {'original': original, 'truncated': True} if text != original else {}
            store.record(self.number, {**self.entry(found, row, text, kind=kind, accepted=True), **use, **cut})

    def scored(self, row: dict[str, Any], last: dict[str, Any]) -> bool:
        return stages.scorecard(str(last['text']), [str(one['name']) for one in store.seats(self.number)
                                                    if one['position'] != row['position']]) is not None

    async def phase_done(self, found: dict[str, Any], stage: str, seated: list[dict[str, Any]],
                         phase: list[dict[str, Any]], *, forced: bool = False) -> None:
        current = self.row()
        if current['state'] != 'running' or current['stage'] != stage or current['topic'] != found['topic']:
            return
        held = render.session(current) or {}
        if stage == 'scoring':
            self.chair(current, self.results(seated, phase))
            store.phase(self.number, 'farewell', said('session_farewell', message=str(held.get('farewell') or '')))
        else:
            self.ending(said('session_ended'))

    def results(self, seated: list[dict[str, Any]], phase: list[dict[str, Any]]) -> str:
        """The scorecards added up: each seat's points from the others, kept in its profile, and the ranking."""
        given: dict[int, list[float]] = {int(one['position']): [] for one in seated}
        by_name = {str(one['name']).casefold(): int(one['position']) for one in seated}
        for row in seated:
            cards = [one for one in phase if one['position'] == row['position'] and one['kind'] == 'score']
            others = [str(one['name']) for one in seated if one['position'] != row['position']]
            card = next((found for one in reversed(cards)
                         if (found := stages.scorecard(str(one['text']), others)) is not None), None)
            for name, points in (card or {}).items():
                given[by_name[name.casefold()]].append(points)
        lines: list[tuple[float, str]] = []
        profiles: dict[str, dict[str, Any]] = {}
        identities = {int(row['position']): str(row.get('profile_key') or
                      f'{row["agent"] or row["kind"]}/{row["model"] or row["id"]}') for row in seated}
        for row in seated:
            agent = identities[int(row['position'])]
            if agent not in profiles:
                points = [point for one in seated
                          if identities[int(one['position'])] == agent
                          for point in given[int(one['position'])]]
                profiles[agent] = store.rated(agent, str(row['name']), points, discussion=self.number)
            points = given[int(row['position'])]
            profile = profiles[agent]
            lines.append((sum(points), said('session_rank', seat=str(row['name']), points=f'{sum(points):g}',
                                            cards=str(len(points)),
                                            rating='unscored' if profile['score'] is None
                                            else f'{float(profile["score"]):g}')))
        ranked = [line for _, line in sorted(lines, key=lambda one: -one[0])]
        return said('session_results', ranking='\n'.join(f'{n}. {line}' for n, line in enumerate(ranked, 1)))

    # ------------------------------------------------------------------------------------------- the end

    def writers(self, found: dict[str, Any]) -> list[dict[str, Any]]:
        """Who is asked for the report, in turn: the named reporter, every other seat that can write it and has not
        left, an ACP seat first, then the `report_model` through OpenRouter. Never Claude through OpenRouter."""
        remaining = float(found['spent']) < float(found['spend'])
        seated = [one for one in store.seats(self.number) if seating.able(one)
                  and (one['kind'] != 'openrouter' or remaining)]
        chosen = [one for one in seated if one['id'] == found['reporter'] and not one['gone']]
        others = sorted((one for one in seated if one['id'] != found['reporter'] and health.usable(one)),
                        key=lambda one: one['kind'] != 'acp')
        model = str(config.value('report_model') or '').strip()
        given: dict[str, Any] = {'kind': 'openrouter', 'id': model, 'model': model, 'agent': None}
        extra = [{**given, 'name': named_base(given), 'position': store.REPORTER}] \
            if remaining and config.openrouter_key() and model and seating.able(given) and all(
                one['id'] != model for one in seated) else []
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
        await self.stop_panel(record=True)
        if self.working:
            if str(found['stage']) in PHASES:
                self.harvest(found, PHASES[str(found['stage'])])
            await self.unseat()
        base = config.reports() / f'{self.number}-{found["subject"]}'
        written = Path(f'{base}.record.md')
        written.write_text(export.mechanical(self.number), encoding='utf-8')
        self.change(mechanical=str(written))
        if render.session(found):  # a session's record is its minutes and the agents' own materials: no report
            report, told = str(written), None
        elif found['report'] and found['report'] != str(written) and Path(str(found['report'])).is_file():
            report, told = str(found['report']), None
        else:
            try:
                rows = [one for one in store.submissions(self.number) if render.entered(one)]
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
