"""Which layers reach each address: select, mask, hiding and the starting selection.

LAYER-007 and STORE-019: effective = (incoming & mask) | select, walked from
trunk to leaf, starting from the toggled layers, LAYER-019. Hidden layers,
and every layer built from a hidden layer, are removed at the end, STORE-013.
Building layers are never selected, STORE-032. Correction layers take no part:
they are always applied, LAYER-011. Every read resolves layers through one
`Resolver`, so no path lets an excluded layer through.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .ids import is_id, prefixes


@dataclass(frozen=True)
class LayerRow:
    layer_id: str
    metaform_id: str
    name: str
    module: str
    variable: str
    mutable: bool
    hideable: bool
    result_id: str | None
    kind: str
    created: str
    ready: str | None

    @property
    def finished(self) -> bool:
        return self.ready is not None


LAYER_COLUMNS = 'layer_id, metaform_id, name, module, variable, mutable, hideable, result_id, kind, created, ready'


def layer_row(row: sqlite3.Row) -> LayerRow:
    return LayerRow(row['layer_id'], row['metaform_id'], row['name'], row['module'], row['variable'],
                    bool(row['mutable']), bool(row['hideable']), row['result_id'], row['kind'], row['created'],
                    row['ready'])


def all_layers(db: sqlite3.Connection) -> dict[str, LayerRow]:
    """Every layer, in creation order. A full read of `layers` is allowed, STORE-005."""
    rows = db.execute(f'SELECT {LAYER_COLUMNS} FROM layers ORDER BY rowid').fetchall()
    return {row['layer_id']: layer_row(row) for row in rows}


def hidden_closure(db: sqlite3.Connection) -> set[str]:
    """Hidden layers and every layer built from one, directly or through other sources, D13."""
    hidden = {row[0] for row in db.execute('SELECT layer_id FROM hidden_layers')}
    if not hidden:
        return hidden
    sources: dict[str, set[str]] = {}
    for layer_id, source in db.execute('SELECT layer_id, source_layer_id FROM layer_sources'):
        sources.setdefault(layer_id, set()).add(source)
    changed = True
    while changed:
        changed = False
        for layer_id, built_from in sources.items():
            if layer_id not in hidden and built_from & hidden:
                hidden.add(layer_id)
                changed = True
    return hidden


def resolve_names(db: sqlite3.Connection, layers: dict[str, LayerRow], names: Iterable[str]) -> list[str]:
    """Layer ids for names, ids and tags, STORE-038: a name that is no layer is a tag.

    A name that is neither turns nothing on, CLI-033; the `layers` setting names it in a notice when it is set.
    """
    by_name = {layer.name: layer.layer_id for layer in layers.values()}
    found: list[str] = []
    for name in names:
        if is_id(name) and name in layers:
            found.append(name)
        elif name in by_name:
            found.append(by_name[name])
        else:
            found.extend(row[0] for row in db.execute('SELECT layer_id FROM layer_tags WHERE tag=?', (name,)))
    return found


class Resolver:
    """The effective selection at any address, from one starting selection."""

    def __init__(self, db: sqlite3.Connection, root: Sequence[str] | None, toggled: Sequence[str]) -> None:
        self.db = db
        self.layers = all_layers(db)
        self.hidden = hidden_closure(db)
        names = root if root is not None else (toggled or None)
        if names is None:
            start = {layer_id for layer_id, layer in self.layers.items() if self._selectable(layer)}
        else:
            start = {layer_id for layer_id in resolve_names(db, self.layers, names)
                     if self._selectable(self.layers[layer_id])}
        self.start = frozenset(start)
        self._rows: dict[str, list[tuple[str, str]]] = {}
        self._at: dict[str, frozenset[str]] = {}

    def _selectable(self, layer: LayerRow) -> bool:
        return layer.finished and layer.kind != 'correction' and layer.layer_id not in self.hidden

    def rows(self, address: str) -> list[tuple[str, str]]:
        """The select and mask rows at one address: one primary-key range read, cached."""
        if address not in self._rows:
            self._rows[address] = [(row[0], row[1]) for row in self.db.execute(
                'SELECT layer_id, kind FROM selections WHERE address=?', (address,))]
        return self._rows[address]

    def at(self, address: str) -> frozenset[str]:
        """The layer ids that reach this address, correction layers excluded."""
        if address in self._at:
            return self._at[address]
        chain = prefixes(address)
        parent = chain[-2] if len(chain) > 1 else None
        incoming = self.at(parent) if parent is not None else self.start
        current = set(incoming)
        rows = self.rows(address)
        for layer_id, kind in rows:
            if kind == 'mask':
                current.discard(layer_id)
        for layer_id, kind in rows:
            if kind == 'select' and self._selectable(self.layers[layer_id]):
                current.add(layer_id)
        result = frozenset(current - self.hidden)
        self._at[address] = result
        return result

    def reaches(self, layer_id: str, address: str | None) -> bool:
        """Whether a layer's content shows at an address in context. Correction layers always do."""
        layer = self.layers.get(layer_id)
        if layer is None:
            return False
        if layer.kind == 'correction':
            return layer.finished
        if address is None:
            return False
        return layer_id in self.at(address)

    def unresolved(self, address: str) -> list[dict[str, str]]:
        """Select and mask rows on the way to an address whose layer is hidden or still building."""
        found: list[dict[str, str]] = []
        for prefix in prefixes(address):
            for layer_id, kind in self.rows(prefix):
                layer = self.layers[layer_id]
                if not layer.finished or layer_id in self.hidden:
                    found.append({'address': prefix, 'layer': layer.name, 'kind': kind})
        return found
