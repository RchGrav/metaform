"""The model of an ACP connection, the one dispatch's work and every other module deal with.

It follows ACP v2, because v2 is where the protocol is going and it can express everything v1 can:

- a turn is `running`, `idle` with a stop reason, or `requires_action`;
- messages, tool calls, plans and display terminals are records with ids, updated in place: a field left out is
  unchanged, `null` clears it, a value replaces it, chunks append;
- a session's settings are config options by `configId`;
- the agent's requests to the client, permissions and questions, are records answered by the client;
- logins and capabilities are records read once at `initialize`;
- a resume replays the session's history or does not.

`Harness` is one started harness on one connection, speaking exactly one protocol version. Its subclasses, the
adapters in `v1` and `v2`, own their version's wire shapes, capabilities, validation and lifecycle, and nothing
outside them sees a wire shape. What the adapters share, the application logic around the wire, is here: the
prompt handle and its end, the agent's requests and their withdrawal, the order updates are delivered in, options
given at setup, and the process's end. Values the protocol may extend, enum values and update kinds, are kept as
received, never rejected; what a version cannot express is reported as `Unsupported`, never dropped.
"""
from __future__ import annotations

import asyncio
import contextlib
import contextvars
import dataclasses
import logging
from collections import deque
from collections.abc import Awaitable
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

from acp.connection import Connection, StreamDirection, StreamEvent
from acp.exceptions import RequestError

log = logging.getLogger(__name__)

RUNNING, IDLE, REQUIRES_ACTION = 'running', 'idle', 'requires_action'
ACTIVE = (RUNNING, REQUIRES_ACTION)
ROLES = ('user', 'agent', 'thought')  # a message's role; ids are unique per role, as ACP says
END_LIMIT = 10.0  # seconds a harness has to end once its input is closed, before its process group is ended
REQUEST_CANCELLED = -32800  # ACP's answer to a request its sender withdrew
METHOD_NOT_FOUND = -32601

# The kinds of `Event`, each with the record it carries.
TURN = 'turn'  # Turn
MESSAGE = 'message'  # Message, with the appended block as `delta` for a chunk
TOOL_CALL = 'tool_call'  # ToolCall, with the appended content item as `delta` for a content chunk
PLAN = 'plan'  # Plan
TERMINAL = 'terminal'  # Terminal, an agent-owned display terminal, with the appended bytes as `delta`
OPTIONS = 'options'  # list[ConfigOption], the session's whole set
COMMANDS = 'commands'  # list[Command], the session's whole set
INFO = 'info'  # dict: the session's title, updatedAt and _meta
USAGE = 'usage'  # dict: used, size, cost
NOTICE = 'notice'  # dict: the notice as the agent sent it
COMPACTION = 'compaction'  # dict: a compaction_update or compaction_summary_chunk as sent
REPLAY = 'replay'  # dict: {'complete': bool}, the end of a resume's replay
AUTH = 'auth'  # dict | None: the login the harness reports it uses, its authStatus push
EXTENSION = 'extension'  # Any: an extension notification's params; `key` is its method
OTHER = 'other'  # dict: an update kind this version's adapter does not model, kept as received; `key` is its kind
INVALID = 'invalid'  # dict: an update of a known kind that breaks its version's rules, not applied
UNSUPPORTED = 'unsupported'  # dict: a request or notification of the agent's this adapter does not take
ENDED = 'ended'  # int | None: the harness's process ended or its stream closed; the exit code when known

# The JSON-RPC id of the agent's request being handled: set by the stream observer as each message is read, in the
# receive loop, and so carried into the task the connection starts for the request, which copies the context it is
# started in.
INCOMING: contextvars.ContextVar[Any] = contextvars.ContextVar('acp_incoming', default=None)


class Unsupported(Exception):
    """Something asked of a connection that its protocol version, or the harness on it, does not offer."""

    def __init__(self, feature: str, protocol: int, detail: str = '') -> None:
        self.feature = feature
        self.protocol = protocol
        super().__init__(f'{feature} is not available on this ACP v{protocol} connection'
                         + (f': {detail}' if detail else ''))


class SelectedVersion(Exception):
    """`initialize` selected a protocol version other than the one the adapter speaks, or refused the one asked."""

    def __init__(self, version: int | None, detail: str) -> None:
        self.version = version
        super().__init__(detail)


# ------------------------------------------------------------------ what initialize tells

@dataclass(slots=True)
class Offer:
    """What the client offers the harness at `initialize`. A terminal login is offered in both versions."""
    terminal_login: bool = False  # login methods of type terminal, which the client runs itself
    elicitation: bool = True  # questions to the person, forms and URLs, answered by `Client.elicitation`
    subagents: bool = False  # v1: a subagent's work as a child session of its own (claude-agent-acp, codex-acp)
    notices: bool = True  # v1: session notices, passed on as NOTICE events
    compaction: bool = True  # v1: compaction updates, passed on as COMPACTION events


@dataclass(slots=True)
class Login:
    """One login method the harness offers. `type` is `agent` (the harness logs in itself, `Harness.login`),
    `terminal` (the client runs the harness's own command with `args` and `env`), `env_var` (v1: variables to set),
    or a value a later version adds, kept as given."""
    method_id: str
    name: str
    type: str
    description: str | None
    args: list[str]
    env: dict[str, str]
    vars: list[dict[str, Any]]
    link: str | None
    raw: dict[str, Any]


@dataclass(slots=True)
class Capabilities:
    """What the harness said it can do, read at `initialize`, in one shape for both versions. In v2 list, resume
    (with and without replay) and close are always there once the harness offers sessions."""
    protocol: int
    info: dict[str, Any]  # the harness's name, title and version
    sessions: bool  # it offers sessions at all (v2's `capabilities.session`; always in v1)
    list: bool
    resume: bool  # resume without replay
    replay: bool  # resume with the history replayed (v1 session/load)
    close: bool
    delete: bool
    fork: bool
    options: bool  # the session/options proposal: options without a session, and values given at setup
    system_prompt: bool  # a system prompt given at setup, appended to the harness's own
    system_prompt_override: bool  # ... or replacing it
    image: bool
    audio: bool
    embedded_context: bool
    mcp_stdio: bool
    mcp_http: bool
    additional_directories: bool
    providers: bool  # Configurable LLM Providers, a draft
    steering: bool  # the `_session/steering` extension (claude-agent-acp, codex-acp)
    auth_status: bool  # the `_auth/status_update` extension
    logout: bool
    terminal_login: bool  # this connection offered terminal logins
    logins: list[Login]
    raw: dict[str, Any]  # the initialize answer as received


# ------------------------------------------------------------------ a session's records

@dataclass(slots=True)
class Choice:
    value: str
    name: str
    description: str | None
    group: str | None


@dataclass(slots=True)
class ConfigOption:
    """One of a session's settings. `type` is `select` or `boolean`, or a value a later version adds; `category` is
    ACP's (`mode`, `model`, `model_config`, `thought_level`, ...) or None. `source` is `option`, or `mode` for v1's
    session modes, which the v1 adapter presents as one option of category mode."""
    config_id: str
    name: str
    description: str | None
    category: str | None
    type: str
    current: str | bool | None
    choices: list[Choice]
    source: str
    raw: dict[str, Any]


@dataclass(slots=True)
class OptionValue:
    """A value for a session's option, given at setup or set later."""
    config_id: str
    value: str | bool


@dataclass(slots=True)
class Command:
    name: str
    description: str | None
    hint: str | None
    raw: dict[str, Any]


@dataclass(slots=True)
class Turn:
    """The session's foreground work: `running`, `requires_action` (waiting on the person) or `idle`, with the stop
    reason that ended it (`end_turn`, `max_tokens`, `max_turn_requests`, `refusal`, `cancelled`, `error`, or a value a
    later version adds) and, for `error`, the error. `background` is the work the agent says still runs while idle."""
    state: str = IDLE
    stop_reason: str | None = None
    error: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None
    background: list[Any] | None = None


@dataclass(slots=True)
class Message:
    role: str  # user, agent or thought
    message_id: str
    content: list[dict[str, Any]]
    meta: dict[str, Any] | None

    @property
    def text(self) -> str:
        return ''.join(str(block.get('text') or '') for block in self.content if block.get('type') == 'text')


@dataclass(slots=True)
class ToolCall:
    """A tool call's fields as ACP names them (`title`, `name`, `kind`, `status`, `content`, `locations`, `rawInput`,
    `rawOutput`, `_meta`), patched in place. Content items are kept as sent: a v1 diff is `path`, `oldText` and
    `newText`, a v2 diff is `changes` and `patch`."""
    tool_call_id: str
    fields: dict[str, Any]

    @property
    def status(self) -> str | None:
        value = self.fields.get('status')
        return str(value) if value is not None else None

    @property
    def title(self) -> str | None:
        value = self.fields.get('title')
        return str(value) if value is not None else None


@dataclass(slots=True)
class Plan:
    plan_id: str
    type: str  # `items`, or a plan type a later version adds, its fields in `raw`
    entries: list[dict[str, Any]]
    raw: dict[str, Any]


@dataclass(slots=True)
class Terminal:
    """An agent-owned display terminal (v2): its command, cwd, size and exit status as patch fields, and its bytes."""
    terminal_id: str
    fields: dict[str, Any]
    output: bytearray


@dataclass(slots=True)
class SessionState:
    """What is known of one session, kept by its harness and changed only by the agent's updates and answers."""
    session_id: str
    turn: Turn = field(default_factory=Turn)
    # its messages by role and id, in the order each was first seen, which is their place in the conversation
    messages: dict[tuple[str, str], Message] = field(default_factory=dict[tuple[str, str], Message])
    tool_calls: dict[str, ToolCall] = field(default_factory=dict[str, ToolCall])
    plans: dict[str, Plan] = field(default_factory=dict[str, Plan])
    terminals: dict[str, Terminal] = field(default_factory=dict[str, Terminal])
    options: list[ConfigOption] = field(default_factory=list[ConfigOption])
    commands: list[Command] = field(default_factory=list[Command])
    info: dict[str, Any] = field(default_factory=dict[str, Any])
    usage: dict[str, Any] = field(default_factory=dict[str, Any])
    replaying: bool = False  # the updates now arriving are its history, replayed by a resume
    replay_done: bool = False  # v2: replay_complete was heard
    v1_count: int = 0  # v1: the ids the adapter gave messages without one
    v1_open: tuple[str, str] | None = None  # v1: the message the next chunk of its role goes on
    v1_echo: tuple[str, str, str] | None = None  # v1: the prompt in flight, its message id, its text, heard so far
    v1_modes: dict[str, Any] | None = None  # v1: session modes as the agent sent them
    user_waits: int = 0  # v1: the agent's requests of this session waiting on the person

    def reset_history(self) -> None:
        """Forget the records a full replay rebuilds, as ACP says to rebuild rather than merge by id."""
        self.messages.clear()
        self.tool_calls.clear()
        self.plans.clear()
        self.terminals.clear()

    def option(self, config_id: str) -> ConfigOption | None:
        return next((one for one in self.options if one.config_id == config_id), None)


@dataclass(slots=True)
class Event:
    """One change to what is known of a session, delivered to the client in the order the agent sent it. `key` names
    the record (`<role>:<id>` for a message, the tool call's, plan's or terminal's id, the method of an extension,
    the update kind of an `other`); `raw` is the update as received, for a reader that needs what the model leaves
    out. Records are the harness's own and change in place: copy what must outlive the event."""
    session_id: str
    kind: str
    key: str
    record: Any
    delta: Any
    replay: bool
    raw: dict[str, Any] | None


@dataclass(slots=True)
class SessionSetup:
    """A session/new, resume, fork or options answer: the session, its settings and commands as the agent gave them,
    whether the answer named settings at all (a resume may leave them out), and the values given at setup the session
    did not take, each with why."""
    session_id: str
    options: list[ConfigOption]
    commands: list[Command]
    named: bool
    ignored: list[tuple[OptionValue, str]]


@dataclass(slots=True)
class SystemPrompt:
    """Instructions given at session setup: `append`ed to the harness's own, or `override` them."""
    text: str
    mode: str = 'append'


@dataclass(slots=True)
class McpServer:
    """An MCP server the session is given: a local command (stdio) or an address (http)."""
    name: str
    command: str | None = None
    args: list[str] = field(default_factory=list[str])
    env: dict[str, str] = field(default_factory=dict[str, str])
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict[str, str])


@dataclass(slots=True)
class PermissionOption:
    option_id: str
    name: str
    kind: str  # allow_once, allow_always, reject_once, reject_always, or a value a later version adds


@dataclass(slots=True)
class PermissionRequest:
    """The agent asks leave for something. `subject` is `tool_call` (its call in `tool_call`, as the session's record
    has it after this request's patch), `command` (in `command`: command, cwd, toolCallId, terminalId), None for none,
    or a type a later version adds, kept in `raw`. `key` is the request's JSON-RPC id, the one `withdrawn` names."""
    session_id: str
    title: str
    description: str | None
    subject: str | None
    tool_call: ToolCall | None
    command: dict[str, Any] | None
    options: list[PermissionOption]
    key: Any
    raw: dict[str, Any]


@dataclass(slots=True)
class Elicitation:
    """A question the agent or one of its MCP servers puts to the person: a `form` with `schema`, or a `url` to open
    (or a mode a later version adds). Scoped to a session (and perhaps its tool call), or to a request of the client's
    still pending, such as a session/new, by `request_id`."""
    session_id: str | None
    request_id: Any
    tool_call_id: str | None
    mode: str
    message: str
    schema: dict[str, Any] | None
    url: str | None
    elicitation_id: str | None
    key: Any
    raw: dict[str, Any]


@dataclass(slots=True)
class ElicitationAnswer:
    action: str  # accept, decline or cancel
    content: dict[str, Any] | None = None


@dataclass(slots=True)
class Prompt:
    """One prompt sent: `accepted` gives the id of the user message it was inserted as (v1: an id the adapter gives
    it, on sending), or the error that refused it; `ended` gives the Turn that ended the work it started."""
    session_id: str
    accepted: asyncio.Future[str]
    ended: asyncio.Future[Turn]
    active_at_send: bool = False
    active_seen: bool = False


class Client(Protocol):
    """The application side of a connection: what the harness tells and asks it."""

    def changed(self, event: Event) -> None:
        """One change, in the order the agent sent it; called in the connection's receive order, never awaited."""
        ...

    async def permission(self, request: PermissionRequest) -> str | None:
        """The chosen option's id, or None to answer cancelled."""
        ...

    async def elicitation(self, request: Elicitation) -> ElicitationAnswer:
        ...

    def elicitation_complete(self, elicitation_id: str) -> None:
        """The page an url elicitation asked the person to open is done with."""
        ...

    def withdrawn(self, key: Any) -> None:
        """A permission or elicitation request, by its key, is no longer wanted: the agent withdrew it, or a cancel of
        its turn answered it. The client ends its wait on the person; the adapter answers the agent."""
        ...

    async def extension(self, method: str, params: Any) -> Any:
        """An extension request of the agent's (`_`-prefixed method); raise RequestError to refuse it."""
        ...


class BaseClient:
    """A client that takes no part: it keeps nothing, cancels permission requests and declines questions."""

    def changed(self, event: Event) -> None:
        return None

    async def permission(self, request: PermissionRequest) -> str | None:
        return None

    async def elicitation(self, request: Elicitation) -> ElicitationAnswer:
        return ElicitationAnswer('decline')

    def elicitation_complete(self, elicitation_id: str) -> None:
        return None

    def withdrawn(self, key: Any) -> None:
        return None

    async def extension(self, method: str, params: Any) -> Any:
        raise RequestError(METHOD_NOT_FOUND, f'Method not found: {method}')


# ------------------------------------------------------------------ patch rules shared by both adapters

def dicts(value: Any) -> list[dict[str, Any]]:
    """The objects of a list as sent; anything else is no list of objects."""
    return [cast(dict[str, Any], one) for one in cast(list[Any], value) if isinstance(one, dict)] \
        if isinstance(value, list) else []


def obj(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def text_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def meta_patched(held: dict[str, Any] | None, given: Any) -> dict[str, Any] | None:
    """ACP v2's metadata patch: null clears it; an object patches it by top-level key, a key set to null removed."""
    if not isinstance(given, dict):
        return None
    kept = dict(held or {})
    for key, value in cast(dict[str, Any], given).items():
        if value is None:
            kept.pop(key, None)
        else:
            kept[key] = value
    return kept


def patched(fields: dict[str, Any], given: dict[str, Any], skip: tuple[str, ...]) -> None:
    """Apply an upsert's fields: one left out is unchanged, null clears it, a value replaces it; `_meta` by key."""
    for key, value in given.items():
        if key in skip:
            continue
        if key == '_meta':
            meta = meta_patched(cast(dict[str, Any] | None, fields.get('_meta')), value)
            if meta is None:
                fields.pop('_meta', None)
            else:
                fields['_meta'] = meta
        elif value is None:
            fields.pop(key, None)
        else:
            fields[key] = value


def appended(content: list[dict[str, Any]], block: dict[str, Any]) -> None:
    """A chunk appended to a message's content: a plain text block joins the plain text block before it, which reads
    the same and keeps a long message from holding one block per chunk."""
    plain = block.get('type') == 'text' and set(block) <= {'type', 'text'}
    if plain and content and content[-1].get('type') == 'text' and set(content[-1]) <= {'type', 'text'}:
        content[-1] = {'type': 'text', 'text': str(content[-1].get('text') or '') + str(block.get('text') or '')}
    else:
        content.append(dict(block))


def option_of(raw: dict[str, Any], id_key: str, group_key: str, source: str = 'option') -> ConfigOption:
    """A config option as either version sends it; its choices' groups flattened, each choice naming its group."""
    choices: list[Choice] = []
    for given in dicts(raw.get('options')):
        if isinstance(given.get('options'), list):  # a group of choices
            group = text_or_none(given.get('name')) or text_or_none(given.get(group_key))
            inner = dicts(given['options'])
        else:
            group, inner = None, [given]
        choices += [Choice(str(one.get('value')), str(one.get('name') or one.get('value')),
                           text_or_none(one.get('description')), group) for one in inner]
    current = raw.get('currentValue')
    return ConfigOption(config_id=str(raw.get(id_key) or ''), name=str(raw.get('name') or raw.get(id_key) or ''),
                        description=text_or_none(raw.get('description')),
                        category=text_or_none(raw.get('category')), type=str(raw.get('type') or 'select'),
                        current=current if isinstance(current, (str, bool)) else None, choices=choices,
                        source=source, raw=raw)


def command_of(raw: dict[str, Any]) -> Command:
    return Command(name=str(raw.get('name') or ''), description=text_or_none(raw.get('description')),
                   hint=text_or_none(obj(raw.get('input')).get('hint')), raw=raw)


def error_of(error: BaseException) -> dict[str, Any]:
    if isinstance(error, RequestError):
        return {'code': error.code, 'message': str(error), **({'data': error.data} if error.data is not None else {})}
    return {'code': -32603, 'message': str(error) or type(error).__name__}


def quiet(future: asyncio.Future[Any]) -> None:
    """A future nobody may await: its exception counts as read, so asyncio does not log it as lost."""
    future.add_done_callback(lambda done: None if done.cancelled() else done.exception())


# ------------------------------------------------------------------ the harness

class Harness:
    """One harness process and the one connection to it, on the version its adapter speaks. Made by
    `connection.connect`; its subclasses implement the wire."""

    protocol = 0

    def __init__(self, process: asyncio.subprocess.Process, client: Client) -> None:
        if process.stdin is None or process.stdout is None:
            raise ValueError('The harness must be started with its standard input and output piped.')
        self.process = process
        self.client = client
        self.capabilities: Capabilities | None = None
        self.sessions: dict[str, SessionState] = {}
        self.ended = asyncio.Event()
        self.tasks: set[asyncio.Task[Any]] = set()
        self.waiting: dict[str, list[Prompt]] = {}  # the prompts of each session whose work has not ended
        self.asked: dict[Any, tuple[str | None, asyncio.Future[bool]]] = {}  # the agent's requests waiting on the client
        self.sent: dict[str, deque[Any]] = {}  # the ids of extension requests sent, by method, for $/cancel_request
        self.conn = Connection(self.handle, process.stdin, process.stdout, observers=[self.observe])
        receiving = getattr(self.conn, '_recv_task', None)  # the SDK gives no public end-of-stream callback
        if isinstance(receiving, asyncio.Task):
            cast(asyncio.Task[Any], receiving).add_done_callback(lambda _: self.gone(None))
        self.spawn(self.watch())

    # -- what a subclass implements: the wire

    async def initialize(self, info: dict[str, str], offer: Offer, timeout: float) -> Capabilities:
        raise NotImplementedError

    async def new_session(self, cwd: str, servers: list[McpServer], *, directories: list[str] | None = None,
                          options: list[OptionValue] | None = None,
                          system_prompt: SystemPrompt | None = None) -> SessionSetup:
        raise NotImplementedError

    async def resume_session(self, session_id: str, cwd: str, servers: list[McpServer], *, replay: bool = False,
                             directories: list[str] | None = None, options: list[OptionValue] | None = None,
                             system_prompt: SystemPrompt | None = None) -> SessionSetup:
        raise NotImplementedError

    async def fork_session(self, session_id: str, cwd: str, servers: list[McpServer]) -> SessionSetup:
        raise NotImplementedError

    async def session_options(self, cwd: str, session_id: str | None = None) -> SessionSetup:
        """What a session would start with, asked without making one (the session/options proposal)."""
        raise NotImplementedError

    async def list_sessions(self, cwd: str | None = None, cursor: str | None = None
                            ) -> tuple[list[dict[str, Any]], str | None]:
        raise NotImplementedError

    async def close_session(self, session_id: str) -> None:
        raise NotImplementedError

    async def delete_session(self, session_id: str) -> None:
        raise NotImplementedError

    def prompt(self, session_id: str, blocks: list[dict[str, Any]]) -> Prompt:
        """Send a prompt; its handle says when it was accepted and when the work it started ended."""
        raise NotImplementedError

    async def cancel(self, session_id: str) -> None:
        """Cancel the session's foreground work; its end arrives as an idle Turn with stop reason `cancelled`."""
        raise NotImplementedError

    async def set_option(self, session_id: str, config_id: str, value: str | bool) -> list[ConfigOption]:
        """Set one of the session's settings; the answer is the whole set, since one can change another."""
        raise NotImplementedError

    async def login(self, method_id: str) -> None:
        raise NotImplementedError

    async def logout(self) -> None:
        raise NotImplementedError

    def apply(self, session_id: str, update: dict[str, Any]) -> None:
        """One session/update, applied to the session's records and told to the client."""
        raise NotImplementedError

    def read_permission(self, params: dict[str, Any], key: Any) -> PermissionRequest:
        raise NotImplementedError

    def answer_permission(self, chosen: str | None) -> dict[str, Any]:
        raise NotImplementedError

    def user_wait(self, session_id: str | None, change: int) -> None:
        """An agent's request of the session began (+1) or ended (-1) waiting on the person."""
        return

    # -- shared

    def session(self, session_id: str) -> SessionState:
        found = self.sessions.get(session_id)
        if found is None:
            found = self.sessions[session_id] = SessionState(session_id)
        return found

    def caps(self) -> Capabilities:
        if self.capabilities is None:
            raise RuntimeError('The connection is not initialized.')
        return self.capabilities

    def tell(self, session_id: str, kind: str, key: str, record: Any, delta: Any = None,
             raw: dict[str, Any] | None = None) -> None:
        state = self.sessions.get(session_id)
        event = Event(session_id, kind, key, record, delta, bool(state is not None and state.replaying), raw)
        try:
            self.client.changed(event)
        except Exception:
            log.exception('The client failed on a %s event', kind)

    def spawn(self, work: Awaitable[Any]) -> asyncio.Task[Any]:
        task = asyncio.ensure_future(work)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    async def request(self, method: str, params: dict[str, Any], timeout: float | None = None) -> Any:
        if timeout is None:
            return await self.conn.send_request(method, params)
        return await asyncio.wait_for(self.conn.send_request(method, params), timeout)

    async def notify(self, method: str, params: dict[str, Any]) -> None:
        await self.conn.send_notification(method, params)

    async def extension(self, method: str, params: Any, timeout: float | None = None) -> Any:
        """An extension request (`_`-prefixed method) such as `_session/steering`. When it is not answered in time
        it is withdrawn with ACP's `$/cancel_request` and TimeoutError is raised: the agent may have acted on it."""
        if not method.startswith('_'):
            raise ValueError(f'{method} is not an extension method; they begin with _.')
        held = self.sent.setdefault(method, deque())
        before = len(held)
        try:
            return await self.request(method, params, timeout)
        except TimeoutError:
            if len(held) > before:
                with contextlib.suppress(Exception):
                    await self.notify('$/cancel_request', {'requestId': held[before]})
            raise
        finally:
            if len(held) > before:
                del held[before]

    async def run(self, session_id: str, blocks: list[dict[str, Any]]) -> Turn:
        """Send a prompt and wait for the end of the work it started."""
        return await self.prompt(session_id, blocks).ended

    def handle_for(self, session_id: str) -> Prompt:
        loop = asyncio.get_running_loop()
        state = self.session(session_id)
        made = Prompt(session_id, loop.create_future(), loop.create_future(),
                      active_at_send=state.turn.state in ACTIVE)
        quiet(made.accepted)
        quiet(made.ended)
        self.waiting.setdefault(session_id, []).append(made)
        return made

    def end_prompt(self, made: Prompt, turn: Turn | None, error: BaseException | None = None) -> None:
        held = self.waiting.get(made.session_id) or []
        if made in held:
            held.remove(made)
        if error is not None:
            for future in (made.accepted, made.ended):
                if not future.done():
                    future.set_exception(error)
        elif turn is not None and not made.ended.done():
            made.ended.set_result(dataclasses.replace(turn))

    async def given(self, options: list[OptionValue], setup: SessionSetup, sent: bool) -> SessionSetup:
        """Values for the session's options, given at setup: sent with the setup request where the harness takes
        them (`sent`), else set one by one after it, in the order given. Either way the session's answer is the word
        on what it took, and a value it does not have is listed as ignored."""
        if not sent:
            for wanted in options:
                found = self.session(setup.session_id).option(wanted.config_id)
                if found is None:
                    continue
                if found.current != wanted.value:
                    try:
                        await self.set_option(setup.session_id, wanted.config_id, wanted.value)
                    except (RequestError, Unsupported) as error:
                        setup.ignored.append((wanted, str(error)))
            setup.options = list(self.session(setup.session_id).options)
        for wanted in options:
            if any(wanted is one for one, _ in setup.ignored):
                continue
            found = next((one for one in setup.options if one.config_id == wanted.config_id), None)
            if found is None:
                setup.ignored.append((wanted, 'the session offers no such option'))
            elif found.current != wanted.value:
                setup.ignored.append((wanted, f'the session kept {found.current!r}'))
        return setup

    # -- the stream

    def observe(self, event: StreamEvent) -> None:
        """Every message, in wire order, before the connection acts on it: the id of each incoming request, carried
        into its handler; the id of each extension request sent, for its withdrawal."""
        message = event.message
        method = message.get('method')
        if event.direction == StreamDirection.INCOMING:
            INCOMING.set(message.get('id') if method is not None else None)
            return
        if isinstance(method, str) and method in self.sent and 'id' in message:
            self.sent[method].append(message['id'])
        self.sent_message(method, message)

    def sent_message(self, method: Any, message: dict[str, Any]) -> None:
        """A message the client sent, as written; the v1 adapter takes a prompt as accepted here."""
        return

    async def handle(self, method: str, params: Any, notification: bool) -> Any:
        given = obj(params)
        if notification:
            self.notification(method, given)
            return None
        key = INCOMING.get()
        if method == 'session/request_permission':
            return await self.permission(given, key)
        if method == 'elicitation/create':
            return await self.elicitation(given, key)
        if method.startswith('_'):
            return await self.client.extension(method, params)
        self.tell(str(given.get('sessionId') or ''), UNSUPPORTED, method, given)
        raise RequestError(METHOD_NOT_FOUND, f'Method not found: {method}')

    def notification(self, method: str, params: dict[str, Any]) -> None:
        """A notification, applied before the handler first awaits, so updates keep the order they were sent in."""
        if method == 'session/update':
            session_id, update = params.get('sessionId'), params.get('update')
            if not isinstance(session_id, str) or not isinstance(update, dict):
                self.tell(str(session_id or ''), INVALID, 'session/update', params, raw=params)
                return
            self.apply(session_id, cast(dict[str, Any], update))
        elif method == '$/cancel_request':
            self.withdraw(params.get('requestId'))
        elif method == 'elicitation/complete':
            elicitation = params.get('elicitationId')
            if isinstance(elicitation, str):
                try:
                    self.client.elicitation_complete(elicitation)
                except Exception:
                    log.exception('The client failed on elicitation/complete')
        elif method == '_auth/status_update':
            status = params.get('authStatus')
            self.tell('', AUTH, method, status if isinstance(status, dict) else None, raw=params)
        elif method.startswith('_'):
            self.tell(str(params.get('sessionId') or ''), EXTENSION, method, params, raw=params)
        else:
            self.tell(str(params.get('sessionId') or ''), UNSUPPORTED, method, params, raw=params)

    def withdraw(self, key: Any, *, cancelled: bool = False) -> None:
        """An agent's request no longer wanted: by the agent (`$/cancel_request`, answered request-cancelled), or by a
        cancel of its turn in v1 (`cancelled`, answered as the client's cancel)."""
        held = self.asked.get(key)
        if held is None or held[1].done():
            return
        held[1].set_result(cancelled)
        try:
            self.client.withdrawn(key)
        except Exception:
            log.exception('The client failed on a withdrawn request')

    async def waited(self, key: Any, session_id: str | None, asking: Awaitable[Any]) -> tuple[bool, bool, Any]:
        """The client's answer to an agent's request, or its withdrawal first: (withdrawn, cancelled, answer)."""
        withdrawal: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self.asked[key] = (session_id, withdrawal)
        self.user_wait(session_id, 1)
        answer = self.spawn(asking)
        try:
            await asyncio.wait({answer, withdrawal}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            self.asked.pop(key, None)
            self.user_wait(session_id, -1)
        if withdrawal.done():
            answer.add_done_callback(lambda done: None if done.cancelled() else done.exception())
            return True, withdrawal.result(), None
        withdrawal.cancel()
        return False, False, answer.result()

    async def permission(self, params: dict[str, Any], key: Any) -> dict[str, Any]:
        request = self.read_permission(params, key)
        withdrawn, cancelled, chosen = await self.waited(key, request.session_id, self.client.permission(request))
        if withdrawn and not cancelled:
            raise RequestError(REQUEST_CANCELLED, 'Request cancelled')
        return self.answer_permission(None if withdrawn else cast(str | None, chosen))

    async def elicitation(self, params: dict[str, Any], key: Any) -> dict[str, Any]:
        mode = str(params.get('mode') or 'form')
        schema = params.get('requestedSchema')
        request = Elicitation(session_id=text_or_none(params.get('sessionId')), request_id=params.get('requestId'),
                              tool_call_id=text_or_none(params.get('toolCallId')), mode=mode,
                              message=str(params.get('message') or ''),
                              schema=cast(dict[str, Any], schema) if isinstance(schema, dict) else None,
                              url=text_or_none(params.get('url')),
                              elicitation_id=text_or_none(params.get('elicitationId')), key=key, raw=params)
        withdrawn, cancelled, answer = await self.waited(key, request.session_id, self.client.elicitation(request))
        if withdrawn and not cancelled:
            raise RequestError(REQUEST_CANCELLED, 'Request cancelled')
        given = ElicitationAnswer('cancel') if withdrawn else cast(ElicitationAnswer, answer)
        action = given.action if given.action in ('accept', 'decline', 'cancel') else 'cancel'
        if action == 'accept' and mode == 'form':
            return {'action': 'accept', 'content': given.content or {}}
        return {'action': action}

    async def watch(self) -> None:
        code = await self.process.wait()
        self.gone(code)

    def gone(self, code: int | None) -> None:
        """The harness's stream closed or its process ended: every prompt waiting on it fails, once."""
        if self.ended.is_set():
            return
        self.ended.set()
        lost = ConnectionError('The harness closed its connection' if code is None else f'The harness exited with {code}')
        for held in list(self.waiting.values()):
            for made in list(held):
                self.end_prompt(made, None, lost)
        for key in list(self.asked):
            self.withdraw(key, cancelled=True)
        self.tell('', ENDED, '', code)

    async def close(self) -> None:
        """Close the connection, then end the harness: its input closed, then its process group ended if it has not
        ended by itself."""
        with contextlib.suppress(Exception):
            await self.conn.close()
        process = self.process
        if process.stdin is not None:  # the connection leaves the pipe open; a harness ends when its input does
            with contextlib.suppress(Exception):
                process.stdin.close()
        if process.returncode is None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(process.wait(), END_LIMIT)
        if process.returncode is None:
            from .. import end_group  # dispatch's own: a harness started through npx runs as a grandchild
            end_group(process.pid)
            with contextlib.suppress(Exception):
                await asyncio.wait_for(process.wait(), END_LIMIT)
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.gone(process.returncode)

