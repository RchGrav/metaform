"""Declared and dynamic subscriptions owned by the chassis lifecycle.

Host operation, event and lifecycle dispatch binds the owning module ID before
calling these module callbacks; the generic CLI context also covers the shell.
"""
from typing import cast

from metaform import cli, event, settings
from metaform.event import EventMessage
from metaform.namespace_objects import JoinRef
from metaform.plugin_contract import Subscription
from . import dao
from .models import WatchState

_watches: dict[str, str] = {}

async def received(notification: EventMessage) -> JoinRef:
    module = cast(str, cli.context().module)
    return await dao.areceipt('data.' + module + '.receipt',
                             notification['id'], notification['refs'])


def observed(notification: EventMessage) -> JoinRef:
    module = cast(str, cli.context().module)
    return dao.receipt('data.' + module + '.observation',
                       notification['id'], notification['refs'])


def watch(enabled: bool = True) -> WatchState:
    module = cast(str, cli.context().module)
    settings.set('watch_enabled', enabled)
    if enabled and module not in _watches:
        _watches[module] = event.subscribe(module + '.saved', observed)
    elif not enabled and module in _watches:
        event.unsubscribe(_watches.pop(module))
    return {'watch_enabled': enabled}


def close_watch() -> None:
    handle = _watches.pop(cast(str, cli.context().module), None)
    if handle is not None:
        event.unsubscribe(handle)


SUBSCRIPTIONS = (Subscription('showcase.saved', received),)
