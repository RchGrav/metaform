"""A verb's result is data, shown the same way on every surface, BASE-036.

A string result is text, returned exactly as the verb gave it. Anything else
is converted with `to_dict()` where it has one, and is JSON on `--json` and
over MCP, or readable `key: value` lines on the CLI.
"""
from __future__ import annotations

import json
from typing import Any

from .data.records import plain


def as_json(result: Any) -> str:
    return json.dumps(plain(result), ensure_ascii=False)


def _compact(value: Any) -> str:
    return json.dumps(value, separators=(',', ':'), ensure_ascii=False)


def noted(result: Any, notices: list[tuple[str, str]]) -> Any:
    """A result as plain data, with the call's own notices first among its `notices` when it is an object."""
    data = plain(result)
    if notices and isinstance(data, dict):
        data = {**data, 'notices': [{'where': where, 'message': message} for where, message in notices]
                + list(data.get('notices') or [])}
    return data


def as_text(result: Any) -> str:
    """The CLI's readable form of a result that is not a string; its notices follow as `Notice:` lines, BASE-044."""
    data = plain(result)
    if isinstance(data, list):
        return ''.join(_compact(entry) + '\n' for entry in data)
    if isinstance(data, dict):
        notices = data.pop('notices', None) or []
        lines = []
        for key, value in data.items():
            shown = _compact(value) if isinstance(value, (list, dict)) else ('' if value is None else str(value))
            lines.append(f'{key}: {shown}')
        lines += [f"Notice: {notice['where']}: {notice['message']}" for notice in notices]
        return '\n'.join(lines) + '\n'
    return f'{data}\n'
