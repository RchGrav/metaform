"""Assigned tasks use native sessions without claiming tickets or calling models."""
import asyncio
import importlib
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from metaform.modules import dispatch
from metaform.modules.dispatch import task_sessions
from metaform.modules.dispatch.runner import Session

pytestmark = pytest.mark.kind('fixture')


@pytest.fixture(autouse=True)
def current_dispatch_modules(monkeypatch):
    """The module loader can replace packages between tests; patch the current import targets."""
    monkeypatch.setitem(globals(), 'dispatch', importlib.import_module('metaform.modules.dispatch'))
    monkeypatch.setitem(globals(), 'task_sessions', importlib.import_module('metaform.modules.dispatch.task_sessions'))
    monkeypatch.setitem(globals(), 'Session', importlib.import_module('metaform.modules.dispatch.runner').Session)


@pytest.fixture
def transport(monkeypatch, tmp_path):
    store = SimpleNamespace(project_id='project')
    ctx = SimpleNamespace(folder=tmp_path, project='project', surface='mcp', session='caller', identity={}, nouns={},
                          require_store=lambda: store, setting=lambda key: 'codex')
    monkeypatch.setattr(task_sessions, 'context', Mock(return_value=ctx))
    task = {'task_id': 'assigned-task', 'work_id': 'task:assigned-task', 'name': 'Investigate',
            'cwd': str(tmp_path / 'target with spaces'), 'payload': {'instructions': 'Exact\nwords.  '}}
    return task_sessions.TaskSessions(), ctx, task


def test_start_persists_exact_payload_and_spawns_ticketless_session(monkeypatch, transport):
    service, ctx, task = transport
    transaction = MagicMock()
    stored = MagicMock()
    stored.tables.return_value.__enter__.return_value = transaction
    monkeypatch.setattr(task_sessions, 'Store', Mock(return_value=stored))
    monkeypatch.setattr(dispatch, 'agent_named', lambda value: value)
    monkeypatch.setattr(dispatch, 'runnable', Mock())
    spawn = Mock(return_value={'pid': 123})
    monkeypatch.setattr(dispatch, 'spawn', spawn)

    result = service.start(ctx, task)

    args, kwargs = spawn.call_args
    assert args[1:3] == (task['work_id'], 'codex')
    assert args[3] == ['prep=true', 'task=assigned-task', f'cwd={task["cwd"]}']
    assert args[4] == 'task'
    assert kwargs == {'ctx': ctx, 'kept': False}
    table, row = transaction.insert.call_args.args
    assert table == 'raised' and row['node'] == ''
    assert json.loads(row['asked']) == {**task['payload'], 'task_id': task['task_id'],
                                        'name': task['name'], 'cwd': task['cwd']}
    assert result == {'work_id': task['work_id'], 'agent': 'codex', 'pid': 123}
    assert 'result' not in result and result.get('state') != 'completed'


def test_inspect_before_native_session_is_working(monkeypatch, transport):
    service, ctx, task = transport
    monkeypatch.setattr(service, '_session', lambda *args: None)
    assert service.inspect(ctx, task) == {'state': 'working', 'message': 'Starting the assigned agent.'}


@pytest.mark.parametrize('activity', ['working', 'idle', 'waiting'])
def test_native_requests_keep_keys_and_ignore_answered_requests(monkeypatch, transport, activity):
    service, ctx, task = transport
    row = {'session_id': 'native', 'state': 'running'}
    monkeypatch.setattr(service, '_session', lambda *args: row)
    tell = Mock(return_value={'state': 'running', 'activity': activity})
    monkeypatch.setattr(dispatch, 'tell', tell)
    lines = [
        {'kind': 'permission', 'data': {'request': 'permission-id', 'state': 'waiting', 'title': 'Run command?',
                                      'options': [{'option_id': 'allow', 'name': 'Allow'}]}},
        {'kind': 'elicitation', 'data': {'request': 'question-id', 'state': 'waiting', 'message': 'Which file?'}},
        {'kind': 'permission', 'data': {'request': 'old', 'state': 'answered'}},
        {'kind': 'agent_message_chunk', 'text': 'A result'}, {'kind': 'turn', 'seq': 23},
    ]
    monkeypatch.setattr(dispatch, 'read_sessions', lambda ctx: {
        'states': {}, 'lines': [{'session_id': 'native', **line} for line in lines]})

    first = service.inspect(ctx, task)
    second = service.inspect(ctx, task)

    assert first == second
    assert first['state'] == 'working' and first['idle'] == (activity == 'idle')
    assert first['turn_seq'] == 23 and first['last_message'] == 'A result'
    assert set(first['inputs']) == {'permission:permission-id', 'elicitation:question-id'}
    permission = first['inputs']['permission:permission-id']
    assert permission['route'] == {'kind': 'permission', 'request': 'permission-id'}
    assert permission['request']['params']['requestedSchema']['properties']['option']['enum'] == ['allow']
    tell.assert_called_with(row, 'status')


@pytest.mark.parametrize(('outcome', 'failure', 'expected', 'error'), [
    ('completed', None, 'completed', False), ('cancelled', None, 'cancelled', False),
    ('completed', 'Native failure', 'completed', True), (None, None, 'completed', True),
])
def test_terminal_outcomes_preserve_output_and_failure(monkeypatch, transport, outcome, failure, expected, error):
    service, ctx, task = transport
    monkeypatch.setattr(service, '_session', lambda *args: {'session_id': 'native', 'state': 'ended'})
    monkeypatch.setattr(dispatch, 'tell', Mock(side_effect=AssertionError('Ended sessions need no live transport')))
    monkeypatch.setattr(dispatch, 'read_sessions', lambda ctx: {
        'states': {'native': {'task_outcome': outcome, 'task_failure': failure}},
        'lines': [{'session_id': 'native', 'kind': 'agent_message_chunk', 'text': 'Final output'}]})

    observed = service.inspect(ctx, task)

    assert observed['state'] == expected
    if expected == 'completed':
        assert observed['result'].get('isError', False) is error
        if not error:
            assert observed['result']['content'] == [{'type': 'text', 'text': 'Final output'}]
        elif failure:
            assert observed['result']['content'][0]['text'] == failure


def test_configuration_and_input_use_native_control(monkeypatch, transport):
    service, ctx, task = transport
    row = {'session_id': 'native', 'state': 'running'}
    monkeypatch.setattr(service, '_session', lambda *args: row)
    tell = Mock(return_value={'accepted': True, 'settings': [{'id': 'mode'}]})
    monkeypatch.setattr(dispatch, 'tell', tell)
    assert service.configure(ctx, task, 'mode', 'plan')['settings'] == [{'id': 'mode'}]
    tell.assert_called_with(row, 'configure', setting='mode', value='plan')
    response = {'route': {'kind': 'permission', 'request': 'native-request'},
                'response': {'action': 'accept', 'content': {'option': 'allow'}}}
    service.respond(ctx, task, 'permission:native-request', response)
    tell.assert_called_with(row, 'task_input', key='permission:native-request', **response)


@pytest.mark.parametrize(('setting', 'choice', 'method', 'expected'), [
    ('mode', 'Plan', 'set_session_mode', {'mode_id': 'plan'}),
    ('model', 'Model B', 'set_config_option', {'config_id': 'model', 'value': 'model-b'}),
])
def test_runner_applies_advertised_native_settings(tmp_path, setting, choice, method, expected):
    ctx = SimpleNamespace(folder=tmp_path, nouns={'task': 'assigned-task'}, setting=Mock(side_effect=KeyError))
    session = Session(ctx, None, None, 'codex', [], prep=True, work_id='task:assigned-task')
    session.session_id = 'native'
    session.conn = SimpleNamespace(set_session_mode=AsyncMock(),
                                   set_config_option=AsyncMock(return_value=SimpleNamespace(config_options=None)))
    session.modes = {'current': 'code', 'available': [{'id': 'plan', 'name': 'Plan'}]}
    session.config = [{'id': 'model', 'name': 'Model', 'category': 'model', 'type': 'select',
                       'currentValue': 'model-a', 'options': [{'value': 'model-b', 'name': 'Model B'}]}]
    session.flush = AsyncMock()
    session.note = AsyncMock()
    session.save_state = AsyncMock()

    result = asyncio.run(session.configure(setting, choice))

    assert 'error' not in result
    getattr(session.conn, method).assert_awaited_once_with(session_id='native', **expected)
    assert result['value'] == ('plan' if setting == 'mode' else 'model-b')
    rejected = asyncio.run(session.configure(setting, 'unknown-choice'))
    assert 'error' in rejected
    assert getattr(session.conn, method).await_count == 1


@pytest.mark.parametrize('interactive', [True, False])
def test_runner_drained_turn_keeps_interactive_task_alive_without_helper_or_ticket(monkeypatch, tmp_path, interactive):
    ctx = SimpleNamespace(folder=tmp_path, nouns={'task': 'assigned-task', 'prep': True},
                          setting=Mock(side_effect=KeyError))
    session = Session(ctx, None, None, 'codex', [], folder=tmp_path / 'target', prep=True,
                      work_id='task:assigned-task')
    assert session.node is None
    assert session.role == '' and not session.system and not session.launched and not session.took
    assert session.acp['cwd'] == str(tmp_path / 'target')
    session.acp['task'] = {'interactive': interactive}
    session.turns = 1
    session.changed = AsyncMock()
    session.end = AsyncMock()
    session.helper_done = AsyncMock(side_effect=AssertionError('A task is not a helper'))
    monkeypatch.setattr('metaform.modules.dispatch.runner.ticket', Mock(side_effect=AssertionError('No ticket')))

    asyncio.run(session.prompted())

    assert session.idle.is_set() and session.turns == 0
    session.helper_done.assert_not_awaited()
    if interactive:
        session.end.assert_not_awaited()
        assert session.acp['task_outcome'] is None
    else:
        session.end.assert_awaited_once()
        assert session.acp['task_outcome'] == 'completed'


@pytest.mark.timeout(20)
def test_explicit_task_completes_through_real_fake_acp_session(run, project_folder, tmp_path, monkeypatch):
    from metaform.data import Store
    from metaform.modules.dispatch import end_group

    log = tmp_path / 'assigned-fake.jsonl'
    target = project_folder / 'target with spaces'
    target.mkdir()
    monkeypatch.setenv('FAKE_ACP_LOG', str(log))
    monkeypatch.setenv('FAKE_ACP_MODE', 'finite')
    run('enable', 'dispatch', cwd=project_folder)
    instruction = 'Return a concise result.\nPreserve these exact words:  a  b.'
    task_id = None
    runner_pid = None

    def entries():
        if not log.exists():
            return []
        data = log.read_bytes()
        return [json.loads(line) for line in data[:data.rfind(b'\n') + 1].decode().splitlines()]

    try:
        launched = json.loads(run('tasks', 'assign', f'text={instruction}', 'agent=claude',
                                  f'folder={target}', '--json', cwd=project_folder).stdout)
        task_id = launched['task_id']
        assert launched['state'] == 'starting' and launched['session_id'] is None
        with Store('proj', module='tasks').tables(write=False) as tx:
            assignment = dict(tx.get('assignments', {'task_id': task_id}))
        runner_pid = assignment['locator']['pid']
        assert assignment['payload']['instructions'] == instruction
        deadline = time.monotonic() + 12
        observed = None
        while time.monotonic() < deadline:
            observed = json.loads(run('tasks', 'get', task_id, '--json', cwd=project_folder).stdout)
            if observed['status'] in ('completed', 'cancelled', 'failed'):
                break
            time.sleep(0.05)
        assert observed and observed['status'] == 'completed', observed
        assert not observed['result'].get('isError'), observed
        assert observed['result']['content'] == [{'type': 'text', 'text': 'Hello from fake'}]
        messages = [entry['message'] for entry in entries() if 'message' in entry]
        assert any(message.get('method') == 'initialize' for message in messages)
        created = [message for message in messages if message.get('method') == 'session/new']
        assert len(created) == 1 and created[0]['params']['cwd'] == str(target)
        prompts = [message for message in messages if message.get('method') == 'session/prompt']
        assert len(prompts) == 1
        text = '\n'.join(block['text'] for block in prompts[0]['params']['prompt'] if block['type'] == 'text')
        assert text.endswith(instruction)
        assert all(not entry.get('role') for entry in entries())
        assert not Store('proj').work(limit=0).results
        with Store('proj', module='dispatch').tables(write=False) as tx:
            sessions = [dict(row) for row in tx.rows('agent_sessions', limit=0).results]
            states = [json.loads(row['text']) for row in tx.rows('session_lines', {'kind': 'state'}, limit=0).results]
        assert len(sessions) == 1 and sessions[0]['work_id'] == launched['work_id']
        assert sessions[0]['state'] == 'ended'
        assert len(states) == 1 and states[0]['task_outcome'] == 'completed'
        assert not states[0].get('role') and not states[0].get('authored_role_uri')
        assert not states[0].get('assignment_id') and not states[0].get('team_id')
    finally:
        if task_id is not None:
            run('tasks', 'cancel', task_id, '--json', cwd=project_folder, ok=False)
        if runner_pid is not None:
            end_group(runner_pid)
        for entry in entries():
            if 'pid' in entry:
                end_group(entry['pid'])


@pytest.mark.timeout(20)
def test_system_runs_canonical_user_task_and_deduplicates_input(run, project_folder, tmp_path, monkeypatch):
    from metaform.data import Store
    from metaform.modules.dispatch import end_group

    log = tmp_path / 'user-agent-fake.jsonl'
    monkeypatch.setenv('FAKE_ACP_LOG', str(log))
    monkeypatch.setenv('FAKE_ACP_MODE', 'finite')
    run('enable', 'dispatch', cwd=project_folder)
    canonical = json.loads(run('tasks', 'read', 'user_agent', '--json', cwd=project_folder).stdout)['instructions']
    task_id = None
    runner_pid = None

    def entries():
        if not log.exists():
            return []
        data = log.read_bytes()
        return [json.loads(line) for line in data[:data.rfind(b'\n') + 1].decode().splitlines()]

    def read_until(predicate):
        deadline = time.monotonic() + 10
        observed = None
        while time.monotonic() < deadline:
            observed = json.loads(run('tasks', 'get', task_id, '--json', cwd=project_folder).stdout)
            if predicate(observed):
                return observed
            time.sleep(0.05)
        raise AssertionError(f'Task did not reach expected state: {observed}')

    try:
        launch = json.loads(run('dispatch', 'system', 'agent=claude', '--json', cwd=project_folder).stdout)
        task_id = launch['task_id']
        with Store('proj', module='tasks').tables(write=False) as tx:
            task = dict(tx.get('assignments', {'task_id': task_id}))
        runner_pid = task['locator']['pid']
        assert task['name'] == 'user_agent' and task['payload']['instructions'] == canonical
        first = read_until(lambda state: state['status'] == 'input_required')
        key, = first['inputRequests']
        assert key.startswith('message:')
        response = {key: {'action': 'accept', 'content': {'message': 'Follow-up with  exact spacing.'}}}
        for _ in range(2):
            run('tasks', 'update', task_id, f'responses={json.dumps(response)}', '--json', cwd=project_folder)
        second = read_until(lambda state: state['status'] == 'input_required' and
                            set(state['inputRequests']) != {key})
        assert len(second['inputRequests']) == 1
        messages = [entry['message'] for entry in entries() if 'message' in entry]
        created, = [message for message in messages if message.get('method') == 'session/new']
        assert created['params']['cwd'] == str(project_folder)
        env = {item['name']: item['value'] for server in created['params']['mcpServers'] for item in server['env']}
        assert env['METAFORM_TASK'] == task_id and not env.get('METAFORM_ROLE')
        prompts = [message for message in messages if message.get('method') == 'session/prompt']
        assert len(prompts) == 2
        first_text = '\n'.join(block['text'] for block in prompts[0]['params']['prompt'] if block['type'] == 'text')
        assert canonical in first_text
        assert prompts[1]['params']['prompt'] == [{'type': 'text', 'text': 'Follow-up with  exact spacing.'}]
        assert all(not entry.get('role') for entry in entries())
        with Store('proj', module='dispatch').tables(write=False) as tx:
            states = [json.loads(row['text']) for row in tx.rows('session_lines', {'kind': 'state'}, limit=0).results]
        assert states[0]['task_inputs'].count(key) == 1
        assert not Store('proj').work(limit=0).results
        run('tasks', 'cancel', task_id, '--json', cwd=project_folder)
        cancelled = read_until(lambda state: state['status'] in ('cancelled', 'completed', 'failed'))
        assert cancelled['status'] == 'cancelled'
        assert json.loads(run('tasks', 'get', task_id, '--json', cwd=project_folder).stdout) == cancelled
    finally:
        if task_id is not None:
            run('tasks', 'cancel', task_id, '--json', cwd=project_folder, ok=False)
        if runner_pid is not None:
            end_group(runner_pid)
        for entry in entries():
            if 'pid' in entry:
                end_group(entry['pid'])
