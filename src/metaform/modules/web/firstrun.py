"""The first screen's endpoints: what a newcomer's two choices need, and the hints each person has dismissed.

`GET /api/first-run/folders?path=` lists the folders in one folder of this machine, starting at the person's own home
folder, each with the project it is registered as, for the welcome's folder picker. `POST /api/first-run/map` registers
the folder chosen as a project, named for the folder as `metaform add project` would be given it, or answers with the
project it already is; the page then opens the intake on it. `POST /api/first-run/demo` starts `metaform demo --reset`
in a process of its own and answers with the address it prints, which the page goes to. All three are the owner's (admin
behind a Node's gate), since they read this machine's folders and start processes.

`GET /api/hints` and `POST /api/hints` keep the page's first-run hints each person has dismissed, in the Metaform home,
per account behind a Node's gate and the owner's otherwise, so a hint dismissed in one browser stays gone in every one.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from metaform import home
from metaform.module import Stop

if TYPE_CHECKING:
    from .server import Handler

PREFIX = '/api/first-run'
HINTS = '/api/hints'
HINT_NAME = re.compile(r'[a-z][a-z0-9-]{0,31}')
ADDRESS = re.compile(r'https?://[\w.:\[\]-]+/\S*')
DEMO_WAIT = 45.0  # seconds the demo may take to print its address; its own target is 30
FOLDERS_SHOWN = 400
NEW_PROCESS_GROUP = 0x00000200  # Windows' CREATE_NEW_PROCESS_GROUP, which subprocess has only on Windows
_demo_lock = threading.Lock()
_demo: dict[str, Any] = {}  # the demo this server started: its process and the address it printed
_hints_lock = threading.Lock()


def answer(handler: Handler, method: str, path: str, query: dict[str, list[str]]) -> None:
    """Route one request under /api/first-run, or /api/hints. The server has checked its Host, token and class."""
    if method == 'POST':
        if not handler.same_origin():
            return handler.send(403, {'error': "A write is taken only from the web GUI's own page."})
        if (handler.headers.get('Content-Type') or '').split(';')[0].strip().lower() != 'application/json':
            return handler.send(415, {'error': 'A write takes a JSON body.'})
        try:
            body: Any = handler.json_body()
        except ValueError:
            return handler.send(400, {'error': 'The body is not JSON.'})
        given = cast(dict[str, Any], body) if isinstance(body, dict) else {}
        writes = {f'{PREFIX}/map': map_folder, f'{PREFIX}/demo': start_demo, HINTS: dismiss_hint}
        if path not in writes:
            return handler.send(404, {'error': f'No such write: {path}.'})
        return writes[path](handler, given)
    if path == f'{PREFIX}/folders':
        return folders(handler, query.get('path', [''])[-1])
    if path == HINTS:
        return handler.send(200, {'dismissed': sorted(_hints().get(_account(handler), []))})
    return handler.send(404, {'error': f'Nothing at {path}.'})


def folders(handler: Handler, given: str) -> None:
    """The folders inside one folder, hidden ones left out, with the folder above it and the project each is."""
    try:
        at = Path(given).expanduser().resolve() if given else Path.home().resolve()
    except (OSError, RuntimeError):
        at = Path.home()
    if not at.is_dir():
        return handler.send(404, {'error': f'There is no folder at {at}.', 'next': 'Choose another folder.'})
    registered = {str(Path(found.path).resolve()): found.project_id for found in home.projects()}
    try:
        inside = sorted((entry for entry in at.iterdir() if not entry.name.startswith('.') and _folder(entry)),
                        key=lambda entry: entry.name.lower())
    except OSError:
        return handler.send(403, {'error': f'{at} cannot be read.', 'next': 'Choose another folder.'})
    handler.send(200, {
        'path': str(at), 'parent': str(at.parent) if at.parent != at else None, 'home': str(Path.home()),
        'project': registered.get(str(at)),
        'folders': [{'name': entry.name, 'path': str(entry), 'project': registered.get(str(entry.resolve()))}
                    for entry in inside[:FOLDERS_SHOWN]],
        'more': max(0, len(inside) - FOLDERS_SHOWN)})


def _folder(entry: Path) -> bool:
    try:
        return entry.is_dir()
    except OSError:
        return False


def map_folder(handler: Handler, given: dict[str, Any]) -> None:
    """The folder chosen registered as a project named for it, or the project it already is."""
    raw = given.get('path')
    if not isinstance(raw, str) or not raw.strip():
        return handler.send(400, {'error': 'No folder was chosen.', 'next': 'Choose the folder of your project.'})
    folder = Path(raw).expanduser().resolve()
    if not folder.is_dir():
        return handler.send(400, {'error': f'There is no folder at {folder}.', 'next': 'Choose another folder.'})
    metaform_home = home.home().resolve()
    if folder == metaform_home or metaform_home in folder.parents:
        return handler.send(400, {'error': "That is Metaform's own folder, not a project.",
                                  'next': 'Choose the folder of your project.'})
    for found in home.projects():
        if Path(found.path).resolve() == folder:
            return handler.send(200, {'project': found.project_id, 'added': False})
    project_id = _free_id(_id_for(folder))
    try:
        home.add_project(project_id, folder)
    except Stop as error:
        return handler.refuse(error, 400)
    handler.send(200, {'project': project_id, 'added': True})


def _id_for(folder: Path) -> str:
    """A project id from a folder's name, held to the rule `add_project` holds an id to."""
    made = re.sub(r'[^a-z0-9_-]+', '-', folder.name.lower()).strip('-_')
    return made[:48] or 'project'


def _free_id(wanted: str) -> str:
    taken = {found.project_id for found in home.projects()}
    if wanted not in taken:
        return wanted
    number = 2
    while f'{wanted}-{number}' in taken:
        number += 1
    return f'{wanted}-{number}'


def start_demo(handler: Handler, given: dict[str, Any]) -> None:
    """`metaform demo` started in a process of its own, answered with the address it prints. A demo this server started
    that still runs is answered again rather than started twice; one already running elsewhere is answered with the
    address its refusal names. It starts fresh, `--reset`, so what an earlier demo stopped uncleanly left behind,
    such as a ticket still claimed, never stops this one; the demo takes its lock before it resets. What it prints
    goes to `run/demo.log` in the home, not a pipe, so it lives on whatever becomes of this server, and what went wrong
    can be read there."""
    del given
    with _demo_lock:
        running = _demo.get('process')
        if running is not None and running.poll() is None and _demo.get('address'):
            return handler.send(200, {'address': _demo['address']})
        env = {key: value for key, value in os.environ.items()
               if key not in ('METAFORM_ROLE', 'METAFORM_SESSION', 'METAFORM_WORK', 'METAFORM_NODE')}
        # webbrowser.open runs the BROWSER command first and stops at the first that succeeds: a command that does
        # nothing and succeeds keeps the demo from opening a second window, since the page that asked goes there
        env['BROWSER'] = 'cmd /c rem %s' if sys.platform == 'win32' else 'true %s'
        env['PYTHONUNBUFFERED'] = '1'  # each line it prints reaches the log as it is printed, its address first
        log = home.home() / 'run' / 'demo.log'
        home.mkdir_private(log.parent)
        # a group of its own, so an interrupt reaches it and it stops its agents and web GUI as Ctrl+C does
        windows = sys.platform == 'win32'
        try:
            descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, 'wb') as output:
                process = subprocess.Popen([sys.executable, '-m', 'metaform', 'demo', '--reset'],
                                           stdin=subprocess.DEVNULL,
                                           stdout=output, stderr=subprocess.STDOUT, env=env,
                                           cwd=str(home.home()), start_new_session=not windows,
                                           creationflags=NEW_PROCESS_GROUP if windows else 0)
        except OSError as error:
            return handler.send(500, {'error': f'The demo could not start: {error.strerror or error}.',
                                      'next': 'Run metaform demo in a terminal.'})
        address, said = _address_of(process, log)
        if address is None:
            return handler.send(502, _demo_failed(process, said))
        _demo.update(process=process, address=address)
    handler.send(200, {'address': address})


def _address_of(process: subprocess.Popen[bytes], log: Path) -> tuple[str | None, list[str]]:
    """The first address the demo prints, read from its log within DEMO_WAIT seconds, and the lines it printed by
    then; a demo that gives none in time is interrupted, so it stops what it started."""
    deadline = time.monotonic() + DEMO_WAIT
    said: list[str] = []
    while True:
        ended = process.poll() is not None  # read once more after it ends, for what it said last
        try:
            said = log.read_text(encoding='utf-8', errors='replace').splitlines()
        except OSError:
            said = []
        for line in said:
            hit = ADDRESS.search(line)
            if hit:
                return hit.group(0).rstrip('",;.'), said
        if ended:
            return None, said
        if time.monotonic() > deadline:
            _interrupt(process)
            return None, said
        time.sleep(0.2)


def _interrupt(process: subprocess.Popen[bytes]) -> None:
    """Ctrl+C for a demo that gave no address in time: it stops what it started itself, its agents and its web GUI,
    which a plain terminate would leave running."""
    try:
        if sys.platform == 'win32':
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(process.pid, signal.SIGINT)
    except OSError:
        return


def _demo_failed(process: subprocess.Popen[bytes], said: list[str]) -> dict[str, str]:
    """Why the demo gave no address, in the words its own command said, never a stack."""
    if process.poll() is None:
        return {'error': 'The demo did not start in time.', 'next': 'Run metaform demo in a terminal.'}
    told = [line for line in said if line.startswith(('Error:', 'Next:'))]
    error = next((line[6:].strip() for line in told if line.startswith('Error:')), '')
    if 'Unknown command' in error:
        return {'error': 'This version of Metaform has no demo yet.', 'next': 'Map your own project instead.'}
    following = next((line[5:].strip() for line in told if line.startswith('Next:')), '')
    return {'error': error or 'The demo stopped before it started.', 'next': following or 'Run metaform demo in a '
            'terminal to see why.'}


def _account(handler: Handler) -> str:
    """Whose hints these are: the signed-in account behind a Node's gate, else the home's owner."""
    from .server import ACCOUNT_HEADER
    return (handler.headers.get(ACCOUNT_HEADER) or '') if handler.gui.gate is not None else ''


def _hints_file() -> Path:
    return home.home() / 'web' / 'hints.json'


def _hints() -> dict[str, list[str]]:
    try:
        kept: Any = json.loads(_hints_file().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    if not isinstance(kept, dict):
        return {}
    return {str(key): [str(name) for name in cast(list[Any], value)]
            for key, value in cast(dict[Any, Any], kept).items() if isinstance(value, list)}


def dismiss_hint(handler: Handler, given: dict[str, Any]) -> None:
    """One hint dismissed for good by the person who dismissed it."""
    name = given.get('hint')
    if not isinstance(name, str) or not HINT_NAME.fullmatch(name):
        return handler.send(400, {'error': 'No hint was named.'})
    account = _account(handler)
    with _hints_lock:
        kept = _hints()
        mine = sorted({*kept.get(account, []), name})
        kept[account] = mine
        home.mkdir_private(_hints_file().parent)
        home.write_private(_hints_file(), json.dumps(kept, indent=1))
    handler.send(200, {'dismissed': mine})
