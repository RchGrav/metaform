"""The roundtable as an A2A server (A2A 1.0, the official `a2a-sdk`), served beside MCP by `roundtable serve --http`.

Each table is one A2A context holding one task, its ids made when the table opens and given by `open` and `status`.
Every turn of the table is an A2A message in that context: the opening and the chair's comments from the user's side,
each seat's turn from the agent's side, credited to its seat in the message's metadata under `roundtable`, an
accepted submission as its text and a vetoed one as its verdict with the link to its text. The task works while the
table runs and completes when it ends, its report and its export the task's artifacts.

Anyone allowed follows a table by its context: ListTasks with the contextId finds the table's task, and SubscribeToTask
streams every turn as it lands, each as a status update carrying the turn's message, then the report and the export,
then the completed status. GetTask reads the table with its history. A2A cannot open, steer or end a table: the chair
does that over MCP, so SendMessage and CancelTask are refused with that said.

The public Agent Card at `/.well-known/agent-card.json` is open; every other request needs a bearer token, one of the
values of the variables the `a2a_tokens` setting names, and none is accepted when none is set. Tokens are read from the
environment and never stored. Requests are checked for a loopback Host and Origin, as the MCP endpoint is.

Specification: https://a2a-protocol.org/latest/specification/ (1.0); SDK: https://github.com/a2aproject/a2a-python.
"""
from __future__ import annotations

import hmac
import json
from collections.abc import AsyncGenerator, Callable
from pathlib import Path
from typing import Any, TypeVar, cast

import anyio
from a2a.server.context import ServerCallContext
from a2a.server.request_handlers import request_handler as sdk_handler
from a2a.server.request_handlers.request_handler import RequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes, create_rest_routes
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    Artifact,
    CancelTaskRequest,
    DeleteTaskPushNotificationConfigRequest,
    GetExtendedAgentCardRequest,
    GetTaskPushNotificationConfigRequest,
    GetTaskRequest,
    HTTPAuthSecurityScheme,
    ListTaskPushNotificationConfigsRequest,
    ListTaskPushNotificationConfigsResponse,
    ListTasksRequest,
    ListTasksResponse,
    Message,
    Part,
    Role,
    SecurityRequirement,
    SecurityScheme,
    SendMessageRequest,
    StringList,
    SubscribeToTaskRequest,
    Task,
    TaskArtifactUpdateEvent,
    TaskPushNotificationConfig,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)
from a2a.utils.constants import PROTOCOL_VERSION_CURRENT, TransportProtocol
from a2a.utils.errors import (
    ExtendedAgentCardNotConfiguredError,
    PushNotificationNotSupportedError,
    TaskNotCancelableError,
    TaskNotFoundError,
    UnsupportedOperationError,
)
from mcp.server.transport_security import (
    DEFAULT_MAX_REQUEST_BODY_SIZE,
    RequestBodyLimitMiddleware,
    TransportSecurityMiddleware,
    TransportSecuritySettings,
)
from starlette.authentication import AuthCredentials, AuthenticationBackend, AuthenticationError, SimpleUser
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import HTTPConnection, Request
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute, Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from . import __version__, config, export, render, runner, store
from .prompts import said
from .urls import http_base

_T = TypeVar('_T')
_F = TypeVar('_F', bound=Callable[..., Any])

JSONRPC_PATH = '/a2a'
REST_PATH = '/a2a/rest'
META = 'roundtable'  # the metadata key a message and a task carry the table's own fields under
POLL = 0.5  # seconds between reads of a followed table
LIST_SIZE, LIST_MOST = 50, 100
LOOPBACK = TransportSecuritySettings(
    enable_dns_rebinding_protection=True, allowed_hosts=['127.0.0.1:*', 'localhost:*', '[::1]:*'],
    allowed_origins=['http://127.0.0.1:*', 'http://localhost:*', 'http://[::1]:*'])


# ---------------------------------------------------------------------------------------------------- access

class Bearer(AuthenticationBackend):
    """Every request but the public card carries `Authorization: Bearer <token>`, one of the person's tokens."""

    async def authenticate(self, conn: HTTPConnection) -> tuple[AuthCredentials, SimpleUser]:
        scheme, _, given = conn.headers.get('authorization', '').partition(' ')
        if not scheme:
            raise AuthenticationError('')
        allowed = config.a2a_tokens()
        if scheme.lower() != 'bearer' or not any(hmac.compare_digest(given.strip(), one) for one in allowed):
            raise AuthenticationError('invalid_token')
        return AuthCredentials(['tables:read']), SimpleUser('a2a')


def refused(conn: HTTPConnection, error: Exception) -> Response:
    challenge = 'Bearer realm="roundtable"' + (f', error="{error}"' if str(error) else '')
    return JSONResponse({'error': str(error) or 'unauthorized', 'error_description': said('a2a_bearer')},
                        status_code=401, headers={'WWW-Authenticate': challenge})


class Loopback:
    """A Host and Origin that are this machine's, as the MCP SDK checks its own endpoint."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.check = TransportSecurityMiddleware(LOOPBACK)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] == 'http':
            answer = await self.check.validate_request(Request(scope), is_post=False)
            if answer is not None:
                await answer(scope, receive, send)
                return
        await self.app(scope, receive, send)


# ---------------------------------------------------------------------------------------------------- a table as A2A

def message_of(found: dict[str, Any], row: dict[str, Any]) -> Message:
    """One turn as an A2A message in the table's context, credited to its seat."""
    number = int(row['number'])
    nouls = store.nouls(row)
    detail = {'discussion': found['number'], 'turn': render.turn(number), 'number': number, 'seat': row['seat'],
              'name': render.who(row), 'kind': row['kind'], 'outcome': render.outcome(row),
              'link': render.link(int(found['number']), number), 'short': render.short(row),
              **({'failed': render.failed(row)} if render.outcome(row) == 'vetoed' else {}),
              **({'truncated': True} if row['truncated'] else {}),
              **({'nouls': dict(zip(store.noul_names(row), nouls, strict=True))} if nouls else {})}
    return Message(message_id=f'{found["context_id"]}-{number}', context_id=found['context_id'],
                   task_id=found['task_id'], role=Role.ROLE_USER if row['kind'] == 'chair' else Role.ROLE_AGENT,
                   parts=[Part(text=render.entry(row))], metadata={META: detail})


def opening_of(found: dict[str, Any]) -> Message:
    return Message(message_id=f'{found["context_id"]}-0', context_id=found['context_id'], task_id=found['task_id'],
                   role=Role.ROLE_USER, parts=[Part(text=found['opening'])],
                   metadata={META: {'discussion': found['number'], 'turn': render.turn(0), 'number': 0,
                                    'seat': 'chair', 'name': said('name_chair'), 'kind': 'opening'}})


def state_of(found: dict[str, Any]) -> TaskState:
    return TaskState.TASK_STATE_COMPLETED if found['state'] == 'ended' else TaskState.TASK_STATE_WORKING


def status_of(found: dict[str, Any], latest: int, stopped: bool = False) -> TaskStatus:
    """Where the table is, as the task's status: ended or held with the reason, stopped when its runner has, else
    whose turn it is."""
    seated = store.seats(int(found['number']))
    if stopped:
        text = said('a2a_stopped', state=found['state'])
    elif found['state'] in ('ended', 'ending', 'held'):
        text = said(f'a2a_{found["state"]}', reason=found['reason'] or '')
    else:
        at = int(found['position'])
        text = said('a2a_turn', round=found['round'], seat=seated[at]['name'] if at < len(seated) else 'Jev')
    return TaskStatus(state=state_of(found), message=Message(
        message_id=f'{found["context_id"]}-status-{"stopped" if stopped else found["state"]}-{latest}',
        context_id=found['context_id'],
        task_id=found['task_id'], role=Role.ROLE_AGENT, parts=[Part(text=text)]))


def artifacts_of(found: dict[str, Any]) -> list[Artifact]:
    """An ended table's report and export."""
    made: list[Artifact] = []
    report = Path(found['report']) if found['report'] else None
    if report is not None and report.is_file():
        made.append(Artifact(artifact_id=f'{found["task_id"]}-report', name='report',
                             parts=[Part(text=report.read_text(encoding='utf-8'), media_type='text/markdown')]))
    if found['state'] == 'ended':
        made.append(Artifact(artifact_id=f'{found["task_id"]}-export', name='export', parts=[Part(
            text=json.dumps(export.build(int(found['number'])), ensure_ascii=False), media_type='application/json')]))
    return made


def task_of(found: dict[str, Any], history: int | None = None) -> Task:
    rows = store.submissions(int(found['number']))
    messages = [opening_of(found), *(message_of(found, row) for row in rows)]
    if history is not None:
        messages = messages[-history:] if history > 0 else []
    latest = rows[-1]['number'] if rows else 0
    return Task(id=found['task_id'], context_id=found['context_id'], status=status_of(found, latest),
                history=messages, artifacts=artifacts_of(found) if found['state'] == 'ended' else [],
                metadata={META: {'discussion': found['number'], 'subject': found['subject'], 'state': found['state'],
                                 'reason': found['reason'] or '', 'round': found['round'], 'latest': latest,
                                 'seats': [{'seat': one['id'], 'name': one['name'], 'kind': one['kind']}
                                           for one in store.seats(int(found['number']))]}})


def by_task(task_id: str) -> dict[str, Any]:
    found = next((one for one in store.discussions() if one['task_id'] == task_id), None)
    if found is None:
        raise TaskNotFoundError
    return found


async def _off(function: Callable[..., _T], *args: Any) -> _T:
    return await anyio.to_thread.run_sync(lambda: function(*args))


def checked(method: _F) -> _F:
    """The SDK's own check of a request's required fields, `validate_request_params`."""
    validate: Callable[[Any], Any] = getattr(sdk_handler, 'validate_request_params')  # noqa: B009
    return cast(_F, validate(method))


async def follow(found: dict[str, Any], cursor: int) -> AsyncGenerator[Any]:
    """The table after turn `cursor`: each new turn as a status update carrying its message, a change of state as
    one, a runner that stopped while the table runs or ends as one, and at the end the report and the export, then
    the completed status."""
    number, state = int(found['number']), found['state']
    quiet: float | None = None  # since when the runner of a running or ending table has not been alive
    told = False  # the subscriber was told the runner stopped
    while True:
        await anyio.sleep(POLL)
        now = await _off(store.discussion, number)
        for row in await _off(store.submissions, number, cursor):
            yield TaskStatusUpdateEvent(task_id=now['task_id'], context_id=now['context_id'], status=TaskStatus(
                state=TaskState.TASK_STATE_WORKING, message=message_of(now, row)))
            cursor = int(row['number'])
        if now['state'] == 'ended' and (now['export'] or now['report_error']):
            for artifact in await _off(artifacts_of, now):
                yield TaskArtifactUpdateEvent(task_id=now['task_id'], context_id=now['context_id'],
                                              artifact=artifact, last_chunk=True)
            yield TaskStatusUpdateEvent(task_id=now['task_id'], context_id=now['context_id'],
                                        status=await _off(status_of, now, cursor))
            return
        moved = now['state'] != state
        if moved:
            yield TaskStatusUpdateEvent(task_id=now['task_id'], context_id=now['context_id'],
                                        status=await _off(status_of, now, cursor))
            state = now['state']
        # a runner starting takes a moment to beat, so it counts as stopped once it has been silent for a beat
        if now['state'] in ('running', 'ending') and not runner.alive(now):
            quiet = anyio.current_time() if quiet is None else quiet
            if not told and anyio.current_time() - quiet >= runner.BEAT:
                yield TaskStatusUpdateEvent(task_id=now['task_id'], context_id=now['context_id'],
                                            status=await _off(status_of, now, cursor, True))
                told = True
        else:
            if told and not moved:  # its runner is back: where the table is now
                yield TaskStatusUpdateEvent(task_id=now['task_id'], context_id=now['context_id'],
                                            status=await _off(status_of, now, cursor))
            quiet, told = None, False


class Tables(RequestHandler):
    """The A2A request handler: the tables as contexts and tasks, read and followed."""

    def __init__(self, host: str, port: int) -> None:
        self.base = http_base(host, port)

    def card(self) -> AgentCard:
        interfaces = [AgentInterface(url=self.base + JSONRPC_PATH, protocol_binding=TransportProtocol.JSONRPC.value,
                                     protocol_version=PROTOCOL_VERSION_CURRENT),
                      AgentInterface(url=self.base + REST_PATH, protocol_binding=TransportProtocol.HTTP_JSON.value,
                                     protocol_version=PROTOCOL_VERSION_CURRENT)]
        skill = AgentSkill(id='follow', name=said('a2a_skill_name'), description=said('a2a_skill'),
                           tags=['roundtable', 'discussion'], input_modes=['text/plain'],
                           output_modes=['text/plain', 'text/markdown', 'application/json'])
        return AgentCard(
            name='Roundtable', description=said('a2a_card'), version=__version__, supported_interfaces=interfaces,
            capabilities=AgentCapabilities(streaming=True, push_notifications=False, extended_agent_card=False),
            security_schemes={'bearer': SecurityScheme(http_auth_security_scheme=HTTPAuthSecurityScheme(
                scheme='Bearer', description=said('a2a_bearer')))},
            security_requirements=[SecurityRequirement(schemes={'bearer': StringList(list=[])})],
            default_input_modes=['text/plain'], default_output_modes=['text/plain'], skills=[skill])

    async def public_card(self, _card: AgentCard) -> AgentCard:
        return self.card()

    @checked
    async def on_get_extended_agent_card(self, params: GetExtendedAgentCardRequest,
                                         context: ServerCallContext) -> AgentCard:
        raise ExtendedAgentCardNotConfiguredError

    @checked
    async def on_get_task(self, params: GetTaskRequest, context: ServerCallContext) -> Task | None:
        length = params.history_length if params.HasField('history_length') else None
        return await _off(task_of, await _off(by_task, params.id), length)

    @checked
    async def on_list_tasks(self, params: ListTasksRequest, context: ServerCallContext) -> ListTasksResponse:
        """The tables, newest first, those of one context when it is named."""
        size = min(params.page_size or LIST_SIZE, LIST_MOST)
        start = int(params.page_token) if params.page_token.isdigit() else 0
        length = params.history_length if params.HasField('history_length') else 0

        def listed() -> tuple[list[Task], int]:
            found = [one for one in store.discussions()
                     if (not params.context_id or one['context_id'] == params.context_id)
                     and (not params.status or state_of(one) == params.status)]
            return [task_of(one, length) for one in found[start:start + size]], len(found)
        tasks, total = await _off(listed)
        following = str(start + size) if start + size < total else ''
        return ListTasksResponse(tasks=tasks, next_page_token=following, page_size=size, total_size=total)

    @checked
    async def on_subscribe_to_task(self, params: SubscribeToTaskRequest,
                                   context: ServerCallContext) -> AsyncGenerator[Any]:
        found = await _off(by_task, params.id)
        if found['state'] == 'ended' and (found['export'] or found['report_error']):
            raise UnsupportedOperationError(message=said('a2a_over', discussion=found['number']))
        task = await _off(task_of, found)
        yield task
        async for event in follow(found, int(cast(Any, task.metadata)[META]['latest'])):
            yield event

    @checked
    async def on_message_send(self, params: SendMessageRequest, context: ServerCallContext) -> Task | Message:
        raise UnsupportedOperationError(message=said('a2a_no_send'))

    @checked
    async def on_message_send_stream(self, params: SendMessageRequest,
                                     context: ServerCallContext) -> AsyncGenerator[Any]:
        raise UnsupportedOperationError(message=said('a2a_no_send'))
        yield  # an async generator, as the SDK expects

    @checked
    async def on_cancel_task(self, params: CancelTaskRequest, context: ServerCallContext) -> Task | None:
        await _off(by_task, params.id)
        raise TaskNotCancelableError(message=said('a2a_no_cancel'))

    async def on_create_task_push_notification_config(self, params: TaskPushNotificationConfig,
                                                      context: ServerCallContext) -> TaskPushNotificationConfig:
        raise PushNotificationNotSupportedError

    async def on_get_task_push_notification_config(self, params: GetTaskPushNotificationConfigRequest,
                                                   context: ServerCallContext) -> TaskPushNotificationConfig:
        raise PushNotificationNotSupportedError

    async def on_list_task_push_notification_configs(self, params: ListTaskPushNotificationConfigsRequest,
                                                     context: ServerCallContext) -> ListTaskPushNotificationConfigsResponse:
        raise PushNotificationNotSupportedError

    async def on_delete_task_push_notification_config(self, params: DeleteTaskPushNotificationConfigRequest,
                                                      context: ServerCallContext) -> None:
        raise PushNotificationNotSupportedError


def _guarded(route: BaseRoute, middleware: list[Middleware]) -> BaseRoute:
    """The SDK's route again, behind `middleware`: Starlette applies a route's middleware when it is made."""
    if isinstance(route, Route):
        return Route(route.path, route.endpoint, methods=list(route.methods or ()), name=route.name,
                     middleware=middleware)
    return route


def routes(host: str, port: int) -> list[BaseRoute]:
    """The A2A routes: the public card behind the loopback guard; the JSON-RPC and HTTP+JSON bindings behind it, a
    body limit and the bearer token."""
    handler = Tables(host, port)
    guard = [Middleware(Loopback)]
    private = [*guard, Middleware(RequestBodyLimitMiddleware, max_body_size=DEFAULT_MAX_REQUEST_BODY_SIZE),
               Middleware(AuthenticationMiddleware, backend=Bearer(), on_error=refused)]
    card = create_agent_card_routes(handler.card(), card_modifier=handler.public_card,
                                    cache_control='public, max-age=60')
    return [*(_guarded(one, guard) for one in card),
            *(_guarded(one, private) for one in create_jsonrpc_routes(handler, rpc_url=JSONRPC_PATH)),
            Mount(REST_PATH, routes=create_rest_routes(handler), middleware=private)]
