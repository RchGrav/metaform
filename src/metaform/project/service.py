"""The single-writer service: the one process that holds a home's project databases open.

The engine allows one process to hold a database, and one write transaction at a time. So one process, this
service, owns every project database of a home, and every other process sends it commands and receives answers.
`send` is that call. It starts the service when none is running, so a caller never opens a database itself and
two callers can never write at once: their commands meet in the service's write queue (`owner`).

The service listens on the loopback address. Its port and a key are written to `<home>/maps/service.json`, readable
by the home's user alone, and a caller proves it holds the key when it connects. The key keeps other users of the
machine out; it is not a permission between agents, which all run as the home's user.

Run as `python -m metaform.project.service <home>`. It serves until it is told to stop or is ended by a signal.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import subprocess
import sys
import threading
import uuid
from multiprocessing.connection import Client, Connection, Listener, answer_challenge, deliver_challenge
from pathlib import Path
from typing import Any, cast

from metaform import sqlite
from metaform.project import commands, owner
from metaform.project.forms import Refusal

_STOP = {'service': 'stop'}
HANDSHAKE_SECONDS = 10.0
ATTEMPTS = 4  # how many times one command is sent before the caller is told the service cannot be reached
_LOCAL = threading.local()  # each thread's own connection to each home's service


def _code() -> str:
    """The project package's code as it is on disk now: each file's modification time and size. A service records
    it when it starts, and a caller that finds another on disk replaces the service, so one never serves code that
    has since been changed."""
    found = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob('*.py')):
        try:
            state = path.stat()
        except OSError:
            continue
        found.update(f'{path.name}\0{state.st_mtime_ns}\0{state.st_size}\n'.encode())
    return found.hexdigest()


def _record(home: Path) -> Path:
    return home / 'maps' / 'service.json'


def serve(home: Path) -> int:
    """Own the home's databases and answer commands until told to stop. Prints one line when it is ready, `ready` or
    `owned` when another service already owns the home, and prints nothing after it."""
    code = _code()  # read before anything is imported further, so it names the code this process runs
    try:
        owned = owner.of(home)
    except owner.Owned:
        print('owned', flush=True)
        return 0
    owned.committed = _Announcer().changed
    key = secrets.token_bytes(32)
    stopped = threading.Event()
    # No key on the listener: its accept would then hold the handshake, and one slow caller would keep every other
    # caller from connecting. Each connection proves the key on its own thread instead.
    with Listener(('127.0.0.1', 0), backlog=512) as listener:
        record = _record(home)
        handle = os.open(record, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            json.dump({'port': cast(tuple[str, int], listener.address)[1], 'key': key.hex(), 'pid': os.getpid(),
                       'code': code}, stream)
        print('ready', flush=True)
        sys.stdout = open(os.devnull, 'w', encoding='utf-8')  # noqa: SIM115  the starter stops reading after `ready`

        def accepting() -> None:
            while not stopped.is_set():
                try:
                    connection = listener.accept()
                except Exception:  # noqa: BLE001, S112  the listener closing
                    continue
                threading.Thread(target=_answering, args=(connection, key, owned, stopped, listener),
                                 daemon=True).start()

        threading.Thread(target=accepting, daemon=True).start()
        stopped.wait()
    record.unlink(missing_ok=True)
    owner.close_all()
    return 0


class _Announcer:
    """Tells the home's other processes that a project's map changed, as `map.changed`, after each commit.

    The writer thread only names the project; a thread of this class's own does the telling, so a write never waits
    on a listener. Commits that land while a telling is in progress are told together, one event for each project."""

    def __init__(self) -> None:
        self._wake = threading.Condition()
        self._changed: dict[str, set[str]] = {}  # each project told of, with the kinds of what changed in it
        threading.Thread(target=self._run, name='announcer', daemon=True).start()

    def changed(self, project: str, kinds: set[str]) -> None:
        with self._wake:
            self._changed.setdefault(project, set()).update(kinds)
            self._wake.notify()

    def _run(self) -> None:
        from metaform import home as metaform_home
        from metaform import relay
        from metaform.project.commands import stored_name
        while True:
            with self._wake:
                while not self._changed:
                    self._wake.wait()
                names, self._changed = self._changed, {}
            try:
                registered = {stored_name(found.project_id): found.project_id for found in metaform_home.projects()}
                for name, kinds in names.items():
                    if name in registered:  # a page shows registered projects only
                        relay.deliver('map.changed', {'project': registered[name], 'base_id': None,
                                                      'tables': [f'project.{kind}' for kind in sorted(kinds)],
                                                      'kinds': sorted(kinds)})
            except Exception:  # noqa: BLE001, S110  a telling that fails loses one redraw, never a write
                pass


def _answering(connection: Connection, key: bytes, owned: owner.Owner, stopped: threading.Event,
               listener: Listener) -> None:
    """One caller's connection: it proves the key, then each message is one command, answered in turn."""
    with connection:
        try:
            deliver_challenge(connection, key)
            answer_challenge(connection, key)
        except Exception:  # noqa: BLE001  a caller without the key, or one that went away
            return
        while True:
            try:
                message: Any = json.loads(connection.recv_bytes())
            except (EOFError, OSError):
                return
            if message == _STOP:
                connection.send_bytes(b'{"status": "ok"}')
                stopped.set()
                listener.close()
                return
            try:
                if isinstance(message.get('specification'), dict):  # a specification document's export or import
                    asked = cast(dict[str, Any], message['specification'])
                    answer = commands.perform_specification(str(asked.get('project') or ''),
                                                            cast('str | None', asked.get('document')), owned,
                                                            str(message.get('caller') or ''),
                                                            asked.get('baseline') is not False)
                elif isinstance(message.get('cypher'), dict):  # a caller's Cypher query, read only
                    asked = cast(dict[str, Any], message['cypher'])
                    answer = commands.perform_cypher(str(asked.get('project') or ''), str(asked.get('query') or ''),
                                                     owned)
                elif isinstance(message.get('memory'), dict):  # a call of a memory tool, `memory`
                    from metaform.project import memory_layer
                    answer = memory_layer.perform(message['memory'], owned, str(message.get('caller') or ''))
                elif isinstance(message.get('bases'), dict):  # a base operation: list, add, activate, collapse, remove
                    from metaform.project import base_maps
                    answer = base_maps.perform(cast(dict[str, Any], message['bases']), owned)
                elif isinstance(message.get('clear'), str):  # clearing a project removes its database
                    answer: dict[str, object] = {'status': 'ok' if owned.remove(message['clear']) else 'error'}
                elif isinstance(message.get('drawn'), str) and isinstance(message.get('overlay'), str):
                    chosen = cast(dict[str, Any], message.get('select') or {})
                    match = cast('list[Any] | None', chosen.get('match'))
                    answer = commands.perform_records(message['drawn'], message['overlay'], owned,
                                                      cast('str | list[str] | None', chosen.get('at')),
                                                      bool(chosen.get('below')),
                                                      (str(match[0]), match[1]) if match else None)
                elif isinstance(message.get('drawn'), str):  # a display's read of a whole project
                    answer = commands.perform_drawn(message['drawn'], owned)
                else:
                    answer = commands.perform(message.get('command'), owned, str(message.get('caller') or ''),
                                              str(message.get('request') or ''))
            except Exception as error:  # noqa: BLE001  a fault in the service is answered, never left as a dropped caller
                answer = commands.refused(message.get('command'), Refusal(
                    'INTERNAL_ERROR', f'the service failed: {type(error).__name__}: {error}'))
            try:
                connection.send_bytes(json.dumps(answer).encode('utf-8'))
            except (EOFError, OSError):
                return  # the caller went away; a write it sent is stored, and its request id answers a resend


def _connect(home: Path) -> Connection | None:
    """A connection to the home's running service, or None when none is running."""
    try:
        found = json.loads(_record(home).read_text(encoding='utf-8'))
        key = bytes.fromhex(found['key'])
        connection = Client(('127.0.0.1', int(found['port'])))
    except Exception:  # noqa: BLE001  no record, a record left by a service that has ended, or a refused connection
        return None
    try:
        if not connection.poll(HANDSHAKE_SECONDS):  # a time limit on this one request, not a wait for a change
            raise TimeoutError
        answer_challenge(connection, key)
        deliver_challenge(connection, key)
    except Exception:  # noqa: BLE001  something else is listening on the recorded port
        connection.close()
        return None
    if found.get('code') != _code():  # the code on disk has changed: this service ends after its queued writes
        with connection:
            try:
                connection.send_bytes(json.dumps(_STOP).encode('utf-8'))
                connection.recv_bytes()
            except (OSError, EOFError):
                pass
        with sqlite.file_lock(home / 'maps' / 'owner.lock'):  # held by that service until its databases are closed
            pass
        return None
    return connection


def _start(home: Path) -> Connection:
    """Start the service unless another caller has, and connect to it. One caller starts at a time: the others wait
    on the lock, in the system's own wait, and then find the service running."""
    (home / 'maps').mkdir(parents=True, exist_ok=True)
    with sqlite.file_lock(home / 'maps' / 'start.lock'):
        connection = _connect(home)
        if connection is not None:
            return connection
        detached: dict[str, Any] = ({'creationflags': 0x00000008 | 0x00000200} if sys.platform == 'win32'
                                    else {'start_new_session': True})
        log = open(home / 'maps' / 'service.log', 'ab')  # noqa: SIM115  handed to the service as its error output
        with log:
            started = subprocess.Popen([sys.executable, '-m', 'metaform.project.service', str(home)],
                                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=log, **detached)
        assert started.stdout is not None
        said = started.stdout.readline().decode('utf-8', 'replace').strip()  # waits for the service's one line
        started.stdout.close()
        connection = _connect(home)
        if connection is None:
            raise owner.StoreError(f'the project service of {home} did not start ({said or "it said nothing"}); '
                                   f'its errors are in {home / "maps" / "service.log"}')
        return connection


def _connection(home: Path, fresh: bool = False) -> Connection:
    held: dict[Path, Connection] = _LOCAL.__dict__.setdefault('held', {})
    connection = None if fresh else held.get(home)
    if connection is None:
        connection = held[home] = _connect(home) or _start(home)
    return connection


def _writes(command: Any) -> bool:
    return isinstance(command, dict) and bool(set(cast(dict[object, object], command)) & {'add', 'update', 'delete'})


def _unrepeatable(clear: str, memory: dict[str, object] | None, specification: dict[str, object] | None,
                  bases: dict[str, object] | None) -> str:
    """What an operation that carries no request id changes, '' when it changes nothing: a base operation other than
    list, clearing a map, a specification import, a memory tool that changes the graph. Sent again after the service
    ended mid-way, it may be done twice, as a base added twice under two names (review of 2026-11-18, F8)."""
    from metaform.project import memory_layer
    if bases and str(bases.get('op') or 'list') != 'list':
        return f"the base operation {bases.get('op')}"
    if clear:
        return 'clearing the map'
    if specification and specification.get('document') is not None:
        return 'the specification import'
    if memory and str(memory.get('tool')) in memory_layer.MUTATIONS:
        return f"the memory tool {memory.get('tool')}"
    return ''


def send(command: object, home: Path, caller: str = '', drawn: str = '', clear: str = '',
         overlay: str = '', memory: dict[str, object] | None = None,
         specification: dict[str, object] | None = None, bases: dict[str, object] | None = None,
         cypher: dict[str, object] | None = None, select: dict[str, object] | None = None) -> dict[str, object]:
    """Send one command to the home's service and return its answer, starting the service when none is running.

    A write carries a request id of its own, and the service stores that id in the same transaction as the write, so a
    write that is sent again is answered and not done a second time; a read changes nothing. When the service ends
    before it answers, those are therefore sent again to a new service. An operation that changes the store with no
    request id (`_unrepeatable`) is sent again only when it never reached the service; once sent, a lost answer is
    said as OUTCOME_UNKNOWN, with the read that shows whether it was done, never repeated blind."""
    home = home.resolve()
    given: Any = command
    payload = json.dumps({'command': command, 'caller': caller or f'process {os.getpid()}',
                          'request': uuid.uuid4().hex if _writes(given) else '',
                          **({'drawn': drawn} if drawn else {}),
                          **({'clear': clear} if clear else {}),
                          **({'overlay': overlay} if overlay else {}),
                          **({'memory': memory} if memory else {}),
                          **({'specification': specification} if specification else {}),
                          **({'bases': bases} if bases else {}),
                          **({'cypher': cypher} if cypher else {}),
                          **({'select': select} if select else {})}).encode('utf-8')
    changing = _unrepeatable(clear, memory, specification, bases)
    for attempt in range(ATTEMPTS):
        sent = False
        try:
            connection = _connection(home, fresh=attempt > 0)
            connection.send_bytes(payload)
            sent = True
            return cast(dict[str, object], json.loads(connection.recv_bytes()))
        except owner.StoreError as error:
            return commands.refused(given, Refusal('INTERNAL_ERROR', str(error)))
        except (OSError, EOFError):
            if sent and changing:
                return commands.refused(given, Refusal(
                    'OUTCOME_UNKNOWN', f'{changing} was sent and the project service ended before it answered, so it '
                    'may have been done. Read the current state (metaform map bases, the map, or the memory graph) '
                    'before sending it again.'))
            continue  # the service ended: the same command, with the same request id, goes to a new one
    return commands.refused(given, Refusal(
        'INTERNAL_ERROR', f'the project service could not be reached in {ATTEMPTS} attempts. Sending the same '
        'command again is safe; its errors are in ' + str(home / 'maps' / 'service.log')))


def stop(home: Path) -> bool:
    """Tell the home's service to stop, after the writes already queued. False when none is running."""
    home = home.resolve()
    connection = _connect(home)
    if connection is None:
        return False
    with connection:
        connection.send_bytes(json.dumps(_STOP).encode('utf-8'))
        try:
            connection.recv_bytes()
        except (OSError, EOFError):
            pass
    _LOCAL.__dict__.get('held', {}).pop(home, None)
    return True


if __name__ == '__main__':
    raise SystemExit(serve(Path(sys.argv[1])))
