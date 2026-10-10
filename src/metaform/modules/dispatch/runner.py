"""runner: one ACP session for one ticket, BASE-052, run by `metaform dispatch run`.

Metaform is the ACP client. A runner started on a ticket with an agent glyph, VIEW-040, works the glyph's tickets one
after another in board order, a session for each, the next taken when the one before is done. The agent's ACP adapter runs as a child process in its own process group, in the
project's folder, with the person's environment unchanged; ACP goes over its standard input and output as bytes,
through the official SDK, `acp`. The runner listens on a loopback port for `message` and `stop`, and hears each
`map.changed` published in another process through the base's listener, QUAL-015 and BASE-053.

An agent asks the person nothing. The one thing a session puts in front of the person is a permission prompt the
agent's own tool raised, answered on the page; a turn that ends with the ticket open leaves the session idle and
reachable, and the ticket taken, until the person acts.

What ACP gives beyond text is kept structured, so the page can show it as it is: the session's state, one `state` line
with the agent's capabilities, its settings (its modes and its config options, a model among them), its slash
commands, its plan, its usage and the parts of the map it has touched; each tool call's diffs, locations and
terminals in a `tool_detail` line, each file placed on the map through the refs of the sources layer; and each
permission request in a `permission` line with its options. A session whose agent can load or resume it is resumed
in place, its thread going on where it ended.
"""
from __future__ import annotations

import asyncio
import contextlib
import difflib
import json
import os
import re
import secrets
import signal
import subprocess
import sys
import time
import uuid
from collections import deque
from collections.abc import Callable, Coroutine, Sequence
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, cast

import acp
from acp.schema import (
    AllowedOutcome,
    BooleanConfigOptionCapabilities,
    ClientCapabilities,
    ClientSessionCapabilities,
    DeniedOutcome,
    FileSystemCapabilities,
    Implementation,
    InitializeResponse,
    McpServerStdio,
    PermissionOption,
    RequestPermissionResponse,
    SessionConfigOptionsCapabilities,
    ToolCallUpdate,
)

from metaform import axiom, nonce
from metaform.data import Item, Node, Store, StoreError, WorkRecord
from metaform.module import Context, Stop

from . import (
    AGENTS,
    READS,
    REPLY_LIMIT,
    agent_named,
    argv,
    end_group,
    glyph_of,
    group_options,
    intake_id,
    intake_prompt,
    intake_store,
    next_ticket,
    prompt,
    release,
    require_eligible,
    runner_of,
    session_state,
    startable,
    ticket,
    workflow_skill,
)

START_LIMIT = 300.0  # the one wait for the agent to start and make its session; npx may download it first
END_LIMIT = 10.0  # the one wait for a cancelled turn to end, and for the agent to end once its input is closed
LINE_LIMIT = 64 * 1024 * 1024  # the longest line read from the agent
CHUNKS = ('agent_message_chunk', 'agent_thought_chunk', 'user_message_chunk')
STREAM_EVERY = 0.4  # seconds between writes of text still being written, so the page shows it as it grows
LINES_EVERY = 0.25  # at most one `dispatch.lines` event per this many seconds; the rows are written at once
TERMINATED = 'the runner was terminated'  # how a session ends on SIGTERM; its runner takes no next ticket
RELEASE_LIMIT = 90.0  # the one wait for a new process to release: its start, and two writes that may each wait on a lock
RELEASE = ('import json, sys; from metaform.data import Store; from metaform.modules.dispatch import release; '
           "given = json.loads(sys.argv[1]); release(Store(given.pop('project'), module='dispatch'), **given)")
# The updates that change what the session is rather than add to its thread: kept in its one `state` line.
STATE_UPDATES = ('available_commands_update', 'current_mode_update', 'config_option_update', 'session_info_update',
                 'usage_update')
SOURCES = 'sources'  # the layer the intake keeps each part's refs in, MAP-021: where on the map a file is
PATCH_LIMIT = 200_000  # the most characters of a file's two texts a diff is worked out from; past it, its size only
PATCH_KEPT = 60_000  # the most characters of one diff kept in the thread; the rest is in the file itself
TOUCHED_KEPT = 40  # the parts of the map a session's state lists as touched, the latest first
# What a session reported of itself that a resume carries over until the agent reports it again, so the page is not
# left blank after a resume; each is named in `before_resume` while it still holds what was known before the resume.
CARRIED = ('plan', 'usage', 'tokens', 'title', 'updated_at', 'commands')
SETTING_LIMIT = 10.0  # the one wait for the agent to take a setting; inside the caller's REPLY_LIMIT
LINE_MARK = re.compile(r'(?::\d+(?:-\d+)?|#L\d+(?:-L?\d+)?)$')  # a line or a range after a path: file.py:12, #L3-L9
FOLDED = os.name == 'nt' or sys.platform == 'darwin'  # their file systems compare names without case, as a rule


def stamp() -> str:
    """The time as the store writes it, to the second."""
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def relative(path: str, roots: Sequence[str]) -> str | None:
    """A path an agent named, as the project names it: relative to the first of the roots it is inside, with forward
    slashes; None for a path inside none of them. ACP paths are absolute; a relative one is taken as given."""
    if not os.path.isabs(path):
        given = path.replace('\\', '/')
        while given.startswith('./'):
            given = given[2:]
        return given.rstrip('/') or None
    for root in roots:
        try:
            found = os.path.relpath(path, root)
        except ValueError:  # Windows: another drive
            continue
        if found == os.curdir or found == os.pardir or found.startswith(os.pardir + os.sep):
            continue
        return found.replace(os.sep, '/')
    return None


def folded(path: str) -> str:
    return path.casefold() if FOLDED else path


def sources_index(store: Store, root: str) -> dict[str, list[dict[str, str]]]:
    """Each path the sources layer's refs name, as the project names it, with the parts of the map it belongs to: an
    element, or a join under its receiver's address. A ref's line mark is left off, so file.py:12 is file.py. With no
    sources layer the map places no file."""
    try:
        items = store.layer_items(SOURCES, limit=0).results
    except StoreError:
        return {}
    index: dict[str, list[dict[str, str]]] = {}
    for item in items:
        if not isinstance(item, Item):
            continue
        place = {'kind': item.target.kind, 'id': item.target.id, 'address': str(item.value)}
        for ref in item.refs:
            path = relative(LINE_MARK.sub('', ref.value.strip()), [root])
            if path:
                held = index.setdefault(folded(path), [])
                if place not in held:
                    held.append(place)
    return index


def placed(index: dict[str, list[dict[str, str]]], path: str | None) -> list[dict[str, str]]:
    """The parts of the map a file belongs to: those whose refs name it, or else those whose refs name the nearest
    folder holding it."""
    if not path or not index:
        return []
    parts = folded(path).split('/')
    for end in range(len(parts), 0, -1):
        found = index.get('/'.join(parts[:end]))
        if found:
            return found
    return []


def unified(path: str, old: str | None, new: str) -> dict[str, Any]:
    """A file edit as a unified diff with the lines it adds and removes; one too large to work out says its size only,
    and a long diff is cut, saying so."""
    if len(old or '') + len(new) > PATCH_LIMIT:
        return {'patch': None, 'added': None, 'removed': None, 'created': old is None, 'truncated': True,
                'size': len(new)}
    lines = list(difflib.unified_diff((old or '').splitlines(keepends=True), new.splitlines(keepends=True),
                                      f'a/{path}', f'b/{path}', n=3))
    added = sum(1 for line in lines if line.startswith('+') and not line.startswith('+++'))
    removed = sum(1 for line in lines if line.startswith('-') and not line.startswith('---'))
    text = ''.join(line if line.endswith('\n') else line + '\n' for line in lines)
    return {'patch': text[:PATCH_KEPT], 'added': added, 'removed': removed, 'created': old is None,
            'truncated': len(text) > PATCH_KEPT}


def setting_of(option: dict[str, Any]) -> dict[str, Any]:
    """One of the agent's config options, as the page offers it: its choices flattened, each with its group."""
    choices: list[dict[str, Any]] = []
    for given in cast(list[dict[str, Any]], option.get('options') or []):
        if 'group' in given:
            choices += [{'value': one.get('value'), 'name': one.get('name'), 'description': one.get('description'),
                         'group': given.get('name')} for one in cast(list[dict[str, Any]], given.get('options') or [])]
        else:
            choices.append({'value': given.get('value'), 'name': given.get('name'),
                            'description': given.get('description'), 'group': None})
    return {'id': option.get('id'), 'name': option.get('name'), 'description': option.get('description'),
            'category': option.get('category'), 'type': option.get('type', 'select'),
            'current': option.get('currentValue'), 'options': choices, 'source': 'option'}


def switched(value: str) -> bool | None:
    """A boolean setting's value as a person writes it; None when it is neither."""
    said = value.strip().casefold()
    return True if said in ('true', 'on', 'yes', '1') else False if said in ('false', 'off', 'no', '0') else None


class Exits(asyncio.subprocess.SubprocessStreamProtocol):
    """The agent's process protocol, which says when the process itself has ended. `Process.wait` waits also for its
    pipes, which a process it started may hold open after it ends."""

    def __init__(self, limit: int, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__(limit=limit, loop=loop)
        self.exited = asyncio.Event()

    def process_exited(self) -> None:
        super().process_exited()
        self.exited.set()


async def dispatch(ctx: Context) -> dict[str, Any]:
    """`metaform dispatch run <id> <agent>`: the session for one ticket, until it ends. When the ticket is done and has an
    agent glyph, VIEW-040, the glyph's next ticket in board order gets a session of its own, and so on until the glyph
    has none waiting or a session ends with its ticket not done."""
    store = ctx.require_store()
    agent, work_id = agent_named(ctx.nouns['agent']), ctx.nouns['id']
    command = argv(str(ctx.setting(f'dispatch_{agent}')))
    resume = str(ctx.nouns['resume']) if ctx.nouns.get('resume') else None
    resumed = await asyncio.to_thread(worked_in, store, work_id, resume) if resume else None
    if intake_id(work_id):  # an intake agent, VIEW-045: no ticket; its session lives in the metaform it began in
        held_in = await asyncio.to_thread(intake_store, store, work_id) or store
        return await Session(ctx, held_in, None, agent, command, resumed, prep=True, system=True, work_id=work_id,
                             resume=resume).run()
    if ctx.nouns.get('system'):  # the person's system agent, the +1: talks with them in the project's folder
        held = await asyncio.to_thread(ticket, store, work_id)
        return await Session(ctx, store, held, agent, command, resumed, prep=True, system=True, resume=resume).run()
    if ctx.nouns.get('prep'):  # VIEW-044: an agent helps the person prepare a merge under review, in its worktree
        from .merge import worktree_of
        held = await asyncio.to_thread(ticket, store, work_id)
        folder = await asyncio.to_thread(worktree_of, store, work_id)
        return await Session(ctx, store, held, agent, command, folder, prep=True).run()

    def reserve(record: WorkRecord) -> WorkRecord:
        with store.atomic():
            record = ticket(store, record.id)
            reservation = ctx.nouns.get('reservation')
            if reservation and record.taken_by == reservation:
                require_eligible(ctx, record, agent)
                return record
            startable(ctx, store, record, agent)
            reservation = 'dispatch starting ' + secrets.token_hex(16)
            record = store.take_work(record.id, by=reservation)
            ctx.nouns['reservation'] = reservation
            return record

    # A worker resumed in place holds its ticket already, taken by its own session, so nothing is reserved for it.
    record = await asyncio.to_thread(ticket, store, work_id) if resume else \
        await asyncio.to_thread(reserve, ticket(store, work_id))
    worked: list[str] = []
    while True:
        folder: Path | None = None
        if resume:
            folder = Path(resumed) if resumed else None  # where it worked, its worktree when it had one
        elif ctx.setting('dispatch_worktrees'):  # VIEW-044: each ticket's agent works in a worktree of its own
            from .merge import worktree_for
            folder = await asyncio.to_thread(worktree_for, store.project().path, record.id)
        ended = await Session(ctx, store, record, agent, command, folder, resume=resume).run()
        resume = None  # the glyph's next ticket, if any, is a new session
        worked.append(record.id)
        if ended.get('ended') == TERMINATED:  # a terminated runner reads nothing more, so a store it cannot reach is no error
            return ended if len(worked) == 1 else {**ended, 'worked': worked}
        record = await asyncio.to_thread(ticket, store, record.id)
        if folder is not None and record.done:  # its work committed, tested and checked to merge, VIEW-044
            from .merge import finished
            await asyncio.to_thread(finished, ctx, store, record, folder)
            active = await asyncio.to_thread(store.active_base)
            await ctx.publish_async('map.changed', {'project': store.project_id, 'tables': 'dispatch',
                                                    'base_id': active.id if active else None})
        glyph = await asyncio.to_thread(glyph_of, ctx, record)  # read again, so a glyph given while it ran counts
        if glyph is None:
            return ended if len(worked) == 1 else {**ended, 'worked': worked}
        def following(glyph: str) -> WorkRecord | None:
            with store.atomic():
                found = next_ticket(ctx, store, glyph, agent=agent, exclude=tuple(worked))
                return reserve(found) if found is not None else None
        try:
            found = (await asyncio.to_thread(following, glyph)
                     if record.done or ended.get('ended') == 'cannot continue without an answer' else None)
        except Stop:  # another runner now occupies the glyph
            found = None
        if found is None:
            return {**ended, 'glyph': glyph, 'worked': worked}
        record = found


def worked_in(store: Store, work_id: str, session_id: str) -> str | None:
    """The folder a session worked in, as its state line keeps it; None when it kept none."""
    held = session_state(intake_store(store, work_id) or store if intake_id(work_id) else store, session_id)
    cwd = held.get('cwd') if held else None
    return str(cwd) if cwd else None


def choose(options: list[PermissionOption], answer: str | None) -> str | None:
    """The option a person's answer names, by its name or its id; None when it names none."""
    said = (answer or '').strip()
    for exact in (True, False):
        for option in options:
            names = (option.name, option.option_id)
            if any(name == said if exact else name.casefold() == said.casefold() for name in names):
                return option.option_id
    return None


def chunk_text(content: Any) -> str:
    if not isinstance(content, dict):
        return ''
    block = cast(dict[str, Any], content)
    return str(block.get('text', '')) if block.get('type') == 'text' else f'[{block.get("type", "content")}]'


def subject(store: Store, work_id: str, talk: str) -> tuple[str, str]:
    """What a conversation agent talks about, in words, and how it reads it first, from `talk=<kind>:<ref>`."""
    kind, _, ref = talk.partition(':')
    if kind == 'ticket':
        record = ticket(store, ref)
        return (f'ticket {ref}, {"done" if record.done else "open"}: {record.task or record.note or ""}',
                f'`metaform map work id={ref}`, and what its agents did with `metaform dispatch sessions id={ref}`')
    if kind == 'question':
        asked = next((one for one in store.messages(None, 'question', None, limit=0).results if one.id == ref), None)
        text = asked.text or '' if asked else ''
        return (f'question {ref}{", answered" if asked and asked.closed else ""}: {text}',
                f'`metaform map messages kind=question` for question {ref}, and its ticket with `metaform map work id={work_id}`')
    if kind == 'thread':
        return (f'what an earlier agent did in session {ref} on ticket {work_id}',
                (f'that session\'s whole thread with `metaform dispatch sessions id={work_id}` (session {ref}), and '
                 f'the ticket with `metaform map work id={work_id}`'))
    return f'the node {ref} of the map', f'`metaform map where {ref}`'


@dataclass
class ActiveTurn:
    """Cancellation belongs to one prompt, including its turn-start publication before ACP receives it."""
    sent: bool = False
    cancel_requested: bool = False


class Session:
    """One ticket's ACP session. The SDK calls `session_update` and `request_permission` on it."""

    def __init__(self, ctx: Context, store: Store, record: WorkRecord | None, agent: str, command: list[str],
                 folder: Any = None, prep: bool = False, system: bool = False, *, work_id: str | None = None,
                 resume: str | None = None) -> None:
        self.system = system  # the person's system agent: no ticket work, a conversation that lasts until stopped
        self.prep = prep  # helping the person prepare a merge, VIEW-044: it takes no ticket and lives between turns
        self.ctx, self.store, self.agent, self.command = ctx, store, agent, command
        # An intake agent has no ticket and no node: its work id names its session alone, and a permission it asks
        # for is put to the person on the page only, as a choice among its options.
        self.work_id = record.id if record is not None else str(work_id)
        self.node = Node.of(record.node_kind, record.node_id) if record is not None else None
        self.root = store.project().path
        self.folder = str(folder) if folder is not None else self.root  # its worktree, VIEW-044
        self.name = AGENTS[agent][0]
        self.base_id: str | None = None
        self.resume = resume  # the ended session this one goes on with, resumed or loaded through ACP
        self.replaying = False  # session/load replays the history the thread already holds; it is not written again
        self.session_id: str | None = resume
        self.number: str | None = None  # the agent's nonce
        self.token = secrets.token_hex(16)
        self.port = 0
        self.process: asyncio.subprocess.Process | None = None
        self.exited = asyncio.Event()  # the agent's process has ended
        self.conn: Any = None
        self.recorded = False  # the session's row is written
        self.took = bool(record is not None and ctx.nouns.get('reservation')
                         and record.taken_by == ctx.nouns['reservation'])
        # What the session is, kept whole in its `state` line: capabilities, settings, commands, plan, usage, touched.
        self.acp: dict[str, Any] = {'agent': agent, 'agent_info': None, 'capabilities': {}, 'cwd': self.folder,
                                    'commands': [], 'plan': [], 'usage': None, 'tokens': None, 'title': None,
                                    'touched': [], 'resumed': None, 'before_resume': []}
        self.modes: dict[str, Any] | None = None  # the agent's session modes: current and available
        self.config: list[dict[str, Any]] = []  # the agent's config options, as it sent them
        self.sources: dict[str, list[dict[str, str]]] | None = None  # the sources layer's paths, read when needed
        self.permissions: dict[str, dict[str, Any]] = {}  # each permission request asked, by its request id
        self.patches: dict[str, tuple[Any, dict[str, Any]]] = {}  # a running call's diffs, worked out once each
        self.named: set[str] = set()  # the lines kept for something, such as one tool call, changed in place
        self.lines = 0
        self.tools: dict[str, dict[str, Any]] = {}
        self.flow_kind: str | None = None
        self.flow_text = ''
        self.flow_key: str | None = None  # the note the text being written grows in
        self.flow_at = 0.0
        self.lines_at = 0.0  # when the last `dispatch.lines` event was fired
        self.lines_due: asyncio.TimerHandle | None = None  # the event that covers lines written since, when one waits
        self.flows = 0
        self.asked: dict[str, tuple[asyncio.Future[str | None], list[PermissionOption], str]] = {}
        self.answers: dict[str, tuple[str | None, str | None]] = {}  # the answer revision already delivered
        self.heard = stamp()  # the last session update or prompt, the earliest a tool call first seen next began
        self.turns = 0
        self.active_turn: ActiveTurn | None = None
        self.interrupt_lock = asyncio.Lock()  # cancellation cannot spill into the next queued prompt
        self.pending: deque[str] = deque()  # prompts wait in arrival order while one turn is in flight
        self.idle = asyncio.Event()
        self.idle.set()
        self.lock = asyncio.Lock()
        self.starting = asyncio.Lock()  # shutdown waits for resources an in-flight startup acquires
        self.ended = asyncio.Event()
        self.ending = False
        self.over = asyncio.Event()
        self.how = ''
        self.tasks: set[asyncio.Task[Any]] = set()
        self.failure: Exception | None = None
        self.progress_steps = record.steps_done if record is not None else 0
        self.progress_at = time.monotonic()
        self.progress_calls = 0
        self.failed_input: str | None = None
        self.failed_count = 0

    async def raise_signal(self, signal: str, *, key: str = '', active: bool = True, **details: Any) -> None:
        from .signals import record
        value = await asyncio.to_thread(record, self.store, signal, work_id=self.work_id,
                                        session_id=self.session_id or '', key=key, active=active, **details)
        if value is not None:
            self.lines += 1
            await self.ctx.publish_async('signal.raised' if active else 'signal.cleared', value)
            self.lines_covered()
            await self.ctx.publish_async('map.changed', {'project': self.store.project_id, 'tables': 'dispatch',
                                                       'dispatch_tables': ['dispatch.lines'], 'signal': value})

    async def progress(self) -> None:
        """Observe progress on an incoming event, never with a timer or a repeated wait."""
        if self.prep or self.ending:
            return
        record = await asyncio.to_thread(ticket, self.store, self.work_id)
        if record.steps_done != self.progress_steps or record.done:
            self.progress_steps = record.steps_done
            self.progress_at = time.monotonic()
            self.progress_calls = self.failed_count = 0
            self.failed_input = None
            for signal in ('spinning-calls', 'spinning-time', 'repeated-failure'):
                await self.raise_signal(signal, active=False)
        elif self.turns and not self.asked and time.monotonic() - self.progress_at >= 60 * self.ctx.setting('dispatch_spin_minutes'):
            await self.raise_signal('spinning-time', minutes=self.ctx.setting('dispatch_spin_minutes'))

    @property
    def by(self) -> str:
        return f'{self.agent} {self.session_id}'

    def spawn(self, coroutine: Coroutine[Any, Any, Any]) -> None:
        task = asyncio.create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.finished)

    def finished(self, task: asyncio.Task[Any]) -> None:
        self.tasks.discard(task)
        if not task.cancelled() and (error := task.exception()) is not None:
            self.fail(error)

    def fail(self, error: BaseException) -> None:
        """A failed callback must wake the owner, including callbacks whose errors the ACP SDK catches."""
        if not self.ending and isinstance(error, Exception):
            self.failure = self.failure or error
            self.ended.set()

    # ------------------------------------------------------------------ the map

    async def write(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """One write through the store, off the loop, then `map.changed`, so an open web GUI shows it at once."""
        try:
            result = await asyncio.to_thread(function, *args, **kwargs)
            await self.changed()
        except Exception as error:
            self.fail(error)
            raise
        return result

    async def table(self, change: Callable[[Any], Any], *, name: str = 'lines') -> Any:
        """One write to this module's own tables, off the loop, then `map.changed` naming the dispatch tables, so an
        open agent window shows it at once and an open page reads only its agents again, not the map, STORE-045."""
        def done() -> Any:
            with self.store.tables() as tx:
                return change(tx)
        try:
            result = await asyncio.to_thread(done)
            if name == 'lines':
                await self.lines_changed()
            else:
                await self.changed(tables='dispatch', dispatch_tables=[f'dispatch.{name}'])
        except Exception as error:
            self.fail(error)
            raise
        return result

    async def lines_changed(self) -> None:
        """Announce lines written: at once when none was announced in the last `LINES_EVERY` seconds, otherwise once
        when that time is up, covering every line written meanwhile. Any other event announces them with it."""
        wait = self.lines_at + LINES_EVERY - time.monotonic()
        if wait <= 0:
            await self.changed(tables='dispatch', dispatch_tables=['dispatch.lines'])
        elif self.lines_due is None:
            self.lines_due = asyncio.get_running_loop().call_later(wait, lambda: self.spawn(self.lines_flush()))

    async def lines_flush(self) -> None:
        if self.lines_due is not None:  # an event fired since has announced them
            await self.changed(tables='dispatch', dispatch_tables=['dispatch.lines'])

    def lines_covered(self) -> None:
        """An event about to fire tells readers of the lines too, so a waiting one is not needed."""
        if self.lines_due is not None:
            self.lines_due.cancel()
            self.lines_due = None
        self.lines_at = time.monotonic()

    async def changed(self, tables: str | None = None, *, dispatch_tables: list[str] | None = None) -> None:
        if self.base_id is None:
            active = await asyncio.to_thread(self.store.active_base)
            self.base_id = active.id if active is not None else None
        payload: dict[str, Any] = {'project': self.store.project_id, 'base_id': self.base_id}
        if tables:
            payload['tables'] = tables
        if dispatch_tables is not None and self.lines_due is not None:
            dispatch_tables = sorted({*dispatch_tables, 'dispatch.lines'})
        if dispatch_tables is not None:
            payload['dispatch_tables'] = dispatch_tables
        if tables != 'dispatch' or dispatch_tables is None or 'dispatch.lines' in dispatch_tables:
            self.lines_covered()  # no detail, or the map's tables, reads the agents too
        await self.ctx.publish_async('map.changed', payload)

    def extra(self, state: str) -> dict[str, Any]:
        return {'dispatch': 'session', 'work_id': self.work_id, 'agent': self.agent, 'session_id': self.session_id,
                'nonce': self.number, 'pid': os.getpid(), 'port': self.port, 'token': self.token, 'state': state,
                'how': self.how or None}

    def summary(self, state: str) -> str:
        return f'{self.name} session {self.session_id} on work {self.work_id}: {state}'

    async def note(self, key: str | None, kind: str, text: str) -> None:
        """A line of the session's thread, in this module's tables and never on the map: a new one, or the one kept
        for `key` changed in place."""
        if self.session_id is None:
            return
        session_id = self.session_id
        if key and key in self.named:
            await self.table(lambda tx: tx.update('lines', {'session_id': session_id, 'name': key}, {'text': text}))
            return
        self.lines += 1
        seq = self.lines
        name = key or f'line:{seq}'
        if key:
            self.named.add(key)
        await self.table(lambda tx: tx.insert('lines', {'session_id': session_id, 'name': name, 'work_id': self.work_id,
                                                        'kind': kind, 'text': text, 'seq': seq}))

    async def checked(self, text: str) -> str:
        """A prompt this module sends, checked before it is sent, BASE-057: a flagged one is still sent, with a notice
        in the session's thread and the incomplete-prompt signal."""
        found = axiom.notices('prompt', text)
        if found:
            await self.note(None, 'notice', ' '.join(one['message'] for one in found))
            await self.raise_signal(axiom.SIGNAL, notices=found)
        return text

    async def flush(self) -> None:
        """The message or thought text gathered so far, as one note: the note it has grown in while it was written."""
        kind, text, key = self.flow_kind, self.flow_text, self.flow_key
        self.flow_kind, self.flow_text, self.flow_key = None, '', None
        if kind is not None and text:
            await self.note(key, kind, text)

    # ------------------------------------------------------------------ the ACP client, called by the SDK

    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
        data: dict[str, Any] = update.model_dump(mode='json', by_alias=True, exclude_none=True)
        kind = str(data.get('sessionUpdate', ''))
        if self.replaying and kind not in STATE_UPDATES:
            return  # the history session/load replays is in the thread already
        heard, self.heard = self.heard, stamp()
        async with self.lock:
            await self.progress()
            if kind in CHUNKS:
                if kind != self.flow_kind:
                    await self.flush()
                    self.flow_kind = kind
                    self.flows += 1
                    self.flow_key = f'flow:{self.flows}'
                self.flow_text += chunk_text(data.get('content'))
                now = time.monotonic()
                if now - self.flow_at >= STREAM_EVERY:  # the text so far, grown in place, so it reads as it is written
                    self.flow_at = now
                    await self.note(self.flow_key, kind, self.flow_text)
                return
            await self.flush()
            if kind in ('tool_call', 'tool_call_update'):
                ident = str(data.get('toolCallId', ''))
                fresh = ident not in self.tools
                # a call first seen before it completes began then; one first seen complete, after the update before it
                known = self.tools.setdefault(ident, {'began': heard if data.get('status') == 'completed' else
                                                      self.heard})
                for field in ('title', 'kind', 'status', 'rawInput'):
                    if data.get(field):
                        known[field] = data[field]
                for field in ('content', 'locations'):  # an update that carries either replaces it whole, as ACP says
                    if field in data:
                        known[field] = data[field]
                title = known.get('title') or known.get('kind') or 'A tool call'
                await self.note(f'tool:{ident}', kind, f'{title} ({known.get("status", "pending")})')
                detail = await self.tool_detail({**known, 'toolCallId': ident, 'title': title})
                if detail is not None:
                    await self.note(f'detail:{ident}', 'tool_detail', json.dumps(detail, ensure_ascii=False))
                    await self.touch(detail['nodes'], str(known.get('kind') or 'other'))
                if fresh and not self.prep and not self.ending:
                    self.progress_calls += 1
                    if self.progress_calls >= self.ctx.setting('dispatch_spin_calls'):
                        await self.raise_signal('spinning-calls', calls=self.progress_calls)
                if not self.prep and not self.ending and known.get('status') in ('failed', 'completed') and not known.get('counted'):
                    known['counted'] = True
                    if known['status'] == 'failed':
                        fingerprint = json.dumps([known.get('kind'), title, known.get('rawInput')], sort_keys=True)
                        self.failed_count = self.failed_count + 1 if fingerprint == self.failed_input else 1
                        self.failed_input = fingerprint
                        if self.failed_count >= self.ctx.setting('dispatch_repeat_failures'):
                            await self.raise_signal('repeated-failure', calls=self.failed_count, tool=title)
                    else:
                        self.failed_input, self.failed_count = None, 0
                if known.get('status') in ('failed', 'completed'):
                    # Its line and its detail line hold what it did; a long session keeps no copy of each file's text.
                    for field in ('content', 'locations', 'rawInput'):
                        known.pop(field, None)
            elif kind == 'plan':
                entries: list[Any] = data.get('entries') or []
                said = [cast(dict[str, Any], entry) for entry in entries if isinstance(entry, dict)]
                await self.note('plan', kind, '\n'.join(f'{entry.get("content")} ({entry.get("status")})'
                                                        for entry in said))
                self.acp['plan'] = [{key: entry.get(key) for key in ('content', 'priority', 'status')} for entry in said]
                self.reported('plan')
                await self.save_state()
            elif kind in STATE_UPDATES:
                self.updated(kind, data)
                await self.save_state()
            else:
                rest = {key: value for key, value in data.items() if key != 'sessionUpdate'}
                await self.note(kind, kind, json.dumps(rest, ensure_ascii=False))

    def reported(self, key: str) -> None:
        """The agent has reported this part of its state since a resume; a replay of its history has not."""
        if not self.replaying and key in self.acp['before_resume']:
            self.acp['before_resume'] = [held for held in self.acp['before_resume'] if held != key]

    def updated(self, kind: str, data: dict[str, Any]) -> None:
        """One update to what the session is, kept in its state."""
        if kind == 'available_commands_update':
            commands = cast(list[dict[str, Any]], data.get('availableCommands') or [])
            self.acp['commands'] = [{'name': one.get('name'), 'description': one.get('description'),
                                     'hint': cast(dict[str, Any], one.get('input') or {}).get('hint')}
                                    for one in commands]
            self.reported('commands')
        elif kind == 'current_mode_update':
            self.modes = {**(self.modes or {'available': []}), 'current': data.get('currentModeId')}
        elif kind == 'config_option_update':
            self.config = cast(list[dict[str, Any]], data.get('configOptions') or [])
        elif kind == 'session_info_update':
            for key, field in (('title', 'title'), ('updatedAt', 'updated_at')):
                if key in data:
                    self.acp[field] = data[key]
                    self.reported(field)
        elif kind == 'usage_update':
            self.acp['usage'] = {'used': data.get('used'), 'size': data.get('size'), 'cost': data.get('cost')}
            self.reported('usage')

    # ------------------------------------------------------------------ what the session is, for the page

    def capture(self, init: InitializeResponse) -> None:
        """What the agent said it can do when it was initialized."""
        caps = init.agent_capabilities
        session = caps.session_capabilities if caps is not None else None
        prompts = caps.prompt_capabilities if caps is not None else None
        self.acp['capabilities'] = {
            'load': bool(caps is not None and caps.load_session),
            'resume': bool(session is not None and session.resume is not None),
            'list': bool(session is not None and session.list is not None),
            'close': bool(session is not None and session.close is not None),
            'fork': bool(session is not None and session.fork is not None),
            'image': bool(prompts is not None and prompts.image),
            'audio': bool(prompts is not None and prompts.audio),
            'embedded_context': bool(prompts is not None and prompts.embedded_context)}
        info = init.agent_info
        self.acp['agent_info'] = info.model_dump(mode='json', exclude_none=True, exclude={'field_meta'}) \
            if info is not None else None

    def apply(self, made: Any) -> None:
        """The modes and config options a session/new, load or resume answered with."""
        if made is None:
            return
        modes = getattr(made, 'modes', None)
        if modes is not None:
            self.modes = {'current': modes.current_mode_id,
                          'available': [{'id': mode.id, 'name': mode.name, 'description': mode.description}
                                        for mode in modes.available_modes]}
        options = getattr(made, 'config_options', None)
        if options is not None:
            self.config = [option.model_dump(mode='json', by_alias=True, exclude_none=True) for option in options]

    def settings(self) -> list[dict[str, Any]]:
        """What the person can set on this session, each a select or a switch: the agent's config options, a model
        among them, and its session modes as one more select, `source` mode, unless a config option already is the
        mode, which ACP says supersedes the modes."""
        found = [setting_of(option) for option in self.config]
        available = cast(list[dict[str, Any]], (self.modes or {}).get('available') or [])
        if available and not any(one['category'] == 'mode' for one in found):
            taken = {one['id'] for one in found}
            found.insert(0, {'id': 'mode' if 'mode' not in taken else 'session_mode', 'name': 'Mode',
                             'description': None, 'category': 'mode', 'type': 'select',
                             'current': (self.modes or {}).get('current'),
                             'options': [{'value': mode['id'], 'name': mode['name'],
                                          'description': mode.get('description'), 'group': None}
                                         for mode in available], 'source': 'mode'})
        return found

    async def save_state(self) -> None:
        """The session's state line, kept at its latest."""
        await self.note('state', 'state', json.dumps({**self.acp, 'settings': self.settings()}, ensure_ascii=False))

    async def places(self) -> dict[str, list[dict[str, str]]]:
        if self.sources is None:
            self.sources = await asyncio.to_thread(sources_index, self.store, self.root)
        return self.sources

    async def tool_detail(self, call: dict[str, Any]) -> dict[str, Any] | None:
        """What a tool call acts on, structured: each file it edits as a diff, each place it reads or writes, each
        terminal it runs, every file placed on the map; None for a call that names none."""
        content = cast(list[dict[str, Any]], call.get('content') or [])
        locations = cast(list[dict[str, Any]], call.get('locations') or [])
        edits = [one for one in content if one.get('type') == 'diff']
        terminals = [str(one.get('terminalId')) for one in content if one.get('type') == 'terminal']
        if not (edits or locations or terminals):
            return None
        index = await self.places()
        roots = [self.folder, self.root]
        nodes: list[dict[str, str]] = []

        def where(path: str) -> tuple[str, list[dict[str, str]]]:
            named = relative(path, roots)
            found = placed(index, named)
            nodes.extend(place for place in found if place not in nodes)
            return named or path, found

        diffs: list[dict[str, Any]] = []
        for at, edit in enumerate(edits):
            path, found = where(str(edit.get('path', '')))
            old, new = edit.get('oldText'), str(edit.get('newText', ''))
            key, sign = f'{call.get("toolCallId")}:{at}', (path, hash(old), hash(new))
            held = self.patches.get(key)  # a status update carries the same diff again
            worked = held[1] if held is not None and held[0] == sign else \
                await asyncio.to_thread(unified, path, old, new)
            if call.get('status') in ('completed', 'failed'):
                self.patches.pop(key, None)  # the call is over: its diff is in its line
            else:
                self.patches[key] = (sign, worked)
            diffs.append({'path': path, **worked, 'nodes': found})
        places: list[dict[str, Any]] = []
        for location in locations:
            path, found = where(str(location.get('path', '')))
            places.append({'path': path, 'line': location.get('line'), 'nodes': found})
        return {'tool_call_id': call.get('toolCallId'), 'title': call.get('title'), 'kind': call.get('kind'),
                'status': call.get('status', 'pending'), 'diffs': diffs, 'locations': places,
                'terminals': terminals, 'nodes': nodes}

    async def touch(self, nodes: list[dict[str, str]], action: str) -> None:
        """The parts of the map this session has touched, the latest first, kept in its state."""
        if not nodes:
            return
        held = cast(list[dict[str, str]], self.acp['touched'])
        fresh = [{**place, 'action': action} for place in nodes]
        kept = fresh + [one for one in held if (one['kind'], one['id']) not in {(p['kind'], p['id']) for p in fresh}]
        if kept[:TOUCHED_KEPT] != held:
            self.acp['touched'] = kept[:TOUCHED_KEPT]
            await self.save_state()

    async def configure(self, setting: str, value: str) -> dict[str, Any]:
        """Set one of the session's settings, as the person chose: a mode with session/set_mode, anything else with
        session/set_config_option; the agent's answer is the settings from then on."""
        if self.ending or self.session_id is None or self.conn is None:
            return {'error': 'The session has not started or is ending.'}
        offered = self.settings()
        found = next((one for one in offered if one['id'] == setting), None)
        if found is None:
            return {'error': f'{self.name} offers no setting {setting} on this session; it offers: '
                             f'{", ".join(str(one["id"]) for one in offered) or "none"}.'}
        try:
            if found['type'] == 'boolean':
                given = switched(value)
                if given is None:
                    return {'error': f'{found["name"]} is on or off, not {value}.'}
                answer = await asyncio.wait_for(self.conn.set_config_option(
                    config_id=found['id'], session_id=self.session_id, value=given), SETTING_LIMIT)
                chosen, shown = given, 'on' if given else 'off'
            else:
                choices = cast(list[dict[str, Any]], found['options'])
                option = next((one for one in choices if one['value'] == value), None) or next(
                    (one for one in choices if str(one['name']).casefold() == value.strip().casefold()), None)
                if option is None:
                    listed = ', '.join(f"{one['name']} ({one['value']})" for one in choices)
                    return {'error': f'{value} is none of the choices of {found["name"]}: {listed}.'}
                chosen, shown = option['value'], option['name']
                if found['source'] == 'mode':
                    answer = await asyncio.wait_for(self.conn.set_session_mode(
                        session_id=self.session_id, mode_id=chosen), SETTING_LIMIT)
                    self.modes = {**(self.modes or {'available': []}), 'current': chosen}
                else:
                    answer = await asyncio.wait_for(self.conn.set_config_option(
                        config_id=found['id'], session_id=self.session_id, value=chosen), SETTING_LIMIT)
        except Exception as error:  # noqa: BLE001  the agent's refusal is the person's to read
            return {'error': f'{self.name} did not take {found["name"]}: {error}'}
        if found['source'] == 'option':
            options = getattr(answer, 'config_options', None)
            if options is not None:
                self.apply(answer)
            else:  # an agent that answers with nothing has taken the value as given
                self.config = [{**option, 'currentValue': chosen} if option.get('id') == found['id'] else option
                               for option in self.config]
        async with self.lock:
            await self.flush()
            await self.note(None, 'setting', f'{found["name"]} set to {shown}.')
            await self.save_state()
        return {'setting': found['id'], 'value': chosen, 'settings': self.settings()}

    async def permission(self, request: str, **changes: Any) -> None:
        """A permission request's line, kept at its latest: waiting, answered, unmatched or cancelled."""
        held = self.permissions.get(request)
        if held is None:
            return
        held.update(changes)
        await self.note(f'permission:{request}', 'permission', json.dumps(held, ensure_ascii=False))

    async def permit(self, request: str, option: str) -> dict[str, Any]:
        """The person's choice for a waiting permission request, given on the page: it answers the agent at once, and
        its question at the node, when there is one, is closed with the option's name, as an answer there would be."""
        held = self.asked.get(request)
        if held is None:
            return {'error': f'No permission request {request} waits on this session.'}
        waiting, options, title = held
        chosen = choose(options, option)
        if chosen is None:
            return {'error': f'{option} is none of the options: '
                             f'{", ".join(f"{one.name} ({one.option_id})" for one in options)}.'}
        name = next(one.name for one in options if one.option_id == chosen)
        async with self.lock:
            if self.asked.get(request) is not held:  # answered at the node meanwhile
                return {'error': f'Permission request {request} was answered already.'}
            del self.asked[request]
            message_id = self.permissions.get(request, {}).get('message_id')
            if message_id:
                await self.write(self.store.reply, message_id, name)
            await self.raise_signal('permission-waiting', key=request, active=False, message_id=message_id,
                                    request=request, tool=title)
            self.progress_at = time.monotonic()  # waiting for a person is not agent spinning
            await self.permission(request, state='answered', chosen=chosen, answer=name)
        if not waiting.done():
            waiting.set_result(chosen)
        return {'request': request, 'chosen': chosen, 'answer': name}

    # ------------------------------------------------------------------ permission requests

    async def request_permission(self, session_id: str, tool_call: ToolCallUpdate, options: list[PermissionOption],
                                 **kwargs: Any) -> RequestPermissionResponse:
        """Asked at the ticket's node with the options as suggestions, and on the page as a choice among them; the
        agent waits for the person's choice."""
        waiting: asyncio.Future[str | None] = asyncio.get_running_loop().create_future()
        title = str(tool_call.title or tool_call.kind or 'a tool call')
        how = await asyncio.to_thread(self.ctx.setting, 'dispatch_prompts')  # as set now, so a change reaches this agent
        allow = next((option for option in options if str(option.kind) == 'allow_once'), None)
        if allow is not None and (how == 'approve-all' or (how == 'approve-reads' and str(tool_call.kind) in READS)):
            async with self.lock:
                await self.flush()
                await self.note(None, 'approved', f'{title}: approved by dispatch_prompts={how}')
            return RequestPermissionResponse(outcome=AllowedOutcome(option_id=allow.option_id, outcome='selected'))
        call = tool_call.model_dump(mode='json', by_alias=True, exclude_none=True)
        detail = await self.tool_detail({**call, 'title': title})  # what it would act on, shown before it does
        async with self.lock:
            await self.flush()
            await self.ask(waiting, options, title, '', call, detail)
        chosen = await waiting
        await self.changed(tables='dispatch')
        if chosen is None:
            return RequestPermissionResponse(outcome=DeniedOutcome(outcome='cancelled'))
        return RequestPermissionResponse(outcome=AllowedOutcome(option_id=chosen, outcome='selected'))

    async def ask(self, waiting: asyncio.Future[str | None], options: list[PermissionOption], title: str,
                  before: str, call: dict[str, Any] | None = None, detail: dict[str, Any] | None = None) -> None:
        if self.ending or (self.active_turn is not None and self.active_turn.cancel_requested):
            if not waiting.done():
                waiting.set_result(None)
            return
        message_id: str | None = None
        if self.node is not None:
            text = f'{before}{self.name} asks permission on work {self.work_id}: {title}'
            asked = await self.write(self.store.ask, self.node, text, suggestions=[option.name for option in options],
                                     by=self.by, work=self.work_id)
            request = message_id = asked.id
        else:
            request = uuid.uuid4().hex
        self.asked[request] = (waiting, options, title)
        self.permissions[request] = {
            'request': request, 'message_id': message_id, 'tool_call_id': (call or {}).get('toolCallId'),
            'title': title, 'kind': (call or {}).get('kind'),
            'options': [{'option_id': option.option_id, 'name': option.name, 'kind': str(option.kind)}
                        for option in options],
            'detail': detail, 'state': 'waiting', 'chosen': None, 'answer': None, 'asked': stamp(),
            'said': before.strip() or None}
        await self.permission(request)
        await self.raise_signal('permission-waiting', key=request, message_id=message_id, request=request, tool=title)
        await self.changed(tables='dispatch', dispatch_tables=['dispatch.lines', 'dispatch.permissions'])

    async def check(self) -> None:
        """Resolve permission requests the person answered on the page, and end the session once its ticket is done
        while no prompt of its own runs, whatever turn closed it, VIEW-035."""
        if not self.ending and self.turns == 0 and not self.prep:
            record = await asyncio.to_thread(ticket, self.store, self.work_id)
            if record.done and not self.ending and self.turns == 0:
                self.spawn(self.end('the ticket is done'))
                return
        async with self.lock:
            await self.progress()
            if not self.asked or self.node is None:  # with no node, nothing is asked as a question
                return
            found = await asyncio.to_thread(self.store.messages, self.node, 'question', None, limit=0)
            for message in found.results:
                held = self.asked.get(message.id)
                if held is None or message.closed is None:
                    continue
                del self.asked[message.id]
                await self.raise_signal('permission-waiting', key=message.id, active=False,
                                        message_id=message.id, request=message.id, tool=held[2])
                self.progress_at = time.monotonic()  # waiting for a person is not agent spinning
                self.answers[message.id] = (message.closed, message.answer)
                waiting, options, title = held
                chosen = choose(options, message.answer)
                if chosen is not None:
                    await self.permission(message.id, state='answered', chosen=chosen, answer=message.answer)
                    if not waiting.done():
                        waiting.set_result(chosen)
                    continue
                await self.permission(message.id, state='unmatched', answer=message.answer)
                asked = self.permissions.get(message.id, {})
                call = {'toolCallId': asked.get('tool_call_id'), 'kind': asked.get('kind')}
                await self.ask(waiting, options, title, f'The answer "{message.answer}" names none of the options. ',
                               call, asked.get('detail'))

    # ------------------------------------------------------------------ the session

    async def run(self) -> dict[str, Any]:
        server = await asyncio.start_server(self.control, '127.0.0.1', 0)
        self.port = int(server.sockets[0].getsockname()[1])
        loop = asyncio.get_running_loop()
        listener = self.ctx.listen(lambda payload: loop.call_soon_threadsafe(self.changed_elsewhere, payload))
        with contextlib.suppress(NotImplementedError):  # Windows ends a process with no signal it can handle
            loop.add_signal_handler(signal.SIGTERM, lambda: self.spawn(self.end(TERMINATED)))
        try:
            async with self.starting:
                await self.begin()
            await self.ended.wait()
            if self.failure is not None:
                raise self.failure
        except Exception as error:  # noqa: BLE001  the agent did not start; the map says why
            said = 'did not start' if self.session_id is None else 'failed'
            sys.stderr.write(f'{self.name} {said} on work {self.work_id}: {error}\n')
            self.how = f'it {said}: {error}'
            try:
                await self.note(None, 'failed', f'{self.name} {said} on work {self.work_id}: {error}')
            except Exception as note_error:  # noqa: BLE001  a failure note cannot prevent resource cleanup
                sys.stderr.write(f'Could not record the session failure: {note_error}\n')
        finally:
            with contextlib.suppress(NotImplementedError):
                loop.remove_signal_handler(signal.SIGTERM)
            try:
                await asyncio.shield(self.end(self.how or 'the runner ended'))
            finally:
                pending = tuple(self.tasks)
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                try:
                    await asyncio.to_thread(listener.close)
                finally:
                    server.close()
                    await server.wait_closed()
        return {'work_id': self.work_id, 'agent': self.agent, 'session_id': self.session_id, 'ended': self.how}

    async def begin(self) -> None:
        if self.ending:
            return
        if self.resume:  # the thread goes on where it ended: its lines keep their names and their order
            await asyncio.to_thread(self.continue_thread)
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.subprocess_exec(
            lambda: Exits(LINE_LIMIT, loop), *self.command, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=None, cwd=self.folder, env=dict(os.environ), **group_options())
        self.process, self.exited = asyncio.subprocess.Process(transport, protocol, loop), protocol.exited
        if self.ending:
            return
        self.spawn(self.watch(self.process))
        self.conn = acp.connect_to_agent(self, self.process.stdin, self.process.stdout)  # pyright: ignore[reportArgumentType]
        try:
            version = metadata.version('metaform')
        except metadata.PackageNotFoundError:
            version = '0'
        # The client offers no file system and no terminal of its own: the agent reads, writes and runs in the folder
        # it works in, and each tool call says where. It takes boolean config options, so every setting reaches the page.
        init = await asyncio.wait_for(self.conn.initialize(
            protocol_version=acp.PROTOCOL_VERSION,
            client_capabilities=ClientCapabilities(
                fs=FileSystemCapabilities(read_text_file=False, write_text_file=False), terminal=False,
                session=ClientSessionCapabilities(config_options=SessionConfigOptionsCapabilities(
                    boolean=BooleanConfigOptionCapabilities()))),
            client_info=Implementation(name='metaform', title='Metaform', version=version)), START_LIMIT)
        self.capture(init)
        if self.ending:
            return
        servers = [McpServerStdio(name='metaform', command=sys.executable, args=['-m', 'metaform', 'mcp', 'serve'],
                                  env=[])]
        if self.resume:
            made = await asyncio.wait_for(self.reopen(servers), START_LIMIT)
        else:
            made = await asyncio.wait_for(self.conn.new_session(cwd=self.folder, mcp_servers=servers), START_LIMIT)
            self.session_id = str(made.session_id)
        self.apply(made)
        if self.ending:
            return
        from .recovery import resources
        recovery = await asyncio.to_thread(resources, self.store.project_id, self.work_id, cast(str, self.session_id),
                                            self.process.pid)
        self.number = await asyncio.to_thread(nonce.request, 'dispatch', 'handoff',
                                              {'work_id': self.work_id, 'agent': self.agent,
                                               'session_id': self.session_id, 'recovery': recovery})
        if self.ending:
            return
        row = {key: value for key, value in self.extra('running').items() if key != 'dispatch'}
        row.update(started=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), seq=time.time_ns() // 1_000_000)
        def take() -> None:
            with self.store.atomic():
                if not self.prep:
                    record = ticket(self.store, self.work_id)
                    if self.resume:  # a worker resumed in place goes on only with the ticket still its own
                        if record.done or record.taken_by != self.by:
                            raise Stop(f'Work {self.work_id} is no longer taken by session {self.session_id}, so it '
                                       'cannot be resumed as its worker.',
                                       f'metaform dispatch talk session={self.work_id}:{self.session_id}')
                    else:
                        if self.took:
                            if record.taken_by != self.ctx.nouns['reservation']:
                                raise Stop('The startup reservation is no longer held.', 'metaform map work open=true')
                            self.store.move_work(self.work_id, 'todo', record.position)
                        self.store.take_work(self.work_id, None, self.by)
                with self.store.tables() as tx:
                    if self.resume:  # the ended session's own row runs again
                        # Two resumes at once, a second click on Resume, would run one ACP session twice: the first
                        # to get here holds it, and a row another live runner of this work holds is not taken over.
                        held = tx.rows('sessions', {'session_id': self.session_id}, limit=1).results
                        other = held[0]['pid'] if held and held[0]['state'] == 'running' else None
                        if other not in (None, os.getpid()) and runner_of(other) == self.work_id:
                            raise Stop(f'Session {self.session_id} has been resumed already.',
                                       f'metaform dispatch sessions id={self.work_id}')
                        tx.update('sessions', {'session_id': self.session_id},
                                  {key: row[key] for key in ('state', 'nonce', 'pid', 'port', 'token', 'how')})
                    else:
                        tx.insert('sessions', row)
            # Acquisition is complete before write publishes its change. A failed announcement still needs release.
            self.took = not self.prep
            self.recorded = True
        await self.write(take)
        if self.node is None:  # an intake agent stays in the metaform it began in, whichever becomes active later
            bound = await asyncio.to_thread(self.store.bound_base)
            if bound is not None:
                self.store = Store(self.store.project_id, base=bound.id, module=self.store.module)
        await self.save_state()
        if self.ending or self.resume:  # a resumed session waits for the person's next message
            return
        if self.node is None and self.ctx.nouns.get('intake'):  # the intake, served as it is, VIEW-045 and BASE-039
            self.turn(await asyncio.to_thread(intake_prompt, self.ctx, await asyncio.to_thread(self.asked_for)))
            return
        if self.system and self.ctx.nouns.get('sentinel'):  # the person raised an issue: the sentinel skill, VIEW-045
            address = str(self.ctx.nouns['sentinel'])
            record = await asyncio.to_thread(ticket, self.store, self.work_id)
            given = f'node: {address}\nticket: {self.work_id}\nreport:\n{record.note or ""}'
            self.turn(await asyncio.to_thread(workflow_skill, self.ctx, 'sentinel', given))
            return
        if self.system and self.ctx.nouns.get('talk'):  # the person clicked something to talk about: no ticket work
            about, read = await asyncio.to_thread(subject, self.store, self.work_id, str(self.ctx.nouns['talk']))
            self.turn(prompt('talk', about=about, read=read))
            return
        if self.system:
            self.turn(prompt('system', project=self.store.project_id))
            return
        if self.prep:
            from .merge import branch_of, dev_branch
            self.turn(prompt('prep', work_id=self.work_id, branch=branch_of(self.work_id),
                             dev=dev_branch(self.store.project().path) or 'the dev branch'))
            return
        text = await self.checked(prompt('handoff', work_id=self.work_id))
        if not self.ending:
            self.turn(text)

    def asked_for(self) -> str:
        """What the person asked the intake for, from the nonce its launch kept it in, so their words never go in an
        argument; the nonce is closed once read. Nothing asked is this project."""
        number = self.ctx.nouns.get('asked')
        if not number:
            return ''
        held = nonce.read(str(number))
        if held is None:
            return ''
        nonce.close(held.nonce)
        value: Any = held.value
        return str(cast(dict[str, Any], value).get('text') or '') if isinstance(value, dict) else ''

    async def reopen(self, servers: list[McpServerStdio]) -> Any:
        """The ended session made live again: session/resume where the agent offers it, which sends nothing back, or
        else session/load, which replays the history the thread already holds and is not written again."""
        caps = cast(dict[str, Any], self.acp['capabilities'])
        session_id = cast(str, self.resume)
        if caps.get('resume'):
            self.acp['resumed'] = 'resume'
            return await self.conn.resume_session(session_id=session_id, cwd=self.folder, mcp_servers=servers)
        if caps.get('load'):
            self.acp['resumed'] = 'load'
            self.replaying = True
            return await self.conn.load_session(cwd=self.folder, session_id=session_id, mcp_servers=servers)
        raise RuntimeError(f'{self.name} offers neither session/resume nor session/load, so session {session_id} '
                           'cannot be resumed')

    def continue_thread(self) -> None:
        """Take up the ended session's thread: the names its lines are kept by, the last of their order, what its
        state held of the map it touched, and what it last reported of itself, its plan, usage, tokens, title and
        commands, each named in `before_resume` until the agent reports it again. Its settings and capabilities are
        not carried: the agent gives them afresh when it starts and resumes."""
        with self.store.tables(write=False) as tx:
            rows = tx.rows('lines', {'session_id': self.session_id}, by=('session_id', 'seq'), limit=0).results
        self.named = {str(row['name']) for row in rows}
        self.lines = max((int(row['seq']) for row in rows), default=0)
        self.flows = max((int(name[5:]) for name in self.named if name.startswith('flow:') and name[5:].isdigit()),
                         default=0)
        kept = next((row for row in rows if row['name'] == 'state'), None)
        before: Any = None
        if kept is not None:
            with contextlib.suppress(ValueError, TypeError):
                before = json.loads(str(kept['text']))
        if isinstance(before, dict):
            held = cast(dict[str, Any], before)
            self.acp['touched'] = list(held.get('touched') or [])
            carried = [key for key in CARRIED if held.get(key) not in (None, [], '')]
            self.acp.update({key: held[key] for key in carried})
            self.acp['before_resume'] = carried

    def turn(self, text: str) -> None:
        if self.ending:
            return
        self.replaying = False  # what comes from here on is the session's own, never a replay
        self.pending.append(text)
        if self.turns == 0:
            self.progress_at = time.monotonic()
        if self.turns:
            return
        self.turns = 1
        self.active_turn = ActiveTurn()
        self.idle.clear()
        self.spawn(self.prompted())

    async def prompted(self) -> None:
        """One prompt in flight, draining messages in order before the normal turn-end decision."""
        try:
            while self.pending and not self.ending:
                async with self.interrupt_lock:
                    current = self.active_turn or ActiveTurn()
                    self.active_turn = current
                    text = self.pending.popleft()
                self.heard = stamp()  # a tool call of this turn began no earlier than its prompt
                try:
                    await self.changed(tables='dispatch')
                    if self.ending:
                        break  # stop may arrive while the turn-start event is published
                    if current.cancel_requested:
                        reason = 'cancelled'
                    else:
                        current.sent = True
                        answer = await self.conn.prompt(session_id=self.session_id, prompt=[acp.text_block(text)])
                        reason = str(answer.stop_reason)
                        if answer.usage is not None:  # the tokens of the session so far, as the agent counts them
                            self.acp['tokens'] = answer.usage.model_dump(mode='json', exclude_none=True,
                                                                         exclude={'field_meta'})
                            self.reported('tokens')
                except Exception as error:  # noqa: BLE001  the turn's end is noted whatever ended it
                    reason = f'error: {error}'
                async with self.interrupt_lock:
                    self.active_turn = None
                async with self.lock:
                    await self.flush()
                    await self.note('turn', 'turn', f'The turn ended: {reason}.')
                    if self.acp['tokens'] is not None:
                        await self.save_state()
        finally:
            self.turns -= 1
            if self.turns == 0:
                self.idle.set()
        await self.changed(tables='dispatch')  # readers now see idle after the queue drained
        if self.turns == 0 and not self.ending and not self.prep:
            record = await asyncio.to_thread(ticket, self.store, self.work_id)
            if self.turns or self.ending:  # a message can arrive while the ticket is read
                return
            if record.done:
                await self.end('the ticket is done')
            # Otherwise the agent stopped with its ticket open: the session stays, idle and reachable, and the
            # ticket stays taken with the agent's last note, until the person talks to it, stops it or puts the
            # ticket back. Nothing restarts by itself, change order of 2026-10-07.

    async def interrupt(self) -> bool:
        """Request cancellation of only the current turn; its response owns completion and queued prompts stay serial."""
        async with self.interrupt_lock:
            current = self.active_turn
            if self.ending or self.session_id is None or current is None:
                return False
            if current.cancel_requested:
                return True
            current.cancel_requested = True
            if current.sent:
                try:
                    await asyncio.wait_for(self.conn.cancel(session_id=self.session_id), END_LIMIT)
                except Exception:
                    current.cancel_requested = False  # a failed notification must allow a real retry
                    raise
            async with self.lock:
                for request, (waiting, _, title) in list(self.asked.items()):
                    message_id = self.permissions.get(request, {}).get('message_id')
                    if message_id:  # closed history remains, without live answer controls
                        await self.write(self.store.reply, message_id)
                    if not waiting.done():
                        waiting.set_result(None)
                    await self.raise_signal('permission-waiting', key=request, active=False,
                                            message_id=message_id, request=request, tool=title)
                    await self.permission(request, state='cancelled')
                self.asked.clear()
                await self.flush()
                await self.note(None, 'interrupt', 'Cancellation of the current turn requested.')
            await self.changed(tables='dispatch')
            return True

    async def watch(self, process: asyncio.subprocess.Process) -> None:
        await self.exited.wait()
        code = process.returncode
        if not self.ending:
            await self.end(f'the agent ended with exit code {code}')

    def changed_elsewhere(self, payload: dict[str, Any]) -> None:
        """map.changed from another process, handed over by the base's listener, BASE-053: a change to this project
        may be the person's answer to a permission prompt, so they are checked. A change to the map itself may move the
        refs that place a file on it, so they are read again when next needed."""
        if payload.get('project') == self.store.project_id and not self.ending:
            if payload.get('tables') != 'dispatch':
                self.sources = None
            self.spawn(self.check())

    async def control(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """One request on the control port, with this session's token: `status`, `message`, `interrupt`, `stop`, and
        the person's own controls of the session, `permit` a permission request's option and `configure` a setting."""
        try:
            line = await asyncio.wait_for(reader.readline(), REPLY_LIMIT)
            found: Any = json.loads(line) if line else None
            asked = cast(dict[str, Any], found) if isinstance(found, dict) else {}
            if asked.get('token') != self.token:
                await self.reply(writer, {'error': 'This is not a request for this session.'})
                return
            said = {'work_id': self.work_id, 'agent': self.agent, 'session_id': self.session_id}
            op = asked.get('op')
            if op == 'status':
                alive = self.process is not None and self.process.returncode is None and not self.exited.is_set()
                live = alive and not self.ending and self.failure is None
                activity = ('waiting' if self.asked else 'working' if self.turns else 'idle') if live else 'idle'
                await self.reply(writer, {**said, 'state': 'running' if live else 'ended', 'agent_alive': alive,
                                          'activity': activity,
                                          'interrupting': bool(self.active_turn and self.active_turn.cancel_requested),
                                          'how': None if live else self.how or 'the agent is no longer running'})
            elif op == 'message':
                if self.ending or self.session_id is None:
                    await self.reply(writer, {**said, 'sent': False, 'error': 'The session has not started or is ending.'})
                    return
                text = str(asked.get('text', ''))
                async with self.lock:  # the person's words in the thread, where the agent's reply follows
                    await self.flush()
                    await self.note(None, 'person', text)
                self.turn(text)
                await self.reply(writer, {**said, 'sent': True})
            elif op == 'interrupt':
                try:
                    requested = await self.interrupt()
                    await self.reply(writer, {**said, 'requested': requested})
                except Exception as error:  # noqa: BLE001  a failed cancel is reported without destroying the session
                    await self.reply(writer, {**said, 'error': f'Could not interrupt the turn: {error}'})
            elif op == 'permit':
                await self.reply(writer, {**said, **await self.permit(str(asked.get('request', '')),
                                                                      str(asked.get('option', '')))})
            elif op == 'configure':
                await self.reply(writer, {**said, **await self.configure(str(asked.get('setting', '')),
                                                                         str(asked.get('value', '')))})
            elif op == 'stop':
                await self.end('stopped by the person', release=False)
                try:
                    await self.reply(writer, {**said, 'stopped': True})
                finally:
                    self.ended.set()
            else:
                await self.reply(writer, {'error': f'No request {op}.'})
        except (TimeoutError, OSError, ValueError):
            pass
        finally:
            with contextlib.suppress(Exception):
                writer.close()

    @staticmethod
    async def reply(writer: asyncio.StreamWriter, answer: dict[str, Any]) -> None:
        writer.write(json.dumps(answer).encode('utf-8') + b'\n')
        await writer.drain()

    async def end(self, how: str, release: bool = True) -> None:
        """End the session once: cancel a running turn, answer every waiting request as cancelled, close the agent's
        input, end its process group, close the nonce and say on the map how it ended."""
        if self.ending:
            await self.over.wait()
            if release:
                self.ended.set()
            return
        self.ending, self.how = True, how
        self.pending.clear()
        try:
            # Cancelling startup would abandon to_thread writes or a child being created. Let the current
            # acquisition finish and let begin observe ending before proceeding, then clean up its resources.
            async with self.starting:
                pass
            for request, (waiting, _, title) in list(self.asked.items()):
                if not waiting.done():
                    waiting.set_result(None)
                with contextlib.suppress(Exception):
                    await self.raise_signal('permission-waiting', key=request, active=False,
                                            message_id=self.permissions.get(request, {}).get('message_id'),
                                            request=request, tool=title)
                with contextlib.suppress(Exception):
                    await self.permission(request, state='cancelled')
            self.asked.clear()
            process = self.process
            if process is not None and process.returncode is None:
                if self.turns and self.conn is not None and self.session_id is not None:
                    with contextlib.suppress(Exception):
                        await self.conn.cancel(session_id=self.session_id)
                    with contextlib.suppress(asyncio.TimeoutError):
                        await asyncio.wait_for(self.idle.wait(), END_LIMIT)
                if process.stdin is not None:
                    with contextlib.suppress(Exception):
                        process.stdin.close()
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(self.exited.wait(), END_LIMIT)
            if process is not None:
                await asyncio.to_thread(end_group, process.pid)  # what it started ends with it
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(process.wait(), END_LIMIT)
            if self.conn is not None:
                with contextlib.suppress(Exception):
                    await self.conn.close()
            try:
                async with self.lock:
                    await self.flush()
            except Exception as error:  # noqa: BLE001  transcript failure cannot prevent nonce and session cleanup
                sys.stderr.write(f"Could not flush the ended session: {error}\n")
            with contextlib.suppress(Exception):  # the last lines are announced before the process can end
                await self.lines_flush()
            if self.number is not None:
                with contextlib.suppress(Exception):
                    await asyncio.to_thread(nonce.close, self.number)
            if self.took or self.recorded:
                await self.release(how)
        finally:
            self.over.set()
            if release:
                self.ended.set()

    async def release(self, how: str) -> None:
        """Give back the ticket and record the session ended, never silently failing: when this runner's code cannot
        reach the store, as when a newer Metaform upgraded it under the runner, STORE-029, a new process does it with
        the code on disk; when that fails too, the runner's log says what is left and how to put the ticket back."""
        owner = self.by if self.recorded else self.ctx.nouns.get('reservation') or self.by
        given: dict[str, Any] = {'work_id': self.work_id, 'by': owner, 'took': self.took,
                                 'session_id': self.session_id if self.recorded else None, 'how': how}
        try:
            await asyncio.to_thread(release, self.store, **given)
        except Exception as error:  # noqa: BLE001  the code on disk may reach what this code cannot
            command = [sys.executable, '-c', RELEASE, json.dumps({'project': self.store.project_id, **given})]
            try:
                done = await asyncio.to_thread(subprocess.run, command, capture_output=True, text=True,
                                               encoding='utf-8', stdin=subprocess.DEVNULL, timeout=RELEASE_LIMIT)
                failed = done.stderr.strip() if done.returncode else None
            except (OSError, subprocess.TimeoutExpired) as run_error:
                failed = str(run_error)
            if failed is not None:
                sys.stderr.write(f'Could not end session {self.session_id} on work {self.work_id}: {error}\n'
                                 f'Nor with the code on disk: {failed}\n')
                if self.took:
                    sys.stderr.write(f'Work {self.work_id} stays taken by {self.by}. To put it back: '
                                     f'metaform map work op=move id={self.work_id} column=todo\n')
                return
        with contextlib.suppress(Exception):  # the release stands whether or not an open page hears of it
            await self.changed()
