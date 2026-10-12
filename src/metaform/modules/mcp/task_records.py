"""What the tasks extension keeps of a tool call answered with a task, BASE-030: the mcp module's own table at project
level, STORE-045, so a task outlives the server process that ran it.

The extension asks a server not to answer with a task until `tasks/get` would find it, and lets the client keep
polling after the server it asked has gone: this server's relay replaces its process on a schema upgrade while the AI
tool's connection stays, and a server over HTTP restarts. So each task is a row, written before the call is answered,
holding its state in the one status vocabulary of work, `metaform.data.status`, its status message, and once it ends
its tool result or its JSON-RPC error.

A task runs in the server process that answered the call, its `owner`, which marks every task it still runs as alive
every `BEAT_S` seconds (`beat`). A task whose owner has not marked it for `LOST_S` seconds is read as failed with
`STOPPED`, so a client polling after the process stopped is told so instead of waiting for ever. A cancel is recorded
as a request (`request_cancel`), seen by the owner at once or, from another process, at its next mark; the task ends
only when its work does, cancelled if the work stopped and completed with its result if it finished first, as the
extension's cooperative cancellation allows. Each task is kept for `TTL_MS` from its
creation, the `ttlMs` every task states, and removed after that whenever a task is made.

Workflow runs are tasks too, kept by the workflow module in its own run records, BASE-051; nothing of them is here.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from metaform.data import Column, Index, Store, StoreError, Table, status

TTL_MS = 24 * 60 * 60 * 1000  # how long a task is kept from its creation: a day, stated as every task's ttlMs
BEAT_S = 10  # how often the owner marks the tasks it still runs as alive
LOST_S = 45  # how long a running task may go unmarked before it is read as failed: its owner has stopped
STOPPED = 'The Metaform server stopped before the task finished; call the tool again.'

TABLE = Table('tool_tasks', place='project', key=('task_id',), columns=(
    Column('task_id', required=True), Column('tool', required=True), Column('state', required=True),
    Column('owner', required=True), Column('created', required=True), Column('updated', required=True),
    Column('beat', 'int', required=True), Column('expires', 'int', required=True), Column('message'),
    Column('result', 'json'), Column('error', 'json'), Column('cancel', 'int')),
    indexes=(Index(('expires',)),))


@dataclass(frozen=True)
class Call:
    """One tool call kept as a task: its state in the status vocabulary, its status message, and once it ends its
    tool result or its JSON-RPC error."""
    task_id: str
    tool: str
    state: str
    owner: str
    created: str
    updated: str
    message: str | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


def _now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _own(project: str) -> Store:
    return Store(project, module='mcp')


def _call(row: Any) -> Call:
    return Call(str(row['task_id']), str(row['tool']), str(row['state']), str(row['owner']), str(row['created']),
                str(row['updated']), row['message'], row['result'], row['error'])


def create(project: str, task_id: str, tool: str, owner: str, message: str) -> Call:
    """A task for one tool call, written before the call is answered, so `tasks/get` finds it at once. Tasks past
    their time are removed first."""
    now = time.time()
    with _own(project).tables() as tx:
        for row in tx.rows('tool_tasks', by=('expires',), limit=0).results:
            if int(row['expires']) > now:
                break
            tx.delete('tool_tasks', {'task_id': row['task_id']})
        stamp = _now()
        row = tx.insert('tool_tasks', {
            'task_id': task_id, 'tool': tool, 'state': 'running', 'owner': owner, 'created': stamp,
            'updated': stamp, 'beat': int(now), 'expires': int(now + TTL_MS / 1000), 'message': message})
    return _call(row)


def get(project: str, task_id: str) -> Call | None:
    """The task as it stands, read without a write lock, since a client polls it every second; one still running
    whose owner has not marked it for `LOST_S` seconds is moved to failed first, since its owner has stopped. None when
    there is no such task, or its time has passed."""
    with _own(project).tables(write=False) as tx:
        row = tx.get('tool_tasks', {'task_id': task_id})
    if row is None or int(row['expires']) <= time.time():
        return None
    if row['state'] in status.OPEN and _lost(row):
        with _own(project).tables() as tx:
            row = tx.get('tool_tasks', {'task_id': task_id})
            if row is not None and row['state'] in status.OPEN and _lost(row):
                row = tx.update('tool_tasks', {'task_id': task_id}, {
                    'state': 'failed', 'updated': _now(), 'message': STOPPED,
                    'error': {'code': -32603, 'message': STOPPED}})
    return None if row is None else _call(row)


def _lost(row: Any) -> bool:
    return time.time() - int(row['beat']) > LOST_S


def request_cancel(project: str, task_id: str, message: str) -> bool:
    """Record that tasks/cancel asked to stop a task still open, with the message that says so; the task stays as it
    is until its work ends. False when there is no such open task."""
    with _own(project).tables() as tx:
        row = tx.get('tool_tasks', {'task_id': task_id})
        if row is None or row['state'] not in status.OPEN:
            return False
        tx.update('tool_tasks', {'task_id': task_id}, {'cancel': 1, 'updated': _now(), 'message': message})
    return True


def move(project: str, task_id: str, state: str, **values: Any) -> bool:
    """Move a task to `state` with its message, result or error, when the vocabulary allows it from where the task
    stands; a task that has ended stays as it ended. False when it did not move."""
    with _own(project).tables() as tx:
        row = tx.get('tool_tasks', {'task_id': task_id})
        if row is None or row['state'] in status.TERMINAL:
            return False
        try:
            status.moved(str(row['state']), state, 'call tasks/get')
        except StoreError:
            return False
        tx.update('tool_tasks', {'task_id': task_id}, {'state': state, 'updated': _now(), **values})
    return True


def beat(project: str, owner: str, running: list[str]) -> list[str]:
    """Mark the tasks this owner still runs as alive; returns those among them whose cancel another process has
    asked for, or that have ended since, so the owner stops their work."""
    ended: list[str] = []
    now = int(time.time())
    with _own(project).tables() as tx:
        for task_id in running:
            row = tx.get('tool_tasks', {'task_id': task_id})
            if row is None or row['state'] in status.TERMINAL or row['cancel']:
                ended.append(task_id)
            if row is not None and row['state'] not in status.TERMINAL:
                tx.update('tool_tasks', {'task_id': task_id}, {'beat': now})
    return ended
