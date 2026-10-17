"""The base in memory: one process's projection of a base's op log, STORE-046.

The store file holds an ordered log of ops, append only, and every process that opens the base holds the whole
base as a projection of that log: a networkx graph of its elements, joins, items and properties, with the
indexes the reads answer from, and the layers, selections and types beside it. A layer is a view by the
`layer_id` attribute. Reads never touch SQLite for structure; a process catches up by applying the ops past the
last sequence it applied. The projection is a deterministic function of the ordered ops, so two processes at one
sequence hold identical graphs, and a damaged projection is rebuilt by replay.

An op is one row: `seq`, `session_id`, `op` (add, change or remove), `kind`, `id`, `layer_id` and `data`, JSON. The
kinds are `layer`, `element`, `join`, `item`, `property`, `selection` and `type`. An object op's data carries its
`mode`: `add` writes the object's first version; `version` writes a refinement, a further version kept beside the
earlier ones, LAYER-025; `place` changes or removes the version the object was added with, in place, as a
knowledge layer is edited, STORE-032. Every version an object was given is kept in order, and its current
version is its newest unless that one removed it, STORE-034.
"""
from __future__ import annotations

import copy
import json
import threading
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from .ids import prefixes

if TYPE_CHECKING:
    import networkx as nx

OBJECT_KINDS = ('element', 'join', 'property', 'item')
ORDER = OBJECT_KINDS


@dataclass
class Version:
    """One stored version of an object: what the row of a table held before STORE-046."""
    seq: int
    layer_id: str
    op: str
    reason: str | None
    evidence: str | None
    fields: dict[str, Any]
    refs: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])
    by: str | None = None  # who wrote the version: a work and session, or the surface; kept on base growth, LAYER-025

    def __getitem__(self, key: str) -> Any:
        """Read as a row was: `row['row']`, `row['layer_id']`, `row['op']` and the object's own fields."""
        if key == 'row':
            return self.seq
        if key in ('layer_id', 'op', 'reason', 'evidence'):
            return getattr(self, key)
        return self.fields.get(key)

    def keys(self) -> list[str]:
        return ['row', 'layer_id', 'op', 'reason', 'evidence', *self.fields]


@dataclass
class LayerRec:
    id: str
    base_id: str
    name: str
    module: str
    variable: str
    mutable: bool
    hideable: bool
    result_id: str | None
    kind: str
    created: str
    ready: str | None
    seq: int = 0
    fields: list[str] = field(default_factory=list[str])
    tags: list[str] = field(default_factory=list[str])
    sources: list[str] = field(default_factory=list[str])
    hidden: bool = False
    provenance: dict[str, Any] | None = None
    reexamine: list[list[str]] = field(default_factory=list[list[str]])  # [changed_in, thing_id] pairs

    @property
    def layer_id(self) -> str:
        return self.id

    @property
    def finished(self) -> bool:
        return self.ready is not None

    def to_data(self) -> dict[str, Any]:
        return {'base_id': self.base_id, 'name': self.name, 'module': self.module, 'variable': self.variable,
                'mutable': self.mutable, 'hideable': self.hideable, 'result_id': self.result_id, 'kind': self.kind,
                'created': self.created, 'ready': self.ready, 'fields': list(self.fields), 'tags': list(self.tags),
                'sources': list(self.sources), 'hidden': self.hidden, 'provenance': self.provenance,
                'reexamine': [list(pair) for pair in self.reexamine]}


@dataclass(frozen=True)
class Op:
    seq: int
    session_id: str
    op: str
    kind: str
    id: str
    layer_id: str
    data: dict[str, Any]
    at: str | None = None  # when it was written; an op carried in from elsewhere keeps its own time


class Projection:
    """One base, whole, in memory."""

    def __init__(self) -> None:
        self.seq = 0
        self.last: tuple[int, str, str] | None = None  # the last op applied: seq, session_id, id
        self.lock = threading.RLock()
        self.layers: dict[str, LayerRec] = {}
        self.kinds: dict[str, str] = {}  # the objects registry: every id and its kind
        self.versions: dict[str, list[Version]] = {}
        self.by_seq: dict[int, tuple[str, Version]] = {}  # every version by the sequence that wrote it
        self.address_last: dict[str, str] = {}  # the element each address last held, STORE-009
        self.types: dict[str, str | None] = {}
        self.selections: set[tuple[str, str, str]] = set()  # address, layer_id, kind
        self._dirty = True
        self._current: dict[str, Version] = {}
        self._by_address: dict[str, str] = {}
        self._joins_by_receiver: dict[str, list[str]] = {}
        self._joins_holding: dict[str, list[str]] = {}
        self._items_by_target: dict[tuple[str, str], list[str]] = {}
        self._items_by_link: dict[tuple[str, str], list[str]] = {}
        self._props_by_element: dict[str, list[str]] = {}
        self._join_edges: dict[str, list[tuple[str, str, str]]] = {}
        self._graph: nx.MultiDiGraph[str] = _empty_graph()

    # ------------------------------------------------------------------ applying ops

    def apply(self, op: Op) -> None:
        """Apply one op, in sequence. Deterministic: the same ops in the same order give the same projection."""
        if op.kind == 'layer':
            self._apply_layer(op)
        elif op.kind == 'selection':
            key = (op.data['address'], op.data['layer_id'], op.data['kind'])
            if op.op == 'remove':
                self.selections.discard(key)
            else:
                self.selections.add(key)
                self.add_type(op.data['address'])
        elif op.kind == 'type':
            self.add_type(op.data['address'])
        elif op.kind in OBJECT_KINDS:
            self._apply_object(op)
            self._refresh(op.id)
        self.seq = op.seq
        self.last = (op.seq, op.session_id, op.id)

    def add_type(self, address: str) -> None:
        parent = None
        for prefix in prefixes(address):
            self.types.setdefault(prefix, parent)
            parent = prefix

    def _apply_layer(self, op: Op) -> None:
        if op.op == 'remove':
            self.layers.pop(op.id, None)
            for other in self.layers.values():
                other.sources = [source for source in other.sources if source != op.id]
                other.reexamine = [pair for pair in other.reexamine if pair[0] != op.id]
            self.selections = {key for key in self.selections if key[1] != op.id}
            return
        data = op.data
        if op.op == 'add':
            self.layers[op.id] = LayerRec(op.id, data['base_id'], data['name'], data['module'], data['variable'],
                                          bool(data['mutable']), bool(data['hideable']), data.get('result_id'),
                                          data['kind'], data['created'], data.get('ready'), op.seq,
                                          list(data.get('fields', ())), list(data.get('tags', ())),
                                          list(data.get('sources', ())), bool(data.get('hidden', False)),
                                          data.get('provenance'),
                                          [list(pair) for pair in data.get('reexamine', ())])
            return
        found = self.layers.get(op.id)
        if found is None:
            return
        for key, value in data.items():
            if key == 'reexamine':
                found.reexamine = [list(pair) for pair in value]
            elif key in ('fields', 'tags', 'sources'):
                setattr(found, key, list(value))
            elif key in ('mutable', 'hideable', 'hidden'):
                setattr(found, key, bool(value))
            elif key in ('name', 'module', 'variable', 'result_id', 'kind', 'created', 'ready', 'provenance',
                         'base_id'):
                setattr(found, key, value)

    def _apply_object(self, op: Op) -> None:
        data = dict(op.data)
        mode = data.pop('mode', 'add')
        reason = data.pop('reason', None)
        evidence = data.pop('evidence', None)
        by = data.pop('by', None)
        refs = [(str(pair[0]), str(pair[1])) for pair in data.pop('refs', ())]
        self.kinds.setdefault(op.id, op.kind)
        held = self.versions.setdefault(op.id, [])
        if mode == 'place':
            added = [version for version in held if version.op == 'add']
            if not added:
                return
            own = added[-1]
            if not self._dirty and self._current.get(op.id) is own:
                self._lift(op.id, own)  # the version changes in place: its index entries go before its fields do
            if op.op == 'remove':
                held.remove(own)
                self.by_seq.pop(own.seq, None)
                return
            if 'layer_id' in data:
                own.layer_id = str(data.pop('layer_id'))
            if 'refs' in op.data:
                own.refs = refs
            own.fields.update(data)
            return
        if op.kind == 'element' and op.op == 'add':
            address = str(data.get('address'))
            self.address_last[address] = op.id
            self.add_type(address)
        version = Version(op.seq, op.layer_id, op.op, reason, evidence, data, refs, by)
        held.append(version)
        self.by_seq[op.seq] = (op.id, version)

    def version_at(self, seq: int) -> tuple[str, Version] | None:
        """The object and the version the op at a sequence wrote, STORE-005."""
        return self.by_seq.get(seq)

    # ------------------------------------------------------------------ the indexes

    def _index(self) -> None:
        """The indexes and the graph, kept as each op is applied; rebuilt whole only after a snapshot is loaded."""
        if not self._dirty:
            return
        self._current = {}
        self._by_address = {}
        self._joins_by_receiver = {}
        self._joins_holding = {}
        self._items_by_target = {}
        self._items_by_link = {}
        self._props_by_element = {}
        self._join_edges = {}
        self._graph = _empty_graph()
        self._dirty = False
        for ident, held in self.versions.items():
            if held and held[-1].op != 'remove':
                self._place(ident, held[-1])

    def _refresh(self, ident: str) -> None:
        """After an op on an object: the object's current version replaces the one indexed before it."""
        if self._dirty:
            return  # rebuilt whole at the next read
        before = self._current.get(ident)
        if before is not None:
            self._lift(ident, before)
        held = self.versions.get(ident, ())
        if held and held[-1].op != 'remove':
            self._place(ident, held[-1])

    def _lift(self, ident: str, version: Version) -> None:
        kind = self.kinds[ident]
        fields = version.fields
        graph = self._graph
        self._current.pop(ident, None)
        if kind == 'element':
            address = str(fields['address'])
            if self._by_address.get(address) == ident:
                del self._by_address[address]
            if ident in graph:
                if graph.degree(ident):
                    graph.nodes[ident].clear()
                    graph.nodes[ident].update(kind='element', current=False)
                else:
                    graph.remove_node(ident)
        elif kind == 'join':
            receiver = str(fields.get('receiver'))
            _drop(self._joins_by_receiver, receiver, ident)
            for element_id in fields.get('held', ()):
                _drop(self._joins_holding, str(element_id), ident)
            for u, v, key in self._join_edges.pop(ident, []):
                if graph.has_edge(u, v, key):
                    graph.remove_edge(u, v, key)
            if ident in graph:
                graph.remove_node(ident)
        elif kind == 'item':
            target = (str(fields.get('target_kind')), str(fields.get('target_id')))
            _drop(self._items_by_target, target, ident)
            if fields.get('link_kind'):
                _drop(self._items_by_link, (str(fields['link_kind']), str(fields['link_id'])), ident)
            if ident in graph:
                graph.remove_node(ident)
        elif kind == 'property':
            _drop(self._props_by_element, str(fields.get('element_id')), ident)
            if ident in graph:
                graph.remove_node(ident)

    def _place(self, ident: str, version: Version) -> None:
        kind = self.kinds[ident]
        fields = version.fields
        graph = self._graph
        self._current[ident] = version
        if kind == 'element':
            self._by_address[str(fields['address'])] = ident
            graph.add_node(ident, kind='element', current=True, layer_id=version.layer_id, **_plain(fields))
        elif kind == 'join':
            receiver = str(fields.get('receiver'))
            self._joins_by_receiver.setdefault(receiver, []).append(ident)
            for element_id in fields.get('held', ()):
                self._joins_holding.setdefault(str(element_id), []).append(ident)
            graph.add_node(ident, kind='join', layer_id=version.layer_id,
                           **_plain({key: value for key, value in fields.items() if key != 'held'}))
            edges: list[tuple[str, str, str]] = [(receiver, ident, f'receives:{ident}')]
            graph.add_edge(receiver, ident, key=f'receives:{ident}', kind='receives', layer_id=version.layer_id)
            for position, element_id in enumerate(fields.get('held', ())):
                graph.add_edge(ident, str(element_id), key=f'holds:{ident}:{position}', kind='holds',
                               position=position, layer_id=version.layer_id)
                graph.add_edge(receiver, str(element_id), key=ident, kind='join', id=ident, position=position,
                               layer_id=version.layer_id, purpose=fields.get('purpose'), ef=fields.get('ef'),
                               ifd=fields.get('ifd'), type=fields.get('type'))
                edges += [(ident, str(element_id), f'holds:{ident}:{position}'), (receiver, str(element_id), ident)]
            self._join_edges[ident] = edges
        elif kind == 'item':
            target = (str(fields.get('target_kind')), str(fields.get('target_id')))
            self._items_by_target.setdefault(target, []).append(ident)
            if fields.get('link_kind'):
                self._items_by_link.setdefault((str(fields['link_kind']), str(fields['link_id'])), []).append(ident)
            graph.add_node(ident, kind='item', layer_id=version.layer_id, **_plain(fields))
            graph.add_edge(target[1], ident, key=f'attached:{ident}', kind='attached', layer_id=version.layer_id)
        elif kind == 'property':
            element_id = str(fields.get('element_id'))
            self._props_by_element.setdefault(element_id, []).append(ident)
            graph.add_node(ident, kind='property', layer_id=version.layer_id, **_plain(fields))
            graph.add_edge(element_id, ident, key=f'property:{ident}', kind='property', layer_id=version.layer_id)

    def _by_seq_order(self, ids: list[str]) -> list[str]:
        return sorted(ids, key=lambda ident: self._current[ident].seq)

    @property
    def graph(self) -> nx.MultiDiGraph[str]:
        self._index()
        return self._graph

    def current(self, ident: str) -> Version | None:
        self._index()
        return self._current.get(ident)

    def is_current(self, ident: str) -> bool:
        self._index()
        return ident in self._current

    def element_at(self, address: str) -> str | None:
        self._index()
        return self._by_address.get(address)

    def address_of(self, element_id: str) -> str | None:
        found = self.current(element_id)
        return None if found is None or self.kinds.get(element_id) != 'element' else str(found.fields['address'])

    def joins_received(self, element_id: str) -> list[str]:
        self._index()
        return sorted(self._joins_by_receiver.get(element_id, ()))

    def joins_holding(self, element_id: str) -> list[str]:
        self._index()
        return sorted(set(self._joins_holding.get(element_id, ())))

    def items_at(self, kind: str, ident: str) -> list[str]:
        self._index()
        return self._by_seq_order(list(self._items_by_target.get((kind, ident), ())))

    def items_linking(self, kind: str, ident: str) -> list[str]:
        self._index()
        return self._by_seq_order(list(self._items_by_link.get((kind, ident), ())))

    def properties_of(self, element_id: str) -> list[str]:
        self._index()
        return self._by_seq_order(list(self._props_by_element.get(element_id, ())))

    def currents(self, kind: str) -> Iterator[tuple[str, Version]]:
        """Every current object of a kind, in the order it was written."""
        self._index()
        for ident, version in sorted(self._current.items(), key=lambda pair: pair[1].seq):
            if self.kinds[ident] == kind:
                yield ident, version

    def addresses(self) -> list[str]:
        """Every current element's address, in order."""
        self._index()
        return sorted(self._by_address)

    def layer_by_name(self, name: str) -> LayerRec | None:
        return next((layer for layer in self.layers.values() if layer.name == name), None)

    def cypher(self, query: str, graph: Any = None) -> Any:
        """A Cypher query over the graph, or over a view of it, through grandcypher."""
        from grandcypher import GrandCypher  # type: ignore[import-untyped]  loaded for the query only
        return cast(Any, GrandCypher(self.graph if graph is None else graph)).run(query)

    # ------------------------------------------------------------------ snapshots

    def snapshot(self) -> dict[str, Any]:
        """The projection's own state as JSON data: what replaying the log to this sequence builds."""
        return {'seq': self.seq, 'last': list(self.last) if self.last else None,
                'layers': {ident: layer.to_data() | {'seq': layer.seq} for ident, layer in self.layers.items()},
                'kinds': dict(self.kinds),
                'versions': {ident: [{'seq': v.seq, 'layer_id': v.layer_id, 'op': v.op, 'reason': v.reason,
                                      'evidence': v.evidence, 'fields': v.fields, 'refs': [list(r) for r in v.refs],
                                      'by': v.by}
                                     for v in held] for ident, held in self.versions.items()},
                'address_last': dict(self.address_last), 'types': dict(self.types),
                'selections': [list(key) for key in sorted(self.selections)]}

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> Projection:
        made = cls()
        made.seq = int(data['seq'])
        made.last = tuple(data['last']) if data.get('last') else None  # type: ignore[assignment]
        for ident, layer in data['layers'].items():
            made.layers[ident] = LayerRec(ident, layer['base_id'], layer['name'], layer['module'], layer['variable'],
                                          bool(layer['mutable']), bool(layer['hideable']), layer.get('result_id'),
                                          layer['kind'], layer['created'], layer.get('ready'), int(layer.get('seq', 0)),
                                          list(layer.get('fields', ())), list(layer.get('tags', ())),
                                          list(layer.get('sources', ())), bool(layer.get('hidden', False)),
                                          layer.get('provenance'), [list(p) for p in layer.get('reexamine', ())])
        made.kinds = dict(data['kinds'])
        made.versions = {ident: [Version(int(v['seq']), v['layer_id'], v['op'], v.get('reason'), v.get('evidence'),
                                         dict(v['fields']), [(str(r[0]), str(r[1])) for r in v.get('refs', ())],
                                         v.get('by'))
                                 for v in held] for ident, held in data['versions'].items()}
        made.address_last = dict(data['address_last'])
        made.types = dict(data['types'])
        made.selections = {(key[0], key[1], key[2]) for key in data['selections']}
        made.by_seq = {version.seq: (ident, version) for ident, held in made.versions.items() for version in held}
        return made

    def copy(self) -> Projection:
        made = Projection()
        made.seq, made.last = self.seq, self.last
        made.layers = copy.deepcopy(self.layers)
        made.kinds = dict(self.kinds)
        made.versions = copy.deepcopy(self.versions)
        made.by_seq = {version.seq: (ident, version) for ident, held in made.versions.items() for version in held}
        made.address_last = dict(self.address_last)
        made.types = dict(self.types)
        made.selections = set(self.selections)
        return made


def _empty_graph() -> nx.MultiDiGraph[str]:
    """networkx is loaded when the first projection is built, never at import, so `metaform --version` and a
    wheel installed without its dependencies still start, BASE-026 and BASE-042."""
    import networkx
    return networkx.MultiDiGraph()


def _drop(index: dict[Any, list[str]], key: Any, ident: str) -> None:
    held = index.get(key)
    if held is not None and ident in held:
        held.remove(ident)
        if not held:
            del index[key]


def _plain(fields: dict[str, Any]) -> dict[str, Any]:
    """Node attributes: every field, with nested values as JSON text so the graph stays flat for Cypher."""
    return {key: (json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else value)
            for key, value in fields.items()}


def ops_from_rows(rows: Iterable[Any]) -> Iterator[Op]:
    for row in rows:
        yield Op(int(row['seq']), str(row['session_id']), str(row['op']), str(row['kind']), str(row['id']),
                 str(row['layer_id']), cast(dict[str, Any], json.loads(str(row['data']))))
