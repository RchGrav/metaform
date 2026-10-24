"""Native ACP transport for assigned tasks, without tickets or authored-role ownership."""
from __future__ import annotations

import json
import time
from typing import Any, cast

from metaform.data import Store
from metaform.module import Context, Stop, context, provided


def assigned(ctx: Context, task_id: str) -> dict[str, Any] | None:
    for owner, service in provided(ctx.folder, 'task.lifecycle'):
        task_ctx = context(owner, ctx.folder, project=ctx.project, surface=ctx.surface)
        return service.assignment(task_ctx, task_id)
    return None


class TaskSessions:
    def start(self, ctx: Context, task: dict[str, Any]) -> dict[str, Any]:
        from . import agent_named, runnable, spawn
        called = context('dispatch', ctx.folder, project=ctx.project, surface=ctx.surface,
                         session=ctx.session, identity=ctx.identity, nouns={
                             'id': task['work_id'], 'task': task['task_id'], 'prep': True})
        agent = agent_named(str(task.get('agent') or called.setting('dispatch_agent')))
        runnable(called, agent)
        store = called.require_store()
        payload = {**task['payload'], 'task_id': task['task_id'], 'name': task['name'], 'cwd': task['cwd']}
        with Store(store.project_id, module='dispatch').tables() as tx:
            tx.insert('raised', {'work_id': task['work_id'], 'node': '', 'agent': agent,
                      'started': time.time(), 'seq': time.time_ns(), 'asked': json.dumps(payload)})
        try:
            started = spawn(store, task['work_id'], agent,
                            ['prep=true', f'task={task["task_id"]}', f'cwd={task["cwd"]}'],
                            'task', ctx=called)
        except Exception:
            with Store(store.project_id, module='dispatch').tables() as tx:
                tx.delete('raised', {'work_id': task['work_id']})
            raise
        return {'work_id': task['work_id'], 'agent': agent, 'pid': started['pid']}

    def _session(self, ctx: Context, task: dict[str, Any]) -> dict[str, Any] | None:
        from . import sessions
        rows = sessions(ctx.require_store(), str(task['work_id']), verify=False)
        return rows[-1] if rows else None

    def inspect(self, ctx: Context, task: dict[str, Any]) -> dict[str, Any]:
        from . import read_sessions, tell
        from .recovery import identity
        row = self._session(ctx, task)
        if row is None:
            locator = cast(dict[str, Any], task.get('locator') or {})
            pid: Any = locator.get('pid')
            if isinstance(pid, int) and identity(pid) == '':
                if task.get('cancel_requested'):
                    return {'state': 'cancelled', 'message': 'The assigned task was cancelled before startup.'}
                return {'state': 'completed', 'message': 'The assigned agent did not start.',
                        'result': {'content': [{'type': 'text', 'text': 'The assigned agent did not start.'}], 'isError': True}}
            return {'state': 'working', 'message': 'Starting the assigned agent.'}
        if task.get('cancel_requested') and row['state'] == 'running':
            self.cancel(ctx, task)
        called = context('dispatch', ctx.folder, project=ctx.project, nouns={'id': task['work_id'], 'thread': True})
        thread = read_sessions(called)
        states = cast(dict[str, Any], thread.get('states') or {})
        state_value: Any = states.get(row['session_id']) or {}
        state = cast(dict[str, Any], state_value) if isinstance(state_value, dict) else {}
        lines = [l for l in thread.get('lines', []) if l.get('session_id') == row['session_id']]
        messages = [str(l.get('text') or '') for l in lines if l.get('kind') == 'agent_message_chunk']
        turns = [int(l.get('seq') or 0) for l in lines if l.get('kind') == 'turn']
        observed = {'turn_seq': int(state.get('task_turns', max(turns, default=0))), 'last_message': messages[-1] if messages else ''}
        if row['state'] != 'running':
            outcome = state.get('task_outcome')
            if outcome == 'cancelled':
                return {**observed, 'state': 'cancelled', 'message': 'The assigned task was cancelled.'}
            failure = state.get('task_failure') or (None if outcome == 'completed' else
                       'The assigned agent ended without a recorded task completion.')
            return {**observed, 'state': 'completed', 'message': str(failure or 'The assigned task ended.'),
                    'result': {'content': [{'type': 'text', 'text': str(failure or '\n\n'.join(messages))}],
                               **({'isError': True} if failure else {})}}
        status = tell(row, 'status')
        if status.get('error') or not status:
            return {**observed, 'state': 'working', 'message': 'Waiting for the assigned agent to respond.'}
        inputs: dict[str, Any] = {}
        # Persisted native requests retain their UUID; normal Task polling never invents a new request key.
        pending: dict[tuple[str, str], dict[str, Any]] = {}
        for line in lines:
            if line.get('kind') in ('permission', 'elicitation'):
                data_value: Any = line.get('data')
                if not isinstance(data_value, dict):
                    try:
                        data_value = json.loads(str(line.get('text') or '{}'))
                    except ValueError:
                        continue
                data = cast(dict[str, Any], data_value)
                if data.get('request'):
                    pending[(str(line['kind']), str(data['request']))] = data
        for (kind, key), data in pending.items():
            if data.get('state') != 'waiting':
                continue
            if kind == 'permission':
                options = [str(o['option_id']) for o in data.get('options', [])]
                schema = {'type': 'object', 'properties': {'option': {'type': 'string', 'enum': options}},
                          'required': ['option']}
            else:
                schema_value: Any = data.get('requestedSchema') or data.get('schema') or data.get('fields')
                if not isinstance(schema_value, dict) or cast(dict[str, Any], schema_value).get('type') != 'object':
                    schema = {'type': 'object', 'properties': {'answer': {'type': 'string'}}, 'required': ['answer']}
                else:
                    schema = cast(dict[str, Any], schema_value)
            request_key = kind + ':' + key
            inputs[request_key] = {'request': {'method': 'elicitation/create', 'params': {
                'mode': 'form', 'message': str(data.get('message') or data.get('title') or 'The agent needs input.'),
                'requestedSchema': schema}}, 'route': {'kind': kind, 'request': key}}
        return {**observed, 'state': 'working', 'idle': status.get('activity') == 'idle', 'inputs': inputs,
                'message': 'The assigned agent needs input.' if inputs else
                           'The assigned agent is waiting for your next message.' if status.get('activity') == 'idle'
                           else 'The assigned agent is working.'}

    def respond(self, ctx: Context, task: dict[str, Any], key: str, message: dict[str, Any]) -> None:
        from . import tell
        row = self._session(ctx, task)
        if row is None or row['state'] != 'running':
            raise Stop('The assigned agent is not available for this response.', 'metaform tasks get <id>')
        answer = tell(row, 'task_input', key=key, route=message['route'], response=message['response'])
        if answer.get('error') or not answer.get('accepted'):
            raise Stop(str(answer.get('error') or 'The assigned agent did not accept the response.'),
                       'metaform tasks get <id>')

    def cancel(self, ctx: Context, task: dict[str, Any]) -> None:
        from . import tell
        row = self._session(ctx, task)
        if row is not None and row['state'] == 'running':
            answer = tell(row, 'stop')
            if answer.get('error'):
                raise Stop(str(answer['error']), 'metaform tasks get <id>')
        # A starting runner reads the durable cancellation request before opening its agent.

    def configure(self, ctx: Context, task: dict[str, Any], setting: str, value: str) -> dict[str, Any]:
        from . import tell
        row = self._session(ctx, task)
        if row is None or row['state'] != 'running':
            raise Stop('The assigned agent is not running.', 'metaform tasks get <id>')
        if not setting:
            return tell(row, 'status')
        return tell(row, 'configure', setting=setting, value=value)


SERVICE = TaskSessions()
