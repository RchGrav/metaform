"""The event bus, BASE-010, BASE-032 and BASE-033: a module publishes a topic and every loaded subscriber receives it.

Each subscriber gets its own Context, built from the publisher's folder and
project, and its outcome comes back to the publisher: completed with its
result, failed with its error, or cancelled. One subscriber's failure never
hides the others. The bus announces and delivers; it runs no workflow.
"""
from __future__ import annotations

import asyncio
import copy
import inspect
from typing import Any

from . import loader
from .module import Context, call


def publish(topic: str, payload: dict[str, Any], source: Context) -> list[dict[str, Any]]:
    """Deliver a topic from synchronous code. Inside a running loop use `publish_async`, which never blocks it."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError(f'{source.module} published {topic} from inside a running event loop; an async verb '
                           'publishes with await ctx.publish_async(...), so the loop is never blocked, BASE-009.')
    from . import context
    deliveries: list[dict[str, Any]] = []
    for module in loader.enabled():
        for subscription in module.subscriptions:
            if subscription.topic != topic:
                continue
            try:
                receiver = context.build(module.id, source.folder, project=source.project, resolve=False,
                                         sink=source.sink, surface=source.surface)
                result = call(subscription.handler, copy.deepcopy(payload), receiver)
                deliveries.append({'module': module.id, 'status': 'completed', 'result': result})
            except asyncio.CancelledError:
                deliveries.append({'module': module.id, 'status': 'cancelled'})
            except Exception as error:  # A subscriber's failure is reported to the publisher, never raised.
                deliveries.append({'module': module.id, 'status': 'failed', 'error': f'{type(error).__name__}: {error}'})
    return deliveries


async def publish_async(topic: str, payload: dict[str, Any], source: Context) -> list[dict[str, Any]]:
    """Deliver a topic from inside a running loop: an async subscriber is awaited on it and a sync one runs in a
    worker thread, so no subscriber blocks the loop, BASE-009. Outcomes are those of `publish`."""
    from . import context
    deliveries: list[dict[str, Any]] = []
    for module in loader.enabled():
        for subscription in module.subscriptions:
            if subscription.topic != topic:
                continue
            try:
                receiver = context.build(module.id, source.folder, project=source.project, resolve=False,
                                         sink=source.sink, surface=source.surface)
                if inspect.iscoroutinefunction(subscription.handler):
                    result = await subscription.handler(copy.deepcopy(payload), receiver)
                else:
                    result = await asyncio.to_thread(subscription.handler, copy.deepcopy(payload), receiver)
                deliveries.append({'module': module.id, 'status': 'completed', 'result': result})
            except asyncio.CancelledError:
                current = asyncio.current_task()
                if current is not None and current.cancelling():
                    raise
                deliveries.append({'module': module.id, 'status': 'cancelled'})
            except Exception as error:  # A subscriber's failure is reported to the publisher, never raised.
                deliveries.append({'module': module.id, 'status': 'failed', 'error': f'{type(error).__name__}: {error}'})
    return deliveries

