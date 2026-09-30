"""The instructions agents read, composed live, MCP-031.

The chassis's instructions prompt, with each surfaced module's instructions
prompt listed in module id order where it marks. With no project for the
folder, the registered projects and the way to register one follow. Every word
is from the prompt files, never from here. `metaform help agents` and the MCP
server's instructions are this same text.
"""
from __future__ import annotations

from pathlib import Path

from . import context, loader, prompt_files, settings
from .module import Module


def on_surface(group: str, folder: Path) -> bool:
    """Whether a command group is on this folder's surface. Empty means every group, CLI-022."""
    groups = settings.value('modules', folder)
    return not groups or group in groups


def surfaced(folder: Path) -> list[Module]:
    return [module for module in sorted(loader.enabled(), key=lambda item: item.id) if on_surface(module.id, folder)]


def compose(folder: Path, project: str | None = None) -> str:
    chosen = project if project is not None else context.project_for(folder)
    listed = [line for line in (prompt_files.module(module.id, 'instructions') for module in surfaced(folder)) if line]
    parts = [prompt_files.chassis('instructions', modules='\n'.join(listed))]
    if chosen is None:
        from . import home
        registered = [record.project_id for record in home.projects()]
        if registered:
            parts.append(prompt_files.chassis('registered', projects=', '.join(registered)))
        parts.append(prompt_files.chassis('no_project'))
    return '\n\n'.join(parts) + '\n'
