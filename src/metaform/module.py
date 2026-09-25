"""The module contract, BASE-035: what a module declares and what a verb receives.

A module is a folder with an `__init__.py` that sets the literals
`SUPPORTED_OS`, and optionally `DEPENDENCIES` and `SHIPS_DISABLED`, and
`MODULE = Module(...)`. Each verb runs as `metaform <module> <verb> <nouns>
[switches]` on the CLI and as the tool `<module>_<verb>` over MCP, both built
from this one declaration. A verb's switches are settings the module declares
with `metaform.settings`.
"""
from __future__ import annotations

import asyncio
import inspect
import re
import sys
from collections.abc import Callable, Coroutine
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .errors import Stop

if TYPE_CHECKING:
    from .data import Store

__all__ = ['Context', 'Module', 'Noun', 'Status', 'Stop', 'Subscription', 'Verb', 'call', 'context', 'instructions',
           'result_json', 'surface']

VERB_NAME = re.compile(r'^[a-z][a-z0-9-]*$')
NOUN_KINDS = ('str', 'int', 'bool', 'json')
SURFACES = ('cli', 'mcp')


@dataclass(frozen=True)
class Noun:
    """What a verb acts on. Required nouns are positional; optional ones are written name=value."""
    name: str
    help: str
    kind: str = 'str'
    required: bool = True
    many: bool = False
    schema: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.kind not in NOUN_KINDS:
            raise ValueError(f'Noun {self.name}: kind must be one of {", ".join(NOUN_KINDS)}.')

    def usage(self) -> str:
        if self.many:
            return f'<{self.name}>...' if self.required else f'[{self.name}...]'
        return f'<{self.name}>' if self.required else f'[{self.name}]'


@dataclass(frozen=True)
class Verb:
    """One command of a module. `switches` names the settings the verb reads, CLI-012."""
    name: str
    run: Callable[..., Any]
    summary: str
    nouns: tuple[Noun, ...] = ()
    switches: tuple[str, ...] = ()
    details: str = ''
    examples: tuple[tuple[str, str], ...] = ()
    caution: str = ''
    supported_os: tuple[str, ...] | None = None
    surfaces: tuple[str, ...] = SURFACES

    def __post_init__(self) -> None:
        if not VERB_NAME.fullmatch(self.name):
            raise ValueError(f'Verb name {self.name!r} must be lowercase letters, digits and hyphens.')
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
    handler: Callable[..., Any]


@dataclass(frozen=True)
class Status:
    """What a module's status hook adds to status, `help agents` and the MCP instructions, BASE-035."""
    lines: tuple[str, ...] = ()
    notice: str | None = None


@dataclass(frozen=True)
class Module:
    id: str
    summary: str
    purpose: str
    verbs: tuple[Verb, ...] = ()
    subscriptions: tuple[Subscription, ...] = ()
    details: str = ''
    start: Callable[..., Any] | None = None
    stop: Callable[..., Any] | None = None
    status: Callable[..., Any] | None = None


@dataclass
class Context:
    """What one verb call, event delivery or tool call receives. Nothing else carries context, BASE-028."""
    module: str
    folder: Path
    project: str | None = None
    store: Store | None = None
    nouns: dict[str, Any] = field(default_factory=dict)
    switches: dict[str, Any] = field(default_factory=dict)
    sink: Callable[[str], None] | None = None
    surface: str = 'cli'

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
            raise Stop('No project for this folder.',
                       'metaform set --project <id>' if registered else 'metaform add project <id> <path>')
        return self.store

    def publish(self, topic: str, payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        from . import events
        return events.publish(topic, payload or {}, self)

    def spawn(self, coroutine: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        """Start a task owned by this module; unload, reload and shutdown cancel it, BASE-018."""
        from . import loader
        return loader.spawn(self.module, coroutine)


def call(function: Callable[..., Any], *args: Any) -> Any:
    """Run a function or a coroutine function the same way, BASE-009."""
    result = function(*args)
    if inspect.isawaitable(result):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_await(result))
        # Inside a running loop, asyncio.run is never called on it: the coroutine gets a loop of its own.
        with ThreadPoolExecutor(max_workers=1) as worker:
            return worker.submit(asyncio.run, _await(result)).result()
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


def context(module: str, folder: Path, *, project: str | None = None, nouns: dict[str, Any] | None = None,
            switches: dict[str, Any] | None = None, sink: Callable[[str], None] | None = None,
            surface: str = 'cli') -> Context:
    """A Context for one call, with the project and store resolved for its folder, BASE-028."""
    from . import context as contexts
    return contexts.build(module, folder, project=project, nouns=nouns, switches=switches, sink=sink, surface=surface)


def result_json(result: Any) -> str:
    """A verb's result as the JSON every surface shows, BASE-036."""
    from . import results
    return results.as_json(result)
