"""Negotiated ACP sessions for roundtable seats.

Every agent uses the same protocol for session configuration, tool progress, permission
requests and completion. Permission requests reach the person through the table's relay.
Agents execute their own file and terminal tools in the project's workspace. The table's
prompts describe its writing rules. There are no agent-specific tool lists or path gates.

Connections offer v2 and select the matching SDK implementation. An agent selecting v1
gets a fresh v1 handshake, including that version's capabilities. V1 completes a prompt
through its response. V2 acknowledges insertion, then reports foreground completion as
idle. Each seat keeps its work alive while the scheduler lets other seats work.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import shlex
import shutil
import signal
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import acp
from acp import schema as legacy
from acp.connection import StreamDirection, StreamEvent
from acp.experimental import v2
from acp.experimental.v2 import schema

from . import __version__, config, seats, store
from .seat import Gone, Late, NoReply, Reply, Seat

log = logging.getLogger(__name__)

START = 120.0  # seconds an agent has to start and make its session
SETTING = 30.0  # seconds an agent has to take a setting
CANCEL = 15.0  # seconds a cancelled turn has to end before the seat's process is stopped
LINE_LIMIT = 64 * 1024 * 1024  # the longest line an agent may write
SUBSCRIPTION_ONLY = ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'OPENAI_API_KEY', 'CODEX_API_KEY')
SERVER_NAME = re.compile(r'[A-Za-z0-9_-]{1,64}')  # a name Claude Code can put in a tool's name, mcp__<name>__<tool>


def seat_servers(given: Any, chosen: list[dict[str, str]]) -> list[dict[str, Any]]:
    """A table's `seat_mcp` as stored: each server's name, its http(s) URL and its headers as name-value pairs, and
    the 0-based position of the seat it is for when it names one (`seat`, its 1-based place in speaking order), else
    for every ACP seat. Refused when a server is not one of these or its seat is not an ACP seat."""
    if given in (None, ''):
        return []
    if not isinstance(given, list):
        raise seats.Refused('seat_mcp is a list of {name, url, headers}.')
    found: list[dict[str, Any]] = []
    for one in cast(list[Any], given):
        if not isinstance(one, dict):
            raise seats.Refused('seat_mcp is a list of {name, url, headers}.')
        server = cast(dict[str, Any], one)
        name, url = str(server.get('name') or ''), str(server.get('url') or '')
        if not SERVER_NAME.fullmatch(name):
            raise seats.Refused(f'seat_mcp: {name!r} is not a server name; letters, digits, _ and -, up to 64.')
        if not url.startswith(('http://', 'https://')):
            raise seats.Refused(f'seat_mcp: {name} needs an http or https url.')
        headers: Any = server.get('headers') or []
        if isinstance(headers, dict):
            headers = [{'name': key, 'value': value} for key, value in cast(dict[Any, Any], headers).items()]
        if not isinstance(headers, list) or not all(
                isinstance(header, dict) and cast(dict[str, Any], header).get('name')
                for header in cast(list[Any], headers)):
            raise seats.Refused(f'seat_mcp: {name}\'s headers are {{header: value}} or [{{name, value}}].')
        row: dict[str, Any] = {'name': name, 'url': url, 'headers': [
            {'name': str(header['name']), 'value': str(header.get('value') or '')}
            for header in cast(list[dict[str, Any]], headers)]}
        place = server.get('seat')
        if place is not None:
            if isinstance(place, bool) or not isinstance(place, int) or not 1 <= place <= len(chosen):
                raise seats.Refused(f'seat_mcp: {name}\'s seat is a place in speaking order, 1 to {len(chosen)}.')
            if chosen[place - 1]['kind'] != 'acp':
                raise seats.Refused(f'seat_mcp: seat {place}, {chosen[place - 1]["id"]}, is not an ACP seat; '
                                    'other seats stay text-only.')
            row['position'] = place - 1
        if any(other['name'] == name and (None in (other.get('position'), row.get('position'))
                                          or other.get('position') == row.get('position')) for other in found):
            raise seats.Refused(f'seat_mcp: {name} is named twice for one seat.')
        found.append(row)
    return found


def servers_of(table: dict[str, Any], position: int) -> list[dict[str, Any]]:
    """The MCP servers a seat at `position` is given: the table's for every seat and its own; none for a host,
    synthesizer or reporter in a fresh request, which is not a seat at the table."""
    return [one for one in cast(list[dict[str, Any]], table.get('seat_mcp') or [])
            if position >= 0 and one.get('position') in (None, position)]


def seat_folder(number: int, position: int) -> str:
    """The empty folder an ACP seat runs in, its own for the life of the table."""
    found = config.home() / 'seats' / f'{number}-{position}'
    found.mkdir(parents=True, exist_ok=True)
    return str(found)


def choices(option: dict[str, Any]) -> list[dict[str, str]]:
    """A select option's choices, its groups flattened."""
    found: list[dict[str, str]] = []
    for given in cast(list[dict[str, Any]], option.get('options') or []):
        inner = cast(list[dict[str, Any]], given['options']) if 'group' in given or 'groupId' in given else [given]
        found += [{'value': str(one.get('value')), 'name': str(one.get('name') or one.get('value'))} for one in inner]
    return found


class V1Client:
    """The v1 SDK handler. Permission decisions use the same relay as v2."""

    def __init__(self, session: Session) -> None:
        self.session = session

    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
        await self.session.session_update(session_id, update, **kwargs)

    async def request_permission(self, session_id: str, tool_call: legacy.ToolCallUpdate,
                                 options: list[legacy.PermissionOption], **kwargs: Any) -> legacy.RequestPermissionResponse:
        payload: dict[str, Any] = {
            'sessionId': session_id, 'title': str(tool_call.title or tool_call.kind or 'Tool permission'),
            'subject': {'type': 'tool_call', 'toolCall': tool_call.model_dump(mode='json', by_alias=True,
                                                                          exclude_none=True)},
            'options': [one.model_dump(mode='json', by_alias=True, exclude_none=True) for one in options]}
        if kwargs:
            payload['_meta'] = kwargs
        chosen = await self.session.permission(payload)
        if chosen is None:
            return legacy.RequestPermissionResponse(outcome=legacy.DeniedOutcome(outcome='cancelled'))
        return legacy.RequestPermissionResponse(outcome=legacy.AllowedOutcome(option_id=chosen, outcome='selected'))

    async def create_elicitation(self, message: str, mode: Any, **kwargs: Any) -> legacy.DeclineElicitationResponse:
        return legacy.DeclineElicitationResponse(action='decline')

    async def complete_elicitation(self, elicitation_id: str, **kwargs: Any) -> None:
        return None


class Session:
    """One agent process and its negotiated ACP session."""

    def __init__(self, number: int, seat: dict[str, Any], folder: str, servers: list[dict[str, Any]] | None = None,
                 *, reads: str | None = None, notes: str | None = None,
                 permission_event: Callable[[dict[str, Any]], None] | None = None) -> None:
        self.number = number
        self.notes = notes
        self.permission_event = permission_event
        self.position = int(seat['position'])
        self.agent = str(seat['agent'])
        self.model = str(seat['model'])
        self.folder = folder
        self.reads = reads
        self.workspace = reads or folder
        self.process: asyncio.subprocess.Process | None = None
        self.conn: Any = None
        self.protocol = v2.PROTOCOL_VERSION
        self.initialize_request: Any = None
        self.initialize_result: dict[str, Any] | None = None
        self.can_close = True
        self.session_id: str | None = None
        self.config: list[dict[str, Any]] = []
        self.said: dict[str, str] = {}
        self.order: list[str] = []
        self.replaying = False
        self.cost = 0.0
        self.reported: str | None = None
        self.servers = servers or []
        self.activity = 'idle'
        self.background: list[Any] | None = None
        self.raw_states: dict[str, deque[dict[str, Any]]] = {}
        self.completion: asyncio.Future[dict[str, Any]] | None = None
        self.foreground_started = False
        self.activity_changed = asyncio.Event()
        self.prompt_lock = asyncio.Lock()
        self.closing = False
        self.inflight: asyncio.Task[Any] | None = None
        self.permission_waits = 0
        self.legacy_message = 0
        self.legacy_breaking = True

    def stream_event(self, event: StreamEvent) -> None:
        """Keep newer state fields that a draft SDK schema does not yet describe."""
        if event.direction == StreamDirection.OUTGOING and event.message.get('method') == 'initialize':
            self.initialize_request = event.message.get('id')
            return
        if event.direction != StreamDirection.INCOMING:
            return
        if event.message.get('id') == self.initialize_request and 'result' in event.message:
            value = event.message['result']
            if isinstance(value, dict):
                self.initialize_result = cast(dict[str, Any], value)
            return
        if event.message.get('method') != 'session/update':
            return
        params = event.message.get('params')
        if not isinstance(params, dict):
            return
        given = cast(dict[str, Any], params)
        session = str(given.get('sessionId') or '')
        if self.session_id is not None and session != self.session_id:
            return
        update = given.get('update')
        if isinstance(update, dict):
            state = cast(dict[str, Any], update)
            if state.get('sessionUpdate') == 'state_update':
                self.raw_states.setdefault(session, deque()).append(state)

    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
        if self.session_id is not None and session_id != self.session_id:
            return
        kind = getattr(update, 'session_update', None)
        if kind == 'config_option_update':
            self.config = [one.model_dump(mode='json', by_alias=True)
                           for one in cast(list[Any], update.config_options or [])]
        elif kind == 'usage_update' and getattr(update, 'cost', None) is not None:
            self.cost = float(update.cost.amount)
        elif kind == 'state_update':
            queued = self.raw_states.get(session_id)
            state = queued.popleft() if queued else update.model_dump(mode='json', by_alias=True, exclude_unset=True)
            self.activity = str(update.state)
            if 'background' in state:
                value = state['background']
                self.background = list(cast(list[Any], value)) if isinstance(value, list) else None
            elif self.background is not None:
                self.background = None
            if self.activity != 'idle':
                self.foreground_started = True
            elif self.foreground_started and self.completion is not None and not self.completion.done():
                self.completion.set_result(state)
            self.activity_changed.set()
        if self.replaying:
            return
        if self.protocol == 1 and kind in ('tool_call', 'tool_call_update'):
            self.legacy_breaking = True
        if kind in ('agent_message_chunk', 'agent_message'):
            message_id = getattr(update, 'message_id', None)
            if message_id is None:
                if self.legacy_breaking:
                    self.legacy_message += 1
                    self.legacy_breaking = False
                message_id = f'legacy-{self.legacy_message}'
            message = str(message_id)
            if message not in self.said:
                self.said[message] = ''
                self.order.append(message)
            if kind == 'agent_message_chunk':
                text = getattr(update.content, 'text', None)
                if text:
                    self.said[message] += text
            elif 'content' in update.model_fields_set:
                self.said[message] = ''.join(str(one.text) for one in cast(list[Any], update.content or [])
                                            if getattr(one, 'type', None) == 'text')

    async def request_permission(self, session_id: str, title: str, options: list[schema.PermissionOption],
                                 description: str | None = None, subject: Any = None,
                                 **kwargs: Any) -> schema.RequestPermissionResponse:
        """Relay the agent's permission request and return the person's selected ACP option."""
        payload: dict[str, Any] = {'sessionId': session_id, 'title': title,
                   'options': [one.model_dump(mode='json', by_alias=True, exclude_none=True) for one in options]}
        if description is not None:
            payload['description'] = description
        if subject is not None:
            payload['subject'] = subject.model_dump(mode='json', by_alias=True, exclude_none=True)
        meta = kwargs.get('_meta') or kwargs.get('field_meta')
        if meta is not None:
            payload['_meta'] = meta
        chosen = await self.permission(payload)
        if chosen is None:
            return schema.RequestPermissionResponse(outcome=schema.CancelledPermissionOutcome())
        return schema.RequestPermissionResponse(outcome=schema.SelectedPermissionOutcomeVariant(option_id=chosen))

    async def permission(self, payload: dict[str, Any]) -> str | None:
        from . import permissions
        self.permission_waits += 1
        self.activity_changed.set()
        try:
            return await permissions.request(self.number, self.position, payload, notify=self.permission_event)
        finally:
            self.permission_waits -= 1
            self.activity_changed.set()

    def mcp_servers(self) -> list[Any]:
        model = schema.HttpMcpServer if self.protocol == 2 else legacy.HttpMcpServer
        return [model.model_validate({'type': 'http', 'name': one['name'], 'url': one['url'],
                                       'headers': one['headers']}) for one in self.servers]

    async def create_elicitation(self, message: str, mode: str, **kwargs: Any) -> schema.DeclineElicitationResponse:
        return schema.DeclineElicitationResponse()

    async def complete_elicitation(self, elicitation_id: str, **kwargs: Any) -> None:
        return None

    def on_connect(self, conn: Any) -> None:
        self.conn = conn

    def environment(self) -> dict[str, str]:
        env = {key: value for key, value in os.environ.items()
               if key not in SUBSCRIPTION_ONLY and not key.startswith('ROUNDTABLE_')}
        env['DISABLE_MCP_CONFIG_FILTERING'] = 'true'
        return env

    async def start(self, resume: str | None = None) -> None:
        await self.begin(resume, f'table-{self.number}-seat-{self.position}.log')
        await self.settle()

    async def connect(self, protocol: int, log_name: str) -> Any:
        """Offer one protocol on a fresh connection and return its typed initialization."""
        self.protocol = protocol
        self.initialize_request = None
        self.initialize_result = None
        self.session_id = None
        self.activity = 'idle'
        self.background = None
        self.raw_states.clear()
        self.config = []
        command = shlex.split(config.agents()[self.agent])
        logs = config.home() / 'logs'
        logs.mkdir(parents=True, exist_ok=True)
        with (logs / log_name).open('ab') as written:
            self.process = await asyncio.create_subprocess_exec(
                *command, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=written,
                cwd=self.folder, env=self.environment(), limit=LINE_LIMIT, start_new_session=os.name != 'nt')
        if protocol == 2:
            self.conn = v2.connect_to_agent(self, self.process.stdin, self.process.stdout,
                                            observers=[self.stream_event])
            return await asyncio.wait_for(self.conn.initialize(
                protocol_version=2, capabilities=schema.ClientCapabilities(),
                info=schema.Implementation(name='roundtable', title='Roundtable', version=__version__)), START)
        self.conn = acp.connect_to_agent(cast(Any, V1Client(self)), self.process.stdin, self.process.stdout,
                                         observers=[self.stream_event])
        initialized = await asyncio.wait_for(self.conn.initialize(
            protocol_version=1, client_capabilities=legacy.ClientCapabilities(),
            client_info=legacy.Implementation(name='roundtable', title='Roundtable', version=__version__)), START)
        if initialized.protocol_version != 1:
            raise acp.RequestError(-32602, f'{self.agent} selected unsupported ACP protocol '
                                          f'{initialized.protocol_version} after a v1 handshake.')
        return initialized

    def offers_v1(self, error: BaseException) -> bool:
        """Only initialize-level version evidence permits reconnecting with v1 capabilities."""
        given = self.initialize_result or {}
        selected = given.get('protocolVersion')
        if selected == 1:
            return True
        if selected == 2 and 'info' not in given and any(
                key in given for key in ('agentInfo', 'agentCapabilities')):
            return True
        if isinstance(error, acp.RequestError):
            if error.code == -32022:
                data = error.data
                if isinstance(data, dict):
                    versions = cast(dict[str, Any], data).get('supported')
                    if isinstance(versions, list):
                        return 1 in cast(list[Any], versions)
                return True
            return error.code in (-32600, -32602) and 'unsupported protocol version' in str(error).lower()
        return False

    async def begin(self, resume: str | None, log_name: str) -> None:
        try:
            try:
                init = await self.connect(2, log_name)
            except (TimeoutError, acp.RequestError, OSError, ConnectionError, ValueError) as first:
                retry = self.offers_v1(first)
                await self.close()
                if not retry:
                    selected = (self.initialize_result or {}).get('protocolVersion')
                    if selected is not None and selected not in (1, 2):
                        raise acp.RequestError(-32602, f'{self.agent} selected unsupported ACP protocol {selected}.') \
                            from first
                    raise
                log.info('Seat %s:%s: initialize selected the v1 path; reconnecting with v1 capabilities.',
                         self.number, self.position)
                try:
                    init = await self.connect(1, log_name)
                except (TimeoutError, acp.RequestError, OSError, ConnectionError, ValueError) as second:
                    raise acp.RequestError(-32602, f'ACP negotiation failed: v2: {first}; v1: {second}') from second
            # Runtime, authentication and session errors never select a different protocol.
            made = await asyncio.wait_for(self.made(init, resume), START)
        except (TimeoutError, acp.RequestError, OSError, ConnectionError, ValueError) as error:
            await self.close()
            raise Gone(f'{self.agent} did not make its ACP session: {error or type(error).__name__}') from None
        self.replaying = False
        if resume is None:
            self.session_id = str(made.session_id)
        self.take(made)

    async def made(self, init: Any, resume: str | None) -> Any:
        if self.protocol == 2:
            caps = getattr(init.capabilities, 'session', None)
            if caps is None:
                raise acp.RequestError(-32602, f'{self.agent} offers no ACP v2 sessions.')
            mcp = getattr(caps, 'mcp', None)
            supports_http = mcp is not None and mcp.http is not None
            supports_directories = getattr(caps, 'additional_directories', None) is not None
            self.can_close = True
        else:
            agent = init.agent_capabilities
            caps = getattr(agent, 'session_capabilities', None)
            mcp = getattr(agent, 'mcp_capabilities', None)
            supports_http = mcp is not None and bool(mcp.http)
            supports_directories = getattr(caps, 'additional_directories', None) is not None
            self.can_close = getattr(caps, 'close', None) is not None
        if self.servers and not supports_http:
            raise acp.RequestError(-32602, f'{self.agent} takes no MCP server over http, and the table named '
                                           f'{", ".join(one["name"] for one in self.servers)} for its seats')
        options: dict[str, Any] = {'cwd': self.workspace, 'mcp_servers': self.mcp_servers()}
        if self.notes and not Path(self.notes).is_relative_to(Path(self.workspace)) and supports_directories:
            options['additional_directories'] = [self.notes]
        if resume is None:
            return await self.conn.new_session(**options)
        self.session_id = resume
        if self.protocol == 2 or getattr(caps, 'resume', None) is not None:
            return await self.conn.resume_session(session_id=resume, **options)
        if getattr(init.agent_capabilities, 'load_session', False):
            self.replaying = True
            return await self.conn.load_session(session_id=resume, **options)
        raise acp.RequestError(-32601, f'{self.agent} offers neither session/resume nor session/load.')

    def take(self, made: Any) -> None:
        options = getattr(made, 'config_options', None)
        if options is not None:
            self.config = [one.model_dump(mode='json', by_alias=True) for one in options]

    def option(self, category: str) -> dict[str, Any] | None:
        return next((one for one in self.config if one.get('category') == category or
                     one.get('configId' if self.protocol == 2 else 'id') == category), None)

    async def settle(self) -> None:
        """Select the requested model through ACP. The agent keeps its advertised permission mode."""
        model = self.option('model')
        if model is None:
            raise await self.gone(f'{self.agent} offers no model to choose, so it cannot sit as {self.model}')
        listed = choices(model)
        store.offer(self.agent, listed)
        value = seats.resolve(self.model, listed)
        if value is None:
            raise await self.gone(f'{self.agent} offers no one model matching {self.model}; it offers '
                                  f'{", ".join(one["value"] for one in listed)}')
        if model.get('currentValue') != value:
            try:
                await self.configure(model, value)
            except (TimeoutError, acp.RequestError) as error:
                raise await self.gone(f'{self.agent} did not take the model {value}: {error}') from None
        self.reported = str((self.option('model') or {}).get('currentValue') or value)

    async def configure(self, option: dict[str, Any], value: str) -> None:
        key = 'configId' if self.protocol == 2 else 'id'
        answer = await asyncio.wait_for(self.conn.set_config_option(
            config_id=option[key], session_id=self.session_id, value=value,
            **({'type': 'id'} if self.protocol == 2 else {})), SETTING)
        if getattr(answer, 'config_options', None):
            self.take(answer)
        else:
            self.config = [{**one, 'currentValue': value} if one.get(key) == option[key] else one
                           for one in self.config]

    async def gone(self, how: str) -> Gone:
        await self.close()
        return Gone(how)

    def alive(self) -> bool:
        return self.process is not None and self.process.returncode is None

    async def waiting(self, tasks: set[asyncio.Future[Any]], seconds: float) -> tuple[set[asyncio.Future[Any]], float]:
        """Wait on actual events. A person's permission wait does not consume the agent's deadline."""
        remaining = seconds
        while True:
            self.activity_changed.clear()
            paused = self.activity == 'requires_action' or self.permission_waits > 0
            changed = asyncio.create_task(self.activity_changed.wait())
            began = time.monotonic()
            try:
                done, _ = await asyncio.wait(tasks | {changed}, timeout=None if paused else max(remaining, 0),
                                             return_when=asyncio.FIRST_COMPLETED)
            finally:
                changed.cancel()
                await asyncio.gather(changed, return_exceptions=True)
            if not paused:
                remaining -= time.monotonic() - began
            ready = done & tasks
            if ready:
                return ready, remaining
            if not done:
                raise TimeoutError

    async def cancel_turn(self) -> None:
        """Cancel foreground work through ACP and wait for its idle acknowledgement."""
        if self.conn is None or self.session_id is None:
            return
        try:
            if self.protocol == 2:
                await self.conn.cancel_session(session_id=self.session_id)
                waiting = self.completion
            else:
                await self.conn.cancel(session_id=self.session_id)
                waiting = self.inflight
            if waiting is not None and not waiting.done():
                await asyncio.wait_for(asyncio.shield(waiting), CANCEL)
        except (TimeoutError, acp.RequestError, ConnectionError, OSError):
            await self.close()

    async def prompt(self, text: str, seconds: float) -> tuple[str, dict[str, Any]]:
        async with self.prompt_lock:
            if not self.alive() or self.session_id is None:
                raise Gone(f'{self.agent} is no longer running')
            self.said, self.order = {}, []
            self.legacy_message, self.legacy_breaking = 0, True
            self.foreground_started = self.activity != 'idle'
            self.completion = asyncio.get_running_loop().create_future()
            before = self.cost
            models = schema if self.protocol == 2 else legacy
            if self.protocol == 1:
                self.activity = 'running'
            asked = asyncio.create_task(self.conn.prompt(
                session_id=self.session_id, prompt=[models.TextContentBlock(text=text)]))
            self.inflight = asked
            assert self.process is not None
            process = self.process
            ended = asyncio.create_task(process.wait())
            accepted = False
            try:
                ready, remaining = await self.waiting({asked, ended}, seconds)
                if asked not in ready:
                    raise Gone(f'{self.agent} exited with {process.returncode}')
                response = asked.result()
                accepted = True
                if self.protocol == 2:
                    ready, _ = await self.waiting({self.completion, ended}, remaining)
                    if self.completion not in ready:
                        raise Gone(f'{self.agent} exited with {process.returncode}')
                    answer = self.completion.result()
                else:
                    answer = response.model_dump(mode='json', by_alias=True, exclude_none=True)
            except TimeoutError:
                await self.cancel_turn()
                raise Late(seconds) from None
            except asyncio.CancelledError:
                await self.cancel_turn()
                raise
            except acp.RequestError as error:
                raise NoReply(f'{self.agent} failed the turn: {error}', delivered=accepted or self.protocol == 1) from None
            except (ConnectionError, OSError) as error:
                raise Gone(f'{self.agent} closed its connection: {error}') from None
            finally:
                asked.cancel()
                ended.cancel()
                await asyncio.gather(asked, ended, return_exceptions=True)
                self.completion = None
                self.inflight = None
                if self.protocol == 1:
                    self.activity = 'idle'
            stop = answer.get('stopReason')
            if stop == 'error':
                error = cast(dict[str, Any], answer.get('error') or {})
                raise NoReply(f'{self.agent} failed the turn: {error.get("message") or error}', delivered=True)
            if stop == 'cancelled':
                raise NoReply(f'{self.agent} cancelled the turn', delivered=True)
            usage = cast(dict[str, Any], answer.get('usage') or {})
            used: dict[str, Any] = {'model': self.reported}
            for source, target in (('inputTokens', 'prompt_tokens'), ('cachedReadTokens', 'cached_tokens'),
                                   ('cachedWriteTokens', 'cache_write_tokens'), ('outputTokens', 'completion_tokens'),
                                   ('thoughtTokens', 'reasoning_tokens')):
                if usage.get(source) is not None:
                    used[target] = usage[source]
            if self.cost > before:
                used['cost'] = round(self.cost - before, 6)
            reply = next((self.said[one].strip() for one in reversed(self.order) if self.said[one].strip()), '')
            if not reply:
                raise NoReply(f'{self.agent} wrote no text (it stopped: {stop})', delivered=True, kind='empty')
            return reply, used

    async def close(self) -> None:
        """Close the ACP session, then stop its process group, including background work."""
        if self.closing:
            return
        self.closing = True
        process, self.process = self.process, None
        try:
            if self.conn is not None:
                if self.can_close and self.session_id is not None and process is not None and process.returncode is None:
                    with contextlib.suppress(Exception):
                        await asyncio.wait_for(self.conn.close_session(session_id=self.session_id), CANCEL)
                with contextlib.suppress(Exception):
                    await self.conn.close()
            if process is None or process.returncode is not None:
                return
            with contextlib.suppress(ProcessLookupError, OSError):
                if os.name != 'nt':
                    os.killpg(process.pid, signal.SIGTERM)
                else:
                    process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 10)
            except TimeoutError:
                with contextlib.suppress(ProcessLookupError, OSError):
                    if os.name != 'nt':
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                await process.wait()
        finally:
            self.conn = None
            self.closing = False


class AcpSeat(Seat):
    """A local agent in its own ACP session for the life of the table."""
    kind = 'acp'
    REPORT_WAIT = 900.0  # seconds the reporter has for the report

    session_made: Session | None = None
    in_world = True  # the seat's session is given the MCP servers named for it; a report's is given none

    async def open(self) -> None:
        """The seat's session started, or taken up again when the seat had one; Gone when it cannot be."""
        if self.session_made is not None and self.session_made.alive():
            return
        if self.session_made is not None:
            self.session_made = None
            raise Gone(f'{self.row["agent"]} exited')
        made = Session(self.number, self.row, seat_folder(self.number, self.position),
                       servers_of(self.table, int(self.row['position'])) if self.in_world else [],
                       reads=str(self.table['folder']),
                       notes=self.notes_folder() if self.in_world else None)
        await made.start(resume=self.session or None)
        self.session_made, self.session, self.reported = made, made.session_id, made.reported

    def notes_folder(self) -> str:
        """Where the seat saves shared materials: the session's folder or the table's notes."""
        from . import render
        held = render.session(self.table)
        return str(held['folder']) if held else str(config.notes(str(self.table['folder']), self.number))

    async def exchange(self, text: str, seconds: float) -> Reply:
        await self.open()
        assert self.session_made is not None
        try:
            reply, used = await self.session_made.prompt(text, seconds)
        except Gone:
            self.session_made = None
            raise
        self.reported = self.session_made.reported
        return Reply(reply, used)

    async def report(self, record: str, seconds: float) -> str:
        """The report, written in a fresh session that holds only the record and is given no MCP server."""
        self.in_world = False
        return (await self.exchange(record, max(seconds, self.REPORT_WAIT))).text

    async def rebuild(self) -> None:
        """The seat's session closed and forgotten, so its next turn starts a fresh one."""
        await self.close()
        self.session = None
        await super().rebuild()

    async def close(self) -> None:
        if self.session_made is not None:
            await self.session_made.close()
            self.session_made = None


def found(agent: str) -> bool:
    """Whether an agent can be started here: the program its command starts is on the PATH, and for Claude Code and
    Codex the agent itself, `claude` or `codex`, whose login the seat runs on."""
    command = config.agents().get(agent)
    if not command:
        return False
    return shutil.which(shlex.split(command)[0]) is not None and \
        (agent not in ('claude', 'codex') or shutil.which(agent) is not None)


async def offers(agent: str) -> list[dict[str, str]]:
    """The models an agent offers, read from it over ACP: one session made in the home, its model choices read, and
    the agent stopped; remembered for `open` as a seat's session remembers them. Gone when it cannot be read."""
    made = Session(0, {'position': 0, 'agent': agent, 'model': ''}, str(config.home()))
    try:
        await made.begin(None, f'models-{agent}.log')
        option = made.option('model')
        if option is None:
            raise Gone(f'{agent} offers no model to choose')
        listed = choices(option)
    finally:
        await made.close()
    store.offer(agent, listed)
    return listed


def folder_of(given: str | None) -> str:
    """The folder the seats read in: the one given, else the server's own."""
    found = Path(given or os.getcwd()).expanduser().resolve()
    if not found.is_dir():
        raise seats.Refused(f'{found} is not a folder; folder= names the one the seats read in.')
    return str(found)
