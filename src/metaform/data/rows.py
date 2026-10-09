"""Row-level helpers every store operation shares, each working inside one open transaction, STORE-023.

These find layers and things by reference, write the versions that come with every
thing (its types, identity and refs), and hold the rules for what does not fit
a write: text that is not text, an `extra` that is not an object or holds a
list of records, a join end or an attachment that names no element. What does
not fit is kept as given and named in a notice, BASE-044; only a reference that
cannot be read at all raises `StoreError`, STORE-026. Everything is read from
and written to the base's projection, STORE-046.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from ..errors import StoreError
from ..wording import odd_refs_notice
from . import versions
from .ids import ADDRESS, as_list, as_object, encode_extra, encode_value, is_id, new_id
from .projection import Projection, Version
from .records import Node, Notice, Ref
from .selection import LayerRow
from .session import Tx

EDITABLE: dict[str, tuple[str, ...]] = {
    'element': ('name_length', 'name', 'role', 'within', 'note'),  # never the address: an element cannot be moved, MAP-015
    'join': ('receiver', 'elements', 'type', 'purpose', 'ef', 'ifd', 'element', 'note'),  # receiver moves it, MAP-003
    'item': ('value', 'link', 'extra', 'read_first', 'always_show'),  # the flags, LAYER-021
    'property': ('element', 'value', 'extra'),
}
TEXT_COLUMNS = ('purpose', 'ef', 'type', 'name', 'ifd', 'note', 'within')

Row = Version


def refine_step(thing: str = '<id>') -> str:
    return f'metaform map refine id={thing} <field>=<value> reason=<why>'


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
    found = tx.base.layers.get(ref) if is_id(ref) else tx.base.layer_by_name(ref)
    if found is None:
        raise StoreError(f'No layer {ref}.', 'metaform map layers')
    return found


def layer_name(tx: Tx, layer_id: str) -> str:
    found = tx.base.layers.get(layer_id)
    return found.name if found else layer_id


def types(tx: Tx, address: str) -> None:
    """The address and each of its prefixes as the Type tree, root first, STORE-008."""
    if address not in tx.base.types:
        tx.emit('add', 'type', address, '', {'address': address})


def identity(tx: Tx, thing_id: str, kind: str) -> None:
    tx.base.kinds.setdefault(thing_id, kind)


def read_refs(base: Projection, owner: str, row: int) -> tuple[Ref, ...]:
    version = _version_at(base, row)
    return tuple(Ref(key, value) for key, value in version.refs) if version is not None else ()


def _version_at(base: Projection, seq: int) -> Version | None:
    found = base.version_at(seq)
    return None if found is None else found[1]


def version_at(tx: Tx, kind: str, seq: int) -> tuple[str, Version] | None:
    """The thing and the version at a sequence, STORE-005."""
    found = tx.base.version_at(seq)
    if found is None or tx.base.kinds.get(found[0]) != kind:
        return None
    return found


def current_element(tx: Tx, ref: str) -> dict[str, Any] | None:
    """The current element by id or address: its id, row and address."""
    element_id = ref if is_id(ref) else tx.base.element_at(ref)
    if element_id is None:
        return None
    version = versions.current_version(tx.base, 'element', element_id)
    if version is None:
        return None
    return {'element_id': element_id, 'row': version.seq, 'address': str(version.fields['address'])}


def holding(tx: Tx, element_id: str) -> list[str]:
    """The current joins that hold an element, in id order."""
    return tx.base.joins_holding(element_id)


def held_elements(base: Projection, join_row: int) -> list[str]:
    """The ids of the elements one version of a join holds, in order."""
    version = _version_at(base, join_row)
    return [str(each) for each in version.fields.get('held', ())] if version is not None else []


def current_join(tx: Tx, join_id: str) -> Version | None:
    """A join's current version."""
    return versions.current_version(tx.base, 'join', join_id)


def owner_address(tx: Tx, row: Version) -> str | None:
    """The address a join sits at: its receiver's, STORE-019."""
    return address_of(tx, str(row['receiver']))


def address_of(tx: Tx, element_id: str) -> str | None:
    return tx.base.address_of(element_id)


def node_address(tx: Tx, kind: str, thing_id: str) -> str | None:
    """Where a node sits: an element's address, or a join's receiver's address."""
    if kind == 'element':
        return address_of(tx, thing_id)
    row = current_join(tx, thing_id)
    return None if row is None else owner_address(tx, row)


def kind_of(tx: Tx, thing: Any) -> str:
    """A bare id's kind, STORE-033, from the objects registry."""
    if not isinstance(thing, str) or not is_id(thing):
        raise StoreError(f'{thing!r} is not an id.', 'metaform map where <address>')
    kind = tx.base.kinds.get(thing)
    if kind is None:
        raise StoreError(f'No element, join, property or item has the id {thing}.', 'metaform map where <address>')
    return kind


def own_row(tx: Tx, kind: str, thing: str) -> tuple[Version, LayerRow]:
    """The version a thing was added with, and the layer that added it."""
    own = versions.own_version(tx.base, thing)
    if own is None or tx.base.kinds.get(thing) != kind:
        raise StoreError(f'No {kind} has the id {thing}.', 'metaform map where <address>')
    return own, layer(tx, own.layer_id)


def target_current(tx: Tx, kind: str, thing: str) -> bool:
    return versions.current_row(tx.base, kind, thing) is not None


# Elements, made where a write needs one ---------------------------------------------------------------------

def reused_element(tx: Tx, address: str) -> str | None:
    """The element id the address last held, when no current element holds that id, STORE-009.

    An element's identity belongs to its address: an add at an address whose element was removed, by a layer's
    own remove or by a refinement, is that element again, and everything still linked to it comes back with it.
    """
    held = tx.base.address_last.get(address)
    if held is None or tx.base.is_current(held):
        return None
    return held


def new_element(tx: Tx, found: LayerRow, address: str, *, name_length: Any = None, role: str | None = None,
                name: str | None = None) -> str:
    """Write a new element version in a layer, under the id the address held before when nothing holds it now.

    The version is the element: its address, name_length, name and role, STORE-009.
    """
    element_id = reused_element(tx, address) or new_id()
    tx.emit('add', 'element', element_id, found.id, {'mode': 'add', 'address': address, 'name_length': name_length,
                                                    'name': name, 'role': role})
    return element_id


def stub_element(tx: Tx, element_id: str | None = None) -> str:
    """An element identity with no version, so what points at it is stored orphaned, STORE-017."""
    stub = element_id or new_id()
    if stub not in tx.base.kinds:  # an id is registered by its first op; a stub's is a removal of nothing
        tx.emit('remove', 'element', stub, '', {'mode': 'place'})
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
    if target_current(tx, 'join', node.id) or any(
            version.layer_id == found.id for version in tx.base.versions.get(node.id, ())
            if tx.base.kinds.get(node.id) == 'join'):
        return 'join', node.id
    notices.append(Notice(what, f'{node} is not a current join; stored as given, orphaned.'))
    return 'join', node.id


# Items ------------------------------------------------------------------------------------------------------


def insert_item(tx: Tx, found: LayerRow, target_kind: str, target_id: str, value: Any, link_kind: str | None,
                link_id: str | None, pairs: list[tuple[str, str]], extra: dict[str, Any] | None,
                read_first: Any = False, always_show: Any = False) -> str:
    """One item version with its identity, refs and flags, LAYER-021, current at once."""
    encoded = encode_value(value, f'{target_kind}:{target_id}')
    encoded_extra = encode_extra(extra, 'the item')
    item_id = new_id()
    tx.emit('add', 'item', item_id, found.id, {'mode': 'add', 'target_kind': target_kind, 'target_id': target_id,
                                              'value': encoded, 'link_kind': link_kind, 'link_id': link_id,
                                              'extra': encoded_extra, 'read_first': int(bool(read_first)),
                                              'always_show': int(bool(always_show)),
                                              'refs': [list(pair) for pair in pairs]})
    return item_id


def split_items(tx: Tx, found: LayerRow, kind: str, thing_id: str, split: list[tuple[str, Any]]) -> None:
    """The records an `extra` held, each written as its own item at the thing, STORE-004."""
    for key, record in split:
        insert_item(tx, found, kind, thing_id, {key: record}, None, None, [], None)


def write_refs(tx: Tx, owner: str, row: int, refs: Iterable[tuple[str, str]], start: int = 0) -> None:
    """Refs added to one version of an item or a property, in place."""
    found = version_at(tx, owner, row)
    if found is None:
        return
    ident, version = found
    kept = list(version.refs[:start]) + [(key, value) for key, value in refs]
    tx.emit('change', owner, ident, version.layer_id, {'mode': 'place', 'refs': [list(pair) for pair in kept]})
