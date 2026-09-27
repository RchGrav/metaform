"""Identity ids, addresses, layer names and the values a row may hold, STORE-004, STORE-007, STORE-008, STORE-013."""
from __future__ import annotations

import json
import re
import uuid
from collections.abc import Iterable, Sequence
from typing import Any, cast

from ..errors import StoreError

ID = re.compile(r'^[0-9a-f]{32}$')
ADDRESS = re.compile(r'^[a-z0-9_]+(\.[a-z0-9_]+)*$')
LAYER_NAME = re.compile(r'^[A-Za-z0-9._-]{1,128}$')
TAG = re.compile(r'^[a-z0-9._-]{1,64}$')


def new_id() -> str:
    return uuid.uuid4().hex


def is_id(text: str) -> bool:
    return bool(ID.fullmatch(text))


def as_object(value: Any) -> dict[str, Any] | None:
    """A JSON value that is an object, typed, or None when it is not one."""
    return cast(dict[str, Any], value) if isinstance(value, dict) else None


def as_list(value: Any) -> list[Any] | None:
    """A JSON value that is an array, typed, or None when it is not one."""
    return cast(list[Any], value) if isinstance(value, list) else None


def check_address(address: object, layer: str = '<layer>') -> str:
    if not isinstance(address, str) or not ADDRESS.fullmatch(address) or is_id(address):
        raise StoreError(f'{address!r} is not an address: write dotted lowercase segments of letters, digits and '
                         'underscores, such as code.engine.game.',
                         f'metaform map knowledge op=add-element layer={layer} address=<segment.segment>')
    return address


def prefixes(address: str) -> list[str]:
    """Every prefix of an address, trunk first, ending with the address itself."""
    parts = address.split('.')
    return ['.'.join(parts[:count]) for count in range(1, len(parts) + 1)]


def check_layer_name(name: object) -> str:
    if not isinstance(name, str) or not LAYER_NAME.fullmatch(name) or is_id(name):
        raise StoreError(f'{name!r} is not a layer name: use 1 to 128 letters, digits, ., _ and -.',
                         'metaform map knowledge op=create layer=<name> variable=<question> mutable=true hideable=true')
    return name


def check_tag(tag: object) -> str:
    if not isinstance(tag, str) or not TAG.fullmatch(tag):
        raise StoreError(f'{tag!r} is not a tag: use 1 to 64 lowercase letters, digits, ., _ and -.',
                         'metaform map layers')
    return tag


def _holds_records(value: Any) -> bool:
    members = as_list(value)
    if members is not None:
        return any(isinstance(member, dict) or _holds_records(member) for member in members)
    mapping = as_object(value)
    if mapping is not None:
        return any(_holds_records(member) for member in mapping.values())
    return False


def encode_extra(extra: Any, where: str) -> str | None:
    """An `extra` is a JSON object of one row's own fields and never holds a list of records, STORE-004."""
    if extra is None:
        return None
    if not isinstance(extra, dict):
        raise StoreError(f'extra on {where} must be an object of its own fields.', 'metaform help map knowledge')
    if _holds_records(extra):
        raise StoreError(f'extra on {where} holds a list of records; write each record as its own thing.',
                         'metaform help map knowledge')
    return json.dumps(extra, ensure_ascii=False, sort_keys=True)


def decode_extra(text: str | None) -> dict[str, Any] | None:
    return None if text is None else json.loads(text)


def encode_value(value: Any, where: str) -> str:
    """One answer at one node: a string, number, boolean, object or null, never a list, STORE-015."""
    if isinstance(value, (list, tuple)):
        raise StoreError(f'The value on {where} is a list; write each answer as its own item.',
                         'metaform help map knowledge')
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as error:
        raise StoreError(f'The value on {where} is not JSON: {error}.', 'metaform help map knowledge') from None


def refs_fit(refs: Iterable[Any] | None) -> tuple[list[tuple[str, str]], list[Any]]:
    """Refs as key and value pairs in order, from pairs or from objects with key and value; and, second, every ref
    that is not a key and a value, both text, as given, for the record's extra, STORE-012 and BASE-044."""
    found: list[tuple[str, str]] = []
    odd: list[Any] = []
    for ref in refs or ():
        mapping = as_object(ref)
        key: Any = None
        value: Any = None
        if mapping is not None:
            key, value = mapping.get('key'), mapping.get('value')
        elif isinstance(ref, (list, tuple)):
            pair = cast(Sequence[Any], ref)
            if len(pair) == 2:
                key, value = pair[0], pair[1]
        if not isinstance(key, str) or not isinstance(value, str):
            odd.append(ref)
        else:
            found.append((key, value))
    return found, odd

