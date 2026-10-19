"""Keep the host's stdio connection while handing a call to newer code.

Two things hand a connection over, both decided before a handler can act: the pre-dispatch schema check's private
retry marker, and a tool call that finds the package's code changed on disk since the server serving it started,
`Fingerprint`. A server keeps the code it imported, so without the second an agent's server served code hours old,
or a file it had imported half written while another agent was editing it, until its session ended (2026-10-19).
In-flight calls finish on the old server before replacement, so a committed write is never replayed; a code change
hands over only when no other call is in flight, so a long call never holds the next one. The first process keeps
the host's pipes and replaces its successor in place, so changes in a busy tree never make a chain of processes.
SDK transports own pipe and child cleanup.
"""
from __future__ import annotations

import inspect
import os
import sys
import uuid
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

import anyio
from anyio.abc import TaskStatus
from mcp import StdioServerParameters, types
from mcp.client.stdio import stdio_client
from mcp.server.subscriptions import SUBSCRIPTION_ID_META_KEY
from mcp.shared._stream_protocols import ReadStream, WriteStream
from mcp.shared.exceptions import MCPError
from mcp.shared.message import ServerMessageMetadata, SessionMessage

from metaform.data import NewerStore
from metaform.module import code_print

Read = ReadStream[SessionMessage | Exception]
Write = WriteStream[SessionMessage]
RETRY = -32098
SUCCESSOR = 'METAFORM_MCP_SUCCESSOR'  # set on a server a relay started: the relay that started it replaces it
LISTEN = 'subscriptions/listen'  # a stream that stays open, so it never holds a hand-over


class Fingerprint:
    """The package's source files as one server imported them: each file's modification time and size. Taken when
    the server starts and read once per tool call, which is what asks whether the code serving it is still the code
    on disk; nothing reads it on a timer. Tests are not served. A file added since matters only once a changed file
    imports it, and that change is seen."""

    def __init__(self) -> None:
        root = Path(inspect.getfile(code_print)).parent
        self.files = {str(path): self.key(path) for path in root.rglob('*.py')
                      if 'tests' not in path.relative_to(root).parts}

    @staticmethod
    def key(path: Path | str) -> tuple[int, int] | None:
        try:
            state = os.stat(path)
        except OSError:
            return None
        return state.st_mtime_ns, state.st_size

    def changed(self) -> bool:
        return any(self.key(path) != kept for path, kept in self.files.items())


class Relay:
    def __init__(self, folder: Path, enabled: bool) -> None:
        # read once and taken out, so the processes this server starts (a runner, its agent's own server) relay
        self.folder, self.enabled = folder, enabled and not os.environ.pop(SUCCESSOR, None)
        self.code = code_print()
        self.prints = Fingerprint() if self.enabled else None
        self.token = uuid.uuid4().hex
        # The client's first request, which fixed the connection's era: a successor must open in the same one. An
        # initialize later is not an opening: Claude Code sends one when its server/discover probe times out, which the
        # server, having read the probe first, refuses (code.server.tool#24).
        self.opening: SessionMessage | None = None
        self.initialized: SessionMessage | None = None

    def stale(self, rpc: types.JSONRPCRequest, pending: dict[Any, SessionMessage]) -> bool:
        """Whether this tool call goes to a new server: the code on disk changed since the one serving the connection
        started, and no other call but an open listen stream is in flight, so none waits on the hand-over."""
        if self.prints is None or rpc.method != 'tools/call':
            return False
        if any(isinstance(one.message, types.JSONRPCRequest) and one.message.id != rpc.id
               and one.message.method != LISTEN for one in pending.values()):
            return False
        return self.prints.changed()

    def refusal(self, error: NewerStore) -> MCPError:
        """A retry marker is private to this relay and only issued before a handler can act."""
        text = f'Error: {error}\nNext: {error.next_step}'
        if self.enabled and code_print() != self.code:
            return MCPError(RETRY, text, self.token)
        return MCPError(-32603, text)

    @asynccontextmanager
    async def successor(self, retry: dict[Any, SessionMessage]) -> AsyncGenerator[
            tuple[Read, Write, SessionMessage | None]]:
        parameters = StdioServerParameters(command=sys.executable, args=['-m', 'metaform', 'mcp', 'serve'],
                                           cwd=self.folder, env={**os.environ, SUCCESSOR: '1'})
        async with stdio_client(parameters) as (read, write):
            opening = self.opening or next(iter(retry.values()))
            legacy = isinstance(opening.message, types.JSONRPCRequest) and opening.message.method == 'initialize'
            if not legacy:
                # A July connection has no initialize. Discover proves that the new package actually started
                # before the old server is stopped, and with the opening request's envelope opens it in July too.
                params = opening.message.params if isinstance(opening.message, types.JSONRPCRequest) else None
                opening = SessionMessage(types.JSONRPCRequest(jsonrpc='2.0', id=self.token,
                    method='server/discover', params={'_meta': (params or {}).get('_meta', {})}))
            await write.send(opening)
            with anyio.fail_after(20):
                reply = await read.receive()
            if isinstance(reply, Exception):
                raise reply
            if isinstance(reply.message, types.JSONRPCError):
                raise MCPError.from_jsonrpc_error(reply.message)
            if not isinstance(reply.message, types.JSONRPCResponse):
                raise MCPError(-32603, 'Replacement did not answer its readiness request.')
            if legacy and self.initialized is not None:
                await write.send(self.initialized)
            # If initialization itself was refused, its verified replacement answer belongs to the host.
            returned = reply if legacy and reply.message.id in retry else None
            yield read, write, returned

    async def run(self, serve: Callable[[Read, Write], Any], read: Read, write: Write,
                  close_subscriptions: Callable[[], None]) -> None:
        # One ordered mailbox owns routing. Buffers hold only traffic already received during hand-over.
        send, receive = anyio.create_memory_object_stream[tuple[str, SessionMessage | Exception | None]](0)
        local_send, local_read = anyio.create_memory_object_stream[SessionMessage | Exception](float('inf'))
        local_write, local_output = anyio.create_memory_object_stream[SessionMessage](0)
        pending: dict[Any, SessionMessage] = {}
        retry: dict[Any, SessionMessage] = {}
        errors: dict[Any, SessionMessage] = {}
        held: list[SessionMessage | Exception] = []
        stale: set[Any] = set()  # the tool calls a code change hands over, which the old server serves if it fails

        async def pump(source: Any, origin: str) -> None:
            async for message in source:
                await send.send((origin, message))
            await send.send((origin, None))

        async def pump_child(source: Any, origin: str) -> None:
            # a successor replaced in place ends its stream; the loop below tells that end from the session's
            try:
                async for message in source:
                    await send.send((origin, message))
            except (anyio.ClosedResourceError, anyio.BrokenResourceError, anyio.EndOfStream):
                pass
            await send.send((origin, None))

        async def forward(message: SessionMessage | Exception) -> None:
            if isinstance(message, SessionMessage) and isinstance(message.message, types.JSONRPCRequest):
                # Cancellation settles without a wire reply. Wait for the SDK's settlement hook so cleanup and
                # synchronous work have finished before replacement, rather than guessing from the cancel notice.
                metadata = message.metadata if isinstance(message.metadata, ServerMessageMetadata) \
                    else ServerMessageMetadata()
                previous = metadata.on_request_unanswered

                async def settled() -> None:
                    if previous is not None:
                        await previous()
                    await send.send(('settled', message))

                await local_send.send(SessionMessage(message.message, replace(
                    metadata, on_request_unanswered=settled)))
            else:
                await local_send.send(message)

        async def start_child(requests: dict[Any, SessionMessage], *,
                              task_status: TaskStatus[tuple[anyio.CancelScope, tuple[Read, Write, SessionMessage | None]]] =
                              anyio.TASK_STATUS_IGNORED) -> None:
            with anyio.CancelScope() as scope:  # cancelled when a newer successor replaces this one
                async with self.successor(requests) as streams:
                    task_status.started((scope, streams))
                    await anyio.sleep_forever()

        async with (send, receive, local_send, local_read, local_write, local_output,
                    anyio.create_task_group() as group):
            group.start_soon(pump, read, 'host')
            child: tuple[anyio.CancelScope, tuple[Read, Write, SessionMessage | None]] | None = None
            async with anyio.create_task_group() as local:
                local.start_soon(serve, local_read, local_write)
                local.start_soon(pump, local_output, 'server')
                async for origin, message in receive:
                    if message is None:
                        group.cancel_scope.cancel()
                        local.cancel_scope.cancel()
                        return
                    if origin == 'settled' and isinstance(message, SessionMessage):
                        if isinstance(message.message, types.JSONRPCRequest) \
                                and pending.get(message.message.id) is message:
                            pending.pop(message.message.id, None)
                    elif origin == 'host':
                        if isinstance(message, SessionMessage):
                            rpc = message.message
                            if isinstance(rpc, types.JSONRPCRequest):
                                if self.opening is None:
                                    self.opening = message
                                if retry:
                                    held.append(message)
                                    continue
                                pending[rpc.id] = message
                                if self.stale(rpc, pending):  # the code changed on disk: a new server serves it
                                    retry[rpc.id] = message
                                    stale.add(rpc.id)
                                    close_subscriptions()
                            elif isinstance(rpc, types.JSONRPCNotification):
                                if rpc.method == 'notifications/initialized':
                                    self.initialized = message
                                if rpc.method == 'notifications/cancelled':
                                    request_id = (rpc.params or {}).get('requestId')
                                    if isinstance(request_id, (str, int)) and not isinstance(request_id, bool):
                                        if request_id in retry:
                                            retry.pop(request_id, None)
                                            errors.pop(request_id, None)
                                            pending.pop(request_id, None)
                                        held[:] = [waiting for waiting in held if not (
                                            isinstance(waiting, SessionMessage)
                                            and isinstance(waiting.message, types.JSONRPCRequest)
                                            and waiting.message.id == request_id)]
                                if retry:
                                    held.append(message)
                        # Responses and cancellation still reach old handlers while they drain.
                        if not (isinstance(message, SessionMessage) and isinstance(message.message,
                                types.JSONRPCRequest) and message.message.id in stale):
                            await forward(message)
                    elif isinstance(message, SessionMessage):
                        rpc = message.message
                        if isinstance(rpc, types.JSONRPCError) and rpc.error.code == RETRY \
                                and rpc.error.data == self.token:
                            if rpc.id not in pending:
                                continue
                            retry[rpc.id] = pending[rpc.id]
                            request = pending[rpc.id].message
                            if isinstance(request, types.JSONRPCRequest) and request.method == 'tools/call':
                                errors[rpc.id] = SessionMessage(types.JSONRPCResponse(
                                    jsonrpc='2.0', id=request.id, result={'isError': True, 'content': [
                                        {'type': 'text', 'text': rpc.error.message}]}))
                            else:
                                errors[rpc.id] = SessionMessage(rpc.model_copy(update={'error': types.ErrorData(
                                    code=-32603, message=rpc.error.message)}))
                            close_subscriptions()
                        else:
                            if isinstance(rpc, (types.JSONRPCResponse, types.JSONRPCError)):
                                pending.pop(rpc.id, None)
                            await write.send(message)
                    if retry and pending.keys() == retry.keys():
                        prints = Fingerprint()  # the code the successor imports
                        try:
                            child = await group.start(start_child, retry)
                        except Exception as error:  # noqa: BLE001  SDK child startup wraps failures in ExceptionGroup
                            print(f'MCP hand-over failed: {error}', file=sys.stderr, flush=True)
                            # Keep the old session usable, and do not retry this same code again.
                            self.code, self.prints = code_print(), prints
                            for request_id, refusal in errors.items():
                                await write.send(refusal)
                                pending.pop(request_id, None)
                            for request_id in stale:  # the old server can serve what only a code change handed over
                                await forward(retry[request_id])
                            retry.clear()
                            errors.clear()
                            stale.clear()
                            for waiting in held:
                                if isinstance(waiting, SessionMessage) and isinstance(
                                        waiting.message, types.JSONRPCRequest):
                                    pending[waiting.message.id] = waiting
                                await forward(waiting)
                            held.clear()
                            continue
                        self.prints = prints
                        local.cancel_scope.cancel()
                        break
                    if not retry and held:
                        for waiting in held:
                            if isinstance(waiting, SessionMessage) and isinstance(
                                    waiting.message, types.JSONRPCRequest):
                                pending[waiting.message.id] = waiting
                            await forward(waiting)
                        held.clear()
            if child is not None:
                scope, (child_read, child_write, opening_reply) = child
                serving = 1  # which successor serves the connection; an earlier one's messages are its last
                group.start_soon(pump_child, child_read, f'child:{serving}')
                outstanding: dict[Any, SessionMessage] = {}  # the host's requests the successor has not answered
                if opening_reply is not None:
                    if isinstance(opening_reply.message, types.JSONRPCResponse):
                        retry.pop(opening_reply.message.id, None)
                    await write.send(opening_reply)
                for waiting in [*retry.values(), *held]:
                    if isinstance(waiting, SessionMessage):
                        if isinstance(waiting.message, types.JSONRPCRequest):
                            outstanding[waiting.message.id] = waiting
                        await child_write.send(waiting)
                async for origin, message in receive:
                    if message is None:
                        if origin.startswith('child:') and origin != f'child:{serving}':
                            continue  # a replaced successor ended
                        group.cancel_scope.cancel()
                        break
                    if isinstance(message, Exception):
                        print(f'MCP relay: {message}', file=sys.stderr, flush=True)
                        continue
                    if origin == 'settled':  # the old server's settlement hook; the host is never sent the request
                        continue
                    if origin == 'host':
                        rpc = message.message
                        if isinstance(rpc, types.JSONRPCRequest):
                            outstanding[rpc.id] = message
                            if self.stale(rpc, outstanding):
                                replaced = await self.replace(group, start_child, message, outstanding,
                                                              child_write, write)
                                if replaced is not None:
                                    scope.cancel()
                                    scope, (child_read, child_write, _) = replaced
                                    serving += 1
                                    group.start_soon(pump_child, child_read, f'child:{serving}')
                        elif isinstance(rpc, types.JSONRPCNotification) and rpc.method == 'notifications/cancelled':
                            outstanding.pop((rpc.params or {}).get('requestId'), None)
                        await child_write.send(message)
                    elif origin == f'child:{serving}':
                        if isinstance(message.message, (types.JSONRPCResponse, types.JSONRPCError)):
                            outstanding.pop(message.message.id, None)
                        await write.send(message)
                    # a replaced successor answered nothing still asked of it: it had no call in flight

    async def replace(self, group: Any, start_child: Any, message: SessionMessage,
                      outstanding: dict[Any, SessionMessage], old: Write, host: Write) -> Any:
        """Start a successor on the code now on disk for one tool call, in place of the one serving the connection,
        which has no call in flight but open listen streams: each is ended to the host as the server ends one, so the
        host listens again, and cancelled on the old successor. None when the new one does not start, after which
        the old one serves this code until the code changes again."""
        prints = Fingerprint()
        try:
            started = await group.start(start_child, {message.message.id: message})  # type: ignore[union-attr]
        except Exception as error:  # noqa: BLE001  SDK child startup wraps failures in ExceptionGroup
            print(f'MCP hand-over failed: {error}', file=sys.stderr, flush=True)
            self.prints = prints
            return None
        self.prints = prints
        for request_id, request in list(outstanding.items()):
            if isinstance(request.message, types.JSONRPCRequest) and request.message.method == LISTEN:
                await old.send(SessionMessage(types.JSONRPCNotification(
                    jsonrpc='2.0', method='notifications/cancelled', params={'requestId': request_id})))
                await host.send(SessionMessage(types.JSONRPCResponse(
                    jsonrpc='2.0', id=request_id, result={'_meta': {SUBSCRIPTION_ID_META_KEY: request_id}})))
                outstanding.pop(request_id, None)
        return started
