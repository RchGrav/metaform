"""Applying and peeling correction layers, STORE-017, STORE-034 and STORE-036.

The current tables always equal the intake map with the whole correction stack
applied in order, with every knowledge and memory layer's own rows on top.
This module keeps them so: it recomputes a thing's current row from its rows
and the stack, applies a finished correction layer, and peels the top one.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from .records import Notice, PeelChange

METAFORM_KINDS = ('intake', 'correction')
RELOCATION = 'generated: relocation'  # the evidence of a remove row that applying a relocation wrote, STORE-017


@dataclass(frozen=True)
class Kind:
    table: str
    id_column: str
    current: str


KINDS: dict[str, Kind] = {
    'element': Kind('elements', 'element_id', 'current_elements'),
    'join': Kind('joins', 'join_id', 'current_joins'),
    'subtype': Kind('subtypes', 'subtype_id', 'current_subtypes'),
    'property': Kind('properties', 'property_id', 'current_properties'),
    'item': Kind('items', 'item_id', 'current_items'),
}

ORDER = ('element', 'join', 'subtype', 'property', 'item')


def layer_kinds(db: sqlite3.Connection) -> dict[str, str]:
    return {row[0]: row[1] for row in db.execute('SELECT layer_id, kind FROM layers')}


def stack_positions(db: sqlite3.Connection) -> dict[str, int]:
    return {row[1]: row[0] for row in db.execute('SELECT position, layer_id FROM correction_stack')}


def top_position(db: sqlite3.Connection) -> int:
    row = db.execute('SELECT MAX(position) FROM correction_stack').fetchone()
    return int(row[0] or 0)


def rows_in_layer(db: sqlite3.Connection, kind: str, layer_id: str) -> list[sqlite3.Row]:
    spec = KINDS[kind]
    return db.execute(f'SELECT * FROM {spec.table} WHERE layer_id=? ORDER BY row', (layer_id,)).fetchall()


def _sequence(db: sqlite3.Connection, kind: str, thing_id: str, kinds: dict[str, str],
              positions: dict[str, int]) -> list[tuple[int, sqlite3.Row]]:
    """A thing's rows in the order they apply: the row a non-correction layer wrote, then the stack."""
    spec = KINDS[kind]
    rows = db.execute(f'SELECT * FROM {spec.table} WHERE {spec.id_column}=?', (thing_id,)).fetchall()
    ordered: list[tuple[int, sqlite3.Row]] = []
    for row in rows:
        layer_kind = kinds.get(row['layer_id'])
        if layer_kind == 'correction':
            if row['layer_id'] in positions and not unapplied(db, row['layer_id'], kind, thing_id):
                ordered.append((positions[row['layer_id']], row))
        else:
            ordered.append((0, row))
    ordered.sort(key=lambda pair: pair[0])
    return ordered


def _current_of(sequence: list[tuple[int, sqlite3.Row]]) -> tuple[sqlite3.Row | None, int]:
    """The current row, and for an element the stack position of its last address change."""
    current: sqlite3.Row | None = None
    address: str | None = None
    moved = 0
    for position, row in sequence:
        if row['op'] == 'remove':
            current = None
            continue
        if 'address' in row.keys():
            if address is not None and row['address'] != address:
                moved = position
            address = row['address']
        current = row
    return current, moved


def unapplied(db: sqlite3.Connection, layer_id: str, kind: str, thing_id: str) -> bool:
    """Whether a correction layer's row for this thing stays unapplied, BASE-044."""
    return db.execute('SELECT 1 FROM unapplied WHERE layer_id=? AND kind=? AND thing_id=?',
                      (layer_id, kind, thing_id)).fetchone() is not None


def recompute(db: sqlite3.Connection, kind: str, ids: list[str], kinds: dict[str, str],
              positions: dict[str, int]) -> None:
    """Rewrite the current rows of these things from their rows and the stack."""
    spec = KINDS[kind]
    computed: list[tuple[str, sqlite3.Row | None, int]] = []
    for thing_id in ids:
        computed.append((thing_id, *_current_of(_sequence(db, kind, thing_id, kinds, positions))))
    for thing_id, _, _ in computed:
        db.execute(f'DELETE FROM {spec.current} WHERE {spec.id_column}=?', (thing_id,))
    for thing_id, row, moved in computed:
        if row is not None:
            insert_current(db, kind, thing_id, row, moved)


def insert_current(db: sqlite3.Connection, kind: str, thing_id: str, row: sqlite3.Row, moved: int) -> None:
    if kind == 'element':
        db.execute('INSERT INTO current_elements(element_id, row, address, moved) VALUES (?, ?, ?, ?)',
                   (thing_id, row['row'], row['address'], moved))
    elif kind == 'join':
        db.execute('INSERT INTO current_joins(join_id, row, receiver, provider) VALUES (?, ?, ?, ?)',
                   (thing_id, row['row'], row['receiver'], row['provider']))
    elif kind == 'subtype':
        join_id = db.execute('SELECT join_id FROM subtype_ids WHERE subtype_id=?', (thing_id,)).fetchone()[0]
        db.execute('INSERT INTO current_subtypes(subtype_id, row, join_id, address) VALUES (?, ?, ?, ?)',
                   (thing_id, row['row'], join_id, row['address']))
    elif kind == 'property':
        db.execute('INSERT INTO current_properties(property_id, row, layer_id, element_id) VALUES (?, ?, ?, ?)',
                   (thing_id, row['row'], row['layer_id'], row['element_id']))
    else:
        db.execute('INSERT INTO current_items(item_id, row, layer_id, target_kind, target_id, link_kind, link_id) '
                   'VALUES (?, ?, ?, ?, ?, ?, ?)',
                   (thing_id, row['row'], row['layer_id'], row['target_kind'], row['target_id'], row['link_kind'],
                    row['link_id']))


def _layer_kind_of_row(db: sqlite3.Connection, kinds: dict[str, str], table: str, row_number: int) -> str:
    layer_id = db.execute(f'SELECT layer_id FROM {table} WHERE row=?', (row_number,)).fetchone()[0]
    return kinds[layer_id]


def _write_relocation_removals(db: sqlite3.Connection, layer_id: str, position: int, kinds: dict[str, str]) -> None:
    """A relocated element's joins of the metaform, and their subtypes, get remove rows in the layer, STORE-017."""
    for row in rows_in_layer(db, 'element', layer_id):
        if row['op'] != 'change':
            continue
        current = db.execute('SELECT address FROM current_elements WHERE element_id=?', (row['element_id'],)).fetchone()
        if current is None or current[0] == row['address']:
            continue
        if unapplied(db, layer_id, 'element', row['element_id']):
            continue
        reason = f'{current[0]} moved to {row["address"]}'
        joins = db.execute('SELECT join_id, row FROM current_joins WHERE receiver=? UNION '
                           'SELECT join_id, row FROM current_joins WHERE provider=?',
                           (row['element_id'], row['element_id'])).fetchall()
        for join_id, join_row in joins:
            if _layer_kind_of_row(db, kinds, 'joins', join_row) not in METAFORM_KINDS:
                continue
            if db.execute('SELECT 1 FROM joins WHERE join_id=? AND layer_id=?', (join_id, layer_id)).fetchone():
                continue
            db.execute('INSERT INTO joins(join_id, layer_id, type, receiver, provider, purpose, function, ef, relation, '
                       'verb, observation, non_goal, extra, stack_at, op, reason, evidence) '
                       'SELECT join_id, ?, type, receiver, provider, purpose, function, ef, relation, verb, observation, '
                       "non_goal, extra, ?, 'remove', ?, ? FROM joins WHERE row=?",
                       (layer_id, position, reason, RELOCATION, join_row))
            for subtype_id, subtype_row in db.execute('SELECT subtype_id, row FROM current_subtypes WHERE join_id=?',
                                                      (join_id,)).fetchall():
                if _layer_kind_of_row(db, kinds, 'subtypes', subtype_row) not in METAFORM_KINDS:
                    continue
                if db.execute('SELECT 1 FROM subtypes WHERE subtype_id=? AND layer_id=?',
                              (subtype_id, layer_id)).fetchone():
                    continue
                db.execute('INSERT INTO subtypes(subtype_id, layer_id, address, name, name_length, role, function, '
                           'ef, relation, verb, observation, extra, op, reason, evidence) '
                           'SELECT subtype_id, ?, address, name, name_length, role, function, ef, relation, verb, '
                           'observation, '
                           "extra, 'remove', ?, ? FROM subtypes WHERE row=?",
                           (layer_id, reason, RELOCATION, subtype_row))


def _touched(db: sqlite3.Connection, layer_id: str) -> dict[str, list[str]]:
    touched: dict[str, list[str]] = {}
    for kind in ORDER:
        spec = KINDS[kind]
        touched[kind] = [row[spec.id_column] for row in rows_in_layer(db, kind, layer_id)]
    return touched


def _hold_back_retypes(db: sqlite3.Connection, layer_id: str, name: str) -> list[Notice]:
    """A retype onto an address another current element keeps stays unapplied, STORE-034 and BASE-044.

    An address an earlier retype of the same layer takes is held from then on, so of two retypes onto one free
    address the first applies and the second stays unapplied.
    """
    notices: list[Notice] = []
    rows = rows_in_layer(db, 'element', layer_id)
    leaving = {row['element_id'] for row in rows if row['op'] == 'remove'}
    moving = {row['element_id']: row['address'] for row in rows if row['op'] == 'change'}
    claimed: dict[str, str] = {}
    for element_id, address in moving.items():
        current = db.execute('SELECT address FROM current_elements WHERE element_id=?', (element_id,)).fetchone()
        if current is not None and current[0] == address:
            continue
        found = db.execute('SELECT element_id FROM current_elements WHERE address=?', (address,)).fetchone()
        holder = None if found is None else str(found[0])
        if holder == element_id or holder in leaving or (holder in moving and moving[holder] != address):
            holder = None
        if holder is None and claimed.get(address, element_id) != element_id:
            holder = claimed[address]
        if holder is None:
            claimed[address] = element_id
            continue
        reason = f'{address} is held by element {holder}; this retype was not applied.'
        db.execute('INSERT OR REPLACE INTO unapplied(layer_id, kind, thing_id, reason) VALUES (?, ?, ?, ?)',
                   (layer_id, 'element', element_id, reason))
        notices.append(Notice(element_id, f'{name}: {reason}'))
    return notices


def _check(db: sqlite3.Connection, layer_id: str, name: str, kinds: dict[str, str]) -> list[Notice]:
    """STORE-034: what of the metaform is left pointing at what the layer removed is orphaned and named."""
    notices: list[Notice] = []
    for row in rows_in_layer(db, 'element', layer_id):
        if row['op'] != 'remove':
            continue
        element_id = row['element_id']
        for join_id, join_row in db.execute('SELECT join_id, row FROM current_joins WHERE receiver=? UNION '
                                            'SELECT join_id, row FROM current_joins WHERE provider=?',
                                            (element_id, element_id)).fetchall():
            if _layer_kind_of_row(db, kinds, 'joins', join_row) in METAFORM_KINDS:
                notices.append(Notice(join_id, f'{name} removed element {element_id}; join {join_id} still points '
                                               'at it and is orphaned.'))
        for property_id, property_row in db.execute(
                'SELECT property_id, row FROM current_properties WHERE element_id=?', (element_id,)).fetchall():
            if _layer_kind_of_row(db, kinds, 'properties', property_row) in METAFORM_KINDS:
                notices.append(Notice(property_id, f'{name} removed element {element_id}; property {property_id} '
                                                   'on it is orphaned.'))
    for row in rows_in_layer(db, 'join', layer_id):
        if row['op'] != 'remove':
            continue
        for subtype_id, subtype_row in db.execute('SELECT subtype_id, row FROM current_subtypes WHERE join_id=?',
                                                  (row['join_id'],)).fetchall():
            if _layer_kind_of_row(db, kinds, 'subtypes', subtype_row) in METAFORM_KINDS:
                notices.append(Notice(subtype_id, f'{name} removed join {row["join_id"]}; subtype {subtype_id} in '
                                                  'it is orphaned.'))
    return notices


def _mark(db: sqlite3.Connection, layer_id: str, touched: dict[str, list[str]], kinds: dict[str, str]) -> None:
    """STORE-036: every layer built from the layer that added a changed thing is marked for re-examination."""
    for kind, ids in touched.items():
        spec = KINDS[kind]
        for thing_id in ids:
            rows = db.execute(f'SELECT layer_id, op FROM {spec.table} WHERE {spec.id_column}=?', (thing_id,)).fetchall()
            mine = [row for row in rows if row['layer_id'] == layer_id]
            if not mine or mine[0]['op'] == 'add':
                continue
            adders = [row['layer_id'] for row in rows if row['op'] == 'add' and row['layer_id'] != layer_id]
            for source in adders:
                for (dependent,) in db.execute('SELECT layer_id FROM layer_sources WHERE source_layer_id=?',
                                               (source,)).fetchall():
                    db.execute('INSERT OR IGNORE INTO reexamine(layer_id, correction_layer_id, thing_id) '
                               'VALUES (?, ?, ?)', (dependent, layer_id, thing_id))


def apply(db: sqlite3.Connection, layer_id: str, name: str) -> list[Notice]:
    """Finish a correction layer: stack it, write its relocation removals, apply it, mark dependents.

    A row that breaks a rule of STORE-034 stays in the layer unapplied, and what the layer leaves orphaned is named;
    every other row is applied. Returns the notices, BASE-044.
    """
    kinds = layer_kinds(db)
    position = top_position(db) + 1
    notices = _hold_back_retypes(db, layer_id, name)
    _write_relocation_removals(db, layer_id, position, kinds)
    db.execute('INSERT INTO correction_stack(position, layer_id) VALUES (?, ?)', (position, layer_id))
    positions = stack_positions(db)
    touched = _touched(db, layer_id)
    for kind in ORDER:
        recompute(db, kind, touched[kind], kinds, positions)
    notices += _check(db, layer_id, name, kinds)
    _mark(db, layer_id, touched, kinds)
    return notices


def peel(db: sqlite3.Connection, layer_id: str) -> None:
    """Take the top correction layer off the stack and recompute everything it touched.

    The remove rows that applying a relocation wrote, and the marks of rows it left unapplied, are deleted, so
    finishing the layer again derives them from its content as it is then, STORE-017.
    """
    kinds = layer_kinds(db)
    db.execute('DELETE FROM correction_stack WHERE layer_id=?', (layer_id,))
    positions = stack_positions(db)
    touched = _touched(db, layer_id)
    for table in ('joins', 'subtypes'):
        for row in db.execute(f"SELECT row FROM {table} WHERE layer_id=? AND op='remove' AND evidence=?",
                              (layer_id, RELOCATION)).fetchall():
            db.execute("DELETE FROM refs WHERE owner=? AND owner_row=?", (table[:-1], row[0]))
            db.execute(f'DELETE FROM {table} WHERE row=?', (row[0],))
    db.execute('DELETE FROM unapplied WHERE layer_id=?', (layer_id,))
    for kind in ORDER:
        recompute(db, kind, touched[kind], kinds, positions)
    _mark(db, layer_id, touched, kinds)


def _address(db: sqlite3.Connection, element_id: str) -> str:
    current = db.execute('SELECT address FROM current_elements WHERE element_id=?', (element_id,)).fetchone()
    if current is not None:
        return str(current[0])
    latest = db.execute('SELECT address FROM elements WHERE element_id=? ORDER BY row DESC LIMIT 1',
                        (element_id,)).fetchone()
    return str(latest[0]) if latest else element_id


def _what(db: sqlite3.Connection, kind: str, row: sqlite3.Row) -> str:
    if kind in ('element', 'subtype'):
        return str(row['address'])
    if kind == 'join':
        return f"{_address(db, str(row['receiver']))} -> {_address(db, str(row['provider']))}"
    if kind == 'property':
        return f"{_address(db, str(row['element_id']))}: {_text(str(row['value']))}"
    return _text(str(row['value']))


def _text(value: str) -> str:
    try:
        decoded = json.loads(value)
    except ValueError:
        return value
    return decoded if isinstance(decoded, str) else json.dumps(decoded, ensure_ascii=False)


def preview(db: sqlite3.Connection, layer_id: str) -> list[PeelChange]:
    """What peeling this stacked correction layer would change, from its own rows, writing nothing, VIEW-014.

    What it added disappears; what it removed, the relocation removals included, comes back; an element it moved
    moves back; anything else it changed reverts. Knowledge and memory items at what it removed show again, and
    those at what it added become orphaned. A row the layer left unapplied changed nothing, so it is left out.
    """
    kinds, positions = layer_kinds(db), stack_positions(db)
    held = {(str(row[0]), str(row[1])) for row in db.execute('SELECT kind, thing_id FROM unapplied WHERE layer_id=?',
                                                               (layer_id,))}
    changes: list[PeelChange] = []
    added: list[tuple[str, str]] = []
    removed: list[tuple[str, str]] = []
    for kind in ORDER:
        spec = KINDS[kind]
        for row in rows_in_layer(db, kind, layer_id):
            thing = str(row[spec.id_column])
            if (kind, thing) in held:
                continue
            what = _what(db, kind, row)
            if row['op'] == 'add':
                changes.append(PeelChange(kind, thing, what, 'disappears'))
                added.append((kind, thing))
            elif row['op'] == 'remove':
                changes.append(PeelChange(kind, thing, what, 'comes back',
                                          'the move removed it' if row['evidence'] == RELOCATION else None))
                removed.append((kind, thing))
            else:
                earlier = [earlier for position, earlier in _sequence(db, kind, thing, kinds, positions)
                           if position < positions.get(layer_id, 0)]
                before = earlier[-1] if earlier else None
                if kind == 'element' and before is not None and before['address'] != row['address']:
                    changes.append(PeelChange(kind, thing, what, 'moves back',
                                              f"from {row['address']} to {before['address']}"))
                else:
                    changes.append(PeelChange(kind, thing, what, 'reverts'))
    for effect, things in (('shows again', removed), ('becomes orphaned', added)):
        for kind, thing in things:
            if kind not in ('element', 'join', 'subtype'):
                continue
            for item in db.execute('SELECT i.item_id, i.value, i.layer_id FROM current_items c JOIN items i '
                                   'ON i.row = c.row WHERE c.target_kind=? AND c.target_id=?', (kind, thing)).fetchall():
                if kinds.get(str(item[2])) not in METAFORM_KINDS:  # an element's own name and role go with it
                    changes.append(PeelChange('item', str(item[0]), _text(str(item[1])), effect))
    return changes
