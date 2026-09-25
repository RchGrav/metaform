"""What the data access object returns: frozen records with `to_dict()`, STORE-023.

Every record converts to plain JSON-ready data, so the CLI's `--json` output and
an MCP tool's JSON result carry the same thing, BASE-036.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Generic, NamedTuple, TypeVar

from ..errors import StoreError

NODE_KINDS = ('element', 'join', 'subtype')

T = TypeVar('T')


def plain(value: Any) -> Any:
    """Convert a record, or anything holding records, to JSON-ready data."""
    if hasattr(value, 'to_dict') and callable(value.to_dict):
        return value.to_dict()
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in value.items()}
    return value


class Record:
    """A frozen dataclass whose `to_dict()` gives every field as plain data."""

    def to_dict(self) -> dict[str, Any]:
        return {item.name: plain(getattr(self, item.name)) for item in dataclasses.fields(self)}  # type: ignore[arg-type]


@dataclass(frozen=True)
class Node(Record):
    """A place an item can attach: an element, a join or a subtype, named by address or identity id."""
    kind: str
    id: str

    def __post_init__(self) -> None:
        if self.kind not in NODE_KINDS:
            raise StoreError(f'{self.kind!r} is not a node kind: use element, join or subtype. '
                             'A bare type address is not a node; create an element there.',
                             f'metaform map knowledge op=add-element layer=<layer> address={self.id}')

    @classmethod
    def parse(cls, text: str) -> Node:
        kind, separator, ident = text.partition(':')
        if not separator or not ident:
            raise StoreError(f'{text!r} is not a node: write element:<address or id>, join:<id> or '
                             'subtype:<address or id>.', 'metaform help map node')
        return cls(kind, ident)

    def __str__(self) -> str:
        return f'{self.kind}:{self.id}'


@dataclass(frozen=True)
class Ref(Record):
    key: str
    value: str


class Page(NamedTuple, Generic[T]):
    """One page of a list read: its results and the cursor for the next page, or None, STORE-025."""
    results: tuple[T, ...]
    next: str | None

    def to_dict(self) -> dict[str, Any]:
        return {'results': plain(self.results), 'next': self.next}


@dataclass(frozen=True)
class Descriptor(Record):
    item_id: str
    layer_id: str
    layer: str
    name: str | None
    name_length: int | None
    role: str | None
    refs: tuple[Ref, ...]


@dataclass(frozen=True)
class Element(Record):
    element_id: str
    address: str
    layer_id: str
    layer: str
    reading: str = ''
    short_name: str = ''
    name: str | None = None
    name_length: int | None = None
    role: str | None = None
    descriptors: tuple[Descriptor, ...] = ()
    refs: tuple[Ref, ...] = ()
    extra: dict[str, Any] | None = None
    existing: bool = False
    differs: bool = False
    state: str | None = None
    orphaned: bool = False


@dataclass(frozen=True)
class Join(Record):
    join_id: str
    layer_id: str
    layer: str
    type: str
    receiver: str
    receiver_address: str | None
    provider: str
    provider_address: str | None
    purpose: str | None
    function: str | None
    relation: str | None
    observation: str | None
    non_goal: str | None
    refs: tuple[Ref, ...] = ()
    extra: dict[str, Any] | None = None
    state: str | None = None
    orphaned: bool = False


@dataclass(frozen=True)
class Subtype(Record):
    subtype_id: str
    join_id: str
    layer_id: str
    layer: str
    address: str
    reading: str
    name: str | None
    name_length: int | None
    role: str | None
    function: str | None
    relation: str | None
    observation: str | None
    refs: tuple[Ref, ...] = ()
    extra: dict[str, Any] | None = None


@dataclass(frozen=True)
class Item(Record):
    item_id: str
    layer_id: str
    layer: str
    target: Node
    value: Any
    link: Node | None = None
    refs: tuple[Ref, ...] = ()
    extra: dict[str, Any] | None = None
    state: str | None = None
    orphaned: bool = False


@dataclass(frozen=True)
class Property(Record):
    property_id: str
    layer_id: str
    layer: str
    element_id: str
    address: str | None
    value: Any
    refs: tuple[Ref, ...] = ()
    extra: dict[str, Any] | None = None
    orphaned: bool = False


@dataclass(frozen=True)
class Provenance(Record):
    layer_id: str
    module: str
    workflow: str | None
    prompt: str | None
    model: str | None
    role: str | None
    blinded: bool | None


@dataclass(frozen=True)
class Layer(Record):
    layer_id: str
    metaform_id: str
    name: str
    module: str
    variable: str
    kind: str
    mutable: bool
    hideable: bool
    result_id: str | None
    created: str
    ready: str | None
    fields: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    hidden: bool = False
    on: bool = False
    reexamine: bool = False
    position: int | None = None
    provenance: Provenance | None = None


@dataclass(frozen=True)
class Version(Record):
    """One stored version of a thing: the row that added it, or a correction layer's row."""
    id: str
    kind: str
    layer_id: str
    layer: str
    position: int | None
    op: str
    reason: str | None
    evidence: str | None
    fields: dict[str, Any] = field(default_factory=dict)
    refs: tuple[Ref, ...] = ()


@dataclass(frozen=True)
class LayerGroup(Record):
    """One layer's items and properties at one node."""
    layer_id: str
    layer: str
    kind: str
    items: tuple[Item, ...] = ()
    properties: tuple[Property, ...] = ()


@dataclass(frozen=True)
class NodeView(Record):
    node: Node
    address: str | None
    layers: tuple[LayerGroup, ...]
    orphaned: bool = False


@dataclass(frozen=True)
class ContextView(Record):
    """The properties that apply at an address, and those visible there from above, STORE-035."""
    address: str
    applying: tuple[Property, ...]
    visible: tuple[Property, ...]
    next: str | None = None


@dataclass(frozen=True)
class Selection(Record):
    address: str
    layer_ids: tuple[str, ...]
    layers: tuple[str, ...]
    unresolved: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True)
class Where(Record):
    kind: str
    element: Element | None = None
    subtype: Subtype | None = None
    join: Join | None = None


@dataclass(frozen=True)
class Citation(Record):
    kind: str
    id: str
    address: str | None
    layer: str


@dataclass(frozen=True)
class ChallengeState(Record):
    item_id: str
    state: str
    link: Node | None
    answered: str
    approved: str | None


@dataclass(frozen=True)
class Plan(Record):
    element_id: str
    join_id: str | None
    layer_id: str
    layer: str
    source: str
    item_id: str | None
