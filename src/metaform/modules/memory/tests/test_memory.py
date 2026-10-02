"""The memory module: a memory graph of its own, the MCP reference memory server's, presented at each node of the map
and tied to it by joins of type memory, BASE-040, LAYER-012, LAYER-013, STORE-020 and VIEW-034."""
from __future__ import annotations

import json

import pytest

from metaform.data import Node, Store

pytestmark = pytest.mark.kind('fixture')

REFERENCE = ('create_entities', 'create_relations', 'add_observations', 'delete_entities', 'delete_observations',
             'delete_relations', 'read_graph', 'search_nodes', 'open_nodes')
ROUTE = 'node=element:code.manager.route'
PROBE = 'node=element:code.probe.echo'


def intake(store):
    with store.atomic():
        layer = store.layer('intake-1', 'intake', 'The functional map.', kind='intake', mutable=False,
                            hideable=False, provenance={'module': 'intake'}, ready=True)
        store.add_element(layer.name, 'code.manager.route', name_length=2, role='DE')
        store.add_element(layer.name, 'code.probe.echo', name_length=2, role='SE')
        store.add_join(layer.name, 'code.manager.route', 'code.probe.echo', purpose='Know a route is alive.',
                       ef='Sends an echo.', relation='The probe checks the route.', observation='ICMP.')


@pytest.fixture
def mapped(run, tmp_path):
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    intake(Store('proj'))
    return folder


def m(run, verb, *args, cwd, ok=True):
    return run('memory', verb, *args, '--json', cwd=cwd, ok=ok)


def mj(run, verb, *args, cwd):
    return json.loads(m(run, verb, *args, cwd=cwd).stdout)


def entity(name, kind='behavior', *observations):
    return {'name': name, 'entityType': kind, 'observations': list(observations)}


def J(value):
    return json.dumps(value)


def where(run, address, cwd, *more):
    return json.loads(run('map', 'where', address, *more, '--json', cwd=cwd).stdout)


@pytest.mark.req('LAYER-013')
@pytest.mark.req('BASE-040')
def test_memory_offers_the_nine_commands_with_the_reference_names_and_argument_shapes(run, mapped):
    from metaform.modules.mcp.server import verb_schema
    from metaform.modules.memory import MODULE
    verbs = {verb.name: verb for verb in MODULE.verbs}
    assert set(REFERENCE) <= set(verbs)
    shapes = {name: verb_schema(verbs[name], mapped)['properties'] for name in REFERENCE}
    text, texts = {'type': 'string'}, {'type': 'array', 'items': {'type': 'string'}}

    def bare(schema):  # a schema without its descriptions, to compare with the reference's types
        if isinstance(schema, dict):
            return {key: bare(value) for key, value in schema.items() if key != 'description'}
        return schema
    reference = {
        'create_entities': {'entities': {'type': 'array', 'items': {'type': 'object', 'properties': {
            'name': text, 'entityType': text, 'observations': texts}, 'required': ['name', 'entityType', 'observations']}}},
        'create_relations': {'relations': {'type': 'array', 'items': {'type': 'object', 'properties': {
            'from': text, 'to': text, 'relationType': text}, 'required': ['from', 'to', 'relationType']}}},
        'add_observations': {'observations': {'type': 'array', 'items': {'type': 'object', 'properties': {
            'entityName': text, 'contents': texts}, 'required': ['entityName', 'contents']}}},
        'delete_entities': {'entityNames': texts},
        'delete_observations': {'deletions': {'type': 'array', 'items': {'type': 'object', 'properties': {
            'entityName': text, 'observations': texts}, 'required': ['entityName', 'observations']}}},
        'delete_relations': {'relations': {'type': 'array', 'items': {'type': 'object', 'properties': {
            'from': text, 'to': text, 'relationType': text}, 'required': ['from', 'to', 'relationType']}}},
        'read_graph': {}, 'search_nodes': {'query': text}, 'open_nodes': {'names': texts}}
    chassis = {'node', 'project', 'layers'}
    assert {name: {key: bare(value) for key, value in shape.items() if key not in chassis}
            for name, shape in shapes.items()} == reference
    assert shapes['create_entities']['entities']['items']['required'] == ['name', 'entityType', 'observations']
    assert shapes['create_relations']['relations']['items']['required'] == ['from', 'to', 'relationType']
    assert shapes['add_observations']['observations']['items']['required'] == ['entityName', 'contents']
    assert shapes['delete_entities']['entityNames'] == {'type': 'array', 'items': {'type': 'string'},
                                                        'description': 'An array of entity names to delete'}
    assert shapes['delete_observations']['deletions']['items']['required'] == ['entityName', 'observations']
    assert shapes['delete_relations']['relations']['items']['required'] == ['from', 'to', 'relationType']
    assert shapes['search_nodes']['query']['type'] == 'string'
    assert shapes['open_nodes']['names']['type'] == 'array'
    assert all('node' in shape and 'node' not in verb_schema(verbs[name], mapped)['required']
               for name, shape in shapes.items())


@pytest.mark.req('LAYER-013')
@pytest.mark.req('STORE-020')
def test_the_whole_graph_behaves_as_the_reference_memory_server(run, mapped):
    made = mj(run, 'create_entities', J([entity('route', 'part', 'Drifts.'), entity('probe', 'part'),
                                         entity('route', 'again')]), cwd=mapped)
    assert made == {'entities': [entity('route', 'part', 'Drifts.'), entity('probe', 'part')]}
    assert mj(run, 'create_entities', J([entity('route', 'part')]), cwd=mapped) == {'entities': []}
    missing = m(run, 'create_relations', J([{'from': 'route', 'to': 'ghost', 'relationType': 'uses'}]), cwd=mapped,
                ok=False)
    assert missing.returncode == 2 and 'Entity with name ghost not found' in missing.stderr
    relation = {'from': 'probe', 'to': 'route', 'relationType': 'checks'}
    assert mj(run, 'create_relations', J([relation, relation]), cwd=mapped) == {'relations': [relation]}
    assert mj(run, 'create_relations', J([relation]), cwd=mapped) == {'relations': []}
    added = mj(run, 'add_observations', J([{'entityName': 'route', 'contents': ['Drifts.', 'Holds 25 routes.']}]),
               cwd=mapped)
    assert added == {'results': [{'entityName': 'route', 'addedObservations': ['Holds 25 routes.']}]}
    refused = m(run, 'add_observations', J([{'entityName': 'ghost', 'contents': ['x']}]), cwd=mapped, ok=False)
    assert 'Entity with name ghost not found' in refused.stderr
    assert mj(run, 'read_graph', cwd=mapped) == {
        'entities': [entity('route', 'part', 'Drifts.', 'Holds 25 routes.'), entity('probe', 'part')],
        'relations': [relation]}
    assert mj(run, 'search_nodes', 'HOLDS', cwd=mapped) == {
        'entities': [entity('route', 'part', 'Drifts.', 'Holds 25 routes.')], 'relations': [relation]}
    assert mj(run, 'open_nodes', J(['probe', 'ghost']), cwd=mapped) == {'entities': [entity('probe', 'part')],
                                                                        'relations': [relation]}
    said = mj(run, 'delete_observations', J([{'entityName': 'route', 'observations': ['Drifts.', 'never']}]),
              cwd=mapped)
    assert said == {'success': True, 'message': 'Deleted 1 of 2 observations.'}
    said = mj(run, 'delete_entities', J(['route', 'ghost']), cwd=mapped)
    assert said == {'success': True, 'message': 'Deleted 1 of 2 entities. Not found: ghost'}
    assert mj(run, 'read_graph', cwd=mapped) == {'entities': [entity('probe', 'part')], 'relations': []}
    mj(run, 'create_entities', J([entity('route', 'part')]), cwd=mapped)
    mj(run, 'create_relations', J([relation]), cwd=mapped)
    assert mj(run, 'delete_relations', J([relation]), cwd=mapped) == {'success': True,
                                                                     'message': 'Relations deleted successfully'}
    assert mj(run, 'read_graph', cwd=mapped)['relations'] == []


@pytest.mark.req('LAYER-013')
@pytest.mark.req('STORE-020')
def test_a_memory_entity_is_never_an_element_of_the_map(run, mapped):
    """Replaces the test that create-entities made an element in the memory layer: Rich, 2026-10-02, the memories
    are addressed not as another segment off of the namespace."""
    before = Store('proj').graph(raw=True, limit=0)
    mj(run, 'create_entities', J([entity('code.watchdog', 'element', 'Barks.')]), cwd=mapped)
    mj(run, 'create_entities', J([entity('code.manager.route.ghost', 'part')]), ROUTE, cwd=mapped)
    assert Store('proj').element('code.watchdog', raw=True) is None
    assert Store('proj').element('code.manager.route.ghost', raw=True) is None
    assert Store('proj').graph(raw=True, limit=0) == before
    assert Store('proj').layer_items('memory', limit=0).results == ()


@pytest.mark.req('LAYER-013')
@pytest.mark.req('BASE-040')
def test_at_a_node_the_commands_act_on_that_nodes_memories_tied_by_a_join_of_type_memory(run, mapped):
    made = mj(run, 'create_entities', J([entity('route ejection', 'behavior', 'Routes are ejected.')]), ROUTE,
              cwd=mapped)
    assert made == {'entities': [entity('route ejection', 'behavior', 'Routes are ejected.')]}
    assert mj(run, 'open_nodes', J(['route ejection']), ROUTE, cwd=mapped)['entities'] == [
        entity('route ejection', 'behavior', 'Routes are ejected.')]
    assert mj(run, 'read_graph', PROBE, cwd=mapped) == {'entities': [], 'relations': []}
    elsewhere = m(run, 'add_observations', J([{'entityName': 'route ejection', 'contents': ['x']}]), PROBE,
                  cwd=mapped, ok=False)
    assert 'Entity with name route ejection not found' in elsewhere.stderr
    joined = mj(run, 'joins', ROUTE, cwd=mapped)['joins']
    assert [(one['entity'], one['address'], one['orphaned']) for one in joined] == [
        ('route ejection', 'code.manager.route', False)]
    mj(run, 'create_entities', J([entity('echo cost', 'fact', 'Echoes are ejected cheaply.')]), PROBE, cwd=mapped)
    assert [one['name'] for one in mj(run, 'search_nodes', 'ejected', ROUTE, cwd=mapped)['entities']] == [
        'route ejection']
    crossing = m(run, 'create_relations', J([{'from': 'route ejection', 'to': 'echo cost', 'relationType': 'uses'}]),
                 ROUTE, cwd=mapped, ok=False)
    assert 'Entity with name echo cost not found' in crossing.stderr
    said = mj(run, 'delete_observations', J([{'entityName': 'echo cost', 'observations': ['Echoes are ejected cheaply.']}]),
              ROUTE, cwd=mapped)
    assert said['message'] == 'Deleted 0 of 1 observations. Entities not found: echo cost'
    mj(run, 'create_entities', J([entity('echo cost', 'ignored', 'ignored')]), ROUTE, cwd=mapped)
    assert mj(run, 'read_graph', ROUTE, cwd=mapped)['entities'][1] == entity('echo cost', 'fact',
                                                                            'Echoes are ejected cheaply.')
    assert mj(run, 'read_graph', cwd=mapped)['entities'] == [
        entity('route ejection', 'behavior', 'Routes are ejected.'), entity('echo cost', 'fact',
                                                                            'Echoes are ejected cheaply.')]


@pytest.mark.req('LAYER-013')
@pytest.mark.req('STORE-020')
def test_a_join_and_a_subtype_join_are_nodes_of_memory_keyed_by_their_receiver_and_provider(run, mapped):
    store = Store('proj')
    join_id = store.joins('code.manager.route').results[0].join_id
    with store.atomic():
        store.add_element('intake-1', 'code.probe.echo.timer', name_length=3, role='SE')
        held = store.add_subtype('intake-1', join_id, 'code.probe.echo.timer', purpose='Time the echo.')
    mj(run, 'create_entities', J([entity('echo timeout', 'fact', 'The echo times out after 1 s.')]),
       f'node=join:{join_id}', cwd=mapped)
    mj(run, 'create_entities', J([entity('timer drift', 'fact')]), f'node=join:{held.join_id}', cwd=mapped)
    assert mj(run, 'read_graph', f'node=join:{join_id}', cwd=mapped)['entities'] == [
        entity('echo timeout', 'fact', 'The echo times out after 1 s.')]
    joined = {one['entity']: (one['receiver'], one['provider']) for one in mj(run, 'joins', cwd=mapped)['joins']}
    assert joined == {'echo timeout': ('code.manager.route', 'code.probe.echo'),
                      'timer drift': ('code.manager.route', 'code.probe.echo.timer')}


@pytest.mark.req('LAYER-013')
@pytest.mark.req('MAP-015')
def test_memory_survives_a_clear_its_joins_are_orphaned_and_a_new_intake_at_the_same_address_reconnects_them(
        run, mapped):
    mj(run, 'create_entities', J([entity('route ejection', 'behavior', 'Routes are ejected.')]), ROUTE, cwd=mapped)
    run('clear', 'project', 'proj', '--confirm', cwd=mapped)
    assert mj(run, 'read_graph', cwd=mapped)['entities'] == [entity('route ejection', 'behavior',
                                                                    'Routes are ejected.')]
    lost = mj(run, 'orphaned', cwd=mapped)['joins']
    assert [(one['entity'], one['address']) for one in lost] == [('route ejection', 'code.manager.route')]
    intake(Store('proj'))
    assert mj(run, 'orphaned', cwd=mapped)['joins'] == []
    assert mj(run, 'read_graph', ROUTE, cwd=mapped)['entities'] == [entity('route ejection', 'behavior',
                                                                           'Routes are ejected.')]


@pytest.mark.req('LAYER-013')
@pytest.mark.req('MAP-015')
def test_a_memory_on_a_map_join_reconnects_by_its_two_addresses_and_only_lost_addresses_are_orphaned(run, mapped):
    join_id = Store('proj').joins('code.manager.route').results[0].join_id
    mj(run, 'create_entities', J([entity('echo timeout', 'fact', 'One second.')]), f'node=join:{join_id}', cwd=mapped)
    mj(run, 'create_entities', J([entity('probe cost', 'fact')]), PROBE, cwd=mapped)
    run('clear', 'project', 'proj', '--confirm', cwd=mapped)
    store = Store('proj')
    with store.atomic():
        layer = store.layer('intake-1', 'intake', 'The functional map.', kind='intake', mutable=False,
                            hideable=False, provenance={'module': 'intake'}, ready=True)
        store.add_element(layer.name, 'code.manager.route', name_length=2, role='DE')
        store.add_element(layer.name, 'code.probe.echo', name_length=2, role='SE')
        store.add_join(layer.name, 'code.manager.route', 'code.probe.echo', purpose='Know a route is alive.')
        store.add_element(layer.name, 'code.manager.table', name_length=2, role='SE')
    new_id = Store('proj').joins('code.manager.route').results[0].join_id
    assert new_id != join_id
    assert mj(run, 'read_graph', f'node=join:{new_id}', cwd=mapped)['entities'] == [
        entity('echo timeout', 'fact', 'One second.')]
    assert mj(run, 'orphaned', cwd=mapped)['joins'] == []
    store = Store('proj')
    with store.atomic():
        store.layer('intake-2', 'intake', 'Another map.', kind='intake', mutable=False, hideable=False,
                    provenance={'module': 'intake'}, ready=True)
    run('clear', 'project', 'proj', '--confirm', cwd=mapped)
    store = Store('proj')
    with store.atomic():
        layer = store.layer('intake-1', 'intake', 'The functional map.', kind='intake', mutable=False,
                            hideable=False, provenance={'module': 'intake'}, ready=True)
        store.add_element(layer.name, 'code.probe.echo', name_length=2, role='SE')
    lost = {one['entity']: one['orphaned'] for one in mj(run, 'joins', cwd=mapped)['joins']}
    assert lost == {'echo timeout': True, 'probe cost': False}
    assert [one['entity'] for one in mj(run, 'orphaned', cwd=mapped)['joins']] == ['echo timeout']


@pytest.mark.req('STORE-020')
@pytest.mark.req('LAYER-013')
def test_memory_is_kept_as_the_reference_keeps_it_in_the_order_it_was_made(run, mapped):
    """Rich, 2026-10-02: "I'm not convinced there is any benefit to dating memories, by keeping them how agents are
    used to using them I think its probably the best". The graph read and the tables hold what the reference holds,
    entities, observations and relations in the order they were made, and the joins their node's address."""
    mj(run, 'create_entities', J([entity('route', 'part', 'Drifts.', 'Holds.'), entity('probe', 'part')]), ROUTE,
       cwd=mapped)
    mj(run, 'create_relations', J([{'from': 'route', 'to': 'probe', 'relationType': 'uses'},
                                   {'from': 'probe', 'to': 'route', 'relationType': 'checks'}]), cwd=mapped)
    whole = mj(run, 'graph', cwd=mapped)
    assert whole['entities'] == [
        {'name': 'route', 'entityType': 'part', 'observations': [{'content': 'Drifts.'}, {'content': 'Holds.'}]},
        {'name': 'probe', 'entityType': 'part', 'observations': []}]
    assert whole['relations'] == [{'from': 'route', 'to': 'probe', 'relationType': 'uses'},
                                  {'from': 'probe', 'to': 'route', 'relationType': 'checks'}]
    assert [sorted(one) for one in whole['joins']] == [['address', 'entity', 'join_id', 'orphaned', 'shows']] * 2
    assert mj(run, 'read_graph', cwd=mapped)['relations'] == whole['relations']
    from metaform.modules.memory import TABLES
    columns = {table.name: [column.name for column in table.columns] for table in TABLES.tables}
    assert columns['entities'] == ['name', 'entity_type', 'seq']
    assert columns['observations'] == ['entity', 'content', 'seq']
    assert columns['relations'] == ['source', 'target', 'relation_type', 'seq']
    assert columns['joins'] == ['join_id', 'entity', 'receiver', 'provider']


def memory_v1():
    from metaform.data import Column, Index, Table, Tables
    return Tables(version=1, tables=(
        Table('entities', place='project', key=('name',),
              columns=(Column('name', required=True), Column('entity_type', required=True),
                       Column('at', required=True)),
              indexes=(Index(('at',)),)),
        Table('observations', place='project', key=('entity', 'content'),
              columns=(Column('entity', required=True), Column('content', required=True),
                       Column('seq', 'int', required=True), Column('at', required=True)),
              indexes=(Index(('entity', 'seq')),)),
        Table('relations', place='project', key=('source', 'target', 'relation_type'),
              columns=(Column('source', required=True), Column('target', required=True),
                       Column('relation_type', required=True), Column('at', required=True)),
              indexes=(Index(('target',)), Index(('at',)))),
        Table('joins', place='project', key=('join_id',),
              columns=(Column('join_id', required=True), Column('entity', required=True),
                       Column('receiver', required=True), Column('provider', required=True, default=''),
                       Column('at', required=True)),
              indexes=(Index(('entity', 'receiver', 'provider'), unique=True), Index(('receiver', 'provider')),
                       Index(('provider',)))),
        Table('notes', place='project', key=('receiver', 'provider'),
              columns=(Column('receiver', required=True), Column('provider', required=True, default=''),
                       Column('text', required=True), Column('by'), Column('at', required=True))),
        Table('carried', place='project', key=('item_id',),
              columns=(Column('item_id', required=True), Column('at', required=True))),
    ))


@pytest.mark.req('STORE-045')
@pytest.mark.req('STORE-020')
def test_memory_kept_with_times_is_upgraded_keeping_every_memory_relation_join_and_note(run, mapped):
    """The memory module's tables change through the public table API's version and upgrade, STORE-045, and every
    memory, relation, join and note written at version 1 is kept."""
    import sqlite3

    from metaform.data.tables import TableTx, ensure, project_store, project_transaction
    declared = memory_v1()
    path = project_store('proj', 'memory')
    path.parent.mkdir(parents=True, exist_ok=True)
    when = '2026-10-02T12:00:00.000000Z'
    with project_transaction(path, write=True) as db:
        ensure(db, path, 'memory', declared, 'project')
        tx = TableTx('memory', declared, write=True, opener=lambda _: (db, path, True), bound='project')
        for name, kind in (('route', 'part'), ('probe', 'part')):
            tx.insert('entities', {'name': name, 'entity_type': kind, 'at': when})
        tx.insert('observations', {'entity': 'route', 'content': 'Drifts.', 'seq': 1, 'at': when})
        tx.insert('observations', {'entity': 'route', 'content': 'Holds.', 'seq': 2, 'at': when})
        tx.insert('relations', {'source': 'probe', 'target': 'route', 'relation_type': 'checks', 'at': when})
        tx.insert('joins', {'join_id': 'j1', 'entity': 'route', 'receiver': 'code.manager.route', 'provider': '',
                            'at': when})
        tx.insert('notes', {'receiver': 'code.manager.route', 'provider': '', 'text': 'Ask Rich first.', 'by': 'user',
                            'at': when})
    whole = mj(run, 'read_graph', cwd=mapped)
    assert sorted(whole['entities'], key=lambda one: one['name']) == [
        entity('probe', 'part'), entity('route', 'part', 'Drifts.', 'Holds.')]
    assert whole['relations'] == [{'from': 'probe', 'to': 'route', 'relationType': 'checks'}]
    assert [(one['join_id'], one['entity'], one['address']) for one in mj(run, 'joins', cwd=mapped)['joins']] == [
        ('j1', 'route', 'code.manager.route')]
    assert mj(run, 'read_graph', ROUTE, cwd=mapped)['entities'] == [entity('route', 'part', 'Drifts.', 'Holds.')]
    noted = mj(run, 'note', 'element:code.manager.route', cwd=mapped)['note']
    assert (noted['text'], noted['by']) == ('Ask Rich first.', 'user')
    db = sqlite3.connect(path)
    try:
        recorded = json.loads(db.execute("SELECT value FROM meta WHERE key='module:memory'").fetchone()[0])
        held = {table: [row[1] for row in db.execute(f'PRAGMA table_info("memory.{table}")')]
                for table in ('entities', 'observations', 'relations', 'joins')}
    finally:
        db.close()
    assert recorded['version'] == 2
    assert held == {'entities': ['name', 'entity_type', 'seq'], 'observations': ['entity', 'content', 'seq'],
                    'relations': ['source', 'target', 'relation_type', 'seq'],
                    'joins': ['join_id', 'entity', 'receiver', 'provider']}
    mj(run, 'create_entities', J([entity('echo', 'part')]), cwd=mapped)
    assert [one['name'] for one in mj(run, 'read_graph', cwd=mapped)['entities']][-1] == 'echo'


@pytest.mark.req('LAYER-012')
@pytest.mark.req('LAYER-007')
def test_agents_see_the_memory_joins_when_they_read_a_node_and_the_layer_named_memory_turns_them_off(run, mapped):
    """Replaces the check on the memory group of a node read: the same select and mask now turn off the memory joins
    the node read shows. Rich, 2026-10-02: Agent sees these joins; the orchestrator uses layer select."""
    mj(run, 'create_entities', J([entity('route ejection', 'behavior', 'Routes are ejected.')]), ROUTE, cwd=mapped)
    shown = where(run, 'code.manager.route', mapped)['memory']
    assert shown['entities'] == [entity('route ejection', 'behavior', 'Routes are ejected.')]
    node = json.loads(run('map', 'node', 'element:code.manager.route', '--json', cwd=mapped).stdout)
    assert node['memory']['entities'] == shown['entities']
    run('map', 'mask', 'code.manager', 'memory', cwd=mapped)
    assert 'memory' not in where(run, 'code.manager.route', mapped)
    assert mj(run, 'read_graph', ROUTE, cwd=mapped) == {'entities': [], 'relations': []}
    run('map', 'clear', 'code.manager', 'memory', 'mask', cwd=mapped)
    assert where(run, 'code.manager.route', mapped)['memory']['entities'] == shown['entities']
    assert 'memory' not in where(run, 'code.manager.route', mapped, '--layers', 'intake-1')
    run('map', 'select', 'code.manager.route', 'memory', cwd=mapped)
    assert where(run, 'code.manager.route', mapped, '--layers', 'intake-1')['memory']['entities'] == shown['entities']


@pytest.mark.req('LAYER-013')
def test_an_elements_read_shows_the_memories_on_the_joins_it_receives_and_provides(run, mapped):
    join_id = Store('proj').joins('code.manager.route').results[0].join_id
    mj(run, 'create_entities', J([entity('echo timeout', 'fact', 'One second.')]), f'node=join:{join_id}', cwd=mapped)
    for address in ('code.manager.route', 'code.probe.echo'):
        assert where(run, address, mapped)['memory']['joins'] == [
            {'receiver': 'code.manager.route', 'provider': 'code.probe.echo',
             'entities': [entity('echo timeout', 'fact', 'One second.')]}]


@pytest.mark.req('LAYER-012')
@pytest.mark.req('VIEW-031')
def test_the_whole_graph_says_of_each_join_whether_its_memory_shows_at_its_node_in_the_layers(run, mapped):
    """For the web GUI's memory graph, VIEW-031: `graph` returns the whole graph, and each join says whether its
    entity shows at its node, as a node read shows it: the memory layer reaches the node's address in the layers of
    the call, and the join is not orphaned."""
    mj(run, 'create_entities', J([entity('old', 'fact', 'Long ago.'), entity('new', 'fact')]), ROUTE, cwd=mapped)
    mj(run, 'create_entities', J([entity('echo', 'fact')]), PROBE, cwd=mapped)

    def shows(*more):
        return {one['entity']: one['shows'] for one in mj(run, 'graph', *more, cwd=mapped)['joins']}
    assert shows() == {'old': True, 'new': True, 'echo': True}
    run('map', 'mask', 'code.manager', 'memory', cwd=mapped)
    assert shows() == {'old': False, 'new': False, 'echo': True}
    run('map', 'clear', 'code.manager', 'memory', 'mask', cwd=mapped)
    assert shows('--layers', 'intake-1') == {'old': False, 'new': False, 'echo': False}
    assert len(mj(run, 'graph', '--layers', 'intake-1', cwd=mapped)['entities']) == 3  # the whole graph still
    run('clear', 'project', '--confirm', cwd=mapped)  # a join the map no longer holds is orphaned and shows nowhere
    assert {one['entity']: (one['orphaned'], one['shows']) for one in mj(run, 'graph', cwd=mapped)['joins']} == {
        'old': (True, False), 'new': (True, False), 'echo': (True, False)}


@pytest.mark.req('VIEW-034')
def test_a_node_holds_one_note_of_at_most_2048_characters_that_anyone_edits(run, mapped):
    """Rich, 2026-10-02: one single note not a list, 2048 characters, the agent and the user edit it, not protected,
    it does not expire, notes do not build up."""
    written = mj(run, 'note', 'element:code.manager.route', 'text=Routes drift under load.', cwd=mapped)
    assert written['note']['text'] == 'Routes drift under load.'
    mj(run, 'note', 'element:code.manager.route', 'text=Routes hold under load.', 'by=user', cwd=mapped)
    read = mj(run, 'note', 'element:code.manager.route', cwd=mapped)
    assert (read['note']['text'], read['note']['by']) == ('Routes hold under load.', 'user')
    assert where(run, 'code.manager.route', mapped)['memory']['note']['text'] == 'Routes hold under load.'
    long = m(run, 'note', 'element:code.manager.route', 'text=' + 'x' * 2049, cwd=mapped, ok=False)
    assert long.returncode == 2 and '2048' in long.stderr
    assert mj(run, 'note', 'element:code.manager.route', cwd=mapped)['note']['text'] == 'Routes hold under load.'
    assert mj(run, 'note', 'element:code.manager.route', 'text=' + 'y' * 2048, cwd=mapped)['note']['text'] == 'y' * 2048
    mj(run, 'note', 'element:code.manager.route', 'text=An agent edits the user\'s note.', cwd=mapped)
    replaced = mj(run, 'note', 'element:code.manager.route', cwd=mapped)['note']
    assert (replaced['text'], replaced['by']) == ("An agent edits the user's note.", None)  # not protected
    run('clear', 'project', 'proj', '--confirm', cwd=mapped)
    intake(Store('proj'))
    assert mj(run, 'note', 'element:code.manager.route', cwd=mapped)['note']['text'] == \
        "An agent edits the user's note."  # it does not expire, and a clear keeps it
    assert mj(run, 'note', 'element:code.manager.route', 'text=', cwd=mapped)['note'] is None


@pytest.mark.req('LAYER-012')
@pytest.mark.req('STORE-020')
def test_the_memory_layer_is_made_on_first_write_with_no_provenance(run, mapped, home):
    assert [layer.name for layer in Store('proj').layers(kind='memory').results] == []
    mj(run, 'create_entities', J([entity('first', 'fact')]), ROUTE, cwd=mapped)
    layer = Store('proj').layers(kind='memory').results[0]
    assert (layer.name, layer.module, layer.variable, layer.mutable, layer.ready is not None) == (
        'memory', 'memory', 'What agents have noted at this node.', True, True)
    assert Store('proj').provenance('memory') is None


@pytest.mark.req('BASE-040')
def test_deleting_at_a_node_removes_memories_only(run, mapped):
    mj(run, 'create_entities', J([entity('route', 'part', 'keep', 'drop'), entity('probe', 'part')]), ROUTE,
       cwd=mapped)
    mj(run, 'create_relations', J([{'from': 'route', 'to': 'probe', 'relationType': 'uses'}]), ROUTE, cwd=mapped)
    mj(run, 'delete_observations', J([{'entityName': 'route', 'observations': ['drop']}]), ROUTE, cwd=mapped)
    assert mj(run, 'open_nodes', J(['route']), ROUTE, cwd=mapped)['entities'][0]['observations'] == ['keep']
    mj(run, 'delete_relations', J([{'from': 'route', 'to': 'probe', 'relationType': 'uses'}]), ROUTE, cwd=mapped)
    assert mj(run, 'open_nodes', J(['route']), ROUTE, cwd=mapped)['relations'] == []
    mj(run, 'delete_entities', J(['route']), ROUTE, cwd=mapped)
    assert [one['name'] for one in mj(run, 'read_graph', ROUTE, cwd=mapped)['entities']] == ['probe']
    assert Store('proj').element('code.manager.route') is not None


@pytest.mark.req('CLI-003')
def test_an_observation_that_starts_with_a_dash_is_kept_as_written(run, mapped):
    mj(run, 'create_entities', J([entity('signal', 'fact')]), ROUTE, cwd=mapped)
    run('memory', 'add_observations', J([{'entityName': 'signal', 'contents': ['-40 dBm is the weakest usable signal.']}]),
        ROUTE, cwd=mapped)
    assert mj(run, 'open_nodes', J(['signal']), ROUTE, cwd=mapped)['entities'][0]['observations'] == [
        '-40 dBm is the weakest usable signal.']


@pytest.mark.req('LAYER-013')
def test_a_node_the_map_does_not_hold_is_refused_and_nothing_is_written(run, mapped):
    """Replaces the test that an observation at an unknown element made it in memory: memory never touches the map."""
    refused = m(run, 'create_entities', J([entity('x', 'fact')]), 'node=element:code.nosuch.node', cwd=mapped,
                ok=False)
    assert refused.returncode == 2 and 'not a node of the map' in refused.stderr
    assert Store('proj').element('code.nosuch.node', raw=True) is None
    assert mj(run, 'read_graph', cwd=mapped)['entities'] == []


@pytest.mark.req('LAYER-012')
@pytest.mark.req('VIEW-034')
def test_what_the_memory_layer_held_carries_into_the_graph_and_the_notes_once(run, mapped):
    store = Store('proj')
    with store.atomic():
        layer = store.layer('memory', 'memory', 'What agents have noted at this node.', kind='memory', mutable=True,
                            hideable=True, ready=True).name
        store.add_item(layer, Node('element', 'code.manager.route'), 'Routes drift under load.')
        store.add_item(layer, Node('element', 'code.manager.route'), 'depends_on',
                       link=Node('element', 'code.probe.echo'))
        store.add_item(layer, Node('element', 'code.manager.route'), 'Ask Rich before changing it.',
                       extra={'by': 'user'})
    graph = mj(run, 'read_graph', cwd=mapped)
    assert graph == {'entities': [entity('code.manager.route', 'element', 'Routes drift under load.'),
                                  entity('code.probe.echo', 'element')],
                     'relations': [{'from': 'code.manager.route', 'to': 'code.probe.echo',
                                    'relationType': 'depends_on'}]}
    assert mj(run, 'note', 'element:code.manager.route', cwd=mapped)['note']['text'] == 'Ask Rich before changing it.'
    assert mj(run, 'read_graph', cwd=mapped) == graph
    assert mj(run, 'read_graph', ROUTE, cwd=mapped)['entities'] == [entity('code.manager.route', 'element',
                                                                           'Routes drift under load.')]
    assert len(Store('proj').layer_items('memory', limit=0).results) == 3
