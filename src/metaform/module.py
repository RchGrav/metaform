"""The module contract: what a module declares, in the chassis's own terms.

A module is a folder with an `__init__.py` that sets `SUPPORTED_OS` and
`MODULE = Module(...)`. Its verbs run as `metaform <module> <verb> <nouns>
[--adverbs]`. Its settings are declared with `metaform.settings` in the same
code, and they join the settings schema under the module's name.
"""
from __future__ import annotations

import asyncio
import inspect
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


from .errors import Stop


@dataclass(frozen=True)
class Adverb:
    """A switch that changes how a verb runs. It never names what the verb acts on."""
    name: str
    help: str
    takes_value: bool = False


@dataclass(frozen=True)
class Verb:
    name: str
    run: Callable
    summary: str
    nouns: str = ''
    adverbs: tuple[Adverb, ...] = ()
    details: str = ''
    examples: tuple[tuple[str, str], ...] = ()
    caution: str = ''

    def usage(self, module: str) -> str:
        parts = ['metaform', module, self.name]
        if self.nouns:
            parts.append(self.nouns)
        parts += [f'[{item.name}' + (' <value>]' if item.takes_value else ']') for item in self.adverbs]
        if self.caution:
            parts.append('[--confirm]')
        return ' '.join(parts)


@dataclass(frozen=True)
class Subscription:
    topic: str
    handler: Callable


@dataclass(frozen=True)
class Module:
    id: str
    purpose: str
    summary: str
    verbs: tuple[Verb, ...] = ()
    subscriptions: tuple[Subscription, ...] = ()
    details: str = ''


@dataclass
class Context:
    """What a verb receives: its nouns, its adverbs, the folder and the module's data folder."""
    module: str
    folder: Path
    nouns: list[str] = field(default_factory=list)
    adverbs: dict[str, object] = field(default_factory=dict)
    sink: Callable[[str], None] | None = None

    def say(self, text: str) -> None:
        if self.sink is not None:
            self.sink(text)
        else:
            sys.stdout.write(text + '\n')

    def setting(self, key: str):
        from . import settings
        return settings.value(key, self.folder)

    @property
    def data(self) -> Path:
        from . import home
        path = home.home() / 'data' / self.module
        path.mkdir(parents=True, exist_ok=True)
        return path

    def publish(self, topic: str, payload: dict | None = None) -> list[dict]:
        from . import events
        return events.publish(topic, payload or {}, self)


def call(function: Callable, *args):
    """Run a sync or an async function the same way."""
    result = function(*args)
    if inspect.isawaitable(result):
        return asyncio.run(_await(result))
    return result


async def _await(awaitable):
    return await awaitable
