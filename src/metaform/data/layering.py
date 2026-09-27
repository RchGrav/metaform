"""Layer operations: create, finish, discard, hide, tag, select and mask, and the correction stack, STORE-024.

Every function works inside one open write transaction. Nothing an agent sends
is refused for its content, BASE-044: an empty variable, a missing provenance,
a taken name, a tag or source that does not fit, are stored as given or
numbered, with a notice. An operation aimed at something that cannot change,
such as hiding a layer that is not hideable or selecting a correction layer,
writes nothing and returns a notice saying why. A reference to no layer cannot
be read and raises `StoreError`, STORE-026.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from typing import Any

from .. import home
from ..errors import StoreError
from . import corrections, rows, views, writes
from .corrections import METAFORM_KINDS
from .ids import LAYER_NAME, TAG, is_id, new_id, refs_fit
from .records import Layer, Notice, Outcome, Version
from .selection import LAYER_COLUMNS, LayerRow, all_layers, layer_row
from .session import Tx

KINDS = ('layer', 'intake', 'memory', 'correction')


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


def create(tx: Tx, name: object, module: str, variable: Any, *, kind: str = 'layer', mutable: bool, hideable: bool,
           fields: Sequence[str] = (), tags: Sequence[Any] = (), provenance: dict[str, Any] | None = None,
           result_id: str | None = None, sources: Sequence[Any] = (), ready: bool = False) -> Layer:
    """Create a layer, or return the one with this name and the same declaration, STORE-024 and LAYER-002."""
    if not isinstance(name, str) or not name or is_id(name):
        raise StoreError(f'{name!r} cannot be a layer name: it would be read as an id.',
                         'metaform map knowledge op=create layer=<name> variable=<question>')
    if kind not in KINDS:
        raise StoreError(f'{kind!r} is not a layer kind: use layer, intake, memory or correction.',
                         'metaform help map knowledge')
    notices: list[Notice] = []
    if not LAYER_NAME.fullmatch(name):
        notices.append(Notice('name', f'{name!r} is not 1 to 128 letters, digits, ., _ and -; it was stored as given.'))
    question = rows.text(variable, 'variable', notices) or ''
    if not question.strip():
        notices.append(Notice('variable', f'Layer {name} has no variable, the one question it answers; it was stored '
                                          'without one. Name it with metaform map knowledge op=create again under a '
                                          'new name, or tell the person who asked for the layer.'))
    if kind == 'correction' and (mutable or hideable):
        notices.append(Notice('kind', 'A correction layer is immutable and never hideable; it was stored so.'))
        mutable = hideable = False
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
    """Mark a layer ready; a correction layer is also applied on top of the stack, STORE-017."""
    found = rows.layer(tx, layer)
    if found.finished:
        return Outcome((Notice('layer', f'Layer {found.name} is already finished; nothing changed.'),))
    notices: list[Notice] = []
    if found.kind == 'correction':
        notices = corrections.apply(tx.db, found.layer_id, found.name)
    tx.db.execute('UPDATE layers SET ready=? WHERE layer_id=?', (home.now(), found.layer_id))
    return dataclasses.replace(views.layer(tx, rows.layer(tx, found.layer_id)), notices=tuple(notices))


def discard(tx: Tx, layer: str) -> Outcome:
    """Delete a knowledge layer's content and the layer; identity and type rows stay, STORE-032."""
    found = rows.layer(tx, layer)
    if found.kind == 'intake':
        return Outcome((Notice('layer', f'{found.name} is the intake layer and is never discarded; the metaform '
                                        f'changes only through a correction layer: {rows.correct_step()}. Nothing '
                                        'changed.'),))
    if found.kind == 'memory':
        return Outcome((Notice('layer', f'{found.name} is memory and is never discarded; remove memories with '
                                        'metaform memory delete-entities <node>. Nothing changed.'),))
    if found.kind == 'correction' and tx.db.execute('SELECT 1 FROM correction_stack WHERE layer_id=?',
                                                    (found.layer_id,)).fetchone():
        return Outcome((Notice('layer', f'Correction layer {found.name} is on the stack; peel it first: metaform map '
                                        f'knowledge op=peel layer={found.name}. Nothing changed.'),))
    db = tx.db
    layer_id = found.layer_id
    for owner in corrections.ORDER:
        spec = corrections.KINDS[owner]
        for row in db.execute(f'SELECT row, {spec.id_column} FROM {spec.table} WHERE layer_id=?',
                              (layer_id,)).fetchall():
            db.execute('DELETE FROM refs WHERE owner=? AND owner_row=?', (owner, row[0]))
            corrections.drop_current(db, owner, 'row', row[0])
            if owner == 'item':
                db.execute('DELETE FROM challenge_states WHERE item_id=?', (row[1],))
            db.execute(f'DELETE FROM {spec.table} WHERE row=?', (row[0],))
            if owner == 'item':
                # item_ids names the item's layer, so it goes with the layer; identities keeps the id.
                db.execute('DELETE FROM item_ids WHERE item_id=? AND layer_id=?', (row[1], layer_id))
    for table in ('plans', 'selections', 'hidden_layers', 'layer_tags',
                  'layer_fields', 'provenance', 'layer_sources', 'reexamine'):
        db.execute(f'DELETE FROM {table} WHERE layer_id=?', (layer_id,))
    db.execute('UPDATE reports SET layer_id=NULL WHERE layer_id=?', (layer_id,))
    db.execute('DELETE FROM layer_sources WHERE source_layer_id=?', (layer_id,))
    for other in all_layers(db):
        db.execute('DELETE FROM reexamine WHERE layer_id=? AND correction_layer_id=?', (other, layer_id))
    db.execute('DELETE FROM layers WHERE layer_id=?', (layer_id,))
    return Outcome()


def _held(found: LayerRow, what: str) -> Notice | None:
    """Why a layer is not hidden, selected or masked: a correction layer is always applied, LAYER-011."""
    if found.kind == 'correction':
        return Notice('layer', f'{found.name} is a correction layer; correction layers are always applied and are '
                               f'never {what}. Nothing changed. See metaform map stack')
    if what == 'hidden' and not found.hideable:
        return Notice('layer', f'Layer {found.name} is not hideable; it was declared so when it was made. Nothing '
                               'changed.')
    return None


def hide(tx: Tx, layer: str, hidden: bool) -> Outcome:
    found = rows.layer(tx, layer)
    stop = _held(found, 'hidden')
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
    """A select or mask row at an address, STORE-019; never for a correction layer."""
    found = rows.layer(tx, layer)
    stop = _held(found, 'selected or masked')
    if stop is not None:
        return Outcome((stop,))
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
    stop = _held(found, 'selected or masked')
    if stop is not None:
        return Outcome((stop,))
    tx.db.execute('DELETE FROM selections WHERE address=? AND kind=? AND layer_id=?', (address, kind, found.layer_id))
    return Outcome()


# The correction stack ---------------------------------------------------------------------------------------

def correct(tx: Tx, layer: str, thing: str, changes: dict[str, Any] | None = None, *, remove: bool = False,
            reason: Any, evidence: Any = None) -> Version | Outcome:
    """Write a change or removal of a thing of the metaform into a building correction layer, STORE-017.

    A key a correction may not change, such as an element's address, is named in a notice and not applied; the rest of
    the correction is written, STORE-034. A join's receiver, provider and parent move it, MAP-003; a join absorbed
    into a parent passes the subtype joins of the metaform it holds to that parent in the same layer, MAP-032.
    """
    found = rows.layer(tx, layer)
    if found.kind != 'correction' or found.finished:
        return Outcome((Notice('layer', f'{found.name} is not a correction layer that is still building; nothing was '
                                        'written. Make one with metaform map knowledge op=create layer=<name> '
                                        'kind=correction mutable=false hideable=false'),))
    kind = rows.kind_of(tx, thing)
    spec = corrections.KINDS[kind]
    notices: list[Notice] = []
    given = {str(key): value for key, value in (changes or {}).items()}
    current = corrections.current_row(tx.db, kind, thing)
    if current is None:
        writes.split_changes(kind, given, notices)
        return Outcome((*notices, Notice('id', f'{thing} is not current in the metaform; nothing was written. See '
                                               f'metaform map history {thing}')))
    base = tx.db.execute(f'SELECT * FROM {spec.table} WHERE row=?', (current,)).fetchone()
    allowed = writes.split_changes(kind, given, notices, held=kind == 'join' and base['parent'] is not None)
    if not remove and given and not allowed:
        return Outcome(tuple(notices))
    base_layer = rows.layer(tx, str(base['layer_id']))
    if base_layer.kind not in METAFORM_KINDS:
        return Outcome((Notice('id', f'{thing} belongs to the knowledge layer {base_layer.name}; a correction never '
                                     'changes a knowledge layer, which is edited in place: metaform map knowledge '
                                     f'op=edit layer={base_layer.name} id={thing} <field>=<value>. Nothing was '
                                     'written.'),))
    columns = {key: base[key] for key in base.keys() if key not in ('row', 'layer_id', 'op', 'reason', 'evidence')}
    split: list[tuple[str, Any]] = []
    if not remove:
        changed, split = writes.changed_columns(tx, kind, allowed, found, notices, base)
        columns.update(changed)
    columns.update({'layer_id': found.layer_id, 'op': 'remove' if remove else 'change',
                    'reason': rows.text(reason, 'reason', notices), 'evidence': rows.text(evidence, 'evidence', notices)})
    previous = tx.db.execute(f'SELECT row FROM {spec.table} WHERE {spec.id_column}=? AND layer_id=?',
                             (thing, found.layer_id)).fetchone()
    if previous is not None:
        tx.db.execute('DELETE FROM refs WHERE owner=? AND owner_row=?', (kind, previous[0]))
        tx.db.execute(f'DELETE FROM {spec.table} WHERE row=?', (previous[0],))
    names = ', '.join(columns)
    marks = ', '.join('?' for _ in columns)
    cursor = tx.db.execute(f'INSERT INTO {spec.table}({names}) VALUES ({marks})', tuple(columns.values()))
    row = int(cursor.lastrowid or 0)
    if 'refs' in allowed and not remove:
        rows.write_refs(tx, kind, row, refs_fit(allowed['refs'])[0])
    else:
        rows.write_refs(tx, kind, row, [(ref.key, ref.value) for ref in rows.read_refs(tx.db, kind, current)])
    if kind == 'join' and not remove and 'parent' in columns and columns['parent'] != base['parent']:
        _lift(tx, found, thing, str(columns['parent']), rows.text(reason, 'reason', []), notices)
    if split:
        notices.append(Notice('extra', 'A correction keeps no list of records in its extra; those records were not '
                                       'written.'))
    record = views.version(tx, kind, tx.db.execute(f'SELECT * FROM {spec.table} WHERE row=?', (row,)).fetchone(), {})
    return dataclasses.replace(record, notices=tuple(notices))


def _lift(tx: Tx, found: LayerRow, thing: str, parent: str, reason: str | None, notices: list[Notice]) -> None:
    """The subtype joins of the metaform that a join absorbed into a parent held pass to that parent, each as a change
    row in the same correction layer, D3 and D5, MAP-032; a knowledge layer's is named and left inside it."""
    kinds = corrections.layer_kinds(tx.db)
    lifted: list[str] = []
    left: list[str] = []
    for child, child_row in tx.db.execute('SELECT join_id, row FROM current_subtypes WHERE parent=?',
                                          (thing,)).fetchall():
        base = tx.db.execute('SELECT * FROM joins WHERE row=?', (child_row,)).fetchone()
        if kinds.get(str(base['layer_id'])) not in METAFORM_KINDS:
            left.append(str(child))
            continue
        written = tx.db.execute('SELECT row FROM joins WHERE join_id=? AND layer_id=?',
                                (child, found.layer_id)).fetchone()
        if written is not None:
            tx.db.execute('UPDATE joins SET parent=? WHERE row=?', (parent, written[0]))
        else:
            columns = {key: base[key] for key in base.keys() if key not in ('row', 'layer_id', 'op', 'reason',
                                                                            'evidence')}
            columns.update({'parent': parent, 'layer_id': found.layer_id, 'op': 'change',
                            'reason': reason or f'its parent join {thing} was absorbed into {parent}'})
            cursor = tx.db.execute(f'INSERT INTO joins({", ".join(columns)}) VALUES '
                                   f'({", ".join("?" for _ in columns)})', tuple(columns.values()))
            rows.write_refs(tx, 'join', int(cursor.lastrowid or 0),
                            [(ref.key, ref.value) for ref in rows.read_refs(tx.db, 'join', int(child_row))])
        lifted.append(str(child))
    if lifted:
        notices.append(Notice('parent', f"{', '.join(lifted)} sat inside {thing}; a subtype join holds no subtype "
                                        f'joins, D5, so {"it passes" if len(lifted) == 1 else "they pass"} to {parent} '
                                        'when this layer is finished.'))
    if left:
        notices.append(Notice('parent', f"{', '.join(left)} of a knowledge layer still "
                                        f"{'sits' if len(left) == 1 else 'sit'} inside {thing}; a correction never "
                                        'changes a knowledge layer, so it was left as it is.'))


def peel(tx: Tx, layer: str) -> Layer | Outcome:
    """Take the top correction layer off the stack and return it to building, STORE-017."""
    found = rows.layer(tx, layer)
    if found.kind != 'correction':
        return Outcome((Notice('layer', f'{found.name} is not a correction layer; nothing was peeled. See metaform map '
                                        'stack'),))
    top = tx.db.execute('SELECT layer_id FROM correction_stack ORDER BY position DESC LIMIT 1').fetchone()
    if top is None or top[0] != found.layer_id:
        name = rows.layer_name(tx, str(top[0])) if top else 'none'
        return Outcome((Notice('layer', f'{found.name} is not on top of the stack; the top correction layer is '
                                        f'{name}. Nothing was peeled. To peel it: metaform map knowledge op=peel '
                                        f'layer={name}'),))
    corrections.peel(tx.db, found.layer_id)
    tx.db.execute('UPDATE layers SET ready=NULL WHERE layer_id=?', (found.layer_id,))
    return views.layer(tx, rows.layer(tx, found.layer_id))
