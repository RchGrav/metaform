"""Assemble an already lexicalized prompt, chosen knowledge and its address footer."""
from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, cast

from metaform.data import Item, Property, Store, StoreError


def _knowledge(record: Item | Property, address: str | None) -> dict[str, Any]:
    """Keep knowledge values intact, with their location and supporting references."""
    result = {'address': address, 'value': record.value}
    if record.refs:
        result['refs'] = [ref.to_dict() for ref in record.refs]
    if record.extra is not None:
        result['extra'] = record.extra
    if isinstance(record, Item):
        if record.target.kind == 'join':
            result['kind'] = 'join'
        if record.read_first:
            result['read_first'] = True
        if record.always_show:
            result['always_show'] = True
    return result


def assemble(store: Store, text: str, addresses: object, *, scope: str = 'context') -> dict[str, Any]:
    """Read through the DAO's visibility rules, without inference or changing the supplied body.

    Context is the small default: the addressed nodes' knowledge and properties in their context. Whole expands
    the layers available at those addresses, still filtering every record at its own origin. Both modes keep
    `always_show` items at the addressed nodes, the explicit visibility exception of LAYER-021.
    """
    if scope not in ('context', 'whole'):
        raise StoreError(f'{scope!r} is not a preprocessing scope: use context or whole.',
                         'metaform help workflow preprocess')
    if (not isinstance(addresses, Sequence) or isinstance(addresses, (str, bytes))
            or any(not isinstance(address, str) or not address.strip()
                   for address in cast(Sequence[Any], addresses))):
        raise StoreError('Preprocessing addresses must be a sequence of nonempty namespace strings.',
                         'metaform help workflow preprocess')
    ordered = list(dict.fromkeys(cast(Sequence[str], addresses)))
    groups: dict[str, dict[str, Any]] = {}
    seen: set[tuple[str, str]] = set()
    available: dict[str, None] = {}
    footer: list[str] = []
    unresolved: list[dict[str, str]] = []
    notices: list[dict[str, str]] = []

    def add(record: Item | Property, address: str | None) -> None:
        kind = 'items' if isinstance(record, Item) else 'properties'
        identity = record.item_id if isinstance(record, Item) else record.property_id
        key = (kind, identity)
        if key in seen:
            return
        seen.add(key)
        group = groups.setdefault(record.layer, {'layer': record.layer, 'items': [], 'properties': []})
        group[kind].append(_knowledge(record, address))

    for address in ordered:
        where = store.where(address)
        if where is None or where.element is None:
            raise StoreError(f'{address} is not an element in the current context.', f'metaform map where {address}')
        element = where.element
        footer.append(f'{element.name or address} -> {address}')
        if not element.name:
            notices.append({'where': address,
                            'message': 'No canonical name is recorded; the footer uses the namespace address.'})
        selection = store.effective_selection(address)
        available.update(dict.fromkeys(selection.layers))
        for notice in selection.unresolved:
            if notice not in unresolved:
                unresolved.append(notice)
        for group in where.layers:
            for item in group.items:
                if scope == 'context' or item.always_show:
                    add(item, address)
            if scope == 'context':
                for prop in group.properties:
                    add(prop, prop.address)
        if scope == 'context':
            # where's property context uses the same resolution, including visible properties toward the leaves.
            for prop in (*where.applying, *where.visible):
                add(prop, prop.address)

    if scope == 'whole':
        for layer in available:
            for record in store.layer_items(layer, in_context=True, limit=0).results:
                if isinstance(record, Property):
                    add(record, record.address)
                else:
                    node = store.node(record.target)
                    if node is not None:
                        add(record, node.address)

    knowledge = list(groups.values())
    parts = [text]
    if knowledge:
        parts.append('Knowledge layers:\n' + json.dumps(knowledge, ensure_ascii=False, indent=2))
    if footer:
        parts.append('\n'.join(footer))
    result: dict[str, Any] = {'prompt': '\n\n'.join(parts), 'addresses': ordered, 'layers': knowledge, 'scope': scope}
    if unresolved:
        result['unresolved'] = unresolved
    if notices:
        result['notices'] = notices
    return result
