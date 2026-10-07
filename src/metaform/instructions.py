"""The instructions agents read, composed live, MCP-031 and MCP-029.

The chassis's instructions prompt, with each surfaced module listed in module id
order where it marks. With connect_instructions=compact, the default, each module
is listed in one line, the chassis's `active` prompt and the instruction its
status hook gives for the folder's state, and the `more` prompt says where each
module's full instructions are; hosts keep only so much, and Claude Code drops
everything past 2,048 characters. With full, each module's whole instructions
prompt is listed. With no project for the folder, the registered projects and
the way to register one follow; with debug on, the trouble report and debug
prompts end it. Every word is from the prompt files, never from here.
`metaform help agents` and the MCP server's instructions are this same text.
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


def _added(module: Module, folder: Path, project: str | None, *, full: bool) -> str | None:
    """The instruction a module's status hook gives for the state the folder is in, VIEW-015; in the compact
    connect-time text only when the hook puts it there, MCP-037."""
    if module.status is None:
        return None
    try:
        got = call(module.status, context.build(module.id, folder, project=project, resolve=False))
    except Exception:  # noqa: BLE001  a failing hook adds nothing to the instructions
        return None
    if not isinstance(got, Status) or (not full and not got.at_connect):
        return None
    return got.instruction


def _listed(module: Module, folder: Path, project: str | None, *, full: bool = True) -> str | None:
    """A module's line under "modules available.": its instructions prompt, or with full off the `active` line,
    then the instruction its status hook gives."""
    own = prompt_files.module(module.id, 'instructions') if full else prompt_files.chassis('active', module=module.id)
    return ' '.join(part for part in (own, _added(module, folder, project, full=full)) if part) or None


def module_text(folder: Path, identifier: str, project: str | None = None) -> str | None:
    """One surfaced module's full instructions, as the full form lists them, or None when it is not on the surface."""
    found = next((module for module in surfaced(folder) if module.id == identifier), None)
    if found is None:
        return None
    chosen = project if project is not None else context.project_for(folder)
    return _listed(found, folder, chosen)


def compose(folder: Path, project: str | None = None) -> str:
    chosen = project if project is not None else context.project_for(folder)
    full = settings.value('connect_instructions', folder) == 'full'
    listed = [line for line in (_listed(module, folder, chosen, full=full) for module in surfaced(folder)) if line]
    parts = [prompt_files.chassis('instructions', modules='\n'.join(listed))]
    if not full:
        parts.append(prompt_files.chassis('more'))
    if chosen is None:
        from . import home
        registered = [record.project_id for record in home.projects()]
        if registered:
            parts.append(prompt_files.chassis('registered', projects=', '.join(registered)))
        parts.append(prompt_files.chassis('no_project'))
    if settings.value('debug', folder):
        parts.extend((prompt_files.chassis('stop'), prompt_files.chassis('debug')))
    return '\n\n'.join(parts) + '\n'
