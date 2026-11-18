"""A table's follower: one detached process for each table, `metaform roundtables run`, started by `open` and
`follow`, for as long as the table runs.

It holds one of dispatch's agent slots for each seat, through dispatch's own admission gate (`dispatch.seats`), so a
table and the project's tickets share one count, for as long as the table's seats run. A table it is given to open is
opened from here, so the slots are held before the engine starts a seat. A follower that stops before its table, on
SIGTERM or SIGHUP (the person's Stop all asks it so), on an error or when the engine's page server fails, ends its table
first, tells the person why, and follows it until the engine has closed its seats; only then do the slots go back. A
table the engine opened before the opening failed is found by the bridge's id it was opened under and ended the same
way, so no table runs unchaired or past its slots.

It follows the table through the engine's events stream (`engine.Page`). Each change names what moved, and the
follower reads only that: the turns after the last it told, the topic and stage, the stages' answers when a stage
answer was added, the operational events after the last it told, the state. Each thing it finds is one event of the
table, written to the project's `events` table with the cursor that says it was told, in one transaction, and then
published: on the bus as `roundtables.event`, and to every other process of the home as the `map.changed` of that
write, which names the kind `roundtables`. A follower started again goes on from the cursors, so nothing is told twice.

Operational events, credits, holds, a seat lost, degraded or back, are the person's: their audience is `person`, and
nothing of them goes to the table, its seats or Jev. At the end the table's record is saved in the project, its
answer is the host's summary of its last topic. The page receives every topic's synthesis and rankings with the
saved transcript, without waiting for another agent to write a report.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any, cast

from metaform import events, home, prompt_files
from metaform.data import Store
from metaform.module import Context, Stop, provided

from . import engine

PACKAGE = resources.files(__name__.rpartition('.')[0])
TOPIC = 'roundtables.event'
CHANGE_KIND = 'roundtables'  # what a follower's writes say they concern, on their map.changed
SEAT_LOST = frozenset({'seat_lost'})
DONE = ('ended',)
GONE = 'The engine no longer holds this table.'
RECORD = 'export.json'  # the table's whole record as the engine exports it, with the Borda count
REPORT = 'mechanical-report.md'  # the engine's text of the complete record


class Stopped(BaseException):
    """SIGTERM or SIGHUP: the follower asked to stop, by the person's Stop all or the end of its session."""


# the signals that stop the follower; Windows has no SIGHUP, and is read when the module is imported there
STOPS: tuple[signal.Signals, ...] = (signal.SIGTERM,) if sys.platform == 'win32' else (signal.SIGTERM, signal.SIGHUP)


def stopping(number: int, _frame: Any) -> None:
    """The first stop raises Stopped where the follower is; later ones are ignored, since it is ending its table
    already and gives the slots back once the engine has closed the seats."""
    for one in STOPS:
        signal.signal(one, signal.SIG_IGN)
    raise Stopped(f'The follower was stopped ({signal.Signals(number).name})')


def named(error: BaseException) -> str:
    """An error as the person reads it: a Stop's or a stop's own words, else its kind and text, the first of a group."""
    inner: tuple[BaseException, ...] = getattr(error, 'exceptions', None) or ()  # an exception group's
    while inner:
        error = inner[0]
        inner = getattr(error, 'exceptions', None) or ()
    if isinstance(error, Stop):
        return error.message
    if isinstance(error, Stopped):
        return str(error)
    return f'{type(error).__name__}: {error}' if str(error) else type(error).__name__


def now() -> str:
    return datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')


def release(paths: list[Any]) -> None:
    for path in paths:
        with contextlib.suppress(OSError):
            path.unlink()


def hold_seats(ctx: Context, table_id: str, count: int) -> list[Any]:
    """One agent slot for each seat, for this process's life, from dispatch's gate; refused when dispatch is off,
    since then nothing would count them."""
    found = [value for _, value in provided(ctx.folder, 'dispatch.seats')]
    if not found:
        raise Stop('Each seat at a table takes one of dispatch\'s agent slots, and dispatch is off, so nothing would '
                   'count them.', 'metaform enable dispatch')
    return cast(list[Any], found[0](str(ctx.project), f'roundtables-{table_id}', count))


class Follower:
    """One table followed from this process."""

    def __init__(self, ctx: Context, table_id: str) -> None:
        self.ctx, self.table_id = ctx, table_id
        self.store = ctx.require_store()
        row = self.row()
        if row is None:
            raise Stop(f'No roundtable {table_id} in this project.', 'metaform roundtables tables')
        self.followed: dict[str, Any] = dict(cast(dict[str, Any], row.get('followed') or {}))
        with self.store.tables(write=False) as tx:
            told = list(tx.rows('events', {'table_id': table_id}, limit=0).results)
        self.seq = max((int(one['seq']) for one in told), default=0)
        self.telling = threading.RLock()  # keep event writes, their cursors and publication in sequence

    def row(self) -> dict[str, Any] | None:
        with self.store.tables(write=False) as tx:
            found = tx.get('tables', {'table_id': self.table_id})
        return dict(found) if found is not None else None

    def concern(self, tx: Any) -> None:
        """What a write of this follower concerns, on its map.changed: the kind roundtables, and the table by a kind
        of its own, `roundtables:<table>`, so a page watching one table reads only for its own."""
        tx.concern(kind=CHANGE_KIND)
        tx.concern(kind=f'{CHANGE_KIND}:{self.table_id}')

    def change(self, **changes: Any) -> None:
        def write() -> None:
            with self.store.tables() as tx:
                self.concern(tx)
                if 'followed' in changes:
                    changes['followed'] = self.current_budget(tx, changes['followed'])
                tx.update('tables', {'table_id': self.table_id}, changes)
        with self.telling:
            events.announced(self.ctx.folder, 'cli', write)

    def current_budget(self, tx: Any, followed: dict[str, Any]) -> dict[str, Any]:
        """Preserve a chair's live edit when this detached follower writes its older in-memory cursors."""
        row = tx.get('tables', {'table_id': self.table_id})
        saved = cast(dict[str, Any], dict(row).get('followed') or {}) if row is not None else {}
        if row is not None and dict(row).get('token_budget') is not None:
            saved = {**saved, 'token_budget': row['token_budget']}
        if 'token_budget' in saved:
            self.followed['token_budget'] = saved['token_budget']
            return {**followed, 'token_budget': saved['token_budget']}
        return followed

    def emit(self, kind: str, audience: str = 'table', changes: dict[str, Any] | None = None,
             **payload: Any) -> None:
        """One event of the table: written with the cursors that say it was told and the table's changes, in one
        transaction, announced as that write's map.changed, then published as roundtables.event."""
        with self.telling:
            self.told(kind, audience, changes, payload)

    def told(self, kind: str, audience: str, changes: dict[str, Any] | None, payload: dict[str, Any]) -> None:
        self.seq += 1
        observed = now()
        event = {'table': self.table_id, 'seq': self.seq, 'kind': kind, 'audience': audience,
                 **payload, 'at': observed}

        def write() -> None:
            with self.store.tables() as tx:
                self.concern(tx)
                tx.insert('events', {'table_id': self.table_id, 'seq': self.seq, 'kind': kind, 'audience': audience,
                                     'payload': payload, 'at': observed})
                updated = {'followed': self.followed, **(changes or {})}
                updated['followed'] = self.current_budget(tx, updated['followed'])
                tx.update('tables', {'table_id': self.table_id}, updated)
        events.announced(self.ctx.folder, 'cli', write)
        self.ctx.publish(TOPIC, event)

    # ------------------------------------------------------------------ opening

    def opened(self, row: dict[str, Any]) -> dict[str, Any]:
        """The table opened by the engine from what `open` kept; the chair token and the engine's ids kept with it."""
        held = cast(dict[str, Any] | None, self.followed.get('session'))
        answer = engine.call(self.ctx.folder, 'open', seats=row['seats'], opening=row['opening'],
                             topics=[str(held['first']) if held else row['topic']],
                             subject=f'{self.table_id} {row["topic"]}'[:80], session=held,
                             spend=row['spend'], host=row['host'], synthesizer=row['synthesizer'],
                             reply_limit=self.followed.get('reply_limit', 512),
                             judging=self.followed.get('judging', True),
                             permissions=self.followed.get('permissions'),
                             token_budget=int(self.followed.get('token_budget') or 0),
                             token_basis=str(self.followed.get('token_basis') or 'all'),
                             folder=str(self.ctx.folder))
        a2a = cast(dict[str, Any], answer.get('a2a') or {})
        changes = {'discussion': int(answer['discussion']), 'chair': str(answer['chair']), 'state': 'running',
                   'context_id': a2a.get('context_id'), 'task_id': a2a.get('task_id'),
                   'seated': [one.get('name') for one in cast(list[dict[str, Any]], answer.get('seats') or [])]}
        self.change(**changes)
        return {key: answer[key] for key in ('seats', 'rounds', 'spend', 'reply_limit', 'host', 'synthesizer', 'notices')
                if key in answer}

    # ------------------------------------------------------------------ following

    def follow(self, page: engine.Page, number: int) -> None:
        last: dict[str, Any] = {}
        for now_ in page.changes(number):
            self.moved(page, number, last, now_)
            last = now_
            if now_.get('state') in DONE and (now_.get('report') or now_.get('runner') == 'stopped'):
                self.ended(page, number)
                return
        self.emit('state', 'person', changes={'state': 'held', 'reason': GONE, 'follower': None},
                  state='held', reason=f'{GONE} Restore its saved engine record before continuing.')

    def followed_to_end(self, number: int) -> None:
        """The table followed to its end on a page server of this follower's; a stop or an error before then winds it
        up."""
        page: engine.Page | None = None
        try:
            page = engine.Page(self.ctx.folder, engine.folder_log() / f'page-{self.table_id}.log')
            self.follow(page, number)
            return
        except Stopped as error:
            why = named(error)
        except Exception as error:  # noqa: BLE001  a stream failure holds discussion rather than completing it
            why = named(error)
            engine.call(self.ctx.folder, 'hold', discussion=number, chair=(self.row() or {}).get('chair'))
            self.emit('operational', 'person', changes={'state': 'held', 'reason': why},
                      what='follower_stopped', text=f'{why}. Discussion is held. Continue restarts following.')
            recovery = engine.Page(self.ctx.folder, engine.folder_log() / f'page-{self.table_id}.log')
            try:
                # Admission stays reserved until the held runner has closed all participant processes.
                last: dict[str, Any] = {}
                for snapshot in recovery.changes(number):
                    self.moved(recovery, number, last, snapshot)
                    last = snapshot
                    if snapshot.get('state') in DONE and (snapshot.get('report') or snapshot.get('runner') == 'stopped'):
                        self.ended(recovery, number)
                        break
                    if snapshot.get('state') == 'held' and snapshot.get('runner') == 'stopped':
                        break
            finally:
                recovery.close()
            return
        finally:
            if page is not None:
                page.close()
        self.wound_up(number, why)

    def wound_up(self, number: int, why: str, page: engine.Page | None = None) -> None:
        """The follower stops before its table: the person told why, the table ended through a page server of its own,
        and followed until the engine has closed its seats, so its slots go back only then. When no page server
        starts, the table is ended with its chair token, and the slots go back with the follower."""
        self.emit('operational', 'person', what='follower_stopped',
                  text=f'{why}. The table is ended, so its seats stop.')
        try:
            page = page or engine.Page(self.ctx.folder, engine.folder_log() / f'page-{self.table_id}.log')
        except Stop:
            chair = (self.row() or {}).get('chair')
            if chair:
                engine.call(self.ctx.folder, 'end', discussion=number, chair=chair)
            raise
        try:
            page.chair(number, 'end')
            self.follow(page, number)
        finally:
            page.close()

    def unchaired(self, why: str) -> None:
        """A table the engine opened before the opening failed, found by the bridge's id its subject begins with, is
        ended and followed to its end; none, and nothing is left to do."""
        page = engine.Page(self.ctx.folder, engine.folder_log() / f'page-{self.table_id}.log')
        try:
            listed = cast(list[dict[str, Any]], cast(dict[str, Any], page.get('/tables'))['tables'])
            found = next((one for one in listed if str(one.get('subject') or '') == self.table_id
                          or str(one.get('subject') or '').startswith(f'{self.table_id}-')), None)
        except BaseException:
            page.close()
            raise
        if found is None:
            page.close()
            return
        self.change(discussion=int(found['number']))
        self.wound_up(int(found['number']), why, page)

    def moved(self, page: engine.Page, number: int, last: dict[str, Any], now_: dict[str, Any]) -> None:
        """What one change of the table moved, read and told: only the parts the change says moved."""
        if int(now_.get('latest') or 0) > int(self.followed.get('turns') or 0):
            self.turns(page, number)
        if now_.get('topic_selection') != last.get('topic_selection'):
            self.emit('topic_selection', 'person', progress=now_.get('topic_selection'))
        place = [now_.get('topic'), now_.get('stage')]
        if now_.get('stage') and place != self.followed.get('place'):
            self.followed['place'] = place
            self.emit('stage', topic=int(now_.get('topic') or 0) + 1, stage=now_.get('stage'))
        if now_.get('staged') != last.get('staged') and now_.get('staged'):
            self.staged(page, number)
        if now_.get('events') != last.get('events') and now_.get('events'):
            self.operational(page, number)
        if now_.get('state') != self.followed.get('state'):
            self.followed['state'] = now_.get('state')
            self.emit('state', 'person', changes={'state': now_.get('state'), 'reason': now_.get('reason')},
                      state=now_.get('state'), reason=now_.get('reason'))

    def turns(self, page: engine.Page, number: int) -> None:
        found = cast(dict[str, Any], page.get(f'/tables/{number}/turns', since=int(self.followed.get('turns') or 0)))
        latest = int(found.get('latest') or 0)
        for row in cast(list[dict[str, Any]], found.get('turns') or []):
            if int(row['n']) > latest or row.get('outcome') == 'unjudged':
                continue  # judged later, and told then
            self.followed['turns'] = int(row['n'])
            self.emit('veto' if row.get('outcome') == 'vetoed' else 'turn', **{key: row[key] for key in (
                'n', 'message_id', 'turn', 'topic', 'round', 'seat', 'outcome', 'scores', 'failed', 'veto_reason',
                'text', 'truncated', 'created')
                if key in row})
        self.followed['turns'] = max(latest, int(self.followed.get('turns') or 0))

    def unjudged(self, page: engine.Page, number: int) -> None:
        """An ended table's last submission, which Jev never judged: the engine lists it last, unjudged, once the
        table ends, and it is told then, once."""
        since = max(int(self.followed.get('turns') or 0), int(self.followed.get('unjudged') or 0))
        found = cast(dict[str, Any], page.get(f'/tables/{number}/turns', since=since))
        for row in cast(list[dict[str, Any]], found.get('turns') or []):
            if row.get('outcome') == 'unjudged' and int(row['n']) > since:
                self.followed['unjudged'] = int(row['n'])
                self.emit('turn', **{key: row[key] for key in (
                    'n', 'message_id', 'turn', 'topic', 'round', 'seat', 'outcome', 'failed', 'text', 'truncated',
                    'created')
                    if key in row})

    def staged(self, page: engine.Page, number: int) -> None:
        """The stages' answers told once each: a topic's ideas, its rankings as they come, its host's summary."""
        seen = cast(dict[str, dict[str, Any]], self.followed.setdefault('topics', {}))
        for topic in cast(list[dict[str, Any]], cast(dict[str, Any], page.get(f'/tables/{number}/topics'))['topics']):
            held = seen.setdefault(str(topic['number']), {'ideas': False, 'rankings': 0, 'summary': False})
            synthesis = cast(dict[str, Any] | None, topic.get('synthesis'))
            if synthesis and synthesis.get('ideas') and not held['ideas']:
                held['ideas'] = True
                self.emit('ideas', topic=topic['number'], title=topic.get('title'), ideas=synthesis['ideas'])
            rankings = cast(list[dict[str, Any]], topic.get('rankings') or [])
            if len(rankings) > int(held['rankings']):
                fresh = rankings[int(held['rankings']):]
                held['rankings'] = len(rankings)
                self.emit('rankings', topic=topic['number'],
                          rankings=[{'name': one.get('name'), 'ranking': one.get('ranking')} for one in fresh])
            summary = cast(dict[str, Any] | None, topic.get('host_summary'))
            if summary and summary.get('text') and not held['summary']:
                held['summary'] = True
                self.emit('summary', topic=topic['number'], name=summary.get('name'), text=summary['text'])

    def operational(self, page: engine.Page, number: int) -> None:
        """The engine's operational events after the last told, each the person's: never the table's or Jev's."""
        found = cast(dict[str, Any], page.get(f'/tables/{number}'))
        after = int(self.followed.get('events') or 0)
        for one in cast(list[dict[str, Any]], found.get('events') or []):
            if int(one['number']) <= after:
                continue
            self.followed['events'] = int(one['number'])
            timestamp = {'created': one['created']} if one.get('created') else {}
            if one.get('kind') == 'permission':
                payload = json.loads(str(one['text']))
                self.emit('permission', 'person', **{**timestamp, **payload})
                continue
            if one.get('kind') == 'budget':
                notice = cast(dict[str, Any], json.loads(str(one['text'])))
                self.emit('operational', 'person', what='budget', text=notice['text'], budget=notice, **timestamp)
                continue
            self.emit('seat_lost' if one.get('kind') in SEAT_LOST else 'operational', 'person', what=one.get('kind'),
                      text=one.get('text'), **timestamp, **({'seat': one['seat']} if one.get('seat') else {}))

    def ended(self, page: engine.Page, number: int) -> None:
        """Save the complete result before publishing its end, so the page can show it immediately or on return."""
        self.unjudged(page, number)
        found = cast(dict[str, Any], page.get(f'/tables/{number}'))
        if str(found.get('reason') or '').lower().startswith('abort'):
            self.change(state='ended', reason=found.get('reason'), follower=None)
            return
        listed = cast(list[dict[str, Any]], cast(dict[str, Any], page.get(f'/tables/{number}/topics'))['topics'])
        summaries = [cast(dict[str, Any], one['host_summary']) for one in listed if one.get('host_summary')]
        answer = str(summaries[-1].get('text') or '') if summaries else ''
        saved = self.saved(page, number)
        recorded, unrecorded = self.recorded(listed, answer, saved)
        self.followed['result_topics'] = listed
        self.emit('end', 'person', changes={'state': 'ended', 'reason': found.get('reason'), 'answer': answer or None,
                                            'answered': bool(answer), 'ended': now(), 'follower': None},
                  reason=found.get('reason'), answered=bool(answer), answer=answer or None, saved=saved,
                  topics=listed, recorded=recorded, **({'unrecorded': unrecorded} if unrecorded else {}))

    def saved(self, page: engine.Page, number: int) -> str:
        """Save only accepted messages and public results in the shared project, leaving the owner's engine audit
        intact. A follower started again keeps its saved folder; existing project artifacts are never replaced."""
        if self.followed.get('saved') and not self.followed.get('refresh_record'):
            return str(self.followed['saved'])
        from .roundtable import export

        exported = cast(dict[str, Any], page.get(f'/tables/{number}/download/export.json'))
        shared = export.safe_shared(exported)
        record_text = json.dumps(shared, indent=2, ensure_ascii=False) + '\n'
        report_text = export.shared_mechanical(shared)
        root = Path(self.store.project().path)
        topic = str((self.row() or {}).get('topic') or '')
        folder = root / 'docs' / 'roundtables' / f'{number}-{slug(topic)}'
        if self.followed.get('continuations'):
            folder /= f'continuation-{self.followed["continuations"]}'
        if not folder.resolve().is_relative_to(root.resolve()):
            raise Stop('The shared record folder is outside the project.', 'choose a project-local record folder')
        if (folder / RECORD).exists() or (folder / REPORT).exists():
            import tempfile

            try:
                same = (folder / RECORD).read_bytes() == record_text.encode('utf-8') and \
                    (folder / REPORT).read_bytes() == report_text.encode('utf-8')
            except OSError:
                same = False
            if same:
                self.followed['saved'] = folder.relative_to(root).as_posix()
                self.followed['refresh_record'] = False
                return str(self.followed['saved'])
            folder.mkdir(parents=True, exist_ok=True)
            folder = Path(tempfile.mkdtemp(prefix='record-', dir=folder))
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / REPORT).open('x', encoding='utf-8') as report:
            report.write(report_text)
        with (folder / RECORD).open('x', encoding='utf-8') as record:
            record.write(record_text)
        self.followed['saved'] = folder.relative_to(root).as_posix()
        self.followed['refresh_record'] = False
        return str(self.followed['saved'])

    def recorded(self, listed: list[dict[str, Any]], answer: str, saved: str) -> tuple[str | None, str | None]:
        """The table's outcome kept as one memory, memory's own write through `memory.record`, at the part the table
        was about, or at the project's top element when it was about none: the question, the host's answer, the
        top-ranked ideas and why the seats ranked them, and the saved record it cites. Written once; the memory's
        name, or None and why when memory is off, the map holds no element or memory refused it."""
        if self.followed.get('recorded'):
            return str(self.followed['recorded']), None
        found = [value for _, value in provided(self.ctx.folder, 'memory.record')]
        if not found:
            return None, 'memory is off here, so the outcome is kept only with the table'
        row = self.row() or {}
        address = str(row.get('address') or '') or top_element(self.store)
        if not address:
            return None, 'the map holds no element yet, so the outcome is kept only with the table'
        entity = outcome(self.table_id, str(row.get('topic') or ''), listed, answer, saved)
        try:
            events.announced(self.ctx.folder, 'cli', found[0], self.ctx, address, [entity])
        except Stop as refused:
            return None, refused.message
        self.followed['recorded'] = entity['name']
        return entity['name'], None

def top_element(store: Store) -> str | None:
    """The project's top element, where a table about no part keeps what it leaves on the map: its DE, else its first
    root element; None while the map holds none. A project held in the project store has its top element there."""
    from . import stored
    name = stored.held(store.project_id)
    if name is not None:
        return stored.top(name)
    roots = store.roots(limit=1)
    found = next((entry.element for entry in roots.entry if entry.element.role == 'DE'), None) \
        or next((entry.element for entry in roots.entry), None) or next(iter(roots.elements), None)
    return None if found is None else found.address


def slug(topic: str) -> str:
    """The topic as a folder's name: lower case words joined by hyphens, at most 60 characters."""
    return re.sub(r'[^a-z0-9]+', '-', topic.lower()).strip('-')[:60].rstrip('-') or 'table'


def quoted(text: str) -> str:
    """Text quoted whole, in the first quotation marks it does not hold, so memory reads it as one statement."""
    held = text.strip()
    for opening, closing in (('"', '"'), ('“', '”'), ('`', '`')):
        if opening not in held and closing not in held:
            return f'{opening}{held}{closing}'
    return '"' + held.replace('"', '”') + '"'


def outcome(table_id: str, question: str, listed: list[dict[str, Any]], answer: str, saved: str) -> dict[str, Any]:
    """The memory of a table's outcome, one fact to each observation: what it was asked, what its host answered, its
    top three ideas by the Borda count over the seats' rankings, each seat's explanation of its top three, where its
    record is saved, which it cites."""
    said: list[str] = [prompt_files.required(PACKAGE, 'outcome_question', question=quoted(question))]
    host = next((cast(dict[str, Any], one['host_summary']) for one in reversed(listed) if one.get('host_summary')),
                None)
    said.append(prompt_files.required(PACKAGE, 'outcome_answer', host=str(host.get('name') or 'the host'),
                                      answer=quoted(answer)) if host and answer else
                prompt_files.required(PACKAGE, 'outcome_unanswered'))
    topic = next((one for one in reversed(listed) if one.get('synthesis')), None)
    if topic is not None:
        ideas = {str(one['id']): one for one in cast(list[dict[str, Any]], topic['synthesis'].get('ideas') or [])}
        borda = cast(dict[str, Any], topic.get('borda') or {})
        points = cast(dict[str, Any], borda.get('points') or {})
        for rank, idea in enumerate(cast(list[str], borda.get('order') or [])[:3], 1):
            if idea in ideas:
                said.append(prompt_files.required(
                    PACKAGE, 'outcome_idea', idea=idea, called=quoted(str(ideas[idea].get('name') or idea)),
                    rank=str(rank), of=str(len(ideas)), points=str(points.get(idea, 0)),
                    substance=quoted(str(ideas[idea].get('summary') or ideas[idea].get('name') or idea))))
        for one in cast(list[dict[str, Any]], topic.get('top_three') or []):
            if str(one.get('text') or '').strip():
                said.append(prompt_files.required(PACKAGE, 'outcome_why', seat=str(one.get('name') or 'a seat'),
                                                  why=quoted(str(one['text']))))
    record = f'{saved}/{RECORD}'
    said.append(prompt_files.required(PACKAGE, 'outcome_record', record=f'`{record}`', files=f'`{saved}`'))
    return {'name': f'Roundtable {table_id}: {question.strip()[:100]}', 'entityType': 'roundtable',
            'title': prompt_files.required(PACKAGE, 'outcome_title', question=question.strip())[:200],
            'why': prompt_files.required(PACKAGE, 'outcome_kept'), 'observations': said, 'cite': [record]}


def run(ctx: Context, table_id: str) -> dict[str, Any]:
    """The follower's whole life: hold the seats' slots, open the table when it is to be opened, say so on the first
    line of standard output for the `open` waiting on it, then follow the table to its end and give the slots back."""
    for one in STOPS:
        signal.signal(one, stopping)
    follower = Follower(ctx, table_id)
    row = follower.row() or {}
    seats = list(cast(list[str], row.get('seats') or []))
    held: list[Any] = []
    try:
        try:
            held = hold_seats(ctx, table_id, len(seats))
            follower.change(follower=os.getpid())
            if row.get('state') == 'continuing':
                # Keep every prior artifact at its existing path. A later completion writes a fresh revision folder.
                if follower.followed.get('continue_from') == 'ended':
                    follower.followed['previous_results'] = [*follower.followed.get('previous_results', []),
                        {key: row.get(key) for key in ('answer', 'answered', 'ended')} |
                        {key: follower.followed.get(key) for key in ('saved', 'result_topics')}]
                    follower.followed['refresh_record'] = True
                    follower.followed['continuations'] = int(follower.followed.get('continuations', 0)) + 1
                    follower.change(followed=follower.followed)
                answer = engine.call(ctx.folder, 'continue', discussion=int(row['discussion']), chair=row['chair'],
                                     spend=follower.followed.get('continue_spend'))
                follower.followed['state'] = answer.get('state')
                follower.emit('state', 'person', changes={'state': answer.get('state'), 'ended': None},
                              state=answer.get('state'), reason=None)
                told = {'continued': table_id}
            else:
                told = follower.opened(row) if row.get('state') == 'opening' else {}
        except Stop as refused:
            reason = f'The table did not open: {refused.message}' if row.get('state') == 'opening' else refused.message
            if row.get('state') in ('opening', 'continuing'):
                follower.change(state=str(follower.followed.get('continue_from') or 'held')
                                if row.get('state') == 'continuing' else 'refused',
                                reason=reason, follower=None)
            say({'refused': reason, 'next': refused.next_step})
            return {'refused': reason}
        except (Exception, Stopped) as error:  # noqa: BLE001  any other failure refuses the opening and says why
            reason = (f'The table did not open: {named(error)}. The engine\'s log is in the Metaform home under '
                      'run/roundtables/engine.log.')
            if row.get('state') == 'opening':
                follower.change(state='refused', reason=reason, follower=None)
            elif row.get('state') == 'continuing':
                follower.change(state='held', reason=reason, follower=None)
            say({'refused': reason, 'next': f'metaform roundtables status {table_id}'})
            if row.get('state') == 'opening' and held:  # the engine may have opened it before the failure
                follower.unchaired(reason)
            return {'refused': reason}
        say({'opened': table_id, **told})
        follower.followed_to_end(int((follower.row() or {})['discussion']))
        return {'followed': table_id}
    finally:
        release(held)
        with contextlib.suppress(Exception):
            if (follower.row() or {}).get('follower') == os.getpid():
                follower.change(follower=None)
        if (follower.row() or {}).get('state') == 'ended':
            if follower.followed.get('session'):
                session_ended(ctx, follower)
            else:
                from . import pipeline
                events.announced(ctx.folder, ctx.surface, pipeline.prepare, ctx, table_id)


def archive(ctx: Context, row: dict[str, Any], engine_archive: str | None) -> Path:
    """Abort archives the run's records and files, then removes its live bridge rows."""
    table_id = str(row['table_id'])
    follower = row.get('follower')
    # ps, process groups and a probe by signal 0, which Windows reads as an end: roundtables run on POSIX alone
    if sys.platform != 'win32':
        if isinstance(follower, int) and follower != os.getpid() and alive(follower):
            # One process-tree snapshot includes the follower's separate ACP and page process groups.
            processes = subprocess.run(['ps', '-eo', 'pid=,ppid=,args='], capture_output=True, text=True, check=False)
            entries = [line.strip().split(None, 2) for line in processes.stdout.splitlines()]
            rows = {int(one[0]): (int(one[1]), one[2]) for one in entries if len(one) == 3}
            command = rows.get(follower, (0, ''))[1]
            if f'roundtables run {table_id}' in command:
                selected = {follower}
                for _ in range(len(rows)):
                    children = {pid for pid, (parent, _) in rows.items() if parent in selected}
                    if children <= selected:
                        break
                    selected.update(children)
                for pid in sorted(selected, reverse=True):
                    with contextlib.suppress(ProcessLookupError, OSError):
                        os.kill(pid, signal.SIGKILL)
    store = ctx.require_store()
    root = Path(store.project().path)
    shelf = home.home() / 'backups' / 'roundtables' / f'{table_id}-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}'
    home.mkdir_private(shelf)
    with store.tables(write=False) as tx:
        saved_events = [dict(one) for one in tx.rows('events', {'table_id': table_id}, limit=0).results]
        summary = tx.get('live_summaries', {'table_id': table_id})
    (shelf / 'table.json').write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (shelf / 'events.json').write_text(json.dumps(saved_events, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if summary is not None:
        (shelf / 'live-summary.json').write_text(
            json.dumps(dict(summary), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if row.get('discussion') is not None:
        from .roundtable import export as engine_export
        from .roundtable import store as engine_store
        with contextlib.suppress(engine_store.Missing):
            exported = engine_export.build(int(row['discussion']))
            (shelf / 'engine-export.json').write_text(
                json.dumps(exported, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    followed = cast(dict[str, Any], row.get('followed') or {})
    session = cast(dict[str, Any], followed.get('session') or {})
    paths = [Path(str(session['folder']))] if session.get('folder') else []
    if followed.get('saved'):
        paths.append(root / str(followed['saved']))
    if row.get('discussion') is not None:
        paths.append(root / 'docs' / 'roundtables' / f'{row["discussion"]}-notes')
    if engine_archive:
        paths.append(Path(engine_archive))
    for source in dict.fromkeys(paths):
        if source.exists():
            destination = shelf / ('engine' if engine_archive and source == Path(engine_archive) else source.name)
            shutil.move(str(source), str(destination))

    def remove() -> None:
        with store.tables() as tx:
            tx.concern(kind=CHANGE_KIND)
            tx.concern(kind=f'{CHANGE_KIND}:{table_id}')
            tx.delete('events', {'table_id': table_id})
            tx.delete('live_summaries', {'table_id': table_id})
            tx.delete('tables', {'table_id': table_id})
    events.announced(ctx.folder, ctx.surface, remove)
    return shelf



def session_ended(ctx: Context, follower: Follower) -> None:
    """A session ended, not aborted: its folder zipped beside it and pushed on a branch of its own, once; a failure
    is told to the person and never undoes the ended session."""
    held = cast(dict[str, Any] | None, follower.followed.get('session'))
    if not held or follower.followed.get('pushed'):
        return
    if str((follower.row() or {}).get('reason') or '').startswith('aborted'):
        return
    follower.followed['pushed'] = True
    follower.change(followed=follower.followed)
    from . import chain
    try:
        branch = chain.pushed(Path(ctx.require_store().project().path), Path(str(held['folder'])))
        follower.emit('operational', 'person', what='session', text=f'The session was pushed on the branch {branch}.')
    except (Stop, OSError) as error:
        why = error.message if isinstance(error, Stop) else named(error)
        follower.emit('operational', 'person', what='session', text=f'The session was not pushed: {why}')


def say(answer: dict[str, Any]) -> None:
    """The first line of standard output, which the `open` or `follow` that started this process reads; standard
    output then goes to the follower's log, so the waiting call is answered at once."""
    import json
    sys.stdout.flush()
    os.write(1, (json.dumps(answer) + '\n').encode('utf-8'))
    log = os.open(engine.folder_log() / 'followers.log', os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    os.dup2(log, 1)
    os.close(log)


def alive(pid: Any) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
