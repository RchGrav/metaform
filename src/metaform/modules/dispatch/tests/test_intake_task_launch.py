"""Intake launch uses durable named tasks and native transport without parsing instructions or starting a model."""
from __future__ import annotations

import importlib
import json
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.kind('fixture')

OPAQUE = 'An editable intake task.\n<Prompt>These are literal instruction bytes.</Prompt>\nDo not replace this source.  \n'


@pytest.fixture
def intake_launch(project_folder, tmp_path, monkeypatch, run):
    run('enable', 'dispatch', cwd=project_folder)
    from metaform import settings
    from metaform.data import Store
    from metaform.module import context, provided
    transport = provided(project_folder, 'task.transport')[0][1]
    lifecycle = provided(project_folder, 'task.lifecycle')[0][1]
    dispatch = importlib.import_module(type(transport).__module__.rpartition('.')[0])
    tasks = importlib.import_module(type(lifecycle).__module__.rpartition('.')[0])

    source = tmp_path / 'intake-instructions.txt'
    source.write_text(OPAQUE, encoding='utf-8')
    settings.put('intake_file', str(source), project_folder)
    started = []
    live = {}
    monkeypatch.setattr(dispatch, 'runnable', lambda *args: None)
    monkeypatch.setattr(dispatch, 'runner_of', lambda pid: live.get(pid))
    monkeypatch.setattr(Store, 'intake_building', lambda self: SimpleNamespace(results=[]))
    monkeypatch.setattr(Store, 'intake_bases', lambda self: ())
    monkeypatch.setattr(Store, 'has_intake', lambda self: False)

    def spawn(store, work_id, agent, extra, name, **kwargs):
        with Store(store.project_id, module='dispatch').tables(write=False) as tx:
            row = tx.get('raised', {'work_id': work_id})
        payload = json.loads(row['asked'])
        assert payload['name'] == 'intake' and payload['instructions'] == OPAQUE
        assert payload['component']['text'] == OPAQUE
        assert store.intake_launch()['work'] == work_id  # structural marker exists before spawn
        started.append({'work_id': work_id, 'agent': agent, 'extra': extra, 'name': name,
                        'payload': payload, 'kwargs': kwargs})
        live[12345] = work_id
        return {'pid': 12345}

    monkeypatch.setattr(dispatch, 'spawn', spawn)

    def launch(**nouns):
        return dispatch.intake(context('dispatch', project_folder, nouns=nouns))

    def direct(**nouns):
        return tasks.assign(context('tasks', project_folder, nouns={'name': 'intake', **nouns}))

    def assigned(task_id):
        return tasks.SERVICE.assignment(context('tasks', project_folder), task_id)

    return SimpleNamespace(launch=launch, direct=direct, assigned=assigned, started=started, live=live,
                           store=Store('proj'), dispatch=dispatch, tasks=tasks, folder=project_folder,
                           context=context, Store=Store)


def test_dispatch_intake_assigns_named_task_preserving_selected_map_and_opaque_source(intake_launch):
    result = intake_launch.launch(agent='codex', map='new', name='precise-map', text=['Focus', 'on', 'timing.'])
    record = intake_launch.assigned(result['task_id'])
    assert record['name'] == 'intake' and record['work_id'].startswith('task-')
    assert record['payload']['instructions'] == OPAQUE
    assert record['payload']['intake'] == {'map': 'new', 'name': 'precise-map', 'mode': 'fresh'}
    assert record['payload']['interactive'] is False and record['payload']['persistent'] is False
    assert 'Selected intake mode: fresh' in record['payload']['input']
    assert 'Focus on timing.' in record['payload']['input']
    assert result['map'] == 'new' and result['name'] == 'precise-map' and result['mode'] == 'fresh'
    assert result['pid'] == 12345 and result['intake'] is True
    launch, = intake_launch.started
    assert launch['name'] == 'task' and launch['agent'] == 'codex'
    assert f'task={result["task_id"]}' in launch['extra']
    assert 'intake=true' not in launch['extra'] and 'system=true' not in launch['extra']
    assert intake_launch.store.intake_launch()['work'] == result['work_id']


def test_direct_intake_assignment_derives_safe_defaults_without_using_task_name_as_map_name(intake_launch):
    result = intake_launch.direct(text='Inspect the existing source.')
    record = intake_launch.assigned(result['task_id'])
    assert record['payload']['intake'] == {'mode': 'fresh'}
    assert 'name' not in record['payload']['intake']
    assert record['payload']['instructions'] == OPAQUE
    assert 'Inspect the existing source.' in record['payload']['input']


def test_direct_intake_on_mapped_project_refines_by_default(intake_launch, monkeypatch):
    monkeypatch.setattr(intake_launch.Store, 'intake_bases', lambda self: ('existing-map',))
    monkeypatch.setattr(intake_launch.Store, 'has_intake', lambda self: True)
    result = intake_launch.direct(text='Refine only what changed.')
    payload = intake_launch.assigned(result['task_id'])['payload']
    assert payload['intake'] == {'map': 'extend', 'mode': 'refine'}
    assert 'Selected intake mode: refine' in payload['input']
    assert payload['instructions'] == OPAQUE


def test_unfinished_intake_requires_explicit_resume_and_keeps_that_destination(intake_launch, monkeypatch):
    unfinished = SimpleNamespace(recording=False, layer=SimpleNamespace(name='unfinished'), base='kept-base', parts=3)
    monkeypatch.setattr(intake_launch.Store, 'intake_building', lambda self: SimpleNamespace(results=[unfinished]))
    refused = intake_launch.direct(text='An accidental fresh start.')
    assert refused['state'] == 'completed' and not intake_launch.started
    assert intake_launch.assigned(refused['task_id'])['result']['isError']
    result = intake_launch.launch(resume=True, text='Continue from the recorded facts.')
    payload = intake_launch.assigned(result['task_id'])['payload']
    assert payload['intake']['mode'] == 'resume'
    assert 'Selected intake mode: resume' in payload['input']
    assert payload['instructions'] == OPAQUE


def test_direct_and_dispatch_launch_share_single_recording_protection(intake_launch):
    first = intake_launch.launch(text='First intake.')
    refused = intake_launch.direct(text='Second intake must not interleave.')
    assert refused['state'] == 'completed'
    assert intake_launch.assigned(refused['task_id'])['result']['isError']
    assert len(intake_launch.started) == 1
    assert intake_launch.store.intake_launch()['work'] == first['work_id']


def test_failed_task_transport_removes_structural_marker_and_launch_row(intake_launch, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError('Native adapter could not start.')
    monkeypatch.setattr(intake_launch.dispatch, 'spawn', fail)
    result = intake_launch.direct(text='Start only if native transport is available.')
    assert result['state'] == 'completed'
    assert intake_launch.assigned(result['task_id'])['result']['isError']
    assert intake_launch.store.intake_launch() is None
    with intake_launch.Store('proj', module='dispatch').tables(write=False) as tx:
        assert not tx.rows('raised', limit=0).results


def test_starting_task_intake_is_listed_and_can_be_stopped_through_normal_dispatch(intake_launch, monkeypatch):
    result = intake_launch.launch(text='Record the map.')
    ctx = intake_launch.context('dispatch', intake_launch.folder, nouns={'id': result['work_id'], 'thread': False})
    listed = intake_launch.dispatch.read_sessions(ctx)
    row, = listed['sessions']
    assert row['work_id'] == result['work_id'] and row['task_name'] == 'intake' and row['state'] == 'starting'
    ended = []
    monkeypatch.setattr(intake_launch.dispatch, 'ended_launch_group', lambda pid: ended.append(pid))
    stopped = intake_launch.dispatch.stop(ctx)
    assert stopped['stopped'] is True and ended == [12345]
    assert intake_launch.store.intake_launch() is None


def test_ended_session_menu_retains_task_name_without_republishing_instruction_body(intake_launch):
    from metaform import home
    result = intake_launch.direct(text='Record the map.')
    task_id, work_id = result['task_id'], result['work_id']
    with intake_launch.Store('proj', module='dispatch').tables() as tx:
        tx.insert('agent_sessions', {'session_id': 'native', 'work_id': work_id, 'agent': 'codex',
                                     'state': 'ended', 'started': '2026-10-24T00:00:00Z', 'ended': home.now(), 'seq': 1})
        tx.insert('session_lines', {'session_id': 'native', 'work_id': work_id, 'name': 'state', 'kind': 'state',
                                    'seq': 1, 'text': json.dumps({'task': {'name': 'intake', 'task_id': task_id,
                                                                         'instructions': OPAQUE}})})
    ctx = intake_launch.context('dispatch', intake_launch.folder, nouns={'thread': False})
    listed = intake_launch.dispatch.read_sessions(ctx)
    row = next(row for row in listed['sessions'] if row.get('session_id') == 'native')
    assert row['task_name'] == 'intake'
    assert listed['states']['native']['task_name'] == 'intake'
    assert OPAQUE not in json.dumps(listed)
