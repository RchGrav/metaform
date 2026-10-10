"""The module contract, BASE-035: what a module declares and what a verb receives.

A module is a folder with an `__init__.py` that sets the literals
`SUPPORTED_OS`, and optionally `DEPENDENCIES`, `SHIPS_DISABLED` and
`REMOTE_AGENT`, whether an agent on a hosted sandbox working through the CLI
has use for it, BASE-060, and `MODULE = Module(...)`. Each verb runs as `metaform <module> <verb> <nouns>
[switches]` on the CLI and as the command `<verb>` of the tool `<module>` over MCP, both built
from this one declaration. A verb's switches are settings the module declares
with `metaform.settings`.
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import re
import sys
from collections.abc import Awaitable, Callable, Coroutine, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from .errors import Stop

if TYPE_CHECKING:
    from .data import Node, Store, WorkRecord
    from .data.operations import Data
    from .data.tables import Tables
    from .relay import Listener

__all__ = [
    'Context',
    'Handler',
    'Hook',
    'Module',
    'NodeReadHook',
    'Noun',
    'NounKind',
    'Resource',
    'Status',
    'StatusHook',
    'Stop',
    'Subscription',
    'Surface',
    'Verb',
    'VerbFunction',
    'WorkReadHook',
    'aliases',
    'call',
    'chassis_version',
    'code_print',
    'command_summary',
    'context',
    'feedback',
    'instructions',
    'list_reports',
    'module_instructions',
    'node_reads',
    'on_surface',
    'on_this_system',
    'project_for',
    'read_report',
    'refresh_modules',
    'request_scope',
    'result_json',
    'save_report',
    'setting_value',
    'surface',
    'tool_arguments',
    'work_reads',
]

VERB_NAME = re.compile(r'^[a-z][a-z0-9_-]*$')
NounKind = Literal['str', 'int', 'bool', 'json']
Surface = Literal['cli', 'mcp', 'web']  # where a call or a change was made; verbs are offered on SURFACES only
NOUN_KINDS: tuple[NounKind, ...] = ('str', 'int', 'bool', 'json')
SURFACES: tuple[Surface, ...] = ('cli', 'mcp')

# The module contract's callables, BASE-035. Each may be a plain function or a coroutine function, BASE-009.
VerbFunction = Callable[['Context'], Any]  # returns the verb's result, BASE-036
Handler = Callable[[dict[str, Any], 'Context'], Any]  # a subscriber: the payload and its own context, BASE-010
Hook = Callable[['Context'], Any]  # start and stop, BASE-018
StatusHook = Callable[['Context'], 'Status | Awaitable[Status]']  # what status and the instructions add
NodeReadHook = Callable[['Context', 'Node'], Any]  # what a module adds to the read of a node, or None, BASE-035
WorkReadHook = Callable[['Context', 'WorkRecord'], Any]  # what a module keeps on a work record, or None, BASE-035


@dataclass(frozen=True)
class Noun:
    """What a verb acts on. Required nouns are positional; optional ones are written name=value."""
    name: str
    help: str
    kind: NounKind = 'str'
    required: bool = True
    many: bool = False
    schema: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.kind not in NOUN_KINDS:
            raise ValueError(f'Noun {self.name}: kind must be one of {", ".join(NOUN_KINDS)}.')
        if self.kind == 'json' and self.schema is None:  # an untyped argument over MCP leaves an agent guessing
            raise ValueError(f'Noun {self.name}: a json noun declares its schema.')

    def usage(self) -> str:
        if self.many:
            return f'<{self.name}>...' if self.required else f'[{self.name}...]'
        return f'<{self.name}>' if self.required else f'[{self.name}=<{self.kind}>]'


@dataclass(frozen=True)
class Verb:
    """One command of a module. `switches` names the settings the verb reads, CLI-012.

    A `transport` verb, such as `mcp serve`, is how a host reaches Metaform rather than a command an agent runs,
    so it runs whatever the folder's command surface; the surface narrows what it serves, CLI-022 and MCP-004.
    """
    name: str
    run: VerbFunction
    summary: str
    nouns: tuple[Noun, ...] = ()
    switches: tuple[str, ...] = ()
    details: str = ''
    examples: tuple[tuple[str, str], ...] = ()
    caution: str = ''
    supported_os: tuple[str, ...] | None = None
    surfaces: tuple[Surface, ...] = SURFACES
    transport: bool = False

    def __post_init__(self) -> None:
        if not VERB_NAME.fullmatch(self.name):
            raise ValueError(f'Verb name {self.name!r} must be lowercase letters, digits, hyphens and underscores.')
        if any(noun.many for noun in self.nouns[:-1]):
            raise ValueError(f'Verb {self.name}: only the last noun may take many words.')
        if not set(self.surfaces) <= set(SURFACES):
            raise ValueError(f'Verb {self.name}: surfaces are cli and mcp.')

    def usage(self, module: str) -> str:
        from . import settings
        parts = ['metaform', module, self.name, *(noun.usage() for noun in self.nouns)]
        for key in self.switches:
            setting = settings.SCHEMA.get(key)
            if setting is not None:
                parts.append(f'[{setting.switch}]' if setting.kind == 'bool' else f'[{setting.switch} <value>]')
        if self.caution:
            parts.append('[--confirm]')
        return ' '.join(parts)


@dataclass(frozen=True)
class Subscription:
    topic: str
    handler: Handler


@dataclass(frozen=True)
class Resource:
    """A read-only text a module serves over MCP as a resource, MCP-037: an agent reads it by its URI at
    discovery, before any tool runs. `verb` names the module verb whose result, called with no arguments, is the
    text; a module serves nothing it cannot also give on the command line."""
    uri: str
    name: str
    description: str
    verb: str
    mime_type: str = 'text/plain'


@dataclass(frozen=True)
class Status:
    """What a module's status hook adds: lines and a notice to status, BASE-035, and an instruction to the
    instructions agents read, after the module's own instructions prompt, MCP-031. With `at_connect` off the
    instruction is in the module's full instructions only, read on demand, and not in what every agent is handed at
    connect: a short notice of the folder's state belongs at connect, a procedure does not, MCP-037."""
    lines: tuple[str, ...] = ()
    notice: str | None = None
    instruction: str | None = None
    at_connect: bool = True


@dataclass(frozen=True)
class Module:
    id: str
    summary: str
    purpose: str
    verbs: tuple[Verb, ...] = ()
    subscriptions: tuple[Subscription, ...] = ()
    details: str = ''
    start: Hook | None = None
    stop: Hook | None = None
    status: StatusHook | None = None
    default: str | None = None  # the verb `metaform <id>` runs when no verb follows, BASE-035
    tables: Tables | None = None  # the module's own tables, reached through ctx.store.tables(), STORE-045
    data: Data | None = None  # module-owned DAO operations, record contributions and cleanup
    node_read: NodeReadHook | None = None  # what the module adds to `map where` and `map node` of a node, BASE-035
    work_read: WorkReadHook | None = None  # what the module keeps on a work record, shown in `map work id=`, BASE-035
    mcp_server: str | None = None  # this module's verb serving MCP over stdio, used by install and provision
    resources: tuple[Resource, ...] = ()  # read-only texts served over MCP as resources, MCP-037

    def __post_init__(self) -> None:
        names = {verb.name for verb in self.verbs}
        for resource in self.resources:
            if resource.verb not in names:
                raise ValueError(f'Module {self.id}: resource {resource.uri} reads verb {resource.verb}, not declared.')


@dataclass
class Context:
    """What one verb call, event delivery or tool call receives. Nothing else carries context, BASE-028."""
    module: str
    folder: Path
    project: str | None = None
    store: Store | None = None
    nouns: dict[str, Any] = field(default_factory=dict[str, Any])
    switches: dict[str, Any] = field(default_factory=dict[str, Any])
    sink: Callable[[str], None] | None = None
    surface: Surface = 'cli'
    client: str | None = None  # the MCP client name, supplied by the transport rather than tool arguments

    def say(self, text: str) -> None:
        """A message for a person. The data an agent needs back is the verb's return value, BASE-036."""
        if self.sink is not None:
            self.sink(text)
        else:
            sys.stdout.write(text + '\n')

    def setting(self, key: str) -> Any:
        """The value passed on this call, otherwise the stored or default value for this folder, CLI-011."""
        if key in self.switches:
            return self.switches[key]
        from . import settings
        return settings.value(key, self.folder)

    def require_store(self) -> Store:
        """This call's store; with no project, the one next step is to register or to select one, PROJ-005."""
        if self.store is None:
            from . import home
            registered = home.projects()
            raise Stop('No project for this folder.', 'metaform add project <id> <path>' + (
                ' for this folder, or metaform set --project <id> for a registered one' if registered else ''))
        return self.store

    def publish(self, topic: str, payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        from . import events
        return events.publish(topic, payload or {}, self)

    async def publish_async(self, topic: str, payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Publish from an async verb; subscribers run without blocking this loop, BASE-009."""
        from . import events
        return await events.publish_async(topic, payload or {}, self)

    def listen(self, handler: Callable[[dict[str, Any]], Any]) -> Listener:
        """Hear each `map.changed` published in another process of this home, in this module's long-running process;
        the handler runs in the listener's own thread. Close the listener when the process is done, BASE-053."""
        from . import events
        return events.listen(self.module, handler)

    def spawn(self, coroutine: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        """Start a task owned by this module; unload, reload and shutdown cancel it, BASE-018."""
        from . import loader
        return loader.spawn(self.module, coroutine)


def on_this_system(verb: Verb) -> bool:
    """Whether a verb runs on this system: its own systems when it narrows them, BASE-016."""
    from .module_metadata import current_os
    return verb.supported_os is None or current_os() in verb.supported_os


def call(function: Callable[..., Any], *args: Any) -> Any:
    """Run a function or a coroutine function the same way from synchronous code, BASE-009.

    Inside a running loop a coroutine is refused: waiting for it there would block that loop. Await it, or run
    the synchronous caller in a worker thread.
    """
    result = function(*args)
    if inspect.isawaitable(result):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_await(result))
        if inspect.iscoroutine(result):
            result.close()
        raise RuntimeError(f'{getattr(function, "__qualname__", function)} is async and was called from inside a '
                           'running event loop; await it there instead, BASE-009.')
    return result


async def _await(awaitable: Any) -> Any:
    return await awaitable


# The chassis resources every module may use, BASE-004: the module registry, the command surface, the
# composed instructions and the per-call Context. The mcp module serves tools through these alone, MCP-001.

def surface(folder: Path) -> list[Module]:
    """The loaded modules on this folder's command surface, in module id order, CLI-022."""
    from . import instructions as composed
    return composed.surfaced(folder)


def instructions(folder: Path, project: str | None = None) -> str:
    """The composed instructions for agents working from this folder, MCP-007."""
    from . import instructions as composed
    return composed.compose(folder, project)


def module_instructions(folder: Path, identifier: str, project: str | None = None) -> str | None:
    """One surfaced module's full instructions, or None when it is not on this folder's surface, MCP-029."""
    from . import instructions as composed
    return composed.module_text(folder, identifier, project)


def on_surface(group: str, folder: Path) -> bool:
    """Whether a command group, a module id or `chassis`, is on this folder's command surface, CLI-022."""
    from . import instructions as composed
    return composed.on_surface(group, folder)


def aliases(folder: Path) -> dict[str, list[Module]]:
    """Each alias on this folder's command surface with the loaded modules it stands for, CLI-039."""
    from . import aliases as named
    return named.shown(folder)


def command_summary(name: str) -> str | None:
    """The summary of the chassis command `name`, or None when the chassis has no such command."""
    from . import docs
    record = docs.COMMANDS.get(name)
    return None if record is None else record.summary


def builder() -> Any:
    """The chassis build, BASE-060: the builds, shapes and modules the web GUI's build panel offers, and the build
    it runs; a build chooses what it carries and never turns a module on or off."""
    from . import build
    return build

def chassis_version() -> str:
    """The version of the running chassis, BASE-020."""
    from . import __version__
    return __version__


def project_for(folder: Path, named: str | None = None) -> str | None:
    """The project a call is about: `named` when given, which must be registered, otherwise the folder's project, or
    None when it has none."""
    from . import context as contexts
    return contexts.project_for(folder, named)


def refresh_modules() -> None:
    """Follow module enablement and the selected project in a long-running process, BASE-037."""
    from . import loader
    loader.follow_enabled()


def code_print() -> str:
    """Identify the package's code on disk, so long-running surfaces can detect a replacement, STORE-029.

    This reads file metadata only, creates no state, and works for installed and editable packages alike.
    """
    found = hashlib.sha256()
    for path in sorted(Path(__file__).parent.rglob('*.py')):
        try:
            state = path.stat()
        except OSError:  # removed since it was listed
            continue
        found.update(f'{path}\0{state.st_mtime_ns}\0{state.st_size}\n'.encode())
    return found.hexdigest()


@contextmanager
def request_scope(*, fresh: bool = False) -> Generator[None, None, None]:
    """Share the chassis registry across the reads and writes of one request, BASE-037."""
    from . import loader
    with loader.request_scope(fresh=fresh):
        yield


def context(module: str, folder: Path, *, project: str | None = None, nouns: dict[str, Any] | None = None,
            switches: dict[str, Any] | None = None, sink: Callable[[str], None] | None = None,
            surface: Surface = 'cli', client: str | None = None) -> Context:
    """A Context for one call, with the project and store resolved for its folder, BASE-028."""
    from . import context as contexts
    return contexts.build(module, folder, project=project, nouns=nouns, switches=switches, sink=sink, surface=surface,
                          client=client)


def node_reads(folder: Path, node: Node, *, project: str | None = None,
               layers: list[str] | None = None) -> dict[str, Any]:
    """What each module on the folder's command surface adds to the read of a node, under the module's id, in module
    id order, BASE-035. Each hook gets a context of its own module with the call's project and toggled layers, and
    returns plain data or None for nothing. A hook that raises adds `{'failed': '<ExceptionType>: <message>'}` and the
    read goes on."""
    from . import context as contexts
    found: dict[str, Any] = {}
    for module in surface(folder):
        if module.node_read is None:
            continue
        try:
            ctx = contexts.build(module.id, folder, project=project,
                                 switches={'layers': list(layers)} if layers else None)
            got = call(module.node_read, ctx, node)
        except Exception as error:  # noqa: BLE001  a failing hook is named in the read, which goes on
            got = {'failed': f'{type(error).__name__}: {error}'}
        if got is not None:
            found[module.id] = got
    return found


def work_reads(folder: Path, record: WorkRecord, *, project: str | None = None) -> dict[str, Any]:
    """What each module on the folder's command surface keeps on one work record, under the module's id, in module
    id order, BASE-035. A module keeps its fields in its own tables keyed by the work id, STORE-045, so the work
    table's layout never changes for them. Each hook gets a context of its own module with the call's project and
    returns plain data or None for nothing. A hook that raises adds `{'failed': '<ExceptionType>: <message>'}` and
    the read goes on."""
    from . import context as contexts
    found: dict[str, Any] = {}
    for module in surface(folder):
        if module.work_read is None:
            continue
        try:
            got = call(module.work_read, contexts.build(module.id, folder, project=project), record)
        except Exception as error:  # noqa: BLE001  a failing hook is named in the read, which goes on
            got = {'failed': f'{type(error).__name__}: {error}'}
        if got is not None:
            found[module.id] = got
    return found


def result_json(result: Any) -> str:
    """A verb's result as the JSON every surface shows, BASE-036."""
    from . import results
    return results.as_json(result)


def tool_arguments(module: str, verb: Verb, arguments: dict[str, Any], *, ignore: tuple[str, ...] = (),
                   folder: Path | None = None) -> tuple[dict[str, Any], dict[str, Any], list[tuple[str, str]]]:
    """A tool call's nouns and switches, checked as the command line checks them, and a notice per name it does
    not know: kept in the record's `extra` when the verb takes one, BASE-043, otherwise ignored."""
    from . import grammar
    parsed = grammar.from_json(module, verb, arguments, ignore=ignore, folder=folder)
    notices = grammar.keep_fields(module, verb, parsed.nouns, {key: arguments[key] for key in parsed.unknown})
    return parsed.nouns, parsed.switches, parsed.notices + notices


def setting_value(key: str, value: Any, folder: Path, notices: list[tuple[str, str]] | None = None) -> Any:
    """A setting's value from its JSON form, checked as `metaform set` checks it, CLI-027; a text setting sent another
    kind is read as its JSON text and named in `notices`, BASE-044."""
    from . import grammar, settings
    setting = settings.SCHEMA.get(key)
    if setting is None:
        raise Stop(f'{key} is not a setting.', 'metaform help switches')
    try:
        return grammar.switch_value(setting, value, folder, notices)
    except settings.SettingError as error:
        raise Stop(str(error), error.next_step or f'metaform help {setting.switch}') from None


def feedback(folder: Path, text: str, *, layer: str | None = None, report: str | None = None,
             shape: str | None = None, project: str | None = None) -> dict[str, Any]:
    """Save feedback on the Metaform process, with a report and a shape when given, BASE-045."""
    from . import reports
    return reports.feedback(folder, text, layer=layer, report=report, shape=shape, project=project)


def save_report(project: str, run: str, kind: str, text: str, *, store: Store | None = None,
                layer: str | None = None) -> str:
    """Write one report, feedback or shape file for a run and record it, BASE-045. Returns the file name."""
    from . import reports
    return reports.write(project, run, kind, text, store=store, layer=layer)


def list_reports(folder: Path, *, project: str | None = None, kind: str | None = None, layer: str | None = None,
                 limit: int = 500, after: str | None = None) -> Any:
    """The report, feedback and shape files for the folder's project, BASE-045."""
    from . import reports
    return reports.list_reports(folder, project=project, kind=kind, layer=layer, limit=limit, after=after)


def read_report(folder: Path, name: str, *, project: str | None = None) -> str:
    """One listed report file's text exactly, BASE-045."""
    from . import reports
    return reports.read_report(folder, name, project=project)
