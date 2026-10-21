"""An A2A seat, `a2a:<peer name>` or `a2a:<card URL>`: a remote A2A agent, reached through the official `a2a-sdk`
client (A2A 1.0).

A peer is one the person names, `config.peers`, with the variable that holds its token; the token is read when a
message is sent and never stored. A card URL that names no peer sits only when the person allows any URL,
`a2a_any_url`, and then with no token.

On its turn the seat is sent the turns since its last reply as one A2A message in the table's context: the first
message carries the table's contextId, and when the peer will not take a context it did not make, it is sent again
with none and the context the peer makes is kept for the seat's later turns. The peer's answer is its reply: a
message, or the task the message made, followed until it completes or asks for input; a task that asks for input is
continued by the seat's next turn. Every message names the table and the seat in its metadata, and the User-Agent
names the roundtable.
"""
from __future__ import annotations

import asyncio
import contextlib
import uuid
from typing import Any

import anyio
import httpx
from a2a.client import A2ACardResolver, A2AClientError, Client, ClientConfig, ClientFactory
from a2a.types import (
    AgentCard,
    CancelTaskRequest,
    GetTaskRequest,
    Message,
    Part,
    Role,
    SendMessageConfiguration,
    SendMessageRequest,
    StreamResponse,
    Task,
    TaskState,
)
from a2a.utils.constants import TransportProtocol
from a2a.utils.errors import A2AError

from . import __version__, config
from .seat import Late, NoReply, Reply, Seat

BINDINGS = [TransportProtocol.JSONRPC.value, TransportProtocol.HTTP_JSON.value]
TIMEOUT = 30.0  # seconds a card read may take
POLL = 1.0  # seconds between reads of a peer's task that is still working
WORKING = (TaskState.TASK_STATE_SUBMITTED, TaskState.TASK_STATE_WORKING)
ASKING = (TaskState.TASK_STATE_INPUT_REQUIRED, TaskState.TASK_STATE_AUTH_REQUIRED)
TRANSPORT: httpx.AsyncBaseTransport | None = None  # what the calls go through; a check may put a peer in-process here
META = 'roundtable'  # the metadata key every message the roundtable sends names its table and seat under


class Refused(Exception):
    """A seat this server will not send to; the message says why."""


def resolve(given: str) -> config.Peer:
    """The peer an `a2a:` seat names: a peer by its name, or by its card URL; any other URL only when the person
    allows any, with no token."""
    known = config.peers()
    if given in known:
        return known[given]
    if given.startswith(('http://', 'https://')):
        url = config.card_url(given)
        named = next((one for one in known.values() if one.card == url), None)
        if named is not None:
            return named
        if config.value('a2a_any_url'):
            return config.Peer('', url, None)
        raise Refused(f'{given} is not the card of an A2A peer the person names ({", ".join(sorted(known)) or "none"});'
                      ' add it under [peers.<name>] in config.toml, or set a2a_any_url.')
    raise Refused(f'{given} is not an A2A peer the person names ({", ".join(sorted(known)) or "none"}); add it '
                  'under [peers.<name>] in config.toml, or write its card URL.')


def http(peer: config.Peer, timeout: float | None = None) -> httpx.AsyncClient:
    headers = {'User-Agent': f'roundtable/{__version__}'}
    if peer.token:
        headers['Authorization'] = f'Bearer {peer.token}'
    return httpx.AsyncClient(timeout=timeout, headers=headers, transport=TRANSPORT)


async def card(peer: config.Peer) -> AgentCard:
    """The peer's Agent Card, read now; Refused when it cannot be."""
    try:
        async with http(peer, TIMEOUT) as client:
            return await A2ACardResolver(client, peer.card).get_agent_card(relative_card_path='/')
    except (A2AClientError, A2AError, httpx.HTTPError, ValueError) as error:
        raise Refused(f'The Agent Card at {peer.card} could not be read: {error}') from None


def text_of(parts: Any) -> str:
    return '\n\n'.join(part.text for part in parts if part.WhichOneof('content') == 'text' and part.text.strip())


def answer_of(task: Task) -> str:
    """What a peer's task says: its status message, else its artifacts, else its last message of its own."""
    if task.status.HasField('message') and text_of(task.status.message.parts):
        return text_of(task.status.message.parts)
    made = '\n\n'.join(text for artifact in task.artifacts if (text := text_of(artifact.parts)))
    if made:
        return made
    own = [one for one in task.history if one.role == Role.ROLE_AGENT and text_of(one.parts)]
    return text_of(own[-1].parts) if own else ''


class PeerSeat(Seat):
    kind = 'a2a'
    client: Client | None = None
    connection: httpx.AsyncClient | None = None
    following: str | None = None  # the peer's task while its answer is awaited

    def peer(self) -> config.Peer:
        try:
            return resolve(str(self.row['agent'] or self.row['model']))
        except Refused as error:
            raise NoReply(str(error)) from None

    async def open(self) -> None:
        if self.client is not None:
            return
        peer = self.peer()
        try:
            found = await card(peer)
        except Refused as error:  # the peer may answer next turn
            raise NoReply(str(error)) from None
        self.connection = http(peer)
        self.client = ClientFactory(ClientConfig(streaming=False, httpx_client=self.connection,
                                                 supported_protocol_bindings=BINDINGS)).create(found)
        self.reported = ' '.join(one for one in (found.name, found.version) if one)

    def message(self, text: str, context: str) -> Message:
        return Message(message_id=uuid.uuid4().hex, role=Role.ROLE_USER, parts=[Part(text=text)], context_id=context,
                       task_id=str(self.extra.get('task') or ''),
                       metadata={META: {'discussion': self.number, 'context': self.table['context_id'],
                                        'seat': self.name, 'position': self.position}})

    async def send(self, text: str, context: str) -> str:
        assert self.client is not None
        request = SendMessageRequest(message=self.message(text, context),
                                     configuration=SendMessageConfiguration(return_immediately=False))
        events: list[StreamResponse] = [event async for event in self.client.send_message(request)]
        if not events:
            raise NoReply('the peer sent nothing back', delivered=True)
        last = events[-1]
        kind = last.WhichOneof('payload')
        if kind == 'message':
            self.extra['context'] = last.message.context_id or self.extra.get('context') or context
            self.extra['task'] = None
            return text_of(last.message.parts)
        task = last.task if kind == 'task' else None
        if task is None:
            raise NoReply(f'the peer answered with {kind}, not a message or a task', delivered=True)
        self.following = task.id
        while task.status.state in WORKING:
            await asyncio.sleep(POLL)
            task = await self.client.get_task(GetTaskRequest(id=task.id))
        self.following = None
        self.extra['context'] = task.context_id or context
        self.extra['task'] = task.id if task.status.state in ASKING else None
        if task.status.state not in (TaskState.TASK_STATE_COMPLETED, *ASKING):
            raise NoReply(f'its task ended {TaskState.Name(task.status.state)}: {answer_of(task)}', delivered=True)
        return answer_of(task)

    async def first(self, text: str) -> str:
        """The turn sent in the seat's own context once it has one; else in the table's, and, when the peer will not
        take a context it did not make, again with none, so the peer makes one and the seat keeps it."""
        own = str(self.extra.get('context') or '')
        if own:
            return await self.send(text, own)
        if self.extra.get('fresh'):  # rebuilt: a context of the peer's own making, never the table's
            answer = await self.send(text, '')
            self.extra.pop('fresh', None)
            return answer
        try:
            return await self.send(text, str(self.table['context_id']))
        except (A2AError, A2AClientError):
            return await self.send(text, '')

    async def exchange(self, text: str, seconds: float) -> Reply:
        await self.open()
        try:
            with anyio.fail_after(seconds):
                answer = await self.first(text)
        except TimeoutError:
            if self.following and self.client is not None:
                with contextlib.suppress(A2AError, A2AClientError, httpx.HTTPError):
                    await self.client.cancel_task(CancelTaskRequest(id=self.following))
            self.following = None
            raise Late(seconds) from None
        except (A2AError, A2AClientError, httpx.HTTPError) as error:
            raise NoReply(f'{self.reported or "the peer"} did not answer: {error}', kind='transient') from None
        if not answer.strip():
            raise NoReply('the peer\'s answer held no text', delivered=True, kind='empty')
        return Reply(answer.strip(), {'model': self.reported})

    async def rebuild(self) -> None:
        """The seat's context at the peer let go, so its next turn starts in a new one."""
        self.extra.update(context=None, task=None, fresh=True)
        await super().rebuild()

    async def close(self) -> None:
        if self.connection is not None:
            await self.connection.aclose()
        self.client = self.connection = None
