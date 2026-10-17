"""A2A beside MCP, P004, P005 and P002: other agents send Metaform work as tickets, over the official `a2a-sdk`.

`metaform mcp serve --http` serves A2A 1.0 on the same port as MCP while `mcp_a2a` is on, built from the SDK's own
Starlette routes, so the wire format, the JSON-RPC and HTTP+JSON bindings, Server-Sent Events, the error codes and the
`A2A-Version` check are the SDK's and not Metaform's. What Metaform supplies is the request handler, which maps the
protocol onto what already exists:

- A message whose contextId is an Address the map holds opens a ticket there, through the map module's own `map work
  op=add`, so it is numbered and titled at that Address like every ticket, MCP-037, and it lands in To do. That is the
  Address extension, P005. A message with no contextId is answered as A2A allows, with a task and a context of
  Metaform's own in `input_required`, offering the Addresses whose words fit the work; the client's reply on that task
  names one and the ticket opens there. A contextId that is neither is refused, as A2A requires.
- A ticket starts only when the person's `dispatch_autostart` is on, through dispatch's own `autostart`.
- A2A sees only what A2A made: the tickets its messages opened and the questions it asked. Any other id, the
  person's own tickets and workflow runs among them, is not found, as A2A asks of a task its client cannot reach.
- A task's state is the one status vocabulary of work, `metaform.data.status`, converted by its own `a2a`, read fresh
  from the ticket's work record and its dispatch record. A wait on Metaform's person, whom the client cannot reach,
  is working with `waitingOn` in the extension's metadata; input-required is only the question the client answers.
- CancelTask is dispatch's `cancel`. Streams, waiting sends and push watches re-read a task when a change is
  announced, `map.changed` from this process or any other of the home, BASE-053, with a slow read in between for
  what announces nothing; a stream closes when its task ends or asks the client for input, as the SDK's own does.
- Push notifications go only to webhooks the person allows in `mcp_a2a_webhooks`, through the SDK's own sender.

The public Agent Card at `/.well-known/agent-card.json` names no project: its one skill is the ticket. Every other
request needs the bearer token in `<home>/run/a2a-token`, separate from every other token, and is checked for a
loopback Host and Origin, as the MCP endpoint is. The authenticated extended card lists one interface per registered
project, the project id as its A2A tenant.

Specification: https://a2a-protocol.org/latest/specification/ (1.0); SDK: https://github.com/a2aproject/a2a-python.
"""
from __future__ import annotations

import contextlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time
import urllib.parse
import uuid
import weakref
import zlib
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Generator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar, cast

import anyio
import anyio.lowlevel
import httpx
from a2a.server.context import ServerCallContext
from a2a.server.request_handlers import request_handler as sdk_handler
from a2a.server.request_handlers.request_handler import RequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes, create_rest_routes
from a2a.server.tasks.base_push_notification_sender import BasePushNotificationSender
from a2a.server.tasks.push_notification_config_store import (
    PushNotificationConfigStore,
    normalize_push_notification_config,
)
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentExtension,
    AgentInterface,
    AgentSkill,
    Artifact,
    AuthenticationInfo,
    AuthorizationCodeOAuthFlow,
    CancelTaskRequest,
    ContentTypeNotSupportedError,
    DeleteTaskPushNotificationConfigRequest,
    GetExtendedAgentCardRequest,
    GetTaskPushNotificationConfigRequest,
    GetTaskRequest,
    HTTPAuthSecurityScheme,
    InvalidParamsError,
    ListTaskPushNotificationConfigsRequest,
    ListTaskPushNotificationConfigsResponse,
    ListTasksRequest,
    ListTasksResponse,
    Message,
    OAuth2SecurityScheme,
    OAuthFlows,
    Part,
    PushNotificationNotSupportedError,
    Role,
    SecurityRequirement,
    SecurityScheme,
    SendMessageRequest,
    StringList,
    SubscribeToTaskRequest,
    Task,
    TaskArtifactUpdateEvent,
    TaskNotCancelableError,
    TaskNotFoundError,
    TaskPushNotificationConfig,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    UnsupportedOperationError,
)
from a2a.utils.constants import PROTOCOL_VERSION_CURRENT, TransportProtocol
from google.protobuf.json_format import MessageToDict
from mcp.server.transport_security import (
    DEFAULT_MAX_REQUEST_BODY_SIZE,
    RequestBodyLimitMiddleware,
    TransportSecurityMiddleware,
    TransportSecuritySettings,
)
from starlette.applications import Starlette
from starlette.authentication import AuthCredentials, AuthenticationBackend, AuthenticationError, SimpleUser
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import HTTPConnection, Request
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute, Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from metaform import events, home, prompt_files, settings
from metaform.data import KINDS, Store, StoreError, WorkRecord, status
from metaform.module import (
    Stop,
    call,
    chassis_version,
    context,
    first_line,
    project_for,
    refresh_modules,
    request_scope,
    surface,
    tool_arguments,
    work_reads,
)

from . import a2a_records as records
from .oauth import A2A_SCOPE, Exposure, Introspection, transport_security

log = logging.getLogger(__name__)
_T = TypeVar('_T')
_F = TypeVar('_F', bound=Callable[..., Any])

# The Address extension, P005: a message's contextId is an Address. Published under Metaform's domain, as its other
# published ids are; the ids under it are an open question with the person, CHANGE-ORDER-2026-10-08 section 5.2.
EXTENSION = 'https://metaform.ing/a2a/address-context/v1'
META_KEYS = ('title', 'kind', 'address')  # what a message may give under the extension; the person decides the rest
JSONRPC_PATH = '/a2a'  # the JSON-RPC binding: POST here
REST_PATH = '/a2a/rest'  # the HTTP+JSON binding: /message:send, /tasks/{id} and the rest under it, and /{tenant}/...
SLOW = 20.0  # seconds a follower's reads go without following module changes, Changes.due
SCHEME = 'bearer'
SCOPES = ('tickets:read', 'tickets:write')  # what the one token grants, until OAuth scopes them, P007
CANDIDATES = 5  # the Addresses offered to a message that named none
WORD = re.compile(r'[a-z0-9]+')
MODES = ['text/plain', 'application/json']
LIST_SIZE, LIST_MOST = 50, 100  # ListTasks' default and largest page, as the SDK's own store pages
INTERRUPTED = (TaskState.TASK_STATE_INPUT_REQUIRED, TaskState.TASK_STATE_AUTH_REQUIRED)  # waits on the client
# A ticket's waits on Metaform's person, by the dispatch signal that says so: the reason under `waitingOn`.
WAITS = {'login-needed': 'login', 'permission-waiting': 'permission', 'question-waiting': 'question'}
LOOPBACK = TransportSecuritySettings(  # the MCP endpoint's own DNS-rebinding guard, the same hosts and origins
    enable_dns_rebinding_protection=True, allowed_hosts=['127.0.0.1:*', 'localhost:*', '[::1]:*'],
    allowed_origins=['http://127.0.0.1:*', 'http://localhost:*', 'http://[::1]:*'])


# ---------------------------------------------------------------------------------------------------- the token

def token_file() -> Path:
    return home.home() / 'run' / 'a2a-token'


def token(create: bool = False) -> str | None:
    """The home's A2A bearer token, made on the first start that serves A2A and kept for the next, readable by its
    owner alone. It is A2A's alone, so a token handed to another agent reaches no other surface, P007."""
    path = token_file()
    if path.exists():
        return path.read_text(encoding='utf-8').strip() or None
    if not create:
        return None
    home.mkdir_private(path.parent)
    made = secrets.token_urlsafe(32)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        handle.write(made)
    return made


class NodeBearer(AuthenticationBackend):
    """On a Metaform Node, an A2A request's bearer token is one the Node's authorization server issued for exactly
    `<public url>/a2a` with the `a2a:tickets` scope, checked by introspection: A2A's credential is apart from MCP's
    and the page's, and no static token is served beyond this machine, P007."""

    def __init__(self, exposed: Exposure) -> None:
        self.verifier = Introspection(exposed, exposed.a2a)

    async def authenticate(self, conn: HTTPConnection) -> tuple[AuthCredentials, SimpleUser]:
        scheme, _, given = conn.headers.get('authorization', '').partition(' ')
        if not scheme:
            raise AuthenticationError('')
        found = await self.verifier.verify_token(given.strip()) if scheme.lower() == SCHEME else None
        if found is None:
            raise AuthenticationError('invalid_token')
        if A2A_SCOPE not in found.scopes:
            raise AuthenticationError('insufficient_scope')
        claims: dict[str, Any] = dict(found.claims or {})
        return AuthCredentials(list(SCOPES)), SimpleUser(str(claims.get('username') or 'a2a'))


class Bearer(AuthenticationBackend):
    """Every A2A request but the public card carries `Authorization: Bearer <token>`, RFC 6750."""

    async def authenticate(self, conn: HTTPConnection) -> tuple[AuthCredentials, SimpleUser]:
        expected = token()
        scheme, _, given = conn.headers.get('authorization', '').partition(' ')
        if not scheme:
            raise AuthenticationError('')
        if expected is None or scheme.lower() != SCHEME or not hmac.compare_digest(given.strip(), expected):
            raise AuthenticationError('invalid_token')
        return AuthCredentials(list(SCOPES)), SimpleUser('a2a')


def refused(conn: HTTPConnection, error: Exception) -> Response:
    """401 with the challenge RFC 6750 names: bare when no credentials came, `invalid_token` when they were wrong."""
    challenge = 'Bearer realm="metaform-a2a"' + (f', error="{error}"' if str(error) else '')
    return JSONResponse({'error': str(error) or 'unauthorized', 'error_description': prompt('a2a_bearer')},
                        status_code=401, headers={'WWW-Authenticate': challenge})


class Loopback:
    """A Host and Origin that are this machine's, or 421 and 403, as the MCP SDK checks its own endpoint, so a web page
    cannot reach the A2A routes through DNS rebinding; on a Metaform Node, the Node's public name instead, oauth.py."""

    def __init__(self, app: ASGIApp, exposed: Exposure | None = None) -> None:
        self.app = app
        self.check = TransportSecurityMiddleware(transport_security(exposed) if exposed else LOOPBACK)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] == 'http':
            answer = await self.check.validate_request(Request(scope), is_post=False)
            if answer is not None:
                await answer(scope, receive, send)
                return
        await self.app(scope, receive, send)


# ---------------------------------------------------------------------------------------------------- changes

class Changes:
    """Wakes the tasks this server follows when a change concerns them: `map.changed` heard from another process of
    the home through `events.listen`, BASE-053, and from this process through the mcp module's subscription, `heard`.
    Each follower waits as a `Waiter` on its project and the ticket its task reads; a change is matched to the waiters
    from what it says alone, `concerns`, on the thread that heard it, so a change that concerns none of them costs the
    loop nothing and no read. A waiter woken while it reads is woken again at its next wait, so no change is missed."""

    def __init__(self) -> None:
        self.token: Any = None
        self.thread: int | None = None
        self.waiters: set[Waiter] = set()
        self.watched: frozenset[tuple[str, str | None]] = frozenset()  # the waiters' keys, for the hearing thread
        self.listener: Any = None
        self.refreshed = 0.0
        HUBS.add(self)

    def bind(self) -> None:
        """Take the running loop as the one to wake; called from it, by every request and at start."""
        self.token, self.thread = anyio.lowlevel.current_token(), threading.get_ident()

    def listen(self) -> None:
        self.bind()
        if self.listener is None:
            self.listener = events.listen('mcp', self.heard)

    def close(self) -> None:
        if self.listener is not None:
            self.listener.close()
            self.listener = None
        self.token = None

    @contextlib.contextmanager
    def waiting(self, project: str, work_id: str | None) -> Generator[Waiter]:
        """A waiter on the project's changes that concern the ticket, held while a follower follows its task. It
        starts woken: what changed since its task was last read is read once."""
        self.bind()
        waiter = Waiter(self, project, work_id)
        self.waiters.add(waiter)
        self._keys()
        try:
            yield waiter
        finally:
            self.waiters.discard(waiter)
            self._keys()

    def _keys(self) -> None:
        self.watched = frozenset((waiter.project, waiter.work_id) for waiter in self.waiters)

    def concerned(self, payload: dict[str, Any]) -> bool:
        """Whether a change concerns any waiter, from the change alone, on the thread that heard it."""
        return any(concerns(payload, project, work_id) for project, work_id in self.watched)

    def heard(self, payload: dict[str, Any]) -> None:
        """A change, on any thread: the waiters it concerns wake. One that concerns none, an agent's thread lines or
        another ticket's change among them, wakes nothing."""
        loop = self.token
        if loop is None or _lines_only(payload) or not self.concerned(payload):
            return
        if threading.get_ident() == self.thread:
            self._wake(payload)
            return
        try:
            anyio.from_thread.run_sync(self._wake, payload, token=loop)
        except Exception:  # noqa: BLE001, S110  a loop that has stopped has nobody left to wake
            pass

    def _wake(self, payload: dict[str, Any]) -> None:
        for waiter in list(self.waiters):
            if concerns(payload, waiter.project, waiter.work_id):
                waiter.wake()

    def due(self) -> bool:
        """Whether a follower's read should follow module changes: at most once a slow interval, as requests do
        each time, BASE-037."""
        now = time.monotonic()
        if now - self.refreshed < SLOW:
            return False
        self.refreshed = now
        return True


@dataclass(eq=False)
class Waiter:
    """One follower's wait on the changes that concern its ticket, `Changes.waiting`. `work_id` is the ticket its task
    reads, None while the task is a question that opened none, `follows`."""
    hub: Changes
    project: str
    work_id: str | None
    woken: bool = True
    event: anyio.Event | None = None

    def wake(self) -> None:
        self.woken = True
        if self.event is not None:
            self.event.set()

    async def wait(self) -> None:
        """Until a change that concerns the ticket, or at once when one came since the last wait."""
        if not self.woken:
            self.event = anyio.Event()
            try:
                await self.event.wait()
            finally:
                self.event = None
        self.woken = False

    def follows(self, work_id: str | None) -> None:
        """The ticket the task reads now: a question's task reads the ticket its answer opened."""
        if work_id != self.work_id:
            self.work_id = work_id
            self.hub._keys()  # pyright: ignore[reportPrivateUsage]


HUBS: weakref.WeakSet[Changes] = weakref.WeakSet()
# What a ticket's task is read from, A2A's `read`: its ticket, steps and questions, dispatch's sessions and signals,
# the A2A records, and the settings that say whether a ticket starts by itself.
TASK_TABLES = frozenset({'work', 'work_steps', 'work_links', 'messages', 'map.question_work', 'dispatch'})
TASK_PREFIXES = ('dispatch.', 'mcp.a2a_')


def concerns(payload: dict[str, Any], project: str, work_id: str | None) -> bool:
    """Whether a `map.changed` can change the task of a ticket, decided from the change alone, BASE-053: it is the
    project's, and it names the ticket; or it names no tickets or sessions and wrote what a task is read from, or did
    not say what it wrote. One that names only other tickets or sessions does not, as a dispatch runner decides."""
    if payload.get('project') not in (None, '', project):
        return False
    named: Any = payload.get('work_ids')
    sessions: Any = payload.get('session_ids')
    if work_id is not None and isinstance(named, list) and work_id in named:
        return True
    if isinstance(named, list) or isinstance(sessions, list):
        return False
    tables: Any = payload.get('tables')
    written = [tables] if isinstance(tables, str) else tables
    if not isinstance(written, list) or not written:
        return True
    return any(str(table) in TASK_TABLES or str(table).startswith(TASK_PREFIXES) or str(table).endswith('.settings')
               for table in cast(list[Any], written))


def _lines_only(payload: dict[str, Any]) -> bool:
    """Whether a change names dispatch's thread lines and nothing else: no signal, no session, no map table."""
    tables: Any = payload.get('tables')
    named: Any = payload.get('dispatch_tables')
    return (tables == 'dispatch' or tables == ['dispatch']) and named == ['dispatch.lines'] \
        and not payload.get('signal')


def heard(payload: dict[str, Any]) -> None:
    """A `map.changed` published in this process: the mcp module's subscription hands it to every server here."""
    for hub in list(HUBS):
        hub.heard(payload)


# ---------------------------------------------------------------------------------------------------- reading

def prompt(name: str, **fills: str) -> str:
    """One of the mcp module's A2A prompts, MCP-031; a blank one gives an empty text."""
    return ' '.join((prompt_files.module('mcp', name, **fills) or '').split())


def _stamp(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _starts(folder: Path) -> bool:
    """Whether a new ticket starts by itself: dispatch is on the folder's surface and the person's Autostart is on."""
    if not any(module.id == 'dispatch' for module in surface(folder)):
        return False
    try:
        return bool(settings.value('dispatch_autostart', folder))
    except KeyError:
        return False


def _verb(folder: Path, project: str, module_id: str, name: str, arguments: dict[str, Any]) -> Any:
    """Run a module's declared verb on the project folder's surface as a tool call runs it, its arguments checked as
    the command line checks them, on the surface `a2a`. A2A calls only `map work op=add` with what `_meta` lets
    through, dispatch's `autostart` and `cancel`, and workflow's `cancel`: none of them lets the sender choose an
    agent or answer for the person."""
    found = next((one for one in surface(folder) if one.id == module_id), None)
    verb = next((one for one in found.verbs if one.name == name), None) if found is not None else None
    if verb is None:
        raise Stop(f'{module_id} {name} is not on this project\'s surface.', f'metaform enable {module_id}')
    nouns, switches, _ = tool_arguments(module_id, verb, arguments, folder=folder)
    ctx = context(module_id, folder, project=project, nouns=nouns, switches=switches, sink=lambda _text: None,
                  surface='a2a')
    return call(verb.run, ctx)


def _work(project: str, work_id: str) -> WorkRecord | None:
    try:
        return cast(WorkRecord, Store(project).ticket(work_id).work)
    except (Stop, AttributeError):  # no such ticket, or the map module, which keeps tickets, is off
        return None


@dataclass
class Read:
    """One task as read now, in the status vocabulary of work, with what decides whether a follower has news."""
    task: Task
    state: status.State
    said: str
    artifacts: tuple[str, ...] = ()
    when: str = ''
    work_id: str | None = None  # the ticket it is read from; None for a question that opened none

    @property
    def ended(self) -> bool:
        return self.state in status.TERMINAL

    @property
    def interrupted(self) -> bool:
        """Whether the task waits on the A2A client, as A2A names it: then a stream closes and a send returns."""
        return self.task.status.state in INTERRUPTED


def _status(task_id: str, context_id: str, state: status.State, reason: str | None, text: str,
            when: str | None) -> TaskStatus:
    """The A2A status of work in `state`, converted by the status vocabulary, with the text that says it."""
    named = status.a2a(state, reason)
    made = TaskStatus(state=named, message=Message(
        message_id=f'{task_id}:status:{named}:{zlib.crc32(text.encode()):08x}', role=Role.ROLE_AGENT,
        parts=[Part(text=text)], context_id=context_id, task_id=task_id))
    stamp = _stamp(when)
    if stamp is not None:
        made.timestamp.FromDatetime(stamp)
    return made


def _limited(history: list[Message], length: int | None) -> list[Message]:
    if length is None:
        return history
    return history[-length:] if length > 0 else []


def checked(method: _F) -> _F:
    """The SDK's own check of a request's required fields, `validate_request_params`, which it leaves untyped."""
    validate: Callable[[Any], Any] = getattr(sdk_handler, 'validate_request_params')  # noqa: B009
    return cast(_F, validate(method))


def _dict(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


# A ticket's state, why it waits on the person when it does, and the prompt that says it, PLAN.md section 3.6.
Said = tuple[status.State, str | None, str]


def ticket_state(work: WorkRecord, kept: dict[str, Any], starts: bool) -> Said:
    """A ticket in the status vocabulary of work. Done ends as its work record says, completed, cancelled or failed,
    P232. Otherwise it is the status dispatch gives the ticket, its `ticket_work_status`, when dispatch keeps anything
    on it: an agent waiting on the person to log it in, or to answer its permission or question, stopped with the
    ticket open, or held by a runner that died, is `input_required` with what it waits for: the person acts, then the
    work goes on. A session idle between turns works on, as it reads to the A2A client. Taken is running; otherwise it
    is submitted."""
    if work.done:
        ended = status.known(work.outcome or 'completed', f'metaform map work id={work.id}')
        return ended, None, {'cancelled': 'a2a_cancelled', 'failed': 'a2a_failed'}.get(ended, 'a2a_completed')
    dispatch = _dict(kept.get('dispatch'))
    given, reason = dispatch.get('status'), dispatch.get('reason')
    if given == 'input_required' and reason not in (None, 'person'):
        said_by = {'login': 'a2a_login', 'stopped': 'a2a_stopped', 'runner died': 'a2a_stopped'}
        return 'input_required', str(reason), said_by.get(str(reason), 'a2a_person')
    if given in ('input_required', 'running'):  # starting, an intake's phase, or idle between turns (person)
        return 'running', None, 'a2a_working'
    if given == 'submitted':
        if reason == 'held' or _dict(kept.get('map')).get('hold'):
            return 'submitted', None, 'a2a_held'
        return 'submitted', None, 'a2a_queued' if starts else 'a2a_waiting'
    raised = {str(_dict(one).get('signal')) for one in cast(list[Any], dispatch.get('signals') or [])}
    for signal, why in WAITS.items():
        if signal in raised:
            return 'input_required', why, 'a2a_login' if why == 'login' else 'a2a_person'
    if work.taken:
        sessions = cast(list[Any], dispatch.get('sessions') or [])
        last = _dict(sessions[-1]) if sessions else {}
        if last.get('state') not in (None, 'running') or 'stopped-open' in raised:
            return 'input_required', 'stopped', 'a2a_stopped'
        return 'running', None, 'a2a_working'
    if work.held or _dict(kept.get('map')).get('hold'):
        return 'submitted', None, 'a2a_held'
    return 'submitted', None, 'a2a_queued' if starts else 'a2a_waiting'


def ticket_task(project: str, folder: Path, work: WorkRecord, history_length: int | None = None, *,
                task_id: str | None = None, context_id: str | None = None,
                sent: records.Sent | None = None) -> Read:
    """The ticket as an A2A task: by default its id is the work id and its contextId the Address it is at; a ticket
    opened in reply to a question keeps that question's task and context ids. A wait on the person reads as working,
    `waitingOn` naming them and `reason` what for; the resolution is an artifact only when the ticket completed."""
    kept = work_reads(folder, work, project=project)
    mapped = _dict(kept.get('map'))
    sent = sent or (None if task_id else records.sent(project, work.id))
    own = task_id or work.id
    context_id = context_id or (sent.context_id if sent else (work.address or work.receiver_address or ''))
    state, why, said_by = ticket_state(work, kept, _starts(folder) if not work.taken and not work.done else False)
    item = str(mapped.get('item') or work.id)
    title = str(mapped.get('title') or first_line(work.task, 0) or '')
    steps = prompt('a2a_steps', done=str(work.steps_done), planned=str(work.steps)) if work.steps else ''
    last = work.said[-1].said if work.said else None
    text = prompt(said_by, item=item, title=title, steps=steps, said=last or '', resolution=work.resolution or '',
                  reason=str(mapped.get('why') or work.resolution or ''))
    when = work.done or work.taken or work.created
    history = [Message(message_id=sent.message_id if sent else own, role=Role.ROLE_USER,
                       parts=[Part(text=work.task or '')], context_id=context_id, task_id=own)]
    history += [Message(message_id=f'{own}:step:{step.number}', role=Role.ROLE_AGENT, parts=[Part(text=step.said)],
                        context_id=context_id, task_id=own) for step in work.said if step.said]
    artifacts: list[Artifact] = []
    if state == 'completed' and work.resolution:
        why_done = mapped.get('why')
        artifacts.append(Artifact(artifact_id=f'{own}:resolution', name='resolution',
                                  parts=[Part(text=work.resolution, media_type='text/plain')],
                                  metadata={'why': str(why_done)} if why_done else None))
    detail: dict[str, Any] = {'item': item, 'title': title, 'column': work.column, 'project': project,
                              'address': work.address or work.receiver_address,
                              'resource': f'metaform://{item}' if '#' in item else None,
                              'steps': work.steps, 'stepsDone': work.steps_done,
                              'waitingOn': 'person' if why else None, 'reason': why}
    task = Task(id=own, context_id=context_id,
                status=_status(own, context_id, state, 'person' if why else None, text, when),
                history=_limited(history, history_length), artifacts=artifacts,
                metadata={EXTENSION: {key: value for key, value in detail.items() if value is not None}})
    return Read(task, state, text, tuple(one.artifact_id for one in artifacts), when, work.id)


def ask_task(project: str, asked: records.Ask, history_length: int | None = None) -> Read:
    """A message that named no Address, as the task Metaform gave it: `input_required`, its status text offering the
    Addresses that fit, until the client names one; `cancelled` when the client withdrew it."""
    if asked.cancelled:
        state: status.State = 'cancelled'
        text = prompt('a2a_ask_withdrawn')
    else:
        state = 'input_required'
        text = prompt('a2a_ask', candidates=_offered(asked.candidates)) if asked.candidates else prompt('a2a_ask_none')
    history = [Message(message_id=asked.message_id, role=Role.ROLE_USER, parts=[Part(text=asked.text)],
                       context_id=asked.context_id, task_id=asked.task_id)]
    detail = {'project': project, 'candidates': [one['address'] for one in asked.candidates]}
    task = Task(id=asked.task_id, context_id=asked.context_id,
                status=_status(asked.task_id, asked.context_id, state, None, text, asked.cancelled or asked.created),
                history=_limited(history, history_length), metadata={EXTENSION: detail})
    return Read(task, state, text, (), asked.cancelled or asked.created)


def _offered(candidates: list[dict[str, str]]) -> str:
    return '; '.join(f'{one["address"]} ({one["purpose"]})' if one.get('purpose') else one['address']
                     for one in candidates)


def read(project: str, folder: Path, task_id: str, history_length: int | None = None) -> Read | None:
    """A task A2A made, by its id: a question Metaform asked, read as its ticket once one opened, or a ticket a
    message opened. None for any other id, so the person's own tickets and workflow runs stay out of A2A's reach,
    A2A 1.0 section 3.3.2."""
    asked = records.asked(project, task_id)
    if asked is not None:
        work = _work(project, asked.work_id) if asked.work_id else None
        if work is None:
            return ask_task(project, asked, history_length)
        return ticket_task(project, folder, work, history_length, task_id=asked.task_id,
                           context_id=asked.context_id)
    sent = records.sent(project, task_id)
    work = _work(project, task_id) if sent is not None else None
    return None if work is None else ticket_task(project, folder, work, history_length, sent=sent)


def changes(before: Read, now: Read) -> list[TaskStatusUpdateEvent | TaskArtifactUpdateEvent]:
    """What a follower is told between two reads: each new artifact, then the status when it changed."""
    task = now.task
    told: list[TaskStatusUpdateEvent | TaskArtifactUpdateEvent] = [
        TaskArtifactUpdateEvent(task_id=task.id, context_id=task.context_id, artifact=artifact, last_chunk=True)
        for artifact in task.artifacts if artifact.artifact_id not in before.artifacts]
    if (now.state, now.said) != (before.state, before.said):
        told.append(TaskStatusUpdateEvent(task_id=task.id, context_id=task.context_id, status=task.status))
    return told


def candidates(project: str, text: str, most: int = CANDIDATES) -> list[dict[str, str]]:
    """The Addresses a work's words fit, best first: each element in context whose address, name or note, or the
    purposes it receives, hold the most of the work's words, whole or as a prefix, as the map's search matches.
    When no word fits, the trunk elements, fewest segments first, so the client still has somewhere to start."""
    words = {word for word in WORD.findall(text.lower()) if len(word) > 2}
    store = Store(project)
    found: list[tuple[int, int, str, str]] = []
    after: str | None = None
    while True:
        page = store.graph(limit=500, after=after)
        purposes: dict[str, list[str]] = {}
        for join in page.joins:
            if join.receiver_address and join.purpose:
                purposes.setdefault(join.receiver_address, []).append(join.purpose)
        for one in page.elements:
            element = one.element
            held = ' '.join([element.address.replace('.', ' ').replace('_', ' '), element.name or '',
                             element.reading, element.note or '', *purposes.get(element.address, [])])
            tokens = set(WORD.findall(held.lower()))
            hits = sum(1 for word in words if any(token.startswith(word) for token in tokens))
            found.append((-hits, element.address.count('.'), element.address,
                          first_line(' '.join(purposes.get(element.address, [])[:1]), 0) or ''))
        after = page.next
        if not after:
            break
    matched = [one for one in found if one[0] < 0] or found
    return [{'address': address, 'purpose': purpose} for _, _, address, purpose in sorted(matched)[:most]]


# ---------------------------------------------------------------------------------------------------- the handler

async def _off(function: Callable[..., _T], *args: Any, refresh: bool = True) -> _T:
    """Run store work in a worker thread, in a fresh registry scope, as each MCP request does, BASE-037: a request
    follows module changes first; a follower's read only when `refresh` says so. A Stop becomes the invalid-params
    error A2A answers with, its next step in the message."""
    def run() -> _T:
        with request_scope(fresh=True):
            if refresh:
                refresh_modules()
            return function(*args)
    try:
        return await anyio.to_thread.run_sync(run)
    except (Stop, StoreError) as stop:
        raise InvalidParamsError(message=f'{stop} Next: {stop.next_step}') from None


def _text(message: Message) -> str:
    """The work a message says: its text parts, its data as JSON and its links, in order. Raw bytes are refused."""
    said: list[str] = []
    for part in message.parts:
        kind = part.WhichOneof('content')
        if kind == 'text':
            said.append(part.text)
        elif kind == 'data':
            said.append(json.dumps(MessageToDict(part.data), ensure_ascii=False))
        elif kind == 'url':
            said.append(f'{part.filename}: {part.url}' if part.filename else part.url)
        elif kind == 'raw':
            raise ContentTypeNotSupportedError(message=prompt('a2a_raw'))
    return '\n\n'.join(one for one in said if one.strip())


def _meta(message: Message) -> dict[str, str]:
    """What a message gives under the Address extension: a title, a kind from the ticket kinds, and, replying to a
    question, the Address chosen. Nothing else is taken from a sender: which agent works a ticket, and what it links
    to, are the person's."""
    given: Any = MessageToDict(message.metadata).get(EXTENSION) if message.HasField('metadata') else None
    meta = {key: str(value).strip() for key, value in _dict(given).items() if key in META_KEYS and value}
    if meta.get('kind') and meta['kind'] not in KINDS:
        raise InvalidParamsError(message=prompt('a2a_kind', kinds=', '.join(KINDS)))
    return meta


def _chosen(message: Message, meta: dict[str, str], text: str) -> str:
    """The Address a reply names: under the extension's metadata, in a data part's `address`, or as its first word."""
    if meta.get('address'):
        return meta['address']
    for part in message.parts:
        if part.WhichOneof('content') == 'data':
            address = _dict(MessageToDict(part.data)).get('address')
            if isinstance(address, str) and address.strip():
                return address.strip()
    words = text.split()
    return words[0].strip('.,;:`"\'()<>') if words else ''


def allowed(url: str, folder: Path) -> bool:
    """A webhook the person allows: the scheme, host and port of one in `mcp_a2a_webhooks`, and a path under its
    path. Compared parsed, so https://agent.example cannot be stretched to https://agent.example.evil."""
    try:
        given = urllib.parse.urlsplit(url)
        given_port = given.port
    except ValueError:
        return False
    if given.scheme not in ('http', 'https') or not given.hostname:
        return False
    for entry in cast(list[str], settings.value('mcp_a2a_webhooks', folder) or []):
        try:
            allow = urllib.parse.urlsplit(entry.strip())
            allow_port = allow.port
        except ValueError:
            continue
        if (allow.scheme, (allow.hostname or '').lower()) != (given.scheme, given.hostname.lower()):
            continue
        if (allow_port or None) != (given_port or None):
            continue
        base = allow.path if allow.path.endswith('/') or not allow.path else allow.path + '/'
        if not allow.path or given.path == allow.path or given.path.startswith(base):
            return True
    return False


class PushConfigs(PushNotificationConfigStore):
    """The SDK's push configuration store, kept in the mcp module's table in one project's database, so a
    configuration lasts until its task ends or its client deletes it, across restarts, as A2A asks."""

    def __init__(self, project: str) -> None:
        self.project = project

    @staticmethod
    def _proto(push: records.Push) -> TaskPushNotificationConfig:
        made = TaskPushNotificationConfig(id=push.config_id, task_id=push.work_id, url=push.url, token=push.token or '')
        if push.scheme:
            made.authentication.CopyFrom(AuthenticationInfo(scheme=push.scheme, credentials=push.credentials or ''))
        return made

    async def set_info(self, task_id: str, notification_config: TaskPushNotificationConfig,
                       context: ServerCallContext) -> TaskPushNotificationConfig:
        stored = normalize_push_notification_config(task_id, notification_config)
        auth = stored.authentication if stored.HasField('authentication') else None
        push = records.Push(task_id, stored.id, stored.url, stored.token or None, auth.scheme if auth else None,
                            auth.credentials if auth else None, context.user.user_name or None)
        await _off(records.set_push, self.project, push)
        return stored

    async def get_info(self, task_id: str, context: ServerCallContext) -> list[TaskPushNotificationConfig]:
        return [self._proto(one) for one in await _off(records.pushes, self.project, task_id)]

    async def get_info_for_dispatch(self, task_id: str) -> list[TaskPushNotificationConfig]:
        return [self._proto(one) for one in await _off(records.pushes, self.project, task_id, refresh=False)]

    async def delete_info(self, task_id: str, context: ServerCallContext, config_id: str | None = None) -> None:
        await _off(records.delete_push, self.project, task_id, config_id)


async def follow(changes_: Changes, project: str, folder: Path, first: Read, *,
                 through_input: bool = False) -> AsyncIterator[TaskStatusUpdateEvent | TaskArtifactUpdateEvent]:
    """Each change to a task from `first` on, read again when its project changes, until it ends or, unless
    `through_input`, until it asks the client for input: a stream then closes, as the SDK's own server closes one on
    input-required, `EventConsumer.consume_all`, so the client sends its answer as a new message. A push watch
    follows through to the end. A task that can no longer be read, its ticket removed or the module keeping it off,
    is told as failed, so the client can tell it from a dropped connection."""
    last = first
    with changes_.waiting(project, first.work_id) as waiter:
        while not last.ended and (through_input or last.task.status.state != TaskState.TASK_STATE_INPUT_REQUIRED):
            await waiter.wait()
            now = await _off(read, project, folder, first.task.id, 0, refresh=changes_.due())
            if now is None:
                task = first.task
                yield TaskStatusUpdateEvent(task_id=task.id, context_id=task.context_id, status=_status(
                    task.id, task.context_id, 'failed', None, prompt('a2a_gone'), None))
                return
            waiter.follows(now.work_id)
            for event in changes(last, now):
                yield event
            last = now


@dataclass
class Pushes:
    """Watches each task that has a push configuration and sends every change through the SDK's sender, until the
    task ends: started for a new configuration, and for every kept one when the server starts."""
    folder: Path
    changes: Changes
    client: httpx.AsyncClient = field(default_factory=lambda: httpx.AsyncClient(timeout=15.0))
    watching: dict[tuple[str, str], Any] = field(default_factory=dict[tuple[str, str], Any])
    group: Any = None

    def sender(self, project: str) -> BasePushNotificationSender:
        folder = self.folder

        async def check(url: str) -> bool:
            return await _off(allowed, url, folder, refresh=False)
        return BasePushNotificationSender(self.client, PushConfigs(project), push_url_validator=check)

    def watch(self, project: str, folder: Path, first: Read) -> None:
        key = (project, first.task.id)
        if first.ended or key in self.watching or self.group is None:
            return
        self.watching[key] = True
        self.group.start_soon(self._run, project, folder, first)

    async def _run(self, project: str, folder: Path, first: Read) -> None:
        sender = self.sender(project)
        try:
            async for event in follow(self.changes, project, folder, first, through_input=True):
                await sender.send_notification(first.task.id, event)
            # The task ended or can no longer be read: its configurations end with it, as A2A asks.
            await _off(records.delete_push, project, first.task.id, refresh=False)
        except Exception:  # a watch that fails is logged; the task is still read on request
            log.exception('A2A push watch on %s stopped', first.task.id)
        finally:
            self.watching.pop((project, first.task.id), None)

    async def resume(self) -> None:
        """Watch again every task that kept a configuration through a restart. Each is first sent where it stands
        now, its artifacts and its status, since what it reached while the server was down was never pushed; one that
        ended, or can no longer be read, is told so and its configurations are deleted."""
        def kept() -> list[tuple[str, Path, str, Read | None, str | None]]:
            found: list[tuple[str, Path, str, Read | None, str | None]] = []
            for project in home.projects():
                try:
                    tasks = {push.work_id for push in records.pushes(project.project_id)}
                except (Stop, StoreError):
                    continue
                for task_id in tasks:
                    now = read(project.project_id, Path(project.path), task_id, 0)
                    known = None if now else (records.sent(project.project_id, task_id)
                                              or records.asked(project.project_id, task_id))
                    found.append((project.project_id, Path(project.path), task_id, now,
                                  known.context_id if known else None))
            return found
        try:
            for project, folder, task_id, now, context_id in await _off(kept):
                sender = self.sender(project)
                if now is None:
                    if context_id is not None:
                        await sender.send_notification(task_id, TaskStatusUpdateEvent(
                            task_id=task_id, context_id=context_id,
                            status=_status(task_id, context_id, 'failed', None, prompt('a2a_gone'), None)))
                    await _off(records.delete_push, project, task_id, refresh=False)
                    continue
                for event in changes(Read(now.task, now.state, now.said), now):  # its artifacts, then its status
                    await sender.send_notification(task_id, event)
                await sender.send_notification(task_id, TaskStatusUpdateEvent(
                    task_id=task_id, context_id=now.task.context_id, status=now.task.status))
                if now.ended:
                    await _off(records.delete_push, project, task_id, refresh=False)
                else:
                    self.watch(project, folder, now)
        except Exception:  # the server serves without the watches it could not resume
            log.exception('A2A push watches were not resumed')


class Tickets(RequestHandler):
    """The A2A request handler: every operation of the specification's section 3.1 on tickets and workflow runs."""

    def __init__(self, folder: Path, port: int, pushes: Pushes, exposed: Exposure | None = None) -> None:
        self.exposed = exposed
        self.folder = folder
        self.port = port
        self.pushes = pushes
        self.changes = pushes.changes

    # ---------------------------------------------------------------- the cards

    def _interfaces(self, tenant: str = '') -> list[AgentInterface]:
        base = self.exposed.public if self.exposed else f'http://127.0.0.1:{self.port}'
        return [AgentInterface(url=base + JSONRPC_PATH, protocol_binding=TransportProtocol.JSONRPC.value,
                               tenant=tenant, protocol_version=PROTOCOL_VERSION_CURRENT),
                AgentInterface(url=base + REST_PATH, protocol_binding=TransportProtocol.HTTP_JSON.value,
                               tenant=tenant, protocol_version=PROTOCOL_VERSION_CURRENT)]

    def card(self, extended: bool = False) -> AgentCard:
        """The Agent Card: the one skill this endpoint performs, a ticket, the bearer scheme, the Address extension,
        and, extended, one interface per registered project, the project id as its tenant."""
        wait = str(settings.value('mcp_a2a_wait', self.folder))
        example = prompt('a2a_skill_example')
        skills = [AgentSkill(id='ticket', name=prompt('a2a_skill_name'), description=prompt('a2a_skill', wait=wait),
                             tags=['ticket', 'address'], examples=[example] if example else [],
                             input_modes=MODES, output_modes=['text/plain'])]
        interfaces = self._interfaces()
        if extended:
            interfaces += [one for project in home.projects() for one in self._interfaces(project.project_id)]
        pushing = bool(settings.value('mcp_a2a_webhooks', self.folder))
        return AgentCard(
            name='Metaform', description=prompt('a2a_card'), version=chassis_version(),
            supported_interfaces=interfaces,
            capabilities=AgentCapabilities(streaming=True, push_notifications=pushing, extended_agent_card=True,
                                           extensions=[AgentExtension(uri=EXTENSION, description=prompt('a2a_extension'),
                                                                      required=False)]),
            security_schemes={SCHEME: self._scheme()},
            security_requirements=[SecurityRequirement(schemes={SCHEME: StringList(
                list=[A2A_SCOPE] if self.exposed else [])})],
            default_input_modes=MODES, default_output_modes=['text/plain'], skills=skills)

    def _scheme(self) -> SecurityScheme:
        """The bearer token in the home's run folder; on a Metaform Node, OAuth 2.0 authorization code with PKCE at
        the Node's own authorization server, its metadata named so a client discovers the rest, A2A 1.0 section 4.5."""
        if self.exposed is None:
            return SecurityScheme(http_auth_security_scheme=HTTPAuthSecurityScheme(
                scheme='Bearer', description=prompt('a2a_bearer')))
        base = self.exposed.public
        return SecurityScheme(oauth2_security_scheme=OAuth2SecurityScheme(
            oauth2_metadata_url=base + '/.well-known/oauth-authorization-server',
            flows=OAuthFlows(authorization_code=AuthorizationCodeOAuthFlow(
                authorization_url=base + '/oauth/authorize', token_url=base + '/oauth/token',
                refresh_url=base + '/oauth/token', pkce_required=True,
                scopes={A2A_SCOPE: 'Send this Metaform tickets and follow them.'}))))

    async def public_card(self, _card: AgentCard) -> AgentCard:
        return await _off(self.card)

    @checked
    async def on_get_extended_agent_card(self, params: GetExtendedAgentCardRequest,
                                         context: ServerCallContext) -> AgentCard:
        return await _off(self.card, True)

    # ---------------------------------------------------------------- where a request is

    def _project(self, tenant: str) -> tuple[str, Path]:
        """The tenant's project, or the folder's when no tenant is named."""
        if tenant:
            record = home.project(tenant)
            if record is None:
                raise Stop(f'No project {tenant} is registered.', 'GetExtendedAgentCard lists them as tenants')
            return record.project_id, Path(record.path)
        found = project_for(self.folder)
        record = home.project(found) if found else None
        if record is None:
            raise Stop(prompt('a2a_no_project'), 'GetExtendedAgentCard')
        return record.project_id, Path(record.path)

    async def _where(self, tenant: str) -> tuple[str, Path]:
        self.changes.bind()
        return await _off(self._project, tenant)

    async def _read(self, tenant: str, task_id: str, history_length: int | None = None) -> tuple[str, Path, Read]:
        project, folder = await self._where(tenant)
        found = await _off(read, project, folder, task_id, history_length)
        if found is None:
            raise TaskNotFoundError
        return project, folder, found

    # ---------------------------------------------------------------- tasks

    @checked
    async def on_get_task(self, params: GetTaskRequest, context: ServerCallContext) -> Task | None:
        length = params.history_length if params.HasField('history_length') else None
        return (await self._read(_tenant(params, context), params.id, length))[2].task

    @checked
    async def on_list_tasks(self, params: ListTasksRequest, context: ServerCallContext) -> ListTasksResponse:
        """The tasks A2A made, newest first: the tickets its messages opened and its questions, as A2A 1.0 section
        3.1.4 lists only what the client can reach. A state filter is applied before any task is built, each ticket
        read in full only when its kind of state could match; only the page is built."""
        project, folder = await self._where(_tenant(params, context))
        size = min(params.page_size or LIST_SIZE, LIST_MOST)
        start = int(params.page_token) if params.page_token.isdigit() else 0
        after = params.status_timestamp_after.ToDatetime() if params.HasField('status_timestamp_after') else None
        length = params.history_length if params.HasField('history_length') else None
        wanted = TaskState.Name(params.status) if params.status else None

        def listed() -> tuple[list[Task], int]:
            sent = records.every_sent(project)
            asked = records.asks(project)
            by_work = {one.work_id: one for one in asked if one.work_id}
            # each entry: when, its contextId, what its state may be as A2A names it, and how to read it in full
            entries: list[tuple[str, str, frozenset[str] | None, Callable[[], Read | None]]] = []
            works = {work.id: work for work in Store(project).work(limit=0, joins=True).results
                     if work.id in sent or work.id in by_work} if sent or by_work else {}
            for work_id, one_sent in sent.items():
                work = works.get(work_id)
                if work is not None:
                    entries.append((work.done or work.taken or work.created or '', one_sent.context_id,
                                    _could_be(work), lambda work=work, one_sent=one_sent: ticket_task(
                                        project, folder, work, length, sent=one_sent)))
            for one in asked:
                work = works.get(one.work_id or '')
                entries.append(((work.done or work.taken or work.created or '') if work else
                                one.cancelled or one.created, one.context_id, _could_be(work) if work else None,
                                lambda one=one: read(project, folder, one.task_id, length)))
            if params.context_id:
                entries = [one for one in entries if one[1] == params.context_id]
            if after is not None:
                entries = [one for one in entries if (stamp := _stamp(one[0])) is not None
                           and stamp.replace(tzinfo=None) > after.replace(tzinfo=None)]
            entries.sort(key=lambda one: one[0], reverse=True)
            if wanted is None:
                page = [built.task for one in entries[start:start + size] if (built := one[3]()) is not None]
                return page, len(entries)
            matching: list[Task] = []
            for one in entries:
                if one[2] is not None and wanted not in one[2]:
                    continue
                built = one[3]()
                if built is not None and TaskState.Name(built.task.status.state) == wanted:
                    matching.append(built.task)
            return matching[start:start + size], len(matching)
        tasks, total = await _off(listed)
        following = str(start + size) if start + size < total else ''
        return ListTasksResponse(tasks=tasks, next_page_token=following, page_size=size, total_size=total)

    @checked
    async def on_cancel_task(self, params: CancelTaskRequest, context: ServerCallContext) -> Task | None:
        """Cancel a ticket A2A opened through dispatch's `cancel`, which closes it with the outcome cancelled, or
        withdraw a question no ticket was opened for. An ended task is not cancelable; any other id is not found."""
        project, folder, found = await self._read(_tenant(params, context), params.id)
        if found.ended:
            raise TaskNotCancelableError
        given: Any = MessageToDict(params.metadata).get('reason') if params.HasField('metadata') else None
        reason = str(given or prompt('a2a_cancel_reason'))

        def cancel() -> Read | None:
            asked = records.asked(project, params.id)
            if asked is not None and not asked.work_id:
                records.withdrawn(project, params.id)
            else:
                if not any(module.id == 'dispatch' for module in surface(folder)):
                    raise TaskNotCancelableError(message=prompt('a2a_no_cancel'))
                work_id = asked.work_id if asked is not None and asked.work_id else params.id
                _verb(folder, project, 'dispatch', 'cancel', {'id': work_id, 'reason': [reason]})
            events.announce(folder, 'a2a')
            return read(project, folder, params.id)
        now = await _off(cancel)
        self.changes.heard({'project': project})
        return now.task if now is not None else None

    # ---------------------------------------------------------------- messages

    def _open(self, project: str, folder: Path, address: str, text: str, meta: dict[str, str], message_id: str,
              caller: str | None) -> str:
        """Open a ticket at an Address the map holds, titled from the metadata or the text's first line, and start it
        when the person's Autostart is on; returns its work id."""
        title = meta.get('title') or first_line(text) or (first_line(text, 0) or '')[:120].rstrip()
        arguments: dict[str, Any] = {'op': 'add', 'address': address, 'title': title, 'task': text,
                                     'note': prompt('a2a_note', caller=caller or prompt('a2a_caller'),
                                                    message=message_id)}
        if meta.get('kind'):
            arguments['kind'] = meta['kind']
        added: Any = _verb(folder, project, 'map', 'work', arguments)
        work_id = str(_dict(added).get('id') or getattr(added, 'id', ''))
        events.announce(folder, 'a2a')
        if _starts(folder):
            try:
                _verb(folder, project, 'dispatch', 'autostart', {})
                events.announce(folder, 'a2a')
            except Stop as stop:  # the ticket is open; it starts when the person or the page next starts tickets
                log.warning('A2A ticket %s was not started: %s', work_id, stop)
        return work_id

    def _ask(self, project: str, message: Message, text: str, meta: dict[str, str], caller: str | None,
             context_id: str | None) -> str:
        """A message that names no Address: a task of Metaform's own, in a context of its own unless the message
        continues one Metaform gave, offering the Addresses that fit; returns the task id."""
        task_id = uuid.uuid4().hex
        asked = records.Ask(task_id, context_id or f'a2a-{uuid.uuid4().hex}', message.message_id or task_id, text,
                            meta.get('title'), meta.get('kind'), caller, candidates(project, text))
        records.ask(project, asked)
        return task_id

    def _reply(self, project: str, folder: Path, message: Message, text: str, meta: dict[str, str]) -> str:
        """A message on an existing task. On a question Metaform asked, it names the Address and the ticket opens
        there. A2A refuses messages to an ended task, and a ticket takes no second message: what it waits on the
        person for, the person answers in Metaform."""
        asked = records.asked(project, message.task_id)
        if asked is None:
            found = read(project, folder, message.task_id)
            if found is None:
                raise TaskNotFoundError
            raise UnsupportedOperationError(message=prompt('a2a_ended' if found.ended else 'a2a_follow_up'))
        if message.context_id and message.context_id != asked.context_id:
            raise InvalidParamsError(message=prompt('a2a_ask_context', context=asked.context_id))
        if asked.cancelled:
            raise UnsupportedOperationError(message=prompt('a2a_ended'))
        if asked.work_id:
            raise UnsupportedOperationError(message=prompt('a2a_follow_up'))
        address = _chosen(message, meta, text)
        if not address or Store(project).element(address) is None:
            raise InvalidParamsError(message=prompt('a2a_no_answer', address=address or '""',
                                                    candidates=_offered(asked.candidates)))
        given = {key: value for key, value in (('title', asked.title), ('kind', asked.kind)) if value}
        work_id = self._open(project, folder, address, asked.text, {**given, **meta}, asked.message_id, asked.caller)
        records.opened(project, asked.task_id, work_id, message.message_id or None)
        return asked.task_id

    def _accept(self, project: str, folder: Path, message: Message, text: str, meta: dict[str, str],
                caller: str | None) -> str:
        """The task a message makes, once per message id: a reply on a task; a ticket at the Address its contextId
        names; a question when it names none, or continues a context Metaform gave. Any other contextId is refused,
        as A2A requires of one the agent cannot accept."""
        if message.message_id:
            already = records.by_message(project, message.message_id)
            if already is not None:
                return already
        if message.task_id:
            return self._reply(project, folder, message, text, meta)
        context_id = message.context_id.strip()
        if not context_id:
            return self._ask(project, message, text, meta, caller, None)
        if records.asks(project, context_id):
            return self._ask(project, message, text, meta, caller, context_id)
        if Store(project).element(context_id) is None:
            raise InvalidParamsError(message=prompt('a2a_no_address', address=context_id))
        work_id = self._open(project, folder, context_id, text, meta, message.message_id or '', caller)
        records.record(project, work_id, message.message_id or work_id, context_id, caller)
        return work_id

    async def _send(self, params: SendMessageRequest, context: ServerCallContext) -> tuple[str, Path, Read]:
        message = params.message
        text = _text(message)
        if not text.strip():
            raise InvalidParamsError(message=prompt('a2a_empty'))
        meta = _meta(message)
        tenant = _tenant(params, context)
        project, folder = await self._where(tenant)
        configuration = params.configuration
        push = configuration.task_push_notification_config \
            if configuration.HasField('task_push_notification_config') else None
        if push is not None:  # checked before anything is opened, so a refused webhook leaves no ticket behind
            await _off(self._pushing, folder)
            if not await _off(allowed, push.url, folder):
                raise InvalidParamsError(message=prompt('a2a_webhook_refused'))
        headers: Any = context.state.get('headers') or {}
        caller = first_line(str(cast(dict[str, Any], headers).get('user-agent') or '')) or None
        task_id = await _off(self._accept, project, folder, message, text, meta, caller)
        self.changes.heard({'project': project})
        length = configuration.history_length if configuration.HasField('history_length') else None
        found = await _off(read, project, folder, task_id, length)
        if found is None:
            raise TaskNotFoundError
        if push is not None:
            await self._configure(project, folder, found, _for_task(push, task_id, tenant), context)
        return project, folder, found

    @checked
    async def on_message_send(self, params: SendMessageRequest, context: ServerCallContext) -> Task | Message:
        """Make the task; then, unless the client asked to return at once, wait as A2A asks for it to end or need
        input, at most `mcp_a2a_wait` seconds, which the card states, and not at all for a ticket nothing will start
        by itself."""
        project, folder, found = await self._send(params, context)
        wait = 0 if params.configuration.return_immediately else int(settings.value('mcp_a2a_wait', folder))
        if wait and found.state == 'submitted' and not await _off(_starts, folder):
            wait = 0
        length = params.configuration.history_length if params.configuration.HasField('history_length') else None
        with anyio.move_on_after(wait), self.changes.waiting(project, found.work_id) as waiter:
            while wait and not found.ended and not found.interrupted:
                await waiter.wait()
                now = await _off(read, project, folder, found.task.id, length, refresh=self.changes.due())
                if now is None:
                    break
                waiter.follows(now.work_id)
                found = now
        return found.task

    @checked
    async def on_message_send_stream(self, params: SendMessageRequest,
                                     context: ServerCallContext) -> AsyncGenerator[Any]:
        project, folder, found = await self._send(params, context)
        yield found.task
        async for event in follow(self.changes, project, folder, found):
            yield event

    @checked
    async def on_subscribe_to_task(self, params: SubscribeToTaskRequest,
                                   context: ServerCallContext) -> AsyncGenerator[Any]:
        project, folder, found = await self._read(_tenant(params, context), params.id)
        if found.ended:
            raise UnsupportedOperationError(message=found.said)
        yield found.task
        async for event in follow(self.changes, project, folder, found):
            yield event

    # ---------------------------------------------------------------- push notifications

    def _pushing(self, folder: Path) -> None:
        if not settings.value('mcp_a2a_webhooks', folder):
            raise PushNotificationNotSupportedError

    async def _configure(self, project: str, folder: Path, found: Read, params: TaskPushNotificationConfig,
                         context: ServerCallContext) -> TaskPushNotificationConfig:
        made = await PushConfigs(project).set_info(found.task.id, params, context)
        self.pushes.watch(project, folder, found)
        return made

    @checked
    async def on_create_task_push_notification_config(self, params: TaskPushNotificationConfig,
                                                      context: ServerCallContext) -> TaskPushNotificationConfig:
        project, folder, found = await self._read(_tenant(params, context), params.task_id)
        await _off(self._pushing, folder)
        if not await _off(allowed, params.url, folder):
            raise InvalidParamsError(message=prompt('a2a_webhook_refused'))
        return await self._configure(project, folder, found, params, context)

    @checked
    async def on_get_task_push_notification_config(self, params: GetTaskPushNotificationConfigRequest,
                                                   context: ServerCallContext) -> TaskPushNotificationConfig:
        project, folder, _found = await self._read(_tenant(params, context), params.task_id)
        await _off(self._pushing, folder)
        for config in await PushConfigs(project).get_info(params.task_id, context):
            if config.id == params.id:
                return config
        raise TaskNotFoundError

    @checked
    async def on_list_task_push_notification_configs(self, params: ListTaskPushNotificationConfigsRequest,
                                                     context: ServerCallContext) -> ListTaskPushNotificationConfigsResponse:
        project, folder, _found = await self._read(_tenant(params, context), params.task_id)
        await _off(self._pushing, folder)
        return ListTaskPushNotificationConfigsResponse(
            configs=await PushConfigs(project).get_info(params.task_id, context))

    @checked
    async def on_delete_task_push_notification_config(self, params: DeleteTaskPushNotificationConfigRequest,
                                                      context: ServerCallContext) -> None:
        project, folder, _found = await self._read(_tenant(params, context), params.task_id)
        await _off(self._pushing, folder)
        await PushConfigs(project).delete_info(params.task_id, context, params.id or None)


def _tenant(params: Any, context: ServerCallContext) -> str:
    """The project a request names: its `tenant` parameter, or over HTTP+JSON the path's, which the SDK puts on the
    call context."""
    return str(getattr(params, 'tenant', '') or context.tenant)


def _could_be(work: WorkRecord) -> frozenset[str]:
    """The A2A states a ticket may read as, from the work record alone: what a state filter needs to skip reading
    the rest of a ticket that cannot match. An open ticket waiting on the person reads as working."""
    if work.done:
        return frozenset({status.a2a(status.known(work.outcome or 'completed', f'metaform map work id={work.id}'))})
    working = status.a2a('running')
    return frozenset({working} if work.taken else {working, status.a2a('submitted')})


def _for_task(config: TaskPushNotificationConfig, task_id: str, tenant: str) -> TaskPushNotificationConfig:
    made = TaskPushNotificationConfig()
    made.CopyFrom(config)
    made.task_id, made.tenant = task_id, tenant
    return made


# ---------------------------------------------------------------------------------------------------- mounting

def _guarded(route: BaseRoute, middleware: list[Middleware]) -> BaseRoute:
    """The SDK's route again, behind `middleware`: Starlette applies a route's middleware when it is made."""
    if isinstance(route, Route):
        return Route(route.path, route.endpoint, methods=list(route.methods or ()), name=route.name,
                     middleware=middleware)
    return route


def routes(folder: Path, port: int, pushes: Pushes, exposed: Exposure | None = None) -> list[BaseRoute]:
    """The A2A routes: the public card behind the loopback guard, and the JSON-RPC and HTTP+JSON bindings behind the
    loopback guard, the MCP endpoint's body limit and the bearer token; on a Metaform Node, the Node's name and its
    authorization server's tokens instead."""
    handler = Tickets(folder, port, pushes, exposed)
    guard = [Middleware(Loopback, exposed=exposed)]
    private = [*guard, Middleware(RequestBodyLimitMiddleware, max_body_size=DEFAULT_MAX_REQUEST_BODY_SIZE),
               Middleware(AuthenticationMiddleware, backend=NodeBearer(exposed) if exposed else Bearer(),
                          on_error=refused)]
    card = create_agent_card_routes(handler.card(), card_modifier=handler.public_card,
                                    cache_control='public, max-age=60')
    return [*(_guarded(one, guard) for one in card),
            *(_guarded(one, private) for one in create_jsonrpc_routes(handler, rpc_url=JSONRPC_PATH)),
            Mount(REST_PATH, routes=create_rest_routes(handler), middleware=private)]


def attach(app: Starlette, folder: Path, port: int, exposed: Exposure | None = None) -> str:
    """Serve A2A on the MCP server's app: its routes after MCP's; with the app, the change listener and the push
    watches kept through a restart start, and stop with it. Returns the line the server prints. On a Metaform Node
    no static token is made: the Node's authorization server issues A2A's."""
    if exposed is None:
        token(create=True)
    pushes = Pushes(folder, Changes())
    app.router.routes.extend(routes(folder, port, pushes, exposed))
    inner: Callable[[Any], Any] = app.router.lifespan_context

    @contextlib.asynccontextmanager
    async def lifespan(started: Any) -> AsyncGenerator[Any]:
        async with inner(started) as state, anyio.create_task_group() as group:
            pushes.changes.listen()
            pushes.group = group
            await pushes.resume()
            try:
                yield state
            finally:
                group.cancel_scope.cancel()
                pushes.changes.close()
                await pushes.client.aclose()
    app.router.lifespan_context = lifespan
    if exposed is not None:
        return f'A2A agent at {exposed.public}/.well-known/agent-card.json, tokens from {exposed.public}'
    return (f'A2A agent at http://127.0.0.1:{port}/.well-known/agent-card.json, bearer token in {token_file()}')
