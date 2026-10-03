"""dispatch: Metaform starts an agent on a ticket through ACP, BASE-052.

`start` runs `run` as a process of its own, detached from the terminal, and returns at once. `run` is the ACP client
for one ticket: it starts the agent's ACP adapter in the project's folder, makes one session with Metaform's MCP
server, takes the ticket for the agent and hands it one prompt, then follows the session until it ends. Its notes, its
session record and the questions it asks are on the map, at the ticket's node.

A ticket with an agent glyph, VIEW-040, is one of that agent's: the runner started on it works the glyph's tickets one
after another in board order, a session for each, and no ticket of a glyph whose agent is at work is started.

`message` and `stop` reach a running session over its loopback control port, kept in the session's record in this
module's `sessions` table. The runner hears each `map.changed` published in another process through the base's
listener, `ctx.listen`, and reads its open questions, QUAL-015 and BASE-053.

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
from importlib import resources
from typing import Any, cast

from metaform import nonce, prompt_files, settings
from metaform.data import Column, Index, Store, StoreError, Table, Tables, WorkRecord
from metaform.module import Context, Module, Noun, Stop, Verb, work_reads

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ('agent-client-protocol>=0.12.1,<0.13',)
SHIPS_DISABLED = True

# A dispatched agent's session and its transcript are this module's own tables, beside the metaform the ticket is in,
# STORE-045, and nothing of them is on the map: a node holds one note, and what an agent learns is a memory, VIEW-034.
# A line is one thing in the session's thread: the agent's words or thinking, a tool call, its plan, a turn's end, a
# prompt Metaform answered, or the person's message; `name` is what a line is kept for, so it changes in place.
TABLES = Tables(version=1, tables=(
    Table('sessions', key=('session_id',),
          columns=(Column('session_id', required=True), Column('work_id', required=True), Column('agent', required=True),
                   Column('state', required=True), Column('nonce'), Column('pid', 'int'), Column('port', 'int'),
                   Column('token'), Column('how'), Column('started', required=True), Column('seq', 'int', required=True)),
          indexes=(Index(('work_id', 'seq')), Index(('seq',)))),
    Table('lines', key=('session_id', 'name'),
          columns=(Column('session_id', required=True), Column('name', required=True), Column('work_id', required=True),
                   Column('kind', required=True), Column('text', required=True), Column('seq', 'int', required=True)),
          indexes=(Index(('session_id', 'seq')), Index(('work_id', 'seq')))),
))
PRIVATE = ('port', 'token', 'pid', 'nonce')  # what only this module uses to reach a running session
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


# How an agent's interactive prompts are answered, as the administrator sets it, read at each request so a change
# reaches agents already running: approve-all answers each with its allow option; approve-reads answers a read or a
# search and asks for anything else; ask_all asks every one as a question at the ticket's node, BASE-052.
PROMPTS = ['approve-all', 'approve-reads', 'ask_all']
READS = ('read', 'search')  # the tool kinds of ACP that only read
settings.choice('dispatch_prompts', PROMPTS, 'ask_all',
                help='How an agent\'s permission prompts are answered: approve-all, approve-reads or ask_all.',
                details='approve-all answers every prompt with its allow option; approve-reads answers a read or a '
                        'search and asks for anything else; ask_all asks every prompt as a question at the ticket\'s '
                        'node. It is read at each prompt, so a change reaches agents already running.')


def prompt(name: str, **fills: str) -> str:
    """The prompt `name` of this module's resources/prompts.xml, MCP-031."""
    return prompt_files.required(resources.files(__name__), name, **fills)


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


def sessions(store: Store, work_id: str | None = None) -> list[dict[str, Any]]:
    """The sessions, oldest first, of one ticket or of every ticket, read through this module's own tables whatever
    module the store was opened for."""
    own = store if store.module == 'dispatch' else Store(store.project_id, module='dispatch')
    try:
        with own.tables(write=False) as tx:
            found = (tx.rows('sessions', {'work_id': work_id}, by=('work_id', 'seq'), limit=0) if work_id
                     else tx.rows('sessions', by=('seq',), limit=0)).results
            return [dict(row) for row in found]
    except StoreError:
        return []


def work_read(ctx: Context, record: WorkRecord) -> dict[str, Any] | None:
    """What dispatch keeps on a work record: the sessions of agents dispatched on it, oldest first, without what only
    this module uses to reach them, shown under `dispatch` in `map work id=<id>`, BASE-035; nothing on a ticket no
    agent was dispatched on."""
    if ctx.store is None:
        return None
    found = sessions(ctx.store, record.work_id)
    if not found:
        return None
    return {'sessions': [{key: value for key, value in session.items() if key not in PRIVATE} for session in found]}


def running(store: Store, work_id: str) -> dict[str, Any] | None:
    found = [row for row in sessions(store, work_id) if row.get('state') == 'running']
    return found[-1] if found else None


def tell(session: dict[str, Any], op: str, limit: float = REPLY_LIMIT, **given: Any) -> dict[str, Any]:
    """Send one request to a running session's control port and return its one reply."""
    held = session
    with socket.create_connection(('127.0.0.1', int(held['port'])), timeout=limit) as connection:
        connection.sendall(json.dumps({'token': held.get('token'), 'op': op, **given}).encode('utf-8') + b'\n')
        with connection.makefile('rb') as answers:
            line = answers.readline()
    found: Any = json.loads(line) if line else None
    return cast(dict[str, Any], found) if isinstance(found, dict) else {}


def glyph_of(ctx: Context, record: WorkRecord) -> str | None:
    """The agent glyph a ticket is assigned to, VIEW-040, as the map module shows it on the work record under `map`,
    BASE-035; None when it has none or the map module is not on the surface."""
    kept = work_reads(ctx.folder, record, project=ctx.project).get('map')
    glyph = cast(dict[str, Any], kept).get('glyph') if isinstance(kept, dict) else None
    return str(glyph) if glyph else None


def startable(ctx: Context, store: Store, record: WorkRecord) -> None:
    """Refuse a ticket done or taken, and one whose glyph's agent is at work on another ticket, VIEW-040: tickets with
    one glyph are one agent's, done one at a time."""
    if record.done:
        raise Stop(f'Work {record.work_id} was done at {record.done}.', 'metaform map work open=true')
    if record.taken:
        raise Stop(f'Work {record.work_id} is already taken by {record.taken_by or "an agent"}.',
                   'metaform map work open=true')
    glyph = glyph_of(ctx, record)
    if glyph is None:
        return
    for session in sessions(store):
        if session.get('state') != 'running' or session['work_id'] == record.work_id:
            continue
        if glyph_of(ctx, ticket(store, session['work_id'])) == glyph:
            raise Stop(f'Agent {glyph} is at work on work {session["work_id"]}; the tickets with its glyph are done one '
                       f'at a time.', f'metaform map work id={session["work_id"]}')


def next_ticket(ctx: Context, store: Store, glyph: str) -> WorkRecord | None:
    """The glyph's next ticket, VIEW-040: the first not done and not taken in board order, To do before Backlog, each by
    its place, a ticket with none after, as Distribute deals them; an exclude record is no ticket."""
    waiting = [record for record in store.work(open=True, limit=0).results
               if not record.taken and record.condition != 'exclude']
    waiting.sort(key=lambda record: (record.held, record.position is None, record.position or 0))
    return next((record for record in waiting if glyph_of(ctx, record) == glyph), None)


def _running_or_stop(store: Store, work_id: str) -> dict[str, Any]:
    session = running(store, work_id)
    if session is None:
        raise Stop(f'No agent is running on work {work_id}.', f'metaform dispatch start {work_id} <agent>')
    return session


def start(ctx: Context) -> dict[str, Any]:
    """Start the runner for one ticket as a process detached from the terminal, and return at once."""
    store = ctx.require_store()
    agent, work_id = agent_named(ctx.nouns['agent']), ctx.nouns['id']
    startable(ctx, store, ticket(store, work_id))
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


def read_sessions(ctx: Context) -> dict[str, Any]:
    """The sessions of one ticket or of every ticket, each with the lines of its thread in order, for the page's agent
    window and a node's work history, VIEW-036 and VIEW-039; with thread=false, the sessions alone, for the agents key.
    What only reaches a running session is left out."""
    store = ctx.require_store()
    work_id = ctx.nouns.get('id') or None
    found = sessions(store, work_id)
    lines: list[dict[str, Any]] = []
    try:
        with store.tables(write=False) as tx:
            for session in found if ctx.nouns.get('thread') is not False else ():
                lines += [dict(row) for row in tx.rows('lines', {'session_id': session['session_id']},
                                                       by=('session_id', 'seq'), limit=0).results]
    except StoreError:
        pass
    return {'sessions': [{key: value for key, value in session.items() if key not in PRIVATE} for session in found],
            'lines': lines}


MODULE = Module(
    id='dispatch',
    summary='Start an agent on a ticket through ACP, follow it, message it and stop it.',
    purpose='Starts Claude Code, Codex or Gemini CLI on one ticket through the Agent Client Protocol, one session per '
            "ticket, in the project's folder with Metaform's MCP server. What the agent does shows as notes at the "
            "ticket's own window, and each permission it asks for is a question at the ticket's node. Details: metaform "
            'help dispatch.',
    details='Each agent runs your own installed command under your own login: --dispatch-claude, --dispatch-codex and '
            '--dispatch-gemini set them. Metaform never reads or stores credentials.',
    verbs=(
        Verb('start', start, 'Start an agent on a ticket; returns at once, and the map shows the rest. On a ticket with '
                             'an agent glyph, the agent then works the glyph\'s other tickets in turn.',
             nouns=(Noun('id', 'The work id of the ticket.'), Noun('agent', 'claude, codex or gemini.')),
             switches=('dispatch_claude', 'dispatch_codex', 'dispatch_gemini'),
             examples=(('metaform dispatch start 198452e1... claude', 'Starts Claude Code on the ticket.'),)),
        Verb('run', run, 'Run one ticket\'s ACP session in this process until it ends. start runs it detached.',
             nouns=(Noun('id', 'The work id of the ticket.'), Noun('agent', 'claude, codex or gemini.')),
             switches=('dispatch_claude', 'dispatch_codex', 'dispatch_gemini'), surfaces=('cli',)),
        Verb('message', message, 'Send a person\'s message to the agent working a ticket.',
             nouns=(Noun('id', 'The work id of the ticket.'), Noun('text', 'The message.', many=True)),
             examples=(('metaform dispatch message 198452e1... "also run the tests"', 'Sends it as session/prompt.'),
                       ('metaform dispatch message 198452e1... -- "--json"',
                        'Sends --json as written; after --, every word is the message, CLI-003.'))),
        Verb('stop', stop, 'Stop the agent working a ticket.', nouns=(Noun('id', 'The work id of the ticket.'),)),
        Verb('sessions', read_sessions, 'The agent sessions of a ticket, or of every ticket, each with its thread.',
             nouns=(Noun('id', 'The work id of the ticket; none for every ticket.', required=False),
                    Noun('thread', 'false leaves the threads out, for a list of the sessions only.', kind='bool',
                         required=False))),
        Verb('handoff', handoff, 'Hand a ticket to an agent: a nonce whose run gives its prompt and the namespace nodes '
                                 'of its work.',
             nouns=(Noun('id', 'The work id of the ticket to hand on.', required=False),),
             examples=(('metaform dispatch handoff id=198452e1...', 'Prints the nonce to give the next agent.'),)),
    ),
    tables=TABLES,
    work_read=work_read,
    start=None,
    stop=None,
    status=None,
)
