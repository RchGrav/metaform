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
import selectors
import signal
import socket
import subprocess
import sys
import threading
from contextlib import ExitStack
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

from metaform import home, settings
from metaform.module import Context, Module, Noun, Pane, Stop, ToolbarItem, Verb, child_environment

from .workspace import DEFAULT, check_layout, check_toolbar, check_workspaces, workspace_choices

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False
REMOTE_AGENT = False  # the web GUI needs a screen and a browser

WAIT = 15.0  # the limit on `start`'s one wait for the server's ready line, and on `stop`'s for its stream to end
WILDCARDS = ('0.0.0.0', '::', '')
IN_USE = {errno.EADDRINUSE, errno.EACCES, 10048, 10013}  # 10048 and 10013 are Windows's in use and access denied

settings.number('web_port', 7433, min=1, max=65535, scope='global',
                help='The port the web GUI listens on.',
                details='One server per Metaform home listens here, so the address stays the same across restarts.')
settings.text('web_bind', '127.0.0.1', scope='global', person_only=True,  # who reaches the page that permits agents
              help='The address the web GUI binds to. Any address but loopback also needs the token.',
              details='At 127.0.0.1 only this machine can reach the web GUI. Another address opens it to that '
                      'network, and then every request needs the token that metaform web prints.')
settings.text('agent_command', 'claude -p', person_only=True,  # the command an agent is started with
              help='The command the web GUI starts an agent with, the task given as its last argument.',
              details='It is run in the project\'s folder when a person asks for an agent from the web GUI, as when '
                      'an element added by hand is to be validated. Where it cannot be run the task waits on the '
                      'map for an agent to take it.')

# The workspace the person arranges on the page, kept for the whole home so every project opens the same way. Each is
# the JSON text of its shape, workspace.py; empty is the defaults the modules declare, so unset returns to them. The
# page is where they are arranged; config, set and the settings screen show and take the JSON text.
settings.text('web_toolbar', '', scope='global', check=check_toolbar,
              help='The web GUI\'s toolbar as the person arranged it, as JSON; empty is the declared defaults.',
              details='{"toolbar": [[id, ...], ...], "extra": [id, ...]}: each inner list is one slot, its first tool '
                      'shown and the others behind it; extra holds the tools behind the toolbar\'s last slot. An id '
                      'is <module>.<id>, or chassis.<id>. A tool not named lands in its declared place. metaform '
                      'unset --web-toolbar restores the defaults.')
settings.text('web_layout', '', scope='global', check=check_layout,
              help='The web GUI\'s panes as the person arranged them, as JSON; empty is the declared defaults.',
              details='{"areas": {"left"|"main"|"right"|"bottom": {"size": px, "groups": [{"id", "tabs": [id, ...], '
                      '"active", "size"}]}}, "floating": [{"pane", "x", "y", "w", "h"}], "off": [id, ...]}. A pane '
                      'in off keeps its place and is not shown. A pane not named lands in its declared group and '
                      'area. metaform unset --web-layout restores the defaults.')
settings.text('web_workspaces', '', scope='global', check=check_workspaces,
              help='The person\'s named workspaces, each a saved toolbar and layout, as JSON.',
              details='{"<name>": {"toolbar": ..., "layout": ...}}. Default is never stored: it is the declared '
                      'defaults, so it cannot be deleted. The page saves, selects, resets and deletes them.')
# How the 3D map is drawn. Shapes tell an element's artifact type before any text is read: code, document, media,
# data, collection, upstream and downstream each have their own, in 2D and in 3D; off draws every element as before.
settings.boolean('web_node_shapes', True, scope='global',
                 help='Draw each element in the shape of its artifact type, the first segment of its address.',
                 details='code is a box, document a page, media a screen, data a cylinder, collection a stack, '
                         'upstream an input and downstream an output, in the 2D and the 3D map. Off draws every '
                         'element in one shape, as the maps did before.')
# The dots that flow along the joins are the 3D map's one motion that never ends by itself; drawing them costs the
# machine every frame. They flow for this long after the map was last touched or changed, then the map draws nothing
# until the next act, so a page left open costs nothing.
settings.number('web_flow_seconds', 30, min=0, max=3600, scope='global',
                help='Seconds the dots along the joins keep flowing after the map was last touched or changed.',
                details='After this the 3D map draws no frame until something on it moves or the person acts. 0 '
                        'stops the flow as soon as nothing else moves. With reduced motion nothing flows at all.')
settings.boolean('web_idle_flow', False, scope='global',
                 help='Keep the dots flowing slowly for as long as the page is open, past web_flow_seconds.',
                 details='On, an idle 3D map is still drawn 15 times a second so the flow never stops, as the map '
                         'was drawn before; off, it stops and the machine rests.')
# The page's developer detail: off shows none of it. info adds the browser-console lines of what the page reads and
# writes and the developer panes, among them the prompts Metaform and each enabled module would send; verbose adds
# the events heard and the panes drawn; trace adds every raw response.
DEBUG_LEVELS = ('off', 'info', 'verbose', 'trace')
settings.choice('web_debug', list(DEBUG_LEVELS), 'off', scope='global',
                help='Developer detail in the web GUI: off, info, verbose or trace.',
                details='info logs each read and write of the page to the browser console and adds the developer '
                        'panes: the prompts Metaform and each enabled module would send, read-only, what an agent '
                        'sees, and the traces; verbose adds the events heard and each pane drawn; trace adds every '
                        'raw response. metaform web start --web-debug <level> starts the page with it for that run.')
settings.choice('web_workspace', workspace_choices, DEFAULT, scope='global',
                help='The workspace the web GUI opens with; Reset returns the toolbar and panes to it as saved.',
                details='Default is the declared defaults. Choosing a workspace on the page copies its toolbar and '
                        'layout into web_toolbar and web_layout, which then hold the person\'s changes until the '
                        'next reset or save.')


def run_dir() -> Path:
    return home.home() / 'run'


def run_file() -> Path:
    return run_dir() / 'web.json'


def token_file() -> Path:
    return run_dir() / 'web-token'


def opened_file() -> Path:
    """The project of the folder `metaform web` last ran in, the one the page shows first, VIEW-002."""
    return run_dir() / 'web-project'


def opened(project: str | None) -> None:
    """Note the project of the folder `start` ran in, so a page opened without one named shows it first, VIEW-002.
    A folder of no project leaves no choice behind, so an older folder's choice does not outlive it."""
    try:
        if project:
            run_dir().mkdir(parents=True, exist_ok=True)
            opened_file().write_text(project, encoding='utf-8')
        else:
            opened_file().unlink(missing_ok=True)
    except OSError:
        pass  # the page then opens on the project it remembers, or the first; nothing else depends on it


def debug_file() -> Path:
    """The developer level the last `metaform web start` asked for, `--web-debug`, so a one-run choice reaches the
    server already running as well as one it starts."""
    return run_dir() / 'web-debug'


def debug_level() -> str:
    """The page's developer level: the more detailed of the setting and what the last start asked for; off shows
    nothing of it."""
    try:
        asked = debug_file().read_text(encoding='utf-8').strip()
    except OSError:
        asked = 'off'
    kept = str(settings.value('web_debug', home.home()) or 'off')
    known = [one for one in (asked, kept) if one in DEBUG_LEVELS]
    return max(known, key=DEBUG_LEVELS.index, default='off')


def opened_project() -> str | None:
    """The project `opened` noted, when it is still registered."""
    try:
        found = opened_file().read_text(encoding='utf-8').strip()
    except OSError:
        return None
    return found if found and home.project(found) is not None else None


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
    is a pipe back to `start`, on which it writes one line once it listens; its standard error is the log. It is the
    person's page, so the role of an agent that ran `start` never passes to it, BASE-052."""
    folder = run_dir()
    folder.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-m', 'metaform.modules.web.server', '--bind', bind, '--port', str(port),
               '--nonce', nonce]
    with open(folder / 'web.log', 'ab') as log:
        if os.name == 'nt':
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
            return subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=log,
                                    cwd=home.home(), env=child_environment(), creationflags=flags)
        return subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=log,
                                cwd=home.home(), env=child_environment(), start_new_session=True)


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
    opened(ctx.project)
    try:
        run_dir().mkdir(parents=True, exist_ok=True)
        debug_file().write_text(str(ctx.setting('web_debug') or 'off'), encoding='utf-8')
    except OSError:
        pass  # the page then follows the setting alone
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
    debug_file().unlink(missing_ok=True)
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


def serve(ctx: Context) -> None:
    """Reconstruct and serve static web variants until interrupted, PROJ-019."""
    store = ctx.require_store()
    ids = cast(list[str], ctx.nouns['variants'])
    try:
        with ExitStack() as stack:
            if os.name == 'nt':
                previous = signal.signal(signal.SIGBREAK, signal.default_int_handler)
                stack.callback(signal.signal, signal.SIGBREAK, previous)
            folder = Path(stack.enter_context(TemporaryDirectory(prefix='metaform-web-')))
            extracted = store.extract(ids, folder, ctx.nouns.get('origin'))
            if not extracted:
                ctx.say('No variants to serve.')
                return
            selector = stack.enter_context(selectors.DefaultSelector())
            addresses: list[tuple[str, int]] = []
            for root in extracted:
                handler = partial(SimpleHTTPRequestHandler, directory=str(root))
                server = stack.enter_context(ThreadingHTTPServer(('127.0.0.1', 0), handler))
                selector.register(server, selectors.EVENT_READ, server)
                identifier = root.name if ids == ['all'] or len(extracted) > 1 else ids[0]
                addresses.append((identifier, server.server_port))
            for identifier, port in addresses:
                ctx.say(f'{identifier}  http://127.0.0.1:{port}/')
            sys.stdout.flush()
            sys.stderr.flush()
            while True:
                for key, _ in selector.select():
                    cast(ThreadingHTTPServer, key.data).handle_request()
    except KeyboardInterrupt:
        pass  # ExitStack closes the listeners and removes the reconstructed folders.


MODULE = Module(
    id='web',
    summary="Start and stop Metaform's web GUI, and serve web variants.",
    purpose="Starts Metaform's web GUI, where people see every registered project's map. Details: metaform help web.",
    details='One server per Metaform home serves every project on one fixed port, --web-port. It binds to '
            '--web-bind, loopback by default, where no token is needed; any other address also needs the token '
            'that start prints. metaform web runs start.',
    default='start',
    verbs=(
        # Starting the GUI writes the server's record under the home and starts its process; it reaches no agent and
        # nothing past this machine on its own, and stop ends that process. Neither changes the map.
        Verb('start', start, 'Start the web GUI, or show the address it already runs at.', switches=('web_debug',),
             effect='write', open_world=False),
        Verb('stop', stop, 'Stop the web GUI.', effect='write', open_world=False),
        Verb('serve', serve, 'Serve reconstructed web variants together, each on its own local port.',
             nouns=(Noun('origin', 'The origin id; the latest origin when omitted.', required=False),
                    Noun('variants', 'Variant ids, or all to serve every variant of the origin.', many=True)),
             details='Serves static files on OS-assigned ports at 127.0.0.1 and prints one address per variant. '
                     'Runs in this terminal until Ctrl+C, then closes the ports and removes the temporary copies. '
                     'The Metaform web GUI keeps its own server and port.',
             examples=(('metaform web serve v000001 v000002', 'Compare two variants.'),
                       ('metaform web serve all origin=<id>', 'Serve every variant of one origin.')),
             surfaces=('cli',)),
    ),
    # The page's two views of the map. The default layout keeps the maps on the left and in the main area, and
    # everything a person reads or types into on the right, where the reading starts.
    # The workflow runs of the project, read and answered by the person: a run paused on the person shows what stopped
    # it, takes the answer and can tell its agent to resume, without the command line. Declared here, the page's own
    # view, beside the chat where answers are typed.
    toolbar=(
        ToolbarItem('runs', 'Workflow runs', 'See the workflow runs at work, answer one waiting on you and resume it, '
                    'or cancel one.', icon='play', pane='runs', placement='extra', order=310),
    ),
    panes=(
        Pane('map2d', '2D map', 'See the whole map flat, and walk it node by node with the keys.', icon='map',
             page='map2d', area='left', visible=True, order=10, min_width=280, min_height=200),
        Pane('map3d', '3D map', 'See the map in depth, with the agents at work on it.', icon='cube', page='map3d',
             area='main', group='stage', visible=True, order=10, min_width=320, min_height=240),
        Pane('runs', 'Workflow runs', 'See the workflow runs at work, answer one waiting on you and resume it, or '
             'cancel one.', icon='play', page='runs', area='right', group='chat', order=130, min_width=320),
    ),
)
