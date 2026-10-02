"""runner: one ACP session for one ticket, BASE-052, run by `metaform dispatch run`.

Metaform is the ACP client. The agent's ACP adapter runs as a child process in its own process group, in the
project's folder, with the person's environment unchanged; ACP goes over its standard input and output as bytes,
through the official SDK, `acp`. The runner listens on a loopback port for `message`, `stop` and `changed`, the last
sent by the module's `map.changed` subscriber in whichever process changed the map, QUAL-015.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import secrets
import sys
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
from metaform.data import Item, Node, Store, WorkRecord
from metaform.module import Context, Stop

from . import AGENTS, LAYER, REPLY_LIMIT, RUNNER, VARIABLE, agent_named, argv, end_group, group_options, prompt, ticket

START_LIMIT = 300.0  # the one wait for the agent to start and make its session; npx may download it first
END_LIMIT = 10.0  # the one wait for a cancelled turn to end, and for the agent to end once its input is closed
LINE_LIMIT = 64 * 1024 * 1024  # the longest line read from the agent
CHUNKS = ('agent_message_chunk', 'agent_thought_chunk', 'user_message_chunk')


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
    """`metaform dispatch run <id> <agent>`: the session for one ticket, until it ends."""
    store = ctx.require_store()
    agent, work_id = agent_named(ctx.nouns['agent']), ctx.nouns['id']
    record = ticket(store, work_id)
    if record.done:
        raise Stop(f'Work {work_id} was done at {record.done}.', 'metaform map work open=true')
    if record.taken:
        raise Stop(f'Work {work_id} is already taken by {record.taken_by or "an agent"}.', 'metaform map work open=true')
    command = argv(str(ctx.setting(f'dispatch_{agent}')))
    RUNNER['pid'] = os.getpid()
    return await Session(ctx, store, record, agent, command).run()


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
        self.record_item: str | None = None
        self.notes: dict[str, str] = {}  # what a note is kept for, such as one tool call, and its item
        self.tools: dict[str, dict[str, Any]] = {}
        self.flow_kind: str | None = None
        self.flow_text = ''
        self.asked: dict[str, tuple[asyncio.Future[str | None], list[PermissionOption], str]] = {}
        self.turns = 0
        self.idle = asyncio.Event()
        self.idle.set()
        self.lock = asyncio.Lock()
        self.ended = asyncio.Event()
        self.ending = False
        self.over = asyncio.Event()
        self.how = ''
        self.tasks: set[asyncio.Task[Any]] = set()

    @property
    def by(self) -> str:
        return f'{self.agent} {self.session_id}'

    def spawn(self, coroutine: Coroutine[Any, Any, Any]) -> None:
        task = asyncio.create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    # ------------------------------------------------------------------ the map

    async def write(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """One write through the store, off the loop, then `map.changed`, so an open web GUI shows it at once."""
        result = await asyncio.to_thread(function, *args, **kwargs)
        if self.metaform_id is None:
            active = await asyncio.to_thread(self.store.active_metaform)
            self.metaform_id = active.metaform_id if active is not None else None
        await self.ctx.publish_async('map.changed', {'project': self.store.project_id, 'metaform_id': self.metaform_id})
        return result

    def extra(self, state: str) -> dict[str, Any]:
        return {'dispatch': 'session', 'work_id': self.work_id, 'agent': self.agent, 'session_id': self.session_id,
                'nonce': self.number, 'pid': os.getpid(), 'port': self.port, 'token': self.token, 'state': state,
                'how': self.how or None}

    def summary(self, state: str) -> str:
        return f'{self.name} session {self.session_id} on work {self.work_id}: {state}'

    async def note(self, key: str | None, kind: str, text: str) -> None:
        """A note at the ticket's node: a new one, or the one kept for `key` changed in place."""
        held = self.notes.get(key) if key else None
        if held is not None:
            await self.write(self.store.edit, held, {'value': text})
            return
        made = await self.write(self.store.add_item, LAYER, self.node, text,
                                extra={'dispatch': 'note', 'work_id': self.work_id, 'agent': self.agent,
                                       'session_id': self.session_id, 'update': kind})
        if key and isinstance(made, Item):
            self.notes[key] = made.item_id

    async def flush(self) -> None:
        """The message or thought text gathered so far, as one note."""
        kind, text = self.flow_kind, self.flow_text
        self.flow_kind, self.flow_text = None, ''
        if kind is not None and text:
            await self.note(None, kind, text)

    # ------------------------------------------------------------------ the ACP client, called by the SDK

    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
        data: dict[str, Any] = update.model_dump(mode='json', by_alias=True, exclude_none=True)
        kind = str(data.get('sessionUpdate', ''))
        async with self.lock:
            if kind in CHUNKS:
                if kind != self.flow_kind:
                    await self.flush()
                    self.flow_kind = kind
                self.flow_text += chunk_text(data.get('content'))
                return
            await self.flush()
            if kind in ('tool_call', 'tool_call_update'):
                ident = str(data.get('toolCallId', ''))
                known = self.tools.setdefault(ident, {})
                for field in ('title', 'kind', 'status'):
                    if data.get(field):
                        known[field] = data[field]
                title = known.get('title') or known.get('kind') or 'A tool call'
                await self.note(f'tool:{ident}', kind, f'{title} ({known.get("status", "pending")})')
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
        async with self.lock:
            await self.flush()
            await self.ask(waiting, options, title, '')
        chosen = await waiting
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
                                 by=self.by)
        self.asked[asked.message_id] = (waiting, options, title)

    async def check(self) -> None:
        """Read the open questions this session asked, and answer the agent for each one the person answered."""
        async with self.lock:
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

    # ------------------------------------------------------------------ the session

    async def run(self) -> dict[str, Any]:
        server = await asyncio.start_server(self.control, '127.0.0.1', 0)
        self.port = int(server.sockets[0].getsockname()[1])
        try:
            await self.begin()
            await self.ended.wait()
        except Exception as error:  # noqa: BLE001  the agent did not start; the map says why
            said = 'did not start' if self.session_id is None else 'failed'
            sys.stderr.write(f'{self.name} {said} on work {self.work_id}: {error}\n')
            self.how = f'it {said}: {error}'
            await self.note(None, 'failed', f'{self.name} {said} on work {self.work_id}: {error}')
        finally:
            await asyncio.shield(self.end(self.how or 'the runner ended'))
            server.close()
        return {'work_id': self.work_id, 'agent': self.agent, 'session_id': self.session_id, 'ended': self.how}

    async def begin(self) -> None:
        await self.write(self.store.layer, LAYER, 'dispatch', VARIABLE, mutable=True, hideable=True, ready=True)
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
        await self.write(self.store.take_work, self.work_id, None, self.by)
        item = await self.write(self.store.add_item, LAYER, self.node, self.summary('running'),
                                extra=self.extra('running'))
        self.record_item = item.item_id if isinstance(item, Item) else None
        self.turn(prompt('handoff', work_id=self.work_id))

    def turn(self, text: str) -> None:
        self.turns += 1
        self.idle.clear()
        self.spawn(self.prompted(text))

    async def prompted(self, text: str) -> None:
        """One prompt turn; when the last turn ends with the ticket done, the session ends."""
        try:
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

    async def watch(self, process: asyncio.subprocess.Process) -> None:
        await self.exited.wait()
        code = process.returncode
        if not self.ending:
            await self.end(f'the agent ended with exit code {code}')

    async def control(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """One request on the control port: `changed`, `message` or `stop`, with this session's token."""
        try:
            line = await asyncio.wait_for(reader.readline(), REPLY_LIMIT)
            found: Any = json.loads(line) if line else None
            asked = cast(dict[str, Any], found) if isinstance(found, dict) else {}
            if asked.get('token') != self.token:
                await self.reply(writer, {'error': 'This is not a request for this session.'})
                return
            said = {'work_id': self.work_id, 'agent': self.agent, 'session_id': self.session_id}
            op = asked.get('op')
            if op == 'changed':
                await self.reply(writer, {'ok': True})
                await self.check()
            elif op == 'message':
                if self.ending or self.session_id is None:
                    await self.reply(writer, {**said, 'sent': False, 'error': 'The session has not started or is ending.'})
                    return
                self.turn(str(asked.get('text', '')))
                await self.reply(writer, {**said, 'sent': True})
            elif op == 'stop':
                await self.end('stopped by the person', release=False)
                await self.reply(writer, {**said, 'stopped': True})
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
        async with self.lock:
            await self.flush()
        if self.number is not None:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(nonce.close, self.number)
        if self.record_item is not None:
            await self.write(self.store.edit, self.record_item,
                             {'value': self.summary(f'ended, {how}'), 'extra': self.extra('ended')})
        self.over.set()
        if release:
            self.ended.set()
