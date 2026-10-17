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
NODE_KINDS: tuple[NodeKind, ...] = ('element', 'join')
PLACE_KINDS: tuple[NodeKind, ...] = (*NODE_KINDS, 'type')
LAYER_KINDS: tuple[LayerKind, ...] = ('layer', 'intake', 'memory')
OPS: tuple[Op, ...] = ('add', 'change', 'remove')
ROLES = ('CQU', 'DE', 'SE', 'NE')  # the intake's classification of an element, MAP-017
HELD_ROLES = ('DE', 'SE', 'NE')  # the role of an element a join holds, in
# The state of a part, held on a work record apart from the map, MAP-046, a stage, where the part is
# on its way to existing, and one fault, a built part that does not do its job. Built is the normal state and draws
# nothing; a record with no condition is a plain task. The intake and the person set it; agents at work do not.
STAGES = ('unbuilt', 'under-construction', 'built')
FAULTS = ('broken', 'trouble')  # trouble is what the intake records where a part does not do its job
# A ticket's kind, what sort of work it is, kept apart from the part's state; none is a plain task.
KINDS = ('broken', 'flawed', 'enhancement')
FINDINGS = ('missing',)  # intended functionality that is absent, kept apart from the stage unbuilt
CHECKS = ('ok',)  # what the intake found when it read a part's source and it does its job
CONDITIONS = STAGES + FAULTS + FINDINGS + CHECKS
WORK_MARKERS = FAULTS + FINDINGS  # a marker that is work with no task: what the agent starter starts an agent on
DRAWN_STAGES = ('unbuilt', 'under-construction')  # a stage with no task is the part's state, drawn on its node
MESSAGES = ('question', 'message')  # what waits for the person at a node, MAP-050; never a condition
COLUMNS = ('backlog', 'todo', 'doing', 'done')  # the board's columns, MAP-048

T = TypeVar('T')


def is_work(condition: str | None, task: str | None) -> bool:
    """A record is work, a card on the board, when it has a task or a trouble, broken or missing marker, MAP-046."""
    return bool((task or '').strip()) or condition in WORK_MARKERS


def shown_open(condition: str | None, task: str | None) -> bool:
    """An open record is shown somewhere: as work on the board, or as a stage with no task, drawn on its node.
    Any other, an ok, a built or a note alone, is shown nowhere, so the store refuses it."""
    return is_work(condition, task) or condition in DRAWN_STAGES


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
    """A place an item can attach: an element or a join, named by address or identity id.

    `type:<address>` names a bare type address; a write there attaches to an element at that address, made by the
    writing layer when the project has none, with a notice, STORE-008.
    """
    kind: NodeKind
    id: str

    def __post_init__(self) -> None:
        if self.kind not in PLACE_KINDS:
            raise StoreError(f'{self.kind!r} is not a node kind: use element, join or type.', 'metaform help map node')

    @classmethod
    def of(cls, kind: str, ident: str) -> Node:
        """A node whose kind was read as text, such as from a row, checked before it is typed."""
        if kind not in PLACE_KINDS:
            raise StoreError(f'{kind!r} is not a node kind: use element, join or type.', 'metaform help map node')
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
    through name_length, MAP-012; `name` is the canonical name the project uses for it, a name goes
    anywhere there is a namespace and name length."""
    id: str
    address: str
    layer_id: str
    layer: str
    reading: str = ''
    short_name: str = ''
    name_length: int | None = None
    role: str | None = None
    existing: bool = False
    differs: bool = False
    state: str | None = None
    orphaned: bool = False
    open_work: tuple[str, ...] = ()
    notices: tuple[Notice, ...] = ()
    name: str | None = None  # the canonical name the project uses for it
    within: str | None = None  # the address of the element that holds it, when the structure says so
    note: str | None = None  # what the recorder noted about it, kept on the element itself


@dataclass(frozen=True)
class Held(Record):
    """An element a join holds, placed inside the join, D115: its address, name_length, name and role,
    with its short name, MAP-012. Every element a join holds provides for the join's purpose."""
    element_id: str
    address: str | None
    short_name: str = ''
    name_length: int | None = None
    name: str | None = None
    role: str | None = None


@dataclass(frozen=True)
class Join(Record):
    """A join: its type, purpose, the ef and the ifd, held by its receiver, holding the
    elements that serve its purpose. A promoted join also records its ordinary element by address, MAP-054."""
    id: str
    layer_id: str
    layer: str
    type: str
    receiver: str
    receiver_address: str | None
    purpose: str | None
    ef: str | None
    ifd: str | None = None  # IFD, Information Flow Direction: sends, receives or both
    elements: tuple[Held, ...] = ()
    state: str | None = None
    orphaned: bool = False
    open_work: tuple[str, ...] = ()
    notices: tuple[Notice, ...] = ()
    element: str | None = None  # the associated element's address, MAP-054
    note: str | None = None  # what the recorder noted about it, kept on the join itself


@dataclass(frozen=True)
class Item(Record):
    id: str
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
    id: str
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
    id: str


@dataclass(frozen=True)
class Layer(Record):
    id: str
    base_id: str
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
    by: str | None = None  # who wrote it: a work and session, or the surface, LAYER-025


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


# The fields a small read leaves out, STORE-025: identity ids, and the ends a join names by id beside their addresses.
ID_FIELDS = frozenset({'id', 'element_id', 'layer_id', 'join_id', 'work_id', 'item_id', 'property_id', 'node_id',
                       'target', 'receiver', 'receiver_address', 'provider_address'})


def small(value: Any) -> Any:
    """Plain data without its ids and empty fields: None, empty text, empty lists and dicts, and false."""
    if isinstance(value, dict):
        kept: dict[str, Any] = {}
        for key, item in cast(dict[str, Any], value).items():
            if key in ID_FIELDS:
                continue
            item = item if key == 'link' else small(item)  # a link is a node, named by its kind and its id
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
    relies on it, every join that holds it, with the receiver and the other elements each holds; `receives`, what it
    relies on, every join it receives with the elements each holds; its open work records, STORE-042; what the layers in
    context hold at it, as `node` gives them, the sources layer's refs among them; and the properties that apply at its
    address and those visible there, as `context` gives them, LAYER-005. Kind `join` is the read of a join, which a
    ticket on a join gets, MAP-048. `to_dict()` leaves ids and empty fields out unless `full`, all but the element's id,
    which `map history` takes, each ticket's work id, which an agent needs to take it, and each open message's message id, which an agent needs to answer it."""
    kind: str
    element: Element | None = None
    join: Join | None = None
    provides: tuple[Join, ...] = ()
    receives: tuple[Join, ...] = ()
    work: tuple[WorkRecord, ...] = ()
    layers: tuple[LayerGroup, ...] = ()
    full: bool = False
    applying: tuple[Property, ...] = ()
    visible: tuple[Property, ...] = ()
    messages: tuple[Message, ...] = ()  # the open questions and unread messages at it, MAP-050
    past_work: tuple[PastWork, ...] = ()  # references only; the log is read by work id, MAP-051
    join_layers: tuple[tuple[str, tuple[LayerGroup, ...]], ...] = ()  # what the layers hold at each join, by join id

    def to_dict(self) -> dict[str, Any]:
        if self.full:
            return {'kind': self.kind, 'element': plain(self.element),
                    **({'join': plain(self.join)} if self.kind == 'join' else {}),
                    'provides': plain(self.provides), 'receives': plain(self.receives), 'work': plain(self.work),
                    'layers': plain(self.layers),
                    'properties': {'applying': plain(self.applying), 'visible': plain(self.visible)},
                    'messages': plain(self.messages), 'past_work': plain(self.past_work),
                    'join_layers': {join_id: plain(groups) for join_id, groups in self.join_layers}}
        data: dict[str, Any] = {'kind': self.kind}
        if self.element is not None:
            data['element'] = {'id': self.element.id, **small(plain(self.element))}
        if self.kind == 'join' and self.join is not None:
            data['join'] = self._join(plain(self.join), True)
        held = dict(self.join_layers)
        def with_layers(join: Join, shown: dict[str, Any]) -> dict[str, Any]:
            return {**shown, 'layers': small(plain(held[join.id]))} if join.id in held else shown
        if self.provides:
            data['provides'] = [with_layers(join, self._join(plain(join), True)) for join in self.provides]
        if self.receives:
            data['receives'] = [with_layers(join, self._join(plain(join), False)) for join in self.receives]
        if self.work:
            data['work'] = [{'id': record.id, **small({'condition': record.condition, 'note': record.note,
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
            data['messages'] = [{'id': one.id, **small({'kind': one.kind, 'text': one.text,
                                                                       'suggestions': list(one.suggestions),
                                                                       'by': one.by})} for one in self.messages]
        return data

    @staticmethod
    def _join(data: Any, receiver: bool) -> dict[str, Any]:
        """A join with its receiver by address when asked for, and the elements it holds by address."""
        fields = cast(dict[str, Any], data)
        named = {'receiver': fields.get('receiver_address')} if receiver else {}
        return {**named, **small(fields)}


@dataclass(frozen=True)
class Recording(Record):
    """An intake building for a project: the base it goes into and its building layer, BASE-039. `recording` when an
    agent records it now, its process alive; else it was left unfinished. `parts` counts its elements, and `last` is
    when it last recorded anything."""
    base_id: str
    base: str
    active: bool
    layer: Layer
    recording: bool = False
    parts: int = 0
    last: str | None = None


@dataclass(frozen=True)
class GraphElement(Record):
    """An element in context, with the address of its nearest parent element in context, if any."""
    element: Element
    parent: str | None


@dataclass(frozen=True)
class GraphPage(Record):
    """A page of the map in address order, VIEW-010: its elements, and the joins they receive."""
    elements: tuple[GraphElement, ...]
    joins: tuple[Join, ...]
    next: str | None = None


@dataclass(frozen=True)
class Citation(Record):
    kind: str
    object_id: str
    address: str | None
    layer: str


@dataclass(frozen=True)
class SourceRef(Record):
    """One ref of the sources layer, a record of its own, STORE-012 and MAP-021: `id` lasts across its versions, `name`
    is its ref_id, and `ref` is how it is named, `{ref_id}@{address}:{join}`, the join left off on the element itself.
    `linked` is the place the latest link named, `by` and `at` who linked it and when, `reason` why."""
    id: str
    name: str
    ref: str
    key: str
    value: str
    details: tuple[Ref, ...]
    node: Node
    address: str | None
    join: str | None
    linked: str | None = None
    by: str | None = None
    at: str | None = None
    reason: str | None = None
    removed: bool = False
    notices: tuple[Notice, ...] = ()


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
    id: str
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
    id: str
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
    """A completed ticket's reference and age; reading it by its id retrieves its log, MAP-051."""
    work_id: str
    done: str

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), 'age_seconds': _age(self.done)}


@dataclass(frozen=True)
class WorkRecord(Record):
    """The condition of one object, apart from the map, STORE-042: an element with its address, or a join with its
    two ends, its receiver and an element it holds, when the object is current; open
    until `done` is set, and then kept with its resolution."""
    id: str
    node_kind: str
    node_id: str
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
    kind: str = ''  # a ticket's kind: broken, flawed, enhancement, or empty for a plain task
    # How it ended, a terminal state of `status.py`: completed, cancelled or failed; None while it is open. A record
    # done before the state was kept reads as completed.
    outcome: str | None = None

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
        return {**super().to_dict(), 'age_seconds': self.age_seconds, 'is_work': is_work(self.condition, self.task)}


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
