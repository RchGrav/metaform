"""Durable assigned-agent tasks; instruction and lifecycle policy do not depend on roles."""
from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from metaform import home, prompt_files, skills
from metaform.data import Column, Index, Store, Table, Tables
from metaform.module import Context, Stop, context, provided

TERMINAL = frozenset({'completed', 'failed', 'cancelled'})
# Version 2 adds the name index for default User Agent reuse; assignment rows remain compatible.
TABLES = Tables(version=2, compatible_from=1, tables=(
    Table('assignments', place='project', key=('task_id',), columns=(
        Column('task_id', required=True), Column('name', required=True), Column('state', required=True),
        Column('created', required=True), Column('updated', required=True), Column('work_id', required=True),
        Column('cwd', required=True), Column('agent'), Column('payload', 'json', required=True),
        Column('locator', 'json'), Column('flow', 'json', required=True), Column('result', 'json'),
        Column('error', 'json'), Column('message'), Column('cancel_requested', 'bool', required=True)),
        indexes=(Index(('work_id',)), Index(('name',)))),
))


def now() -> str:
    return datetime.now(UTC).isoformat()


def target(ctx: Context, task_id: str) -> Context:
    try:
        token, encoded = task_id.split('.', 1)
        uuid.UUID(hex=token)
        project = base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)).decode()
    except (ValueError, UnicodeError):
        return ctx
    found = home.project(project)
    return context('tasks', Path(found.path), project=project, surface=ctx.surface,
                   session=ctx.session, identity=ctx.identity) if found else ctx


def own(ctx: Context) -> Store:
    return Store(ctx.require_store().project_id, module='tasks')


def transport(ctx: Context) -> Any:
    found = provided(ctx.folder, 'task.transport')
    if not found:
        raise Stop('No enabled transport can run assigned tasks.', 'enable the dispatch module')
    return found[0][1]


def tool_result(text: str, *, error: bool = False) -> dict[str, Any]:
    return {'content': [{'type': 'text', 'text': text}], **({'isError': True} if error else {})}


def wire(row: dict[str, Any]) -> dict[str, Any]:
    result = {'taskId': row['task_id'], 'status': row['state'], 'createdAt': row['created'],
              'lastUpdatedAt': row['updated'], 'ttlMs': None, 'pollIntervalMs': 1000}
    if row.get('message'):
        result['statusMessage'] = row['message']
    if row['state'] == 'input_required':
        result['inputRequests'] = row['flow']['requests']
    elif row['state'] == 'completed':
        result['result'] = row['result']
    elif row['state'] == 'failed':
        result['error'] = row['error']
    return result


def selected_skill(ctx: Context, selected: str) -> dict[str, Any]:
    """Load the selected document only. Supporting files remain addressable through their resource URIs."""
    from . import expertise
    if not selected.startswith('skill://'):
        return {key: value for key, value in expertise.read(ctx, selected, ctx.nouns.get('node')).items()
                if key != 'files'}
    bundle: dict[str, Any] | None = None
    try:
        bundle = skills.reusable(selected)
    except ValueError:
        pass
    if bundle is None and selected.startswith('skill://metaform/'):
        bundle = next((skills.native_document(one) for one in skills.catalog()
                       if selected == f'skill://metaform/{one.name}/SKILL.md'), None)
    if bundle is None and selected.startswith('skill://expertise/'):
        return {key: value for key, value in expertise.read(ctx, selected, ctx.nouns.get('node')).items()
                if key != 'files'}
    if bundle is None:
        raise Stop(f'No reusable skill {selected}.', 'discover skills with skills/list or give an expertise node')
    text = cast(dict[str, bytes], bundle['files'])['SKILL.md'].decode('utf-8')
    component = prompt_files.component(selected, text)
    component.update(origin='resource', source={'kind': 'resource', 'uri': selected})
    return {key: bundle[key] for key in ('uri', 'frontmatter', 'resources')} | {
        'name': bundle['frontmatter']['name'], 'text': text, 'component': component}


class Lifecycle:
    def assign(self, ctx: Context, name: str, component: dict[str, Any] | None) -> dict[str, Any]:
        given = str(ctx.nouns.get('text') or '')
        if component is None and not given.strip():
            raise Stop('Give a task definition or an explicit assignment.', 'metaform tasks list')
        folder = Path(str(ctx.nouns.get('folder') or ctx.folder)).expanduser().resolve()
        if not folder.is_dir():
            raise Stop(f'No working directory {folder}.', 'give an existing folder')
        selected: Any = ctx.nouns.get('skills') or []
        if not isinstance(selected, list) or any(not isinstance(s, str) for s in cast(list[Any], selected)):
            raise Stop('skills is a list of skill names.', 'metaform tasks list')
        loaded = [selected_skill(ctx, s) for s in cast(list[str], selected)]
        ident = uuid.uuid4().hex
        project = ctx.require_store().project_id
        task_id = ident + '.' + base64.urlsafe_b64encode(project.encode()).decode().rstrip('=')
        stamp = now()
        row: dict[str, Any] = {'task_id': task_id, 'name': name or 'assigned_task', 'state': 'working',
               'created': stamp, 'updated': stamp, 'work_id': 'task-' + ident, 'cwd': str(folder),
               'agent': ctx.nouns.get('agent'),
               'payload': {'instructions': component['text'] if component else given,
                           'component': component, 'input': given if component else '',
                           'skills': loaded, 'interactive': name == 'user_agent', 'persistent': name == 'worker',
                           'node': ctx.nouns.get('node'), 'agent_name': ctx.nouns.get('agent_name'),
                           'options': ctx.nouns.get('options') or {}},
               'locator': None, 'flow': {'epoch': 0, 'requests': {}, 'routes': {}, 'answered': [],
                                        'pending': {}, 'wait_after': None, 'last_turn': 0},
               'result': None, 'error': None, 'message': 'Starting the assigned agent.', 'cancel_requested': False}
        if name == 'intake' and isinstance(ctx.nouns.get('intake'), dict):
            row['payload']['intake'] = dict(ctx.nouns['intake'])
        with own(ctx).tables() as tx:
            tx.insert('assignments', row)
            tx.concern(work_id=row['work_id'], kind='task')
        if name == 'worker':
            from .board import Board
            Board(project).register(task_id, str(ctx.nouns.get('agent_name') or 'worker-' + ident[:8]), row['work_id'])
        locator: dict[str, Any] = {}
        launch_state = 'starting'
        try:
            locator = transport(ctx).start(ctx, row)
        except Exception as error:  # noqa: BLE001  a tool failure is a completed task with an error result
            launch_state = 'completed'
            if name == 'worker':
                from .board import Board
                Board(project).remove(task_id)
            with own(ctx).tables() as tx:
                tx.update('assignments', {'task_id': task_id}, {'state': 'completed', 'updated': now(),
                          'result': tool_result(str(error), error=True), 'message': str(error)})
        else:
            with own(ctx).tables() as tx:
                tx.update('assignments', {'task_id': task_id}, {'locator': locator, 'payload': row['payload'],
                                                             'updated': now()})
        return {'task_id': task_id, 'project_id': project, 'work_id': row['work_id'],
                'state': launch_state, 'agent': (locator.get('agent') or row['agent']),
                'session_id': None}

    def user_agent(self, ctx: Context, *, fresh: bool = False) -> dict[str, Any]:
        with own(ctx).tables(write=False) as tx:
            rows = [dict(r) for r in tx.rows('assignments', {'name': 'user_agent'}, limit=0).results]
        for row in sorted(rows, key=lambda r: r['created'], reverse=True):
            state = self.get(ctx, row['task_id'])
            if state and state['status'] not in TERMINAL:
                if fresh:
                    self.cancel(ctx, row['task_id'])
                    continue
                return {'task_id': row['task_id'], 'project_id': ctx.project, 'work_id': row['work_id'],
                        'agent': cast(dict[str, Any], row.get('locator') or {}).get('agent'), 'state': 'running', 'session_id': None}
        from . import definition
        reading = context('tasks', ctx.folder, project=ctx.project, surface=ctx.surface,
                          session=ctx.session, identity=ctx.identity, nouns={'name': 'user_agent'})
        component = definition(reading)['component']
        return self.assign(ctx, 'user_agent', component)

    def assignment(self, ctx: Context, task_id: str) -> dict[str, Any] | None:
        return self._read(target(ctx, task_id), task_id)

    def _read(self, ctx: Context, task_id: str) -> dict[str, Any] | None:
        if ctx.store is None:
            return None
        with own(ctx).tables(write=False) as tx:
            row = tx.get('assignments', {'task_id': task_id})
        return dict(row) if row else None

    def _deliver(self, ctx: Context, row: dict[str, Any]) -> None:
        for key, message in list(row['flow']['pending'].items()):
            transport(ctx).respond(ctx, row, key, message)
            with own(ctx).tables() as tx:
                current = tx.get('assignments', {'task_id': row['task_id']})
                if current is None:
                    return
                flow: dict[str, Any] = dict(current['flow'])
                flow['pending'] = {k: v for k, v in flow['pending'].items() if k != key}
                tx.update('assignments', {'task_id': row['task_id']}, {'flow': flow, 'updated': now()})

    def get(self, ctx: Context, task_id: str) -> dict[str, Any] | None:
        ctx = target(ctx, task_id)
        row = self._read(ctx, task_id)
        if row is None:
            return None
        if row['state'] in TERMINAL or row['locator'] is None:
            return wire(row)
        try:
            self._deliver(ctx, row)
            observed = transport(ctx).inspect(ctx, row)
        except (OSError, Stop):
            return wire(row)  # input remains durably queued for a later request
        with own(ctx).tables() as tx:
            current = tx.get('assignments', {'task_id': task_id})
            if current is None:
                return None
            if current['state'] in TERMINAL:
                return wire(dict(current))
            flow: dict[str, Any] = dict(current['flow'])
            flow['last_turn'] = int(observed.get('turn_seq') or 0)
            requests: dict[str, Any] = {}
            routes: dict[str, Any] = {}
            inputs = cast(dict[str, Any], observed.get('inputs') or {})
            for key, item in inputs.items():
                if key not in flow['answered']:
                    requests[key], routes[key] = item['request'], item['route']
            state = str(observed['state'])
            if state not in TERMINAL and row['payload'].get('interactive') and observed.get('idle') and not requests:
                waiting = flow.get('wait_after')
                if waiting is None or flow['last_turn'] > waiting:
                    key = f'message:{task_id}:{flow["epoch"]}'
                    requests[key] = {'method': 'elicitation/create', 'params': {
                        'mode': 'form', 'message': str(observed.get('last_message') or '') +
                        '\nSend your next message, or decline to end this task.',
                        'requestedSchema': {'type': 'object', 'properties': {'message': {'type': 'string'}},
                                            'required': ['message']}}}
                    routes[key] = {'kind': 'message'}
            if state not in TERMINAL:
                state = 'input_required' if requests else 'working'
            flow.update(requests=requests if state == 'input_required' else {}, routes=routes)
            changes: dict[str, Any] = {'state': state, 'flow': flow, 'message': observed.get('message')}
            if state == 'completed':
                changes['result'] = observed.get('result') or tool_result(str(observed.get('last_message') or ''))
            elif state == 'failed':
                changes['error'] = observed['error']
            if any(current.get(k) != v for k, v in changes.items()):
                tx.update('assignments', {'task_id': task_id}, {**changes, 'updated': now()})
                tx.concern(work_id=current['work_id'], kind='task')
            updated = tx.get('assignments', {'task_id': task_id})
            if updated is None:
                return None
            answer = wire(dict(updated))
        if row['name'] == 'worker':
            from . import protocol
            protocol.reconcile(ctx, row, observed)
        return answer

    def seed(self, ctx: Context, task_id: str) -> dict[str, Any] | None:
        task = self.get(ctx, task_id)
        return None if task is None else {'resultType': 'task', **task}

    def update(self, ctx: Context, task_id: str, responses: dict[str, Any]) -> bool:
        ctx = target(ctx, task_id)
        if self.get(ctx, task_id) is None:
            return False
        with own(ctx).tables() as tx:
            row = tx.get('assignments', {'task_id': task_id})
            if row is None:
                return False
            if row['state'] in TERMINAL:
                return True
            flow: dict[str, Any] = dict(row['flow'])
            accepted = False
            for key, response in responses.items():
                if key not in flow['requests'] or not isinstance(response, dict):
                    continue
                route = flow['routes'][key]
                flow['pending'][key] = {'route': route, 'response': response}
                flow['answered'].append(key)
                del flow['requests'][key]
                flow['routes'].pop(key, None)
                flow['epoch'] += 1
                if route['kind'] == 'message':
                    flow['wait_after'] = flow['last_turn']
                accepted = True
            if accepted:
                tx.update('assignments', {'task_id': task_id}, {'flow': flow, 'updated': now(),
                          'state': 'input_required' if flow['requests'] else 'working'})
                tx.concern(work_id=row['work_id'], kind='task')
        row = self._read(ctx, task_id)
        if row and row['state'] not in TERMINAL:
            self._deliver(ctx, row)
        return True

    def cancel(self, ctx: Context, task_id: str) -> bool:
        ctx = target(ctx, task_id)
        row = self._read(ctx, task_id)
        if row is None:
            return False
        if row['state'] in TERMINAL:
            return True
        with own(ctx).tables() as tx:
            tx.update('assignments', {'task_id': task_id}, {'cancel_requested': True, 'updated': now()})
        transport(ctx).cancel(ctx, row)
        self.get(ctx, task_id)
        return True

    def configure(self, ctx: Context, task_id: str, setting: str, value: str) -> dict[str, Any]:
        ctx = target(ctx, task_id)
        row = self._read(ctx, task_id)
        if row is None:
            raise Stop(f'No assigned task {task_id}.', 'metaform tasks get <id>')
        return cast(dict[str, Any], transport(ctx).configure(ctx, row, setting, value))

    def changed(self, ctx: Context, payload: dict[str, Any]) -> None:
        # Native session events drive progress. Task writes never trigger another session scan.
        tables = payload.get('tables')
        if payload.get('project') != ctx.project:
            return
        if tables != 'dispatch' and not (isinstance(tables, list) and any(
                str(t).startswith('dispatch.') for t in cast(list[Any], tables))):
            return
        kinds = payload.get('kinds')
        if isinstance(kinds, list) and not {'session', 'worker-idle'} & set(cast(list[str], kinds)):
            return
        work_ids = cast(list[str], payload.get('work_ids') or [])
        if not work_ids:
            return
        found: list[dict[str, Any]] = []
        with own(ctx).tables(write=False) as tx:
            for work_id in work_ids:
                found.extend(dict(r) for r in tx.rows('assignments', {'work_id': work_id}, limit=0).results)
        for row in found:
            if row['state'] not in TERMINAL:
                self.get(ctx, str(row['task_id']))


SERVICE = Lifecycle()
