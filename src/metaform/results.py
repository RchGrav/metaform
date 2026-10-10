"""A verb's result is data, shown the same way on every surface, BASE-036.

A string result is text, returned exactly as the verb gave it. Anything else
is converted with `to_dict()` where it has one, and is JSON on `--json` and
over MCP, or readable `key: value` lines on the CLI.
"""
from __future__ import annotations

import json
from typing import Any, cast

from .data.records import Layer, plain


def as_json(result: Any) -> str:
    return json.dumps(plain(result), ensure_ascii=False)


def _compact(value: Any) -> str:
    return json.dumps(value, separators=(',', ':'), ensure_ascii=False)


def noted(result: Any, notices: list[tuple[str, str]]) -> Any:
    """A result as plain data, with the call's own notices first among its `notices` when it is an object."""
    data = plain(result)
    if notices and isinstance(data, dict):
        fields = cast(dict[str, Any], data)
        return {**fields, 'notices': [{'where': where, 'message': message} for where, message in notices]
                + list(cast(list[Any], fields.get('notices') or []))}
    return data


def _layer_row(layer: Layer) -> list[str]:
    """One layer as a row: name, kind, module, tags, ready or building, on or off, CLI-033 and LAYER-019.

    `hidden` and the re-examine mark follow when they hold, LAYER-006 and STORE-036.
    """
    state = 'ready' if layer.ready else 'building'
    toggled = 'on' if layer.on else 'off'
    flags = [word for word, holds in (('hidden', layer.hidden), ('re-examine', layer.reexamine)) if holds]
    return [layer.name, layer.kind, layer.module, ','.join(layer.tags), state, toggled, *flags]


def _rows(result: Any) -> list[list[str]] | None:
    """A page of layers or of bases as rows, or None for any other result."""
    from .home import Base
    found = getattr(result, 'results', None)
    if not isinstance(found, tuple) or not found:
        return None
    items = cast(tuple[Any, ...], found)
    if all(isinstance(item, Layer) for item in items):
        return [_layer_row(item) for item in items]
    if all(isinstance(item, Base) for item in items):
        return [[item.name, item.created, 'active' if item.active else ''] for item in items]
    return None


def _aligned(rows: list[list[str]]) -> list[str]:
    widths = [max(len(row[index]) for row in rows if index < len(row)) for index in range(max(map(len, rows)))]
    return ['  '.join(cell.ljust(widths[index]) for index, cell in enumerate(row)).rstrip() for row in rows]


def as_text(result: Any) -> str:
    """The CLI's readable form of a result that is not a string; its notices follow as `Notice:` lines, BASE-044.

    A page of layers or bases is one aligned row each, CLI-033; `--json` and MCP keep the data, BASE-036.
    """
    rows = _rows(result)
    if rows is not None:
        lines = _aligned(rows)
        next_page = getattr(result, 'next', None)
        return '\n'.join([*lines, *([f'next: {next_page}'] if next_page else [])]) + '\n'
    data = plain(result)
    if isinstance(data, list):
        return ''.join(_compact(entry) + '\n' for entry in cast(list[Any], data))
    if isinstance(data, dict):
        fields = cast(dict[str, Any], data)
        notices = cast(list[dict[str, str]], fields.pop('notices', None) or [])
        lines: list[str] = []
        for key, value in fields.items():
            shown = _compact(value) if isinstance(value, (list, dict)) else ('' if value is None else str(value))
            lines.append(f'{key}: {shown}')
        lines += [f"Notice: {notice['where']}: {notice['message']}" for notice in notices]
        return '\n'.join(lines) + '\n'
    return f'{data}\n'
