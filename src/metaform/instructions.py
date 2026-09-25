"""The instructions agents read, composed live, MCP-007 and MCP-009.

The chassis base text, then each surfaced module's `purpose` under `## <id>`,
in module id order, then each surfaced module's status notice. With no project
for the folder, the text ends with the way to register one. `metaform help
agents` and the MCP server's instructions are this same text.
"""
from __future__ import annotations

from pathlib import Path

from . import context, loader, settings
from .module import Status, call

BASE = ("Metaform keeps this project's functional map: what each part is for, who receives what it does, and how. "
        'Read the map before you change the project, so you work from the purpose of each part. Each tool comes '
        'from a module; the sections below say what each module is for. A tool named <module>_<verb> takes the '
        "verb's nouns and switches as named arguments. A tool error ends with the one next step to take. For any "
        "module's full help, run metaform help <module>.")
NO_PROJECT = 'This folder is not in a registered project. To register one: metaform add project <id> <path>'


def on_surface(group: str, folder: Path) -> bool:
    """Whether a command group is on this folder's surface. Empty means every group, CLI-022."""
    groups = settings.value('modules', folder)
    return not groups or group in groups


def surfaced(folder: Path) -> list:
    return [module for module in sorted(loader.enabled(), key=lambda item: item.id) if on_surface(module.id, folder)]


def notices(folder: Path, project: str | None) -> list[str]:
    found = []
    for module in surfaced(folder):
        if module.status is None:
            continue
        try:
            got = call(module.status, context.build(module.id, folder, project=project, resolve=False))
        except Exception:  # A failing hook contributes nothing to the instructions.
            continue
        if isinstance(got, Status) and got.notice:
            found.append(got.notice)
    return found


def compose(folder: Path, project: str | None = None) -> str:
    chosen = project if project is not None else context.project_for(folder)
    parts = [BASE]
    for module in surfaced(folder):
        parts.append(f'## {module.id}\n{module.purpose}')
    if chosen is None:
        parts.append(NO_PROJECT)
    else:
        parts.extend(notices(folder, chosen))
    return '\n\n'.join(parts) + '\n'
