"""Assigned-task lifecycle with real isolated stores and a deterministic in-process transport."""
from __future__ import annotations

import hashlib
import importlib
import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace

import pytest

from metaform.module import Stop, context
from metaform.modules import tasks
from metaform.modules.tasks import runtime

pytestmark = pytest.mark.kind('fixture')


@pytest.fixture(autouse=True)
def task_modules_for_current_home(home):
    """Each isolated home resets the loader, so use its current module instances."""
    global tasks, runtime
    tasks = importlib.import_module('metaform.modules.tasks')
    runtime = importlib.import_module('metaform.modules.tasks.runtime')


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


def test_keyed_assignment_replay_and_concurrent_calls_start_one_task(assigned):
    ctx, lifecycle, adapter = assigned
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda _: lifecycle.assign(ctx, '', None, request_key='one-attempt'), range(2)))
    assert replies[0]['task_id'] == replies[1]['task_id']
    assert len(adapter.started) == 1
    assert lifecycle.assign(ctx, '', None, request_key='one-attempt')['task_id'] == replies[0]['task_id']
    assert len(adapter.started) == 1


def test_keyed_assignment_rejects_changed_instructions_and_new_attempt_uses_new_key(assigned):
    ctx, lifecycle, adapter = assigned
    adapter.start_error = Stop('No free slots.', 'Wait for a slot.')
    failed = lifecycle.assign(ctx, '', None, request_key='attempt-one')
    assert failed['state'] == 'completed'
    adapter.start_error = None
    assert lifecycle.assign(ctx, '', None, request_key='attempt-one')['task_id'] == failed['task_id']
    assert len(adapter.started) == 1
    with pytest.raises(Stop, match='different instructions'):
        lifecycle.assign(replace(ctx, nouns={'text': 'Changed request.'}), '', None, request_key='attempt-one')
    retry = lifecycle.assign(ctx, '', None, request_key='attempt-two')
    assert retry['task_id'] != failed['task_id'] and len(adapter.started) == 2


def test_keyed_assignment_recovers_a_record_written_before_transport_start(assigned):
    ctx, lifecycle, adapter = assigned

    def interrupted(*_args):
        raise KeyboardInterrupt

    adapter.before_start = interrupted
    with pytest.raises(KeyboardInterrupt):
        lifecycle.assign(ctx, '', None, request_key='interrupted-start')
    assert adapter.started == []
    adapter.before_start = None
    recovered = lifecycle.assign(ctx, '', None, request_key='interrupted-start')
    assert len(adapter.started) == 1
    assert lifecycle.assignment(ctx, recovered['task_id'])['locator'] == {'session_id': 'dedicated-test-session'}


def test_cancel_before_initial_transport_start_prevents_keyed_replay_from_launching(assigned):
    ctx, lifecycle, adapter = assigned

    def interrupted(*_args):
        raise KeyboardInterrupt

    adapter.before_start = interrupted
    with pytest.raises(KeyboardInterrupt):
        lifecycle.assign(ctx, '', None, request_key='cancel-before-start')
    with runtime.own(ctx).tables(write=False) as tx:
        task_id = tx.rows('assignments', limit=0).results[0]['task_id']
    lifecycle.cancel(ctx, task_id)
    adapter.before_start = None
    assert lifecycle.assign(ctx, '', None, request_key='cancel-before-start')['task_id'] == task_id
    assert adapter.started == []


@pytest.mark.parametrize('state', ['completed', 'cancelled'])
def test_keyed_replay_never_recreates_a_terminal_task(assigned, state):
    ctx, lifecycle, adapter = assigned
    created = lifecycle.assign(ctx, '', None, request_key='terminal-attempt')
    adapter.observed = {'state': state, 'result': runtime.tool_result('Done.'), 'inputs': {}}
    assert lifecycle.get(ctx, created['task_id'])['status'] == state
    replayed = lifecycle.assign(ctx, '', None, request_key='terminal-attempt')
    assert replayed['task_id'] == created['task_id'] and replayed['state'] == state
    assert len(adapter.started) == 1


def test_user_agent_preserves_canonical_source_and_binds_only_project(project_folder):
    canonical = (tasks.PACKAGE / 'resources' / 'user_agent.txt').read_text(encoding='utf-8')
    ctx = context('tasks', project_folder, nouns={'name': 'user_agent', 'project_name': 'Example & <Project>'})
    definition = tasks.definition(ctx)
    expected = canonical.replace('{project}', 'Example & <Project>')
    assert definition['instructions'] == expected
    assert definition['component']['text'] == expected
    assert definition['component']['bindings'] == {'{project}': 'Example & <Project>'}
    assert definition['component']['rendered_fingerprint'] == hashlib.sha256(expected.encode()).hexdigest()
    assert definition['component']['source']['shipped_identity'] == hashlib.sha256(canonical.encode()).hexdigest()


def test_default_user_agent_uses_the_same_literal_selected_task_document(assigned):
    from metaform.data import prompts

    ctx, lifecycle, adapter = assigned
    tasks.definition(context('tasks', ctx.folder, nouns={'name': 'user_agent'}))
    edited = 'Use {project}. <unclosed> & preserve {prompt}.\n\n'
    selected = prompts.save_prompt('prompt.tasks:user_agent.txt', edited, format='xml')
    created = lifecycle.user_agent(ctx)
    payload = lifecycle.assignment(ctx, created['task_id'])['payload']
    assert payload['instructions'] == edited.replace('{project}', ctx.project)
    assert payload['component']['actual_version_id'] == selected.version_id
    assert adapter.started[0]['payload'] == payload


@pytest.mark.parametrize('name', ['project_agent', 'composer', 'facilitator', 'architect'])
def test_authored_task_source_and_delivered_component_preserve_user_wording(project_folder, name):
    canonical = (tasks.PACKAGE / 'resources' / f'{name}.txt').read_bytes()
    fingerprint = hashlib.sha256(canonical).hexdigest()
    ctx = context('tasks', project_folder,
                  nouns={'name': name, 'project_name': 'Actual Project', 'agent_name': 'Actual Agent'})
    result = tasks.definition(ctx)
    expected = canonical.decode().replace('{project}', 'Actual Project').replace('{name variable}', 'Actual Agent')
    assert result['instructions'] == expected
    assert result['component']['text'] == expected
    assert result['component']['source']['shipped_identity'] == fingerprint


def test_intake_is_discoverable_and_reads_the_canonical_procedure_component(run, project_folder):
    import asyncio
    from importlib import resources

    from metaform import prompt_files
    from metaform.module import prepare_agent_context, record_agent_context
    from metaform.modules import intake
    from metaform.modules.mcp import server

    ctx = context('tasks', project_folder, nouns={'name': 'intake'})
    entry = next(row for row in tasks.catalog(ctx)['tasks'] if row['name'] == 'intake')
    assert entry['uri'] == 'metaform://tasks/definitions/intake'
    definition = tasks.definition(ctx)
    authored = intake.RESOURCE.read_text(encoding='utf-8')
    expected = authored.replace('{project_id}', 'proj').replace('{prompt}', '', 1).rstrip('\n')
    pointer = prompt_files.required(resources.files('metaform.modules.intake'), 'schema_pointer', project='proj')
    expected += '\n\n' + pointer + '\n'
    assert definition['instructions'] == expected
    assert definition['component']['text'] == expected
    assert definition['component']['actual_version_id'] == 'intake-source:' + hashlib.sha256(
        intake.RESOURCE.read_bytes()).hexdigest()
    assert definition['component']['source']['path'] == str(intake.RESOURCE)
    assert intake.prompt(context('intake', project_folder)) == expected
    read = json.loads(run('tasks', 'read', 'name=intake', '--json', cwd=project_folder).stdout)
    assert read['instructions'] == expected
    session, component = 'assigned-intake', definition['component']
    prepared = prepare_agent_context(project_folder, session, [component])
    record_agent_context(project_folder, session, [component], epoch=prepared['epoch'], channel='acp_prompt')
    due = server.instruction_required(project_folder, 'intake_start', {}, session)
    assert due and component['name'] not in {one['name'] for one in due['instructions']}
    asyncio.run(server.read_resource_text(project_folder, server.instruction_uri('intake_start'), session=session))
    assert server.instruction_required(project_folder, 'intake_start', {}, session) is None


def test_list_shows_reusable_skills_beside_the_skill_layer_with_or_without_a_project(project_folder, tmp_path):
    from metaform import skills
    from metaform.modules.tasks import skill_layer
    ctx = context('tasks', project_folder, nouns={'node': 'code.receiver'})
    store = ctx.require_store()
    base = store.layer('functional-map', 'map', 'The functional map.', kind='base', mutable=False, hideable=False)
    for address in ('code', 'code.receiver'):
        store.add_element(base.name, address, name=address, role='SE')
    store.finish(base.name)
    layered = skill_layer.put(ctx, 'code.receiver', 'layer-skill', 'Follow the node method.', 'Found at the node.')
    skills.publish('listed-reference', 'Follow the listed method.', 'Find this skill through tasks list.')
    entry = {'name': 'listed-reference', 'description': 'Find this skill through tasks list.',
             'uri': 'skill://listed-reference/SKILL.md'}
    listed = tasks.catalog(ctx)['skills']
    assert [row.get('id') for row in listed] == [layered['id'], None]
    assert listed[1] == entry
    outside = context('tasks', tmp_path)
    assert outside.store is None
    assert tasks.catalog(outside)['skills'] == [entry]


@pytest.mark.parametrize(('filename', 'authored'), [
    ('custom.md', '# Alternative instructions\nKeep {project}, {name variable} and {prompt}.\n\n'),
    ('custom.xml', '<malformed attr="{prompt}"\nA & B without closing markup.\n'),
    ('custom.txt', 'Follow the supplied method. No required headings or tags.\n'),
])
def test_intake_task_preserves_configured_source_with_canonical_prompt_binding(
        project_folder, tmp_path, filename, authored):
    from importlib import resources

    from metaform import prompt_files, settings
    from metaform.modules import intake

    source = tmp_path / filename
    source.write_text(authored, encoding='utf-8')
    settings.put('intake_file', str(source), project_folder)
    ctx = context('tasks', project_folder, nouns={'name': 'intake'})
    definition = tasks.definition(ctx)
    expected = authored.replace('{prompt}', '', 1).rstrip('\n')
    expected += '\n\n' + prompt_files.required(resources.files('metaform.modules.intake'), 'schema_pointer', project='proj') + '\n'
    assert definition['instructions'] == expected
    assert definition['component']['text'] == expected
    assert definition['component']['source'] == {
        'kind': 'configured_file', 'path': str(source), 'sha256': hashlib.sha256(authored.encode()).hexdigest()}
    assert intake.prompt(context('intake', project_folder)).startswith(expected)
    assert source.read_text(encoding='utf-8') == authored


def test_intake_assignment_preserves_canonical_source_identity_and_separate_input(assigned):
    from importlib import resources

    from metaform import prompt_files
    from metaform.modules import intake

    ctx, lifecycle, adapter = assigned
    ctx.nouns.update(name='intake', text='Inspect the selected artifact.')
    definition = tasks.definition(ctx)
    authored = intake.RESOURCE.read_text(encoding='utf-8')
    expected = authored.replace('{project_id}', 'proj').replace('{prompt}', '', 1).rstrip('\n')
    expected += '\n\n' + prompt_files.required(resources.files('metaform.modules.intake'), 'schema_pointer', project='proj') + '\n'
    edited = 'Use this revised method exactly. <unclosed> & {prompt}\n\n'
    with pytest.raises(ValueError, match='Canonical Intake'):
        prompt_files.save_edit('prompt.intake:intake.axiom', edited)
    assert tasks.definition(ctx) == definition
    assert definition['instructions'] == expected
    assert definition['component']['source']['sha256'] == hashlib.sha256(intake.RESOURCE.read_bytes()).hexdigest()
    assert intake.prompt(context('intake', ctx.folder)).startswith(expected)
    created = tasks.assign(ctx)
    row = lifecycle.assignment(ctx, created['task_id'])
    assert row['name'] == 'intake'
    assert row['payload']['instructions'] == expected
    assert row['payload']['component'] == definition['component']
    assert row['payload']['input'] == 'Inspect the selected artifact.'
    assert row['payload']['interactive'] is False
    assert adapter.started[0]['payload'] == row['payload']
    assert ctx.require_store().active_base() is None


def test_assignment_is_durable_before_transport_start_without_role_or_ticket(assigned, monkeypatch):
    ctx, lifecycle, adapter = assigned
    skill_layer = importlib.import_module('metaform.modules.tasks.skill_layer')
    monkeypatch.setattr(skill_layer, 'read', lambda *args: pytest.fail('No skill was selected.'))

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


@pytest.mark.parametrize('name', ['user_agent', 'architect', 'intake'])
def test_named_task_retains_exact_component_and_assignment_input(assigned, name):
    ctx, lifecycle, adapter = assigned
    ctx.nouns.update(name=name, project_name='Bound Project', text='Focus on the current question.')
    created = tasks.assign(ctx)
    payload = lifecycle.assignment(ctx, created['task_id'])['payload']
    assert payload['instructions'] == tasks.definition(ctx)['instructions']
    assert payload['component'] == tasks.definition(ctx)['component']
    assert payload['input'] == 'Focus on the current question.'
    assert payload['interactive'] is (name == 'user_agent')
    assert adapter.started[0]['payload'] == payload


def test_assignment_attaches_reusable_document_by_uri_without_reference_bodies(assigned):
    from metaform import skills
    ctx, lifecycle, adapter = assigned
    source = skills.publish('assigned-reference', 'Use [the reference](references/input.md) when needed.',
                            'Execute the supplied assignment.', {'references/input.md': 'Reference body.'})
    ctx.nouns['skills'] = [source['uri']]
    created = lifecycle.assign(ctx, '', None)
    payload = lifecycle.assignment(ctx, created['task_id'])['payload']
    delivered, = payload['skills']
    assert delivered['uri'] == source['uri']
    assert delivered['text'].encode() == source['files']['SKILL.md']
    assert delivered['resources'] == source['resources']
    assert delivered['component']['rendered_fingerprint'] == hashlib.sha256(source['files']['SKILL.md']).hexdigest()
    assert 'files' not in delivered
    assert adapter.started[0]['payload'] == payload


def test_only_explicitly_selected_skills_are_loaded(assigned, monkeypatch):
    ctx, lifecycle, adapter = assigned
    loaded = []

    def read(skill_ctx, name, node):
        from metaform import prompt_files
        assert skill_ctx is ctx and node == 'code.Example'
        loaded.append(name)
        text = f'Exact instructions for {name}.'
        attachment = {'layer': 'skills', 'node': node, 'item_id': f'item-{name}'}
        component = prompt_files.component(f'map:skills/item-{name}', text)
        component.update(origin='graph', source={'kind': 'graph', **attachment})
        return {'id': f'item-{name}', 'name': name, 'node': node, 'text': text,
                'component': component, 'attachment': attachment}

    skill_layer = importlib.import_module('metaform.modules.tasks.skill_layer')
    monkeypatch.setattr(skill_layer, 'read', read)
    ctx.nouns['skills'] = ['review', 'research']
    ctx.nouns['node'] = 'code.Example'
    created = lifecycle.assign(ctx, '', None)
    assert loaded == ['review', 'research']
    selected = lifecycle.assignment(ctx, created['task_id'])['payload']['skills']
    assert [(skill['name'], skill['text']) for skill in selected] == [
        (name, f'Exact instructions for {name}.') for name in loaded]
    assert all(skill['component']['origin'] == 'graph' and skill['attachment']['node'] == 'code.Example'
               for skill in selected)
    assert adapter.started[0]['payload']['skills'] == selected


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
def test_terminal_result_stays_as_recorded_until_its_session_runs_again(assigned, state):
    ctx, lifecycle, task_id = create(assigned)
    adapter = assigned[2]
    adapter.observed.update(state=state, result=runtime.tool_result('Done.'),
                            error={'code': -32000, 'message': 'Transport failed.'})
    terminal = lifecycle.get(ctx, task_id)
    assert terminal['status'] == state
    before = lifecycle.assignment(ctx, task_id)
    adapter.observed.update(result=runtime.tool_result('Said later.'), message='Said later.')
    assert lifecycle.update(ctx, task_id, {'late': {'action': 'accept'}})
    assert lifecycle.cancel(ctx, task_id)
    assert lifecycle.get(ctx, task_id) == terminal, 'an ended task reads as recorded while its session is ended'
    assert lifecycle.assignment(ctx, task_id) == before
    assert adapter.responses == []
    assert adapter.cancelled == []
    # its session runs again, the context called back: the task comes out of its terminal state, its outcome open
    adapter.observed.update(state='working', inputs={'late': {'request': {}, 'route': {'kind': 'message'}}})
    assert lifecycle.get(ctx, task_id) == terminal, 'an observation naming no session is no session of it running'
    adapter.observed['session_id'] = 'dedicated-test-session'
    revived = lifecycle.get(ctx, task_id)
    assert revived['status'] == 'input_required' and list(revived['inputRequests']) == ['late']
    row = lifecycle.assignment(ctx, task_id)
    assert (row['result'], row['error'], row['cancel_requested']) == (None, None, False)
    assert lifecycle.update(ctx, task_id, {'late': {'action': 'accept'}})
    assert len(adapter.responses) == 1


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
    ctx, lifecycle, _ = assigned
    ctx.nouns['name'] = 'user_agent'
    task_id = tasks.assign(ctx)['task_id']
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


def test_start_begins_a_pair_of_project_agents_as_the_settings_choose_them(assigned, monkeypatch, tmp_path):
    from metaform.modules.tasks.board import Board
    monkeypatch.setenv('TMPDIR', str(tmp_path / 'temporary'))
    from metaform import settings
    ctx, _, adapter = assigned
    from dataclasses import replace
    for key, offered in (('tasks_agent_1_model', ['default', 'opus']), ('tasks_agent_1_effort', ['default', 'high'])):
        monkeypatch.setitem(settings.SCHEMA, key, replace(settings.SCHEMA[key], choices=lambda ctx=None, o=offered: o))
    settings.put('tasks_agent_1_model', 'opus', ctx.folder)
    settings.put('tasks_agent_1_effort', 'high', ctx.folder)
    started = tasks.start(ctx)['agents']
    assert [row['agent'] for row in adapter.started] == ['claude', 'codex']
    assert all(row['name'] == 'project_agent' and row['payload']['persistent'] for row in adapter.started)
    # each slot's own model and thinking level ride on the task for the runner to apply; a slot at default sends none
    assert adapter.started[0]['payload']['options'] == {'model': 'opus', 'thought_level': 'high'}
    assert adapter.started[1]['payload']['options'] == {}
    assert adapter.started[0]['payload']['instructions'] == adapter.started[1]['payload']['instructions']
    ids = {one['task_id'] for one in started}
    assert len(ids) == 2
    online = Board(ctx.require_store().project_id).workers()
    assert {worker['agent_id'] for worker in online} >= ids and all(worker['score'] is None for worker in online)
