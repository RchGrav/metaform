"""Durable intake classification preserves source evidence and resumes paid work."""
import io
import json
from dataclasses import replace

import pytest

from metaform import settings
from metaform.module import Context
from metaform.modules.source_placement import pipeline

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('BASE-065')]


@pytest.fixture
def prepared(store, project_folder, monkeypatch):
    with store.atomic():
        store.layer('base', 'intake', 'Map', kind='intake', mutable=False, hideable=False, ready=True)
        for address in ['code', 'code.controller.session', 'code.controller.build']:
            store.add_element('base', address, name_length=1, role='SE')
        store.add_join('base', 'code', 'code.controller.session', purpose='Run.', ef='Runs sessions.')
        store.add_join('base', 'code', 'code.controller.build', purpose='Build.', ef='Builds code.')
    source = 'function start() {}\nfunction stop() {}'
    path = project_folder / 'app.js'
    path.write_text(source)
    items = [{'file': 'app.js', 'symbol': name, 'source': body, 'start_byte': start, 'end_byte': end}
             for name, body, start, end in [('start', 'function start() {}', 0, 19),
                                          ('stop', 'function stop() {}', 20, 38)]]
    def inventory(ctx, paths=None):
        return {'items': items, 'gaps': [], 'coverage': {'file': 'app.js'}}
    monkeypatch.setattr(pipeline, 'provided', lambda *args: [('map', inventory)])
    monkeypatch.setenv('OPENROUTER_API_KEY', 'fake-test-key')
    settings.put('jev', True, project_folder)
    calls = []
    def respond(request, **kwargs):
        payload = json.loads(request.data)
        calls.append(payload)
        return io.BytesIO(json.dumps({'answers': {
            key: {'type': 'choice', 'choice': 'category_000', 'confidence': .9 if key.endswith('0') else .89,
                  'probabilities': {'category_000': 1.0}}
            for key in payload['questions']}, 'usage': {'cost': .002}}).encode())
    monkeypatch.setattr('urllib.request.urlopen', respond)
    ctx = Context('source_placement', project_folder, project='proj', store=store)
    return ctx, calls


def test_places_high_confidence_and_validates_remainder_without_rebilling(prepared):
    ctx, calls = prepared
    run = pipeline.prepare(ctx, exclude=['code.controller.build'])
    run_id = run['run_id']
    result = pipeline.execute(ctx, run_id)
    assert result['status'] == 'review', result
    assert result['accepted'] == 1
    assert result['pending'] == 1
    assert result['usage']['cost'] == .002
    assert set(calls[0]['state']['items']['function_00000']) == {'symbol', 'source'}
    assert list(calls[0]['questions']['function_00000']['criteria'].values()) == [
        'Category: Session Controller Program Code\nRuns sessions.']
    assert len(ctx.store.layer_items('source_placement', limit=0).results) == 1
    assert pipeline.prepare(ctx, exclude=['code.controller.build'])['run_id'] == run_id
    pipeline.execute(ctx, run_id)
    assert len(calls) == 1
    queue = pipeline.pending(ctx, run_id)
    assert queue['items'][0]['source'] == 'function stop() {}'
    complete = pipeline.resolve(ctx, run_id, run['base_id'], 'function_00001',
                                'code.controller.session', 'Stops the execution session.')
    assert complete['status'] == 'complete'
    assert complete['pending'] == 0
    pipeline.resolve(ctx, run_id, run['base_id'], 'function_00001',
                     'code.controller.session', 'Stops the execution session.')
    assert len(ctx.store.layer_items('source_placement', limit=0).results) == 2


def test_missing_key_keeps_intake_ordinary(prepared, monkeypatch):
    ctx, calls = prepared
    monkeypatch.delenv('OPENROUTER_API_KEY')
    assert pipeline.prepare(ctx)['status'] == 'skipped'
    assert not calls


def test_changed_source_cannot_place_old_results(prepared):
    ctx, calls = prepared
    run = pipeline.prepare(ctx, exclude=['code.controller.build'])
    (ctx.folder / 'app.js').write_text('changed')
    with pytest.raises(ValueError, match='Code changed'):
        pipeline.execute(ctx, run['run_id'])
    assert not calls


def test_run_found_from_dispatch_subfolder(prepared):
    ctx, _ = prepared
    run = pipeline.prepare(ctx, exclude=['code.controller.build'])
    child = replace(ctx, folder=ctx.folder / '.worktree')
    assert pipeline.status(child, run['run_id']) == run


def test_failed_api_preserves_intake_and_can_resume(prepared, monkeypatch):
    ctx, calls = prepared
    run = pipeline.prepare(ctx, exclude=['code.controller.build'])
    original = pipeline.jev.associate
    monkeypatch.setattr(pipeline.jev, 'associate', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('offline')))
    failed = pipeline.execute(ctx, run['run_id'])
    assert failed['status'] == 'unavailable'
    assert not calls
    assert not any(layer.name == 'source_placement' for layer in ctx.store.layers(limit=0).results)
    monkeypatch.setattr(pipeline.jev, 'associate', original)
    assert pipeline.execute(ctx, run['run_id'])['accepted'] == 1


def test_oversized_item_goes_to_manual_queue_without_blocking_other_functions(prepared, monkeypatch):
    ctx, calls = prepared
    original = pipeline.jev.prepare_batches
    def limited(items, candidates):
        if any(item['symbol'] == 'stop' for item in items.values()):
            raise ValueError('Too large')
        return original(items, candidates)
    monkeypatch.setattr(pipeline.jev, 'prepare_batches', limited)
    run = pipeline.prepare(ctx, exclude=['code.controller.build'])
    result = pipeline.execute(ctx, run['run_id'])
    assert result['status'] == 'review'
    assert result['accepted'] == 1
    assert result['gap_count'] == 1
    assert result['pending'] == 1
    assert len(calls) == 1
    queue = pipeline.pending(ctx, run['run_id'])
    assert queue['items'][0]['gap']['evidence']['source'] == 'function stop() {}'
    result = pipeline.resolve(ctx, run['run_id'], run['base_id'], 'gap_00000',
                              'code.controller.session', 'Read source and verified session shutdown.')
    assert result['status'] == 'complete'
    assert result['pending'] == 0


def test_concurrent_execute_cannot_acquire_same_run(prepared):
    ctx, calls = prepared
    run = pipeline.prepare(ctx, exclude=['code.controller.build'])
    directory = pipeline._directory(ctx, run['run_id'])
    with pipeline._lock(directory), pytest.raises(ValueError, match='already being processed'):
        pipeline.execute(ctx, run['run_id'])
    assert not calls
    assert pipeline.execute(ctx, run['run_id'])['accepted'] == 1


def test_resume_reuses_successful_batch_checkpoint(prepared, monkeypatch):
    ctx, calls = prepared
    original_batches = pipeline.jev.prepare_batches
    monkeypatch.setattr(pipeline.jev, 'prepare_batches', lambda items, candidates: [
        batch for key, value in items.items() for batch in original_batches({key: value}, candidates)])
    original_associate = pipeline.jev.associate
    failed = False
    def flaky(items, candidates, *args, **kwargs):
        nonlocal failed
        if 'function_00001' in items and not failed:
            failed = True
            raise RuntimeError('Temporary connection failure')
        return original_associate(items, candidates, *args, **kwargs)
    monkeypatch.setattr(pipeline.jev, 'associate', flaky)
    run = pipeline.prepare(ctx, exclude=['code.controller.build'])
    assert pipeline.execute(ctx, run['run_id'])['status'] == 'unavailable'
    assert len(calls) == 1
    result = pipeline.execute(ctx, run['run_id'])
    assert result['status'] == 'review'
    assert result['usage']['cost'] == .004
    assert len(calls) == 2


def test_legacy_run_filters_forbidden_categories_without_rewriting_history(prepared):
    ctx, _ = prepared
    run = pipeline.prepare(ctx, exclude=['code.controller.build'])
    pipeline.execute(ctx, run['run_id'])
    path = pipeline._directory(ctx, run['run_id']) / 'input.json'
    inputs = json.loads(path.read_text())
    for provider in ['code', 'upstream.code.browser.web', 'downstream.user']:
        inputs['candidates'][provider] = {'provider': provider, 'ef': ['Historical description.']}
    path.write_text(json.dumps(inputs))
    before = path.read_bytes()
    assert len(pipeline.pending(ctx, run['run_id'])['categories']) == 1
    assert pipeline.execute(ctx, run['run_id'])['accepted'] == 1
    for provider in ['code', 'upstream.code.browser.web', 'downstream.user']:
        with pytest.raises(ValueError, match='existing provider category'):
            pipeline.resolve(ctx, run['run_id'], run['base_id'], 'function_00001', provider, 'Invalid target.')
    assert path.read_bytes() == before
    state = path.with_name('run.json')
    value = json.loads(state.read_text())
    value['status'] = 'ready'
    state.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='excluded providers'):
        pipeline.execute(ctx, run['run_id'])


@pytest.mark.parametrize('oversized', [False, True])
def test_gap_only_run_probes_service_then_opens_review_queue(prepared, monkeypatch, oversized):
    ctx, calls = prepared
    def inventory(ctx, paths=None):
        return {'items': [], 'gaps': [{'file': 'app.js', 'reason': 'Parser unavailable.'}]}
    if oversized:
        def too_large(*args, **kwargs):
            raise ValueError('Too large')
        monkeypatch.setattr(pipeline.jev, 'prepare_batches', too_large)
    else:
        monkeypatch.setattr(pipeline, 'provided', lambda *args: [('map', inventory)])
    def probe(request, **kwargs):
        payload = json.loads(request.data)
        calls.append(payload)
        assert payload['state'] == {'availability': 'ready'}
        return io.BytesIO(json.dumps({'answers': {'availability': {
            'type': 'choice', 'choice': 'ready', 'confidence': 1., 'probabilities': {'ready': 1.}}},
            'usage': {'cost': .0001}}).encode())
    monkeypatch.setattr('urllib.request.urlopen', probe)
    run = pipeline.prepare(ctx, exclude=['code.controller.build'])
    result = pipeline.execute(ctx, run['run_id'])
    assert result['status'] == 'review'
    assert result['accepted'] == 0
    assert result['pending'] == (2 if oversized else 1)
    assert result['usage'] == {'cost': .0001}
    assert pipeline.pending(ctx, run['run_id'])['items'][0]['item_id'] == 'gap_00000'
    assert ctx.store.layer_items('source_placement', limit=0).results == ()
    pipeline.execute(ctx, run['run_id'])
    assert len(calls) == 1
