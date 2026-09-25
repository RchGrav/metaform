"""Building the one Context each verb call, event delivery and tool call receives, BASE-028.

The folder's project is the project named for the call, otherwise the folder's
`project` setting, PROJ-003. The store is that project's data access object,
started from the folder's toggled layers, LAYER-019, or None with no project.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import settings
from .data import Store
from .errors import Stop
from .module import Context


def project_for(folder: Path, named: str | None = None) -> str | None:
    if named is not None:
        from . import home
        if home.project(named) is None:
            raise Stop(f'No project {named} is registered.', 'metaform list projects')
        return named
    value = settings.value('project', folder)
    return value if isinstance(value, str) and value else None


def toggled_for(folder: Path) -> list[str]:
    if 'layers' not in settings.SCHEMA:
        return []
    value = settings.value('layers', folder)
    return list(value) if isinstance(value, list) else []


def build(module: str, folder: Path, *, project: str | None = None, nouns: dict[str, Any] | None = None,
          switches: dict[str, Any] | None = None, sink: Callable[[str], None] | None = None,
          surface: str = 'cli', resolve: bool = True) -> Context:
    """A Context for one operation, with the project and store resolved for its folder."""
    chosen = project_for(folder, project) if resolve else project
    toggled = list(switches['layers']) if switches and isinstance(switches.get('layers'), list) else toggled_for(folder)
    store = Store(chosen, toggled=toggled, module=module) if chosen else None
    return Context(module=module, folder=folder, project=chosen, store=store, nouns=dict(nouns or {}),
                   switches=dict(switches or {}), sink=sink, surface=surface)
