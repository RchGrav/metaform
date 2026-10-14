"""The optional classifier never makes ordinary intake depend on an external service."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from metaform.module import Context
from metaform.modules import refactor

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('BASE-065')]


def test_unavailable_key_does_not_launch_or_require_store(monkeypatch, tmp_path):
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    ctx = Context('refactor', tmp_path)
    assert refactor.finished({'code': True}, ctx)['status'] == 'skipped'


def test_unavailable_inventory_does_not_launch(monkeypatch, tmp_path):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-only')
    monkeypatch.setattr(refactor, 'provided', lambda *_: [])
    assert refactor.finished({'code': True}, Context('refactor', tmp_path))['status'] == 'skipped'


def test_saved_intake_starts_detached_pinned_extension(monkeypatch, project_folder, store):
    with store.atomic():
        store.layer('base', 'intake', 'Map', kind='intake', mutable=False, hideable=False, ready=True)
    base = store.bound_base().id
    calls = []
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-only')
    monkeypatch.setattr(refactor, 'provided', lambda *_: [('map', object())])

    def launch(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(pid=123)

    monkeypatch.setattr(refactor.subprocess, 'Popen', launch)
    result = refactor.finished({'code': True, 'project': store.project_id, 'base': base},
                              Context('refactor', project_folder, project=store.project_id, store=store))
    assert result['status'] == 'running'
    assert result['base'] == base
    assert f'base={base}' in calls[0][0]
    assert calls[0][0][-3:] == ['--project', store.project_id, '--json']
    assert calls[0][1]['cwd'] == Path(store.project().path)
    assert 'test-only' not in ' '.join(calls[0][0])
    assert Path(result['result']).is_file()


def test_non_code_intake_does_not_use_classifier(monkeypatch, tmp_path):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-only')
    monkeypatch.setattr(refactor, 'provided', lambda *_: pytest.fail('Non-code intake must not inspect the indexer'))
    assert refactor.finished({'code': False}, Context('refactor', tmp_path))['status'] == 'skipped'


def test_existing_intake_extension_dispatches_pending_validation(monkeypatch, project_folder, store):
    from metaform.modules.refactor import pipeline, remainder
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
    result = refactor.extend(Context('refactor', project_folder, store=store))
    assert launches == [('saved', base)]
    assert result['follow_up']['state'] == 'running'


def test_existing_intake_extension_skips_without_dependencies(monkeypatch, project_folder, store):
    from metaform.modules.refactor import pipeline, remainder
    monkeypatch.setattr(pipeline, 'prepare', lambda *a, **k: {'status': 'skipped', 'reason': 'Unavailable'})
    monkeypatch.setattr(remainder, 'start_remainder', lambda *a, **k: pytest.fail('No review run exists'))
    assert refactor.extend(Context('refactor', project_folder, store=store))['status'] == 'skipped'
