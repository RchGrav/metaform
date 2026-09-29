"""The instructions agents read, composed live, MCP-029 and MCP-009.

A few messages, each an imperative that says what to do and how. The chassis's
own come first. Then each surfaced module gives its message for the state the
project is in, through its status hook, and gives none when that state does not
hold or a setting turns it off. With no project for the folder, the text ends
with the way to register one. `metaform help agents` and the MCP server's
instructions are this same text.
"""
from __future__ import annotations

from pathlib import Path

from . import context, loader, settings
from .module import Module, Status, call

BASE = ("Metaform keeps this project's functional map: what each part is for, who receives what it does, and how. "
        'Read the part you are about to change before you change it, so you work from its purpose. Each tool is a '
        'module of Metaform. Call a tool with no command to see its commands and what each takes; then call it with '
        "command, and the command's arguments in arguments. On the command line the same command is metaform "
        '<module> <command>. An error ends with the one next step to take.')
STOP = ('If you cannot continue, stop and submit a trouble report: call the metaform tool with command feedback, '
        'attaching what you have in its shape field. Do not retry.')
DEBUG = ('Submit feedback on the Metaform process with the same command: bad semantics, a command that did not match '
         'what it said it takes, where you got stuck.')
NO_PROJECT = 'This folder is not in a registered project. To register one: metaform add project <id> <path>'


def on_surface(group: str, folder: Path) -> bool:
    """Whether a command group is on this folder's surface. Empty means every group, CLI-022."""
    groups = settings.value('modules', folder)
    return not groups or group in groups


def surfaced(folder: Path) -> list[Module]:
    return [module for module in sorted(loader.enabled(), key=lambda item: item.id) if on_surface(module.id, folder)]


def notices(folder: Path, project: str | None) -> list[str]:
    found: list[str] = []
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
    parts = [BASE + '\n\n' + STOP]
    if settings.value('debug', folder):
        parts.append(DEBUG)
    if chosen is None:
        from . import home
        registered = [record.project_id for record in home.projects()]
        if registered:
            parts.append('Registered projects: ' + ', '.join(registered) + '.')
        parts.append(NO_PROJECT)
    else:
        parts.extend(notices(folder, chosen))
    return '\n\n'.join(parts) + '\n'
