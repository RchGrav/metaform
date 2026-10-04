"""What the data access object returns: frozen records with `to_dict()`, STORE-023.

Every record converts to plain JSON-ready data, so the CLI's `--json` output and
an MCP tool's JSON result carry the same thing, BASE-036.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, Literal, NamedTuple, TypeVar, cast

from .. import home
from ..errors import StoreError

NodeKind = Literal['element', 'join', 'type']
LayerKind = Literal['layer', 'intake', 'memory']
Op = Literal['add', 'change', 'remove']  # what a row does, STORE-017
Answer = Literal['A', 'B', 'C', 'plan']  # a challenge's state, STORE-040
NODE_KINDS: tuple[NodeKind, ...] = ('element', 'join')  # a subtype join is a join, STORE-011
PLACE_KINDS: tuple[NodeKind, ...] = (*NODE_KINDS, 'type')
LAYER_KINDS: tuple[LayerKind, ...] = ('layer', 'intake', 'memory')
OPS: tuple[Op, ...] = ('add', 'change', 'remove')
ROLES = ('AUE', 'CQU', 'DE', 'SE', 'NE')  # the intake's classification of an element, MAP-017
SUBTYPE_ROLES = ('DE', 'SE', 'NE')  # the role of the element a subtype join holds, in the Canonical Intake, MAP-030
# The condition a work record holds, MAP-046: three that wait for work, and the two a record takes once an agent has
# taken its task, a part to be built being in progress and a broken one being fixed.
CONDITIONS = ('missing', 'broken', 'flawed', 'enhancement', 'exclude')
MESSAGES = ('question', 'message')  # what an agent says to the user at a node, MAP-050; never a condition
TICKETS = ('missing', 'broken', 'flawed', 'enhancement')  # the kinds of ticket an agent takes, VIEW-035
TAKEN = {'missing': 'in-progress', 'broken': 'fixing'}  # how a taken one reads in open_work, VIEW-027 and VIEW-029
COLUMNS = ('backlog', 'todo', 'doing', 'done')  # the board's columns, MAP-048

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
    """A place an item can attach: an element or a join, a subtype join included, named by address or identity id.

    `type:<address>` names a bare type address; a write there attaches to an element at that address, made by the
    writing layer when the project has none, with a notice, STORE-008.
    """
    kind: NodeKind
    id: str

    def __post_init__(self) -> None:
        if self.kind not in PLACE_KINDS:
            raise StoreError(f'{self.kind!r} is not a node kind: use element, join or type. A subtype join is a join, '
                             'and the element it holds an element.', 'metaform help map node')

    @classmethod
    def of(cls, kind: str, ident: str) -> Node:
        """A node whose kind was read as text, such as from a row, checked before it is typed."""
        if kind not in PLACE_KINDS:
            raise StoreError(f'{kind!r} is not a node kind: use element, join or type. A subtype join is a join, and '
                             'the element it holds an element.', 'metaform help map node')
        return cls(kind, ident)

    @classmethod
    def parse(cls, text: str) -> Node:
        kind, separator, ident = text.partition(':')
        if not separator or not ident:
            raise StoreError(f'{text!r} is not a node: write element:<address or id>, join:<id> or '
                             'type:<address>.', 'metaform help map node')
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
class Element(Record):
    """An element is its address, name_length, name and role, STORE-009. `short_name` is its address read backward
    through name_length, MAP-012; `name` is the canonical name the project uses for it, Rich 2026-10-01: a name goes
    anywhere there is a namespace and name length."""
    element_id: str
    address: str
    layer_id: str
    layer: str
    reading: str = ''
    short_name: str = ''
    name_length: int | None = None
    role: str | None = None
    refs: tuple[Ref, ...] = ()
    extra: dict[str, Any] | None = None
    existing: bool = False
    differs: bool = False
    state: str | None = None
    orphaned: bool = False
    open_work: tuple[str, ...] = ()
    notices: tuple[Notice, ...] = ()
    name: str | None = None  # the canonical name the project uses for it


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
    name: str | None  # the project's own name for the functionality, MAP-020
    purpose: str | None
    ef: str | None
    verb: str | None
    non_goal: str | None
    refs: tuple[Ref, ...] = ()
    extra: dict[str, Any] | None = None
    state: str | None = None
    orphaned: bool = False
    open_work: tuple[str, ...] = ()
    notices: tuple[Notice, ...] = ()
    ifd: str | None = None  # IFD, Information Flow Direction: sends, receives or both
    element: str | None = None  # the address of the element the join was promoted to, MAP-054


@dataclass(frozen=True)
class Subtype(Record):
    """A subtype join, STORE-011: a join of type subtype held in its parent join, with its own fields, its own
    purpose among them, the share of the parent's purpose it serves,
    and the element it holds, an ordinary element record, by its id, address, reading, short name, name_length and
    role, MAP-030."""
    join_id: str
    parent: str
    layer_id: str
    layer: str
    type: str
    element_id: str
    address: str | None
    reading: str
    short_name: str
    name: str | None  # the subtype join's name for the functionality, MAP-020
    name_length: int | None
    role: str | None
    purpose: str | None
    ef: str | None
    verb: str | None
    non_goal: str | None
    refs: tuple[Ref, ...] = ()
    extra: dict[str, Any] | None = None
    orphaned: bool = False
    open_work: tuple[str, ...] = ()
    notices: tuple[Notice, ...] = ()
    ifd: str | None = None  # IFD, Information Flow Direction: sends, receives or both
    element_name: str | None = None  # the canonical name of the element it holds


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
    read_first: bool = False
    always_show: bool = False
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
    provenance: Provenance | None = None
    notices: tuple[Notice, ...] = ()


@dataclass(frozen=True)
class Version(Record):
    """One stored version of a thing: the row that added it, or a refinement, LAYER-025."""
    id: str
    kind: str
    layer_id: str
    layer: str
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
    """The properties that apply at an address, and those attached toward the leaves from it that are visible
    there, STORE-035."""
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
class GraphJoin(Join):
    """A join with the subtype joins it holds, as a page of the whole map carries it, VIEW-005."""
    subtypes: tuple[Subtype, ...] = ()


# The fields a small read leaves out, STORE-025: identity ids, and the ends a join names by id beside their addresses.
ID_FIELDS = frozenset({'element_id', 'layer_id', 'join_id', 'parent', 'work_id', 'item_id', 'property_id', 'target',
                       'receiver', 'provider', 'receiver_address', 'provider_address'})


def small(value: Any) -> Any:
    """Plain data without its ids and empty fields: None, empty text, empty lists and dicts, and false."""
    if isinstance(value, dict):
        kept: dict[str, Any] = {}
        for key, item in cast(dict[str, Any], value).items():
            if key in ID_FIELDS:
                continue
            item = small(item)
            if item is None or item is False or item == '' or item == [] or item == {}:
                continue
            kept[str(key)] = item
        return kept
    if isinstance(value, (list, tuple)):
        return [small(item) for item in cast(Sequence[Any], value)]
    return value


@dataclass(frozen=True)
class Where(Record):
    """One read of an address, the read an agent orients from, LAYER-017 and STORE-025: the element; `provides`, what
    relies on it, every join where it is the provider with the subtype joins each holds; `receives`, what it relies on,
    every join it receives with the subtype joins each holds; the subtype join holding it and the join that sits in,
    MAP-031, kind `subtype` when it is held only; its open work records, STORE-042; and what the layers in context hold
    at it, as `node` gives them; and the properties that apply at its address and those visible there, as `context`
    gives them, LAYER-005, so one read holds what reaches the part. Kind `join` is the read of a join, or of a subtype
    join with the join holding it, which a ticket on a join gets, MAP-048. `to_dict()` leaves ids and empty fields out
    unless `full`, all but each ticket's work id, which an agent needs to take it, and each open message's message id,
    which an agent needs to answer it."""
    kind: str
    element: Element | None = None
    subtype: Subtype | None = None
    join: Join | None = None
    provides: tuple[GraphJoin, ...] = ()
    receives: tuple[GraphJoin, ...] = ()
    work: tuple[WorkRecord, ...] = ()
    layers: tuple[LayerGroup, ...] = ()
    full: bool = False
    applying: tuple[Property, ...] = ()
    visible: tuple[Property, ...] = ()
    messages: tuple[Message, ...] = ()  # the open questions and unread messages at it, MAP-050
    past_work: tuple[PastWork, ...] = ()  # references only; the log is read by work id, MAP-051
    promoted_from: tuple[Join, ...] = ()  # the joins promoted to this element, MAP-054

    def to_dict(self) -> dict[str, Any]:
        held = None if self.subtype is None else {'subtype': plain(self.subtype), 'join': plain(self.join)}
        if self.full:
            return {'kind': self.kind, 'element': plain(self.element),
                    **({'join': plain(self.join)} if self.kind == 'join' and self.subtype is None else {}),
                    'provides': plain(self.provides),
                    'receives': plain(self.receives), 'held': held, 'work': plain(self.work),
                    'layers': plain(self.layers),
                    'properties': {'applying': plain(self.applying), 'visible': plain(self.visible)},
                    'messages': plain(self.messages), 'past_work': plain(self.past_work),
                    'promoted_from': plain(self.promoted_from)}
        data: dict[str, Any] = {'kind': self.kind}
        if self.element is not None:
            data['element'] = small(plain(self.element))
        if self.kind == 'join' and self.subtype is None and self.join is not None:
            data['join'] = self._join(plain(self.join), 'receiver', 'provider')
        if self.promoted_from:
            data['promoted_from'] = [self._join(plain(join), 'receiver', 'provider') for join in self.promoted_from]
        if self.provides:
            data['provides'] = [self._join(plain(join), 'receiver') for join in self.provides]
        if self.receives:
            data['receives'] = [self._join(plain(join), 'provider') for join in self.receives]
        if held is not None:
            data['held'] = {'subtype': self._subtype(held['subtype']),
                            'join': self._join(held['join'], 'receiver', 'provider')}
        if self.work:
            data['work'] = [{'work_id': record.work_id, **small({'condition': record.condition, 'note': record.note,
                                                                 'task': record.task, 'taken': record.taken,
                                                                 'taken_by': record.taken_by,
                                                                 'age_seconds': record.age_seconds})}
                            for record in self.work]
        if self.past_work:
            data['past_work'] = plain(self.past_work)
        if self.layers:
            data['layers'] = small(plain(self.layers))
        reaching = {name: [{'value': one.value, 'address': one.address, 'layer': one.layer} for one in found]
                    for name, found in (('applying', self.applying), ('visible', self.visible)) if found}
        if reaching:
            data['properties'] = reaching
        if self.messages:
            data['messages'] = [{'message_id': one.message_id, **small({'kind': one.kind, 'text': one.text,
                                                                       'suggestions': list(one.suggestions),
                                                                       'by': one.by})} for one in self.messages]
        return data

    @staticmethod
    def _subtype(data: dict[str, Any]) -> dict[str, Any]:
        """A subtype join with the element it holds named by its address, as `element`."""
        return {'element': data.get('address'), **small({key: value for key, value in data.items() if key != 'address'})}

    @classmethod
    def _join(cls, data: Any, *ends: str) -> dict[str, Any]:
        """A join with the ends asked for as addresses, and its subtype joins."""
        fields = cast(dict[str, Any], data)
        named = {end: fields.get(f'{end}_address') for end in ends}
        inside = [cls._subtype(cast(dict[str, Any], subtype))
                  for subtype in cast(list[Any], fields.get('subtypes') or [])]
        return {**named, **small({key: value for key, value in fields.items() if key != 'subtypes'}),
                **({'subtypes': inside} if inside else {})}


@dataclass(frozen=True)
class Recording(Record):
    """The intake being recorded for a project: the metaform it goes into and its building layer, BASE-039."""
    metaform_id: str
    metaform: str
    active: bool
    layer: Layer


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
    """A CQU or DE element of the intake with the joins it receives, the map's entry, STORE-025."""
    element: Element
    joins: tuple[Join, ...]


@dataclass(frozen=True)
class RootElement(Record):
    element_id: str
    address: str
    role: str
    short_name: str


@dataclass(frozen=True)
class Roots(Record):
    """Where an agent starts: the CQU and DE with their joins, and every root element, one page, STORE-025."""
    entry: tuple[RootEntry, ...]
    elements: tuple[RootElement, ...]
    next: str | None = None


@dataclass(frozen=True)
class Message(Record):
    """What an agent says to the user at a node, MAP-050: a question, which waits for an answer, or a message, which
    waits to be read. It has its object's address, or its join's two ends, as a work record has."""
    message_id: str
    kind: str
    node_kind: str
    node_id: str
    address: str | None
    receiver_address: str | None
    provider_address: str | None
    text: str | None
    suggestions: tuple[str, ...]
    by: str | None
    created: str
    closed: str | None
    answer: str | None
    notices: tuple[Notice, ...] = ()
    work_id: str | None = None


@dataclass(frozen=True)
class WorkLink(Record):
    """A node a ticket links for reference: an element with its address, or a join."""
    kind: str
    id: str
    address: str | None


@dataclass(frozen=True)
class Step(Record):
    """One step of a task an agent finished, MAP-053: its number, what the agent said of it, and when."""
    number: int
    said: str | None
    at: str


def _age(at: str) -> int:
    """Seconds since a stored UTC timestamp, calculated on read rather than stored."""
    return max(0, int((datetime.fromisoformat(home.now()) - datetime.fromisoformat(at)).total_seconds()))


@dataclass(frozen=True)
class PastWork(Record):
    """A completed ticket's reference and age; reading it by work_id retrieves its log, MAP-051."""
    work_id: str
    done: str

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), 'age_seconds': _age(self.done)}


@dataclass(frozen=True)
class WorkRecord(Record):
    """The condition of one object, apart from the map, STORE-042: an element with its address, or a join with its
    two ends, a subtype join with its parent's receiver and the element it holds, when the object is current; open
    until `done` is set, and then kept with its resolution."""
    work_id: str
    kind: str
    id: str
    address: str | None
    receiver_address: str | None
    provider_address: str | None
    condition: str
    note: str | None
    task: str | None
    held: bool
    reviewed: bool
    created: str
    done: str | None
    resolution: str | None
    notices: tuple[Notice, ...] = ()
    steps: int | None = None  # the steps the agent plans, MAP-053
    steps_done: int = 0
    said: tuple[Step, ...] = ()  # what the agent said of each step it finished, in order
    taken: str | None = None  # when it was taken
    taken_by: str | None = None  # who took it
    position: int | None = None  # its place in its column
    links: tuple[WorkLink, ...] = ()  # the other nodes it links for reference

    @property
    def column(self) -> str:
        """Its column on the board: done, doing once taken, backlog while held, and to do otherwise."""
        return 'done' if self.done else 'doing' if self.taken else 'backlog' if self.held else 'todo'

    @property
    def age_seconds(self) -> int | None:
        """Age since completion for past work, or since take for a task still held, MAP-049 and MAP-051."""
        at = self.done or self.taken
        return None if at is None else _age(at)

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), 'age_seconds': self.age_seconds}


@dataclass(frozen=True)
class Ticket(Record):
    """One ticket read by its id with what the map holds at its node and at each node it links, MAP-048: the where
    read of each, which carries its refs, its open work and its open questions. `at` is None when its node is not in
    context, and so is a linked node's read. `read_first` holds the items flagged read_first those reads show, read
    before the task, LAYER-021. Its plain data is the ticket's own fields with `read_first`, `at` and `linked`."""
    work: WorkRecord
    at: Where | None = None
    linked: tuple[Where | None, ...] = ()
    notices: tuple[Notice, ...] = ()
    read_first: tuple[Item, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = plain(self.work)
        data['notices'] = [*plain(self.notices), *data.get('notices', [])]
        data['read_first'] = plain(self.read_first)
        data['at'] = plain(self.at)
        data['linked'] = plain(self.linked)
        return data


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
