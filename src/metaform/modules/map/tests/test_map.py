"""The map module: the data access object's map and layer operations as verbs, BASE-038, MAP and LAYER."""
from __future__ import annotations

import json
import re

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
        store.add_element(layer.name, 'stakeholder.cook.home', name_length=2, role='VE')
        store.add_element(layer.name, 'code.timer.kitchen', name_length=2, role='DE')
        store.add_element(layer.name, 'code.alarm.audible', name_length=2, role='SE')
        store.add_join(layer.name, 'stakeholder.cook.home', 'code.timer.kitchen', name='kitchen timer',
                       purpose='Know when a dish is done.',
                       function='Counts down and rings.', relation='The timer tells the cook.',
                       observation='One countdown per dish.')
        store.add_join(layer.name, 'code.timer.kitchen', 'code.alarm.audible', purpose='Get attention.',
                       function='Plays a tone.', relation='The alarm rings for the timer.', observation='A piezo.')
    return folder


def j(run, *args, cwd):
    return json.loads(run('map', *args, '--json', cwd=cwd).stdout)


def k(run, cwd, *args, ok=True):
    return run('map', 'knowledge', *args, '--json', cwd=cwd, ok=ok)


def without_open_work(value):
    """The parsed structure with every `open_work` field removed, wherever it sits."""
    if isinstance(value, dict):
        return {key: without_open_work(inner) for key, inner in value.items() if key != 'open_work'}
    if isinstance(value, list):
        return [without_open_work(inner) for inner in value]
    return value


def open_work_in(value):
    """Every non-empty `open_work` in a parsed structure, in document order."""
    if isinstance(value, dict):
        return [inner for key, inner in value.items() if key == 'open_work' and inner] + [
            found for inner in value.values() for found in open_work_in(inner)]
    if isinstance(value, list):
        return [found for inner in value for found in open_work_in(inner)]
    return []


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
    made = json.loads(k(run, mapped, 'op=add-property', 'layer=practices', 'element=code.engine.game',
                        'value="Fixed timestep."').stdout)
    assert made['address'] == 'code.engine.game' and made['notices']
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
    run('map', 'tag', 'notes', 'review', cwd=mapped)
    listed = j(run, 'layers', 'tag=practices', cwd=mapped)['results']
    assert [(layer['name'], sorted(layer['tags']), layer['ready'] is not None) for layer in listed] == [
        ('notes', ['practices', 'review'], True)]
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
    unlinked = run('map', 'answer', challenge['item_id'], 'C', cwd=mapped)
    assert re.search(r'^Notice: link: ', unlinked.stdout, re.MULTILINE)
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
@pytest.mark.req('STORE-025')
@pytest.mark.req('LAYER-017')
def test_where_is_one_read_of_an_address_small_unless_full_is_asked(run, mapped):
    run('map', 'work', 'op=add', 'node=element:code.alarm.audible', 'condition=tbd', 'note=no speaker yet',
        'task=wire the piezo', cwd=mapped)
    kitchen = j(run, 'where', 'code.timer.kitchen', cwd=mapped)
    assert set(kitchen) == {'kind', 'element', 'provides', 'receives'}
    assert (kitchen['element']['short_name'], kitchen['element']['role']) == ('kitchen timer', 'DE')
    assert [(join['receiver'], join['purpose'], join['function'], join['name']) for join in kitchen['provides']] == [
        ('stakeholder.cook.home', 'Know when a dish is done.', 'Counts down and rings.', 'kitchen timer')]
    assert [(join['provider'], join['function'], join['layer']) for join in kitchen['receives']] == [
        ('code.alarm.audible', 'Plays a tone.', 'intake-1')]
    alarm = j(run, 'where', 'code.alarm.audible', cwd=mapped)
    assert alarm['work'] == [{'condition': 'tbd', 'note': 'no speaker yet', 'task': 'wire the piezo'}]
    assert 'element_id' not in alarm['element'] and 'join_id' not in alarm['provides'][0]
    full = j(run, 'where', 'code.alarm.audible', 'full=true', cwd=mapped)
    store = Store('proj')
    assert full['element']['element_id'] == store.element('code.alarm.audible').element_id
    assert full['provides'][0]['join_id'] == store.joins('code.timer.kitchen').results[0].join_id
    assert full['work'][0]['work_id'] and full['held'] is None
    assert 'map_where' in run('help', 'map', cwd=mapped).stdout or 'where' in run('help', 'map', cwd=mapped).stdout


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
    notes = store.layer('memory', 'memory', 'What agents have noted at this node.', kind='memory', mutable=True,
                        hideable=True, ready=True)
    store.add_item(notes.name, Node('element', 'code.timer.kitchen'), 'The kitchen timer drifts under load.')
    found = j(run, 'search', 'kitchen', cwd=mapped)
    assert found == json.loads(json.dumps(store.search('kitchen').to_dict()))
    assert [item['value'] for item in found['results']] == ['The kitchen timer drifts under load.']
    listed = j(run, 'joins', 'code.timer.kitchen', 'as=provider', cwd=mapped)['results']
    assert [join['receiver_address'] for join in listed] == ['stakeholder.cook.home']
    node = Node('element', 'code.timer.kitchen')
    assert j(run, 'links', str(node), cwd=mapped) == {'results': [], 'next': None}


@pytest.mark.req('BASE-038')
@pytest.mark.req('MAP-020')
@pytest.mark.req('STORE-009')
@pytest.mark.req('BASE-043')
def test_a_knowledge_layer_names_a_functionality_on_its_join_and_a_name_sent_for_an_element_is_kept_in_its_extra(
        run, mapped):
    """Rich, 2026-09-27: the project's name for a functionality goes on the join; an element is its address,
    name_length and role, so a name sent with add-element is kept in the element's extra and named, BASE-043."""
    k(run, mapped, 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true', *PROVENANCE)
    element = json.loads(k(run, mapped, 'op=add-element', 'layer=notes', 'address=code.display.lcd',
                           'name=time display', 'name_length=2').stdout)
    assert (element['short_name'], element['name_length'], element['extra']) == ('lcd display', 2,
                                                                                   {'name': 'time display'})
    assert 'name' not in element and [notice['where'] for notice in element['notices']] == ['name']
    join = json.loads(k(run, mapped, 'op=add-join', 'layer=notes', 'receiver=code.display.lcd',
                        'provider=code.timer.kitchen', 'name=time left', 'purpose=Show the time left.',
                        'function=Reports the time left.', 'relation=The timer feeds the display.',
                        'observation=An LCD.').stdout)
    assert (join['name'], join['extra']) == ('time left', None) and join['notices'] == []
    assert [held.name for held in Store('proj').joins('code.display.lcd', raw=True).results] == ['time left']


@pytest.mark.req('BASE-043')
@pytest.mark.req('BASE-044')
@pytest.mark.req('STORE-021')
def test_an_unknown_named_field_is_kept_in_the_records_extra_with_a_notice(run, mapped):
    k(run, mapped, 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true', *PROVENANCE)
    added = run('map', 'knowledge', 'op=add-item', 'layer=notes', 'node=element:code.timer.kitchen', 'value="n"',
                'colour=red', cwd=mapped)
    assert re.search(r'^Notice: colour: .*extra', added.stdout, re.MULTILINE)
    item = Store('proj').layer_items('notes').results[0]
    assert item.extra == {'colour': 'red'}


@pytest.mark.req('LAYER-001')
@pytest.mark.req('BASE-044')
def test_a_write_sent_without_a_layer_goes_to_a_new_unnamed_layer(run, mapped):
    added = json.loads(k(run, mapped, 'op=add-element', 'address=code.orphan.idea').stdout)
    unnamed = [layer.name for layer in Store('proj').layers(limit=0).results if layer.name.startswith('unnamed-')]
    assert len(unnamed) == 1 and re.fullmatch(r'unnamed-\d{8}T\d{6}Z', unnamed[0])
    assert added['layer'] == unnamed[0] and any(unnamed[0] in notice['message'] for notice in added['notices'])


@pytest.mark.req('STORE-034')
@pytest.mark.req('BASE-044')
def test_a_correction_moves_a_join_by_its_receiver_and_never_moves_an_element(run, mapped):
    store = Store('proj')
    join = store.joins('code.timer.kitchen').results[0]
    kitchen = store.element('code.timer.kitchen').element_id
    k(run, mapped, 'op=create', 'layer=fix-a', 'kind=correction', 'variable=Fixes.', 'mutable=false',
      'hideable=false', *PROVENANCE)
    moved = run('map', 'knowledge', 'op=correct', 'layer=fix-a', f'id={join.join_id}', 'purpose=First fix.',
                'receiver=stakeholder.cook.home', 'reason=r', cwd=mapped)
    assert 'Notice:' not in moved.stdout
    kept = run('map', 'knowledge', 'op=correct', 'layer=fix-a', f'id={kitchen}', 'address=code.timer.egg',
               'reason=r', cwd=mapped)
    assert re.search(r'^Notice: address: ', kept.stdout, re.MULTILINE)
    k(run, mapped, 'op=finish', 'layer=fix-a')
    after = {found.join_id: found for found in Store('proj').joins('stakeholder.cook.home').results}[join.join_id]
    assert (after.purpose, after.receiver_address) == ('First fix.', 'stakeholder.cook.home')
    assert Store('proj').element('code.timer.kitchen').element_id == kitchen
    assert Store('proj').element('code.timer.egg') is None


@pytest.mark.req('STORE-039')
@pytest.mark.req('STORE-008')
@pytest.mark.req('BASE-044')
def test_a_property_named_by_node_attaches_by_the_nodes_kind(run, mapped):
    k(run, mapped, 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true', *PROVENANCE)
    join = Store('proj').joins('stakeholder.cook.home').results[0]
    at_element = json.loads(k(run, mapped, 'op=add-property', 'layer=notes', 'element=element:code.timer.kitchen',
                              'value="a"').stdout)
    assert at_element['address'] == 'code.timer.kitchen' and at_element['notices'] == []
    at_type = json.loads(k(run, mapped, 'op=add-property', 'layer=notes', 'element=type:code', 'value="b"').stdout)
    assert at_type['address'] == 'code' and at_type['notices']
    at_join = json.loads(k(run, mapped, 'op=add-property', 'layer=notes', f'element=join:{join.join_id}',
                           'value="c"').stdout)
    assert at_join['orphaned'] and at_join['extra'] == {'target': f'join:{join.join_id}'} and at_join['notices']
    store = Store('proj')
    assert [store.where(address, raw=True) for address in ('type:code', f'join:{join.join_id}')] == [None, None]


@pytest.mark.req('CLI-033')
@pytest.mark.req('LAYER-019')
@pytest.mark.req('BASE-036')
def test_layers_stack_and_metaforms_read_as_one_aligned_row_each(run, mapped):
    k(run, mapped, 'op=create', 'layer=practices-cpp', 'variable=C++ practice here.', 'mutable=true', 'hideable=true',
      'tags=["practices"]', *PROVENANCE)
    k(run, mapped, 'op=finish', 'layer=practices-cpp')
    k(run, mapped, 'op=create', 'layer=draft', 'variable=Drafts.', 'mutable=true', 'hideable=true', *PROVENANCE)
    k(run, mapped, 'op=create', 'layer=fix-1', 'kind=correction', 'variable=Fixes.', 'mutable=false',
      'hideable=false', *PROVENANCE)
    join = Store('proj').joins('code.timer.kitchen').results[0]
    k(run, mapped, 'op=correct', 'layer=fix-1', f'id={join.join_id}', 'function=Plays a loud tone.', 'reason=r')
    k(run, mapped, 'op=finish', 'layer=fix-1')

    def rows(*args):
        lines = run('map', *args, cwd=mapped).stdout.splitlines()
        starts = {len(line) - len(line[len(line.split()[0]):].lstrip()) for line in lines}
        assert len(starts) == 1, lines
        return {line.split()[0]: line.split() for line in lines}
    layers = rows('layers')
    assert layers['intake-1'] == ['intake-1', 'intake', 'intake', 'ready', 'on']
    assert layers['practices-cpp'] == ['practices-cpp', 'layer', 'test', 'practices', 'ready', 'on']
    assert layers['draft'] == ['draft', 'layer', 'test', 'building', 'off']
    assert layers['fix-1'] == ['fix-1', 'correction', 'test', 'ready', 'applied']
    assert list(rows('stack')) == ['fix-1']
    metaforms = rows('metaforms')
    assert metaforms['main'][-1] == 'active'
    assert {layer['name'] for layer in j(run, 'layers', cwd=mapped)['results']} == set(layers)


@pytest.mark.req('BASE-044')
@pytest.mark.req('BASE-043')
def test_a_noun_the_operation_does_not_read_is_kept_in_extra_or_named_as_ignored(run, mapped):
    k(run, mapped, 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true', *PROVENANCE)
    made = json.loads(k(run, mapped, 'op=add-property', 'layer=notes', 'element=code.timer.kitchen', 'value="v"',
                        'key=path').stdout)
    assert made['extra'] == {'key': 'path'} and [notice['where'] for notice in made['notices']] == ['key']
    finished = json.loads(k(run, mapped, 'op=finish', 'layer=notes', 'reason=done').stdout)
    assert [notice['where'] for notice in finished['notices']] == ['reason']
    assert 'ignored' in finished['notices'][0]['message'] and finished['ready']
    join = Store('proj').joins('code.timer.kitchen').results[0]
    k(run, mapped, 'op=create', 'layer=fix-1', 'kind=correction', 'variable=Fixes.', 'mutable=false',
      'hideable=false', *PROVENANCE)
    corrected = json.loads(k(run, mapped, 'op=correct', 'layer=fix-1', f'id={join.join_id}', 'purpose=Fixed.',
                             'reason=r', 'variable=x').stdout)
    assert [notice['where'] for notice in corrected['notices']] == ['variable']
    assert 'ignored' in corrected['notices'][0]['message'] and corrected['fields']['extra'] is None


def said(result):
    return [(notice['where'], notice['message']) for notice in result['notices']]


@pytest.mark.req('BASE-044')
@pytest.mark.req('BASE-038')
@pytest.mark.req('LAYER-018')
@pytest.mark.req('LAYER-002')
def test_a_knowledge_write_missing_a_field_its_record_can_hold_empty_is_stored_with_a_notice_for_it(run, mapped):
    made = json.loads(k(run, mapped, 'op=create', 'layer=bare', *PROVENANCE).stdout)
    assert (made['name'], made['variable'], made['mutable'], made['hideable']) == ('bare', '', False, False)
    assert sorted(notice['where'] for notice in made['notices']) == ['hideable', 'mutable', 'variable']
    assert {where: message for where, message in said(made) if where != 'variable'} == {
        'mutable': 'mutable is missing; stored as false.', 'hideable': 'hideable is missing; stored as false.'}

    joined = json.loads(k(run, mapped, 'op=add-join', 'layer=bare', 'receiver=code.timer.kitchen',
                          'provider=code.alarm.audible').stdout)
    empty = ('purpose', 'function', 'relation', 'observation')
    assert said(joined) == [(field, f'{field} is missing; stored empty.') for field in empty]
    stored = {join.join_id: join for join in Store('proj').joins('code.timer.kitchen', raw=True).results}
    assert stored[joined['join_id']].layer == 'bare'
    assert [getattr(stored[joined['join_id']], field) for field in empty] == [None, None, None, None]

    item = json.loads(k(run, mapped, 'op=add-item', 'layer=bare', 'node=element:code.timer.kitchen').stdout)
    held = json.loads(k(run, mapped, 'op=add-property', 'layer=bare', 'element=code.timer.kitchen').stdout)
    for written in (item, held):
        assert written['value'] is None and said(written) == [('value', 'value is missing; stored empty.')]

    ref = json.loads(k(run, mapped, 'op=add-ref', 'layer=bare', f'owner={joined["join_id"]}').stdout)
    assert (ref['key'], ref['value']) == ('', '')
    assert said(ref) == [('key', 'key is missing; stored empty.'), ('value', 'value is missing; stored empty.')]
    numbered = json.loads(k(run, mapped, 'op=add-ref', 'layer=bare', f'owner={joined["join_id"]}', 'key=line',
                            'value=12').stdout)
    assert (numbered['key'], numbered['value']) == ('line', '12') and [where for where, _ in said(numbered)] == ['value']
    stored = {join.join_id: join for join in Store('proj').joins('code.timer.kitchen', raw=True).results}
    assert [(found.key, found.value) for found in stored[joined['join_id']].refs] == [('', ''), ('line', '12')]

    edited = json.loads(k(run, mapped, 'op=edit', f'id={item["item_id"]}', 'value="Set later."').stdout)
    removed = json.loads(k(run, mapped, 'op=remove', f'id={held["property_id"]}').stdout)
    assert [where for where, _ in said(edited)] == ['layer'] and [where for where, _ in said(removed)] == ['layer']
    assert [found.value for found in Store('proj').layer_items('bare').results] == ['Set later.']

    k(run, mapped, 'op=create', 'layer=fix-1', 'kind=correction', 'variable=Fixes.', 'mutable=false',
      'hideable=false', *PROVENANCE)
    intake_join = Store('proj').joins('code.timer.kitchen').results[0]
    corrected = json.loads(k(run, mapped, 'op=correct', 'layer=fix-1', f'id={intake_join.join_id}',
                             'purpose=Get the cook back.').stdout)
    assert said(corrected) == [('reason', 'reason is missing; stored empty.')]


@pytest.mark.req('BASE-038')
@pytest.mark.req('BASE-044')
@pytest.mark.req('STORE-042')
def test_a_map_write_missing_what_its_record_cannot_be_stored_without_stops_once_and_writes_nothing(run, mapped):
    k(run, mapped, 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true', *PROVENANCE)
    join = Store('proj').joins('code.timer.kitchen').results[0].join_id
    before = run('export', cwd=mapped).stdout
    stops = [
        ('op', ['knowledge', 'layer=notes']),
        ('op', ['knowledge', 'op=paint', 'layer=notes']),
        ('layer', ['knowledge', 'op=create', 'variable=x', 'mutable=true', 'hideable=true']),
        ('layer', ['knowledge', 'op=finish']),
        ('layer', ['knowledge', 'op=peel']),
        ('layer', ['knowledge', 'op=discard']),
        ('layer', ['knowledge', 'op=add-plan', 'element=code.alarm.audible']),
        ('layer', ['knowledge', 'op=correct', f'id={join}', 'reason=r']),
        ('kind', ['knowledge', 'op=create', 'layer=odd', 'kind=memory', 'variable=x', 'mutable=true',
                  'hideable=true']),
        ('address', ['knowledge', 'op=add-element', 'layer=notes']),
        ('address', ['knowledge', 'op=add-subtype', 'layer=notes', f'join={join}']),
        ('receiver', ['knowledge', 'op=add-join', 'provider=code.alarm.audible', 'purpose=p']),
        ('provider', ['knowledge', 'op=add-join', 'layer=notes', 'receiver=code.timer.kitchen']),
        ('join', ['knowledge', 'op=add-subtype', 'layer=notes', 'address=code.alarm.audible.piezo']),
        ('element', ['knowledge', 'op=add-property', 'layer=notes', 'value="v"']),
        ('element', ['knowledge', 'op=add-plan', 'layer=notes']),
        ('node', ['knowledge', 'op=add-item', 'layer=notes', 'value="v"']),
        ('owner', ['knowledge', 'op=add-ref', 'layer=notes', 'key=path', 'value="alarm.c"']),
        ('id', ['knowledge', 'op=edit', 'layer=notes', 'value="v"']),
        ('id', ['knowledge', 'op=remove', 'layer=notes']),
        ('id', ['knowledge', 'op=correct', 'layer=notes', 'reason=r']),
        ('op', ['work', 'op=paint']),
        ('node', ['work', 'op=add', 'condition=tbd']),
        ('id', ['work', 'op=edit', 'condition=tbd']),
        ('id', ['work', 'op=done']),
    ]
    for field, words in stops:
        stopped = run('map', *words, cwd=mapped, ok=False)
        lines = stopped.stderr.splitlines()
        assert stopped.returncode == 2 and len(lines) == 2, (words, stopped.stderr)
        assert lines[0].startswith('Error: ') and field in lines[0] and lines[1].startswith('Next: '), (words, lines)
    assert run('export', cwd=mapped).stdout == before, 'a stopped call wrote something'


@pytest.mark.req('BASE-038')
@pytest.mark.req('MAP-020')
def test_add_join_and_add_subtype_keep_ef_and_verb_in_their_own_fields(run, mapped):
    k(run, mapped, 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true', *PROVENANCE)
    joined = json.loads(k(run, mapped, 'op=add-join', 'layer=notes', 'receiver=code.timer.kitchen',
                          'provider=code.alarm.audible', 'name=done alarm', 'purpose=Get attention.',
                          'function=Plays a tone.', 'ef=Function', 'relation=rings for the timer', 'verb=rings',
                          'observation=A piezo.').stdout)
    assert (joined['name'], joined['ef'], joined['verb'], joined['extra'], joined['notices']) == (
        'done alarm', 'Function', 'rings', None, [])
    inside = json.loads(k(run, mapped, 'op=add-subtype', 'layer=notes', f'join={joined["join_id"]}',
                          'address=code.alarm.audible.piezo', 'name=buzzer', 'function=Buzzes.', 'ef=Encounter',
                          'relation=buzzes when driven', 'verb=buzzes', 'observation=A disc.').stdout)
    assert (inside['name'], inside['ef'], inside['verb'], inside['extra'], inside['notices']) == (
        'buzzer', 'Encounter', 'buzzes', None, [])
    store = Store('proj')
    stored = {join.join_id: join for join in store.joins('code.timer.kitchen', raw=True).results}[joined['join_id']]
    assert (stored.name, stored.ef, stored.verb, stored.extra) == ('done alarm', 'Function', 'rings', None)
    (subtype,) = store.subtypes(joined['join_id'], raw=True).results
    assert (subtype.name, subtype.ef, subtype.verb, subtype.extra) == ('buzzer', 'Encounter', 'buzzes', None)


@pytest.mark.req('BASE-038')
@pytest.mark.req('BASE-044')
@pytest.mark.req('STORE-042')
def test_a_work_record_sent_without_a_condition_is_stored_empty_with_a_notice(run, mapped):
    added = j(run, 'work', 'op=add', 'node=element:code.alarm.audible', 'task=decide what it is', cwd=mapped)
    assert (added['condition'], added['task'], added['done']) == ('', 'decide what it is', None)
    assert said(added) == [('condition', 'condition is missing; stored empty.')]
    listed = j(run, 'work', 'node=element:code.alarm.audible', cwd=mapped)['results']
    assert [(row['work_id'], row['condition']) for row in listed] == [(added['work_id'], '')]


@pytest.mark.req('BASE-038')
@pytest.mark.req('MAP-046')
@pytest.mark.req('STORE-042')
def test_work_records_are_added_edited_listed_and_done_through_one_verb_and_never_change_the_map(run, mapped):
    store = Store('proj')
    join = store.joins('code.timer.kitchen').results[0]
    before = json.loads(run('query', 'graph', 'limit=0', '--json', cwd=mapped).stdout)
    added = j(run, 'work', 'op=add', 'node=code.alarm.audible', 'condition=tbd', 'note=in the spec, not built',
              'task=build the piezo driver', 'held=true', cwd=mapped)
    assert (added['kind'], added['address'], added['condition'], added['held'], added['reviewed'], added['done']) == (
        'element', 'code.alarm.audible', 'tbd', True, False, None)
    on_join = j(run, 'work', 'op=add', f'node=join:{join.join_id}', 'condition=broken', 'task=fix the tone', cwd=mapped)
    assert (on_join['kind'], on_join['receiver_address'], on_join['provider_address']) == (
        'join', 'code.timer.kitchen', 'code.alarm.audible')
    listed = j(run, 'work', cwd=mapped)['results']
    assert [(row['condition'], row['held']) for row in listed] == [('tbd', True), ('broken', False)]
    assert [row['work_id'] for row in j(run, 'work', 'open=true', 'condition=tbd', cwd=mapped)['results']] == [added['work_id']]
    assert [row['work_id'] for row in j(run, 'work', 'node=element:code.alarm.audible', cwd=mapped)['results']] == [added['work_id']]
    edited = j(run, 'work', 'op=edit', f'id={added["work_id"]}', 'reviewed=true', 'held=false', cwd=mapped)
    assert (edited['reviewed'], edited['held'], edited['task']) == (True, False, 'build the piezo driver')
    done = j(run, 'work', 'op=done', f'id={added["work_id"]}', 'resolution=driver in alarm.c', cwd=mapped)
    assert done['done'] is not None and done['resolution'] == 'driver in alarm.c'
    assert [row['work_id'] for row in j(run, 'work', 'open=false', cwd=mapped)['results']] == [added['work_id']]
    assert j(run, 'element', 'code.alarm.audible', cwd=mapped)['open_work'] == []
    assert j(run, 'joins', 'code.timer.kitchen', cwd=mapped)['results'][0]['open_work'] == ['broken']
    after = json.loads(run('query', 'graph', 'limit=0', '--json', cwd=mapped).stdout)
    # Only open_work may differ between the two graphs: the conditions of the open records, on the join now.
    assert without_open_work(after) == without_open_work(before), 'a work record changed the map'
    assert open_work_in(before) == [] and open_work_in(after) == [['broken']]
    refused = run('map', 'work', 'op=add', 'condition=tbd', '--json', cwd=mapped, ok=False)
    assert refused.returncode == 2 and 'node' in refused.stderr
    unknown = run('map', 'work', 'op=add', 'node=element:code.alarm.audible', 'condition=cruft', 'later=yes', '--json',
                  cwd=mapped, ok=False)
    assert unknown.returncode == 2 and "does not take 'later=yes'" in unknown.stderr  # the chassis grammar, BASE-043
    assert j(run, 'work', 'op=done', f'id={on_join["work_id"]}', 'task=ignored here', cwd=mapped)['notices'][0]['where'] == 'task'
    assert run('help', 'map', 'work', cwd=mapped).stdout.count('tbd') >= 1


@pytest.mark.req('BASE-038')
@pytest.mark.req('MAP-003')
@pytest.mark.req('MAP-030')
def test_knowledge_edit_moves_a_join_by_its_receiver_and_absorbs_it_by_its_parent(run, mapped):
    k(run, mapped, 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true', *PROVENANCE)
    k(run, mapped, 'op=add-element', 'layer=notes', 'address=code.alarm.visual')
    first = json.loads(k(run, mapped, 'op=add-join', 'layer=notes', 'receiver=code.timer.kitchen',
                         'provider=code.alarm.visual', 'purpose=See the end.', 'function=Flashes.', 'relation=r',
                         'observation=o').stdout)
    moved = json.loads(k(run, mapped, 'op=edit', 'layer=notes', f'id={first["join_id"]}',
                         'receiver=stakeholder.cook.home').stdout)
    assert moved['notices'] == []
    store = Store('proj')
    assert first['join_id'] in [join.join_id for join in store.joins('stakeholder.cook.home', raw=True).results]
    assert first['join_id'] not in [join.join_id for join in store.joins('code.timer.kitchen', raw=True).results]
    parent = store.joins('stakeholder.cook.home').results[0].join_id
    k(run, mapped, 'op=edit', 'layer=notes', f'id={first["join_id"]}', f'parent={parent}')
    held = store.subtypes(parent, raw=True).results
    assert [(sub.join_id, sub.address, sub.extra) for sub in held] == [
        (first['join_id'], 'code.alarm.visual', {'purpose': 'See the end.'})]
    assert first['join_id'] not in [join.join_id for join in store.joins('stakeholder.cook.home', raw=True).results]


@pytest.mark.req('BASE-038')
@pytest.mark.req('BASE-044')
@pytest.mark.req('STORE-012')
def test_a_ref_that_is_not_a_key_and_a_value_both_text_is_kept_in_the_extra_and_never_refused(run, mapped):
    k(run, mapped, 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true', *PROVENANCE)
    joined = json.loads(k(run, mapped, 'op=add-join', 'layer=notes', 'receiver=code.timer.kitchen',
                          'provider=code.alarm.audible', 'purpose=p', 'function=f', 'relation=r', 'observation=o',
                          'refs=[["path", "a.c"], ["line", 12]]').stdout)
    assert joined['refs'] == [{'key': 'path', 'value': 'a.c'}]
    assert joined['extra'] == {'refs': [['line', 12]]}
    assert joined['notices'] == [{'where': 'refs', 'message': 'A ref is a key and a value, both text; one was not, '
                                                              'and kept in the extra under refs.'}]
    element = json.loads(k(run, mapped, 'op=add-element', 'layer=notes', 'address=code.display.lcd',
                           'refs=[["line", 12], ["col", 3]]', 'extra={"a": 1}').stdout)
    assert element['refs'] == [] and element['extra'] == {'a': 1, 'refs': [['line', 12], ['col', 3]]}
    assert [notice['message'] for notice in element['notices']] == [
        'A ref is a key and a value, both text; two were not, and kept in the extra under refs.']
    edited = json.loads(k(run, mapped, 'op=edit', f'id={joined["join_id"]}', 'refs=[["line", 12]]').stdout)
    assert 'refs' in [notice['where'] for notice in edited['notices']]
    store = Store('proj')
    stored = {join.join_id: join for join in store.joins('code.timer.kitchen', raw=True).results}[joined['join_id']]
    assert stored.refs == () and stored.extra == {'refs': [['line', 12]]}
