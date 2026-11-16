"""The page's map read from the project store (`metaform.project`).

The page draws a map from a `GraphPage`: elements, each with its nearest parent element, and joins, each held by
its receiver and holding the elements that serve it. `graph` builds that page from a project in the project store:
an element is drawn by its address, and a want is drawn as the join its holder receives, holding the wanted element.
"""
from __future__ import annotations

from typing import Any, cast

from metaform import project as commands
from metaform.data import Element, GraphElement, GraphPage, Held, Item, Join, Layer, LayerGroup, Node, NodeView
from metaform.project import ROLE_WORDS

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


def layers(project: str, base: str) -> list[Layer] | None:
    """The layers the page lists for a project in the project store: the base map, then each overlay that is defined
    beside the wants, by its key and with its description. None when the store holds no such project."""
    name = commands.stored_name(project)
    if not commands.holds(name):
        return None
    found = commands.run({'map': name})
    if found.get('status') == 'error':
        return None

    def layer(key: str, said: str) -> Layer:
        return Layer(id=key, base_id=base, name=key, module='project', variable=said, kind='layer', mutable=True,
                     hideable=key != BASE, result_id=None, created='', ready='recorded', on=True)

    made = [layer(BASE, "The project's map: its elements and what each wants of another.")]
    for key in cast(list[str], found.get('overlays') or []):
        if key == 'wants':  # the wants are the base map's own joins
            continue
        steps = '.'.join(reversed(key.split('_')))
        definition = cast(dict[str, Any], commands.run({f'{name}.overlay.{steps}': {}}).get(f'{name}.overlay.{steps}') or {})
        made.append(layer(key, str(definition.get('description') or '')))
    return made


def node(project: str, target: str, chosen: str | None = None) -> NodeView | None:
    """One element as the page's panel reads it: each overlay that holds records there as a layer, each record an
    item whose value is the record's fields. None when the project store holds no such project or element, or the
    target is not an element."""
    kind, _, address = target.partition(':')
    name = commands.stored_name(project)
    if kind != 'element' or not address or not commands.holds(name):
        return None
    path = f'{name}.{address}'
    place = Node('element', address)
    read = commands.run({path: {}})
    if read.get('status') == 'error':
        # An element an intake has since removed or renamed: the page still holds it for a moment. It is answered as
        # a place with nothing at it, as the page reads any part that is gone, and the page's next read lets go of it.
        return NodeView(place, None, (), orphaned=True)
    overlays = cast(list[str], cast(dict[str, Any], read[path]).get('overlays') or [])
    if chosen is not None:  # the layers the person has switched on in the page's Layers control
        shown = set(chosen.split(','))
        overlays = [key for key in overlays if key in shown]
    asked: dict[str, object] = {key: {} for key in overlays}
    held = cast(dict[str, Any], commands.run({path: asked}).get(path) or {}) if overlays else {}
    groups = tuple(LayerGroup(key, key, 'layer', tuple(
        Item(id=f'{address}:{key}:{position}', layer_id=key, layer=key, target=place, value=record)
        for position, record in enumerate(cast(list[dict[str, Any]], held.get(key) or []))))
        for key in overlays)
    return NodeView(place, address, groups)


def tickets(project: str, given: dict[str, str]) -> list[dict[str, Any]] | None:
    """The project's tickets as the page's board and panels read work records: each record of the tickets overlay,
    with the element it is at. `node` keeps those at one element, `open` those not done, `ids` those named. None when
    the project store holds no such project."""
    name = commands.stored_name(project)
    found = commands.overlay_records(name, 'tickets')
    if found is None:
        return None
    lead = len(name) + 1
    at = given.get('node', '').partition(':')[2] if given.get('node', '').startswith('element:') else None
    wanted = set(given['ids'].replace(',', ' ').split()) if given.get('ids') else None
    listed: list[dict[str, Any]] = []
    for record in found:
        address, position = str(record['element'])[lead:], cast(int, record['position'])
        done = cast('str | None', record.get('done'))
        if (at is not None and address != at) or (given.get('open') == 'true' and done) or (
                wanted is not None and record.get('id') not in wanted):
            continue
        taken_by = cast('str | None', record.get('taken_by'))
        listed.append({
            'id': record.get('id'), 'node_kind': 'element', 'node_id': address, 'address': address,
            'receiver_address': None, 'provider_address': None, 'condition': '', 'note': record.get('note'),
            'task': record.get('task'), 'held': bool(record.get('held')), 'reviewed': False, 'created': '',
            'done': done, 'resolution': None, 'notices': [], 'steps': None, 'steps_done': 0, 'said': [],
            'taken': taken_by, 'taken_by': taken_by, 'position': position, 'links': [],
            'kind': record.get('kind') or '', 'outcome': record.get('outcome'), 'age_seconds': None, 'is_work': True,
            'map': {'item': f'{address}#{position + 1}', 'title': record.get('title') or ''}})
    return listed

