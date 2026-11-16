"""Native ACP transport for assigned tasks, without tickets or authored-role ownership."""
from __future__ import annotations

import json
import time
from typing import Any, cast

from metaform import home
from metaform.data import Store
from metaform.module import Context, Stop, context, provided


def assigned(ctx: Context, task_id: str) -> dict[str, Any] | None:
    for owner, service in provided(ctx.folder, 'task.lifecycle'):
        task_ctx = context(owner, ctx.folder, project=ctx.project, surface=ctx.surface)
        return service.assignment(task_ctx, task_id)
    return None


class TaskSessions:
    def start(self, ctx: Context, task: dict[str, Any]) -> dict[str, Any]:
        from . import agent_named, launches, runnable
        existing = self._session(ctx, task)
        if existing is not None:
            return {'work_id': task['work_id'], 'agent': existing['agent'], 'session_id': existing['session_id']}
        for entry in launches():
            if entry.get('project') == ctx.project and entry.get('work_id') == task['work_id']:
                return {'work_id': task['work_id'], 'agent': entry['agent'], 'pid': entry['pid']}
        called = context('dispatch', ctx.folder, project=ctx.project, surface=ctx.surface,
                         session=ctx.session, identity=ctx.identity, nouns={
                             'id': task['work_id'], 'task': task['task_id'], 'prep': True})
        agent = agent_named(str(task.get('agent') or called.setting('dispatch_agent')))
        runnable(called, agent)
        if task['name'] == 'intake':
            return self._intake(ctx, called, task, agent)
        return self._start(ctx, called, task, agent)

    def _intake(self, ctx: Context, called: Context, task: dict[str, Any], agent: str) -> dict[str, Any]:

        from . import intake_folder, intake_map_choice, refuse_second_intake
        store = called.require_store()
        raw: Any = task['payload'].get('intake')
        selection = cast(dict[str, Any], raw) if isinstance(raw, dict) else {}
        choosing = context('dispatch', ctx.folder, project=ctx.project, surface=ctx.surface,
                           nouns={key: selection[key] for key in ('map', 'name') if key in selection})
        chosen = intake_map_choice(choosing)
        with home.file_lock(intake_folder(store) / 'intake.lock'):
            refuse_second_intake(store)
            building = store.intake_building().results
            if building and building[0].recording:
                held = building[0]
                raise Stop(f'An agent is recording the intake in layer {held.layer.name} of metaform {held.base} now; '
                           'two agents would interleave their records in it.', 'metaform intake status')
            if building and not selection.get('resume'):
                held = building[0]
                raise Stop(f'An intake was left unfinished in layer {held.layer.name} of metaform {held.base}, with '
                           f'{held.parts} parts; resume that intake with resume=true.',
                           'metaform dispatch intake resume=true')
            # refine when the project store already holds this project's map and the person chose to extend it
            from metaform import project as project_store
            has_map = project_store.holds(project_store.stored_name(store.project_id))
            mode = 'resume' if building else 'refine' if chosen.get('map') == 'extend' and has_map else 'fresh'
            metadata = {**chosen, 'mode': mode}
            task['payload']['intake'] = metadata
            asked = str(task['payload'].get('input') or '')
            # The first turn is the intake exactly as `intake prompt` serves it: the procedure with the selected mode
            # and what the person asked in the place the procedure itself gives a request, and nothing after it.
            from metaform.module import surface
            serving = next(verb for module in surface(called.folder) if module.id == 'intake'
                           for verb in module.verbs if verb.name == 'prompt')
            task['payload']['instructions'] = str(serving.run(context(
                'intake', called.folder, project=called.project, nouns={'mode': mode, **({'text': asked} if asked else {})})))
            task['payload']['input'] = ''
            noted = {'work': task['work_id'], 'agent': agent, 'since': home.now(), **metadata}
            store.note_intake_launch(noted)
            try:
                started = self._start(ctx, called, task, agent)
            except Exception:
                store.forget_intake_launch(str(task['work_id']))
                raise
            store.note_intake_launch({**noted, 'pid': started['pid']})
            return started

    def _start(self, ctx: Context, called: Context, task: dict[str, Any], agent: str) -> dict[str, Any]:
        from . import spawn
        store = called.require_store()
        payload = {**task['payload'], 'task_id': task['task_id'], 'name': task['name'], 'cwd': task['cwd']}
        with Store(store.project_id, module='dispatch').tables() as tx:
            raised = {'node': '', 'agent': agent, 'started': time.time(), 'seq': time.time_ns(),
                      'asked': json.dumps(payload)}
            if tx.get('raised', {'work_id': task['work_id']}) is None:
                tx.insert('raised', {'work_id': task['work_id'], **raised})
            else:  # a task started again, its ended context renewed: the new runner reads this payload
                tx.update('raised', {'work_id': task['work_id']}, raised)
        try:
            requested_at = cast(dict[str, Any], task['payload'].get('options') or {}).get('requested_at')
            asked = requested_at if isinstance(requested_at, int) and not isinstance(requested_at, bool) else None
            started = spawn(store, task['work_id'], agent,
                            ['prep=true', f'task={task["task_id"]}', f'cwd={task["cwd"]}'],
                            'task', kept=bool(ctx.nouns.get('wait')), ctx=called, subject=f'task:{task["task_id"]}',
                            asked=asked)
        except Exception:
            with Store(store.project_id, module='dispatch').tables() as tx:
                tx.delete('raised', {'work_id': task['work_id']})
            raise
        return {'work_id': task['work_id'], 'agent': agent, 'pid': started['pid']}

    def _session(self, ctx: Context, task: dict[str, Any]) -> dict[str, Any] | None:
        from . import sessions
        rows = sessions(ctx.require_store(), str(task['work_id']), verify=False)
        return rows[-1] if rows else None

    def resume(self, ctx: Context, task: dict[str, Any]) -> dict[str, Any]:
        """The task's ended context called back: its last session resumed in place as the same task agent, with its own
        memory, where its agent offers resume or load, or else a new session of the same agent reading the ended
        thread, `renew`; a running one is the answer as it is. A task that never had a session starts."""
        from . import agent_named, resumed_session, runnable
        row = self._session(ctx, task)
        called = context('dispatch', ctx.folder, project=ctx.project, surface=ctx.surface,
                         session=ctx.session, identity=ctx.identity, nouns={'id': task['work_id']})
        if row is None:
            agent = agent_named(str(cast(dict[str, Any], task.get('locator') or {}).get('agent') or task.get('agent')
                                    or called.setting('dispatch_agent')))
            runnable(called, agent)
            return self._start(ctx, called, task, agent)  # it never ran: its first session, no thread to read
        if row['state'] == 'running':
            return {key: row[key] for key in ('work_id', 'agent', 'session_id', 'state')}
        return resumed_session(called, called.require_store(), row, f'thread:{row["session_id"]}')

    def renew(self, ctx: Context, task_id: str, session_id: str, agent: str) -> dict[str, Any]:
        """A new session of the task's agent where the ended one cannot be resumed: the same assignment started again,
        its opening input the thread it continues, so it comes back onto the board as that task's agent and takes the
        messages queued for it. The assignment comes out of its terminal state first, so the runner starts."""
        from . import prompt
        task = None
        for owner, service in provided(ctx.folder, 'task.lifecycle'):
            task_ctx = context(owner, ctx.folder, project=ctx.project, surface=ctx.surface)
            task = service.called_back(task_ctx, task_id)
            break
        if task is None:
            raise Stop(f'No assigned task {task_id}.', 'metaform tasks get <id>')
        called = context('dispatch', ctx.folder, project=ctx.project, surface=ctx.surface,
                         session=ctx.session, identity=ctx.identity, nouns={
                             'id': task['work_id'], 'task': task_id, 'prep': True})
        task['payload'] = {**task['payload'], 'input': prompt('new_context', work=str(task['work_id']),
                                                              session=session_id)}
        return self._start(ctx, called, task, agent)

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
        called = context('dispatch', ctx.folder, project=ctx.project, nouns={'id': task['work_id'], 'thread': True})
        thread = read_sessions(called)
        states = cast(dict[str, Any], thread.get('states') or {})
        state_value: Any = states.get(row['session_id']) or {}
        state = cast(dict[str, Any], state_value) if isinstance(state_value, dict) else {}
        lines = [l for l in thread.get('lines', []) if l.get('session_id') == row['session_id']]
        messages = [str(l.get('text') or '') for l in lines if l.get('kind') == 'agent_message_chunk']
        turns = [int(l.get('seq') or 0) for l in lines if l.get('kind') == 'turn']
        observed = {'name': state.get('name'), 'context': state.get('usage'), 'session_id': row['session_id'],
                    'turn_seq': int(state.get('task_turns', max(turns, default=0))), 'last_message': messages[-1] if messages else ''}
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

    def wake(self, ctx: Context, task: dict[str, Any], key: str, text: str) -> None:
        from . import tell
        row = self._session(ctx, task)
        if row is None or row['state'] != 'running':
            raise Stop('The assigned agent is not ready for the message yet.', 'metaform tasks get <id>')
        answer = tell(row, 'task_wake', key=key, text=text)
        if not answer.get('accepted'):
            raise Stop(str(answer.get('error') or 'The message was not accepted.'), 'metaform tasks get <id>')

    def finish(self, ctx: Context, task: dict[str, Any], reason: str) -> None:
        from . import tell
        row = self._session(ctx, task)
        if row is not None and row['state'] == 'running':
            answer = tell(row, 'task_end', reason=reason)
            if not answer.get('accepted'):
                raise Stop(str(answer.get('error') or 'The agent did not accept completion.'), 'metaform tasks get <id>')

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
