"""Which intake an agent records now, BASE-039: the process recording a project's intake holds a lock in the project's
folder in the home for as long as it lives, so an intake is being recorded only while that agent is there, and an
unfinished intake whose agent has gone is left unfinished, never shown as recorded forever.

Only a process that serves one agent's conversation holds it: the MCP server a host starts over stdio, or a
dispatched agent's, which ends with that agent. A command line ends with its command, and a server over HTTP serves
any number of agents, so neither says an agent is there. The system lets go of the lock when the process ends, a
crash too; a process that ends normally then announces `map.changed` for the base naming only `intake.recorder`, so
open pages read at once what is building, and see that the intake is no longer being recorded, VIEW-018. Taking the
hold, or moving it to another layer, names `intake.recorder` in the command's own change too, so a page reads what is
building only when a change says an intake's recording began or ended, never on every write to the map.

An intake agent Metaform starts is held the same way, for the life of its runner, whose process lives exactly as long
as the agent does: the runner takes `intake.agent` before its agent starts, and the system lets go of it when the
runner ends, a crash too. Its launcher writes what it launched into `intake.agent.json` first, under the intake lock,
so the moments between the launch and the runner taking the lock are known too. This is the one record of an intake
under way that every surface reads, and the one a second start is refused by, whatever surface asks.
"""
from __future__ import annotations

import atexit
import json
import os
import threading
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Any, cast

from .. import changes, home, shown, sqlite

LOCK = 'intake.recorder'  # held while the agent's process lives
HELD = 'intake.recorder.json'  # what it holds: {"base": <base id>, "layer": <layer id>}
ENDED = 'intake.recorder'  # the table a `map.changed` names when an agent begins recording an intake, or has gone

AGENT = 'intake.agent'  # held by an intake agent's runner while it lives
LAUNCH = 'intake.agent.json'  # what was launched: {"work", "agent", "pid", "since", "map"}

# this process's hold on each project: the lock, and the base and layer it records into
_HOLDS: dict[str, tuple[ExitStack, str, str]] = {}
_GUARD = threading.Lock()
_AGENTS: dict[str, tuple[ExitStack, str]] = {}  # this runner's hold on each project's intake agent, and its work id


def _folder(project_id: str) -> Path | None:
    folder = home.project_folder(project_id)
    if folder is not None:
        home.mkdir_private(folder)
    return folder


def hold(project_id: str, base_id: str, layer_id: str) -> None:
    """Say that this process records the layer now, when it serves one agent. Another process that holds the lock
    keeps it: two agents recording one intake is the intake's own concern, and the lock still says one is there."""
    if not shown.is_serving():
        return
    with _GUARD:
        held = _HOLDS.get(project_id)
        if held is not None and held[1:] == (base_id, layer_id):
            return
        folder = _folder(project_id)
        if folder is None:
            return
        if held is None:
            stack = ExitStack()
            try:
                stack.enter_context(sqlite.file_lock(folder / LOCK, wait=False))
            except sqlite.Held:  # another agent's process holds it, or a reader is looking this instant
                stack.close()
                return
            if not _HOLDS:
                atexit.register(_ended)
        else:
            stack = held[0]
        home.write_private(folder / HELD, json.dumps({'base': base_id, 'layer': layer_id}))
        _HOLDS[project_id] = (stack, base_id, layer_id)
    changes.note(project_id, base_id, {ENDED}, about={'kinds': {'intake'}})  # announced with the command's writes


def held(project_id: str) -> str | None:
    """The id of the layer an agent records into now for the project, or None when no agent's process holds it."""
    with _GUARD:
        own = _HOLDS.get(project_id)
    if own is not None:
        return own[2]
    folder = home.project_folder(project_id)
    if folder is None or not (folder / LOCK).exists():
        return None
    try:
        with sqlite.file_lock(folder / LOCK, wait=False):
            return None
    except sqlite.Held:
        pass
    try:
        found: Any = json.loads((folder / HELD).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    layer = cast(dict[str, Any], found).get('layer') if isinstance(found, dict) else None
    return layer if isinstance(layer, str) else None


def let_go(project_id: str, layer_id: str) -> None:
    """Let go of the hold on the layer, once it is finished or gone; a hold on another layer stays."""
    with _GUARD:
        own = _HOLDS.get(project_id)
        if own is None or own[2] != layer_id:
            return
        del _HOLDS[project_id]
    own[0].close()


def _ended() -> None:
    """At the end of the process: let go of each hold, then say so, so open pages stop showing the intake as being
    recorded at once. Nothing here may stop the process from ending."""
    with _GUARD:
        holds = dict(_HOLDS)
        _HOLDS.clear()
    for project_id, (stack, base_id, _) in holds.items():
        try:
            stack.close()
            project = home.project(project_id)
            if project is None:
                continue
            changes.note(project_id, base_id, {ENDED})
            changes.announce(Path(project.path), 'mcp')
        except Exception:  # noqa: BLE001, S112  the process is ending; a page reads it on its next change
            continue


def _launch(folder: Path) -> dict[str, Any] | None:
    try:
        found: Any = json.loads((folder / LAUNCH).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if not isinstance(found, dict):
        return None
    record = cast(dict[str, Any], found)
    return record if record.get('work') else None


def note_launch(project_id: str, record: dict[str, Any]) -> None:
    """Keep what an intake launch started: its work id, agent, runner pid, since when, and the map the person chose it
    makes, written by its launcher under the intake lock before its runner takes `intake.agent`."""
    folder = _folder(project_id)
    if folder is not None:
        home.write_private(folder / LAUNCH, json.dumps(record))


def launch_noted(project_id: str) -> dict[str, Any] | None:
    """The intake launch last noted for the project, whether or not its runner still lives: the caller checks."""
    folder = home.project_folder(project_id)
    return _launch(folder) if folder is not None else None


def forget_launch(project_id: str, work_id: str) -> None:
    """Drop the noted launch when it is this work's: it was stopped before its runner took the lock."""
    folder = home.project_folder(project_id)
    if folder is not None and (_launch(folder) or {}).get('work') == work_id:
        (folder / LAUNCH).unlink(missing_ok=True)


def hold_agent(project_id: str, work_id: str) -> dict[str, Any] | None:
    """Hold `intake.agent` for this process, an intake agent's runner, for as long as it lives: None once held, or
    the launch record of the other live runner that holds it, so this one does not start a second intake agent."""
    folder = _folder(project_id)
    if folder is None:
        return None
    with _GUARD:
        own = _AGENTS.get(project_id)
        if own is not None:
            return None if own[1] == work_id else {'work': own[1]}
        stack = ExitStack()
        for attempt in range(3):  # a reader of `agent_held` holds it for an instant: tried again after it
            try:
                stack.enter_context(sqlite.file_lock(folder / AGENT, wait=False))
                break
            except sqlite.Held:
                if attempt == 2:
                    stack.close()
                    return _launch(folder) or {'work': None}
                time.sleep(0.1)
        _AGENTS[project_id] = (stack, work_id)
        noted = _launch(folder)
        record: dict[str, Any] = {**(noted if noted is not None and noted.get('work') == work_id else
                                     {'work': work_id, 'since': home.now()}), 'pid': os.getpid()}
        home.write_private(folder / LAUNCH, json.dumps(record))
    return None


def agent_held(project_id: str) -> dict[str, Any] | None:
    """What a live intake agent's runner holds `intake.agent` for: its launch record, or {"work": None} when none is
    kept; None when no runner holds it."""
    folder = home.project_folder(project_id)
    if folder is None:
        return None
    with _GUARD:
        own = _AGENTS.get(project_id)
    if own is not None:
        return _launch(folder) or {'work': own[1]}
    if not (folder / AGENT).exists():
        return None
    try:
        with sqlite.file_lock(folder / AGENT, wait=False):
            return None
    except sqlite.Held:
        return _launch(folder) or {'work': None}
