"""The map as a short Markdown document, MAP-052.

One writer for the command `metaform map markdown` and for the web GUI's export, VIEW-024, so the two give the same
document. It reads through `roots` and `where`, STORE-025, so select, mask and hiding hold. The document holds what a
reader finds its way by: each element's name, address, role and paths, and each join's receiver, provider, ef,
purpose and non_goal.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from .data import Store
from .errors import Stop

FIRST = {'CQU': 0, 'AUE': 1, 'DE': 2}


def _join_lines(join: dict[str, Any], receiver: str, provider: str) -> list[str]:
    """One join: who receives from whom, the ef as written, the purpose and the non_goal, and each subtype join as
    one line."""
    lines = [f'### {receiver} receives from {provider}', '']
    for text in (str(join.get('ef') or ''),
                 f"Why: {join['purpose']}" if join.get('purpose') else '',
                 f"Not: {join['non_goal']}" if join.get('non_goal') else ''):
        if text:
            lines += [text, '']
    held = [': '.join(part for part in (str(subtype.get('short_name') or subtype.get('element') or ''),
                                        str(subtype.get('ef') or '')) if part)
            for subtype in cast(list[dict[str, Any]], join.get('subtypes') or [])]
    return lines + ([f'- {line}' for line in held] + [''] if held else [])


def _element_lines(store: Store, address: str, names: dict[str, str], reading: dict[str, Any],
                   around: bool) -> list[str]:
    """One element with the joins it receives, and with `around` those it provides too."""
    found = store.where(address, **reading)
    view: dict[str, Any] = found.to_dict() if found is not None else {}
    element = cast(dict[str, Any], view.get('element') or {})
    if not element:
        return []
    name = str(element.get('short_name') or address)
    lines = [f'## {name}', '', f"`{element.get('address', address)}`, {element.get('role') or 'no role'}", '']
    paths = [str(ref['value']) for ref in cast(list[dict[str, Any]], element.get('refs') or [])
             if ref.get('key') == 'path']
    if paths:
        lines += ['Paths: ' + ', '.join(paths), '']
    for join in cast(list[dict[str, Any]], view.get('receives') or []):
        provider = str(join.get('provider') or '')
        lines += _join_lines(join, name, names.get(provider, provider))
    if around:
        for join in cast(list[dict[str, Any]], view.get('provides') or []):
            receiver = str(join.get('receiver') or '')
            lines += _join_lines(join, names.get(receiver, receiver), name)
    return lines


def markdown(store: Store, address: str | None = None, *, selection: Sequence[str] | None = None,
             raw: bool = False) -> str:
    """The whole map, the CQU, the AUE and the DE first, or with an address that element and all around it."""
    reading: dict[str, Any] = {'selection': selection, 'raw': raw}
    found = store.roots(limit=0, **reading)
    names = {element.address: element.short_name for element in found.elements}
    if address:
        lines = _element_lines(store, address, names, reading, True)
        if not lines:
            raise Stop(f'No element at {address}.', 'metaform map roots')
        title = f'# {names.get(address, address)}'
    else:
        ordered = sorted(found.elements, key=lambda element: (FIRST.get(element.role, 3), element.address))
        title = f'# {store.project().project_id} functional map'
        lines = [line for element in ordered
                 for line in _element_lines(store, element.address, names, reading, False)]
    return '\n'.join([title, '', *lines]).rstrip('\n') + '\n'
