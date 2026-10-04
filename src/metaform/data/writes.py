"""Writing the map's objects into a layer: elements, joins, subtype joins, refs, items and properties, STORE-024.

Every function works inside one open write transaction and never refuses a
write for its content, BASE-044 and STORE-026: what does not fit is stored as
given, and the result carries a notice for it. A write aimed at something that
cannot change in place, what a finished intake holds or memory through the
knowledge tool, writes nothing and returns a notice naming the operation that
does it. The finished intake still takes additions: the metaform grows in its
own layer, LAYER-025. Only a reference that cannot be read at all,
such as an id that names nothing, raises `StoreError`.
"""
from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterable
from typing import Any, TypeVar, cast

from ..errors import StoreError
from ..wording import count
from . import operations, rows, versions, views
from .ids import as_object, encode_extra, encode_value, is_id, new_id, refs_fit
from .records import (
    ROLES,
    Element,
    Item,
    Join,
    Node,
    Notice,
    Outcome,
    Property,
    Ref,
    Subtype,
    Version,
)
from .rows import Row
from .selection import LayerRow, all_layers
from .session import Tx
from .versions import METAFORM_KINDS

RecordT = TypeVar('RecordT', Element, Join, Subtype, Item, Property, Version)


def _as_answers(value: Any, notices: list[Notice]) -> list[Any]:
    """One answer per item: a list given as one value becomes one item per member, STORE-004."""
    if isinstance(value, (list, tuple)):
        members: list[Any] = list(cast(Iterable[Any], value))
        notices.append(Notice('value', f'The value was a list of {count(len(members))} answers; each was stored as its '
                                       'own item.'))
        return members
    return [value]


# Elements, joins and subtype joins --------------------------------------------------------------------------

def _element_fields(name_length: Any, role: Any, found: LayerRow,
                    notices: list[Notice]) -> tuple[int | None, str | None, dict[str, Any]]:
    """An element's name_length and role as its row holds them, and what does not fit, kept for its extra, STORE-009.

    A name_length that is not a whole number is kept in the extra; a whole number below 1 is stored as given. A role
    is the intake's classification of the artifact, D48: given in a layer other than the intake, it is kept in the
    extra; a role outside the five is stored as given. Each is named in a notice, BASE-044.
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
            notices.append(Notice('role', f'{role!r} is not AUE, CQU, DE, SE or NE; it was stored as given.'))
    return length, stored_role, kept


def add_element(tx: Tx, layer: str, address: Any, *, name_length: Any = None, role: Any = None,
                refs: Iterable[Any] = (), extra: Any = None, name: Any = None) -> Element | Outcome:
    """Write an element, its address, name_length, name and role, or return the one already at the address,
    STORE-009. Its name is the canonical name the project uses for it, Rich 2026-10-01.
    """
    pairs, odd = refs_fit(refs)
    if not isinstance(address, str):
        raise StoreError(f'{address!r} is not an address: an address is text.', 'metaform map where <address>')
    found = rows.layer(tx, layer)
    notices: list[Notice] = []
    kept_extra, split = rows.extra_fields(extra, address, notices)
    kept_extra, more = rows.odd_refs(odd, kept_extra, address, notices)
    split += more
    if not rows.address_form(address):
        notices.append(Notice('address', f'{address!r} is not in the address form, dotted lowercase segments of '
                                         'letters, digits and underscores; it was stored as given.'))
    current = rows.current_element(tx, address)
    if current is not None:
        element_id = str(current['element_id'])
        record = views.element(tx, element_id, None)
        assert record is not None
        differs = (name_length is not None and name_length != record.name_length) or \
            (role is not None and role != record.role) or (name is not None and name != record.name)
        given = (('name_length', name_length is not None and name_length != record.name_length),
                 ('name', name is not None and name != record.name),
                 ('role', role is not None and role != record.role), ('refs', bool(pairs)))
        notices += [Notice(field, f'{address} is already element {element_id} of layer {record.layer}, which keeps '
                                  f'its own {field}; the {field} given here was not applied.')
                    for field, unapplied in given if unapplied]
        rows.split_items(tx, found, 'element', element_id, split)
        return _with(record, notices, existing=True, differs=differs)
    length, stored_role, aside = _element_fields(name_length, role, found, notices)
    if aside:
        kept_extra = {**(kept_extra or {}), **aside}
    element_id = rows.new_element(tx, found, address, kept_extra, name_length=length, role=stored_role, refs=pairs,
                                  name=rows.text(name, 'name', notices))
    rows.split_items(tx, found, 'element', element_id, split)
    record = views.element(tx, element_id, None)
    assert record is not None
    return _with(record, notices)


def _with(record: RecordT, notices: list[Notice], **changes: Any) -> RecordT:
    """The record with the write's notices, BASE-044."""
    return dataclasses.replace(record, notices=tuple(notices), **changes)


def add_join(tx: Tx, layer: str, receiver: Any, provider: Any, *, name: Any = None, purpose: Any = None,
             ef: Any = None, verb: Any = None, non_goal: Any = None, type: Any = 'purpose',
             refs: Iterable[Any] = (), extra: Any = None, ifd: Any = None, element: Any = None) -> Join | Outcome:
    """Write one join, owned by its receiver and served by its provider, STORE-010; `name` is the project's own name
    for the functionality it names, MAP-020. `element` promotes it: the address of the element written for it, which
    receives and provides joins as any element does, MAP-054."""
    pairs, odd = refs_fit(refs)
    found = rows.layer(tx, layer)
    notices: list[Notice] = []
    texts = {field: rows.text(value, field, notices) for field, value in (
        ('name', name), ('purpose', purpose), ('ef', ef), ('verb', verb), ('non_goal', non_goal))}
    kind = rows.text(type, 'type', notices) or 'purpose'
    kept_extra, split = rows.extra_fields(extra, 'the join', notices)
    kept_extra, more = rows.odd_refs(odd, kept_extra, 'the join', notices)
    split += more
    receiver_id = rows.element_at(tx, receiver, found, 'receiver', notices)
    provider_id = rows.element_at(tx, provider, found, 'provider', notices)
    if receiver_id == provider_id:
        notices.append(Notice('provider', 'The provider is the receiver itself; the join was stored as given, D82.'))
    if kind != 'purpose' and not rows.address_form(kind):
        notices.append(Notice('type', f'{kind!r} is not purpose or an address; it was stored as given.'))
    promoted_to = promoted(tx, found, element, texts['name'], notices)
    join_id = new_id()
    tx.db.execute('INSERT INTO join_ids(join_id) VALUES (?)', (join_id,))
    rows.identity(tx, join_id, 'join')
    cursor = tx.db.execute(
        'INSERT INTO joins(join_id, layer_id, type, receiver, provider, name, purpose, ef, ifd, verb, non_goal, '
        'element, extra) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (join_id, found.layer_id, kind, receiver_id, provider_id, texts['name'], texts['purpose'], texts['ef'],
         _ifd(ifd, notices), texts['verb'], texts['non_goal'], promoted_to, encode_extra(kept_extra, 'the join')))
    row = int(cursor.lastrowid or 0)
    tx.db.execute('INSERT INTO current_joins(join_id, row, receiver, provider) VALUES (?, ?, ?, ?)',
                  (join_id, row, receiver_id, provider_id))
    rows.write_refs(tx, 'join', row, pairs)
    rows.split_items(tx, found, 'join', join_id, split)
    record = views.join(tx, tx.db.execute('SELECT * FROM joins WHERE row=?', (row,)).fetchone(), all_layers(tx.db))
    return _with(record, notices)


def add_subtype(tx: Tx, layer: str, join: Any, address: Any, *, ef: Any = None, verb: Any = None,
                non_goal: Any = None,
                name: Any = None, name_length: Any = None, role: Any = None, refs: Iterable[Any] = (),
                extra: Any = None, purpose: Any = None, ifd: Any = None, element_name: Any = None) -> Subtype | Outcome:
    """Write a subtype join inside its parent join, holding the element at `address`, with its own purpose, the
    share of the parent's purpose it serves, STORE-011.

    The element is an ordinary element record, MAP-030: one is written in the layer with the name_length and role
    given when the address holds none; an element already there keeps its own, and each field given that differs is
    named in a notice, as `add_element` does. The subtype join's refs are its own.
    """
    pairs, odd = refs_fit(refs)
    if not isinstance(address, str):
        raise StoreError(f'{address!r} is not an address: an address is text.', 'metaform map where <address>')
    found = rows.layer(tx, layer)
    parent = _parent_of(tx, join, found)
    notices: list[Notice] = []
    kept_extra, split = rows.extra_fields(extra, 'the subtype join', notices)
    kept_extra, more = rows.odd_refs(odd, kept_extra, 'the subtype join', notices)
    split += more
    texts = {field: rows.text(value, field, notices) for field, value in (
        ('purpose', purpose), ('ef', ef), ('verb', verb), ('non_goal', non_goal), ('name', name))}
    element_id = _held_element(tx, found, address, name_length, role, notices, element_name)
    for other in rows.holding(tx, element_id):
        notices.append(Notice('address', f'{address} is already held by subtype join {other}; a part serving two '
                                         'joins is its own element, D4. Stored as given.'))
    join_id = new_id()
    tx.db.execute('INSERT INTO join_ids(join_id) VALUES (?)', (join_id,))
    rows.identity(tx, join_id, 'join')
    cursor = tx.db.execute(
        "INSERT INTO joins(join_id, layer_id, type, parent, receiver, provider, name, purpose, ef, ifd, "
        "verb, non_goal, extra) VALUES (?, ?, 'subtype', ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)",
        (join_id, found.layer_id, parent, element_id, texts['name'], texts['purpose'], texts['ef'],
         _ifd(ifd, notices), texts['verb'], texts['non_goal'], encode_extra(kept_extra, 'the subtype join')))
    row = int(cursor.lastrowid or 0)
    tx.db.execute('INSERT INTO current_subtypes(join_id, row, parent, provider) VALUES (?, ?, ?, ?)',
                  (join_id, row, parent, element_id))
    rows.write_refs(tx, 'join', row, pairs)
    rows.split_items(tx, found, 'join', join_id, split)
    record = views.subtype(tx, tx.db.execute('SELECT * FROM joins WHERE row=?', (row,)).fetchone(), all_layers(tx.db))
    return _with(record, notices)


def promoted(tx: Tx, found: LayerRow, element: Any, name: Any, notices: list[Notice]) -> str | None:
    """The address a promoted join names, MAP-054, Rich 2026-10-02: "When a join becomes an element it creates an
    element record for the join which can accept more joins itself. they are associated by the namespace name".

    An address that holds no element gets one in the layer, named with the join's name; an element already there keeps
    its own fields and is named in a notice. An element given by its id is named by its address. None promotes nothing.
    """
    if element is None:
        return None
    if not isinstance(element, str):
        raise StoreError(f'{element!r} is not an address: an address is text.', 'metaform map where <address>')
    current = rows.current_element(tx, element)
    if current is None:
        if is_id(element):
            raise StoreError(f'No element has the id {element}.', 'metaform map where <address>')
        if not rows.address_form(element):
            notices.append(Notice('element', f'{element!r} is not in the address form, dotted lowercase segments of '
                                             'letters, digits and underscores; it was stored as given.'))
        rows.new_element(tx, found, element, name=rows.text(name, 'name', notices))
        return element
    record = views.element(tx, str(current['element_id']), None)
    assert record is not None
    notices.append(Notice('element', f'{record.address} is already element {record.element_id} of layer '
                                     f'{record.layer}, which keeps its own fields; the join names it.'))
    return record.address


IFDS = ('sends', 'receives', 'both')  # IFD, Information Flow Direction, Rich 2026-10-01


def _ifd(value: Any, notices: list[Notice]) -> str | None:
    """A join's Information Flow Direction: sends, receives or both; anything else is stored as given, BASE-044."""
    if value is None or value in IFDS:
        return value
    notices.append(Notice('ifd', f'{value!r} is not sends, receives or both; it was stored as given.'))
    return str(value)


def _held_element(tx: Tx, found: LayerRow, address: str, name_length: Any, role: Any,
                  notices: list[Notice], name: Any = None) -> str:
    """The element a subtype join holds: the one at the address, or a new one written in the layer, STORE-011."""
    if not rows.address_form(address) and not is_id(address):
        notices.append(Notice('address', f'{address!r} is not in the address form; it was stored as given.'))
    current = rows.current_element(tx, address)
    if current is None:
        if is_id(address):
            raise StoreError(f'No element has the id {address}.', 'metaform map where <address>')
        length, stored_role, kept = _element_fields(name_length, role, found, notices)
        return rows.new_element(tx, found, address, kept or None, name_length=length, role=stored_role,
                                name=rows.text(name, 'name', notices))
    element_id = str(current['element_id'])
    record = views.element(tx, element_id, None)
    assert record is not None
    for field, given, own in (('name_length', name_length, record.name_length), ('name', name, record.name),
                              ('role', role, record.role)):
        if given is not None and given != own:
            notices.append(Notice(field, f'{record.address} is already element {element_id} of layer {record.layer}, '
                                         f'which keeps its own {field}; the {field} given here was not applied.'))
    return element_id


def _parent_of(tx: Tx, join: Any, found: LayerRow) -> str:
    """The join a subtype join sits in: a join held by a receiver, current or written in this layer, STORE-011. A
    subtype join cannot be stored without one, so any other reference cannot be read, D5 and MAP-032."""
    if isinstance(join, str) and is_id(join):
        held = tx.db.execute('SELECT 1 FROM current_joins WHERE join_id=?', (join,)).fetchone()
        written = tx.db.execute('SELECT parent FROM joins WHERE join_id=? AND layer_id=? ORDER BY row DESC LIMIT 1',
                                (join, found.layer_id)).fetchone()
        if held is not None or (written is not None and written[0] is None):
            return join
        if rows.target_current(tx, 'join', join) or written is not None:
            raise StoreError(f'{join} is a subtype join; a subtype join sits inside a join held by a receiver, and '
                             'holds no subtype joins of its own.', f'metaform map subtypes {join}')
    raise StoreError(f'{join} is not a join held by a receiver in this project; a subtype join lives inside one join.',
                     'metaform map joins <element>')


def add_ref(tx: Tx, owner: str, key: Any, value: Any) -> Ref | Outcome:
    """Add one ref to a thing's current version, STORE-012; the metaform's own things take refs too, LAYER-025."""
    key = key if isinstance(key, str) else json.dumps(key, ensure_ascii=False, sort_keys=True)
    value = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    kind = rows.kind_of(tx, owner)
    current = versions.current_row(tx.db, kind, owner)
    if current is None:
        return Outcome((Notice('owner', f'{owner} has no current version; nothing was written. See metaform map '
                                        f'history {owner}'),))
    last = tx.db.execute('SELECT MAX(position) FROM refs WHERE owner=? AND owner_row=?',
                         (kind, current)).fetchone()[0]
    rows.write_refs(tx, kind, current, [(key, value)], start=(int(last) + 1) if last is not None else 0)
    return Ref(key, value)


# Items and properties ---------------------------------------------------------------------------------------

def add_item(tx: Tx, layer: str, target: Node, value: Any, *, link: Node | None = None, refs: Iterable[Any] = (),
             extra: Any = None, read_first: Any = False, always_show: Any = False, task: Any = False,
             condition: Any = None) -> Item | Outcome:
    """Attach one value of the layer's variable at one node, with an optional link to another, STORE-015.

    `read_first` and `always_show` are stored on the item. An item flagged `task` is a ticket, D92: it adds a work
    record at its node whose task is the item's value, and the flag is not stored on the item, LAYER-021."""
    pairs, odd = refs_fit(refs)
    found = rows.layer(tx, layer)
    notices: list[Notice] = []
    answers = _as_answers(value, notices)
    if not answers:
        return Outcome((Notice('value', 'The value was an empty list; there was nothing to store.'),))
    kept_extra, split = rows.extra_fields(extra, 'the item', notices)
    kept_extra, more = rows.odd_refs(odd, kept_extra, 'the item', notices)
    split += more
    target_kind, target_id = rows.node_at(tx, target, found, 'target', notices)
    link_kind, link_id = rows.node_at(tx, link, found, 'link', notices) if link is not None else (None, None)
    made = [rows.insert_item(tx, found, target_kind, target_id, answer, link_kind, link_id, pairs, kept_extra,
                             read_first, always_show) for answer in answers]
    rows.split_items(tx, found, target_kind, target_id, split)
    operations.item_write(tx, Node.of(target_kind, target_id), answers,
                          {'task': task, 'condition': condition}, notices)
    return _with(views.item_by_id(tx, made[0]), notices)


def add_property(tx: Tx, layer: str, element: Any, value: Any, *, refs: Iterable[Any] = (),
                 extra: Any = None) -> Property | Outcome:
    """Attach a property to an element; it travels the namespace and has no join, STORE-039.

    Sent to a type address, it goes on the element there, made when the project has none. Sent to a join or a
    subtype join, it is stored as given, orphaned, with the target in its `extra`: properties attach only to
    elements.
    """
    pairs, odd = refs_fit(refs)
    found = rows.layer(tx, layer)
    notices: list[Notice] = []
    answers = _as_answers(value, notices)
    if not answers:
        return Outcome((Notice('value', 'The value was an empty list; there was nothing to store.'),))
    kept_extra, split = rows.extra_fields(extra, 'the property', notices)
    kept_extra, more = rows.odd_refs(odd, kept_extra, 'the property', notices)
    split += more
    element_id = _property_element(tx, element, found, notices)
    if isinstance(element, Node) and element.kind == 'join':
        kept_extra = {**(kept_extra or {}), 'target': str(element)}
    made: list[int] = []
    for answer in answers:
        property_id = new_id()
        cursor = tx.db.execute('INSERT INTO properties(property_id, layer_id, element_id, value, extra) '
                               'VALUES (?, ?, ?, ?, ?)', (property_id, found.layer_id, element_id,
                                                          encode_value(answer, 'the property'),
                                                          encode_extra(kept_extra, 'the property')))
        row = int(cursor.lastrowid or 0)
        tx.db.execute('INSERT INTO current_properties(property_id, row, layer_id, element_id) VALUES (?, ?, ?, ?)',
                      (property_id, row, found.layer_id, element_id))
        rows.write_refs(tx, 'property', row, pairs)
        made.append(row)
    rows.split_items(tx, found, 'element', element_id, split)
    record = views.prop(tx, tx.db.execute('SELECT * FROM properties WHERE row=?', (made[0],)).fetchone(),
                        all_layers(tx.db))
    return _with(record, notices)


def _property_element(tx: Tx, element: Any, found: LayerRow, notices: list[Notice]) -> str:
    if isinstance(element, Node) and element.kind == 'join':
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


# Edit and remove, in place, in a knowledge layer or a building intake ----------------------------------------

def unchangeable(tx: Tx, found: LayerRow, thing: str) -> Notice | None:
    """Why a thing cannot change in place: memory has its own operations; the finished metaform changes only by
    refining, which keeps every version, LAYER-025."""
    if found.kind == 'memory':
        return Notice('id', f'{thing} is a memory; change it with the memory operations, such as metaform memory '
                            'delete_observations. Nothing was written.')
    if found.kind in METAFORM_KINDS and found.finished:
        return Notice('id', f'{thing} belongs to {found.name}; the metaform changes by refining, which keeps every '
                            f'version: {rows.refine_step(thing)}. Nothing was written.')
    return None


MOVED = ("An element cannot be moved: its address is its identity, and another address is a different element, "
         "MAP-015. address was not applied; record the element at the new address and move its joins to it with "
         "receiver or provider.")


def split_changes(kind: str, changes: dict[str, Any], notices: list[Notice], *, held: bool = False) -> dict[str, Any]:
    """The changes a thing of this kind takes; any other key is named in a notice and not applied, STORE-034.

    An element's address is never applied, MAP-015. A subtype join, `held`, sits in its parent join, so a receiver
    given for it is not applied: `parent` moves it.
    """
    allowed: dict[str, Any] = {}
    for key, value in changes.items():
        if kind == 'element' and key == 'address':
            notices.append(Notice('address', MOVED))
        elif held and key == 'receiver':
            notices.append(Notice('receiver', "A subtype join sits in its parent join, whose receiver owns it; receiver "
                                              'was not applied. parent moves it to another join.'))
        elif held and key == 'element':
            notices.append(Notice('element', 'A subtype join already holds an element of its own, which receives and '
                                             'provides joins; element was not applied, MAP-054.'))
        elif key == 'refs' or key in rows.EDITABLE[kind]:
            allowed[key] = value
        else:
            notices.append(Notice(key, f'{key} is not a field of a {kind}; it was not applied. The fields are '
                                       f'{", ".join(rows.EDITABLE[kind])} and refs.'))
    return allowed


def _receiver_of(tx: Tx, join_id: str) -> str | None:
    """The receiver of a join held by a receiver: its current row's, or the latest row written for it."""
    found = tx.db.execute('SELECT receiver FROM current_joins WHERE join_id=?', (join_id,)).fetchone()
    if found is None:
        found = tx.db.execute('SELECT receiver FROM joins WHERE join_id=? ORDER BY row DESC LIMIT 1',
                              (join_id,)).fetchone()
    return None if found is None or found[0] is None else str(found[0])


def _naming(tx: Tx, element_id: str, thing: str) -> list[str]:
    """The other current joins that name an element: as receiver or provider, or as the element a subtype join holds."""
    found = [str(row[0]) for row in tx.db.execute(
        'SELECT join_id FROM current_joins WHERE receiver=? UNION SELECT join_id FROM current_joins WHERE provider=? '
        'UNION SELECT join_id FROM current_subtypes WHERE provider=?', (element_id, element_id, element_id))]
    return sorted(join_id for join_id in found if join_id != thing)


def _absorbed(tx: Tx, base: Row, value: Any, changes: dict[str, Any], found: LayerRow, columns: dict[str, Any],
              aside: dict[str, Any], notices: list[Notice]) -> None:
    """A change of a join's parent: it becomes a subtype join inside that join, MAP-030, keeping every field but its
    receiver, which the parent's receiver now holds. Its purpose stays its own: the share of the parent's purpose it
    serves, STORE-034."""
    parent = _parent_of(tx, value, found)
    if parent == base['join_id']:
        raise StoreError(f'{parent} cannot be held inside itself; a subtype join sits inside another join held by a '
                         'receiver.', 'metaform map joins <receiver>')
    columns.update(parent=parent, type='subtype', receiver=None)
    held_by = _receiver_of(tx, parent)
    if base['receiver'] is not None and base['receiver'] != held_by:
        aside['receiver'] = rows.address_of(tx, str(base['receiver'])) or str(base['receiver'])
        notices.append(Notice('receiver', f"The join's receiver, {aside['receiver']}, is not the receiver of join "
                                          f'{parent}; it is held inside that join as given, with its receiver kept in '
                                          'its extra.'))
    others = _naming(tx, str(columns.get('provider', base['provider'])), str(base['join_id']))
    if others:
        notices.append(Notice('join', f"{', '.join(others)} still {'names' if len(others) == 1 else 'name'} the "
                                      'element this subtype join holds; left as '
                                      f"{'it is' if len(others) == 1 else 'they are'}."))


def changed_columns(tx: Tx, kind: str, changes: dict[str, Any], found: LayerRow, notices: list[Notice],
                    base: Row) -> tuple[dict[str, Any], list[tuple[str, Any]]]:
    """The column values of a change of `base`, each checked the way a write checks it; and records split from an
    extra. What does not fit its column is kept in the extra, with the extra's other fields, BASE-044."""
    columns: dict[str, Any] = {}
    split: list[tuple[str, Any]] = []
    aside: dict[str, Any] = {}
    for key, value in changes.items():
        if key == 'refs':
            placed, more = rows.odd_refs(refs_fit(value)[1], None, kind, notices)
            aside.update(placed or {})
            split += more
            continue
        if key == 'extra':
            kept, split = rows.extra_fields(value, kind, notices)
            columns['extra'] = encode_extra(kept, kind)
        elif key == 'value':
            answers = _as_answers(value, notices)
            columns['value'] = encode_value(answers[0] if answers else None, kind)
            split += [('value', answer) for answer in answers[1:]]
        elif kind == 'join' and key == 'element':
            columns['element'] = promoted(tx, found, value, changes.get('name', base['name']), notices)
        elif key in ('receiver', 'provider', 'element'):
            columns['element_id' if key == 'element' else key] = rows.element_at(tx, value, found, key, notices)
        elif key == 'parent':
            _absorbed(tx, base, value, changes, found, columns, aside, notices)
        elif key == 'link':
            if value is None:
                columns['link_kind'], columns['link_id'] = None, None
            else:
                link = value if isinstance(value, Node) else Node.parse(str(value))
                columns['link_kind'], columns['link_id'] = rows.node_at(tx, link, found, 'link', notices)
        elif kind == 'element' and key in ('name_length', 'role'):
            length, role, kept = _element_fields(value if key == 'name_length' else None,
                                                 value if key == 'role' else None, found, notices)
            aside.update(kept)
            if key not in kept:
                columns[key] = length if key == 'name_length' else role
        elif key in rows.TEXT_COLUMNS:
            columns[key] = rows.text(value, key, notices)
        elif kind == 'item' and key in ('read_first', 'always_show'):
            columns[key] = int(bool(value))
        else:
            columns[key] = value
    if aside:
        encoded = columns['extra'] if 'extra' in columns else base['extra']
        current = (as_object(json.loads(encoded)) if isinstance(encoded, str) else None) or {}
        columns['extra'] = encode_extra({**current, **aside}, kind)
    return columns, split


def _lift(tx: Tx, found: LayerRow, thing: str, parent: str, notices: list[Notice]) -> None:
    """A join absorbed while it holds subtype joins passes them to its new parent, D3 and D5, MAP-032: those written
    in the same layer move with it; any other is named and left inside."""
    lifted: list[str] = []
    for row in tx.db.execute('SELECT * FROM joins WHERE layer_id=? AND parent=? ORDER BY row',
                             (found.layer_id, thing)).fetchall():
        tx.db.execute('UPDATE joins SET parent=? WHERE row=?', (parent, row['row']))
        if versions.current_of_row(tx.db, 'join', int(row['row'])) is not None:
            versions.drop_current(tx.db, 'join', 'row', row['row'])
            versions.insert_current(tx.db, 'join', str(row['join_id']),
                                       tx.db.execute('SELECT * FROM joins WHERE row=?', (row['row'],)).fetchone())
        lifted.append(str(row['join_id']))
    left = [str(row[0]) for row in tx.db.execute('SELECT join_id FROM current_subtypes WHERE parent=?', (thing,))]
    if lifted:
        notices.append(Notice('parent', f"{', '.join(lifted)} sat inside {thing}; a subtype join holds no subtype "
                                        f'joins, D5, so {"it was" if len(lifted) == 1 else "they were"} passed to '
                                        f'{parent}.'))
    if left:
        notices.append(Notice('parent', f"{', '.join(left)} of another layer still {'sits' if len(left) == 1 else 'sit'}"
                                        f' inside {thing}; left as {"it is" if len(left) == 1 else "they are"}.'))


def edit(tx: Tx, thing: str, changes: Any) -> Version | Outcome:
    """Change a thing of a knowledge layer, or of a building intake, in place, STORE-032.

    A join's receiver, provider and parent move it, and it stays the same join, MAP-003; an element's address is never
    changed, MAP-015.
    """
    kind = rows.kind_of(tx, thing)
    row, found = rows.own_row(tx, kind, thing)
    stop = unchangeable(tx, found, thing)
    if stop is not None:
        return Outcome((stop,))
    given_changes = as_object(changes)
    if not given_changes:
        return Outcome((Notice('changes', 'No field to change was named; nothing was written.'),))
    notices: list[Notice] = []
    allowed = split_changes(kind, {str(key): value for key, value in given_changes.items()}, notices,
                            held=kind == 'join' and row['parent'] is not None)
    if not allowed:
        return Outcome(tuple(notices))
    spec = versions.KINDS[kind]
    columns, split = changed_columns(tx, kind, allowed, found, notices, row)
    if columns:
        assignments = ', '.join(f'{column}=?' for column in columns)
        tx.db.execute(f'UPDATE {spec.table} SET {assignments} WHERE row=?', (*columns.values(), row['row']))
    if allowed.get('refs') is not None:
        tx.db.execute('DELETE FROM refs WHERE owner=? AND owner_row=?', (kind, row['row']))
        rows.write_refs(tx, kind, int(row['row']), refs_fit(allowed['refs'])[0])
    if split:
        target_kind, target_id = (('element', str(columns.get('element_id', row['element_id']))) if kind == 'property'
                                  else _node_of(kind, thing, row))
        rows.split_items(tx, found, target_kind, target_id, split)
    if versions.current_of_row(tx.db, kind, int(row['row'])) is not None:
        updated = tx.db.execute(f'SELECT * FROM {spec.table} WHERE row=?', (row['row'],)).fetchone()
        versions.drop_current(tx.db, kind, 'row', row['row'])
        versions.insert_current(tx.db, kind, thing, updated)
    if kind == 'join' and 'parent' in columns:
        _lift(tx, found, thing, str(columns['parent']), notices)
    record = views.version(tx, kind, tx.db.execute(f'SELECT * FROM {spec.table} WHERE row=?',
                                                   (row['row'],)).fetchone())
    return _with(record, notices)


def _node_of(kind: str, thing: str, row: Any) -> tuple[str, str]:
    """Where items split from a changed row attach: the thing itself, or an item's own node."""
    if kind == 'item':
        return str(row['target_kind']), str(row['target_id'])
    return kind, thing


def remove(tx: Tx, thing: str | int) -> Outcome:
    """Delete a row a knowledge layer or a building intake wrote, with its refs, STORE-032.

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
    spec = versions.KINDS[kind]
    tx.db.execute('DELETE FROM refs WHERE owner=? AND owner_row=?', (kind, row['row']))
    versions.drop_current(tx.db, kind, 'row', row['row'])
    if kind == 'item':
        operations.cleanup(tx, 'item', str(thing))
    tx.db.execute(f'DELETE FROM {spec.table} WHERE row=?', (row['row'],))
    if not users:
        return Outcome()
    return Outcome((Notice('id', f'{thing} was still used in {found.name} by {", ".join(users)}; '
                                 f'{"that is" if len(users) == 1 else "those are"} now orphaned.'),))


def _remove_ref(tx: Tx, ref_id: int) -> Outcome:
    ref = tx.db.execute('SELECT owner, owner_row FROM refs WHERE ref_id=?', (ref_id,)).fetchone()
    if ref is None:
        raise StoreError(f'No ref {ref_id}.', 'metaform map where <address>')
    table = versions.KINDS[str(ref['owner'])].table
    layer_id = tx.db.execute(f'SELECT layer_id FROM {table} WHERE row=?', (ref['owner_row'],)).fetchone()[0]
    stop = unchangeable(tx, rows.layer(tx, str(layer_id)), str(ref_id))
    if stop is not None:
        return Outcome((stop,))
    tx.db.execute('DELETE FROM refs WHERE ref_id=?', (ref_id,))
    return Outcome()


def _users(tx: Tx, kind: str, thing: str, found: LayerRow) -> list[str]:
    """The current rows of the same layer that use a thing as receiver, provider, parent join, held element or
    target."""
    db = tx.db
    users: list[str] = []
    if kind == 'element':
        users += [str(row[0]) for row in db.execute('SELECT c.join_id FROM current_joins c JOIN joins j ON j.row = c.row '
                                                    'WHERE c.receiver=? AND j.layer_id=?', (thing, found.layer_id))]
        users += [str(row[0]) for row in db.execute('SELECT c.join_id FROM current_joins c JOIN joins j ON j.row = c.row '
                                                    'WHERE c.provider=? AND j.layer_id=?', (thing, found.layer_id))]
        users += [str(row[0]) for row in db.execute('SELECT c.join_id FROM current_subtypes c JOIN joins j '
                                                    'ON j.row = c.row WHERE c.provider=? AND j.layer_id=?',
                                                    (thing, found.layer_id))]
        users += [str(row[0]) for row in db.execute('SELECT property_id FROM current_properties WHERE element_id=? '
                                                    'AND layer_id=?', (thing, found.layer_id))]
    if kind == 'join':
        users += [str(row[0]) for row in db.execute('SELECT c.join_id FROM current_subtypes c JOIN joins j '
                                                    'ON j.row = c.row WHERE c.parent=? AND j.layer_id=?',
                                                    (thing, found.layer_id))]
    if kind in ('element', 'join'):
        users += [str(row[0]) for row in db.execute('SELECT item_id FROM current_items WHERE target_kind=? AND '
                                                    'target_id=? AND layer_id=?', (kind, thing, found.layer_id))]
    return users
