"""The memory module: the reference memory server's operations over the map's own nodes, BASE-040, LAYER-012, LAYER-013."""
from __future__ import annotations

import json

import pytest

from metaform.data import Store

pytestmark = pytest.mark.kind('fixture')


@pytest.fixture
def mapped(run, tmp_path):
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    store = Store('proj')
    with store.atomic():
        layer = store.layer('intake-1', 'intake', 'The functional map.', kind='intake', mutable=False,
                            hideable=False, provenance={'module': 'intake'}, ready=True)
        store.add_element(layer.name, 'code.manager.route', name='route manager', name_length=2, role='DE')
        store.add_element(layer.name, 'code.probe.echo', name='echo probe', name_length=2, role='SE')
        store.add_join(layer.name, 'code.manager.route', 'code.probe.echo', purpose='Know a route is alive.',
                       function='Sends an echo.', relation='The probe checks the route.', observation='ICMP.')
    return folder


def m(run, *args, cwd, ok=True):
    return run('memory', *args, '--json', cwd=cwd, ok=ok)


def opened(run, cwd, *nodes):
    return json.loads(m(run, 'open-nodes', *nodes, cwd=cwd).stdout)


@pytest.mark.req('LAYER-013')
@pytest.mark.req('BASE-040')
def test_observations_added_at_a_node_are_read_back_by_opening_it(run, mapped):
    m(run, 'add-observations', 'element:code.manager.route', 'Routes are ejected, never packed on delete.',
      'Metric classes hold 25 routes.', cwd=mapped)
    node = opened(run, mapped, 'element:code.manager.route')['nodes'][0]
    assert node['name'] == 'code.manager.route' and node['entityType'] == 'element'
    assert node['observations'] == ['Routes are ejected, never packed on delete.', 'Metric classes hold 25 routes.']


@pytest.mark.req('BASE-040')
@pytest.mark.req('STORE-020')
def test_a_relation_shows_when_opening_either_end(run, mapped):
    m(run, 'create-relations', 'element:code.probe.echo', 'depends_on', 'element:code.manager.route', cwd=mapped)
    probe = opened(run, mapped, 'element:code.probe.echo')
    route = opened(run, mapped, 'element:code.manager.route')
    expected = {'from': 'code.probe.echo', 'to': 'code.manager.route', 'relationType': 'depends_on'}
    assert expected in probe['relations'] and expected in route['relations']


@pytest.mark.req('LAYER-013')
@pytest.mark.req('STORE-020')
def test_a_join_is_a_node_of_memory(run, mapped):
    join_id = Store('proj').joins('code.manager.route').results[0].join_id
    m(run, 'add-observations', f'join:{join_id}', 'The echo times out after 1 s.', cwd=mapped)
    node = opened(run, mapped, f'join:{join_id}')['nodes'][0]
    assert node['entityType'] == 'join' and node['observations'] == ['The echo times out after 1 s.']


@pytest.mark.req('LAYER-012')
@pytest.mark.req('STORE-020')
def test_the_memory_layer_is_made_on_first_write_with_no_provenance(run, mapped, home):
    assert [layer.name for layer in Store('proj').layers(kind='memory').results] == []
    m(run, 'add-observations', 'element:code.manager.route', 'first', cwd=mapped)
    layer = Store('proj').layers(kind='memory').results[0]
    assert (layer.name, layer.module, layer.variable, layer.mutable, layer.ready is not None) == (
        'memory', 'memory', 'What agents have noted at this node.', True, True)
    assert Store('proj').provenance('memory') is None


@pytest.mark.req('BASE-040')
def test_deleting_observations_relations_and_entities_removes_memories_only(run, mapped):
    m(run, 'add-observations', 'element:code.manager.route', 'keep', 'drop', cwd=mapped)
    m(run, 'create-relations', 'element:code.manager.route', 'uses', 'element:code.probe.echo', cwd=mapped)
    m(run, 'delete-observations', 'element:code.manager.route', 'drop', cwd=mapped)
    assert opened(run, mapped, 'element:code.manager.route')['nodes'][0]['observations'] == ['keep']
    m(run, 'delete-relations', 'element:code.manager.route', 'uses', 'element:code.probe.echo', cwd=mapped)
    assert opened(run, mapped, 'element:code.manager.route')['relations'] == []
    m(run, 'delete-entities', 'element:code.manager.route', cwd=mapped)
    node = opened(run, mapped, 'element:code.manager.route')['nodes'][0]
    assert node['observations'] == []
    assert Store('proj').element('code.manager.route') is not None


@pytest.mark.req('BASE-040')
@pytest.mark.req('STORE-020')
def test_search_and_read_graph_group_by_node(run, mapped):
    m(run, 'add-observations', 'element:code.manager.route', 'Routes drift under load.', cwd=mapped)
    m(run, 'add-observations', 'element:code.probe.echo', 'Echoes are cheap.', cwd=mapped)
    found = json.loads(m(run, 'search-nodes', 'drift', cwd=mapped).stdout)
    assert [node['name'] for node in found['nodes']] == ['code.manager.route']
    graph = json.loads(m(run, 'read-graph', cwd=mapped).stdout)
    assert {node['name'] for node in graph['nodes']} == {'code.manager.route', 'code.probe.echo'}


@pytest.mark.req('BASE-040')
@pytest.mark.req('STORE-020')
def test_creating_an_entity_that_is_not_in_the_map_makes_an_element_in_memory(run, mapped):
    made = json.loads(m(run, 'create-entities', 'code.watchdog', 'element', cwd=mapped).stdout)
    assert made['entities'][0]['name'] == 'code.watchdog'
    element = Store('proj').element('code.watchdog')
    assert element is not None and element.layer == 'memory'
    again = json.loads(m(run, 'create-entities', 'code.manager.route', 'element', cwd=mapped).stdout)
    assert again['entities'][0]['existing'] is True


@pytest.mark.req('CLI-003')
def test_an_observation_that_starts_with_a_dash_follows_the_double_dash(run, mapped):
    run('memory', 'add-observations', 'element:code.manager.route', '--', '-40 dBm is the weakest usable signal.',
        cwd=mapped)
    assert opened(run, mapped, 'element:code.manager.route')['nodes'][0]['observations'] == [
        '-40 dBm is the weakest usable signal.']


@pytest.mark.req('LAYER-012')
@pytest.mark.req('LAYER-007')
def test_memory_takes_part_in_select_and_mask(run, mapped):
    m(run, 'add-observations', 'element:code.manager.route', 'visible here', cwd=mapped)
    run('map', 'mask', 'code.manager', 'memory', cwd=mapped)
    view = json.loads(run('map', 'node', 'element:code.manager.route', '--json', cwd=mapped).stdout)
    assert 'memory' not in [group['layer'] for group in view['layers']]
    run('map', 'clear', 'code.manager', 'memory', 'mask', cwd=mapped)
    view = json.loads(run('map', 'node', 'element:code.manager.route', '--json', cwd=mapped).stdout)
    assert 'memory' in [group['layer'] for group in view['layers']]


@pytest.mark.req('LAYER-012')
@pytest.mark.req('STORE-020')
@pytest.mark.req('BASE-044')
def test_an_observation_at_an_element_the_map_does_not_hold_makes_it_in_memory(run, mapped):
    added = json.loads(m(run, 'add-observations', 'element:code.nosuch.node', 'A note.', cwd=mapped).stdout)
    assert added['notices'] and 'memory' in added['notices'][0]['message']
    assert Store('proj').element('code.nosuch.node', raw=True).layer == 'memory'
    assert opened(run, mapped, 'element:code.nosuch.node')['nodes'][0]['observations'] == ['A note.']
