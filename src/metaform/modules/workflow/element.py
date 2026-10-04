"""The read-only, address-based element values available to Axiom logic, MAP-057."""
from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Any, NoReturn, cast

from metaform.data import Join, Node, Property, Ref, Store
from metaform.module import Context, call, surface


class _ReadOnlyList(list[Any]):
    def _immutable(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise TypeError('Element values are read-only.')

    __setitem__ = _immutable
    __delitem__ = _immutable
    __iadd__ = _immutable
    __imul__ = _immutable
    append = _immutable
    clear = _immutable
    extend = _immutable
    insert = _immutable
    pop = _immutable
    remove = _immutable
    reverse = _immutable

    def sort(self, *, key: Callable[[Any], Any] | None = None, reverse: bool = False) -> NoReturn:
        raise TypeError('Element values are read-only.')


def _freeze(value: Any) -> Any:
    if isinstance(value, Value):
        return value
    if isinstance(value, dict):
        return Value(cast(dict[str, Any], value))
    if isinstance(value, (list, tuple)):
        return _ReadOnlyList(_freeze(one) for one in cast(Sequence[Any], value))
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, Value):
        return value.to_dict()
    if isinstance(value, list):
        return [_plain(one) for one in cast(list[Any], value)]
    return value


class Value:
    """Named fields and data keys, with Python reads and detached JSON conversion."""
    __slots__ = ('_values',)
    _values: Mapping[str, Any]

    def __init__(self, fields: Mapping[str, Any]) -> None:
        object.__setattr__(self, '_values', MappingProxyType({key: _freeze(one) for key, one in fields.items()}))

    def __getattr__(self, name: str) -> Any:
        try:
            return self._values[name]
        except KeyError:
            raise AttributeError(name) from None

    def __setattr__(self, name: str, value: Any) -> NoReturn:
        raise AttributeError('Element values are read-only.')

    def __delattr__(self, name: str) -> NoReturn:
        raise AttributeError('Element values are read-only.')

    def __getitem__(self, key: str) -> Any:
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)

    def keys(self) -> Sequence[str]:
        return tuple(self._values)

    def to_dict(self) -> dict[str, Any]:
        return {key: _plain(one) for key, one in self._values.items()}


class ElementValue(Value):
    """The element carrying the current logic, or passed explicitly to another subroutine."""
    __slots__ = ()


def _refs(refs: Sequence[Ref]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for ref in refs:
        grouped.setdefault(ref.key, []).append(ref.value)
    return grouped


def _join(join: Join) -> dict[str, Any]:
    """A join as Rich's shape holds it: its purpose, ef and ifd, and the elements it holds by address."""
    return {'purpose': join.purpose, 'ef': join.ef, 'ifd': join.ifd,
            'elements': [held.address for held in join.elements if held.address is not None]}


def _property(prop: Property) -> dict[str, Any]:
    return {'value': prop.value, 'address': prop.address, 'layer': prop.layer, 'refs': _refs(prop.refs)}


def element_value(store: Store, address: str, *, selection: Sequence[str] | None = None) -> ElementValue:
    """Read one visible element through the DAO, retaining only the fields named by MAP-057."""
    where = store.where(address, selection=selection)
    if where is None or where.element is None:
        raise KeyError(address)
    element = where.element
    active = store.bound_metaform()
    memory_store = Store(store.project_id, module='memory',
                         metaform=None if active is None else active.metaform_id,
                         toggled=store.toggled if selection is None else selection)
    ctx = Context('memory', Path(store.project().path), store=memory_store)
    provider = next((module for module in surface(ctx.folder) if module.id == 'memory'), None)
    held: dict[str, Any] = (call(provider.node_read, ctx, Node('element', element.element_id)) or {}
                            if provider is not None and provider.node_read is not None else {})
    fields: dict[str, Any] = {name: getattr(element, name) for name in (
        'address', 'name', 'name_length', 'short_name', 'role', 'layer')}
    fields.update({
        'parent': element.address.rpartition('.')[0] or None,
        'refs': _refs([ref for group in where.layers if group.layer == 'sources' for item in group.items
                       for ref in item.refs]),
        'require': {held.address: _join(join) for join in where.receives for held in join.elements
                    if held.address is not None},
        'provides': {join.receiver_address: _join(join)
                     for join in where.provides if join.receiver_address is not None},
        'items': {group.layer: [{'value': item.value, 'read_first': item.read_first, 'always_show': item.always_show}
                                for item in group.items] for group in where.layers if group.items},
        'properties': {group.layer: [_property(prop) for prop in group.properties]
                       for group in where.layers if group.properties},
        'context': [_property(prop) for prop in where.applying],
        'note': held.get('note'),
        'memories': [{'name': entity['name'], 'entity_type': entity['entityType'],
                      'observations': entity['observations']} for entity in held.get('entities', [])],
        'work': [{name: getattr(ticket, name) for name in ('condition', 'note', 'task', 'steps', 'steps_done')}
                 for ticket in where.work],
        'messages': [{name: getattr(message, name) for name in ('kind', 'text', 'answer')}
                     for message in where.messages],
    })
    return ElementValue(fields)
