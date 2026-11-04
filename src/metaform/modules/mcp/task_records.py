"""What the tasks extension keeps of a tool call answered with a task, BASE-030: the mcp module's own table at project
level, STORE-045, so a task outlives the server process that ran it.

The extension asks a server not to answer with a task until `tasks/get` would find it, and lets the client keep
polling after the server it asked has gone: this server's relay replaces its process on a schema upgrade while the AI
tool's connection stays, and a server over HTTP restarts. So each task is a row, written before the call is answered,
holding its state in the one status vocabulary of work, `metaform.data.status`, its status message, and once it ends
its tool result or its JSON-RPC error.

A task runs in the server process that answered the call, its `owner`, named by that process's id and the time the
system started it, `owner()`. A task still open whose owner has ended is read as failed with `STOPPED` when a client
asks for it, `get`, so a client polling after the process stopped is told so instead of waiting for ever; nothing marks
a task alive on a clock. A cancel is recorded as a request (`request_cancel`), seen by the owner at once or, from
another process, by the `map.changed` the write announces, which names the `tool_tasks` table and the kind `task`; the
owner then reads only the tasks it runs, `ended`. The task ends only when its work does, cancelled if the work stopped
and completed with its result if it finished first, as the extension's cooperative cancellation allows. Each task is
kept for `TTL_MS` from its creation, the `ttlMs` every task states, and removed after that whenever a task is made.

"""
from __future__ import annotations

import os
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any

from metaform.data import Column, Index, Store, StoreError, Table, status

TTL_MS = 24 * 60 * 60 * 1000  # how long a task is kept from its creation: a day, stated as every task's ttlMs
TABLE_NAME = 'mcp.tool_tasks'  # the table as a change names it, `map.changed`'s tables
KIND = 'task'  # the kind of change a task write says it is, `Tx.concern`
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


def owner() -> str:
    """This process as a task's owner: its id, the time the system started it where the system says, and a random
    part, so a process that later takes the same id is never read as the owner."""
    return f'{os.getpid()}:{_started(os.getpid())}:{uuid.uuid4().hex}'


def _stat(pid: int) -> list[str]:
    """Process `pid`'s fields after its name in /proc/<pid>/stat, its state first and its start time twentieth: on
    Linux, while it exists; [] elsewhere, or once it is gone."""
    try:
        with open(f'/proc/{pid}/stat', encoding='ascii', errors='replace') as handle:
            fields = handle.read().rsplit(')', 1)[1].split()
    except (OSError, IndexError):
        return []
    return fields if len(fields) > 19 else []


def _started(pid: int) -> str:
    """When the system started process `pid`, in its clock ticks since boot, on Linux; '' elsewhere, where the id
    alone names the process."""
    fields = _stat(pid)
    return fields[19] if fields else ''


def _alive(pid: int) -> bool:
    """Whether process `pid` runs: by its handle's exit code on Windows, since os.kill there would end it."""
    if pid <= 0:
        return False
    if sys.platform == 'win32':
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _lost(row: Any) -> bool:
    """Whether a task's owner has ended: its process is gone, or the id now names a process started at another time.
    An owner written before owners named their process is read as ended: that server ran older code and is gone."""
    pid, _, rest = str(row['owner']).partition(':')
    started, _, _ = rest.partition(':')
    if not pid.isdigit() or not rest:
        return True
    fields = _stat(int(pid))
    if fields:  # Linux: ended once it exited, a zombie its parent has not yet reaped, or another process by now
        return fields[0] in ('Z', 'X') or fields[19] != started
    return bool(started) or not _alive(int(pid))  # a start time was read, so the process was Linux's and is gone


def get(project: str, task_id: str) -> Call | None:
    """The task as it stands, read without a write lock, since a client polls it every second; one still running
    whose owner has ended is moved to failed first, `_lost`. None when there is no such task, or its time has
    passed."""
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


def request_cancel(project: str, task_id: str, message: str) -> bool:
    """Record that tasks/cancel asked to stop a task still open, with the message that says so; the task stays as it
    is until its work ends. Its change says it is a task's, so the owner in another process hears it and reads only
    its own tasks. False when there is no such open task."""
    with _own(project).tables() as tx:
        row = tx.get('tool_tasks', {'task_id': task_id})
        if row is None or row['state'] not in status.OPEN:
            return False
        tx.concern(kind=KIND)
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
        tx.concern(kind=KIND)
        tx.update('tool_tasks', {'task_id': task_id}, {'state': state, 'updated': _now(), **values})
    return True


def ended(project: str, running: list[str]) -> list[str]:
    """Of the tasks this process runs, those whose cancel another process has asked for, or that have ended or gone
    since, so the owner stops their work: read when a change says a task changed, one row each."""
    found: list[str] = []
    with _own(project).tables(write=False) as tx:
        for task_id in running:
            row = tx.get('tool_tasks', {'task_id': task_id})
            if row is None or row['state'] in status.TERMINAL or row['cancel']:
                found.append(task_id)
    return found
