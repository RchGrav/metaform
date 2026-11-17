"""Paperclip's tickets and messages for a project held in the project store (`metaform.project`): an issue's ticket is a
record of the project's `tickets` overlay, the one the page's board reads, and a comment that crosses in is a message
of its `questions` overlay, where the page's Messages pane reads it.

Kickoff 2026-11-17, Phase 3, decision t-legacy-keep: every old-store feature is kept and moved onto the project store.
A ticket there holds id, title, task, kind, held, taken_by, note, done and outcome at one element, so a resolution,
which has no field, is a paragraph of the note as `map work done` writes it (`Resolution: ... Why: ...`), and read
back from it. Each change names the record it found (F02), and a claim the revision it read as well, so of two claims
one is refused (F09). The links and bridged tables stay in this module's own tables, which are not the map.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from metaform import project as project_store
from metaform.data import Message, Store, StoreError

RESOLUTION = 'Resolution: '
WHY = ' Why: '


def name_of(store: Store) -> str | None:
    """The project's name in the project store when its tickets and messages are kept there, else None: the old path
    is taken."""
    name = project_store.stored_name(store.project_id)
    return name if project_store.holds(name) else None


@dataclass(frozen=True)
class Ticket:
    """A ticket of the tickets overlay, with the fields this module reads of a work record by the same names, so the
    sync reads either one alike: where it is, by its element's full path, position, record id and revision."""
    id: str
    element: str
    position: int
    record: str
    revision: int
    address: str
    title: str | None
    task: str | None
    note: str | None
    taken_by: str | None
    held: bool
    done: str | None
    outcome: str | None
    receiver_address: str | None = None  # a ticket in the project store is at one element, never on a join

    @property
    def taken(self) -> bool:
        return bool(self.taken_by)

    @property
    def resolution(self) -> str | None:
        """The resolution written into the note when the ticket closed: its last `Resolution:` paragraph, without the
        why written after it."""
        for paragraph in reversed((self.note or '').split('\n\n')):
            if paragraph.startswith(RESOLUTION):
                said = paragraph[len(RESOLUTION):]
                return said.rpartition(WHY)[0] if WHY in said else said
        return None


@dataclass(frozen=True)
class Said(Message):
    """A question or message of the questions overlay as the old store's Message reads, with the title it is kept
    under, since the project store keeps no item numbers to find a title by."""
    title: str | None = None


def tickets(name: str) -> dict[str, Ticket]:
    """Every ticket of the project, by its id, in one read."""
    start = len(name) + 1
    return {str(one['id']): Ticket(
        id=str(one['id']), element=str(one['element']), position=cast(int, one['position']),
        record=str(one['record']), revision=cast(int, one['revision']), address=str(one['element'])[start:],
        title=cast('str | None', one.get('title')), task=cast('str | None', one.get('task')),
        note=cast('str | None', one.get('note')), taken_by=cast('str | None', one.get('taken_by')),
        held=bool(one.get('held')), done=cast('str | None', one.get('done')),
        outcome=cast('str | None', one.get('outcome')))
        for one in project_store.overlay_records(name, 'tickets') or [] if one.get('id')}


def ticket(name: str, work_id: str) -> Ticket | None:
    return tickets(name).get(work_id)


def add(name: str, address: str, title: str, task: str, taken_by: str | None = None) -> Ticket:
    """A new ticket at the element `address`, taken by `taken_by` when one is named. StoreError when the store refuses
    it, as it refuses an address that holds no element."""
    ident = 't-' + secrets.token_hex(4)
    record: dict[str, object] = {'id': ident, 'title': title, 'task': task, **({'taken_by': taken_by} if taken_by else {})}
    _done(project_store.run({'add': {f'{name}.{address}': {'tickets': [record]}}}), f'the ticket at {address}')
    found = ticket(name, ident)
    if found is None:
        raise StoreError(f'the ticket {ident} at {address} was written and is not there', 'metaform map work op=list')
    return found


def take(one: Ticket, by: str) -> None:
    """Claim a ticket for `by`, by the revision read: a ticket changed since, a claim among them, is refused."""
    change(one, {'taken_by': by, 'held': None}, exact=True)


def give_back(one: Ticket) -> None:
    """A claim undone: the ticket as it was read before it was taken, back in its column on the board."""
    change(one, {'taken_by': one.taken_by, 'held': True if one.held else None})


def finish(one: Ticket, resolution: str, why: str, outcome: str) -> None:
    """Close a ticket with an outcome, its resolution and why in their own paragraph of the note, after what it already
    says, as `map work done` writes them."""
    kept = (one.note or '').strip()
    said = f'{RESOLUTION}{resolution}{WHY}{why}'
    change(one, {'done': datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'), 'outcome': outcome,
                 'note': '\n\n'.join(part for part in (kept, said) if part)})


def change(one: Ticket, fields: dict[str, object], exact: bool = False) -> None:
    """Change one ticket, named by its position and record, and with `exact` by the revision read as well."""
    named: dict[str, object] = {'position': one.position, 'record': one.record,
                                **({'revision': one.revision} if exact else {}), **fields}
    _done(project_store.run({'update': {one.element: {'tickets': [named]}}}), f'ticket {one.id}')


def held_messages(name: str, address: str) -> list[Message]:
    """The questions and messages at the element, oldest first."""
    from metaform.modules.map import project_messages  # the questions overlay's one definition and reader
    return [Said(id=str(one['id']), kind=str(one['kind']), node_kind='element', node_id=str(one['address']),
                 address=str(one['address']), receiver_address=None, provider_address=None,
                 text=cast('str | None', one.get('text')),
                 suggestions=tuple(str(said) for said in cast(list[Any], one.get('suggestions') or [])),
                 by=cast('str | None', one.get('by')), created=str(one.get('created') or ''),
                 closed=cast('str | None', one.get('closed')), answer=cast('str | None', one.get('answer')),
                 work_id=cast('str | None', one.get('work_id')), title=cast('str | None', one.get('title')))
            for one in project_messages.listed(name, {'node': f'element:{address}', 'limit': 0})['results']]


def tell(name: str, address: str, text: str, *, by: str, title: str) -> str:
    """A message left at the element, written by map's own writer, which defines the questions overlay in the project
    the first time one is written there (map/project_messages.py `tell`, kept for the modules that leave one); its
    id."""
    from metaform.modules.map import project_messages
    return str(project_messages.tell(name, address, text, by=by, title=title)['id'])


def marks(name: str, work_ids: set[str]) -> dict[str, tuple[object, ...]]:
    """What a sync of each ticket reads of the project store, as revisions: the ticket's own, and its questions'. Two
    reads alike are the same; a write since, by anyone, changes them."""
    if not work_ids:
        return {}
    found: dict[str, list[object]] = {one: [] for one in work_ids}
    for one in project_store.overlay_records(name, 'tickets') or []:
        if one.get('id') in found:
            found[str(one['id'])].append(('ticket', one.get('record'), one.get('revision')))
    for one in project_store.overlay_records(name, 'questions') or []:
        if one.get('work') in found:
            found[str(one['work'])].append(('question', one.get('record'), one.get('revision')))
    return {work_id: tuple(sorted(held, key=repr)) for work_id, held in found.items()}


def texts(name: str) -> dict[str, list[str]]:
    """Each element's own words and the purposes of the wants it holds, as the old store's elements and the joins
    they receive: a want's holder is the element that relies on what it wants, the receiver of the old Join."""
    drawn = project_store.drawn(name) or {}
    start = len(name) + 1
    held: dict[str, list[str]] = {}
    for one in cast(list[dict[str, Any]], drawn.get('elements') or []):
        address = str(one['address'])[start:]
        if address and not address.startswith('overlay.'):
            held.setdefault(address, [str(one.get('name') or one.get('technical_name') or '')])
    for want in cast(list[dict[str, Any]], drawn.get('wants') or []):
        holder = str(want['holder'])[start:]
        if holder and not holder.startswith('overlay.'):
            held.setdefault(holder, ['']).append(' '.join(str(want[part]) for part in ('why', 'how') if want.get(part)))
    return held


def _done(answer: dict[str, object], what: str) -> None:
    if answer.get('status') == 'error':
        raise StoreError(f'the project store refused {what}: {answer.get("message")}',
                         str(answer.get('remediation') or 'metaform map work op=list'))
