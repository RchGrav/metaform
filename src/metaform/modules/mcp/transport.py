"""Keep the host's stdio connection while handing a refused call to newer code.

Only the pre-dispatch schema check emits our private retry marker. In-flight calls finish on the old
server before replacement, so a committed write is never replayed. SDK transports own pipe and child cleanup.
"""
from __future__ import annotations

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
from mcp.shared._stream_protocols import ReadStream, WriteStream
from mcp.shared.exceptions import MCPError
from mcp.shared.message import ServerMessageMetadata, SessionMessage

from metaform.data import NewerStore
from metaform.module import code_print

Read = ReadStream[SessionMessage | Exception]
Write = WriteStream[SessionMessage]
RETRY = -32098


class Relay:
    def __init__(self, folder: Path, enabled: bool) -> None:
        self.folder, self.enabled = folder, enabled
        self.code = code_print()
        self.token = uuid.uuid4().hex
        self.initialize: SessionMessage | None = None
        self.initialized: SessionMessage | None = None

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
                                           cwd=self.folder, env=dict(os.environ))
        async with stdio_client(parameters) as (read, write):
            opening = self.initialize
            if opening is None:
                # A July connection has no initialize. Discover proves that the new package actually started
                # before the old server is stopped, using the refused request's protocol/client envelope.
                request = next(iter(retry.values())).message
                params = request.params if isinstance(request, types.JSONRPCRequest) else None
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
            if self.initialize is not None and self.initialized is not None:
                await write.send(self.initialized)
            # If initialization itself was refused, its verified replacement answer belongs to the host.
            returned = reply if self.initialize is not None and reply.message.id in retry else None
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

        async def pump(source: Any, origin: str) -> None:
            async for message in source:
                await send.send((origin, message))
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
                              task_status: TaskStatus[tuple[Read, Write, SessionMessage | None]] =
                              anyio.TASK_STATUS_IGNORED) -> None:
            async with self.successor(requests) as streams:
                task_status.started(streams)
                await anyio.sleep_forever()

        async with (send, receive, local_send, local_read, local_write, local_output,
                    anyio.create_task_group() as group):
            group.start_soon(pump, read, 'host')
            child: tuple[Read, Write, SessionMessage | None] | None = None
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
                                if rpc.method == 'initialize':
                                    self.initialize = message
                                if retry:
                                    held.append(message)
                                    continue
                                pending[rpc.id] = message
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
                        try:
                            child = await group.start(start_child, retry)
                        except Exception as error:  # noqa: BLE001  SDK child startup wraps failures in ExceptionGroup
                            print(f'MCP hand-over failed: {error}', file=sys.stderr, flush=True)
                            # Keep the old session usable, and do not retry this same code again.
                            self.code = code_print()
                            for request_id, refusal in errors.items():
                                await write.send(refusal)
                                pending.pop(request_id, None)
                            retry.clear()
                            errors.clear()
                            for waiting in held:
                                if isinstance(waiting, SessionMessage) and isinstance(
                                        waiting.message, types.JSONRPCRequest):
                                    pending[waiting.message.id] = waiting
                                await forward(waiting)
                            held.clear()
                            continue
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
                child_read, child_write, opening_reply = child
                group.start_soon(pump, child_read, 'child')
                if opening_reply is not None:
                    if isinstance(opening_reply.message, types.JSONRPCResponse):
                        retry.pop(opening_reply.message.id, None)
                    await write.send(opening_reply)
                for waiting in [*retry.values(), *held]:
                    if isinstance(waiting, SessionMessage):
                        await child_write.send(waiting)
                async for origin, message in receive:
                    if message is None:
                        group.cancel_scope.cancel()
                        break
                    if isinstance(message, Exception):
                        print(f'MCP relay: {message}', file=sys.stderr, flush=True)
                        continue
                    if origin == 'settled':  # the old server's settlement hook; the host is never sent the request
                        continue
                    await (child_write if origin == 'host' else write).send(message)
