"""The page's map read from the project store (`metaform.project`).

The page draws a map from a `GraphPage`: elements, each with its nearest parent element, and joins, each held by
its receiver and holding the elements that serve it. `graph` builds that page from a project in the project store:
an element is drawn by its address, and a want is drawn as the join its holder receives, holding the wanted element.
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any, cast

from metaform import project as commands
from metaform.data import Element, GraphElement, GraphPage, Held, Item, Join, Layer, LayerGroup, Node, NodeView
from metaform.module import Stop
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
    found = commands.drawn(name)
    if found is None:
        return None

    def layer(key: str, said: str) -> Layer:
        # the base map is of kind base, which the page draws in the intake's colour and never loads as an overlay; as
        # kind layer it took the first knowledge colour, an amber the 3D map's shading turned brown (2026-11-17)
        return Layer(id=key, base_id=base, name=key, module='project', variable=said,
                     kind='base' if key == BASE else 'layer', mutable=True,
                     hideable=key != BASE, result_id=None, created='', ready='recorded', on=True)

    made = [layer(BASE, "The project's map: its elements and what each wants of another.")]
    # each overlay with the description its stored definition holds, found by its key: a key is never split back into
    # an address, since a step may hold an underscore (F04)
    for overlay in cast(list[dict[str, Any]], found.get('overlays') or []):
        if overlay['key'] == 'wants':  # the wants are the base map's own joins
            continue
        made.append(layer(str(overlay['key']), str(overlay.get('description') or '')))
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
    # the memories overlay is shown in the panel's Memories section, every other overlay under Knowledge
    groups = tuple(LayerGroup(key, key, 'memory' if key == 'memories' else 'layer', tuple(
        Item(id=f'{address}:{key}:{position}', layer_id=key, layer=key, target=place, value=record)
        for position, record in enumerate(cast(list[dict[str, Any]], held.get(key) or []))))
        for key in overlays)
    return NodeView(place, address, groups)


def local_view(project: str, address: str) -> dict[str, Any] | None:
    """What an agent assigned to an element receives there: the `project` tool's own answer at the element's address,
    as the tool gives it, so the page's picture of it is the agent's view and not a copy. `lead` is the project's
    prefix on every address in the answer. None when the project store holds no such project or element."""
    name = commands.stored_name(project)
    if not address or not commands.holds(name):
        return None
    path = f'{name}.{address}'
    read = commands.run({path: {}})
    if read.get('status') == 'error' or path not in read:
        return None
    return {'lead': f'{name}.', 'answer': read[path]}


def _shaped(record: dict[str, Any], lead: int) -> dict[str, Any]:
    """One record of the tickets overlay as the page reads a work record."""
    address, position = str(record['element'])[lead:], cast(int, record['position'])
    taken_by = cast('str | None', record.get('taken_by'))
    return {
        'id': record.get('id'), 'node_kind': 'element', 'node_id': address, 'address': address,
        'receiver_address': None, 'provider_address': None, 'condition': '', 'note': record.get('note'),
        'task': record.get('task'), 'held': bool(record.get('held')), 'reviewed': False, 'created': '',
        'done': record.get('done'), 'resolution': None, 'notices': [], 'steps': None, 'steps_done': 0, 'said': [],
        'taken': taken_by, 'taken_by': taken_by, 'position': position, 'links': [],
        'kind': record.get('kind') or '', 'outcome': record.get('outcome'), 'age_seconds': None, 'is_work': True,
        'map': {'item': f'{address}#{position + 1}', 'title': record.get('title') or ''}}


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
    return [_shaped(record, lead) for record in found
            if (at is None or str(record['element'])[lead:] == at)
            and not (given.get('open') == 'true' and record.get('done'))
            and (wanted is None or record.get('id') in wanted)]


def _done(answer: dict[str, object]) -> None:
    if answer.get('status') == 'error':
        raise Stop(str(answer.get('message') or 'The ticket was not changed.'), 'metaform help')


def _found(project: str, work_id: str) -> tuple[str, dict[str, Any]] | None:
    """The store's name for the project and the ticket's record there, or None when the project store holds no such
    project or ticket, which leaves the change to whatever else holds the ticket."""
    name = commands.stored_name(project)
    for record in commands.overlay_records(name, 'tickets') or []:
        if record.get('id') == work_id:
            return name, record
    return None


def _changed(name: str, record: dict[str, Any], fields: dict[str, object]) -> dict[str, Any]:
    """Change one ticket in place, by its position at its element and the record id found there, so a ticket moved
    by another writer meanwhile is refused rather than another card changed (F02), and give it back as the page reads
    it. The revision is not named: the person's move of a card stands over an agent's note written meanwhile. A field
    given as None is removed."""
    _done(commands.run({'update': {str(record['element']): {'tickets': [
        {'position': record['position'], 'record': record['record'], **fields}]}}}))
    kept = {key: value for key, value in {**record, **fields}.items() if value is not None}
    return _shaped(kept, len(name) + 1)


# A column of the board is said by a ticket's own fields: done once `done` is set, doing once taken, backlog while
# held, to do otherwise. Putting a card in a column writes those fields.
def move_ticket(project: str, work_id: str, column: str, by: object) -> dict[str, Any] | None:
    found = _found(project, work_id)
    if found is None:
        return None
    name, record = found
    now = datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
    columns: dict[str, dict[str, object]] = {
        'backlog': {'held': True, 'taken_by': None, 'done': None, 'outcome': None},
        'todo': {'held': None, 'taken_by': None, 'done': None, 'outcome': None},
        'doing': {'held': None, 'taken_by': str(by or record.get('taken_by') or 'person'), 'done': None,
                  'outcome': None},
        'done': {'held': None, 'done': now, 'outcome': 'completed'}}
    return _changed(name, record, columns[column])


def edit_ticket(project: str, work_id: str, fields: dict[str, object]) -> dict[str, Any] | None:
    found = _found(project, work_id)
    if found is None:
        return None
    return _changed(found[0], found[1], {key: (value if value != '' else None) for key, value in fields.items()})


def remove_ticket(project: str, work_id: str) -> dict[str, Any] | None:
    found = _found(project, work_id)
    if found is None:
        return None
    name, record = found
    _done(commands.run({'delete': {str(record['element']): {'tickets': [record['record']]}}}))  # by its id (F02)
    return _shaped(record, len(name) + 1)


def add_ticket(project: str, node: str, task: str, *, kind: object = None, held: bool = False) -> dict[str, Any] | None:
    """A ticket a person wrote, put on the element it is assigned to. Its title is the task's first line."""
    name = commands.stored_name(project)
    kind_of, _, address = node.partition(':')
    if kind_of != 'element' or not address or not commands.holds(name):
        return None
    record: dict[str, Any] = {'id': 't-' + secrets.token_hex(4), 'title': task.strip().splitlines()[0][:120],
                              'task': task.strip(), **({'kind': kind} if kind else {}), **({'held': True} if held else {})}
    path = f'{name}.{address}'
    _done(commands.run({'add': {path: {'tickets': [record]}}}))
    made = next((one for one in commands.overlay_records(name, 'tickets') or [] if one.get('id') == record['id']), None)
    return _shaped(made or {**record, 'element': path, 'position': 0}, len(name) + 1)


def assignment(project: str, work_id: str) -> str | None:
    """The assignment an agent started on a ticket receives: the ticket's own words and how it keeps the ticket
    current with the project tool. None when the project store holds no such ticket."""
    from importlib import resources

    from metaform import prompt_files
    found = _found(project, work_id)
    if found is None:
        return None
    _, record = found
    return prompt_files.required(resources.files('metaform.modules.web'), 'ticket_assignment',
                                 path=str(record['element']), id=str(record.get('id') or ''),
                                 title=str(record.get('title') or ''), task=str(record.get('task') or ''))


def memories(project: str) -> dict[str, Any] | None:
    """The project's memories as the page reads the memory graph: each entity with its observations, and where each
    is kept. A record of the memories overlay is one observation of the entity it names, at the element it is at.
    None when the project store holds no such project."""
    name = commands.stored_name(project)
    found = commands.overlay_records(name, 'memories')
    if found is None:
        return None
    lead = len(name) + 1
    entities: dict[str, dict[str, Any]] = {}
    joins: dict[tuple[str, str], dict[str, Any]] = {}
    for record in found:
        entity, address = str(record.get('entity') or ''), str(record['element'])[lead:]
        held = entities.setdefault(entity, {'name': entity, 'entityType': record.get('entity_type') or '',
                                            'observations': []})
        held['observations'].append({'content': record.get('observation') or '', 'by': ''})
        joins.setdefault((entity, address), {'join_id': f'{address}:{entity}', 'entity': entity, 'address': address,
                                             'by': '', 'orphaned': False, 'shows': True})
    return {'entities': list(entities.values()), 'relations': [], 'joins': list(joins.values())}

