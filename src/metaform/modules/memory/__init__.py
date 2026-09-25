"""memory: the reference memory server's operations over the map's own nodes, BASE-040, LAYER-013.

An entity is an element, join or subtype of the map, named by its address or
id. An observation is one item of the memory layer at that node; a relation is
one item at the `from` node, linking to the `to` node, with the relation type
as its value, STORE-020. The memory layer is made on the first write, LAYER-012.
"""
from __future__ import annotations

from typing import Any

from metaform.data import Element, Item, Node, Store
from metaform.module import Context, Module, Noun, Stop, Verb

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False

VARIABLE = 'What agents have noted at this node.'


def _node(text: str) -> Node:
    return Node.parse(text)


def _memory(store: Store, *, create: bool) -> str | None:
    """The memory layer's name, found by its kind, made on the first write when asked."""
    found = store.layers(kind='memory', limit=0).results
    if found:
        return found[0].name
    if not create:
        return None
    return store.layer('memory', 'memory', VARIABLE, kind='memory', mutable=True, hideable=True, ready=True).name


def _name(store: Store, node: Node) -> str:
    """How memory names a node: its address, or a join's id."""
    if node.kind == 'join':
        return node.id
    view = store.node(node, raw=True)
    return view.address if view is not None and view.address else node.id


def _entity(store: Store, node: Node, items: list[Item]) -> dict[str, Any]:
    return {'name': _name(store, node), 'entityType': node.kind,
            'observations': [item.value for item in items if item.link is None]}


def _relation(store: Store, item: Item) -> dict[str, Any]:
    assert item.link is not None
    return {'from': _name(store, item.target), 'to': _name(store, item.link), 'relationType': item.value}


def _at(store: Store, layer: str, node: Node) -> list[Item]:
    """Every memory at a node, for changing them: memory's own layer read directly, LAYER-008."""
    return [item for item in store.layer_items(layer, node, limit=0).results if isinstance(item, Item)]


def _said(result: dict[str, Any], done: list[Any]) -> dict[str, Any]:
    """A verb's result with the notices of the writes it made, BASE-044."""
    notices = [notice for written in done for notice in getattr(written, 'notices', ())]
    if notices:
        result['notices'] = notices
    return result


def _grouped(store: Store, items: list[Item]) -> dict[str, Any]:
    nodes: dict[tuple[str, str], list[Item]] = {}
    relations: list[dict[str, Any]] = []
    for item in items:
        nodes.setdefault((item.target.kind, item.target.id), []).append(item)
        if item.link is not None:
            relations.append(_relation(store, item))
    return {'nodes': [_entity(store, Node.of(kind, ident), found) for (kind, ident), found in nodes.items()],
            'relations': relations}


def create_entities(ctx: Context) -> Any:
    store = ctx.require_store()
    name = ctx.nouns['name']
    with store.atomic():
        layer = _memory(store, create=True)
        assert layer is not None
        element = store.add_element(layer, name)
    if not isinstance(element, Element):
        return element
    return _said({'entities': [{'name': element.address, 'entityType': ctx.nouns['type'],
                                'existing': element.existing}]}, [element])


def create_relations(ctx: Context) -> Any:
    store = ctx.require_store()
    source, target = _node(ctx.nouns['from']), _node(ctx.nouns['to'])
    with store.atomic():
        layer = _memory(store, create=True)
        assert layer is not None
        item = store.add_item(layer, source, ctx.nouns['relation'], link=target)
    if not isinstance(item, Item):
        return item
    return _said(_relation(store, item), [item])


def add_observations(ctx: Context) -> Any:
    store = ctx.require_store()
    node = _node(ctx.nouns['node'])
    with store.atomic():
        layer = _memory(store, create=True)
        assert layer is not None
        written = [store.add_item(layer, node, text) for text in ctx.nouns['text']]
    added = [item.value for item in written if isinstance(item, Item)]
    return _said({'node': _name(store, node), 'added': added}, written)


def delete_entities(ctx: Context) -> Any:
    store = ctx.require_store()
    layer = _memory(store, create=False)
    deleted = 0
    if layer is not None:
        with store.atomic():
            for text in ctx.nouns['node']:
                for item in _at(store, layer, _node(text)):
                    store.delete_item(item.item_id)
                    deleted += 1
    return {'deleted': deleted}


def delete_observations(ctx: Context) -> Any:
    store = ctx.require_store()
    layer = _memory(store, create=False)
    node = _node(ctx.nouns['node'])
    deleted = 0
    if layer is not None:
        with store.atomic():
            for item in _at(store, layer, node):
                if item.link is None and item.value in ctx.nouns['text']:
                    store.delete_item(item.item_id)
                    deleted += 1
    return {'node': _name(store, node), 'deleted': deleted}


def delete_relations(ctx: Context) -> Any:
    store = ctx.require_store()
    layer = _memory(store, create=False)
    source, target = _node(ctx.nouns['from']), _node(ctx.nouns['to'])
    deleted = 0
    if layer is not None:
        target_name = _name(store, target)
        with store.atomic():
            for item in _at(store, layer, source):
                if item.link is not None and item.value == ctx.nouns['relation'] and \
                        _name(store, item.link) == target_name:
                    store.delete_item(item.item_id)
                    deleted += 1
    return {'deleted': deleted}


def read_graph(ctx: Context) -> Any:
    store = ctx.require_store()
    layer = _memory(store, create=False)
    if layer is None:
        return {'nodes': [], 'relations': []}
    return _grouped(store, [item for item in store.layer_items(layer, in_context=True, limit=0).results
                            if isinstance(item, Item)])


def search_nodes(ctx: Context) -> Any:
    store = ctx.require_store()
    layer = _memory(store, create=False)
    if layer is None:
        return {'nodes': [], 'relations': []}
    return _grouped(store, list(store.search(ctx.nouns['query'], layer, limit=0).results))


def open_nodes(ctx: Context) -> Any:
    """Each node with its observations and the relations it holds and receives; memory read in context."""
    store = ctx.require_store()
    layer = _memory(store, create=False)
    nodes: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    for text in ctx.nouns['node']:
        node = _node(text)
        view = store.node(node)
        if view is None:
            raise Stop(f'{text} is not a node here.', f'metaform map where {node.id}')
        mine = [item for group in view.layers if layer is not None and group.layer == layer for item in group.items]
        nodes.append(_entity(store, view.node, mine))
        relations += [_relation(store, item) for item in mine if item.link is not None]
        if layer is not None:
            relations += [_relation(store, item) for item in store.links_to(view.node, layer, limit=0).results]
    return {'nodes': nodes, 'relations': relations}


NODE = 'element:<address or id>, join:<id> or subtype:<address or id>'

MODULE = Module(
    id='memory',
    summary="Notes agents keep at the map's own nodes.",
    purpose="Notes that agents keep at the map's own nodes, in the reference memory server's operations. When the "
            'map is wrong or incomplete at a node, add an observation there so the next agent reads it where it '
            'looks. Details: metaform help memory.',
    details='An entity is a node of the map. Observations and relations are items of the memory layer, which is '
            'mutable, hideable and takes part in select and mask like any layer: read-graph, search-nodes and '
            'open-nodes read memory in context, so hiding or masking it hides it there too.',
    verbs=(
        Verb('create-entities', create_entities, 'Make a node for a name the map does not hold yet.',
             nouns=(Noun('name', 'An address.'), Noun('type', 'The entity type.'))),
        Verb('create-relations', create_relations, 'Relate one node to another.',
             nouns=(Noun('from', NODE), Noun('relation', 'The relation type.'), Noun('to', NODE))),
        Verb('add-observations', add_observations, 'Add observations at a node.',
             nouns=(Noun('node', NODE), Noun('text', 'Each observation.', many=True)),
             examples=(('metaform memory add-observations element:code.manager.route "Routes are ejected."',
                        'Note one observation at the route manager.'),)),
        Verb('delete-entities', delete_entities, "Delete every memory at each node; never the node.",
             nouns=(Noun('node', NODE, many=True),)),
        Verb('delete-observations', delete_observations, 'Delete observations at a node by their text.',
             nouns=(Noun('node', NODE), Noun('text', 'Each observation.', many=True))),
        Verb('delete-relations', delete_relations, 'Delete a relation.',
             nouns=(Noun('from', NODE), Noun('relation', 'The relation type.'), Noun('to', NODE))),
        Verb('read-graph', read_graph, 'Every memory, grouped by node.'),
        Verb('search-nodes', search_nodes, 'Nodes whose memories hold every word of the query.',
             nouns=(Noun('query', 'The words to find.'),)),
        Verb('open-nodes', open_nodes, 'Each node with its observations and relations.',
             nouns=(Noun('node', NODE, many=True),)),
    ),
)
