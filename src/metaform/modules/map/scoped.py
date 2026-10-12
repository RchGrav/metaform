"""What a layer holds at a scope, addressed `<scope>@<layer>`, P165: read backward with `@` as "for".

`code.timer.kitchen@code` is the code for the kitchen timer: what the code layer holds at that Address. The scope is an
Address, or a join named by its receiver and provider, `<receiver>:<provider>`, as every read names a join, MAP-005:
`code.timer.kitchen:code.alarm.audible@code` is the code realizing the timer's join with the alarm, the EF the alarm
serves the timer with. `base` as the scope, or no scope, is the whole project: `base@best_practices` is the best
practices for the whole project.

A layer may be named with its scope, `code.cpp@best_practices`, as map knowledge's layer noun asks a new layer to be
named; its full name is then its address, and resolves first. Otherwise the part after `@` names the layer.

The address is a view of the map, never a copy: the element's name, role and joins come from the map, and the layer
adds what it holds there. A hidden layer resolves to nothing, as LAYER-028 has it, while the map itself is unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass

from metaform.data import PLACE_KINDS, Store, StoreError
from metaform.module import Stop

BASE = 'base'  # the scope of the whole project


@dataclass(frozen=True)
class Scoped:
    """One resolved `<scope>@<layer>`: the layer's stored name, the Address it is for, None for the whole project, and
    the provider naming a join that Address receives."""
    given: str
    layer: str
    address: str | None
    provider: str | None = None

    @property
    def scope(self) -> str:
        if self.address is None:
            return BASE
        return f'{self.address}:{self.provider}' if self.provider else self.address

    @property
    def text(self) -> str:
        """The address as it is written back, `<scope>@<layer>`; a layer named with its scope by that name alone."""
        return self.layer if '@' in self.layer else f'{self.scope}@{self.layer}'


def is_scoped(text: str) -> bool:
    """Whether an address names a layer's view of it: it holds `@` after something, and is no `kind:` node."""
    head = text.partition(':')[0]
    return '@' in text and not (':' in text and head in PLACE_KINDS)


def _layer(store: Store, name: str) -> str | None:
    try:
        return store.layer_ref(name).name
    except StoreError:
        return None


def resolve(store: Store, text: str) -> Scoped:
    """`<scope>@<layer>` read against this map: the layer by its full name first, then by the part after the last
    `@`; the scope as an Address, a join `<receiver>:<provider>`, or `base`. Stop with the next step when the layer or
    the Address is not there, or the layer is hidden."""
    given = text.strip()
    scope, _, named = given.rpartition('@')
    if not named:
        raise Stop(f'{given!r} names no layer after @.', 'write <scope>@<layer>, such as code.timer.kitchen@code')
    layer = _layer(store, given) or _layer(store, named)
    if layer is None:
        raise Stop(f'No layer {named} here, so {given} does not resolve.', 'metaform map layers')
    if layer == given:  # a layer named with its scope: the part before its own `@` is the scope
        scope = given.rpartition('@')[0]
    found = store.layer_ref(layer)
    if found.hidden:
        raise Stop(f'The layer {layer} is hidden, so {given} resolves to nothing; the map itself is unchanged.',
                   f'metaform map unhide {layer}')
    if scope in ('', BASE):
        return Scoped(given, layer, None)
    receiver, _, provider = scope.partition(':')
    if store.element(receiver) is None:
        raise Stop(f'No element {receiver} in context here, so {given} does not resolve.',
                   f'metaform map children {receiver}')
    if provider and store.element(provider) is None:
        raise Stop(f'No element {provider} in context here, so {given} does not resolve.',
                   f'metaform map joins element={receiver}')
    return Scoped(given, layer, receiver, provider or None)
