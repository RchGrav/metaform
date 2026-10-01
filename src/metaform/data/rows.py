"""Row-level helpers every store operation shares, each working inside one open transaction, STORE-023.

These find layers and things by reference, write the rows that come with every
thing (its types, identity and refs), and hold the rules for what does not fit
a write: text that is not text, an `extra` that is not an object or holds a
list of records, a join end or an attachment that names no element. What does
not fit is kept as given and named in a notice, BASE-044; only a reference that
cannot be read at all raises `StoreError`, STORE-026.
"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from typing import Any

from ..errors import StoreError
from ..wording import odd_refs_notice
from . import corrections
from .ids import ADDRESS, as_list, as_object, encode_extra, encode_value, is_id, new_id, prefixes
from .records import Node, Notice, Ref
from .selection import LAYER_COLUMNS, LayerRow, layer_row
from .session import Tx

EDITABLE: dict[str, tuple[str, ...]] = {
    'element': ('name_length', 'role', 'extra'),  # never the address: an element cannot be moved, MAP-015
    'join': ('receiver', 'provider', 'parent', 'type', 'name', 'purpose', 'ef', 'perspective', 'relation', 'verb',
             'observation', 'non_goal', 'extra'),  # receiver, provider and parent move it, MAP-003
    'item': ('value', 'link', 'extra'),
    'property': ('element', 'value', 'extra'),
}
TEXT_COLUMNS = ('purpose', 'ef', 'relation', 'verb', 'observation', 'non_goal', 'type', 'name')

Row = sqlite3.Row


def correct_step(thing: str = '<id>') -> str:
    return f'metaform map knowledge op=correct layer=<correction layer> id={thing} reason=<why>'


# Values that do not fit -----------------------------------------------------------------------------------------

def address_form(address: str) -> bool:
    """Whether an address has the form of MAP-010 and cannot be read as an id, STORE-008."""
    return bool(ADDRESS.fullmatch(address)) and not is_id(address)


def text(value: Any, field: str, notices: list[Notice]) -> str | None:
    """A text column's value: text as given, or anything else written as JSON text with a notice, BASE-044."""
    if value is None or isinstance(value, str):
        return value
    notices.append(Notice(field, f'{field} is not text; it was stored as the JSON text of what was given.'))
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def whole_number(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def holds_records(value: Any) -> bool:
    members = as_list(value)
    return members is not None and any(isinstance(member, dict) for member in members)


def extra_fields(extra: Any, where: str,
                 notices: list[Notice]) -> tuple[dict[str, Any] | None, list[tuple[str, Any]]]:
    """An `extra` object, and the records it held, split out to be items of their own, STORE-004 and STORE-015.

    An `extra` that is not an object is kept as `{"value": <what was given>}`. Each list of records under a key is
    taken out; each record becomes its own item, `{<key>: <record>}`, with a notice.
    """
    if extra is None:
        return None, []
    fields = as_object(extra)
    if fields is None:
        notices.append(Notice('extra', f'extra on {where} is not an object; it was kept as {{"value": ...}}.'))
        return {'value': extra}, []
    kept: dict[str, Any] = {}
    split: list[tuple[str, Any]] = []
    for key, value in fields.items():
        members = as_list(value)
        if members is not None and holds_records(members):
            split += [(str(key), member) for member in members]
            notices.append(_records_notice(str(key), where))
        else:
            kept[str(key)] = value
    return (kept or None), split


def _records_notice(key: str, where: str) -> Notice:
    return Notice('extra', f'extra.{key} on {where} held a list of records; each was stored as its own item.')


def odd_refs(odd: list[Any], kept: dict[str, Any] | None, where: str,
             notices: list[Notice]) -> tuple[dict[str, Any] | None, list[tuple[str, Any]]]:
    """Refs that are not a key and a value, both text, named once and kept in the extra under refs, STORE-012; when
    they are records, they are split into items of their own, as any list of records in an extra is, STORE-004.
    """
    if not odd:
        return kept, []
    notices.append(Notice('refs', odd_refs_notice(odd)))
    if holds_records(odd):
        notices.append(_records_notice('refs', where))
        return kept, [('refs', member) for member in odd]
    return {**(kept or {}), 'refs': odd}, []


# Finding layers and things -------------------------------------------------------------------------------------

def layer(tx: Tx, ref: object) -> LayerRow:
    """A layer by id or name; a reference to no layer cannot be read, STORE-013."""
    if not isinstance(ref, str) or not ref:
        raise StoreError('Every write names its layer.', 'metaform map layers')
    column = 'layer_id' if is_id(ref) else 'name'
    row = tx.db.execute(f'SELECT {LAYER_COLUMNS} FROM layers WHERE {column}=?', (ref,)).fetchone()
    if row is None:
        raise StoreError(f'No layer {ref}.', 'metaform map layers')
    return layer_row(row)


def layer_name(tx: Tx, layer_id: str) -> str:
    row = tx.db.execute('SELECT name FROM layers WHERE layer_id=?', (layer_id,)).fetchone()
    return str(row[0]) if row else layer_id


def frozen(tx: Tx, found: LayerRow) -> Notice | None:
    """Why a write into this layer is not applied: a finished intake and a finished correction layer."""
    if found.kind == 'intake' and found.finished and found.layer_id not in tx.created:
        return Notice('layer', f'{found.name} is the intake layer; the metaform changes only through a correction '
                               f'layer: {correct_step()}. Nothing was written.')
    if found.kind == 'correction' and found.finished:
        return Notice('layer', f'Correction layer {found.name} is finished; only the top correction layer can be '
                               f'peeled and changed: metaform map knowledge op=peel layer={found.name}. Nothing was '
                               'written.')
    return None


def top(tx: Tx) -> int:
    return corrections.top_position(tx.db)


def types(tx: Tx, address: str) -> None:
    """The address and each of its prefixes as rows of the Type tree, root first, STORE-008."""
    parent = None
    for prefix in prefixes(address):
        tx.db.execute('INSERT OR IGNORE INTO types(address, parent) VALUES (?, ?)', (prefix, parent))
        parent = prefix


def identity(tx: Tx, thing_id: str, kind: str) -> None:
    tx.db.execute('INSERT INTO identities(id, kind) VALUES (?, ?)', (thing_id, kind))


def write_refs(tx: Tx, owner: str, row: int, refs: Iterable[tuple[str, str]], start: int = 0) -> None:
    tx.db.executemany('INSERT INTO refs(owner, owner_row, position, key, value) VALUES (?, ?, ?, ?, ?)',
                      [(owner, row, start + index, key, value) for index, (key, value) in enumerate(refs)])


def read_refs(db: sqlite3.Connection, owner: str, row: int) -> tuple[Ref, ...]:
    return tuple(Ref(str(ref['key']), str(ref['value'])) for ref in db.execute(
        'SELECT key, value FROM refs WHERE owner=? AND owner_row=? ORDER BY position', (owner, row)))


def current_element(tx: Tx, ref: str) -> Row | None:
    column = 'element_id' if is_id(ref) else 'address'
    row: Row | None = tx.db.execute(f'SELECT element_id, row, address FROM current_elements WHERE {column}=?',
                                    (ref,)).fetchone()
    return row


def holding(tx: Tx, element_id: str) -> list[str]:
    """The current subtype joins that hold an element, in id order; one read on `current_subtypes_by_provider`."""
    return [str(row[0]) for row in tx.db.execute('SELECT join_id FROM current_subtypes WHERE provider=? '
                                                 'ORDER BY join_id', (element_id,))]


def held_only(tx: Tx, element_id: str) -> bool:
    """Whether an element's only current joins are subtype joins holding it, so it is no root and no node of the
    outer map, MAP-031: the one check every read of the outer map uses for it."""
    db = tx.db
    if db.execute('SELECT 1 FROM current_subtypes WHERE provider=? LIMIT 1', (element_id,)).fetchone() is None:
        return False
    return (db.execute('SELECT 1 FROM current_joins WHERE receiver=? LIMIT 1', (element_id,)).fetchone() is None and
            db.execute('SELECT 1 FROM current_joins WHERE provider=? LIMIT 1', (element_id,)).fetchone() is None)


def current_join(tx: Tx, join_id: str) -> Row | None:
    """A join's current version row, held by a receiver or, for a subtype join, by its parent join."""
    row: Row | None = tx.db.execute('SELECT j.* FROM current_joins c JOIN joins j ON j.row = c.row WHERE c.join_id=?',
                                    (join_id,)).fetchone()
    if row is None:
        row = tx.db.execute('SELECT j.* FROM current_subtypes c JOIN joins j ON j.row = c.row WHERE c.join_id=?',
                            (join_id,)).fetchone()
    return row


def owner_address(tx: Tx, row: Row) -> str | None:
    """The address a join sits at: its receiver's, or for a subtype join its parent join's receiver's, STORE-019."""
    if row['parent'] is None:
        return address_of(tx, str(row['receiver']))
    parent = tx.db.execute('SELECT receiver FROM current_joins WHERE join_id=?', (row['parent'],)).fetchone()
    return None if parent is None else address_of(tx, str(parent[0]))


def address_of(tx: Tx, element_id: str) -> str | None:
    row = tx.db.execute('SELECT address FROM current_elements WHERE element_id=?', (element_id,)).fetchone()
    return None if row is None else str(row[0])


def node_address(tx: Tx, kind: str, thing_id: str) -> str | None:
    """Where a node sits: an element's address, or a join's receiver's address, a subtype join's parent's
    receiver's."""
    if kind == 'element':
        return address_of(tx, thing_id)
    row = current_join(tx, thing_id)
    return None if row is None else owner_address(tx, row)


def kind_of(tx: Tx, thing: Any) -> str:
    """A bare id's kind, STORE-033: identities first, then properties, which have no identity row."""
    if not isinstance(thing, str) or not is_id(thing):
        raise StoreError(f'{thing!r} is not an id.', 'metaform map where <address>')
    row = tx.db.execute('SELECT kind FROM identities WHERE id=?', (thing,)).fetchone()
    if row is not None:
        return str(row[0])
    if tx.db.execute('SELECT 1 FROM properties WHERE property_id=? LIMIT 1', (thing,)).fetchone():
        return 'property'
    raise StoreError(f'No element, join, property or item has the id {thing}.', 'metaform map where <address>')


def own_row(tx: Tx, kind: str, thing: str) -> tuple[Row, LayerRow]:
    """The row a thing was added with, and the layer that added it."""
    spec = corrections.KINDS[kind]
    rows = tx.db.execute(f'SELECT * FROM {spec.table} WHERE {spec.id_column}=?', (thing,)).fetchall()
    added = [row for row in rows if row['op'] == 'add']
    if not added:
        raise StoreError(f'No {kind} has the id {thing}.', 'metaform map where <address>')
    row: Row = added[-1]
    return row, layer(tx, str(row['layer_id']))


def target_current(tx: Tx, kind: str, thing: str) -> bool:
    return corrections.current_row(tx.db, kind, thing) is not None


# Elements, made where a write needs one ---------------------------------------------------------------------

def reused_element(tx: Tx, address: str) -> str | None:
    """The element id the address last held, when no current element holds that id, STORE-009.

    An element's identity belongs to its address: an add at an address whose element was removed, by a layer's
    own remove or by a correction, is that element again, and everything still linked to it comes back with it.
    """
    held = tx.db.execute('SELECT element_id FROM address_elements WHERE address=?', (address,)).fetchone()
    if held is None:
        return None
    if tx.db.execute('SELECT 1 FROM current_elements WHERE element_id=?', (held[0],)).fetchone() is not None:
        return None
    return str(held[0])


def new_element(tx: Tx, found: LayerRow, address: str, extra: dict[str, Any] | None = None, *,
                name_length: int | None = None, role: str | None = None, refs: Iterable[tuple[str, str]] = ()) -> str:
    """Write a new element row in a layer, under the id the address held before when nothing holds it now.

    The row is the element: its address, name_length and role, STORE-009; its refs are rows owned by it.
    """
    element_id = reused_element(tx, address) or new_id()
    if tx.db.execute('SELECT 1 FROM element_ids WHERE element_id=?', (element_id,)).fetchone() is None:
        tx.db.execute('INSERT INTO element_ids(element_id) VALUES (?)', (element_id,))
        identity(tx, element_id, 'element')
    types(tx, address)
    cursor = tx.db.execute('INSERT INTO elements(element_id, layer_id, address, name_length, role, extra) '
                           'VALUES (?, ?, ?, ?, ?, ?)',
                           (element_id, found.layer_id, address, name_length, role, encode_extra(extra, address)))
    row = int(cursor.lastrowid or 0)
    corrections.hold_address(tx.db, address, element_id)
    if found.kind != 'correction':
        tx.db.execute('INSERT INTO current_elements(element_id, row, address, role) VALUES (?, ?, ?, ?)',
                      (element_id, row, address, role))
    write_refs(tx, 'element', row, refs)
    return element_id


def stub_element(tx: Tx, element_id: str | None = None) -> str:
    """An element identity with no row, so what points at it is stored orphaned, STORE-017."""
    stub = element_id or new_id()
    tx.db.execute('INSERT OR IGNORE INTO element_ids(element_id) VALUES (?)', (stub,))
    tx.db.execute("INSERT OR IGNORE INTO identities(id, kind) VALUES (?, 'element')", (stub,))
    return stub


def element_at(tx: Tx, ref: Any, found: LayerRow, what: str, notices: list[Notice]) -> str:
    """An element named by address or id. An address that names no element gets one in the writing layer.

    A bare type address, `type:<address>`, is the element there, made when the project has none, STORE-008. An id
    that names no element cannot be read.
    """
    if isinstance(ref, Node):
        if ref.kind not in ('element', 'type'):
            raise StoreError(f'{ref} is a {ref.kind}; {what} is an element.', 'metaform map where <address>')
        ref = ref.id
    if not isinstance(ref, str) or not ref:
        raise StoreError(f'The {what} {ref!r} is not an address or an element id.', 'metaform map where <address>')
    current = current_element(tx, ref)
    if current is not None:
        return str(current['element_id'])
    if found.kind == 'correction':
        column = 'element_id' if is_id(ref) else 'address'
        row = tx.db.execute(f"SELECT element_id FROM elements WHERE {column}=? AND layer_id=? AND op != 'remove'",
                            (ref, found.layer_id)).fetchone()
        if row is not None:
            return str(row[0])
    if is_id(ref):
        raise StoreError(f'No element has the id {ref}.', 'metaform map where <address>')
    notices.append(Notice(what, f'{ref} was not an element; it was created in layer {found.name}.'))
    return new_element(tx, found, ref)


def node_at(tx: Tx, node: Any, found: LayerRow, what: str, notices: list[Notice]) -> tuple[str, str]:
    """The kind and identity id of a node an item attaches to or links to.

    An element or type address with no element gets one in the writing layer. An id that names no current node is
    kept as given, so the item is stored orphaned, with a notice, BASE-044.
    """
    if not isinstance(node, Node):
        raise StoreError(f'{node!r} is not a node: give element:, join: or type:.', 'metaform help map node')
    if node.kind in ('element', 'type'):
        if node.kind == 'element' and is_id(node.id) and current_element(tx, node.id) is None:
            notices.append(Notice(what, f'No current element has the id {node.id}; stored as given, orphaned.'))
            return 'element', node.id
        if node.kind == 'type' and current_element(tx, node.id) is None:
            notices.append(Notice(what, f'{node.id} is a type address; an element was created there in layer '
                                        f'{found.name} to hold it.'))
            return 'element', new_element(tx, found, node.id)
        return 'element', element_at(tx, node.id, found, what, notices)
    if target_current(tx, 'join', node.id) or \
            tx.db.execute('SELECT 1 FROM joins WHERE join_id=? AND layer_id=?', (node.id, found.layer_id)).fetchone():
        return 'join', node.id
    notices.append(Notice(what, f'{node} is not a current join; stored as given, orphaned.'))
    return 'join', node.id


# Work records and items -------------------------------------------------------------------------------------

def open_work(tx: Tx, kind: str, thing_id: str) -> tuple[str, ...]:
    """The conditions of an object's open work records, in row order, STORE-042; one lookup on `work_by_target`."""
    conditions = tuple(str(row[0]) for row in tx.db.execute(
        'SELECT condition FROM work WHERE target_kind=? AND target_id=? AND done IS NULL ORDER BY row', (kind, thing_id)))
    # What waits for the user at the object is open at it too: a question not answered, a message not read, MAP-050.
    waiting = tuple(str(row[0]) for row in tx.db.execute(
        'SELECT kind FROM messages WHERE target_kind=? AND target_id=? AND closed IS NULL ORDER BY row', (kind, thing_id)))
    return conditions + waiting


def work_target(tx: Tx, node: Any, notices: list[Notice]) -> tuple[str, str]:
    """The kind and identity id a work record attaches to: the current element at an address, or the object with the
    id given, a subtype join being a join. A node that names no current object is kept as written, with a notice,
    BASE-044."""
    if not isinstance(node, Node):
        raise StoreError(f'{node!r} is not a node: write element:<address or id> or join:<id>.',
                         'metaform help map work')
    kind, ident = node.kind, node.id
    if kind == 'type':
        notices.append(Notice('node', f'{node} is a type address, which no work record attaches to; it was stored as '
                                      'given, as an element node.'))
        kind = 'element'
    if kind == 'element':
        current = current_element(tx, ident)
        if current is not None:
            return kind, str(current['element_id'])
    elif target_current(tx, 'join', ident):
        return kind, ident
    notices.append(Notice('node', f'No current {kind} is at {ident}; the work record was stored as given and will '
                                  'show once one is recorded there.'))
    return kind, ident


def insert_item(tx: Tx, found: LayerRow, target_kind: str, target_id: str, value: Any, link_kind: str | None,
                link_id: str | None, pairs: list[tuple[str, str]], extra: dict[str, Any] | None) -> str:
    """One item row with its identity and refs; current at once unless its layer is a correction layer."""
    encoded = encode_value(value, f'{target_kind}:{target_id}')
    encoded_extra = encode_extra(extra, 'the item')
    item_id = new_id()
    tx.db.execute('INSERT INTO item_ids(item_id, layer_id) VALUES (?, ?)', (item_id, found.layer_id))
    identity(tx, item_id, 'item')
    cursor = tx.db.execute('INSERT INTO items(item_id, layer_id, target_kind, target_id, value, link_kind, link_id, '
                           'extra) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                           (item_id, found.layer_id, target_kind, target_id, encoded, link_kind, link_id,
                            encoded_extra))
    row = int(cursor.lastrowid or 0)
    if found.kind != 'correction':
        tx.db.execute('INSERT INTO current_items(item_id, row, layer_id, target_kind, target_id, link_kind, '
                      'link_id) VALUES (?, ?, ?, ?, ?, ?, ?)',
                      (item_id, row, found.layer_id, target_kind, target_id, link_kind, link_id))
    write_refs(tx, 'item', row, pairs)
    return item_id


def split_items(tx: Tx, found: LayerRow, kind: str, thing_id: str, split: list[tuple[str, Any]]) -> None:
    """The records an `extra` held, each written as its own item at the thing, STORE-004."""
    for key, record in split:
        insert_item(tx, found, kind, thing_id, {key: record}, None, None, [], None)
