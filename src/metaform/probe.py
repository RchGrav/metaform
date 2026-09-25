"""A small standard-library MCP client that proves a registered command starts a server, MCP-017.

It starts the command, writes newline-delimited JSON-RPC 2.0: `initialize`,
the `notifications/initialized` notification, then `tools/list`, and reads
standard output line by line. Every line must be one JSON object. Standard
error is kept only to show in a failure. The whole exchange has a time limit.
"""
from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROTOCOL = '2025-06-18'
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
        self.process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True, encoding='utf-8', bufsize=1)
        self.lines: queue.Queue[str | None] = queue.Queue()
        self.errors: list[str] = []
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

    def request(self, method: str, params: dict[str, Any] | None = None, *, deadline: float) -> dict[str, Any]:
        self.next_id += 1
        ident = self.next_id
        self._send({'id': ident, 'method': method, **({'params': params} if params is not None else {})})
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
            message = json.loads(line)
            if not isinstance(message, dict):
                raise ValueError('a line of standard output is not a JSON object')
            if 'method' in message and 'id' in message:
                self._send({'id': message['id'], 'error': {'code': -32601, 'message': 'not supported'}})
                continue
            if message.get('id') == ident:
                if 'error' in message:
                    raise RuntimeError(f'{method} failed: {message["error"]}')
                return dict(message.get('result') or {})

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


def initialize(session: Session, limit: float = LIMIT) -> dict[str, Any]:
    """Initialize a started server. Returns the initialize result."""
    result = session.request('initialize', {'protocolVersion': PROTOCOL, 'capabilities': {},
                                            'clientInfo': {'name': 'metaform-install', 'version': '1'}},
                             deadline=time.monotonic() + limit)
    session.notify('notifications/initialized')
    return result


def open_session(command: list[str], *, cwd: Path, env: dict[str, str] | None = None,
                 limit: float = LIMIT) -> tuple[Session, dict[str, Any]]:
    """Start a server and initialize it. Returns the session and the initialize result; on failure the server stops."""
    session = Session(command, cwd=cwd, env=env)
    try:
        return session, initialize(session, limit)
    except BaseException:
        session.close()
        raise


def probe(command: list[str], *, cwd: Path, env: dict[str, str] | None = None, limit: float = LIMIT) -> Proof:
    """Pass when the command answers initialize and tools/list with at least one tool. The server always stops."""
    try:
        session = Session(command, cwd=cwd, env=env)
    except OSError as error:
        return Proof(False, reason=str(error))
    try:
        initialized = initialize(session, limit)
        listed = session.request('tools/list', {}, deadline=time.monotonic() + limit)
        tools = listed.get('tools') or []
        if not tools:
            return Proof(False, reason='the server lists no tools')
        return Proof(True, len(tools), instructions=str(initialized.get('instructions') or ''))
    except (OSError, ValueError, RuntimeError, TimeoutError, EOFError) as error:
        session.close()
        detail = ''.join(session.errors[-3:]).strip()
        return Proof(False, reason=f'{error}' + (f' ({detail})' if detail else ''))
    finally:
        session.close()
