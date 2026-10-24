"""Assigned-task lifecycle with real isolated stores and a deterministic in-process transport."""
from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

from metaform.module import Stop, context
from metaform.modules import tasks
from metaform.modules.tasks import runtime

pytestmark = pytest.mark.kind('fixture')


class Transport:
    def __init__(self):
        self.started = []
        self.responses = []
        self.cancelled = []
        self.observed = {'state': 'working', 'turn_seq': 1, 'idle': False, 'inputs': {}}
        self.before_start = None
        self.start_error = None

    def start(self, ctx, row):
        if self.before_start:
            self.before_start(ctx, row)
        self.started.append(deepcopy(row))
        if self.start_error:
            raise self.start_error
        return {'session_id': 'dedicated-test-session'}

    def inspect(self, ctx, row):
        return deepcopy(self.observed)

    def respond(self, ctx, row, key, message):
        self.responses.append((key, deepcopy(message)))

    def cancel(self, ctx, row):
        self.cancelled.append(row['task_id'])


@pytest.fixture
def assigned(project_folder, monkeypatch):
    adapter = Transport()
    monkeypatch.setattr(runtime, 'transport', lambda ctx: adapter)
    ctx = context('tasks', project_folder, nouns={'text': 'Inspect the supplied example.'})
    return ctx, runtime.Lifecycle(), adapter


def create(assigned):
    ctx, lifecycle, _ = assigned
    task_id = lifecycle.assign(ctx, '', None)['task_id']
    return ctx, lifecycle, task_id


def test_user_agent_preserves_canonical_source_and_binds_only_project(project_folder):
    canonical = (tasks.PACKAGE / 'resources' / 'user_agent.txt').read_text(encoding='utf-8')
    assert hashlib.sha256(canonical.encode()).hexdigest() == \
        '52af5044e666182d2cb3a2f4aea6ee0e202cf851d56e40a5bd662fccf67a927e'
    ctx = context('tasks', project_folder, nouns={'name': 'user_agent', 'project_name': 'Example & <Project>'})
    definition = tasks.definition(ctx)
    expected = canonical.replace('{project}', 'Example & <Project>')
    assert definition['instructions'] == expected
    assert definition['component']['text'] == expected
    assert definition['component']['bindings'] == {'{project}': 'Example & <Project>'}
    assert definition['component']['rendered_fingerprint'] == hashlib.sha256(expected.encode()).hexdigest()
    assert definition['component']['source']['shipped_identity'] == hashlib.sha256(canonical.encode()).hexdigest()


def test_assignment_is_durable_before_transport_start_without_role_or_ticket(assigned, monkeypatch):
    ctx, lifecycle, adapter = assigned
    monkeypatch.setattr(runtime.skills, 'served', lambda name: pytest.fail('No skill was selected.'))

    def durable(start_ctx, row):
        persisted = runtime.Lifecycle().assignment(start_ctx, row['task_id'])
        assert persisted == row
        assert persisted['state'] == 'working'
        assert persisted['locator'] is None
        assert persisted['payload']['instructions'] == ctx.nouns['text']
        assert 'role' not in persisted['payload']
        assert 'ticket' not in persisted['payload']
        assert start_ctx.require_store().active_base() is None

    adapter.before_start = durable
    created = lifecycle.assign(ctx, '', None)
    row = lifecycle.assignment(ctx, created['task_id'])
    assert row['locator'] == {'session_id': 'dedicated-test-session'}
    assert row['payload']['skills'] == []
    assert row['payload']['interactive'] is False
    assert len(adapter.started) == 1


def test_named_task_retains_exact_component_and_assignment_input(assigned):
    ctx, lifecycle, adapter = assigned
    ctx.nouns.update(name='user_agent', project_name='Bound Project', text='Focus on the current question.')
    created = tasks.assign(ctx)
    payload = lifecycle.assignment(ctx, created['task_id'])['payload']
    assert payload['instructions'] == tasks.definition(ctx)['instructions']
    assert payload['component'] == tasks.definition(ctx)['component']
    assert payload['input'] == 'Focus on the current question.'
    assert payload['interactive'] is True
    assert adapter.started[0]['payload'] == payload


def test_only_explicitly_selected_skills_are_loaded(assigned, monkeypatch):
    ctx, lifecycle, adapter = assigned
    loaded = []

    def served(name):
        loaded.append(name)
        return f'Exact instructions for {name}.'

    monkeypatch.setattr(runtime.skills, 'served', served)
    ctx.nouns['skills'] = ['review', 'research']
    created = lifecycle.assign(ctx, '', None)
    assert loaded == ['review', 'research']
    expected = [{'name': name, 'text': f'Exact instructions for {name}.'} for name in loaded]
    assert lifecycle.assignment(ctx, created['task_id'])['payload']['skills'] == expected
    assert adapter.started[0]['payload']['skills'] == expected


def test_input_requests_accept_once_and_ignore_unknown_keys(assigned):
    ctx, lifecycle, task_id = create(assigned)
    adapter = assigned[2]
    request = {'method': 'elicitation/create', 'params': {'message': 'Choose a target.'}}
    adapter.observed['inputs'] = {'choice:1': {'request': request, 'route': {'kind': 'elicitation', 'id': 'one'}}}
    waiting = lifecycle.get(ctx, task_id)
    assert waiting['status'] == 'input_required'
    assert waiting['inputRequests'] == {'choice:1': request}
    before = lifecycle.assignment(ctx, task_id)
    assert lifecycle.update(ctx, task_id, {'unknown': {'action': 'accept'}})
    assert lifecycle.assignment(ctx, task_id) == before
    response = {'action': 'accept', 'content': {'target': 'example'}}
    assert lifecycle.update(ctx, task_id, {'choice:1': response})
    assert adapter.responses == [('choice:1', {'route': {'kind': 'elicitation', 'id': 'one'}, 'response': response})]
    assert lifecycle.get(ctx, task_id)['status'] == 'working'
    after = lifecycle.assignment(ctx, task_id)
    assert lifecycle.update(ctx, task_id, {'choice:1': response, 'unknown': response})
    assert lifecycle.assignment(ctx, task_id) == after
    assert len(adapter.responses) == 1


@pytest.mark.parametrize('state', ['completed', 'failed', 'cancelled'])
def test_terminal_result_is_immutable_under_poll_update_and_cancel(assigned, state):
    ctx, lifecycle, task_id = create(assigned)
    adapter = assigned[2]
    adapter.observed.update(state=state, result=runtime.tool_result('Done.'),
                            error={'code': -32000, 'message': 'Transport failed.'})
    terminal = lifecycle.get(ctx, task_id)
    assert terminal['status'] == state
    before = lifecycle.assignment(ctx, task_id)
    adapter.observed.update(state='working', inputs={'late': {'request': {}, 'route': {'kind': 'message'}}})
    assert lifecycle.update(ctx, task_id, {'late': {'action': 'accept'}})
    assert lifecycle.cancel(ctx, task_id)
    assert lifecycle.get(ctx, task_id) == terminal
    assert lifecycle.assignment(ctx, task_id) == before
    assert adapter.responses == []
    assert adapter.cancelled == []


def test_cancellation_waits_for_transport_acknowledgement(assigned):
    ctx, lifecycle, task_id = create(assigned)
    adapter = assigned[2]
    assert lifecycle.cancel(ctx, task_id)
    row = lifecycle.assignment(ctx, task_id)
    assert row['cancel_requested'] is True
    assert row['state'] == 'working'
    assert adapter.cancelled == [task_id]
    adapter.observed['state'] = 'cancelled'
    assert lifecycle.get(ctx, task_id)['status'] == 'cancelled'


@pytest.mark.parametrize('error', [OSError('Adapter unavailable.'), Stop('No transport.', 'enable dispatch')])
def test_startup_tool_failure_completes_with_error_result(assigned, error):
    ctx, lifecycle, adapter = assigned
    adapter.start_error = error
    created = lifecycle.assign(ctx, '', None)
    assert created['state'] == 'completed'
    result = lifecycle.get(ctx, created['task_id'])
    assert result['status'] == 'completed'
    assert result['result']['isError'] is True
    assert result['result']['content'] == [{'type': 'text', 'text': str(error)}]
    assert lifecycle.assignment(ctx, created['task_id'])['locator'] is None


def test_idle_message_request_stays_stable_until_a_new_agent_turn(assigned):
    ctx, lifecycle, task_id = create(assigned)
    adapter = assigned[2]
    adapter.observed.update(idle=True, last_message='Ready for your next instruction.')
    first = lifecycle.get(ctx, task_id)
    assert first['status'] == 'input_required'
    assert len(first['inputRequests']) == 1
    key = next(iter(first['inputRequests']))
    assert first['inputRequests'][key]['params']['requestedSchema']['required'] == ['message']
    assert lifecycle.get(ctx, task_id) == first
    response = {'action': 'accept', 'content': {'message': 'Inspect the next example.'}}
    assert lifecycle.update(ctx, task_id, {key: response})
    assert lifecycle.get(ctx, task_id)['status'] == 'working'
    before = lifecycle.assignment(ctx, task_id)
    assert lifecycle.update(ctx, task_id, {key: response})
    assert lifecycle.assignment(ctx, task_id) == before
    assert len(adapter.responses) == 1
    adapter.observed.update(turn_seq=2, last_message='Next example inspected.')
    next_turn = lifecycle.get(ctx, task_id)
    assert next_turn['status'] == 'input_required'
    assert set(next_turn['inputRequests']) != {key}
    assert lifecycle.get(ctx, task_id) == next_turn
