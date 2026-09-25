"""How an address reads, MAP-012, and the root Types, MAP-014.

An address reads as its name with its segments reversed and underscores as
spaces; every root reads as its own name, D56. Readings are computed, never
stored as identity. The roots are data in `roots.json`, so changing them
needs no code change.
"""
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any


def _words(segments: list[str]) -> str:
    return ' '.join(segment.replace('_', ' ') for segment in reversed(segments))


def reading(address: str) -> str:
    return _words(address.split('.'))


def short_name(address: str, name_length: int | None) -> str:
    segments = address.split('.')
    if not name_length or name_length > len(segments):
        return reading(address)
    return _words(segments[-name_length:])


@lru_cache(maxsize=1)
def _roots() -> tuple[dict[str, Any], ...]:
    return tuple(json.loads((resources.files('metaform.data') / 'roots.json').read_text(encoding='utf-8')))


def roots() -> list[dict[str, Any]]:
    return [dict(root) for root in _roots()]
