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
# Whether the page is laid out by the workspace, its toolbar, panes and Window menu, or as it was written before them:
# the side column with its tabs beside the large map. A fork in how the page is arranged, so it is the person's. Off
# until the workspace's Default reproduces the page as written and every check of it passes with the workspace on.
settings.boolean('web_panes', False, scope='global',
                 help='Lay the web GUI out by the workspace: the toolbar, docked and floating panes, the Window menu.',
                 details='Off, the page keeps the side column with its tabs beside the large map, and no toolbar; '
                         'the workspace settings are kept for when it is on again.')
# How the 3D map is drawn. Shapes tell an element's artifact type before any text is read: code, document, media,
# data, collection, upstream and downstream each have their own, in 2D and in 3D; off draws every element as before.
settings.boolean('web_node_shapes', True, scope='global',
                 help='Draw each element in the shape of its artifact type, the first segment of its address.',
                 details='code is a box, document a page, media a screen, data a cylinder, collection a stack, '
                         'upstream an input and downstream an output, in the 2D and the 3D map. Off draws every '
                         'element in one shape, as the maps did before.')
# How much the 3D map draws. clean is the map as it has always been; ultra draws it in outer space, page/ultra.js:
# a starfield and a faint nebula behind it, each element a celestial body of its artifact type, the joins as
# filaments of light and a glow on what is bright. It steps its own quality down when the frame rate stays low, and
# an idle map still rests. The 2D map is the same in both.
# Giving an agent in the chat a body on the map: the page offers it once per conversation, in its thread, at a pause
# (a turn ended or a ticket closed, never while it works), after web_embody_turns turns or web_embody_minutes minutes,
# whichever comes first. Asked too soon, the offer interrupts a conversation that has not shown it is worth keeping;
# about eight turns or twenty minutes is a conversation the person is staying with. always gives each conversation the
# person's last choice, or the mascot to the system agent; never makes no offer. The figure itself is the flow's,
# `window.metaform.embody`.
settings.choice('web_embody', ['offer', 'always', 'never'], 'offer', scope='global',
                help='Whether the chat offers to give its agent a body on the map: offer, always or never.',
                details='offer asks once per conversation, at a pause, after web_embody_turns turns or '
                        'web_embody_minutes minutes; always gives every conversation your last choice, or the mascot '
                        'to your system agent; never makes no offer. The avatar in the chat\'s head, its menu or B '
                        'give or change a body at any time.')
settings.number('web_embody_turns', 8, min=0, max=100, scope='global',
                help='Turns of a chat before it offers to give its agent a body; 0 offers at once.')
settings.number('web_embody_minutes', 20, min=0, max=600, scope='global',
                help='Minutes of a chat before it offers to give its agent a body, if its turns come later.')
# The 3D map's names: outward stands each as a sign facing away from the map's middle, turned round where the eye is
# behind it so it never reads mirrored; facing turns each to the eye.
settings.choice('web_signs', ['outward', 'facing'], 'outward', scope='global',
                help="How the 3D map's names stand: outward from the map's middle, or facing you.",
                details='outward keeps each name a sign in the scene, facing away from the map\'s middle, upright in '
                        'the map; seen from behind it turns round, so its letters always read as written. facing turns '
                        'every name to the eye. S in the web GUI switches them.')
settings.choice('web_lens', ['natural', 'wide', 'fisheye'], 'natural', scope='global',
                help="The 3D map's lens: natural, wide, or fisheye, how far the view opens as its pane grows tall.",
                details='The 3D map keeps a name the same size when its pane changes height, by opening or narrowing '
                        'its field of view. natural holds it between 30 and 55 degrees, wide up to 80, and fisheye up '
                        'to 120, the view bending round the map as the 3D map takes the large area.')
settings.choice('web_graphics', ['clean', 'ultra'], 'clean', scope='global',
                help='How the 3D map is drawn: clean, or ultra, the map in outer space.',
                details='ultra draws a starfield and a nebula behind the map, each element as a planet, star or '
                        'other body by its artifact type, the joins as filaments of light, and a soft glow on the '
                        'selection, the flow and the agents. It draws less when the frame rate stays under 40 a '
                        'second. U in the web GUI switches between the two.')
# The dots that flow along the joins are the 3D map's one motion that never ends by itself; drawing them costs the
# machine every frame. They flow for this long after the map was last touched or changed, then the map draws nothing
# until the next act, so a page left open costs nothing.
settings.number('web_flow_seconds', 30, min=0, max=3600, scope='global',
                help='Seconds the dots along the joins keep flowing after the map was last touched or changed.',
                details='After this the 3D map draws no frame until something on it moves or the person acts. 0 '
                        'stops the flow as soon as nothing else moves. With reduced motion nothing flows at all.')
# How often each join pulses: after each request and reply a join waits (random + random) times this, so the waits
# bunch around it with now and then a quick one or a slow one, each join drawing its own, and nothing pulses in step.
# In milliseconds, since a setting's number is whole.
# Which joins the dots flow along: off draws none, and no agents' activity either; selected, the selected node's joins;
# all, every join; live, only what agents really do. The map's bar, the View menu and the key D choose it on the page.
settings.choice('web_flow_mode', ['off', 'selected', 'all', 'live'], 'selected', scope='global',
                help="Which joins the dots flow along: off, selected (the selection's joins), all, or live.",
                details="selected draws the flow on the selected node's joins only, so a large map costs nothing; all "
                        "draws it on every join; live draws only what agents really do; off draws nothing, agents' "
                        'activity included. A change eases the dots in or out.')
settings.number('web_pulse_ms', 2000, min=200, max=30000, scope='global',
                help='The usual wait, in milliseconds, between one request and reply on a join and the next.',
                details='Each join waits (random + random) times this after each cycle, a fresh wait every time, so '
                        'the flow bunches about this pace and never pulses in step, in the 3D and the 2D map.')
settings.boolean('web_idle_flow', False, scope='global',
                 help='Keep the dots flowing slowly for as long as the page is open, past web_flow_seconds.',
                 details='On, an idle 3D map is still drawn 15 times a second so the flow never stops, as the map '
                         'was drawn before; off, it stops and the machine rests.')
# What agents really do is drawn in the flow's own looks, a little larger and brighter than the flow the map shows of
# itself: a session starting, each part of the map a tool call reaches, and each note, item or work record written on
# a node. It comes from the page's event stream as it happens and costs nothing while nothing happens.
settings.boolean('web_live_flow', True, scope='global',
                 help="Draw agents' real activity on the map: requests to the parts a tool call reaches, records "
                      'landing where something is written.',
                 details='Off, the map shows only the flow it draws of its own joins. With reduced motion nothing '
                         'flows at all.')
# The characters the agents' figures are drawn as, page/agent-glyphs, read from the files so the choices are the
# characters there are.
CHARACTERS = sorted(path.stem for path in (Path(__file__).parent / 'page' / 'agent-glyphs').glob('*.svg'))
# The person's mascot: one of the characters stands for the person on the map, goes to what they select, greets the
# agent they chat with, calls their attention to what needs them, and sleeps while they are away. It is never given
# to an agent. none draws no mascot.
settings.choice('web_mascot', ['none', *CHARACTERS], 'none', scope='global',
                help='The character that stands for you on the map, or none.',
                details='It goes to what you select and waits beside it, greets the agent you chat with, brings you '
                        'a note when something needs you, and sleeps while you are away. It never takes a click.')
settings.choice('web_mascot_mischief', ['calm', 'playful', 'chaotic'], 'playful', scope='global',
                help='How much the mascot does of its own accord: calm, playful or chaotic.',
                details='calm only calls your attention and never wanders; playful wanders now and then and nudges a '
                        'node it passes; chaotic does both more often. It never takes the pointer or blocks a click.')
settings.items('web_agent_glyphs', [], scope='global',
               help='The character for each agent type, as type=character, such as claude=owl or codex=beetle.',
               details='Without one, characters are given as before, so no two agents at work look alike; a '
                       'character already at work, or the mascot, is never given twice.')
# Which way the 2D map runs. auto lays it out each way for its pane and keeps the one drawn largest with the whole map
# in view; across and down hold it to one direction whatever the pane's shape.
settings.choice('web_map_direction', ['auto', 'across', 'down'], 'auto', scope='global',
                help='Which way the 2D map runs: auto, across (left to right) or down (top to bottom).',
                details='auto lays the map out left to right and top to bottom, and each folded into rows or '
                        'columns when it is long, and keeps the one its pane shows largest with the whole map in '
                        'view; it is laid out again when the pane changes shape. across and down hold it to that '
                        'direction, unfolded.')
# The large map's bar, with its modes, Fit, the 2D map's direction and the 3D map's physics, at the top right of the
# large area. auto keeps the display clean, since nothing shows until the person rests the pointer where the bar sits.
settings.choice('web_mode_bar', ['auto', 'shown', 'keys'], 'auto', scope='global',
                help="When the large map's bar shows: auto, shown or keys.",
                details='auto brings it out when the pointer rests under a second in the strip it occupies at the top '
                        'right of the large map, and puts it away fifteen seconds after the pointer leaves that '
                        'strip; while it is out the map below it is that much shorter, so it covers nothing. shown '
                        'keeps it out; keys keeps it away and lets it peek only when a key changes the mode, the '
                        'direction or the physics. M toggles between shown and the other choice.')
# Node zoom: each node selected in the 3D map is flown to, framed close with its neighbours, in either pane and
# whatever framing or physics is in force; it is what shows a part in its place. Off, a selection never moves the
# camera; Whole and Free then hold the view.
# What the maps say of what the pointer is on: its name across the top where the map shows none that can be read, and
# a card of its details at the lower right, both by default.
settings.choice('web_hover_info', ['name+summary', 'name', 'summary', 'off'], 'name+summary', scope='global',
                help='What the maps say of what the pointer is on: name+summary, name, summary or off.',
                details='name is the hovered thing\'s name across the top of the map, shown only where the map has '
                        'no name of its own that can be read, an edge always; summary is the card at the lower right '
                        'with its kind, address and purpose or EF, an agent\'s work and status. I in the web GUI, the '
                        'map bar and the View menu choose it.')
settings.boolean('web_node_zoom', True, scope='global',
                 help='Fly the 3D camera to each node selected and frame it with its neighbours.',
                 details='On, every selection in 3D flies there, in the large and the small pane, whatever Whole, '
                         'Free or physics is chosen; those frame the map while nothing is being flown to. Off, a '
                         'selection never moves the camera. Z in the web GUI, the map bar and the View menu toggle it.')
# The window of the agents at work: auto slides it out as an agent starts work and away a few seconds after the last
# one stops; open keeps it out, hidden keeps it away.
settings.choice('web_agents_window', ['auto', 'open', 'hidden'], 'auto', scope='global',
                help='When the window of the agents at work shows: auto, open or hidden.',
                details='auto shows it while any agent is at work and slides it away a few seconds after the last '
                        'one stops; open pins it out, hidden pins it away. A in the web GUI, or the View menu, '
                        'changes it.')
# The 3D map's layout: organic, as it has always been, or flat, everything on one plane with the names facing you.
PHYSICS = ('organic', 'flat')
settings.choice('web_physics', list(PHYSICS), 'organic', scope='global',
                help="The 3D map's layout: organic, or flat.",
                details='organic is the natural layout; flat lays the map on one plane with its names facing you. '
                        'Alt+1 and Alt+2 choose them in the web GUI.')
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
    started = starting(ctx)
    # `web.started`, so a module that serves beside the page starts with it, such as twilio's phone bridge when the
    # person has turned it on; a subscriber's failure is its own and never the page's.
    with contextlib.suppress(Exception):
        ctx.publish('web.started', {'project': ctx.project, 'folder': str(ctx.folder), 'state': started['state']})
    return started


def starting(ctx: Context) -> dict[str, Any]:
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


# The person's mascot, web_mascot, and every agent's figure, VIEW-005: what they do and see on the open page. Each act
# goes to the running web GUI, which hands it to every open page of the project with an id of its own; an act that asks
# something, what a figure sees, a picture from its eyes, or what the person is looking at, waits up to five seconds
# for the page's answer. Nothing is written. With no page open it is refused, with what to do next. An agent asks from
# its own figure, METAFORM_WORK, the ticket its runner gave it; the person's system agent and the person from the
# mascot.
EMOTES = ('wave', 'think', 'celebrate', 'shrug', 'sleep')
PUSH_WAYS = ('away', 'up', 'down')  # a push's direction, else the address of an element it is pushed toward
TABS = ('object', 'brief', 'provenance', 'prompt')
OPENS = ('board', 'ticket', 'settings', 'pane')
CAMERAS = ('whole', 'zoom', 'free')


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
        raise Stop(str(answer.get('error') or f'The page refused it ({response.status}).'),
                   str(answer.get('next') or 'open the page on this project'))
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
    return mascot_act(ctx, 'say', text=str(ctx.nouns['text']))


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
    found = ask_page(ctx, 'look', address=str(ctx.nouns.get('address') or ''))
    picture = str(found.pop('png', '') or '')
    if picture and ctx.surface == 'mcp':
        found['image'] = {'data': picture, 'mimeType': 'image/png'}
    elif picture:
        import base64
        saved = home.home() / 'run' / 'looks' / f'look-{secrets.token_hex(4)}.png'
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_bytes(base64.b64decode(picture))
        found['file'] = str(saved)
    return found


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
    return mascot_act(ctx, 'open', what=str(ctx.nouns['what']), id=str(ctx.nouns.get('id') or ''))


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


def embody(ctx: Context) -> dict[str, Any]:
    """The calling agent asks for a body of its own on the map, one of the characters: the page gives it unless the
    person chose its body already or another figure at work has that character."""
    if ctx.nouns['character'] not in CHARACTERS:
        raise Stop(f'{ctx.nouns["character"]} is not a character: {", ".join(CHARACTERS)}.', 'metaform web embody owl')
    return ask_page(ctx, 'embody', character=str(ctx.nouns['character']))


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
        # The mascot's and the figures' acts change no map and write nothing: each is told to the open pages, which
        # draw it, and what they see comes back from the page.
        Verb('say', say, "Say a short line in the person's mascot's word bubble on the map.",
             nouns=(Noun('text', 'What the mascot says, a line or two.'),), effect='read', open_world=False),
        Verb('go', go, "Walk the person's mascot to a part of the map, or to a viewpoint near it.",
             nouns=(Noun('address', 'The address of the element it goes to.'),
                    Noun('distance', 'How far from it to stand, in the map\'s units, as see measures them.', required=False),
                    Noun('height', 'How far above it to stand, in the map\'s units.', required=False)),
             effect='read', open_world=False),
        Verb('turn', turn, "Turn the person's mascot to face a part of the map, or by some degrees, left is negative.",
             nouns=(Noun('address', 'The address of the element to face.', required=False),
                    Noun('degrees', 'How far to turn instead, in degrees, left negative, right positive.', required=False)),
             effect='read', open_world=False),
        Verb('point', point, "Turn the person's mascot toward a part of the map and gesture at it.",
             nouns=(Noun('address', 'The address of the element it points at.'),), effect='read', open_world=False),
        Verb('emote', emote, "Show a feeling with the person's mascot: wave, think, celebrate, shrug or sleep.",
             nouns=(Noun('emote', 'One of wave, think, celebrate, shrug, sleep.'),), effect='read', open_world=False),
        # The mascot's body in the map's space: only the layout's positions move, as a node dragged by hand does.
        Verb('move', move, "Move the person's mascot freely through the 3D map: to an element, a point, or a step from its heading.",
             nouns=(Noun('address', 'The element it goes to.', required=False),
                    Noun('point', 'A point x,y,z in the units web_see measures.', required=False),
                    Noun('forward', 'A step ahead, negative back.', required=False),
                    Noun('right', 'A step to its right, negative left.', required=False),
                    Noun('up', 'A step up, negative down.', required=False)), effect='read', open_world=False),
        Verb('push', push, "Have the person's mascot shove an element on the 3D map; its joins pull its neighbours along.",
             nouns=(Noun('address', 'The element it shoves.'),
                    Noun('direction', 'away from the mascot, up, down, or the address of an element to shove it toward.',
                         required=False),
                    Noun('strength', 'From 0 to 1, capped so the map is never flung apart; 0.5 when not given.',
                         required=False)), effect='read', open_world=False),
        Verb('drag', drag, "Have the person's mascot carry an element of the 3D map to a point or beside another; it holds it until web_drop.",
             nouns=(Noun('address', 'The element it carries, one at a time.'),
                    Noun('point', 'A point x,y,z to carry it to.', required=False),
                    Noun('beside', 'An element to set it down beside.', required=False)), effect='read', open_world=False),
        Verb('drop', drop, "Have the person's mascot let go of the element it carries; the map settles round it.",
             effect='read', open_world=False),
        Verb('take', take, "Hold the person's mascot under your lead past your turn, its own will paused, until web_release.",
             nouns=(Noun('reason', 'Why, in a few words, said in its bubble.'),), effect='read', open_world=False),
        Verb('release', release, "Give the person's mascot back its own will; it goes on from where it stands.",
             effect='read', open_world=False),
        Verb('see', see, 'List what your figure sees on the 3D map now: each node in view, how far, which way, and the nearest.',
             nouns=(Noun('address', 'Turn to face this element first.', required=False),), effect='read', open_world=False),
        Verb('look', look, "A picture of the 3D map from your figure's own eyes, with what it sees.",
             nouns=(Noun('address', 'Turn to face this element first.', required=False),), effect='read', open_world=False),
        Verb('select', select, "Select an element or a join on the person's page, the mascot walking to it.",
             nouns=(Noun('address', 'The element\'s address, or a join as receiver>provider.'),), effect='read',
             open_world=False),
        Verb('camera', camera, "Set the person's 3D view to whole, zoom or free, or fly it to an element.",
             nouns=(Noun('mode', 'whole, zoom or free.', required=False),
                    Noun('address', 'An element to fly the camera to.', required=False)), effect='read', open_world=False),
        Verb('tab', tab, "Open a tab of the person's side panel: object, brief, provenance or prompt.",
             nouns=(Noun('tab', 'object, brief, provenance or prompt.'),), effect='read', open_world=False),
        Verb('open', open_on_page, "Open the board, a ticket, the settings screen or a pane on the person's page.",
             nouns=(Noun('what', 'board, ticket, settings or pane.'),
                    Noun('id', 'The ticket\'s id or the pane\'s id.', required=False)), effect='read', open_world=False),
        Verb('swap', swap, "Show the 2d or the 3d map in the large area of the person's page.",
             nouns=(Noun('large', '2d or 3d.'),), effect='read', open_world=False),
        Verb('flow', flow, "Set which joins the dots flow along on the person's page: off, selected, all or live.",
             nouns=(Noun('mode', 'off, selected, all or live.'),), effect='read', open_world=False),
        Verb('physics', physics, "Set how the person's 3D map lays itself out, a physics preset, for the page.",
             nouns=(Noun('preset', 'A physics preset, as the page names them, such as organic or clusters.'),),
             effect='read', open_world=False),
        Verb('embody', embody, 'Take a body of your own on the map, one of the characters, unless the person chose yours.',
             nouns=(Noun('character', 'The character, such as owl, beetle or puffer.'),), effect='read', open_world=False),
        Verb('viewing', viewing, 'Read what the person is looking at now: the selection, each view, the open panes and the nodes in view.',
             effect='read', open_world=False),
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
)
