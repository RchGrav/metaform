"""Applying and peeling correction layers, STORE-017, STORE-034 and STORE-036.

The current tables always equal the intake map with the whole correction stack
applied in order, with every knowledge and memory layer's own rows on top.
This module keeps them so: it recomputes a thing's current row from its rows
and the stack, applies a finished correction layer, and peels the top one.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from ..errors import StoreError

METAFORM_KINDS = ('intake', 'correction')


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
            if row['layer_id'] in positions:
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


def recompute(db: sqlite3.Connection, kind: str, ids: list[str], kinds: dict[str, str],
              positions: dict[str, int]) -> None:
    """Rewrite the current rows of these things from their rows and the stack."""
    spec = KINDS[kind]
    computed = []
    for thing_id in ids:
        computed.append((thing_id, *_current_of(_sequence(db, kind, thing_id, kinds, positions))))
    for thing_id, _, _ in computed:
        db.execute(f'DELETE FROM {spec.current} WHERE {spec.id_column}=?', (thing_id,))
    for thing_id, row, moved in computed:
        if row is None:
            continue
        try:
            insert_current(db, kind, thing_id, row, moved)
        except sqlite3.IntegrityError:
            if kind == 'element':
                raise StoreError(f'{row["address"]} is already held by another current element.',
                                 'metaform map stack') from None
            raise


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
        reason = f'{current[0]} moved to {row["address"]}'
        joins = db.execute('SELECT join_id, row FROM current_joins WHERE receiver=? UNION '
                           'SELECT join_id, row FROM current_joins WHERE provider=?',
                           (row['element_id'], row['element_id'])).fetchall()
        for join_id, join_row in joins:
            if _layer_kind_of_row(db, kinds, 'joins', join_row) not in METAFORM_KINDS:
                continue
            if db.execute('SELECT 1 FROM joins WHERE join_id=? AND layer_id=?', (join_id, layer_id)).fetchone():
                continue
            db.execute('INSERT INTO joins(join_id, layer_id, type, receiver, provider, purpose, function, relation, '
                       'observation, non_goal, extra, stack_at, op, reason) '
                       'SELECT join_id, ?, type, receiver, provider, purpose, function, relation, observation, '
                       "non_goal, extra, ?, 'remove', ? FROM joins WHERE row=?",
                       (layer_id, position, reason, join_row))
            for subtype_id, subtype_row in db.execute('SELECT subtype_id, row FROM current_subtypes WHERE join_id=?',
                                                      (join_id,)).fetchall():
                if _layer_kind_of_row(db, kinds, 'subtypes', subtype_row) not in METAFORM_KINDS:
                    continue
                if db.execute('SELECT 1 FROM subtypes WHERE subtype_id=? AND layer_id=?',
                              (subtype_id, layer_id)).fetchone():
                    continue
                db.execute('INSERT INTO subtypes(subtype_id, layer_id, address, name, name_length, role, function, '
                           'relation, observation, extra, op, reason) '
                           'SELECT subtype_id, ?, address, name, name_length, role, function, relation, observation, '
                           "extra, 'remove', ? FROM subtypes WHERE row=?", (layer_id, reason, subtype_row))


def _touched(db: sqlite3.Connection, layer_id: str) -> dict[str, list[str]]:
    touched: dict[str, list[str]] = {}
    for kind in ORDER:
        spec = KINDS[kind]
        touched[kind] = [row[spec.id_column] for row in rows_in_layer(db, kind, layer_id)]
    return touched


def _check(db: sqlite3.Connection, layer_id: str, name: str, kinds: dict[str, str]) -> None:
    """STORE-034: nothing of the metaform is left pointing at what the layer removed."""
    step = f'metaform map knowledge op=correct layer={name} id={{}} remove=true reason=<why>'
    for row in rows_in_layer(db, 'element', layer_id):
        if row['op'] != 'remove':
            continue
        element_id = row['element_id']
        for join_id, join_row in db.execute('SELECT join_id, row FROM current_joins WHERE receiver=? UNION '
                                            'SELECT join_id, row FROM current_joins WHERE provider=?',
                                            (element_id, element_id)).fetchall():
            if _layer_kind_of_row(db, kinds, 'joins', join_row) in METAFORM_KINDS:
                raise StoreError(f'Finishing {name} would leave join {join_id} pointing at removed element '
                                 f'{element_id}.', step.format(join_id))
        for property_id, property_row in db.execute(
                'SELECT property_id, row FROM current_properties WHERE element_id=?', (element_id,)).fetchall():
            if _layer_kind_of_row(db, kinds, 'properties', property_row) in METAFORM_KINDS:
                raise StoreError(f'Finishing {name} would leave property {property_id} on removed element '
                                 f'{element_id}.', step.format(property_id))
    for row in rows_in_layer(db, 'join', layer_id):
        if row['op'] != 'remove':
            continue
        for subtype_id, subtype_row in db.execute('SELECT subtype_id, row FROM current_subtypes WHERE join_id=?',
                                                  (row['join_id'],)).fetchall():
            if _layer_kind_of_row(db, kinds, 'subtypes', subtype_row) in METAFORM_KINDS:
                raise StoreError(f'Finishing {name} would leave subtype {subtype_id} in removed join '
                                 f'{row["join_id"]}.', step.format(subtype_id))


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


def apply(db: sqlite3.Connection, layer_id: str, name: str) -> None:
    """Finish a correction layer: stack it, write its relocation removals, apply it, check it, mark dependents."""
    kinds = layer_kinds(db)
    position = top_position(db) + 1
    _write_relocation_removals(db, layer_id, position, kinds)
    db.execute('INSERT INTO correction_stack(position, layer_id) VALUES (?, ?)', (position, layer_id))
    positions = stack_positions(db)
    touched = _touched(db, layer_id)
    for kind in ORDER:
        recompute(db, kind, touched[kind], kinds, positions)
    _check(db, layer_id, name, kinds)
    _mark(db, layer_id, touched, kinds)


def peel(db: sqlite3.Connection, layer_id: str) -> None:
    """Take the top correction layer off the stack and recompute everything it touched."""
    kinds = layer_kinds(db)
    db.execute('DELETE FROM correction_stack WHERE layer_id=?', (layer_id,))
    positions = stack_positions(db)
    touched = _touched(db, layer_id)
    for kind in ORDER:
        recompute(db, kind, touched[kind], kinds, positions)
    _mark(db, layer_id, touched, kinds)
