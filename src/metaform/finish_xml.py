"""The map as an XML document in the Finish shape of Intake 2.1, every field written, MAP-059.

One writer for the command `metaform map xml` and for the web GUI's export menu, VIEW-024, so the two give the same
document. It reads through `roots`, `where` and `graph`, STORE-025, so select, mask and hiding hold. The document is
for reviewing what was recorded: the metaform and each CQU in it, as the schema has them, each join under its receiver with its type,
ifd, purpose and ef, and each element under the join that holds it with its namespace_address, name_length, name and
role. An element's first occurrence holds its refs, the items the layers in context hold at it, its open work and the
joins it receives; a later occurrence carries only its four fields. What the trace never reaches is kept under
`unplaced`, so nothing in view is left out.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from typing import Any

from .data import Element, Join, Node, Store, Where
from .errors import Stop


def _text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


class _Writer:
    def __init__(self, store: Store, reading: dict[str, Any]) -> None:
        self.store, self.reading = store, reading
        self.placed: set[str] = set()
        self.joined: set[str] = set()

    def fields(self, parent: ET.Element, element: Element | Any) -> ET.Element:
        return ET.SubElement(parent, 'element', {
            'namespace_address': element.address, 'name_length': '' if element.name_length is None else
            str(element.name_length), 'name': element.name or '', 'role': element.role or ''})

    def work(self, parent: ET.Element, node: Node) -> None:
        for record in self.store.work(node, open=True, limit=0).results:
            ET.SubElement(parent, 'work', condition=record.condition or '').text = record.note or ''

    def element(self, parent: ET.Element, address: str) -> None:
        found: Where | None = self.store.where(address, **self.reading)
        if found is None or found.element is None:
            return
        node = self.fields(parent, found.element)
        if address in self.placed:
            return
        self.placed.add(address)
        for group in found.layers:
            for item in group.items:
                if group.layer == 'sources':
                    for ref in item.refs:
                        ET.SubElement(node, 'ref', key=ref.key, value=_text(ref.value))
                else:
                    ET.SubElement(node, 'item', layer=group.layer).text = _text(item.value)
            for prop in group.properties:
                ET.SubElement(node, 'property', layer=group.layer).text = _text(prop.value)
        self.work(node, Node('element', found.element.id))
        for join in found.receives:
            self.join(node, join)

    def join(self, parent: ET.Element, join: Join, receiver: bool = False) -> None:
        self.joined.add(join.id)
        node = ET.SubElement(parent, 'join', {**({'receiver': join.receiver_address or ''} if receiver else {}),
                                              'type': join.type or '', 'ifd': join.ifd or ''})
        ET.SubElement(node, 'purpose').text = join.purpose or ''
        ET.SubElement(node, 'ef').text = join.ef or ''
        self.work(node, Node('join', join.id))
        for held in join.elements:
            if held.address:
                self.element(node, held.address)


def xml(store: Store, address: str | None = None, *, selection: Sequence[str] | None = None,
        raw: bool = False) -> str:
    """The whole map from its CQUs, or with an address that element and all it receives, as an XML document."""
    reading: dict[str, Any] = {'selection': selection, 'raw': raw}
    metaform = store.active_base()
    root = ET.Element('metaform', id=metaform.id if metaform else '', name=metaform.name if metaform else '',
                      project=store.project().project_id)
    writer = _Writer(store, reading)
    if address:
        writer.element(root, address)
        if not len(root):
            raise Stop(f'No element at {address}.', 'metaform map roots')
    else:
        entry = sorted(store.roots(limit=0, **reading).elements, key=lambda element: element.address)
        for cqu in (element.address for element in entry if element.role == 'CQU'):
            writer.element(root, cqu)  # the map comes off each CQU's root join to the DE
        graph = store.graph(limit=0, **reading)
        unplaced = ET.Element('unplaced')
        for found in graph.elements:
            if found.element.address not in writer.placed:
                writer.element(unplaced, found.element.address)
        for join in graph.joins:
            if join.id not in writer.joined:
                writer.join(unplaced, join, receiver=True)
        if len(unplaced):
            root.append(unplaced)
    ET.indent(root)
    return ET.tostring(root, encoding='unicode', xml_declaration=True) + '\n'
