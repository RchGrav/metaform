"""Which layers reach each address: select, mask, hiding and the starting selection.

LAYER-007 and STORE-019: effective = (incoming & mask) | select, walked from
trunk to leaf, starting from the toggled layers, LAYER-019. Hidden layers,
and every layer built from a hidden layer, are removed at the end, STORE-013.
Building layers are never selected, STORE-032. There are no correction
layers, LAYER-025. Every read resolves layers through one
`Resolver`, so no path lets an excluded layer through. The layers, their
sources, the hidden set and the select and mask rows are read from the
projection, STORE-046.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence

from .ids import is_id, prefixes
from .projection import LayerRec, Projection

LayerRow = LayerRec


def all_layers(base: Projection) -> dict[str, LayerRow]:
    """Every layer, in creation order."""
    return dict(sorted(base.layers.items(), key=lambda pair: pair[1].seq))


def hidden_closure(base: Projection) -> set[str]:
    """Hidden layers and every layer built from one, directly or through other sources, D13."""
    hidden = {layer_id for layer_id, layer in base.layers.items() if layer.hidden}
    if not hidden:
        return hidden
    changed = True
    while changed:
        changed = False
        for layer_id, layer in base.layers.items():
            if layer_id not in hidden and set(layer.sources) & hidden:
                hidden.add(layer_id)
                changed = True
    return hidden


def resolve_names(base: Projection, layers: dict[str, LayerRow], names: Iterable[str]) -> list[str]:
    """Layer ids for names, ids and tags, STORE-038: a name that is no layer is a tag.

    A name that is neither turns nothing on, CLI-033; the `layers` setting names it in a notice when it is set.
    """
    by_name = {layer.name: layer.id for layer in layers.values()}
    found: list[str] = []
    for name in names:
        if is_id(name) and name in layers:
            found.append(name)
        elif name in by_name:
            found.append(by_name[name])
        else:
            found.extend(layer_id for layer_id, layer in layers.items() if name in layer.tags)
    return found


class Resolver:
    """The effective selection at any address, from one starting selection."""

    def __init__(self, base: Projection, root: Sequence[str] | None, toggled: Sequence[str]) -> None:
        self.base = base
        self.layers = all_layers(base)
        self.hidden = hidden_closure(base)
        names = root if root is not None else (toggled or None)
        if names is None:
            start = {layer_id for layer_id, layer in self.layers.items() if self._selectable(layer)}
        else:
            start = {layer_id for layer_id in resolve_names(base, self.layers, names)
                     if self._selectable(self.layers[layer_id])}
        self.start = frozenset(start)
        self._rows: dict[str, list[tuple[str, str]]] = {}
        self._at: dict[str, frozenset[str]] = {}

    def _selectable(self, layer: LayerRow) -> bool:
        return layer.finished and layer.id not in self.hidden

    def rows(self, address: str) -> list[tuple[str, str]]:
        """The select and mask rows at one address, cached."""
        if address not in self._rows:
            self._rows[address] = sorted((layer_id, kind) for held, layer_id, kind in self.base.selections
                                         if held == address and layer_id in self.layers)
        return self._rows[address]

    def at(self, address: str) -> frozenset[str]:
        """The layer ids that reach this address."""
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
        """Whether a layer's content shows at an address in context."""
        layer = self.layers.get(layer_id)
        if layer is None or address is None:
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
