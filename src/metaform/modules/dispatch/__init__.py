"""dispatch: Metaform starts an agent on a ticket through ACP, BASE-052.

`start` runs `run` as a process of its own, detached from the terminal, and returns at once. `run` is the ACP client
for one ticket: it starts the agent's ACP adapter in the project's folder, makes one session with Metaform's MCP
server, takes the ticket for the agent and hands it one prompt, then follows the session until it ends. Its notes, its
session record and the questions it asks are on the map, at the ticket's node.

`message` and `stop` reach a running session over its loopback control port, kept in the session's record on the
`dispatch` layer. So does this module's `map.changed` subscriber, which runs in whichever process changed the map
and tells each running session of the project to read its open questions, QUAL-015.

The ACP SDK is imported only by `runner`, so only the runner process loads it.
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from importlib import resources
from typing import Any, cast

from metaform import nonce, settings
from metaform.data import Item, Store, StoreError, WorkRecord
from metaform.module import Context, Module, Noun, Stop, Subscription, Verb

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ('agent-client-protocol>=0.12.1,<0.13',)
SHIPS_DISABLED = True

LAYER = 'dispatch'
VARIABLE = 'What a dispatched agent is doing on its ticket, and its session.'
AGENTS = {
    'claude': ('Claude Code', 'npx -y @agentclientprotocol/claude-agent-acp'),
    'codex': ('Codex', 'npx -y @agentclientprotocol/codex-acp'),
    'gemini': ('Gemini CLI', 'gemini --acp'),
}
REPLY_LIMIT = 30.0  # the one wait for a running session to answer `message`, `stop` or a change
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000

for _agent, (_name, _command) in AGENTS.items():
    settings.text(f'dispatch_{_agent}', _command,
                  help=f'The command that starts {_name} as an ACP agent.',
                  details=f'metaform dispatch start <work id> {_agent} runs it in the project folder. It runs your own '
                          f'installed {_name} under your own login; Metaform never reads or stores credentials.')


def prompt(name: str, **fills: str) -> str:
    """The prompt `name` of this module's resources/prompts.xml, MCP-031: what is between its tags, each empty element
    inside it filled with the value of its name."""
    text = (resources.files(__name__) / 'resources' / 'prompts.xml').read_text(encoding='utf-8')
    found = ET.fromstring(text).find(name)
    if found is None:
        raise LookupError(f'dispatch has no prompt {name}.')
    return ((found.text or '') + ''.join(fills.get(child.tag, '') + (child.tail or '') for child in found)).strip()


def argv(command: str, system: str | None = None) -> list[str]:
    """A start command as the arguments to run, its first word found on PATH, so `npx` is `npx.cmd` on Windows."""
    windows = (system or os.name) == 'nt'
    parts = shlex.split(command, posix=not windows)
    if windows:
        parts = [part[1:-1] if len(part) > 1 and part[0] == part[-1] == '"' else part for part in parts]
    if not parts:
        raise Stop('The start command is empty.', 'metaform help dispatch')
    found = shutil.which(parts[0])
    return [found or parts[0], *parts[1:]]


def group_options(system: str | None = None) -> dict[str, Any]:
    """How a process starts in a process group of its own, so stopping it ends what it started too."""
    if (system or os.name) == 'nt':
        return {'creationflags': CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW}
    return {'start_new_session': True}


def end_group(pid: int, system: str | None = None) -> None:
    """End a process and every process it started: `npx` starts the agent as a grandchild."""
    if (system or os.name) == 'nt':
        subprocess.run(['taskkill', '/T', '/F', '/PID', str(pid)], capture_output=True, check=False)
        return
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def agent_named(name: str) -> str:
    if name not in AGENTS:
        raise Stop(f'{name} is not an agent dispatch starts: {", ".join(AGENTS)}.', 'metaform help dispatch start')
    return name


def ticket(store: Store, work_id: str) -> WorkRecord:
    try:
        return store.ticket(work_id).work
    except StoreError as error:
        raise Stop(str(error), 'metaform map work open=true') from None


def extra(item: Item) -> dict[str, Any]:
    return item.extra if item.extra is not None else {}


def sessions(store: Store) -> list[Item]:
    """The session records on the dispatch layer, oldest first."""
    try:
        found = store.layer_items(LAYER, limit=0).results
    except StoreError:
        return []
    return [item for item in found if isinstance(item, Item) and extra(item).get('dispatch') == 'session']


def running(store: Store, work_id: str) -> Item | None:
    found = [item for item in sessions(store) if extra(item).get('work_id') == work_id
             and extra(item).get('state') == 'running']
    return found[-1] if found else None


def tell(session: Item, op: str, limit: float = REPLY_LIMIT, **given: Any) -> dict[str, Any]:
    """Send one request to a running session's control port and return its one reply."""
    held = extra(session)
    with socket.create_connection(('127.0.0.1', int(held['port'])), timeout=limit) as connection:
        connection.sendall(json.dumps({'token': held.get('token'), 'op': op, **given}).encode('utf-8') + b'\n')
        with connection.makefile('rb') as answers:
            line = answers.readline()
    found: Any = json.loads(line) if line else None
    return cast(dict[str, Any], found) if isinstance(found, dict) else {}


def _running_or_stop(store: Store, work_id: str) -> Item:
    session = running(store, work_id)
    if session is None:
        raise Stop(f'No agent is running on work {work_id}.', f'metaform dispatch start {work_id} <agent>')
    return session


def start(ctx: Context) -> dict[str, Any]:
    """Start the runner for one ticket as a process detached from the terminal, and return at once."""
    store = ctx.require_store()
    agent, work_id = agent_named(ctx.nouns['agent']), ctx.nouns['id']
    record = ticket(store, work_id)
    if record.done:
        raise Stop(f'Work {work_id} was done at {record.done}.', 'metaform map work open=true')
    if record.taken:
        raise Stop(f'Work {work_id} is already taken by {record.taken_by or "an agent"}.', 'metaform map work open=true')
    command = argv(str(ctx.setting(f'dispatch_{agent}')))
    if shutil.which(command[0]) is None:
        raise Stop(f'{command[0]}, the start command of {agent}, is not found on this system.',
                   f'metaform set --dispatch-{agent} "<command>"')
    folder = store.project().path
    log = os.path.join(tempfile.gettempdir(), f'metaform-dispatch-{work_id}.log')
    with open(log, 'ab') as written:
        process = subprocess.Popen([sys.executable, '-m', 'metaform', 'dispatch', 'run', work_id, agent,
                                    '--project', store.project_id],
                                   cwd=folder, stdin=subprocess.DEVNULL, stdout=written, stderr=written,
                                   **group_options())
    return {'state': 'starting', 'work_id': work_id, 'agent': agent, 'pid': process.pid, 'log': log}


async def run(ctx: Context) -> dict[str, Any]:
    from .runner import dispatch
    return await dispatch(ctx)


def message(ctx: Context) -> dict[str, Any]:
    """Carry a person's message to the agent working a ticket, as session/prompt."""
    store = ctx.require_store()
    given: Any = ctx.nouns['text']
    words = [str(word) for word in cast(list[Any], given)] if isinstance(given, (list, tuple)) else [str(given)]
    text = ' '.join(words)
    return tell(_running_or_stop(store, ctx.nouns['id']), 'message', text=text)


def stop(ctx: Context) -> dict[str, Any]:
    """Stop the agent working a ticket: session/cancel, then its process group ends."""
    return tell(_running_or_stop(ctx.require_store(), ctx.nouns['id']), 'stop')


def handoff(ctx: Context) -> str:
    """Run through a nonce, the hand-off prompt and the namespace nodes of its work, as the map holds them. Run with a
    work id, a new nonce for that ticket, which an agent gives the next agent to hand the work on."""
    store = ctx.require_store()
    held = nonce.reached()
    if held is None:
        work_id = ctx.nouns.get('id')
        if not work_id:
            raise Stop('handoff needs the work id of the ticket to hand on.', 'metaform dispatch handoff id=<work id>')
        ticket(store, str(work_id))
        number = nonce.request('dispatch', 'handoff', {'work_id': str(work_id)})
        return prompt('handed', nonce=number) + '\n'
    value: Any = held.value
    given = cast(dict[str, Any], value) if isinstance(value, dict) else {}
    if 'work_id' not in given:
        raise Stop('This nonce names no ticket.', 'metaform dispatch handoff id=<work id>')
    work_id = str(given['work_id'])
    try:
        read = store.ticket(work_id).to_dict()
    except StoreError as error:
        raise Stop(str(error), 'metaform map work open=true') from None
    nodes = json.dumps({'at': read.get('at'), 'linked': read.get('linked')}, ensure_ascii=False, indent=1)
    return f"{prompt('handoff', work_id=work_id)}\n\n{prompt('nodes')}\n{nodes}\n"


RUNNER: dict[str, int] = {}  # the pid of this process when it is a runner, which tells itself nothing


def relayed(payload: dict[str, Any], ctx: Context) -> dict[str, int]:
    """map.changed: tell each running session of the project to read its open questions, QUAL-015.

    This subscriber runs in the process that changed the map, BASE-010: a command, the MCP server or the web server.
    A session that does not answer is left as it is.
    """
    if RUNNER.get('pid') == os.getpid() or ctx.store is None:
        return {'told': 0}
    told = 0
    for session in sessions(ctx.store):
        if extra(session).get('state') != 'running':
            continue
        try:
            tell(session, 'changed', limit=2.0)
            told += 1
        except (OSError, ValueError, KeyError):
            continue
    return {'told': told}


MODULE = Module(
    id='dispatch',
    summary='Start an agent on a ticket through ACP, follow it, message it and stop it.',
    purpose='Starts Claude Code, Codex or Gemini CLI on one ticket through the Agent Client Protocol, one session per '
            "ticket, in the project's folder with Metaform's MCP server. What the agent does shows as notes at the "
            "ticket's node, and each permission it asks for is a question there. Details: metaform help dispatch.",
    details='Each agent runs your own installed command under your own login: --dispatch-claude, --dispatch-codex and '
            '--dispatch-gemini set them. Metaform never reads or stores credentials.',
    verbs=(
        Verb('start', start, 'Start an agent on a ticket; returns at once, and the map shows the rest.',
             nouns=(Noun('id', 'The work id of the ticket.'), Noun('agent', 'claude, codex or gemini.')),
             switches=('dispatch_claude', 'dispatch_codex', 'dispatch_gemini'),
             examples=(('metaform dispatch start 198452e1... claude', 'Starts Claude Code on the ticket.'),)),
        Verb('run', run, 'Run one ticket\'s ACP session in this process until it ends. start runs it detached.',
             nouns=(Noun('id', 'The work id of the ticket.'), Noun('agent', 'claude, codex or gemini.')),
             switches=('dispatch_claude', 'dispatch_codex', 'dispatch_gemini'), surfaces=('cli',)),
        Verb('message', message, 'Send a person\'s message to the agent working a ticket.',
             nouns=(Noun('id', 'The work id of the ticket.'), Noun('text', 'The message.', many=True)),
             examples=(('metaform dispatch message 198452e1... "also run the tests"', 'Sends it as session/prompt.'),)),
        Verb('stop', stop, 'Stop the agent working a ticket.', nouns=(Noun('id', 'The work id of the ticket.'),)),
        Verb('handoff', handoff, 'Hand a ticket to an agent: a nonce whose run gives its prompt and the namespace nodes '
                                 'of its work.',
             nouns=(Noun('id', 'The work id of the ticket to hand on.', required=False),),
             examples=(('metaform dispatch handoff id=198452e1...', 'Prints the nonce to give the next agent.'),)),
    ),
    subscriptions=(Subscription('map.changed', relayed),),
    start=None,
    stop=None,
    status=None,
)
