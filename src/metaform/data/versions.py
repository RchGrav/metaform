"""The current version of each thing, and what a refinement leaves behind, STORE-034, STORE-036 and LAYER-025.

Every thing keeps every version written for it, in the op log. Its current version is its newest, unless that one
is a removal, which leaves it out of the current set. The base is refined in its own base layer: a refinement is
one more version of the thing in that layer, so nothing is lost and no layer is made. An element's address never
changes, MAP-015; a join can be moved to another receiver and stays the same join, MAP-003.
"""
from __future__ import annotations

from .projection import OBJECT_KINDS, Projection, Version
from .records import Notice

BASE_KINDS = ('base',)
ORDER = OBJECT_KINDS


def current_row(base: Projection, kind: str, thing_id: str) -> int | None:
    """The sequence of a thing's current version, or None when it is not current."""
    found = base.current(thing_id)
    return None if found is None or base.kinds.get(thing_id) != kind else found.seq


def current_version(base: Projection, kind: str, thing_id: str) -> Version | None:
    found = base.current(thing_id)
    return None if found is None or base.kinds.get(thing_id) != kind else found


def own_version(base: Projection, thing_id: str) -> Version | None:
    """The version a thing was added with: the newest `add` among its versions."""
    added = [version for version in base.versions.get(thing_id, ()) if version.op == 'add']
    return added[-1] if added else None


def _of_base(base: Projection, layer_id: str) -> bool:
    layer = base.layers.get(layer_id)
    return layer is not None and layer.kind in BASE_KINDS


def orphaned_by(base: Projection, kind: str, thing_id: str) -> list[Notice]:
    """STORE-034: what of the base is left pointing at a thing a refinement removed is orphaned and named."""
    notices: list[Notice] = []
    if kind == 'element':
        joins = sorted(set(base.joins_received(thing_id)) | set(base.joins_holding(thing_id)))
        for join_id in joins:
            version = base.current(join_id)
            if version is not None and _of_base(base, version.layer_id):
                notices.append(Notice(join_id, f'Element {thing_id} was removed; join {join_id} still points at it '
                                               'and is orphaned.'))
        for property_id in base.properties_of(thing_id):
            version = base.current(property_id)
            if version is not None and _of_base(base, version.layer_id):
                notices.append(Notice(property_id, f'Element {thing_id} was removed; property {property_id} on it is '
                                                   'orphaned.'))
    return notices


def mark(tx: object, layer_id: str, thing_id: str) -> None:
    """STORE-036: every layer built from the base's layer is marked for re-examination of a thing refined in it."""
    from .session import Tx
    assert isinstance(tx, Tx)
    for dependent in tx.base.layers.values():
        if layer_id in dependent.sources:
            pairs = [list(pair) for pair in dependent.reexamine]
            if [layer_id, thing_id] not in pairs:
                pairs.append([layer_id, thing_id])
                tx.emit('change', 'layer', dependent.id, dependent.id, {'reexamine': pairs})
