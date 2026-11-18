"""Roundtables on a project held in the project store (`metaform.project`): the part a table opens on, the top element
it keeps what it leaves at, and the tickets it makes (an adopted idea, a follow-through stage) are read and written
there, so they are the map and the tickets the page shows.

Kickoff 2026-11-17, Phase 3, decision t-legacy-keep: every old-store feature is kept and moved onto the project store.
A ticket there is a record of the `tickets` overlay at one element: id, title, task, kind and note. The tables, their
events and the follow-through's pipeline stay in this module's own tables, which are not the map. A decomposition's
board, its ticket order and its dependencies have no place in the project store yet, so that stage is refused by name
(`refuse_board`). Projects not in the project store keep the old path unchanged.
"""
from __future__ import annotations

import secrets
from typing import Any, cast

from metaform import project as project_store
from metaform.module import Stop

HELP = 'metaform help map work'


def held(project_id: str) -> str | None:
    """The project's name in the project store when its map and tickets are kept there, else None."""
    name = project_store.stored_name(project_id)
    return name if project_store.holds(name) else None


def _drawn(name: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    found = project_store.drawn(name) or {}
    lead = len(name) + 1
    # A bare branch on the way to an element holds only its address: it is no element of the map's own.
    elements = [{**row, 'address': str(row['address'])[lead:]}
                for row in cast(list[dict[str, Any]], found.get('elements') or []) if len(row) > 1]
    wants = [{**want, 'holder': str(want['holder'])[lead:], 'element': str(want['element'])[lead:]}
             for want in cast(list[dict[str, Any]], found.get('wants') or [])]
    return elements, wants


def top(name: str) -> str | None:
    """The project's top element: the Defining Element nearest the root, else the element nearest it; None while the
    map holds none. The address is without the project's name, as the old store's are."""
    elements, _ = _drawn(name)
    found = min(elements, key=lambda one: (one.get('role') != 'Defining Element', one['address'].count('.'),
                                           one['address']), default=None)
    return None if found is None else str(found['address'])


def has(name: str, address: str) -> bool:
    return any(one['address'] == address for one in _drawn(name)[0])


def part(name: str, address: str) -> str:
    """The part as the map holds it, in the form `outline.markdown` gives the old store's: the element, its role and
    ref, the wants it holds (what it receives, with how and why) and the wants on it (what it provides)."""
    elements, wants = _drawn(name)
    by = {str(one['address']): one for one in elements}
    element = by.get(address)
    if element is None:
        raise Stop(f'No element at {address}.', f'the project tool: {{"{name}.{address}": {{}}}}')

    def named(at: str) -> str:
        return str(by.get(at, {}).get('name') or by.get(at, {}).get('technical_name') or at)

    def join(receiver: str, provider: str, want: dict[str, Any]) -> list[str]:
        lines = [f'### {receiver} receives from {provider}', '']
        for text in (str(want.get('how') or ''), f"Why: {want['why']}" if want.get('why') else ''):
            if text:
                lines += [text, '']
        return lines

    title = named(address)
    lines = [f'# {title}', '', f'## {title}', '', f"`{address}`, {element.get('role') or 'no role'}", '']
    if element.get('ref'):
        lines += [f"Paths: {element['ref']}", '']
    for want in wants:
        if want['holder'] == address:
            lines += join(title, named(want['element']), want)
    for want in wants:
        if want['element'] == address and want['holder'] != address:
            lines += join(named(want['holder']), title, want)
    return '\n'.join(lines).rstrip('\n') + '\n'


def add(name: str, address: str, *, title: str, task: str, note: str | None = None) -> str:
    """A new ticket of kind enhancement at the element `address`; its id. An element the map does not hold is
    refused by the store."""
    ident = 't-' + secrets.token_hex(4)
    record: dict[str, object] = {'id': ident, 'title': title[:120], 'task': task, 'kind': 'enhancement',
                                 **({'note': note} if note else {})}
    answer = project_store.run({'add': {f'{name}.{address}': {'tickets': [record]}}})
    if answer.get('status') == 'error':
        raise Stop(str(answer.get('message') or 'The ticket was not made.'), str(answer.get('remediation') or HELP))
    return ident


def ticket(name: str, ident: str) -> dict[str, Any] | None:
    """One ticket by its id, open or completed, with the address of its element without the project's name; None when
    there is none."""
    found = project_store.overlay_record(name, 'tickets', 'id', ident)
    if found is None:
        return None
    return {**found, 'address': str(found['element'])[len(name) + 1:]}


def refuse_board(name: str) -> None:
    """Decomposition makes a fresh board of ordered tickets with dependencies, and the execution outline is read from
    it. The project store's tickets have no board, order or dependency yet, so neither has a faithful place there."""
    raise Stop(f"Decomposition needs a board of ordered tickets with dependencies, and the project store, where "
               f"{name}'s tickets are kept, has no board, ticket order or dependency yet, so the decomposition stage "
               'and its execution outline are refused there rather than made without them.',
               'boards need a place in the project store first (docs/plans/old-store-removal.md, step 3)')
