"""Find modules, read their declarations without running them, and load the enabled ones, BASE-037.

Modules come from three places, in this order:
  system  the modules that ship with Metaform, `metaform/modules/`
  user    folders under `<home>/modules`
  entry   installed packages that declare a `metaform.modules` entry point

Everything a module registers, its verbs, settings, subscriptions and tasks,
is owned by the module, and unload, reload and shutdown withdraw all of it
while stored data stays, BASE-018.
"""
from __future__ import annotations

import asyncio
import atexit
import importlib
import inspect
import importlib.resources
import importlib.util
import re
import sys
from collections.abc import Coroutine
from dataclasses import dataclass, field
from importlib import metadata
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any

from . import home, module_metadata, settings
from .module import Context, Module, call

RESERVED = {'help', 'add', 'list', 'set', 'unset', 'config', 'enable', 'disable', 'activate', 'import', 'export',
            'query', 'build', 'install', 'uninstall', 'feedback', 'read', 'extract', 'prompts', 'prompt', 'clear', 'chassis'}
SYSTEM: Traversable = importlib.resources.files('metaform') / 'modules'
TOOL_NAME = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')


@dataclass
class Found:
    """One module candidate: where it was found, whether it is on, and why it did not load when it did not."""
    id: str
    place: str
    path: Traversable
    import_name: str = ''
    enabled: bool = True
    module: Module | None = None
    problem: str = ''
    declared: module_metadata.Declared | None = None
    tasks: set[asyncio.Task[Any]] = field(default_factory=set[asyncio.Task[Any]])


_cache: list[Found] | None = None
_exit_registered = False


def _candidates() -> list[Found]:
    found: list[Found] = []
    for place, root in (('system', SYSTEM), ('user', home.home() / 'modules')):
        if root.is_dir():
            for folder in sorted(root.iterdir(), key=lambda item: item.name):
                if folder.is_dir() and (folder / '__init__.py').is_file():
                    found.append(Found(folder.name, place, folder, f'metaform_module_{place}_{folder.name}'))
    for entry in sorted(metadata.entry_points(group='metaform.modules'), key=lambda item: item.name):
        package = entry.value.split(':')[0]
        if package == f'metaform.modules.{entry.name}':
            continue  # A built wheel names its own system modules as entry points too; they are found above.
        spec = importlib.util.find_spec(package)
        if spec is None or spec.origin is None:
            found.append(Found(entry.name, 'entry', Path('.'), package, problem=f'Package {package} is not importable.'))
            continue
        found.append(Found(entry.name, 'entry', Path(spec.origin).parent, package))
    return found


def _import(item: Found) -> Module:
    if item.place == 'entry':
        imported = importlib.import_module(item.import_name)
    elif not isinstance(item.path, Path):
        item.import_name = f'metaform.modules.{item.id}'  # A system module inside a directly run wheel.
        imported = importlib.import_module(item.import_name)
    else:
        spec = importlib.util.spec_from_file_location(item.import_name, item.path / '__init__.py',
                                                      submodule_search_locations=[str(item.path)])
        if spec is None or spec.loader is None:
            raise ImportError(f'Cannot load {item.path}.')
        imported = importlib.util.module_from_spec(spec)
        sys.modules[item.import_name] = imported
        spec.loader.exec_module(imported)
    declared = getattr(imported, 'MODULE', None)
    if not isinstance(declared, Module):
        raise ValueError('MODULE must be a metaform.module.Module.')
    if declared.id != item.id:
        raise ValueError(f'MODULE.id is {declared.id!r}; it must match its name {item.id!r}.')
    if not declared.purpose.strip():
        raise ValueError('The module has no purpose, the concise instructions for agents.')
    names = [verb.name for verb in declared.verbs]
    if len(names) != len(set(names)):
        raise ValueError('Two verbs share one name.')
    if declared.default is not None and declared.default not in names:
        raise ValueError(f'default names {declared.default!r}, which is not one of its verbs.')
    for name in names:
        tool = f'{declared.id}_{name}'
        if not TOOL_NAME.fullmatch(tool) or '__' in tool:
            raise ValueError(f'The tool name {tool!r} must be 1 to 64 letters, digits, _ and -, with no double _.')
    return declared


def _withdraw_settings(owner: str) -> None:
    for key in [key for key, setting in settings.SCHEMA.items() if setting.owner == owner]:
        del settings.SCHEMA[key]


def _forget(import_name: str) -> None:
    """Drop a module's package and every submodule from `sys.modules`, so the next load runs them again."""
    for name in [name for name in sys.modules if name == import_name or name.startswith(import_name + '.')]:
        del sys.modules[name]


REQUIREMENT = re.compile(r'^\s*([A-Za-z0-9][A-Za-z0-9._-]*)')


def missing_dependencies(requirements: tuple[str, ...]) -> list[str]:
    """The declared requirements whose distribution is not installed, read without importing anything, BASE-015."""
    missing: list[str] = []
    for requirement in requirements:
        match = REQUIREMENT.match(requirement)
        if match is None:
            missing.append(requirement)
            continue
        try:
            metadata.distribution(match.group(1))
        except metadata.PackageNotFoundError:
            missing.append(requirement)
    return missing


def discover() -> list[Found]:
    """Every module Metaform can see, loaded when enabled and compatible, with the reason when it is not."""
    global _cache
    if _cache is not None:
        return _cache
    found = _candidates()
    seen: dict[str, Found] = {}
    for item in found:
        if item.problem:
            continue
        if item.id in RESERVED:
            item.problem = f'The name {item.id!r} belongs to a chassis command.'
            continue
        if item.id in seen:
            item.problem = f'The {seen[item.id].place} place already holds a module with the id {item.id!r}.'
            continue
        seen[item.id] = item
        try:
            item.declared = module_metadata.read(item.path)
        except (ValueError, OSError, SyntaxError) as error:
            item.problem = str(error)
            continue
        state = home.module_state(item.id)
        item.enabled = state if state is not None else not item.declared.ships_disabled
        if not item.declared.compatible:
            item.problem = item.declared.reason or 'incompatible'
            continue
        if not item.enabled:
            continue
        needed = missing_dependencies(item.declared.dependencies)
        if needed:
            item.problem = f'Needs {", ".join(needed)}, which {"is" if len(needed) == 1 else "are"} not installed.'
            continue
        try:
            with settings.owned_by(item.id):
                item.module = _import(item)
        except Exception as error:  # noqa: BLE001  a broken module is reported and withdrawn; the chassis goes on
            _withdraw_settings(item.id)
            _forget(item.import_name)
            item.problem = f'{type(error).__name__}: {error}'
    _cache = found
    _register_exit()
    for item in found:
        if item.module is not None and item.module.start is not None:
            try:
                call(item.module.start, Context(module=item.id, folder=Path.cwd()))
            except Exception as error:  # A start that raises unloads its module, BASE-018.
                _unload(item)
                item.problem = f'{type(error).__name__}: {error}'
    return found


def enabled() -> list[Module]:
    return [item.module for item in discover() if item.module is not None]


def get(identifier: str) -> Found | None:
    """The module holding this id: the first candidate with it, which is the one that loads."""
    return next((item for item in discover() if item.id == identifier), None)


def tasks_of(owner: str) -> set[asyncio.Task[Any]]:
    """The tasks a module has spawned and that have not finished."""
    item = next((found for found in discover() if found.id == owner), None)
    return set() if item is None else {task for task in item.tasks if not task.done()}


def spawn(owner: str, coroutine: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
    item = next((found for found in discover() if found.id == owner and found.module is not None), None)
    task = asyncio.get_running_loop().create_task(coroutine)
    if item is not None:
        item.tasks.add(task)
        task.add_done_callback(item.tasks.discard)
    return task


def finish_tasks(tasks: set[asyncio.Task[Any]]) -> None:
    """Cancel tasks and wait for each to finish on its own loop, when that loop can still run it, BASE-018.

    A task whose loop is closed has already ended. A task whose loop is running in this thread cannot be waited
    for from synchronous code; `unload_async` is the path for that case.
    """
    pending = [task for task in tasks if not task.done()]
    for task in pending:
        task.cancel()
    by_loop: dict[asyncio.AbstractEventLoop, list[asyncio.Task[Any]]] = {}
    for task in pending:
        by_loop.setdefault(task.get_loop(), []).append(task)
    for loop, group in by_loop.items():
        if loop.is_closed() or loop.is_running():
            continue
        loop.run_until_complete(asyncio.gather(*group, return_exceptions=True))


def _withdraw(item: Found, module: Module) -> None:
    """Call stop, then withdraw settings and code whatever stop did; a failing stop becomes the module's problem."""
    try:
        if module.stop is not None:
            call(module.stop, Context(module=item.id, folder=Path.cwd()))
    except Exception as error:  # noqa: BLE001  a failing stop is reported, and withdrawal still completes
        item.problem = f'stop failed: {type(error).__name__}: {error}'
    finally:
        _withdraw_settings(item.id)
        _forget(item.import_name)


def _unload(item: Found) -> None:
    """Withdraw everything a module registered: cancel its tasks and wait for them, then stop; stored data stays."""
    module, item.module = item.module, None
    finish_tasks(item.tasks)
    if module is not None:
        _withdraw(item, module)


async def unload_async(identifier: str) -> None:
    """Unload one module from inside a running loop: cancel its tasks, wait for them, then call stop."""
    item = next((found for found in discover() if found.id == identifier and found.module is not None), None)
    if item is None or item.module is None:
        return
    module, item.module = item.module, None
    tasks = [task for task in item.tasks if not task.done()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    if module.stop is not None and inspect.iscoroutinefunction(module.stop):
        try:
            await module.stop(Context(module=item.id, folder=Path.cwd()))
        except Exception as error:  # noqa: BLE001  a failing stop is reported, and withdrawal still completes
            item.problem = f'stop failed: {type(error).__name__}: {error}'
        finally:
            _withdraw_settings(item.id)
            _forget(item.import_name)
        return
    _withdraw(item, module)


def unload(identifier: str) -> None:
    for item in discover():
        if item.id == identifier and item.module is not None:
            _unload(item)


def set_enabled(identifier: str, on: bool) -> None:
    home.set_module_state(identifier, on)
    reset()


def reset() -> None:
    """Unload every module and forget what was found, so the next discover reads the places again."""
    global _cache
    if _cache is not None:
        for item in _cache:
            if item.module is not None:
                _unload(item)
    _cache = None


def _register_exit() -> None:
    global _exit_registered
    if not _exit_registered:
        atexit.register(reset)
        _exit_registered = True
