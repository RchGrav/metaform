"""Building the records the data access object returns, from versions, STORE-023 and STORE-025.

Every builder works inside one open transaction, on its base's projection. A builder given a `Resolver`
builds for a read in context: it leaves out what the selection does not reach,
STORE-019. Without one it builds for a raw read, and marks what is orphaned,
STORE-017. Every element and join carries the conditions
of its open work records, STORE-042, in context and raw alike, since a work record
has no layer.
"""
from __future__ import annotations

import json
from typing import Any, cast

from . import operations, prompts, versions
from .ids import decode_extra
from .names import reading, short_name
from .projection import Version
from .records import Element, Held, Item, Join, Layer, Node, Op, Property, Provenance, VersionRef
from .records import Version as VersionRecord
from .rows import address_of, held_elements, layer_name, read_refs, target_current, whole_number
from .selection import LayerRow, Resolver, all_layers, hidden_closure
from .session import Tx
from .versions import BASE_KINDS

Row = Version


def element_shows(res: Resolver, layer_id: str, address: str) -> bool:
    """An element of the base is always a node; one a knowledge layer created shows where its layer does."""
    found = res.layers.get(layer_id)
    if found is not None and found.kind in BASE_KINDS:
        return found.finished
    return res.reaches(layer_id, address)


def element(tx: Tx, element_id: str, res: Resolver | None, layers: dict[str, LayerRow] | None = None) -> Element | None:
    """An element as its current version holds it: its address, name_length, name and role, STORE-009, with its
    reading and its short name, the address read through name_length, MAP-012; in context, only when its layer
    reaches its address."""
    current = versions.current_version(tx.base, 'element', element_id)
    if current is None:
        return None
    known = layers or (res.layers if res else all_layers(tx.base))
    address = str(current['address'])
    if res is not None and not element_shows(res, current.layer_id, address):
        return None
    length = current['name_length'] if whole_number(current['name_length']) else None
    return operations.decorate(tx, Element(element_id, address, current.layer_id, known[current.layer_id].name,
                   reading(address), short_name(address, length), current['name_length'], current['role'],
                   name=current['name'], within=current['within'], note=current['note']))


def held(tx: Tx, join_row: int) -> tuple[Held, ...]:
    """The elements one version of a join holds, in order, each as its current version holds it, or its last
    version when it is not current."""
    found: list[Held] = []
    for element_id in held_elements(tx.base, join_row):
        row = versions.current_version(tx.base, 'element', element_id)
        if row is None:
            held_versions = tx.base.versions.get(element_id, ())
            row = held_versions[-1] if held_versions and tx.base.kinds.get(element_id) == 'element' else None
        if row is None:
            found.append(Held(element_id, None))
            continue
        length = row['name_length'] if whole_number(row['name_length']) else None
        found.append(Held(element_id, str(row['address']), short_name(str(row['address']), length),
                          row['name_length'], row['name'], row['role']))
    return tuple(found)


def join_orphaned(tx: Tx, row: Row) -> bool:
    """A join with an end that is not current, STORE-017: its receiver or an element it holds."""
    ends = [str(row['receiver']), *held_elements(tx.base, row.seq)]
    return any(address_of(tx, end) is None for end in ends)


def join(tx: Tx, join_id: str, row: Row, layers: dict[str, LayerRow], orphaned: bool = False) -> Join:
    return operations.decorate(tx, Join(join_id, row.layer_id, layers[row.layer_id].name,
                str(row['type']), str(row['receiver']), address_of(tx, str(row['receiver'])), row['purpose'],
                row['ef'], row['ifd'], held(tx, row.seq), None, orphaned, element=row['element'], note=row['note']))


def visible_join(tx: Tx, join_id: str, row: Row, res: Resolver | None) -> Join | None:
    """A join as a raw read returns it, or in context only when its layer reaches its receiver, STORE-025."""
    orphaned = join_orphaned(tx, row)
    if res is None:
        return join(tx, join_id, row, all_layers(tx.base), orphaned)
    if orphaned or not res.reaches(row.layer_id, address_of(tx, str(row['receiver']))):
        return None
    return join(tx, join_id, row, res.layers)


def item(tx: Tx, item_id: str, row: Row, layers: dict[str, LayerRow]) -> Item:
    orphaned = not target_current(tx, str(row['target_kind']), str(row['target_id']))
    return operations.decorate(tx, Item(item_id, row.layer_id, layers[row.layer_id].name,
                Node.of(str(row['target_kind']), str(row['target_id'])), json.loads(str(row['value'])),
                Node.of(str(row['link_kind']), str(row['link_id'])) if row['link_kind'] else None,
                read_refs(tx.base, 'item', row.seq), decode_extra(row['extra']),
                None, orphaned, bool(row['read_first']), bool(row['always_show'])))


def item_by_id(tx: Tx, item_id: str) -> Item:
    row = versions.current_version(tx.base, 'item', item_id)
    if row is None:
        row = tx.base.versions[item_id][-1]
    return item(tx, item_id, row, all_layers(tx.base))


def prop(tx: Tx, property_id: str, row: Row, layers: dict[str, LayerRow]) -> Property:
    address = address_of(tx, str(row['element_id']))
    return Property(property_id, row.layer_id, layers[row.layer_id].name,
                    str(row['element_id']), address, json.loads(str(row['value'])),
                    read_refs(tx.base, 'property', row.seq), decode_extra(row['extra']), address is None)


def provenance(tx: Tx, layer_id: str) -> Provenance | None:
    """The layer's one provenance record, with its report, feedback and shape files as refs, STORE-016."""
    found = tx.base.layers.get(layer_id)
    if found is None or found.provenance is None:
        return None
    row = found.provenance
    used = prompts.use_of(tx.project_id, tx.base_id, layer_id) if tx.base_id else None
    blinded = row.get('blinded')
    return operations.decorate(tx, Provenance(layer_id, str(row.get('module')), row.get('workflow'), row.get('prompt'),
                      row.get('model'), row.get('role'), None if blinded is None else bool(blinded), (),
                      VersionRef(used.name, used.number, used.version_id) if used else None))


def layer(tx: Tx, found: LayerRow, *, toggled: frozenset[str] | None = None, hidden: set[str] | None = None,
          with_provenance: bool = False) -> Layer:
    layer_id = found.id
    return Layer(
        layer_id, found.base_id, found.name, found.module, found.variable, cast(Any, found.kind), found.mutable,
        found.hideable, found.result_id, found.created, found.ready,
        tuple(found.fields), tuple(sorted(found.tags)),
        tuple(layer_name(tx, source) for source in found.sources),
        layer_id in (hidden if hidden is not None else hidden_closure(tx.base)),
        (layer_id in toggled) if toggled is not None else False,
        bool(found.reexamine),
        provenance(tx, layer_id) if with_provenance else None)


def version(tx: Tx, kind: str, ident: str, row: Row) -> VersionRecord:
    fields: dict[str, Any] = {key: value for key, value in row.fields.items() if key != 'held'}
    if 'extra' in fields:
        fields['extra'] = decode_extra(fields['extra'])
    if 'value' in fields and fields['value'] is not None:
        fields['value'] = json.loads(str(fields['value']))
    if kind == 'item':
        fields.update(read_first=bool(fields.get('read_first')), always_show=bool(fields.get('always_show')))
    if kind == 'join':
        fields['elements'] = [address_of(tx, element_id) or element_id
                              for element_id in held_elements(tx.base, row.seq)]
    return VersionRecord(ident, kind, row.layer_id, layer_name(tx, row.layer_id),
                         cast(Op, row.op), row.reason, row.evidence, fields,
                         read_refs(tx.base, kind, row.seq) if kind in ('item', 'property') else (), by=row.by)


def join_ends(tx: Tx, join_id: str) -> tuple[str | None, str | None]:
    """A current join's receiver and the first element it holds, by address, STORE-010: the two addresses that name
    it."""
    found = versions.current_version(tx.base, 'join', join_id)
    if found is None:
        return None, None
    first = held_elements(tx.base, found.seq)
    return address_of(tx, str(found['receiver'])), (address_of(tx, first[0]) if first else None)
