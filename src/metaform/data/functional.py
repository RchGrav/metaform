"""A ticket's immediate functional neighborhood, shared by routing and inspection."""
from __future__ import annotations

import html
from typing import TYPE_CHECKING, Any

from .records import WorkRecord

if TYPE_CHECKING:
    from .store import Store


def functional_context(store: Store, work: WorkRecord) -> dict[str, Any]:
    """Read actual joins at the ticket's receiver, never infer dependencies from adjacent namespaces."""
    address = work.address or work.receiver_address
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
    for title, joins in (('Requirements', requirements), ('Functionality relying on this element', dependents)):
        lines.extend(['', f'### {title}', ''])
        for join in joins:
            providers = ', '.join(nodes[at]['name'] for at in join['providers']) or 'No provider recorded'
            lines.append(f'- **{nodes[join["receiver"]]["name"]}**: {join["purpose"] or "No purpose recorded"}. '
                         f'Providers: {providers}. EF: {join["ef"] or "Unspecified"}. '
                         f'IFD: {join["ifd"] or "Unspecified"}.')
        if not joins:
            lines.append('None recorded.')
    return {'address': element.address, 'name': nodes[element.address]['name'], 'nodes': list(nodes.values()),
            'requirements': requirements, 'dependents': dependents, 'markdown': '\n'.join(lines)}
