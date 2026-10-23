"""Episode continuity keeps concurrency, stop semantics and historical return ownership intact."""
from __future__ import annotations

import asyncio

import pytest

from metaform.data import Store
from metaform.modules.dispatch import orchestration, runner
from metaform.modules.orchestration.state import SERVICE, own, update
from metaform.modules.orchestration.tests.test_episodes import assigned
from metaform.modules.orchestration.tests.test_orchestration import ctx
from tests.storekit import small_map

pytestmark = pytest.mark.kind('simulation')


@pytest.fixture
def project(store, project_folder, run):
    small_map(store)
    run('enable', 'dispatch', cwd=project_folder)
    run('enable', 'orchestration', cwd=project_folder)
    return store, project_folder


def shared_caller(project, monkeypatch):
    monkeypatch.setattr(orchestration, 'service', lambda ctx: SERVICE)
    original = assigned(project, monkeypatch, 'Wait for the original child evidence.')
    SERVICE.bind(ctx(project), original['assignment_id'], 'shared', runner='retained-runner')
    with own(ctx(project)).tables() as tx:
        original = update(tx, original, state='waiting')
    current = assigned(project, monkeypatch, 'Make a related local improvement.', previous=original['work_id'])
    SERVICE.bind(ctx(project), current['assignment_id'], 'shared', runner='retained-runner')
    child = assigned(project, monkeypatch, 'Collect the requested original evidence.', role='reviewer')
    with own(ctx(project)).tables() as tx:
        child = update(tx, child, state='returned', return_to={'assignment_id': original['assignment_id']})
    envelope = {'id': 'original-child-result', 'assignment_id': original['assignment_id'],
                'kind': 'result', 'state': 'returned', 'text': 'Original child evidence is ready.',
                'sender_assignment_id': child['assignment_id'],
                'from': {'assignment_id': child['assignment_id'], 'session_id': 'child', 'agent': 'codex'},
                'to': [{'assignment_id': original['assignment_id'], 'work_id': original['work_id'],
                        'session_id': 'shared'}]}
    return original, current, child, envelope


def test_delayed_original_child_return_survives_runner_queue_and_revalidation(project, monkeypatch):
    from metaform.modules import dispatch as package

    original, current, _, envelope = shared_caller(project, monkeypatch)
    assert orchestration.actionable(ctx(project), envelope, recipient=original)
    assert orchestration.actionable(ctx(project), envelope, session_id='shared')
    delivered = []
    monkeypatch.setattr(orchestration, '_row', lambda *args, **kwargs: {
        'session_id': 'shared', 'work_id': current['work_id'], 'agent': 'codex', 'state': 'running'})
    monkeypatch.setattr(package, 'tell', lambda row, op, **kwargs: delivered.append(kwargs['line']) or {'noted': True})
    sent = orchestration.TRANSPORT.send(ctx(project), original, {
        key: value for key, value in envelope.items() if key != 'assignment_id'})
    assert sent['accepted'] and delivered[0]['assignment_id'] == original['assignment_id']
    store, _ = project
    worker = runner.Session(ctx(project), Store('proj', module='dispatch'),
                            store.ticket(current['work_id']).work, 'codex', ['true'])
    worker.session_id, worker.runner, worker.turns = 'shared', 'retained-runner', 1
    result = asyncio.run(worker.peer_note({'line': delivered[0], 'deliver': True}))
    assert result['queued'] is True
    assert len(worker.pending) == 1
    assert worker.pending_peer(envelope['id'])['assignment_id'] == original['assignment_id']
    assert SERVICE.assignment(ctx(project), session_id='shared')['assignment_id'] == current['assignment_id']
    assert worker.work_id == current['work_id']


@pytest.mark.parametrize('stopped', ['original', 'current', 'child'])
def test_stopped_work_does_not_reactivate_from_a_historical_episode_return(project, monkeypatch, stopped):
    original, current, child, envelope = shared_caller(project, monkeypatch)
    target = {'original': original, 'current': current, 'child': child}[stopped]
    with own(ctx(project)).tables() as tx:
        update(tx, target, state='stopped', stop={'by': 'user', 'at': '2026-10-23T00:00:00Z'})
    assert not orchestration.actionable(ctx(project), envelope, session_id='shared')


def test_a_forged_historical_recipient_from_an_unrelated_episode_is_not_delivered(project, monkeypatch):
    _, current, child, envelope = shared_caller(project, monkeypatch)
    unrelated = assigned(project, monkeypatch, 'An unrelated contribution.')
    with own(ctx(project)).tables() as tx:
        unrelated = update(tx, unrelated, owner_session_id='shared', state='waiting')
        update(tx, child, return_to={'assignment_id': unrelated['assignment_id']})
    assert not orchestration.actionable(ctx(project), {**envelope, 'assignment_id': unrelated['assignment_id']},
                                        session_id='shared')
    assert SERVICE.assignment(ctx(project), session_id='shared')['assignment_id'] == current['assignment_id']


def test_fresh_context_replaces_an_existing_target_session_instead_of_resuming_it(project, monkeypatch):
    from metaform.modules import dispatch as package

    held = assigned(project, monkeypatch, 'Reconstruct the same contribution in fresh context.')
    SERVICE.bind(ctx(project), held['assignment_id'], 'old')
    with own(ctx(project)).tables() as tx:
        held = update(tx, held, state='suspended')
    SERVICE.episode(ctx(project), held['work_id'], fresh=True)
    monkeypatch.setattr(orchestration, 'service', lambda ctx: SERVICE)
    monkeypatch.setattr(package, 'launches', list)
    monkeypatch.setattr(package, 'admit', lambda *args, **kwargs: None)
    monkeypatch.setattr(package, 'startable', lambda *args, **kwargs: None)
    monkeypatch.setattr(orchestration.Transport, 'runtime_settings', lambda *args: {'agent': 'codex'})
    monkeypatch.setattr(orchestration, '_row', lambda *args, **kwargs: {
        'work_id': held['work_id'], 'session_id': 'old', 'agent': 'codex', 'state': 'ended'})
    starts = []
    monkeypatch.setattr(package, 'start_runner', lambda *args, **kwargs: starts.append(args[4]) or {'pid': 123})
    monkeypatch.setattr(package, 'resume_spawn', lambda *args, **kwargs: pytest.fail('Fresh context resumed old ACP'))
    launched = orchestration.TRANSPORT.launch(ctx(project), held, 'fresh-launch')
    assert launched['pid'] == 123 and len(starts) == 1
    assert not any(word.startswith('resume=') for word in starts[0])


def test_a_related_card_waits_for_an_episode_resume_already_in_startup(project, monkeypatch):
    from metaform.modules import dispatch as package

    first = assigned(project, monkeypatch, 'Original contribution.')
    SERVICE.bind(ctx(project), first['assignment_id'], 'old')
    with own(ctx(project)).tables() as tx:
        update(tx, first, state='delivered')
    starting = assigned(project, monkeypatch, 'Related contribution starting.', previous=first['work_id'])
    other = assigned(project, monkeypatch, 'Another related contribution.', previous=first['work_id'])
    monkeypatch.setattr(orchestration, 'service', lambda ctx: SERVICE)
    monkeypatch.setattr(package, 'launches', lambda: [{'project': 'proj', 'work_id': starting['work_id'],
                                                     'pid': 123, 'lease': 'starting'}])
    monkeypatch.setattr(orchestration, '_row', lambda *args, **kwargs: pytest.fail('Ignored active episode startup'))
    launched = orchestration.TRANSPORT.launch(ctx(project), other, 'other-launch')
    assert launched['state'] == 'queued' and 'already starting' in launched['reason']


def test_a_user_can_reach_the_same_agent_through_its_original_work_session_link(project, monkeypatch):
    from dataclasses import replace

    from metaform.modules import dispatch as package

    original, current, _, _ = shared_caller(project, monkeypatch)
    active = {'work_id': current['work_id'], 'session_id': 'shared', 'agent': 'codex', 'state': 'running'}
    monkeypatch.setattr(package, 'sessions', lambda *args, **kwargs: [active])
    called = replace(ctx(project), module='dispatch', nouns={'session': f'{original["work_id"]}:shared'})
    assert package.talk(called) == active
    assert SERVICE.session_bound(ctx(project), 'shared', original['work_id'])
    # A later fresh owner does not destroy the shared context's historical identity.
    with own(ctx(project)).tables() as tx:
        update(tx, original, owner_session_id='fresh-original')
    assert package.talk(called) == active
    unrelated = assigned(project, monkeypatch, 'This card never used the chosen session.')
    from metaform.module import Stop
    with pytest.raises(Stop, match='No agent session'):
        package.talk(replace(called, nouns={'session': f'{unrelated["work_id"]}:shared'}))


@pytest.mark.parametrize(('resume_enabled', 'supports_load'), [(False, True), (True, False), (True, True)])
def test_workspace_preparation_runs_only_for_a_supported_selected_resume(
        project, monkeypatch, resume_enabled, supports_load):
    import importlib
    from dataclasses import replace

    from metaform.modules import dispatch as package

    merge = importlib.import_module('metaform.modules.dispatch.merge')
    first = assigned(project, monkeypatch, 'Prior workspace contribution.')
    SERVICE.bind(ctx(project), first['assignment_id'], 'old')
    with own(ctx(project)).tables() as tx:
        update(tx, first, state='suspended')
    target = assigned(project, monkeypatch, 'Related workspace contribution.', previous=first['work_id'])
    stream = SERVICE.episode_context(ctx(project), target)
    old = {'work_id': first['work_id'], 'session_id': 'old', 'agent': 'codex', 'state': 'ended'}
    monkeypatch.setattr(orchestration, 'service', lambda ctx: SERVICE)
    monkeypatch.setattr(package, 'launches', list)
    monkeypatch.setattr(package, 'sessions', lambda *args, **kwargs: [])
    monkeypatch.setattr(package, 'admit', lambda *args, **kwargs: None)
    monkeypatch.setattr(package, 'startable', lambda *args, **kwargs: None)
    monkeypatch.setattr(orchestration.Transport, 'runtime_settings', lambda *args: {'agent': 'codex'})
    monkeypatch.setattr(orchestration, '_row', lambda *args, **kwargs: None)
    monkeypatch.setattr(orchestration, 'episode_row', lambda *args, **kwargs: (old, stream))
    monkeypatch.setattr(package, 'session_state', lambda *args: {
        'cwd': str(project[1] / '.worktrees' / 'original'), 'capabilities': {'load': supports_load}})
    prepared = []

    def prepare(*args):
        prepared.append(args)
        return {'baseline': 'current-start', 'source_branch': 'metaform/prior', 'source_candidate': 'prior-candidate'}

    monkeypatch.setattr(merge, 'episode_workspace', prepare)
    launched = []
    monkeypatch.setattr(package, 'resume_spawn', lambda *args, **kwargs: launched.append(('resume', args[3])) or {'pid': 1})
    monkeypatch.setattr(package, 'start_runner', lambda *args, **kwargs: launched.append(('new', args[4])) or {'pid': 1})
    called = replace(ctx(project), switches={'dispatch_resume_chats': resume_enabled})
    orchestration.TRANSPORT.launch(called, target, 'workspace-launch')
    should_resume = resume_enabled and supports_load
    assert len(prepared) == int(should_resume)
    assert launched[0][0] == ('resume' if should_resume else 'new')
    if should_resume:
        assert {'episode_source_candidate=prior-candidate', 'episode_source_branch=metaform/prior',
                'episode_workspace_base=current-start'} <= set(launched[0][1])
