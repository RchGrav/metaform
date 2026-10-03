"""A small standard-library MCP client that proves a registered command starts a server, MCP-017.

It speaks MCP 2026-07-28: there is no handshake, and every request carries the
per-request `_meta`, the protocol version, the client's capabilities and its
info. It starts the command, writes newline-delimited JSON-RPC 2.0:
`server/discover`, then `tools/list`, and reads standard output line by line.
Every line must be one JSON object; a notification is kept in `notices`.
Standard error is kept only to show in a failure. The whole exchange has a
time limit.
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

PROTOCOL = '2026-07-28'
CLIENT = {'name': 'metaform-install', 'version': '1'}
LIMIT = 30.0


@dataclass(frozen=True)
class Proof:
    ok: bool
    tools: int = 0
    reason: str = ''
    instructions: str = ''


class Session:
    """One scripted connection: requests go out as lines, responses come back matched by id."""

    def __init__(self, command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
        # The full path, so a launcher that is a .cmd file starts on Windows as it does elsewhere, QUAL-002.
        resolved = [shutil.which(command[0], path=(env or os.environ).get('PATH')) or command[0], *command[1:]]
        self.process = subprocess.Popen(resolved, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True, encoding='utf-8', bufsize=1)
        self.lines: queue.Queue[str | None] = queue.Queue()
        self.errors: list[str] = []
        self.notices: list[dict[str, Any]] = []
        self.next_id = 0
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.drainer = threading.Thread(target=self._drain, daemon=True)
        self.reader.start()
        self.drainer.start()

    def _read(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def _drain(self) -> None:
        assert self.process.stderr is not None
        for line in self.process.stderr:
            self.errors.append(line)

    def _send(self, message: dict[str, Any]) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps({'jsonrpc': '2.0', **message}) + '\n')
        self.process.stdin.flush()

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        self._send({'method': method, **({'params': params} if params is not None else {})})

    def open(self, method: str, params: dict[str, Any] | None = None) -> int:
        """Send a request with the per-request `_meta` and return its id without waiting for the answer, as for
        `subscriptions/listen`, whose answer is a stream."""
        self.next_id += 1
        given = dict(params or {})
        given['_meta'] = {**given.get('_meta', {}), 'io.modelcontextprotocol/protocolVersion': PROTOCOL,
                          'io.modelcontextprotocol/clientCapabilities': {},
                          'io.modelcontextprotocol/clientInfo': CLIENT}
        self._send({'id': self.next_id, 'method': method, 'params': given})
        return self.next_id

    def request(self, method: str, params: dict[str, Any] | None = None, *, deadline: float) -> dict[str, Any]:
        ident = self.open(method, params)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f'no answer to {method} in time')
            try:
                line = self.lines.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError(f'no answer to {method} in time') from None
            if line is None:
                raise EOFError(f'the server exited before answering {method}')
            decoded = json.loads(line)
            if not isinstance(decoded, dict):
                raise ValueError('a line of standard output is not a JSON object')
            message = cast(dict[str, Any], decoded)
            if 'method' in message and 'id' in message:
                self._send({'id': message['id'], 'error': {'code': -32601, 'message': 'not supported'}})
                continue
            if 'method' in message:
                self.notices.append(message)
                continue
            if message.get('id') == ident:
                if 'error' in message:
                    raise RuntimeError(f'{method} failed: {message["error"]}')
                return dict(cast(dict[str, Any], message.get('result') or {}))

    def call(self, name: str, arguments: dict[str, Any], *, limit: float = LIMIT) -> dict[str, Any]:
        """Call one tool; the result holds its content blocks and whether it is an error."""
        return self.request('tools/call', {'name': name, 'arguments': arguments}, deadline=time.monotonic() + limit)

    def close(self) -> None:
        """Close standard input and wait; a server that does not stop within a few seconds is killed."""
        if self.process.poll() is None:
            try:
                if self.process.stdin is not None:
                    self.process.stdin.close()
                self.process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                self.process.kill()
                self.process.wait()
        self.drainer.join(timeout=1)


def discover(session: Session, limit: float = LIMIT) -> dict[str, Any]:
    """Ask a started server what it supports, with `server/discover`. Returns its result."""
    return session.request('server/discover', {}, deadline=time.monotonic() + limit)


def open_session(command: list[str], *, cwd: Path, env: dict[str, str] | None = None,
                 limit: float = LIMIT) -> tuple[Session, dict[str, Any]]:
    """Start a server and discover it. Returns the session and the discover result; on failure the server stops."""
    session = Session(command, cwd=cwd, env=env)
    try:
        return session, discover(session, limit)
    except BaseException:
        session.close()
        raise


def probe(command: list[str], *, cwd: Path, env: dict[str, str] | None = None, limit: float = LIMIT) -> Proof:
    """Pass when the command answers server/discover supporting 2026-07-28, and tools/list completely with at least
    one tool. The server always stops."""
    try:
        session = Session(command, cwd=cwd, env=env)
    except OSError as error:
        return Proof(False, reason=str(error))
    try:
        found = discover(session, limit)
        if PROTOCOL not in cast(list[Any], found.get('supportedVersions') or []):
            return Proof(False, reason=f'the server does not support MCP {PROTOCOL}')
        listed = session.request('tools/list', {}, deadline=time.monotonic() + limit)
        if listed.get('resultType', 'complete') != 'complete':
            return Proof(False, reason=f'tools/list answered {listed.get("resultType")}, not complete')
        tools = cast(list[Any], listed.get('tools') or [])
        if not tools:
            return Proof(False, reason='the server lists no tools')
        return Proof(True, len(tools), instructions=str(found.get('instructions') or ''))
    except (OSError, ValueError, RuntimeError, TimeoutError, EOFError) as error:
        session.close()
        detail = ''.join(session.errors[-3:]).strip()
        return Proof(False, reason=f'{error}' + (f' ({detail})' if detail else ''))
    finally:
        session.close()
