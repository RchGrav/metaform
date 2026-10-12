"""The memory module: a memory graph of its own, the MCP reference memory server's, presented at each node of the map
and tied to it by joins of type memory, BASE-040, LAYER-012, LAYER-013, STORE-020 and VIEW-034."""
from __future__ import annotations

import json

import pytest

from metaform.data import Node, Store
from tests.storekit import page_note

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
                       ef='Sends an echo.')


@pytest.fixture
def mapped(run, tmp_path):
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    intake(Store('proj'))
    return folder


def m(run, verb, *args, cwd, ok=True):
    return run('memory', verb, *(kept(arg) if verb == 'create_entities' else arg for arg in args), '--json', cwd=cwd,
               ok=ok)


def kept(arg):
    """A create_entities argument with what a new memory carries, MCP-037: a why, and a title when its first
    observation is not one short line to stand as its title. Each test's own entities stay as the reference has them."""
    if not isinstance(arg, str) or not arg.startswith('['):
        return arg
    given = json.loads(arg)
    for one in given:
        one.setdefault('why', 'Kept for the next agent here.')
        if not one['observations'] or '\n' in one['observations'][0]:
            one.setdefault('title', one['name'])
    return json.dumps(given)


def mj(run, verb, *args, cwd):
    return json.loads(m(run, verb, *args, cwd=cwd).stdout)


def entity(name, kind='behavior', *observations):
    return {'name': name, 'entityType': kind, 'observations': list(observations)}


def J(value):
    return json.dumps(value)


def where(run, address, cwd, *more):
    """A node's read with what is held there in full, which carries memory's node read; the read an agent orients
    from counts it instead, MCP-039."""
    return json.loads(run('map', 'where', address, 'contents=true', *more, '--json', cwd=cwd).stdout)


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
            'name': text, 'entityType': text, 'observations': texts, 'title': text, 'why': text},
            'required': ['name', 'entityType', 'observations']}}},
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
    chassis = {'node', 'receiver', 'provider', 'address', 'project', 'layers'}
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
    assert made['entities'] == [entity('route', 'part', 'Drifts.'), entity('probe', 'part')]
    assert mj(run, 'create_entities', J([entity('route', 'part')]), cwd=mapped) == {'entities': []}
    missing = m(run, 'create_relations', J([{'from': 'route', 'to': 'ghost', 'relationType': 'uses'}]), cwd=mapped,
                ok=False)
    assert missing.returncode == 2 and 'Entity with name ghost not found' in missing.stderr
    relation = {'from': 'probe', 'to': 'route', 'relationType': 'checks'}
    assert mj(run, 'create_relations', J([relation, relation]), cwd=mapped)['relations'] == [relation]
    assert mj(run, 'create_relations', J([relation]), cwd=mapped) == {'relations': []}
    added = mj(run, 'add_observations', J([{'entityName': 'route', 'contents': ['Drifts.', 'Holds 25 routes.']}]),
               cwd=mapped)
    assert added['results'] == [{'entityName': 'route', 'addedObservations': ['Holds 25 routes.']}]
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
    """Replaces the test that create-entities made an element in the memory layer: the memories
    are not addressed as another segment off the namespace."""
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
    assert made == {'entities': [entity('route ejection', 'behavior', 'Routes are ejected.')],
                    'items': ['code.manager.route#1  Routes are ejected.']}  # its number at the node, MCP-037
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
    # an existing name keeps its type and gains the new observation, BASE-040 as amended 2026-10-11
    mj(run, 'create_entities', J([entity('echo cost', 'other type', 'Echoes cost one packet.')]), ROUTE, cwd=mapped)
    assert mj(run, 'read_graph', ROUTE, cwd=mapped)['entities'][1] == entity('echo cost', 'fact',
                                                                            'Echoes are ejected cheaply.',
                                                                            'Echoes cost one packet.')
    assert mj(run, 'read_graph', cwd=mapped)['entities'] == [
        entity('route ejection', 'behavior', 'Routes are ejected.'), entity('echo cost', 'fact',
                                                                            'Echoes are ejected cheaply.',
                                                                            'Echoes cost one packet.')]


@pytest.mark.req('LAYER-013')
@pytest.mark.req('STORE-020')
def test_a_join_is_a_node_of_memory_keyed_by_its_receiver_and_provider(run, mapped):
    store = Store('proj')
    join_id = store.joins('code.manager.route').results[0].id
    mj(run, 'create_entities', J([entity('echo timeout', 'fact', 'The echo times out after 1 s.')]),
       f'node=join:{join_id}', cwd=mapped)
    assert mj(run, 'read_graph', f'node=join:{join_id}', cwd=mapped)['entities'] == [
        entity('echo timeout', 'fact', 'The echo times out after 1 s.')]
    joined = {one['entity']: (one['receiver'], one['provider']) for one in mj(run, 'joins', cwd=mapped)['joins']}
    assert joined == {'echo timeout': ('code.manager.route', 'code.probe.echo')}


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
    join_id = Store('proj').joins('code.manager.route').results[0].id
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
    new_id = Store('proj').joins('code.manager.route').results[0].id
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
    """Memories are not dated, so they are kept as agents are used to using them. The graph read and the tables hold what the reference holds,
    entities, observations and relations in the order they were made, and the joins their node's address."""
    mj(run, 'create_entities', J([entity('route', 'part', 'Drifts.', 'Holds.'), entity('probe', 'part')]), ROUTE,
       cwd=mapped)
    mj(run, 'create_relations', J([{'from': 'route', 'to': 'probe', 'relationType': 'uses'},
                                   {'from': 'probe', 'to': 'route', 'relationType': 'checks'}]), cwd=mapped)
    whole = mj(run, 'graph', cwd=mapped)
    assert whole['entities'] == [
        {'name': 'route', 'entityType': 'part', 'observations': [{'content': 'Drifts.', 'by': None},
                                                                 {'content': 'Holds.', 'by': None}]},
        {'name': 'probe', 'entityType': 'part', 'observations': []}]
    assert whole['relations'] == [{'from': 'route', 'to': 'probe', 'relationType': 'uses'},
                                  {'from': 'probe', 'to': 'route', 'relationType': 'checks'}]
    assert [sorted(one) for one in whole['joins']] == [['address', 'by', 'entity', 'join_id', 'orphaned', 'shows']] * 2
    assert mj(run, 'read_graph', cwd=mapped)['relations'] == whole['relations']
    from metaform.modules.memory import TABLES
    columns = {table.name: [column.name for column in table.columns] for table in TABLES.tables}
    assert columns['entities'] == ['name', 'entity_type', 'seq', 'title', 'why']
    assert columns['observations'] == ['entity', 'content', 'seq', 'by', 'session', 'at']
    assert columns['relations'] == ['source', 'target', 'relation_type', 'seq']
    assert columns['joins'] == ['join_id', 'entity', 'receiver', 'provider', 'by', 'session', 'at', 'number']


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
        tx.insert('notes', {'receiver': 'code.manager.route', 'provider': '', 'text': 'Ask the owner first.', 'by': 'user',
                            'at': when})
    whole = mj(run, 'read_graph', cwd=mapped)
    assert sorted(whole['entities'], key=lambda one: one['name']) == [
        entity('probe', 'part'), entity('route', 'part', 'Drifts.', 'Holds.')]
    assert whole['relations'] == [{'from': 'probe', 'to': 'route', 'relationType': 'checks'}]
    assert [(one['join_id'], one['entity'], one['address']) for one in mj(run, 'joins', cwd=mapped)['joins']] == [
        ('j1', 'route', 'code.manager.route')]
    assert mj(run, 'read_graph', ROUTE, cwd=mapped)['entities'] == [entity('route', 'part', 'Drifts.', 'Holds.')]
    noted = mj(run, 'note', 'element:code.manager.route', cwd=mapped)['note']
    assert (noted['text'], noted['by']) == ('Ask the owner first.', 'user')
    with project_transaction(path, write=False) as db:  # read through the public table API, never sqlite3, STORE-045
        recorded = json.loads(db.execute("SELECT value FROM meta WHERE key='module:memory'").fetchone()[0])
        held = {table: [row[1] for row in db.execute(f'PRAGMA table_info("memory.{table}")')]
                for table in ('entities', 'observations', 'relations', 'joins')}
    assert recorded['version'] == 5
    assert held == {'entities': ['name', 'entity_type', 'seq', 'title', 'why'],
                    'observations': ['entity', 'content', 'seq', 'by', 'session', 'at'],
                    'relations': ['source', 'target', 'relation_type', 'seq'],
                    'joins': ['join_id', 'entity', 'receiver', 'provider', 'by', 'session', 'at', 'number']}
    mj(run, 'create_entities', J([entity('echo', 'part')]), cwd=mapped)
    assert [one['name'] for one in mj(run, 'read_graph', cwd=mapped)['entities']][-1] == 'echo'


@pytest.mark.req('LAYER-012')
@pytest.mark.req('LAYER-007')
def test_agents_see_the_memory_joins_when_they_read_a_node_and_the_layer_named_memory_turns_them_off(run, mapped):
    """Replaces the check on the memory group of a node read: the same select and mask now turn off the memory joins
    the node read shows. Agent sees these joins; the orchestrator uses layer select."""
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
    join_id = Store('proj').joins('code.manager.route').results[0].id
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


@pytest.mark.req('STORE-005')
def test_one_graph_read_opens_the_project_databases_of_the_home_as_often_whatever_the_number_of_projects(
        run, mapped, home, tmp_path, monkeypatch, capsys):
    """The web page reads the whole graph on every reload. A read's cost follows its answer, STORE-005, so the home's
    project databases it opens do not grow with the number of projects the home holds: finding one project's folder
    does not open every other project's database."""
    from metaform import cli
    from metaform import home as metaform_home
    from metaform import sqlite as metaform_sqlite
    store = Store('proj')
    join_id = store.joins('code.manager.route').results[0].id
    store.add_element('intake-1', 'code.probe.echo.timer', name_length=3, role='SE')
    for number, node in enumerate((ROUTE, PROBE, f'node=join:{join_id}', 'node=element:code.probe.echo.timer')):
        mj(run, 'create_entities', J([entity(f'fact {number}', 'fact')]), node, cwd=mapped)
    opened: list[str] = []
    real = metaform_sqlite.connect

    def connect(path):
        if str(path).endswith(metaform_home.PROJECT_DB):
            opened.append(str(path))
        return real(path)
    monkeypatch.setattr(metaform_sqlite, 'connect', connect)  # every chassis database is opened through it
    monkeypatch.chdir(mapped)

    def graph():
        metaform_home._invalidate_registry()  # a cold read each time; the process cache would hide the opens
        opened.clear()
        assert cli.main(['memory', 'graph', '--json']) == 0
        said = json.loads(capsys.readouterr().out)
        return said, len(opened)
    graph()  # the process's first command also resolves the folder's settings, once
    alone, few = graph()
    assert len(alone['joins']) == 4
    assert few > 0  # the count sees the project's own database, so an equal count is not two zeros
    for number in range(11):
        other = tmp_path / f'other-{number}'
        other.mkdir()
        metaform_home.add_project(f'other-{number}', other)
    among, many = graph()
    assert among == alone
    assert many == few, f'{few} opens with one project, {many} with twelve'


@pytest.mark.req('VIEW-034')
def test_a_node_holds_one_note_of_at_most_2048_characters_that_only_the_person_writes(run, mapped):
    """The note is the person's: written for people to read on the node, not for agents, which have the memory
    server. One single note, not a list, of at most 2048 characters; it
    does not expire, and notes do not build up."""
    from metaform.errors import Stop
    written = page_note('proj', 'element:code.manager.route', 'Routes drift under load.')
    assert written['note']['text'] == 'Routes drift under load.'
    page_note('proj', 'element:code.manager.route', 'Routes hold under load.')
    read = mj(run, 'note', 'element:code.manager.route', cwd=mapped)  # every surface reads it
    assert (read['note']['text'], read['note']['by']) == ('Routes hold under load.', 'user')
    assert where(run, 'code.manager.route', mapped)['memory']['note']['text'] == 'Routes hold under load.'
    with pytest.raises(Stop, match='2048'):
        page_note('proj', 'element:code.manager.route', 'x' * 2049)
    assert mj(run, 'note', 'element:code.manager.route', cwd=mapped)['note']['text'] == 'Routes hold under load.'
    assert page_note('proj', 'element:code.manager.route', 'y' * 2048)['note']['text'] == 'y' * 2048
    # An agent never writes the note: the command line refuses, and nothing changes.
    refused = m(run, 'note', 'element:code.manager.route', "text=An agent edits the user's note.", cwd=mapped,
                ok=False)
    assert refused.returncode == 2 and 'The note is written only from the web page.' in refused.stderr
    cleared = m(run, 'note', 'element:code.manager.route', 'text=', cwd=mapped, ok=False)  # nor clears it
    assert cleared.returncode == 2
    assert mj(run, 'note', 'element:code.manager.route', cwd=mapped)['note']['text'] == 'y' * 2048
    run('clear', 'project', 'proj', '--confirm', cwd=mapped)
    intake(Store('proj'))
    assert mj(run, 'note', 'element:code.manager.route', cwd=mapped)['note']['text'] == 'y' * 2048  # a clear keeps it
    assert page_note('proj', 'element:code.manager.route', '')['note'] is None


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
        store.add_item(layer, Node('element', 'code.manager.route'), 'Ask the owner before changing it.',
                       extra={'by': 'user'})
    mj(run, 'create_entities', J([entity('echo timing', 'fact', 'Echoes answer in a second.')]), PROBE, cwd=mapped)
    graph = mj(run, 'read_graph', cwd=mapped)
    assert graph == {'entities': [entity('code.manager.route', 'element', 'Routes drift under load.'),
                                  entity('code.probe.echo', 'element'),
                                  entity('echo timing', 'fact', 'Echoes answer in a second.')],
                     'relations': [{'from': 'code.manager.route', 'to': 'code.probe.echo',
                                    'relationType': 'depends_on'}]}
    assert mj(run, 'note', 'element:code.manager.route', cwd=mapped)['note']['text'] == 'Ask the owner before changing it.'
    assert mj(run, 'read_graph', cwd=mapped) == graph
    assert mj(run, 'read_graph', ROUTE, cwd=mapped)['entities'] == [entity('code.manager.route', 'element',
                                                                           'Routes drift under load.')]
    assert len(Store('proj').layer_items('memory', limit=0).results) == 3
    mj(run, 'delete_observations', J([{'entityName': 'code.manager.route', 'observations': [
        'Routes drift under load.']}]), cwd=mapped)
    mj(run, 'create_entities', J([entity('later', 'fact')]), PROBE, cwd=mapped)
    assert mj(run, 'read_graph', ROUTE, cwd=mapped)['entities'] == [entity('code.manager.route', 'element')]


CARRYING = (('create_entities', J([entity('echo timing', 'fact')]), PROBE),
            ('create_relations', J([{'from': 'echo seed', 'to': 'echo seed', 'relationType': 'repeats'}])),
            ('add_observations', J([{'entityName': 'echo seed', 'contents': ['Echoes answer in a second.']}])),
            ('delete_entities', J(['nothing'])),
            ('delete_observations', J([{'entityName': 'echo seed', 'observations': ['nothing']}])),
            ('delete_relations', J([{'from': 'echo seed', 'to': 'echo seed', 'relationType': 'nothing'}])))
# The note is not among them: an agent never writes it, VIEW-034.


def _seeded(run, mapped):
    """The memory of the two tests below: one entity the agent made, and two items at the route, one the person's."""
    mj(run, 'create_entities', J([entity('echo seed', 'fact')]), PROBE, cwd=mapped)
    store = Store('proj')
    layer = store.layers(kind='memory').results[0].name
    with store.atomic():
        store.add_item(layer, Node('element', 'code.manager.route'), 'Routes drift under load.')
        store.add_item(layer, Node('element', 'code.manager.route'), 'Ask the owner before changing it.',
                       extra={'by': 'user'})


@pytest.mark.req('VIEW-011')
@pytest.mark.req('STORE-020')
def test_a_memory_command_that_only_reads_writes_nothing(run, mapped, home):
    _seeded(run, mapped)
    stores = sorted((home / 'projects').rglob('*.sqlite3'))
    assert any(path.name == 'memory.sqlite3' for path in stores)
    before = [path.read_bytes() for path in stores]
    for verb, *args in (('read_graph',), ('read_graph', ROUTE), ('search_nodes', 'query=drift'),
                        ('open_nodes', J(['code.manager.route'])), ('joins',), ('joins', ROUTE), ('orphaned',),
                        ('graph',), ('note', 'element:code.manager.route')):
        m(run, verb, *args, cwd=mapped)
    assert sorted((home / 'projects').rglob('*.sqlite3')) == stores
    assert [path.read_bytes() for path in stores] == before


@pytest.mark.req('VIEW-011')
@pytest.mark.req('STORE-020')
@pytest.mark.parametrize('write', CARRYING, ids=[one[0] for one in CARRYING])
def test_a_memory_command_that_writes_carries_what_was_kept(run, mapped, write):
    _seeded(run, mapped)
    mj(run, *write, cwd=mapped)
    assert mj(run, 'open_nodes', J(['code.manager.route']), cwd=mapped)['entities'] == [
        entity('code.manager.route', 'element', 'Routes drift under load.')]
    assert mj(run, 'note', 'element:code.manager.route', cwd=mapped)['note']['text'] == 'Ask the owner before changing it.'


PURPOSE =('receiver=code.manager.route', 'provider=code.probe.echo')


@pytest.mark.req('LAYER-013')
@pytest.mark.req('MAP-005')
def test_memory_names_a_join_by_its_receiver_and_an_element_it_holds(run, mapped):
    """Ticket ad135d54: what an agent names is most easily inferred from what it already read; ids
    are internal. An agent names a join by its receiver and an element it holds, as refine does, and never handles
    join:<id>; with address beside them it names an element that join holds."""
    store = Store('proj')
    join_id = store.joins('code.manager.route').results[0].id
    with store.atomic():
        store.add_element('intake-1', 'code.probe.echo.timer', name_length=3, role='SE')
        store.refine(join_id, {'elements': ['code.probe.echo', 'code.probe.echo.timer']}, reason='the timer serves it')
        store.add_element('intake-1', 'code.manager.table', name_length=2, role='SE')
        store.add_element('intake-1', 'code.manager.table.row', name_length=3, role='SE')
        tabled = store.add_join('intake-1', 'code.manager.route', ['code.manager.table', 'code.manager.table.row'],
                                purpose='Keep the routes.')
    # The route manager holds two joins, so the provider, not the order they are held in, picks one.
    table = ('receiver=code.manager.route', 'provider=code.manager.table')
    mj(run, 'create_entities', J([entity('echo timeout', 'fact', 'One second.')]), *PURPOSE, cwd=mapped)
    beside = mj(run, 'create_entities', J([entity('table size', 'fact')]), *table, PROBE, cwd=mapped)
    assert beside['notices'] == [{'where': 'node', 'message': 'receiver, provider and address name the node; node '
                                                              'was not read.'}]
    # Any element the join holds names it.
    timer = ('receiver=code.manager.route', 'provider=code.probe.echo.timer')
    assert mj(run, 'read_graph', *timer, cwd=mapped) == mj(run, 'read_graph', *PURPOSE, cwd=mapped)
    mj(run, 'create_entities', J([entity('timer drift', 'fact')]), *PURPOSE, 'address=code.probe.echo.timer',
       cwd=mapped)
    elsewhere = m(run, 'create_entities', J([entity('x', 'fact')]), *PURPOSE, 'address=code.manager.table.row',
                  cwd=mapped, ok=False)
    assert elsewhere.returncode == 2 and 'code.manager.table.row is not held by' in elsewhere.stderr
    mj(run, 'create_entities', J([entity('route cost', 'fact')]), 'address=code.manager.route', cwd=mapped)
    assert mj(run, 'read_graph', *PURPOSE, cwd=mapped) == mj(run, 'read_graph', f'node=join:{join_id}', cwd=mapped)
    assert [one['name'] for one in mj(run, 'read_graph', *PURPOSE, cwd=mapped)['entities']] == ['echo timeout']
    assert [one['name'] for one in mj(run, 'read_graph', f'node=join:{tabled.id}', cwd=mapped)['entities']] == [
        'table size']
    assert [one['name'] for one in mj(run, 'read_graph', 'node=element:code.probe.echo.timer',
                                      cwd=mapped)['entities']] == ['timer drift']
    assert [one['name'] for one in mj(run, 'read_graph', ROUTE, cwd=mapped)['entities']] == ['route cost']
    assert [one['name'] for one in mj(run, 'read_graph', PROBE, cwd=mapped)['entities']] == []
    assert [one['entity'] for one in mj(run, 'joins', *PURPOSE, cwd=mapped)['joins']] == ['echo timeout']
    # note takes node first, provider beside it names the join node holds as its receiver.
    # The note is the person's, written from the page, VIEW-034; reading it is the same on every surface.
    written = page_note('proj', 'element:code.manager.route', 'The echo is the only liveness check.',
                        provider='code.probe.echo')
    assert (written['receiver'], written['provider']) == ('code.manager.route', 'code.probe.echo')
    assert mj(run, 'note', f'join:{join_id}', cwd=mapped)['note']['text'] == 'The echo is the only liveness check.'
    timed = page_note('proj', 'code.manager.route', 'Drifts warm.', provider='code.probe.echo',
                      address='code.probe.echo.timer')
    assert timed['address'] == 'code.probe.echo.timer'
    assert mj(run, 'note', 'element:code.probe.echo.timer', cwd=mapped)['note']['text'] == 'Drifts warm.'
    assert mj(run, 'note', 'element:code.manager.route', cwd=mapped)['note'] is None
    alone = mj(run, 'note', 'element:code.manager.route', 'address=code.probe.echo.timer', cwd=mapped)
    assert (alone['address'], alone['note'], alone['notices']) == ('code.manager.route', None, [
        {'where': 'address', 'message': 'address names an element a join holds only with provider; it was not read.'}])


@pytest.mark.req('LAYER-013')
@pytest.mark.req('MAP-005')
def test_a_purpose_the_map_does_not_hold_or_cannot_tell_apart_is_refused_by_its_addresses(run, mapped):
    """Nothing is written when the receiver and provider name no purpose, or several with the same two ends; the
    refusal names them by address and, for several, by their purposes."""
    unheld = m(run, 'create_entities', J([entity('x', 'fact')]), 'receiver=code.manager.route',
               'provider=code.nosuch.node', cwd=mapped, ok=False)
    assert unheld.returncode == 2 and 'code.manager.route has no purpose served by code.nosuch.node' in unheld.stderr
    half = m(run, 'create_entities', J([entity('x', 'fact')]), 'receiver=code.manager.route', cwd=mapped, ok=False)
    assert half.returncode == 2 and 'provider' in half.stderr
    store = Store('proj')
    with store.atomic():
        store.add_join('intake-1', 'code.manager.route', 'code.probe.echo', purpose='Measure the route delay.')
    twice = m(run, 'create_entities', J([entity('x', 'fact')]), *PURPOSE, cwd=mapped, ok=False)
    assert twice.returncode == 2 and 'Know a route is alive.' in twice.stderr and 'Measure the route delay.' in twice.stderr
    assert mj(run, 'read_graph', cwd=mapped)['entities'] == []


@pytest.mark.req('MAP-005')
def test_no_memory_command_tells_an_agent_to_name_a_node_by_a_join_id(run, mapped):
    """What an agent reads of a command: its help on the command line, its MCP schema, which carries each noun's
    help, a required one's included, and the refusal of a node written wrong. Every command that takes node also takes
    receiver, provider and address."""
    from metaform.modules.mcp.server import verb_schema
    from metaform.modules.memory import MODULE
    for verb in MODULE.verbs:
        if verb.name == 'unjoin':  # a memory join's own id, which joins and orphaned give
            continue
        assert 'join:<id>' not in run('help', 'memory', verb.name, cwd=mapped).stdout, verb.name
        schema = verb_schema(verb, mapped)
        assert 'join:<id>' not in json.dumps(schema), verb.name
        if 'node' in schema['properties']:
            named = {'provider', 'address'} if verb.name == 'note' else {'receiver', 'provider', 'address'}
            assert named <= set(schema['properties']), verb.name
    wrong = m(run, 'read_graph', 'node=join:', cwd=mapped, ok=False)
    assert wrong.returncode == 2 and 'join:<id>' not in wrong.stderr


@pytest.mark.req('STORE-020')
@pytest.mark.req('LAYER-013')
@pytest.mark.parametrize('old_missing', [False, True])
def test_rekey_transfers_exact_addresses_at_both_ends_and_preserves_the_graph(run, mapped, old_missing):
    old, new = 'code.manager.route', 'code.manager.table'
    store = Store('proj', module='memory')
    with store.atomic():
        store.add_element('intake-1', new, name_length=2, role='DE')
        store.add_join('intake-1', new, 'code.probe.echo', purpose='Know the table is alive.')
    mj(run, 'create_entities', J([entity('routing fact', 'fact', 'Routes drift.')]), ROUTE, cwd=mapped)
    before_graph = mj(run, 'read_graph', cwd=mapped)
    keys = [(old, ''), (old, 'code.probe.echo'), ('code.probe.echo', old), (old, old), (old + '.child', '')]
    with store.tables() as tx:
        for number, (receiver, provider) in enumerate(keys):
            if number:
                tx.insert('joins', {'join_id': str(number), 'entity': 'routing fact',
                                    'receiver': receiver, 'provider': provider})
            tx.insert('notes', {'receiver': receiver, 'provider': provider, 'text': f'Note {number}',
                                'by': 'user', 'at': '2026-10-02T00:00:00Z'})
    with store.tables(write=False) as tx:
        before = {table: list(tx.rows(table, limit=0).results) for table in ('joins', 'notes')}
    if old_missing:
        store.refine(store.element(old, raw=True).id, remove=True, reason='Replace the old address.')
        assert any(one.get('address') == old for one in mj(run, 'orphaned', cwd=mapped)['joins'])
    result = mj(run, 'rekey', old, new, cwd=mapped)
    assert result == {'old': old, 'new': new, 'joins': 4, 'notes': 4}
    with store.tables(write=False) as tx:
        after = {table: list(tx.rows(table, limit=0).results) for table in ('joins', 'notes')}
    def unnumbered(row):  # a join moved to a new address takes the next number there, MCP-037
        return {key: value for key, value in row.items() if key != 'number'}
    for table, rows in before.items():
        expected = [{**row, **{end: new if row[end] == old else row[end] for end in ('receiver', 'provider')}}
                    for row in rows]
        def sort_key(row):
            return row['receiver'], row['provider']
        assert [unnumbered(row) for row in sorted(after[table], key=sort_key)] == [
            unnumbered(row) for row in sorted(expected, key=sort_key)]
    moved = [row['number'] for row in after['joins'] if row['receiver'] == new]
    assert len(set(moved)) == len(moved) and all(moved)
    assert mj(run, 'read_graph', cwd=mapped) == before_graph
    assert mj(run, 'read_graph', f'address={new}', cwd=mapped) == before_graph
    assert not any(one.get('address') == old for one in mj(run, 'joins', cwd=mapped)['joins'])
    assert mj(run, 'read_graph', f'receiver={new}', 'provider=code.probe.echo', cwd=mapped) == before_graph
    assert mj(run, 'note', f'element:{new}', cwd=mapped)['note'] == {
        'text': 'Note 0', 'by': 'user', 'at': '2026-10-02T00:00:00Z'}
    assert where(run, new, mapped)['memory']['note']['text'] == 'Note 0'
    assert mj(run, 'rekey', old, new, cwd=mapped)['joins'] == 0
    assert mj(run, 'rekey', new, new, cwd=mapped) == {
        'old': new, 'new': new, 'joins': 0, 'notes': 0}


@pytest.mark.req('STORE-020')
@pytest.mark.req('STORE-024')
@pytest.mark.parametrize('collision', ['joins', 'notes'])
def test_rekey_rolls_back_all_attachments_and_notes_on_a_destination_collision(run, mapped, collision):
    old, new = 'code.manager.route', 'code.probe.echo'
    mj(run, 'create_entities', J([entity('routing fact', 'fact')]), ROUTE, cwd=mapped)
    page_note('proj', f'element:{old}', 'Keep the old note.')
    if collision == 'joins':
        mj(run, 'create_entities', J([entity('routing fact', 'fact')]), PROBE, cwd=mapped)
    else:
        page_note('proj', f'element:{new}', 'Keep the destination note.')
    store = Store('proj', module='memory')
    with store.tables(write=False) as tx:
        before = {table: list(tx.rows(table, limit=0).results) for table in ('joins', 'notes')}
    refused = m(run, 'rekey', old, new, cwd=mapped, ok=False)
    assert refused.returncode == 2 and 'UNIQUE constraint failed' in refused.stderr
    with store.tables(write=False) as tx:
        assert {table: list(tx.rows(table, limit=0).results) for table in ('joins', 'notes')} == before


@pytest.mark.req('BASE-040')
def test_create_entities_with_an_existing_name_keeps_the_new_observations_and_says_so(run, mapped):
    """An agent recording under a name already in the graph loses nothing: the new observation is added to the
    existing entity, with a notice, and an observation it already holds is not repeated."""
    first = json.dumps([{'name': 'route ejection', 'entityType': 'behavior', 'observations': ['Routes are ejected.']}])
    again = json.dumps([{'name': 'route ejection', 'entityType': 'behavior',
                         'observations': ['Routes are ejected.', 'Ejection waits for the probe.']}])
    m(run, 'create_entities', first, ROUTE, cwd=mapped)
    said = json.loads(m(run, 'create_entities', again, ROUTE, cwd=mapped).stdout)
    assert said['entities'] == []
    assert any('route ejection already exists; 1 new observation' in n['message'] for n in said['notices'])
    found = json.loads(m(run, 'open_nodes', '["route ejection"]', ROUTE, cwd=mapped).stdout)
    assert found['entities'][0]['observations'] == ['Routes are ejected.', 'Ejection waits for the probe.']


@pytest.mark.req('BASE-040')
def test_a_bare_address_names_the_element_at_it(run, mapped):
    """node=<address> acts on the element at that address, as node=element:<address> does, MAP-005."""
    m(run, 'create_entities', J([entity('route ejection', 'behavior', 'Routes are ejected.')]),
      'node=code.manager.route', cwd=mapped)
    assert mj(run, 'read_graph', 'node=code.manager.route', cwd=mapped) == mj(run, 'read_graph', ROUTE, cwd=mapped)
    assert mj(run, 'read_graph', ROUTE, cwd=mapped)['entities'][0]['name'] == 'route ejection'


@pytest.mark.req('BASE-040')
def test_an_unscoped_write_lands_and_says_no_node_will_show_it(run, mapped):
    """Without a node the entity is still written, BASE-044, and the notice names it and says how to place it."""
    said = mj(run, 'create_entities', J([entity('probe timeout', 'behavior', 'Echo waits 2 s.')]), cwd=mapped)
    assert said['entities'][0]['name'] == 'probe timeout'
    assert any(n['message'] == 'Written to the whole memory graph; no node will show probe timeout. '
               'To tie it to a node, pass node or address.' for n in said['notices'])
    assert mj(run, 'open_nodes', '["probe timeout"]', cwd=mapped)['entities'][0]['observations'] == ['Echo waits 2 s.']


@pytest.mark.req('BASE-040')
def test_an_unscoped_write_to_an_entity_a_node_shows_carries_no_notice(run, mapped):
    """Observations added without a node to an entity joined at a node show there, so nothing is said."""
    m(run, 'create_entities', J([entity('route ejection', 'behavior', 'Routes are ejected.')]), ROUTE, cwd=mapped)
    said = mj(run, 'add_observations', J([{'entityName': 'route ejection', 'contents': ['Ejection waits.']}]),
              cwd=mapped)
    assert said['results'][0]['addedObservations'] == ['Ejection waits.'] and 'notices' not in said


@pytest.mark.req('BASE-040')
@pytest.mark.req('STORE-020')
def test_a_memory_write_records_by_the_session_the_server_runs_for(run, mapped):
    """A dispatcher tells whether its session recorded at its node by the by on the join and on each observation,
    since add_observations writes no join. A join already there keeps who made it."""
    session = {'METAFORM_SESSION': 'r1'}
    run('memory', 'create_entities', kept(J([entity('route', 'part', 'Drifts.')])), ROUTE, '--json', cwd=mapped,
        env=session)
    run('memory', 'add_observations', J([{'entityName': 'route', 'contents': ['Holds.']}]), ROUTE, '--json',
        cwd=mapped, env={'METAFORM_SESSION': 'r2'})
    run('memory', 'create_entities', kept(J([entity('route', 'part', 'Slips.')])), ROUTE, '--json', cwd=mapped,
        env={'METAFORM_SESSION': 'r3'})
    whole = mj(run, 'graph', cwd=mapped)
    assert whole['entities'][0]['observations'] == [{'content': 'Drifts.', 'by': 'r1'}, {'content': 'Holds.', 'by': 'r2'},
                                                    {'content': 'Slips.', 'by': 'r3'}]
    assert [(one['entity'], one['by']) for one in mj(run, 'joins', ROUTE, cwd=mapped)['joins']] == [('route', 'r1')]


@pytest.mark.req('STORE-029')
@pytest.mark.req('STORE-020')
def test_memory_kept_at_version_2_is_upgraded_keeping_every_row_with_no_by(run, mapped):
    """by may be empty, so the tables of version 2 are upgraded in place, every row kept with no by, and the store
    records that version 2's code still reads them."""
    from dataclasses import replace

    from metaform.data import Tables
    from metaform.data.tables import TableTx, ensure, project_store, project_transaction
    from metaform.modules.memory import TABLES
    declared = Tables(version=2, tables=tuple(
        replace(table, columns=tuple(column for column in table.columns if column.name != 'by'))
        if table.name in ('observations', 'joins') else table for table in TABLES.tables))
    path = project_store('proj', 'memory')
    path.parent.mkdir(parents=True, exist_ok=True)
    with project_transaction(path, write=True) as db:
        ensure(db, path, 'memory', declared, 'project')
        tx = TableTx('memory', declared, write=True, opener=lambda _: (db, path, True), bound='project')
        tx.insert('entities', {'name': 'route', 'entity_type': 'part', 'seq': 1})
        tx.insert('observations', {'entity': 'route', 'content': 'Drifts.', 'seq': 1})
        tx.insert('joins', {'join_id': 'j1', 'entity': 'route', 'receiver': 'code.manager.route', 'provider': ''})
    whole = mj(run, 'graph', cwd=mapped)
    assert whole['entities'] == [{'name': 'route', 'entityType': 'part', 'observations': [{'content': 'Drifts.', 'by': None}]}]
    assert [(one['join_id'], one['by']) for one in whole['joins']] == [('j1', None)]
    with project_transaction(path, write=False) as db:
        recorded = json.loads(db.execute("SELECT value FROM meta WHERE key='module:memory'").fetchone()[0])
    assert (recorded['version'], recorded['compatible_from']) == (5, 2)


def item(run, reference, cwd, ok=True):
    return run('map', 'item', reference, '--json', cwd=cwd, ok=ok)


@pytest.mark.req('BASE-040')
@pytest.mark.req('MCP-037')
def test_each_memory_at_a_node_takes_the_next_number_there_and_a_number_is_never_reused(run, mapped):
    """One counter per address: a memory joined at a node takes its next number, shown in lowercase hex and read in
    either case; deleting a memory leaves a gap, and the next memory takes the number after the last one taken."""
    made = mj(run, 'create_entities', J([entity('first', 'fact', 'One.'), entity('second', 'fact', 'Two.')]), ROUTE,
              cwd=mapped)
    assert made['items'] == ['code.manager.route#1  One.', 'code.manager.route#2  Two.']
    mj(run, 'delete_entities', J(['second']), cwd=mapped)
    assert item(run, 'code.manager.route#2', mapped, ok=False).returncode == 2
    again = mj(run, 'create_entities', J([entity('third', 'fact', 'Three.')]), ROUTE, cwd=mapped)
    assert again['items'] == ['code.manager.route#3  Three.']
    assert json.loads(item(run, 'code.manager.route', mapped).stdout)['item'] == 'code.manager.route#3'  # the latest
    for number in range(4, 12):
        mj(run, 'create_entities', J([entity(f'fact {number}', 'fact', f'Fact {number}.')]), ROUTE, cwd=mapped)
    read = json.loads(item(run, 'code.manager.route#B', mapped).stdout)
    assert (read['item'], read['title'], read['why']) == ('code.manager.route#b', 'Fact 11.', 'Kept for the next agent here.')
    assert mj(run, 'create_entities', J([entity('elsewhere', 'fact', 'Else.')]), PROBE, cwd=mapped)['items'] == [
        'code.probe.echo#1  Else.']  # each address counts on its own


@pytest.mark.req('BASE-040')
@pytest.mark.req('MCP-037')
def test_a_new_memory_without_its_title_or_why_is_refused_naming_which_and_nothing_is_written(run, mapped):
    """A memory records knowledge, so a new one carries a short title and why; a first observation that is one short
    line is its title. The refusal's next step names what is missing, and nothing of the call is written."""
    def given(*entities):
        return run('memory', 'create_entities', J(list(entities)), ROUTE, '--json', cwd=mapped, ok=False)
    no_why = given({'name': 'a', 'entityType': 'fact', 'observations': ['One line.']})
    assert no_why.returncode == 2 and 'Next: add why: one line' in no_why.stderr
    neither = given({'name': 'b', 'entityType': 'fact', 'observations': ['Two lines.\nOf it.']},
                    {'name': 'c', 'entityType': 'fact', 'observations': ['Fine.'], 'why': 'Kept.'})
    assert 'Next: add title: one line saying what this is; add why' in neither.stderr
    assert mj(run, 'read_graph', cwd=mapped) == {'entities': [], 'relations': []}
    titled = given({'name': 'd', 'entityType': 'fact', 'observations': ['One line.'], 'why': 'Kept.'})
    assert titled.returncode == 0 and json.loads(titled.stdout)['items'] == ['code.manager.route#1  One line.']


@pytest.mark.req('STORE-045')
@pytest.mark.req('MCP-037')
def test_memories_kept_before_numbers_are_numbered_in_the_order_they_were_made_with_titles_from_their_first_line(
        run, mapped):
    """Memory tables version 5 numbers the joins already held, those kept before joins had times first, then by when
    each was made, and titles each memory from the first line of its first observation; version 4 code still reads
    the tables."""
    from dataclasses import replace

    from metaform.data import Tables
    from metaform.data.tables import TableTx, ensure, project_store, project_transaction
    from metaform.modules.memory import TABLES
    new = {'title', 'why', 'number'}
    declared = Tables(version=4, compatible_from=2, tables=tuple(
        replace(table, columns=tuple(column for column in table.columns if column.name not in new),
                indexes=tuple(index for index in table.indexes if 'number' not in index.columns))
        for table in TABLES.tables))
    path = project_store('proj', 'memory')
    path.parent.mkdir(parents=True, exist_ok=True)
    with project_transaction(path, write=True) as db:
        ensure(db, path, 'memory', declared, 'project')
        tx = TableTx('memory', declared, write=True, opener=lambda _: (db, path, True), bound='project')
        for seq, name in enumerate(('late', 'early', 'untimed'), start=1):
            tx.insert('entities', {'name': name, 'entity_type': 'fact', 'seq': seq})
            tx.insert('observations', {'entity': name, 'content': f'{name.title()} memory.\nMore.', 'seq': 1})
        tx.insert('joins', {'join_id': 'j1', 'entity': 'late', 'receiver': 'code.manager.route',
                            'at': '2026-10-05T00:00:00.000000Z'})
        tx.insert('joins', {'join_id': 'j2', 'entity': 'early', 'receiver': 'code.manager.route',
                            'at': '2026-10-01T00:00:00.000000Z'})
        tx.insert('joins', {'join_id': 'j3', 'entity': 'untimed', 'receiver': 'code.manager.route'})
    read = [json.loads(item(run, f'code.manager.route#{number}', mapped).stdout) for number in (1, 2, 3)]
    assert [(one['name'], one['title']) for one in read] == [
        ('untimed', 'Untimed memory.'), ('early', 'Early memory.'), ('late', 'Late memory.')]
    after = mj(run, 'create_entities', J([entity('next', 'fact', 'Next.')]), ROUTE, cwd=mapped)
    assert after['items'] == ['code.manager.route#4  Next.']
    with project_transaction(path, write=False) as db:
        recorded = json.loads(db.execute("SELECT value FROM meta WHERE key='module:memory'").fetchone()[0])
    assert (recorded['version'], recorded['compatible_from']) == (5, 2)


@pytest.mark.req('MCP-039')
def test_a_memory_cites_its_evidence_and_a_read_flags_it_stale_once_the_cited_lines_change(run, mapped):
    """cite on create_entities is kept as what the cited lines read as; reads say which citations no longer hold,
    with where the text went, the node's counts count the memory as stale, and a citation naming nothing is refused."""
    source = mapped / 'route.py'
    source.write_text('def route():\n    return eject()\n')
    m(run, 'create_entities', J([{**entity('ejection', 'behavior', 'Routes are ejected.'),
                                 'cite': ['route.py:2', 'route.py:route']}]), ROUTE, cwd=mapped)
    held = mj(run, 'read_graph', ROUTE, cwd=mapped)['entities'][0]
    assert held['cites'] == ['route.py:2', 'route.py:route'] and 'stale' not in held
    source.write_text('# moved down\ndef route():\n    return eject()\n')  # the same text, a line lower
    held = mj(run, 'read_graph', ROUTE, cwd=mapped)['entities'][0]
    assert held['stale'] == ['route.py:2: line 2 changed; the cited text is now at line 3']
    counted = run('map', 'where', 'code.manager.route', cwd=mapped).stdout
    assert '1 stale memory' in counted, counted
    item = json.loads(run('map', 'item', 'code.manager.route', '1', '--json', cwd=mapped).stdout)
    assert 'STALE: route.py:2: line 2 changed' in item['body']
    refused = m(run, 'create_entities', J([{**entity('ghost', 'behavior', 'Nothing.'), 'cite': 'nowhere.py:3'}]),
                ROUTE, cwd=mapped, ok=False)
    assert refused.returncode != 0 and 'names no file' in refused.stderr + refused.stdout
