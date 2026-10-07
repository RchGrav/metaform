"""Building the records the data access object returns, from rows, STORE-023 and STORE-025.

Every builder works inside one open transaction. A builder given a `Resolver`
builds for a read in context: it leaves out what the selection does not reach,
STORE-019. Without one it builds for a raw read, and marks what is orphaned,
STORE-017. Every element and join carries the conditions
of its open work records, STORE-042, in context and raw alike, since a work record
has no layer.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, cast

from . import operations, prompts, versions
from .ids import decode_extra
from .names import reading, short_name
from .records import Element, Held, Item, Join, Layer, Node, Op, Property, Provenance, Version, VersionRef
from .rows import address_of, held_elements, layer_name, read_refs, target_current, whole_number
from .selection import LayerRow, Resolver, all_layers, hidden_closure
from .session import Tx
from .versions import BASE_KINDS

Row = sqlite3.Row


def element_shows(res: Resolver, layer_id: str, address: str) -> bool:
    """An element of the metaform is always a node; one a knowledge layer created shows where its layer does."""
    found = res.layers.get(layer_id)
    if found is not None and found.kind in BASE_KINDS:
        return found.finished
    return res.reaches(layer_id, address)


def element(tx: Tx, element_id: str, res: Resolver | None, layers: dict[str, LayerRow] | None = None) -> Element | None:
    """An element as its current row holds it: its address, name_length, name and role, STORE-009, with its reading
    and its short name, the address read through name_length, MAP-012; in context, only when its layer reaches its
    address."""
    current = tx.db.execute('SELECT c.address, e.* FROM current_elements c JOIN elements e ON e.row = c.row '
                            'WHERE c.element_id=?', (element_id,)).fetchone()
    if current is None:
        return None
    known = layers or (res.layers if res else all_layers(tx.db))
    address = str(current['address'])
    if res is not None and not element_shows(res, str(current['layer_id']), address):
        return None
    length = current['name_length'] if whole_number(current['name_length']) else None
    return operations.decorate(tx, Element(element_id, address, str(current['layer_id']), known[current['layer_id']].name,
                   reading(address), short_name(address, length), current['name_length'], current['role'],
                   name=current['name']))


def held(tx: Tx, join_row: int) -> tuple[Held, ...]:
    """The elements one version of a join holds, in order, each as its current row holds it, or its last row when it
    is not current."""
    found: list[Held] = []
    for element_id in held_elements(tx.db, join_row):
        row = tx.db.execute('SELECT e.address, e.name_length, e.name, e.role FROM current_elements c JOIN elements e '
                            'ON e.row = c.row WHERE c.element_id=?', (element_id,)).fetchone()
        if row is None:
            row = tx.db.execute('SELECT address, name_length, name, role FROM elements WHERE element_id=? '
                                'ORDER BY row DESC LIMIT 1', (element_id,)).fetchone()
        if row is None:
            found.append(Held(element_id, None))
            continue
        length = row['name_length'] if whole_number(row['name_length']) else None
        found.append(Held(element_id, str(row['address']), short_name(str(row['address']), length),
                          row['name_length'], row['name'], row['role']))
    return tuple(found)


def join_orphaned(tx: Tx, row: Row) -> bool:
    """A join with an end that is not current, STORE-017: its receiver or an element it holds."""
    ends = [str(row['receiver']), *held_elements(tx.db, int(row['row']))]
    return any(address_of(tx, end) is None for end in ends)


def join(tx: Tx, row: Row, layers: dict[str, LayerRow], orphaned: bool = False) -> Join:
    return operations.decorate(tx, Join(str(row['join_id']), str(row['layer_id']), layers[row['layer_id']].name,
                str(row['type']), str(row['receiver']), address_of(tx, str(row['receiver'])), row['purpose'],
                row['ef'], row['ifd'], held(tx, int(row['row'])), None, orphaned, element=row['element']))


def visible_join(tx: Tx, row: Row, res: Resolver | None) -> Join | None:
    """A join as a raw read returns it, or in context only when its layer reaches its receiver, STORE-025."""
    orphaned = join_orphaned(tx, row)
    if res is None:
        return join(tx, row, all_layers(tx.db), orphaned)
    if orphaned or not res.reaches(str(row['layer_id']), address_of(tx, str(row['receiver']))):
        return None
    return join(tx, row, res.layers)


def item(tx: Tx, row: Row, layers: dict[str, LayerRow]) -> Item:
    orphaned = not target_current(tx, str(row['target_kind']), str(row['target_id']))
    return operations.decorate(tx, Item(str(row['item_id']), str(row['layer_id']), layers[row['layer_id']].name,
                Node.of(str(row['target_kind']), str(row['target_id'])), json.loads(str(row['value'])),
                Node.of(str(row['link_kind']), str(row['link_id'])) if row['link_kind'] else None,
                read_refs(tx.db, 'item', row['row']), decode_extra(row['extra']),
                None, orphaned, bool(row['read_first']), bool(row['always_show'])))


def item_by_id(tx: Tx, item_id: str) -> Item:
    row = tx.db.execute('SELECT i.* FROM current_items c JOIN items i ON i.row = c.row WHERE c.item_id=?',
                        (item_id,)).fetchone()
    if row is None:
        row = tx.db.execute('SELECT * FROM items WHERE item_id=? ORDER BY row DESC LIMIT 1', (item_id,)).fetchone()
    return item(tx, row, all_layers(tx.db))


def prop(tx: Tx, row: Row, layers: dict[str, LayerRow]) -> Property:
    address = address_of(tx, str(row['element_id']))
    return Property(str(row['property_id']), str(row['layer_id']), layers[row['layer_id']].name,
                    str(row['element_id']), address, json.loads(str(row['value'])),
                    read_refs(tx.db, 'property', row['row']), decode_extra(row['extra']), address is None)


def provenance(tx: Tx, layer_id: str) -> Provenance | None:
    """The layer's one provenance record, with its report, feedback and shape files as refs, STORE-016."""
    row = tx.db.execute('SELECT * FROM provenance WHERE layer_id=?', (layer_id,)).fetchone()
    if row is None:
        return None
    used = prompts.use_of(tx.project_id, tx.base_id, layer_id) if tx.base_id else None
    return operations.decorate(tx, Provenance(str(row['layer_id']), str(row['module']), row['workflow'], row['prompt'], row['model'],
                      row['role'], None if row['blinded'] is None else bool(row['blinded']), (),
                      VersionRef(used.name, used.number, used.version_id) if used else None))


def layer(tx: Tx, found: LayerRow, *, toggled: frozenset[str] | None = None, hidden: set[str] | None = None,
          with_provenance: bool = False) -> Layer:
    db = tx.db
    layer_id = found.layer_id
    return Layer(
        layer_id, found.base_id, found.name, found.module, found.variable, found.kind, found.mutable,
        found.hideable, found.result_id, found.created, found.ready,
        tuple(str(row[0]) for row in db.execute('SELECT name FROM layer_fields WHERE layer_id=? ORDER BY position',
                                                (layer_id,))),
        tuple(str(row[0]) for row in db.execute('SELECT tag FROM layer_tags WHERE layer_id=? ORDER BY tag',
                                                (layer_id,))),
        tuple(layer_name(tx, str(row[0])) for row in db.execute(
            'SELECT source_layer_id FROM layer_sources WHERE layer_id=?', (layer_id,))),
        layer_id in (hidden if hidden is not None else hidden_closure(db)),
        (layer_id in toggled) if toggled is not None else False,
        db.execute('SELECT 1 FROM reexamine WHERE layer_id=? LIMIT 1', (layer_id,)).fetchone() is not None,
        provenance(tx, layer_id) if with_provenance else None)


def version(tx: Tx, kind: str, row: Row) -> Version:
    spec = versions.KINDS[kind]
    fields: dict[str, Any] = {key: row[key] for key in row.keys()  # noqa: SIM118  SQLite rows iterate values; keys() returns column names
                              if key not in ('row', spec.id_column, 'layer_id', 'op', 'reason', 'evidence')}
    if 'extra' in fields:
        fields['extra'] = decode_extra(fields['extra'])
    if 'value' in fields and fields['value'] is not None:
        fields['value'] = json.loads(str(fields['value']))
    if kind == 'item':
        fields.update(read_first=bool(fields['read_first']), always_show=bool(fields['always_show']))
    if kind == 'join':
        fields['elements'] = [address_of(tx, element_id) or element_id
                              for element_id in held_elements(tx.db, int(row['row']))]
    return Version(str(row[spec.id_column]), kind, str(row['layer_id']), layer_name(tx, str(row['layer_id'])),
                   cast(Op, row['op']), row['reason'], row['evidence'], fields,
                   read_refs(tx.db, kind, row['row']) if kind in ('item', 'property') else ())


def join_ends(tx: Tx, join_id: str) -> tuple[str | None, str | None]:
    """A current join's receiver and the first element it holds, by address, STORE-010: the two addresses that name
    it."""
    found = tx.db.execute('SELECT receiver, row FROM current_joins WHERE join_id=?', (join_id,)).fetchone()
    if found is None:
        return None, None
    first = held_elements(tx.db, int(found[1]))
    return address_of(tx, str(found[0])), (address_of(tx, first[0]) if first else None)
