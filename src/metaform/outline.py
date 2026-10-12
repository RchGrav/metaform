"""The map as a short Markdown document, MAP-052, and as a Mermaid flowchart, P063.

One writer of each for the commands `metaform map markdown` and `metaform map mermaid` and for the web GUI's export,
VIEW-024, so the command and the page give the same document. It reads through `roots` and `where`, STORE-025, so
select, mask and hiding hold. The document holds what a reader finds its way by: each element's name, address, role
and paths, from the sources layer, and each join's receiver, the elements it holds, its ef and its purpose.
"""
from __future__ import annotations

import json
import re
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


# Mermaid's flowchart syntax, https://mermaid.js.org/syntax/flowchart.html: a node id holds letters, digits and `_`;
# a label in double quotes takes any character but `"`, written as the entity code `#quot;`, and `#`, written `#35;`,
# so a label is never read as Mermaid's own; `<br>` breaks a line; `-->|"text"|` is a link's text; `<-->` an arrow at
# both ends (there is no arrow at the start alone); `classDef` and `class` style nodes. A lowercase `end` breaks the
# flowchart, so no id is one. The YAML frontmatter, https://mermaid.js.org/config/configuration.html, carries the
# title and the layout, ELK by network simplex, https://mermaid.js.org/config/layouts.html, as the page lays out its
# 2D map; the limits Mermaid renders under, maxTextSize and maxEdges, are secure keys frontmatter cannot raise.
DIRECTIONS = ('TB', 'LR')
LABELS = ('none', 'purpose', 'ef')
MAX_TEXT = 50_000  # Mermaid's default maxTextSize: a longer diagram is refused by a renderer that keeps its defaults
MAX_EDGES = 500  # Mermaid's default maxEdges
ROLES = {'CQU': ('cqu', 'stroke-width:3px'), 'DE': ('de', 'stroke-width:2px,stroke-dasharray:6 3')}
_ID = re.compile(r'[^0-9A-Za-z_]+')


def _label(text: str) -> str:
    return text.replace('#', '#35;').replace('"', '#quot;').replace('<', '#lt;').replace('>', '#gt;')


def _edge(receiver: str, provider: str, ifd: str | None, text: str) -> str:
    """One join to one element it holds, pointing the way the join's information goes, its ifd, as the page's 2D map
    points it: at the element served when the receiver sends or nothing is recorded, at the receiver when it receives,
    at both when both."""
    link = '<-->' if ifd == 'both' else '-->'
    said = f'|"{_label(text)}"|' if text else ''
    return f'  {provider} {link}{said} {receiver}' if ifd == 'receives' else f'  {receiver} {link}{said} {provider}'


def mermaid(store: Store, address: str | None = None, *, direction: str = 'TB', leave_out: Sequence[str] = (),
            labels: str = 'none', selection: Sequence[str] | None = None, raw: bool = False) -> str:
    """The map in view as a Mermaid flowchart, `direction` TB or LR: what the page's 2D map draws, the elements of the
    layers in view less the roots left out, and an edge for each element each join holds, each pointing the way its
    information goes, its ifd. Each element is a node named by what the project calls it, else its short name, over its
    address; the CQUs and the DE carry their role's class. With `labels` purpose or ef each edge says its join's. The
    frontmatter gives the title and the page's layout, ELK by network simplex. With an address, that element and those
    one join away. `leave_out` names roots, such as `upstream`, whose elements are not drawn, as the page leaves out a
    root turned off. A diagram past what Mermaid renders by default says so in a comment at its top."""
    if direction not in DIRECTIONS:
        raise Stop(f'direction is {direction!r}; it is TB, top to bottom, or LR, left to right.',
                   'metaform map mermaid direction=TB')
    if labels not in LABELS:
        raise Stop(f'labels is {labels!r}; it is none, purpose or ef.', 'metaform map mermaid labels=purpose')
    found = store.graph(limit=0, selection=selection, raw=raw)
    off = set(leave_out)
    elements = {each.element.address: each.element for each in found.elements
                if each.element.address.split('.')[0] not in off}
    edges = [(join.receiver_address, held.address, join.ifd, str(getattr(join, labels, None) or '')
              if labels != 'none' else '')
             for join in found.joins for held in join.elements
             if join.receiver_address in elements and held.address in elements]
    if address:
        if address not in elements:
            raise Stop(f'No element at {address} in these layers.', 'metaform map roots')
        edges = [edge for edge in edges if address in edge[:2]]
        near = {address, *(end for edge in edges for end in edge[:2])}
        elements = {key: value for key, value in elements.items() if key in near}
    ids: dict[str, str] = {}
    for key in elements:
        made = _ID.sub('_', key).strip('_') or 'node'
        made = f'n_{made}' if made[0].isdigit() or made.lower() == 'end' else made
        while made in ids.values():
            made += '_'
        ids[key] = made
    title = f'{store.project().project_id} functional map' + (f' around {address}' if address else '')
    lines = ['---', f'title: {json.dumps(title, ensure_ascii=False)}', 'config:', '  layout: elk', '  elk:',
             '    nodePlacementStrategy: NETWORK_SIMPLEX', '---', f'flowchart {direction}']
    for key, element in elements.items():
        called = element.name or element.short_name or key
        lines.append(f'  {ids[key]}["{_label(called)}' + (f'<br>{_label(key)}' if called != key else '') + '"]')
    lines += [_edge(ids[receiver], ids[provider], ifd, text) for receiver, provider, ifd, text in edges]
    roles = {role: [ids[key] for key, element in elements.items() if element.role == role] for role in ROLES}
    for role, (name, style) in ROLES.items():
        if roles[role]:
            lines += [f'  classDef {name} {style}', f'  class {",".join(roles[role])} {name}']
    text = '\n'.join(lines) + '\n'
    notice = mermaid_limits(text)
    return text.replace('flowchart ', f'%% {notice}\nflowchart ', 1) if notice else text


def mermaid_limits(text: str) -> str | None:
    """What a Mermaid renderer that keeps its defaults says to a diagram this long: past `MAX_TEXT` characters or
    `MAX_EDGES` edges it draws nothing. None when the diagram is within both."""
    edges = sum(1 for line in text.splitlines() if re.match(r'\s+\w+ (?:<-->|-->)', line))
    over = [said for said, past in ((f'{len(text):,} characters, past {MAX_TEXT:,}', len(text) > MAX_TEXT),
                                    (f'{edges:,} edges, past {MAX_EDGES:,}', edges > MAX_EDGES)) if past]
    if not over:
        return None
    return (f'This diagram has {" and ".join(over)}: Mermaid with its default limits, as GitHub and mermaid.live run '
            'it, refuses it. Draw part of the map with address=, or raise maxTextSize and maxEdges where you render '
            'it.')
