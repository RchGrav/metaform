"""The project map: a store on LadybugDB (`store`) and the command engine of the `project` tool (`commands`).

This package is part of the public base. A module reads and writes a project's map through the names below and
through nothing beneath them; none of them opens a database, which the home's single-writer service alone holds.
"""
from __future__ import annotations

from pathlib import Path

from metaform.project.texts import COMMANDS, ROLE_WORDS

__all__ = ['COMMANDS', 'ROLE_WORDS', 'clear', 'drawn', 'holds', 'run', 'stored_name']


def run(command: object, home: Path | None = None, caller: str = '') -> dict[str, object]:
    """Answer one command of the project tool: one JSON command in, one JSON answer out, `commands.run`."""
    from metaform.project import commands
    return commands.run(command, home, caller)


def drawn(project: str, home: Path | None = None) -> dict[str, object] | None:
    """Everything a display draws of a project in one read, or None when the store holds no such project."""
    from metaform.project import commands
    return commands.drawn(project, home)


def clear(project: str, home: Path | None = None) -> bool:
    """Remove a project's map from the store. False when it holds none."""
    from metaform.project import commands
    return commands.clear(project, home)


def holds(project: str, home: Path | None = None) -> bool:
    """Whether the store holds a map of this project, asked of the folder: no database is opened and no read made."""
    from metaform import home as metaform_home
    return ((home if home is not None else metaform_home.home()) / 'maps' / f'{project}.lbug').exists()


def stored_name(project_id: str) -> str:
    """The name a registered project has in the project store: its id, with the underscores a step is written with."""
    return project_id.lower().replace('-', '_')
