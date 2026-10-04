"""Find modules, read their declarations without running them, and load the enabled ones, BASE-037.

Modules come from four places, in this order:
  system   the modules that ship with Metaform, `metaform/modules/`
  user     folders under `<home>/modules`
  entry    installed packages that declare a `metaform.modules` entry point
  project  folders under `.metaform/modules/` in the active selected project's folder, which Metaform only
           reads, D93

Everything a module registers, its verbs, settings, subscriptions and tasks,
is owned by the module, and unload, reload and shutdown withdraw all of it
while stored data stays, BASE-018.
"""
from __future__ import annotations

import asyncio
import atexit
import importlib
import importlib.machinery
import importlib.resources
import importlib.util
import inspect
import re
import shutil
import sys
from collections.abc import Coroutine
from contextlib import ExitStack
from dataclasses import dataclass, field
from importlib import metadata
from importlib.resources.abc import Traversable
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType
from typing import Any

from . import home, module_metadata, settings
from .module import Context, Module, call

RESERVED = {'help', 'add', 'list', 'set', 'unset', 'config', 'enable', 'disable', 'activate', 'import', 'export',
            'query', 'build', 'install', 'uninstall', 'feedback', 'read', 'extract', 'prompts', 'prompt', 'clear', 'restore', 'remove', 'chassis',
            'alias'}
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
_cache_project: str | None = None
_exit_registered = False
_read_only: set[Path] = set()
_data_resources: dict[str, ExitStack] = {}


def _selected_project() -> str | None:
    """The active selected project of the folder this process runs in, PROJ-003."""
    chosen = settings.value('project', Path.cwd())
    return chosen if isinstance(chosen, str) and chosen else None


def project_place(project_id: str | None) -> Path | None:
    """A project's module place, `.metaform/modules/` in its folder, which the person creates, D93."""
    record = home.project(project_id) if project_id else None
    return None if record is None else Path(record.path) / '.metaform' / 'modules'


class _ReadOnlyLoader(importlib.machinery.SourceFileLoader):
    """Loads a project-place module's source and never writes its bytecode, since Metaform writes nothing into a
    project folder, STORE-001."""

    def set_data(self, path: str, data: Any, *, _mode: int = 0o666) -> None:
        return None


def _read_only_finder(entry: str) -> importlib.machinery.FileFinder:
    """The finder for a folder inside a project place, so a module's submodules load read-only too."""
    path = Path(entry)
    if not any(path == root or root in path.parents for root in _read_only):
        raise ImportError(entry)
    return importlib.machinery.FileFinder(
        entry, (importlib.machinery.ExtensionFileLoader, importlib.machinery.EXTENSION_SUFFIXES),
        (_ReadOnlyLoader, importlib.machinery.SOURCE_SUFFIXES),
        (importlib.machinery.SourcelessFileLoader, importlib.machinery.BYTECODE_SUFFIXES))


def _candidates(project_id: str | None) -> list[Found]:
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
    root = project_place(project_id)
    if root is not None and root.is_dir():
        for folder in sorted(root.iterdir(), key=lambda item: item.name):
            if folder.is_dir() and (folder / '__init__.py').is_file():
                found.append(Found(folder.name, 'project', folder, f'metaform_module_project_{folder.name}'))
    return found


def _import(item: Found) -> Module:
    if item.place == 'entry':
        imported = importlib.import_module(item.import_name)
    elif not isinstance(item.path, Path):
        item.import_name = f'metaform.modules.{item.id}'  # A system module inside a directly run wheel.
        imported = importlib.import_module(item.import_name)
    else:
        source = item.path / '__init__.py'
        read_only = None
        if item.place == 'project':
            _read_only.add(item.path)
            if _read_only_finder not in sys.path_hooks:
                sys.path_hooks.insert(0, _read_only_finder)
            for entry in [entry for entry in sys.path_importer_cache if Path(entry) == item.path
                          or item.path in Path(entry).parents]:
                del sys.path_importer_cache[entry]
            read_only = _ReadOnlyLoader(item.import_name, str(source))
        spec = importlib.util.spec_from_file_location(item.import_name, source, loader=read_only,
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
    resources = _data_resources.pop(import_name, None)
    if resources is not None:
        resources.close()
    prefixes = [import_name]
    if import_name.startswith('metaform_module_system_'):
        prefixes.append('metaform.modules.' + import_name.removeprefix('metaform_module_system_'))
    for name in [name for name in sys.modules if any(name == prefix or name.startswith(prefix + '.')
                                                   for prefix in prefixes)]:
        parent, _, attribute = name.rpartition('.')
        package = sys.modules.get(parent)
        if package is not None and getattr(package, attribute, None) is sys.modules[name]:
            delattr(package, attribute)
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
    global _cache, _cache_project
    if _cache is not None:
        return _cache
    _cache_project = _selected_project()
    found = _candidates(_cache_project)
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
    found = next((item for item in discover() if item.id == identifier), None)
    if found is not None and found.module is None:
        follow_enabled()
        found = next((item for item in discover() if item.id == identifier), None)
    return found


def data_source(identifier: str) -> ModuleType | None:
    """Load a compatible module's standalone DAO declaration without enabling its runtime module."""
    item = next((item for item in discover() if item.id == identifier), None)
    if item is None or item.declared is None or not item.declared.compatible or not item.declared.data_source:
        return None
    name = item.import_name + '.data_source'
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    resources = ExitStack()
    created_package = item.import_name not in sys.modules
    try:
        if isinstance(item.path, Path):
            folder = item.path
        else:
            folder = Path(resources.enter_context(TemporaryDirectory(prefix='metaform-data-')))
            _copy_resources(item.path, folder)
        source = folder / item.declared.data_source
        if item.place == 'project':
            _read_only.add(folder)
            if _read_only_finder not in sys.path_hooks:
                sys.path_hooks.insert(0, _read_only_finder)
            for entry in [entry for entry in sys.path_importer_cache if Path(entry) == folder
                          or folder in Path(entry).parents]:
                del sys.path_importer_cache[entry]
        package = sys.modules.get(item.import_name)
        if package is None:
            package = ModuleType(item.import_name)
            package.__path__ = [str(folder)]
            package.__package__ = item.import_name
            package.__spec__ = importlib.util.spec_from_file_location(
                item.import_name, folder / '__init__.py', submodule_search_locations=[str(folder)])
            sys.modules[item.import_name] = package
        spec = importlib.util.spec_from_file_location(name, source,
                                                      loader=_ReadOnlyLoader(name, str(source)))
        if spec is None or spec.loader is None:
            raise ImportError(f'Cannot load {source}.')
        imported = importlib.util.module_from_spec(spec)
        sys.modules[name] = imported
        spec.loader.exec_module(imported)
    except BaseException as error:
        resources.close()
        _forget(item.import_name if created_package else name)
        if isinstance(error, Exception):
            item.problem = f'DATA_SOURCE: {type(error).__name__}: {error}'
            return None
        raise
    package.__dict__['data_source'] = imported
    _data_resources[item.import_name] = resources
    return imported


def _copy_resources(source: Traversable, folder: Path) -> None:
    """Keep wheel helpers available until unload; Python 3.11's as_file accepts files only."""
    for resource in source.iterdir():
        destination = folder / resource.name
        if resource.is_dir():
            destination.mkdir()
            _copy_resources(resource, destination)
        else:
            with importlib.resources.as_file(resource) as path:
                shutil.copyfile(path, destination)


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


def follow_enabled() -> None:
    """Reset the cache when a module found has been enabled or disabled since, by any process, or the folder's
    selected project has changed, so a long-lived process, the web GUI's server or the MCP server, loads what is
    enabled now, with the project place of the project selected now, before it publishes, VIEW-018 and D93."""
    if _cache is None:
        return
    if _selected_project() != _cache_project:
        reset()
        return
    path = home.base_path()
    if not path.is_file() or not path.stat().st_size:
        return
    for item in _cache:
        if item.declared is None:
            continue
        state = home.module_state(item.id)
        if (state if state is not None else not item.declared.ships_disabled) != item.enabled:
            reset()
            return


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
            else:
                _forget(item.import_name)
    _cache = None


def _register_exit() -> None:
    global _exit_registered
    if not _exit_registered:
        atexit.register(reset)
        _exit_registered = True
