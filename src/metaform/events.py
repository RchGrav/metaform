"""The event bus: a module publishes a topic, and every enabled subscriber receives it.

Each subscriber's outcome is returned, so one failing subscriber never hides
the others.
"""
from __future__ import annotations

from . import loader
from .module import Context, call


def publish(topic: str, payload: dict, source: Context) -> list[dict]:
    deliveries = []
    for module in loader.enabled():
        for subscription in module.subscriptions:
            if subscription.topic != topic:
                continue
            context = Context(module=module.id, folder=source.folder)
            try:
                result = call(subscription.handler, dict(payload), context)
                deliveries.append({'module': module.id, 'status': 'completed', 'result': result})
            except Exception as error:  # A subscriber's failure is reported, not raised.
                deliveries.append({'module': module.id, 'status': 'failed', 'error': str(error)})
    return deliveries
