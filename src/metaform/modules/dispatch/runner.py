"""runner: one ACP session for one ticket, BASE-052, run by `metaform dispatch run`.

Metaform is the ACP client. A runner started on a ticket with an agent glyph, VIEW-040, works the glyph's tickets one
after another in board order, a session for each, the next taken when the one before is done. The agent's ACP adapter runs as a child process in its own process group, in the
project's folder, with the person's environment unchanged; ACP goes over its standard input and output as bytes,
through the official SDK, `acp`. The runner listens on a loopback port for `message` and `stop`, and hears each
`map.changed` published in another process through the base's listener, QUAL-015 and BASE-053.

A question the agent asks itself, with `map ask` through the MCP server or the command line, is known by its id in
the output of the agent's own tool call, made no earlier than that call began, so a question it only read is not
taken for its own. When the person answers it, the agent is told the answer as a prompt.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import secrets
import signal
import subprocess
import sys
import time
from collections import deque
from collections.abc import Callable, Coroutine
from importlib import metadata
from typing import Any, cast

import acp
from acp.schema import (
    AllowedOutcome,
    ClientCapabilities,
    DeniedOutcome,
    FileSystemCapabilities,
    Implementation,
    McpServerStdio,
    PermissionOption,
    RequestPermissionResponse,
    ToolCallUpdate,
)

from metaform import axiom, nonce
from metaform.data import Message, Node, Store, WorkRecord
from metaform.module import Context, Stop

from . import (
    AGENTS,
    READS,
    REPLY_LIMIT,
    agent_named,
    argv,
    end_group,
    glyph_of,
    group_options,
    next_ticket,
    prompt,
    questions,
    release,
    require_eligible,
    startable,
    ticket,
)

START_LIMIT = 300.0  # the one wait for the agent to start and make its session; npx may download it first
END_LIMIT = 10.0  # the one wait for a cancelled turn to end, and for the agent to end once its input is closed
LINE_LIMIT = 64 * 1024 * 1024  # the longest line read from the agent
CHUNKS = ('agent_message_chunk', 'agent_thought_chunk', 'user_message_chunk')
STREAM_EVERY = 0.4  # seconds between writes of text still being written, so the page shows it as it grows
LINES_EVERY = 0.25  # at most one `dispatch.lines` event per this many seconds; the rows are written at once
IDS = re.compile(r'\b[0-9a-f]{32}\b')  # a message id, as a tool call's output shows it
TERMINATED = 'the runner was terminated'  # how a session ends on SIGTERM; its runner takes no next ticket
RELEASE_LIMIT = 90.0  # the one wait for a new process to release: its start, and two writes that may each wait on a lock
RELEASE = ('import json, sys; from metaform.data import Store; from metaform.modules.dispatch import release; '
           "given = json.loads(sys.argv[1]); release(Store(given.pop('project'), module='dispatch'), **given)")


def stamp() -> str:
    """The time as the store writes it, to the second."""
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


class Exits(asyncio.subprocess.SubprocessStreamProtocol):
    """The agent's process protocol, which says when the process itself has ended. `Process.wait` waits also for its
    pipes, which a process it started may hold open after it ends."""

    def __init__(self, limit: int, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__(limit=limit, loop=loop)
        self.exited = asyncio.Event()

    def process_exited(self) -> None:
        super().process_exited()
        self.exited.set()


async def dispatch(ctx: Context) -> dict[str, Any]:
    """`metaform dispatch run <id> <agent>`: the session for one ticket, until it ends. When the ticket is done and has an
    agent glyph, VIEW-040, the glyph's next ticket in board order gets a session of its own, and so on until the glyph
    has none waiting or a session ends with its ticket not done."""
    store = ctx.require_store()
    agent, work_id = agent_named(ctx.nouns['agent']), ctx.nouns['id']
    command = argv(str(ctx.setting(f'dispatch_{agent}')))
    if ctx.nouns.get('system'):  # the person's system agent, the +1: talks with them in the project's folder
        held = await asyncio.to_thread(ticket, store, work_id)
        return await Session(ctx, store, held, agent, command, None, prep=True, system=True).run()
    if ctx.nouns.get('prep'):  # VIEW-044: an agent helps the person prepare a merge under review, in its worktree
        from .merge import worktree_of
        held = await asyncio.to_thread(ticket, store, work_id)
        folder = await asyncio.to_thread(worktree_of, store, work_id)
        return await Session(ctx, store, held, agent, command, folder, prep=True).run()

    def reserve(record: WorkRecord) -> WorkRecord:
        with store.atomic():
            record = ticket(store, record.id)
            reservation = ctx.nouns.get('reservation')
            if reservation and record.taken_by == reservation:
                require_eligible(ctx, record, agent)
                return record
            startable(ctx, store, record, agent)
            reservation = 'dispatch starting ' + secrets.token_hex(16)
            record = store.take_work(record.id, by=reservation)
            ctx.nouns['reservation'] = reservation
            return record

    record = await asyncio.to_thread(reserve, ticket(store, work_id))
    worked: list[str] = []
    while True:
        folder = None
        if ctx.setting('dispatch_worktrees'):  # VIEW-044: each ticket's agent works in a worktree of its own
            from .merge import worktree_for
            folder = await asyncio.to_thread(worktree_for, store.project().path, record.id)
        ended = await Session(ctx, store, record, agent, command, folder).run()
        worked.append(record.id)
        if ended.get('ended') == TERMINATED:  # a terminated runner reads nothing more, so a store it cannot reach is no error
            return ended if len(worked) == 1 else {**ended, 'worked': worked}
        record = await asyncio.to_thread(ticket, store, record.id)
        if folder is not None and record.done:  # its work committed, tested and checked to merge, VIEW-044
            from .merge import finished
            await asyncio.to_thread(finished, ctx, store, record, folder)
            active = await asyncio.to_thread(store.active_base)
            await ctx.publish_async('map.changed', {'project': store.project_id, 'tables': 'dispatch',
                                                    'base_id': active.id if active else None})
        glyph = await asyncio.to_thread(glyph_of, ctx, record)  # read again, so a glyph given while it ran counts
        if glyph is None:
            return ended if len(worked) == 1 else {**ended, 'worked': worked}
        def following(glyph: str) -> WorkRecord | None:
            with store.atomic():
                found = next_ticket(ctx, store, glyph, agent=agent, exclude=tuple(worked))
                return reserve(found) if found is not None else None
        try:
            found = (await asyncio.to_thread(following, glyph)
                     if record.done or ended.get('ended') == 'cannot continue without an answer' else None)
        except Stop:  # another runner now occupies the glyph
            found = None
        if found is None:
            return {**ended, 'glyph': glyph, 'worked': worked}
        record = found


def choose(options: list[PermissionOption], answer: str | None) -> str | None:
    """The option a person's answer names, by its name or its id; None when it names none."""
    said = (answer or '').strip()
    for exact in (True, False):
        for option in options:
            names = (option.name, option.option_id)
            if any(name == said if exact else name.casefold() == said.casefold() for name in names):
                return option.option_id
    return None


def chunk_text(content: Any) -> str:
    if not isinstance(content, dict):
        return ''
    block = cast(dict[str, Any], content)
    return str(block.get('text', '')) if block.get('type') == 'text' else f'[{block.get("type", "content")}]'


def subject(store: Store, work_id: str, talk: str) -> tuple[str, str]:
    """What a conversation agent talks about, in words, and how it reads it first, from `talk=<kind>:<ref>`."""
    kind, _, ref = talk.partition(':')
    if kind == 'ticket':
        record = ticket(store, ref)
        return (f'ticket {ref}, {"done" if record.done else "open"}: {record.task or record.note or ""}',
                f'`metaform map work id={ref}`, and what its agents did with `metaform dispatch sessions id={ref}`')
    if kind == 'question':
        asked = next((one for one in store.messages(None, 'question', None, limit=0).results if one.id == ref), None)
        text = asked.text or '' if asked else ''
        return (f'question {ref}{", answered" if asked and asked.closed else ""}: {text}',
                f'`metaform map messages kind=question` for question {ref}, and its ticket with `metaform map work id={work_id}`')
    if kind == 'thread':
        return (f'what an earlier agent did in session {ref} on ticket {work_id}',
                f'that session\'s whole thread with `metaform dispatch sessions id={work_id}` (session {ref}), and the '
                f'ticket with `metaform map work id={work_id}`')
    return f'the node {ref} of the map', f'`metaform map where {ref}`'


class Session:
    """One ticket's ACP session. The SDK calls `session_update` and `request_permission` on it."""

    def __init__(self, ctx: Context, store: Store, record: WorkRecord, agent: str, command: list[str],
                 folder: Any = None, prep: bool = False, system: bool = False) -> None:
        self.system = system  # the person's system agent: no ticket work, a conversation that lasts until stopped
        self.prep = prep  # helping the person prepare a merge, VIEW-044: it takes no ticket and lives between turns
        self.ctx, self.store, self.agent, self.command = ctx, store, agent, command
        self.work_id = record.id
        self.node = Node.of(record.node_kind, record.node_id)
        self.folder = str(folder) if folder is not None else store.project().path  # its worktree, VIEW-044
        self.name = AGENTS[agent][0]
        self.base_id: str | None = None
        self.session_id: str | None = None
        self.number: str | None = None  # the agent's nonce
        self.token = secrets.token_hex(16)
        self.port = 0
        self.process: asyncio.subprocess.Process | None = None
        self.exited = asyncio.Event()  # the agent's process has ended
        self.conn: Any = None
        self.recorded = False  # the session's row is written
        self.took = bool(ctx.nouns.get('reservation') and record.taken_by == ctx.nouns['reservation'])
        self.chat_question = ctx.nouns.get('question') or ('prep' if prep else None)
        self.named: set[str] = set()  # the lines kept for something, such as one tool call, changed in place
        self.lines = 0
        self.tools: dict[str, dict[str, Any]] = {}
        self.flow_kind: str | None = None
        self.flow_text = ''
        self.flow_key: str | None = None  # the note the text being written grows in
        self.flow_at = 0.0
        self.lines_at = 0.0  # when the last `dispatch.lines` event was fired
        self.lines_due: asyncio.TimerHandle | None = None  # the event that covers lines written since, when one waits
        self.flows = 0
        self.asked: dict[str, tuple[asyncio.Future[str | None], list[PermissionOption], str]] = {}
        self.theirs: dict[str, Message] = {}  # linked ticket questions and questions this agent asks, answered once
        self.answers: dict[str, tuple[str | None, str | None]] = {}  # the answer revision already delivered
        self.questions_ready = False  # startup includes existing answers in the handoff before live delivery
        self.heard = stamp()  # the last session update or prompt, the earliest a tool call first seen next began
        self.turns = 0
        self.pending: deque[str] = deque()  # prompts wait in arrival order while one turn is in flight
        self.idle = asyncio.Event()
        self.idle.set()
        self.lock = asyncio.Lock()
        self.starting = asyncio.Lock()  # shutdown waits for resources an in-flight startup acquires
        self.ended = asyncio.Event()
        self.ending = False
        self.over = asyncio.Event()
        self.how = ''
        self.tasks: set[asyncio.Task[Any]] = set()
        self.failure: Exception | None = None
        self.progress_steps = record.steps_done
        self.progress_at = time.monotonic()
        self.progress_calls = 0
        self.failed_input: str | None = None
        self.failed_count = 0

    async def raise_signal(self, signal: str, *, key: str = '', active: bool = True, **details: Any) -> None:
        from .signals import record
        value = await asyncio.to_thread(record, self.store, signal, work_id=self.work_id,
                                        session_id=self.session_id or '', key=key, active=active, **details)
        if value is not None:
            self.lines += 1
            await self.ctx.publish_async('signal.raised' if active else 'signal.cleared', value)
            self.lines_covered()
            await self.ctx.publish_async('map.changed', {'project': self.store.project_id, 'tables': 'dispatch',
                                                       'dispatch_tables': ['dispatch.lines'], 'signal': value})

    async def progress(self) -> None:
        """Observe progress on an incoming event, never with a timer or a repeated wait."""
        if self.prep or self.ending:
            return
        record = await asyncio.to_thread(ticket, self.store, self.work_id)
        if record.steps_done != self.progress_steps or record.done:
            self.progress_steps = record.steps_done
            self.progress_at = time.monotonic()
            self.progress_calls = self.failed_count = 0
            self.failed_input = None
            for signal in ('spinning-calls', 'spinning-time', 'repeated-failure'):
                await self.raise_signal(signal, active=False)
        elif self.turns and not self.asked and time.monotonic() - self.progress_at >= 60 * self.ctx.setting('dispatch_spin_minutes'):
            await self.raise_signal('spinning-time', minutes=self.ctx.setting('dispatch_spin_minutes'))

    @property
    def by(self) -> str:
        return f'{self.agent} {self.session_id}'

    def spawn(self, coroutine: Coroutine[Any, Any, Any]) -> None:
        task = asyncio.create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.finished)

    def finished(self, task: asyncio.Task[Any]) -> None:
        self.tasks.discard(task)
        if not task.cancelled() and (error := task.exception()) is not None:
            self.fail(error)

    def fail(self, error: BaseException) -> None:
        """A failed callback must wake the owner, including callbacks whose errors the ACP SDK catches."""
        if not self.ending and isinstance(error, Exception):
            self.failure = self.failure or error
            self.ended.set()

    # ------------------------------------------------------------------ the map

    async def write(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """One write through the store, off the loop, then `map.changed`, so an open web GUI shows it at once."""
        try:
            result = await asyncio.to_thread(function, *args, **kwargs)
            await self.changed()
        except Exception as error:
            self.fail(error)
            raise
        return result

    async def table(self, change: Callable[[Any], Any], *, name: str = 'lines') -> Any:
        """One write to this module's own tables, off the loop, then `map.changed` naming the dispatch tables, so an
        open agent window shows it at once and an open page reads only its agents again, not the map, STORE-045."""
        def done() -> Any:
            with self.store.tables() as tx:
                return change(tx)
        try:
            result = await asyncio.to_thread(done)
            if name == 'lines':
                await self.lines_changed()
            else:
                await self.changed(tables='dispatch', dispatch_tables=[f'dispatch.{name}'])
        except Exception as error:
            self.fail(error)
            raise
        return result

    async def lines_changed(self) -> None:
        """Announce lines written: at once when none was announced in the last `LINES_EVERY` seconds, otherwise once
        when that time is up, covering every line written meanwhile. Any other event announces them with it."""
        wait = self.lines_at + LINES_EVERY - time.monotonic()
        if wait <= 0:
            await self.changed(tables='dispatch', dispatch_tables=['dispatch.lines'])
        elif self.lines_due is None:
            self.lines_due = asyncio.get_running_loop().call_later(wait, lambda: self.spawn(self.lines_flush()))

    async def lines_flush(self) -> None:
        if self.lines_due is not None:  # an event fired since has announced them
            await self.changed(tables='dispatch', dispatch_tables=['dispatch.lines'])

    def lines_covered(self) -> None:
        """An event about to fire tells readers of the lines too, so a waiting one is not needed."""
        if self.lines_due is not None:
            self.lines_due.cancel()
            self.lines_due = None
        self.lines_at = time.monotonic()

    async def changed(self, tables: str | None = None, *, dispatch_tables: list[str] | None = None) -> None:
        if self.base_id is None:
            active = await asyncio.to_thread(self.store.active_base)
            self.base_id = active.id if active is not None else None
        payload: dict[str, Any] = {'project': self.store.project_id, 'base_id': self.base_id}
        if tables:
            payload['tables'] = tables
        if dispatch_tables is not None and self.lines_due is not None:
            dispatch_tables = sorted({*dispatch_tables, 'dispatch.lines'})
        if dispatch_tables is not None:
            payload['dispatch_tables'] = dispatch_tables
        if tables != 'dispatch' or dispatch_tables is None or 'dispatch.lines' in dispatch_tables:
            self.lines_covered()  # no detail, or the map's tables, reads the agents too
        await self.ctx.publish_async('map.changed', payload)

    def extra(self, state: str) -> dict[str, Any]:
        return {'dispatch': 'session', 'work_id': self.work_id, 'agent': self.agent, 'session_id': self.session_id,
                'nonce': self.number, 'pid': os.getpid(), 'port': self.port, 'token': self.token, 'state': state,
                'how': self.how or None}

    def summary(self, state: str) -> str:
        return f'{self.name} session {self.session_id} on work {self.work_id}: {state}'

    async def note(self, key: str | None, kind: str, text: str) -> None:
        """A line of the session's thread, in this module's tables and never on the map: a new one, or the one kept
        for `key` changed in place."""
        if self.session_id is None:
            return
        session_id = self.session_id
        if key and key in self.named:
            await self.table(lambda tx: tx.update('lines', {'session_id': session_id, 'name': key}, {'text': text}))
            return
        self.lines += 1
        seq = self.lines
        name = key or f'line:{seq}'
        if key:
            self.named.add(key)
        await self.table(lambda tx: tx.insert('lines', {'session_id': session_id, 'name': name, 'work_id': self.work_id,
                                                        'kind': kind, 'text': text, 'seq': seq}))

    async def checked(self, text: str) -> str:
        """A prompt this module sends, checked before it is sent, BASE-057: a flagged one is still sent, with a notice
        in the session's thread and the incomplete-prompt signal."""
        found = axiom.notices('prompt', text)
        if found:
            await self.note(None, 'notice', ' '.join(one['message'] for one in found))
            await self.raise_signal(axiom.SIGNAL, notices=found)
        return text

    async def flush(self) -> None:
        """The message or thought text gathered so far, as one note: the note it has grown in while it was written."""
        kind, text, key = self.flow_kind, self.flow_text, self.flow_key
        self.flow_kind, self.flow_text, self.flow_key = None, '', None
        if kind is not None and text:
            await self.note(key, kind, text)

    # ------------------------------------------------------------------ the ACP client, called by the SDK

    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
        data: dict[str, Any] = update.model_dump(mode='json', by_alias=True, exclude_none=True)
        kind = str(data.get('sessionUpdate', ''))
        heard, self.heard = self.heard, stamp()
        async with self.lock:
            await self.progress()
            if kind in CHUNKS:
                if kind != self.flow_kind:
                    await self.flush()
                    self.flow_kind = kind
                    self.flows += 1
                    self.flow_key = f'flow:{self.flows}'
                self.flow_text += chunk_text(data.get('content'))
                now = time.monotonic()
                if now - self.flow_at >= STREAM_EVERY:  # the text so far, grown in place, so it reads as it is written
                    self.flow_at = now
                    await self.note(self.flow_key, kind, self.flow_text)
                return
            await self.flush()
            if kind in ('tool_call', 'tool_call_update'):
                ident = str(data.get('toolCallId', ''))
                fresh = ident not in self.tools
                # a call first seen before it completes began then; one first seen complete, after the update before it
                known = self.tools.setdefault(ident, {'began': heard if data.get('status') == 'completed' else
                                                      self.heard})
                for field in ('title', 'kind', 'status', 'rawInput'):
                    if data.get(field):
                        known[field] = data[field]
                title = known.get('title') or known.get('kind') or 'A tool call'
                await self.note(f'tool:{ident}', kind, f'{title} ({known.get("status", "pending")})')
                if fresh and not self.prep and not self.ending:
                    self.progress_calls += 1
                    if self.progress_calls >= self.ctx.setting('dispatch_spin_calls'):
                        await self.raise_signal('spinning-calls', calls=self.progress_calls)
                if not self.prep and not self.ending and known.get('status') in ('failed', 'completed') and not known.get('counted'):
                    known['counted'] = True
                    if known['status'] == 'failed':
                        fingerprint = json.dumps([known.get('kind'), title, known.get('rawInput')], sort_keys=True)
                        self.failed_count = self.failed_count + 1 if fingerprint == self.failed_input else 1
                        self.failed_input = fingerprint
                        if self.failed_count >= self.ctx.setting('dispatch_repeat_failures'):
                            await self.raise_signal('repeated-failure', calls=self.failed_count, tool=title)
                    else:
                        self.failed_input, self.failed_count = None, 0
                if data.get('rawOutput') is not None or data.get('content'):
                    await self.learn(json.dumps([data.get('rawOutput'), data.get('content')]), known['began'])
            elif kind == 'plan':
                entries: list[Any] = data.get('entries') or []
                said = [cast(dict[str, Any], entry) for entry in entries if isinstance(entry, dict)]
                await self.note('plan', kind, '\n'.join(f'{entry.get("content")} ({entry.get("status")})'
                                                        for entry in said))
            else:
                rest = {key: value for key, value in data.items() if key != 'sessionUpdate'}
                await self.note(kind, kind, json.dumps(rest, ensure_ascii=False))

    async def request_permission(self, session_id: str, tool_call: ToolCallUpdate, options: list[PermissionOption],
                                 **kwargs: Any) -> RequestPermissionResponse:
        """Asked at the ticket's node with the options as suggestions; the agent waits for the person's choice."""
        waiting: asyncio.Future[str | None] = asyncio.get_running_loop().create_future()
        title = str(tool_call.title or tool_call.kind or 'a tool call')
        how = await asyncio.to_thread(self.ctx.setting, 'dispatch_prompts')  # as set now, so a change reaches this agent
        allow = next((option for option in options if str(option.kind) == 'allow_once'), None)
        if allow is not None and (how == 'approve-all' or (how == 'approve-reads' and str(tool_call.kind) in READS)):
            async with self.lock:
                await self.flush()
                await self.note(None, 'approved', f'{title}: approved by dispatch_prompts={how}')
            return RequestPermissionResponse(outcome=AllowedOutcome(option_id=allow.option_id, outcome='selected'))
        async with self.lock:
            await self.flush()
            await self.ask(waiting, options, title, '')
        chosen = await waiting
        await self.changed(tables='dispatch')
        if chosen is None:
            return RequestPermissionResponse(outcome=DeniedOutcome(outcome='cancelled'))
        return RequestPermissionResponse(outcome=AllowedOutcome(option_id=chosen, outcome='selected'))

    async def ask(self, waiting: asyncio.Future[str | None], options: list[PermissionOption], title: str,
                  before: str) -> None:
        if self.ending:
            if not waiting.done():
                waiting.set_result(None)
            return
        text = f'{before}{self.name} asks permission on work {self.work_id}: {title}'
        asked = await self.write(self.store.ask, self.node, text, suggestions=[option.name for option in options],
                                 by=self.by, work=self.work_id)
        self.asked[asked.id] = (waiting, options, title)
        await self.raise_signal('permission-waiting', key=asked.id, message_id=asked.id, tool=title)
        await self.changed(tables='dispatch')

    async def learn(self, output: str, began: str) -> None:
        """The questions the agent asked itself in one tool call: each one whose id the call's output shows and that
        was made no earlier than the call began, so a question it only read is not taken for its own."""
        ids = set(IDS.findall(output)) - set(self.asked) - set(self.theirs)
        if not ids:
            return
        found = await asyncio.to_thread(self.store.messages, None, 'question', True, limit=0)
        for message in found.results:
            if message.id in ids and message.created >= began:
                self.theirs[message.id] = message
                await self.table(lambda tx, message=message: tx.insert(
                    'questions', {'message_id': message.id, 'work_id': self.work_id,
                                  'session_id': self.session_id}), name='questions')

    async def check(self) -> None:
        """Read questions linked to this ticket, including ones added or reopened while it runs, and deliver each
        answer once; resolve permission requests separately and end the session once its ticket is done while no prompt
        of its own runs, whatever turn closed it, VIEW-035."""
        if not self.ending and self.turns == 0 and not self.prep:
            record = await asyncio.to_thread(ticket, self.store, self.work_id)
            if record.done and not self.ending and self.turns == 0:
                self.spawn(self.end('the ticket is done'))
                return
        async with self.lock:
            await self.progress()
            if self.questions_ready and not self.ending:
                for message in await asyncio.to_thread(questions, self.store, self.work_id):
                    if message.id in self.asked:
                        continue  # ACP permission answers are returned through their waiting request
                    if message.closed is None:
                        self.answers.pop(message.id, None)
                        self.theirs[message.id] = message
                    elif self.answers.get(message.id) != (message.closed, message.answer):
                        self.theirs[message.id] = message
            if self.theirs and not self.ending:
                await self.answered()
            if not self.asked:
                return
            found = await asyncio.to_thread(self.store.messages, self.node, 'question', None, limit=0)
            for message in found.results:
                held = self.asked.get(message.id)
                if held is None or message.closed is None:
                    continue
                del self.asked[message.id]
                await self.raise_signal('permission-waiting', key=message.id, active=False,
                                        message_id=message.id, tool=held[2])
                self.progress_at = time.monotonic()  # waiting for a person is not agent spinning
                self.answers[message.id] = (message.closed, message.answer)
                waiting, options, title = held
                chosen = choose(options, message.answer)
                if chosen is not None:
                    if not waiting.done():
                        waiting.set_result(chosen)
                    continue
                await self.ask(waiting, options, title, f'The answer "{message.answer}" names none of the options. ')

    async def answered(self) -> None:
        """Each tracked question's answer, told to the ticket's current holder as a prompt, once per revision."""
        found = await asyncio.to_thread(self.store.messages, None, 'question', False, limit=0)
        for message in found.results:
            asked = self.theirs.pop(message.id, None)
            if asked is None:
                continue
            self.answers[message.id] = (message.closed, message.answer)
            text = prompt('answered', message_id=message.id, question=asked.text or '',
                          answer=message.answer or '')
            await self.flush()
            await self.note(None, 'answered', text)
            self.turn(await self.checked(text))

    # ------------------------------------------------------------------ the session

    async def run(self) -> dict[str, Any]:
        server = await asyncio.start_server(self.control, '127.0.0.1', 0)
        self.port = int(server.sockets[0].getsockname()[1])
        loop = asyncio.get_running_loop()
        listener = self.ctx.listen(lambda payload: loop.call_soon_threadsafe(self.changed_elsewhere, payload))
        with contextlib.suppress(NotImplementedError):  # Windows ends a process with no signal it can handle
            loop.add_signal_handler(signal.SIGTERM, lambda: self.spawn(self.end(TERMINATED)))
        try:
            async with self.starting:
                await self.begin()
            await self.ended.wait()
            if self.failure is not None:
                raise self.failure
        except Exception as error:  # noqa: BLE001  the agent did not start; the map says why
            said = 'did not start' if self.session_id is None else 'failed'
            sys.stderr.write(f'{self.name} {said} on work {self.work_id}: {error}\n')
            self.how = f'it {said}: {error}'
            try:
                await self.note(None, 'failed', f'{self.name} {said} on work {self.work_id}: {error}')
            except Exception as note_error:  # noqa: BLE001  a failure note cannot prevent resource cleanup
                sys.stderr.write(f'Could not record the session failure: {note_error}\n')
        finally:
            with contextlib.suppress(NotImplementedError):
                loop.remove_signal_handler(signal.SIGTERM)
            try:
                await asyncio.shield(self.end(self.how or 'the runner ended'))
            finally:
                pending = tuple(self.tasks)
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                try:
                    await asyncio.to_thread(listener.close)
                finally:
                    server.close()
                    await server.wait_closed()
        return {'work_id': self.work_id, 'agent': self.agent, 'session_id': self.session_id, 'ended': self.how}

    async def begin(self) -> None:
        if self.ending:
            return
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.subprocess_exec(
            lambda: Exits(LINE_LIMIT, loop), *self.command, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=None, cwd=self.folder, env=dict(os.environ), **group_options())
        self.process, self.exited = asyncio.subprocess.Process(transport, protocol, loop), protocol.exited
        if self.ending:
            return
        self.spawn(self.watch(self.process))
        self.conn = acp.connect_to_agent(self, self.process.stdin, self.process.stdout)  # pyright: ignore[reportArgumentType]
        try:
            version = metadata.version('metaform')
        except metadata.PackageNotFoundError:
            version = '0'
        await asyncio.wait_for(self.conn.initialize(
            protocol_version=acp.PROTOCOL_VERSION,
            client_capabilities=ClientCapabilities(
                fs=FileSystemCapabilities(read_text_file=False, write_text_file=False), terminal=False),
            client_info=Implementation(name='metaform', title='Metaform', version=version)), START_LIMIT)
        if self.ending:
            return
        made = await asyncio.wait_for(self.conn.new_session(
            cwd=self.folder,
            mcp_servers=[McpServerStdio(name='metaform', command=sys.executable, args=['-m', 'metaform', 'mcp', 'serve'],
                                        env=[])]), START_LIMIT)
        self.session_id = str(made.session_id)
        if self.ending:
            return
        from .recovery import resources
        recovery = await asyncio.to_thread(resources, self.store.project_id, self.work_id, self.session_id,
                                            self.process.pid)
        self.number = await asyncio.to_thread(nonce.request, 'dispatch', 'handoff',
                                              {'work_id': self.work_id, 'agent': self.agent,
                                               'session_id': self.session_id, 'recovery': recovery})
        if self.ending:
            return
        row = {key: value for key, value in self.extra('running').items() if key != 'dispatch'}
        row.update(started=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), seq=time.time_ns() // 1_000_000)
        def take() -> None:
            with self.store.atomic():
                if not self.prep:
                    record = ticket(self.store, self.work_id)
                    if self.took:
                        if record.taken_by != self.ctx.nouns['reservation']:
                            raise Stop('The startup reservation is no longer held.', 'metaform map work open=true')
                        self.store.move_work(self.work_id, 'todo', record.position)
                    self.store.take_work(self.work_id, None, self.by)
                with self.store.tables() as tx:
                    tx.insert('sessions', row)
            # Acquisition is complete before write publishes its change. A failed announcement still needs release.
            self.took = not self.prep
            self.recorded = True
        await self.write(take)
        if self.ending:
            return
        if self.system and self.ctx.nouns.get('talk'):  # the person clicked something to talk about: no ticket work
            about, read = await asyncio.to_thread(subject, self.store, self.work_id, str(self.ctx.nouns['talk']))
            self.turn(prompt('talk', about=about, read=read))
            return
        if self.system:
            self.turn(prompt('system', project=self.store.project_id))
            return
        if self.prep:
            from .merge import branch_of, dev_branch
            self.turn(prompt('prep', work_id=self.work_id, branch=branch_of(self.work_id),
                             dev=dev_branch(self.store.project().path) or 'the dev branch'))
            return
        text = prompt('handoff', work_id=self.work_id)
        for question in await asyncio.to_thread(questions, self.store, self.work_id):
            if question.closed is not None:
                self.answers[question.id] = (question.closed, question.answer)
                text += '\n\n' + prompt('answered', message_id=question.id, question=question.text or '',
                                         answer=question.answer or '')
            else:
                self.theirs[question.id] = question
                if question.id == self.chat_question:
                    text += '\n\n' + prompt('chat', message_id=question.id, question=question.text or '')
        text = await self.checked(text)
        if not self.ending:
            self.questions_ready = True
            self.turn(text)

    def turn(self, text: str) -> None:
        if self.ending:
            return
        self.pending.append(text)
        if self.turns == 0:
            self.progress_at = time.monotonic()
        if self.turns:
            return
        self.turns = 1
        self.idle.clear()
        self.spawn(self.prompted())

    async def prompted(self) -> None:
        """One prompt in flight, draining messages in order before the normal turn-end decision."""
        try:
            while self.pending and not self.ending:
                text = self.pending.popleft()
                self.heard = stamp()  # a tool call of this turn began no earlier than its prompt
                try:
                    await self.changed(tables='dispatch')
                    if self.ending:
                        break  # stop may arrive while the turn-start event is published
                    answer = await self.conn.prompt(session_id=self.session_id, prompt=[acp.text_block(text)])
                    reason = str(answer.stop_reason)
                except Exception as error:  # noqa: BLE001  the turn's end is noted whatever ended it
                    reason = f'error: {error}'
                async with self.lock:
                    await self.flush()
                    await self.note('turn', 'turn', f'The turn ended: {reason}.')
        finally:
            self.turns -= 1
            if self.turns == 0:
                self.idle.set()
        await self.changed(tables='dispatch')  # readers now see idle after the queue drained
        if self.turns == 0 and not self.ending and not self.prep:
            record = await asyncio.to_thread(ticket, self.store, self.work_id)
            if self.turns or self.ending:  # a message can arrive while the ticket is read
                return
            if record.done:
                await self.end('the ticket is done')
            elif any(message_id != self.chat_question for message_id in self.theirs):
                await self.end('cannot continue without an answer')
            elif self.chat_question is None:
                # Work never stops: a turn that ends with the ticket open and nothing asked ends the session, and the
                # ticket goes back to the queue for the next agent.
                await self.end('the turn ended with the ticket open and no question asked')

    async def watch(self, process: asyncio.subprocess.Process) -> None:
        await self.exited.wait()
        code = process.returncode
        if not self.ending:
            await self.end(f'the agent ended with exit code {code}')

    def changed_elsewhere(self, payload: dict[str, Any]) -> None:
        """map.changed from another process, handed over by the base's listener, BASE-053: a change to this project
        may be an answer to a question, so the open questions are read, QUAL-015."""
        if payload.get('project') == self.store.project_id and not self.ending:
            self.spawn(self.check())

    async def control(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """One request on the control port: `message` or `stop`, with this session's token."""
        try:
            line = await asyncio.wait_for(reader.readline(), REPLY_LIMIT)
            found: Any = json.loads(line) if line else None
            asked = cast(dict[str, Any], found) if isinstance(found, dict) else {}
            if asked.get('token') != self.token:
                await self.reply(writer, {'error': 'This is not a request for this session.'})
                return
            said = {'work_id': self.work_id, 'agent': self.agent, 'session_id': self.session_id}
            op = asked.get('op')
            if op == 'status':
                alive = self.process is not None and self.process.returncode is None and not self.exited.is_set()
                live = alive and not self.ending and self.failure is None
                activity = ('waiting' if self.asked else 'working' if self.turns else
                            'waiting' if self.theirs else 'idle') if live else 'idle'
                await self.reply(writer, {**said, 'state': 'running' if live else 'ended', 'agent_alive': alive,
                                          'activity': activity,
                                          'how': None if live else self.how or 'the agent is no longer running'})
            elif op == 'message':
                if self.ending or self.session_id is None:
                    await self.reply(writer, {**said, 'sent': False, 'error': 'The session has not started or is ending.'})
                    return
                text = str(asked.get('text', ''))
                async with self.lock:  # the person's words in the thread, where the agent's reply follows
                    await self.flush()
                    await self.note(None, 'person', text)
                self.turn(text)
                await self.reply(writer, {**said, 'sent': True})
            elif op == 'stop':
                await self.end('stopped by the person', release=False)
                try:
                    await self.reply(writer, {**said, 'stopped': True})
                finally:
                    self.ended.set()
            else:
                await self.reply(writer, {'error': f'No request {op}.'})
        except (TimeoutError, OSError, ValueError):
            pass
        finally:
            with contextlib.suppress(Exception):
                writer.close()

    @staticmethod
    async def reply(writer: asyncio.StreamWriter, answer: dict[str, Any]) -> None:
        writer.write(json.dumps(answer).encode('utf-8') + b'\n')
        await writer.drain()

    async def end(self, how: str, release: bool = True) -> None:
        """End the session once: cancel a running turn, answer every waiting request as cancelled, close the agent's
        input, end its process group, close the nonce and say on the map how it ended."""
        if self.ending:
            await self.over.wait()
            if release:
                self.ended.set()
            return
        self.ending, self.how = True, how
        self.pending.clear()
        try:
            # Cancelling startup would abandon to_thread writes or a child being created. Let the current
            # acquisition finish and let begin observe ending before proceeding, then clean up its resources.
            async with self.starting:
                pass
            for message_id, (waiting, _, title) in self.asked.items():
                if not waiting.done():
                    waiting.set_result(None)
                with contextlib.suppress(Exception):
                    await self.raise_signal('permission-waiting', key=message_id, active=False,
                                            message_id=message_id, tool=title)
            self.asked.clear()
            process = self.process
            if process is not None and process.returncode is None:
                if self.turns and self.conn is not None and self.session_id is not None:
                    with contextlib.suppress(Exception):
                        await self.conn.cancel(session_id=self.session_id)
                    with contextlib.suppress(asyncio.TimeoutError):
                        await asyncio.wait_for(self.idle.wait(), END_LIMIT)
                if process.stdin is not None:
                    with contextlib.suppress(Exception):
                        process.stdin.close()
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(self.exited.wait(), END_LIMIT)
            if process is not None:
                await asyncio.to_thread(end_group, process.pid)  # what it started ends with it
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(process.wait(), END_LIMIT)
            if self.conn is not None:
                with contextlib.suppress(Exception):
                    await self.conn.close()
            try:
                async with self.lock:
                    await self.flush()
            except Exception as error:  # noqa: BLE001  transcript failure cannot prevent nonce and session cleanup
                sys.stderr.write(f"Could not flush the ended session: {error}\n")
            with contextlib.suppress(Exception):  # the last lines are announced before the process can end
                await self.lines_flush()
            if self.number is not None:
                with contextlib.suppress(Exception):
                    await asyncio.to_thread(nonce.close, self.number)
            if self.took or self.recorded:
                await self.release(how)
        finally:
            self.over.set()
            if release:
                self.ended.set()

    async def release(self, how: str) -> None:
        """Give back the ticket and record the session ended, never silently failing: when this runner's code cannot
        reach the store, as when a newer Metaform upgraded it under the runner, STORE-029, a new process does it with
        the code on disk; when that fails too, the runner's log says what is left and how to put the ticket back."""
        owner = self.by if self.recorded else self.ctx.nouns.get('reservation') or self.by
        given: dict[str, Any] = {'work_id': self.work_id, 'by': owner, 'took': self.took,
                                 'session_id': self.session_id if self.recorded else None, 'how': how}
        try:
            await asyncio.to_thread(release, self.store, **given)
        except Exception as error:  # noqa: BLE001  the code on disk may reach what this code cannot
            command = [sys.executable, '-c', RELEASE, json.dumps({'project': self.store.project_id, **given})]
            try:
                done = await asyncio.to_thread(subprocess.run, command, capture_output=True, text=True,
                                               encoding='utf-8', stdin=subprocess.DEVNULL, timeout=RELEASE_LIMIT)
                failed = done.stderr.strip() if done.returncode else None
            except (OSError, subprocess.TimeoutExpired) as run_error:
                failed = str(run_error)
            if failed is not None:
                sys.stderr.write(f'Could not end session {self.session_id} on work {self.work_id}: {error}\n'
                                 f'Nor with the code on disk: {failed}\n')
                if self.took:
                    sys.stderr.write(f'Work {self.work_id} stays taken by {self.by}. To put it back: '
                                     f'metaform map work op=move id={self.work_id} column=todo\n')
                return
        with contextlib.suppress(Exception):  # the release stands whether or not an open page hears of it
            await self.changed()
