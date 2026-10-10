"""Writing the map's objects into a layer: elements, joins, items, properties and their refs, STORE-024.

Every function works inside one open write transaction and never refuses a
write for its content, BASE-044 and STORE-026: what does not fit is stored as
given, and the result carries a notice for it. A write aimed at something that
cannot change in place, what a finished base holds or memory through the
knowledge tool, writes nothing and returns a notice naming the operation that
does it. The finished base still takes additions: the base grows in its
own layer, LAYER-025. Only a reference that cannot be read at all,
such as an id that names nothing, raises `StoreError`. Every write is ops on the
base's projection, appended to the log at commit, STORE-046.
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
from .records import ROLES, Element, Item, Join, Node, Notice, Outcome, Property, Ref, Version
from .rows import Row
from .selection import LayerRow, all_layers
from .session import Tx
from .versions import BASE_KINDS

RecordT = TypeVar('RecordT', Element, Join, Item, Property, Version)


def _as_answers(value: Any, notices: list[Notice]) -> list[Any]:
    """One answer per item: a list given as one value becomes one item per member, STORE-004."""
    if isinstance(value, (list, tuple)):
        members: list[Any] = list(cast(Iterable[Any], value))
        notices.append(Notice('value', f'The value was a list of {count(len(members))} answers; each was stored as its '
                                       'own item.'))
        return members
    return [value]


# Elements and joins ---------------------------------------------------------------------------------------

def _element_fields(name_length: Any, role: Any, found: LayerRow,
                    notices: list[Notice]) -> tuple[Any, str | None, list[tuple[str, Any]]]:
    """An element's name_length and role as its version holds them, STORE-009, each stored as given and named in a
    notice when it does not fit, BASE-044: a name_length that is not a whole number of at least 1, or a role outside
    the five. A role is the intake's classification of the artifact, D48: one given in another layer is not the
    element's; it is kept as an item of that layer at the element, returned here to be written, so nothing given is
    lost.
    """
    if name_length is not None and not rows.whole_number(name_length):
        notices.append(Notice('name_length', 'name_length is not a whole number; it was stored as given.'))
    elif name_length is not None and int(name_length) < 1:
        notices.append(Notice('name_length', 'name_length is less than 1; it was stored as given.'))
    stored_role: str | None = None
    aside: list[tuple[str, Any]] = []
    if role is not None and found.kind not in BASE_KINDS:
        aside.append(('role', role))
        notices.append(Notice('role', f"A role is the intake's classification of the artifact, and {found.name} is "
                                      f'not the intake; the role was kept as an item of {found.name} at the element.'))
    elif role is not None:
        stored_role = rows.text(role, 'role', notices)
        if stored_role not in ROLES:
            notices.append(Notice('role', f'{role!r} is not CQU, DE, SE or NE; it was stored as given.'))
    return name_length, stored_role, aside


def add_element(tx: Tx, layer: str, address: Any, *, name_length: Any = None, role: Any = None,
                name: Any = None) -> Element | Outcome:
    """Write an element, its address, name_length, name and role, or return the one already at the
    address, STORE-009. Its name is the canonical name the project uses for it."""
    if not isinstance(address, str):
        raise StoreError(f'{address!r} is not an address: an address is text.', 'metaform map where <address>')
    found = rows.layer(tx, layer)
    notices: list[Notice] = []
    if not rows.address_form(address):
        notices.append(Notice('address', f'{address!r} is not in the address form, dotted lowercase segments of '
                                         'letters, digits and underscores; it was stored as given.'))
    current = rows.current_element(tx, address)
    if current is not None:
        element_id = str(current['element_id'])
        record = views.element(tx, element_id, None)
        assert record is not None
        given = (('name_length', name_length is not None and name_length != record.name_length),
                 ('name', name is not None and name != record.name),
                 ('role', role is not None and role != record.role))
        notices += [Notice(field, f'{address} is already element {element_id} of layer {record.layer}, which keeps '
                                  f'its own {field}; the {field} given here was not applied.')
                    for field, unapplied in given if unapplied]
        return _with(record, notices, existing=True, differs=any(unapplied for _, unapplied in given))
    length, stored_role, aside = _element_fields(name_length, role, found, notices)
    element_id = rows.new_element(tx, found, address, name_length=length, role=stored_role,
                                  name=rows.text(name, 'name', notices))
    rows.split_items(tx, found, 'element', element_id, aside)
    record = views.element(tx, element_id, None)
    assert record is not None
    return _with(record, notices)


def _with(record: RecordT, notices: list[Notice], **changes: Any) -> RecordT:
    """The record with the write's notices, BASE-044."""
    return dataclasses.replace(record, notices=tuple(notices), **changes)


def _addresses(value: Any) -> list[Any]:
    """The elements a join is given: one address or id, or a list of them."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(cast(Iterable[Any], value))
    return [value]


def held_ids(tx: Tx, elements: Any, found: LayerRow, notices: list[Notice]) -> list[str]:
    """The ids of the elements a join holds, in the order given, each made in the layer when its address holds none;
    an element named twice is held once."""
    ids: list[str] = []
    for each in _addresses(elements):
        element_id = rows.element_at(tx, each, found, 'elements', notices)
        if element_id in ids:
            notices.append(Notice('elements', f'{each} was named twice; the join holds it once.'))
            continue
        ids.append(element_id)
    return ids


def add_join(tx: Tx, layer: str, receiver: Any, elements: Any, *, purpose: Any = None, ef: Any = None,
             ifd: Any = None, type: Any = 'purpose') -> Join | Outcome:
    """Write one join: held by its receiver, holding the elements that serve its purpose,
    with its type, purpose, ef and ifd, STORE-010."""
    found = rows.layer(tx, layer)
    notices: list[Notice] = []
    texts = {field: rows.text(value, field, notices) for field, value in (('purpose', purpose), ('ef', ef))}
    kind = rows.text(type, 'type', notices) or 'purpose'
    if kind != 'purpose':
        notices.append(Notice('type', f'{kind!r} is not purpose; it was stored as given.'))
    receiver_id = rows.element_at(tx, receiver, found, 'receiver', notices)
    ids = held_ids(tx, elements, found, notices)
    if not ids:
        notices.append(Notice('elements', 'The join holds no element; it was stored as given.'))
    if receiver_id in ids:
        notices.append(Notice('elements', 'The join holds its own receiver; it was stored as given, D82.'))
    join_id = new_id()
    tx.emit('add', 'join', join_id, found.id, {'mode': 'add', 'type': kind, 'receiver': receiver_id,
                                              'purpose': texts['purpose'], 'ef': texts['ef'],
                                              'ifd': _ifd(ifd, notices), 'element': None, 'held': ids})
    current = rows.current_join(tx, join_id)
    assert current is not None
    return _with(views.join(tx, join_id, current, all_layers(tx.base)), notices)


IFDS = ('sends', 'receives', 'both')  # IFD, Information Flow Direction
IFD_SPELLINGS = {'send': 'sends', 'receive': 'receives'}  # the intake procedure's spelling, stored as the store's


def _ifd(value: Any, notices: list[Notice]) -> str | None:
    """A join's Information Flow Direction: sends, receives or both, the procedure's send and receive read as them;
    anything else is stored as given, BASE-044."""
    if value is None or value in IFDS:
        return value
    if value in IFD_SPELLINGS:
        return IFD_SPELLINGS[value]
    notices.append(Notice('ifd', f'{value!r} is not sends, receives or both; it was stored as given.'))
    return str(value)


def add_ref(tx: Tx, owner: str, key: Any, value: Any) -> Ref | Outcome:
    """Add one ref to an item's or a property's current version, STORE-012. The base holds no refs; an element's
    refs are items of the sources layer."""
    key = key if isinstance(key, str) else json.dumps(key, ensure_ascii=False, sort_keys=True)
    value = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    kind = rows.kind_of(tx, owner)
    if kind not in ('item', 'property'):
        return Outcome((Notice('owner', f'{owner} is a {kind}, and the base holds no refs; an element\'s refs go '
                                        'in the sources layer. Nothing was written.'),))
    current = versions.current_version(tx.base, kind, owner)
    if current is None:
        return Outcome((Notice('owner', f'{owner} has no current version; nothing was written. See metaform map '
                                        f'history {owner}'),))
    rows.write_refs(tx, kind, current.seq, [(key, value)], start=len(current.refs))
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

    Sent to a type address, it goes on the element there, made when the project has none. Sent to a join, it is
    stored as given, orphaned, with the target in its `extra`: properties attach only to elements.
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
    made: list[str] = []
    for answer in answers:
        property_id = new_id()
        tx.emit('add', 'property', property_id, found.id, {'mode': 'add', 'element_id': element_id,
                                                          'value': encode_value(answer, 'the property'),
                                                          'extra': encode_extra(kept_extra, 'the property'),
                                                          'refs': [list(pair) for pair in pairs]})
        made.append(property_id)
    rows.split_items(tx, found, 'element', element_id, split)
    current = versions.current_version(tx.base, 'property', made[0])
    assert current is not None
    return _with(views.prop(tx, made[0], current, all_layers(tx.base)), notices)


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


def _memory_item(tx: Tx, item_id: str, change: str) -> tuple[Row, LayerRow] | Notice:
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
    tx.emit('change', 'item', item_id, row.layer_id, {'mode': 'place', 'value': encode_value(value, item_id)})
    return views.item_by_id(tx, item_id)


def delete_item(tx: Tx, item_id: str) -> Outcome:
    found = _memory_item(tx, item_id, 'remove')
    if isinstance(found, Notice):
        return Outcome((found,))
    row, _ = found
    tx.emit('remove', 'item', item_id, row.layer_id, {'mode': 'place'})
    return Outcome()


# Edit and remove, in place, in a knowledge layer or a building base ----------------------------------------

def unchangeable(tx: Tx, found: LayerRow, thing: str) -> Notice | None:
    """Why a thing cannot change in place: memory has its own operations; the finished base changes only by
    refining, which keeps every version, LAYER-025."""
    if found.kind == 'memory':
        return Notice('id', f'{thing} is a memory; change it with the memory operations, such as metaform memory '
                            'delete_observations. Nothing was written.')
    if found.kind in BASE_KINDS and found.finished:
        return Notice('id', f'{thing} belongs to {found.name}; the base changes by refining, which keeps every '
                            f'version: {rows.refine_step(thing)}. Nothing was written.')
    return None


MOVED = ("An element cannot be moved: its address is its identity, and another address is a different element, "
         "MAP-015. address was not applied; record the element at the new address and move its joins to it with "
         "receiver or elements.")
HELD = '_held'  # the key changed_columns gives a join's new elements under, written as the version's held list


def split_changes(kind: str, changes: dict[str, Any], notices: list[Notice]) -> dict[str, Any]:
    """The changes a thing of this kind takes; any other key is named in a notice and not applied, STORE-034. An
    element's address is never applied, MAP-015. Items and properties take refs; the base holds none."""
    allowed: dict[str, Any] = {}
    takes_refs = kind in ('item', 'property')
    for key, value in changes.items():
        if kind == 'element' and key == 'address':
            notices.append(Notice('address', MOVED))
        elif (key == 'refs' and takes_refs) or key in rows.EDITABLE[kind]:
            allowed[key] = value
        else:
            fields = ', '.join(rows.EDITABLE[kind]) + (' and refs' if takes_refs else '')
            notices.append(Notice(key, f'{key} is not a field of a {kind}; it was not applied. The fields are '
                                       f'{fields}.'))
    return allowed


def changed_columns(tx: Tx, kind: str, changes: dict[str, Any], found: LayerRow, notices: list[Notice],
                    base: Row) -> tuple[dict[str, Any], list[tuple[str, Any]]]:
    """The field values of a change of `base`, each checked the way a write checks it; and records split from an
    extra. A join's `elements` come back under HELD, the ids of the elements it now holds."""
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
            kept, more = rows.extra_fields(value, kind, notices)
            split += more  # added to what refs split out in the same change, never in its place
            columns['extra'] = encode_extra(kept, kind)
        elif key == 'value':
            answers = _as_answers(value, notices)
            columns['value'] = encode_value(answers[0] if answers else None, kind)
            split += [('value', answer) for answer in answers[1:]]
        elif kind == 'join' and key == 'elements':
            columns[HELD] = held_ids(tx, value, found, notices)
        elif kind == 'join' and key == 'element':
            element = rows.element_at(tx, value, found, key, notices) if value is not None else None
            columns[key] = views.address_of(tx, element) if element is not None else None
        elif key in ('receiver', 'element'):
            columns['element_id' if key == 'element' else key] = rows.element_at(tx, value, found, key, notices)
        elif key == 'link':
            if value is None:
                columns['link_kind'], columns['link_id'] = None, None
            else:
                link = value if isinstance(value, Node) else Node.parse(str(value))
                columns['link_kind'], columns['link_id'] = rows.node_at(tx, link, found, 'link', notices)
        elif kind == 'element' and key in ('name_length', 'role'):
            length, role, kept = _element_fields(value if key == 'name_length' else None,
                                                 value if key == 'role' else None, found, notices)
            split += kept
            if not kept:
                columns[key] = length if key == 'name_length' else role
        elif kind == 'join' and key == 'ifd':
            columns[key] = _ifd(value, notices)
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


def edit(tx: Tx, thing: str, changes: Any) -> Version | Outcome:
    """Change a thing of a knowledge layer, or of a building base, in place, STORE-032.

    A join's receiver moves it, and it stays the same join, MAP-003, and `elements` gives the elements it holds; an
    element's address is never changed, MAP-015.
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
    allowed = split_changes(kind, {str(key): value for key, value in given_changes.items()}, notices)
    if not allowed:
        return Outcome(tuple(notices))
    columns, split = changed_columns(tx, kind, allowed, found, notices, row)
    held = columns.pop(HELD, None)
    data: dict[str, Any] = {'mode': 'place', **columns}
    if held is not None:
        data['held'] = held
    if allowed.get('refs') is not None:
        data['refs'] = [list(pair) for pair in refs_fit(allowed['refs'])[0]]
    if len(data) > 1:
        tx.emit('change', kind, thing, row.layer_id, data)
    if split:
        target_kind, target_id = (('element', str(columns.get('element_id', row['element_id']))) if kind == 'property'
                                  else _node_of(kind, thing, row))
        rows.split_items(tx, found, target_kind, target_id, split)
    record = views.version(tx, kind, thing, row)
    return _with(record, notices)


def _node_of(kind: str, thing: str, row: Any) -> tuple[str, str]:
    """Where items split from a changed row attach: the thing itself, or an item's own node."""
    if kind == 'item':
        return str(row['target_kind']), str(row['target_id'])
    return kind, thing


def remove(tx: Tx, thing: str | int) -> Outcome:
    """Delete a version a knowledge layer or a building base wrote, with its refs, STORE-032.

    What in the same layer still used it as receiver, held element or target is left orphaned and named, STORE-017.
    """
    if isinstance(thing, int):
        return _remove_ref(tx, thing)
    kind = rows.kind_of(tx, thing)
    row, found = rows.own_row(tx, kind, thing)
    stop = unchangeable(tx, found, thing)
    if stop is not None:
        return Outcome((stop,))
    users = _users(tx, kind, thing, found)
    if kind == 'item':
        operations.cleanup(tx, 'item', str(thing))
    tx.emit('remove', kind, thing, row.layer_id, {'mode': 'place'})
    if not users:
        return Outcome()
    return Outcome((Notice('id', f'{thing} was still used in {found.name} by {", ".join(users)}; '
                                 f'{"that is" if len(users) == 1 else "those are"} now orphaned.'),))


def _remove_ref(tx: Tx, ref_id: int) -> Outcome:
    """A ref named by its number: the sequence of the version that holds it and its position, as `(seq << 16) + position`."""
    seq, position = divmod(ref_id, 1 << 16)
    for kind in ('item', 'property'):
        found = rows.version_at(tx, kind, seq)
        if found is None:
            continue
        ident, version = found
        stop = unchangeable(tx, rows.layer(tx, version.layer_id), str(ref_id))
        if stop is not None:
            return Outcome((stop,))
        if position >= len(version.refs):
            break
        kept = [list(pair) for index, pair in enumerate(version.refs) if index != position]
        tx.emit('change', kind, ident, version.layer_id, {'mode': 'place', 'refs': kept})
        return Outcome()
    raise StoreError(f'No ref {ref_id}.', 'metaform map where <address>')


def _users(tx: Tx, kind: str, thing: str, found: LayerRow) -> list[str]:
    """The current things of the same layer that use a thing as receiver, held element or target."""
    base = tx.base
    users: list[str] = []

    def in_layer(ident: str) -> bool:
        current = base.current(ident)
        return current is not None and current.layer_id == found.id

    if kind == 'element':
        users += [join_id for join_id in base.joins_received(thing) if in_layer(join_id)]
        users += [join_id for join_id in base.joins_holding(thing) if in_layer(join_id) and join_id not in users]
        users += [property_id for property_id in base.properties_of(thing) if in_layer(property_id)]
    if kind in ('element', 'join'):
        users += [item_id for item_id in base.items_at(kind, thing) if in_layer(item_id)]
    return users
