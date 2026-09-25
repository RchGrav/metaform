"""The event bus, BASE-010, BASE-032 and BASE-033: a module publishes a topic and every loaded subscriber receives it.

Each subscriber gets its own Context, built from the publisher's folder and
project, and its outcome comes back to the publisher: completed with its
result, failed with its error, or cancelled. One subscriber's failure never
hides the others. The bus announces and delivers; it runs no workflow.
"""
from __future__ import annotations

import asyncio
import copy
from typing import Any

from . import loader
from .module import Context, call


def publish(topic: str, payload: dict[str, Any], source: Context) -> list[dict[str, Any]]:
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
