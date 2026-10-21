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
import os
import re
import shutil
import sys
import threading
from collections.abc import Coroutine, Generator
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from importlib import metadata
from importlib.resources.abc import Traversable
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType
from typing import Any

from . import home, module_metadata, prompt_files, settings
from .module import Context, Module, call, resource_problems

RESERVED = {'help', 'add', 'list', 'set', 'unset', 'config', 'enable', 'disable', 'activate', 'import', 'export',
            'query', 'build', 'install', 'uninstall', 'feedback', 'report', 'read', 'extract', 'prompts', 'prompt', 'clear', 'restore', 'remove', 'chassis',
            'alias', 'instructions', 'provision', 'return', 'metaform'}
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
_withdrawn: frozenset[str] = frozenset()  # the enabled modules a run straight from a wheel left out, `withdrawn`
# Discovery imports modules and runs their start hooks, and the web and MCP servers reach it from several threads:
# one thread discovers, the others wait and read its result. Re-entrant, since a module may ask for another as it loads.
_discovering = threading.RLock()
_refreshing = False
_refresh_pending = False
_exit_registered = False
_read_only: set[Path] = set()
_data_resources: dict[str, ExitStack] = {}


@dataclass
class _Request:
    followed: bool = False
    active: bool = True
    revision: tuple[Path, int] | None = None


_request: ContextVar[_Request | None] = ContextVar('metaform_module_request', default=None)


def in_request_scope() -> bool:
    request = _request.get()
    return request is not None and request.active


def request_followed() -> bool:
    request = _request.get()
    return (request is not None and request.active and request.followed
            and request.revision == home.registry_revision())


@contextmanager
def request_scope(*, fresh: bool = False) -> Generator[None, None, None]:
    """Share registry validation and module refresh within one command or server request.

    Fresh server requests replace inherited command scopes, since the command that starts a server lives until
    it stops. Refresh stays lazy so MCP can do it in a worker thread before executing the request.
    """
    if in_request_scope() and not fresh:
        yield
        return
    with home.registry_scope(fresh=fresh):
        request = _Request()
        token = _request.set(request)
        try:
            yield
        finally:
            request.active = False
            _request.reset(token)


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
        raise ValueError('MODULE must be a metaform.module.Module.')  # noqa: TRY004  keep the module validation error contract
    if declared.id != item.id:
        raise ValueError(f'MODULE.id is {declared.id!r}; it must match its name {item.id!r}.')
    if not declared.purpose.strip():
        raise ValueError('The module has no purpose, the concise instructions for agents.')
    names = [verb.name for verb in declared.verbs]
    if len(names) != len(set(names)):
        raise ValueError('Two verbs share one name.')
    if declared.default is not None and declared.default not in names:
        raise ValueError(f'default names {declared.default!r}, which is not one of its verbs.')
    if declared.mcp_server is not None:
        server = next((verb for verb in declared.verbs if verb.name == declared.mcp_server), None)
        if server is None or not server.transport or 'cli' not in server.surfaces:
            raise ValueError('mcp_server must name a CLI transport verb of this module.')
        if any(noun.required for noun in server.nouns) or server.caution:
            raise ValueError('mcp_server must start without required nouns or confirmation.')
    for name in names:
        tool = f'{declared.id}_{name}'
        if not TOOL_NAME.fullmatch(tool) or '__' in tool:
            raise ValueError(f'The tool name {tool!r} must be 1 to 64 letters, digits, _ and -, with no double _.')
    problems = resource_problems(declared, importlib.resources.files(imported.__name__)) \
        if declared.toolbar or declared.panes else []
    if problems:  # an icon or a pane's file it does not carry would show as nothing on the page
        raise ValueError(problems[0])
    # A rule an agent is handed without its reason cannot be applied to a case it does not name, MCP-031.
    prompt_files.rules(importlib.resources.files(imported.__name__))
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
    if _cache is not None:
        return _cache
    with _discovering:
        if _cache is not None:  # another thread discovered while this one waited
            return _cache
        project = _selected_project()
        return _load(_prepare(project), project)


def _prepare(project: str | None) -> list[Found]:
    """Read candidate declarations and enablement before changing any runtime registrations."""
    found = _candidates(project)
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
        if needed and os.environ.get('METAFORM_WHEEL'):
            # A wheel cannot carry some compiled dependencies; installing it brings them, BASE-042.
            item.problem = 'withdrawn'
            continue
        if needed:
            item.problem = f'Needs {", ".join(needed)}, which {"is" if len(needed) == 1 else "are"} not installed.'
    return found


def _load(found: list[Found], project: str | None) -> list[Found]:
    """Load pending candidates while keeping retained modules and their lifecycle state intact."""
    global _cache, _cache_project, _withdrawn
    started: list[Found] = []
    for item in found:
        if item.problem or not item.enabled or item.module is not None:
            continue
        try:
            with settings.owned_by(item.id):
                item.module = _import(item)
        except Exception as error:  # noqa: BLE001  a broken module is reported and withdrawn; the chassis goes on
            _withdraw_settings(item.id)
            _forget(item.import_name)
            item.problem = f'{type(error).__name__}: {error}'
        else:
            started.append(item)
    _withdrawn = frozenset(item.id for item in found if item.problem == 'withdrawn')
    found = [item for item in found if item.problem != 'withdrawn']
    _cache, _cache_project = found, project
    _register_exit()
    for item in started:
        if item.module is not None and item.module.start is not None:
            try:
                call(item.module.start, Context(module=item.id, folder=Path.cwd()))
            except Exception as error:  # noqa: BLE001  any failed start unloads its module and records the problem, BASE-018
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
    """Refresh when a module found has been enabled or disabled since, by any process, or the folder's
    selected project has changed, so a long-lived process, the web GUI's server or the MCP server, loads what is
    enabled now, with the project place of the project selected now, before it publishes, VIEW-018 and D93."""
    request = _request.get()
    if request is not None and request.active:
        if request_followed():
            return
        request.followed = True  # lifecycle hooks reached by refresh share this refresh
        request.revision = home.registry_revision()
    try:
        _follow_enabled()
    except BaseException:
        if request is not None:
            request.followed = False
        raise


def _follow_enabled() -> None:
    if _refreshing:  # stop hooks may refresh through another thread while their caller waits for them
        return
    cached = _cache  # one reading: a reset on another thread, such as a test's teardown, must not empty it mid-loop
    if cached is None:
        return
    if _selected_project() != _cache_project:
        _refresh()
        return
    path = home.chassis_path()
    if not path.is_file() or not path.stat().st_size:
        return
    for item in cached:
        if item.declared is None:
            continue
        state = home.module_state(item.id)
        if (state if state is not None else not item.declared.ships_disabled) != item.enabled:
            _refresh()
            return


def _refresh() -> None:
    """Retain unchanged modules and publish them before stopping those being replaced or disabled."""
    global _cache, _cache_project, _withdrawn, _refreshing, _refresh_pending
    with _discovering:
        if _refreshing:
            _refresh_pending = True
            return
        if _cache is None:
            return
        previous, previous_project, previous_withdrawn = _cache, _cache_project, _withdrawn
        project = _selected_project()
        found = _prepare(project)
        existing = {(item.id, item.place, str(item.path)): item for item in previous
                    if not item.problem and (item.module is not None or not item.enabled)}
        retained: set[int] = set()
        for index, item in enumerate(found):
            kept = existing.get((item.id, item.place, str(item.path)))
            if kept is not None and item.enabled == kept.enabled and not item.problem:
                found[index] = kept
                retained.add(id(kept))
        retiring = [item for item in previous if id(item) not in retained]
        _refreshing = True
        _cache = [item for item in found if item.problem != 'withdrawn']
        _cache_project = project
        _withdrawn = frozenset(item.id for item in found if item.problem == 'withdrawn')
    try:
        # Cleanup can wait for work on another thread, which must see the retained cache without this lock.
        for item in retiring:
            if item.module is not None:
                _unload(item)
            else:
                _forget(item.import_name)
        with _discovering:
            _load(found, project)
    except BaseException:
        with _discovering:
            _cache, _cache_project, _withdrawn = previous, previous_project, previous_withdrawn
        raise
    finally:
        with _discovering:
            _refreshing = False
            pending, _refresh_pending = _refresh_pending, False
        if pending:
            _refresh()


def set_enabled(identifier: str, on: bool) -> None:
    home.set_module_state(identifier, on)
    _refresh()


def withdrawn() -> frozenset[str]:
    """The enabled modules this run left out because it runs straight from a wheel that cannot carry their
    dependencies, BASE-042; none in an installed Metaform."""
    discover()
    return _withdrawn


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
