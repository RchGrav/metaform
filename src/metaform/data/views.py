"""Building the records the data access object returns, from rows, STORE-023 and STORE-025.

Every builder works inside one open transaction. A builder given a `Resolver`
builds for a read in context: it leaves out what the selection does not reach,
STORE-019. Without one it builds for a raw read, and marks what is orphaned,
STORE-017. Every element and join, subtype joins included, carries the conditions
of its open work records, STORE-042, in context and raw alike, since a work record
has no layer.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, cast

from . import prompts, versions
from .ids import decode_extra
from .names import reading, short_name
from .records import (
    Element,
    Item,
    Join,
    Layer,
    Message,
    Node,
    Notice,
    Op,
    Property,
    Provenance,
    Ref,
    Report,
    Step,
    Subtype,
    Version,
    VersionRef,
    WorkLink,
    WorkRecord,
)
from .rows import (
    address_of,
    layer_name,
    node_address,
    open_work,
    owner_address,
    read_refs,
    target_current,
    whole_number,
)
from .selection import LayerRow, Resolver, all_layers, hidden_closure
from .session import Tx
from .versions import METAFORM_KINDS

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
                   state='plan' if plan else None, open_work=open_work(tx, 'element', element_id), name=current['name'])


def join_orphaned(tx: Tx, row: Row) -> bool:
    """A join with an end that is not current, STORE-017: its receiver or provider, or for a subtype join its parent
    join or the element it holds."""
    if row['parent'] is not None and not target_current(tx, 'join', str(row['parent'])):
        return True
    return any(end is not None and address_of(tx, str(end)) is None for end in (row['receiver'], row['provider']))


def join(tx: Tx, row: Row, layers: dict[str, LayerRow], orphaned: bool = False) -> Join:
    plan = None
    for end in (row['provider'], row['receiver']):
        found = tx.db.execute('SELECT join_id FROM plans WHERE element_id=?', (end,)).fetchone()
        if found is not None and found[0] == row['join_id']:
            plan = 'plan'
    receiver_address = address_of(tx, str(row['receiver']))
    return Join(str(row['join_id']), str(row['layer_id']), layers[row['layer_id']].name, str(row['type']),
                str(row['receiver']), receiver_address, str(row['provider']), address_of(tx, str(row['provider'])),
                row['name'], row['purpose'], row['ef'], row['perspective'], row['relation'], row['verb'], row['observation'], row['non_goal'],
                read_refs(tx.db, 'join', row['row']), decode_extra(row['extra']), plan, orphaned,
                open_work(tx, 'join', str(row['join_id'])), ifd=row['ifd'])


def visible_join(tx: Tx, row: Row, res: Resolver | None) -> Join | None:
    """A join as a raw read returns it, or in context only when its layer reaches its receiver, STORE-025."""
    orphaned = join_orphaned(tx, row)
    if res is None:
        return join(tx, row, all_layers(tx.db), orphaned)
    if orphaned or not res.reaches(str(row['layer_id']), address_of(tx, str(row['receiver']))):
        return None
    return join(tx, row, res.layers)


def subtype(tx: Tx, row: Row, layers: dict[str, LayerRow]) -> Subtype:
    """A subtype join, STORE-011: its own fields and layer, with the element it holds, an ordinary element record read
    by its id, MAP-030."""
    element_id = str(row['provider'])
    held = tx.db.execute('SELECT e.address, e.name_length, e.role, e.name FROM current_elements c JOIN elements e '
                         'ON e.row = c.row WHERE c.element_id=?', (element_id,)).fetchone()
    if held is None:
        held = tx.db.execute('SELECT address, name_length, role, name FROM elements WHERE element_id=? ORDER BY row DESC '
                             'LIMIT 1', (element_id,)).fetchone()
    address = None if held is None else str(held['address'])
    length = held['name_length'] if held is not None and whole_number(held['name_length']) else None
    return Subtype(str(row['join_id']), str(row['parent']), str(row['layer_id']), layers[row['layer_id']].name,
                   str(row['type']), element_id, address, reading(address) if address else '',
                   short_name(address, length) if address else '', row['name'], length,
                   None if held is None else held['role'], row['purpose'], row['ef'], row['perspective'], row['relation'],
                   row['verb'],
                   row['observation'], row['non_goal'], read_refs(tx.db, 'join', row['row']),
                   decode_extra(row['extra']), join_orphaned(tx, row), open_work(tx, 'join', str(row['join_id'])),
                   ifd=row['ifd'], element_name=None if held is None else held['name'])


def visible_subtype(tx: Tx, row: Row, res: Resolver | None) -> Subtype | None:
    """A subtype join as a raw read returns it, or in context only when its parent join is shown, its own layer
    reaches its parent's receiver and the element it holds is current, STORE-025."""
    if res is None:
        return subtype(tx, row, all_layers(tx.db))
    parent = tx.db.execute('SELECT j.* FROM current_joins c JOIN joins j ON j.row = c.row WHERE c.join_id=?',
                           (row['parent'],)).fetchone()
    if parent is None or visible_join(tx, parent, res) is None:
        return None
    at = owner_address(tx, row)
    if at is None or join_orphaned(tx, row) or not res.reaches(str(row['layer_id']), at):
        return None
    return subtype(tx, row, res.layers)


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
        provenance(tx, layer_id) if with_provenance else None)


def version(tx: Tx, kind: str, row: Row) -> Version:
    spec = versions.KINDS[kind]
    fields: dict[str, Any] = {key: row[key] for key in row.keys()
                              if key not in ('row', spec.id_column, 'layer_id', 'op', 'reason', 'evidence')}
    if 'extra' in fields:
        fields['extra'] = decode_extra(fields['extra'])
    if 'value' in fields and fields['value'] is not None:
        fields['value'] = json.loads(str(fields['value']))
    return Version(str(row[spec.id_column]), kind, str(row['layer_id']), layer_name(tx, str(row['layer_id'])),
                   cast(Op, row['op']), row['reason'], row['evidence'], fields,
                   read_refs(tx.db, kind, row['row']))


def work_record(tx: Tx, row: Row, notices: tuple[Notice, ...] = ()) -> WorkRecord:
    """One work row as a record, with its object's address, or its join's two ends, when the object is current: a
    subtype join's receiver is its parent join's."""
    kind, thing = str(row['target_kind']), str(row['target_id'])
    address = receiver = provider = None
    if kind == 'join':
        ends = tx.db.execute('SELECT receiver, provider FROM current_joins WHERE join_id=?', (thing,)).fetchone()
        held = tx.db.execute('SELECT provider FROM current_subtypes WHERE join_id=?', (thing,)).fetchone()
        if ends is not None:
            receiver, provider = address_of(tx, str(ends[0])), address_of(tx, str(ends[1]))
        elif held is not None:
            receiver, provider = node_address(tx, 'join', thing), address_of(tx, str(held[0]))
    elif kind == 'element':
        address = node_address(tx, kind, thing)
    said = tuple(Step(int(step['number']), step['said'], str(step['at'])) for step in tx.db.execute(
        'SELECT number, said, at FROM work_steps WHERE work_id=? ORDER BY number, row', (str(row['work_id']),)))
    links = tuple(WorkLink(str(link['target_kind']), str(link['target_id']),
                           node_address(tx, str(link['target_kind']), str(link['target_id'])))
                  for link in tx.db.execute('SELECT target_kind, target_id FROM work_links WHERE work_id=? ORDER BY number',
                                            (str(row['work_id']),)))
    return WorkRecord(str(row['work_id']), kind, thing, address, receiver, provider, str(row['condition']), row['note'],
                      row['task'], bool(row['held']), bool(row['reviewed']), str(row['created']), row['done'],
                      row['resolution'], notices, row['steps'], int(row['steps_done'] or 0), said, row['taken'],
                      row['taken_by'], row['position'], links)


def message(tx: Tx, row: Row, notices: tuple[Notice, ...] = ()) -> Message:
    """One message row as a record, with its object's address or its join's two ends, as a work record has."""
    kind, thing = str(row['target_kind']), str(row['target_id'])
    address = receiver = provider = None
    if kind == 'join':
        ends = tx.db.execute('SELECT receiver, provider FROM current_joins WHERE join_id=?', (thing,)).fetchone()
        held = tx.db.execute('SELECT provider FROM current_subtypes WHERE join_id=?', (thing,)).fetchone()
        if ends is not None:
            receiver, provider = address_of(tx, str(ends[0])), address_of(tx, str(ends[1]))
        elif held is not None:
            receiver, provider = node_address(tx, 'join', thing), address_of(tx, str(held[0]))
    elif kind == 'element':
        address = node_address(tx, kind, thing)
    try:
        read: Any = json.loads(row['suggestions']) if row['suggestions'] else []
    except ValueError:
        read = []
    suggested = tuple(str(one) for one in cast(list[Any], read)) if isinstance(read, list) else ()
    return Message(str(row['message_id']), str(row['kind']), kind, thing, address, receiver, provider, row['text'],
                   suggested, row['by'], str(row['created']), row['closed'], row['answer'], notices)


def report(tx: Tx, row: Row) -> Report:
    layer_id = row['layer_id']
    return Report(str(row['report_id']), str(row['run_id']), layer_id,
                  layer_name(tx, str(layer_id)) if layer_id else None, str(row['kind']), str(row['created']),
                  int(row['size']))
