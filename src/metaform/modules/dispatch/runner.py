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
import sys
import time
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

from metaform import nonce
from metaform.data import Message, Node, Store, WorkRecord
from metaform.module import Context, Stop

from . import (
    AGENTS,
    READS,
    REPLY_LIMIT,
    agent_named,
    argv,
    blocked,
    end_group,
    glyph_of,
    group_options,
    next_ticket,
    prompt,
    questions,
    startable,
    ticket,
)

START_LIMIT = 300.0  # the one wait for the agent to start and make its session; npx may download it first
END_LIMIT = 10.0  # the one wait for a cancelled turn to end, and for the agent to end once its input is closed
LINE_LIMIT = 64 * 1024 * 1024  # the longest line read from the agent
CHUNKS = ('agent_message_chunk', 'agent_thought_chunk', 'user_message_chunk')
STREAM_EVERY = 0.4  # seconds between writes of text still being written, so the page shows it as it grows
IDS = re.compile(r'\b[0-9a-f]{32}\b')  # a message id, as a tool call's output shows it


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

    def reserve(record: WorkRecord) -> WorkRecord:
        with store.atomic():
            record = ticket(store, record.work_id)
            reservation = ctx.nouns.get('reservation')
            if reservation and record.taken_by == reservation:
                return record
            startable(ctx, store, record)
            reservation = 'dispatch starting ' + secrets.token_hex(16)
            record = store.take_work(record.work_id, by=reservation)
            ctx.nouns['reservation'] = reservation
            return record

    record = await asyncio.to_thread(reserve, ticket(store, work_id))
    worked: list[str] = []
    while True:
        ended = await Session(ctx, store, record, agent, command).run()
        worked.append(record.work_id)
        record = await asyncio.to_thread(ticket, store, record.work_id)
        glyph = await asyncio.to_thread(glyph_of, ctx, record)  # read again, so a glyph given while it ran counts
        if glyph is None:
            return ended if len(worked) == 1 else {**ended, 'worked': worked}
        def following(glyph: str) -> WorkRecord | None:
            with store.atomic():
                found = next_ticket(ctx, store, glyph)
                return reserve(found) if found is not None else None
        try:
            found = await asyncio.to_thread(following, glyph) if record.done or blocked(store, record.work_id) else None
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


class Session:
    """One ticket's ACP session. The SDK calls `session_update` and `request_permission` on it."""

    def __init__(self, ctx: Context, store: Store, record: WorkRecord, agent: str, command: list[str]) -> None:
        self.ctx, self.store, self.agent, self.command = ctx, store, agent, command
        self.work_id = record.work_id
        self.node = Node.of(record.kind, record.id)
        self.folder = store.project().path
        self.name = AGENTS[agent][0]
        self.metaform_id: str | None = None
        self.session_id: str | None = None
        self.number: str | None = None  # the agent's nonce
        self.token = secrets.token_hex(16)
        self.port = 0
        self.process: asyncio.subprocess.Process | None = None
        self.exited = asyncio.Event()  # the agent's process has ended
        self.conn: Any = None
        self.recorded = False  # the session's row is written
        self.took = bool(ctx.nouns.get('reservation') and record.taken_by == ctx.nouns['reservation'])
        self.chat_question = ctx.nouns.get('question')
        self.named: set[str] = set()  # the lines kept for something, such as one tool call, changed in place
        self.lines = 0
        self.tools: dict[str, dict[str, Any]] = {}
        self.flow_kind: str | None = None
        self.flow_text = ''
        self.flow_key: str | None = None  # the note the text being written grows in
        self.flow_at = 0.0
        self.flows = 0
        self.asked: dict[str, tuple[asyncio.Future[str | None], list[PermissionOption], str]] = {}
        self.theirs: dict[str, Message] = {}  # the open questions the agent asked itself, told to it when answered
        self.heard = stamp()  # the last session update or prompt, the earliest a tool call first seen next began
        self.turns = 0
        self.idle = asyncio.Event()
        self.idle.set()
        self.lock = asyncio.Lock()
        self.ended = asyncio.Event()
        self.ending = False
        self.over = asyncio.Event()
        self.how = ''
        self.tasks: set[asyncio.Task[Any]] = set()
        self.failure: Exception | None = None

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

    async def table(self, change: Callable[[Any], Any]) -> Any:
        """One write to this module's own tables, off the loop, then `map.changed` naming the dispatch tables, so an
        open agent window shows it at once and an open page reads only its agents again, not the map, STORE-045."""
        def done() -> Any:
            with self.store.tables() as tx:
                return change(tx)
        try:
            result = await asyncio.to_thread(done)
            await self.changed(tables='dispatch')
        except Exception as error:
            self.fail(error)
            raise
        return result

    async def changed(self, tables: str | None = None) -> None:
        if self.metaform_id is None:
            active = await asyncio.to_thread(self.store.active_metaform)
            self.metaform_id = active.metaform_id if active is not None else None
        payload: dict[str, Any] = {'project': self.store.project_id, 'metaform_id': self.metaform_id}
        if tables:
            payload['tables'] = tables
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
                # a call first seen before it completes began then; one first seen complete, after the update before it
                known = self.tools.setdefault(ident, {'began': heard if data.get('status') == 'completed' else
                                                      self.heard})
                for field in ('title', 'kind', 'status'):
                    if data.get(field):
                        known[field] = data[field]
                title = known.get('title') or known.get('kind') or 'A tool call'
                await self.note(f'tool:{ident}', kind, f'{title} ({known.get("status", "pending")})')
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
        self.asked[asked.message_id] = (waiting, options, title)
        await self.changed(tables='dispatch')

    async def learn(self, output: str, began: str) -> None:
        """The questions the agent asked itself in one tool call: each one whose id the call's output shows and that
        was made no earlier than the call began, so a question it only read is not taken for its own."""
        ids = set(IDS.findall(output)) - set(self.asked) - set(self.theirs)
        if not ids:
            return
        found = await asyncio.to_thread(self.store.messages, None, 'question', True, limit=0)
        for message in found.results:
            if message.message_id in ids and message.created >= began:
                self.theirs[message.message_id] = message
                await self.table(lambda tx, message=message: tx.insert(
                    'questions', {'message_id': message.message_id, 'work_id': self.work_id,
                                  'session_id': self.session_id}))

    async def check(self) -> None:
        """Read the open questions this session asked, and answer the agent for each one the person answered; tell the
        agent the answer to each question it asked itself; and end the session once its ticket is done while no prompt
        of its own runs, whatever turn closed it, VIEW-035."""
        if not self.ending and self.turns == 0:
            record = await asyncio.to_thread(ticket, self.store, self.work_id)
            if record.done:
                self.spawn(self.end('the ticket is done'))
                return
        async with self.lock:
            if self.theirs and not self.ending:
                await self.answered()
            if not self.asked:
                return
            found = await asyncio.to_thread(self.store.messages, self.node, 'question', None, limit=0)
            for message in found.results:
                held = self.asked.get(message.message_id)
                if held is None or message.closed is None:
                    continue
                del self.asked[message.message_id]
                waiting, options, title = held
                chosen = choose(options, message.answer)
                if chosen is not None:
                    if not waiting.done():
                        waiting.set_result(chosen)
                    continue
                await self.ask(waiting, options, title, f'The answer "{message.answer}" names none of the options. ')

    async def answered(self) -> None:
        """Each question the agent asked itself that the person has answered, told to the agent as a prompt, once."""
        found = await asyncio.to_thread(self.store.messages, None, 'question', False, limit=0)
        for message in found.results:
            asked = self.theirs.pop(message.message_id, None)
            if asked is None:
                continue
            text = prompt('answered', message_id=message.message_id, question=asked.text or '',
                          answer=message.answer or '')
            await self.flush()
            await self.note(None, 'answered', text)
            self.turn(text)

    # ------------------------------------------------------------------ the session

    async def run(self) -> dict[str, Any]:
        server = await asyncio.start_server(self.control, '127.0.0.1', 0)
        self.port = int(server.sockets[0].getsockname()[1])
        loop = asyncio.get_running_loop()
        listener = self.ctx.listen(lambda payload: loop.call_soon_threadsafe(self.changed_elsewhere, payload))
        try:
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
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.subprocess_exec(
            lambda: Exits(LINE_LIMIT, loop), *self.command, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=None, cwd=self.folder, env=dict(os.environ), **group_options())
        self.process, self.exited = asyncio.subprocess.Process(transport, protocol, loop), protocol.exited
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
        made = await asyncio.wait_for(self.conn.new_session(
            cwd=self.folder,
            mcp_servers=[McpServerStdio(name='metaform', command=sys.executable, args=['-m', 'metaform', 'mcp', 'serve'],
                                        env=[])]), START_LIMIT)
        self.session_id = str(made.session_id)
        self.number = await asyncio.to_thread(nonce.request, 'dispatch', 'handoff',
                                              {'work_id': self.work_id, 'agent': self.agent,
                                               'session_id': self.session_id})
        def take() -> None:
            with self.store.atomic():
                record = ticket(self.store, self.work_id)
                if self.took:
                    if record.taken_by != self.ctx.nouns['reservation']:
                        raise Stop('The startup reservation is no longer held.', 'metaform map work open=true')
                    self.store.move_work(self.work_id, 'todo', record.position)
                self.store.take_work(self.work_id, None, self.by)
        await self.write(take)
        self.took = True
        row = {key: value for key, value in self.extra('running').items() if key != 'dispatch'}
        row.update(started=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), seq=time.time_ns() // 1_000_000)
        await self.table(lambda tx: tx.insert('sessions', row))
        self.recorded = True
        text = prompt('handoff', work_id=self.work_id)
        for question in await asyncio.to_thread(questions, self.store, self.work_id):
            if question.closed is not None:
                text += '\n\n' + prompt('answered', message_id=question.message_id, question=question.text or '',
                                         answer=question.answer or '')
            elif question.message_id == self.chat_question:
                self.theirs[question.message_id] = question
                text += '\n\n' + prompt('chat', message_id=question.message_id, question=question.text or '')
        self.turn(text)

    def turn(self, text: str) -> None:
        self.heard = stamp()  # a tool call of this turn began no earlier than its prompt
        self.turns += 1
        self.idle.clear()
        self.spawn(self.prompted(text))

    async def prompted(self, text: str) -> None:
        """One prompt turn; when the last turn ends with the ticket done, the session ends."""
        try:
            await self.changed(tables='dispatch')
            answer = await self.conn.prompt(session_id=self.session_id, prompt=[acp.text_block(text)])
            reason = str(answer.stop_reason)
        except Exception as error:  # noqa: BLE001  the turn's end is noted whatever ended it
            reason = f'error: {error}'
        finally:
            self.turns -= 1
            if self.turns == 0:
                self.idle.set()
        async with self.lock:
            await self.flush()
            await self.note('turn', 'turn', f'The turn ended: {reason}.')
        if self.turns == 0 and not self.ending:
            record = await asyncio.to_thread(ticket, self.store, self.work_id)
            if record.done:
                await self.end('the ticket is done')
            elif any(message_id != self.chat_question for message_id in self.theirs):
                await self.end('cannot continue without an answer')

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
        try:
            for waiting, _, _ in self.asked.values():
                if not waiting.done():
                    waiting.set_result(None)
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
            if self.number is not None:
                with contextlib.suppress(Exception):
                    await asyncio.to_thread(nonce.close, self.number)
            if self.took:  # a ticket this session leaves open goes back to To do, so no figure circles it, VIEW-035
                with contextlib.suppress(Exception):
                    record = await asyncio.to_thread(ticket, self.store, self.work_id)
                    if not record.done:
                        waiting = await asyncio.to_thread(blocked, self.store, self.work_id)
                        await self.write(self.store.move_work, self.work_id, 'backlog' if waiting else 'todo',
                                         record.position, self.by)
            if self.recorded:
                session_id = self.session_id
                try:
                    await self.table(lambda tx: tx.update('sessions', {'session_id': session_id},
                                                         {'state': 'ended', 'how': how}))
                except Exception as error:  # noqa: BLE001  persistence cannot prevent the shutdown signals
                    sys.stderr.write(f"Could not record the ended session: {error}\n")
        finally:
            self.over.set()
            if release:
                self.ended.set()
