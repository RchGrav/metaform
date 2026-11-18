"""The worker protocol's tickets for a project held in the project store (`metaform.project`): they are the `tickets`
overlay records there, the ones the page's board reads, so a pair's ticket is the ticket the person sees.

Kickoff 2026-11-17, Phase 3, decision t-legacy-keep: every old-store feature is kept and moved onto the project store.
A ticket there holds id, title, task, kind, held, taken_by, note, done, outcome, steps and steps_done at one element.
A worksheet's progress is steps and steps_done, its completed text is written into the note as the old store's was,
and a resolution, which has no field, is a paragraph of the note as `map work done` writes it. A ticket on a join has
no place there and is refused by name. Each change names the record it found (F02), so it never lands on another
ticket, and a claim names the revision it read too, so of two claims one is refused (F09). The worktrees, rounds and
ratings stay in this module's own tables, which are not the map.
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any, cast

from metaform import project as project_store
from metaform.module import Context, Stop

HELP = 'metaform help tasks ticket'


def held(ctx: Context) -> str | None:
    """The project's name in the project store when its tickets are kept there, else None: the old path is taken."""
    name = project_store.stored_name(ctx.require_store().project_id)
    return name if project_store.holds(name) else None


def records(name: str) -> dict[str, dict[str, Any]]:
    """Every ticket of the project, by its id, in one read."""
    return {str(one['id']): cast(dict[str, Any], one)
            for one in project_store.overlay_records(name, 'tickets') or [] if one.get('id')}


def found(name: str, tickets: dict[str, dict[str, Any]], ident: str) -> dict[str, Any]:
    """One ticket by its id: from the open ones read, else by reference, so a completed ticket is found as done
    rather than as missing (review of 2026-11-18, F4)."""
    one = tickets.get(ident) or cast('dict[str, Any] | None', project_store.overlay_record(name, 'tickets', 'id', ident))
    if one is None:
        raise Stop(f"No ticket {ident!r} in {name}'s tickets: it was removed from the board.", 'metaform tasks board')
    return one


def add(name: str, node: str, title: str, task: str) -> str:
    """A new ticket at the element `node`; its id."""
    if node.startswith('join:'):
        raise Stop(f"A ticket in the project store, where {name}'s tickets are kept, is at one element; a join has no "
                   "tickets there yet. Put it at the join's receiver.", HELP)
    ident = 't-' + secrets.token_hex(4)
    _done(project_store.run({'add': {f'{name}.{node}': {'tickets': [{'id': ident, 'title': title, 'task': task}]}}}))
    return ident


def take(one: dict[str, Any], by: str) -> None:
    """Claim a ticket for `by`, exclusively: one another agent holds is refused, and the claim names the revision it
    read, so a claim made since is not overwritten."""
    holder = one.get('taken_by')
    if holder and holder != by and not one.get('done'):
        raise Stop(f"Ticket {one['id']!r} is taken by {holder}; it is not taken again. Its holder or the person "
                   'releases it on the board first.', 'metaform tasks board')
    change(one, {'taken_by': by, 'held': None}, exact=True)


def change(one: dict[str, Any], fields: dict[str, object], exact: bool = False) -> None:
    """Change one ticket, named by its position and record, and with `exact` by the revision read as well."""
    named: dict[str, object] = {'position': one['position'], 'record': one['record'],
                                **({'revision': one['revision']} if exact else {}), **fields}
    _done(project_store.run({'update': {str(one['element']): {'tickets': [named]}}}))


def finished(one: dict[str, Any], resolution: str, why: str) -> dict[str, object]:
    """The fields that close a ticket as completed: the resolution and why in their own paragraph of the note, after
    what it already says, as `map work done` writes them."""
    kept = str(one.get('note') or '').strip()
    said = f'Resolution: {resolution} Why: {why}'
    return {'done': datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'), 'outcome': 'completed',
            'note': '\n\n'.join(part for part in (kept, said) if part)}


def _done(answer: dict[str, object]) -> None:
    if answer.get('status') == 'error':
        raise Stop(str(answer.get('message') or 'The ticket was not changed.'),
                   str(answer.get('remediation') or HELP))
