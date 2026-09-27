"""Writing the map's objects into a layer: elements, joins, subtypes, refs, items and properties, STORE-024.

Every function works inside one open write transaction and never refuses a
write for its content, BASE-044 and STORE-026: what does not fit is stored as
given, and the result carries a notice for it. A write aimed at something that
cannot change in place, a finished intake, a finished correction layer
or memory through the knowledge tool, writes nothing and returns a notice
naming the operation that does it. Only a reference that cannot be read at all,
such as an id that names nothing, raises `StoreError`.
"""
from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterable
from typing import Any, TypeVar, cast

from .. import home
from ..errors import StoreError
from . import corrections, rows, views
from .corrections import METAFORM_KINDS
from .ids import as_object, encode_extra, encode_value, is_id, new_id, refs_list
from .names import reading, short_name
from .records import (CONDITIONS, EF_WORDS, ROLES, SUBTYPE_ROLES, Element, Item, Join, Node, Notice, Outcome, Property,
                      Ref, Subtype, Version, WorkRecord)
from .selection import LayerRow, all_layers
from .session import Tx

RecordT = TypeVar('RecordT', Element, Join, Subtype, Item, Property, Version)


def _as_answers(value: Any, notices: list[Notice]) -> list[Any]:
    """One answer per item: a list given as one value becomes one item per member, STORE-004."""
    if isinstance(value, (list, tuple)):
        members: list[Any] = list(cast(Iterable[Any], value))
        notices.append(Notice('value', f'The value was a list of {len(members)} answers; each was stored as its '
                                       'own item.'))
        return members
    return [value]


# Elements, joins and subtypes -------------------------------------------------------------------------------

def _element_fields(name_length: Any, role: Any, found: LayerRow,
                    notices: list[Notice]) -> tuple[int | None, str | None, dict[str, Any]]:
    """An element's name_length and role as its row holds them, and what does not fit, kept for its extra, STORE-009.

    A name_length that is not a whole number is kept in the extra; a whole number below 1 is stored as given. A role
    is the intake's classification of the artifact, D48: given in a layer other than the intake or a correction
    layer, it is kept in the extra; a role outside the five is stored as given. Each is named in a notice, BASE-044.
    """
    kept: dict[str, Any] = {}
    length: int | None = None
    if name_length is not None and not rows.whole_number(name_length):
        kept['name_length'] = name_length
        notices.append(Notice('name_length', "name_length is not a whole number; it was kept in the element's "
                                             'extra.'))
    elif name_length is not None:
        length = int(name_length)
        if length < 1:
            notices.append(Notice('name_length', 'name_length is less than 1; it was stored as given.'))
    stored_role: str | None = None
    if role is not None and found.kind not in METAFORM_KINDS:
        kept['role'] = role
        notices.append(Notice('role', f"A role is the intake's classification of the artifact, and an element of "
                                      f"{found.name} carries none; the role was kept in the element's extra."))
    elif role is not None:
        stored_role = rows.text(role, 'role', notices)
        if stored_role not in ROLES:
            notices.append(Notice('role', f'{role!r} is not AUE, VE, DE, SE or NE; it was stored as given.'))
    return length, stored_role, kept


def add_element(tx: Tx, layer: str, address: Any, *, name_length: Any = None, role: Any = None,
                refs: Iterable[Any] = (), extra: Any = None) -> Element | Outcome:
    """Write an element, its address, name_length and role, or return the one already at the address, STORE-009.

    An element holds no name: the project's name for a functionality is on the join, MAP-020.
    """
    pairs = refs_list(refs)
    if not isinstance(address, str):
        raise StoreError(f'{address!r} is not an address: an address is text.', 'metaform map where <address>')
    found = rows.layer(tx, layer)
    stop = rows.frozen(tx, found)
    if stop is not None:
        return Outcome((stop,))
    notices: list[Notice] = []
    kept_extra, split = rows.extra_fields(extra, address, notices)
    if not rows.address_form(address):
        notices.append(Notice('address', f'{address!r} is not in the address form, dotted lowercase segments of '
                                         'letters, digits and underscores; it was stored as given.'))
    current = rows.current_element(tx, address)
    if current is not None:
        element_id = str(current['element_id'])
        record = views.element(tx, element_id, None)
        assert record is not None
        differs = (name_length is not None and name_length != record.name_length) or \
            (role is not None and role != record.role)
        given = (('name_length', name_length is not None and name_length != record.name_length),
                 ('role', role is not None and role != record.role), ('refs', bool(pairs)))
        notices += [Notice(field, f'{address} is already element {element_id} of layer {record.layer}, which keeps '
                                  f'its own {field}; the {field} given here was not applied.')
                    for field, unapplied in given if unapplied]
        rows.split_items(tx, found, 'element', element_id, split)
        return _with(record, notices, existing=True, differs=differs)
    length, stored_role, moved = _element_fields(name_length, role, found, notices)
    if moved:
        kept_extra = {**(kept_extra or {}), **moved}
    holder = rows.subtype_holding(tx, address)
    if holder is not None:
        notices.append(Notice('address', f'{address} is also held by subtype {holder}; the element was stored as '
                                         'given.'))
    element_id = rows.new_element(tx, found, address, kept_extra, name_length=length, role=stored_role, refs=pairs)
    rows.split_items(tx, found, 'element', element_id, split)
    if found.kind == 'correction':
        return Element(element_id, address, found.layer_id, found.name, reading(address), short_name(address, length),
                       length, stored_role, tuple(Ref(key, value) for key, value in pairs), kept_extra,
                       notices=tuple(notices))
    record = views.element(tx, element_id, None)
    assert record is not None
    return _with(record, notices)


def _with(record: RecordT, notices: list[Notice], **changes: Any) -> RecordT:
    """The record with the write's notices, BASE-044."""
    return dataclasses.replace(record, notices=tuple(notices), **changes)


def add_join(tx: Tx, layer: str, receiver: Any, provider: Any, *, name: Any = None, purpose: Any = None,
             function: Any = None, ef: Any = None, relation: Any = None, verb: Any = None, observation: Any = None,
             non_goal: Any = None, type: Any = 'purpose',
             refs: Iterable[Any] = (), extra: Any = None) -> Join | Outcome:
    """Write one join, owned by its receiver and served by its provider, STORE-010; `name` is the project's own name
    for the functionality it names, MAP-020."""
    pairs = refs_list(refs)
    found = rows.layer(tx, layer)
    stop = rows.frozen(tx, found)
    if stop is not None:
        return Outcome((stop,))
    notices: list[Notice] = []
    texts = {field: rows.text(value, field, notices) for field, value in (
        ('name', name), ('purpose', purpose), ('function', function), ('relation', relation), ('verb', verb),
        ('observation', observation), ('non_goal', non_goal))}
    kind = rows.text(type, 'type', notices) or 'purpose'
    kept_extra, split = rows.extra_fields(extra, 'the join', notices)
    ef, kept_extra = _ef(ef, kept_extra, "the join's", notices)
    receiver_id = rows.element_at(tx, receiver, found, 'receiver', notices)
    provider_id = rows.element_at(tx, provider, found, 'provider', notices)
    if receiver_id == provider_id:
        notices.append(Notice('provider', 'The provider is the receiver itself; the join was stored as given, D82.'))
    if kind != 'purpose' and not rows.address_form(kind):
        notices.append(Notice('type', f'{kind!r} is not purpose or an address; it was stored as given.'))
    join_id = new_id()
    tx.db.execute('INSERT INTO join_ids(join_id, receiver) VALUES (?, ?)', (join_id, receiver_id))
    rows.identity(tx, join_id, 'join')
    cursor = tx.db.execute(
        'INSERT INTO joins(join_id, layer_id, type, receiver, provider, name, purpose, function, ef, relation, verb, '
        'observation, non_goal, extra, stack_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (join_id, found.layer_id, kind, receiver_id, provider_id, texts['name'], texts['purpose'], texts['function'],
         ef,
         texts['relation'], texts['verb'], texts['observation'], texts['non_goal'], encode_extra(kept_extra, 'the join'),
         rows.top(tx)))
    row = int(cursor.lastrowid or 0)
    if found.kind != 'correction':
        tx.db.execute('INSERT INTO current_joins(join_id, row, receiver, provider) VALUES (?, ?, ?, ?)',
                      (join_id, row, receiver_id, provider_id))
    rows.write_refs(tx, 'join', row, pairs)
    rows.split_items(tx, found, 'join', join_id, split)
    record = views.join(tx, tx.db.execute('SELECT * FROM joins WHERE row=?', (row,)).fetchone(), all_layers(tx.db))
    return _with(record, notices)


def add_subtype(tx: Tx, layer: str, join: Any, address: Any, *, function: Any = None, ef: Any = None,
                relation: Any = None, verb: Any = None, observation: Any = None, name: Any = None, name_length: Any = None, role: Any = None,
                refs: Iterable[Any] = (), extra: Any = None, purpose: Any = None) -> Subtype | Outcome:
    """Write a subtype inside the one join it shares with its parent; it has no purpose, STORE-011."""
    pairs = refs_list(refs)
    if not isinstance(address, str):
        raise StoreError(f'{address!r} is not an address: an address is text.', 'metaform map where <address>')
    found = rows.layer(tx, layer)
    stop = rows.frozen(tx, found)
    if stop is not None:
        return Outcome((stop,))
    notices: list[Notice] = []
    kept_extra, split = rows.extra_fields(extra, address, notices)
    moved: dict[str, Any] = {}
    if purpose is not None:
        moved['purpose'] = purpose
        notices.append(Notice('purpose', 'A subtype has no purpose of its own; the purpose was kept in its extra.'))
    if role is not None and role not in SUBTYPE_ROLES:
        moved['role'] = role
        notices.append(Notice('role', f"{role!r} is not DE, SE or NE; it was kept in the subtype's extra."))
        role = None
    if name_length is not None and not rows.whole_number(name_length):
        moved['name_length'] = name_length
        notices.append(Notice('name_length', "name_length is not a whole number; it was kept in the subtype's "
                                             'extra.'))
        name_length = None
    if moved:
        kept_extra = {**(kept_extra or {}), **moved}
    ef, kept_extra = _ef(ef, kept_extra, "the subtype's", notices)
    texts = {field: rows.text(value, field, notices) for field, value in (
        ('function', function), ('relation', relation), ('verb', verb), ('observation', observation),
        ('name', name))}
    join_id = _join_of(tx, join, found)
    if not rows.address_form(address):
        notices.append(Notice('address', f'{address!r} is not in the address form; it was stored as given.'))
    holder = rows.subtype_holding(tx, address)
    if holder is not None:
        notices.append(Notice('address', f'{address} is also held by subtype {holder}; stored as given.'))
    elif rows.current_element(tx, address) is not None:
        notices.append(Notice('address', f'{address} is also held by an element; stored as given.'))
    subtype_id = new_id()
    tx.db.execute('INSERT INTO subtype_ids(subtype_id, join_id) VALUES (?, ?)', (subtype_id, join_id))
    rows.identity(tx, subtype_id, 'subtype')
    rows.types(tx, address)
    cursor = tx.db.execute(
        'INSERT INTO subtypes(subtype_id, layer_id, address, name, name_length, role, function, ef, relation, verb, '
        'observation, extra) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (subtype_id, found.layer_id, address, texts['name'], name_length, role, texts['function'], ef, texts['relation'],
         texts['verb'],
         texts['observation'], encode_extra(kept_extra, address)))
    row = int(cursor.lastrowid or 0)
    if found.kind != 'correction':
        tx.db.execute('INSERT INTO current_subtypes(subtype_id, row, join_id, address) VALUES (?, ?, ?, ?)',
                      (subtype_id, row, join_id, address))
    rows.write_refs(tx, 'subtype', row, pairs)
    rows.split_items(tx, found, 'subtype', subtype_id, split)
    record = views.subtype(tx, tx.db.execute('SELECT * FROM subtypes WHERE row=?', (row,)).fetchone(), join_id,
                           all_layers(tx.db))
    return _with(record, notices)


def _ef(ef: Any, extra: dict[str, Any] | None, owner: str,
        notices: list[Notice]) -> tuple[str | None, dict[str, Any] | None]:
    """The EF's word, Function or Encounter; any other value is kept in the extra and named, MAP-020."""
    if ef is None or ef in EF_WORDS:
        return ef, extra
    notices.append(Notice('ef', f"{ef!r} is not Function or Encounter; it was kept in {owner} extra."))
    return None, {**(extra or {}), 'ef': ef}


def _join_of(tx: Tx, join: Any, found: LayerRow) -> str:
    """The join a subtype lives in; a subtype cannot be stored without one, so an unknown join cannot be read."""
    if isinstance(join, str) and is_id(join) and (
            tx.db.execute('SELECT 1 FROM current_joins WHERE join_id=?', (join,)).fetchone() or
            tx.db.execute('SELECT 1 FROM joins WHERE join_id=? AND layer_id=?', (join, found.layer_id)).fetchone()):
        return join
    raise StoreError(f'{join} is not a join in this project; a subtype lives inside one join.',
                     'metaform map joins <element>')


def add_ref(tx: Tx, owner: str, key: str, value: str) -> Ref | Outcome:
    """Add one ref to a thing's current version in a knowledge or mutable layer, STORE-012."""
    (key, value), = refs_list([(key, value)])
    kind = rows.kind_of(tx, owner)
    spec = corrections.KINDS[kind]
    current = tx.db.execute(f'SELECT row FROM {spec.current} WHERE {spec.id_column}=?', (owner,)).fetchone()
    if current is None:
        return Outcome((Notice('owner', f'{owner} has no current version; nothing was written. See metaform map '
                                        f'history {owner}'),))
    layer_id = tx.db.execute(f'SELECT layer_id FROM {spec.table} WHERE row=?', (current[0],)).fetchone()[0]
    found = rows.layer(tx, str(layer_id))
    if found.kind in METAFORM_KINDS and not (found.kind == 'intake' and (not found.finished or
                                                                        found.layer_id in tx.created)):
        return Outcome((Notice('owner', f'{owner} belongs to {found.name}; its refs change only through a correction '
                                        f'layer: {rows.correct_step(owner)}. Nothing was written.'),))
    last = tx.db.execute('SELECT MAX(position) FROM refs WHERE owner=? AND owner_row=?',
                         (kind, current[0])).fetchone()[0]
    rows.write_refs(tx, kind, int(current[0]), [(key, value)], start=(int(last) + 1) if last is not None else 0)
    return Ref(key, value)


# Items and properties ---------------------------------------------------------------------------------------

def add_item(tx: Tx, layer: str, target: Node, value: Any, *, link: Node | None = None, refs: Iterable[Any] = (),
             extra: Any = None) -> Item | Outcome:
    """Attach one value of the layer's variable at one node, with an optional link to another, STORE-015."""
    pairs = refs_list(refs)
    found = rows.layer(tx, layer)
    stop = rows.frozen(tx, found)
    if stop is not None:
        return Outcome((stop,))
    notices: list[Notice] = []
    answers = _as_answers(value, notices)
    if not answers:
        return Outcome((Notice('value', 'The value was an empty list; there was nothing to store.'),))
    kept_extra, split = rows.extra_fields(extra, 'the item', notices)
    target_kind, target_id = rows.node_at(tx, target, found, 'target', notices)
    link_kind, link_id = rows.node_at(tx, link, found, 'link', notices) if link is not None else (None, None)
    made = [rows.insert_item(tx, found, target_kind, target_id, answer, link_kind, link_id, pairs, kept_extra)
            for answer in answers]
    rows.split_items(tx, found, target_kind, target_id, split)
    return _with(views.item_by_id(tx, made[0]), notices)


def add_property(tx: Tx, layer: str, element: Any, value: Any, *, refs: Iterable[Any] = (),
                 extra: Any = None) -> Property | Outcome:
    """Attach a property to an element; it travels the namespace and has no join, STORE-039.

    Sent to a type address, it goes on the element there, made when the project has none. Sent to a join or a
    subtype, it is stored as given, orphaned, with the target in its `extra`: properties attach only to elements.
    """
    pairs = refs_list(refs)
    found = rows.layer(tx, layer)
    stop = rows.frozen(tx, found)
    if stop is not None:
        return Outcome((stop,))
    notices: list[Notice] = []
    answers = _as_answers(value, notices)
    if not answers:
        return Outcome((Notice('value', 'The value was an empty list; there was nothing to store.'),))
    kept_extra, split = rows.extra_fields(extra, 'the property', notices)
    element_id = _property_element(tx, element, found, notices)
    if isinstance(element, Node) and element.kind in ('join', 'subtype'):
        kept_extra = {**(kept_extra or {}), 'target': str(element)}
    made: list[int] = []
    for answer in answers:
        property_id = new_id()
        cursor = tx.db.execute('INSERT INTO properties(property_id, layer_id, element_id, value, extra) '
                               'VALUES (?, ?, ?, ?, ?)', (property_id, found.layer_id, element_id,
                                                          encode_value(answer, 'the property'),
                                                          encode_extra(kept_extra, 'the property')))
        row = int(cursor.lastrowid or 0)
        if found.kind != 'correction':
            tx.db.execute('INSERT INTO current_properties(property_id, row, layer_id, element_id) VALUES (?, ?, ?, ?)',
                          (property_id, row, found.layer_id, element_id))
        rows.write_refs(tx, 'property', row, pairs)
        made.append(row)
    rows.split_items(tx, found, 'element', element_id, split)
    record = views.prop(tx, tx.db.execute('SELECT * FROM properties WHERE row=?', (made[0],)).fetchone(),
                        all_layers(tx.db))
    return _with(record, notices)


def _property_element(tx: Tx, element: Any, found: LayerRow, notices: list[Notice]) -> str:
    if isinstance(element, Node) and element.kind in ('join', 'subtype'):
        notices.append(Notice('element', f'{element} is a {element.kind}; properties attach only to elements, so it '
                                         'was stored as given, orphaned, with its target in its extra.'))
        return rows.stub_element(tx)
    ref = element.id if isinstance(element, Node) else element
    if isinstance(ref, str) and is_id(ref) and rows.current_element(tx, ref) is None:
        notices.append(Notice('element', f'No current element has the id {ref}; stored as given, orphaned.'))
        return rows.stub_element(tx, ref)
    if isinstance(element, Node) and element.kind == 'type' and rows.current_element(tx, element.id) is None:
        notices.append(Notice('element', f'{element.id} is a type address; an element was created there in layer '
                                         f'{found.name} to hold the property.'))
        return rows.new_element(tx, found, element.id)
    return rows.element_at(tx, ref, found, 'element', notices)


def _memory_item(tx: Tx, item_id: str, change: str) -> tuple[Any, LayerRow] | Notice:
    if rows.kind_of(tx, item_id) != 'item':
        return Notice('item', f'{item_id} is not an item; nothing was written.')
    row, found = rows.own_row(tx, 'item', item_id)
    if found.kind != 'memory':
        return Notice('item', f'{item_id} is in {found.name}, which is not memory; {change} it with metaform map '
                              f'knowledge op={"edit" if change == "change" else "remove"} layer={found.name} '
                              f'id={item_id}. Nothing was written.')
    return row, found


def update_item(tx: Tx, item_id: str, value: Any) -> Item | Outcome:
    """Change a memory in place, with no history, STORE-018."""
    found = _memory_item(tx, item_id, 'change')
    if isinstance(found, Notice):
        return Outcome((found,))
    row, _ = found
    tx.db.execute('UPDATE items SET value=? WHERE row=?', (encode_value(value, item_id), row['row']))
    return views.item_by_id(tx, item_id)


def delete_item(tx: Tx, item_id: str) -> Outcome:
    found = _memory_item(tx, item_id, 'remove')
    if isinstance(found, Notice):
        return Outcome((found,))
    row, _ = found
    tx.db.execute('DELETE FROM refs WHERE owner=? AND owner_row=?', ('item', row['row']))
    tx.db.execute('DELETE FROM current_items WHERE item_id=?', (item_id,))
    tx.db.execute('DELETE FROM items WHERE row=?', (row['row'],))
    return Outcome()


# Edit and remove, in place, in a knowledge layer or a building correction layer --------------------------------

def unchangeable(tx: Tx, found: LayerRow, thing: str) -> Notice | None:
    """Why a thing cannot change in place: memory has its own operations; the metaform changes only by correction."""
    if found.kind == 'memory':
        return Notice('id', f'{thing} is a memory; change it with the memory operations, such as metaform memory '
                            'delete-observations. Nothing was written.')
    if found.kind in ('intake', 'correction') and found.finished:
        return Notice('id', f'{thing} belongs to {found.name}; the metaform changes only through a correction layer: '
                            f'{rows.correct_step(thing)}. Nothing was written.')
    return None


def split_changes(kind: str, changes: dict[str, Any], notices: list[Notice],
                  refused: tuple[str, ...] = ()) -> dict[str, Any]:
    """The changes a thing of this kind takes; any other key is named in a notice and not applied, STORE-034."""
    allowed: dict[str, Any] = {}
    for key, value in changes.items():
        if key == 'refs' or key in rows.EDITABLE[kind]:
            allowed[key] = value
        elif key in refused:
            notices.append(Notice(key, f'A join keeps its receiver for life; {key} was not applied. To move a join, '
                                       'remove it and add a new one in the same correction layer.'))
        else:
            notices.append(Notice(key, f'{key} is not a field of a {kind}; it was not applied. The fields are '
                                       f'{", ".join(rows.EDITABLE[kind])} and refs.'))
    return allowed


def changed_columns(tx: Tx, kind: str, changes: dict[str, Any], found: LayerRow,
                    notices: list[Notice]) -> tuple[dict[str, Any], list[tuple[str, Any]]]:
    """The column values of a change, each checked the way a write checks it; and records split from an extra."""
    columns: dict[str, Any] = {}
    split: list[tuple[str, Any]] = []
    moved: dict[str, Any] = {}
    for key, value in changes.items():
        if key == 'refs':
            continue
        if key == 'extra':
            kept, split = rows.extra_fields(value, kind, notices)
            columns['extra'] = encode_extra(kept, kind)
        elif key == 'value':
            answers = _as_answers(value, notices)
            columns['value'] = encode_value(answers[0] if answers else None, kind)
            split += [('value', answer) for answer in answers[1:]]
        elif key == 'address':
            address = rows.text(value, 'address', notices) or ''
            if not rows.address_form(address):
                notices.append(Notice('address', f'{address!r} is not in the address form; it was stored as given.'))
            holder = rows.subtype_holding(tx, address)
            if holder is not None and kind == 'element':
                notices.append(Notice('address', f'{address} is also held by subtype {holder}; stored as given.'))
            rows.types(tx, address)
            columns['address'] = address
        elif key == 'provider':
            columns['provider'] = rows.element_at(tx, value, found, 'provider', notices)
        elif key == 'element':
            columns['element_id'] = rows.element_at(tx, value, found, 'element', notices)
        elif key == 'link':
            if value is None:
                columns['link_kind'], columns['link_id'] = None, None
            else:
                link = value if isinstance(value, Node) else Node.parse(str(value))
                columns['link_kind'], columns['link_id'] = rows.node_at(tx, link, found, 'link', notices)
        elif kind == 'element' and key in ('name_length', 'role'):
            length, role, kept = _element_fields(value if key == 'name_length' else None,
                                                 value if key == 'role' else None, found, notices)
            moved.update(kept)
            if key not in kept:
                columns[key] = length if key == 'name_length' else role
        elif key == 'role' and value is not None and value not in SUBTYPE_ROLES:
            moved['role'] = value
            notices.append(Notice('role', f"{value!r} is not DE, SE or NE; it was kept in the subtype's extra."))
        elif key == 'ef' and value is not None and value not in EF_WORDS:
            moved['ef'] = value
            notices.append(Notice('ef', f'{value!r} is not Function or Encounter; it was kept in the extra.'))
        elif key == 'name_length' and value is not None and not rows.whole_number(value):
            moved['name_length'] = value
            notices.append(Notice('name_length', "name_length is not a whole number; it was kept in the extra."))
        elif key in rows.TEXT_COLUMNS:
            columns[key] = rows.text(value, key, notices)
        else:
            columns[key] = value
    if moved:
        encoded = columns.get('extra')
        current = (as_object(json.loads(encoded)) if isinstance(encoded, str) else None) or {}
        columns['extra'] = encode_extra({**current, **moved}, kind)
    return columns, split


def edit(tx: Tx, thing: str, changes: Any) -> Version | Outcome:
    """Change a thing of a knowledge layer, or of a building correction layer, in place, STORE-032."""
    kind = rows.kind_of(tx, thing)
    row, found = rows.own_row(tx, kind, thing)
    stop = unchangeable(tx, found, thing)
    if stop is not None:
        return Outcome((stop,))
    given_changes = as_object(changes)
    if not given_changes:
        return Outcome((Notice('changes', 'No field to change was named; nothing was written.'),))
    notices: list[Notice] = []
    allowed = split_changes(kind, {str(key): value for key, value in given_changes.items()}, notices)
    if not allowed:
        return Outcome(tuple(notices))
    spec = corrections.KINDS[kind]
    columns, split = changed_columns(tx, kind, allowed, found, notices)
    if columns:
        assignments = ', '.join(f'{column}=?' for column in columns)
        tx.db.execute(f'UPDATE {spec.table} SET {assignments} WHERE row=?', (*columns.values(), row['row']))
    if allowed.get('refs') is not None:
        tx.db.execute('DELETE FROM refs WHERE owner=? AND owner_row=?', (kind, row['row']))
        rows.write_refs(tx, kind, int(row['row']), refs_list(allowed['refs']))
    if split:
        target_kind, target_id = (('element', str(columns.get('element_id', row['element_id']))) if kind == 'property'
                                  else _node_of(kind, thing, row))
        rows.split_items(tx, found, target_kind, target_id, split)
    if tx.db.execute(f'SELECT 1 FROM {spec.current} WHERE row=?', (row['row'],)).fetchone():
        updated = tx.db.execute(f'SELECT * FROM {spec.table} WHERE row=?', (row['row'],)).fetchone()
        tx.db.execute(f'DELETE FROM {spec.current} WHERE row=?', (row['row'],))
        corrections.insert_current(tx.db, kind, thing, updated, rows.moved(tx, kind, thing))
    record = views.version(tx, kind, tx.db.execute(f'SELECT * FROM {spec.table} WHERE row=?',
                                                   (row['row'],)).fetchone(), {})
    return _with(record, notices)


# Work records --------------------------------------------------------------------------------------------------

WORK_FIELDS = ('condition', 'note', 'task', 'held', 'reviewed')


def _work_text(value: Any, field: str, notices: list[Notice]) -> str | None:
    """A note, task or resolution: text, or anything else kept as JSON text with a notice, BASE-044."""
    if value is None or isinstance(value, str):
        return value
    notices.append(Notice(field, f'{field} is not text; it was stored as JSON text.'))
    return json.dumps(value, ensure_ascii=False)


def _condition(value: Any, notices: list[Notice]) -> str:
    if value in CONDITIONS:
        return str(value)
    notices.append(Notice('condition', f'{value!r} is not tbd, broken or cruft; it was stored as given.'))
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _work_row(tx: Tx, work_id: str) -> Any:
    row = tx.db.execute('SELECT * FROM work WHERE work_id=?', (work_id,)).fetchone()
    if row is None:
        raise StoreError(f'No work record has the id {work_id}.', 'metaform map work')
    return row


def add_work(tx: Tx, node: Any, condition: Any, *, note: Any = None, task: Any = None, held: Any = False,
             reviewed: Any = False) -> WorkRecord:
    """Write the condition of an element, join or subtype as its own record, apart from the map, STORE-042."""
    notices: list[Notice] = []
    kind, thing = rows.work_target(tx, node, notices)
    work_id = new_id()
    tx.db.execute('INSERT INTO work(work_id, target_kind, target_id, condition, note, task, held, reviewed, created) '
                  'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                  (work_id, kind, thing, _condition(condition, notices), _work_text(note, 'note', notices),
                   _work_text(task, 'task', notices), int(bool(held)), int(bool(reviewed)), home.now()))
    return views.work_record(tx, _work_row(tx, work_id), tuple(notices))


def edit_work(tx: Tx, work_id: str, changes: Any) -> WorkRecord:
    """Change a work record's condition, note, task, held or reviewed in place; other keys are named and not stored."""
    notices: list[Notice] = []
    _work_row(tx, work_id)
    given = as_object(changes)
    if given is None:
        raise StoreError('The changes to a work record are an object of its fields.', 'metaform help map work')
    for key in sorted(given):
        if key not in WORK_FIELDS:
            notices.append(Notice(key, f'A work record has no field {key}; it was not stored.'))
            continue
        value: Any = given[key]
        if key == 'condition':
            value = _condition(value, notices)
        elif key in ('held', 'reviewed'):
            value = int(bool(value))
        else:
            value = _work_text(value, key, notices)
        tx.db.execute(f'UPDATE work SET {key}=? WHERE work_id=?', (value, work_id))
    return views.work_record(tx, _work_row(tx, work_id), tuple(notices))


def finish_work(tx: Tx, work_id: str, resolution: Any = None) -> WorkRecord:
    """Mark a work record done, keeping its resolution beside it; a record already done keeps its first resolution."""
    notices: list[Notice] = []
    row = _work_row(tx, work_id)
    if row['done'] is not None:
        notices.append(Notice('work_id', f'This work record was done at {row["done"]}; its resolution was kept.'))
        return views.work_record(tx, row, tuple(notices))
    tx.db.execute('UPDATE work SET done=?, resolution=? WHERE work_id=?',
                  (home.now(), _work_text(resolution, 'resolution', notices), work_id))
    return views.work_record(tx, _work_row(tx, work_id), tuple(notices))


def _node_of(kind: str, thing: str, row: Any) -> tuple[str, str]:
    """Where items split from a changed row attach: the thing itself, or an item's own node."""
    if kind == 'item':
        return str(row['target_kind']), str(row['target_id'])
    return kind, thing


def remove(tx: Tx, thing: str | int) -> Outcome:
    """Delete a row a knowledge layer or a building correction layer wrote, with its refs, STORE-032.

    What in the same layer still used it as receiver, provider or target is left orphaned and named, STORE-017.
    """
    if isinstance(thing, int):
        return _remove_ref(tx, thing)
    kind = rows.kind_of(tx, thing)
    row, found = rows.own_row(tx, kind, thing)
    stop = unchangeable(tx, found, thing)
    if stop is not None:
        return Outcome((stop,))
    users = _users(tx, kind, thing, found)
    spec = corrections.KINDS[kind]
    tx.db.execute('DELETE FROM refs WHERE owner=? AND owner_row=?', (kind, row['row']))
    tx.db.execute(f'DELETE FROM {spec.current} WHERE row=?', (row['row'],))
    if kind == 'item':
        tx.db.execute('DELETE FROM challenge_states WHERE item_id=?', (thing,))
    tx.db.execute(f'DELETE FROM {spec.table} WHERE row=?', (row['row'],))
    if not users:
        return Outcome()
    return Outcome((Notice('id', f'{thing} was still used in {found.name} by {", ".join(users)}; '
                                 f'{"that is" if len(users) == 1 else "those are"} now orphaned.'),))


def _remove_ref(tx: Tx, ref_id: int) -> Outcome:
    ref = tx.db.execute('SELECT owner, owner_row FROM refs WHERE ref_id=?', (ref_id,)).fetchone()
    if ref is None:
        raise StoreError(f'No ref {ref_id}.', 'metaform map where <address>')
    table = corrections.KINDS[str(ref['owner'])].table
    layer_id = tx.db.execute(f'SELECT layer_id FROM {table} WHERE row=?', (ref['owner_row'],)).fetchone()[0]
    stop = unchangeable(tx, rows.layer(tx, str(layer_id)), str(ref_id))
    if stop is not None:
        return Outcome((stop,))
    tx.db.execute('DELETE FROM refs WHERE ref_id=?', (ref_id,))
    return Outcome()


def _users(tx: Tx, kind: str, thing: str, found: LayerRow) -> list[str]:
    """The current rows of the same layer that use a thing as receiver, provider or target."""
    db = tx.db
    users: list[str] = []
    if kind == 'element':
        users += [str(row[0]) for row in db.execute('SELECT c.join_id FROM current_joins c JOIN joins j ON j.row = c.row '
                                                    'WHERE c.receiver=? AND j.layer_id=?', (thing, found.layer_id))]
        users += [str(row[0]) for row in db.execute('SELECT c.join_id FROM current_joins c JOIN joins j ON j.row = c.row '
                                                    'WHERE c.provider=? AND j.layer_id=?', (thing, found.layer_id))]
        users += [str(row[0]) for row in db.execute('SELECT property_id FROM current_properties WHERE element_id=? '
                                                    'AND layer_id=?', (thing, found.layer_id))]
    if kind == 'join':
        users += [str(row[0]) for row in db.execute('SELECT c.subtype_id FROM current_subtypes c JOIN subtypes s '
                                                    'ON s.row = c.row WHERE c.join_id=? AND s.layer_id=?',
                                                    (thing, found.layer_id))]
    if kind in ('element', 'join', 'subtype'):
        users += [str(row[0]) for row in db.execute('SELECT item_id FROM current_items WHERE target_kind=? AND '
                                                    'target_id=? AND layer_id=?', (kind, thing, found.layer_id))]
    return users
