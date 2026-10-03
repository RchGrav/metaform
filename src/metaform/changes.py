"""What a command changed in the map, so the chassis can announce it when the command ends, VIEW-018 and QUAL-015.

The store notes each committed write to a metaform's store, and the home each metaform added, removed or made
active. After every command, on the command line or over MCP, the chassis takes the notes and fires `map.changed`
on the module event bus once for each metaform changed, BASE-010, so every subscriber, the web GUI's open pages
among them, is told what changed. Nothing polls for a change and no module has to remember to announce one.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .module import Surface

_NOTED: dict[str, set[str]] = {}
_LOCK = threading.Lock()


def note(project_id: str, metaform_id: str | None = None) -> None:
    """A change to a project's map: one metaform's store, or, with no metaform, the project's metaforms themselves."""
    with _LOCK:
        _NOTED.setdefault(project_id, set()).add(metaform_id or '')


def take() -> dict[str, set[str]]:
    """Everything noted since the last take, once."""
    with _LOCK:
        found = {project: set(metaforms) for project, metaforms in _NOTED.items()}
        _NOTED.clear()
    return found


def announce(folder: Path, surface: Surface) -> list[dict[str, str | None]]:
    """Fire `map.changed` for each metaform the command changed; a metaform id of None means the project's metaforms
    changed, such as one added, removed or made active. A subscriber's failure never reaches the command, BASE-032.
    Returns the payloads fired, so a long-running process can follow its own changes, BASE-053."""
    from . import events
    from .module import Context
    fired: list[dict[str, str | None]] = []
    for project, metaforms in sorted(take().items()):
        source = Context(module='chassis', folder=folder, project=project, surface=surface)
        for metaform in sorted(metaforms):
            payload: dict[str, str | None] = {'project': project, 'metaform_id': metaform or None}
            events.publish('map.changed', dict(payload), source)
            fired.append(payload)
    return fired
