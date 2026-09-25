"""The map module: the data access object's map and layer operations as verbs, BASE-038, MAP and LAYER."""
from __future__ import annotations

import json

import pytest

from metaform.data import Node, Store

pytestmark = pytest.mark.kind('fixture')

PROVENANCE = ['module=test', 'prompt=Write the fixture.', 'role=fixture writer']


@pytest.fixture
def mapped(run, tmp_path):
    """A registered project with a small intake map: a cook receiving from a timer receiving from an alarm."""
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    store = Store('proj')
    with store.atomic():
        layer = store.layer('intake-1', 'intake', 'The functional map.', kind='intake', mutable=False,
                            hideable=False, provenance={'module': 'intake'}, ready=True)
        store.add_element(layer.name, 'stakeholder.cook.home', name='Home cook', name_length=2, role='VE')
        store.add_element(layer.name, 'code.timer.kitchen', name='kitchen timer', name_length=2, role='DE')
        store.add_element(layer.name, 'code.alarm.audible', name='audible alarm', name_length=2, role='SE')
        store.add_join(layer.name, 'stakeholder.cook.home', 'code.timer.kitchen', purpose='Know when a dish is done.',
                       function='Counts down and rings.', relation='The timer tells the cook.',
                       observation='One countdown per dish.')
        store.add_join(layer.name, 'code.timer.kitchen', 'code.alarm.audible', purpose='Get attention.',
                       function='Plays a tone.', relation='The alarm rings for the timer.', observation='A piezo.')
    return folder


def j(run, *args, cwd):
    return json.loads(run('map', *args, '--json', cwd=cwd).stdout)


def k(run, cwd, *args, ok=True):
    return run('map', 'knowledge', *args, '--json', cwd=cwd, ok=ok)


@pytest.mark.req('MAP-012')
def test_an_address_reads_as_its_name_reversed():
    from metaform.data import reading, short_name
    assert reading('code.bus.data.event') == 'event data bus code'
    assert reading('data.bill_of_materials') == 'bill of materials data'
    assert short_name('code.engine.game', 2) == 'game engine'
    assert short_name('code.engine.game', 9) == 'game engine code'
    assert short_name('code.engine.game', None) == 'game engine code'


@pytest.mark.req('MAP-012')
@pytest.mark.req('BASE-038')
def test_an_element_read_shows_its_address_reading_and_role(run, mapped):
    element = j(run, 'element', 'code.timer.kitchen', cwd=mapped)
    assert (element['address'], element['reading'], element['role'], element['short_name']) == (
        'code.timer.kitchen', 'kitchen timer code', 'DE', 'kitchen timer')


@pytest.mark.req('MAP-010')
@pytest.mark.req('MAP-011')
def test_every_prefix_is_a_type_and_properties_apply_from_the_trunk(run, mapped):
    k(run, mapped, 'op=create', 'layer=practices', 'variable=Practices for each type.', 'mutable=true',
      'hideable=true', *PROVENANCE)
    k(run, mapped, 'op=add-element', 'layer=practices', 'address=code')
    k(run, mapped, 'op=add-element', 'layer=practices', 'address=code.engine.game.fps')
    k(run, mapped, 'op=add-property', 'layer=practices', 'element=code', 'value="Name things for what they do."')
    k(run, mapped, 'op=add-property', 'layer=practices', 'element=code.engine.game', 'value="Fixed timestep."',
      ok=False)
    k(run, mapped, 'op=add-element', 'layer=practices', 'address=code.engine.game')
    k(run, mapped, 'op=add-property', 'layer=practices', 'element=code.engine.game', 'value="Fixed timestep."')
    k(run, mapped, 'op=finish', 'layer=practices')
    assert j(run, 'children', 'code.engine', cwd=mapped)['results'] == ['code.engine.game']
    at_game = [item['value'] for item in j(run, 'context', 'code.engine.game', cwd=mapped)['applying']]
    assert at_game == ['Name things for what they do.', 'Fixed timestep.']
    at_code = j(run, 'context', 'code', cwd=mapped)
    assert [item['value'] for item in at_code['applying']] == ['Name things for what they do.']
    assert 'Fixed timestep.' in [item['value'] for item in at_code['visible']]


@pytest.mark.req('LAYER-018')
@pytest.mark.req('LAYER-016')
@pytest.mark.req('MAP-044')
def test_a_knowledge_layer_is_built_object_by_object_then_finished(run, mapped, tmp_path):
    other = tmp_path / 'other-agent'
    other.mkdir()
    run('set', '--project', 'proj', cwd=other)
    k(run, mapped, 'op=create', 'layer=practices-cpp', 'variable=C++ practice at each node.', 'mutable=true',
      'hideable=true', 'tags=["practices"]', *PROVENANCE)
    added = json.loads(k(run, mapped, 'op=add-item', 'layer=practices-cpp', 'node=element:code.timer.kitchen',
                         'value="Prefer steady_clock."').stdout)
    doomed = json.loads(k(run, mapped, 'op=add-item', 'layer=practices-cpp', 'node=element:code.timer.kitchen',
                          'value="A mistake."').stdout)
    k(run, mapped, 'op=add-element', 'layer=practices-cpp', 'address=code.watchdog')
    joined = json.loads(k(run, mapped, 'op=add-join', 'layer=practices-cpp', 'receiver=code.timer.kitchen',
                          'provider=code.watchdog', 'purpose=Recover from a hang.', 'function=Restarts the loop.',
                          'relation=The watchdog restarts the timer.', 'observation=Not built yet.').stdout)
    k(run, mapped, 'op=edit', 'layer=practices-cpp', f'id={added["item_id"]}', 'value="Prefer steady_clock always."')
    k(run, mapped, 'op=remove', 'layer=practices-cpp', f'id={doomed["item_id"]}')

    def seen(cwd):
        view = j(run, 'node', 'element:code.timer.kitchen', cwd=cwd)
        return [item['value'] for group in view['layers'] if group['layer'] == 'practices-cpp' for item in group['items']]
    assert seen(other) == []
    assert [item['value'] for item in j(run, 'layer', 'practices-cpp', cwd=mapped)['results']] == \
        ['Prefer steady_clock always.']
    k(run, mapped, 'op=finish', 'layer=practices-cpp')
    assert seen(other) == ['Prefer steady_clock always.']
    receiver_joins = j(run, 'joins', 'code.timer.kitchen', cwd=other)['results']
    assert {(join['provider_address'], join['layer']) for join in receiver_joins} == {
        ('code.alarm.audible', 'intake-1'), ('code.watchdog', 'practices-cpp')}
    k(run, mapped, 'op=edit', 'layer=practices-cpp', f'id={added["item_id"]}', 'value="Use steady_clock."')
    assert seen(other) == ['Use steady_clock.']
    run('set', '--layers', 'intake-1', cwd=other)
    assert seen(other) == []
    assert joined['join_id'] not in [join['join_id'] for join in j(run, 'joins', 'code.timer.kitchen', cwd=other)['results']]
    raw = json.loads(run('map', 'joins', 'code.timer.kitchen', '--raw', '--json', cwd=other).stdout)['results']
    assert joined['join_id'] in [join['join_id'] for join in raw]


@pytest.mark.req('LAYER-008')
@pytest.mark.req('LAYER-007')
@pytest.mark.req('LAYER-006')
def test_the_raw_and_in_context_node_reads_differ_by_masked_and_hidden_layers(run, mapped):
    for name in ('kept', 'masked', 'hidden'):
        k(run, mapped, 'op=create', f'layer={name}', f'variable={name} notes.', 'mutable=true', 'hideable=true',
          *PROVENANCE)
        k(run, mapped, 'op=add-item', f'layer={name}', 'node=element:code.timer.kitchen', f'value="{name} note"')
        k(run, mapped, 'op=finish', f'layer={name}')
    run('map', 'mask', 'code.timer', 'masked', cwd=mapped)
    run('map', 'hide', 'hidden', '--confirm', cwd=mapped)
    in_context = {group['layer'] for group in j(run, 'node', 'element:code.timer.kitchen', cwd=mapped)['layers']}
    raw = {group['layer'] for group in json.loads(run('map', 'node', 'element:code.timer.kitchen', '--raw', '--json',
                                                      cwd=mapped).stdout)['layers']}
    assert raw - in_context == {'masked', 'hidden'}
    run('map', 'clear', 'code.timer', 'masked', 'mask', cwd=mapped)
    run('map', 'unhide', 'hidden', cwd=mapped)
    assert {group['layer'] for group in j(run, 'node', 'element:code.timer.kitchen', cwd=mapped)['layers']} == raw


@pytest.mark.req('LAYER-019')
@pytest.mark.req('STORE-038')
def test_layers_are_tagged_listed_and_filtered(run, mapped):
    k(run, mapped, 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true',
      'tags=["practices"]', *PROVENANCE)
    k(run, mapped, 'op=finish', 'layer=notes')
    run('map', 'tag', 'notes', 'mgm', cwd=mapped)
    listed = j(run, 'layers', 'tag=practices', cwd=mapped)['results']
    assert [(layer['name'], sorted(layer['tags']), layer['ready'] is not None) for layer in listed] == [
        ('notes', ['mgm', 'practices'], True)]
    run('map', 'untag', 'notes', 'practices', cwd=mapped)
    assert j(run, 'layers', 'tag=practices', cwd=mapped)['results'] == []


@pytest.mark.req('LAYER-015')
@pytest.mark.req('STORE-040')
def test_a_blind_spot_is_answered_and_only_a_person_approves_it(run, mapped):
    k(run, mapped, 'op=create', 'layer=challenge.blind', 'variable=Blind spots.', 'mutable=true', 'hideable=true',
      *PROVENANCE, 'blinded=true')
    k(run, mapped, 'op=add-element', 'layer=challenge.blind', 'address=code.watchdog')
    k(run, mapped, 'op=add-join', 'layer=challenge.blind', 'receiver=code.timer.kitchen', 'provider=code.watchdog',
      'purpose=Recover.', 'function=Restarts.', 'relation=r', 'observation=o')
    challenge = json.loads(k(run, mapped, 'op=add-item', 'layer=challenge.blind', 'node=element:code.watchdog',
                             'value="Nothing recovers a hung loop."').stdout)
    k(run, mapped, 'op=finish', 'layer=challenge.blind')
    refused = run('map', 'answer', challenge['item_id'], 'C', cwd=mapped, ok=False)
    assert refused.returncode == 2
    refused = run('map', 'approve', challenge['item_id'], cwd=mapped, ok=False)
    assert refused.returncode == 2
    run('map', 'answer', challenge['item_id'], 'B', cwd=mapped)
    run('map', 'approve', challenge['item_id'], cwd=mapped)
    assert j(run, 'element', 'code.watchdog', cwd=mapped)['state'] == 'plan'
    listed = run('help', 'map', cwd=mapped).stdout
    assert 'approve' in listed


@pytest.mark.req('STORE-023')
@pytest.mark.req('BASE-038')
def test_a_map_verb_outside_a_project_names_the_way_to_register_one(run, tmp_path):
    folder = tmp_path / 'nowhere'
    folder.mkdir()
    refused = run('map', 'where', 'code', cwd=folder, ok=False)
    assert refused.returncode == 2
    assert refused.stderr.splitlines()[-1] == 'Next: metaform add project <id> <path>'


@pytest.mark.req('BASE-038')
def test_each_read_verb_returns_what_its_operation_returns(run, mapped):
    store = Store('proj')
    kitchen = store.element('code.timer.kitchen')
    assert j(run, 'element', 'code.timer.kitchen', cwd=mapped)['element_id'] == kitchen.element_id
    assert j(run, 'identity', 'code.timer.kitchen', cwd=mapped) == json.loads(json.dumps(
        store.identity('code.timer.kitchen').to_dict()))
    assert j(run, 'where', 'code.alarm.audible', cwd=mapped)['element']['address'] == 'code.alarm.audible'
    assert j(run, 'stack', cwd=mapped) == {'results': [], 'next': None}
    assert [form['name'] for form in j(run, 'metaforms', cwd=mapped)['results']] == ['main']
    join = store.joins('code.timer.kitchen').results[0]
    assert j(run, 'history', join.join_id, cwd=mapped)['results'][0]['op'] == 'add'
    assert j(run, 'search', 'kitchen', cwd=mapped)['results'][0]['value']['descriptor']['name'] == 'kitchen timer'
    listed = j(run, 'joins', 'code.timer.kitchen', 'as=provider', cwd=mapped)['results']
    assert [join['receiver_address'] for join in listed] == ['stakeholder.cook.home']
    node = Node('element', 'code.timer.kitchen')
    assert j(run, 'links', str(node), cwd=mapped) == {'results': [], 'next': None}
