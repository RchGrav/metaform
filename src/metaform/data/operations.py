"""Module-owned DAO operations and contributions to records, through the public base.

An operation runs inside the same transaction as native map operations. Modules
declare their table layouts with Tables; no feature's SQL belongs to the chassis.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Mapping
from dataclasses import dataclass, field
from functools import partial
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .session import Tx
    from .tables import Tables


@dataclass(frozen=True)
class Operation:
    run: Callable[..., Any]
    write: bool = False
    retained: bool = False


@dataclass(frozen=True)
class Data:
    operations: Mapping[str, Operation] = field(default_factory=dict[str, Operation])
    decorate: Callable[[Tx, Any], Any] | None = None
    cleanup: Callable[[Tx, str, str], None] | None = None
    item_write: Callable[..., None] | None = None


def declarations() -> list[tuple[str, Data]]:
    from .. import loader

    return [(module.id, module.data) for module in loader.enabled() if module.data is not None]


def operation(name: str) -> Operation | None:
    return next((declared for _, declared, _ in _providers(name)), None)


def _providers(name: str) -> Generator[tuple[str, Operation, Tables | None], None, None]:
    from .. import loader
    from .tables import Tables

    active = [(owner, data.operations[name], None) for owner, data in declarations() if name in data.operations]
    if active:
        yield from active
        return
    for item in loader.discover():
        if item.module is not None:
            continue
        source = loader.data_source(item.id)
        data = getattr(source, "DATA", None)
        declared = getattr(source, "TABLES", None)
        if not isinstance(data, Data) or not isinstance(declared, Tables):
            continue
        found = data.operations.get(name)
        if found is not None and found.retained and not found.write:
            yield item.id, found, declared


def preparation(name: str) -> tuple[str, Tables] | None:
    return next(((owner, declared) for owner, _, declared in _providers(name) if declared is not None), None)


def _call(tx: Tx, owner: str, handler: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    previous = tx.module
    tx.module = owner
    try:
        return handler(tx, *args, **kwargs)
    finally:
        tx.module = previous


def invoke(tx: Tx, name: str, *args: Any, **kwargs: Any) -> Any:
    for owner, declared, _ in _providers(name):
        return _call(tx, owner, declared.run, *args, **kwargs)
    raise AttributeError(f"No enabled module declares the data operation {name}.")


def decorate(tx: Tx, record: Any) -> Any:
    for owner, data in declarations():
        if data.decorate is not None:
            record = _call(tx, owner, data.decorate, record)
    return record


def cleanup(tx: Tx, kind: str, identity: str) -> None:
    from . import tables

    tables.cleanup(tx.db, kind, identity)
    for owner, data in declarations():
        if data.cleanup is not None:
            _call(tx, owner, data.cleanup, kind, identity)


def item_write(tx: Tx, *args: Any) -> None:
    for owner, data in declarations():
        if data.item_write is not None:
            _call(tx, owner, data.item_write, *args)


class Access:
    """Native DAO helpers on the current transaction, for a module's composite operation."""

    def __init__(self, tx: Tx, service: Any) -> None:
        self.tx = tx
        self.service = service

    def __getattr__(self, name: str) -> Any:
        return partial(getattr(self.service, name), self.tx)
