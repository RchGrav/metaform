"""Peers can adjust or cancel tickets without creator or procedural-role ownership."""
import importlib

import pytest

from metaform.data import Node, Store
from metaform.module import Stop, context

pytestmark = pytest.mark.kind('fixture')


@pytest.fixture
def peer_ticket(run, project_folder):
    run('enable', 'dispatch', cwd=project_folder)
    store = Store('proj')
    store.layer('parts', 'test', 'Parts.', mutable=True, hideable=True, ready=True)
    store.add_element('parts', 'code.Example')
    ticket = store.add_work(Node('element', 'code.Example'), None, task='Example task.', title='Example').id
    return project_folder, store, ticket


@pytest.mark.parametrize('identity', [{'METAFORM_TASK': 'peer-task'}, {'METAFORM_SESSION': 'peer-session'}])
def test_peer_tune_saves_runtime_with_its_actual_identity(peer_ticket, identity):
    folder, _, ticket = peer_ticket
    module = importlib.import_module('metaform.modules.dispatch')
    ctx = context('dispatch', folder, surface='mcp', identity=identity,
                  nouns={'id': ticket, 'model': 'adapter-model', 'effort': 'adapter-effort'})

    result = module.tune(ctx)

    assert (result['model'], result['effort']) == ('adapter-model', 'adapter-effort')
    assert result['decision']['decider'] == next(iter(identity.values()))
    assert all('kept unchecked' in notice['message'] for notice in result['notices'])


@pytest.mark.parametrize('identity', [{'METAFORM_TASK': 'peer-task'}, {'METAFORM_SESSION': 'peer-session'}])
def test_peer_cancel_preserves_cancelled_outcome_and_actual_caller(peer_ticket, identity):
    folder, store, ticket = peer_ticket
    module = importlib.import_module('metaform.modules.dispatch')
    ctx = context('dispatch', folder, surface='mcp', identity=identity, nouns={'id': ticket})

    result = module.cancel(ctx)

    closed = store.ticket(ticket).work
    assert result['state'] == 'cancelled' and result['session'] is None
    assert closed.done and closed.outcome == 'cancelled' and closed.resolution == 'Cancelled.'
    with Store('proj', module='map').tables(write=False) as tx:
        numbered = dict(tx.get('numbered', {'kind': 'work', 'item_id': ticket}))
    assert numbered['why'] == f'Cancelled by {next(iter(identity.values()))}.'
    assert not store.work(open=True, limit=0).results
    with pytest.raises(Stop, match='was done'):
        module.cancel(ctx)
