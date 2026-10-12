"""The workflow run record, BASE-051: where a run's resumable state is kept between the agents that carry it.

One row per run, in the workflow module's own table at project level, STORE-045, so a run outlives a clear of the
project's metaforms and a change of the active one, and is reached by its run id from any agent working in the
project. A run is either a call, whose call frames, caller scope, waiting children and parallel branches the
executor keeps here, or an assignment, a skill handed to a fresh agent. `parent` names the run a fresh-agent call
returns to.

`state` is the run's lifecycle in the one status vocabulary of work, `metaform.data.status`, which maps it to MCP
Tasks and A2A task states: `running`; `waiting` on its children; `input_required`, paused on the person, with what
stopped it in `message` and the ticket and session of the agent that paused it in `ticket` and `session`; then
`completed` or `failed` once it returns, or `cancelled`, with the reason in `message`. `status.TRANSITIONS` decides
every move; a run that has ended keeps its row, with its result, and accepts nothing more. `updated` is when its state
last changed, an MCP task's `lastUpdatedAt`.
"""
from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from metaform.data import Column, Index, Store, Table, TableTx, status
from metaform.module import Stop

TABLE = Table('runs', place='project', key=('run_id',), columns=(
    Column('run_id', required=True), Column('kind', required=True), Column('state', required=True),
    Column('parent'), Column('context', 'json'), Column('frames', 'json'), Column('caller', 'json'),
    Column('waiting', 'json'), Column('branches', 'json'), Column('assignment', 'json'), Column('result', 'json'),
    Column('created', required=True), Column('closed'), Column('seq', 'int', required=True),
    Column('message'), Column('updated'), Column('ticket'), Column('session')),
    indexes=(Index(('parent',)), Index(('state', 'seq'))))
STATE = ('context', 'frames', 'caller', 'parent', 'waiting', 'branches', 'assignment')  # what the executor carries
HELP = 'metaform help workflow'


@dataclass(frozen=True)
class Run:
    run_id: str
    kind: str  # call or assign
    state: str  # a run's states of metaform.data.status: running, waiting, input_required, completed, failed, cancelled
    value: dict[str, Any]  # the executor's state: context, frames, caller, parent and, while waiting, waiting
    created: str
    closed: str | None
    result: Any = None  # once it returned: its value, or the named error it failed with
    message: str | None = None  # what stopped it while input_required, or why it was cancelled
    ticket: str | None = None  # the work id of the ticket whose agent paused it, MAP-050, kept once answered
    session: str | None = None  # that agent's dispatch session, to message it once the person has answered

    @property
    def open(self) -> bool:
        return self.state in status.OPEN


def _now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _own(store: Store) -> Store:
    return store if store.module == 'workflow' else Store(store.project_id, module='workflow')


def _run(row: dict[str, Any]) -> Run:
    value = {key: row[key] for key in STATE if row[key] is not None or key in ('parent', 'context')}
    return Run(str(row['run_id']), str(row['kind']), str(row['state']), value, str(row['created']), row['closed'],
               row['result'], row['message'], row['ticket'], row['session'])


def _columns(value: dict[str, Any]) -> dict[str, Any]:
    columns = {key: value.get(key) for key in STATE}
    columns['state'] = 'waiting' if value.get('waiting') else 'running'
    return columns


def _stopped(store: Store, run_id: str, row: dict[str, Any] | None) -> Stop:
    """A stop for a run that is not open: none by that id, or one that ended, named with how it ended."""
    ended = '' if row is None else f': it is {row["state"]}' + (f', {row["message"]}' if row['message'] else '')
    return Stop(f'No open workflow run {run_id} in project {store.project_id}{ended}.', HELP)


def start(store: Store, kind: str, value: dict[str, Any]) -> str:
    """A new open run holding the executor's state, and its id."""
    run_id = uuid.uuid4().hex
    now = _now()
    with _own(store).tables() as tx:
        tx.insert('runs', {'run_id': run_id, 'kind': kind, **_columns(value), 'created': now, 'updated': now,
                           'seq': time.time_ns()})
    return run_id


def read(store: Store, run_id: str) -> Run | None:
    with _own(store).tables(write=False) as tx:
        row = tx.get('runs', {'run_id': run_id})
    return None if row is None else _run(dict(row))


def held(store: Store, run_id: str) -> Run:
    """The open run, or a stop naming how to find one: a run that ended accepts nothing more."""
    with _own(store).tables(write=False) as tx:
        row = tx.get('runs', {'run_id': run_id})
    if row is None or row['state'] not in status.OPEN:
        raise _stopped(store, run_id, None if row is None else dict(row))
    return _run(dict(row))


def _move(tx: TableTx, store: Store, run_id: str, columns: dict[str, Any]) -> dict[str, Any]:
    """Write a change of an open run, its new state checked against the vocabulary's transitions; its old row."""
    row = tx.get('runs', {'run_id': run_id})
    if row is None or row['state'] not in status.OPEN:
        raise _stopped(store, run_id, None if row is None else dict(row))
    status.moved(str(row['state']), str(columns['state']), f'metaform workflow resume run={run_id}')
    tx.update('runs', {'run_id': run_id}, {**columns, 'updated': _now()})
    return dict(row)


def save(store: Store, run_id: str, value: dict[str, Any]) -> None:
    """Write the run's state as the executor holds it now."""
    with _own(store).tables() as tx:
        _move(tx, store, run_id, _columns(value))


def _mutating(tx: TableTx, store: Store, run_id: str, change: Callable[[dict[str, Any]], dict[str, Any]]) -> Run:
    row = tx.get('runs', {'run_id': run_id})
    if row is None or row['state'] not in status.OPEN:
        raise _stopped(store, run_id, None if row is None else dict(row))
    found = _run(dict(row))
    value = change(found.value)
    columns = _columns(value)
    _move(tx, store, run_id, columns)
    return Run(found.run_id, found.kind, columns['state'], value, found.created, None)


def mutate(store: Store, run_id: str, change: Callable[[dict[str, Any]], dict[str, Any]]) -> Run:
    """Read and change an open run's state in one transaction, so branches returning at once each keep their result."""
    with _own(store).tables() as tx:
        return _mutating(tx, store, run_id, change)


Delivery = tuple[str, Callable[[dict[str, Any]], dict[str, Any]]]  # the caller's run id, and how its state takes a return


def close(store: Store, run_id: str, *, result: Any = None, failed: bool = False,
          delivery: Delivery | None = None) -> Run | None:
    """The run has returned: completed, or failed with a named error, its result kept and its row kept. With a
    delivery, its caller receives the return in the same transaction, so a cancel cannot fall between them; the
    caller's run after."""
    with _own(store).tables() as tx:
        _move(tx, store, run_id, {'state': 'failed' if failed else 'completed', 'result': result, 'waiting': None,
                                  'branches': None, 'closed': _now()})
        return None if delivery is None else _mutating(tx, store, *delivery)


def pause(store: Store, run_id: str, found: str, *, ticket: str | None = None, session: str | None = None) -> Run:
    """Pause a running run on the person, `input_required`, with what stopped it as its message until they answer,
    and the ticket and session of the agent that paused it, so the answer can name who goes on."""
    columns = {'state': 'input_required', 'message': found, 'ticket': ticket, 'session': session}
    with _own(store).tables() as tx:
        row = _move(tx, store, run_id, columns)
    return _run({**row, **columns})


def answer(store: Store, run_id: str, change: Callable[[dict[str, Any], str], dict[str, Any]]) -> Run:
    """The person's answer to a run paused on them: `change` receives the run's state and what stopped it and places
    the answer in it; the run is running again and its message is cleared."""
    with _own(store).tables() as tx:
        row = tx.get('runs', {'run_id': run_id})
        if row is None or row['state'] != 'input_required':
            if row is not None and row['state'] in status.OPEN:
                raise Stop(f'Workflow run {run_id} is {row["state"]}; only a run paused on the person takes an '
                           'answer.', f'metaform workflow resume run={run_id}')
            raise _stopped(store, run_id, None if row is None else dict(row))
        found = _run(dict(row))
        value = change(found.value, str(found.message or ''))
        _move(tx, store, run_id, {**{key: value.get(key) for key in STATE}, 'state': 'running', 'message': None})
    return Run(found.run_id, found.kind, 'running', value, found.created, None, ticket=found.ticket,
               session=found.session)


def cancel(store: Store, run_id: str, reason: str, *,
           delivery: Callable[[Run], Delivery | None] | None = None) -> tuple[list[str], Run | None]:
    """Cancel an open run and every open run below it, in one transaction: each keeps its row, `cancelled` with the
    reason as its message, and accepts nothing more. `delivery`, given the named run, says what its caller receives,
    in the same transaction, when that caller is still open. The ids cancelled, the named run first, and the caller's
    run after."""
    cancelled: list[str] = []
    with _own(store).tables() as tx:
        first = tx.get('runs', {'run_id': run_id})
        if first is None or first['state'] not in status.OPEN:
            raise _stopped(store, run_id, None if first is None else dict(first))
        pending = [run_id]
        while pending:
            one = pending.pop(0)
            row = tx.get('runs', {'run_id': one})
            if row is None or row['state'] not in status.OPEN:
                continue
            _move(tx, store, one, {'state': 'cancelled', 'message': reason or None, 'waiting': None,
                                   'branches': None, 'closed': _now()})
            cancelled.append(one)
            pending.extend(str(child['run_id']) for child in tx.rows('runs', {'parent': one}, limit=0).results)
        given = None if delivery is None else delivery(_run(dict(first)))
        caller = None if given is None else tx.get('runs', {'run_id': given[0]})
        after = (_mutating(tx, store, *given) if given is not None and caller is not None
                 and caller['state'] in status.OPEN else None)
    return cancelled, after


LIMIT = 20  # runs listed at a time; ended runs keep their rows, so a state's list grows without end


def listed(store: Store, state: str | None = None, *, limit: int = LIMIT,
           after: str | None = None) -> tuple[list[dict[str, Any]], str | None]:
    """A page of the open runs, oldest first, or of those in one state, the newest first for a state that has ended:
    each run's id, kind, state, caller, message, the ticket that paused it and when its state last changed; and the
    cursor of the next page, None on the last. `after` is the cursor a page returned."""
    given = None if state is None else status.known(state, HELP)
    with _own(store).tables(write=False) as tx:
        rows = tx.rows('runs', None if given is None else {'state': given}, limit=0).results
    newest = given in status.TERMINAL
    try:
        past = None if after is None else int(after)
    except ValueError:
        raise Stop(f'{after!r} is not a cursor a page of runs returned.', 'metaform workflow runs') from None
    kept = sorted((row for row in rows if given or row['state'] in status.OPEN),
                  key=lambda row: int(row['seq']), reverse=newest)
    if past is not None:
        kept = [row for row in kept if (int(row['seq']) < past if newest else int(row['seq']) > past)]
    page = kept[:limit] if limit else kept
    cursor = str(page[-1]['seq']) if limit and len(kept) > limit else None
    return [{'run': row['run_id'], 'kind': row['kind'], 'state': row['state'], 'parent': row['parent'],
             **{key: row[key] for key in ('message', 'ticket') if row[key]},
             'updated': row['updated'] or row['created']} for row in page], cursor


def upgrade(tx: TableTx, found: int) -> None:
    """Version 3: every state a version 2 row holds, running, waiting, completed or failed, is already in the one
    status vocabulary and keeps its meaning, so no row changes state; each row's new `updated` is when it last
    changed as far as the row shows, its close or else its creation. Its `message` stays empty. Version 4 adds
    `ticket` and `session`, empty on every row, since no row before it was paused by an agent with them kept."""
    if found >= 3:
        return
    for row in tx.rows('runs', limit=0).results:
        status.known(str(row['state']), 'metaform disable workflow')
        tx.update('runs', {'run_id': row['run_id']}, {'updated': row['closed'] or row['created']})
