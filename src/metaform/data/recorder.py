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
"""
from __future__ import annotations

import atexit
import json
import threading
from contextlib import ExitStack
from pathlib import Path
from typing import Any, cast

from .. import changes, home, shown, sqlite

LOCK = 'intake.recorder'  # held while the agent's process lives
HELD = 'intake.recorder.json'  # what it holds: {"base": <base id>, "layer": <layer id>}
ENDED = 'intake.recorder'  # the table a `map.changed` names when an agent begins recording an intake, or has gone

# this process's hold on each project: the lock, and the base and layer it records into
_HOLDS: dict[str, tuple[ExitStack, str, str]] = {}
_GUARD = threading.Lock()


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
