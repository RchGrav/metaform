"""The MCP Tasks extension, `io.modelcontextprotocol/tasks`: long tool calls as tasks, BASE-030.

Every task speaks the one status vocabulary of work, `metaform.data.status`, whose table gives each state its task
status. Three kinds of work are served as tasks, each only to a client that declares the extension on its request:

- A call of a verb declared `task=True`, such as hello's `wait`: the server writes the task (`task_records.py`),
  answers at once with it, and runs the verb in its own process. When the verb returns, the task holds the tool
  result it would have given; a tool error is a completed task whose result says so, as the extension requires. The
  task outlives the process: a client that polls after the server stopped is told the task failed, `STOPPED`.
  `tasks/cancel` is a request, as the extension makes it: the task is cancelled once its verb has stopped, which an
  `async` verb does at its next `await`, and completed with its result when the verb finished first, as a verb run in
  a thread always does, so a task never reads cancelled while its effect still lands. A cancel asked of another
  process reaches the owner as the `map.changed` its write announces, heard while the owner runs a task, `Running`.
- An assigned agent session, declared `task='session'`, whose durable lifecycle is supplied by enabled modules
  through `task.lifecycle`. The MCP bridge launches the session and reads its persisted handle before responding.
  Its provider owns status, outstanding inputs, results and cancellation, independently of this server process.

Source, read 2026-10-12: github.com/modelcontextprotocol/ext-tasks, specification/2026-07-28/tasks.md and
schema/2026-07-28/schema.ts.
"""
from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import anyio

from metaform import events, home
from metaform.data import StoreError, status
from metaform.module import Context, Stop, context, project_for, provided

from . import task_records as records

EXTENSION = 'io.modelcontextprotocol/tasks'
POLL_MS = 1000  # how often a client is asked to poll, in milliseconds: a long verb's result is not wanted sooner
STOPPED = records.STOPPED
CANCELLED = 'Cancelled through tasks/cancel.'
CANCELLING = 'Cancel asked through tasks/cancel; the task ends cancelled if the tool stops, completed if it finishes.'


def declared(capabilities: Any) -> bool:
    """Whether the request declares the tasks extension; a task is never returned to a client that did not."""
    extensions: Any = getattr(capabilities, 'extensions', None)
    return isinstance(extensions, dict) and EXTENSION in extensions


@dataclass
class Running:
    """The tool calls this server process runs as tasks: who it is, as each task's owner, and the scope that stops
    each call, by task id. While it runs any, it hears the changes of other processes, `listener`, so a cancel asked
    there stops the call at once; with none running it hears nothing."""
    owner: str = field(default_factory=records.owner)
    scopes: dict[str, anyio.CancelScope] = field(default_factory=dict[str, anyio.CancelScope])
    project: str | None = None  # the project whose store keeps the tasks, while any runs
    listener: Any = None
    token: Any = None  # the server's loop, where a scope is cancelled from the listener's thread


def concerns(payload: dict[str, Any], project: str) -> bool:
    """Whether a `map.changed` can say a task of `project` changed, decided from the change alone: its project, the
    tables it wrote when it names them, and its kinds when it names them. One that names neither may have changed
    anything."""
    if payload.get('project') not in (None, '', project):
        return False
    kinds: Any = payload.get('kinds')
    if isinstance(kinds, list) and records.KIND not in kinds:
        return False
    tables: Any = payload.get('tables')
    if isinstance(tables, str):
        return False  # a module's own payload, such as dispatch's, never a task's
    return not isinstance(tables, list) or records.TABLE_NAME in tables


def heard(running: Running, payload: dict[str, Any]) -> None:
    """A change from another process, on the listener's thread: when it can be a task's, the tasks this process runs
    are read, one row each, and each one cancelled or ended since has its work stopped in the server's loop."""
    project, token = running.project, running.token
    if project is None or token is None or not running.scopes or not concerns(payload, project):
        return
    for task_id in records.ended(project, list(running.scopes)):
        scope = running.scopes.get(task_id)
        if scope is not None:
            try:
                anyio.from_thread.run_sync(scope.cancel, token=token)
            except Exception:  # noqa: BLE001, S110  a loop that has stopped has no work left to stop
                pass


async def _listen(running: Running, project: str) -> None:
    """Hear other processes while a task runs, the listener opened in the loop as the resource watcher opens its own;
    then read the tasks once, for a cancel asked before the listener was there."""
    if running.listener is not None:
        return
    running.project, running.token = project, anyio.lowlevel.current_token()
    running.listener = events.listen('mcp', lambda payload: heard(running, payload))
    await anyio.to_thread.run_sync(heard, running, {'project': project})


async def _unlisten(running: Running) -> None:
    """Stop hearing other processes once no task runs; closed in a worker thread, since a close waits for the
    listener's thread, which may be handing a cancel to this loop."""
    if running.scopes or running.listener is None:
        return
    listener, running.listener = running.listener, None
    with anyio.CancelScope(shield=True):
        await anyio.to_thread.run_sync(listener.close)


def create(running: Running, project: str, tool: str, message: str) -> dict[str, Any]:
    """Write the task for one tool call and give its `CreateTaskResult`: written first, so `tasks/get` finds it at
    once. Its id is a random UUID, which no other client can guess, as the extension asks."""
    made = records.create(project, uuid.uuid4().hex, tool, running.owner, message)
    return {'resultType': 'task', **_base(made.task_id, made.created, made.updated, made.state, made.message,
                                          records.TTL_MS)}


async def run(running: Running, project: str, task_id: str, work: Callable[[], Awaitable[dict[str, Any]]]) -> None:
    """Run one tool call as its task and keep its result: cancelled when tasks/cancel stopped the work, completed with
    its result when the work finished, even after a cancel was asked; a stop of the server marks it failed."""
    scope = running.scopes.setdefault(task_id, anyio.CancelScope())
    result: dict[str, Any] | None = None
    try:
        await _listen(running, project)
        with scope:
            result = await work()
        if result is None:  # tasks/cancel stopped the work before it finished
            await anyio.to_thread.run_sync(lambda: records.move(project, task_id, 'cancelled', message=CANCELLED))
        else:
            done = result
            await anyio.to_thread.run_sync(lambda: records.move(project, task_id, 'completed', result=done,
                                                                message=None))
    except anyio.get_cancelled_exc_class():
        with anyio.CancelScope(shield=True):
            await anyio.to_thread.run_sync(lambda: records.move(
                project, task_id, 'failed', error={'code': -32603, 'message': STOPPED}, message=STOPPED))
        raise
    except Exception as error:  # noqa: BLE001  a fault outside the tool's own errors fails the task as JSON-RPC does
        said = f'{type(error).__name__}: {error}'
        await anyio.to_thread.run_sync(lambda: records.move(
            project, task_id, 'failed', error={'code': -32603, 'message': said}, message=said))
    finally:
        running.scopes.pop(task_id, None)
        await _unlisten(running)


def _base(task_id: str, created: str, updated: str, state: str, message: str | None,
          ttl: int | None) -> dict[str, Any]:
    said = cast(dict[str, str], status.MCP_TASKS).get(state, 'working')
    return {'taskId': task_id, 'status': said, 'createdAt': created, 'lastUpdatedAt': updated, 'ttlMs': ttl,
            'pollIntervalMs': POLL_MS, **({'statusMessage': message} if message else {})}


def _of_call(made: records.Call) -> dict[str, Any]:
    task = _base(made.task_id, made.created, made.updated, made.state, made.message, records.TTL_MS)
    if made.state == 'completed':
        return {**task, 'result': made.result}
    if made.state == 'failed':
        return {**task, 'error': made.error or {'code': -32603, 'message': STOPPED}}
    return task


def owning(folder: Path) -> str | None:
    """The project whose store keeps the folder's tool-call tasks, or None when the folder is no project's, and a
    call there is answered without a task, since nowhere would keep it."""
    try:
        return project_for(folder)
    except (Stop, StoreError):
        return None


def lifecycle(folder: Path, project: str | None = None) -> list[tuple[Context, Any]]:
    """Enabled task lifecycle services, resolved through the owning project's public module surface.

    Providers own task persistence, input keys and terminal-state immutability. Ordinary reads use the caller's
    folder; a just-launched task uses its returned project, which may differ from the caller's project.
    """
    if project is not None:
        registered = home.project(project)
        if registered is None:
            return []
        folder = Path(registered.path)
    return [(context(owner, folder, project=project, surface='mcp'), service)
            for owner, service in provided(folder, 'task.lifecycle')]


def seed_session(folder: Path, project: str, task_id: str) -> dict[str, Any] | None:
    """The durable task handle of a launched agent session, read before answering the launch request."""
    for ctx, service in lifecycle(folder, project):
        seeded = service.seed(ctx, task_id)
        if seeded is not None:
            return cast(dict[str, Any], seeded)
    return None


def detailed(project: str | None, task_id: str, folder: Path | None = None) -> dict[str, Any] | None:
    """The full tool-call or assigned-session task; None when no source knows its id."""
    made = None if project is None else records.get(project, task_id)
    if made is not None:
        return _of_call(made)
    for ctx, service in lifecycle(folder) if folder is not None else []:
        detail = service.get(ctx, task_id)
        if detail is not None:
            return cast(dict[str, Any], detail)
    return None


async def update(project: str | None, task_id: str, responses: dict[str, Any], folder: Path | None = None) -> bool:
    """An answer to a task's input request, given to the service that owns the task. False when there is no such
    task."""
    if project is not None and await anyio.to_thread.run_sync(records.get, project, task_id) is not None:
        return True
    services = [] if folder is None else await anyio.to_thread.run_sync(lifecycle, folder)
    for ctx, service in services:
        if await anyio.to_thread.run_sync(service.update, ctx, task_id, responses):
            return True
    return False


async def cancel(running: Running, project: str | None, task_id: str, folder: Path | None = None) -> bool:
    """Cancel a task: for a tool call the cancel is recorded and its work stopped, here at once or by the process
    running it when it hears the change, and `run` ends the task as the work ends. A task that has ended stays as it
    ended. False when there is none."""
    if project is not None and await anyio.to_thread.run_sync(records.get, project, task_id) is not None:
        asked = await anyio.to_thread.run_sync(records.request_cancel, project, task_id, CANCELLING)
        scope = running.scopes.get(task_id)
        if asked and scope is not None:
            scope.cancel()
        return True
    services = [] if folder is None else await anyio.to_thread.run_sync(lifecycle, folder)
    for ctx, service in services:
        if await anyio.to_thread.run_sync(service.cancel, ctx, task_id):
            return True
    return False
