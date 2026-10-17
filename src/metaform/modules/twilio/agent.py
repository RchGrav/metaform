"""Who answers on the phone: the person's system agent, reached through dispatch's public verbs.

`SystemAgent.reply(text)` makes sure the system agent runs (dispatch system starts it, or resumes the last
conversation, or reuses the running one), carries the person's words to it as their own message (dispatch message),
and yields the agent's answer as it grows, read from the session's thread (dispatch sessions, with `since` the last
line before the message, so each read takes only the lines begun after it), until its turn ends. It reads again only
when the runner announces its lines or its session changed, in `map.changed` from the runner's process, BASE-053:
nothing is read on a timer, QUAL-015. The bridge hands it the changes its own listener hears; alone, it listens itself.
Nothing here stops the agent: a call that ends leaves it running, as the chat dock does.

`ScriptedAgent` answers from a script with no agent at all, for the simulated call of `twilio test`.
"""
from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from pathlib import Path
from typing import Any, Protocol, cast

from metaform import events
from metaform.module import Stop, context, surface

# the dispatch tables whose change is read again: a thread's lines and sessions, kept beside the map before version 16
READ_AGAIN = {'dispatch.lines', 'dispatch.sessions', 'dispatch.session_lines', 'dispatch.agent_sessions'}
START_LIMIT = 90.0   # seconds a system agent may take to start before the call is told it could not
TURN_LIMIT = 180.0   # seconds an answer may take before what has come is all there is


class Agent(Protocol):
    async def prepare(self) -> None:
        """Have the agent ready to answer, started or resumed when it is not running, so the first answer is not
        delayed by its start."""
        ...

    def reply(self, text: str) -> AsyncIterator[str]:
        """The agent's answer to `text`, the whole answer so far each time it grows."""
        ...


Runner = Callable[[str, dict[str, Any]], Any]


class Closing(Protocol):
    def close(self) -> None: ...


def verb_runner(folder: Path, project: str | None) -> Runner:
    """Run a dispatch verb as the person would on the command line, through the module declarations on the folder's
    surface, never by importing dispatch."""
    def run(name: str, nouns: dict[str, Any]) -> Any:
        found = next((module for module in surface(folder) if module.id == 'dispatch'), None)
        if found is None:
            raise Stop('The phone answers with your system agent, which needs the dispatch module.',
                       'metaform enable dispatch')
        verb = next(verb for verb in found.verbs if verb.name == name)
        return verb.run(context('dispatch', folder, project=project, nouns=nouns))
    return run


def _lines(read: Any) -> list[dict[str, Any]]:
    held = cast(dict[str, Any], read) if isinstance(read, dict) else {}
    return [cast(dict[str, Any], line) for line in cast(list[Any], held.get('lines') or []) if isinstance(line, dict)]


def _sessions(read: Any) -> list[dict[str, Any]]:
    held = cast(dict[str, Any], read) if isinstance(read, dict) else {}
    return [cast(dict[str, Any], row) for row in cast(list[Any], held.get('sessions') or []) if isinstance(row, dict)]


def concerns(payload: dict[str, Any], work_id: str | None, session_id: str | None) -> bool:
    """Whether a `map.changed` can change what the thread or the session shows. One that names tickets or sessions
    concerns it only when it names this one's; else one that names dispatch's lines or sessions, names dispatch with no
    table, or names nothing, which may have changed anything."""
    named, sessions = payload.get('work_ids'), payload.get('session_ids')
    if work_id is not None and (isinstance(named, list) or isinstance(sessions, list)):
        return (isinstance(named, list) and work_id in cast(list[Any], named)) or \
            (session_id is not None and isinstance(sessions, list) and session_id in cast(list[Any], sessions))
    tables = payload.get('tables')
    if tables is None:
        return True
    if tables != 'dispatch':
        return False
    named = payload.get('dispatch_tables')
    return not isinstance(named, list) or bool(READ_AGAIN & set(cast(list[Any], named)))


class SystemAgent:
    """The person's system agent, through dispatch system, message and sessions. `listening` False when the caller
    hands it each `map.changed` with `heard`, as the bridge does from the listener it holds already."""

    def __init__(self, run: Runner, *, project: str | None = None, listening: bool = True,
                 start_limit: float = START_LIMIT, turn_limit: float = TURN_LIMIT) -> None:
        self.run = run
        self.project, self.listening = project, listening
        self.start_limit, self.turn_limit = start_limit, turn_limit
        self.work_id: str | None = None
        self.session_id: str | None = None  # the running session its reads follow
        self.started: dict[str, Any] = {}  # what dispatch system last answered: the runner's pid when it started one
        self.lock: asyncio.Lock | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.waiting: set[asyncio.Event] = set()  # one for each read waiting on a change
        self.listener: Closing | None = None  # its own listener, when it listens itself

    def heard(self, payload: dict[str, Any]) -> None:
        """A `map.changed` from another process, in the listener's thread: every read waiting on a change it concerns
        reads again."""
        loop = self.loop
        if loop is None or not self.waiting or not concerns(payload, self.work_id, self.session_id) \
                or self.project is not None and payload.get('project') not in (None, self.project):
            return
        with contextlib.suppress(RuntimeError):  # the loop has closed: nothing waits on it any more
            loop.call_soon_threadsafe(lambda: [one.set() for one in list(self.waiting)])

    def close(self) -> None:
        if self.listener is not None:
            self.listener.close()
            self.listener = None

    async def _call(self, name: str, **nouns: Any) -> Any:
        return await asyncio.to_thread(self.run, name, nouns)

    @contextlib.asynccontextmanager
    async def _changes(self) -> AsyncGenerator[asyncio.Event]:
        """An event set by each change the runner announces, from before the first read it guards, so a change made
        while a read runs is never missed: clear it before each read, then wait on it."""
        self.loop = asyncio.get_running_loop()
        if self.listening and self.listener is None:
            self.listener = await asyncio.to_thread(events.listen, 'twilio', self.heard)
        changed = asyncio.Event()
        self.waiting.add(changed)
        try:
            yield changed
        finally:
            self.waiting.discard(changed)

    async def _running(self) -> tuple[str, str]:
        """The held ticket of the system agent and its running session, started when none runs; one at a time, so a
        call's early start and its first answer never start two agents."""
        if self.lock is None:
            self.lock = asyncio.Lock()
        async with self.lock:
            return await self._start()

    async def _start(self) -> tuple[str, str]:
        async with self._changes() as changed:
            started = cast(dict[str, Any], await self._call('system'))
            self.started = started
            work_id = str(started['work_id'])
            self.work_id = work_id
            deadline = time.monotonic() + self.start_limit
            while True:
                changed.clear()
                rows = _sessions(await self._call('sessions', id=work_id, thread=False))
                live = next((row for row in reversed(rows) if row.get('state') == 'running' and row.get('session_id')),
                            None)
                if live is not None:
                    self.session_id = str(live['session_id'])
                    return work_id, self.session_id
                if not await _until(changed, deadline):
                    raise Stop('Your system agent did not start in time.', 'metaform dispatch system')

    async def prepare(self) -> None:
        await self._running()

    async def reply(self, text: str) -> AsyncIterator[str]:
        work_id, session_id = await self._running()
        async with self._changes() as changed:
            async for said in self._answer(changed, work_id, session_id, text):
                yield said

    async def _answer(self, changed: asyncio.Event, work_id: str, session_id: str, text: str) -> AsyncIterator[str]:
        """The answer as it grows, read once now and again at each change the runner announces, until the turn the
        message started has ended; the runner counts the message's turn before it answers the message, so the session
        reads idle again only once that turn is over."""
        before = max((int(line.get('seq') or 0) for line in _lines(await self._call('sessions', id=work_id))
                      if line.get('session_id') == session_id), default=0)
        await self._call('message', id=work_id, session=session_id, text=[text])
        deadline = time.monotonic() + self.turn_limit
        said = ''
        while True:
            changed.clear()
            read = await self._call('sessions', id=work_id, since=before)  # only the lines begun since it was asked
            lines = [line for line in _lines(read) if line.get('session_id') == session_id
                     and int(line.get('seq') or 0) > before]
            asked = next((int(line['seq']) for line in lines if line.get('kind') == 'person'
                          and str(line.get('text') or '').strip() == text.strip()), None)
            if asked is not None:
                answer = ' '.join(str(line.get('text') or '').strip() for line in sorted(lines, key=lambda one: one['seq'])
                                  if line.get('kind') == 'agent_message_chunk' and int(line['seq']) > asked)
                if answer and answer != said:
                    said = answer
                    yield said
                none: dict[str, Any] = {}
                row = next((one for one in _sessions(read) if one.get('session_id') == session_id), none)
                if row.get('state') != 'running':
                    return  # the agent ended; what it said is all there is
                if row.get('activity') in ('idle', 'waiting'):  # its turn ended, or it asks the person, as the page shows
                    return
            if not await _until(changed, deadline):
                return  # the turn's time is up: what has come is all there is


async def _until(changed: asyncio.Event, deadline: float) -> bool:
    """Wait for a change, or for the deadline; False once the deadline has passed."""
    left = deadline - time.monotonic()
    if left <= 0:
        return False
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(changed.wait(), left)
    return changed.is_set()


class ScriptedAgent:
    """An agent with no model, for the simulated call: it answers each message with the next line of its script, or
    repeats what it heard, after `delay` seconds."""

    def __init__(self, script: list[str] | None = None, delay: float = 0.0) -> None:
        self.script = list(script or [])
        self.delay = delay
        self.heard: list[str] = []

    async def prepare(self) -> None:
        return None

    async def reply(self, text: str) -> AsyncIterator[str]:
        self.heard.append(text)
        if self.delay:
            await asyncio.sleep(self.delay)
        yield self.script.pop(0) if self.script else f'You said: {text.splitlines()[-1]}'
