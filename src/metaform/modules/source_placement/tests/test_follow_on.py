"""The optional classifier never makes ordinary intake depend on an external service."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from metaform import home, settings
from metaform.module import Context
from metaform.modules import source_placement

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('BASE-065')]


def test_unavailable_key_does_not_launch_or_require_store(monkeypatch, tmp_path):
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    ctx = Context('source_placement', tmp_path)
    assert source_placement.finished({'code': True}, ctx)['status'] == 'skipped'


def test_unavailable_inventory_does_not_launch(monkeypatch, project_folder):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-only')
    settings.put('jev', True, project_folder)
    monkeypatch.setattr(source_placement, 'provided', lambda *_: [])
    assert source_placement.finished({'code': True}, Context('source_placement', project_folder))['status'] == 'skipped'


def test_saved_intake_starts_detached_pinned_extension(monkeypatch, project_folder, store):
    with store.atomic():
        store.layer('base', 'intake', 'Map', kind='intake', mutable=False, hideable=False, ready=True)
    base = store.bound_base().id
    calls = []
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-only')
    settings.put('jev', True, project_folder)
    monkeypatch.setattr(source_placement, 'provided', lambda *_: [('map', object())])

    def launch(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(pid=123)

    monkeypatch.setattr(source_placement.subprocess, 'Popen', launch)
    result = source_placement.finished({'code': True, 'project': store.project_id, 'base': base},
                              Context('source_placement', project_folder, project=store.project_id, store=store))
    assert result['status'] == 'running'
    assert result['base'] == base
    assert f'base={base}' in calls[0][0]
    assert calls[0][0][-3:] == ['--project', store.project_id, '--json']
    assert calls[0][1]['cwd'] == Path(store.project().path)
    assert 'test-only' not in ' '.join(calls[0][0])
    assert Path(result['result']).is_relative_to(home.project_folder(store.project_id))
    assert Path(result['result']).is_file()
    assert not (project_folder / '.metaform').exists()


@pytest.mark.parametrize('jev_on', [False, True])
def test_intake_finish_sends_code_to_jev_only_when_the_person_turned_jev_on(run, monkeypatch, project_folder, jev_on):
    import io
    import json

    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-only')
    if jev_on:
        settings.put('jev', True, project_folder)
    for args in (('start',), ('element', 'stakeholder.operator', 'role=CQU', 'name_length=1'),
                 ('element', 'code.controller.session', 'role=SE', 'name_length=2'),
                 ('purpose', 'stakeholder.operator', '["code.controller.session"]', 'purpose=Run a session.',
                  'ef=Runs sessions.', 'ifd=receives')):
        run('intake', *args, '--json', cwd=project_folder)
    from metaform.data import Store
    from metaform.jev import ENDPOINTS
    from metaform.modules.intake import finish
    (project_folder / 'app.js').write_text('function start() {}')
    item = {'file': 'app.js', 'symbol': 'start', 'source': 'function start() {}', 'start_byte': 0, 'end_byte': 19}
    # Publishing loads the modules afresh, so the code graph is stubbed where each fresh import binds it.
    monkeypatch.setattr('metaform.module.provided', lambda *_: [('map', lambda ctx, paths=None: {
        'items': [item], 'gaps': [], 'coverage': {}})])
    requests = []

    def network(request, **kwargs):
        payload = json.loads(request.data)
        requests.append(payload)
        return io.BytesIO(json.dumps({'answers': {key: {
            'type': 'choice', 'choice': 'category_000', 'confidence': .9, 'probabilities': {'category_000': 1.0}}
            for key in payload['questions']}, 'usage': {'cost': .001}}).encode())

    monkeypatch.setattr('urllib.request.urlopen', network)
    launched = []

    def detached(command, **kwargs):  # the detached `source_placement extend`, run here so its requests meet the stub
        launched.append(command)
        base = next(part.removeprefix('base=') for part in command if part.startswith('base='))
        source_placement.extend(Context('source_placement', project_folder, project='proj', store=Store('proj'), nouns={'base': base}))
        return SimpleNamespace(pid=123)

    monkeypatch.setattr(source_placement.subprocess, 'Popen', detached)
    result = finish(Context('intake', project_folder, store=Store('proj')))
    delivery = next(one for one in result['follow_on'] if one['module'] == 'source_placement')
    if not jev_on:
        assert launched == [] and requests == []
        assert not (project_folder / '.metaform' / 'source_placement').exists()
        assert delivery['result'] == {'status': 'skipped', 'reason': 'jev is off; only the person turns it on.'}
        return
    assert delivery['result']['status'] == 'running'
    assert not (project_folder / '.metaform').exists()
    assert len(launched) == 1 and len(requests) == 1
    assert requests[0]['state']['items']['function_00000'] == {'symbol': 'start', 'source': 'function start() {}'}
    assert requests[0]['model'] == ENDPOINTS['openrouter'].model  # jev_model's default, from the shared client


def test_non_code_intake_does_not_use_classifier(monkeypatch, tmp_path):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-only')
    monkeypatch.setattr(source_placement, 'provided', lambda *_: pytest.fail('Non-code intake must not inspect the indexer'))
    assert source_placement.finished({'code': False}, Context('source_placement', tmp_path))['status'] == 'skipped'


def test_existing_intake_extension_dispatches_pending_validation(monkeypatch, project_folder, store):
    from metaform.modules.source_placement import pipeline, remainder
    with store.atomic():
        store.layer('base', 'intake', 'Map', kind='intake', mutable=False, hideable=False, ready=True)
    base = store.bound_base().id
    launches = []
    monkeypatch.setattr(pipeline, 'prepare', lambda *a, **k: {'run_id': 'saved', 'base_id': base})
    monkeypatch.setattr(pipeline, 'execute', lambda *a, **k: {
        'run_id': 'saved', 'base_id': base, 'pending': 2, 'status': 'review'})

    def start(ctx, run_id, *, base_id):
        launches.append((run_id, base_id))
        return {'state': 'running'}

    monkeypatch.setattr(remainder, 'start_remainder', start)
    result = source_placement.extend(Context('source_placement', project_folder, store=store))
    assert launches == [('saved', base)]
    assert result['follow_up']['state'] == 'running'


def test_existing_intake_extension_skips_without_dependencies(monkeypatch, project_folder, store):
    from metaform.modules.source_placement import pipeline, remainder
    monkeypatch.setattr(pipeline, 'prepare', lambda *a, **k: {'status': 'skipped', 'reason': 'Unavailable'})
    monkeypatch.setattr(remainder, 'start_remainder', lambda *a, **k: pytest.fail('No review run exists'))
    assert source_placement.extend(Context('source_placement', project_folder, store=store))['status'] == 'skipped'


@pytest.mark.parametrize('actions, again', [(('clear',), 'b'), (('remove',), 'b'), (('clear', 'remove'), 'b'),
                                            (('remove',), 'a')])
def test_deleted_project_bases_do_not_resurface_placement_runs(run, tmp_path, actions, again):
    folder_a, folder_b = tmp_path / 'a', tmp_path / 'b'
    folder_a.mkdir()
    folder_b.mkdir()
    run('add', 'project', 'p', str(folder_a), cwd=folder_a)
    base = home.add_base('p', 'original').id
    run_id = 'a' * 24
    directory = source_placement.runs_root('p') / run_id
    directory.mkdir()
    (directory / 'run.json').write_text(json.dumps({'run_id': run_id, 'project': 'p', 'base_id': base}))
    assert run('source_placement', 'status', f'run={run_id}', '--json', cwd=folder_a).returncode == 0

    for action in actions:
        run(action, 'project', 'p', '--confirm', cwd=folder_a)
        if action == 'clear':
            # Each CLI call is its own process, so the next one starts the module, which removes the orphaned run.
            assert run('source_placement', 'status', f'run={run_id}', cwd=folder_a, ok=False,
                       isolated=True).returncode != 0
            assert not directory.exists()
    if 'remove' not in actions:
        run('remove', 'project', 'p', '--confirm', cwd=folder_a)
    folder = tmp_path / again
    run('add', 'project', 'p', str(folder), cwd=folder)
    missing = run('source_placement', 'status', f'run={run_id}', cwd=folder, ok=False, isolated=True)
    assert missing.returncode != 0
    assert f'No source placement run {run_id} in this project.' in missing.stdout + missing.stderr
    assert not (source_placement.runs_root('p') / run_id).exists()


def test_run_on_a_missing_base_is_refused(project_folder, store):
    from metaform.modules.source_placement import pipeline

    current_base = home.add_base(store.project_id, 'original').id
    run_id = 'a' * 24
    directory = source_placement.runs_root(store.project_id) / run_id
    directory.mkdir()
    record = {'run_id': run_id, 'project': store.project_id, 'base_id': current_base}
    (directory / 'run.json').write_text(json.dumps(record))
    ctx = Context('source_placement', project_folder, store=store)
    assert pipeline.status(ctx, run_id) == record
    record['base_id'] = 'deleted-base'
    (directory / 'run.json').write_text(json.dumps(record))
    with pytest.raises(ValueError, match='base.*no longer exists'):
        pipeline.status(ctx, run_id)


def test_runs_require_a_registered_project(home):
    with pytest.raises(ValueError, match='No project missing is registered'):
        source_placement.runs_root('missing')
