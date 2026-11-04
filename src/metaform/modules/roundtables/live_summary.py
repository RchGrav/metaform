"""A web-owned Haiku observer, separate from the follower and participants' shared documents."""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import sys
import threading
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any, cast

from metaform import events, home, prompt_files
from metaform.module import Context

from . import engine
from .roundtable.harness import Session

PACKAGE = resources.files(__name__.rpartition('.')[0])
ACTIVE = frozenset({'opening', 'continuing', 'running', 'held', 'ending'})
SUMMARY_WAIT = 300.0


def now() -> str:
    return datetime.now(UTC).isoformat(timespec='seconds')


def aborted(row: dict[str, Any]) -> bool:
    return str(row.get('reason') or '').lower().startswith('abort')


def snapshot(ctx: Context, table_id: str) -> dict[str, Any]:
    """The person's current summary, with a cursor independent of the follower's events."""
    with ctx.require_store().tables(write=False) as tx:
        row = tx.get('live_summaries', {'table_id': table_id})
        table = tx.get('tables', {'table_id': table_id})
    saved = dict(row) if row is not None else {}
    paused = table is not None and aborted(dict(table))
    return {'state': 'paused' if paused else saved.get('state') or 'idle', 'text': saved.get('text') or '',
            'through_seq': int(saved.get('through_seq') or 0), 'updated': saved.get('updated'),
            'error': saved.get('error'), 'permissions': [] if paused else saved.get('permissions') or []}


def answer(ctx: Context, table_id: str, request: str, option: str) -> dict[str, Any] | None:
    """Recognize an auxiliary request and answer through the engine's standard permission relay."""
    if not any(one.get('request') == request for one in snapshot(ctx, table_id)['permissions']):
        return None
    with ctx.require_store().tables(write=False) as tx:
        row = tx.get('tables', {'table_id': table_id})
    if row is None or row['discussion'] is None:
        return None
    return engine.call(ctx.folder, 'permit', discussion=int(row['discussion']), request=request, option=option)


class Background:
    """One project observer. A blocking OS lock prevents duplicate writers during web handover."""

    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.store = ctx.require_store()
        self.closed = threading.Event()
        self.lock = threading.RLock()
        self.pending: set[str] = set()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.wake: asyncio.Event | None = None
        self.task: asyncio.Task[None] | None = None
        self.current: str | None = None
        self.attempted: dict[str, int] = {}
        self.thread = threading.Thread(target=self.run, name=f'roundtable summaries {ctx.project}', daemon=True)
        self.thread.start()

    def heard(self, payload: dict[str, Any]) -> None:
        """Ignore unrelated changes and our own snapshots before opening the database."""
        if payload.get('project') != self.ctx.project:
            return
        tables = payload.get('tables')
        if isinstance(tables, list) and tables and all(one == 'roundtables.live_summaries'
                                                      for one in cast(list[Any], tables)):
            return
        ids = {str(one).split(':', 1)[1] for one in payload.get('kinds', [])
               if str(one).startswith('roundtables:') and str(one).count(':') == 1}
        if not ids:
            return
        with self.lock:
            if self.closed.is_set():
                return
            self.pending.update(ids)
            loop, wake, task, current = self.loop, self.wake, self.task, self.current
        if loop is not None and wake is not None:
            with contextlib.suppress(RuntimeError):  # the service may have closed since taking its loop
                loop.call_soon_threadsafe(wake.set)
        if task is not None and current in ids:
            with self.store.tables(write=False) as tx:
                row = tx.get('tables', {'table_id': str(current)})
            if (row is None or aborted(dict(row))) and loop is not None:
                with contextlib.suppress(RuntimeError):
                    loop.call_soon_threadsafe(task.cancel)

    def write(self, table_id: str, **changes: Any) -> bool:
        """A late model response cannot recreate a table that Abort removed."""
        def saved() -> bool:
            with self.store.tables() as tx:
                parent = tx.get('tables', {'table_id': table_id})
                if parent is None or aborted(dict(parent)):
                    return False
                tx.concern(kind='roundtables')
                tx.concern(kind=f'roundtables:{table_id}')
                key = {'table_id': table_id}
                if tx.get('live_summaries', key) is None:
                    tx.insert('live_summaries', {**key, **changes})
                else:
                    tx.update('live_summaries', key, changes)
            return True
        return bool(events.announced(self.ctx.folder, self.ctx.surface, saved)[0])

    def permission(self, table_id: str, payload: dict[str, Any]) -> None:
        with self.store.tables(write=False) as tx:
            row = tx.get('live_summaries', {'table_id': table_id})
        given = cast(list[dict[str, Any]], row['permissions'] or []) if row is not None else []
        kept = [one for one in given if one.get('request') != payload['request'] and one.get('state') == 'waiting']
        self.write(table_id, permissions=[*kept, {**payload, 'name': 'Live summary'}])

    def run(self) -> None:
        name = hashlib.sha256(str(self.ctx.project).encode()).hexdigest()[:24]
        lease = home.home() / 'run' / 'roundtables' / f'live-summary-{name}.lock'
        try:
            lease.parent.mkdir(parents=True, exist_ok=True)
            with home.file_lock(lease):
                if not self.closed.is_set():
                    asyncio.run(self.observe())
        except Exception as error:  # noqa: BLE001  observer failure never interrupts participants
            sys.stderr.write(f'Roundtable live summary observer: {type(error).__name__}: {error}\n')

    async def observe(self) -> None:
        with self.lock:
            self.loop = asyncio.get_running_loop()
            self.wake = asyncio.Event()
        try:
            with self.store.tables(write=False) as tx:
                active = [str(row['table_id']) for row in tx.rows('tables', limit=0).results
                          if row['state'] in ACTIVE and row['discussion'] is not None and not aborted(dict(row))]
            with self.lock:
                self.pending.update(active)
            while not self.closed.is_set():
                with self.lock:
                    table_id = self.pending.pop() if self.pending else None
                    wake = self.wake
                assert wake is not None
                if table_id is None:
                    await wake.wait()
                    wake.clear()
                    continue
                task = asyncio.create_task(self.summarize(table_id))
                with self.lock:
                    self.task, self.current = task, table_id
                try:
                    await task
                except asyncio.CancelledError:
                    if self.closed.is_set():
                        return
                finally:
                    with self.lock:
                        self.task, self.current = None, None
        finally:
            with self.lock:
                self.loop, self.wake = None, None

    async def summarize(self, table_id: str) -> None:
        with self.store.tables(write=False) as tx:
            row = tx.get('tables', {'table_id': table_id})
            prior = tx.get('live_summaries', {'table_id': table_id})
            if row is None or row['discussion'] is None or aborted(dict(row)) or \
                    row['state'] not in ACTIVE and prior is None:
                return
            records = [dict(one) for one in tx.rows('events', {'table_id': table_id}, limit=0).results]
        saved = dict(prior) if prior is not None else {}
        through = int(saved.get('through_seq') or 0)
        latest = max((int(one['seq']) for one in records), default=0)
        if latest <= max(through, self.attempted.get(table_id, 0)):
            return
        topic = next((cast(dict[str, Any], one['payload']).get('topic') for one in reversed(records)
                      if one['kind'] in ('turn', 'veto', 'stage') and
                      cast(dict[str, Any], one['payload']).get('topic') is not None), None)
        lines: list[str] = []
        substantive = False
        for record in records:
            payload = cast(dict[str, Any], record['payload'])
            if int(record['seq']) <= through or topic is not None and payload.get('topic') not in (None, topic):
                continue
            if record['kind'] == 'stage':
                lines.append(f'[Topic {payload.get("topic", "")}, stage {payload.get("stage", "discussion")}]')
            elif record['kind'] in ('turn', 'veto'):
                text = str(payload.get('text') or '').strip()
                if not text or payload.get('outcome') in ('pass', 'none') or text.strip(' .!').upper() == 'PASS':
                    continue
                substantive = True
                vetoed = ' (vetoed proposal)' if record['kind'] == 'veto' else ''
                lines.append(f'{payload.get("seat", "Speaker")}{vetoed}: {text}')
        self.attempted[table_id] = latest
        if not substantive:
            await asyncio.to_thread(self.write, table_id, through_seq=latest)
            return
        session: Session | None = None
        try:
            if not await asyncio.to_thread(self.write, table_id, state='working', error=None):
                return
            if self.closed.is_set():
                return
            root = Path(self.store.project().path)
            followed = cast(dict[str, Any], row['followed'] or {})
            shared = cast(dict[str, Any], followed.get('session') or {})
            folder = str(shared.get('folder') or root / 'docs' / 'roundtables' / f'{row["discussion"]}-notes')
            taste = ''
            with contextlib.suppress(OSError, UnicodeError):
                taste = (root / 'docs' / 'taste.md').read_text(encoding='utf-8').strip()
            system = prompt_files.required(PACKAGE, 'live_summary_system',
                                           taste=taste or prompt_files.required(PACKAGE, 'minutes_taste_default'))
            asked = prompt_files.required(PACKAGE, 'live_summary_turn', project=str(root), session_folder=folder,
                                          question=str(row['topic']), previous=str(saved.get('text') or ''),
                                          turns='\n\n'.join(lines))
            choices = cast(dict[str, Any], followed.get('permissions') or {})
            command = engine.environment(self.ctx.folder).get('ROUNDTABLE_AGENT_CLAUDE')
            session = Session(int(row['discussion']), {'position': -4, 'agent': 'claude', 'model': 'haiku'}, str(root),
                              permission_settings=cast(dict[str, str], choices.get('claude') or {}), command=command,
                              permission_event=lambda payload: self.permission(table_id, payload))
            await session.start()
            text, used = await session.prompt(f'{system}\n\n{asked}', SUMMARY_WAIT)
            if self.closed.is_set():
                return
            if not text.strip():
                raise ValueError('Haiku returned an empty live summary.')
            usage = cast(dict[str, Any], saved.get('usage') or {})
            total = {**usage, **used, **{key: (usage.get(key) or 0) + value for key, value in used.items()
                                        if isinstance(value, (int, float)) and not isinstance(value, bool)}}
            await asyncio.to_thread(self.write, table_id, text=text.strip(), through_seq=latest,
                                    state='ready', error=None, updated=now(), usage=total)
        except asyncio.CancelledError:
            await asyncio.to_thread(self.write, table_id, state='paused')
            raise
        except Exception as error:  # noqa: BLE001  keep the last useful summary on failure
            await asyncio.to_thread(self.write, table_id, state='error', error=f'{type(error).__name__}: {error}')
        finally:
            if session is not None:
                await session.close()

    def close(self) -> None:
        self.closed.set()
        with self.lock:
            loop, wake, task = self.loop, self.wake, self.task
        if loop is not None:
            with contextlib.suppress(RuntimeError):
                if task is not None:
                    loop.call_soon_threadsafe(task.cancel)
                if wake is not None:
                    loop.call_soon_threadsafe(wake.set)
        if self.thread is not threading.current_thread():
            self.thread.join(12)


def start(ctx: Context) -> Background | None:
    return Background(ctx) if ctx.setting('roundtables_live_summary') else None
