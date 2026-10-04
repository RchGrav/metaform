"""Layer operations: create, finish, discard, hide, tag, select and mask, and refining the metaform, STORE-024.

Every function works inside one open write transaction. Nothing an agent sends
is refused for its content, BASE-044: an empty variable, a missing provenance,
a taken name, a tag or source that does not fit, are stored as given or
numbered, with a notice. An operation aimed at something that cannot change,
such as hiding a layer that is not hideable,
writes nothing and returns a notice saying why. A reference to no layer cannot
be read and raises `StoreError`, STORE-026.
"""
from __future__ import annotations

import dataclasses
import sqlite3
from collections.abc import Sequence
from typing import Any

from .. import home
from ..errors import StoreError
from . import operations, rows, versions, views, writes
from .ids import LAYER_NAME, TAG, is_id, new_id
from .records import Layer, Notice, Outcome, Version
from .selection import LAYER_COLUMNS, LayerRow, all_layers, layer_row
from .session import Tx
from .versions import METAFORM_KINDS

KINDS = ('layer', 'intake', 'memory')


def _free_name(tx: Tx, name: str) -> str:
    chosen, number = name, 1
    while tx.db.execute('SELECT 1 FROM layers WHERE name=?', (chosen,)).fetchone():
        number += 1
        chosen = f'{name}-{number}'
    return chosen


def _tags(tags: Sequence[Any], notices: list[Notice]) -> list[str]:
    kept: list[str] = []
    for tag in tags:
        if not isinstance(tag, str) or not 1 <= len(tag) <= 64:
            notices.append(Notice('tags', f'{tag!r} is not a tag of 1 to 64 characters; it was not stored.'))
            continue
        if not TAG.fullmatch(tag):
            notices.append(Notice('tags', f'{tag!r} is not lowercase letters, digits, ., _ and -; it was stored as '
                                          'given.'))
        kept.append(tag)
    return kept


def _sources(tx: Tx, sources: Sequence[Any], notices: list[Notice]) -> list[str]:
    found: list[str] = []
    by_name = {item.name: item.layer_id for item in all_layers(tx.db).values()}
    for source in sources:
        name = str(source)
        if name in by_name.values():
            found.append(name)
        elif name in by_name:
            found.append(by_name[name])
        else:
            notices.append(Notice('sources', f'{name} is not a layer here; it was not recorded as a source.'))
    return found


def complete(tx: Tx, name: str, provenance: dict[str, Any], result_id: str | None = None) -> Outcome:
    """Fill in what a layer still being built lacks of its provenance and its result id, LAYER-010.

    What the layer holds is kept: a different value given for it is named in a notice and not stored, so the record
    of what made the layer never changes once it says something.
    """
    row = tx.db.execute('SELECT l.layer_id, l.result_id, l.ready, p.model, p.role, p.blinded FROM layers l '
                        'LEFT JOIN provenance p ON p.layer_id=l.layer_id WHERE l.name=?', (name,)).fetchone()
    if row is None:
        raise StoreError(f'No layer {name}.', 'metaform map layers')
    notices: list[Notice] = []
    if row['ready'] is not None:
        return Outcome((Notice('layer', f'Layer {name} is finished; its provenance was kept as it is.'),))
    given = {'model': provenance.get('model'), 'role': provenance.get('role'), 'blinded': provenance.get('blinded'),
             'id': result_id}
    for key, value in given.items():
        if value is None:
            continue
        held = row['result_id' if key == 'id' else key]
        value = int(bool(value)) if key == 'blinded' else value
        if held is None:
            if key == 'id':
                tx.db.execute('UPDATE layers SET result_id=? WHERE layer_id=?', (value, row['layer_id']))
            else:
                tx.db.execute(f'UPDATE provenance SET {key}=? WHERE layer_id=?', (value, row['layer_id']))
        elif held != value:
            shown = (bool(held), bool(value)) if key == 'blinded' else (held, value)
            notices.append(Notice(key, f'The layer holds {key} {shown[0]}; {shown[1]} was given and was not stored.'))
    return Outcome(tuple(notices))


def create(tx: Tx, name: object, module: str, variable: Any, *, kind: str = 'layer', mutable: bool, hideable: bool,
           fields: Sequence[str] = (), tags: Sequence[Any] = (), provenance: dict[str, Any] | None = None,
           result_id: str | None = None, sources: Sequence[Any] = (), ready: bool = False) -> Layer:
    """Create a layer, or return the one with this name and the same declaration, STORE-024 and LAYER-002."""
    if not isinstance(name, str) or not name or is_id(name):
        raise StoreError(f'{name!r} cannot be a layer name: it would be read as an id.',
                         'metaform map knowledge op=create layer=<name> variable=<question>')
    if kind not in KINDS:
        raise StoreError(f'{kind!r} is not a layer kind: use layer, intake or memory.',
                         'metaform help map knowledge')
    notices: list[Notice] = []
    if not LAYER_NAME.fullmatch(name):
        notices.append(Notice('name', f'{name!r} is not 1 to 128 letters, digits, ., _ and -; it was stored as given.'))
    question = rows.text(variable, 'variable', notices) or ''
    if not question.strip():
        notices.append(Notice('variable', f'Layer {name} has no variable, the one question it answers; it was stored '
                                          'without one. Name it with metaform map knowledge op=create again under a '
                                          'new name, or tell the person who asked for the layer.'))
    existing = tx.db.execute(f'SELECT {LAYER_COLUMNS} FROM layers WHERE name=?', (name,)).fetchone()
    if existing is not None:
        found = layer_row(existing)
        if (found.kind, found.module, found.variable, found.mutable, found.hideable) == (
                kind, module, question, bool(mutable), bool(hideable)):
            return views.layer(tx, found)
        taken, name = name, _free_name(tx, name)
        notices.append(Notice('name', f'A layer named {taken} already exists with another declaration; this one was '
                                      f'named {name}.'))
    source_ids = _sources(tx, sources, notices)
    kept_tags = _tags(tags, notices)
    layer_id = new_id()
    stamp = home.now()
    tx.db.execute('INSERT INTO layers(layer_id, metaform_id, name, module, variable, mutable, hideable, result_id, kind, '
                  'created, ready) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                  (layer_id, tx.metaform_id, name, module, question, int(bool(mutable)), int(bool(hideable)),
                   result_id, kind, stamp, stamp if (ready or kind == 'memory') else None))
    if kind != 'memory':
        given = provenance or {}
        if not provenance:
            notices.append(Notice('provenance', f'Layer {name} was created without provenance; its record holds only '
                                                f'the module {module}.'))
        blinded = given.get('blinded')
        tx.db.execute('INSERT INTO provenance(layer_id, module, workflow, prompt, model, role, blinded) '
                      'VALUES (?, ?, ?, ?, ?, ?, ?)',
                      (layer_id, str(given.get('module') or module), given.get('workflow'), given.get('prompt'),
                       given.get('model'), given.get('role'), None if blinded is None else int(bool(blinded))))
    tx.db.executemany('INSERT INTO layer_fields(layer_id, position, name) VALUES (?, ?, ?)',
                      [(layer_id, index, str(field)) for index, field in enumerate(fields)])
    tx.db.executemany('INSERT OR IGNORE INTO layer_tags(layer_id, tag) VALUES (?, ?)',
                      [(layer_id, tag) for tag in kept_tags])
    tx.db.executemany('INSERT OR IGNORE INTO layer_sources(layer_id, source_layer_id) VALUES (?, ?)',
                      [(layer_id, source) for source in source_ids])
    tx.created.add(layer_id)
    return dataclasses.replace(views.layer(tx, rows.layer(tx, layer_id)), notices=tuple(notices))


def finish(tx: Tx, layer: str) -> Layer | Outcome:
    """Mark a layer ready, STORE-024."""
    found = rows.layer(tx, layer)
    if found.finished:
        return Outcome((Notice('layer', f'Layer {found.name} is already finished; nothing changed.'),))
    tx.db.execute('UPDATE layers SET ready=? WHERE layer_id=?', (home.now(), found.layer_id))
    return views.layer(tx, rows.layer(tx, found.layer_id))


def discard(tx: Tx, layer: str) -> Outcome:
    """Delete a knowledge layer's content and the layer; identity and type rows stay, STORE-032."""
    found = rows.layer(tx, layer)
    if found.kind == 'intake':
        return Outcome((Notice('layer', f'{found.name} is the intake layer and is never discarded; the metaform '
                                        f'changes by refining: {rows.refine_step()}. Nothing changed.'),))
    if found.kind == 'memory':
        return Outcome((Notice('layer', f'{found.name} is memory and is never discarded; remove memories with '
                                        'metaform memory delete_entities <entityNames>. Nothing changed.'),))
    db = tx.db
    layer_id = found.layer_id
    notices: list[Notice] = []
    for owner in versions.ORDER:
        spec = versions.KINDS[owner]
        for row in db.execute(f'SELECT row, {spec.id_column} FROM {spec.table} WHERE layer_id=?',
                              (layer_id,)).fetchall():
            if owner == 'element':
                heir = _heir(db, str(row[1]), layer_id)
                if heir is not None:
                    db.execute('UPDATE elements SET layer_id=? WHERE row=?', (heir, row[0]))
                    address = db.execute('SELECT address FROM elements WHERE row=?', (row[0],)).fetchone()[0]
                    notices.append(Notice('element', f'The element at {address} was made by {found.name}, and layer '
                                                     f'{rows.layer(tx, heir).name} still holds something at it; '
                                                     f'the element was kept and now belongs to '
                                                     f'{rows.layer(tx, heir).name}.'))
                    continue
            if owner in ('item', 'property'):
                db.execute('DELETE FROM refs WHERE owner=? AND owner_row=?', (owner, row[0]))
            if owner == 'join':
                db.execute('DELETE FROM join_elements WHERE join_row=?', (row[0],))
            versions.drop_current(db, owner, 'row', row[0])
            if owner == 'item':
                operations.cleanup(tx, 'item', str(row[1]))
            db.execute(f'DELETE FROM {spec.table} WHERE row=?', (row[0],))
            if owner == 'item':
                # item_ids names the item's layer, so it goes with the layer; identities keeps the id.
                db.execute('DELETE FROM item_ids WHERE item_id=? AND layer_id=?', (row[1], layer_id))
    for table in ('selections', 'hidden_layers', 'layer_tags',
                  'layer_fields', 'provenance', 'layer_sources', 'reexamine'):
        db.execute(f'DELETE FROM {table} WHERE layer_id=?', (layer_id,))
    operations.cleanup(tx, 'layer', layer_id)
    db.execute('DELETE FROM layer_sources WHERE source_layer_id=?', (layer_id,))
    for other in all_layers(db):
        db.execute('DELETE FROM reexamine WHERE layer_id=? AND changed_in=?', (other, layer_id))
    db.execute('DELETE FROM layers WHERE layer_id=?', (layer_id,))
    return Outcome(tuple(notices))


def _heir(db: sqlite3.Connection, element_id: str, leaving: str) -> str | None:
    """The first other layer that holds a property, an item or a join at the element, and no row of its own for it."""
    found = db.execute(
        'SELECT layer_id FROM ('
        ' SELECT layer_id, 0 AS kind, row FROM properties WHERE element_id=:e'
        " UNION ALL SELECT layer_id, 1, row FROM items WHERE (target_kind='element' AND target_id=:e)"
        "  OR (link_kind='element' AND link_id=:e)"
        ' UNION ALL SELECT layer_id, 2, row FROM joins WHERE receiver=:e'
        '  OR row IN (SELECT join_row FROM join_elements WHERE element_id=:e)) '
        'WHERE layer_id<>:l AND layer_id NOT IN (SELECT layer_id FROM elements WHERE element_id=:e) '
        'ORDER BY kind, row LIMIT 1', {'e': element_id, 'l': leaving}).fetchone()
    return None if found is None else str(found[0])


def _held(found: LayerRow) -> Notice | None:
    """Why a layer is not hidden: it was declared not hideable."""
    if not found.hideable:
        return Notice('layer', f'Layer {found.name} is not hideable; it was declared so when it was made. Nothing '
                               'changed.')
    return None


def hide(tx: Tx, layer: str, hidden: bool) -> Outcome:
    found = rows.layer(tx, layer)
    stop = _held(found)
    if stop is not None:
        return Outcome((stop,))
    if hidden:
        tx.db.execute('INSERT OR IGNORE INTO hidden_layers(layer_id) VALUES (?)', (found.layer_id,))
    else:
        tx.db.execute('DELETE FROM hidden_layers WHERE layer_id=?', (found.layer_id,))
    return Outcome()


def tag(tx: Tx, layer: str, name: Any) -> Outcome:
    found = rows.layer(tx, layer)
    notices: list[Notice] = []
    for kept in _tags([name], notices):
        tx.db.execute('INSERT OR IGNORE INTO layer_tags(layer_id, tag) VALUES (?, ?)', (found.layer_id, kept))
    return Outcome(tuple(notices))


def untag(tx: Tx, layer: str, name: str) -> Outcome:
    found = rows.layer(tx, layer)
    tx.db.execute('DELETE FROM layer_tags WHERE layer_id=? AND tag=?', (found.layer_id, name))
    return Outcome()


def reexamined(tx: Tx, layer: str) -> Outcome:
    found = rows.layer(tx, layer)
    tx.db.execute('DELETE FROM reexamine WHERE layer_id=?', (found.layer_id,))
    return Outcome()


def selection(tx: Tx, address: str, layer: str, kind: str) -> Outcome:
    """A select or mask row at an address, STORE-019."""
    found = rows.layer(tx, layer)
    notices: list[Notice] = []
    if not rows.address_form(address):
        notices.append(Notice('address', f'{address!r} is not in the address form; the {kind} was stored as given.'))
    rows.types(tx, address)
    tx.db.execute('INSERT OR IGNORE INTO selections(address, layer_id, kind) VALUES (?, ?, ?)',
                  (address, found.layer_id, kind))
    return Outcome(tuple(notices))


def clear(tx: Tx, address: str, layer: str, kind: str) -> Outcome:
    if kind not in ('select', 'mask'):
        raise StoreError(f'{kind!r} is not select or mask.', f'metaform map clear {address} {layer} mask')
    found = rows.layer(tx, layer)
    tx.db.execute('DELETE FROM selections WHERE address=? AND kind=? AND layer_id=?', (address, kind, found.layer_id))
    return Outcome()


# Refining the metaform ---------------------------------------------------------------------------------------

def refine(tx: Tx, thing: str, changes: dict[str, Any] | None = None, *, remove: bool = False, reason: Any,
           evidence: Any = None) -> Version | Outcome:
    """Write a change or removal of a thing of the metaform as its newest version, in the metaform's own intake
    layer, LAYER-025. Every earlier version is kept.

    A key a refinement may not change, such as an element's address, is named in a notice and not applied; the rest
    is written, STORE-034. A join's receiver moves it, MAP-003, and `elements` gives the elements it holds; a change
    that does not name them keeps the ones it held. What a removal leaves pointing at the removed thing is orphaned
    and named, and the layers built from the metaform are marked for re-examination, STORE-036.
    """
    kind = rows.kind_of(tx, thing)
    spec = versions.KINDS[kind]
    notices: list[Notice] = []
    given = {str(key): value for key, value in (changes or {}).items()}
    current = versions.current_row(tx.db, kind, thing)
    if current is None:
        writes.split_changes(kind, given, notices)
        return Outcome((*notices, Notice('id', f'{thing} is not current in the metaform; nothing was written. See '
                                               f'metaform map history {thing}')))
    base = tx.db.execute(f'SELECT * FROM {spec.table} WHERE row=?', (current,)).fetchone()
    found = rows.layer(tx, str(base['layer_id']))
    if found.kind not in METAFORM_KINDS:
        return Outcome((Notice('id', f'{thing} belongs to the knowledge layer {found.name}, not to the metaform; a '
                                     'knowledge layer is edited in place: metaform map knowledge '
                                     f'op=edit layer={found.name} id={thing} <field>=<value>. Nothing was '
                                     'written.'),))
    allowed = writes.split_changes(kind, given, notices)
    if not remove and given and not allowed:
        return Outcome(tuple(notices))
    columns = {key: base[key] for key in base.keys() if key not in ('row', 'layer_id', 'op', 'reason', 'evidence')}
    split: list[tuple[str, Any]] = []
    held: list[str] | None = None
    if not remove:
        changed, split = writes.changed_columns(tx, kind, allowed, found, notices, base)
        held = changed.pop(writes.HELD, None)
        columns.update(changed)
    columns.update({'layer_id': found.layer_id, 'op': 'remove' if remove else 'change',
                    'reason': rows.text(reason, 'reason', notices), 'evidence': rows.text(evidence, 'evidence', notices)})
    row = _version(tx, spec.table, columns)
    if kind == 'join':
        rows.write_held(tx, row, held if held is not None else rows.held_elements(tx.db, current))
    if remove:
        notices += versions.orphaned_by(tx.db, kind, thing)
    versions.recompute(tx.db, kind, [thing])
    versions.mark(tx.db, found.layer_id, thing)
    if split:
        notices.append(Notice('extra', 'A refinement keeps no list of records in its extra; those records were not '
                                       'written.'))
    record = views.version(tx, kind, tx.db.execute(f'SELECT * FROM {spec.table} WHERE row=?', (row,)).fetchone())
    return dataclasses.replace(record, notices=tuple(notices))


def _version(tx: Tx, table: str, columns: dict[str, Any]) -> int:
    names = ', '.join(columns)
    marks = ', '.join('?' for _ in columns)
    cursor = tx.db.execute(f'INSERT INTO {table}({names}) VALUES ({marks})', tuple(columns.values()))
    return int(cursor.lastrowid or 0)
