"""An ACP seat, `acp:<agent>/<model>`: Claude Code, Codex or Antigravity in its own session, started by this server's own
ACP client (the `agent-client-protocol` SDK), on the person's own login to the agent and never an API key.

Each ACP seat is one agent process and one session for the life of its table, so it keeps its own conversation and
its provider's prompt cache stays warm between its turns; each runs on its own model. A seat only reads:

- the session is made with no MCP servers, and for Claude Code with its built-in tools cut to Read, Grep and Glob,
  the writing ones refused by name and a strict MCP config, so the folder's own allow rules cannot let it write;
- unless the table named MCP servers for its seats at open (`seat_mcp`, section 2.6 of the specification): those
  servers alone, the ones for every seat and the ones for this seat, are given in `session/new` (never a config
  file), with Claude Code's `allowedTools` set to them alone under its strict MCP config, and a permission request
  for one of their tools allowed (Codex asks by the call's id alone, so each call's server is remembered as the
  agent reports it), never one that writes a file or opens a URL; an agent that takes no MCP server over http makes
  no session at such a table, and the report's session is given none; with the playground's per-agent endpoints,
  the seat stands there as a body;
- it is put in the first mode its agent offers of `read-only` (Codex's sandbox) and `default`, so a person's own
  default of a mode that writes never reaches a seat;
- the client offers no file writes and no terminals, every permission request is answered at once, reads allowed and
  the rest refused, and any question the agent puts is declined;
- the agent's environment has no ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, OPENAI_API_KEY or CODEX_API_KEY, so it runs
  on the person's subscription;
- its process runs in an empty folder of its own under the home, `seats/<table>-<position>`, and Claude Code with
  `settingSources: []`, so no project's CLAUDE.md, AGENTS.md, skills or commands enter its base prefix; the table's
  folder is given to Claude Code as a directory it may also read. Antigravity's session cwd is the table's folder:
  its native file tools restrict reads to that workspace and ignore additional directories.

On its turn a seat is sent the seat view as one prompt; its reply is the last text the agent wrote in that turn. A
turn that runs past `agent_wait` is cancelled and passes with no submission; the session stays. When a topic opens the
seat's session is closed and a fresh one started, seeded by its next prompt. A session that ends takes the seat away
from the table. When the runner stops and starts again, a seat's session is resumed, or loaded,
where its agent offers either; otherwise the seat has left the table.
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
from pathlib import Path
from typing import Any, cast

import acp
from acp.schema import (
    AllowedOutcome,
    ClientCapabilities,
    DeclineElicitationResponse,
    DeniedOutcome,
    FileSystemCapabilities,
    HttpHeader,
    HttpMcpServer,
    Implementation,
    PermissionOption,
    RequestPermissionResponse,
    ToolCallUpdate,
)

from . import __version__, config, seats, store
from .seat import Gone, Late, NoReply, Reply, Seat

log = logging.getLogger(__name__)

START = 120.0  # seconds an agent has to start and make its session
SETTING = 30.0  # seconds an agent has to take a setting
CANCEL = 15.0  # seconds a cancelled turn has to end before the seat's process is stopped
LINE_LIMIT = 64 * 1024 * 1024  # the longest line an agent may write
SUBSCRIPTION_ONLY = ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'OPENAI_API_KEY', 'CODEX_API_KEY')
SEAT_MODES = ('read-only', 'default')
READS = ('read', 'search')  # the ACP tool kinds that only read
NEVER = ('edit', 'delete', 'move', 'fetch')  # the kinds refused even to a named MCP server: writes, URLs opened
SEAT_META: dict[str, Any] = {'claudeCode': {'options': {
    'tools': ['Read', 'Grep', 'Glob'],
    'disallowedTools': ['Bash', 'Edit', 'Write', 'MultiEdit', 'NotebookEdit', 'Task', 'Agent', 'WebFetch',
                        'WebSearch'],
    'settingSources': [],  # no user, project or local settings, CLAUDE.md, skills or commands
    'strictMcpConfig': True}}}
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
        inner = cast(list[dict[str, Any]], given['options']) if 'group' in given else [given]
        found += [{'value': str(one.get('value')), 'name': str(one.get('name') or one.get('value'))} for one in inner]
    return found


class Session:
    """One seat's agent process and its session; the SDK calls `session_update` and `request_permission` on it."""

    def __init__(self, number: int, seat: dict[str, Any], folder: str, servers: list[dict[str, Any]] | None = None,
                 *, reads: str | None = None) -> None:
        self.number = number
        self.position = int(seat['position'])
        self.agent = str(seat['agent'])
        self.model = str(seat['model'])
        self.folder = folder
        self.reads = reads  # a folder besides its own that the seat may read: the table's
        self.workspace = reads if self.agent == 'antigravity' and reads else folder
        self.process: asyncio.subprocess.Process | None = None
        self.conn: Any = None
        self.session_id: str | None = None
        self.config: list[dict[str, Any]] = []
        self.modes: dict[str, Any] = {}
        self.said: list[str] = []  # the agent's messages in the turn in flight, a tool call starting a new one
        self.breaking = True
        self.replaying = False
        self.cost = 0.0  # the agent's own running cost for the session, when it reports one
        self.reported: str | None = None
        self.servers = servers or []  # the MCP servers the table named for this seat, the only ones it is given
        self.calls: dict[str, str] = {}  # a tool call's id and the MCP server it calls, as the agent reported it

    # ------------------------------------------------------------------------------------------- the SDK calls these

    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
        kind = getattr(update, 'session_update', None)
        if kind == 'config_option_update':
            self.config = [one.model_dump(mode='json', by_alias=True)
                           for one in cast(list[Any], update.config_options or [])]
        elif kind == 'current_mode_update':
            self.modes['currentModeId'] = update.current_mode_id
        elif kind == 'usage_update' and getattr(update, 'cost', None) is not None:
            self.cost = float(update.cost.amount)
        if kind in ('tool_call', 'tool_call_update') and (server := self.server_of(update)) is not None:
            self.calls[str(update.tool_call_id)] = server
        if self.replaying:
            return
        if kind == 'agent_message_chunk':
            text = getattr(update.content, 'text', None)
            if text:
                if self.breaking or not self.said:
                    self.said.append('')
                    self.breaking = False
                self.said[-1] += text
        elif kind in ('tool_call', 'tool_call_update'):
            self.breaking = True

    async def request_permission(self, session_id: str, tool_call: ToolCallUpdate, options: list[PermissionOption],
                                 **kwargs: Any) -> RequestPermissionResponse:
        """A seat reads and never writes, and calls the tools of the MCP servers named for it: answered at once,
        never put to anyone."""
        named = str(tool_call.kind) not in NEVER and \
            (self.server_of(tool_call) or self.calls.get(str(tool_call.tool_call_id))) is not None
        reads = str(tool_call.kind) in READS or named
        wanted = ('allow_once',) if reads else ('reject_once', 'reject_always')
        chosen = next((one for one in options if str(one.kind) in wanted), None)
        log.info('Seat %s:%s %s %s.', self.number, self.position, 'allowed' if reads and chosen else 'refused',
                 tool_call.title or tool_call.kind)
        if chosen is None:
            return RequestPermissionResponse(outcome=DeniedOutcome(outcome='cancelled'))
        return RequestPermissionResponse(outcome=AllowedOutcome(option_id=chosen.option_id, outcome='selected'))

    def server_of(self, call: Any) -> str | None:
        """The MCP server named for this seat that a tool call calls, by its title (Claude Code's
        `mcp__<server>__<tool>`, Codex's `mcp.<server>.<tool>`) or its input's server; None for any other call."""
        title = str(getattr(call, 'title', None) or '')
        given = getattr(call, 'raw_input', None)
        said = cast(dict[str, Any], given) if isinstance(given, dict) else {}
        return next((one['name'] for one in self.servers
                     if title.startswith((f'mcp__{one["name"]}__', f'mcp.{one["name"]}.'))
                     or one['name'] in (said.get('server'), said.get('serverName'))), None)

    def mcp_servers(self) -> list[HttpMcpServer]:
        return [HttpMcpServer(type='http', name=one['name'], url=one['url'],
                              headers=[HttpHeader(**header) for header in one['headers']]) for one in self.servers]

    async def create_elicitation(self, message: str, mode: Any, **kwargs: Any) -> DeclineElicitationResponse:
        return DeclineElicitationResponse(action='decline')

    async def complete_elicitation(self, elicitation_id: str, **kwargs: Any) -> None:
        return None

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        return {}

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        return None

    def on_connect(self, conn: Any) -> None:
        return None

    # ------------------------------------------------------------------------------------------- starting

    def environment(self) -> dict[str, str]:
        env = {key: value for key, value in os.environ.items()
               if key not in SUBSCRIPTION_ONLY and not key.startswith('ROUNDTABLE_')}
        env['DISABLE_MCP_CONFIG_FILTERING'] = 'true'  # codex-acp starts no server of the person's config in its place
        return env

    async def start(self, resume: str | None = None) -> None:
        """The agent started and its session made, or resumed when `resume` names one, on the seat's model in a mode
        that only reads; Gone when it cannot be."""
        await self.begin(resume, f'table-{self.number}-seat-{self.position}.log')
        await self.settle()

    async def begin(self, resume: str | None, log_name: str) -> None:
        """The agent started and its session made or taken up again, as the agent offers it; Gone when it cannot be."""
        command = shlex.split(config.agents()[self.agent])
        logs = config.home() / 'logs'
        logs.mkdir(parents=True, exist_ok=True)
        with (logs / log_name).open('ab') as written:
            try:
                self.process = await asyncio.create_subprocess_exec(
                    *command, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=written,
                    cwd=self.folder, env=self.environment(), limit=LINE_LIMIT, start_new_session=os.name != 'nt')
            except OSError as error:
                raise Gone(f'{self.agent} did not start: {error}') from None
        self.conn = acp.connect_to_agent(cast(Any, self), self.process.stdin, self.process.stdout)
        try:
            init = await asyncio.wait_for(self.conn.initialize(
                protocol_version=acp.PROTOCOL_VERSION,
                client_capabilities=ClientCapabilities(
                    fs=FileSystemCapabilities(read_text_file=False, write_text_file=False), terminal=False),
                client_info=Implementation(name='roundtable', title='Roundtable', version=__version__)), START)
            made = await asyncio.wait_for(self.made(init, resume), START)
        except (TimeoutError, acp.RequestError, OSError, ConnectionError) as error:
            await self.close()
            raise Gone(f'{self.agent} did not make its session: {error or type(error).__name__}') from None
        self.replaying = False
        if resume is None:
            self.session_id = str(made.session_id)
        self.take(made)

    def meta(self) -> dict[str, Any]:
        """The session's `_meta`, Claude Code's options: what a seat may do, the table's folder as one it may also
        read, and the tools of its named MCP servers allowed."""
        if not self.reads and not self.servers:
            return SEAT_META
        options = {**SEAT_META['claudeCode']['options'],
                   **({'additionalDirectories': [self.reads]} if self.reads else {}),
                   **({'allowedTools': [f'mcp__{one["name"]}' for one in self.servers]} if self.servers else {})}
        return {'claudeCode': {'options': options}}

    async def made(self, init: Any, resume: str | None) -> Any:
        caps = init.agent_capabilities
        mcp = getattr(caps, 'mcp_capabilities', None)
        if self.servers and not (mcp is not None and mcp.http):
            raise acp.RequestError(-32602, f'{self.agent} takes no MCP server over http, and the table named '
                                           f'{", ".join(one["name"] for one in self.servers)} for its seats')
        servers, meta = self.mcp_servers(), self.meta()
        if resume is None:
            return await self.conn.new_session(cwd=self.workspace, mcp_servers=servers, **meta)
        self.session_id = resume
        sessions = getattr(caps, 'session_capabilities', None)
        if sessions is not None and sessions.resume is not None:
            return await self.conn.resume_session(session_id=resume, cwd=self.workspace, mcp_servers=servers, **meta)
        if caps is not None and caps.load_session:
            self.replaying = True  # the history it replays is already this seat's conversation
            return await self.conn.load_session(cwd=self.workspace, session_id=resume, mcp_servers=servers, **meta)
        raise acp.RequestError(-32601, f'{self.agent} offers neither session/resume nor session/load')

    def take(self, made: Any) -> None:
        options = getattr(made, 'config_options', None)
        if options is not None:
            self.config = [one.model_dump(mode='json', by_alias=True) for one in options]
        modes = getattr(made, 'modes', None)
        if modes is not None:
            self.modes = modes.model_dump(mode='json', by_alias=True)

    def option(self, category: str) -> dict[str, Any] | None:
        return next((one for one in self.config if one.get('category') == category or one.get('id') == category),
                    None)

    async def settle(self) -> None:
        """The seat's mode, one that only reads, and its model; Gone when the agent offers neither."""
        mode_option = self.option('mode')
        offered = [one['value'] for one in choices(mode_option)] if mode_option else \
            [str(one.get('id')) for one in cast(list[dict[str, Any]], self.modes.get('availableModes') or [])]
        mode = next((one for one in SEAT_MODES if one in offered), None)
        if offered and mode is None:
            raise await self.gone(f'{self.agent} offers no mode that only reads: {", ".join(offered)}')
        if mode is not None:
            try:
                if mode_option is not None:
                    if mode_option.get('currentValue') != mode:
                        await self.configure(mode_option, mode)
                elif self.modes.get('currentModeId') != mode:
                    await asyncio.wait_for(self.conn.set_session_mode(session_id=self.session_id, mode_id=mode),
                                           SETTING)
                    self.modes['currentModeId'] = mode
            except (TimeoutError, acp.RequestError) as error:
                raise await self.gone(f'{self.agent} did not take the mode {mode}: {error}') from None
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
        """One config option set; the agent's answer is the options from then on, or, when it answers with none, the
        value as given."""
        answer = await asyncio.wait_for(self.conn.set_config_option(
            config_id=option['id'], session_id=self.session_id, value=value), SETTING)
        if getattr(answer, 'config_options', None):
            self.take(answer)
        else:
            self.config = [{**one, 'currentValue': value} if one.get('id') == option['id'] else one
                           for one in self.config]

    async def gone(self, how: str) -> Gone:
        await self.close()
        return Gone(how)

    # ------------------------------------------------------------------------------------------- a turn

    def alive(self) -> bool:
        return self.process is not None and self.process.returncode is None

    async def prompt(self, text: str, seconds: float) -> tuple[str, dict[str, Any]]:
        """One prompt of the session and the last text the agent wrote in that turn, with what the turn used as the
        agent reports it. Late when it runs past `seconds` (the turn is cancelled, the session stays), Gone when the
        session ends, NoReply when the agent failed the turn or wrote no text."""
        if not self.alive() or self.session_id is None:
            raise Gone(f'{self.agent} is no longer running')
        self.said, self.breaking = [], True
        before = self.cost
        asked = asyncio.ensure_future(self.conn.prompt(session_id=self.session_id, prompt=[acp.text_block(text)]))
        assert self.process is not None
        ended = asyncio.ensure_future(self.process.wait())
        done, _ = await asyncio.wait({asked, ended}, timeout=seconds, return_when=asyncio.FIRST_COMPLETED)
        if asked not in done:
            if ended in done:
                asked.cancel()
                raise Gone(f'{self.agent} exited with {self.process.returncode}')
            ended.cancel()
            with contextlib.suppress(Exception):
                await self.conn.cancel(session_id=self.session_id)
            try:
                await asyncio.wait_for(asked, CANCEL)
            except Exception as error:  # noqa: BLE001  the turn is over either way
                log.info('Seat %s:%s: the cancelled turn ended with %r.', self.number, self.position, error)
            raise Late(seconds)
        ended.cancel()
        try:
            answer = asked.result()
        except acp.RequestError as error:
            raise NoReply(f'{self.agent} failed the turn: {error}', delivered=True) from None
        except (ConnectionError, OSError) as error:
            raise Gone(f'{self.agent} closed its connection: {error}') from None
        usage = getattr(answer, 'usage', None)
        used: dict[str, Any] = {'model': self.reported}
        if usage is not None:
            used.update(prompt_tokens=usage.input_tokens, cached_tokens=usage.cached_read_tokens,
                        cache_write_tokens=usage.cached_write_tokens)
        if self.cost > before:
            used['cost'] = round(self.cost - before, 6)
        reply = next((one.strip() for one in reversed(self.said) if one.strip()), '')
        if not reply:
            raise NoReply(f'{self.agent} wrote no text (it stopped: {answer.stop_reason})', delivered=True,
                          kind='empty')
        return reply, used

    async def close(self) -> None:
        """The agent's process stopped, its whole group, so nothing it started outlives the table."""
        process, self.process = self.process, None
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
                       reads=str(self.table['folder']))
        await made.start(resume=self.session or None)
        self.session_made, self.session, self.reported = made, made.session_id, made.reported

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
