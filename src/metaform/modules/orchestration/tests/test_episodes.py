"""Workstream continuity retains results and return routes independently of the current binding."""
from __future__ import annotations

import pytest

from metaform.data import Node, Store
from metaform.module import Stop
from metaform.modules.orchestration.state import SERVICE, Orchestration, own, update
from metaform.modules.orchestration.tests.test_orchestration import NODE, ctx
from tests.storekit import small_map

pytestmark = pytest.mark.kind('simulation')


@pytest.fixture
def project(store, project_folder):
    small_map(store)
    return store, project_folder


def assigned(project, monkeypatch, task, previous=None, role='researcher'):
    monkeypatch.setattr(Orchestration, 'prepare_runtime', lambda *args, **kwargs: True)
    store, _ = project
    work = store.add_work(Node('element', NODE), None, task=task)
    held = SERVICE.ensure(ctx(project), work.id, role=role)
    SERVICE.episode(ctx(project), work.id, continue_from=previous)
    return held


def test_three_related_cards_keep_one_session_and_independent_results(project, monkeypatch):
    held = assigned(project, monkeypatch, 'Correct countdown.')
    episode = SERVICE.episode(ctx(project), held['work_id'])['episode_id']
    results = []
    for index in range(3):
        if index:
            held = assigned(project, monkeypatch, f'Continue correction {index}.', previous=held['work_id'])
        bound = SERVICE.bind(ctx(project), held['assignment_id'], 'retained-context', runner='retained-runner')
        assert SERVICE.assignment(ctx(project), session_id='retained-runner')['work_id'] == held['work_id']
        with own(ctx(project)).tables() as tx:
            update(tx, bound, state='delivered', result={'summary': f'Outcome {index}'}, evidence=[f'candidate-{index}'])
        results.append(held['assignment_id'])
    with own(ctx(project)).tables(write=False) as tx:
        history = tx.rows('binding_history', {'session_id': 'retained-context'}, limit=0).results
        assert len(history) == 3 and {one['episode_id'] for one in history} == {episode}
        assert [tx.get('assignments', {'assignment_id': ident})['result']['summary']
                for ident in results] == ['Outcome 0', 'Outcome 1', 'Outcome 2']
        assert tx.get('sessions', {'session_id': 'retained-context'})['assignment_id'] == held['assignment_id']


def test_unrelated_running_or_different_responsibility_does_not_take_context(project, monkeypatch):
    first = assigned(project, monkeypatch, 'Implement countdown.')
    SERVICE.bind(ctx(project), first['assignment_id'], 'one')
    second = assigned(project, monkeypatch, 'Related follow-up.', previous=first['work_id'])
    with pytest.raises(Stop, match='active workstream'):
        SERVICE.bind(ctx(project), second['assignment_id'], 'one')
    with own(ctx(project)).tables() as tx:
        update(tx, first, state='delivered')
    unrelated = assigned(project, monkeypatch, 'Unrelated work.')
    with pytest.raises(Stop, match='active workstream'):
        SERVICE.bind(ctx(project), unrelated['assignment_id'], 'one')
    review = assigned(project, monkeypatch, 'Independently inspect.', previous=first['work_id'], role='architect')
    with pytest.raises(Stop, match='responsibilities'):
        SERVICE.bind(ctx(project), review['assignment_id'], 'one')
    SERVICE.bind(ctx(project), review['assignment_id'], 'independent-review')
    assert SERVICE.assignment(ctx(project), session_id='one')['assignment_id'] == first['assignment_id']


def test_fresh_context_retains_episode_and_delayed_return_targets_original_assignment(project, monkeypatch):
    first = assigned(project, monkeypatch, 'Initial implementation.')
    SERVICE.bind(ctx(project), first['assignment_id'], 'old')
    with own(ctx(project)).tables() as tx:
        update(tx, first, state='waiting')
    follow = assigned(project, monkeypatch, 'Related local work.', previous=first['work_id'])
    SERVICE.bind(ctx(project), follow['assignment_id'], 'old')
    event = SERVICE.queue_message(ctx(project), first['assignment_id'], {
        'kind': 'child_return', 'text': 'Original child evidence.'}, key='original-return')
    assert event['assignment_id'] == first['assignment_id']
    stream = SERVICE.episode(ctx(project), follow['work_id'], fresh=True)
    assert stream['fresh_context'] is True
    SERVICE.bind(ctx(project), follow['assignment_id'], 'fresh')
    resumed = SERVICE.episode(ctx(project), follow['work_id'])
    assert resumed['episode_id'] == stream['episode_id'] and resumed['fresh_context'] is False
    assert SERVICE.assignment(ctx(project), assignment_id=first['assignment_id'])['owner_session_id'] == 'old'
    with Store('proj', module='orchestration').tables(write=False) as tx:
        assert tx.get('transitions', {'transition_id': event['transition_id']})['assignment_id'] == first['assignment_id']
