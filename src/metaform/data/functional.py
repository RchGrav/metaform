"""A ticket's immediate functional neighborhood, shared by routing and inspection."""
from __future__ import annotations

import html
from typing import TYPE_CHECKING, Any, cast

from .records import WorkRecord

if TYPE_CHECKING:
    from .store import Store


def functional_context(store: Store, work: WorkRecord) -> dict[str, Any]:
    """Read actual joins at the ticket's receiver, never infer dependencies from adjacent namespaces."""
    address = work.address or work.receiver_address
    if address:
        from metaform import project as project_store
        held = project_store.stored_name(store.project_id)
        if project_store.holds(held):
            return _stored(held, address)
    element = store.element(address) if address else None
    if element is None:
        return {'address': address, 'name': address or work.node_id, 'nodes': [], 'requirements': [],
                'dependents': [], 'markdown': 'The ticket’s functional element is unavailable.'}
    nodes: dict[str, dict[str, str]] = {}

    def node(at: str, name: str | None = None, short: str = '') -> str:
        if at not in nodes:
            found = store.element(at) if not (name or short) else None
            label = name or (found.name if found else None)
            reading = short or (found.short_name if found else '') or ' '.join(reversed(at.split('.')))
            label = label or ' '.join(word if word.isupper() else word.capitalize()
                                     for word in reading.replace('_', ' ').split())
            nodes[at] = {'id': f'n{len(nodes)}', 'address': at, 'name': label}
        return nodes[at]['id']

    node(element.address, element.name, element.short_name)
    requirements: list[dict[str, Any]] = []
    dependents: list[dict[str, Any]] = []
    for direction, target in (('receiver', requirements), ('provider', dependents)):
        for join in store.joins(element.address, as_=direction, limit=0).results:
            receiver = join.receiver_address or join.receiver
            node(receiver)
            providers = [held.address or held.element_id for held in join.elements]
            for held, at in zip(join.elements, providers, strict=True):
                node(at, held.name, held.short_name)
            target.append({'id': join.id, 'receiver': receiver, 'purpose': join.purpose or '',
                           'ef': join.ef or '', 'ifd': join.ifd, 'providers': providers})
    return _rendered(element.address, nodes, requirements, dependents)


def _label(at: str) -> str:
    """An element's name read from its address, backward, as a short name reads."""
    return ' '.join(word if word.isupper() else word.capitalize()
                    for word in ' '.join(reversed(at.split('.'))).replace('_', ' ').split())


def _stored(project: str, address: str) -> dict[str, Any]:
    """The neighbourhood of an element of a project held in the project store: the elements its wants name, each want
    a requirement, and the elements whose wants name it, each relying on it (review of 2026-11-18, F3 and F10)."""
    from metaform import project as project_store
    path = f'{project}.{address}'
    read = project_store.run({path: {}})
    if read.get('status') == 'error':
        return {'address': address, 'name': address, 'nodes': [], 'requirements': [], 'dependents': [],
                'markdown': 'The ticket’s functional element is unavailable.'}
    held = cast(dict[str, Any], read[path])
    start = len(project) + 1
    nodes: dict[str, dict[str, str]] = {}

    def node(at: str, name: str | None = None) -> None:
        if at not in nodes:
            nodes[at] = {'id': f'n{len(nodes)}', 'address': at, 'name': name or _label(at)}

    def wanted(holder: str, want: dict[str, Any]) -> dict[str, Any]:
        element = str(want.get('element') or '')[start:]
        node(element)
        return {'id': f'want:{holder}->{element}', 'receiver': holder, 'purpose': str(want.get('why') or ''),
                'ef': str(want.get('how') or ''), 'ifd': want.get('direction'), 'providers': [element]}
    node(address, str(held.get('name') or '') or None)
    requirements = [wanted(address, one) for one in cast(list[dict[str, Any]], held.get('wants') or [])]
    dependents: list[dict[str, Any]] = []
    if held.get('wanted_by'):  # the wants naming it, with their holders, in one read-only query
        # the address is the stored element's own, letters, digits, '_' and '.', so it stands in the query as it is
        found = project_store.cypher(project, f"MATCH (h:Element)-[w:Wants]->(e:Element {{address: '{address}'}}) "
                                              'RETURN h.address, w.why, w.how, w.direction ORDER BY h.address')
        if found.get('status') == 'error':  # what was read stands; the gap is said where the dependents go
            return _rendered(address, nodes, requirements, [],
                             unread=f"The elements relying on {address} could not be read: {found.get('message')}")
        for holder, why, how, direction in cast(list[list[Any]], found.get('rows') or []):
            node(str(holder))
            dependents.append(wanted(str(holder), {'element': path, 'why': why, 'how': how,
                                                   'direction': direction}))
    return _rendered(address, nodes, requirements, dependents)


def _rendered(address: str, nodes: dict[str, dict[str, str]], requirements: list[dict[str, Any]],
              dependents: list[dict[str, Any]], unread: str | None = None) -> dict[str, Any]:
    """The neighbourhood as a Mermaid diagram and its requirements and dependents in words. With `unread`, the
    dependents could not be read: it is said in their place and kept as `dependents_unread`, never shown as none."""
    lines = ['```mermaid', 'flowchart LR']
    for one in nodes.values():
        lines.append(f'  {one["id"]}["{html.escape(one["name"], quote=True)}"]')
    seen: set[str] = set()
    for join in [*requirements, *dependents]:
        if join['id'] in seen:
            continue
        seen.add(join['id'])
        ident = f'r{len(seen)}'
        label = html.escape(join['purpose'] or 'Requirement', quote=True).replace('\n', ' ')
        lines.append(f'  {ident}{{"{label}"}} --> {nodes[join["receiver"]]["id"]}')
        lines.extend(f'  {nodes[at]["id"]} --> {ident}' for at in join['providers'])
    lines.extend(['```', '', 'Arrows show which providers serve each receiver’s requirement; IFD is recorded separately.'])
    for title, joins, empty in (('Requirements', requirements, 'None recorded.'),
                                ('Functionality relying on this element', dependents, unread or 'None recorded.')):
        lines.extend(['', f'### {title}', ''])
        for join in joins:
            providers = ', '.join(nodes[at]['name'] for at in join['providers']) or 'No provider recorded'
            lines.append(f'- **{nodes[join["receiver"]]["name"]}**: {join["purpose"] or "No purpose recorded"}. '
                         f'Providers: {providers}. EF: {join["ef"] or "Unspecified"}. '
                         f'IFD: {join["ifd"] or "Unspecified"}.')
        if not joins:
            lines.append(empty)
    return {'address': address, 'name': nodes[address]['name'], 'nodes': list(nodes.values()),
            'requirements': requirements, 'dependents': dependents, 'markdown': '\n'.join(lines),
            **({'dependents_unread': unread} if unread else {})}
