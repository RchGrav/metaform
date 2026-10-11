"""dispatch: Metaform starts an agent on a ticket through ACP, BASE-052.

`start` runs `run` as a process of its own, detached from the terminal, and returns at once. `run` is the ACP client
for one ticket: it starts the agent's ACP adapter in the project's folder, makes one session with Metaform's MCP
server, takes the ticket for the agent and hands it one prompt, then follows the session until it ends. Its notes, its
session record is on the map, at the ticket's node.

A ticket with an agent glyph, VIEW-040, is one of that agent's: the runner started on it works the glyph's tickets one
after another in board order, a session for each, and no ticket of a glyph whose agent is at work is started.

`message` and `stop` reach a running session over its loopback control port, kept in the session's record in this
module's `sessions` table. The runner hears each `map.changed` published in another process through the base's
listener, `ctx.listen`, and reads its open questions, QUAL-015 and BASE-053.

The ACP SDK is imported only by `runner`, so only the runner process loads it.
"""
from __future__ import annotations

import ctypes
import json
import os
import secrets
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Sequence
from importlib import resources
from pathlib import Path
from typing import Any, cast

from metaform import home, nonce, prompt_files, settings
from metaform.data import Column, Index, Store, StoreError, Table, Tables, WorkRecord
from metaform.module import Context, Module, Noun, Stop, Subscription, Verb, context, surface, work_reads

from .signals import collect, own_store, requeued, rework_limit
from .signals import read as read_signals

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ('agent-client-protocol>=0.12.1,<0.13',)
SHIPS_DISABLED = True
REMOTE_AGENT = False  # it launches agents on this machine, which a hosted sandbox does not have

# A dispatched agent's session and its transcript are this module's own tables, beside the metaform the ticket is in,
# STORE-045, and nothing of them is on the map: a node holds one note, and what an agent learns is a memory, VIEW-034.
# A line is one thing in the session's thread: the agent's words or thinking, a tool call, its plan, a turn's end, a
# prompt Metaform answered, or the person's message; `name` is what a line is kept for, so it changes in place.
TABLES = Tables(version=7, compatible_from=5, tables=(  # 5: agents do not ask; 6 and 7 only add tables
    Table('sessions', key=('session_id',),
          columns=(Column('session_id', required=True), Column('work_id', required=True), Column('agent', required=True),
                   Column('state', required=True), Column('nonce'), Column('pid', 'int'), Column('port', 'int'),
                   Column('token'), Column('how'), Column('started', required=True), Column('seq', 'int', required=True)),
          indexes=(Index(('work_id', 'seq')), Index(('seq',)))),
    Table('lines', key=('session_id', 'name'),
          columns=(Column('session_id', required=True), Column('name', required=True), Column('work_id', required=True),
                   Column('kind', required=True), Column('text', required=True), Column('seq', 'int', required=True)),
          indexes=(Index(('session_id', 'seq')), Index(('work_id', 'seq')))),
    Table('merges', place='project', key=('work_id',),
          columns=(Column('work_id', required=True), Column('branch', required=True), Column('worktree', required=True),
                   Column('state', required=True), Column('reason'), Column('ready', 'real', required=True),
                   Column('deadline', 'real', required=True), Column('seq', 'int', required=True)),
          indexes=(Index(('state',)),)),
    # An issue raised and not yet talking: waiting for its node or a slot, oldest first, or, with `started`, its
    # sentinel launched and its session not made yet, which holds a slot all the same, VIEW-045.
    Table('raised', key=('work_id',),
          columns=(Column('work_id', required=True), Column('node', required=True), Column('agent', required=True),
                   Column('started', 'real'), Column('seq', 'int', required=True)),
          indexes=(Index(('seq',)),)),
    # A work claim, LAYER-029: the part of the map a chosen proposal reserves while its tickets are built, the
    # addresses of the elements it touches as a JSON list, and the tickets it covers in claim_work.
    Table('claims', key=('claim_id',),
          columns=(Column('claim_id', required=True), Column('name', required=True), Column('nodes', required=True),
                   Column('issue'), Column('seq', 'int', required=True)),
          indexes=(Index(('seq',)),)),
    Table('claim_work', key=('work_id',),
          columns=(Column('work_id', required=True), Column('claim_id', required=True)),
          indexes=(Index(('claim_id',)),)),
    # A sentinel's proposals for the issue it was raised on, as a JSON list, for the page to present, VIEW-045.
    Table('proposals', key=('issue',),
          columns=(Column('issue', required=True), Column('text', required=True), Column('seq', 'int', required=True)),
          indexes=(Index(('seq',)),)),
))
PRIVATE = ('port', 'token', 'pid', 'nonce')  # what only this module uses to reach a running session
AGENTS = {
    'claude': ('Claude Code', 'npx -y @agentclientprotocol/claude-agent-acp'),
    'codex': ('Codex', 'npx -y @agentclientprotocol/codex-acp'),
    'gemini': ('Gemini CLI', 'gemini --acp'),
}
settings.boolean('dispatch_autostart', False, label='Autostart',
                 help='Start agents on tickets that have not been tried; a ticket an agent stopped on waits for the person.')
settings.choice('dispatch_agent', list(AGENTS), 'codex',
                help='The default agent: the one started when none is chosen, for a chat, an issue or an intake.',
                details='Starting an agent of another kind on a ticket leaves it as it is; the person sets it here or '
                        'from the page.')
settings.choice('dispatch_recovery', ['manual', 'automatic'], 'manual', label='Dead runner recovery',
                help='manual leaves a dead runner ticket taken; automatic verifies death and cleans up before returning it.',
                details='Applies before Autostart selection or with dispatch recover. Older sessions or uncertain cleanup '
                        'still require manual recovery. Session reads never change ownership.')
settings.number('dispatch_agents', 5, min=1, help='How many agents may work at once. The person can always summon one '
                'more; agents the person summons beyond that use the slots the agents at work leave free.')
settings.number('dispatch_spin_calls', 40, min=1, help='Tool calls without a completed ticket step before raising a spinning signal.')
settings.number('dispatch_spin_minutes', 10, min=1, help='Minutes without a completed step before the next session event raises a spinning signal.')
settings.number('dispatch_repeat_failures', 3, min=2, help='Consecutive failures of the same tool input before raising a repeated-failure signal.')
settings.boolean('dispatch_worktrees', False, help='Each ticket\'s agent works in a git worktree of its own, and done '
                 'work waits for review, then merges into the active dev branch, VIEW-044. Off until the dev branch '
                 'holds the work in progress, since a worktree starts from the last commit.')
settings.text('dispatch_test_command', '', help='The project\'s test command, run in a worktree before its merge is '
              'offered and again before it merges; with none, no merge is offered.')
settings.number('dispatch_review_minutes', 15, min=1, help='How long done work waits for a person\'s review before '
                'it merges by itself.')

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


def handoff_prompt(work_id: str, folder: Path) -> str:
    """The handoff, with its line on recording what the agent learns only while the memory module is on the folder's
    surface, so an agent is never told to use a command it does not have, BASE-052."""
    from metaform import instructions
    memory = any(module.id == 'memory' for module in instructions.surfaced(folder))
    return prompt('handoff', work_id=work_id, record=f"  {prompt('record')}\n" if memory else '')


def prompt_written(name: str) -> None:
    """Refuse a feature whose prompt is not written yet: the element ships empty until it is."""
    if not prompt(name):
        raise Stop(f'This needs its prompt written: {resources.files(__name__) / "resources" / "prompts.xml"} {name}',
                   'write the prompt, then try again')


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


def command_line(pid: int) -> list[str]:
    """The words of a process's command line; none for a process that has ended or cannot be read."""
    try:
        if sys.platform == 'win32':
            return [word.strip('"') for word in (_windows_command_line(pid) or '').split()]
        if sys.platform.startswith('linux'):
            with open(f'/proc/{pid}/cmdline', 'rb') as found:
                return [os.fsdecode(word) for word in found.read().split(b'\0') if word]
        said = subprocess.run(['ps', '-ww', '-o', 'command=', '-p', str(pid)], capture_output=True, text=True,
                              check=False)
        return said.stdout.split() if said.returncode == 0 else []
    except (OSError, ValueError):
        return []


def _windows_command_line(pid: int) -> str | None:
    """A Windows process's command line through its process handle, ProcessCommandLineInformation, Windows 8.1 on."""
    from ctypes import wintypes

    class Text(ctypes.Structure):
        _fields_ = [('Length', wintypes.USHORT), ('MaximumLength', wintypes.USHORT), ('Buffer', ctypes.c_void_p)]

    # WinDLL is present only on Windows; its CDLL base carries the shared ctypes interface for type checking.
    kernel = cast(ctypes.CDLL, getattr(ctypes, 'WinDLL')('kernel32', use_last_error=True))  # noqa: B009 -- WinDLL exists only on Windows.
    ntdll = cast(ctypes.CDLL, getattr(ctypes, 'WinDLL')('ntdll'))  # noqa: B009 -- WinDLL exists only on Windows.
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    ntdll.NtQueryInformationProcess.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.ULONG,
                                                ctypes.POINTER(wintypes.ULONG)]
    ntdll.NtQueryInformationProcess.restype = wintypes.LONG
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:  # STILL_ACTIVE
            return None
        size = wintypes.ULONG(0)
        ntdll.NtQueryInformationProcess(handle, 60, None, 0, ctypes.byref(size))  # ProcessCommandLineInformation
        if not size.value:
            return None
        held = ctypes.create_string_buffer(size.value)
        if ntdll.NtQueryInformationProcess(handle, 60, held, size, ctypes.byref(size)) != 0:
            return None
        text = Text.from_buffer(held)
        return ctypes.wstring_at(text.Buffer, text.Length // 2) if text.Buffer else None
    finally:
        kernel.CloseHandle(handle)


def runner_of(pid: Any) -> str | None:
    """The work id a process runs as `dispatch run <work id>`; none for a pid that is no runner, since a recorded pid
    can outlive its runner and be given to another process. A runner on a glyph goes on to the glyph's other tickets
    in the same process, so the work id is the one it started on."""
    if not isinstance(pid, int) or pid <= 0:
        return None
    words = command_line(pid)
    return next((words[at + 2] for at in range(len(words) - 2) if words[at:at + 2] == ['dispatch', 'run']), None)


def agent_named(name: str) -> str:
    if name not in AGENTS:
        raise Stop(f'{name} is not an agent dispatch starts: {", ".join(AGENTS)}.', 'metaform help dispatch start')
    return name


def ticket(store: Store, work_id: str) -> WorkRecord:
    try:
        return store.ticket(work_id).work
    except StoreError as error:
        raise Stop(str(error), 'metaform map work open=true') from None


# An intake agent's session holds no ticket: its work id is this prefix and a token of its own, so the CLI and the
# page reach it as they reach any session, and nothing takes it for a ticket. Its row stays in the metaform it began
# in, which an intake into a new base leaves for the one it activates at its finish, VIEW-045 and BASE-039.
INTAKE = 'intake-'


def intake_id(work_id: Any) -> bool:
    return str(work_id).startswith(INTAKE)


def intake_store(store: Store, work_id: str) -> Store | None:
    """This module's store on the metaform an intake agent's session is kept in: the active one first, then the
    project's other metaforms; None when no metaform holds it."""
    for base in sorted(home.bases(store.project_id), key=lambda base: not base.active):
        held = Store(store.project_id, base=base.id, module='dispatch')
        try:
            with held.tables(write=False) as tx:
                if tx.rows('sessions', {'work_id': work_id}, limit=1).results:
                    return held
        except StoreError:
            continue
    return None


def session_state(store: Store, session_id: str) -> dict[str, Any] | None:
    """A session's state as its runner last kept it: what the agent can do, its settings, commands, plan, usage, the
    folder it worked in and the parts of the map it touched; None for a session that kept none."""
    try:
        with own_store(store).tables(write=False) as tx:
            found = tx.rows('lines', {'session_id': session_id, 'name': 'state'}, limit=1).results
    except StoreError:
        return None
    if not found:
        return None
    try:
        value: Any = json.loads(str(found[0]['text']))
    except ValueError:
        return None
    return cast(dict[str, Any], value) if isinstance(value, dict) else None


def located(command: str) -> str | None:
    """Where a start command's first word is found on this system, by PATH and, on Windows, PATHEXT; None when it is
    not, or the command cannot be read."""
    try:
        return shutil.which(argv(command)[0])
    except (Stop, ValueError):
        return None


def runnable(ctx: Context, agent: str) -> None:
    """Refuse an agent whose start command is not found, before anything is written."""
    if located(str(ctx.setting(f'dispatch_{agent}'))) is None:
        raise Stop(f'The start command of {agent} is not found on this system.',
                   f'metaform set --dispatch-{agent} "<command>"')


def sessions(store: Store, work_id: str | None = None, *, verify: bool = True,
             open_work: Sequence[WorkRecord] | None = None) -> list[dict[str, Any]]:
    """The sessions, oldest first, of one ticket or of every ticket, read through this module's own tables whatever
    module the store was opened for."""
    own = own_store(store)
    try:
        with own.tables(write=False) as tx:
            found = (tx.rows('sessions', {'work_id': work_id}, by=('work_id', 'seq'), limit=0) if work_id
                     else tx.rows('sessions', by=('seq',), limit=0)).results
            rows = [dict(row) for row in found]
    except StoreError:
        return []
    if not verify:
        return rows
    # one read of the open tickets for every running row, rather than a ticket read for each
    opened: set[str] = set()
    if any(row['state'] == 'running' for row in rows):
        opened = {record.id for record in (open_work if open_work is not None
                                               else store.work(open=True, limit=0).results)}
    # an intake agent's session holds no ticket, so no ticket's being done ends it
    return [session_status(own, row, done=row['work_id'] not in opened and not intake_id(row['work_id']))
            for row in rows]


def recorded_activity(store: Store, row: dict[str, Any]) -> str:
    """Only a final recorded end_turn supports idle activity; it says nothing about session liveness."""
    activity = 'unknown'
    # Old runners cannot report their current turn. A final recorded end_turn supports idle activity only;
    # it does not end the session, and later output makes that historical turn insufficient evidence.
    try:
        with store.tables(write=False) as tx:
            lines = tx.rows('lines', {'session_id': row['session_id']}, by=('session_id', 'seq'), limit=0).results
        latest = [line for line in lines if line['seq'] == lines[-1]['seq']] if lines else []
        if len(latest) == 1 and latest[0]['kind'] == 'turn' and latest[0]['text'] == 'The turn ended: end_turn.':
            activity = 'idle'
    except StoreError:
        pass
    return activity


def session_status(store: Store, row: dict[str, Any], *, done: bool | None = None) -> dict[str, Any]:
    """A stored running row is a claim: check the ticket, that its pid is a runner, and the runner's authenticated
    reply, including its adapter; a runner that cannot reply is that ticket's only when its pid runs that work id.
    `done` is whether the ticket is done when the caller has read it already. Reads preserve the row and transcript."""
    if row['state'] != 'running':
        return {**row, 'activity': 'idle'}
    if (done if done is not None else ticket(store, row['work_id']).done) and not summoned(row):
        return {**row, 'state': 'ended', 'how': 'the ticket is done', 'activity': 'idle'}
    runner = runner_of(row.get('pid'))
    if runner is None:
        return {**row, 'state': 'ended', 'how': 'the runner is no longer running', 'activity': 'idle'}
    try:
        answer = tell(row, 'status', limit=1.0)
    except ConnectionRefusedError:
        return {**row, 'state': 'ended', 'how': 'the runner is no longer listening', 'activity': 'idle'}
    except (OSError, ValueError, TypeError, KeyError):
        answer = {}
    if answer.get('session_id') not in (None, row['session_id']):
        return {**row, 'state': 'ended', 'how': 'its port answers for another session', 'activity': 'idle'}
    if answer.get('state') not in ('running', 'ended'):  # an older runner, with no status to give, or a late reply
        if runner != row['work_id']:  # only the session's own reply shows a runner went on to this ticket
            return {**row, 'state': 'ended', 'how': 'its pid runs the runner of another ticket', 'activity': 'idle'}
        return {**row, 'activity': recorded_activity(store, row)}
    reported = answer.get('activity')
    return {**row, 'state': answer['state'], 'how': answer.get('how'),
            'interrupting': answer.get('interrupting') is True,
            'activity': reported if reported in ('working', 'waiting', 'idle') else recorded_activity(store, row)}


def work_read(ctx: Context, record: WorkRecord) -> dict[str, Any] | None:
    """What dispatch keeps on a work record: the sessions of agents dispatched on it, oldest first, without what only
    this module uses to reach them, shown under `dispatch` in `map work id=<id>`, BASE-035; nothing on a ticket no
    agent was dispatched on."""
    if ctx.store is None:
        return None
    found = sessions(ctx.store, record.id)
    from .signals import rows
    signals = rows(ctx.store, record.id)
    if not found and not signals:
        return None
    return {'sessions': [{key: value for key, value in session.items() if key not in PRIVATE} for session in found],
            'signals': signals}


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


def eligible_of(ctx: Context, record: WorkRecord) -> list[str]:
    """The eligible agents map serves on a ticket, MAP-058; an absent choice means Any."""
    kept = work_reads(ctx.folder, record, project=ctx.project).get('map')
    agents: Any = cast(dict[str, Any], kept).get('eligible', []) if isinstance(kept, dict) else []
    if not isinstance(agents, list) or any(not isinstance(agent, str) for agent in cast(list[Any], agents)):
        raise Stop(f'Work {record.id} has an unreadable eligible agents choice: {agents!r}.',
                   f'metaform map work id={record.id}')
    return cast(list[str], agents)


def require_eligible(ctx: Context, record: WorkRecord, agent: str) -> None:
    agents = eligible_of(ctx, record)
    if agents and agent not in agents:
        raise Stop(f'{agent} is not eligible for work {record.id}; eligible agents: {", ".join(agents)}.',
                   f'metaform map work id={record.id}')


def agent_for(ctx: Context, record: WorkRecord, agent: str | None = None) -> str:
    """Use the configured agent when eligible, otherwise the first agent listed, MAP-058."""
    chosen = agent or str(ctx.setting('dispatch_agent'))
    agents = eligible_of(ctx, record)
    return agent_named(chosen if not agents or chosen in agents else agents[0])


def startable(ctx: Context, store: Store, record: WorkRecord, agent: str) -> None:
    """Refuse a ticket done, taken or already holding a session, and an occupied glyph, VIEW-039 and VIEW-040:
    tickets with one glyph are one agent's, done one at a time."""
    require_eligible(ctx, record, agent)
    if record.done:
        raise Stop(f'Work {record.id} was done at {record.done}.', 'metaform map work open=true')
    if record.taken:
        raise Stop(f'Work {record.id} is already taken by {record.taken_by or "an agent"}.',
                   'metaform map work open=true')
    if not (record.task or '').strip():
        raise Stop(f'Work {record.id} has no task: nothing for an agent to do until one is written.',
                   f'metaform map work op=edit id={record.id} task="<what it needs>"')
    lock = claimed(store, record.address or record.receiver_address, record.id)
    if lock is not None:  # work claims are the scheduling lock, LAYER-029: no ticket inside another's claim starts
        raise Stop(f'Work {record.id} is on a part of the map claimed by "{lock["name"]}" until that work has landed.',
                   'metaform dispatch claims')
    glyph = glyph_of(ctx, record)
    if glyph is not None:
        occupied = next((held for held in store.work(open=True, limit=0).results
                         if held.taken and (held.taken_by or '').startswith('dispatch starting ') and
                         held.id != record.id and glyph_of(ctx, held) == glyph), None)
        if occupied is not None:
            raise Stop(f'Agent {glyph} is at work on work {occupied.id}; the tickets with its glyph are done '
                       'one at a time.', f'metaform map work id={occupied.id}')
    for session in sessions(store, record.id if glyph is None else None):
        if session.get('state') != 'running':
            continue
        if session['work_id'] == record.id:
            raise Stop(f'Work {record.id} already has an agent session.',
                       f'metaform dispatch sessions id={record.id}')
        if glyph is not None and glyph_of(ctx, ticket(store, session['work_id'])) == glyph:
            raise Stop(f'Agent {glyph} is at work on work {session["work_id"]}; the tickets with its glyph are done one '
                       f'at a time.', f'metaform map work id={session["work_id"]}')


def next_ticket(ctx: Context, store: Store, glyph: str, *, agent: str | None = None,
                exclude: tuple[str, ...] = ()) -> WorkRecord | None:
    """The glyph's next ticket, VIEW-040: the first not done and not taken in board order, To do before Backlog, each by
    its place, a ticket with none after, as Distribute deals them; an exclude record is no ticket."""
    kept = ticket_settings(ctx)
    waiting = [record for record in store.work(open=True, limit=0).results
               if not record.taken and record.id not in exclude
               and not kept.get(record.id, {}).get('hold') and (record.task or '').strip()]  # no task: nothing to do
    waiting.sort(key=lambda record: (record.held, record.position is None, record.position or 0))
    chosen = agent or ctx.nouns.get('agent') or str(ctx.setting('dispatch_agent'))
    for record in waiting:
        if kept.get(record.id, {}).get('glyph') != glyph:
            continue
        try:
            require_eligible(ctx, record, chosen)
        except Stop:
            continue
        return record
    return None


def map_work(ctx: Context, **nouns: Any) -> Any:
    """Use the map's public verb without importing its implementation."""
    found = next((module for module in surface(ctx.folder) if module.id == 'map'), None)
    if found is None:
        raise Stop('The map module is not active.', 'metaform enable map')
    verb = next(verb for verb in found.verbs if verb.name == 'work')
    return verb.run(context('map', ctx.folder, project=ctx.project, nouns=nouns))


def workflow_skill(ctx: Context, name: str, given: str) -> str:
    """A skill of the workflow module served whole with an input, for a purpose agent's first turn, VIEW-045."""
    found = next((module for module in surface(ctx.folder) if module.id == 'workflow'), None)
    if found is None:
        raise Stop('The workflow module is not active; the sentinel is one of its skills.', 'metaform enable workflow')
    verb = next(verb for verb in found.verbs if verb.name == 'serve')
    return str(verb.run(context('workflow', ctx.folder, project=ctx.project, nouns={'name': name, 'input': given})))


def intake_prompt(ctx: Context, asked: str) -> str:
    """The intake exactly as the intake module serves it, with what the person asked for in its prompt slot, for an
    intake agent's first turn: the intake is the instruction, and nothing is added to it, BASE-039."""
    found = next((module for module in surface(ctx.folder) if module.id == 'intake'), None)
    if found is None:
        raise Stop('The intake module is not active; it serves the intake the agent follows.', 'metaform enable intake')
    verb = next(verb for verb in found.verbs if verb.name == 'prompt')
    return str(verb.run(context('intake', ctx.folder, project=ctx.project, nouns={'text': asked} if asked else {})))


def release(store: Store, work_id: str, by: str, took: bool, session_id: str | None, how: str) -> None:
    """What an ending session leaves: its session row says it ended. A ticket it took and did not finish stays taken,
    with the agent's last note on it, until the person puts it back on the board: nothing restarts by itself. A
    runner whose own code cannot reach the store runs this in a new process, with the code on disk."""
    requeued = False
    if session_id is not None:
        with store.tables() as tx:
            tx.update('sessions', {'session_id': session_id}, {'state': 'ended', 'how': how})
    if session_id is not None or requeued:
        from .signals import clear_permissions, publish
        ctx = context('dispatch', Path(store.project().path), project=store.project_id)
        if session_id is not None:
            clear_permissions(ctx, session_id)
        if not intake_id(work_id) and not ticket(store, work_id).done:
            publish(ctx, 'not-smooth', work_id=work_id, session_id=session_id or '', key=by, reason=how)
            if requeued:
                publish(ctx, 'requeue', work_id=work_id, session_id=session_id or '', key=by, reason=how)


FRONTEND = frozenset({'gui', 'web', 'page', 'viewer', 'view', 'board', 'ui', 'frontend'})  # address words of front-end work


def ticket_settings(ctx: Context) -> dict[str, dict[str, Any]]:
    """What the map module keeps on each open ticket, read once: its glyph, its preferred agent and whether the person
    holds it, held tickets included."""
    if not any(module.id == 'map' for module in surface(ctx.folder)):
        return {}
    store = ctx.require_store()
    own = Store(store.project_id, module='map')
    with own.tables(write=False) as tx:
        kept: dict[str, dict[str, Any]] = {
            str(row['work_id']): {'glyph': row['glyph']} for row in tx.rows('glyphs', limit=0).results}
        for row in tx.rows('ticket_settings', limit=0).results:
            kept.setdefault(str(row['work_id']), {}).update(agent=row['agent'], hold=bool(row['hold']))
        for row in tx.rows('eligible', limit=0).results:
            kept.setdefault(str(row['work_id']), {})['eligible'] = row['agents']
    return kept


def preferred(record: WorkRecord, kept: dict[str, Any] | None) -> str:
    """The agent a ticket prefers: the one the person chose, or by default Claude for front-end and GUI work and Codex
    for back-end and system work."""
    agent = (kept or {}).get('agent')
    if agent in AGENTS:
        return str(agent)
    return 'claude' if FRONTEND & set((record.address or '').split('.')) else 'codex'


def summoned(row: dict[str, Any]) -> bool:
    """A session the person summoned to chat about a question: its runner was started with question=."""
    pid = row.get('pid')
    return isinstance(pid, int) and any(word.startswith(('question=', 'prep=', 'system=')) for word in command_line(pid))


STALE_START = 180  # seconds a start may take before its reservation is taken for a start that died


def _seconds(stamp: str | None) -> float:
    """An ISO time as seconds since the epoch; none or unreadable reads as now, so it is never taken for stale."""
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(stamp)).timestamp()
    except ValueError:
        return time.time()


def autostart(ctx: Context) -> dict[str, Any]:
    """The agent starter, VIEW-042: start the tickets that have not been tried, in board order, up to
    `dispatch_agents` at once besides the one summoned to chat, one at a time per glyph, each with the agent it
    prefers. A ticket the person holds is left out; one an agent stopped on stays taken until the person puts it
    back, so nothing restarts by itself."""
    from .recovery import recover
    recovered = recover(ctx)
    store = ctx.require_store()
    start_raised(ctx, store)  # the person raised these, so they start whether Autostart agents is checked or not
    if not ctx.setting('dispatch_autostart'):
        return {'started': [], 'recovery': recovered}
    kept = ticket_settings(ctx)
    opened = store.work(open=True, limit=0).results
    open_work = [record for record in opened
                 if not kept.get(record.id, {}).get('hold')]
    candidates = [record for record in open_work if not record.taken and (record.task or '').strip()]
    active = [row for row in sessions(store, open_work=opened) if row['state'] == 'running']
    workers = [row for row in active if not summoned(row)]
    candidates.sort(key=lambda record: (record.held, record.position is None, record.position or 0))
    glyph = {work_id: held.get('glyph') for work_id, held in kept.items()}
    occupied = {glyph.get(row['work_id']) for row in active} - {None}
    taken = [record for record in open_work
             if record.taken and (record.taken_by or '').startswith('dispatch starting ')]
    # A reservation whose runner never made its session is a start that died: it goes back to the queue, so a
    # crashed start never holds a slot for good.
    stale = [record for record in taken if record.id not in {row['work_id'] for row in active}
             and time.time() - _seconds(record.taken) > STALE_START]
    for record in stale:
        store.move_work(record.id, 'backlog' if record.held else 'todo', record.position)
        from .signals import publish
        publish(ctx, 'not-smooth', work_id=record.id, key=record.taken_by or '', reason='startup reservation expired')
        publish(ctx, 'requeue', work_id=record.id, key=record.taken_by or '', reason='startup reservation expired')
    taken = [record for record in taken if record not in stale]
    occupied.update(glyph.get(record.id) for record in taken)
    # An agent at work always holds its ticket, so the tickets in motion are the agents at work: a runner on its
    # glyph's next ticket, or one too busy to answer a status check, is counted all the same. The tickets the
    # person's summoned chats hold are not workers; the first summoned is the +1, and the rest take slots, as `extra`.
    chatting = {row['work_id'] for row in active if summoned(row)}
    in_motion = {record.id for record in opened if record.taken and not record.done} - chatting
    extra = max(0, sum(1 for row in active if summoned(row)) - 1)  # summoned beyond the first hold worker slots
    capacity = max(0, int(ctx.setting('dispatch_agents')) - extra -
                   len(in_motion | {row['work_id'] for row in workers} | {record.id for record in taken}))
    started: list[dict[str, Any]] = []
    for record in candidates:
        if capacity == 0:
            break
        mark = glyph.get(record.id)
        if mark is not None and mark in occupied:
            continue
        try:
            raw: Any = kept.get(record.id, {}).get('eligible', [])
            if not isinstance(raw, list) or any(not isinstance(agent, str) for agent in cast(list[Any], raw)):
                continue  # unreadable eligibility is refused, as by the individual start check
            agents = cast(list[str], raw)
            chosen = preferred(record, kept.get(record.id))  # the ticket's own choice, else by its area
            agent = agent_named(chosen if not agents or chosen in agents else agents[0])
            result = start(context('dispatch', ctx.folder, project=ctx.project,
                                   nouns={'id': record.id,
                                          'agent': agent}))
        except Stop:
            continue
        started.append(result)
        capacity -= 1
        if mark:
            occupied.add(mark)
    return {'started': started, 'recovery': recovered}


def recover(ctx: Context) -> dict[str, Any]:
    from .recovery import recover as recovering
    return recovering(ctx)


def reset(ctx: Context) -> dict[str, Any]:
    """Put the agent bookkeeping back in order after crashes: every ticket taken with no live agent behind it goes back
    to the queue, every session recorded as running whose runner is gone is recorded as ended.
    Live agents and their tickets are left alone; nothing is deleted."""
    store = ctx.require_store()
    own = Store(store.project_id, module='dispatch')
    alive = {row['work_id'] for row in sessions(store) if row['state'] == 'running'}  # verified against the runner
    with own.tables(write=False) as tx:
        recorded = [dict(row) for row in tx.rows('sessions', limit=0).results if row['state'] == 'running']
    ended: list[str] = []
    for row in recorded:
        if row['work_id'] not in alive:
            with own.tables() as tx:
                tx.update('sessions', {'session_id': row['session_id']},
                          {'state': 'ended', 'how': 'its runner was gone; ended by dispatch reset'})
            ended.append(row['work_id'])
            from .signals import clear_permissions, publish
            clear_permissions(ctx, row['session_id'])
            publish(ctx, 'not-smooth', work_id=row['work_id'], session_id=row['session_id'],
                    reason='its runner was gone; ended by dispatch reset')
    released: list[str] = []
    for record in store.work(open=True, limit=0).results:
        if record.taken and record.id not in alive:
            store.move_work(record.id, 'backlog' if record.held else 'todo', record.position)
            released.append(record.id)
            from .signals import publish
            publish(ctx, 'requeue', work_id=record.id, key=record.taken_by or '', reason='dispatch reset')
    return {'released': released, 'sessions_ended': ended, 'still_working': sorted(alive)}


def merges(ctx: Context) -> dict[str, Any]:
    """The merges waiting for review, VIEW-044, the soonest first."""
    from .merge import due
    return {'merges': due(ctx.require_store())}


def review(ctx: Context) -> dict[str, Any]:
    """The person takes a waiting merge over: its countdown is cancelled for good, VIEW-044."""
    from .merge import review as taking
    if not taking(ctx.require_store(), str(ctx.nouns['id'])):
        raise Stop(f'No merge of work {ctx.nouns["id"]} is waiting for review.', 'metaform dispatch merges')
    return {'work_id': ctx.nouns['id'], 'state': 'review'}


def merge(ctx: Context) -> dict[str, Any]:
    """Merge a waiting worktree whose review time is up, after both checks pass again, VIEW-044."""
    from .merge import merge_due
    return merge_due(ctx, ctx.require_store(), str(ctx.nouns['id']))


def _running_or_stop(store: Store, work_id: str) -> dict[str, Any]:
    # Stop and message must still reach older runners and runners finishing a completed ticket, and an intake agent
    # whatever metaform has become active since it began.
    held = (intake_store(store, work_id) or store) if intake_id(work_id) else store
    found = [row for row in sessions(held, work_id, verify=False) if row.get('state') == 'running']
    session = found[-1] if found else None
    if session is None:
        raise Stop(f'No agent is running on work {work_id}.', f'metaform dispatch start {work_id} <agent>')
    return session


def start(ctx: Context) -> dict[str, Any]:
    """Start the runner for one ticket as a process detached from the terminal, and return at once."""
    store = ctx.require_store()
    agent, work_id = agent_named(ctx.nouns['agent']), ctx.nouns['id']
    command = argv(str(ctx.setting(f'dispatch_{agent}')))
    if shutil.which(command[0]) is None:
        raise Stop(f'{command[0]}, the start command of {agent}, is not found on this system.',
                   f'metaform set --dispatch-{agent} "<command>"')
    folder = store.project().path
    log = os.path.join(tempfile.gettempdir(), f'metaform-dispatch-{work_id}.log')
    reservation = 'dispatch starting ' + secrets.token_hex(16)
    with store.atomic():
        record = ticket(store, work_id)
        startable(ctx, store, record, agent)
        store.take_work(work_id, by=reservation)
    extra = ['reservation=' + reservation]
    try:
        with open(log, 'ab') as written:
            process = subprocess.Popen([sys.executable, '-m', 'metaform', 'dispatch', 'run', work_id, agent, *extra,
                                        '--project', store.project_id],
                                       cwd=folder, stdin=subprocess.DEVNULL, stdout=written, stderr=written,
                                       **group_options())
    except OSError:
        with store.atomic():
            if ticket(store, work_id).taken_by == reservation:
                store.move_work(work_id, 'backlog' if record.held else 'todo', record.position)
        raise
    return {'state': 'starting', 'work_id': work_id, 'agent': agent, 'pid': process.pid, 'log': log}


def prep(ctx: Context) -> dict[str, Any]:
    """Start an agent in a merge's worktree to prepare its code for the person's review, VIEW-044; it takes no ticket
    and stays to talk with the person until stopped. It is an agent the person summons, VIEW-045."""
    store = ctx.require_store()
    work_id = str(ctx.nouns['id'])
    from .merge import worktree_of
    worktree_of(store, work_id)  # refuses a ticket with no merge
    record = ticket(store, work_id)
    kept = work_reads(ctx.folder, record, project=ctx.project).get('map')  # a done ticket's own, as it shows it
    agent = preferred(record, cast(dict[str, Any], kept) if isinstance(kept, dict) else None)
    if shutil.which(argv(str(ctx.setting(f'dispatch_{agent}')))[0]) is None:
        raise Stop(f'The start command of {agent} is not found on this system.', f'metaform set --dispatch-{agent} "<command>"')
    log = os.path.join(tempfile.gettempdir(), f'metaform-dispatch-prep-{work_id}.log')
    with open(log, 'ab') as written:
        process = subprocess.Popen([sys.executable, '-m', 'metaform', 'dispatch', 'run', work_id, agent, 'prep=true',
                                    '--project', store.project_id],
                                   cwd=store.project().path, stdin=subprocess.DEVNULL, stdout=written, stderr=written,
                                   **group_options())
    return {'state': 'starting', 'work_id': work_id, 'agent': agent, 'pid': process.pid, 'log': log}


SYSTEM_TASK = 'Conversation with the system agent'  # the ticket that anchors the person's system agent chat; held, so no agent works it


def anchor(ctx: Context, store: Store, at: str | None = None) -> WorkRecord:
    """The held ticket the person's conversations hang on when what they talk about has no ticket of its own: the system
    agent, a node, an ended agent's thread. Held, so no agent works it; made at the DE the first time."""
    def anchored() -> WorkRecord | None:
        return next((record for record in store.work(open=True, limit=0).results if record.task == SYSTEM_TASK), None)
    found = anchored()
    if found is None:
        roots = store.roots(limit=1)
        root = next((entry.element for entry in roots.entry if entry.element.role == 'DE'), None) \
            or next((entry.element for entry in roots.entry), None) or next(iter(roots.elements), None)
        node = root.address if root is not None else at  # a map with no roles yet: the node talked about holds it
        if node is None:
            raise Stop('Talking with an agent needs a map with one element at least.', 'metaform intake prompt')
        map_work(ctx, op='add', node=node, task=SYSTEM_TASK,
                 note='Held for the person\'s conversations with agents; no agent works this ticket.', held=True, hold=True)
        found = anchored()
        if found is None:
            raise Stop('The conversation ticket was not made.', 'metaform map work')
    return found


def converse(ctx: Context, store: Store, work_id: str, agent: str, extra: Sequence[str]) -> dict[str, Any]:
    """Start a conversation agent on a ticket without taking it: an agent the person summons, one always and more in the
    slots the agents at work leave free, VIEW-045. It never takes, reopens or closes the ticket, and lasts until the person stops it."""
    if any(word.startswith('talk=') for word in extra):
        prompt_written('talk')
    if shutil.which(argv(str(ctx.setting(f'dispatch_{agent}')))[0]) is None:
        raise Stop(f'The start command of {agent} is not found on this system.', f'metaform set --dispatch-{agent} "<command>"')
    log = os.path.join(tempfile.gettempdir(), f'metaform-dispatch-talk-{work_id}.log')
    with open(log, 'ab') as written:
        process = subprocess.Popen([sys.executable, '-m', 'metaform', 'dispatch', 'run', work_id, agent, 'system=true',
                                    *extra, '--project', store.project_id],
                                   cwd=store.project().path, stdin=subprocess.DEVNULL, stdout=written, stderr=written,
                                   **group_options())
    return {'state': 'starting', 'work_id': work_id, 'agent': agent, 'pid': process.pid, 'log': log, 'session_id': None,
            'conversation': True}


def system(ctx: Context) -> dict[str, Any]:
    """Start the person's system agent, the one agent they may summon besides the agents at work: it talks with them
    about anything in the project, from the project's folder, and stays until stopped. A running one is reused."""
    store = ctx.require_store()
    held = anchor(ctx, store)
    live = next((row for row in sessions(store, held.id) if row['state'] == 'running'), None)
    if live is not None:
        return {'state': 'running', 'work_id': held.id, 'agent': live['agent'], 'session_id': live['session_id']}
    return converse(ctx, store, held.id, agent_named(str(ctx.nouns.get('agent') or ctx.setting('dispatch_agent'))), [])


def json_list(value: Any, name: str) -> list[str]:
    """A list argument: a JSON list of text, or one value alone."""
    if isinstance(value, str):
        try:
            value = json.loads(value) if value.strip().startswith('[') else [value]
        except ValueError:
            raise Stop(f'{name} is a JSON list, such as ["code.alarm.audible"].', 'metaform help dispatch') from None
    if not isinstance(value, list) or any(not isinstance(one, str) for one in cast(list[Any], value)):
        raise Stop(f'{name} is a list of text.', 'metaform help dispatch')
    return cast(list[str], value)


def claim_rows(store: Store) -> list[dict[str, Any]]:
    """Every work claim with its nodes, its tickets and its state, LAYER-029: proposed until a ticket of it is taken,
    active from then, and ended when every ticket is done and nothing of it waits to merge."""
    own = Store(store.project_id, module='dispatch')
    with own.tables(write=False) as tx:
        claims = [dict(row) for row in tx.rows('claims', by=('seq',), limit=0).results]
        members = [dict(row) for row in tx.rows('claim_work', limit=0).results]
    with own.tables(write=False) as tx:  # merges are in the project's store, a transaction of their own, STORE-006
        waiting = {row['work_id'] for row in tx.rows('merges', limit=0).results if row['state'] != 'merged'}
    for claim in claims:
        claim['nodes'] = json.loads(claim['nodes'])
        claim['work'] = [row['work_id'] for row in members if row['claim_id'] == claim['claim_id']]
        held = []
        for work_id in claim['work']:
            try:
                held.append(store.ticket(work_id).work)
            except StoreError:
                continue
        started = any(record.taken or record.done for record in held)
        landed = bool(held) and all(record.done and record.id not in waiting for record in held)
        claim['state'] = 'ended' if started and landed else 'active' if started else 'proposed'
    return claims


def claimed(store: Store, address: str | None, work_id: str | None = None) -> dict[str, Any] | None:
    """The active claim reserving an address that the work is not part of, or None."""
    if not address:
        return None
    return next((claim for claim in claim_rows(store) if claim['state'] == 'active' and address in claim['nodes']
                 and work_id not in claim['work']), None)


def in_use(store: Store, node: str) -> list[str]:
    """What is using a node: the tickets in motion on it, taken by an agent and not done, and any active work claim
    that reserves it, LAYER-029."""
    using = [record.id for record in store.work(open=True, limit=0).results if record.taken and not record.done
             and node in (record.address, record.receiver_address, record.provider_address)]
    found = claimed(store, node)
    return using + ([f'claim {found["name"]}'] if found else [])


def summon_room(ctx: Context, store: Store) -> int:
    """How many more agents the person may summon now: one is always theirs, and beyond it the agent slots the agents
    at work leave free, up to `dispatch_agents`."""
    opened = store.work(open=True, limit=0).results
    active = [row for row in sessions(store, open_work=opened) if row['state'] == 'running']
    called = [row for row in active if summoned(row)]
    chatting = {row['work_id'] for row in called}
    made = {row['work_id'] for row in sessions(store)}  # a launch holds its slot until its session is made
    with Store(store.project_id, module='dispatch').tables(write=False) as tx:
        launching = [row for row in tx.rows('raised', by=('seq',), limit=0).results if row['started'] is not None
                     and row['work_id'] not in made and time.time() - row['started'] < STALE_START]
    working = ({record.id for record in opened if record.taken and not record.done} - chatting) | {
        row['work_id'] for row in active if not summoned(row)}
    free = max(0, int(ctx.setting('dispatch_agents')) - len(working))
    return max(0, 1 + free - len(called) - len(launching))


def start_raised(ctx: Context, store: Store) -> list[str]:
    """Start the sentinel of each queued issue whose node is no longer in use, oldest first, while there is room to
    summon an agent, VIEW-045."""
    own = Store(store.project_id, module='dispatch')
    with own.tables(write=False) as tx:  # read first: a pass with nothing queued writes nothing, so it never makes a
        held = [dict(row) for row in tx.rows('raised', by=('seq',), limit=0).results]  # cleared project's base again
    if not held:
        return []
    made = {row['work_id'] for row in sessions(store)}
    done = [row['work_id'] for row in held if row['started'] is not None
            and (row['work_id'] in made or time.time() - row['started'] >= STALE_START)]
    if done:  # a launch whose session is made, or that never made one, is done waiting
        with own.tables() as tx:
            for work_id in done:
                tx.delete('raised', {'work_id': work_id})
    waiting = [row for row in held if row['started'] is None]
    started: list[str] = []
    for row in waiting:
        if summon_room(ctx, store) <= 0:
            break
        if in_use(store, row['node']):
            continue
        launch(ctx, store, row['work_id'], row['node'], row['agent'])
        started.append(row['work_id'])
    return started


def launch(ctx: Context, store: Store, work_id: str, node: str, agent: str) -> dict[str, Any]:
    """Start an issue's sentinel, holding its slot in `raised` until its session is made."""
    with Store(store.project_id, module='dispatch').tables() as tx:
        tx.delete('raised', {'work_id': work_id})
        tx.insert('raised', {'work_id': work_id, 'node': node, 'agent': agent, 'started': time.time(),
                             'seq': time.time_ns()})
    return converse(ctx, store, work_id, agent, [f'sentinel={node}'])


def claim(ctx: Context) -> dict[str, Any]:
    """Record a work claim, LAYER-029: the part of the map a chosen proposal reserves and the tickets it covers. It
    is active from the first of its tickets being taken until the last has landed; while active, no other ticket on
    its nodes starts, and an issue raised on them waits."""
    store = ctx.require_store()
    name = str(ctx.nouns['name']).strip()
    nodes = json_list(ctx.nouns.get('nodes') or [], 'nodes')
    work = json_list(ctx.nouns.get('work') or [], 'work')
    if not name or not nodes:
        raise Stop('A claim has a name and the addresses it reserves.', 'metaform dispatch claim "<name>" nodes=\'["<address>"]\'')
    for work_id in work:
        ticket(store, work_id)
    claim_id = uuid.uuid4().hex
    with Store(store.project_id, module='dispatch').tables() as tx:
        tx.insert('claims', {'claim_id': claim_id, 'name': name, 'nodes': json.dumps(nodes),
                             'issue': ctx.nouns.get('issue'), 'seq': time.time_ns()})
        for work_id in work:
            tx.delete('claim_work', {'work_id': work_id})
            tx.insert('claim_work', {'work_id': work_id, 'claim_id': claim_id})
    return next(one for one in claim_rows(store) if one['claim_id'] == claim_id)


def claims(ctx: Context) -> dict[str, Any]:
    """The work claims with their state, and the proposals sentinels have made, for the page, VIEW-045."""
    store = ctx.require_store()
    with Store(store.project_id, module='dispatch').tables(write=False) as tx:
        proposals = {row['issue']: json.loads(row['text']) for row in tx.rows('proposals', by=('seq',), limit=0).results}
    return {'claims': claim_rows(store), 'proposals': proposals}


def propose(ctx: Context) -> dict[str, Any]:
    """A sentinel's proposals for its issue, kept for the page to present beside what each reserves, VIEW-045: each
    a title, its grounds, its disruption with the addresses it reserves as reach, its benefit and its trade-off,
    and, where the sentinel made one, a link to its own explanation as view."""
    store = ctx.require_store()
    issue = ticket(store, str(ctx.nouns['issue'])).id
    given: Any = ctx.nouns.get('proposals')
    if isinstance(given, str):
        try:
            given = json.loads(given)
        except ValueError:
            raise Stop('proposals is a JSON list of objects.', 'metaform help dispatch propose') from None
    if not isinstance(given, list) or not given or any(not isinstance(one, dict) or not one.get('title')
                                                      for one in cast(list[Any], given)):
        raise Stop('proposals is a JSON list of objects, each with a title.', 'metaform help dispatch propose')
    for one in cast(list[dict[str, Any]], given):
        one['reach'] = json_list(one.get('reach') or [], 'reach')
    with Store(store.project_id, module='dispatch').tables() as tx:
        tx.delete('proposals', {'issue': issue})
        tx.insert('proposals', {'issue': issue, 'text': json.dumps(given), 'seq': time.time_ns()})
    return {'issue': issue, 'proposals': given}


def raise_issue(ctx: Context) -> dict[str, Any]:
    """The person raises an issue on a node, a sentinel starts on it with their words, investigates,
    and brings proposals to the page's chat; the person chooses one or talks it through, and the chosen one becomes
    held tickets. The issue is held on a ticket of its own at the node, so the chat has a place and the report is
    kept; no worker takes it. An issue on a node other work is using, or raised when every agent slot is taken,
    waits; its sentinel starts when the work is complete and a slot is free."""
    store = ctx.require_store()
    given: Any = ctx.nouns['text']
    words = [str(word) for word in cast(list[Any], given)] if isinstance(given, (list, tuple)) else [str(given)]
    text = ' '.join(words).strip()
    if not text:
        raise Stop('An issue says what is wrong, in the person\'s words.', 'metaform dispatch raise <node> -- "<what is wrong>"')
    node = str(ctx.nouns['node'])
    agent = str(ctx.nouns.get('agent') or ctx.setting('dispatch_agent'))
    if shutil.which(argv(str(ctx.setting(f'dispatch_{agent}')))[0]) is None:  # checked before anything is written
        raise Stop(f'The start command of {agent} is not found on this system.', f'metaform set --dispatch-{agent} "<command>"')
    if not any(module.id == 'workflow' for module in surface(ctx.folder)):  # the sentinel is its skill, checked first
        raise Stop('The workflow module is not active; the sentinel is one of its skills.', 'metaform enable workflow')
    first = text.splitlines()[0][:120]
    made = map_work(ctx, op='add', node=node, task=f'Issue raised by the person: {first}', note=text, held=True, hold=True)
    work_id = str(made['id'] if isinstance(made, dict) else made.id)
    busy = in_use(store, node)
    if busy or summon_room(ctx, store) <= 0:
        with Store(store.project_id, module='dispatch').tables() as tx:
            tx.insert('raised', {'work_id': work_id, 'node': node, 'agent': agent, 'seq': time.time_ns()})
        return {'state': 'queued', 'work_id': work_id, 'node': node,
                'waiting_on': busy or 'a free agent slot', 'conversation': True}
    return launch(ctx, store, work_id, node, agent)


def talk(ctx: Context) -> dict[str, Any]:
    """Talk with an agent about anything the person clicks, VIEW-042: a ticket, open or done, a node, or an ended
    agent's session. An agent at work on it is talked to directly; otherwise a conversation agent starts, told
    what it is about. One summoned agent is always the person's; more use the agent slots left free, and past them
    a chat is refused until a slot frees."""
    store = ctx.require_store()
    given = {key: str(ctx.nouns[key]) for key in ('id', 'node', 'session') if ctx.nouns.get(key)}
    if len(given) != 1:
        raise Stop('Talk names one thing: id=<work id>, node=<address>, question=<message id> or '
                   'session=<work id>:<session id>.', 'metaform help dispatch talk')
    (kind, ref), = given.items()
    everyone = sessions(store)
    running = [row for row in everyone if row['state'] == 'running']
    if kind == 'id':
        work_id, about = ticket(store, ref).id, f'ticket:{ref}'
    elif kind == 'session':
        work_id, _, session_id = ref.partition(':')
        if not any(row['work_id'] == work_id and row['session_id'] == session_id for row in everyone):
            raise Stop(f'No agent session {ref}.', 'metaform dispatch sessions thread=false')
        about = f'thread:{session_id}'
    else:
        work_id, about = anchor(ctx, store, ref).id, f'node:{ref}'
    if kind in ('id', 'session'):  # an agent at work on it is talked to directly, never restarted
        working = next((row for row in reversed(running) if row['work_id'] == work_id and not summoned(row)), None)
        if working is not None and (kind != 'session' or working['session_id'] == ref.partition(':')[2]):
            return {key: working[key] for key in ('work_id', 'agent', 'session_id', 'state')}
    talking = next((row for row in running if summoned(row) and row['work_id'] == work_id
                    and f'talk={about}' in command_line(row['pid'])), None)
    if talking is not None:  # the chat about this is already open: it is reused
        return {key: talking[key] for key in ('work_id', 'agent', 'session_id', 'state')}
    if summon_room(ctx, store) <= 0:
        raise Stop(f'Every agent slot is in use: {ctx.setting("dispatch_agents")} besides the one you can always '
                   'summon. A chat opens when an agent finishes or one is stopped.', 'metaform dispatch sessions')
    record = ticket(store, work_id)
    return converse(ctx, store, work_id, agent_for(ctx, record, ctx.nouns.get('agent')), [f'talk={about}'])


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


def interrupt(ctx: Context) -> dict[str, Any]:
    """Cancel the current turn while keeping the session reachable and queued messages in order."""
    row = _running_or_stop(ctx.require_store(), ctx.nouns['id'])
    if ctx.nouns.get('session') and ctx.nouns['session'] != row['session_id']:
        raise Stop('The chat session is no longer the running session on this ticket.',
                   f'metaform dispatch sessions id={ctx.nouns["id"]}')
    result = tell(row, 'interrupt')
    if result.get('error'):
        raise Stop(str(result['error']), f'metaform dispatch stop {ctx.nouns["id"]}')
    return result


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
    return f"{handoff_prompt(work_id, ctx.folder)}\n\n{prompt('nodes')}\n{nodes}\n"


def threaded(lines: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """A thread as the page reads it: each tool call's line carries its detail as `data`, each permission line its
    request as `data`, and each session's state is taken out of the thread, by session id."""
    states: dict[str, dict[str, Any]] = {}
    details: dict[tuple[str, str], Any] = {}
    kept: list[dict[str, Any]] = []
    for line in lines:
        kind = line['kind']
        if kind in ('state', 'tool_detail', 'permission'):
            try:
                value: Any = json.loads(str(line['text']))
            except ValueError:
                value = None
            if kind == 'state':
                if isinstance(value, dict):
                    states[str(line['session_id'])] = cast(dict[str, Any], value)
                continue
            if kind == 'tool_detail':
                details[(str(line['session_id']), str(line['name'])[len('detail:'):])] = value
                continue
            line = {**line, 'data': value}
        kept.append(line)
    for line in kept:
        name = str(line['name'])
        if name.startswith('tool:'):
            found = details.get((str(line['session_id']), name[len('tool:'):]))
            if found is not None:
                line['data'] = found
    return kept, states


def read_sessions(ctx: Context) -> dict[str, Any]:
    """The sessions of one ticket or of every ticket, each with the lines of its thread in order, for the page's agent
    window and a node's work history, VIEW-036 and VIEW-039; with thread=false, the sessions alone, for the agents key.
    Each session's state is under `states` by its session id, so a session row reads the same on every surface, and
    a tool call's or a permission request's line carries its structure as `data`. What only reaches a running session
    is left out. An intake agent's session is found in whatever metaform it is kept in."""
    store = ctx.require_store()
    work_id = ctx.nouns.get('id') or None
    if work_id and intake_id(work_id):
        store = intake_store(store, str(work_id)) or store
    found = sessions(store, work_id)
    lines: list[dict[str, Any]] = []
    states: dict[str, dict[str, Any]] = {}
    try:
        with store.tables(write=False) as tx:
            for session in found:
                if ctx.nouns.get('thread') is not False:
                    lines += [dict(row) for row in tx.rows('lines', {'session_id': session['session_id']},
                                                           by=('session_id', 'seq'), limit=0).results]
                else:
                    lines += [dict(row) for row in tx.rows('lines', {'session_id': session['session_id'],
                                                                     'name': 'state'}, limit=1).results]
    except StoreError:
        pass
    lines, states = threaded(lines)
    if ctx.nouns.get('thread') is False:
        lines = []
    from .signals import rows
    return {'sessions': [{key: value for key, value in session.items() if key not in PRIVATE} for session in found],
            'lines': lines, 'signals': rows(store, work_id), 'states': states}


def harnesses(ctx: Context) -> dict[str, Any]:
    """The agents dispatch starts, for the person to choose from: each with its name, its start command, whether that
    command is found on this system, and which is the default; with a project, how many more agents the person may
    summon now."""
    default = str(ctx.setting('dispatch_agent'))
    found: list[dict[str, Any]] = []
    for agent, (label, _) in AGENTS.items():
        command = str(ctx.setting(f'dispatch_{agent}'))
        path = located(command)
        found.append({'agent': agent, 'label': label, 'command': command, 'available': path is not None,
                      'path': path, 'default': agent == default,
                      'next': None if path else f'metaform set --dispatch-{agent} "<command>"'})
    result: dict[str, Any] = {'agents': found, 'default': default}
    if ctx.store is not None:
        result['room'] = summon_room(ctx, ctx.store)
    return result


def permit(ctx: Context) -> dict[str, Any]:
    """The person's choice for an agent's waiting permission request, by the option's id or name: it answers the
    agent at once, and closes the request's question at the node with the option's name. Only the person gives it:
    it is not offered to agents over MCP, and nothing approves beyond dispatch_prompts."""
    work_id = str(ctx.nouns['id'])
    given: Any = ctx.nouns['option']
    option = ' '.join(str(word) for word in cast(list[Any], given)) if isinstance(given, (list, tuple)) else str(given)
    result = tell(_running_or_stop(ctx.require_store(), work_id), 'permit', request=str(ctx.nouns['request']),
                  option=option.strip())
    if result.get('error'):
        raise Stop(str(result['error']), f'metaform dispatch sessions id={work_id}')
    return result


def configure(ctx: Context) -> dict[str, Any]:
    """Set one of a running session's settings, as the agent offers them in the session's state: its mode, its model
    or any other config option, by the setting's id and the value or name of a choice, or on or off. The agent takes
    it from its next step. Only the person sets it: it is not offered to agents over MCP."""
    work_id = str(ctx.nouns['id'])
    given: Any = ctx.nouns['value']
    value = ' '.join(str(word) for word in cast(list[Any], given)) if isinstance(given, (list, tuple)) else str(given)
    result = tell(_running_or_stop(ctx.require_store(), work_id), 'configure', setting=str(ctx.nouns['setting']),
                  value=value.strip())
    if result.get('error'):
        raise Stop(str(result['error']), f'metaform dispatch sessions id={work_id}')
    return result


def spawn(store: Store, work_id: str, agent: str, extra: list[str], name: str) -> dict[str, Any]:
    """A runner started detached from the terminal in the project's folder, its output in the log named for it."""
    log = os.path.join(tempfile.gettempdir(), f'metaform-dispatch-{name}-{work_id}.log')
    with open(log, 'ab') as written:
        process = subprocess.Popen([sys.executable, '-m', 'metaform', 'dispatch', 'run', work_id, agent, *extra,
                                    '--project', store.project_id],
                                   cwd=store.project().path, stdin=subprocess.DEVNULL, stdout=written, stderr=written,
                                   **group_options())
    return {'pid': process.pid, 'log': log}


def resume(ctx: Context) -> dict[str, Any]:
    """Resume an ended agent session in place, with the agent's own memory of it, where its agent can load or resume
    a session: its thread goes on where it ended. A worker whose ticket is still its own goes on as that ticket's
    worker; any other session comes back as a conversation the person summoned. It waits for the person's next
    message. An agent that can do neither is refused, with a fresh agent that reads the thread as the next step."""
    store = ctx.require_store()
    work_id = str(ctx.nouns['id'])
    held = (intake_store(store, work_id) or store) if intake_id(work_id) else store
    found = sessions(held, work_id)
    wanted = ctx.nouns.get('session')
    row = next((one for one in reversed(found) if one['session_id'] == wanted), None) if wanted else \
        (found[-1] if found else None)
    if row is None:
        raise Stop(f'No agent session {wanted} on work {work_id}.' if wanted else f'No agent session on work {work_id}.',
                   f'metaform dispatch sessions id={work_id} thread=false')
    session_id, agent = str(row['session_id']), agent_named(str(row['agent']))
    said = {'work_id': work_id, 'agent': agent, 'session_id': session_id}
    if row['state'] == 'running':  # it is there already: talked to as it is
        return {**said, 'state': 'running'}
    fresh = f'metaform dispatch talk session={work_id}:{session_id}'
    kept = session_state(held, session_id) or {}
    caps = cast(dict[str, Any], kept.get('capabilities') or {})
    if not (caps.get('resume') or caps.get('load')):
        raise Stop(f'{AGENTS[agent][0]} did not offer to resume its sessions, so session {session_id} cannot go on; '
                   'a new agent can read its thread instead.', fresh)
    cwd = kept.get('cwd')
    if not isinstance(cwd, str) or not os.path.isdir(cwd):
        raise Stop(f'The folder session {session_id} worked in, {cwd}, is gone.', fresh)
    runnable(ctx, agent)
    record = None if intake_id(work_id) else ticket(store, work_id)
    worker = record is not None and not record.done and record.taken_by == f'{agent} {session_id}'
    if worker and running(store, work_id) is not None:
        raise Stop(f'Another agent is at work on work {work_id}.', f'metaform dispatch sessions id={work_id}')
    if not worker and summon_room(ctx, store) <= 0:
        raise Stop(f'Every agent slot is in use: {ctx.setting("dispatch_agents")} besides the one you can always '
                   'summon. A session resumes when an agent finishes or one is stopped.', 'metaform dispatch sessions')
    started = spawn(store, work_id, agent, [f'resume={session_id}', *([] if worker else ['system=true'])], 'resume')
    return {**said, 'state': 'starting', **started, 'conversation': not worker}


def intake(ctx: Context) -> dict[str, Any]:
    """Start an agent on this project's intake, VIEW-045 and BASE-039: its first turn is the intake as `intake prompt`
    serves it, with what the person asked for filled in, and it works in the project's folder with Metaform's MCP
    server, recording the map as it reasons it, so an open page follows it. It takes no ticket and counts against the
    agent slots as a summoned agent does, staying to talk until the person stops it. One intake runs at a time."""
    store = ctx.require_store()
    agent = agent_named(str(ctx.nouns.get('agent') or ctx.setting('dispatch_agent')))
    runnable(ctx, agent)
    if not any(module.id == 'intake' for module in surface(ctx.folder)):
        raise Stop('The intake module is not active; it serves the intake the agent follows.', 'metaform enable intake')
    for base in sorted(home.bases(store.project_id), key=lambda base: not base.active):
        for row in sessions(Store(store.project_id, base=base.id, module='dispatch')):
            if intake_id(row['work_id']) and row['state'] == 'running':
                raise Stop(f'An intake agent is already at work in this project: {row["agent"]}, session '
                           f'{row["session_id"]}.', f'metaform dispatch stop {row["work_id"]}')
    building = store.intake_recording().results
    if building and not ctx.nouns.get('resume'):
        held = building[0]
        raise Stop(f'An intake is being recorded in layer {held.layer.name} of metaform {held.base}, by an agent '
                   'Metaform did not start or one that stopped. When no agent is still recording it, start the intake '
                   'agent with resume=true and it resumes that intake.', 'metaform dispatch intake resume=true')
    if summon_room(ctx, store) <= 0:
        raise Stop(f'Every agent slot is in use: {ctx.setting("dispatch_agents")} besides the one you can always '
                   'summon. An intake starts when an agent finishes or one is stopped.', 'metaform dispatch sessions')
    given: Any = ctx.nouns.get('text') or []
    words = ' '.join(str(word) for word in cast(list[Any], given)) if isinstance(given, (list, tuple)) else str(given)
    work_id = INTAKE + secrets.token_hex(16)
    # The launch holds its slot until its session is made, as a sentinel's does. The check for another intake
    # starting and the reservation are one write, so two starts at once cannot both pass.
    made = {row['work_id'] for row in sessions(store)}
    with Store(store.project_id, module='dispatch').tables() as tx:
        if any(intake_id(row['work_id']) and row['started'] is not None and row['work_id'] not in made
               and time.time() - row['started'] < STALE_START for row in tx.rows('raised', limit=0).results):
            raise Stop('An intake agent is starting in this project.', 'metaform dispatch sessions thread=false')
        tx.insert('raised', {'work_id': work_id, 'node': '', 'agent': agent, 'started': time.time(),
                             'seq': time.time_ns()})
    extra = ['system=true', 'intake=true']
    if words.strip():  # the person's words reach the runner in a nonce, never in an argument
        extra.append('asked=' + nonce.request('dispatch', 'handoff', {'intake': work_id, 'text': words.strip()}))
    started = spawn(store, work_id, agent, extra, 'intake')
    return {'state': 'starting', 'work_id': work_id, 'agent': agent, **started, 'session_id': None,
            'conversation': True, 'intake': True}


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
        Verb('signals', read_signals,
             'Read dispatch signals raised by session events, including cleared signals with active=false.',
             nouns=(Noun('id', 'A work id; omit for every ticket.', required=False),
                    Noun('active', 'true reads waiting signals, false reads cleared signals.', kind='bool', required=False))),
        Verb('autostart', autostart, 'Start waiting tickets when Autostart agents is checked.',
             switches=('dispatch_autostart', 'dispatch_agent', 'dispatch_agents', 'dispatch_recovery')),
        Verb('recover', recover, 'Apply the configured dead runner recovery policy; uncertain cleanup leaves work taken.',
             switches=('dispatch_recovery',)),
        Verb('start', start, 'Start an agent on a ticket; returns at once, and the map shows the rest. On a ticket with '
                             'an agent glyph, the agent then works the glyph\'s other tickets in turn.',
             nouns=(Noun('id', 'The work id of the ticket.'), Noun('agent', 'claude, codex or gemini.')),
             switches=('dispatch_claude', 'dispatch_codex', 'dispatch_gemini'),
             examples=(('metaform dispatch start 198452e1... claude', 'Starts Claude Code on the ticket.'),)),
        Verb('reset', reset, 'Put agent bookkeeping back in order after crashes: tickets taken with no live agent go back to '
                             'the queue and dead sessions are recorded as ended; live agents are left alone.',
             examples=(('metaform dispatch reset', 'Release every ticket a dead agent still holds.'),)),
        Verb('merges', merges, 'The merges waiting for review, VIEW-044.',
             switches=('dispatch_worktrees', 'dispatch_test_command', 'dispatch_review_minutes')),
        Verb('review', review, 'Take a waiting merge over for review; its countdown is cancelled for good.',
             nouns=(Noun('id', 'The work id of the ticket whose merge waits.'),)),
        Verb('merge', merge, 'Merge a waiting worktree whose review time is up, after its checks pass again.',
             nouns=(Noun('id', 'The work id of the ticket whose merge waits.'),), surfaces=('cli',)),
        Verb('system', system, 'Start the person\'s system agent to talk with, or reuse the one running.',
             nouns=(Noun('agent', 'claude, codex or gemini; the default agent, dispatch_agent, when none is given.',
                         required=False),)),
        Verb('agents', harnesses, 'The agents dispatch starts: each one\'s name, its start command, whether that '
                                  'command is found on this system, and which is the default; with how many more '
                                  'agents may be summoned now.',
             switches=('dispatch_agent', 'dispatch_claude', 'dispatch_codex', 'dispatch_gemini'),
             examples=(('metaform dispatch agents', 'Lists Claude Code, Codex and Gemini CLI with what each needs.'),
                       ('metaform set --dispatch-agent claude', 'Makes Claude Code the default agent.'))),
        Verb('intake', intake, 'Start an agent on this project\'s intake: it follows the intake as `intake prompt` '
                               'serves it and records the map as it goes, and an open page follows it. It counts as '
                               'a summoned agent; one intake runs at a time.',
             nouns=(Noun('agent', 'claude, codex or gemini; the default agent, dispatch_agent, when none is given.',
                         required=False),
                    Noun('resume', 'true: start it although an intake is being recorded that no agent of Metaform\'s '
                                   'started, to resume that intake once no agent is still recording it.',
                         kind='bool', required=False),
                    Noun('text', 'What the intake is for, a target or a request, as `intake prompt` takes it; '
                                 'nothing means this project.', required=False, many=True)),
             switches=('dispatch_agent', 'dispatch_claude', 'dispatch_codex', 'dispatch_gemini'),
             examples=(('metaform dispatch intake agent=claude', 'Starts Claude Code on the intake of this project.'),
                       ('metaform dispatch intake -- "src/engine only"',
                        'Starts the default agent on an intake of what is asked.'))),
        Verb('resume', resume, 'Resume an ended agent session in place, where its agent can load or resume it: the '
                               'agent keeps its memory and its thread goes on; it waits for your next message.',
             nouns=(Noun('id', 'The work id of the session\'s ticket, or an intake agent\'s work id.'),
                    Noun('session', 'The session id; the latest session of the ticket when none is given.',
                         required=False)),
             examples=(('metaform dispatch resume 198452e1... session=4f2c...', 'Resumes that session.'),)),
        Verb('permit', permit, 'Answer an agent\'s waiting permission request with one of its options, by its id or '
                               'its name, as the person chooses it.',
             nouns=(Noun('id', 'The work id of the agent\'s ticket, or an intake agent\'s work id.'),
                    Noun('request', 'The permission request, as its line in the session\'s thread names it.'),
                    Noun('option', 'The option\'s id or name.', many=True)),
             examples=(('metaform dispatch permit 198452e1... 7c1e... -- allow', 'Answers with the option allow.'),),
             surfaces=('cli',)),
        Verb('configure', configure, 'Set one of a running agent session\'s settings as its agent offers them: its '
                                     'mode, its model or another option, by the setting\'s id.',
             nouns=(Noun('id', 'The work id of the agent\'s ticket, or an intake agent\'s work id.'),
                    Noun('setting', 'The setting\'s id, as the session\'s state lists it under settings.'),
                    Noun('value', 'A choice\'s value or name, or on or off for a switch.', many=True)),
             examples=(('metaform dispatch configure 198452e1... model -- opus', 'Sets the session\'s model.'),
                       ('metaform dispatch configure 198452e1... mode -- plan', 'Sets the session\'s mode.')),
             surfaces=('cli',)),
        Verb('raise', raise_issue, 'Raise an issue on a node: a sentinel investigates it and brings proposals to the chat; '
                                   'the person chooses one, and it becomes held tickets.',
             nouns=(Noun('node', 'The address of the part the issue is about.'),
                    Noun('agent', 'claude, codex or gemini; the configured agent by default.', required=False),
                    Noun('text', 'What is wrong, in the person\'s words.', many=True)),
             examples=(('metaform dispatch raise code.alarm.audible -- "The alarm plays twice when the timer ends."',
                        'Starts the sentinel on the alarm with that report.'),),
             surfaces=('cli',)),
        Verb('propose', propose, 'A sentinel records its proposals for the issue it was raised on, for the page to '
                                 'present beside what each reserves.',
             nouns=(Noun('issue', 'The work id of the issue the sentinel was raised on.'),
                    Noun('proposals', 'Required: a JSON list, each {"title", "grounds", "disruption", "reach": [addresses], '
                                      '"benefit", "tradeoff", "view": an optional link to its own explanation}.',
                         required=False))),
        Verb('claim', claim, 'Reserve the part of the map a chosen proposal touches while its tickets are built; '
                             'no other ticket on it starts until they have landed.',
             nouns=(Noun('name', 'What the work is called.'),
                    Noun('nodes', 'The addresses it reserves, as a JSON list; required.', required=False),
                    Noun('work', 'The work ids of its tickets, as a JSON list.', required=False),
                    Noun('issue', 'The work id of the issue it answers.', required=False)),
             examples=(('metaform dispatch claim "Quieter alarm" nodes=\'["code.alarm.audible"]\' work=\'["<work id>"]\'',
                        'Reserves the alarm for those tickets.'),)),
        Verb('claims', claims, 'The work claims with their state, and the proposals sentinels have made.'),
        Verb('talk', talk, 'Talk with an agent about a ticket, open or done, a node or an ended agent\'s '
                           'session; an agent at work on it is talked to directly.',
             nouns=(Noun('id', 'The work id of a ticket, open or done.', required=False),
                    Noun('node', 'The address of a node.', required=False),
                    Noun('session', 'An agent session, as <work id>:<session id>.', required=False),
                    Noun('agent', 'claude, codex or gemini.', required=False))),
        Verb('prep', prep, 'Start an agent in a merge\'s worktree to prepare its code for review, VIEW-044.',
             nouns=(Noun('id', 'The work id of the ticket whose merge is under review.'),)),
        Verb('run', run, 'Run one ticket\'s ACP session in this process until it ends. start runs it detached.',
             nouns=(Noun('id', 'The work id of the ticket.'), Noun('agent', 'claude, codex or gemini.'),
                    Noun('prep', 'true: help the person prepare a merge under review, in its worktree, VIEW-044.',
                         kind='bool', required=False),
                    Noun('system', 'true: the person\'s system agent, a conversation with no ticket work.',
                         kind='bool', required=False),
                    Noun('talk', 'What a conversation agent talks about: ticket:<id>, node:<address> or '
                                 'thread:<session id>.', required=False),
                    Noun('sentinel', 'The address of the node the person raised an issue on; the ticket holds the '
                                     'report, and the sentinel prompt is served.', required=False),
                    Noun('reservation', 'The startup reservation made by start.', required=False),
                    Noun('resume', 'The ended session to go on with, loaded or resumed through ACP.', required=False),
                    Noun('intake', 'true: an intake agent, whose work id names no ticket and whose first turn is the '
                                   'intake.', kind='bool', required=False),
                    Noun('asked', 'The nonce holding what the person asked the intake for.', required=False)),
             switches=('dispatch_claude', 'dispatch_codex', 'dispatch_gemini'), surfaces=('cli',)),
        Verb('message', message, 'Send a person\'s message to the agent working a ticket.',
             nouns=(Noun('id', 'The work id of the ticket.'), Noun('text', 'The message.', many=True)),
             examples=(('metaform dispatch message 198452e1... "also run the tests"', 'Sends it as session/prompt.'),
                       ('metaform dispatch message 198452e1... -- "--json"',
                        'Sends --json as written; after --, every word is the message, CLI-003.'))),
        Verb('interrupt', interrupt, 'Interrupt the current turn while keeping the conversation available.',
             nouns=(Noun('id', 'The work id of the ticket.'),
                    Noun('session', 'The chat session id, to avoid interrupting a replacement session.', required=False)),
             examples=(('metaform dispatch interrupt 198452e1...', 'Requests cancellation; the session stays available.'),)),
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
    subscriptions=(Subscription('work.requeued', requeued), Subscription('dispatch.rework-limit', rework_limit),
                   Subscription('signal.raised', collect)),
    work_read=work_read,
    start=None,
    stop=None,
    status=None,
)
