"""The MCP Tasks extension, `io.modelcontextprotocol/tasks`: long tool calls and workflow runs as tasks, BASE-030.

Every task speaks the one status vocabulary of work, `metaform.data.status`, whose table gives each state its task
status. Two kinds of work are served as tasks, each only to a client that declares the extension on its request:

- A call of a verb declared `task=True`, such as hello's `wait`: the server writes the task (`task_records.py`),
  answers at once with it, and runs the verb in its own process. When the verb returns, the task holds the tool
  result it would have given; a tool error is a completed task whose result says so, as the extension requires. The
  task outlives the process: a client that polls after the server stopped is told the task failed, `STOPPED`.
  `tasks/cancel` is a request, as the extension makes it: the task is cancelled once its verb has stopped, which an
  `async` verb does at its next `await`, and completed with its result when the verb finished first, as a verb run in
  a thread always does, so a task never reads cancelled while its effect still lands.
- A workflow run, the work of a verb declared `task='run'`, which returns the id of a run the server itself advances
  to its end: the run is the task, by its run id, which the workflow module makes with a random UUID as the extension
  asks of a task id. Its record is read for `tasks/get`; `tasks/update` and `tasks/cancel` go through the workflow
  module's own `answer` and `cancel` verbs, so the run moves as the workflow module moves it. A run paused on the
  person asks its question as a form, under a key of that one pause. Work that waits on the calling agent to act on
  the verb's result, such as workflow's `assign`, is never a task: a host gives the model a task's result only once
  the task ends, so the agent would never learn what to do.

Source, read 2026-10-12: github.com/modelcontextprotocol/ext-tasks, specification/2026-07-28/tasks.md and
schema/2026-07-28/schema.ts.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import anyio

from metaform.data import Store, StoreError, plain, status
from metaform.module import Stop, project_for, surface

from . import task_records as records

EXTENSION = 'io.modelcontextprotocol/tasks'
POLL_MS = 1000  # how often a client is asked to poll, in milliseconds: a long verb's result is not wanted sooner
ANSWER = 'answer'  # the field of the form a question asks
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
    each call, by task id."""
    owner: str = field(default_factory=lambda: uuid.uuid4().hex)
    scopes: dict[str, anyio.CancelScope] = field(default_factory=dict[str, anyio.CancelScope])


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


async def beat(running: Running, folder: Path) -> None:
    """While the server runs: mark the tasks it runs alive every `BEAT_S` seconds, and stop any that another process
    has ended since, such as by tasks/cancel."""
    while True:
        await anyio.sleep(records.BEAT_S)
        project = await anyio.to_thread.run_sync(owning, folder) if running.scopes else None
        if project is None:
            continue
        ended = await anyio.to_thread.run_sync(records.beat, project, running.owner, list(running.scopes))
        for task_id in ended:
            scope = running.scopes.get(task_id)
            if scope is not None:
                scope.cancel()


def _key(run_id: str, row: dict[str, Any]) -> str:
    """The key of the input request one pause of a run asks under: the run, when it paused, what it asked, and the
    state it paused in, which holds the answers it was given before. A run that asks the same question again, after
    an answer, asks it under a new key, as the extension requires: a key is never used again once a response for it
    has been delivered."""
    held = json.dumps([row.get('frames'), row.get('assignment')], sort_keys=True, default=str)
    paused = f'{run_id}\0{row.get("updated") or row["created"]}\0{row.get("message") or ""}\0{held}'
    return 'question-' + hashlib.sha256(paused.encode('utf-8')).hexdigest()[:16]


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


def store(folder: Path) -> Store | None:
    """The workflow module's store for the folder's project, where its runs are, or None when there are none to
    read: no project, or the workflow module not on the folder's surface."""
    if not any(module.id == 'workflow' for module in surface(folder)):
        return None
    project = project_for(folder)
    return None if project is None else Store(project, module='workflow')


def _row(found: Store, run_id: str) -> dict[str, Any] | None:
    try:
        with found.tables(write=False) as tx:
            row = tx.get('runs', {'run_id': run_id})
    except (Stop, StoreError):
        return None
    return None if row is None else dict(row)


def of_run(run_id: str, row: dict[str, Any]) -> dict[str, Any]:
    """A workflow run as a task: its state through the vocabulary; a run that returned or failed with its authored
    error is a completed task whose result is the run's, since a run's named error is not a JSON-RPC fault; a run
    paused on the person asks its question as a form. A run record is kept as long as the project, so its task
    states no time limit."""
    state, message = str(row['state']), row.get('message')
    task = _base(run_id, str(row['created']), str(row.get('updated') or row.get('closed') or row['created']),
                 state, message, None)
    if state in ('completed', 'failed'):
        value = plain(row.get('result'))
        return {**task, 'status': 'completed', 'result': {
            'content': [{'type': 'text', 'text': json.dumps(value, ensure_ascii=False, indent=2)}],
            **({'structuredContent': value} if isinstance(value, dict) else {}), 'isError': state == 'failed'}}
    if state == 'input_required':
        question = str(message or '')
        return {**task, 'inputRequests': {_key(run_id, row): {'method': 'elicitation/create', 'params': {
            'mode': 'form', 'message': question, 'requestedSchema': {
                'type': 'object', 'required': [ANSWER],
                'properties': {ANSWER: {'type': 'string', 'title': 'Answer', 'description': question}}}}}}}
    return task


def seed_run(found: Store, run_id: str) -> dict[str, Any] | None:
    """The `CreateTaskResult` of a workflow run a verb has just made: its record is written, so `tasks/get` finds it."""
    row = _row(found, run_id)
    return None if row is None else {'resultType': 'task', **of_run(run_id, row)}


def detailed(project: str | None, found: Store | None, task_id: str) -> dict[str, Any] | None:
    """The task in full, for `tasks/get`: a tool call run as a task, or a workflow run by its id; None when there is
    no such task."""
    made = None if project is None else records.get(project, task_id)
    if made is not None:
        return _of_call(made)
    row = None if found is None else _row(found, task_id)
    return None if row is None or found is None else of_run(task_id, row)


# A module verb run for the person's request through the task: the module, the verb and its nouns.
Verb = Callable[[str, str, dict[str, Any]], Awaitable[Any]]


async def update(project: str | None, found: Store | None, task_id: str, responses: dict[str, Any],
                 verb: Verb) -> bool:
    """The person's answer to the question a paused workflow run asks, given through the workflow module's `answer`
    verb, which only the person runs: the answer comes from the form their AI tool showed them. Only the key of the
    pause outstanding now is read; a response to another key, or one declined, is ignored, as the extension asks.
    False when there is no such task."""
    if project is not None and await anyio.to_thread.run_sync(records.get, project, task_id) is not None:
        return True
    row = None if found is None else await anyio.to_thread.run_sync(_row, found, task_id)
    if row is None:
        return False
    if row['state'] != 'input_required':
        return True
    response: Any = responses.get(_key(task_id, row))
    if not isinstance(response, dict):
        return True
    answered = cast(dict[str, Any], response)
    content = cast(dict[str, Any], answered.get('content') or {})
    if answered.get('action') == 'accept' and isinstance(content.get(ANSWER), str):
        await verb('workflow', 'answer', {'run': task_id, 'answer': content[ANSWER]})
    return True


async def cancel(running: Running, project: str | None, found: Store | None, task_id: str, verb: Verb) -> bool:
    """Cancel a task: for a tool call the cancel is recorded and its work stopped, here at once or by the process
    running it at its next mark, and `run` ends the task as the work ends; a workflow run is cancelled through the
    workflow module's `cancel` verb. A task that has ended stays as it ended. False when there is none."""
    if project is not None and await anyio.to_thread.run_sync(records.get, project, task_id) is not None:
        asked = await anyio.to_thread.run_sync(records.request_cancel, project, task_id, CANCELLING)
        scope = running.scopes.get(task_id)
        if asked and scope is not None:
            scope.cancel()
        return True
    row = None if found is None else await anyio.to_thread.run_sync(_row, found, task_id)
    if row is None:
        return False
    if row['state'] in status.OPEN:
        await verb('workflow', 'cancel', {'run': task_id, 'reason': CANCELLED})
    return True
