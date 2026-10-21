"""The Roundtable 2 engine as the bridge reaches it: its MCP server over stdio for opening and chairing a table, and its
web page's server-sent events for following one.

The engine is the Roundtable 2 engine (https://github.com/RchGrav/roundtable), shipped inside this module as the
package `roundtable` and run as `python -m` of it with Metaform's own interpreter, so it is there on every install and
nothing is looked up on PATH. Each call to it starts its `serve` over stdio, calls one tool and ends; a table's runner
is detached by the engine, so a table outlives the call that opened it. The chair token `open` returns is kept
with the table in the project, and every chair tool is passed it.

A follower reads the table live from a web page server of its own, the engine's `web` on a free loopback port with a
token only it holds. The page's `events` stream says when anything of the table moves; the follower then reads only
what moved. The engine's page server looks at its own store for those events about once a second: that is the engine's
own loop, in its own process, and nothing in Metaform waits on a clock for a change.

Each process the bridge starts for the engine is given the person's environment without the identity of a Metaform
agent session, so no seat is mistaken for one, and with dispatch's own commands for claude, codex and antigravity as the
engine's ACP agents, unless the person set `ROUNDTABLE_AGENT_<NAME>` themselves.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import httpx

from metaform import home, settings
from metaform.module import Stop

ENGINE = 'metaform.modules.roundtables.roundtable'  # the shipped engine's package, by the name every process imports
AGENTS = ('claude', 'codex', 'antigravity')  # Metaform's own agents, seated through the engine's ACP client
IDENTITY = ('METAFORM_ROLE', 'METAFORM_SESSION', 'METAFORM_WORK', 'METAFORM_NODE', 'METAFORM_AUTHORED_ROLE',
            'METAFORM_LEASE')
CALL_LIMIT = 180.0  # seconds one engine call has, its process start included: a deadline on one request
START_LIMIT = 60.0  # seconds the follower's page server has to answer its first request
SILENCE = 60.0  # seconds of nothing on the events stream, whose server says it is there every 15, before reconnecting


def folder_log() -> Path:
    found = home.home() / 'run' / 'roundtables'
    home.mkdir_private(found)
    return found


def command() -> list[str]:
    """The shipped engine's command: this interpreter running its package."""
    return [sys.executable, '-m', ENGINE]


def environment(folder: Path) -> dict[str, str]:
    """The person's environment for the engine: no Metaform agent identity, and dispatch's agent commands."""
    env = {key: value for key, value in os.environ.items() if key not in IDENTITY}
    for agent in AGENTS:
        key = f'ROUNDTABLE_AGENT_{agent.upper()}'
        if key in env:
            continue
        try:
            value = str(settings.value(f'dispatch_{agent}', folder) or '').strip()
        except Exception:  # noqa: BLE001  dispatch disabled: the engine starts its own default for the agent
            value = ''
        if value:
            env[key] = value
    return env


def call(where: Path, tool: str, /, **arguments: Any) -> dict[str, Any]:
    """One engine tool's answer, the engine started in the folder `where`; its refusal raised as a Stop with the
    engine's own words."""
    return asyncio.run(asyncio.wait_for(_call(where, tool, {key: value for key, value in arguments.items()
                                                               if value is not None}), CALL_LIMIT))


async def _call(folder: Path, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    parts = command()
    params = StdioServerParameters(command=parts[0], args=[*parts[1:], 'serve'], env=environment(folder), cwd=folder)
    descriptor = os.open(folder_log() / 'engine.log', os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as errlog:
        async with stdio_client(params, errlog=errlog) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            result: Any = await session.call_tool(tool, arguments)
    content = cast(list[Any], getattr(result, 'content', None) or [])
    text = ''.join(str(getattr(one, 'text', '')) for one in content)
    if getattr(result, 'is_error', False):
        raise Stop(f'The roundtable engine refused {tool}: {text}', 'metaform roundtables status table=<id>')
    found: Any = getattr(result, 'structured_content', None)
    if isinstance(found, dict):
        held = cast(dict[str, Any], found)
        return cast(dict[str, Any], held['result']) if set(held) == {'result'} else held
    try:
        parsed: Any = json.loads(text)
    except ValueError:
        return {'text': text}
    return cast(dict[str, Any], parsed) if isinstance(parsed, dict) else {'result': parsed}


def _free_port() -> int:
    with socket.socket() as held:
        held.bind(('127.0.0.1', 0))
        return int(held.getsockname()[1])


class Page:
    """The engine's page server, started for one follower and ended with it."""

    def __init__(self, folder: Path, log: Path) -> None:
        self.token = secrets.token_urlsafe(24)
        self.port = _free_port()
        self.base = f'http://127.0.0.1:{self.port}/{self.token}/api'
        parts = command()
        descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(descriptor, 'ab') as written:
            self.process = subprocess.Popen([*parts, 'web', '--port', str(self.port)], cwd=folder,
                                            env={**environment(folder), 'ROUNDTABLE_WEB_TOKEN': self.token},
                                            stdin=subprocess.DEVNULL, stdout=written, stderr=written,
                                            start_new_session=True)
        self.client = httpx.Client(timeout=httpx.Timeout(30.0, read=SILENCE))
        try:
            self._ready()
        except BaseException:  # its start failed or was stopped: the server it started goes with it
            self.close()
            raise

    def _ready(self) -> None:
        """The server answers, waited for by a retry with a growing wait after each refused connection, within its
        start's deadline."""
        deadline, pause = time.monotonic() + START_LIMIT, 0.1
        while True:
            try:
                self.client.get(f'{self.base}/limits').raise_for_status()
                return
            except httpx.TransportError:
                if self.process.poll() is not None or time.monotonic() > deadline:
                    raise Stop('The roundtable engine\'s page server did not start; its log is in the Metaform '
                               'home under run/roundtables.', 'metaform roundtables status table=<id>') from None
                time.sleep(pause)  # a retry backoff after a refused connection, never a look for a change
                pause = min(pause * 2, 2.0)

    def get(self, path: str, **params: Any) -> Any:
        answer = self.client.get(f'{self.base}{path}', params=params or None)
        if answer.status_code == 404 and path.endswith('/report'):
            return None
        answer.raise_for_status()
        return answer.text if path.endswith('/report') else answer.json()

    def chair(self, number: int, action: str) -> dict[str, Any]:
        """One of the chair's actions on table `number`, through this page server, whose token chairs any table: how
        a follower ends a table it holds no chair token for, one the engine opened before the opening failed."""
        answer = self.client.post(f'{self.base}/tables/{number}/{action}')
        answer.raise_for_status()
        return cast(dict[str, Any], answer.json())

    def changes(self, number: int) -> Iterator[dict[str, Any]]:
        """Each change of table `number` as the engine's events stream says it; the caller stops at the change that
        says the table ended, and the changes end when the engine says it no longer holds the table. A stream that drops or falls silent past SILENCE is opened again, and its first change
        says where the table is, so nothing in between is lost."""
        pause = 0.5
        while True:
            try:
                with self.client.stream('GET', f'{self.base}/tables/{number}/events') as stream:
                    stream.raise_for_status()
                    pause = 0.5
                    event, data = '', ''
                    for line in stream.iter_lines():
                        if line.startswith('event:'):
                            event = line.removeprefix('event:').strip()
                        elif line.startswith('data:'):
                            data += line.removeprefix('data:').strip()
                        elif not line and event:
                            if event == 'gone':
                                return
                            if event == 'change' and data:
                                found: Any = json.loads(data)
                                if isinstance(found, dict):
                                    yield cast(dict[str, Any], found)
                            event, data = '', ''
            except (httpx.TransportError, httpx.HTTPStatusError):
                if self.process.poll() is not None:
                    raise
            # the stream ended: with the table, and the caller stops at the change saying so; or the server dropped
            # it, and it is opened again after a retry backoff
            time.sleep(pause)
            pause = min(pause * 2, 10.0)

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self.client.close()
        if self.process.poll() is None:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(10)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.killpg(self.process.pid, signal.SIGKILL)
