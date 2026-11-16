"""The page's map read from the project store (`metaform.project`).

The page draws a map from a `GraphPage`: elements, each with its nearest parent element, and joins, each held by
its receiver and holding the elements that serve it. `graph` builds that page from a project in the project store:
an element is drawn by its address, and a want is drawn as the join its holder receives, holding the wanted element.
"""
from __future__ import annotations

from typing import Any, cast

from metaform.data import Element, GraphElement, GraphPage, Held, Item, Join, LayerGroup, Node, NodeView
from metaform.project import commands
from metaform.project.texts import ROLE_WORDS

BASE = 'base'
_CODES = {name: code for code, name in ROLE_WORDS.items() if len(code) <= 3}  # the page draws by the short role

_FLOW = {'send': 'sends', 'receive': 'receives', 'both': 'both'}  # the page's words for a want's direction


def graph(project: str) -> GraphPage | None:
    """The project's whole map as the page draws it, or None when the project store holds no such project."""
    project = commands.stored_name(project)
    found = commands.drawn(project)
    if found is None:
        return None
    lead = len(project) + 1
    every = cast(list[dict[str, Any]], found['elements'])
    wants = cast(list[dict[str, Any]], found['wants'])
    named = {str(want[end]) for want in wants for end in ('holder', 'element')}
    # A bare branch on the way to an element is not drawn: it holds nothing of its own and no want names it.
    rows = [row for row in every if len(row) > 1 or row['address'] in named]
    known = {str(row['address'])[lead:] for row in rows}

    def element(row: dict[str, Any]) -> GraphElement:
        address = str(row['address'])[lead:]
        steps = address.split('.')
        parent = next(('.'.join(steps[:count]) for count in range(len(steps) - 1, 0, -1)
                       if '.'.join(steps[:count]) in known), None)
        technical = str(row.get('technical_name') or '')
        return GraphElement(Element(
            id=address, address=address, layer_id=BASE, layer=BASE, reading=' '.join(reversed(steps)),
            short_name=technical or ' '.join(reversed(steps)), name_length=len(technical.split()) or None,
            role=_CODES.get(str(row.get('role') or '')), state=cast('str | None', row.get('status')),
            name=cast('str | None', row.get('name'))), parent)

    by_address = {str(row['address'])[lead:]: row for row in rows}

    def join(number: int, want: dict[str, Any]) -> Join:
        holder, wanted = str(want['holder'])[lead:], str(want['element'])[lead:]
        held = by_address.get(wanted, {})
        technical = str(held.get('technical_name') or '')
        return Join(id=f'{holder}>{wanted}#{number}', layer_id=BASE, layer=BASE, type='purpose', receiver=holder,
                    receiver_address=holder, purpose=cast('str | None', want.get('why')),
                    ef=cast('str | None', want.get('how')), ifd=_FLOW.get(str(want.get('direction') or '')),
                    elements=(Held(element_id=wanted, address=wanted, short_name=technical,
                                   name_length=len(technical.split()) or None,
                                   name=cast('str | None', held.get('name')),
                                   role=_CODES.get(str(held.get('role') or ''))),))

    return GraphPage(tuple(element(row) for row in rows),
                     tuple(join(number, want) for number, want in enumerate(wants)))


def node(project: str, target: str) -> NodeView | None:
    """One element as the page's panel reads it: each overlay that holds records there as a layer, each record an
    item whose value is the record's fields. None when the project store holds no such project or element, or the
    target is not an element."""
    kind, _, address = target.partition(':')
    name = commands.stored_name(project)
    if kind != 'element' or not address or commands.drawn(name) is None:
        return None
    path = f'{name}.{address}'
    read = commands.run({path: {}})
    if read.get('status') == 'error':
        return None
    overlays = cast(list[str], cast(dict[str, Any], read[path]).get('overlays') or [])
    asked: dict[str, object] = {key: {} for key in overlays}
    held = cast(dict[str, Any], commands.run({path: asked}).get(path) or {}) if overlays else {}
    place = Node('element', address)
    groups = tuple(LayerGroup(key, key, 'layer', tuple(
        Item(id=f'{address}:{key}:{position}', layer_id=key, layer=key, target=place, value=record)
        for position, record in enumerate(cast(list[dict[str, Any]], held.get(key) or []))))
        for key in overlays)
    return NodeView(place, address, groups)
