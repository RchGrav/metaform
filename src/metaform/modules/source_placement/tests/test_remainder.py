"""Remainder mapping is durable ordinary work and reuses its run's ticket."""
from __future__ import annotations

import pytest

from metaform.data import Store
from metaform.module import Stop, context

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('BASE-063')]


@pytest.fixture
def remainder_case(run, tmp_path, monkeypatch):
    from metaform.modules.source_placement import remainder
    folder = tmp_path / 'project'
    folder.mkdir()
    run('add', 'project', 'remainder-test', str(folder))
    store = Store('remainder-test')
    store.layer('base', 'intake', 'Map', kind='intake', mutable=False, hideable=False, ready=True)
    store.add_element('base', 'code', role='DE', name_length=1)
    base = store.active_base().id
    prompt = tmp_path / 'prompts.xml'
    prompt.write_text('<prompts><remainder>Resolve <run/> in <base/> of <project/>.</remainder></prompts>')
    monkeypatch.setenv('METAFORM_PROMPTS', str(prompt))
    ctx = context('source_placement', folder, project='remainder-test')
    calls = []
    response = {'sessions': [], 'room': 1, 'fail': False}
    original = remainder._invoke

    def invoke(ctx, module, verb, **nouns):
        if module != 'dispatch':
            return original(ctx, module, verb, **nouns)
        calls.append((verb, nouns))
        if verb == 'sessions':
            return {'sessions': response['sessions']}
        if verb == 'agents':
            return {'default': 'codex', 'room': response['room'],
                    'agents': [{'agent': 'codex', 'available': True}]}
        assert verb == 'start'
        if response['fail']:
            raise Stop('No slot available.', 'metaform dispatch sessions')
        store.take_work(nouns['id'], by='dispatch starting test')
        return {'state': 'starting', 'work_id': nouns['id'], 'pid': 123}

    monkeypatch.setattr(remainder, '_invoke', invoke)
    return remainder, ctx, store, base, calls, response


def test_remainder_starts_normal_worker_with_durable_prompt_and_reuses_reservation(remainder_case):
    remainder, ctx, store, base, calls, _ = remainder_case
    first = remainder.start_remainder(ctx, 'run-one', base_id=base)
    second = remainder.start_remainder(ctx, 'run-one', base_id=base)
    ticket, = store.work(limit=0).results
    assert first['work_id'] == second['work_id'] == ticket.id
    assert ticket.task == f'Resolve run-one in {base} of remainder-test.'
    assert ticket.address == 'code'
    assert ticket.note == 'source_placement remainder: run-one'
    assert len([c for c in calls if c[0] == 'start']) == 1
    assert calls[-1][0] == 'sessions'
    assert not any(c[0] == 'intake' for c in calls)


def test_remainder_reuses_running_session(remainder_case):
    remainder, ctx, _store, base, calls, response = remainder_case
    first = remainder.start_remainder(ctx, 'run-one', base_id=base)
    response['sessions'] = [{'state': 'running', 'work_id': first['work_id'], 'session_id': 'live'}]
    reused = remainder.start_remainder(ctx, 'run-one', base_id=base)
    assert reused['session_id'] == 'live'
    assert reused['state'] == 'running'
    assert len([c for c in calls if c[0] == 'start']) == 1


def test_waiting_ticket_survives_capacity_and_start_failure_then_retries(remainder_case):
    remainder, ctx, store, base, _calls, response = remainder_case
    response['room'] = 0
    first = remainder.start_remainder(ctx, 'run-one', base_id=base)
    assert first['state'] == 'waiting'
    response.update(room=1, fail=True)
    failed = remainder.start_remainder(ctx, 'run-one', base_id=base)
    assert failed['state'] == 'waiting'
    assert failed['work_id'] == first['work_id']
    response['fail'] = False
    started = remainder.start_remainder(ctx, 'run-one', base_id=base)
    assert started['state'] == 'starting'
    assert len(store.work(limit=0).results) == 1


def test_wrong_base_does_not_create_ticket_or_launch(remainder_case):
    remainder, ctx, store, _base, calls, _response = remainder_case
    result = remainder.start_remainder(ctx, 'run-one', base_id='different-base')
    assert result['state'] == 'waiting'
    assert not store.work(limit=0).results
    assert not calls


def test_completed_ticket_is_not_restarted(remainder_case):
    remainder, ctx, store, base, calls, _response = remainder_case
    first = remainder.start_remainder(ctx, 'run-one', base_id=base)
    store.finish_work(first['work_id'], resolution='All entries placed.')
    result = remainder.start_remainder(ctx, 'run-one', base_id=base)
    assert result['state'] == 'completed'
    assert len([c for c in calls if c[0] == 'start']) == 1


def test_base_change_during_preparation_leaves_ticket_unstarted(remainder_case, monkeypatch):
    from types import SimpleNamespace
    remainder, ctx, store, base, calls, _response = remainder_case
    seen = iter([SimpleNamespace(id=base), SimpleNamespace(id='other')])
    monkeypatch.setattr(ctx.store, 'active_base', lambda: next(seen))
    result = remainder.start_remainder(ctx, 'run-one', base_id=base)
    assert result['state'] == 'waiting'
    assert len(store.work(limit=0).results) == 1
    assert not any(c[0] == 'start' for c in calls)


def test_authored_remainder_keeps_every_queue_call_bound_to_original_intake(monkeypatch):
    from importlib import resources

    from metaform import prompt_files
    monkeypatch.delenv('METAFORM_PROMPTS', raising=False)
    prompt = prompt_files.required(resources.files('metaform.modules.source_placement'), 'remainder',
                                   run='test-run', base='original-base', project='example')
    calls = [line.strip() for line in prompt.splitlines() if 'source_placement_pending' in line or 'source_placement_resolve' in line]
    assert len(calls) == 3
    assert all('run=test-run base=original-base' in line for line in calls)
    assert 'remaining queue is empty' in prompt
    assert 'Do not edit source files' in prompt
