"""What the data access object returns: frozen records with `to_dict()`, STORE-023.

Every record converts to plain JSON-ready data, so the CLI's `--json` output and
an MCP tool's JSON result carry the same thing, BASE-036.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from collections.abc import Sequence
from typing import Any, Generic, Literal, NamedTuple, TypeVar, cast

from ..errors import StoreError

NodeKind = Literal['element', 'join', 'subtype', 'type']
LayerKind = Literal['layer', 'intake', 'memory', 'correction']
Op = Literal['add', 'change', 'remove']  # what a row does, STORE-017
Answer = Literal['A', 'B', 'C', 'plan']  # a challenge's state, STORE-040
NODE_KINDS: tuple[NodeKind, ...] = ('element', 'join', 'subtype')
PLACE_KINDS: tuple[NodeKind, ...] = (*NODE_KINDS, 'type')
LAYER_KINDS: tuple[LayerKind, ...] = ('layer', 'intake', 'memory', 'correction')
OPS: tuple[Op, ...] = ('add', 'change', 'remove')
ROLES = ('AUE', 'VE', 'DE', 'SE', 'NE')  # the intake's classification of an element, MAP-017
SUBTYPE_ROLES = ('DE', 'SE', 'NE')  # a subtype's role, MAP-030
FLAGS = ('missing', 'broken', 'cruft')  # an intake finding, MAP-046

T = TypeVar('T')


def plain(value: Any) -> Any:
    """Convert a record, or anything holding records, to JSON-ready data."""
    if hasattr(value, 'to_dict') and callable(value.to_dict):
        return value.to_dict()
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in cast(Sequence[Any], value)]
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in cast(dict[Any, Any], value).items()}
    return value


class Record:
    """A frozen dataclass whose `to_dict()` gives every field as plain data."""

    def to_dict(self) -> dict[str, Any]:
        # Every Record subclass is a dataclass; the base class itself is not, so the checker cannot know that.
        return {item.name: plain(getattr(self, item.name)) for item in dataclasses.fields(self)}  # type: ignore[arg-type]


@dataclass(frozen=True)
class Node(Record):
    """A place an item can attach: an element, a join or a subtype, named by address or identity id.

    `type:<address>` names a bare type address; a write there attaches to an element at that address, made by the
    writing layer when the project has none, with a notice, STORE-008.
    """
    kind: NodeKind
    id: str

    def __post_init__(self) -> None:
        if self.kind not in PLACE_KINDS:
            raise StoreError(f'{self.kind!r} is not a node kind: use element, join, subtype or type.',
                             'metaform help map node')

    @classmethod
    def of(cls, kind: str, ident: str) -> Node:
        """A node whose kind was read as text, such as from a row, checked before it is typed."""
        if kind not in PLACE_KINDS:
            raise StoreError(f'{kind!r} is not a node kind: use element, join, subtype or type.', 'metaform help map node')
        return cls(kind, ident)

    @classmethod
    def parse(cls, text: str) -> Node:
        kind, separator, ident = text.partition(':')
        if not separator or not ident:
            raise StoreError(f'{text!r} is not a node: write element:<address or id>, join:<id> or '
                             'subtype:<address or id>.', 'metaform help map node')
        return cls.of(kind, ident)

    def __str__(self) -> str:
        return f'{self.kind}:{self.id}'


@dataclass(frozen=True)
class Ref(Record):
    key: str
    value: str


@dataclass(frozen=True)
class Notice(Record):
    """What did not fit a write and what happened to it, BASE-044: the write still succeeded."""
    where: str
    message: str


@dataclass(frozen=True)
class Outcome(Record):
    """The result of a write that returns no record: only its notices, STORE-026."""
    notices: tuple[Notice, ...] = ()


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
    flag: str | None = None
    flag_note: str | None = None
    notices: tuple[Notice, ...] = ()


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
    flag: str | None = None
    flag_note: str | None = None
    notices: tuple[Notice, ...] = ()


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
    flag: str | None = None
    flag_note: str | None = None
    notices: tuple[Notice, ...] = ()


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
    notices: tuple[Notice, ...] = ()


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
    notices: tuple[Notice, ...] = ()


@dataclass(frozen=True)
class Provenance(Record):
    layer_id: str
    module: str
    workflow: str | None
    prompt: str | None
    model: str | None
    role: str | None
    blinded: bool | None
    refs: tuple[Ref, ...] = ()
    prompt_version: VersionRef | None = None


@dataclass(frozen=True)
class VersionRef(Record):
    """The stored prompt version a layer was made from, STORE-044."""
    name: str
    number: int
    version_id: str


@dataclass(frozen=True)
class Layer(Record):
    layer_id: str
    metaform_id: str
    name: str
    module: str
    variable: str
    kind: LayerKind
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
    notices: tuple[Notice, ...] = ()


@dataclass(frozen=True)
class Version(Record):
    """One stored version of a thing: the row that added it, or a correction layer's row."""
    id: str
    kind: str
    layer_id: str
    layer: str
    position: int | None
    op: Op
    reason: str | None
    evidence: str | None
    fields: dict[str, Any] = field(default_factory=dict[str, Any])
    refs: tuple[Ref, ...] = ()
    notices: tuple[Notice, ...] = ()


@dataclass(frozen=True)
class LayerGroup(Record):
    """One layer's items and properties at one node."""
    layer_id: str
    layer: str
    kind: LayerKind
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
class GraphJoin(Join):
    """A join with the subtypes it holds, as a page of the whole map carries it, VIEW-005."""
    subtypes: tuple[Subtype, ...] = ()


@dataclass(frozen=True)
class GraphElement(Record):
    """An element in context, with the address of its nearest parent element in context, if any."""
    element: Element
    parent: str | None


@dataclass(frozen=True)
class GraphPage(Record):
    """A page of the map in address order, VIEW-010: its elements, and the joins they receive."""
    elements: tuple[GraphElement, ...]
    joins: tuple[GraphJoin, ...]
    next: str | None = None


@dataclass(frozen=True)
class PeelChange(Record):
    """One change removing a correction layer would make: what, and whether it disappears, comes back, moves back,
    reverts, shows again or becomes orphaned, VIEW-014."""
    kind: str
    id: str
    what: str
    effect: str
    detail: str | None = None


@dataclass(frozen=True)
class PeelPreview(Record):
    """What removing a correction layer would change, and whether it is on top, so it can be removed, VIEW-014."""
    layer: str
    top: bool
    changes: tuple[PeelChange, ...] = ()
    notices: tuple[Notice, ...] = ()


@dataclass(frozen=True)
class Citation(Record):
    kind: str
    id: str
    address: str | None
    layer: str


@dataclass(frozen=True)
class ChallengeState(Record):
    item_id: str
    state: Answer
    link: Node | None
    answered: str
    approved: str | None
    notices: tuple[Notice, ...] = ()


@dataclass(frozen=True)
class Plan(Record):
    element_id: str
    join_id: str | None
    layer_id: str
    layer: str
    source: str
    item_id: str | None
    notices: tuple[Notice, ...] = ()


@dataclass(frozen=True)
class RootEntry(Record):
    """A VE or DE element of the intake with the joins it receives, the map's entry, STORE-025."""
    element: Element
    joins: tuple[Join, ...]


@dataclass(frozen=True)
class RootElement(Record):
    element_id: str
    address: str
    role: str
    name: str | None


@dataclass(frozen=True)
class Roots(Record):
    """Where an agent starts: the VE and DE with their joins, and every root element, one page, STORE-025."""
    entry: tuple[RootEntry, ...]
    elements: tuple[RootElement, ...]
    next: str | None = None


@dataclass(frozen=True)
class Finding(Record):
    """One flagged object, STORE-042: an element or subtype with its address, or a join with its two ends."""
    kind: str
    id: str
    address: str | None
    receiver_address: str | None
    provider_address: str | None
    layer_id: str
    layer: str
    flag: str
    note: str | None


@dataclass(frozen=True)
class Report(Record):
    """One report, feedback or shape file, STORE-043."""
    name: str
    run_id: str
    layer_id: str | None
    layer: str | None
    kind: str
    created: str
    size: int
