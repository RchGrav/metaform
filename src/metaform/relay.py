"""Map changes reach a module's own long-running process in another process, through the base, BASE-053.

The event bus delivers in the process that publishes, BASE-010. A process that runs on, such as the web GUI's server
or a dispatch runner, hears `map.changed` published in every other process of the same home with `ctx.listen(handler)`,
or `listen(module, handler)` where it has no Context. Its listener is a port on the loopback address, recorded with a
token of its own under the home's `run/listeners`, readable only by the user. The bus hands each `map.changed` it
publishes to every recorded listener of another process. The listener answers at once and then calls the handler in
its own thread, one payload at a time. Nothing polls: the thread waits for a connection with no timeout, QUAL-015.
"""
from __future__ import annotations

import contextlib
import json
import os
import secrets
import socket
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Self, cast

from . import home

TOPIC = 'map.changed'
LIMIT = 2.0  # the one wait for a listener to answer, and for a connection to send its line


def folder() -> Path:
    return home.home() / 'run' / 'listeners'


class Listener:
    """One process's listener for map changes made in other processes; `close` ends it and removes its record."""

    def __init__(self, module: str, handler: Callable[[dict[str, Any]], Any]) -> None:
        self.module, self.handler = module, handler
        self.token = secrets.token_hex(16)
        self.closed = False
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(('127.0.0.1', 0))
        self.socket.listen()
        self.port = int(self.socket.getsockname()[1])
        self.path = folder() / f'{module}-{os.getpid()}-{self.token[:8]}.json'
        home.mkdir_private(self.path.parent)
        written = self.path.with_suffix('.tmp')
        descriptor = os.open(written, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            json.dump({'module': module, 'pid': os.getpid(), 'port': self.port, 'token': self.token}, handle)
        os.replace(written, self.path)
        self.thread = threading.Thread(target=self.serve, name=f'metaform-listener-{module}', daemon=True)
        self.thread.start()

    def serve(self) -> None:
        while True:
            try:
                connection, _ = self.socket.accept()  # no timeout: wakes only for a connection, QUAL-015
            except OSError:
                return
            if self.closed:
                connection.close()
                return
            payload = self.take(connection)
            if payload is None:
                continue
            try:
                self.handler(payload)
            except Exception as error:  # noqa: BLE001  a handler's failure never ends the listener
                sys.stderr.write(f'{self.module} listener: {type(error).__name__}: {error}\n')

    def take(self, connection: socket.socket) -> dict[str, Any] | None:
        """The payload of one delivery, answered at once; None when it is not one for this listener."""
        with connection:
            connection.settimeout(LIMIT)  # one bounded wait for the one line a delivery sends
            try:
                with connection.makefile('rb') as lines:
                    line = lines.readline()
                found: Any = json.loads(line) if line else None
                given = cast(dict[str, Any], found) if isinstance(found, dict) else {}
                if given.get('token') != self.token or given.get('topic') != TOPIC \
                        or not isinstance(given.get('payload'), dict):
                    connection.sendall(b'{"ok": false}\n')
                    return None
                connection.sendall(b'{"ok": true}\n')
            except (OSError, ValueError):
                return None
        return cast(dict[str, Any], given['payload'])

    def close(self) -> None:
        """End the listener once and remove its record. One connection wakes its thread, since closing a socket does
        not wake a thread waiting on it on every system."""
        if self.closed:
            return
        self.closed = True
        self.path.unlink(missing_ok=True)
        with contextlib.suppress(OSError), socket.create_connection(('127.0.0.1', self.port), timeout=LIMIT):
            pass
        self.thread.join(LIMIT)
        self.socket.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def listen(module: str, handler: Callable[[dict[str, Any]], Any]) -> Listener:
    """Hear each `map.changed` published in another process of this home; the handler runs in the listener's thread."""
    return Listener(module, handler)


def deliver(topic: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Hand `map.changed` to every recorded listener of another process, one delivery entry each, BASE-032. A listener
    whose port refuses has ended without closing, and its record is removed."""
    if topic != TOPIC:
        return []
    try:
        paths = sorted(folder().glob('*.json'))
    except OSError:
        return []
    deliveries: list[dict[str, Any]] = []
    for path in paths:
        try:
            found: Any = json.loads(path.read_text(encoding='utf-8'))
            record = cast(dict[str, Any], found) if isinstance(found, dict) else {}
            module, pid, port = str(record['module']), int(record['pid']), int(record['port'])
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if pid == os.getpid():
            continue
        line = json.dumps({'token': record.get('token'), 'topic': topic, 'payload': payload}).encode('utf-8') + b'\n'
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=LIMIT) as connection:
                connection.sendall(line)
                with connection.makefile('rb') as answers:
                    answer: Any = json.loads(answers.readline() or b'null')
            if isinstance(answer, dict) and cast(dict[str, Any], answer).get('ok') is True:
                deliveries.append({'module': module, 'pid': pid, 'status': 'completed'})
            else:
                deliveries.append({'module': module, 'pid': pid, 'status': 'failed',
                                   'error': 'The listener did not take the delivery.'})
        except ConnectionRefusedError as error:
            path.unlink(missing_ok=True)
            deliveries.append({'module': module, 'pid': pid, 'status': 'failed',
                               'error': f'{type(error).__name__}: {error}'})
        except (OSError, ValueError) as error:
            deliveries.append({'module': module, 'pid': pid, 'status': 'failed',
                               'error': f'{type(error).__name__}: {error}'})
    return deliveries
