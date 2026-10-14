"""The roundtable's tables and the reads and writes on them, BASE-066 and STORE-045.

A discussion is numbered in the project and its submissions within it, which gives each submission its resource
address, `metaform://roundtable/discussion<N>/submission<M>`. Every submission is kept, accepted or not, with its
seat, its text and Jev's four nouls, so the threshold can later be checked against the person's own judgment. A
seat keeps its own running conversation: the number of the last submission it was shown, and for a model reached
through OpenRouter the messages it has sent and received. A comment waits in `waiting` until the runner enters it
at the next gap between turns. The tables live in the project's store, `place='project'`, so a clear of the map
keeps the record of every table, as it keeps the reports in `docs/roundtables/`.
"""
from __future__ import annotations

import time
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, cast

from metaform.data import Column, Store, Table, Tables
from metaform.module import Stop

STATES = ('running', 'held', 'ending', 'ended')  # a table runs, is held by its chair or by a failure, then ends
KINDS = ('seat', 'person', 'head', 'none')  # a seat's submission, a comment of the person or the head agent, no reply
NOULS = ('new', 'valuable', 'relevant', 'keep')  # Jev's four nouls, in the order the review's array gives them

TABLES = Tables(version=1, tables=(
    Table('discussions', place='project', key=('number',), columns=(
        Column('number', 'int', required=True), Column('address', required=True),
        Column('subject', required=True), Column('opening', required=True),
        # who chairs: 'person', or 'head' with the head agent's ticket and dispatch session, to deliver turns into
        Column('chair', required=True), Column('chair_work'), Column('chair_session'),
        Column('seats', 'json', required=True), Column('state', required=True), Column('reason'),
        # where the table is: the round, the seat whose turn is next, and how many seat submissions this round kept
        Column('round', 'int', required=True, default=1), Column('position', 'int', required=True, default=0),
        Column('round_kept', 'int', required=True, default=0),
        # the last submission delivered into the head agent's session, so a restart neither skips nor repeats one
        Column('delivered', 'int', required=True, default=0),
        # until when the person is watching, renewed by the page; and a continue that ends the pause at once
        Column('watched', 'real', required=True, default=0.0), Column('go', 'bool', required=True, default=False),
        # the runner holding the table and when it last said so; a submission Jev could not judge, kept for continue
        Column('runner'), Column('beat', 'real', required=True, default=0.0), Column('unjudged', 'json'),
        Column('report'), Column('report_error'), Column('created', required=True), Column('ended'))),
    Table('seats', place='project', key=('discussion', 'position'), columns=(
        Column('discussion', 'int', required=True), Column('position', 'int', required=True),
        Column('kind', required=True), Column('id', required=True),
        Column('seen', 'int', required=True, default=0), Column('messages', 'json'),
        # an agent seat's turn: what it is shown, when the turn began, its reply, its tries over the limit, and the
        # agent session that first answered for it, MCP-042
        Column('pending'), Column('asked', 'real'), Column('reply', 'json'),
        Column('tries', 'int', required=True, default=0), Column('session'),
        Column('taken', 'int', required=True, default=0), Column('kept', 'int', required=True, default=0))),
    Table('submissions', place='project', key=('discussion', 'number'), columns=(
        Column('discussion', 'int', required=True), Column('number', 'int', required=True),
        Column('round', 'int', required=True), Column('position', 'int'), Column('seat', required=True),
        Column('kind', required=True), Column('text', required=True),
        Column('accepted', 'bool', required=True, default=False),
        Column('new', 'real'), Column('valuable', 'real'), Column('relevant', 'real'), Column('keep', 'real'),
        Column('over512', 'bool', required=True, default=False), Column('reason'), Column('created', required=True))),
    Table('waiting', place='project', key=('discussion', 'seq'), columns=(
        Column('discussion', 'int', required=True), Column('seq', 'int', required=True),
        Column('by', required=True), Column('text', required=True))),
))


def stamp() -> str:
    return datetime.now(UTC).isoformat(timespec='seconds')


def own(store: Store) -> Store:
    """The roundtable's own store on the same project, whichever module the store was opened for."""
    return store if store.module == 'roundtable' else Store(store.project_id, module='roundtable')


def discussion(store: Store, number: int) -> dict[str, Any]:
    """The discussion numbered so, or a Stop naming the list."""
    with own(store).tables(write=False) as tx:
        found = tx.get('discussions', {'number': number})
    if found is None:
        raise Stop(f'No roundtable discussion {number} in this project.', 'metaform roundtable list')
    return dict(found)


def discussions(store: Store) -> list[dict[str, Any]]:
    with own(store).tables(write=False) as tx:
        return [dict(row) for row in tx.rows('discussions', limit=0).results]


def seats(store: Store, number: int) -> list[dict[str, Any]]:
    with own(store).tables(write=False) as tx:
        return [dict(row) for row in tx.rows('seats', {'discussion': number}, limit=0).results]


def submissions(store: Store, number: int, since: int = 0) -> list[dict[str, Any]]:
    """The discussion's submissions numbered after `since`, in order."""
    with own(store).tables(write=False) as tx:
        found = tx.rows('submissions', {'discussion': number}, limit=0).results
    return [dict(row) for row in found if int(row['number']) > since]


def submission(store: Store, number: int, at: int) -> dict[str, Any]:
    with own(store).tables(write=False) as tx:
        found = tx.get('submissions', {'discussion': number, 'number': at})
    if found is None:
        raise Stop(f'No submission {at} in roundtable discussion {number}.',
                   f'metaform roundtable read {number}')
    return dict(found)


def opened(store: Store, row: Mapping[str, Any], chosen: list[dict[str, str]]) -> int:
    """A new discussion with its seats in order; its number, the next in the project."""
    with own(store).tables() as tx:
        number = 1 + max((int(one['number']) for one in tx.rows('discussions', limit=0).results), default=0)
        tx.insert('discussions', {**row, 'number': number, 'seats': chosen, 'state': 'running',
                                  'created': stamp()})
        for position, seat in enumerate(chosen):
            tx.insert('seats', {'discussion': number, 'position': position, 'kind': seat['kind'],
                                'id': seat['id'], 'messages': []})
    return number


def change(store: Store, number: int, **changes: Any) -> dict[str, Any]:
    with own(store).tables() as tx:
        found = tx.update('discussions', {'number': number}, changes)
    if found is None:
        raise Stop(f'No roundtable discussion {number} in this project.', 'metaform roundtable list')
    return dict(found)


def seat_change(store: Store, number: int, position: int, **changes: Any) -> None:
    with own(store).tables() as tx:
        tx.update('seats', {'discussion': number, 'position': position}, changes)


def record(store: Store, number: int, entry: Mapping[str, Any]) -> dict[str, Any]:
    """One submission, numbered next in its discussion; a seat's counts its turn and, when accepted, its keep."""
    with own(store).tables() as tx:
        latest = max((int(one['number']) for one in tx.rows('submissions', {'discussion': number}, limit=0).results),
                     default=0)
        row = {'over512': False, 'accepted': False, **entry, 'discussion': number, 'number': latest + 1,
               'created': stamp()}
        tx.insert('submissions', row)
        position = entry.get('position')
        if position is not None:
            seat = tx.get('seats', {'discussion': number, 'position': position})
            if seat is not None:
                tx.update('seats', {'discussion': number, 'position': position},
                          {'taken': int(seat['taken']) + 1, 'kept': int(seat['kept']) + int(bool(row['accepted']))})
    return row


def wait_comment(store: Store, number: int, by: str, text: str) -> None:
    with own(store).tables() as tx:
        tx.insert('waiting', {'discussion': number, 'seq': time.time_ns(), 'by': by, 'text': text})


def take_comments(store: Store, number: int) -> list[dict[str, Any]]:
    """The comments waiting, oldest first, taken out of the queue."""
    with own(store).tables() as tx:
        found = [dict(row) for row in tx.rows('waiting', {'discussion': number}, limit=0).results]
        for row in found:
            tx.delete('waiting', {'discussion': number, 'seq': row['seq']})
    return found


def nouls(row: Mapping[str, Any]) -> list[float] | None:
    """A submission's four nouls as the review's array, `[new, valuable, relevant, keep]`; None when unjudged."""
    values = [row.get(name) for name in NOULS]
    return None if any(value is None for value in values) else [round(float(cast(float, v)), 2) for v in values]
