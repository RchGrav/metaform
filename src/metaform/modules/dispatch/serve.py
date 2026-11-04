"""serve: Metaform as an ACP agent that editors mount, BASE-062.

An editor that speaks the Agent Client Protocol, Zed, a JetBrains IDE or any ACP client, starts `metaform dispatch
serve` as its agent and speaks ACP v1 with it over standard input and output, newline-delimited JSON-RPC 2.0. One
engine serves two modes.

With an agent behind it, the adapter command after `--`, `agent=<name>`, or the `dispatch_serve_agent` setting,
Metaform is a transparent ACP proxy between the editor and that agent, started when the editor first speaks. Started
by a conductor of the Proxy Chains RFD instead, which initializes it with `proxy/initialize`, Metaform starts no agent
and reaches the chain's next component through the conductor (proxy.py). Either way every message passes through as
the JSON it was, so the editor's client capabilities and the agent's requests of the editor (files, terminals,
permission, elicitation) reach the other side unchanged. Metaform changes only what makes it Metaform:
`session/new`, `session/load` and `session/resume` gain Metaform's MCP server, over ACP itself when the agent
advertises MCP-over-ACP and as a stdio server otherwise; `session/list` adds the dispatch
sessions of the same agent; the agent's slash commands gain Metaform's verbs, and a prompt that is one of them is
answered by Metaform without a turn; each session is recorded in this module's tables on the held ticket editor
sessions hang on, so the dock and the 3D layer show it, and the page can message and interrupt each session by its
id. A terminal login the agent offers is rewritten so the editor's login terminal reaches the agent through this same
command, ACP's terminal authentication. Messages pass first and are recorded after, so the record never slows them.

With none, it is an agent with no model, BASE-003: it answers its verbs as slash commands from their declarations,
lists and loads (replays) the project's dispatch sessions, and says plainly that free text needs an agent behind it.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import queue
import secrets
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any, cast

from metaform import home, settings
from metaform.data import Store, StoreError
from metaform.module import (
    Context,
    Stop,
    chassis_version,
    child_environment,
    context,
    mcp_server,
    on_this_system,
    project_for,
    surface,
)

from . import (
    AGENTS,
    REPLY_LIMIT,
    SERVED,
    anchor,
    argv,
    end_group,
    from_agent,
    group_options,
    origin,
    prompt,
    runner_of,
    sessions,
)
from . import proxy as layers
from .signals import add_line, concerning, mark_peer

settings.choice('dispatch_serve_agent', ['default', 'none', *AGENTS], 'default',
                label='Editor agent',
                help='The agent an editor reaches through metaform dispatch serve when no command follows --: default '
                     'is the dispatch_agent setting, none is Metaform alone, answering its own commands.',
                details='Zed, JetBrains IDEs and other ACP editors start metaform dispatch serve as their agent. With an '
                        'agent behind it, Metaform passes the conversation through, adds its MCP server and records '
                        'the session, so the page shows and steers it. With none, Metaform starts no model.')

EDITOR_TASK = 'Sessions from editors'  # the held ticket editor sessions hang on, beside the person's conversations
OWN = 'metaform:'  # the ids of the requests Metaform itself sends, apart from any the editor or the agent uses
LINE_LIMIT = 64 * 1024 * 1024  # the longest line read from the agent
STREAM_EVERY = 0.5  # seconds between writes of a message still being written, so the page shows it as it grows
LINES_EVERY = 0.25  # at most one `dispatch.session_lines` event per this many seconds
PAGE = 50  # sessions in one page of session/list
CHUNKS = ('agent_message_chunk', 'agent_thought_chunk', 'user_message_chunk')
SETTLE_LIMIT = 10  # seconds a closing session waits for its record to be written
LOGIN = 'METAFORM_SERVE_LOGIN'  # set by the editor's login terminal: the agent's own login arguments, as JSON
REPLAYED = {'person': 'user_message_chunk', 'message': 'user_message_chunk', **{kind: kind for kind in CHUNKS}}
RELEASE_LIMIT = 5  # seconds the agent's next line waits at most for Metaform to pass on a response it took
STEER_LIMIT = 10.0  # seconds a page message waits for the agent to take it into the turn in flight, as the runner's
EARLY_LIMIT = 200  # updates of a session kept while its record is made
UNLISTED = 'unlisted'  # the line, name and kind, that keeps a session out of session/list once an editor deletes it


class Refused(Exception):
    """A JSON-RPC error answered to the editor."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code, self.data = code, data

    def body(self) -> dict[str, Any]:
        error: dict[str, Any] = {'code': self.code, 'message': str(self)}
        if self.data is not None:
            error['data'] = self.data
        return {'error': error}


def refused(stop: Stop) -> Refused:
    return Refused(-32602, str(stop), {'next': stop.next_step})


@dataclass
class Session:
    """One editor session: its folder, Metaform's identity for it, and what it shows. ACP's turns are sequential, so
    every turn the agent is given, the editor's and one the page sends, holds `lock` from its prompt to its answer:
    an editor prompt sent during the page's turn waits for it, and the other way round. `cancels` counts the editor's
    session/cancel, so a prompt that waited through one is answered cancelled and never sent; `queued` counts the turns
    waiting for the lock, so a page message is steered into the turn in flight only when nothing waits before it."""
    session_id: str
    cwd: str
    token: str
    directories: list[str] = field(default_factory=list[str])  # ACP's additionalDirectories, as the editor gave them
    turns: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    cancels: int = 0
    queued: int = 0
    record: Record | None = None
    early: list[dict[str, Any]] | None = field(default_factory=list[dict[str, Any]])  # heard before its record is
    running: asyncio.Task[Any] | None = None  # a command Metaform is answering

    def began(self) -> None:
        self.turns += 1

    def ended(self) -> None:
        self.turns = max(0, self.turns - 1)


def adapter_for(ctx: Context) -> tuple[list[str] | None, str, str | None]:
    """The adapter command to proxy, the name the session is recorded under, and why there is none when the agent the
    settings name cannot be found: then Metaform serves alone and says so, rather than leave the editor with nothing."""
    given: Any = ctx.nouns.get('command')
    words = [str(word) for word in cast(list[Any], given)] if isinstance(given, (list, tuple)) else \
        ([str(given)] if given else [])
    if words:
        command = [shutil.which(words[0]) or words[0], *words[1:]]
        if shutil.which(command[0]) is None and not Path(command[0]).is_file():
            raise Stop(f'The adapter command {words[0]} is not found on this system.', 'metaform help dispatch serve')
        for name in AGENTS:  # an adapter that is one of dispatch's agents is recorded as that agent
            with contextlib.suppress(Stop):
                if argv(str(ctx.setting(f'dispatch_{name}'))) == command:
                    return command, name, None
        return command, Path(words[0]).stem, None
    chosen = str(ctx.nouns.get('agent') or ctx.setting('dispatch_serve_agent') or 'default')
    named = chosen != 'default' and 'agent' in ctx.nouns
    if chosen == 'default':
        chosen = str(ctx.setting('dispatch_agent'))
    if chosen == 'none':
        return None, 'metaform', None
    if chosen not in AGENTS:
        raise Stop(f'{chosen} is not an agent dispatch starts: {", ".join(["none", *AGENTS])}.',
                   'metaform help dispatch serve')
    setting = str(ctx.setting(f'dispatch_{chosen}'))
    command = argv(setting)
    if shutil.which(command[0]) is None and not Path(command[0]).is_file():
        if named:
            raise Stop(f'The start command of {chosen} is not found on this system.',
                       f'metaform set --dispatch-{chosen} "<command>"')
        return None, 'metaform', f'The start command of {chosen}, {setting}, is not found on this system.'
    return command, chosen, None


async def serve(ctx: Context) -> None:
    """`metaform dispatch serve`: speak ACP to the editor on standard input and output until it closes them. Standard
    output carries ACP alone: anything else this process prints goes to standard error."""
    command, agent, missing = adapter_for(ctx)
    login = os.environ.get(LOGIN)
    if login is not None:
        log_in(command, login)
        return
    out = _protocol_output()
    try:
        served = Served(ctx, command, agent, missing, _lines(sys.stdin.buffer), out)
        await served.run()
    finally:
        out.close()


def terminal_login(method: dict[str, Any]) -> dict[str, Any]:
    """An agent's terminal login method as the editor is given it. ACP's terminal authentication has the editor run
    the agent program it is configured with, here `metaform dispatch serve` with its own arguments, plus the method's
    `args` and `env` (agentclientprotocol.com/protocol/authentication). Appended to this command, the agent's own
    arguments would be refused, or taken for part of an adapter command after `--`; so they travel as JSON in one
    variable the method's `env` sets, and `id`, `name`, `env` and `_meta` are kept as the agent gave them. Any other
    method passes as it is."""
    if method.get('type') != 'terminal':
        return method
    args = [str(word) for word in cast(list[Any], method.get('args') or [])]
    env = cast(dict[str, Any], method.get('env') or {})
    return {**{key: value for key, value in method.items() if key != 'args'}, 'env': {**env, LOGIN: json.dumps(args)}}


def log_in(command: list[str] | None, login: str) -> None:
    """The editor's login terminal: this process becomes the agent's adapter run with the login arguments it offered,
    in this terminal with this environment, so the person logs in as the agent itself asks; the editor reads the exit
    status. No ACP is spoken."""
    if command is None:
        raise Stop('No agent is behind metaform dispatch serve here, so there is nothing to log in to.',
                   'metaform help dispatch serve')
    try:
        found: Any = json.loads(login)
    except ValueError:
        found = None
    if not isinstance(found, list):
        raise Stop(f'{LOGIN} is not a JSON list of arguments.', 'metaform help dispatch serve')
    words = [*command, *(str(word) for word in cast(list[Any], found))]
    env = _agent_environment()
    env.pop(LOGIN, None)
    sys.stdout.flush()
    sys.stderr.flush()
    if os.name == 'nt':  # Windows has no exec that keeps the process: run it and end with its status
        raise SystemExit(subprocess.call(words, env=env))
    os.execvpe(words[0], words, env)


class _Output:
    """Lines to the editor, written in the order given by one thread, so a slow reader never blocks the loop."""

    def __init__(self, stream: IO[bytes], restore: Callable[[], None]) -> None:
        self.stream, self.restore = stream, restore
        self.queue: queue.Queue[bytes | None] = queue.Queue()
        self.thread = threading.Thread(target=self._write, daemon=True)
        self.thread.start()

    def _write(self) -> None:
        while (line := self.queue.get()) is not None:
            try:
                self.stream.write(line)
                self.stream.flush()
            except (OSError, ValueError):
                return

    def send(self, message: dict[str, Any]) -> None:
        self.queue.put(json.dumps(message, ensure_ascii=False).encode('utf-8') + b'\n')

    def close(self) -> None:
        self.queue.put(None)
        self.thread.join(5)
        self.restore()


def _protocol_output() -> _Output:
    """Standard output kept for ACP, and the process's own standard output pointed at standard error, so a stray print
    of any code in this process can never break the editor's stream."""
    try:
        fd = sys.stdout.fileno()
        kept = os.dup(fd)
        sys.stdout.flush()
        os.dup2(sys.stderr.fileno(), fd)
    except (OSError, ValueError, AttributeError):  # no file descriptors, as under a host that captures output
        return _Output(sys.stdout.buffer, lambda: None)
    stream = os.fdopen(kept, 'wb', buffering=0)

    def restore() -> None:
        with contextlib.suppress(OSError, ValueError):
            os.dup2(kept, fd)
            stream.close()
    return _Output(stream, restore)


def _lines(stream: IO[bytes]) -> asyncio.Queue[bytes | None]:
    """The editor's lines, read by a thread on every system, ending with None."""
    loop = asyncio.get_running_loop()
    lines: asyncio.Queue[bytes | None] = asyncio.Queue()

    def read() -> None:
        try:
            for line in iter(stream.readline, b''):
                loop.call_soon_threadsafe(lines.put_nowait, line)
        except (OSError, ValueError):
            pass
        finally:
            with contextlib.suppress(RuntimeError):  # the loop has closed
                loop.call_soon_threadsafe(lines.put_nowait, None)
    threading.Thread(target=read, daemon=True).start()
    return lines


def _dicts(value: Any) -> list[dict[str, Any]]:
    """The objects in a JSON list, or none when it is not one."""
    if not isinstance(value, list):
        return []
    return [cast(dict[str, Any], one) for one in cast(list[Any], value) if isinstance(one, dict)]


def _text(blocks: Any) -> str:
    """The text of a prompt's content blocks."""
    return ''.join(str(block.get('text', '')) for block in _dicts(blocks) if block.get('type') == 'text')


def _chunk(content: Any) -> str:
    return str(cast(dict[str, Any], content).get('text', '')) if isinstance(content, dict) else ''


def commands_of(folder: Path) -> dict[str, tuple[list[str], dict[str, Any]]]:
    """Metaform's verbs as ACP slash commands, from the declarations of the folder's command surface: each named as
    its MCP tool, `<module>_<verb>`, MCP-038, described by its summary, with its arguments as the input hint; with the
    command line each runs. Only what an agent may call over MCP is offered: no transport and nothing that runs until
    stopped, so a command always answers."""
    found: dict[str, tuple[list[str], dict[str, Any]]] = {}
    for module in surface(folder):
        for verb in module.verbs:
            if verb.transport or 'cli' not in verb.surfaces or 'mcp' not in verb.surfaces or not on_this_system(verb):
                continue
            name = f'{module.id}_{verb.name}'
            entry: dict[str, Any] = {'name': name, 'description': verb.summary}
            hint = ' '.join(noun.usage() for noun in verb.nouns)
            if hint:
                entry['input'] = {'hint': hint}
            found[name] = ([module.id, verb.name], entry)
    return found


class Served:
    """One editor connection: the agent behind it, if any, and the sessions made on it."""

    def __init__(self, ctx: Context, command: list[str] | None, agent: str, missing: str | None,
                 editor: asyncio.Queue[bytes | None], out: _Output) -> None:
        self.ctx, self.command, self.agent, self.missing = ctx, command, agent, missing
        self.editor, self.out = editor, out
        self.process: asyncio.subprocess.Process | None = None
        self.waiting: dict[str, asyncio.Future[dict[str, Any]]] = {}  # responses Metaform takes, by their id
        self.releases: dict[str, asyncio.Future[None]] = {}  # set once Metaform has passed such a response on
        self.sessions: dict[str, Session] = {}
        self.agent_commands: dict[str, list[Any]] = {}  # the agent's own slash commands, by session
        self.commands: dict[str, dict[str, tuple[list[str], dict[str, Any]]]] = {}  # Metaform's, by folder
        self.tasks: set[asyncio.Task[Any]] = set()
        self.next_id = 0
        self.agent_info: dict[str, Any] | None = None
        self.capabilities: dict[str, Any] = {}
        self.client: dict[str, Any] = {}  # the editor's clientCapabilities, from initialize
        self.agent_lists = False  # whether the agent itself answers session/list
        self.takes_up = False  # whether the agent can take a listed session up: session/load or session/resume
        self.steers = False  # whether the agent takes `_session/steering` into a turn in flight, `_meta.steering`
        self.agent_listed: set[str] = set()  # the sessions the agent listed itself, so Metaform never lists one twice
        self.handling: dict[str, asyncio.Task[Any]] = {}  # the editor's requests Metaform is answering, by their id
        self.withdrawn: set[str] = set()  # those the editor cancelled with $/cancel_request
        self.chain: layers.Chain | None = None  # set when a conductor started Metaform as a proxy of its chain
        self.version = 1  # the ACP version initialize negotiated
        self.mcp_acp = False  # whether the agent takes MCP servers over ACP itself
        self.providers: dict[str, layers.McpProvider] = {}  # Metaform's MCP server over ACP, by serverId
        self.began = False  # whether the editor has spoken, and so the agent behind it been started
        self.finished: asyncio.Future[str] | None = None
        self.successor: asyncio.Queue[dict[str, Any]] = asyncio.Queue()  # the chain's next component's messages

    @property
    def behind(self) -> bool:
        """Whether an agent is behind Metaform: an adapter it started, or the next component of a conductor's chain."""
        return self.process is not None or self.chain is not None

    # ------------------------------------------------------------------ the two sides

    def spawn(self, coroutine: Awaitable[Any]) -> asyncio.Task[Any]:
        task = asyncio.ensure_future(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    def to_editor(self, message: dict[str, Any]) -> None:
        self.out.send({'jsonrpc': '2.0', **message})

    def to_agent(self, message: dict[str, Any]) -> None:
        if self.chain is not None:
            self.chain.to_successor(message)
            return
        assert self.process is not None and self.process.stdin is not None
        self.process.stdin.write(json.dumps({'jsonrpc': '2.0', **message}, ensure_ascii=False).encode('utf-8') + b'\n')

    def update(self, session_id: str, update: dict[str, Any]) -> None:
        self.to_editor({'method': 'session/update', 'params': {'sessionId': session_id, 'update': update}})

    def say(self, session_id: str, text: str, kind: str = 'agent_message_chunk') -> None:
        """One whole message Metaform writes in the session, with a `messageId` of its own, so an editor that groups
        chunks by message never joins it to the agent's (agentclientprotocol.com/rfds/message-id)."""
        self.update(session_id, {'sessionUpdate': kind, 'messageId': f'metaform-{uuid.uuid4().hex}',
                                 'content': {'type': 'text', 'text': text}})

    def notice(self, session_id: str, title: str, description: str) -> None:
        """Something the person should know about the session, as a Session Notice when the editor takes them
        (`clientCapabilities.session.notices`, agentclientprotocol.com/rfds/session-notices), else as a message."""
        offered = self.client.get('session')
        if isinstance(offered, dict) and cast(dict[str, Any], offered).get('notices') is not None:
            self.update(session_id, {'sessionUpdate': 'notice', 'severity': 'warning', 'title': title,
                                     'description': description})
        else:
            self.say(session_id, f'{title}: {description}')

    async def ask_agent(self, message: dict[str, Any]) -> dict[str, Any]:
        """Send a request to the agent and take its response here, rather than pass it to the editor. What the agent
        writes after that response waits until Metaform has passed it on, `release`, so the editor hears the two in the
        agent's order: a session's id before the updates of that session."""
        key = json.dumps(message['id'])
        loop = asyncio.get_running_loop()
        waiting: asyncio.Future[dict[str, Any]] = loop.create_future()
        self.waiting[key] = waiting
        self.releases[key] = loop.create_future()
        try:
            self.to_agent(message)
            return await waiting
        finally:
            self.waiting.pop(key, None)

    def release(self, ident: Any) -> None:
        """The response to request `ident` is passed on, or will never be: the agent's next line may follow it."""
        released = self.releases.pop(json.dumps(ident), None)
        if released is not None and not released.done():
            released.set_result(None)

    def own_id(self) -> str:
        self.next_id += 1
        return f'{OWN}{self.next_id}'

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        self.finished = loop.create_future()
        self.watch(self.spawn(self.read_editor()), 'the editor closed the session')
        with contextlib.suppress(NotImplementedError, RuntimeError):  # an editor that ends its agent with SIGTERM
            loop.add_signal_handler(signal.SIGTERM, lambda: self.editor.put_nowait(None))  # ends it as a close does
        how = 'the session failed'
        try:
            how = await self.finished
        finally:
            for waiting in self.waiting.values():
                if not waiting.done():
                    waiting.set_result({'error': {'code': -32603, 'message': f'The session ended: {how}.'}})
            for released in self.releases.values():
                if not released.done():
                    released.set_result(None)
            for session in list(self.sessions.values()):
                if session.record is not None:
                    with contextlib.suppress(Exception):
                        await session.record.close(how)
            for task in list(self.tasks):
                task.cancel()
            await asyncio.gather(*self.tasks, return_exceptions=True)
            for provider in self.providers.values():
                with contextlib.suppress(Exception):
                    await provider.close()
            if self.process is not None:
                await self.stop_agent()
            with contextlib.suppress(NotImplementedError, RuntimeError):
                loop.remove_signal_handler(signal.SIGTERM)
        sys.stderr.write(f'metaform dispatch serve: {how}.\n')

    def watch(self, side: asyncio.Task[Any], how: str) -> None:
        """The connection ends when either side does: `how` when it ended cleanly, a failure when it raised."""
        def ended(task: asyncio.Task[Any]) -> None:
            if self.finished is not None and not self.finished.done():
                failed = task.cancelled() or task.exception() is not None
                self.finished.set_result('the session failed' if failed else how)
        side.add_done_callback(ended)

    async def begin(self, first: dict[str, Any]) -> None:
        """The editor's first message decides what is behind Metaform: `proxy/initialize` from a conductor makes it a
        proxy of that chain, with no agent of its own; anything else starts the adapter, if there is one."""
        self.began = True
        if first.get('method') in layers.INITIALIZE:
            self.chain = layers.Chain(str(first['method']), self.to_editor)
            self.missing = None  # the agent the settings name is not wanted: the chain has its own
            self.agent = 'successor'  # until its initialize answer names it
            self.watch(self.spawn(self.read_successor()), 'the agent ended')
            return
        if self.command is not None:
            self.process = await asyncio.create_subprocess_exec(
                *self.command, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=None,
                limit=LINE_LIMIT, env=_agent_environment(), **group_options())
            self.watch(self.spawn(self.read_agent()), 'the agent ended')

    async def read_successor(self) -> None:
        """What the chain's next component sends, unwrapped, in its order, as the agent's lines are read."""
        while True:
            await self.from_agent(await self.successor.get())

    async def stop_agent(self) -> None:
        process = self.process
        if process is None:
            return
        if process.stdin is not None:
            with contextlib.suppress(Exception):
                process.stdin.close()
        try:
            await asyncio.wait_for(process.wait(), 5)
        except TimeoutError:
            end_group(process.pid)
            with contextlib.suppress(Exception):
                await asyncio.wait_for(process.wait(), 5)

    async def read_editor(self) -> None:
        while (line := await self.editor.get()) is not None:
            if not line.strip():
                continue
            try:
                found: Any = json.loads(line)
            except ValueError:
                self.to_editor({'id': None, 'error': {'code': -32700, 'message': 'Parse error'}})
                continue
            if not isinstance(found, dict):
                continue
            message = cast(dict[str, Any], found)
            if not self.began:
                await self.begin(message)
            if self.chain is not None:
                theirs, message = self.chain.sort(message)
                if theirs:
                    self.successor.put_nowait(message)
                    continue
            self.from_editor(message)

    def from_editor(self, message: dict[str, Any]) -> None:
        method = message.get('method')
        if not isinstance(method, str):  # the editor's answer to a request of the agent's
            if self.behind:
                self.to_agent(message)
            return
        if 'id' in message:
            self.spawn(self.request(method, message))
        elif method == 'session/cancel':
            self.cancel(message)
        elif method == '$/cancel_request':
            self.cancel_request(message)
        elif self.behind:
            self.to_agent(message)

    def cancel_request(self, message: dict[str, Any]) -> None:
        """ACP's request cancellation (agentclientprotocol.com/rfds/request-cancellation): a request Metaform is
        answering itself stops and is answered -32800, a prompt `cancelled`; one at the agent goes on to the agent,
        which answers it."""
        params = cast(dict[str, Any], message.get('params') or {})
        key = json.dumps(params.get('requestId'))
        task = self.handling.get(key)
        if task is not None and key not in self.waiting:
            self.withdrawn.add(key)
            task.cancel()
        elif self.behind:
            self.to_agent(message)

    async def read_agent(self) -> None:
        assert self.process is not None and self.process.stdout is not None
        while line := await self.process.stdout.readline():
            if not line.strip():
                continue
            try:
                found: Any = json.loads(line)
            except ValueError:
                sys.stderr.write(f'metaform dispatch serve: the agent wrote a line that is not JSON: {line[:200]!r}\n')
                continue
            if isinstance(found, dict):
                await self.from_agent(cast(dict[str, Any], found))

    async def from_agent(self, message: dict[str, Any]) -> None:
        method = message.get('method')
        if not isinstance(method, str):  # a response: Metaform's own, or to the editor's request
            key = json.dumps(message.get('id'))
            waiting = self.waiting.get(key)
            if waiting is not None and not waiting.done():
                waiting.set_result(message)
                if (released := self.releases.get(key)) is not None:  # in the agent's order, as a proxy must keep it
                    with contextlib.suppress(TimeoutError):
                        await asyncio.wait_for(asyncio.shield(released), RELEASE_LIMIT)
            elif not str(message.get('id', '')).startswith(OWN):
                self.to_editor(message)
            return
        if method == 'mcp/message' and 'id' in message:  # a request of the agent's to an MCP server over ACP
            params = cast(dict[str, Any], message.get('params') or {})
            provider = self.providers.get(str(params.get('serverId')))
            if provider is not None:  # Metaform's own; another provider's goes on to the editor
                self.spawn(self.mcp_answer(provider, message['id'], params))
                return
        elif method == '$/cancel_request' and 'id' not in message:
            withdrawn = cast(dict[str, Any], message.get('params') or {}).get('requestId')
            if any(provider.cancel(withdrawn) for provider in self.providers.values()):
                return
        if method == 'session/update' and 'id' not in message:
            params = cast(dict[str, Any], message.get('params') or {})
            session_id = str(params.get('sessionId', ''))
            update = cast(dict[str, Any], params.get('update') or {})
            kind = update.get('sessionUpdate')
            session = self.sessions.get(session_id)
            if kind == 'state_update' and session is not None:  # v2: work begins and ends apart from prompts
                session.turns = 0 if update.get('state') == 'idle' else 1
            if kind == 'available_commands_update':
                self.agent_commands[session_id] = list(cast(list[Any], update.get('availableCommands') or []))
                if session is not None:
                    await self.offer(session)
                    return
            self.to_editor(message)  # first, so the record never holds back what follows it
            if session is not None and (record := session.record) is not None:
                record.later(lambda: record.heard(update))
            elif session is not None and session.early is not None and len(session.early) < EARLY_LIMIT:
                session.early.append(update)  # as the session opened: recorded once its record is made
            return
        self.to_editor(message)

    async def mcp_answer(self, provider: layers.McpProvider, ident: Any, params: dict[str, Any]) -> None:
        """Answer the agent's `mcp/message` request with Metaform's MCP server, under the request's own id."""
        answer = await provider.request(ident, params)
        self.to_agent({'id': ident, **answer})

    # ------------------------------------------------------------------ requests of the editor

    async def request(self, method: str, message: dict[str, Any]) -> None:
        try:
            await self.answered(method, message)
        finally:
            self.release(message['id'])

    async def answered(self, method: str, message: dict[str, Any]) -> None:
        handler = HANDLERS.get(method)
        key = json.dumps(message['id'])
        current = asyncio.current_task()
        if current is not None:
            self.handling[key] = current
        try:
            if handler is None:
                if not self.behind:
                    raise Refused(-32601, f'Method not found: {method}')
                self.to_agent(message)  # its response passes back as it is
                return
            answer = await handler(self, message)
        except asyncio.CancelledError:
            if key not in self.withdrawn:
                raise
            answer = {'result': {'stopReason': 'cancelled'}} if method == 'session/prompt' else \
                {'error': {'code': -32800, 'message': 'Request cancelled'}}
        except Refused as error:
            answer = error.body()
        except Stop as stop:
            answer = refused(stop).body()
        except Exception as error:  # noqa: BLE001  any failure is the editor's answer, never the end of the connection
            answer = {'error': {'code': -32603, 'message': f'{type(error).__name__}: {error}'}}
        finally:
            self.handling.pop(key, None)
            self.withdrawn.discard(key)
        if answer is not None:
            self.to_editor({'id': message['id'], **{name: value for name, value in answer.items()
                                                    if name in ('result', 'error')}})

    async def initialize(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """initialize, or a conductor's proxy/initialize, which the successor is sent as initialize: the agent's answer
        passed back with what Metaform adds, its capabilities read in the version they negotiated (proxy.py)."""
        params = cast(dict[str, Any], message.get('params') or {})
        self.client = layers.client_capabilities(params)
        if self.behind:
            answer = await self.ask_agent({**message, 'method': 'initialize'})
            result = answer.get('result')
            if isinstance(result, dict):
                result = cast(dict[str, Any], result)
                self.version = layers.version_of(result)
                caps = layers.agent_capabilities(result)
                self.agent_lists = layers.lists_sessions(caps, self.version)
                self.takes_up = layers.takes_up(caps, self.version)
                self.mcp_acp = layers.mcp_over_acp(caps, self.version)
                if self.takes_up:  # Metaform adds the dispatch sessions to session/list only where they can be opened
                    layers.advertise_list(result)
                    caps = layers.agent_capabilities(result)
                if isinstance(result.get('authMethods'), list):
                    result['authMethods'] = [terminal_login(cast(dict[str, Any], one)) if isinstance(one, dict)
                                             else one for one in cast(list[Any], result['authMethods'])]
                self.capabilities = caps
                self.agent_info = layers.agent_info(result)
                meta = cast(dict[str, Any], result.get('_meta') or {})  # the steering extension, at the top level
                self.steers = isinstance(meta.get('steering'), dict) and \
                    bool(cast(dict[str, Any], meta['steering']).get('supported'))
                if self.agent not in AGENTS and self.agent_info and self.agent_info.get('name'):
                    self.agent = str(self.agent_info['name'])  # an adapter of no dispatch agent goes by its own name
            return answer
        # ACP v1 as published (agentclientprotocol.com/protocol/initialization): load replays a dispatch session,
        # list and close are answered, and nothing but text is taken.
        return {'result': {
            'protocolVersion': 1,
            'agentCapabilities': {
                'loadSession': True,
                'promptCapabilities': {'image': False, 'audio': False, 'embeddedContext': False},
                'mcpCapabilities': {'http': False, 'sse': False},
                'sessionCapabilities': {'list': {}, 'close': {}, 'delete': {}}},
            'authMethods': [],
            'agentInfo': {'name': 'metaform', 'title': 'Metaform', 'version': chassis_version()}}}

    def with_server(self, params: dict[str, Any], token: str, cwd: str) -> str | None:
        """Metaform's MCP server added to a session's servers, as dispatch's runner adds it, run by this interpreter
        with the session's identity, MCP-010 and BASE-052; why not, when it could not be. A server the editor already
        names metaform is the person's own choice and is kept in its place. With an agent that takes MCP over ACP, it is
        declared `type: "acp"` and Metaform answers the agent's requests to it
        itself (proxy.py), with one registration per session, as each carries its own identity."""
        servers = cast(list[Any], params.get('mcpServers') or [])
        if any(isinstance(one, dict) and cast(dict[str, Any], one).get('name') == 'metaform' for one in servers):
            params['mcpServers'] = servers
            return None
        why: str | None = None
        try:
            command = mcp_server(Path(cwd))
        except Stop as stop:
            command, why = None, f'{stop} Next: {stop.next_step}'
        over_acp = self.mcp_acp
        stdio = self.version < 2 or layers.offered(
            cast(dict[str, Any], layers.session_group(self.capabilities, self.version).get('mcp') or {}), 'stdio')
        if command is not None and over_acp:
            server_id = f'metaform-{token}'
            provider = layers.McpProvider(
                server_id, layers.provider_command(command), cwd,
                layers.provider_environment(child_environment(METAFORM_SESSION=token)), self.to_agent)
            self.providers[server_id] = provider
            servers = [*servers, provider.declaration()]
        elif command is not None and stdio:
            env = [{'name': name, 'value': value} for name, value in
                   sorted(child_environment(METAFORM_SESSION=token).items()) if name.startswith('METAFORM_')]
            servers = [*servers, {**({'type': 'stdio'} if self.version >= 2 else {}), 'name': 'metaform',
                                  'command': sys.executable, 'args': ['-m', *command], 'env': env}]
        elif command is not None:
            why = f'{self.agent} takes neither a stdio MCP server nor MCP over ACP.'
        elif why is None:
            why = 'No enabled module serves MCP here.'
        params['mcpServers'] = servers
        if why:
            sys.stderr.write(f'metaform dispatch serve: no MCP server added: {why}\n')
        return why

    async def new_session(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """session/new, and session/fork of an agent that forks (agentclientprotocol.com/rfds/session-fork, which
        takes the options session/load takes): either way a new session, with Metaform's MCP server, its slash commands
        and its record."""
        params = cast(dict[str, Any], message.setdefault('params', {}))
        cwd = str(params.get('cwd') or os.getcwd())
        directories = [str(one) for one in cast(list[Any], params.get('additionalDirectories') or [])]
        token = secrets.token_hex(8)
        why: str | None = None
        if not self.behind:
            if message['method'] != 'session/new':
                raise Refused(-32601, f'Method not found: {message["method"]}')
            session = Session(f'metaform-{uuid.uuid4().hex}', cwd, token, directories)
            answer: dict[str, Any] = {'result': {'sessionId': session.session_id}}
        else:
            why = await asyncio.to_thread(self.with_server, params, token, cwd)
            answer = await self.ask_agent(message)
            result = answer.get('result')
            if not isinstance(result, dict):
                return answer
            session = Session(str(cast(dict[str, Any], result).get('sessionId')), cwd, token, directories)
        self.sessions[session.session_id] = session
        self.to_editor({'id': message['id'], **answer})
        if self.missing:
            commands = prompt('serve_alone_commands') if await self.has_commands(cwd) else ''
            self.notice(session.session_id, prompt('serve_alone_title'),
                        prompt('serve_alone_notice', why=f'{self.missing} ', commands=commands))
        if why:
            self.notice(session.session_id, prompt('serve_server_title'), why)
        self.release(message['id'])
        await self.offer(session)
        if self.behind:
            await self.recorded(session, None)
        return None

    async def reopen(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """session/load and session/resume: a session of the agent's taken up again, or with Metaform alone, a dispatch
        session's thread replayed. A session a dispatch runner is running is refused: two processes on one session
        would each send it prompts."""
        method = str(message['method'])
        if not self.behind and method != 'session/load':
            raise Refused(-32601, f'Method not found: {method}')
        params = cast(dict[str, Any], message.setdefault('params', {}))
        session_id, cwd = str(params.get('sessionId', '')), str(params.get('cwd') or os.getcwd())
        row = await asyncio.to_thread(self.dispatch_row, cwd, session_id)
        if row is not None and row['state'] == 'running' and row.get('pid') != os.getpid():
            if runner_of(row.get('pid')) == SERVED:
                raise Refused(-32602, f'Session {session_id} is open in another editor through Metaform; continue it '
                                      'there, or close it there first.',
                              {'next': f'metaform dispatch sessions id={row["work_id"]} thread=false'})
            raise Refused(-32602, f'Session {session_id} is running in Metaform for work {row["work_id"]}; talk to '
                                  'it on the page, or stop it there first.',
                          {'next': f'metaform dispatch stop {row["work_id"]}'})
        token = secrets.token_hex(8)
        session = Session(session_id, cwd, token,
                          [str(one) for one in cast(list[Any], params.get('additionalDirectories') or [])])
        if not self.behind:
            if row is None:
                raise Refused(-32002, f'No session {session_id} is recorded in this project.',
                              {'next': 'metaform dispatch sessions thread=false'})
            await self.replay(session_id, cwd)
            self.sessions[session_id] = session
            self.to_editor({'id': message['id'], 'result': {}})
            await self.offer(session)
            return None
        why = await asyncio.to_thread(self.with_server, params, token, cwd)
        answer = await self.ask_agent(message)
        if 'result' not in answer:
            return answer
        self.sessions[session_id] = session
        self.to_editor({'id': message['id'], **answer})
        if why:
            self.notice(session_id, prompt('serve_server_title'), why)
        self.release(message['id'])
        await self.offer(session)
        await self.recorded(session, row)
        return None

    async def close_session(self, message: dict[str, Any]) -> dict[str, Any] | None:
        params = cast(dict[str, Any], message.get('params') or {})
        session = self.sessions.pop(str(params.get('sessionId', '')), None)
        answer: dict[str, Any] = await self.ask_agent(message) if self.behind else {'result': {}}
        if session is not None and session.record is not None:
            await session.record.close('the editor closed the session')
        return answer

    async def delete_session(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """session/delete (agentclientprotocol.com/protocol/session-list): the session leaves every later session/list.
        The agent deletes its own; Metaform keeps the dispatch session out of the sessions it adds, and alone, or for a
        session the agent does not know, that is the whole of it. A session the agent refused and Metaform does not
        hold keeps the agent's answer."""
        params = cast(dict[str, Any], message.get('params') or {})
        session_id = str(params.get('sessionId', ''))
        answer: dict[str, Any] | None = await self.ask_agent(message) if self.behind else None
        if answer is not None and 'result' not in answer and session_id in self.agent_listed:
            return answer
        held = self.sessions.get(session_id)
        unlisted = await asyncio.to_thread(_unlist, session_id, held.cwd if held is not None else None)
        if answer is not None and ('result' in answer or not unlisted):
            return answer
        if not unlisted:
            raise Refused(-32002, f'No session {session_id} is recorded in this home.',
                          {'next': 'metaform dispatch sessions thread=false'})
        return {'result': {}}

    def dispatch_row(self, cwd: str, session_id: str) -> dict[str, Any] | None:
        store = _store(cwd)
        if store is None:
            return None
        return next((row for row in sessions(store) if row['session_id'] == session_id), None)

    async def replay(self, session_id: str, cwd: str) -> None:
        """A dispatch session's thread as ACP replays a loaded session: what was said, by whom, and each tool call."""
        def read() -> list[dict[str, Any]]:
            store = _store(cwd)
            if store is None:
                return []
            with Store(store.project_id, module='dispatch').tables(write=False) as tx:
                return [dict(row) for row in tx.rows('session_lines', {'session_id': session_id},
                                                      by=('session_id', 'seq'), limit=0).results]
        for row in await asyncio.to_thread(read):
            kind, text = str(row['kind']), str(row['text'])
            if kind in REPLAYED:
                self.say(session_id, text, REPLAYED[kind])
            elif kind in ('tool_call', 'tool_call_update'):
                self.update(session_id, {'sessionUpdate': 'tool_call', 'toolCallId': str(row['name']),
                                         'title': text, 'status': 'completed'})

    async def list_sessions(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """session/list (agentclientprotocol.com/protocol/session-list): the agent's own pages first, when it lists
        sessions, then Metaform's pages of the dispatch sessions it can open, each a session the agent did not list
        itself; Metaform's cursors begin with `metaform:`. Alone, every dispatch session is listed and replayed."""
        params = cast(dict[str, Any], message.get('params') or {})
        cursor, cwd = params.get('cursor'), params.get('cwd')
        wanted = str(cwd) if isinstance(cwd, str) and cwd else None
        if isinstance(cursor, str) and cursor.startswith(OWN):
            at = cursor[len(OWN):]
            return {'result': await asyncio.to_thread(self.our_page, wanted, int(at) if at.isdigit() else 0)}
        result: dict[str, Any] = {'sessions': []}
        if self.behind and self.agent_lists:
            answer = await self.ask_agent(message)
            if not isinstance(answer.get('result'), dict):
                return answer
            result = cast(dict[str, Any], answer['result'])
            self.agent_listed.update(str(one.get('sessionId')) for one in _dicts(result.get('sessions')))
            if result.get('nextCursor'):
                return answer  # a page of the agent's own; Metaform's follow its last
        if self.behind and not self.takes_up:
            return {'result': result}
        page = await asyncio.to_thread(self.our_page, wanted, 0)
        return {'result': {**result, 'sessions': [*_dicts(result.get('sessions')), *page['sessions']],
                           **({'nextCursor': page['nextCursor']} if 'nextCursor' in page else {})}}

    def our_page(self, cwd: str | None, start: int) -> dict[str, Any]:
        ours = [one for one in self.listed(cwd) if one['sessionId'] not in self.agent_listed]
        page: dict[str, Any] = {'sessions': ours[start:start + PAGE]}
        if start + PAGE < len(ours):
            page['nextCursor'] = f'{OWN}{start + PAGE}'
        return page

    def listed(self, cwd: str | None) -> list[dict[str, Any]]:
        """The dispatch sessions as ACP lists sessions, the latest first, each with the folder it worked in: with
        `cwd`, only those that worked there, of the project the folder is in; without, those of every project this
        home knows. An agent behind Metaform takes up only its own kind of session."""
        if cwd is not None:
            stores = [found] if (found := _store(cwd)) is not None else []
            wanted: str | None = _resolved(cwd)
        else:
            stores = [Store(project.project_id, module='dispatch') for project in home.projects()]
            wanted = None
        listed: list[tuple[str, dict[str, Any]]] = []
        for store in stores:
            try:
                folder = _resolved(store.project().path)
                tasks = {record.id: record.task or '' for record in store.work(limit=0).results}
            except (StoreError, Stop, OSError):
                continue
            rows = sessions(store, verify=False)
            if self.behind:
                rows = [row for row in rows if row['agent'] == self.agent]
            states = _states(store, [str(row['session_id']) for row in rows])
            for row in rows:
                state = states.get(str(row['session_id']))
                if state is None:  # deleted from an editor's list
                    continue
                place = _resolved(str(state['cwd'])) if state.get('cwd') else folder
                if wanted is not None and place != wanted:
                    continue
                task = tasks.get(str(row['work_id']))
                # the title and last activity the agent gave (session_info_update), else the ticket and the start
                title = str(state.get('title') or (f'{row["agent"]} on {task}' if task else f'{row["agent"]} session'))
                updated = str(state.get('updated_at') or state.get('active_at') or row['started'])
                directories = [str(one) for one in cast(list[Any], state.get('additional_directories') or [])]
                listed.append((updated, {
                    'sessionId': str(row['session_id']), 'cwd': place, 'title': title, 'updatedAt': updated,
                    **({'additionalDirectories': directories} if directories else {}),
                    '_meta': {'metaform': {'work_id': row['work_id'], 'agent': row['agent'], 'state': row['state'],
                                           'project': store.project_id}}}))
        listed.sort(key=lambda one: one[0], reverse=True)
        return [one for _, one in listed]

    async def prompt_turn(self, message: dict[str, Any]) -> dict[str, Any] | None:
        params = cast(dict[str, Any], message.get('params') or {})
        session_id = str(params.get('sessionId', ''))
        session = self.sessions.get(session_id)
        if session is None:  # a session this connection did not make: Metaform alone still answers it
            session = self.sessions.setdefault(session_id, Session(session_id, os.getcwd(), secrets.token_hex(8)))
        seen = session.cancels  # before any wait, so a cancel sent while the prompt is read is one it waited through
        text = _text(params.get('prompt'))
        command = await asyncio.to_thread(self.command_of, session, text)
        if command is not None:
            if (record := session.record) is not None:
                record.later(lambda: record.said('person', text))
            if self.version >= 2:  # v2 answers a prompt once it is inserted; the work's end is a state_update
                return await self.answer_inserted(message, session, command, params.get('prompt'))
            reason = await self.answer(session, *command)
            return {'result': {'stopReason': reason}}
        if not self.behind:
            listed = prompt('serve_commands') if await self.has_commands(session.cwd) else ''
            self.say(session_id, prompt('serve_free_text', why=f'{self.missing} ' if self.missing else '',
                                        commands=listed))
            return {'result': {'stopReason': 'end_turn'}}
        if session.cancels != seen:
            return {'result': {'stopReason': 'cancelled'}}
        async with self.queue(session):  # after a turn the page sent, never beside it
            if session.cancels != seen:
                return {'result': {'stopReason': 'cancelled'}}
            if (record := session.record) is not None and self.version < 2:  # v2 agents report the user message
                record.later(lambda: record.said('person', text))
            return await self.turn(session, message)

    async def has_commands(self, cwd: str) -> bool:
        """Whether Metaform offers slash commands in the folder, so nothing tells the person to type / for none."""
        return bool(await asyncio.to_thread(self.own_commands, cwd))

    async def answer_inserted(self, message: dict[str, Any], session: Session, command: tuple[list[str], str],
                              blocks: Any) -> None:
        """One of Metaform's commands in a v2 session (rfds/v2/prompt): the prompt is answered with the message id it
        was inserted under, the message is reported, and the work is bracketed by `state_update` running and idle."""
        inserted = f'metaform-{uuid.uuid4().hex}'
        self.to_editor({'id': message['id'], 'result': {'messageId': inserted}})
        self.release(message['id'])
        sid = session.session_id
        self.update(sid, {'sessionUpdate': 'user_message', 'messageId': inserted, 'content': _dicts(blocks)})
        self.update(sid, {'sessionUpdate': 'state_update', 'state': 'running'})
        reason = 'cancelled'
        try:
            reason = await self.answer(session, *command)
        finally:
            self.update(sid, {'sessionUpdate': 'state_update', 'state': 'idle', 'stopReason': reason})

    @contextlib.asynccontextmanager
    async def queue(self, session: Session) -> AsyncGenerator[None]:
        """The session's turn, after those before it; `queued` counts those still waiting for theirs."""
        session.queued += 1
        try:
            await session.lock.acquire()
        finally:
            session.queued -= 1
        try:
            yield
        finally:
            session.lock.release()

    async def turn(self, session: Session, message: dict[str, Any]) -> dict[str, Any]:
        """One turn of the agent's, with the session's lock held by the caller; recorded after, off its path. In v2
        the answer comes at insertion and the turn's end is a `state_update`, recorded as it is heard."""
        record = session.record
        if record is not None:
            record.later(record.changed)
        if self.version >= 2:
            return await self.ask_agent(message)
        session.began()
        try:
            answer = await self.ask_agent(message)
        finally:
            session.ended()
        if record is not None:
            result = cast(dict[str, Any], answer.get('result') or {})
            reason = str(result.get('stopReason')
                         or f'error: {cast(dict[str, Any], answer.get("error") or {}).get("message")}')
            record.later(lambda: record.turned(reason))
        return answer

    async def steer(self, session: Session, text: str) -> bool | None:
        """A page message into the turn in flight, as the dispatch runner delivers one, P016: with the agent's
        `_session/steering` request when it advertises it, a turn is in flight and nothing
        waits before it. True when the agent took it into the turn; False when it is to go as the next prompt, the
        agent having answered promptRequired or refused it; None when the agent did not answer in time, so the request
        is withdrawn with `$/cancel_request` and, since the agent may have taken it, never sent again."""
        if not (self.steers and session.turns and not session.queued and self.behind):
            return False
        ident = self.own_id()
        try:
            answer = await asyncio.wait_for(self.ask_agent({
                'id': ident, 'method': '_session/steering',
                'params': {'sessionId': session.session_id, 'prompt': [{'type': 'text', 'text': text}],
                           '_meta': {'steering': {'idleBehavior': 'promptRequired'}}}}), STEER_LIMIT)
        except TimeoutError:
            self.to_agent({'method': '$/cancel_request', 'params': {'requestId': ident}})
            return None
        finally:
            self.release(ident)
        result = answer.get('result')
        return isinstance(result, dict) and cast(dict[str, Any], result).get('outcome') == 'injected'

    def shown(self, session: Session, text: str, by: str) -> None:
        """A page message shown in the editor as a message of its own; one another agent sent says so, as the thread
        does: an agent's message is never shown as the person's, BASE-052."""
        self.say(session.session_id, from_agent(by, text) if by else text, 'user_message_chunk')

    async def steered(self, session: Session, text: str, by: str) -> None:
        """A page message sent to the agent as the editor would send it, in its own turn after any turn in flight."""
        async with self.queue(session):
            self.shown(session, text, by)
            ident = self.own_id()
            try:
                await self.turn(session, {'id': ident, 'method': 'session/prompt',
                                          'params': {'sessionId': session.session_id,
                                                     'prompt': [{'type': 'text', 'text': text}]}})
            finally:
                self.release(ident)

    async def peer_turn(self, session: Session, envelope: dict[str, Any]) -> None:
        """An editor receives the authored message; sender provenance stays in the registered note."""
        text = str(envelope.get('text') or '')
        async with self.queue(session):
            record = session.record
            if record is None or record.closed:
                return
            sender = cast(dict[str, Any], envelope.get('from') or {})
            self.shown(session, text, str(sender.get('agent') or 'peer'))
            ident = self.own_id()
            try:
                answer = await self.turn(session, {'id': ident, 'method': 'session/prompt',
                    'params': {'sessionId': session.session_id, 'prompt': [{'type': 'text', 'text': text}]}})
                if 'error' in answer:
                    await record.peer_state(envelope, 'failed')
                else:
                    await record.peer_state(envelope, 'delivered')
                    result = cast(dict[str, Any], answer.get('result') or {})
                    if self.version < 2 and result.get('stopReason') != 'cancelled':
                        await record.peer_state(envelope, 'read')
            finally:
                self.release(ident)

    def cancel(self, message: dict[str, Any]) -> None:
        """session/cancel: Metaform's command stops; the agent's turn, the page's included, is cancelled by the agent;
        and an editor prompt still waiting for the page's turn is answered cancelled, never sent."""
        params = cast(dict[str, Any], message.get('params') or {})
        session = self.sessions.get(str(params.get('sessionId', '')))
        if session is not None:
            session.cancels += 1
            if session.running is not None:
                session.running.cancel()
        if self.behind:
            self.to_agent(message)

    # ------------------------------------------------------------------ Metaform's own commands

    def own_commands(self, cwd: str) -> dict[str, tuple[list[str], dict[str, Any]]]:
        if cwd not in self.commands:
            self.commands[cwd] = commands_of(Path(cwd))
        return self.commands[cwd]

    def command_of(self, session: Session, text: str) -> tuple[list[str], str] | None:
        """The command line a prompt runs when it is one of Metaform's slash commands, with the text after it."""
        stripped = text.strip()
        if not stripped.startswith('/'):
            return None
        name, _, rest = stripped[1:].partition(' ')
        if name in {str(one.get('name')) for one in _dicts(self.agent_commands.get(session.session_id))}:
            return None  # the agent's own command of that name goes to the agent
        found = self.own_commands(session.cwd).get(name)
        return (found[0], rest.strip()) if found is not None else None

    async def offer(self, session: Session) -> None:
        """The session's slash commands: the agent's own, then Metaform's that do not take one of their names."""
        theirs = _dicts(self.agent_commands.get(session.session_id))
        names = {str(one.get('name')) for one in theirs}
        ours = [entry for name, (_, entry) in (await asyncio.to_thread(self.own_commands, session.cwd)).items()
                if name not in names]
        if not theirs and not ours:
            return
        self.update(session.session_id, {'sessionUpdate': 'available_commands_update',
                                         'availableCommands': [*theirs, *ours]})
        if (record := session.record) is not None:  # the agent's own, as the runner keeps them
            record.later(lambda: record.state({'commands': theirs, 'metaform_commands': bool(ours)}))

    async def answer(self, session: Session, words: list[str], rest: str) -> str:
        """Run one of Metaform's commands as the person, in the session's folder, and show what it prints."""
        session.running = asyncio.current_task()
        try:
            given = shlex.split(rest, posix=os.name != 'nt')
        except ValueError as error:
            self.say(session.session_id, f'The arguments do not parse: {error}')
            session.running = None
            return 'end_turn'
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable, '-m', 'metaform', *words, *given, cwd=session.cwd, stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=child_environment())
        except asyncio.CancelledError:
            session.running = None
            return 'cancelled'
        try:
            printed, errors = await process.communicate()
        except asyncio.CancelledError:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            await process.wait()
            return 'cancelled'
        finally:
            session.running = None
        shown = printed.decode('utf-8', 'replace')
        if process.returncode:
            shown += errors.decode('utf-8', 'replace')
        text = f'```\n{shown.strip()}\n```' if shown.strip() else f'metaform {" ".join(words)}: done.'
        self.say(session.session_id, text)
        if (record := session.record) is not None:
            record.later(lambda: record.said('agent_message_chunk', text))
        return 'end_turn'

    # ------------------------------------------------------------------ the record the page reads

    async def recorded(self, session: Session, row: dict[str, Any] | None) -> None:
        """Record a session of the agent's, so the page shows it: a new row on the held ticket editor sessions hang
        on, or a dispatch session's own row taken up again. Nothing is recorded where there is no project or map; the
        session works the same."""
        early, session.early = session.early or [], None
        try:
            record = await asyncio.to_thread(Record.made, self, session, row)
        except (Stop, StoreError) as error:
            sys.stderr.write(f'metaform dispatch serve: session {session.session_id} is not recorded: {error}\n')
            return
        if record is not None:
            session.record = record
            record.later(lambda: record.open(row))
            for update in early:
                record.later(lambda update=update: record.heard(update))


def _store(cwd: str) -> Store | None:
    """The dispatch store of the project a folder is in, or None for a folder of no project."""
    try:
        project = project_for(Path(cwd))
    except Stop:
        return None
    return Store(project, module='dispatch') if project else None


def _resolved(folder: str) -> str:
    try:
        return str(Path(folder).resolve())
    except OSError:
        return folder


def _states(store: Store, session_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Each session's state line, read in one transaction: the folder it worked in, and for an editor's session the
    title and last activity its agent gave; an empty one for a session that kept none, and none at all for a session
    an editor deleted from its list."""
    found: dict[str, dict[str, Any]] = {}
    try:
        with Store(store.project_id, module='dispatch').tables(write=False) as tx:
            for session_id in session_ids:
                if tx.get('session_lines', {'session_id': session_id, 'name': UNLISTED}) is not None:
                    continue
                line = tx.get('session_lines', {'session_id': session_id, 'name': 'state'})
                held: Any = None
                with contextlib.suppress(ValueError, TypeError, KeyError):
                    held = json.loads(str(line['text'])) if line is not None else None
                found[session_id] = cast(dict[str, Any], held) if isinstance(held, dict) else {}
    except StoreError:
        pass
    return found


def _unlist(session_id: str, cwd: str | None) -> bool:
    """Keep a dispatch session out of every later session/list, as session/delete asks: a line of its own, read by
    nothing else and left out of the thread the page shows. False when no project of this home records the session."""
    stores = [found] if cwd is not None and (found := _store(cwd)) is not None else []
    stores += [Store(project.project_id, module='dispatch') for project in home.projects()]
    for store in stores:
        try:
            with Store(store.project_id, module='dispatch').tables() as tx:
                row = tx.get('agent_sessions', {'session_id': session_id})
                if row is None:
                    continue
                if tx.get('session_lines', {'session_id': session_id, 'name': UNLISTED}) is None:
                    tx.insert('session_lines', {'session_id': session_id, 'name': UNLISTED,
                                                'work_id': row['work_id'], 'kind': UNLISTED, 'text': _stamp(),
                                                'seq': 0})
                return True
        except StoreError:
            continue
    return False


def _agent_environment() -> dict[str, str]:
    from .runner import agent_environment
    return agent_environment()


class Record:
    """A session as this module's tables keep it, BASE-052: its row, the lines of its thread, and the control port the
    page reaches it on, `status`, `message` and `interrupt`."""

    def __init__(self, served: Served, session: Session, ctx: Context, store: Store, work_id: str) -> None:
        self.served, self.session, self.ctx, self.store, self.work_id = served, session, ctx, store, work_id
        self.token = secrets.token_hex(16)
        self.port = 0
        self.server: asyncio.Server | None = None
        self.lines = 0
        self.named: set[str] = set()
        self.flow_kind: str | None = None
        self.flow_key: str | None = None
        self.flow_text = ''
        self.flow_at = 0.0
        self.flows = 0
        self.texts: dict[str, str] = {}  # each message's text so far, by its line's key, `message:<messageId>`
        self.calls: dict[str, dict[str, Any]] = {}  # each tool call as its updates left it, by toolCallId
        self.lines_at = 0.0
        self.lines_due: asyncio.TimerHandle | None = None
        self.base_id: str | None = None
        self.closed = False
        self.how: str | None = None
        self.backlog: deque[Callable[[], Awaitable[Any]]] = deque()
        self.writer: asyncio.Task[Any] | None = None
        self.queued_peer_ids: set[str] = set()

    def later(self, step: Callable[[], Awaitable[Any]]) -> None:
        """Write to the record in order, after what was asked before, on a task of its own: what the editor and the
        agent say to each other never waits for the store, a subscriber or the relay. A write that fails is said on
        standard error and the session goes on."""
        if self.closed:
            return
        self.backlog.append(step)
        if self.writer is None or self.writer.done():
            self.writer = self.served.spawn(self.drain())

    async def drain(self) -> None:
        while self.backlog:
            step = self.backlog.popleft()
            try:
                await step()
            except asyncio.CancelledError:
                raise
            except Exception as error:  # noqa: BLE001  the record is not the session
                sys.stderr.write(f'metaform dispatch serve: session {self.session.session_id} was not recorded in '
                                 f'full: {type(error).__name__}: {error}\n')

    async def settled(self) -> None:
        """Wait, a while at most, for what was asked to be written."""
        if self.writer is not None and not self.writer.done():
            await asyncio.wait({self.writer}, timeout=SETTLE_LIMIT)

    @classmethod
    def made(cls, served: Served, session: Session, row: dict[str, Any] | None) -> Record | None:
        store = _store(session.cwd)
        if store is None:
            return None
        ctx = context('dispatch', Path(session.cwd), project=store.project_id)
        if row is not None:
            return cls(served, session, ctx, store, str(row['work_id']))
        # At the DE once the intake has given the map its roots; before that, at the first node of the map.
        mapped = ctx.require_store()
        first = mapped.graph(limit=50).elements
        held = anchor(ctx, mapped, first[0].element.address if first else None, task=EDITOR_TASK)
        return cls(served, session, ctx, store, held)

    async def open(self, row: dict[str, Any] | None) -> None:
        self.server = await asyncio.start_server(self.control, '127.0.0.1', 0)
        self.port = int(self.server.sockets[0].getsockname()[1])
        mine = {'state': 'running', 'pid': os.getpid(), 'port': self.port, 'token': self.token, 'how': None,
                'runner': self.session.token, 'origin': origin(), 'ended': ''}
        session_id = self.session.session_id

        def write(tx: Any) -> None:
            if row is not None and tx.get('agent_sessions', {'session_id': session_id}) is not None:
                tx.update('agent_sessions', {'session_id': session_id}, mine)
                found = tx.rows('session_lines', {'session_id': session_id}, by=('session_id', 'seq'),
                                limit=0).results
                self.lines = max((int(one['seq']) for one in found), default=0)
                self.named = {str(one['name']) for one in found}
            else:
                tx.insert('agent_sessions', {'session_id': session_id, 'work_id': self.work_id,
                                             'agent': self.served.agent, 'started': _stamp(),
                                             'seq': time.time_ns() // 1_000_000, **mine})
        await self.table(write, 'agent_sessions')
        await self.state({'editor': True, 'cwd': self.session.cwd,
                          'additional_directories': self.session.directories,
                          'capabilities': self.served.capabilities,
                          'agent_info': self.served.agent_info,
                          'commands': _dicts(self.served.agent_commands.get(session_id))})

    async def table(self, change: Callable[[Any], Any], name: str = 'session_lines') -> Any:
        def done() -> Any:
            with self.store.tables() as tx:
                return change(tx)
        result = await asyncio.to_thread(done)
        if name == 'session_lines':
            await self.lines_changed()
        else:
            await self.changed([f'dispatch.{name}'])
        return result

    async def changed(self, tables: list[str] | None = None) -> None:
        if self.base_id is None:
            active = await asyncio.to_thread(self.ctx.require_store().active_base)
            self.base_id = active.id if active is not None else None
        if self.lines_due is not None:
            self.lines_due.cancel()
            self.lines_due = None
        self.lines_at = time.monotonic()
        named: list[str] = sorted({*(tables or []), 'dispatch.session_lines'})
        await self.ctx.publish_async('map.changed', {'project': self.store.project_id, 'base_id': self.base_id,
                                                     'tables': 'dispatch', 'dispatch_tables': named,
                                                     **concerning(self.work_id, self.session.session_id, named)})

    async def lines_changed(self) -> None:
        wait = self.lines_at + LINES_EVERY - time.monotonic()
        if wait <= 0:
            await self.changed()
        elif self.lines_due is None:
            self.lines_due = asyncio.get_running_loop().call_later(
                wait, lambda: self.served.spawn(self.changed()))

    async def note(self, key: str | None, kind: str, text: str) -> None:
        """A line of the thread: a new one, or the one kept for `key` changed in place."""
        if self.closed:
            return
        session_id, known = self.session.session_id, self.lines
        try:  # numbered from the table, so another writer on the session takes no name of ours, code.dispatcher.agent#12
            written = await self.table(lambda tx: add_line(tx, session_id, self.work_id, key, kind, text, known))
        except Exception as error:  # noqa: BLE001  a line not written never ends the session; it is logged
            sys.stderr.write(f'A line of session {session_id} on work {self.work_id} was not written: {error}\n')
            return
        self.named.add(written[0])
        self.lines = max(self.lines, written[1])

    async def flush(self) -> None:
        kind, text, key = self.flow_kind, self.flow_text, self.flow_key
        self.flow_kind, self.flow_text, self.flow_key = None, '', None
        if kind is not None and text:
            await self.note(key, kind, text)

    async def said(self, kind: str, text: str, key: str | None = None) -> None:
        await self.flush()
        await self.note(key, kind, text)

    async def heard(self, update: dict[str, Any]) -> None:
        """What the agent sent the editor, kept as the runner keeps it: text as it grows, and each tool call. A message
        with a `messageId` keeps one line under that id, so a v2 whole-message upsert replaces its text, a chunk
        appends, and a replay that clears and resends it leaves one line, not two; a tool call keeps one line under
        its id, every update patching it, with the files it changes (proxy.py)."""
        kind = str(update.get('sessionUpdate', ''))
        if kind == 'session_info_update':  # the title and last activity the agent gives, for session/list
            given = {name: update[key] for key, name in (('title', 'title'), ('updatedAt', 'updated_at'))
                     if key in update}
            if given:
                await self.state(given)
            return
        message_id = update.get('messageId')
        if kind in layers.MESSAGES and isinstance(message_id, str):  # v2: the message's content as a whole
            await self.flush()
            key, shown = f'message:{message_id}', layers.MESSAGES[kind]
            if 'content' in update:
                self.texts[key] = layers.text_of(update.get('content'))
                if self.texts[key] or key in self.named:
                    await self.note(key, shown, self.texts[key])
            return
        if kind in CHUNKS:
            key = f'message:{message_id}' if isinstance(message_id, str) else None
            if kind != self.flow_kind or (key is not None and key != self.flow_key):
                await self.flush()
                self.flow_kind = kind
                if key is None:
                    self.flows += 1
                    key = f'flow:serve:{self.flows}'
                self.flow_key = key
                self.flow_text = self.texts.get(key, '')
            self.flow_text += _chunk(update.get('content'))
            if self.flow_key is not None and self.flow_key.startswith('message:'):
                self.texts[self.flow_key] = self.flow_text
            now = time.monotonic()
            if now - self.flow_at >= STREAM_EVERY:
                self.flow_at = now
                await self.note(self.flow_key, kind, self.flow_text)
            return
        await self.flush()
        if kind in ('tool_call', 'tool_call_update', 'tool_call_content_chunk'):
            ident = str(update.get('toolCallId', ''))
            call = self.calls.setdefault(ident, {'title': None, 'status': 'pending', 'files': []})
            if update.get('title'):
                call['title'] = update['title']
            if update.get('status'):
                call['status'] = update['status']
            content = [update['content']] if kind == 'tool_call_content_chunk' else update.get('content')
            for change in layers.file_changes(content):
                if change not in call['files']:
                    call['files'].append(change)
            files = f': {"; ".join(call["files"])}' if call['files'] else ''
            await self.note(f'tool:{ident}', 'tool_call', f'{call["title"] or "A tool call"} ({call["status"]}){files}')
        elif kind in ('plan', 'plan_update'):
            await self.note('plan', 'plan', '\n'.join(layers.plan_lines(update)))
        elif kind == 'state_update':  # v2: work runs and ends apart from prompts, idle with why it stopped
            state = str(update.get('state', ''))
            if state == 'idle':
                error = update.get('error')
                reason = str(update.get('stopReason') or 'end_turn')
                if isinstance(error, dict) and cast(dict[str, Any], error).get('message'):
                    reason = f'{reason}: {cast(dict[str, Any], error)["message"]}'
                await self.turned(reason)
            elif state:
                await self.state({'activity': state})

    async def turned(self, reason: str) -> None:
        await self.flush()
        await self.note('turn', 'turn', f'The turn ended: {reason}.')
        await self.state({'active_at': _stamp()})  # the last activity session/list gives, when the agent gives none

    async def state(self, more: dict[str, Any]) -> None:
        """The session's state line, as the runner keeps one: what the agent can do and its slash commands."""
        session_id = self.session.session_id

        def merged(tx: Any) -> None:
            found = tx.get('session_lines', {'session_id': session_id, 'name': 'state'})
            held: dict[str, Any] = {}
            if found is not None:
                with contextlib.suppress(ValueError, TypeError):
                    held = cast(dict[str, Any], json.loads(str(found['text'])))
            text = json.dumps({**held, **more}, ensure_ascii=False)
            _, seq = add_line(tx, session_id, self.work_id, 'state', 'state', text, self.lines)
            self.named.add('state')
            self.lines = max(self.lines, seq)
        if not self.closed:
            await self.table(merged)

    async def close(self, how: str) -> None:
        if self.closed:
            return
        await self.settled()
        if self.closed:
            return
        await self.flush()
        self.closed, self.how = True, how
        session_id = self.session.session_id
        if self.server is not None:
            self.server.close()
        await self.table(lambda tx: tx.update('agent_sessions', {'session_id': session_id},
                                              {'state': 'ended', 'how': how, 'ended': home.now()}), 'agent_sessions')

    async def peer_state(self, envelope: dict[str, Any], state: str) -> None:
        sender = cast(dict[str, Any], envelope.get('from') or {})
        recipient = self.session.session_id

        def write(tx: Any) -> None:
            for session_id in {recipient, str(sender.get('session_id') or '')} - {''}:
                mark_peer(tx, session_id, str(envelope['id']), self.work_id, state, recipient_session=recipient)
        await self.table(write)

    async def control(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """One request on the control port with this session's token, as the page sends a runner's: `status`,
        `message` and `interrupt`. Permission requests are the editor's to answer, and the session ends when the
        editor closes it."""
        try:
            line = await asyncio.wait_for(reader.readline(), REPLY_LIMIT)
            found: Any = json.loads(line) if line else None
            asked = cast(dict[str, Any], found) if isinstance(found, dict) else {}
            if asked.get('token') != self.token:
                await _reply(writer, {'error': 'This is not a request for this session.'})
                return
            session = self.session
            said = {'work_id': self.work_id, 'agent': self.served.agent, 'session_id': session.session_id}
            op = asked.get('op')
            if op == 'status':
                live = not self.closed
                await _reply(writer, {**said, 'state': 'running' if live else 'ended', 'agent_alive': live,
                                      'activity': 'working' if session.turns else 'idle', 'interrupting': False,
                                      'how': None if live else self.how})
            elif op == 'note':
                envelope = cast(dict[str, Any], asked.get('line') or {})
                note_id = str(envelope.get('id') or '')
                if not note_id or self.closed:
                    await _reply(writer, {**said, 'noted': False, 'error': 'The note or recipient is unavailable.'})
                    return
                await self.note(f'peer:{note_id}', 'peer', json.dumps(envelope, ensure_ascii=False))
                if asked.get('deliver') and note_id not in self.queued_peer_ids:
                    self.queued_peer_ids.add(note_id)
                    self.served.spawn(self.served.peer_turn(session, envelope))
                await _reply(writer, {**said, 'noted': True, 'queued': bool(asked.get('deliver')), 'steered': False})
            elif op == 'message':
                text, by = str(asked.get('text', '')), str(asked.get('by') or '')
                sent = str(asked.get('broadcast') or '')  # one message of a broadcast, kept under its id
                self.later(lambda: self.said('message' if by else 'person',
                                             from_agent(by, text) if by else text,
                                             f'broadcast:{sent}' if sent else None))
                steered = await self.served.steer(session, text)  # into the turn in flight, as the runner does
                if steered is False:
                    self.served.spawn(self.served.steered(session, text, by))
                else:
                    self.served.shown(session, text, by)
                    self.later(lambda: self.note(
                        None, 'steered', 'Delivered into the running turn.' if steered else
                        f'{self.served.agent} did not answer the steer in time, so it was withdrawn; it may have '
                        'reached the turn, so it is not sent again. Send it again if it did not.'))
                await _reply(writer, {**said, 'sent': True, 'steered': steered})
            elif op == 'interrupt':
                self.served.to_agent({'method': 'session/cancel', 'params': {'sessionId': session.session_id}})
                self.later(lambda: self.note(None, 'interrupt', 'Cancellation of the current turn requested.'))
                await _reply(writer, {**said, 'requested': bool(session.turns)})
            elif op in ('permit', 'configure', 'stop'):
                await _reply(writer, {**said, 'error': 'This session runs in an editor: answer it and end it there.'})
            else:
                await _reply(writer, {'error': f'No request {op}.'})
        except (TimeoutError, OSError, ValueError):
            pass
        finally:
            with contextlib.suppress(Exception):
                writer.close()


async def _reply(writer: asyncio.StreamWriter, answer: dict[str, Any]) -> None:
    writer.write(json.dumps(answer).encode('utf-8') + b'\n')
    await writer.drain()


def _stamp() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


Handler = Callable[[Served, dict[str, Any]], Awaitable[dict[str, Any] | None]]
HANDLERS: dict[str, Handler] = {
    'initialize': Served.initialize,
    **{method: Served.initialize for method in layers.INITIALIZE},  # a conductor's, Proxy Chains
    'session/new': Served.new_session,
    'session/load': Served.reopen,
    'session/resume': Served.reopen,
    'session/list': Served.list_sessions,
    'session/prompt': Served.prompt_turn,
    'session/close': Served.close_session,
    'session/delete': Served.delete_session,
    'session/fork': Served.new_session,
}
