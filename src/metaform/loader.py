"""Find modules, read their declarations without running them, and load the enabled ones.

Modules come from three places, in this order:
  system  the modules that ship with Metaform
  user    folders under <home>/modules
  entry   installed packages that declare a `metaform.modules` entry point

A module's id is its folder or entry point name. Two modules with one id, a
module named like a chassis command, or a module without SUPPORTED_OS is not
loaded, and `metaform list modules` says why.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path

from . import home, module_metadata, settings
from .module import Module

RESERVED = {'help', 'add', 'list', 'set', 'unset', 'config', 'enable', 'disable', 'mcp', 'chassis'}
SYSTEM = Path(__file__).parent / 'modules'


@dataclass
class Found:
    id: str
    place: str
    path: Path
    enabled: bool = True
    module: Module | None = None
    problem: str = ''
    import_name: str = ''
    extras: dict = field(default_factory=dict)


_cache: list[Found] | None = None


def _candidates() -> list[Found]:
    found = []
    for place, root in (('system', SYSTEM), ('user', home.home() / 'modules')):
        if root.is_dir():
            for folder in sorted(root.iterdir()):
                if (folder / '__init__.py').is_file():
                    found.append(Found(folder.name, place, folder))
    for entry in metadata.entry_points(group='metaform.modules'):
        spec = importlib.util.find_spec(entry.value.split(':')[0])
        if spec is None or spec.origin is None:
            found.append(Found(entry.name, 'entry', Path('.'), problem=f'Package {entry.value} is not importable.'))
            continue
        found.append(Found(entry.name, 'entry', Path(spec.origin).parent, import_name=entry.value.split(':')[0]))
    return found


def _disabled() -> set[str]:
    with home.base() as db:
        db.execute('CREATE TABLE IF NOT EXISTS disabled_modules(id TEXT PRIMARY KEY)')
        return {row[0] for row in db.execute('SELECT id FROM disabled_modules')}


def set_enabled(identifier: str, on: bool) -> None:
    with home.base(write=True) as db:
        db.execute('CREATE TABLE IF NOT EXISTS disabled_modules(id TEXT PRIMARY KEY)')
        if on:
            db.execute('DELETE FROM disabled_modules WHERE id=?', (identifier,))
        else:
            db.execute('INSERT OR IGNORE INTO disabled_modules(id) VALUES (?)', (identifier,))
    reset()


def _import(item: Found) -> Module:
    name = item.import_name or f'metaform_module_{item.place}_{item.id}'
    if item.import_name:
        imported = importlib.import_module(name)
    else:
        spec = importlib.util.spec_from_file_location(name, item.path / '__init__.py',
                                                      submodule_search_locations=[str(item.path)])
        imported = importlib.util.module_from_spec(spec)
        sys.modules[name] = imported
        spec.loader.exec_module(imported)
    declared = getattr(imported, 'MODULE', None)
    if not isinstance(declared, Module):
        raise ValueError('MODULE must be a metaform.module.Module.')
    if declared.id != item.id:
        raise ValueError(f'MODULE.id is {declared.id!r}; it must match its name {item.id!r}.')
    names = [verb.name for verb in declared.verbs]
    if len(names) != len(set(names)):
        raise ValueError('Two verbs share one name.')
    return declared


def discover() -> list[Found]:
    """Every module Metaform can see, loaded when enabled, with the reason when it is not."""
    global _cache
    if _cache is not None:
        return _cache
    disabled = _disabled()
    found = _candidates()
    seen: dict[str, Found] = {}
    for item in found:
        item.enabled = item.id not in disabled
        if item.problem:
            continue
        if item.id in RESERVED:
            item.problem = f'The name {item.id!r} belongs to a chassis command.'
            continue
        if item.id in seen:
            item.problem = f'Another module already has the id {item.id!r} ({seen[item.id].place}).'
            continue
        seen[item.id] = item
        try:
            declared = module_metadata.read(item.path)
        except (ValueError, OSError, SyntaxError) as error:
            item.problem = str(error)
            continue
        if not declared['compatible']:
            item.problem = declared['compatibility_reason']
            continue
        if not item.enabled:
            continue
        before = dict(settings.SCHEMA)
        try:
            with settings.owned_by(item.id):
                item.module = _import(item)
        except Exception as error:  # A broken module is reported and skipped.
            settings.SCHEMA.clear()
            settings.SCHEMA.update(before)
            item.problem = f'{type(error).__name__}: {error}'
    _cache = found
    return found


def enabled() -> list[Module]:
    return [item.module for item in discover() if item.module is not None]


def get(identifier: str) -> Found | None:
    return next((item for item in discover() if item.id == identifier and not item.problem.startswith('Another')), None)


def reset() -> None:
    """Forget what was loaded, so the next discover reads the places again."""
    global _cache
    if _cache is not None:
        for item in _cache:
            if item.module is not None:
                for key in [key for key, setting in settings.SCHEMA.items() if setting.owner == item.id]:
                    del settings.SCHEMA[key]
    _cache = None
