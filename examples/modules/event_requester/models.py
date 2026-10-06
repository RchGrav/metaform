"""The request receipt links retained work to its subscriber deliveries."""
from typing import TypedDict

from metaform.event import EventDelivery
from metaform.objects import Record


class RequestReceipt(TypedDict):
    request: Record
    deliveries: list[EventDelivery]
