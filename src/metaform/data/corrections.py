"""Applying and peeling correction layers, STORE-017, STORE-034 and STORE-036.

The current tables always equal the intake map with the whole correction stack
applied in order, with every knowledge and memory layer's own rows on top.
This module keeps them so: it recomputes a thing's current row from its rows
and the stack, applies a finished correction layer, and peels the top one.
An element's address never changes, MAP-015; a join can be moved to another
receiver, provider or parent join and stays the same join, MAP-003. A join's
current row goes to `current_joins`, or to `current_subtypes` when it has a
parent, only here, in `insert_current`, STORE-011.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from .records import Notice, PeelChange

METAFORM_KINDS = ('intake', 'correction')


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
        if kinds.get(row['layer_id']) == 'correction':
            if row['layer_id'] in positions:
                ordered.append((positions[row['layer_id']], row))
        else:
            ordered.append((0, row))
    ordered.sort(key=lambda pair: pair[0])
    return ordered


def _current_of(sequence: list[tuple[int, sqlite3.Row]]) -> sqlite3.Row | None:
    """The current row: the last one applied, or none when that one is a removal."""
    current: sqlite3.Row | None = None
    for _, row in sequence:
        current = None if row['op'] == 'remove' else row
    return current


def recompute(db: sqlite3.Connection, kind: str, ids: list[str], kinds: dict[str, str],
              positions: dict[str, int]) -> None:
    """Rewrite the current rows of these things from their rows and the stack."""
    spec = KINDS[kind]
    computed = [(thing_id, _current_of(_sequence(db, kind, thing_id, kinds, positions))) for thing_id in ids]
    for thing_id, _ in computed:
        drop_current(db, kind, spec.id_column, thing_id)
    for thing_id, row in computed:
        if row is not None:
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


def _layer_kind_of_row(db: sqlite3.Connection, kinds: dict[str, str], table: str, row_number: int) -> str:
    layer_id = db.execute(f'SELECT layer_id FROM {table} WHERE row=?', (row_number,)).fetchone()[0]
    return kinds[layer_id]


def _touched(db: sqlite3.Connection, layer_id: str) -> dict[str, list[str]]:
    touched: dict[str, list[str]] = {}
    for kind in ORDER:
        spec = KINDS[kind]
        touched[kind] = [row[spec.id_column] for row in rows_in_layer(db, kind, layer_id)]
    return touched


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
        for join_id, join_row in db.execute('SELECT join_id, row FROM current_subtypes WHERE provider=?',
                                            (element_id,)).fetchall():
            if _layer_kind_of_row(db, kinds, 'joins', join_row) in METAFORM_KINDS:
                notices.append(Notice(join_id, f'{name} removed element {element_id}; subtype join {join_id} still '
                                               'holds it and is orphaned.'))
        for property_id, property_row in db.execute(
                'SELECT property_id, row FROM current_properties WHERE element_id=?', (element_id,)).fetchall():
            if _layer_kind_of_row(db, kinds, 'properties', property_row) in METAFORM_KINDS:
                notices.append(Notice(property_id, f'{name} removed element {element_id}; property {property_id} '
                                                   'on it is orphaned.'))
    for row in rows_in_layer(db, 'join', layer_id):
        if row['op'] != 'remove':
            continue
        for join_id, join_row in db.execute('SELECT join_id, row FROM current_subtypes WHERE parent=?',
                                            (row['join_id'],)).fetchall():
            if _layer_kind_of_row(db, kinds, 'joins', join_row) in METAFORM_KINDS:
                notices.append(Notice(join_id, f'{name} removed join {row["join_id"]}; subtype join {join_id} in '
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
    """Finish a correction layer: stack it, apply it, name what it leaves orphaned, mark dependents.

    Nothing is held back, BASE-044: every row is applied, and what the layer leaves pointing at a thing it removed is
    orphaned and named, STORE-034. Returns the notices.
    """
    kinds = layer_kinds(db)
    position = top_position(db) + 1
    db.execute('INSERT INTO correction_stack(position, layer_id) VALUES (?, ?)', (position, layer_id))
    positions = stack_positions(db)
    touched = _touched(db, layer_id)
    for kind in ORDER:
        recompute(db, kind, touched[kind], kinds, positions)
    notices = _check(db, layer_id, name, kinds)
    _mark(db, layer_id, touched, kinds)
    return notices


def peel(db: sqlite3.Connection, layer_id: str) -> None:
    """Take the top correction layer off the stack and recompute everything it touched, STORE-017."""
    kinds = layer_kinds(db)
    db.execute('DELETE FROM correction_stack WHERE layer_id=?', (layer_id,))
    positions = stack_positions(db)
    touched = _touched(db, layer_id)
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


def _ends(db: sqlite3.Connection, join_id: str) -> str:
    """A join held by a receiver, as its receiver and provider: its current row's, or its latest row's."""
    found = db.execute('SELECT receiver, provider FROM current_joins WHERE join_id=?', (join_id,)).fetchone()
    if found is None:
        found = db.execute('SELECT receiver, provider FROM joins WHERE join_id=? ORDER BY row DESC LIMIT 1',
                           (join_id,)).fetchone()
    if found is None or found[0] is None:
        return join_id
    return f'{_address(db, str(found[0]))} -> {_address(db, str(found[1]))}'


def _join_what(db: sqlite3.Connection, row: sqlite3.Row) -> str:
    """A join as a person reads it: receiver -> provider; a subtype join as its parent's ends holding its element."""
    if row['parent'] is not None:
        return f"{_ends(db, str(row['parent']))} holds {_address(db, str(row['provider']))}"
    return f"{_address(db, str(row['receiver']))} -> {_address(db, str(row['provider']))}"


def _what(db: sqlite3.Connection, kind: str, row: sqlite3.Row) -> str:
    if kind == 'element':
        return str(row['address'])
    if kind == 'join':
        return _join_what(db, row)
    if kind == 'property':
        return f"{_address(db, str(row['element_id']))}: {_text(str(row['value']))}"
    return _text(str(row['value']))


def _text(value: str) -> str:
    try:
        decoded = json.loads(value)
    except ValueError:
        return value
    return decoded if isinstance(decoded, str) else json.dumps(decoded, ensure_ascii=False)


MOVES = ('receiver', 'provider', 'parent')  # the fields whose change moves a join, MAP-003


def preview(db: sqlite3.Connection, layer_id: str) -> list[PeelChange]:
    """What peeling this stacked correction layer would change, from its own rows, writing nothing, VIEW-014.

    What it added disappears; what it removed comes back; a join it moved moves back to where it was; anything else it
    changed reverts. Knowledge and memory items at what it removed show again, and those at what it added become
    orphaned.
    """
    kinds, positions = layer_kinds(db), stack_positions(db)
    changes: list[PeelChange] = []
    added: list[tuple[str, str]] = []
    removed: list[tuple[str, str]] = []
    for kind in ORDER:
        spec = KINDS[kind]
        for row in rows_in_layer(db, kind, layer_id):
            thing = str(row[spec.id_column])
            what = _what(db, kind, row)
            if row['op'] == 'add':
                changes.append(PeelChange(kind, thing, what, 'disappears'))
                added.append((kind, thing))
            elif row['op'] == 'remove':
                changes.append(PeelChange(kind, thing, what, 'comes back'))
                removed.append((kind, thing))
            else:
                earlier = [earlier for position, earlier in _sequence(db, kind, thing, kinds, positions)
                           if position < positions.get(layer_id, 0)]
                before = earlier[-1] if earlier else None
                if kind == 'join' and before is not None and any(before[field] != row[field] for field in MOVES):
                    changes.append(PeelChange(kind, thing, what, 'moves back', f'to {_join_what(db, before)}'))
                else:
                    changes.append(PeelChange(kind, thing, what, 'reverts'))
    for effect, things in (('shows again', removed), ('becomes orphaned', added)):
        for kind, thing in things:
            if kind not in ('element', 'join'):
                continue
            for item in db.execute('SELECT i.item_id, i.value, i.layer_id FROM current_items c JOIN items i '
                                   'ON i.row = c.row WHERE c.target_kind=? AND c.target_id=?', (kind, thing)).fetchall():
                if kinds.get(str(item[2])) not in METAFORM_KINDS:  # the metaform's own items go with the thing
                    changes.append(PeelChange('item', str(item[0]), _text(str(item[1])), effect))
    return changes
