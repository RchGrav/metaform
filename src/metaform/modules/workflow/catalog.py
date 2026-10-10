"""Callable Axiom records attached through ordinary knowledge-layer items."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from metaform.data import Column, Item, Layer, Node, Outcome, Store, StoreError, Table, Tables
from metaform.module import Context

from .binding import Logic
from .element import ElementValue, element_value

FORMAT = 'metaform-workflow:1'  # the portable document `export` writes and `import` reads
TABLES = Tables(version=1, tables=(
    Table('logic_versions', key=('logic_id', 'number'), columns=(
        Column('logic_id', required=True), Column('number', 'int', required=True),
        Column('name', required=True), Column('content', required=True)),
        on_remove=(('item', 'logic_id', 'delete'),)),
))


def _owned(store: Store) -> Store:
    if store.module == 'workflow':
        return store
    active = store.bound_base()
    return Store(store.project_id, module='workflow', toggled=store.toggled,
                 base=None if active is None else active.id)


def ensure_layer(store: Store, layer: str, provenance: Mapping[str, Any] | None = None) -> Layer:
    """Create a ready knowledge layer; an existing layer keeps its lifecycle."""
    for found in store.layers(limit=0).results:
        if found.name == layer:
            return found
    return store.layer(layer, 'workflow', 'Reusable workflow logic.', mutable=True, hideable=True,
                       provenance=dict(provenance or {}), ready=True)


def _items(store: Store, address: str, *, layer: str | None = None,
           selection: Sequence[str] | None = None) -> list[Item]:
    element = store.element(address, raw=layer is not None, selection=selection)
    if element is None:
        return []
    node = Node('element', element.id)
    if layer is not None:
        return [item for item in store.layer_items(layer, node, limit=0).results if isinstance(item, Item)]
    view = store.node(node, selection=selection)
    return [] if view is None else [item for group in view.layers for item in group.items]


def _typed(items: Sequence[Item], kind: str, name: str | None = None) -> list[Item]:
    results: list[Item] = []
    for item in items:
        raw: Any = item.value
        if isinstance(raw, dict):
            value = cast(dict[str, Any], raw)
            if value.get('type') == kind and (name is None or value.get('name') == name):
                results.append(item)
    return results


def _logic(item: Item) -> Logic:
    return Logic('logic', item.id, item.value['name'], item.value['content'])


def _edit(store: Store, identity: str, changes: dict[str, Any]) -> None:
    result = store.edit(identity, changes)
    if isinstance(result, Outcome):
        raise StoreError(' '.join(notice.message for notice in result.notices), 'metaform help map knowledge')


def _put(store: Store, address: str, layer: str, value: dict[str, Any]) -> Item:
    candidates = _typed(_items(store, address, layer=layer), value['type'], value.get('name'))
    if candidates:
        item = candidates[-1]
        _edit(store, item.id, {'value': value})
        return next(one for one in _items(store, address, layer=layer) if one.id == item.id)
    element = store.element(address, raw=True)
    if element is None:
        raise KeyError(address)
    item = store.add_item(layer, Node('element', element.id), value)
    if not isinstance(item, Item):
        raise TypeError(item.to_dict())
    return item


def submit_workflow(store: Store, address: str, layer: str, name: str | None = None,
                    name_length: int = 2, layers: Sequence[str] = (),
                    provenance: Mapping[str, Any] | None = None) -> dict[str, Any]:
    with store.atomic():
        ensure_layer(store, layer, provenance)
        existing = store.element(address, raw=True)
        if existing is None:
            store.add_element(layer, address, name=name, name_length=name_length)
        else:
            changes: dict[str, Any] = {}
            if name is not None and name != existing.name:
                changes['name'] = name
            if name_length != existing.name_length:
                changes['name_length'] = name_length
            if changes:
                _edit(store, existing.id, changes)
        _put(store, address, layer, {'type': 'workflow', 'selected_layers': list(layers)})
    return document(store, address, layer)


def _versions(store: Store, logic_id: str) -> list[dict[str, Any]]:
    with store.tables(write=False) as tables:
        return list(tables.rows('logic_versions', {'logic_id': logic_id}, limit=0).results)


def submit_logic(store: Store, address: str, layer: str, name: str, content: str,
                 provenance: Mapping[str, Any] | None = None) -> Logic:
    owned = _owned(store)
    with owned.atomic():
        ensure_layer(owned, layer, provenance)
        prior = _typed(_items(owned, address, layer=layer), 'logic', name)
        item = _put(owned, address, layer, {'type': 'logic', 'name': name, 'content': content})
        versions = _versions(owned, item.id)
        with owned.tables() as tables:
            if prior and not versions:
                tables.insert('logic_versions', {'logic_id': item.id, 'number': 1,
                              'name': prior[-1].value['name'], 'content': prior[-1].value['content']})
                versions = [{'number': 1}]
            tables.insert('logic_versions', {'logic_id': item.id,
                          'number': len(versions) + 1, 'name': name, 'content': content})
        return _logic(item)


def selected_layers(store: Store, address: str, selection: Sequence[str] | None = None) -> list[str]:
    """Only a workflow visible in this context brings its selected knowledge."""
    metadata = _typed(_items(store, address, selection=selection), 'workflow')
    return list(metadata[-1].value.get('selected_layers', ())) if metadata else []


def lookup(store: Store, address: str, name: str,
           selection: Sequence[str] | None = None) -> tuple[Logic, ElementValue]:
    accompanying = selected_layers(store, address, selection)
    if accompanying:
        starting = selection if selection is not None else (store.toggled or tuple(
            layer.name for layer in store.layers(limit=0).results if layer.on))
        selection = list(dict.fromkeys((*starting, *accompanying)))
    found = _typed(_items(store, address, selection=selection), 'logic', name)
    if not found:
        raise KeyError(f'{address}.{name}')
    return _logic(found[-1]), element_value(store, address, selection=selection)


def history(store: Store, address: str, name: str, layer: str) -> list[dict[str, Any]]:
    found = _typed(_items(store, address, layer=layer), 'logic', name)
    if not found:
        raise KeyError(f'{address}.{name}')
    return _saved(_owned(store), found[-1].id)


def _saved(store: Store, logic_id: str) -> list[dict[str, Any]]:
    """Every saved version of one logic requirement, without the id it is kept under."""
    return [{key: value for key, value in version.items() if key != 'logic_id'}
            for version in _versions(store, logic_id)]


def workflows(store: Store, selection: Sequence[str] | None = None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for entry in store.graph(selection=selection, limit=0).elements:
        element = entry.element
        if not element.address.startswith('workflow.'):
            continue
        items = _items(store, element.address, selection=selection)
        metadata = _typed(items, 'workflow')
        if metadata:
            results.append({'address': element.address, 'name': element.name,
                            'selected_layers': metadata[-1].value.get('selected_layers', []),
                            'logic': [item.value['name'] for item in _typed(items, 'logic')]})
    return results


def node_read(ctx: Context, node: Node) -> dict[str, Any] | None:
    if ctx.store is None or node.kind != 'element':
        return None
    view = ctx.store.node(node)
    if view is None:
        return None
    items = [item for group in view.layers for item in group.items]
    metadata = _typed(items, 'workflow')
    logic = _typed(items, 'logic')
    if not metadata and not logic:
        return None
    return {'selected_layers': metadata[-1].value.get('selected_layers', []) if metadata else [],
            'logic': [_logic(item).to_dict() for item in logic]}


def document(store: Store, address: str, layer: str) -> dict[str, Any]:
    """A portable workflow, without source project or native layer ownership."""
    element = store.element(address, raw=True)
    if element is None:
        raise KeyError(address)
    found = next((one for one in store.layers(limit=0).results if one.name == layer), None)
    if found is None:
        raise StoreError(f'No layer {layer}.', 'metaform map layers')
    items = _items(store, address, layer=layer)
    metadata = _typed(items, 'workflow')
    logic = _typed(items, 'logic')
    recorded = store.provenance(layer)
    provenance = {} if recorded is None else recorded.to_dict()
    provenance.pop('layer_id', None)
    owned = _owned(store)
    return {'format': FORMAT, 'workflow': {
        'address': address, 'name': element.name, 'name_length': element.name_length,
        'selected_layers': metadata[-1].value.get('selected_layers', []) if metadata else []},
        'layer': {'name': layer, 'variable': found.variable, 'provenance': provenance},
        'logic': [_logic(item).to_dict() for item in logic],
        'versions': {item.id: _saved(owned, item.id) for item in logic}}


def ingest_document(store: Store, given: object, layer: str | None = None) -> dict[str, Any]:
    payload: Mapping[str, Any] = cast(Mapping[str, Any], given) if isinstance(given, Mapping) else {}
    if payload.get('format') != FORMAT:
        raise StoreError(f'This is not a portable workflow: it does not carry the format {FORMAT}.',
                         'metaform help workflow import')
    owned = _owned(store)
    workflow = payload['workflow']
    source = payload['layer']
    destination = layer or source['name']
    with owned.atomic():
        if not any(found.name == destination for found in owned.layers(limit=0).results):
            owned.layer(destination, 'workflow', source.get('variable', 'Reusable workflow logic.'),
                        mutable=True, hideable=True, provenance=source.get('provenance'), ready=True)
        submit_workflow(owned, workflow['address'], destination, workflow.get('name'),
                        workflow.get('name_length', 2), workflow.get('selected_layers', ()))
        for logic in payload['logic']:
            versions = payload.get('versions', {}).get(logic['logic_id'], ())
            if versions:
                for version in versions:
                    saved = submit_logic(owned, workflow['address'], destination, logic['name'], version['content'])
                    number = len(_versions(owned, saved.logic_id))
                    with owned.tables() as tables:
                        tables.update('logic_versions', {'logic_id': saved.logic_id, 'number': number},
                                      {'name': version['name']})
            if not versions or (versions[-1]['name'], versions[-1]['content']) != (logic['name'], logic['content']):
                submit_logic(owned, workflow['address'], destination, logic['name'], logic['content'])
    return document(owned, workflow['address'], destination)
