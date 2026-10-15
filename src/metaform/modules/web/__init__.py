"""web: Metaform's one web GUI for the user, one server per home on one fixed port, VIEW-001, VIEW-002 and VIEW-015.

`metaform web` starts the server as a process detached from the terminal and
returns its address; run again from any folder, it finds the running server
and starts no second one. `metaform web stop` ends it. The server records its
address and process id in `run/web.json` under the home. On a loopback bind
address the server's Host and Origin checks guard it; on any other address the
home's token is also required, and `start` returns it for the user.
"""
from __future__ import annotations

import contextlib
import errno
import http.client
import ipaddress
import json
import os
import secrets
import selectors
import shutil
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
from metaform.data import BASE_VARIABLE
from metaform.module import Context, Module, Noun, Pane, Stop, Subscription, ToolbarItem, Verb, child_environment

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False
REMOTE_AGENT = False  # the web GUI needs a screen and a browser

WAIT = 15.0  # the limit on `start`'s one wait for the server's ready line, and on `stop`'s for its stream to end
RESTART_WAIT = 4 * WAIT  # the limit on `restart`'s wait for its stop and start, each with waits of its own
WILDCARDS = ('0.0.0.0', '::', '')
# Behind a Metaform Node's gate: the per-deploy secret Caddy adds to every page request, which the server reads from
# this variable once, at start (the node module's gate.env gives it to Caddy and the web container only).
GATE_SECRET = 'METAFORM_GATE_SECRET'
IN_USE = {errno.EADDRINUSE, errno.EACCES, 10048, 10013}  # 10048 and 10013 are Windows's in use and access denied
# The watchdog, watchdog.py, that `start` runs the server under, VIEW-002: its process id, and the restart that started
# a server, with when, why and how many so far, both in the server's environment; and the hold tool it runs under, a
# path or empty for none, else `hold` on the PATH.
SUPERVISOR = 'METAFORM_WEB_SUPERVISOR'
RESTARTED = 'METAFORM_WEB_RESTARTED'
HOLD = 'METAFORM_HOLD'
PYTHON = 'METAFORM_WATCHDOG_PYTHON'  # the python a hold call runs the watchdog with, given by its own path

settings.number('web_port', 7433, min=1, max=65535, scope='global',
                help='The port the web GUI listens on.',
                details='One server per Metaform home listens here, so the address stays the same across restarts.',
                label='Page port', category='advanced')
settings.text('web_bind', '127.0.0.1', scope='global', person_only=True,  # who reaches the page that permits agents
              help='The address the web GUI binds to. Any address but loopback also needs the token.',
              details='At 127.0.0.1 only this machine can reach the web GUI. Another address opens it to that '
                      'network, and then every request needs the token that metaform web prints.',
              label='Page bind address', category='advanced')
# Whether the page is laid out by the workspace, its toolbar, panes and Window menu, or as it was written before them:
# the side column with its tabs beside the large map. A fork in how the page is arranged, so it is the person's. Off
# until the workspace's Default reproduces the page as written and every check of it passes with the workspace on.
settings.boolean('web_panes', False, scope='global',
                 help='Lay the web GUI out by the workspace: the toolbar, docked and floating panes, the Window menu.',
                 details='Off, the page keeps the side column with its tabs beside the large map, and no toolbar; '
                         'the workspace settings are kept for when it is on again.',
                 label='Draw the page from panes', category='advanced')
# How the 3D map is drawn. Shapes tell an element's artifact type before any text is read: code, document, media,
# data, collection, upstream and downstream each have their own, in 2D and in 3D; off draws every element as before.
settings.boolean('web_node_shapes', True, scope='global',
                 help='Draw each element in the shape of its artifact type, the first segment of its address.',
                 details='code is a box, document a page, media a screen, data a cylinder, collection a stack, '
                         'upstream an input and downstream an output, in the 2D and the 3D map. Off draws every '
                         'element in one shape, as the maps did before.',
                 label='Node shapes', heading='Look')
# The page's theme, its colors, and with space the 3D map drawn in outer space, page/ultra.js: a starfield and a faint
# nebula behind it, each element a celestial body of its artifact type, the joins as filaments of light and a glow on
# what is bright. One choice of look, settings cleanup 2026-10-15, which removed web_graphics, its shadow that the page
# rewrote from the theme. Written only when the person picks a theme; until then each browser keeps the theme it last
# showed, so nobody's look changed when it became a setting. The names are page/index.html's #theme options.
THEMES = ('space', 'black', 'midnight', 'graphite', 'plum', 'forest', 'ember', 'paper', 'mist')
settings.choice('web_theme', list(THEMES), 'space', scope='global',
                help="The page's theme: space draws the 3D map in outer space; every other theme draws it flat.",
                details='Chosen in the View menu, with U for space and back, or here, and kept for every browser. '
                        'Until a theme is chosen, each browser keeps the one it last showed, space in a new one.',
                label='Theme', heading='Look')
# Giving an agent in the chat a body on the map: the page offers it once per conversation, in its thread, at a pause
# (a turn ended or a ticket closed, never while it works), after EMBODY_TURNS turns or EMBODY_MINUTES minutes in
# page/app/dock/embody.js, whichever comes first. Asked too soon, the offer interrupts a conversation that has not shown it is worth keeping;
# about eight turns or twenty minutes is a conversation the person is staying with. always gives each conversation the
# person's last choice, or the mascot to the system agent; never makes no offer. The figure itself is the flow's,
# `window.metaform.embody`.
settings.choice('web_embody', ['offer', 'always', 'never'], 'offer', scope='global',
                help='Whether the chat offers to give its agent a body on the map: offer, always or never.',
                details='offer asks once per conversation, at a pause, after eight turns or twenty minutes; always gives every conversation your last choice, or the mascot '
                        'to your system agent; never makes no offer. The avatar in the chat\'s head, its menu or B '
                        'give or change a body at any time.',
                label='Agents take a figure', heading='Mascot and agents')
# What a chat's thread shows of the agent's work. Off, it shows what the agent says to the person, its messages and the
# lines it says on the map, so an agent that comes out in the chat speaks without its tool calls and thinking between
# its words; those are debug detail, shown with this on, or for one page with W.
settings.boolean('web_chat_details', False, scope='global',
                 help="Show the agent's work in the chat: its tool calls, their details and its thinking.",
                 details='Off, a thread shows only what the agent says to you, its messages and the lines it says on '
                         'the map, with its permission requests and questions. W in the web GUI shows or hides the '
                         'work on that page until it is reloaded, and saves nothing.',
                 label="Show the agent's work in the chat", heading='Mascot and agents')
# The dots that flow along the joins are the 3D map's one motion that never ends by itself; drawing them costs the
# machine every frame. They flow for this long after the map was last touched or changed, then the map draws nothing
# until the next act, so a page left open costs nothing.
settings.number('web_flow_seconds', 30, min=0, max=3600, scope='global',
                help='Seconds the dots along the joins keep flowing after the map was last touched or changed.',
                details='After this the 3D map draws no frame until something on it moves or the person acts. 0 '
                        'stops the flow as soon as nothing else moves. With reduced motion nothing flows at all.',
                label='Activity flow lasts', category='advanced', heading='Flow')
# How often each join pulses: after each request and reply a join waits (random + random) times this, so the waits
# bunch around it with now and then a quick one or a slow one, each join drawing its own, and nothing pulses in step.
# In milliseconds, since a setting's number is whole. Which joins the dots flow along, how deep the map shows and
# whether the joins' lines are drawn are the person's view, view.py.
settings.number('web_pulse_ms', 3000, min=200, max=30000, scope='global',
                help='The usual wait, in milliseconds, between one request and reply on a join and the next.',
                details='Each join waits (random + random) times this after each cycle, a fresh wait every time, so '
                        'the flow bunches about this pace and never pulses in step, in the 3D and the 2D map.',
                label='Pulse length', category='advanced', heading='Flow')
settings.number('web_bubble_seconds', 5, min=1, max=120, scope='global',
                help="How long, in seconds, an agent's speech bubble stays up after each new line it says.",
                details='The next line the agent says brings the bubble back; between lines it fades out.',
                label='Word bubble shown for', category='advanced')
settings.boolean('web_idle_flow', True, scope='global',
                 help='Keep the dots flowing for as long as the page is open, past web_flow_seconds.',
                 details='On, an idle map is still drawn at the full frame rate so the flow never stops and stays '
                         'smooth; off, it stops after web_flow_seconds and the machine rests.',
                 label='Flow while idle', heading='Flow')
# What agents really do is drawn in the flow's own looks, a little larger and brighter than the flow the map shows of
# itself: a session starting, each part of the map a tool call reaches, and each note, item or work record written on
# a node. It comes from the page's event stream as it happens and costs nothing while nothing happens.
settings.boolean('web_live_flow', True, scope='global',
                 help="Draw agents' real activity on the map: requests to the parts a tool call reaches, records "
                      'landing where something is written.',
                 details='Off, the map shows only the flow it draws of its own joins. With reduced motion nothing '
                         'flows at all.',
                 label="Flow on agents' activity", heading='Flow')
# The characters the agents' figures are drawn as, page/agent-glyphs, read from the files so the choices are the
# characters there are.
CHARACTERS = sorted(path.stem for path in (Path(__file__).parent / 'page' / 'agent-glyphs').glob('*.svg'))
# The person's mascot: one of the characters stands for the person on the map, goes to what they select, greets the
# agent they chat with, calls their attention to what needs them, and sleeps while they are away. It is never given
# to an agent. none draws no mascot.
settings.choice('web_mascot', ['none', *CHARACTERS], 'none', scope='global',
                help='The character that stands for you on the map, or none.',
                details='It goes to what you select and waits beside it, greets the agent you chat with, brings you '
                        'a note when something needs you, and sleeps while you are away. It never takes a click.',
                label='Your mascot', heading='Mascot and agents')
settings.choice('web_mascot_mischief', ['calm', 'playful', 'chaotic'], 'playful', scope='global',
                help='How much the mascot does of its own accord: calm, playful or chaotic.',
                details='calm only calls your attention and never wanders; playful wanders now and then and nudges a '
                        'node it passes; chaotic does both more often. It never takes the pointer or blocks a click.',
                label='Mascot mischief', heading='Mascot and agents')
def _glyph_choices(ctx: Context) -> list[str]:
    """Each agent type dispatch starts, by its dispatch_agent choices, with each character there is."""
    agent = settings.SCHEMA.get('dispatch_agent')
    agents = agent.options(ctx.folder) if agent is not None else ['claude', 'codex', 'gemini']
    return [f'{one}={character}' for one in agents for character in CHARACTERS]


settings.items('web_agent_glyphs', [], scope='global', exclusive='=', choices=_glyph_choices,
               help='The character for each agent type, as type=character, such as claude=owl or codex=beetle.',
               details='Without one, characters are given as before, so no two agents at work look alike; a '
                       'character already at work, or the mascot, is never given twice.',
               label='Agent glyphs', category='advanced')
# The page's developer detail: off shows none of it. info adds the browser-console lines of what the page reads and
# writes and the developer panes, among them the prompts Metaform and each enabled module would send; verbose adds
# the events heard and the panes drawn; trace adds every raw response.
DEBUG_LEVELS = ('off', 'info', 'verbose', 'trace')
settings.choice('web_debug', list(DEBUG_LEVELS), 'off', scope='global',
                help='Developer detail in the web GUI: off, info, verbose or trace.',
                details='info logs each read and write of the page to the browser console and adds the developer '
                        'panes: the prompts Metaform and each enabled module would send, read-only, what an agent '
                        'sees, and the traces; verbose adds the events heard and each pane drawn; trace adds every '
                        'raw response. metaform web start --web-debug <level> starts the page with it for that run.',
                label='Developer level', category='advanced')


def run_dir() -> Path:
    return home.home() / 'run'


def run_file() -> Path:
    return run_dir() / 'web.json'


def watchdog_file() -> Path:
    return run_dir() / 'web-watchdog.json'


def write_run(path: Path, text: str) -> None:
    """Write one of the server's run files, readable by its owner alone, as the token is."""
    home.write_private(path, text)


def restart_said(text: str) -> dict[str, Any] | None:
    """The restart that started a server, as the watchdog gives it in RESTARTED; None for a first start."""
    try:
        found: Any = json.loads(text) if text else None
    except ValueError:
        return None
    return cast(dict[str, Any], found) if isinstance(found, dict) else None


def hold_tool() -> str | None:
    """The hold tool the watchdog runs under: HOLD when it is set, empty for none, else `hold` on the PATH."""
    given = os.environ.get(HOLD)
    if given is not None:
        return given or None
    return shutil.which('hold') if os.name != 'nt' else None


def hold_name(port: int) -> str:
    """The hold call the watchdog of the server on `port` is placed as, so `hold list` names it."""
    return f'metaform-web-{port}'


def alive(pid: int) -> bool:
    """Whether a process with this id runs: on Windows by tasklist, since os.kill there would end it."""
    if pid <= 0:
        return False
    if os.name == 'nt':
        done = subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/NH', '/FO', 'CSV'], capture_output=True,
                              text=True, timeout=WAIT, check=False)
        return f'"{pid}"' in done.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def ended(pid: int, limit: float | None = None) -> bool | None:
    """Wait for process `pid`, which need not be this one's child, to end, woken by the system's own event of its exit,
    QUAL-015: a pidfd on Linux, kqueue's NOTE_EXIT on macOS, the process's handle on Windows. True once it has ended,
    False when `limit` seconds passed first, None when this system gives no such event."""
    if os.name == 'nt':
        import ctypes
        windows: Any = ctypes  # windll is Windows's alone
        kernel32 = windows.windll.kernel32
        handle = kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if not handle:
            return True
        try:
            return kernel32.WaitForSingleObject(handle, 0xFFFFFFFF if limit is None else int(limit * 1000)) == 0
        finally:
            kernel32.CloseHandle(handle)
    import select
    if hasattr(select, 'kqueue'):
        bsd: Any = select  # kqueue is macOS's and the BSDs'
        queue = bsd.kqueue()
        try:
            change = bsd.kevent(pid, filter=bsd.KQ_FILTER_PROC, flags=bsd.KQ_EV_ADD | bsd.KQ_EV_ONESHOT,
                                fflags=bsd.KQ_NOTE_EXIT)
            return bool(queue.control([change], 1, limit))
        except ProcessLookupError:
            return True
        finally:
            queue.close()
    try:
        fd = pidfd(pid)
    except ProcessLookupError:
        return True
    if fd is None:
        return None
    try:
        return bool(select.select([fd], [], [], limit)[0])
    finally:
        os.close(fd)


def pidfd(pid: int) -> int | None:
    """A Linux pidfd of `pid`, readable once it ends; by the system call where this Python build has no
    os.pidfd_open, as the standalone builds do; None where neither is to be had."""
    if hasattr(os, 'pidfd_open'):
        try:
            return os.pidfd_open(pid)
        except ProcessLookupError:
            raise
        except OSError:
            return None
    import ctypes
    import platform
    if not sys.platform.startswith('linux') or platform.machine().lower() not in ('x86_64', 'aarch64'):
        return None  # 434 is pidfd_open on these two 64-bit ABIs
    try:
        call: Any = ctypes.CDLL(None, use_errno=True).syscall
    except (OSError, AttributeError):
        return None
    call.restype, call.argtypes = ctypes.c_long, [ctypes.c_long, ctypes.c_int, ctypes.c_uint]
    found = int(call(434, pid, 0))
    if found >= 0:
        return found
    if ctypes.get_errno() == errno.ESRCH:
        raise ProcessLookupError(pid)
    return None


def watchdog() -> dict[str, Any] | None:
    """The record of this home's watchdog, while its process runs."""
    try:
        found: Any = json.loads(watchdog_file().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if not isinstance(found, dict):
        return None
    record = cast(dict[str, Any], found)
    return record if alive(int(record.get('pid') or 0)) else None


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
            home.mkdir_private(run_dir())
            write_run(opened_file(), project)
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
    home.mkdir_private(path.parent)
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


def page_environment() -> dict[str, str]:
    """The environment of the server and its watchdog. It is the person's page, so the role of an agent that ran
    `start` never passes to it, BASE-052, nor the base its ticket is on: the page shows whichever base the person
    chooses."""
    return {name: value for name, value in child_environment().items() if name != BASE_VARIABLE}


def spawn(bind: str, port: int, nonce: str, origin: str = '', gate: str | None = None, *,
          supervisor: str | None = None, restarted: str | None = None) -> subprocess.Popen[bytes]:
    """The server as a process detached from the terminal, so it runs until stopped, VIEW-002. Its standard output
    is a pipe back to `start`, on which it writes one line once it listens; its standard error is the log. A server
    behind a Node's gate hands its public origin and gate secret to its replacement, and to nothing else; one under
    the watchdog is told the watchdog's process, and the restart that started it."""
    env = page_environment()
    command = [sys.executable, '-m', 'metaform.modules.web.server', '--bind', bind, '--port', str(port),
               '--nonce', nonce]
    if origin and gate:
        command += ['--origin', origin]
        env[GATE_SECRET] = gate
    if supervisor:
        env[SUPERVISOR] = supervisor
    if restarted:
        env[RESTARTED] = restarted
    return detached(command, env)


def detached(command: list[str], env: dict[str, str]) -> subprocess.Popen[bytes]:
    """A process detached from the terminal, in a session of its own, with its standard output a pipe back to this
    one and its standard error the log, run/web.log."""
    folder = run_dir()
    home.mkdir_private(folder)
    with os.fdopen(os.open(folder / 'web.log', os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600), 'ab') as log:
        if os.name == 'nt':
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
            return subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=log,
                                    cwd=home.home(), env=env, creationflags=flags)
        return subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=log,
                                cwd=home.home(), env=env, start_new_session=True)


def ready_line(process: subprocess.Popen[bytes], limit: float = WAIT) -> bytes | None:
    """The server's one line saying it listens, empty when it ended first, None when it said nothing within `limit`.

    One wait for a message, QUAL-015: a thread blocks on the pipe and is woken by the line or by the pipe closing
    with the process; the join's limit only keeps `metaform web` from hanging forever on a server that does neither.
    """
    pipe = process.stdout
    assert pipe is not None
    heard: list[bytes] = []
    reader = threading.Thread(target=lambda: heard.append(pipe.readline()), daemon=True)
    reader.start()
    reader.join(limit)
    return heard[0] if heard else None


def log_tail() -> str:
    try:
        lines = (run_dir() / 'web.log').read_text(encoding='utf-8', errors='replace').strip().splitlines()
    except OSError:
        return 'it wrote no log'
    return lines[-1] if lines else 'it wrote no log'


def start(ctx: Context) -> dict[str, Any]:
    return announced(ctx, starting(ctx))


def announced(ctx: Context, started: dict[str, Any]) -> dict[str, Any]:
    """`web.started`, so a module that serves beside the page starts with it, such as twilio's phone bridge when the
    person has turned it on; a subscriber's failure is its own and never the page's."""
    with contextlib.suppress(Exception):
        ctx.publish('web.started', {'project': ctx.project, 'folder': str(ctx.folder), 'state': started['state']})
    return started


def starting(ctx: Context) -> dict[str, Any]:
    bind, port = str(ctx.setting('web_bind')), int(ctx.setting('web_port'))
    opened(ctx.project)
    try:
        home.mkdir_private(run_dir())
        write_run(debug_file(), str(ctx.setting('web_debug') or 'off'))
    except OSError:
        pass  # the page then follows the setting alone
    return launched(bind, port)


def launched(bind: str, port: int) -> dict[str, Any]:
    """The server answering at `bind` and `port`: the one that runs, or one started under a new watchdog."""
    record = recorded()
    if record is not None and answering(record):
        return shown(record, 'running')
    kept = watchdog()
    if kept is not None:  # its server ended or hangs, and the watchdog is starting it again
        return shown(kept, 'restarting')
    run_file().unlink(missing_ok=True)
    check_free(bind, port)
    if not loopback(bind):
        token(create=True)
    nonce = secrets.token_hex(8)
    line = watched(bind, port, nonce)
    if line:
        record = recorded()
        if record is not None and answering(record):
            return shown(record, 'started' if record.get('nonce') == nonce else 'running')
        raise Stop(f'The web GUI said it was ready but does not answer: {log_tail()}', 'metaform web stop')
    if line is None:
        raise Stop(f'The web GUI did not answer within {WAIT:.0f} seconds: {log_tail()}', 'metaform web stop')
    record = recorded()
    if record is not None and answering(record):
        return shown(record, 'running')  # another `metaform web` started one first
    raise Stop(f'The web GUI did not start: {log_tail()}', 'metaform web')


def watched(bind: str, port: int, nonce: str) -> bytes | None:
    """Start the watchdog, which starts the server, VIEW-002, and its one line saying the server listens: empty when
    the server ended first, None when nothing was said within `WAIT`. With the hold tool the watchdog is placed as a
    hold call, so `hold list` shows it and `hold end` stops it and its server, and it says so through a named pipe,
    since hold keeps a call's standard output; without it, it is a detached process saying so on a pipe, as the server
    does."""
    name = hold_name(port)
    line = outliving(['-m', 'metaform.modules.web.watchdog', '--bind', bind, '--port', str(port), '--nonce', nonce],
                     name, "web GUI's watchdog", 'start', WAIT)
    held = hold_tool()
    if line is None and held is not None:  # the watchdog ended before it could say anything: hold kept what it wrote
        told = subprocess.run([held, 'logs', name, '-p'], capture_output=True, text=True, encoding='utf-8',
                              errors='replace', timeout=WAIT, check=False).stdout.strip().splitlines()
        raise Stop(f"The web GUI's watchdog, hold call {name}, did not start: "
                   f'{told[-1] if told else "hold kept no log"}', f'hold logs {name}')
    return line


def outliving(module: list[str], name: str, what: str, verb: str, limit: float) -> bytes | None:
    """Run `module` with this python as a process that outlives this one, and wait for the one line it says: empty
    when it ended first, None when it said nothing within `limit`. With the hold tool it is the hold call `name` and
    says it through a named pipe; without, a detached process saying it on a pipe."""
    command = [sys.executable, *module]
    held = hold_tool()
    if held is None:
        process = detached(command, page_environment())
        line = ready_line(process, limit)
        if process.stdout is not None:
            process.stdout.close()
        return line
    home.mkdir_private(run_dir())
    pipe = run_dir() / f'web-ready-{secrets.token_hex(8)}'
    os.mkfifo(pipe, 0o600)  # type: ignore[attr-defined]  hold runs on POSIX systems only
    try:
        subprocess.run([held, 'purge', name], capture_output=True, timeout=WAIT, check=False)  # a past call's name
        # hold runs every path in a call by its real path, which takes a virtual environment's python, a link, to the
        # base interpreter, outside the environment Metaform is installed in; so the shell is given it to run, in the
        # environment, where hold leaves it as it is. hold -d leaves the processes that keep the call in the session
        # of whoever placed it, and hold counts a call as running while its group has any: placed from the restart's
        # own call, the watchdog's would keep that call running as long as the server runs, and the next restart
        # could neither purge it nor take its name. So it is placed from a session of its own.
        placed = subprocess.run([held, '--quiet', '--name', name, '-d', '/bin/sh', '-c', f'exec "${PYTHON}" "$@"',
                                 'sh', *command[1:], '--ready', str(pipe)],
                                cwd=home.home(), env={**page_environment(), PYTHON: sys.executable},
                                capture_output=True, text=True, encoding='utf-8', stdin=subprocess.DEVNULL,
                                start_new_session=True, timeout=WAIT, check=False)
        if placed.returncode != 0:
            raise Stop(f'hold could not place the {what}: {placed.stderr.strip() or placed.returncode}',
                       f'{HOLD}= metaform web {verb}, which runs it without hold')
        return heard(pipe, limit)
    finally:
        pipe.unlink(missing_ok=True)


def heard(pipe: Path, limit: float = WAIT) -> bytes | None:
    """The one line written to the named pipe, as `ready_line` reads it from a process's pipe; None when no one opened
    it within `limit`, whose other end is then opened here, so the waiting reader ends."""
    said: list[bytes] = []

    def listen() -> None:
        with pipe.open('rb') as stream:
            said.append(stream.readline())

    reader = threading.Thread(target=listen, daemon=True)
    reader.start()
    reader.join(limit)
    if reader.is_alive():
        with contextlib.suppress(OSError):
            os.close(os.open(pipe, os.O_WRONLY | os.O_NONBLOCK))
        return None
    return said[0] if said else b''


def purged(name: str) -> None:
    """Remove the hold call `name` from the ledger once its process has ended, its exit the system's own event waited
    for at most WAIT / 3, so a call whose work is done leaves no past call in `hold list`. Without hold, nothing."""
    held = hold_tool()
    if held is None:
        return
    shown = subprocess.run([held, 'inspect', name], capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=WAIT, check=False)
    try:
        pid = int(json.loads(shown.stdout)[0]['pid'])
    except (ValueError, LookupError, TypeError):
        return
    ended(pid, WAIT / 3)
    subprocess.run([held, 'purge', name], capture_output=True, timeout=WAIT, check=False)


def stop(ctx: Context) -> dict[str, Any]:
    """Stop the watchdog and its server. On POSIX systems the watchdog ends its server itself; on Windows the stop
    signal ends a process at once, so the server is ended here too, as it is when no watchdog keeps it."""
    kept, record = watchdog(), recorded()
    live = record is not None and answering(record)
    if kept is None and not live:
        run_file().unlink(missing_ok=True)
        return {'state': 'not running'}
    debug_file().unlink(missing_ok=True)
    stream = held_open(record) if live and record is not None else None
    if kept is not None:
        with contextlib.suppress(OSError):
            os.kill(int(kept['pid']), signal.SIGTERM)
    if live and record is not None and (kept is None or os.name == 'nt'):
        with contextlib.suppress(OSError):
            os.kill(int(record['pid']), signal.SIGTERM)
    if stream is not None:
        try:
            stream.read()  # returns when the system closes the ended process's sockets, QUAL-015; WAIT is its limit
        except OSError:
            pass
    if live and record is not None and answering(record):  # a watchdog that did not end its server
        with contextlib.suppress(OSError):
            os.kill(int(record['pid']), signal.SIGTERM)
    held = hold_tool()
    if kept is not None and held is not None:  # its hold call, once it has ended, leaves no past call in the ledger
        ended(int(kept['pid']), WAIT / 3)  # its exit, the system's own event, waited for at most WAIT / 3
        subprocess.run([held, 'purge', hold_name(int(kept['port']))], capture_output=True, timeout=WAIT, check=False)
    run_file().unlink(missing_ok=True)
    watchdog_file().unlink(missing_ok=True)
    return {'state': 'stopped'}


def restart(ctx: Context) -> dict[str, Any]:
    """Stop the web GUI and start it again, VIEW-002, in a process of its own, restart.py, that outlives this one: an
    agent whose session ends between the stop and the start leaves the page coming back, not gone. With the hold tool
    it is the hold call metaform-web-restart-<port>. This waits for its word at most RESTART_WAIT; past that the restart
    goes on without anyone waiting."""
    port = int((recorded() or {}).get('port') or ctx.setting('web_port'))
    name = f'metaform-web-restart-{port}'
    line = outliving(['-m', 'metaform.modules.web.restart', '--folder', str(ctx.folder)],
                     name, "web GUI's restart", 'restart', RESTART_WAIT)
    if line is None:
        return {'state': 'restarting', 'next': 'metaform web start gives the address once the page answers'}
    purged(name)
    said = restart_said(line.decode('utf-8', errors='replace'))
    if said is None:
        raise Stop(f"The web GUI's restart ended before it said how it went: {log_tail()}", 'metaform web start')
    if said.get('error'):
        raise Stop(str(said['error']), str(said.get('next') or 'metaform web start'))
    return said


RECONNECTS = 'An open page reconnects on its own through its live stream, and offers a reload if the code changed.'


def restarting(ctx: Context) -> dict[str, Any]:
    """The restart itself, which restart.py runs in its own process: the server that runs is stopped, the exits of it
    and its watchdog waited for as the system's own events, and a new one started on the bind address and port it was
    started with, keeping the developer level it was started at and the project its page opens on. With none running
    it is a start, from the folder's settings."""
    kept, record = watchdog(), recorded()
    live = record if record is not None and answering(record) else None
    was = live or kept
    if was is None:
        return {**announced(ctx, starting(ctx)), 'pages': RECONNECTS}
    try:
        debug: str | None = debug_file().read_text(encoding='utf-8').strip() or None
    except OSError:
        debug = None
    stop(ctx)
    for gone in (live, kept):
        if gone is not None and gone.get('pid'):
            ended(int(gone['pid']), WAIT)
    if debug:
        write_run(debug_file(), debug)
    started = announced(ctx, launched(str(was['bind']), int(was['port'])))
    return {**started, 'state': 'restarted' if started['state'] == 'started' else started['state'],
            'pages': RECONNECTS}


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


# The person's mascot, web_mascot, and every agent's figure, VIEW-005: what they do and see on the open page. Each act
# goes to the running web GUI, which hands it to every open page of the project with an id of its own; an act that asks
# something, what a figure sees, a picture from its eyes, or what the person is looking at, and an act of the body,
# which the page answers once the body is done with where it ended up, waits for the page's answer. Nothing is written. With no page open it is refused, with what to do next. An agent asks from
# its own figure, METAFORM_WORK, the ticket its runner gave it; the person's system agent and the person from the
# mascot.
EMOTES = ('wave', 'think', 'celebrate', 'shrug', 'sleep')
PUSH_WAYS = ('away', 'up', 'down')  # a push's direction, else the address of an element it is pushed toward
TABS = ('object', 'brief', 'provenance', 'prompt')
OPENS = ('board', 'ticket', 'settings', 'pane')
CAMERAS = ('work', 'whole', 'zoom', 'free')


def ask_page(ctx: Context, act: str, **given: Any) -> dict[str, Any]:
    if not ctx.project:
        raise Stop("The mascot and the figures live on a project's map.", 'cd <project folder>')
    record = recorded()
    if record is None or not answering(record):
        raise Stop('The web GUI is not running, so no page shows the map.', 'metaform web start, then open the page')
    address, port = reach(str(record.get('bind', ''))), int(record.get('port') or 0)
    host = host_port(address, port)
    # the agent asking: its ticket, and its role, the person's system agent being the mascot
    work, role = os.environ.get('METAFORM_WORK') or None, os.environ.get('METAFORM_ROLE') or None
    body = json.dumps({'project': ctx.project, 'act': act, **({'work': work} if work else {}),
                       **({'role': role} if role else {}), **given}).encode('utf-8')
    connection = http.client.HTTPConnection(address, port, timeout=15)
    try:
        connection.request('POST', '/api/mascot', body=body, headers={
            'Host': host, 'Origin': f'http://{host}', 'Content-Type': 'application/json',
            'Content-Length': str(len(body)), 'X-Metaform-Token': token() or ''})
        response = connection.getresponse()
        found: Any = json.loads(response.read() or b'null')
    except (OSError, ValueError) as error:
        raise Stop(f'The web GUI did not answer: {error}.', 'metaform web start') from error
    finally:
        connection.close()
    answer = cast(dict[str, Any], found) if isinstance(found, dict) else {}
    if response.status != 200 or answer.get('error'):
        # the page answered and refused: it is open, so the agent reads what it shows; else no page answered
        fallback = 'metaform web viewing' if response.status == 200 else 'open the page on this project'
        raise Stop(str(answer.get('error') or f'The page refused it ({response.status}).'),
                   str(answer.get('next') or fallback))
    return answer


def mascot_act(ctx: Context, act: str, **given: Any) -> dict[str, Any]:
    return {'act': act, **given, **ask_page(ctx, act, **given)}


def number(ctx: Context, name: str) -> float | None:
    given = ctx.nouns.get(name)
    if given in (None, ''):
        return None
    try:
        return float(given)
    except (TypeError, ValueError) as error:
        raise Stop(f'{name} is a number, not {given}.', f'{name}=2') from error


def say(ctx: Context) -> dict[str, Any]:
    speak = str(ctx.nouns.get('speak') or '').lower() in ('true', 'yes', '1')
    return mascot_act(ctx, 'say', text=str(ctx.nouns['text']), **({'speak': True} if speak else {}))


def go(ctx: Context) -> dict[str, Any]:
    return mascot_act(ctx, 'go', address=str(ctx.nouns['address']), distance=number(ctx, 'distance'),
                      height=number(ctx, 'height'))


def turn(ctx: Context) -> dict[str, Any]:
    toward, bearing = ctx.nouns.get('address'), number(ctx, 'degrees')
    if not toward and bearing is None:
        raise Stop('Turn toward an address, or by a number of degrees.', 'metaform web turn address=<address>')
    return mascot_act(ctx, 'turn', address=str(toward or ''), degrees=bearing)


def point(ctx: Context) -> dict[str, Any]:
    return mascot_act(ctx, 'point', address=str(ctx.nouns['address']))


def emote(ctx: Context) -> dict[str, Any]:
    if ctx.nouns['emote'] not in EMOTES:
        raise Stop(f'{ctx.nouns["emote"]} is not one of the emotes: {", ".join(EMOTES)}.', 'metaform web emote wave')
    return mascot_act(ctx, 'emote', emote=str(ctx.nouns['emote']))


def point_noun(ctx: Context, name: str) -> list[float] | None:
    """A point in the 3D map's space, x,y,z in the units web_see measures; None when not given."""
    given = ctx.nouns.get(name)
    if given in (None, ''):
        return None
    try:
        found = [float(part) for part in str(given).split(',')]
    except ValueError:
        found = []
    if len(found) != 3:
        raise Stop(f'{name} is a point, x,y,z, not {given}.', f'{name}=0,40,0')
    return found


def move(ctx: Context) -> dict[str, Any]:
    """The mascot moves freely through the scene: to a point, to an element, or by a step from where it faces."""
    steps = {key: number(ctx, key) for key in ('forward', 'right', 'up')}
    point = point_noun(ctx, 'point')
    if not ctx.nouns.get('address') and point is None and all(value is None for value in steps.values()):
        raise Stop('Move to an address, to a point, or by forward, right or up.', 'metaform web move address=<address>')
    return mascot_act(ctx, 'move', address=str(ctx.nouns.get('address') or ''), point=point,
                      **{key: value for key, value in steps.items() if value is not None})


def push(ctx: Context) -> dict[str, Any]:
    strength = number(ctx, 'strength')
    if strength is not None and not 0 <= strength <= 1:
        raise Stop('strength is from 0 to 1.', 'metaform web push address=<address> strength=0.5')
    direction = str(ctx.nouns.get('direction') or 'away')
    toward = '' if direction in PUSH_WAYS else direction
    return mascot_act(ctx, 'push', address=str(ctx.nouns['address']), direction=direction if not toward else 'toward',
                      toward=toward, strength=0.5 if strength is None else strength)


def drag(ctx: Context) -> dict[str, Any]:
    point, beside = point_noun(ctx, 'point'), str(ctx.nouns.get('beside') or '')
    if point is None and not beside:
        raise Stop('Drag it to a point, or beside another element.', 'metaform web drag address=<address> beside=<address>')
    return mascot_act(ctx, 'drag', address=str(ctx.nouns['address']), point=point, beside=beside)


def drop(ctx: Context) -> dict[str, Any]:
    return mascot_act(ctx, 'drop')


def take(ctx: Context) -> dict[str, Any]:
    return mascot_act(ctx, 'take', reason=str(ctx.nouns['reason']))


def release(ctx: Context) -> dict[str, Any]:
    return mascot_act(ctx, 'release')


def see(ctx: Context) -> dict[str, Any]:
    return ask_page(ctx, 'see', address=str(ctx.nouns.get('address') or ''))


def look(ctx: Context) -> dict[str, Any]:
    """A picture from the figure's own eyes, with what it sees. Over MCP the picture is the tool's image; elsewhere it
    is saved under the home and its path given, so a terminal is not filled with it."""
    return pictured(ctx, ask_page(ctx, 'look', address=str(ctx.nouns.get('address') or '')))


def pictured(ctx: Context, found: dict[str, Any]) -> dict[str, Any]:
    """The page's picture, `png` or `jpeg`, as the tool's image over MCP, so it reaches the agent that asked as image
    content; elsewhere saved under the home and its path given."""
    kind = 'png' if found.get('png') else 'jpeg'
    picture = str(found.pop('png', '') or found.pop('jpeg', '') or '')
    if picture and ctx.surface == 'mcp':
        found['image'] = {'data': picture, 'mimeType': f'image/{kind}'}
    elif picture:
        import base64
        saved = home.home() / 'run' / 'looks' / f'look-{secrets.token_hex(4)}.{"png" if kind == "png" else "jpg"}'
        home.mkdir_private(saved.parent)
        home.write_private(saved, base64.b64decode(picture))
        found['file'] = str(saved)
    return found


CAPTURES = ('view', 'screen')


def capture(ctx: Context) -> dict[str, Any]:
    """What the person sees, for the agent that asks: `view`, a picture from their own 3D camera with the mouse
    pointer's ray drawn in, and the pointer's ray and what it takes; or `screen`, a frame of the screen, window or tab
    they share with agents from the page, refused with how to start one while nothing is shared."""
    source = str(ctx.nouns.get('source') or 'view')
    if source not in CAPTURES:
        raise Stop(f'{source} is not a capture: {", ".join(CAPTURES)}.', 'metaform web capture source=view')
    return pictured(ctx, ask_page(ctx, 'capture', source=source))


def select(ctx: Context) -> dict[str, Any]:
    return mascot_act(ctx, 'select', address=str(ctx.nouns['address']))


def camera(ctx: Context) -> dict[str, Any]:
    mode = str(ctx.nouns.get('mode') or '')
    if mode and mode not in CAMERAS:
        raise Stop(f'{mode} is not a camera mode: {", ".join(CAMERAS)}.', 'metaform web camera mode=whole')
    return mascot_act(ctx, 'camera', mode=mode, address=str(ctx.nouns.get('address') or ''))


def tab(ctx: Context) -> dict[str, Any]:
    if ctx.nouns['tab'] not in TABS:
        raise Stop(f'{ctx.nouns["tab"]} is not a tab: {", ".join(TABS)}.', 'metaform web tab brief')
    return mascot_act(ctx, 'tab', tab=str(ctx.nouns['tab']))


def open_on_page(ctx: Context) -> dict[str, Any]:
    if ctx.nouns['what'] not in OPENS:
        raise Stop(f'{ctx.nouns["what"]} cannot be opened: {", ".join(OPENS)}.', 'metaform web open board')
    what, which = str(ctx.nouns['what']), str(ctx.nouns.get('id') or '')
    # the page's `id` is the act's own, the one its answer comes back under, so the ticket or pane goes as `which`
    return {'act': 'open', 'what': what, 'id': which, **ask_page(ctx, 'open', what=what, which=which)}


def swap(ctx: Context) -> dict[str, Any]:
    if ctx.nouns['large'] not in ('2d', '3d'):
        raise Stop('The large area shows the 2d or the 3d map.', 'metaform web swap 3d')
    return mascot_act(ctx, 'swap', large=str(ctx.nouns['large']))


def flow(ctx: Context) -> dict[str, Any]:
    return mascot_act(ctx, 'flow', mode=str(ctx.nouns['mode']))


def physics(ctx: Context) -> dict[str, Any]:
    return mascot_act(ctx, 'physics', preset=str(ctx.nouns['preset']))


def viewing(ctx: Context) -> dict[str, Any]:
    return ask_page(ctx, 'viewing')


COMES = ('view', 'pointer', 'hit')


def come(ctx: Context) -> dict[str, Any]:
    """The calling agent's figure, or else the person's mascot, comes to the person to get their attention, as the
    agent chooses: where, whether it follows, and for how long; seconds=0 ends the approach."""
    to = str(ctx.nouns.get('to') or 'view')
    if to not in COMES:
        raise Stop(f'{to} is not where a body comes: {", ".join(COMES)}.', 'metaform web come to=view')
    seconds = number(ctx, 'seconds')
    follow = str(ctx.nouns.get('follow') or 'true').lower() not in ('false', 'no', '0')
    return mascot_act(ctx, 'come', to=to, follow=follow, **({'seconds': seconds} if seconds is not None else {}))


def embody(ctx: Context) -> dict[str, Any]:
    """The calling agent asks for a body of its own on the map, one of the characters: the page gives it unless the
    person chose its body already or another figure at work has that character."""
    if ctx.nouns['character'] not in CHARACTERS:
        raise Stop(f'{ctx.nouns["character"]} is not a character: {", ".join(CHARACTERS)}.', 'metaform web embody owl')
    return ask_page(ctx, 'embody', character=str(ctx.nouns['character']))


def gui_running(folder: Path) -> bool:
    """Whether this home's web GUI runs, so the verbs that act on its page or stop it are listed over MCP, MCP-004:
    its record, read from the home, names a process that is alive."""
    record = recorded()
    return record is not None and alive(int(record.get('pid') or 0))


# The page server this process runs, server.py's serve: the loader may run this module's subscriptions from a copy of
# its own, so they reach the server's open pages through the package the server imported, `served`.
SERVING: list[Any] = []


def served() -> list[Any]:
    package = sys.modules.get('metaform.modules.web')
    return list(cast(list[Any], getattr(package, 'SERVING', None) or []))


def voice_download(payload: dict[str, Any], ctx: Context) -> None:
    """What a model download has fetched, the voice module's `voice.download`, pushed to every open page, where its
    bar is drawn; only the page server has pages, so in any other process this does nothing."""
    for server in served():
        server.push({'topic': 'voice.download', 'payload': payload})


def carry_view(ctx: Context | None = None) -> list[str]:
    """The web module's start: the page's view, stored as global settings before the settings cleanup of 2026-10-15,
    carried into the person's view once per home, view.py."""
    from .view import carry
    return carry(ctx)


MODULE = Module(
    id='web',
    summary="Start and stop Metaform's web GUI, and serve web variants.",
    purpose="Starts Metaform's web GUI, where people see every registered project's map. Details: metaform help web.",
    details='One server per Metaform home serves every project on one fixed port, --web-port. It binds to '
            '--web-bind, loopback by default, where no token is needed; any other address also needs the token '
            'that start prints. metaform web runs start.',
    default='start',
    start=carry_view,
    subscriptions=(Subscription('voice.download', voice_download),),
    verbs=(
        # Starting the GUI writes the server's record under the home and starts its process; it reaches no agent and
        # nothing past this machine on its own, and stop ends that process. Neither changes the map.
        Verb('start', start, 'Start the web GUI, or show the address it already runs at.', switches=('web_debug',),
             effect='write', open_world=False, needs_project=False),
        Verb('stop', stop, 'Stop the web GUI.', effect='write', open_world=False, needs_project=False,
        listed=gui_running),
        # A restart is handed to a process of its own, so the page comes back even when the caller ends midway.
        Verb('restart', restart, 'Stop the web GUI and start it again; it comes back even if your session ends meanwhile.',
             effect='write', open_world=False, needs_project=False),
        # The mascot's and the figures' acts change no map and write nothing: each is told to the open pages, which
        # draw it, and what they see comes back from the page.
        Verb('say', say, "Say a short line in the person's mascot's word bubble on the map.",
             nouns=(Noun('text', 'What the mascot says, a line or two.'),
                    Noun('speak', 'true says it aloud too, where the person\'s voice settings speak; the answer says if it was.',
                         required=False)), effect='read', open_world=False, listed=gui_running),
        Verb('go', go, "Walk your figure, or else the person's mascot, to a part of the map and face it; answers where it ended up.",
             nouns=(Noun('address', 'The address of the element it goes to.'),
                    Noun('distance', 'How far from its surface to stand, in the map\'s units, as see measures them.', required=False),
                    Noun('height', 'How far above it to stand, in the map\'s units.', required=False)),
             effect='read', open_world=False, listed=gui_running),
        Verb('turn', turn, "Turn your figure, or else the person's mascot, to face a part of the map, or by some degrees, left negative.",
             nouns=(Noun('address', 'The address of the element to face.', required=False),
                    Noun('degrees', 'How far to turn instead, in degrees, left negative, right positive.', required=False)),
             effect='read', open_world=False, listed=gui_running),
        Verb('point', point, "Turn your figure, or else the person's mascot, toward a part of the map and gesture at it.",
             nouns=(Noun('address', 'The address of the element it points at.'),), effect='read', open_world=False,
             listed=gui_running),
        Verb('emote', emote, "Show a feeling with your figure, or else the person's mascot: wave, think, celebrate, shrug or sleep.",
             nouns=(Noun('emote', 'One of wave, think, celebrate, shrug, sleep.'),), effect='read', open_world=False,
             listed=gui_running),
        # The mascot's body in the map's space: only the layout's positions move, as a node dragged by hand does.
        Verb('move', move, "Move your figure, or else the person's mascot, through the 3D map: to an element, a point, or a step from where it faces.",
             nouns=(Noun('address', 'The element it goes to.', required=False),
                    Noun('point', 'A point x,y,z in the units web_see measures.', required=False),
                    Noun('forward', 'A step ahead, negative back.', required=False),
                    Noun('right', 'A step to its right, negative left.', required=False),
                    Noun('up', 'A step up, negative down.', required=False)), effect='read', open_world=False,
                    listed=gui_running),
        Verb('push', push, "Have the person's mascot shove an element on the 3D map; its joins pull its neighbours along.",
             nouns=(Noun('address', 'The element it shoves.'),
                    Noun('direction', 'away from the mascot, up, down, or the address of an element to shove it toward.',
                         required=False),
                    Noun('strength', 'From 0 to 1, capped so the map is never flung apart; 0.5 when not given.',
                         required=False)), effect='read', open_world=False, listed=gui_running),
        Verb('drag', drag, "Have the person's mascot carry an element of the 3D map to a point or beside another; it holds it until web_drop.",
             nouns=(Noun('address', 'The element it carries, one at a time.'),
                    Noun('point', 'A point x,y,z to carry it to.', required=False),
                    Noun('beside', 'An element to set it down beside.', required=False)), effect='read', open_world=False,
                    listed=gui_running),
        Verb('drop', drop, "Have the person's mascot let go of the element it carries; the map settles round it.",
             effect='read', open_world=False, listed=gui_running),
        Verb('take', take, "Hold your figure still where it stands, or the person's mascot under your lead past your turn, until web_release.",
             nouns=(Noun('reason', 'Why, in a few words, said in its bubble.'),), effect='read', open_world=False,
             listed=gui_running),
        Verb('release', release, "Let your figure, or the person's mascot, go its own way again from where it stands.",
             effect='read', open_world=False, listed=gui_running),
        Verb('see', see, 'List what your figure perceives on the 3D map now: the nearest parts in view and not hidden, how far, which way.',
             nouns=(Noun('address', 'Turn to face this element first.', required=False),), effect='read', open_world=False,
             listed=gui_running),
        Verb('look', look, "A picture of the 3D map from your figure's own eyes, with what it sees.",
             nouns=(Noun('address', 'Turn to face this element first.', required=False),), effect='read', open_world=False,
             listed=gui_running),
        Verb('select', select, "Select an element or a join on the person's page, the mascot walking to it.",
             nouns=(Noun('address', 'The element\'s address, or a join as receiver>provider.'),), effect='read',
             open_world=False, listed=gui_running),
        Verb('camera', camera, "Set the person's 3D view to work, whole, zoom or free, or fly it to an element.",
             nouns=(Noun('mode', 'work, the agents at work in view; whole, zoom or free.', required=False),
                    Noun('address', 'An element to fly the camera to.', required=False)), effect='read', open_world=False,
                    listed=gui_running),
        Verb('tab', tab, "Open a tab of the person's side panel: object, brief, provenance or prompt.",
             nouns=(Noun('tab', 'object, brief, provenance or prompt.'),), effect='read', open_world=False,
             listed=gui_running),
        Verb('open', open_on_page, "Open the board, a ticket, the settings screen or a pane on the person's page.",
             nouns=(Noun('what', 'board, ticket, settings or pane.'),
                    Noun('id', 'The ticket\'s id or the pane\'s id.', required=False)), effect='read', open_world=False,
                    listed=gui_running),
        Verb('swap', swap, "Show the 2d or the 3d map in the large area of the person's page.",
             nouns=(Noun('large', '2d or 3d.'),), effect='read', open_world=False, listed=gui_running),
        Verb('flow', flow, "Set which joins the dots flow along on the person's page: off, selected, all or live.",
             nouns=(Noun('mode', 'off, selected, all or live.'),), effect='read', open_world=False, listed=gui_running),
        Verb('physics', physics, "Set how the person's 3D map lays itself out, a physics preset, for the page.",
             nouns=(Noun('preset', 'A physics preset, as the page names them, such as organic or clusters.'),),
             effect='read', open_world=False, listed=gui_running),
        Verb('embody', embody, 'Take a body of your own on the map, one of the characters, unless the person chose yours.',
             nouns=(Noun('character', 'The character, such as owl, beetle or puffer.'),), effect='read', open_world=False,
             listed=gui_running),
        Verb('viewing', viewing, 'Read what the person is looking at now: the selection, each view, the open panes, the nodes in view and where their 3D view is.',
             effect='read', open_world=False, listed=gui_running),
        Verb('come', come, "Bring your figure, or else the person's mascot, to the person to get their attention: their view, pointer or what it points at.",
             nouns=(Noun('to', 'view, in front of their 3D view, the default; pointer, under their mouse pointer; or hit, beside what the pointer points at.',
                         required=False),
                    Noun('seconds', 'How long it stays, 10 when not given, at most 3600; 0 ends the approach now.', required=False),
                    Noun('follow', 'true, the default, keeps up with the view or the pointer as it moves; false stays where it went.',
                         required=False)), effect='read', open_world=False, listed=gui_running),
        Verb('capture', capture, "A picture of what the person sees: their 3D view with the mouse pointer's ray, or the screen they share.",
             nouns=(Noun('source', 'view, their own 3D view, the default; or screen, the screen, window or tab they share with agents.',
                         required=False),), effect='read', open_world=False, listed=gui_running),
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
        # The Default workspace is the page as written: the 2D map in the large area, where its names are read, and
        # the 3D map above the node's tabs on the right, keeping the whole in view beside it. Which of the two takes
        # the large area stays this browser's choice while the arrangement is that one, as Swap always made it.
        Pane('map2d', '2D map', 'See the whole map flat, and walk it node by node with the keys.', icon='map',
             page='map2d', area='main', group='stage', visible=True, order=5, min_width=280, min_height=200),
        Pane('map3d', '3D map', 'See the map in depth, with the agents at work on it.', icon='cube', page='map3d',
             area='right', group='overview', visible=True, order=5, min_width=320, min_height=200),
        Pane('runs', 'Workflow runs', 'See the workflow runs at work, answer one waiting on you and resume it, or '
             'cancel one.', icon='play', page='runs', area='right', group='chat', order=130, min_width=320),
    ),
    settings_category='map',
)
