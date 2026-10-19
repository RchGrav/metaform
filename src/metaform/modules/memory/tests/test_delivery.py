"""Memory bodies reach actual MCP responses once per identity/revision/context epoch, with relevant live notices."""
from __future__ import annotations

import asyncio
import json

import pytest

from metaform import events
from metaform.data import Store
from metaform.module import Context, advance_agent_context
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


def test_same_count_correction_is_unread_to_a_grounded_agent_until_it_reads_the_body(project):
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
    assert 'memory read_unread' in count.legend and node_count(ctx, (A,))[0].at[A][1] == 1, 'a count reads no body'
    assert mcp_read(project)['entities'][0]['observations'] == ['Routes survive interrupted work.']
    assert node_count(ctx, (A,))[0].at[A][1] == 0


def test_a_write_is_never_an_unread_notice_to_the_session_that_wrote_it(project):
    """Code.dispatcher.agent#5b: a worker that recorded at its node was given one more turn telling it of its own
    memory. The writer receives what it wrote; another agent's change it has not read stays unread to it."""
    from metaform.modules.memory import add_observations, node_count
    make(project)
    mcp_read(project)
    mcp_read(project, session='other')
    events.announce(project, 'cli')

    def observe(session, text):
        add_observations(reading(project, session=session, observations=[{'entityName': 'shared',
                                                                          'contents': [text]}]))
    _, emitted = events.announced(project, 'cli', observe, 'worker', 'Routes answer within a second.')
    relevant = next(one for one in emitted if 'memory.changed' in one.get('kinds', []))
    assert relevant['session_ids'] == ['other'], 'the writer is not told of its own write'
    assert node_count(reading(project, session='worker'), (A,))[0].at[A][1] == 0
    assert node_count(reading(project, session='other'), (A,))[0].at[A][1] == 1
    observe('other', 'Routes log each echo.')
    observe('worker', 'Routes retry once.')
    assert node_count(reading(project, session='worker'), (A,))[0].at[A][1] == 1, \
        "another's change the writer had not read stays unread"


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
    restored = mcp_read(project)
    assert restored['relations'] == [] and len(restored['restored']) == 1
    assert restored['restored'][0]['name'].startswith('memory:relation:')
    delete_entities(reading(project, entityNames=['route']))
    result = mcp_read(project)
    assert result['deleted_entities'] == ['route'] and len(result['restored']) == 1
    assert result['restored'][0]['fingerprint'] != restored['restored'][0]['fingerprint']
    assert mcp_read(project) == {'entities': [], 'relations': []}, 'The active version reference is delivered once.'
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


def test_author_knows_its_writes_but_does_not_acknowledge_other_agents_changes(project):
    from metaform.modules.memory import add_observations, node_count

    def write(name, arguments):
        result = asyncio.run(answer(project, name, arguments, session='author'))
        assert result[0] is False, result[1]

    # Counts register interest without acknowledging bodies. The writer already knows what it supplies.
    ctx = reading(project, session='author')
    node_count(ctx, (A,))
    write('memory_create_entities', {'node': f'element:{A}', 'entities': [
        {'name': 'own', 'entityType': 'behavior', 'observations': ['Routes remain usable.'],
         'why': 'Supports delivery.'}]})
    assert mcp_read(project, session='author')['entities'] == []
    assert mcp_read(project, session='peer')['entities'][0]['name'] == 'own'

    write('memory_add_observations', {'observations': [
        {'entityName': 'own', 'contents': ['Own correction.']},
        {'entityName': 'own', 'contents': ['Another fact in the same batch.']}]})
    assert mcp_read(project, session='author')['entities'] == []
    add_observations(reading(project, observations=[{'entityName': 'own', 'contents': ['Unseen peer correction.']}]))
    write('memory_add_observations', {'observations': [{'entityName': 'own', 'contents': ['Another own fact.']}]})
    assert 'Unseen peer correction.' in mcp_read(project, session='author')['entities'][0]['observations']

    write('memory_delete_observations', {'deletions': [{'entityName': 'own', 'observations': ['Own correction.']}]})
    assert mcp_read(project, session='author')['entities'] == []
    write('memory_delete_entities', {'entityNames': ['own']})
    assert not any(mcp_read(project, session='author').values())
    assert mcp_read(project, session='peer')['deleted_entities'] == ['own']


def test_memory_changes_are_read_contextually_without_an_extra_turn(project, monkeypatch):
    from unittest.mock import AsyncMock

    from metaform.module import context
    from metaform.modules.dispatch.runner import Session
    from metaform.modules.memory import add_observations

    make(project)
    ctx = context('dispatch', project, project='memory-delivery', session='worker')
    runner = Session(ctx, Store('memory-delivery', module='dispatch'), None, 'claude', [], prep=True)
    runner.runner, runner.session_id, runner.turns = 'worker', 'adapter', 1
    # Register the encounter without acknowledging the body. Edits stay unread until a contextual read.
    from metaform.modules.memory import node_count
    node_count(reading(project, session='worker'), (A,))

    async def scenario():
        for number in range(3):
            add_observations(reading(project, observations=[
                {'entityName': 'shared', 'contents': [f'Peer correction {number}.']}]))
            runner.changed_elsewhere({'project': 'memory-delivery', 'tables': ['memory.observations'],
                                      'kinds': ['memory.changed'], 'session_ids': ['worker']})
        assert not runner.pending, 'Memory changes must not schedule an automatic model turn.'
        result = await answer(project, 'memory_read_unread', {'node': f'element:{A}'}, session='worker')
        assert result[0] is False and result[2]['entities']
        assert 'Peer correction 2.' in result[2]['entities'][0]['observations']
        again = await answer(project, 'memory_read_unread', {'node': f'element:{A}'}, session='worker')
        assert again[0] is False and again[2] == {'entities': [], 'relations': []}
        await runner.prompted()

    runner.conn = type('Connection', (), {'prompt': AsyncMock(side_effect=AssertionError('Stale notice sent.'))})()
    monkeypatch.setattr(runner, 'changed', AsyncMock())
    monkeypatch.setattr(runner, 'note', AsyncMock())
    monkeypatch.setattr(runner, 'flush', AsyncMock())
    asyncio.run(scenario())
    runner.conn.prompt.assert_not_called()
    assert runner.turns == 0 and runner.active_turn is None and not runner.pending


def test_author_knows_relation_and_index_changes_while_peers_receive_withdrawals(project):
    make(project, name='route')
    make(project, name='echo', address=B)
    for session in ('author', 'peer'):
        mcp_read(project, session=session)
        mcp_read(project, B, session=session)
    edge = {'from': 'echo', 'to': 'route', 'relationType': 'checks'}
    def write(name, arguments):
        result = asyncio.run(answer(project, name, arguments, session='author'))
        assert result[0] is False, result[1]
        assert not any(mcp_read(project, session='author').values())
    write('memory_create_relations', {'relations': [edge]})
    assert mcp_read(project, session='peer')['relations'] == [edge]
    write('memory_delete_relations', {'relations': [edge]})
    assert mcp_read(project, session='peer')['deleted_relations'] == [edge]
    with Store('memory-delivery', module='memory').tables(write=False) as tx:
        link = tx.rows('joins', {'entity': 'route'}, limit=1).results[0]
    write('memory_unjoin', {'id': link['join_id']})
    assert mcp_read(project, session='peer')['withdrawn'][0]['name'] == 'route'


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


def test_the_notice_counts_what_read_unread_returns_for_a_memory_whose_citation_went_stale(project):
    """Code.store.memory, 2026-10-18: a memory with a stale citation was read with its `stale` lines, while the notice
    built its body without them, so it counted 1 unread, 1 updated, and read_unread came back empty."""
    from metaform.modules.memory import add_observations, create_entities, node_count
    (project / 'route.py').write_text('def route():\n    return 1\n')
    create_entities(reading(project, node=f'element:{A}', entities=[
        {'name': 'shared', 'entityType': 'behavior', 'observations': ['Routes return one.'], 'why': 'Supports it.',
         'cite': ['route.py:2']}]))
    (project / 'route.py').write_text('def route():\n    return 2\n')
    assert mcp_read(project)['entities'][0]['stale']
    ctx = reading(project, session='worker')
    assert node_count(ctx, (A,))[0].at[A][1] == 0
    assert mcp_read(project) == {'entities': [], 'relations': []}
    add_observations(reading(project, observations=[{'entityName': 'shared', 'contents': ['Routes changed.']}]))
    count = node_count(ctx, (A,))[0]
    assert (count.at[A][1], count.updated[A]) == (1, 1)
    assert [one['name'] for one in mcp_read(project)['entities']] == ['shared']


def test_a_memory_whose_cited_text_moves_again_is_not_read_again_and_one_whose_cited_text_changes_is(project):
    """Code.store.memory#18, 2026-10-19: a stale citation said 'the cited text is now at line N', so every edit above
    the cited text changed the memory's body and handed it to every agent at the node again, unchanged. The reader is
    still shown where it stands (#1c); a fresh citation going stale is an update."""
    from metaform.modules.memory import create_entities, node_count
    ctx = reading(project, session='worker')
    source = project / 'route.py'
    source.write_text('def route():\n    return 1\n')
    create_entities(reading(project, node=f'element:{A}', entities=[
        {'name': 'shared', 'entityType': 'behavior', 'observations': ['Routes return one.'], 'why': 'Supports it.',
         'cite': ['route.py:2']}]))
    assert 'stale' not in mcp_read(project)['entities'][0]
    source.write_text('# above\ndef route():\n    return 1\n')
    count = node_count(ctx, (A,))[0]
    assert (count.at[A][1], count.updated[A]) == (1, 1)
    assert mcp_read(project)['entities'][0]['stale'] == ['route.py:2: line 2 changed; the cited text is now at line 3']
    source.write_text('# above\n# and above\ndef route():\n    return 1\n')
    assert node_count(ctx, (A,))[0].at[A][1] == 0
    assert mcp_read(project) == {'entities': [], 'relations': []}
    assert mcp_read(project, session='another')['entities'][0]['stale'] == [
        'route.py:2: line 2 changed; the cited text is now at line 4']
    source.write_text('# above\n# and above\ndef route():\n    return 2\n')
    count = node_count(ctx, (A,))[0]
    assert (count.at[A][1], count.updated[A]) == (1, 1)
    assert mcp_read(project)['entities'][0]['stale'] == ['route.py:2: line 2 changed']


def test_a_memory_made_again_after_its_delete_is_read_once_and_not_withdrawn_again_at_another_node(project):
    """Code.store.memory#e, 2026-10-19: the withdrawal of a deleted memory stayed at a node its remade namesake did
    not reach, so reads there and where it was remade took turns returning the withdrawal and the body, unread forever.
    At that node it becomes an index withdrawal, read once; another memory's withdrawal is not touched."""
    from metaform.modules.memory import delete_entities, join
    make(project)
    join(reading(project, entity='shared', node=f'element:{B}'))
    make(project, name='separate', address=B)
    mcp_read(project)
    mcp_read(project, B)
    delete_entities(reading(project, node=f'element:{B}', entityNames=['separate']))
    assert mcp_read(project, B)['deleted_entities'] == ['separate']
    delete_entities(reading(project, node=f'element:{A}', entityNames=['shared']))
    make(project, text='Routes are remade.')
    store = Store('memory-delivery', module='memory')
    with store.tables(write=False) as tx:
        assert tx.get('withdrawals', {'receiver': B, 'provider': '', 'component': 'memory:entity:separate'})
    assert mcp_read(project)['entities'][0]['observations'] == ['Routes are remade.']
    assert mcp_read(project, B) == {'entities': [], 'relations': [], 'withdrawn': [{'name': 'shared', 'address': B}]}
    for _ in range(3):
        assert mcp_read(project, B) == {'entities': [], 'relations': []}
        assert mcp_read(project) == {'entities': [], 'relations': []}
