"""proxy: the parts of ACP that `metaform dispatch serve` speaks beyond the plain stdio pipe, BASE-062.

Three layers, each taken up only when the other side shows it speaks it, so a peer that does not is served exactly as
before and is never told of a capability Metaform cannot honour:

- **Proxy Chains** (agentclientprotocol.com/rfds/proxy-chains). A conductor starts Metaform as one component of its
  chain and initializes it with `proxy/initialize` instead of `initialize`; the reference conductor
  (crates.io agent-client-protocol-conductor 3.3, `schema/proxy_protocol.rs`) spells the methods `_proxy/initialize`
  and `_proxy/successor`, the RFD without the underscore, and both are taken. Metaform then starts no agent of its own:
  what it sends its successor goes to the conductor wrapped in `proxy/successor`, what the successor sends comes back
  wrapped the same way, and a wrapped request's response is the successor's response as it is. Request ids are
  hop-local, so each request crossing the conductor gets an id of Metaform's and is mapped back, and `$/cancel_request`
  is re-issued with the id of its own hop, never tunnelled (the conductor's `tests/request_cancellation.rs`).
- **MCP-over-ACP** (agentclientprotocol.com/rfds/mcp-over-acp; schema-v1.25.0 `MessageMcpRequest`). When the agent
  advertises it, `agentCapabilities.mcpCapabilities.acp` in ACP v1 or `capabilities.session.mcp.acp` in draft v2,
  Metaform declares its MCP server as `{"type": "acp", "serverId": ...}` and answers the agent's `mcp/message` requests
  itself, through its own MCP server run for the session: stateless MCP 2026-07-28, one inner request per outer
  request, request-scoped notifications back as `mcp/message` notifications. An agent that does not advertise it gets
  the stdio server as before. The installed Python SDK (agent-client-protocol 0.12.1, schema 1.19) still carries the
  earlier `mcp/connect` draft the RFD replaced; serve speaks raw JSON-RPC and follows the current schema.
- **ACP v2** (agentclientprotocol.com/rfds/v2/overview, schema-v2.0.0-alpha.8). What serve reads of a v2 peer, read
  by version: `capabilities` and `info` for v1's `agentCapabilities` and `agentInfo`, the session group, a prompt
  answered at insertion with its `messageId` and its turn ended by `state_update`, whole-message upserts keyed by
  `messageId`, `tool_call_update` upserts and diff file states. Metaform alone answers version 1, as ACP's
  negotiation lets an agent.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
from collections.abc import Callable
from typing import Any, cast

SUCCESSOR = ('proxy/successor', '_proxy/successor')  # the RFD's spelling, then the reference conductor's
INITIALIZE = ('proxy/initialize', '_proxy/initialize')
CHAIN = 'metaform:chain:'  # ids of requests crossing the conductor, apart from Metaform's own and the editor's
MCP_REVISION = '2026-07-28'  # the only MCP revision MCP-over-ACP carries
MCP_ACTIVE = 64  # inner MCP requests a session's server holds at once before -33000
MCP_LINE = 64 * 1024 * 1024
NOT_FOUND = object()


# ------------------------------------------------------------------ ACP v1 and draft v2, read by version

def version_of(result: dict[str, Any]) -> int:
    """The protocol version an initialize answer negotiated; 1 when it names none."""
    found = result.get('protocolVersion')
    return found if isinstance(found, int) and found > 0 else 1


def _group(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def agent_capabilities(result: dict[str, Any]) -> dict[str, Any]:
    """The agent's capabilities: v2's `capabilities`, v1's `agentCapabilities`."""
    return _group(result.get('capabilities' if version_of(result) >= 2 else 'agentCapabilities'))


def client_capabilities(params: dict[str, Any]) -> dict[str, Any]:
    """The editor's capabilities from initialize: v2's `capabilities`, v1's `clientCapabilities`."""
    return _group(params.get('capabilities') if version_of(params) >= 2 else params.get('clientCapabilities'))


def agent_info(result: dict[str, Any]) -> dict[str, Any] | None:
    found = result.get('info' if version_of(result) >= 2 else 'agentInfo')
    return cast(dict[str, Any], found) if isinstance(found, dict) else None


def session_group(capabilities: dict[str, Any], version: int) -> dict[str, Any]:
    """The session capability group: v2's `session`, v1's `sessionCapabilities`."""
    return _group(capabilities.get('session' if version >= 2 else 'sessionCapabilities'))


def offered(group: dict[str, Any], name: str) -> bool:
    """A support marker: `{}` offers it, omission, null or false do not (v2 markers are objects, v1 some booleans)."""
    return group.get(name) not in (None, False)


def lists_sessions(capabilities: dict[str, Any], version: int) -> bool:
    """Whether the agent answers session/list: v1 when it advertises `list`; v2 whenever it has sessions at all, since
    `session/list` is baseline there (rfds/v2/required-session-methods)."""
    if version >= 2:
        return capabilities.get('session') is not None
    return offered(session_group(capabilities, version), 'list')


def takes_up(capabilities: dict[str, Any], version: int) -> bool:
    """Whether the agent can open a listed session again: v1's `loadSession` or `resume`; v2's baseline resume."""
    if version >= 2:
        return capabilities.get('session') is not None
    return bool(capabilities.get('loadSession')) or offered(session_group(capabilities, version), 'resume')


def advertise_list(result: dict[str, Any]) -> None:
    """Add `list` to an agent's session capabilities in v1, so Metaform's sessions can be listed beside its own; v2
    has it whenever it has sessions."""
    if version_of(result) >= 2:
        return
    capabilities = agent_capabilities(result)
    group = session_group(capabilities, 1)
    group.setdefault('list', {})
    capabilities['sessionCapabilities'] = group
    result['agentCapabilities'] = capabilities


def mcp_over_acp(capabilities: dict[str, Any], version: int) -> bool:
    """Whether the agent takes MCP servers of `type: "acp"`: v1 `mcpCapabilities.acp: true`, v2
    `session.mcp.acp: {}`."""
    if version >= 2:
        return offered(_group(session_group(capabilities, version).get('mcp')), 'acp')
    return _group(capabilities.get('mcpCapabilities')).get('acp') is True


def notices(client: dict[str, Any]) -> bool:
    """Whether the editor takes Session Notices, `session.notices`, in either version."""
    return _group(client.get('session')).get('notices') is not None


# ------------------------------------------------------------------ what a v2 session update says, for the record

MESSAGES = {'user_message': 'user_message_chunk', 'agent_message': 'agent_message_chunk',
            'agent_thought': 'agent_thought_chunk'}  # v2 whole-message upserts, by the chunk kind they replace


def text_of(content: Any) -> str:
    """The text of one content block, or of a list of them."""
    if isinstance(content, list):
        return ''.join(text_of(one) for one in cast(list[Any], content))
    return str(cast(dict[str, Any], content).get('text', '')) if isinstance(content, dict) else ''


def file_changes(content: Any) -> list[str]:
    """The files a tool call's content changes, one `operation path` each: v2's diff file states
    (rfds/v2/diff-file-states, `changes` of add, delete, modify, move and copy) and v1's `diff` with `path` and
    `oldText`, an add when there is no old text."""
    found: list[str] = []
    for block in cast(list[Any], content) if isinstance(content, list) else []:
        if not isinstance(block, dict) or cast(dict[str, Any], block).get('type') != 'diff':
            continue
        block = cast(dict[str, Any], block)
        changes = block.get('changes')
        if isinstance(changes, list):
            for change in cast(list[Any], changes):
                if isinstance(change, dict):
                    change = cast(dict[str, Any], change)
                    moved = f'{change["oldPath"]} -> ' if change.get('oldPath') else ''
                    found.append(f'{change.get("operation", "modify")} {moved}{change.get("path", "")}')
        elif block.get('path'):
            found.append(f'{"modify" if block.get("oldText") is not None else "add"} {block["path"]}')
    return found


def plan_lines(update: dict[str, Any]) -> list[str]:
    """A plan's entries as lines, each `content (status)`: v1's `plan` and v2's `plan_update` of `type: "items"`
    (rfds/v2/plan-variants), whose entries sit in its `plan` object."""
    entries = update.get('entries')
    if not isinstance(entries, list):
        entries = _group(update.get('plan')).get('entries')
    if not isinstance(entries, list):
        entries = []
    lines: list[str] = []
    for entry in cast(list[Any], entries):
        if isinstance(entry, dict):
            entry = cast(dict[str, Any], entry)
            lines.append(f'{entry.get("content") or entry.get("title") or ""} ({entry.get("status", "pending")})')
    return lines


# ------------------------------------------------------------------ Proxy Chains

class Chain:
    """Metaform as a proxy in a conductor's chain: one channel to the conductor carries the editor's side as it is and
    the successor's side wrapped in `proxy/successor`. `send` writes one message to the conductor."""

    def __init__(self, initialized_with: str, send: Callable[[dict[str, Any]], None]) -> None:
        self.method = SUCCESSOR[1] if initialized_with.startswith('_') else SUCCESSOR[0]
        self.send = send
        self.count = 0
        self.sent: dict[str, Any] = {}  # Metaform's id of each request it passed on to the successor: the id it had
        self.taken: dict[str, Any] = {}  # Metaform's id of each request of the successor's: the conductor's id for it

    def fresh(self) -> str:
        self.count += 1
        return f'{CHAIN}{self.count}'

    def to_successor(self, message: dict[str, Any]) -> None:
        """A message for the agent: a request or notification wrapped, a response to one of the successor's requests
        answered to the conductor's request that carried it, and a cancellation re-issued on this hop."""
        method = message.get('method')
        if not isinstance(method, str):
            original = self.taken.pop(json.dumps(message.get('id')), NOT_FOUND)
            if original is not NOT_FOUND:
                self.send({**message, 'id': original})
            return
        if method == '$/cancel_request':
            params = _group(message.get('params'))
            wanted = params.get('requestId')
            ours = next((key for key, value in self.sent.items() if value == wanted), None)
            if ours is not None:
                self.send({'method': method, 'params': {**params, 'requestId': json.loads(ours)}})
            return
        wrapped: dict[str, Any] = {'method': self.method, 'params': {
            'method': method, **({'params': message['params']} if 'params' in message else {})}}
        if 'id' in message:
            ours = self.fresh()
            self.sent[json.dumps(ours)] = message['id']
            wrapped['id'] = ours
        self.send(wrapped)

    def sort(self, message: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        """Whether a message from the conductor is the successor's, and the message as Metaform handles it."""
        method = message.get('method')
        if method in SUCCESSOR:
            params = _group(message.get('params'))
            inner: dict[str, Any] = {'method': params.get('method')}
            if 'params' in params:
                inner['params'] = params['params']
            if 'id' in message:
                ours = self.fresh()
                self.taken[json.dumps(ours)] = message['id']
                inner['id'] = ours
            return True, inner
        if not isinstance(method, str):
            original = self.sent.pop(json.dumps(message.get('id')), NOT_FOUND)
            if original is not NOT_FOUND:
                return True, {**message, 'id': original}
            return False, message
        if method == '$/cancel_request':  # the successor withdrawing a request it sent through the conductor
            wanted = _group(message.get('params')).get('requestId')
            ours = next((key for key, value in self.taken.items() if value == wanted), None)
            if ours is not None:
                return True, {'method': method, 'params': {'requestId': json.loads(ours)}}
        return False, message


# ------------------------------------------------------------------ MCP-over-ACP

def binding_error(code: int, message: str) -> dict[str, Any]:
    """An outer ACP error of the binding (rfds/mcp-over-acp, Binding failures)."""
    return {'error': {'code': code, 'message': message}}


class McpProvider:
    """Metaform's MCP server for one session, offered to the agent over ACP under `server_id`: the server the stdio
    declaration would start, started on the first request and kept for the connection, its inner requests keyed by
    the caller's `requestId`. `notify` sends one `mcp/message` notification to the agent."""

    def __init__(self, server_id: str, command: list[str], cwd: str, env: dict[str, str],
                 notify: Callable[[dict[str, Any]], None]) -> None:
        self.server_id, self.command, self.cwd, self.env, self.notify = server_id, command, cwd, env, notify
        self.process: asyncio.subprocess.Process | None = None
        self.reader: asyncio.Task[None] | None = None
        self.starting: asyncio.Lock | None = None
        self.active: dict[str, asyncio.Future[dict[str, Any]]] = {}  # by requestId
        self.outer: dict[str, str] = {}  # the outer ACP id of each active request, json-encoded: its requestId
        self.tokens: dict[str, str] = {}  # each progress token in use: its requestId

    def declaration(self) -> dict[str, Any]:
        return {'type': 'acp', 'name': 'metaform', 'serverId': self.server_id}

    async def started(self) -> asyncio.subprocess.Process:
        if self.starting is None:
            self.starting = asyncio.Lock()
        async with self.starting:
            if self.process is None or self.process.returncode is not None:
                self.process = await asyncio.create_subprocess_exec(
                    *self.command, cwd=self.cwd, env=self.env, stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, limit=MCP_LINE)
                self.reader = asyncio.ensure_future(self.read(self.process))
            return self.process

    async def request(self, outer_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        """One `mcp/message` request: the outer answer, `{"result": {"result" | "error": ...}}`, or a binding error."""
        request_id, method, inner = params.get('requestId'), params.get('method'), params.get('params')
        if not isinstance(request_id, str) or not isinstance(method, str) or \
                (inner is not None and not isinstance(inner, dict)):
            return binding_error(-32602, 'mcp/message needs a string requestId and method, and params as an object.')
        if request_id in self.active:
            return binding_error(-32602, f'Request {request_id} is already active on server {self.server_id}.')
        if len(self.active) >= MCP_ACTIVE:
            return binding_error(-33000, f'Server {self.server_id} holds {MCP_ACTIVE} requests already.')
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self.active[request_id] = future
        key = json.dumps(outer_id)
        self.outer[key] = request_id
        token = _group(_group(inner).get('_meta')).get('progressToken')
        if isinstance(token, (str, int)):
            self.tokens[json.dumps(token)] = request_id
        try:
            try:
                process = await self.started()
                assert process.stdin is not None
                process.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': request_id, 'method': method,
                                                **({'params': inner} if inner is not None else {})},
                                               ensure_ascii=False).encode('utf-8') + b'\n')
                await process.stdin.drain()
            except (OSError, ValueError, RuntimeError) as error:
                return binding_error(-33002, f'Metaform\'s MCP server did not start: {error}')
            return await future
        finally:
            self.active.pop(request_id, None)
            self.outer.pop(key, None)
            for held in [one for one, value in self.tokens.items() if value == request_id]:
                self.tokens.pop(held, None)

    def cancel(self, outer_id: Any) -> bool:
        """`$/cancel_request` for an outer request this server holds: the server is told, and the request answers
        -32800. False when it holds no such request."""
        request_id = self.outer.get(json.dumps(outer_id))
        future = self.active.get(request_id) if request_id is not None else None
        if request_id is None or future is None:
            return False
        process = self.process
        if process is not None and process.stdin is not None and process.returncode is None:
            with contextlib.suppress(OSError, RuntimeError):
                process.stdin.write(json.dumps({'jsonrpc': '2.0', 'method': 'notifications/cancelled',
                                                'params': {'requestId': request_id}}).encode('utf-8') + b'\n')
        if not future.done():
            future.set_result(binding_error(-32800, 'Request cancelled'))
        return True

    def owner(self, params: dict[str, Any]) -> str | None:
        """The active request an MCP notification belongs to, or None, so it is never given to another."""
        meta = _group(params.get('_meta'))
        for key in ('io.modelcontextprotocol/subscriptionId', 'io.modelcontextprotocol/related-request'):
            if isinstance(meta.get(key), str) and meta[key] in self.active:
                return str(meta[key])
        token = params.get('progressToken')
        return self.tokens.get(json.dumps(token)) if isinstance(token, (str, int)) else None

    async def read(self, process: asyncio.subprocess.Process) -> None:
        assert process.stdout is not None
        try:
            while line := await process.stdout.readline():
                try:
                    found: Any = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(found, dict):
                    continue
                message = cast(dict[str, Any], found)
                method = message.get('method')
                if not isinstance(method, str):
                    future = self.active.get(str(message.get('id')))
                    if future is not None and not future.done():
                        error = message.get('error')
                        future.set_result({'result': {'error': error} if isinstance(error, dict) and
                                           'result' not in message else {'result': message.get('result')}})
                elif 'id' in message:  # 2026-07-28 has no server-originated requests: MRTR replaces them
                    if process.stdin is not None:
                        process.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': message['id'], 'error': {
                            'code': -32601, 'message': 'Method not found'}}).encode('utf-8') + b'\n')
                else:
                    params = _group(message.get('params'))
                    request_id = self.owner(params)
                    if request_id is not None:
                        self.notify({'method': 'mcp/message', 'params': {
                            'serverId': self.server_id, 'requestId': request_id, 'method': method,
                            **({'params': message['params']} if 'params' in message else {})}})
        finally:
            for future in self.active.values():
                if not future.done():
                    future.set_result(binding_error(-33002, 'Metaform\'s MCP server ended without an answer.'))

    async def close(self) -> None:
        process = self.process
        if process is None:
            return
        if process.stdin is not None:
            with contextlib.suppress(Exception):
                process.stdin.close()
        try:
            await asyncio.wait_for(process.wait(), 5)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
        if self.reader is not None:
            self.reader.cancel()
            with contextlib.suppress(BaseException):
                await self.reader


def provider_command(command: list[str]) -> list[str]:
    """The MCP server's command line as this interpreter runs it, as the stdio declaration gives it."""
    return [sys.executable, '-m', *command]


def provider_environment(extra: dict[str, str]) -> dict[str, str]:
    return {**os.environ, **extra}
