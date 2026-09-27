"""Building the records the data access object returns, from rows, STORE-023 and STORE-025.

Every builder works inside one open transaction. A builder given a `Resolver`
builds for a read in context: it leaves out what the selection does not reach,
STORE-019. Without one it builds for a raw read, and marks what is orphaned,
STORE-017. Every element, join and subtype carries the conditions of its open
work records, STORE-042, in context and raw alike, since a work record has no layer.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, cast

from . import corrections, prompts
from .corrections import METAFORM_KINDS
from .ids import decode_extra
from .names import reading, short_name
from .records import (Element, Item, Join, Layer, Node, Notice, Op, Property, Provenance, Ref, Report, Subtype, Version,
                      VersionRef, WorkRecord)
from .rows import (address_of, layer_name, node_address, open_work, read_refs, target_current, whole_number)
from .selection import LayerRow, Resolver, all_layers, hidden_closure
from .session import Tx

Row = sqlite3.Row


def element_shows(res: Resolver, layer_id: str, address: str) -> bool:
    """An element of the metaform is always a node; one a knowledge layer created shows where its layer does."""
    found = res.layers.get(layer_id)
    if found is not None and found.kind in METAFORM_KINDS:
        return found.finished
    return res.reaches(layer_id, address)


def element(tx: Tx, element_id: str, res: Resolver | None, layers: dict[str, LayerRow] | None = None) -> Element | None:
    """An element as its current row holds it: its address, name_length and role, STORE-009, with its reading and its
    short name, the address read through name_length, MAP-012; in context, only when its layer reaches its address."""
    current = tx.db.execute('SELECT c.address, e.* FROM current_elements c JOIN elements e ON e.row = c.row '
                            'WHERE c.element_id=?', (element_id,)).fetchone()
    if current is None:
        return None
    known = layers or (res.layers if res else all_layers(tx.db))
    address = str(current['address'])
    if res is not None and not element_shows(res, str(current['layer_id']), address):
        return None
    length = current['name_length'] if whole_number(current['name_length']) else None
    plan = tx.db.execute('SELECT 1 FROM plans WHERE element_id=?', (element_id,)).fetchone()
    return Element(element_id, address, str(current['layer_id']), known[current['layer_id']].name,
                   reading(address), short_name(address, length), length, current['role'],
                   read_refs(tx.db, 'element', current['row']), decode_extra(current['extra']),
                   state='plan' if plan else None, open_work=open_work(tx, 'element', element_id))


def join_orphaned(tx: Tx, row: Row, layers: dict[str, LayerRow]) -> bool:
    """A join with an end that is not current, or a knowledge join whose end moved after it, STORE-017."""
    ends = [tx.db.execute('SELECT moved FROM current_elements WHERE element_id=?', (end,)).fetchone()
            for end in (row['receiver'], row['provider'])]
    if any(end is None for end in ends):
        return True
    if layers[row['layer_id']].kind in METAFORM_KINDS:
        return False
    return any(int(end[0]) > int(row['stack_at']) for end in ends if end is not None)


def join(tx: Tx, row: Row, layers: dict[str, LayerRow], orphaned: bool = False, res: Resolver | None = None) -> Join:
    plan = None
    for end in (row['provider'], row['receiver']):
        found = tx.db.execute('SELECT join_id FROM plans WHERE element_id=?', (end,)).fetchone()
        if found is not None and found[0] == row['join_id']:
            plan = 'plan'
    receiver_address = address_of(tx, str(row['receiver']))
    return Join(str(row['join_id']), str(row['layer_id']), layers[row['layer_id']].name, str(row['type']),
                str(row['receiver']), receiver_address, str(row['provider']), address_of(tx, str(row['provider'])),
                row['name'], row['purpose'], row['function'], row['ef'], row['relation'], row['verb'], row['observation'], row['non_goal'],
                read_refs(tx.db, 'join', row['row']), decode_extra(row['extra']), plan, orphaned,
                open_work(tx, 'join', str(row['join_id'])))


def visible_join(tx: Tx, row: Row, res: Resolver | None) -> Join | None:
    """A join as a raw read returns it, or in context only when its layer reaches its receiver, STORE-025."""
    orphaned = join_orphaned(tx, row, res.layers if res else all_layers(tx.db))
    if res is None:
        return join(tx, row, all_layers(tx.db), orphaned)
    if orphaned or not res.reaches(str(row['layer_id']), address_of(tx, str(row['receiver']))):
        return None
    return join(tx, row, res.layers, res=res)


def subtype(tx: Tx, row: Row, join_id: str, layers: dict[str, LayerRow], res: Resolver | None = None) -> Subtype:
    join_row = tx.db.execute('SELECT j.layer_id FROM current_joins c JOIN joins j ON j.row = c.row '
                             'WHERE c.join_id=?', (join_id,)).fetchone()
    layer_id = str(join_row[0]) if join_row is not None else str(row['layer_id'])
    address = str(row['address'])
    length = row['name_length'] if whole_number(row['name_length']) else None
    return Subtype(str(row['subtype_id']), join_id, layer_id, layers[layer_id].name, address, reading(address),
                   short_name(address, length), row['name'], row['name_length'], row['role'], row['function'],
                   row['ef'], row['relation'], row['verb'], row['observation'], read_refs(tx.db, 'subtype', row['row']),
                   decode_extra(row['extra']), open_work(tx, 'subtype', str(row['subtype_id'])))


def item(tx: Tx, row: Row, layers: dict[str, LayerRow]) -> Item:
    state_row = tx.db.execute('SELECT state FROM challenge_states WHERE item_id=?', (row['item_id'],)).fetchone()
    orphaned = not target_current(tx, str(row['target_kind']), str(row['target_id']))
    return Item(str(row['item_id']), str(row['layer_id']), layers[row['layer_id']].name,
                Node.of(str(row['target_kind']), str(row['target_id'])), json.loads(str(row['value'])),
                Node.of(str(row['link_kind']), str(row['link_id'])) if row['link_kind'] else None,
                read_refs(tx.db, 'item', row['row']), decode_extra(row['extra']),
                str(state_row[0]) if state_row else None, orphaned)


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
    refs = tuple(Ref(str(ref[0]), str(ref[1])) for ref in tx.db.execute(
        'SELECT kind, report_id FROM reports WHERE layer_id=? ORDER BY kind, report_id', (layer_id,)))
    used = prompts.use_of(tx.project_id, tx.metaform_id, layer_id) if tx.metaform_id else None
    return Provenance(str(row['layer_id']), str(row['module']), row['workflow'], row['prompt'], row['model'],
                      row['role'], None if row['blinded'] is None else bool(row['blinded']), refs,
                      VersionRef(used.name, used.number, used.version_id) if used else None)


def layer(tx: Tx, found: LayerRow, *, toggled: frozenset[str] | None = None, hidden: set[str] | None = None,
          with_provenance: bool = False) -> Layer:
    db = tx.db
    layer_id = found.layer_id
    position = db.execute('SELECT position FROM correction_stack WHERE layer_id=?', (layer_id,)).fetchone()
    return Layer(
        layer_id, found.metaform_id, found.name, found.module, found.variable, found.kind, found.mutable,
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
        int(position[0]) if position else None,
        provenance(tx, layer_id) if with_provenance else None)


def version(tx: Tx, kind: str, row: Row, positions: dict[str, int]) -> Version:
    spec = corrections.KINDS[kind]
    fields: dict[str, Any] = {key: row[key] for key in row.keys()
                              if key not in ('row', spec.id_column, 'layer_id', 'op', 'reason', 'evidence')}
    if 'extra' in fields:
        fields['extra'] = decode_extra(fields['extra'])
    if 'value' in fields and fields['value'] is not None:
        fields['value'] = json.loads(str(fields['value']))
    return Version(str(row[spec.id_column]), kind, str(row['layer_id']), layer_name(tx, str(row['layer_id'])),
                   positions.get(str(row['layer_id'])), cast(Op, row['op']), row['reason'], row['evidence'], fields,
                   read_refs(tx.db, kind, row['row']))


def work_record(tx: Tx, row: Row, notices: tuple[Notice, ...] = ()) -> WorkRecord:
    """One work row as a record, with its object's address, or its join's two ends, when the object is current."""
    kind, thing = str(row['target_kind']), str(row['target_id'])
    address = receiver = provider = None
    if kind == 'join':
        ends = tx.db.execute('SELECT receiver, provider FROM current_joins WHERE join_id=?', (thing,)).fetchone()
        if ends is not None:
            receiver, provider = address_of(tx, str(ends[0])), address_of(tx, str(ends[1]))
    elif kind in ('element', 'subtype'):
        address = node_address(tx, kind, thing)
    return WorkRecord(str(row['work_id']), kind, thing, address, receiver, provider, str(row['condition']), row['note'],
                      row['task'], bool(row['held']), bool(row['reviewed']), str(row['created']), row['done'],
                      row['resolution'], notices)


def report(tx: Tx, row: Row) -> Report:
    layer_id = row['layer_id']
    return Report(str(row['report_id']), str(row['run_id']), layer_id,
                  layer_name(tx, str(layer_id)) if layer_id else None, str(row['kind']), str(row['created']),
                  int(row['size']))
