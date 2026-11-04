"""Ticket runtime edits use public providers and preserve the caller's identity."""
import importlib
import time
from unittest.mock import Mock

import pytest

from metaform.data import Node, Store
from metaform.module import Stop, context, provided

pytestmark = pytest.mark.kind('fixture')


@pytest.fixture
def runtime_ticket(run, project_folder):
    run('enable', 'dispatch', cwd=project_folder)
    store = Store('proj')
    store.layer('parts', 'test', 'Parts.', mutable=True, hideable=True, ready=True)
    store.add_element('parts', 'code.Example')
    ticket = store.add_work(Node('element', 'code.Example'), None, task='Implement the example.', title='Example').id
    module = importlib.import_module('metaform.modules.dispatch')
    with module.own_store(store).tables() as tx:
        tx.insert('catalog', {'agent': 'codex', 'version': 'fixture', 'seen': '2026-10-24T00:00:00Z',
                             'seq': time.time_ns(), 'settings': [
            {'id': 'model', 'name': 'Model', 'category': 'model', 'type': 'select',
             'options': [{'value': 'native-model', 'name': 'Native Model'}]},
            {'id': 'effort', 'name': 'Effort', 'category': 'thought_level', 'type': 'select',
             'options': [{'value': 'native-effort', 'name': 'Native Effort'}]}]})
    return project_folder, store, ticket


@pytest.mark.parametrize('identity', [{'METAFORM_TASK': 'unrelated-peer-task'},
                                    {'METAFORM_SESSION': 'unrelated-peer-session'}])
def test_agent_runtime_edit_uses_public_provider_with_actual_provenance(runtime_ticket, monkeypatch, identity):
    folder, store, ticket = runtime_ticket
    module = importlib.import_module('metaform.modules.map')
    offered = provided(folder, 'ticket.runtime.edit')
    assert len(offered) == 1 and offered[0][0] == 'dispatch'
    edit = Mock(wraps=offered[0][1])
    original = module.provided
    monkeypatch.setattr(module, 'provided', lambda path, kind: [('dispatch', edit)] if kind == 'ticket.runtime.edit'
                        else original(path, kind))
    ctx = context('map', folder, surface='mcp', identity=identity,
                  nouns={'op': 'edit', 'id': ticket, 'agent': 'codex',
                         'model': 'native-model', 'effort': 'native-effort'})

    module.work(ctx)

    assert edit.call_count == 1 and edit.call_args.args[:2] == (ctx, ticket)
    saved = module.TICKET_RUNTIME.read(ctx, ticket)
    assert (saved['agent'], saved['model'], saved['effort']) == ('codex', 'native-model', 'native-effort')
    assert saved['decision']['decider'] == next(iter(identity.values()))
    assert saved['decision']['overrides'] == {'agent': 'codex', 'model': 'native-model', 'effort': 'native-effort'}
    assert store.ticket(ticket).work.task == 'Implement the example.'


def test_native_catalog_rejects_unknown_model_without_saving_partial_edit(runtime_ticket):
    folder, _, ticket = runtime_ticket
    module = importlib.import_module('metaform.modules.map')
    ctx = context('map', folder, surface='mcp', identity={'METAFORM_TASK': 'peer'},
                  nouns={'op': 'edit', 'id': ticket, 'agent': 'codex', 'model': 'invented-model'})
    before = module.TICKET_RUNTIME.read(ctx, ticket)

    with pytest.raises(Stop, match='invented-model'):
        module.work(ctx)

    assert module.TICKET_RUNTIME.read(ctx, ticket) == before


def test_map_without_runtime_edit_provider_saves_values_and_caller(runtime_ticket, run):
    folder, _, ticket = runtime_ticket
    run('disable', 'dispatch', cwd=folder)
    assert provided(folder, 'ticket.runtime.edit') == []
    module = importlib.import_module('metaform.modules.map')
    ctx = context('map', folder, surface='mcp', identity={'METAFORM_TASK': 'peer-without-dispatch'},
                  nouns={'op': 'edit', 'id': ticket, 'model': 'deferred-model', 'effort': 'deferred-effort'})

    module.work(ctx)

    saved = module.TICKET_RUNTIME.read(ctx, ticket)
    assert (saved['model'], saved['effort']) == ('deferred-model', 'deferred-effort')
    assert saved['decision']['decider'] == 'peer-without-dispatch'
