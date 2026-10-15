"""metaform demo: one command, no questions, and within seconds the living map of a sample project with agents at work
on it in the browser, CLI-032.

It runs in a home of its own, `demo` inside the Metaform home, so the person's projects and settings are never read
or written: `cli.main` points METAFORM_HOME there before the command starts, and every process the demo starts
inherits it. The first run copies the sample project, Pocket Ledger, into that home and imports its finished map
from map.json, so no intake runs. It turns dispatch on there, with the demo agent, `agent.py`, as the start command
of every agent, so nothing it starts calls a model, a network service or anything that costs money. It starts the
web GUI on a free port, opens the person's desktop browser once (never a terminal one) and prints the address. Then
it keeps three demo agents at work: each lane is a node of the map with its ticket, and once an agent has closed its
ticket the lane rests a few seconds and a fresh ticket is worked there again; only one lane rests at a time, so
someone who arrives late always sees agents at work. The person's system agent is the demo agent too, the mascot that
greets them. Ctrl+C stops the agents and the server and puts their tickets back on the board, so the next run starts
them again; --reset removes the demo's home first, so it starts fresh."""
from __future__ import annotations

import contextlib
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from .. import harness, home, loader
from ..data import BASE_VARIABLE, Store, StoreError
from ..errors import Stop
from ..sqlite import Held, file_lock

HERE = Path(__file__).parent
FOLDER = 'demo'  # the demo's home, inside the Metaform home
CARD = 'demo.json'  # what the page's demo card says, read by the web GUI from the home it serves
REST = 10.0  # seconds a lane rests after its ticket is closed before a fresh one is worked there; one lane at a time
STALLED = 240.0  # a ticket worked this long without being closed is started again
STAGGER = 1.0  # seconds between the agents' first starts, so they set off one after another
IDENTITY = ('METAFORM_ROLE', 'METAFORM_SESSION', 'METAFORM_WORK', 'METAFORM_NODE', BASE_VARIABLE)
AGENTS = ('claude', 'codex', 'gemini')
NEEDED = ('map', 'dispatch', 'web')  # the modules the demo runs; a build without them cannot show it


def script() -> dict[str, Any]:
    """The demo's tickets, each with the script its agent plays, the mascot's lines and the card's words."""
    return cast(dict[str, Any], json.loads((HERE / 'script.json').read_text(encoding='utf-8')))


@contextlib.contextmanager
def own_home() -> Generator[Path, None, None]:
    """Run inside the demo's own home, `demo` in the Metaform home, without any agent session's identity, and put both
    back afterwards."""
    root = home.home() / FOLDER
    home.mkdir_private(root)
    kept = {name: os.environ.get(name) for name in ('METAFORM_HOME', *IDENTITY)}
    for name in IDENTITY:
        os.environ.pop(name, None)
    os.environ['METAFORM_HOME'] = str(root)
    try:
        yield root
    finally:
        for name, value in kept.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def metaform(*words: str, folder: Path) -> subprocess.CompletedProcess[str]:
    """The real metaform command line in the demo's home, from `folder`."""
    return subprocess.run([sys.executable, '-m', 'metaform', *words], cwd=folder, capture_output=True, text=True,
                          check=False, stdin=subprocess.DEVNULL, env=harness.child_environment())


def must(*words: str, folder: Path) -> str:
    """What the command printed; it stops the demo, saying why, when the command failed."""
    done = metaform(*words, folder=folder)
    if done.returncode != 0:
        said = [line for line in (done.stderr + done.stdout).splitlines() if not line.startswith('Notice:')]
        why = next((line[len('Error: '):] for line in said if line.startswith('Error: ')), ' '.join(said[-2:]))
        raise Stop(f'The demo could not run metaform {" ".join(words[:2])}: {why}', 'metaform demo --reset')
    return done.stdout


def agent_command() -> str:
    """The start command of every agent in the demo's home: the demo agent, run by this interpreter."""
    return f'{shlex.quote(sys.executable)} -m metaform.demo.agent' if os.name != 'nt' else \
        f'"{sys.executable}" -m metaform.demo.agent'


def project_folder(root: Path) -> Path:
    return root / str(script()['project'])


def prepare(root: Path) -> Path:
    """The demo's project in its home, made on the first run and reused after: the sample project's files, its map
    imported finished, dispatch on with the demo agent as every agent's start command. Returns its folder."""
    found = {item.id for item in loader.discover()}
    missing = [name for name in NEEDED if name not in found]
    if missing:
        raise Stop(f'This Metaform build carries no {" or ".join(missing)} module, which the demo runs, so it cannot '
                   'run the demo.', 'metaform list modules')
    folder = project_folder(root)
    ready = root / 'ready'
    if ready.exists() and folder.is_dir():
        return folder
    if folder.exists():  # an earlier first run was interrupted halfway: start again from nothing
        reset(root)
    shutil.copytree(HERE / 'sample', folder, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    if os.name != 'nt':  # in the home, the owner's alone, as every folder and file there is
        for where, _, files in os.walk(folder):
            os.chmod(where, 0o700)
            for name in files:
                os.chmod(os.path.join(where, name), 0o600)
    project = str(script()['project'])
    must('add', 'project', project, '.', folder=folder)
    must('import', str(HERE / 'map.json'), project, folder=folder)
    must('enable', 'dispatch', folder=folder)
    must('set', *[word for agent in AGENTS for word in (f'--dispatch-{agent}', agent_command())], folder=folder)
    home.write_private(ready, 'The demo project is in place.\n')
    return folder


def free_port() -> int:
    """A port no one listens on now, never the person's own web GUI's default."""
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(('127.0.0.1', 0))
            port = int(probe.getsockname()[1])
        if port != 7433:
            return port


def serve(folder: Path) -> str:
    """The web GUI of the demo's home, started on a free port, or the one already running there; its address."""
    must('set', '--web-port', str(free_port()), folder=folder)
    started = cast(dict[str, Any], json.loads(must('web', 'start', '--json', folder=folder)))
    return str(started['address'])


def write_card(root: Path, address: str) -> None:
    """What the page's demo card says, for the web GUI to serve; and the address, for a second `metaform demo`."""
    home.write_private(root / CARD, json.dumps({'project': script()['project'], 'address': address,
                                                **cast(dict[str, Any], script()['card'])}, ensure_ascii=False))


@dataclass
class Lane:
    """A node of the demo map where an agent works one ticket after another."""
    address: str
    agent: str
    title: str
    task: str
    kind: str
    ticket: str | None = None
    started: float = 0.0
    closed: float | None = None


def lanes(folder: Path) -> list[Lane]:
    """A lane for each of the demo's tickets, taking up an open ticket an earlier run left there."""
    made = [Lane(str(one['address']), str(one['agent']), str(one['title']), str(one['task']), str(one['kind']))
            for one in cast(list[dict[str, Any]], script()['tickets'])]
    store = Store(str(script()['project']))
    for record in store.work(open=True, limit=0).results:
        lane = next((one for one in made if one.address == record.address and one.task == record.task), None)
        if lane is not None and lane.ticket is None:
            lane.ticket = record.id
    return made


def start(lane: Lane, folder: Path) -> None:
    """Put the lane's agent to work: on its open ticket, or on a fresh one."""
    if lane.ticket is None:
        added = cast(dict[str, Any], json.loads(must(
            'map', 'work', 'op=add', f'node={lane.address}', f'title={lane.title}', f'task={lane.task}',
            f'kind={lane.kind}', f'agent={lane.agent}', '--json', folder=folder)))
        lane.ticket = str(added['id'])
    else:  # a ticket an earlier run left open, or one that stalled: its session, if any, ends first
        metaform('dispatch', 'stop', lane.ticket, folder=folder)
    must('dispatch', 'start', lane.ticket, lane.agent, folder=folder)
    lane.started, lane.closed = time.monotonic(), None


def tend(lane: Lane, folder: Path, store: Store, working: list[Lane]) -> None:
    """Keep the lane at work: a closed ticket rests, then a fresh one is started; a stalled one is started again.
    While another lane rests, a closed ticket's lane starts its fresh one at once, so the lanes, whose scripts take
    about as long as each other, never rest together and leave the map without an agent."""
    if lane.ticket is None:
        return start(lane, folder)
    try:
        done = store.ticket(lane.ticket).work.done
    except StoreError:
        done = None
    now = time.monotonic()
    if done and lane.closed is None and any(other.closed is not None for other in working if other is not lane):
        lane.ticket = None
        start(lane, folder)
    elif done and lane.closed is None:
        lane.closed = now
    elif done and lane.closed is not None and now - lane.closed >= REST:
        lane.ticket = None
        start(lane, folder)
    elif not done and now - lane.started >= STALLED:
        start(lane, folder)


def stop(folder: Path, working: list[Lane]) -> None:
    """Stop every demo agent and the demo's web GUI, and put the tickets they held back on the board: a stopped
    agent's ticket otherwise stays taken, and the next run could not start it."""
    for lane in working:
        if lane.ticket is not None:
            metaform('dispatch', 'stop', lane.ticket, folder=folder)
    with contextlib.suppress(StoreError, Stop):
        system = next((record.id for record in Store(str(script()['project'])).work(open=True, limit=0).results
                       if record.held and record.task == 'Conversation with the system agent'), None)
        if system is not None:
            metaform('dispatch', 'stop', system, folder=folder)
    metaform('dispatch', 'reset', folder=folder)
    metaform('web', 'stop', folder=folder)


def running_address(root: Path) -> str:
    try:
        return str(json.loads((root / CARD).read_text(encoding='utf-8')).get('address') or '')
    except (OSError, ValueError):
        return ''


def run(args: list[str], folder: Path, out: Callable[[str], None]) -> None:
    """`metaform demo [--reset]`, run inside the demo's own home, `own_home`, until Ctrl+C."""
    unknown = [word for word in args if word != '--reset']
    if unknown:
        raise Stop(f'demo takes --reset alone, not {unknown[0]}.', 'metaform demo')
    root = home.home()

    def say(text: str) -> None:  # each line as it is said, also when the output is a pipe rather than a terminal
        out(text)
        sys.stdout.flush()
    try:
        with file_lock(root / 'demo.lock', wait=False):
            if '--reset' in args:
                reset(root)
            show(root, say)
    except Held:
        address = running_address(root)
        raise Stop(f'The demo is already running{f" at {address}" if address else ""}; stop it with Ctrl+C there.',
                   address or 'metaform demo') from None


def reset(root: Path) -> None:
    """Stop what an earlier demo left running and remove everything in the demo's home but its lock."""
    folder = project_folder(root)
    if folder.is_dir():
        stop(folder, [])
    for path in root.iterdir():
        if path.name != 'demo.lock':
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()


def show(root: Path, out: Callable[[str], None]) -> None:
    """Prepare the demo, serve it, open the browser, and keep its agents at work until Ctrl+C, which stops the agents
    and the web GUI whenever it comes."""
    began = time.monotonic()
    out(f'Metaform demo, in a home of its own at {root}; your projects and settings are not touched.')
    folder = project_folder(root)
    working: list[Lane] = []
    try:
        prepare(root)
        must('dispatch', 'reset', folder=folder)  # tickets a run ended without its Ctrl+C, a kill, still held
        address = serve(folder)
        write_card(root, address)
        out(f'The map of Pocket Ledger, with three demo agents at work: {address}')
        from ..start import open_browser
        opened = open_browser(address)
        out(f'Ready in {time.monotonic() - began:.1f} s. ' + ('Opened in your browser. ' if opened else
                                                              'Open that address in your browser. ')
            + 'Ctrl+C stops it; metaform demo --reset starts it fresh.')
        working = lanes(folder)
        for at, lane in enumerate(working):
            if at:
                time.sleep(STAGGER)
            start(lane, folder)
        metaform('dispatch', 'system', 'agent=claude', folder=folder)  # the mascot
        store = Store(str(script()['project']))
        while True:
            time.sleep(1)
            for lane in working:
                tend(lane, folder, store, working)
    except KeyboardInterrupt:
        pass
    finally:
        if (root / 'ready').exists():
            out('Stopping the demo agents and the web GUI...')
            with contextlib.suppress(KeyboardInterrupt):
                stop(folder, working)
    out('Stopped. Run metaform demo to watch again, or metaform demo --reset to start fresh.')
