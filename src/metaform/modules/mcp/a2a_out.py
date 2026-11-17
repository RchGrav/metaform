"""A2A outbound, MCP-040 to MCP-043: an agent sends a peer the person names a message about an Address, and what the
peer's task does comes back to that Address, over the official `a2a-sdk` client.

- Peers are the person's, records in the home that `mcp a2a_peer_add` and `a2a_peer_remove` keep, a2a_peers.py: each
  a name, a card URL and a token variable. The token is read from that variable when a message is sent and never
  stored. A peer's Agent Card is read when it is first used and kept in
  the project, `a2a_peers`; it is read again when a call fails with a version or interface error, MCP-040.
- `mcp a2a_send` sends one message with the Address as its `contextId`, the Address extension Metaform reads inbound,
  P005, and the sending agent instance under the same extension's metadata, `sender`, as the User-Agent says it too,
  MCP-042. The exchange is kept before the message leaves, `a2a_exchanges`, so a reply after any restart finds its
  Address and its ticket, MCP-043.
- What the peer's task does is recorded as it is heard: a state change on the exchange, an artifact as a message at
  the Address, numbered there, and a question the peer asks, its input-required status, as an open question at the
  Address on the exchange's ticket, MAP-050. Each is written once however many followers hear it, `records.moved`.
  The answer given there goes back on the peer's task, once, `answered`.
- `metaform mcp serve --http` follows every open exchange of every project while it runs, `attach`: those open at its
  start, then each one a change to a project's exchanges brings, read for that project alone; by the peer's stream
  where its card offers one, else by reading the peer's task again every `SLOW` seconds, the one clock here, since
  such a peer pushes nothing to this server; and again after each restart. Without a server,
  `mcp a2a_exchanges` reads the open ones again when it lists them. Receiving the peer's push notifications needs a
  webhook this server serves, and is not built.
- For a project held in the project store (kickoff 2026-11-17, t-legacy-keep), the Address is an element of that map,
  and what the peer says and asks is a record of its `questions` overlay at the Address, written through the map
  module's `project.messages`, where the page's Messages pane reads it. The exchanges stay in the mcp module's tables,
  which are not the map. Any other project keeps the old store's path.

Specification: https://a2a-protocol.org/latest/specification/ (1.0); SDK: https://github.com/a2aproject/a2a-python.
"""
from __future__ import annotations

import contextlib
import logging
import os
import time
import uuid
import zlib
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar, cast

import anyio
import httpx
from a2a.client import A2ACardResolver, A2AClientError, Client, ClientConfig, ClientFactory
from a2a.client.card_resolver import parse_agent_card
from a2a.types import (
    AgentCard,
    Artifact,
    CancelTaskRequest,
    GetTaskRequest,
    Message,
    Part,
    Role,
    SendMessageConfiguration,
    SendMessageRequest,
    StreamResponse,
    SubscribeToTaskRequest,
    Task,
    TaskState,
    TaskStatus,
    VersionNotSupportedError,
)
from a2a.utils.constants import TransportProtocol
from a2a.utils.errors import A2AError
from google.protobuf.json_format import MessageToDict
from starlette.applications import Starlette

from metaform import events, home, prompt_files
from metaform import project as project_store
from metaform.data import Node, Store, StoreError
from metaform.module import Context, Stop, chassis_version, first_line, provided, request_scope

from . import a2a_records as records
from .a2a import EXTENSION, SLOW, Changes, held, mapped
from .a2a_peers import Peer, peer

log = logging.getLogger(__name__)
_T = TypeVar('_T')

TIMEOUT = 30.0  # seconds a call to a peer may take; a stream is read without one
BINDINGS = [TransportProtocol.JSONRPC.value, TransportProtocol.HTTP_JSON.value]
# A2A's task states in the status vocabulary of work: a peer's interrupted states ask this side to act.
STATES: dict[int, str] = {
    TaskState.TASK_STATE_SUBMITTED: 'submitted', TaskState.TASK_STATE_WORKING: 'running',
    TaskState.TASK_STATE_INPUT_REQUIRED: 'input_required', TaskState.TASK_STATE_AUTH_REQUIRED: 'input_required',
    TaskState.TASK_STATE_COMPLETED: 'completed', TaskState.TASK_STATE_FAILED: 'failed',
    TaskState.TASK_STATE_REJECTED: 'failed', TaskState.TASK_STATE_CANCELED: 'cancelled'}
ENDED = ('completed', 'failed', 'cancelled')
ASKED = 10 * SLOW  # seconds between reads of a peer's task whose question waits on an answer here
TRANSPORT: httpx.AsyncBaseTransport | None = None  # what the calls go through; tests put a peer's app in-process here


# ---------------------------------------------------------------------------------------------------- peers
# The person's peers are records of the home, a2a_peers.py; each send looks its peer up there.


def prompt(name: str, **fills: str) -> str:
    return ' '.join((prompt_files.module('mcp', name, **fills) or '').split())


# ---------------------------------------------------------------------------------------------------- the client

def _http(peer: Peer, sender: str | None, timeout: float | None = TIMEOUT) -> httpx.AsyncClient:
    """The HTTP client one peer is reached with: its bearer token, and a User-Agent naming the sending agent, which a
    Metaform peer records on the ticket it opens, MCP-042."""
    headers = {'User-Agent': f'Metaform/{chassis_version()} ({sender or "person"})'}
    if peer.token:
        headers['Authorization'] = f'Bearer {peer.token}'
    return httpx.AsyncClient(timeout=timeout, headers=headers, transport=TRANSPORT)


async def card(project: str, peer: Peer, http: httpx.AsyncClient, fresh: bool = False) -> AgentCard:
    """The peer's Agent Card: kept from its first read, or read again when `fresh`, MCP-040."""
    kept = None if fresh else await _off(records.kept_card, project, peer.name, peer.url)
    if kept is not None:
        return parse_agent_card(kept)
    read = await A2ACardResolver(http, peer.url).get_agent_card(relative_card_path='/')
    await _off(records.keep_card, project, peer.name, peer.url, MessageToDict(read))
    return read


async def connect(project: str, peer: Peer, http: httpx.AsyncClient, *, streaming: bool,
                  fresh: bool = False) -> tuple[Client, AgentCard]:
    found = await card(project, peer, http, fresh)
    config = ClientConfig(streaming=streaming, httpx_client=http, supported_protocol_bindings=BINDINGS)
    return ClientFactory(config).create(found), found


async def calling(project: str, peer: Peer, sender: str | None, call: Callable[[Client], Any]) -> Any:
    """One call to a peer; on a version or interface error its card is read again and the call made once more."""
    async with _http(peer, sender) as http:
        for fresh in (False, True):
            try:
                client, _ = await connect(project, peer, http, streaming=False, fresh=fresh)
                return await call(client)
            except (VersionNotSupportedError, ValueError, A2AClientError, httpx.TransportError) as error:
                # an interface the kept card names that no longer answers, or none of it fits (ValueError)
                if fresh:
                    raise Stop(f'{peer.name} cannot be reached over A2A: {error}', 'ask the person to check the '
                               'peer\'s card URL') from None


async def _off(function: Callable[..., _T], *args: Any) -> _T:
    def run() -> _T:
        with request_scope(fresh=True):
            return function(*args)
    return await anyio.to_thread.run_sync(run)


# ---------------------------------------------------------------------------------------------------- what comes back

def _said(parts: Any) -> str:
    return '\n\n'.join(part.text for part in cast(list[Part], parts) if part.WhichOneof('content') == 'text'
                       and part.text.strip())


def _messages(project: str) -> Any:
    """The map module's questions and messages of a project held in the project store, `project.messages`: found before
    anything is claimed, so a module turned off leaves what the peer said to be heard again, never lost."""
    registered = home.project(project)
    found = provided(Path(registered.path), 'project.messages') if registered is not None else []
    if not found:
        raise Stop(f"The map module, which keeps {project}'s questions and messages, is not enabled; what the peer said "
                   'is kept until it is.', 'metaform enable map')
    return found[0][1]


def _tell(project: str, address: str, text: str, by: str, title: str, messages: Any = None) -> None:
    """A message for the person at the Address, as the peer said it."""
    name = held(project)
    if name is None:
        Store(project).tell(Node('element', address), text, by=by, title=title)
    else:
        (messages or _messages(project)).tell(name, address, text, by=by, title=title)


def _ask(project: str, address: str, said: str, by: str, title: str, why: str, messages: Any) -> str:
    """An open question at the Address, as the peer asked it; its id."""
    name = held(project)
    if name is None:
        return Store(project).ask(Node('element', address), said, by=by, title=title, why=why).id
    asked: Any = messages.ask(name, {'node': address, 'question': said, 'by': by, 'title': title, 'why': why}, [])
    return str(asked['id'])


def heard(project: str, exchange_id: str, status: TaskStatus | None = None, artifacts: tuple[Artifact, ...] = (),
          peer_task_id: str | None = None) -> records.Exchange | None:
    """What a peer told of an exchange's task, recorded where the work lives: the state on the exchange; each new
    artifact as a message at its Address; a question it asks as an open question there, which the agent or the person
    answers, MCP-041. The exchange keeps its ticket; the question is not linked to it, as that link marks an agent's
    permission request, which only the person answers. A key per artifact and per question, claimed with the state in
    one transaction, writes each once."""
    state = STATES.get(status.state) if status is not None else None
    said = _said(status.message.parts) if status is not None and status.HasField('message') else None
    claims = [f'artifact:{one.artifact_id}' for one in artifacts if _said(one.parts)]
    if state == 'input_required' and said:
        asked = status.message.message_id if status is not None and status.message.message_id else ''
        claims.append(f'question:{asked or format(zlib.crc32(said.encode()), "08x")}')
    messages = _messages(project) if claims and held(project) else None
    now, _, taken = records.moved(project, exchange_id, state=state, said=said, peer_task_id=peer_task_id,
                                  claims=tuple(claims))
    if now is None or not taken:
        return now
    by = f'a2a {now.peer}'
    for one in artifacts:
        if f'artifact:{one.artifact_id}' in taken:
            text = _said(one.parts)
            _tell(project, now.address, text, by, one.name or _title(text), messages)
    if any(key.startswith('question:') for key in taken) and said:
        question = _ask(project, now.address, said, by, _title(said), prompt('a2a_peer_question_why', peer=now.peer),
                        messages)
        if records.asking(project, exchange_id, now.asked, question):  # its answer goes back, `answered`
            now = records.exchange(project, exchange_id)
    return now


def _answer(project: str, found: records.Exchange) -> tuple[bool, str | None]:
    """Whether the exchange's open question is closed, and the answer it was closed with: read at its Address, else
    wherever it was moved to. A question no longer kept waits on nothing."""
    name = held(project)
    if name is not None:  # a record of the questions overlay, wherever it is now
        one = next((one for one in project_store.overlay_records(name, 'questions') or []
                    if one.get('id') == found.asked), None)
        return (True, None) if one is None else (bool(one.get('closed')), str(one.get('answer') or '').strip() or None)
    store = Store(project)
    for node in (Node('element', found.address), None):
        for one in store.messages(node, kind='question', limit=0).results:
            if one.id == found.asked:
                return one.closed is not None, (one.answer or '').strip() or None
    return True, None


def answered(project: str, exchange_id: str, folder: Path) -> records.Exchange | None:
    """The answer to the question a peer's task asked, sent back on that task once it is given at the Address,
    MCP-041: called by the follower, which a change to the map wakes, and by a listing before it reads the task again.
    The answer is claimed before it leaves, `records.sending`, so of two that read it only one sends it, and the open
    question is cleared only once the peer took it; a claim whose sender died mid-send is free again after twice
    `TIMEOUT`. When the peer is not reached the claim is let go, to be sent later. A peer that refuses the answer is
    said at the Address. A question closed with no answer clears it and sends nothing."""
    found = records.exchange(project, exchange_id)
    if found is None or not found.asked or found.state in ENDED or not found.peer_task_id:
        return found
    asked = found.asked
    closed, answer = _answer(project, found)
    if not closed:
        return found
    if answer is None:
        records.asking(project, exchange_id, asked, None)
        return records.exchange(project, exchange_id)
    to = peer(folder, found.peer)
    if not records.sending(project, exchange_id, asked, 2 * TIMEOUT):
        return records.exchange(project, exchange_id)
    message = Message(message_id=f'{exchange_id}:{asked}', role=Role.ROLE_USER, parts=[Part(text=answer)],
                      task_id=found.peer_task_id, context_id=found.address, extensions=[EXTENSION])
    request = SendMessageRequest(message=message, configuration=SendMessageConfiguration(return_immediately=True))

    async def go(client: Client) -> list[StreamResponse]:
        return [event async for event in client.send_message(request)]
    by = f'a2a {found.peer}'
    try:
        told = cast(list[StreamResponse], anyio.run(calling, project, to, found.sender, go))
    except Stop:  # not reached: the answer waits to be sent again
        records.unsent(project, exchange_id, asked)
        raise
    except Exception as error:  # noqa: BLE001  the peer's refusal, such as a task that takes no answer
        records.asking(project, exchange_id, asked, None)
        refused = prompt('a2a_answer_refused', peer=found.peer, error=str(error))
        if refused:
            _tell(project, found.address, refused, by, _title(refused))
        now, _, _ = records.moved(project, exchange_id, said=str(error))
        return now
    records.asking(project, exchange_id, asked, None)
    now = records.exchange(project, exchange_id)
    for event in told:
        if event.WhichOneof('payload') == 'message':  # the peer answered at once; its task goes on
            said = _said(event.message.parts)
            if said:
                _tell(project, found.address, said, by, _title(said))
        else:
            now = heard_event(project, exchange_id, event)
    return now


def _title(text: str) -> str:
    """An item's title from what the peer said: its first line, cut short when it is long."""
    return first_line(text) or (first_line(text, 0) or '')[:120].rstrip()


def heard_task(project: str, exchange_id: str, task: Task) -> records.Exchange | None:
    return heard(project, exchange_id, task.status, tuple(task.artifacts), task.id or None)


def heard_event(project: str, exchange_id: str, event: StreamResponse) -> records.Exchange | None:
    kind = event.WhichOneof('payload')
    if kind == 'task':
        return heard_task(project, exchange_id, event.task)
    if kind == 'status_update':
        return heard(project, exchange_id, event.status_update.status)
    if kind == 'artifact_update':
        return heard(project, exchange_id, artifacts=(event.artifact_update.artifact,))
    return records.exchange(project, exchange_id)


# ---------------------------------------------------------------------------------------------------- the verbs

def _shown(found: records.Exchange) -> dict[str, Any]:
    return {'exchange': found.exchange_id, 'peer': found.peer, 'peer_task': found.peer_task_id,
            'address': found.address, 'state': found.state, 'said': found.said, 'sender': found.sender,
            'work': found.work_id, 'created': found.created, 'updated': found.updated}


def send(ctx: Context) -> Any:
    """Send a peer one message about an Address and keep the exchange, MCP-041: the Address is the `contextId`, and
    the sending agent instance is named in the metadata, MCP-042. Returns the exchange id and the peer's task id."""
    ctx.require_store()
    project = str(ctx.project)
    to = peer(ctx.folder, str(ctx.nouns['peer']))
    address, text = str(ctx.nouns['address']).strip(), str(ctx.nouns['text']).strip()
    if not mapped(project, address):
        raise Stop(f'{address} is no Address in this project\'s map; what the peer returns is kept at the Address.',
                   'metaform map where <address>')
    if not text:
        raise Stop('The message holds no text.', 'give text="<the work>"')
    sender = ctx.session or 'person'
    work = str(ctx.nouns.get('work') or os.environ.get('METAFORM_WORK') or '') or None
    made = records.send(project, records.Exchange(uuid.uuid4().hex, to.name, address, text, sender=sender,
                                                  work_id=work))
    detail = {'sender': sender, **({'work': work} if work else {}),
              **({'title': str(ctx.nouns['title'])} if ctx.nouns.get('title') else {})}
    message = Message(message_id=made.exchange_id, role=Role.ROLE_USER, parts=[Part(text=text)], context_id=address,
                      metadata={EXTENSION: detail}, extensions=[EXTENSION])
    request = SendMessageRequest(message=message, configuration=SendMessageConfiguration(return_immediately=True))

    async def go(client: Client) -> list[StreamResponse]:
        return [event async for event in client.send_message(request)]
    try:
        answered = cast(list[StreamResponse], anyio.run(calling, project, to, sender, go))
    except Exception as error:  # the exchange is kept as failed, with what the peer said
        records.moved(project, made.exchange_id, state='failed', said=str(error))
        events.announce(ctx.folder, 'a2a')
        if isinstance(error, Stop):
            raise
        raise Stop(f'{to.name} did not take the message: {error}', 'metaform mcp a2a_exchanges') from None
    now: records.Exchange | None = made
    for event in answered:
        if event.WhichOneof('payload') == 'message':  # the peer answered at once, with no task to follow
            said = _said(event.message.parts)
            if said:
                _tell(project, address, said, f'a2a {to.name}', _title(said))
            now, _, _ = records.moved(project, made.exchange_id, state='completed', said=said)
        else:
            now = heard_event(project, made.exchange_id, event)
    events.announce(ctx.folder, 'a2a')
    shown = _shown(now or made)
    return {**shown, 'next': f'metaform mcp a2a_exchanges id={made.exchange_id}'}


def _reread(project: str, found: records.Exchange, folder: Path) -> records.Exchange:
    """An open exchange read again from its peer, for a listing made with no server following it."""
    if found.state in ENDED or not found.peer_task_id:
        return found
    try:
        if found.asked:
            found = answered(project, found.exchange_id, folder) or found
        to = peer(folder, found.peer)
        task_id = found.peer_task_id

        async def go(client: Client) -> Task:
            return await client.get_task(GetTaskRequest(id=task_id))
        task = cast(Task, anyio.run(calling, project, to, found.sender, go))
    except Exception as error:  # noqa: BLE001  the listing still shows what was last heard
        log.info('A2A exchange %s was not read again: %s', found.exchange_id, error)
        return found
    return heard_task(project, found.exchange_id, task) or found


def exchanges(ctx: Context) -> Any:
    """The exchanges this project sent, newest first, or one by its id, or those about one Address; an open one is
    read again from its peer first, MCP-041 and VIEW-050."""
    ctx.require_store()
    project = str(ctx.project)
    if ctx.nouns.get('id'):
        found = records.exchange(project, str(ctx.nouns['id']))
        if found is None:
            raise Stop(f'No exchange {ctx.nouns["id"]} in this project.', 'metaform mcp a2a_exchanges')
        listed = [found]
    else:
        listed = records.exchanges(project, str(ctx.nouns.get('address') or '') or None)
    shown = [_shown(_reread(project, one, ctx.folder)) for one in listed]
    return shown[0] if ctx.nouns.get('id') else {'exchanges': shown}


def cancel(ctx: Context) -> Any:
    """Cancel an exchange's task at its peer, MCP-041; the state the peer answers with is recorded."""
    ctx.require_store()
    project = str(ctx.project)
    found = records.exchange(project, str(ctx.nouns['id']))
    if found is None:
        raise Stop(f'No exchange {ctx.nouns["id"]} in this project.', 'metaform mcp a2a_exchanges')
    if found.state in ENDED or not found.peer_task_id:
        raise Stop(f'Exchange {found.exchange_id} is {found.state}; there is nothing to cancel.',
                   f'metaform mcp a2a_exchanges id={found.exchange_id}')
    task_id = found.peer_task_id

    async def go(client: Client) -> Task:
        return await client.cancel_task(CancelTaskRequest(id=task_id))
    try:
        task = cast(Task, anyio.run(calling, project, peer(ctx.folder, found.peer), found.sender, go))
    except Stop:
        raise
    except Exception as error:  # noqa: BLE001  the peer's refusal, such as a task that cannot be cancelled
        raise Stop(f'{found.peer} did not cancel its task: {error}',
                   f'metaform mcp a2a_exchanges id={found.exchange_id}') from None
    now = heard_task(project, found.exchange_id, task) or found
    events.announce(ctx.folder, 'a2a')
    return _shown(now)


# ---------------------------------------------------------------------------------------------------- following

EXCHANGES = 'mcp.a2a_exchanges'  # the exchanges' table, as a change names it


def exchanged(payload: dict[str, Any]) -> bool:
    """Whether a `map.changed` can have made or moved an exchange, from the change alone: it wrote the exchanges'
    table, or did not say what it wrote. A module's own payload, such as dispatch's, never does."""
    tables: Any = payload.get('tables')
    if isinstance(tables, str):
        return False
    return not isinstance(tables, list) or EXCHANGES in tables


class Wakes(Changes):
    """The A2A server's change listener, also woken by a change to a project's exchanges, so a new exchange is followed
    as soon as it is sent, from this process or another of the home, BASE-053: `pending` names the projects whose
    exchanges changed since they were last read, '' for every project."""

    def __init__(self) -> None:
        super().__init__()
        self.pending: set[str] = set()
        self.any: anyio.Event | None = None

    def concerned(self, payload: dict[str, Any]) -> bool:
        return exchanged(payload) or super().concerned(payload)

    def _wake(self, payload: dict[str, Any]) -> None:
        super()._wake(payload)
        if exchanged(payload):
            self.pending.add(str(payload.get('project') or ''))
            if self.any is not None:
                self.any.set()

    async def anything(self) -> set[str]:
        """The projects whose exchanges changed, once one has; a burst heard meanwhile is one answer."""
        self.bind()
        if not self.pending:
            self.any = anyio.Event()
            try:
                await self.any.wait()
            finally:
                self.any = None
        found, self.pending = self.pending, set()
        return found


@dataclass
class Followers:
    """Follows every open exchange of every registered project while the HTTP server runs, MCP-043."""
    folder: Path
    wakes: Wakes
    group: Any = None

    def __post_init__(self) -> None:
        self.following: set[tuple[str, str]] = set()

    async def run(self) -> None:
        """Every open exchange once at the start; then those of each project a change to its exchanges names."""
        projects: set[str] = {''}
        while True:
            try:
                for project, found in await _off(_open_exchanges, projects):
                    key = (project, found.exchange_id)
                    if key not in self.following and self.group is not None:
                        self.following.add(key)
                        self.group.start_soon(self.follow, project, found)
            except Exception:  # read again when the exchanges next change
                log.exception('A2A exchanges were not read')
            projects = await self.wakes.anything()

    async def follow(self, project: str, found: records.Exchange) -> None:
        """One exchange to its end: the peer's stream where its card offers one, else its task read again every `SLOW`
        seconds, the peer pushing nothing here; a stream that closes on input-required is opened again only once the
        task moves on. While its question waits on an answer here, the task cannot move: the follower waits for a
        change to the exchange's ticket, where the answer is given, sends the answer once it is, and reads the peer's
        task only every `ASKED` seconds, MCP-041."""
        try:
            to = await _off(peer, self.folder, found.peer)
            now: records.Exchange | None = found
            read: float | None = None  # when the peer's task was last read
            with self.wakes.waiting(project, found.work_id) as waiter:
                while now is not None and now.state not in ENDED and now.peer_task_id:
                    if now.state == 'input_required' and now.asked:
                        now = await _off(answered, project, found.exchange_id, self.folder)
                        if now is None or now.state in ENDED or not now.peer_task_id:
                            break
                        if now.asked and read is not None and time.monotonic() - read < ASKED:
                            with anyio.move_on_after(ASKED - (time.monotonic() - read)):  # the peer's task, read again
                                await waiter.wait()
                            continue
                    task_id = now.peer_task_id
                    async with _http(to, now.sender, timeout=None) as http:
                        client, offered = await connect(project, to, http, streaming=True)
                        if offered.capabilities.streaming and now.state != 'input_required':
                            with contextlib.suppress(A2AError, httpx.HTTPError, NotImplementedError):
                                async for event in client.subscribe(SubscribeToTaskRequest(id=task_id)):
                                    now = await _off(heard_event, project, found.exchange_id, event)
                        task = await client.get_task(GetTaskRequest(id=task_id))
                        now = await _off(heard_task, project, found.exchange_id, task)
                        read = time.monotonic()
                    if now is not None and now.state not in ENDED and not (now.state == 'input_required' and now.asked):
                        await anyio.sleep(SLOW)  # the peer pushes nothing here: its task is read again, or its stream
                        # opened again after it closed with the task still open
        except Stop as stop:  # the person took the peer off the list: the exchange waits until it is back
            log.warning('A2A exchange %s is not followed: %s', found.exchange_id, stop)
        except Exception:  # read again on the next round
            log.exception('A2A exchange %s stopped being followed', found.exchange_id)
            await anyio.sleep(SLOW)  # backoff after a failure
        finally:
            self.following.discard((project, found.exchange_id))


def _open_exchanges(projects: set[str]) -> list[tuple[str, records.Exchange]]:
    """The open exchanges of the projects named, of every registered project when '' is among them."""
    found: list[tuple[str, records.Exchange]] = []
    for project in home.projects():
        if '' not in projects and project.project_id not in projects:
            continue
        try:
            found += [(project.project_id, one) for one in records.exchanges(project.project_id, open_only=True)]
        except (Stop, StoreError):
            continue
    return found


def attach(app: Starlette, folder: Path) -> None:
    """Follow the open exchanges while the HTTP server runs, from its start, so every one sent before a restart is
    followed again, MCP-043."""
    followers = Followers(folder, Wakes())
    inner: Callable[[Any], Any] = app.router.lifespan_context

    @contextlib.asynccontextmanager
    async def lifespan(started: Any) -> AsyncGenerator[Any]:
        async with inner(started) as state, anyio.create_task_group() as group:
            followers.wakes.listen()
            followers.group = group
            group.start_soon(followers.run)
            try:
                yield state
            finally:
                group.cancel_scope.cancel()
                followers.wakes.close()
    app.router.lifespan_context = lifespan
