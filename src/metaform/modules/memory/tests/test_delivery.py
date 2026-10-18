"""Memory bodies reach actual MCP responses once per identity/revision/context epoch, with relevant live notices."""
from __future__ import annotations

import asyncio
import json

import pytest

from metaform import events
from metaform.data import Store
from metaform.module import Context, advance_agent_context, record_agent_context
from metaform.modules.mcp import shaping
from metaform.modules.mcp.server import Watch, answer

pytestmark = pytest.mark.kind('simulation')

A = 'code.manager.route'
B = 'code.probe.echo'


@pytest.fixture
def project(run, tmp_path):
    folder = tmp_path / 'delivery-project'
    folder.mkdir()
    run('add', 'project', 'memory-delivery', str(folder))
    store = Store('memory-delivery')
    with store.atomic():
        store.layer('intake', 'intake', 'Functional map.', kind='intake', mutable=False,
                    hideable=False, ready=True)
        store.add_element('intake', A, name_length=2, role='DE')
        store.add_element('intake', B, name_length=2, role='SE')
        store.add_join('intake', A, B, purpose='Know a route is alive.', ef='Returns the echo.')
    return folder


def reading(project, *, session=None, **nouns):
    return Context('memory', project, project='memory-delivery', store=Store('memory-delivery', module='memory'),
                   session=session, nouns=nouns)


def make(project, name='shared', address=A, text='Routes remain usable.'):
    from metaform.modules.memory import create_entities
    return create_entities(reading(project, node=f'element:{address}', entities=[
        {'name': name, 'entityType': 'behavior', 'observations': [text], 'why': 'Supports delivery.'}]))


def mcp_read(project, address=A, *, session='worker', name='memory_read_unread', shape=None, **arguments):
    result = asyncio.run(answer(project, name, {'node': f'element:{address}', **arguments},
                                session=session, shape=shape))
    assert result[0] is False, result[1]
    return result[2]


def test_same_identity_at_two_entries_is_delivered_once_but_distinct_memories_remain_distinct(project):
    from metaform.modules.memory import join
    make(project)
    join(reading(project, entity='shared', node=f'element:{B}'))
    make(project, name='separate', address=B)
    assert [one['name'] for one in mcp_read(project)['entities']] == ['shared']
    second = mcp_read(project, B)
    assert [one['name'] for one in second['entities']] == ['separate']
    assert mcp_read(project, A) == {'entities': [], 'relations': []}
    assert {one['name'] for one in mcp_read(project, B, session='replacement')['entities']} == {'shared', 'separate'}


def test_count_and_shaped_away_body_do_not_mark_read(project):
    from metaform.modules.memory import node_count
    make(project)
    ctx = reading(project, session='worker')
    first = node_count(ctx, (A,))[0]
    assert first.at[A] == (1, 1, 0)
    assert first.updated[A] == 0
    assert node_count(ctx, (A,))[0].at[A] == (1, 1, 0)
    shape = shaping.Shape(view='count')
    mcp_read(project, name='memory_read_graph', shape=shape)
    assert node_count(ctx, (A,))[0].at[A] == (1, 1, 0)
    assert mcp_read(project)['entities'][0]['name'] == 'shared'
    assert node_count(ctx, (A,))[0].at[A] == (1, 0, 0)


def test_nested_map_and_item_reads_use_transport_identity_and_ack_only_emitted_bodies(project, monkeypatch):
    """HTTP callers keep their identity through module hooks; a count/list cannot acknowledge a hidden body."""
    from metaform.module import collecting_agent_context, items_page
    from metaform.modules.memory import node_count

    made = make(project)
    monkeypatch.setenv('METAFORM_SESSION', 'unrelated-process-session')

    def read(name, arguments, session, shape=None):
        result = asyncio.run(answer(project, name, arguments, session=session, shape=shape))
        assert result[0] is False, result[1]
        return result[2]

    args = {'address': A, 'contents': True}
    read('map_where', args, 'map-http-worker', shaping.Shape(view='count'))
    assert node_count(reading(project, session='map-http-worker'), (A,))[0].at[A][1] == 1
    shown = read('map_where', args, 'map-http-worker')
    assert 'Routes remain usable.' in json.dumps(shown)
    assert node_count(reading(project, session='map-http-worker'), (A,))[0].at[A][1] == 0
    assert node_count(reading(project, session='unrelated-process-session'), (A,))[0].at[A][1] == 1

    with collecting_agent_context('item-http-worker') as receipts:
        listed = items_page(project, A, project='memory-delivery')
    assert listed and not receipts
    assert node_count(reading(project, session='item-http-worker'), (A,))[0].at[A][1] == 1
    with Store('memory-delivery', module='memory').tables(write=False) as tx:
        number = tx.rows('joins', {'entity': made['entities'][0]['name']}, limit=1).results[0]['number']
    item = {'item': f'{A}#{number:x}'}
    read('map_item', item, 'item-http-worker', shaping.Shape(view='count'))
    assert node_count(reading(project, session='item-http-worker'), (A,))[0].at[A][1] == 1
    assert 'Routes remain usable.' in read('map_item', item, 'item-http-worker')['body']
    assert mcp_read(project, session='item-http-worker') == {'entities': [], 'relations': []}


def test_same_count_correction_notifies_grounded_agent_and_notice_does_not_ack_body(project):
    from metaform.modules.memory import add_observations, delete_observations, delivery, node_count
    make(project)
    mcp_read(project)
    ctx = reading(project, session='worker')
    before = delivery.revision('memory-delivery', A)
    events.announce(project, 'cli')

    def correct():
        delete_observations(reading(project, deletions=[{'entityName': 'shared',
                                                         'observations': ['Routes remain usable.']}]))
        add_observations(reading(project, observations=[{'entityName': 'shared',
                                                        'contents': ['Routes survive interrupted work.']}]))
    _, emitted = events.announced(project, 'cli', correct)
    relevant = next(one for one in emitted if 'memory.changed' in one.get('kinds', []))
    assert relevant['session_ids'] == ['worker']
    assert f'memory:{A}' in relevant['kinds']
    assert delivery.revision('memory-delivery', A) != before
    count = node_count(ctx, (A,))[0]
    assert count.at[A] == (1, 1, 0) and count.updated[A] == 1
    notice = delivery.notices(ctx, relevant)
    assert 'memory read_unread' in notice['text']
    record_agent_context(project, 'worker', notice['components'], project='memory-delivery',
                         epoch=notice['epoch'], channel='normal_turn')
    assert delivery.notices(ctx, relevant)['components'] == []
    assert node_count(ctx, (A,))[0].at[A][1] == 1
    assert mcp_read(project)['entities'][0]['observations'] == ['Routes survive interrupted work.']
    assert node_count(ctx, (A,))[0].at[A][1] == 0


def test_inspection_by_identity_registers_its_functional_entry_and_each_same_count_revision_notifies(project):
    from metaform.modules.memory import add_observations, delete_observations, delivery

    make(project)
    shown = asyncio.run(answer(project, 'memory_open_nodes', {'names': ['shared']}, session='inspector'))
    assert shown[0] is False and shown[2]['entities'][0]['name'] == 'shared'
    ctx = reading(project, session='inspector')
    previous = 'Routes remain usable.'
    identities = []
    for current in ('Routes retain their requested output.', 'Routes restore their requested output.'):
        delete_observations(reading(project, deletions=[{'entityName': 'shared', 'observations': [previous]}]))
        add_observations(reading(project, observations=[{'entityName': 'shared', 'contents': [current]}]))
        notice = delivery.notices(ctx)
        assert len(notice['components']) == 1 and notice['entries'][0]['receiver'] == A
        identities.append(notice['components'][0]['name'])
        record_agent_context(project, 'inspector', notice['components'], project='memory-delivery',
                             epoch=notice['epoch'], channel='normal_turn')
        previous = current
    assert len(set(identities)) == 2
    assert mcp_read(project, session='inspector')['entities'][0]['observations'] == [previous]


def test_revision_written_during_response_remains_unread(project, monkeypatch):
    from metaform.modules.mcp.server import tools
    from metaform.modules.memory import add_observations, node_count

    make(project)
    served = tools(project)['memory_read_unread'][1].run.__globals__
    original = served['_delivered']
    changed = False

    def during_read(ctx, whole, key=None, *, unread=False):
        nonlocal changed
        result = original(ctx, whole, key, unread=unread)
        if not changed:
            changed = True
            add_observations(reading(project, observations=[{'entityName': 'shared',
                                                            'contents': ['A later revision arrived.']}]))
        return result
    monkeypatch.setitem(served, '_delivered', during_read)
    first = mcp_read(project)
    assert changed
    assert first['entities'][0]['observations'] == ['Routes remain usable.']
    assert node_count(reading(project, session='worker'), (A,))[0].updated[A] == 1
    second = mcp_read(project)
    assert second['entities'][0]['observations'] == ['Routes remain usable.', 'A later revision arrived.']
    assert mcp_read(project) == {'entities': [], 'relations': []}


def test_entity_and_relation_deletions_are_retrievable_and_new_sessions_receive_no_old_withdrawals(project):
    from metaform.modules.memory import create_relations, delete_entities, delete_relations
    make(project, name='route')
    make(project, name='echo', address=B)
    edge = {'from': 'echo', 'to': 'route', 'relationType': 'checks'}
    create_relations(reading(project, relations=[edge]))
    assert mcp_read(project)['relations'] == [edge]
    assert mcp_read(project, B)['relations'] == []
    delete_relations(reading(project, relations=[edge]))
    removed = mcp_read(project, B)
    assert removed == {'entities': [], 'relations': [], 'deleted_relations': [edge]}
    assert mcp_read(project, A) == {'entities': [], 'relations': []}
    create_relations(reading(project, relations=[edge]))
    mcp_read(project)
    delete_entities(reading(project, entityNames=['route']))
    result = mcp_read(project)
    assert result['deleted_entities'] == ['route'] and result['deleted_relations'] == [edge]
    assert mcp_read(project, session='new') == {'entities': [], 'relations': []}
    with Store('memory-delivery', module='memory').tables(write=False) as tx:
        assert not tx.rows('joins', {'entity': 'route'}, limit=0).results
        assert not tx.rows('relations', limit=0).results


def test_compaction_makes_current_memory_due_again(project):
    make(project)
    mcp_read(project)
    assert mcp_read(project)['entities'] == []
    advance_agent_context(project, 'worker', project='memory-delivery', reason='compaction')
    assert mcp_read(project)['entities'][0]['name'] == 'shared'


def test_separate_cli_processes_share_memory_receipts_and_epoch(project, run):
    from metaform.modules.memory import join
    make(project)
    join(reading(project, entity='shared', node=f'element:{B}'))
    env = {'METAFORM_SESSION': 'separate-process-worker'}
    first = run('memory', 'read_unread', f'node=element:{A}', '--json', cwd=project, env=env, isolated=True)
    assert json.loads(first.stdout)['entities'][0]['name'] == 'shared'
    second = run('memory', 'read_unread', f'node=element:{B}', '--json', cwd=project, env=env, isolated=True)
    assert json.loads(second.stdout) == {'entities': [], 'relations': []}


def test_memory_watcher_detects_correction_with_same_item_number_and_filters_unrelated_bursts(project, monkeypatch):
    from metaform.modules.memory import add_observations
    make(project)
    sent = []

    class Bus:
        async def publish(self, value):
            sent.append(value)

    watch = Watch(project, Bus(), lambda **value: value)
    uri = f'metaform://{A}'
    watch.project = 'memory-delivery'
    watch.latest[uri] = watch._number(uri)
    watch.memory_latest[uri] = watch._memory_revision(uri)
    watch.listeners[uri] = 1
    add_observations(reading(project, observations=[{'entityName': 'shared', 'contents': ['An updated observation.']}]))
    asyncio.run(watch.check())
    assert sent == [{'uri': uri}]
    calls = []
    monkeypatch.setattr(watch, '_number', lambda uri: calls.append(uri))
    monkeypatch.setattr(watch, '_memory_revision', lambda uri: calls.append(uri))
    for _ in range(100):
        watch._heard({'project': 'memory-delivery', 'tables': ['memory.observations'],
                      'kinds': ['memory.changed', 'memory:code.other']})
        watch._heard({'project': 'another', 'tables': ['memory.observations']})
        watch._heard({'project': 'memory-delivery', 'tables': ['memory.encounters']})
    assert calls == []
