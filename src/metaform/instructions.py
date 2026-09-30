"""The instructions agents read, composed live, MCP-031.

The chassis's instructions prompt, with each surfaced module's instructions
prompt listed in module id order where it marks. With no project for the
folder, the registered projects and the way to register one follow; with debug
on, the trouble report and debug prompts end it. Every word
is from the prompt files, never from here. `metaform help agents` and the MCP
server's instructions are this same text.
"""
from __future__ import annotations

from pathlib import Path

from . import context, loader, prompt_files, settings
from .module import Module, Status, call


def on_surface(group: str, folder: Path) -> bool:
    """Whether a command group is on this folder's surface. Empty means every group, CLI-022."""
    groups = settings.value('modules', folder)
    return not groups or group in groups


def surfaced(folder: Path) -> list[Module]:
    return [module for module in sorted(loader.enabled(), key=lambda item: item.id) if on_surface(module.id, folder)]


def _listed(module: Module, folder: Path, project: str | None) -> str | None:
    """A module's line under "modules available.": its instructions prompt, then the instruction its status hook
    gives for the state the folder is in, VIEW-015."""
    own = prompt_files.module(module.id, 'instructions')
    if module.status is None:
        return own
    try:
        got = call(module.status, context.build(module.id, folder, project=project, resolve=False))
    except Exception:  # noqa: BLE001  a failing hook adds nothing to the instructions
        return own
    added = got.instruction if isinstance(got, Status) else None
    return ' '.join(part for part in (own, added) if part) or None


def compose(folder: Path, project: str | None = None) -> str:
    chosen = project if project is not None else context.project_for(folder)
    listed = [line for line in (_listed(module, folder, chosen) for module in surfaced(folder)) if line]
    parts = [prompt_files.chassis('instructions', modules='\n'.join(listed))]
    if chosen is None:
        from . import home
        registered = [record.project_id for record in home.projects()]
        if registered:
            parts.append(prompt_files.chassis('registered', projects=', '.join(registered)))
        parts.append(prompt_files.chassis('no_project'))
    if settings.value('debug', folder):
        parts.extend((prompt_files.chassis('stop'), prompt_files.chassis('debug')))
    return '\n\n'.join(parts) + '\n'
