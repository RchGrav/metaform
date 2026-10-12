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
`metaform help agents` and the MCP server's instructions are this same text, but
for its opening line: the MCP server's names the server, and every other surface's,
the command line and a project wheel's run, names only Metaform, since no server
is known to be connected there.
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
    """A module's line under "modules available.": its instructions prompt, or with full off its `connect` line, when
    to need it and where to go then, MCP-029; a module with no `connect` line gets the chassis's `active` line, and
    an empty one lists nothing of its own. Then the instruction its status hook gives."""
    if full:
        own = prompt_files.module(module.id, 'instructions')
    else:
        own = prompt_files.module(module.id, 'connect')
        if own is None:
            own = prompt_files.chassis('active', module=module.id)
    return ' '.join(part for part in (own, _added(module, folder, project, full=full)) if part) or None


def _mapped(folder: Path, project: str | None) -> bool:
    """Whether the project has a finished intake, so the order of work has a map to orient on and record at; before
    one the steps would speak to a state that does not hold, MCP-029."""
    try:
        store = context.build('map', folder, project=project, resolve=False).store
        return store is not None and store.has_intake()
    except Exception:  # noqa: BLE001  a project that cannot be read has no map to orient on
        return False


def module_text(folder: Path, identifier: str, project: str | None = None) -> str | None:
    """One surfaced module's full instructions, as the full form lists them, or None when it is not on the surface."""
    found = next((module for module in surfaced(folder) if module.id == identifier), None)
    if found is None:
        return None
    chosen = project if project is not None else context.project_for(folder)
    return _listed(found, folder, chosen)


def startup(folder: Path, project: str | None = None) -> str:
    """What the MCP server sends when an agent connects, MCP-029: an order, not a notice. The mcp module's instructions
    prompt as written, which says Metaform must be used, then one line per module on the folder's surface, in module
    id order, from that module's `connect` prompt, saying what an agent uses it for; a module whose `connect` is empty
    or absent adds nothing. Then mcp's `instructions_end`, which says to read metaform://metaform before beginning
    work and then metaform://<project>, the project's own terms, when the folder is a registered one; mcp's
    `instructions_tools`, one sentence pointing at metaform://tools; and last what the folder's state calls for, each
    line from the module that owns that state, such as intake's first-run notice while the project has no intake."""
    chosen = project if project is not None else context.project_for(folder)
    uses = [line for line in (prompt_files.module(module.id, 'connect') for module in surfaced(folder)) if line]
    order = '\n'.join(part for part in (prompt_files.module('mcp', 'instructions'), *uses) if part)
    states = [line for line in (_added(module, folder, chosen, full=False) for module in surfaced(folder)) if line]
    if chosen is None and not states:
        states.append(prompt_files.chassis('no_project'))
    own = (prompt_files.module('mcp', 'instructions_terms', project=chosen) or ''
           if chosen is not None and chosen != 'metaform' else '')
    end = '\n'.join(part for part in (prompt_files.module('mcp', 'instructions_end', terms=own),
                                       prompt_files.module('mcp', 'instructions_tools')) if part)
    parts = [part for part in (order, end, *states) if part]
    return '\n\n'.join(parts) + '\n' if parts else ''


def compose(folder: Path, project: str | None = None, *, surface: str = 'cli') -> str:
    """The instructions for agents working from this folder; `surface` is where they are served, `mcp` for the MCP
    server, so the opening line claims a server only when one serves them."""
    chosen = project if project is not None else context.project_for(folder)
    full = settings.value('connect_instructions', folder) == 'full'
    listed = [line for line in (_listed(module, folder, chosen, full=full) for module in surfaced(folder)) if line]
    opening = prompt_files.chassis('surface_mcp' if surface == 'mcp' else 'surface_cli')
    # The order of work comes first: orient on the map, then read the memories there, each step its module's, MCP-029.
    steps = [] if full or not _mapped(folder, chosen) else [
        step for step in (prompt_files.module(module.id, 'orient') for module in surfaced(folder)) if step]
    opening = '\n'.join((opening, *steps))
    parts = [prompt_files.chassis('instructions', surface=opening, modules='\n'.join(listed))]
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
