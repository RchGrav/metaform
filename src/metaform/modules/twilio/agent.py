"""Who answers on the phone: the person's system agent, reached through dispatch's public verbs.

`SystemAgent.reply(text)` makes sure the system agent runs (dispatch system starts it, or resumes the last
conversation, or reuses the running one), carries the person's words to it as their own message (dispatch message),
and yields the agent's answer as it grows, read from the session's thread (dispatch sessions, with `since` the last
line before the message, so each poll reads only the lines begun after it), until its turn ends.
Nothing here stops the agent: a call that ends leaves it running, as the chat dock does.

`ScriptedAgent` answers from a script with no agent at all, for the simulated call of `twilio test`.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any, Protocol, cast

from metaform.module import Stop, context, surface

POLL = 0.15          # seconds between reads of the thread while the agent answers
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


class SystemAgent:
    """The person's system agent, through dispatch system, message and sessions."""

    def __init__(self, run: Runner, *, poll: float = POLL, start_limit: float = START_LIMIT,
                 turn_limit: float = TURN_LIMIT) -> None:
        self.run = run
        self.poll, self.start_limit, self.turn_limit = poll, start_limit, turn_limit
        self.work_id: str | None = None
        self.started: dict[str, Any] = {}  # what dispatch system last answered: the runner's pid when it started one
        self.lock: asyncio.Lock | None = None

    async def _call(self, name: str, **nouns: Any) -> Any:
        return await asyncio.to_thread(self.run, name, nouns)

    async def _running(self) -> tuple[str, str]:
        """The held ticket of the system agent and its running session, started when none runs; one at a time, so a
        call's early start and its first answer never start two agents."""
        if self.lock is None:
            self.lock = asyncio.Lock()
        async with self.lock:
            return await self._start()

    async def _start(self) -> tuple[str, str]:
        started = cast(dict[str, Any], await self._call('system'))
        self.started = started
        work_id = str(started['work_id'])
        self.work_id = work_id
        deadline = time.monotonic() + self.start_limit
        while True:
            rows = _sessions(await self._call('sessions', id=work_id, thread=False))
            live = next((row for row in reversed(rows) if row.get('state') == 'running' and row.get('session_id')),
                        None)
            if live is not None:
                return work_id, str(live['session_id'])
            if time.monotonic() > deadline:
                raise Stop('Your system agent did not start in time.', 'metaform dispatch system')
            await asyncio.sleep(self.poll * 2)

    async def prepare(self) -> None:
        await self._running()

    async def reply(self, text: str) -> AsyncIterator[str]:
        work_id, session_id = await self._running()
        before = max((int(line.get('seq') or 0) for line in _lines(await self._call('sessions', id=work_id))
                      if line.get('session_id') == session_id), default=0)
        await self._call('message', id=work_id, session=session_id, text=[text])
        deadline = time.monotonic() + self.turn_limit
        said, worked, settled = '', False, 0
        while time.monotonic() < deadline:
            read = await self._call('sessions', id=work_id, since=before)  # only the lines begun since it was asked
            lines = [line for line in _lines(read) if line.get('session_id') == session_id
                     and int(line.get('seq') or 0) > before]
            asked = next((int(line['seq']) for line in lines if line.get('kind') == 'person'
                          and str(line.get('text') or '').strip() == text.strip()), None)
            if asked is not None:
                answer = ' '.join(str(line.get('text') or '').strip() for line in sorted(lines, key=lambda one: one['seq'])
                                  if line.get('kind') == 'agent_message_chunk' and int(line['seq']) > asked)
                if answer and answer != said:
                    said, settled = answer, 0
                    yield said
                none: dict[str, Any] = {}
                row = next((one for one in _sessions(read) if one.get('session_id') == session_id), none)
                activity = row.get('activity')
                worked = worked or activity == 'working'
                if row.get('state') != 'running':
                    return  # the agent ended; what it said is all there is
                if activity == 'idle' and (worked or said):
                    settled += 1
                    # idle twice running once it has answered, so a turn about to start is not taken for one ended;
                    # longer while it has said nothing, as a queued message waits for the turn before it to end
                    if settled >= (2 if said else 8):
                        return
                elif activity != 'idle':
                    settled = 0
                if activity == 'waiting':  # it asks the person something: the page shows the question
                    return
            await asyncio.sleep(self.poll)


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
