"""The eventual response is received through the shared event bus."""
from typing import cast

from metaform.plugin_contract import Subscription
from metaform.event import EventMessage
from metaform.namespace_objects import JoinRef
from metaform.objects import Record
from . import dao


async def response(notification: EventMessage) -> Record:
    # harness_runner._respond publishes its retained record's JoinRef first.
    # The DAO still resolves that exact revision through the public data service.
    source = cast(JoinRef, notification['refs'][0])
    return await dao.save_response(source, notification['id'], notification['nonce'])


SUBSCRIPTIONS = (Subscription('harness.response', response),)
