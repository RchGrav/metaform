"""The roundtable's tables and the reads and writes on them, BASE-066 and STORE-045.

A discussion is numbered in the project and its submissions within it, which gives each submission its resource
address, `metaform://roundtable/discussion<N>/submission<M>`. Every submission is kept, accepted or not, with its
seat, its text and Jev's four nouls, so the threshold can later be checked against the person's own judgment. A
seat keeps its own running conversation: the number of the last submission it was shown, and for a model reached
through OpenRouter the messages it has sent and received. A harness seat's conversation is its dispatch session, on
the one held ticket its table keeps for its harness seats; its row names the agent and model, the session, the last
line of the session's thread it has read, and why it left the table when its session ended. A comment waits in
`waiting` until the runner enters it at the next gap between turns. The tables live in the project's store,
`place='project'`, so a clear of the map keeps the record of every table, as it keeps the reports in
`docs/roundtables/`.
"""
from __future__ import annotations

import time
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, cast

from metaform.data import Column, Store, Table, Tables
from metaform.module import Stop

from .names import names as named

STATES = ('running', 'held', 'ending', 'ended')  # a table runs, is held by its chair or by a failure, then ends
KINDS = ('seat', 'person', 'head', 'none')  # a seat's submission, a comment of the person or the head agent, no reply
NOULS = ('new', 'valuable', 'relevant', 'keep')  # Jev's four nouls, in the order the review's array gives them

TABLES = Tables(version=6, compatible_from=1, tables=(  # 2 adds the harness seats' columns, 3 the scene's, 4 the limits,
    # 5 the model a harness seat's agent reported, 6 what a model seat's turn used of the prompt cache
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
        Column('report'), Column('report_error'), Column('created', required=True), Column('ended'),
        # the held ticket its harness seats' dispatch sessions hang on, closed when the table ends
        Column('seat_work'),
        # the scene, version 3: whether the seats have had their time to explore their controls and until when it
        # runs, and the runner's watch server, {url, token}, while it runs
        Column('explored', 'bool', required=True, default=False), Column('explore_until', 'real'),
        Column('scene', 'json'),
        # version 4: the most rounds and OpenRouter dollars this table was opened with, none for the settings'; and the
        # dollars spent so far, from the usage cost OpenRouter returns for its seats, its reporter and Jev
        Column('rounds', 'int'), Column('spend', 'real'), Column('spent', 'real', required=True, default=0.0))),
    Table('seats', place='project', key=('discussion', 'position'), columns=(
        Column('discussion', 'int', required=True), Column('position', 'int', required=True),
        Column('kind', required=True), Column('id', required=True),
        Column('seen', 'int', required=True, default=0), Column('messages', 'json'),
        # an agent seat's turn: what it is shown, when the turn began, its reply, its tries over the limit, and the
        # agent session that first answered for it, MCP-042
        Column('pending'), Column('asked', 'real'), Column('reply', 'json'),
        Column('tries', 'int', required=True, default=0), Column('session'),
        Column('taken', 'int', required=True, default=0), Column('kept', 'int', required=True, default=0),
        # a harness seat's agent and model, the last line of its session's thread read, and why it left the table;
        # its dispatch session is kept in `session`
        Column('agent'), Column('model'), Column('cursor', 'int', default=0), Column('gone'),
        # version 3: the name the seat goes by at its table, and its facing, a bearing in degrees, none at its home
        # facing toward the middle of the table
        Column('name'), Column('facing', 'real'),
        # version 5: the model a harness seat's agent reports its session runs, as the session's state names it, so
        # the record says which model the seat really was
        Column('reported'))),
    Table('submissions', place='project', key=('discussion', 'number'), columns=(
        Column('discussion', 'int', required=True), Column('number', 'int', required=True),
        Column('round', 'int', required=True), Column('position', 'int'), Column('seat', required=True),
        Column('kind', required=True), Column('text', required=True),
        Column('accepted', 'bool', required=True, default=False),
        Column('new', 'real'), Column('valuable', 'real'), Column('relevant', 'real'), Column('keep', 'real'),
        Column('over512', 'bool', required=True, default=False), Column('reason'), Column('created', required=True),
        # version 3: the name of the seat that made it, as the discussion shows it
        Column('name'),
        # version 6: a model seat's turn through OpenRouter, every call of it added up: the prompt tokens sent, those
        # read from the provider's cache and those written to it, and the US dollars; none for other seats
        Column('prompt_tokens', 'int'), Column('cached_tokens', 'int'), Column('cache_write_tokens', 'int'),
        Column('cost', 'real'))),
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
    """The table's seats in order, each with its name; a table opened before names has them made from its seats."""
    with own(store).tables(write=False) as tx:
        found = [dict(row) for row in tx.rows('seats', {'discussion': number}, limit=0).results]
    found.sort(key=lambda row: int(row['position']))
    for row, name in zip(found, named(found), strict=True):
        row['name'] = row.get('name') or name
    return found


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
        for position, (seat, name) in enumerate(zip(chosen, named(chosen), strict=True)):
            tx.insert('seats', {'discussion': number, 'position': position, 'kind': seat['kind'],
                                'id': seat['id'], 'messages': [], 'agent': seat.get('agent'),
                                'model': seat.get('model'), 'name': name})
    return number


def change(store: Store, number: int, **changes: Any) -> dict[str, Any]:
    with own(store).tables() as tx:
        found = tx.update('discussions', {'number': number}, changes)
    if found is None:
        raise Stop(f'No roundtable discussion {number} in this project.', 'metaform roundtable list')
    return dict(found)


def spend(store: Store, number: int, cost: float) -> None:
    """Add what one paid call cost to the table's spent, in one transaction, so seats exploring at once all count."""
    with own(store).tables() as tx:
        found = tx.get('discussions', {'number': number})
        if found is not None:
            tx.update('discussions', {'number': number}, {'spent': float(found['spent'] or 0) + cost})


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
