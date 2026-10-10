"""The map as a short Markdown document, MAP-052.

One writer for the command `metaform map markdown` and for the web GUI's export, VIEW-024, so the two give the same
document. It reads through `roots` and `where`, STORE-025, so select, mask and hiding hold. The document holds what a
reader finds its way by: each element's name, address, role and paths, from the sources layer, and each join's
receiver, the elements it holds, its ef and its purpose.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from .data import Store
from .errors import Stop

FIRST = {'CQU': 0, 'DE': 1}


def _held(join: dict[str, Any], names: dict[str, str]) -> str:
    """The elements a join holds, each by its short name."""
    held = [str(each.get('address') or '') for each in cast(list[dict[str, Any]], join.get('elements') or [])]
    return ', '.join(names.get(address, address) for address in held if address)


def _join_lines(join: dict[str, Any], receiver: str, provider: str) -> list[str]:
    """One join: who receives from whom, the ef as written, and the purpose."""
    lines = [f'### {receiver} receives from {provider}', '']
    for text in (str(join.get('ef') or ''), f"Why: {join['purpose']}" if join.get('purpose') else ''):
        if text:
            lines += [text, '']
    return lines


def _view(store: Store, address: str, reading: dict[str, Any]) -> dict[str, Any]:
    """One element as `where` reads it, or nothing when it is not in view."""
    found = store.where(address, **reading)
    return found.to_dict() if found is not None else {}


def _element_lines(view: dict[str, Any], address: str, names: dict[str, str], around: bool) -> list[str]:
    """One element with the joins it receives, and with `around` those it provides too."""
    element = cast(dict[str, Any], view.get('element') or {})
    if not element:
        return []
    name = str(element.get('name') or element.get('short_name') or address)  # its name, else its short name
    lines = [f'## {name}', '', f"`{element.get('address', address)}`, {element.get('role') or 'no role'}", '']
    paths = [str(ref['value']) for group in cast(list[dict[str, Any]], view.get('layers') or [])
             if group.get('layer') == 'sources' for item in cast(list[dict[str, Any]], group.get('items') or [])
             for ref in cast(list[dict[str, Any]], item.get('refs') or []) if ref.get('key') == 'path']
    if paths:
        lines += ['Paths: ' + ', '.join(paths), '']
    for join in cast(list[dict[str, Any]], view.get('receives') or []):
        lines += _join_lines(join, name, _held(join, names))
    if around:
        for join in cast(list[dict[str, Any]], view.get('provides') or []):
            receiver = str(join.get('receiver') or '')
            lines += _join_lines(join, names.get(receiver, receiver), name)
    return lines


def _labels(store: Store, elements: Sequence[Any], reading: dict[str, Any]) -> dict[str, str]:
    """Each root element's name, the project's name for it, where it has one."""
    found: dict[str, str] = {}
    for element in elements:
        record = store.element(element.address, **reading)
        found[element.address] = (record.name if record is not None else None) or ''
    return found


def markdown(store: Store, address: str | None = None, *, selection: Sequence[str] | None = None,
             raw: bool = False) -> str:
    """The whole map, the CQUs and the DE first, or with an address that element and all around it."""
    reading: dict[str, Any] = {'selection': selection, 'raw': raw}
    found = store.roots(limit=0, **reading)
    names = {element.address: element.short_name for element in found.elements}
    if address:
        names.update({address: label for address, label in _labels(store, found.elements, reading).items() if label})
        lines = _element_lines(_view(store, address, reading), address, names, True)
        if not lines:
            raise Stop(f'No element at {address}.', 'metaform map roots')
        title = f'# {names.get(address, address)}'
    else:
        ordered = sorted(found.elements, key=lambda element: (FIRST.get(element.role, 3), element.address))
        # Each root is read once: its name comes from the same read that writes its section.
        views = {element.address: _view(store, element.address, reading) for element in ordered}
        names.update({root: str(label) for root, view in views.items()
                      if (label := cast(dict[str, Any], view.get('element') or {}).get('name'))})
        title = f'# {store.project().project_id} functional map'
        lines = [line for element in ordered
                 for line in _element_lines(views[element.address], element.address, names, False)]
    return '\n'.join([title, '', *lines]).rstrip('\n') + '\n'
