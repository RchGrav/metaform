"""Inspection results preserve exact identities and open retained join content."""
from typing import TypedDict

from metaform.namespace_objects import JoinRef


class ProductionInspection(TypedDict):
    reference: JoinRef
    production: dict[str, object] | None


class JoinInspection(TypedDict):
    reference: JoinRef | None
    join: dict[str, object] | None
    productions: list[ProductionInspection]


class WatchState(TypedDict):
    watch_enabled: bool
