"""The current version of each thing, and what a refinement leaves behind, STORE-034, STORE-036 and LAYER-025.

Every thing keeps every row written for it. Its current row is its newest, by row order, unless that row is a
removal, which leaves it out of the current tables. The metaform is refined in its own intake layer: a refinement is
one more row of the thing in that layer, so nothing is lost and no layer is made. An element's address never
changes, MAP-015; a join can be moved to another receiver, provider or parent join and stays the same join, MAP-003.
A join's current row goes to `current_joins`, or to `current_subtypes` when it has a parent, only here, in
`insert_current`, STORE-011.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .records import Notice

METAFORM_KINDS = ('intake',)


@dataclass(frozen=True)
class Kind:
    table: str
    id_column: str
    current: str


KINDS: dict[str, Kind] = {
    'element': Kind('elements', 'element_id', 'current_elements'),
    'join': Kind('joins', 'join_id', 'current_joins'),
    'property': Kind('properties', 'property_id', 'current_properties'),
    'item': Kind('items', 'item_id', 'current_items'),
}

ORDER = ('element', 'join', 'property', 'item')


def current_tables(kind: str) -> tuple[str, ...]:
    """Where a thing's current row can be: a join's in `current_joins`, or in `current_subtypes` for a subtype
    join, STORE-011."""
    return ('current_joins', 'current_subtypes') if kind == 'join' else (KINDS[kind].current,)


def current_row(db: sqlite3.Connection, kind: str, thing_id: str) -> int | None:
    """The row number of a thing's current version, or None when it is not current."""
    spec = KINDS[kind]
    for table in current_tables(kind):
        found = db.execute(f'SELECT row FROM {table} WHERE {spec.id_column}=?', (thing_id,)).fetchone()
        if found is not None:
            return int(found[0])
    return None


def current_of_row(db: sqlite3.Connection, kind: str, row: int) -> str | None:
    """The identity id whose current version is this row, or None when the row is not a current version."""
    spec = KINDS[kind]
    for table in current_tables(kind):
        found = db.execute(f'SELECT {spec.id_column} FROM {table} WHERE row=?', (row,)).fetchone()
        if found is not None:
            return str(found[0])
    return None


def drop_current(db: sqlite3.Connection, kind: str, column: str, value: object) -> None:
    """Delete a thing's current row, by its id or by its row, from whichever current table holds it."""
    for table in current_tables(kind):
        db.execute(f'DELETE FROM {table} WHERE {column}=?', (value,))


def layer_kinds(db: sqlite3.Connection) -> dict[str, str]:
    return {row[0]: row[1] for row in db.execute('SELECT layer_id, kind FROM layers')}


def recompute(db: sqlite3.Connection, kind: str, ids: list[str]) -> None:
    """Rewrite the current rows of these things: each one's newest row, or none when that row is a removal."""
    spec = KINDS[kind]
    newest = [(thing_id, db.execute(f'SELECT * FROM {spec.table} WHERE {spec.id_column}=? ORDER BY row DESC LIMIT 1',
                                    (thing_id,)).fetchone()) for thing_id in ids]
    for thing_id, _ in newest:
        drop_current(db, kind, spec.id_column, thing_id)
    for thing_id, row in newest:
        if row is not None and row['op'] != 'remove':
            insert_current(db, kind, thing_id, row)


def hold_address(db: sqlite3.Connection, address: str, element_id: str) -> None:
    """Remember that this element is the one at this address, STORE-009: a later add there is the same element."""
    db.execute('INSERT OR REPLACE INTO address_elements(address, element_id) VALUES (?, ?)', (address, element_id))


def insert_current(db: sqlite3.Connection, kind: str, thing_id: str, row: sqlite3.Row) -> None:
    """Make a row a thing's current version. A join with a parent is a subtype join, and its current row goes to
    `current_subtypes`, never to `current_joins`: the one place this is decided, STORE-011."""
    if kind == 'element':
        db.execute('INSERT INTO current_elements(element_id, row, address, role) VALUES (?, ?, ?, ?)',
                   (thing_id, row['row'], row['address'], row['role']))
        hold_address(db, str(row['address']), thing_id)
    elif kind == 'join' and row['parent'] is not None:
        db.execute('INSERT INTO current_subtypes(join_id, row, parent, provider) VALUES (?, ?, ?, ?)',
                   (thing_id, row['row'], row['parent'], row['provider']))
    elif kind == 'join':
        db.execute('INSERT INTO current_joins(join_id, row, receiver, provider) VALUES (?, ?, ?, ?)',
                   (thing_id, row['row'], row['receiver'], row['provider']))
    elif kind == 'property':
        db.execute('INSERT INTO current_properties(property_id, row, layer_id, element_id) VALUES (?, ?, ?, ?)',
                   (thing_id, row['row'], row['layer_id'], row['element_id']))
    else:
        db.execute('INSERT INTO current_items(item_id, row, layer_id, target_kind, target_id, link_kind, link_id) '
                   'VALUES (?, ?, ?, ?, ?, ?, ?)',
                   (thing_id, row['row'], row['layer_id'], row['target_kind'], row['target_id'], row['link_kind'],
                    row['link_id']))


def _of_metaform(db: sqlite3.Connection, kinds: dict[str, str], table: str, row_number: int) -> bool:
    layer_id = db.execute(f'SELECT layer_id FROM {table} WHERE row=?', (row_number,)).fetchone()[0]
    return kinds[layer_id] in METAFORM_KINDS


def orphaned_by(db: sqlite3.Connection, kind: str, thing_id: str) -> list[Notice]:
    """STORE-034: what of the metaform is left pointing at a thing a refinement removed is orphaned and named."""
    kinds = layer_kinds(db)
    notices: list[Notice] = []
    if kind == 'element':
        for join_id, join_row in db.execute('SELECT join_id, row FROM current_joins WHERE receiver=? UNION '
                                            'SELECT join_id, row FROM current_joins WHERE provider=?',
                                            (thing_id, thing_id)).fetchall():
            if _of_metaform(db, kinds, 'joins', join_row):
                notices.append(Notice(join_id, f'Element {thing_id} was removed; join {join_id} still points at it '
                                               'and is orphaned.'))
        for join_id, join_row in db.execute('SELECT join_id, row FROM current_subtypes WHERE provider=?',
                                            (thing_id,)).fetchall():
            if _of_metaform(db, kinds, 'joins', join_row):
                notices.append(Notice(join_id, f'Element {thing_id} was removed; subtype join {join_id} still holds '
                                               'it and is orphaned.'))
        for property_id, property_row in db.execute(
                'SELECT property_id, row FROM current_properties WHERE element_id=?', (thing_id,)).fetchall():
            if _of_metaform(db, kinds, 'properties', property_row):
                notices.append(Notice(property_id, f'Element {thing_id} was removed; property {property_id} on it is '
                                                   'orphaned.'))
    elif kind == 'join':
        for join_id, join_row in db.execute('SELECT join_id, row FROM current_subtypes WHERE parent=?',
                                            (thing_id,)).fetchall():
            if _of_metaform(db, kinds, 'joins', join_row):
                notices.append(Notice(join_id, f'Join {thing_id} was removed; subtype join {join_id} in it is '
                                               'orphaned.'))
    return notices


def mark(db: sqlite3.Connection, layer_id: str, thing_id: str) -> None:
    """STORE-036: every layer built from the metaform's layer is marked for re-examination of a thing refined in it."""
    for (dependent,) in db.execute('SELECT layer_id FROM layer_sources WHERE source_layer_id=?',
                                   (layer_id,)).fetchall():
        db.execute('INSERT OR IGNORE INTO reexamine(layer_id, changed_in, thing_id) VALUES (?, ?, ?)',
                   (dependent, layer_id, thing_id))
