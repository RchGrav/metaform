"""web: Metaform's one web GUI for the user, one server per home on one fixed port, VIEW-001, VIEW-002 and VIEW-015.

`metaform web` starts the server as a process detached from the terminal and
returns its address; run again from any folder, it finds the running server
and starts no second one. `metaform web stop` ends it. The server records its
address and process id in `run/web.json` under the home. On a loopback bind
address the server's Host and Origin checks guard it; on any other address the
home's token is also required, and `start` returns it for the user.
"""
from __future__ import annotations

import errno
import http.client
import ipaddress
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import threading
from importlib import resources
from pathlib import Path
from typing import Any, cast

from metaform import home, prompt_files, settings
from metaform.module import Context, Module, Status, Stop, Subscription, Verb

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False

AUTOSTART = prompt_files.required(resources.files(__name__), 'autostart')
WAIT = 15.0  # the limit on `start`'s one wait for the server's ready line, and on `stop`'s for its stream to end
WILDCARDS = ('0.0.0.0', '::', '')
IN_USE = {errno.EADDRINUSE, errno.EACCES, 10048, 10013}  # 10048 and 10013 are Windows's in use and access denied

settings.number('web_port', 7433, min=1, max=65535, scope='global',
                help='The port the web GUI listens on.',
                details='One server per Metaform home listens here, so the address stays the same across restarts.')
settings.text('web_bind', '127.0.0.1', scope='global',
              help='The address the web GUI binds to. Any address but loopback also needs the token.',
              details='At 127.0.0.1 only this machine can reach the web GUI. Another address opens it to that '
                      'network, and then every request needs the token that metaform web prints.')
settings.boolean('web_autostart', True,
                 help='Have agents start the web GUI before an intake and tell you its address.')
settings.text('agent_command', 'claude -p',
              help='The command the web GUI starts an agent with, the task given as its last argument.',
              details='It is run in the project\'s folder when a person asks for an agent from the web GUI, as when '
                      'an element added by hand is to be validated. Where it cannot be run the task waits on the '
                      'map for an agent to take it.')


def run_dir() -> Path:
    return home.home() / 'run'


def run_file() -> Path:
    return run_dir() / 'web.json'


def token_file() -> Path:
    return run_dir() / 'web-token'


def loopback(bind: str) -> bool:
    if bind == 'localhost':
        return True
    try:
        return ipaddress.ip_address(bind).is_loopback
    except ValueError:
        return False


def host_port(host: str, port: int) -> str:
    return f'[{host}]:{port}' if ':' in host else f'{host}:{port}'


def reach(bind: str) -> str:
    """The address this machine uses to reach a server bound at `bind`."""
    if bind in WILDCARDS:
        return '::1' if bind == '::' else '127.0.0.1'
    return bind


def token(create: bool = False) -> str | None:
    """The home's token, made on the first start that needs it and kept for the next ones, VIEW-002."""
    path = token_file()
    if path.exists():
        return path.read_text(encoding='utf-8').strip()
    if not create:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    made = secrets.token_urlsafe(24)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        handle.write(made)
    return made


def recorded() -> dict[str, Any] | None:
    try:
        found: Any = json.loads(run_file().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return cast(dict[str, Any], found) if isinstance(found, dict) else None


def answering(record: dict[str, Any]) -> bool:
    """Whether the recorded server of this home answers at its address."""
    address, port = reach(str(record.get('bind', ''))), int(record.get('port') or 0)
    connection = http.client.HTTPConnection(address, port, timeout=2)
    try:
        connection.request('GET', '/api/server', headers={'Host': host_port(address, port),
                                                          'X-Metaform-Token': token() or ''})
        response = connection.getresponse()
        found: Any = json.loads(response.read()) if response.status == 200 else None
    except (OSError, ValueError):
        return False
    finally:
        connection.close()
    if not isinstance(found, dict):
        return False
    server = cast(dict[str, Any], found)
    return server.get('pid') == record.get('pid') and server.get('home') == str(home.home())


def shown(record: dict[str, Any], state: str) -> dict[str, Any]:
    """What `start` returns: the state, the address a browser opens, and the token when one is needed."""
    bind, port = str(record['bind']), int(record['port'])
    host = socket.gethostname() if bind in WILDCARDS else bind
    needed = None if loopback(bind) else token()
    address = f'http://{host_port(host, port)}/' + (f'?t={needed}' if needed else '')
    return {'state': state, 'address': address, **({'token': needed} if needed else {})}


def check_free(bind: str, port: int) -> None:
    """Stop with the setting to change when the server could not listen at `bind` and `port`."""
    family = socket.AF_INET6 if ':' in bind else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            if os.name == 'nt':
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)  # type: ignore[attr-defined]
            else:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind((bind, port))
    except OSError as error:
        reason = error.strerror or str(error)
        if error.errno in IN_USE:
            raise Stop(f'The web GUI cannot listen on port {port}: {reason}.', 'metaform set --web-port <port>')
        raise Stop(f'The web GUI cannot bind to {bind}: {reason}.', 'metaform set --web-bind <address>')


def spawn(bind: str, port: int, nonce: str) -> subprocess.Popen[bytes]:
    """The server as a process detached from the terminal, so it runs until stopped, VIEW-002. Its standard output
    is a pipe back to `start`, on which it writes one line once it listens; its standard error is the log."""
    folder = run_dir()
    folder.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-m', 'metaform.modules.web.server', '--bind', bind, '--port', str(port),
               '--nonce', nonce]
    with open(folder / 'web.log', 'ab') as log:
        if os.name == 'nt':
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
            return subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=log,
                                    cwd=home.home(), creationflags=flags)
        return subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=log,
                                cwd=home.home(), start_new_session=True)


def ready_line(process: subprocess.Popen[bytes]) -> bytes | None:
    """The server's one line saying it listens, empty when it ended first, None when it said nothing within `WAIT`.

    One wait for a message, QUAL-015: a thread blocks on the pipe and is woken by the line or by the pipe closing
    with the process; the join's limit only keeps `metaform web` from hanging forever on a server that does neither.
    """
    pipe = process.stdout
    assert pipe is not None
    heard: list[bytes] = []
    reader = threading.Thread(target=lambda: heard.append(pipe.readline()), daemon=True)
    reader.start()
    reader.join(WAIT)
    return heard[0] if heard else None


def log_tail() -> str:
    try:
        lines = (run_dir() / 'web.log').read_text(encoding='utf-8', errors='replace').strip().splitlines()
    except OSError:
        return 'it wrote no log'
    return lines[-1] if lines else 'it wrote no log'


def start(ctx: Context) -> dict[str, Any]:
    bind, port = str(ctx.setting('web_bind')), int(ctx.setting('web_port'))
    record = recorded()
    if record is not None:
        if answering(record):
            return shown(record, 'running')
        run_file().unlink(missing_ok=True)
    check_free(bind, port)
    if not loopback(bind):
        token(create=True)
    nonce = secrets.token_hex(8)
    process = spawn(bind, port, nonce)
    line = ready_line(process)
    if process.stdout is not None:
        process.stdout.close()
    if line:
        record = recorded()
        if record is not None and answering(record):
            return shown(record, 'started' if record.get('nonce') == nonce else 'running')
        raise Stop(f'The web GUI said it was ready but does not answer: {log_tail()}', 'metaform web stop')
    if line is None:
        raise Stop(f'The web GUI did not answer within {WAIT:.0f} seconds: {log_tail()}', 'metaform web stop')
    process.wait()
    record = recorded()
    if record is not None and answering(record):
        return shown(record, 'running')  # another `metaform web` started one first
    raise Stop(f'The web GUI did not start: {log_tail()}', 'metaform web')


def stop(ctx: Context) -> dict[str, Any]:
    record = recorded()
    if record is None:
        return {'state': 'not running'}
    if not answering(record):
        run_file().unlink(missing_ok=True)
        return {'state': 'not running'}
    stream = held_open(record)
    os.kill(int(record['pid']), signal.SIGTERM)
    if stream is not None:
        try:
            stream.read()  # returns when the system closes the ended process's sockets, QUAL-015; WAIT is its limit
        except OSError:
            pass
    run_file().unlink(missing_ok=True)
    return {'state': 'stopped'}


def held_open(record: dict[str, Any]) -> http.client.HTTPResponse | None:
    """The server's events stream, VIEW-018, which it holds open until it ends; None when it cannot be opened."""
    address, port = reach(str(record.get('bind', ''))), int(record.get('port') or 0)
    connection = http.client.HTTPConnection(address, port, timeout=WAIT)
    try:
        connection.request('GET', '/api/events', headers={'Host': host_port(address, port),
                                                          'X-Metaform-Token': token() or ''})
        response = connection.getresponse()
    except OSError:
        connection.close()
        return None
    if response.status != 200:
        connection.close()
        return None
    return response


def pushed(payload: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """map.changed: hand the event to the running server, which pushes it to every open page, VIEW-018.

    This subscriber runs in the publishing command's process, as every subscriber does, BASE-010. The server takes
    the event only from this machine and with the nonce from its run file. With no server running it does nothing.
    """
    record = recorded()
    if record is None:
        return {'pushed': False}
    address, port = reach(str(record.get('bind', ''))), int(record.get('port') or 0)
    body = json.dumps({'topic': 'map.changed', 'payload': payload}).encode('utf-8')
    connection = http.client.HTTPConnection(address, port, timeout=1)
    try:
        connection.request('POST', '/api/notify', body=body, headers={
            'Host': host_port(address, port), 'Content-Type': 'application/json',
            'X-Metaform-Nonce': str(record.get('nonce', '')), 'X-Metaform-Token': token() or ''})
        answer = connection.getresponse()
        answer.read()
        return {'pushed': answer.status == 200}
    except OSError:
        return {'pushed': False}
    finally:
        connection.close()


def status(ctx: Context) -> Status:
    """With `web_autostart` on, the autostart message is in the instructions agents read, VIEW-015, and in status
    for a project with no map yet, where an intake comes next. Off, it is in neither."""
    if not ctx.setting('web_autostart'):
        return Status()
    mapped = ctx.store is not None and ctx.store.has_intake()
    return Status(notice=None if mapped else AUTOSTART, instruction=AUTOSTART)


MODULE = Module(
    id='web',
    summary="Start and stop Metaform's web GUI.",
    purpose="Starts Metaform's web GUI, where people see every registered project's map. Details: metaform help web.",
    details='One server per Metaform home serves every project on one fixed port, --web-port. It binds to '
            '--web-bind, loopback by default, where no token is needed; any other address also needs the token '
            'that start prints. metaform web runs start.',
    default='start',
    verbs=(
        Verb('start', start, 'Start the web GUI, or show the address it already runs at.'),
        Verb('stop', stop, 'Stop the web GUI.'),
    ),
    subscriptions=(Subscription('map.changed', pushed),),
    status=status,
)
