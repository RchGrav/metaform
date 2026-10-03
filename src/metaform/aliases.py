"""Aliases, CLI-039: one name at the top menu that stands for two or more modules, defined for a folder.

An alias defined at a folder holds there and in every folder below it, as a folder setting does, CLI-014; the
nearest folder's definition of a name wins. Entering it gives the commands of the modules it stands for that the
folder's command surface shows, CLI-022. A module or chassis command of the same name comes first.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import home, instructions, loader
from .errors import Stop
from .module import Module

NAME = re.compile(r'^[a-z][a-z0-9_-]{0,63}$')
OWN_TOOL = 'metaform'  # the tool of the chassis's own commands over MCP, CLI-037


def defined(folder: Path) -> dict[str, list[str]]:
    """The aliases of a folder and of every folder above it, the nearest definition of a name winning."""
    found: dict[str, list[str]] = {}
    folder = folder.resolve()
    for candidate in (folder, *folder.parents):
        for name, modules in home.aliases_at(home.path_key(candidate)).items():
            found.setdefault(name, modules)
    return dict(sorted(found.items()))


def shown(folder: Path) -> dict[str, list[Module]]:
    """Each alias with the modules it stands for that are loaded and on the folder's surface; an alias with none of
    them, or whose name a module has taken, is left out."""
    surfaced = {module.id: module for module in instructions.surfaced(folder)}
    found: dict[str, list[Module]] = {}
    for name, modules in defined(folder).items():
        held = [surfaced[module] for module in modules if module in surfaced]
        if held and loader.get(name) is None:
            found[name] = held
    return found


def define(folder: Path, name: str, modules: list[str], taken: set[str]) -> list[str]:
    """Store an alias for the folder and return the modules it stands for, each once, in the order given. `taken` is
    the names of the chassis's commands."""
    modules = list(dict.fromkeys(modules))
    if not name or len(modules) < 2:
        raise Stop('alias needs a name and two or more modules.', 'metaform help alias')
    if not NAME.fullmatch(name):
        raise Stop('An alias is named with a lowercase letter, then letters, digits, - or _.', 'metaform help alias')
    if name in taken or name in loader.RESERVED or name == OWN_TOOL or loader.get(name) is not None:
        raise Stop(f'{name} is already a command.', 'metaform help commands')
    for module in modules:
        if loader.get(module) is None:
            raise Stop(f'No module {module}.', 'metaform list modules')
    home.save_alias(folder.resolve(), name, modules)
    return modules
