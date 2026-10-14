"""The runner of a table, BASE-066: one process per table, started detached when the table opens, that starts its
harness seats' sessions, gives each seat its turn in a fixed round-robin order, skipping a seat that has left, has
Jev judge each submission, enters the comments at the gaps, delivers each turn into the head agent's session when it
chairs, pauses while the person watches, and when the table ends stops its harness seats and writes the report.

Everything the runner knows is in the module's tables, so a runner that stops, and the one started in its place by
`continue`, `end` or `open` again, picks up where the table is: the next seat, a submission Jev did not judge yet, the
last turn the head agent was given. It says it is alive by its beat, every few seconds; one silent for half a minute
has stopped.
"""
from __future__ import annotations

import logging
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, cast

from metaform.data import Store
from metaform.module import Context, Stop, child_environment

from . import chair, explore, harness, judge, render, seats, stage, store, toolloop
from .render import LIMIT, said

log = logging.getLogger(__name__)

POLL = 0.25  # seconds between looks at the table while it waits on the person, a hold or an agent seat
BEAT = 5.0  # seconds between the runner's beats
STALE = 30.0  # a runner whose beat is older than this has stopped
REPORT_WAIT = 900  # seconds a harness seat has to write the report


def alive(row: dict[str, Any]) -> bool:
    return bool(row.get('runner')) and time.time() - float(row.get('beat') or 0) < STALE


def spawn(ctx: Context, number: int) -> int | None:
    """Start the table's runner detached from the caller, unless one runs; its pid, or None when one was running.
    The runner's role is `roundtable`, so what it sends the head agent is credited to it, BASE-052."""
    held = store.own(ctx.require_store())
    if alive(store.discussion(held, number)):
        return None
    log_path = os.path.join(tempfile.gettempdir(), f'metaform-roundtable-{held.project_id}-{number}.log')
    options: dict[str, Any] = ({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
                               if os.name == 'nt' else {'start_new_session': True})
    with open(log_path, 'ab') as written:
        child = subprocess.Popen([sys.executable, '-m', 'metaform', 'roundtable', 'run', str(number),
                                  '--project', held.project_id],
                                 cwd=held.project().path, env=child_environment(METAFORM_ROLE=chair.ROLE),
                                 stdin=subprocess.DEVNULL, stdout=written, stderr=written, **options)
    return child.pid


class Table:
    """One table's runner."""

    def __init__(self, ctx: Context, number: int) -> None:
        self.ctx = ctx
        self.number = number
        self.store: Store = store.own(ctx.require_store())
        self.folder = Path(self.store.project().path)
        self.token = secrets.token_hex(8)
        self.stopped = threading.Event()
        self.stage: stage.Stage | None = None

    # ------------------------------------------------------------------------------------------- reading, writing

    def row(self) -> dict[str, Any]:
        return store.discussion(self.store, self.number)

    def change(self, **changes: Any) -> dict[str, Any]:
        return store.change(self.store, self.number, **changes)

    def keep(self) -> float:
        return int(self.ctx.setting('roundtable_keep')) / 100

    def pay(self, cost: float) -> None:
        """One paid call's cost, added to what the table has spent."""
        if cost > 0:
            store.spend(self.store, self.number, cost)

    def rounds(self, found: dict[str, Any]) -> int:
        """The most rounds the table runs: its own, given when it opened, else roundtable_rounds."""
        return int(found.get('rounds') or self.ctx.setting('roundtable_rounds'))

    def spend(self, found: dict[str, Any]) -> float:
        """The most OpenRouter dollars the table spends: its own, given when it opened, else roundtable_spend."""
        given = found.get('spend')
        return float(given if given is not None else self.ctx.setting('roundtable_spend'))

    def spent_out(self, found: dict[str, Any]) -> bool:
        spent = float(found.get('spent') or 0)
        return spent > 0 and spent >= self.spend(found)

    def hold(self, reason: str) -> None:
        """The table held with its reason, and the head agent told, once."""
        self.change(state='held', reason=reason)
        self.notice(said('chair_held', discussion=self.number, reason=reason))

    # ------------------------------------------------------------------------------------------- the loop

    def run(self) -> dict[str, Any]:
        found = self.row()
        if alive(found):
            return {'discussion': self.number, 'state': found['state'], 'runner': 'already running'}
        self.change(runner=self.token, beat=time.time())
        beating = threading.Thread(target=self.beat, daemon=True)
        beating.start()
        try:
            if found['state'] in ('running', 'held'):
                self.open_stage()
                self.seat_harnesses()
                explore.explore(self)
            while True:
                found = self.row()
                self.enter_comments()
                self.deliver()
                if found['state'] == 'ended':
                    self.unseat()
                    return self.summary()
                if found['state'] == 'ending':
                    self.finish()
                    return self.summary()
                if found['state'] == 'held':
                    time.sleep(POLL)
                    continue
                if self.spent_out(found):
                    self.change(state='ending', reason=said('ended_spend', spend=f'{self.spend(found):.2f}',
                                                             spent=f'{float(found["spent"]):.2f}'))
                    continue
                if store.seats(self.store, self.number)[int(found['position'])]['gone']:  # it left the table
                    self.advance()
                    continue
                if self.turn(found):
                    self.advance()
                    self.deliver()
                    self.gap()
        finally:
            self.stopped.set()
            self.close_stage()
            if self.row().get('runner') == self.token:
                self.change(runner=None)

    def beat(self) -> None:
        while not self.stopped.wait(BEAT):
            try:
                self.change(beat=time.time())
            except Stop as error:
                log.warning('Roundtable %s: the beat was not kept: %s', self.number, error)

    def open_stage(self) -> None:
        """The watch server, its address kept on the table while this runner runs; a table runs on without it."""
        try:
            self.stage = stage.Stage(self.store, self.number)
            self.change(scene=self.stage.start())
        except OSError as error:
            log.warning('Roundtable %s: the watch server did not start: %s', self.number, error)
            self.stage = None

    def close_stage(self) -> None:
        if self.stage is None:
            return
        try:
            self.stage.stop()
            if self.row().get('runner') == self.token:
                self.change(scene=None)
        except (OSError, Stop) as error:
            log.warning('Roundtable %s: the watch server did not stop cleanly: %s', self.number, error)
        self.stage = None

    def picture(self, position: int) -> str:
        """A seat's eye view, drawn by this runner's own renderer."""
        if self.stage is None:
            raise stage.Unseen('the table has no renderer running')
        return self.stage.look(position)

    def summary(self) -> dict[str, Any]:
        found = self.row()
        return {'discussion': self.number, 'state': found['state'], 'reason': found['reason'],
                'report': found['report']}

    # ------------------------------------------------------------------------------------------- a turn

    def turn(self, found: dict[str, Any]) -> bool:
        """The turn of the seat whose turn it is; False when the table holds or ends before it is recorded."""
        seat = store.seats(self.store, self.number)[int(found['position'])]
        given: Any = found.get('unjudged')
        unjudged = cast(dict[str, Any], given) if isinstance(given, dict) else {}
        if unjudged and unjudged.get('position') == seat['position']:
            text, over = str(unjudged['text']), bool(unjudged['over512'])
        else:
            since = store.submissions(self.store, self.number, int(seat['seen']))
            # its own kept turns are in its own conversation already; its vetoed ones it sees as their verdicts
            shown = [one for one in since if not (one['position'] == seat['position'] and render.entered(one))]
            view = render.seat_view(found['opening'], shown, not seat['messages'])
            latest = max([int(one['number']) for one in since], default=int(seat['seen']))
            spoke = (self.speak(seat, view, latest) if seat['kind'] == 'openrouter' else
                     harness.speak(self.ctx, self.store, found, seat, view, latest, self.ending)
                     if seat['kind'] == 'acp' else self.wait(seat, view, latest))
            if spoke is None:
                return False
            text, over, reason = spoke
            if text is None:
                store.record(self.store, self.number, self.entry(found, seat, '', kind='none', reason=reason))
                return True
        if over:
            store.record(self.store, self.number, self.entry(found, seat, text, over512=True))
            self.change(unjudged=None)
            return True
        entered = [one for one in store.submissions(self.store, self.number) if render.entered(one)]
        try:
            nouls = judge.ask(self.folder, judge.state(found['opening'], entered, seat['name'], text), self.pay)
        except judge.Failed as error:
            if '402' in str(error) or 'credits' in str(error).lower():  # Jev out of credits: end, never hold
                self.change(state='ending', reason=said('ended_credits', error=error), position=0)
                return False
            reason = said('held_jev', error=error)
            self.change(state='held', reason=reason,
                        unjudged={'position': seat['position'], 'text': text, 'over512': False})
            self.notice(said('chair_held', discussion=self.number, reason=reason))
            return False
        accepted = all(nouls[name] >= self.keep() for name in store.NOULS)
        store.record(self.store, self.number, self.entry(found, seat, text, accepted=accepted, **nouls))
        self.change(unjudged=None, round_kept=int(self.row()['round_kept']) + int(accepted))
        return True

    def entry(self, found: dict[str, Any], seat: dict[str, Any], text: str, **given: Any) -> dict[str, Any]:
        return {'round': found['round'], 'position': seat['position'], 'seat': seat['id'], 'name': seat['name'],
                'kind': 'seat', 'text': text, **given}

    def speak(self, seat: dict[str, Any], view: str, latest: int) -> tuple[str | None, bool, str] | None:
        """A model's turn through OpenRouter, in its own running conversation, with its controls as tools; told once
        when it runs over the limit, and given one retry. None when OpenRouter refuses it for want of credits: the
        table holds with the reason, and the turn stays this seat's for continue."""
        at = toolloop.At(self.store, self.number, int(seat['position']), self.picture)
        messages: list[dict[str, Any]] = [*seat['messages'], {'role': 'user', 'content': view}]
        try:
            reply, messages = toolloop.turn(seat['id'], at, messages, paid=self.pay)
            over = len(reply) > LIMIT
            if over:
                messages.append({'role': 'user', 'content': said('over_limit', length=len(reply), limit=LIMIT)})
                reply, messages = toolloop.turn(seat['id'], at, messages, paid=self.pay)
                over = len(reply) > LIMIT
        except seats.Unpaid as error:  # out of credits: the table ends and its report is written, never left held
            self.change(state='ending', reason=said('ended_credits', error=error), position=0)
            return None
        except seats.Silent as error:
            return None, False, said('no_reply_model', error=error)
        store.seat_change(self.store, self.number, seat['position'], messages=messages, seen=latest)
        return reply, over, ''

    def wait(self, seat: dict[str, Any], view: str, latest: int) -> tuple[str | None, bool, str] | None:
        """An agent seat's turn: shown to it by `turn`, answered by `submit`; no submission in time is recorded as
        such. None when the table ends while it waits."""
        seconds = int(self.ctx.setting('roundtable_agent_wait'))
        if not (seat['pending'] and seat['reply']):  # a reply given while no runner ran is kept for this one
            store.seat_change(self.store, self.number, seat['position'], pending=view, asked=time.time(), reply=None,
                              tries=0)
        deadline = time.time() + seconds
        reply: Any = None
        while time.time() < deadline:
            held = store.seats(self.store, self.number)[int(seat['position'])]
            reply = held['reply']
            if reply or self.row()['state'] == 'ending':
                break
            time.sleep(POLL)
        if not reply:
            store.seat_change(self.store, self.number, seat['position'], pending=None)
            return None if self.row()['state'] == 'ending' else (None, False, said('no_reply_time', seconds=seconds))
        text = str(reply['text'])
        messages = [*seat['messages'], {'role': 'user', 'content': view}, {'role': 'assistant', 'content': text}]
        store.seat_change(self.store, self.number, seat['position'], pending=None, reply=None, messages=messages,
                          seen=latest)
        return text, bool(reply.get('over512')), ''

    def ending(self) -> bool:
        return self.row()['state'] == 'ending'

    def seat_harnesses(self) -> None:
        """Every harness seat's session started as the runner starts, so each is ready by its turn; one that cannot
        be started now is tried again on its turn, and leaves the table if it still cannot."""
        try:
            harness.start(self.ctx, self.store, self.row())
        except Stop as error:
            log.warning('Roundtable %s: the harness seats were not started: %s', self.number, error)

    def unseat(self) -> None:
        """The table has ended: every harness seat's session stopped through dispatch, and its held ticket closed."""
        try:
            harness.stop(self.ctx, self.store, self.row())
        except Stop as error:
            log.warning('Roundtable %s: the harness seats were not all stopped: %s', self.number, error)

    def advance(self) -> None:
        """The next seat; after the last, the next round, or the end when the round kept nothing."""
        found = self.row()
        position = int(found['position']) + 1
        if position < len(found['seats']):
            self.change(position=position)
        elif int(found['round_kept']) == 0:
            self.change(state='ending', reason=said('ended_round'), position=0)
        elif int(found['round']) >= self.rounds(found):
            self.change(state='ending', reason=said('ended_rounds', rounds=self.rounds(found)), position=0)
        else:
            self.change(round=int(found['round']) + 1, position=0, round_kept=0)

    # ------------------------------------------------------------------------------------------- between turns

    def gap(self) -> None:
        """While the person watches, roundtable_pause seconds for hold, a comment, continue or end; while nobody
        watches, nothing: the next turn follows at once."""
        found = self.row()
        if float(found['watched']) <= time.time():
            if found['go']:  # a continue with no pause to end
                self.change(go=False)
            return
        end = time.time() + int(self.ctx.setting('roundtable_pause'))
        while time.time() < end:
            self.enter_comments()
            self.deliver()
            found = self.row()
            if found['state'] != 'running' or found['go']:
                break
            time.sleep(POLL)
        if found['go']:
            self.change(go=False)

    def enter_comments(self) -> None:
        """The comments waiting, entered inline in order, credited to whoever wrote them, unjudged."""
        found = self.row()
        for comment in store.take_comments(self.store, self.number):
            # the head agent's comment is credited to its name, made from its model as a seat's is
            named = None if comment['by'] == 'person' else chair.head_name(
                self.ctx, found['chair_work'], found['chair_session'],
                [str(seat['name']) for seat in store.seats(self.store, self.number)])
            store.record(self.store, self.number, {
                'round': found['round'], 'position': None, 'kind': comment['by'], 'text': comment['text'],
                'seat': 'person' if comment['by'] == 'person' else 'head agent', 'name': named})

    def deliver(self) -> None:
        """Every turn the head agent has not been given yet, in order, when it chairs; one it cannot be given now
        stays for the next try, and the table goes on."""
        found = self.row()
        if found['chair'] != 'head':
            return
        for one in store.submissions(self.store, self.number, int(found['delivered'])):
            try:
                chair.deliver(self.ctx, found['chair_work'], found['chair_session'], render.chair_message(found, one))
            except Stop as error:
                log.warning('Roundtable %s: turn %s was not delivered to the head agent: %s', self.number,
                            one['number'], error)
                return
            self.change(delivered=int(one['number']))

    def notice(self, text: str) -> None:
        found = self.row()
        if found['chair'] != 'head':
            return
        try:
            chair.deliver(self.ctx, found['chair_work'], found['chair_session'], text)
        except Stop as error:
            log.warning('Roundtable %s: the head agent was not told: %s', self.number, error)

    # ------------------------------------------------------------------------------------------- the end

    def report(self, found: dict[str, Any], rows: list[dict[str, Any]], reporter: str) -> str:
        """The report's text: through OpenRouter for a model id, or from the harness seat at this table that the
        reporter names. A harness reporter that does not sit at the table is refused, since starting one would be a
        session outside the table."""
        record = render.record(found, rows)
        if not reporter.startswith('acp:'):
            return seats.chat(reporter, [{'role': 'user', 'content': record}], tokens=seats.REPORT_TOKENS,
                              paid=self.pay)
        wanted = seats.parse(reporter)['id']
        seat = next((one for one in store.seats(self.store, self.number)
                     if one['id'] == wanted and not one.get('gone')), None)
        if seat is None:
            raise seats.Silent(f'{reporter} does not sit at this table, so it cannot write the report.')
        deadline = time.time() + max(REPORT_WAIT, int(self.ctx.setting('roundtable_agent_wait')))
        row = harness.session_of(self.ctx, self.store, found, seat, deadline, lambda: False)
        if row is None:
            raise seats.Silent(f'{reporter} has no running session.')
        found = store.discussion(self.store, self.number)  # with its ticket
        text = harness.exchange(self.ctx, self.store, found, seat, row, record, deadline, lambda: False)
        if not text:
            raise seats.Silent('the reply was empty.')
        return text

    def finish(self) -> None:
        """The report: one model given the whole record, its answer saved under docs/roundtables/. A reporter written
        as a harness seat, `acp:<agent>/<model>`, is that seat at this table writing it in its own session, on the
        person's own login rather than paid tokens, before the seats leave; the harness seats then leave, so no
        session outlives its table."""
        found = self.row()
        rows = store.submissions(self.store, self.number)
        reporter = str(self.ctx.setting('roundtable_reporter'))
        try:
            text = self.report(found, rows, reporter)
        except (seats.Silent, harness.Silent, harness.Gone) as error:
            self.unseat()
            told = said('report_failed', error=error)
            self.change(state='ended', ended=store.stamp(), report=None, report_error=told)
        else:
            self.unseat()
            path = Path('docs') / 'roundtables' / f'{self.number}-{found["subject"]}.md'
            (self.folder / path).parent.mkdir(parents=True, exist_ok=True)
            (self.folder / path).write_text(text.rstrip() + '\n', encoding='utf-8')
            self.change(state='ended', ended=store.stamp(), report=path.as_posix(), report_error=None)
            told = said('report_saved', path=path.as_posix())
        self.deliver()
        self.notice(said('chair_ended', discussion=self.number, reason=found['reason'] or '', report=told))
