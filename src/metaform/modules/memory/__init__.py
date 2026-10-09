"""memory: a memory graph of its own, presented at each node of the map as the MCP reference memory server, BASE-040,
LAYER-012, LAYER-013, STORE-020 and VIEW-034.

The graph is the reference server's: entities with a name, an entityType and observations, and relations between
entities, kept in the order they were made. It is kept in this module's project-level tables, STORE-045, so a clear
of the project's metaforms keeps it. A memory entity is never an element of the map and never a namespace segment.

A memory is tied to a map node by a join of type memory: a row naming the entity and the node's namespace address, an
element's address, or a map join's receiver and provider addresses. A new intake that holds the same address reconnects
it, MAP-015; a memory join whose address the active map does not hold is orphaned, kept, and listed by `orphaned`.

The nine commands carry the reference's names, argument shapes and behavior. Given `node`, each acts on that node's
memories as the reference acts on its whole graph: the entities joined to the node and the relations between them.
Without `node` they act on the whole graph. At a node, memory shows while the layer named memory reaches the node's
address, so select, mask and the folder's --layers turn it off.

Each node also holds one note, of at most 2048 characters, which an agent and a person edit alike; it never expires.

What the memory layer held before this graph, observations, relations and the person's notes, is carried into the
graph and the notes once, by each command, and left where it was.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

from metaform.data import Column, Index, Item, Node, Store, StoreError, Table, Tables, TableTx
from metaform.module import Context, Module, Noun, Stop, Verb

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False

VARIABLE = 'What agents have noted at this node.'
LAYER = 'memory'
NOTE_LIMIT = 2048

# Version 2 keeps no time on entities, observations, relations or joins: an entity's and a relation's `seq` is its place
# in the order they were made. Rows from version 1 take seq 0 and keep the order of their key, before every later one.
TABLES = Tables(version=2, tables=(
    Table('entities', place='project', key=('name',),
          columns=(Column('name', required=True), Column('entity_type', required=True),
                   Column('seq', 'int', required=True, default=0)),
          indexes=(Index(('seq',)),)),
    Table('observations', place='project', key=('entity', 'content'),
          columns=(Column('entity', required=True), Column('content', required=True),
                   Column('seq', 'int', required=True)),
          indexes=(Index(('entity', 'seq')),)),
    Table('relations', place='project', key=('source', 'target', 'relation_type'),
          columns=(Column('source', required=True), Column('target', required=True),
                   Column('relation_type', required=True), Column('seq', 'int', required=True, default=0)),
          indexes=(Index(('target',)), Index(('seq',)))),
    Table('joins', place='project', key=('join_id',),
          columns=(Column('join_id', required=True), Column('entity', required=True),
                   Column('receiver', required=True), Column('provider', required=True, default='')),
          indexes=(Index(('entity', 'receiver', 'provider'), unique=True), Index(('receiver', 'provider')),
                   Index(('provider',)))),
    Table('notes', place='project', key=('receiver', 'provider'),
          columns=(Column('receiver', required=True), Column('provider', required=True, default=''),
                   Column('text', required=True), Column('by'), Column('at', required=True))),
    Table('carried', place='project', key=('item_id',),
          columns=(Column('item_id', required=True), Column('at', required=True))),
))

Row = dict[str, Any]
# The nouns that name a node by address, MAP-005, as refine names what it changes.
NAMING = ('receiver', 'provider', 'address')


def _now() -> str:
    return datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


# ------------------------------------------------------------------------------------------------ nodes and keys

@dataclass(frozen=True)
class Key:
    """A node's namespace address: an element's address, or a map join's receiver and provider addresses. `address`
    is where the node sits, for the layers that reach it."""
    receiver: str
    provider: str = ''

    @property
    def address(self) -> str:
        return self.receiver

    def said(self) -> dict[str, str]:
        return {'receiver': self.receiver, 'provider': self.provider} if self.provider else {'address': self.receiver}


def _join_key(store: Store, node: Node) -> Key | None:
    """A map join's two ends: its receiver and the first element it holds."""
    ends = store.join_ends(node.id)
    return None if ends is None else Key(*ends)


def _key_of(store: Store, node: Node) -> Key | None:
    if node.kind == 'element':
        found = store.element(node.id, raw=True)
        return Key(found.address) if found is not None and found.address else None
    if node.kind == 'join':
        return _join_key(store, node)
    return None


def _key(store: Store, text: str) -> Key:
    """The key of the node a command names, which must be a node of the active map."""
    try:
        node = Node.parse(text)
    except StoreError:
        raise Stop(f'{text!r} is not a node: name an element by address, or a purpose by receiver and '
                   'provider.', 'metaform help memory read_graph') from None
    if node.kind == 'type':
        raise Stop('Memory is kept at an element or a join, not at a bare type address.',
                   f'metaform memory read_graph node=element:{node.id}')
    if store.active_base() is None:
        raise Stop(f'{text} is not a node here: the project has no metaform.', 'metaform memory orphaned')
    key = _key_of(store, node)
    if key is None:
        raise Stop(f'{text} is not a node of the map here.', 'metaform map where')
    return key


class _Map:
    """Whether the active map holds an address key, read once per key."""

    def __init__(self, store: Store) -> None:
        self.store = store
        self.active = store.active_base() is not None
        self._held: dict[tuple[str, str], bool] = {}

    def holds(self, key: Key) -> bool:
        found = (key.receiver, key.provider)
        if found not in self._held:
            self._held[found] = self.active and self._holds(key)
        return self._held[found]

    def _holds(self, key: Key) -> bool:
        if self.store.element(key.receiver, raw=True) is None:
            return False
        if not key.provider:
            return True
        joins = self.store.joins(key.receiver, 'receiver', raw=True, limit=0).results
        return any(held.address == key.provider for join in joins for held in join.elements)


# ------------------------------------------------------------------------------------------------ the memory layer

def _memory(store: Store, *, create: bool) -> str | None:
    """The memory layer's name, found by its kind, LAYER-012; made on the first write when the project has a
    metaform, so a memory write never makes one."""
    found = store.layers(kind='memory', limit=0).results
    if found:
        return found[0].name
    if not create or store.active_base() is None:
        return None
    return store.layer(LAYER, 'memory', VARIABLE, kind='memory', mutable=True, hideable=True, ready=True).name


def _reaches(store: Store, address: str) -> bool:
    """Whether memory shows at an address: the memory layer reaches it, with select, mask, hiding and the toggled
    layers; with no memory layer, or no metaform, unless the toggled layers leave memory out."""
    layer = _memory(store, create=False) if store.active_base() is not None else None
    if layer is None:
        return not store.toggled or LAYER in store.toggled
    return layer in store.effective_selection(address).layers


# ------------------------------------------------------------------------------------------------ the graph

@dataclass
class Graph:
    """The memory graph as read in one transaction: entities in the order they were made, each one's observations in
    the order they were added, and relations in the order they were made."""
    entities: dict[str, Row] = field(default_factory=dict[str, Row])
    observations: dict[str, list[Row]] = field(default_factory=dict[str, list[Row]])
    relations: list[Row] = field(default_factory=list[Row])

    @classmethod
    def read(cls, tx: TableTx) -> Graph:
        graph = cls()
        for row in tx.rows('entities', by=('seq',), limit=0).results:
            graph.entities[row['name']] = row
            graph.observations[row['name']] = []
        for row in tx.rows('observations', limit=0).results:
            graph.observations.setdefault(row['entity'], []).append(row)
        for rows in graph.observations.values():
            rows.sort(key=lambda row: row['seq'])
        graph.relations = list(tx.rows('relations', by=('seq',), limit=0).results)
        return graph

    def entity(self, name: str) -> dict[str, Any]:
        row = self.entities[name]
        return {'name': name, 'entityType': row['entity_type'],
                'observations': [one['content'] for one in self.observations.get(name, [])]}

    @staticmethod
    def relation(row: Row) -> dict[str, Any]:
        return {'from': row['source'], 'to': row['target'], 'relationType': row['relation_type']}

    def made(self, tx: TableTx, name: str, kind: str) -> None:
        """A new entity, after every entity the graph holds."""
        seq = max((row['seq'] for row in self.entities.values()), default=0) + 1
        self.entities[name] = tx.insert('entities', {'name': name, 'entity_type': kind, 'seq': seq})
        self.observations[name] = []

    def related(self, tx: TableTx, source: str, target: str, kind: str) -> None:
        """A new relation, after every relation the graph holds."""
        seq = max((row['seq'] for row in self.relations), default=0) + 1
        self.relations.append(tx.insert('relations', {'source': source, 'target': target, 'relation_type': kind,
                                                      'seq': seq}))


@dataclass
class View:
    """The graph an operation sees: the whole graph, or a node's memories and the relations between them."""
    graph: Graph
    names: list[str]

    @property
    def known(self) -> set[str]:
        return set(self.names)

    def relations(self) -> list[Row]:
        known = self.known
        return [row for row in self.graph.relations if row['source'] in known and row['target'] in known]

    def whole(self) -> dict[str, Any]:
        return {'entities': [self.graph.entity(name) for name in self.names],
                'relations': [Graph.relation(row) for row in self.relations()]}

    def around(self, chosen: list[str]) -> dict[str, Any]:
        """The chosen entities, and every relation with at least one end among them, as the reference returns."""
        picked = set(chosen)
        return {'entities': [self.graph.entity(name) for name in chosen],
                'relations': [Graph.relation(row) for row in self.relations()
                              if row['source'] in picked or row['target'] in picked]}


def _joined(tx: TableTx, key: Key) -> list[Row]:
    return list(tx.rows('joins', {'receiver': key.receiver, 'provider': key.provider}, limit=0).results)


def _view(tx: TableTx, key: Key | None) -> View:
    graph = Graph.read(tx)
    if key is None:
        return View(graph, list(graph.entities))
    joined = {row['entity'] for row in _joined(tx, key)}
    return View(graph, [name for name in graph.entities if name in joined])


def _join(tx: TableTx, entity: str, key: Key) -> None:
    held = tx.rows('joins', {'entity': entity, 'receiver': key.receiver, 'provider': key.provider}).results
    if not held:
        tx.insert('joins', {'join_id': uuid.uuid4().hex, 'entity': entity, 'receiver': key.receiver,
                            'provider': key.provider})


def _observe(tx: TableTx, graph: Graph, entity: str, contents: list[str]) -> list[str]:
    """Add each content the entity does not hold yet, in order; returns those added."""
    held = graph.observations.setdefault(entity, [])
    added: list[str] = []
    for content in contents:
        if any(one['content'] == content for one in held):
            continue
        row = tx.insert('observations', {'entity': entity, 'content': content,
                                         'seq': (held[-1]['seq'] + 1) if held else 1})
        held.append(row)
        added.append(content)
    return added


def _forget(tx: TableTx, graph: Graph, name: str) -> None:
    """Delete an entity with its observations, every relation touching it and every join of it."""
    tx.delete('observations', {'entity': name})
    tx.delete('relations', {'source': name})
    tx.delete('relations', {'target': name})
    tx.delete('joins', {'entity': name})
    tx.delete('entities', {'name': name})
    graph.entities.pop(name, None)
    graph.observations.pop(name, None)
    graph.relations = [row for row in graph.relations if name not in (row['source'], row['target'])]


# ------------------------------------------------------------------------------------------------ carrying over

def _text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _entity_name(key: Key) -> str:
    return f'{key.receiver} -> {key.provider}' if key.provider else key.receiver


def _carry(store: Store) -> None:
    """Carry what the memory layer held before this graph into it once: an observation becomes an observation of an
    entity named by its node's address and joined to it, a relation a relation between two such entities, and a
    person's note the node's note. Each item is carried once and left where it was. An item whose node the active map
    does not hold waits until it does."""
    if store.active_base() is None:
        return
    layer = _memory(store, create=False)
    if layer is None:
        return
    items = [item for item in store.layer_items(layer, limit=0).results if isinstance(item, Item)]
    if not items:
        return
    with store.tables(write=False) as tx:
        carried = {row['item_id'] for row in tx.rows('carried', limit=0).results}
    pending = [item for item in items if item.id not in carried]
    if not pending:
        return
    keyed: list[tuple[Item, Key, Key | None]] = []
    for item in pending:
        key = _key_of(store, item.target)
        linked = _key_of(store, item.link) if item.link is not None else None
        if key is None or (item.link is not None and linked is None):
            continue
        keyed.append((item, key, linked))
    if not keyed:
        return
    with store.tables() as tx:
        graph = Graph.read(tx)

        def entity_at(key: Key, kind: str) -> str:
            name = _entity_name(key)
            if name not in graph.entities:
                graph.made(tx, name, kind)
            _join(tx, name, key)
            return name

        for item, key, linked in keyed:
            source = entity_at(key, item.target.kind)
            if item.link is not None and linked is not None:
                target = entity_at(linked, item.link.kind)
                kind = _text(item.value)
                if not any(row['source'] == source and row['target'] == target and row['relation_type'] == kind
                           for row in graph.relations):
                    graph.related(tx, source, target, kind)
            elif (item.extra or {}).get('by') == 'user' and _noted(tx, key, _text(item.value)):
                pass
            else:
                _observe(tx, graph, source, [_text(item.value)])
            tx.insert('carried', {'item_id': item.id, 'at': _now()})


def _noted(tx: TableTx, key: Key, text: str) -> bool:
    """A person's note from the memory layer into the node's one note: the note itself when the node has none, or
    added after it on a line of its own while the whole fits; False when it does not fit, so it is kept as an
    observation instead and nothing is cut."""
    held = tx.get('notes', {'receiver': key.receiver, 'provider': key.provider})
    if held is None:
        if len(text) > NOTE_LIMIT:
            return False
        tx.insert('notes', {'receiver': key.receiver, 'provider': key.provider, 'text': text, 'by': 'user',
                            'at': _now()})
        return True
    if text in held['text'].split('\n'):
        return True
    joined = held['text'] + '\n' + text
    if len(joined) > NOTE_LIMIT:
        return False
    tx.update('notes', {'receiver': key.receiver, 'provider': key.provider}, {'text': joined, 'at': _now()})
    return True


# ------------------------------------------------------------------------------------------------ the nine commands

def _named(store: Store, nouns: dict[str, Any], notices: list[dict[str, str]]) -> Key | None:
    """The key of the node a command names by address, MAP-005: a join by its receiver and an element it holds, an
    element by its address; or the node noun as written. A node noun given beside them is
    named in a notice as not read."""
    if not any(name in nouns for name in NAMING):
        return _key(store, nouns['node']) if nouns.get('node') else None
    if 'node' in nouns:
        notices.append({'where': 'node', 'message': 'receiver, provider and address name the node; node was not read.'})
    if 'receiver' not in nouns and 'provider' not in nouns:
        return _key(store, f"element:{nouns['address']}")
    if store.active_base() is None:
        raise Stop('A purpose is not a node here: the project has no metaform.', 'metaform memory orphaned')
    found = _key_of(store, store.purpose(nouns.get('receiver'), nouns.get('provider'), nouns.get('address')))
    if found is None:
        raise Stop(f"The purpose of {nouns.get('receiver')} served by {nouns.get('provider')} is not a node of the "
                   'map here.', 'metaform map where')
    return found


def _held(store: Store, nouns: dict[str, Any], notices: list[dict[str, str]]) -> Key:
    """The key of the node note names, node first, with provider beside it, the purpose node holds
    as its receiver, and with address the element at that address the join holds, MAP-005."""
    if 'provider' not in nouns:
        if 'address' in nouns:
            notices.append({'where': 'address', 'message': 'address names an element a join holds only with provider; it was not read.'})
        return _key(store, nouns['node'])
    node = str(nouns['node'])
    receiver = node.partition(':')[2] if node.startswith('element:') else node
    found = _named(store, {'receiver': receiver, **{name: nouns[name] for name in ('provider', 'address')
                                                    if name in nouns}}, [])
    assert found is not None  # receiver and provider are given, so _named names a node or stops
    return found


def _scope(ctx: Context, notices: list[dict[str, str]], *, carry: bool = True) -> tuple[Store, Key | None]:
    """The store and the named node; a command that writes first carries what the memory layer held, and one that
    only reads writes nothing, VIEW-011."""
    store = ctx.require_store()
    if carry:
        _carry(store)
    return store, _named(store, ctx.nouns, notices)


class _Given:
    """A command's arguments read in the reference's shapes. A value that should be text and is another JSON value is
    kept as its JSON text and named in `notices`, BASE-044; only an argument that cannot be read stops the call."""

    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.notices: list[dict[str, str]] = []

    def text(self, value: Any, where: str) -> str:
        if isinstance(value, str):
            return value
        self.notices.append({'where': where, 'message': f'{where} is text; what was sent was kept as its JSON text.'})
        return json.dumps(value, ensure_ascii=False)

    def texts(self, value: Any, where: str) -> list[str]:
        if not isinstance(value, list):
            self.notices.append({'where': where, 'message': f'{where} is an array; what was sent was kept as its '
                                                            'one member.'})
            value = [value]
        return [self.text(one, where) for one in cast(list[Any], value)]

    def objects(self, name: str, fields: tuple[str, ...]) -> list[dict[str, Any]]:
        value = self.ctx.nouns.get(name)
        members = cast(list[Any], value) if isinstance(value, list) else [value]
        found: list[dict[str, Any]] = []
        for one in members:
            if not isinstance(one, dict) or any(field_ not in one for field_ in fields):
                raise Stop(f'Each member of {name} is an object with {", ".join(fields)}.',
                           'metaform help memory')
            found.append(cast(dict[str, Any], one))
        return found

    def said(self, result: dict[str, Any]) -> dict[str, Any]:
        if self.notices:
            result['notices'] = self.notices
        return result


def _not_found(name: str, nouns: dict[str, Any]) -> Stop:
    named = ''.join(f' {noun}={nouns[noun]}' for noun in ('node', *NAMING) if noun in nouns)
    return Stop(f'Entity with name {name} not found', f'metaform memory read_graph{named}')


def _layered(store: Store) -> None:
    """The memory layer, made on the first write so the orchestrator can turn memory off, LAYER-012."""
    with store.atomic():
        _memory(store, create=True)


def create_entities(ctx: Context) -> Any:
    given = _Given(ctx)
    store, key = _scope(ctx, given.notices)
    entities = [(given.text(one['name'], 'name'), given.text(one['entityType'], 'entityType'),
                 given.texts(one['observations'], 'observations'))
                for one in given.objects('entities', ('name', 'entityType', 'observations'))]
    made: list[dict[str, Any]] = []
    with store.tables() as tx:
        graph = Graph.read(tx)
        seen: set[str] = set()
        for name, kind, observations in entities:
            if name in graph.entities or name in seen:
                if key is not None and name in graph.entities:
                    _join(tx, name, key)
                continue
            seen.add(name)
            graph.made(tx, name, kind)
            _observe(tx, graph, name, observations)
            if key is not None:
                _join(tx, name, key)
            made.append({'name': name, 'entityType': kind, 'observations': observations})
    _layered(store)
    return given.said({'entities': made})


def _relations(given: _Given) -> list[tuple[str, str, str]]:
    return [(given.text(one['from'], 'from'), given.text(one['to'], 'to'),
             given.text(one['relationType'], 'relationType'))
            for one in given.objects('relations', ('from', 'to', 'relationType'))]


def create_relations(ctx: Context) -> Any:
    given = _Given(ctx)
    store, key = _scope(ctx, given.notices)
    relations = _relations(given)
    made: list[dict[str, Any]] = []
    with store.tables() as tx:
        view = _view(tx, key)
        known = view.known
        for source, target, _ in relations:
            for end in (source, target):
                if end not in known:
                    raise _not_found(end, ctx.nouns)
        held = {(row['source'], row['target'], row['relation_type']) for row in view.graph.relations}
        for triple in relations:
            if triple in held:
                continue
            held.add(triple)
            view.graph.related(tx, *triple)
            made.append({'from': triple[0], 'to': triple[1], 'relationType': triple[2]})
    _layered(store)
    return given.said({'relations': made})


def add_observations(ctx: Context) -> Any:
    given = _Given(ctx)
    store, key = _scope(ctx, given.notices)
    observations = [(given.text(one['entityName'], 'entityName'), given.texts(one['contents'], 'contents'))
                    for one in given.objects('observations', ('entityName', 'contents'))]
    results: list[dict[str, Any]] = []
    with store.tables() as tx:
        view = _view(tx, key)
        known = view.known
        for name, contents in observations:
            if name not in known:
                raise _not_found(name, ctx.nouns)
            results.append({'entityName': name, 'addedObservations': _observe(tx, view.graph, name, contents)})
    _layered(store)
    return given.said({'results': results})


def delete_entities(ctx: Context) -> Any:
    given = _Given(ctx)
    store, key = _scope(ctx, given.notices)
    names = given.texts(ctx.nouns.get('entityNames'), 'entityNames')
    with store.tables() as tx:
        view = _view(tx, key)
        known = view.known
        deleted = [name for name in names if name in known]
        not_found = [name for name in names if name not in known]
        for name in dict.fromkeys(deleted):
            _forget(tx, view.graph, name)
    message = ('Entities deleted successfully' if not not_found else
               f'Deleted {len(deleted)} of {len(names)} entities. Not found: {", ".join(not_found)}')
    return given.said({'success': True, 'message': message})


def delete_observations(ctx: Context) -> Any:
    given = _Given(ctx)
    store, key = _scope(ctx, given.notices)
    deletions = [(given.text(one['entityName'], 'entityName'), given.texts(one['observations'], 'observations'))
                 for one in given.objects('deletions', ('entityName', 'observations'))]
    deleted, requested, missing = 0, 0, list[str]()
    with store.tables() as tx:
        known = _view(tx, key).known
        for name, contents in deletions:
            requested += len(contents)
            if name not in known:
                missing.append(name)
                continue
            for content in dict.fromkeys(contents):
                deleted += tx.delete('observations', {'entity': name, 'content': content})
    message = ('Observations deleted successfully' if deleted == requested else
               f'Deleted {deleted} of {requested} observations.' +
               (f' Entities not found: {", ".join(missing)}' if missing else ''))
    return given.said({'success': True, 'message': message})


def delete_relations(ctx: Context) -> Any:
    given = _Given(ctx)
    store, key = _scope(ctx, given.notices)
    relations = _relations(given)
    deleted = 0
    with store.tables() as tx:
        known = _view(tx, key).known
        for source, target, kind in relations:
            if source in known and target in known:
                deleted += tx.delete('relations', {'source': source, 'target': target, 'relation_type': kind})
    message = ('Relations deleted successfully' if deleted == len(relations) else
               f'Deleted {deleted} of {len(relations)} relations. The rest matched nothing.')
    return given.said({'success': True, 'message': message})


def _shown(store: Store, tx: TableTx, view: View) -> View:
    """The whole graph as it shows with the layers in context: an entity joined to nodes shows where memory reaches
    one of their addresses, as at a node; one joined to none shows while memory reaches the root of the namespace."""
    reach: dict[str, bool] = {}

    def reaches(address: str) -> bool:
        if address not in reach:
            reach[address] = _reaches(store, address)
        return reach[address]

    at: dict[str, list[str]] = {}
    for row in tx.rows('joins', by=('receiver', 'provider'), limit=0).results:
        at.setdefault(row['entity'], []).append(row['receiver'])
    return View(view.graph, [name for name in view.names
                             if any(reaches(address) for address in at.get(name, ['']))])


def _read(ctx: Context, notices: list[dict[str, str]]) -> View | None:
    store, key = _scope(ctx, notices, carry=False)
    if key is not None and not _reaches(store, key.address):
        return None
    with store.tables(write=False) as tx:
        if key is not None:
            return _view(tx, key)
        return _shown(store, tx, _view(tx, None))


EMPTY: dict[str, list[Any]] = {'entities': [], 'relations': []}


def read_graph(ctx: Context) -> Any:
    given = _Given(ctx)
    view = _read(ctx, given.notices)
    return given.said(dict(EMPTY) if view is None else view.whole())


def search_nodes(ctx: Context) -> Any:
    given = _Given(ctx)
    wanted = given.text(ctx.nouns.get('query'), 'query').lower()
    view = _read(ctx, given.notices)
    if view is None:
        return given.said(dict(EMPTY))
    chosen = [name for name in view.names
              if wanted in name.lower() or wanted in view.graph.entities[name]['entity_type'].lower()
              or any(wanted in one['content'].lower() for one in view.graph.observations.get(name, []))]
    return given.said(view.around(chosen))


def open_nodes(ctx: Context) -> Any:
    given = _Given(ctx)
    names = given.texts(ctx.nouns.get('names'), 'names')
    view = _read(ctx, given.notices)
    if view is None:
        return given.said(dict(EMPTY))
    return given.said(view.around([name for name in view.names if name in names]))


# ------------------------------------------------------------------------------------------------ joins and notes

def _join_said(row: Row, held: bool) -> dict[str, Any]:
    return {'join_id': row['join_id'], 'entity': row['entity'],
            **Key(row['receiver'], row['provider']).said(), 'orphaned': not held}


def joins(ctx: Context) -> Any:
    """The joins of type memory, at a node or of an entity, or all of them, each with whether it is orphaned."""
    store = ctx.require_store()
    notices: list[dict[str, str]] = []
    key, entity = _named(store, ctx.nouns, notices), ctx.nouns.get('entity')
    with store.tables(write=False) as tx:
        if key is not None:
            found = _joined(tx, key)
        elif entity:
            found = list(tx.rows('joins', {'entity': entity}, limit=0).results)
        else:
            found = list(tx.rows('joins', by=('receiver', 'provider'), limit=0).results)
    if key is not None and entity:
        found = [row for row in found if row['entity'] == entity]
    mapped = _Map(store)
    said: dict[str, Any] = {'joins': [_join_said(row, mapped.holds(Key(row['receiver'], row['provider'])))
                                      for row in found]}
    if notices:
        said['notices'] = notices
    return said


def orphaned(ctx: Context) -> Any:
    """The memory joins whose address the active map does not hold, with what each was attached to, for the orphaned
    menu; they are kept, and a new intake that holds the address reconnects them."""
    store = ctx.require_store()
    with store.tables(write=False) as tx:
        found = list(tx.rows('joins', by=('receiver', 'provider'), limit=0).results)
    mapped = _Map(store)
    return {'joins': [_join_said(row, False) for row in found
                      if not mapped.holds(Key(row['receiver'], row['provider']))]}


def unjoin(ctx: Context) -> Any:
    """Take one memory join away by its id, an orphaned one included; the entity stays in the graph."""
    store = ctx.require_store()
    with store.tables() as tx:
        deleted = tx.delete('joins', {'join_id': ctx.nouns['id']})
    return {'deleted': deleted}


def rekey(ctx: Context) -> Any:
    """Transfer memory attachments and notes at an exact address, including either end of a map join. The old
    address may already be absent from the map; existing unique keys make a collision roll the whole transfer back."""
    store = ctx.require_store()
    old, new = ctx.nouns['old'], ctx.nouns['new']
    counts = {'joins': 0, 'notes': 0}
    if old != new:
        with store.tables() as tx:
            for table, key in (('joins', ('join_id',)), ('notes', ('receiver', 'provider'))):
                for row in tx.rows(table, limit=0).results:
                    changes = {end: new for end in ('receiver', 'provider') if row[end] == old}
                    if changes:
                        tx.update(table, {name: row[name] for name in key}, changes)
                        counts[table] += 1
    return {'old': old, 'new': new, **counts}


def graph(ctx: Context) -> Any:
    """The whole graph with every join, for a browser of it. Each join also says whether its entity shows at its node
    as a read of the node shows it: the join is not orphaned and memory reaches the node's address in the call's
    layers, VIEW-031."""
    store = ctx.require_store()
    with store.tables(write=False) as tx:
        whole = Graph.read(tx)
        rows = list(tx.rows('joins', by=('receiver', 'provider'), limit=0).results)
    mapped = _Map(store)
    reach: dict[str, bool] = {}

    def said(row: Row) -> dict[str, Any]:
        key = Key(row['receiver'], row['provider'])
        held = mapped.holds(key)
        if held and key.address not in reach:
            reach[key.address] = _reaches(store, key.address)
        return {**_join_said(row, held), 'shows': held and reach[key.address]}
    return {'entities': [{'name': name, 'entityType': row['entity_type'],
                          'observations': [{'content': one['content']} for one in whole.observations.get(name, [])]}
                         for name, row in whole.entities.items()],
            'relations': [Graph.relation(row) for row in whole.relations],
            'joins': [said(row) for row in rows]}


def _note_said(row: Row | None) -> dict[str, Any] | None:
    return None if row is None else {'text': row['text'], 'by': row['by'], 'at': row['at']}


def note(ctx: Context) -> Any:
    """The node's one note: read it, or, from the web page only, write it in place of what it held; empty text clears
    it. The note is the person's, not the agents'. An agent reads the note and never writes it."""
    store = ctx.require_store()
    notices: list[dict[str, str]] = []
    key = _held(store, ctx.nouns, notices)
    text = ctx.nouns.get('text')
    where = {'receiver': key.receiver, 'provider': key.provider}
    if text is not None and ctx.surface != 'web':
        raise Stop('The note is written only from the web page.', f'metaform memory note {ctx.nouns["node"]}')
    if text is None:
        with store.tables(write=False) as tx:
            return {**key.said(), 'note': _note_said(tx.get('notes', where)), **({'notices': notices} if notices else {})}
    _carry(store)
    if len(text) > NOTE_LIMIT:
        raise Stop(f'A note holds at most {NOTE_LIMIT} characters; this one has {len(text)}.',
                   f'metaform memory note {ctx.nouns["node"]} text=<at most {NOTE_LIMIT} characters>')
    with store.tables() as tx:
        if text == '':
            tx.delete('notes', where)
            return {**key.said(), 'note': None, **({'notices': notices} if notices else {})}
        changes = {'text': text, 'by': ctx.nouns.get('by'), 'at': _now()}
        row = tx.update('notes', where, changes) or tx.insert('notes', {**where, **changes})
    return {**key.said(), 'note': _note_said(row), **({'notices': notices} if notices else {})}


# ------------------------------------------------------------------------------------------------ the node read

def node_read(ctx: Context, node: Node) -> Any:
    """What memory adds to the read of a node, BASE-035: its note, and while memory shows at the node, the entities
    joined to it with the relations between them, and for an element, the memories on the joins it receives and
    provides."""
    store = ctx.store
    if store is None or store.active_base() is None:
        return None
    key = _key_of(store, node)
    if key is None:
        return None
    found: dict[str, Any] = {}
    shows = _reaches(store, key.address)
    with store.tables(write=False) as tx:
        held = _note_said(tx.get('notes', {'receiver': key.receiver, 'provider': key.provider}))
        if held is not None:
            found['note'] = held
        if not shows:
            return found or None
        view = _view(tx, key)
        if view.names:
            found.update(view.whole())
        if node.kind == 'element':
            around: dict[tuple[str, str], list[str]] = {}
            for row in [*tx.rows('joins', {'receiver': key.receiver}, by=('receiver', 'provider'), limit=0).results,
                        *tx.rows('joins', {'provider': key.receiver}, limit=0).results]:
                if row['provider'] and row['entity'] in view.graph.entities:
                    around.setdefault((row['receiver'], row['provider']), []).append(row['entity'])
            if around:
                found['joins'] = [{'receiver': receiver, 'provider': provider,
                                   'entities': [view.graph.entity(name) for name in names]}
                                  for (receiver, provider), names in around.items()]
    return found or None


# ------------------------------------------------------------------------------------------------ the declaration

NODE = ('The map element whose memories the command acts on, element:<address>. Without node, receiver, provider or '
        'address the command acts on the whole memory graph.')
RECEIVER = 'A purpose whose memories the command acts on: the address of the element that holds it, with provider.'
PROVIDER = 'A purpose whose memories the command acts on: the address of the element that serves it, with receiver.'
ADDRESS = 'An element, by address; with receiver and provider, the element at that address the join holds.'
NAMED = (Noun('receiver', RECEIVER, required=False), Noun('provider', PROVIDER, required=False),
         Noun('address', ADDRESS, required=False))
ENTITY = {'type': 'object', 'properties': {
    'name': {'type': 'string', 'description': 'The name of the entity'},
    'entityType': {'type': 'string', 'description': 'The type of the entity'},
    'observations': {'type': 'array', 'items': {'type': 'string'},
                     'description': 'An array of observation contents associated with the entity'}},
    'required': ['name', 'entityType', 'observations']}
RELATION = {'type': 'object', 'properties': {
    'from': {'type': 'string', 'description': 'The name of the entity where the relation starts'},
    'to': {'type': 'string', 'description': 'The name of the entity where the relation ends'},
    'relationType': {'type': 'string', 'description': 'The type of the relation'}},
    'required': ['from', 'to', 'relationType']}
OBSERVATIONS = {'type': 'array', 'items': {'type': 'object', 'properties': {
    'entityName': {'type': 'string', 'description': 'The name of the entity to add the observations to'},
    'contents': {'type': 'array', 'items': {'type': 'string'}, 'description': 'An array of observation contents to add'}},
    'required': ['entityName', 'contents']}}
DELETIONS = {'type': 'array', 'items': {'type': 'object', 'properties': {
    'entityName': {'type': 'string', 'description': 'The name of the entity containing the observations'},
    'observations': {'type': 'array', 'items': {'type': 'string'}, 'description': 'An array of observations to delete'}},
    'required': ['entityName', 'observations']}}
NAMES = {'type': 'array', 'items': {'type': 'string'}}


EXAMPLE = ('metaform memory create_entities \'[{"name":"route ejection","entityType":"behavior",'
           '"observations":["Routes are ejected, never packed on delete."]}]\' node=element:code.manager.route')


def _at(*nouns: Noun) -> tuple[Noun, ...]:
    return (*nouns, Noun('node', NODE, required=False), *NAMED)


MODULE = Module(
    id='memory',
    summary='A memory graph, presented at each node of the map as the MCP reference memory server.',
    purpose='A knowledge graph of entities, observations and relations, the MCP reference memory server\'s, kept apart '
            'from the map and tied to its nodes. Give node to work with the memories at a node of the map; leave it '
            'out for the whole graph. When the map is wrong or incomplete at a node, record what you learned there. '
            'Details: metaform help memory.',
    details='The nine commands take the reference memory server\'s arguments and return its results. With node, they '
            'act on the entities joined to that node and the relations between them; create_entities joins what it '
            'makes to the node. A memory join is keyed by the node\'s namespace address, so a clear keeps it and a new '
            'intake with the same address reconnects it; orphaned lists those the map no longer holds. '
            'rekey <old-address> <new-address> transfers attachments and notes when an address is replaced. The reads at '
            'a node show nothing while the layer named memory is turned off there, with select, mask or --layers. Each '
            'node also holds one note of at most 2048 characters.',
    verbs=(
        Verb('create_entities', create_entities, 'Create multiple new entities in the knowledge graph.',
             nouns=_at(Noun('entities', 'The entities to create.', kind='json',
                            schema={'type': 'array', 'items': ENTITY})),
             examples=((EXAMPLE, 'Create an entity in the memories of the route manager.'),)),
        Verb('create_relations', create_relations,
             'Create multiple new relations between entities in the knowledge graph. Relations should be in active '
             'voice.',
             nouns=_at(Noun('relations', 'The relations to create.', kind='json',
                            schema={'type': 'array', 'items': RELATION}))),
        Verb('add_observations', add_observations, 'Add new observations to existing entities in the knowledge graph.',
             nouns=_at(Noun('observations', 'The observations to add, by entity.', kind='json', schema=OBSERVATIONS))),
        Verb('delete_entities', delete_entities,
             'Delete multiple entities and their associated relations from the knowledge graph.',
             nouns=_at(Noun('entityNames', 'An array of entity names to delete', kind='json', schema=NAMES))),
        Verb('delete_observations', delete_observations,
             'Delete specific observations from entities in the knowledge graph.',
             nouns=_at(Noun('deletions', 'The observations to delete, by entity.', kind='json', schema=DELETIONS))),
        Verb('delete_relations', delete_relations, 'Delete multiple relations from the knowledge graph.',
             nouns=_at(Noun('relations', 'An array of relations to delete', kind='json',
                            schema={'type': 'array', 'items': RELATION}))),
        Verb('read_graph', read_graph, 'Read the entire knowledge graph.', nouns=_at()),
        Verb('search_nodes', search_nodes, 'Search for nodes in the knowledge graph based on a query.',
             nouns=_at(Noun('query', 'The search query to match against entity names, types, and observation '
                                     'content'))),
        Verb('open_nodes', open_nodes, 'Open specific nodes in the knowledge graph by their names.',
             nouns=_at(Noun('names', 'An array of entity names to retrieve', kind='json', schema=NAMES))),
        Verb('note', note, "Read a node's one note, the person's; only the web page writes it.",
             nouns=(Noun('node', 'An element, element:<address>; with provider, the purpose it holds as receiver.'),
                    Noun('provider', 'A purpose node holds as its receiver: the address of the element that serves '
                                     'it.', required=False),
                    Noun('address', 'With provider: the element at that address the join holds.', required=False),
                    Noun('text', f'The note, at most {NOTE_LIMIT} characters; only the web page writes it.', required=False),
                    Noun('by', 'Who wrote it.', required=False)),
             examples=(('metaform memory note element:code.manager.route text="Routes drift under load."',
                        "Write the route manager's note."),)),
        Verb('joins', joins, 'The joins of type memory: at a node, of an entity, or all, each with whether it is '
                             'orphaned.',
             nouns=(Noun('node', 'element:<address>.', required=False), *NAMED,
                    Noun('entity', 'An entity name.', required=False))),
        Verb('orphaned', orphaned, 'The memory joins whose address the active map does not hold, with what each was '
                                   'attached to.'),
        Verb('unjoin', unjoin, 'Take one memory join away by its id; the entity stays in the graph.',
             nouns=(Noun('id', 'The join id joins or orphaned gives.'),)),
        Verb('rekey', rekey, 'Transfer memory joins and notes from an old address to a new address.',
             nouns=(Noun('old', 'The exact old namespace address, including one no longer held by the map.'),
                    Noun('new', 'The replacement namespace address.')),
             details='Replaces the exact address in receivers and providers of memory joins and notes in one '
                     'transaction. Keeps join ids, note text, author and time, and the memory graph. A destination '
                     'key collision rolls back the whole transfer. Returns the number of joins and notes changed.',
             examples=(('metaform memory rekey code.manager.route code.manager.table',
                        'Transfer the route manager\'s memory to its replacement address.'),)),
        Verb('graph', graph, 'The whole graph with every join, and whether each join\'s memory shows at its '
                             'node.'),
    ),
    node_read=node_read,
    tables=TABLES,
)
