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
        store.add_element(layer.name, 'stakeholder.cook.home', name_length=2, role='CQU')
        store.add_element(layer.name, 'code.timer.kitchen', name_length=2, role='DE')
        store.add_element(layer.name, 'code.alarm.audible', name_length=2, role='SE')
        store.add_join(layer.name, 'stakeholder.cook.home', 'code.timer.kitchen', name='kitchen timer',
                       purpose='Know when a dish is done.',
                       ef='Counts down and rings.')
        store.add_join(layer.name, 'code.timer.kitchen', 'code.alarm.audible', purpose='Get attention.',
                       ef='Plays a tone.')
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
                          'provider=code.watchdog', 'purpose=Recover from a hang.', 'ef=Restarts the loop.').stdout)
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
      'purpose=Recover.', 'ef=Restarts.')
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
    run('map', 'work', 'op=add', 'node=element:code.alarm.audible', 'condition=missing', 'note=no speaker yet',
        'task=wire the piezo', cwd=mapped)
    kitchen = j(run, 'where', 'code.timer.kitchen', cwd=mapped)
    assert set(kitchen) == {'kind', 'element', 'provides', 'receives'}
    assert (kitchen['element']['short_name'], kitchen['element']['role']) == ('kitchen timer', 'DE')
    assert [(join['receiver'], join['purpose'], join['ef'], join['name']) for join in kitchen['provides']] == [
        ('stakeholder.cook.home', 'Know when a dish is done.', 'Counts down and rings.', 'kitchen timer')]
    assert [(join['provider'], join['ef'], join['layer']) for join in kitchen['receives']] == [
        ('code.alarm.audible', 'Plays a tone.', 'intake-1')]
    alarm = j(run, 'where', 'code.alarm.audible', cwd=mapped)
    assert alarm['work'] == [{'work_id': Store('proj').work().results[0].work_id, 'condition': 'missing',
                              'note': 'no speaker yet', 'task': 'wire the piezo'}]
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
def test_a_knowledge_layer_names_an_element_and_a_functionality_on_its_join(run, mapped):
    """Rich, 2026-10-01: a name goes anywhere there is a namespace and name length, the element's own field beside
    name_length; the project's name for a functionality stays on the join."""
    k(run, mapped, 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true', *PROVENANCE)
    element = json.loads(k(run, mapped, 'op=add-element', 'layer=notes', 'address=code.display.lcd',
                           'name=time display', 'name_length=2').stdout)
    assert (element['short_name'], element['name_length'], element['name'], element.get('extra')) == (
        'lcd display', 2, 'time display', None)
    assert element['notices'] == []
    join = json.loads(k(run, mapped, 'op=add-join', 'layer=notes', 'receiver=code.display.lcd',
                        'provider=code.timer.kitchen', 'name=time left', 'purpose=Show the time left.',
                        'ef=Reports the time left.').stdout)
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


@pytest.mark.req('LAYER-025')
@pytest.mark.req('STORE-034')
@pytest.mark.req('BASE-044')
def test_refining_moves_a_join_by_its_receiver_in_the_intake_layer_and_never_moves_an_element(run, mapped):
    store = Store('proj')
    join = store.joins('code.timer.kitchen').results[0]
    kitchen = store.element('code.timer.kitchen').element_id
    layers = [layer.name for layer in store.layers(limit=0).results]
    moved = run('map', 'knowledge', 'op=refine', f'id={join.join_id}', 'purpose=First fix.',
                'receiver=stakeholder.cook.home', 'reason=r', cwd=mapped)
    assert 'Notice:' not in moved.stdout
    kept = run('map', 'knowledge', 'op=refine', f'id={kitchen}', 'address=code.timer.egg', 'reason=r', cwd=mapped)
    assert re.search(r'^Notice: address: ', kept.stdout, re.MULTILINE)
    after = {found.join_id: found for found in Store('proj').joins('stakeholder.cook.home').results}[join.join_id]
    assert (after.purpose, after.receiver_address, after.layer) == ('First fix.', 'stakeholder.cook.home', 'intake-1')
    assert Store('proj').element('code.timer.kitchen').element_id == kitchen
    assert Store('proj').element('code.timer.egg') is None
    assert [layer.name for layer in Store('proj').layers(limit=0).results] == layers
    history = j(run, 'history', join.join_id, cwd=mapped)['results']
    assert [(version['layer'], version['op'], version['fields']['purpose']) for version in history] == [
        ('intake-1', 'add', join.purpose), ('intake-1', 'change', 'First fix.')]


@pytest.mark.req('LAYER-025')
def test_knowledge_creates_no_correction_layer_and_offers_no_correct_or_peel(run, mapped):
    refused = run('map', 'knowledge', 'op=create', 'layer=fix-a', 'kind=correction', 'variable=Fixes.',
                  'mutable=false', 'hideable=false', *PROVENANCE, cwd=mapped, ok=False)
    assert refused.returncode != 0 and 'kind=layer' in refused.stdout + refused.stderr
    for op in ('correct', 'peel'):
        gone = run('map', 'knowledge', f'op={op}', 'layer=intake', 'id=x', 'reason=r', cwd=mapped, ok=False)
        assert gone.returncode != 0 and 'not a knowledge operation' in gone.stdout + gone.stderr
    page = run('help', 'map', 'knowledge', cwd=mapped).stdout
    assert 'refine' in page and 'correction' not in page and 'peel' not in page
    assert 'stack' not in run('help', 'map', cwd=mapped).stdout.split()


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
def test_layers_and_metaforms_read_as_one_aligned_row_each(run, mapped):
    k(run, mapped, 'op=create', 'layer=practices-cpp', 'variable=C++ practice here.', 'mutable=true', 'hideable=true',
      'tags=["practices"]', *PROVENANCE)
    k(run, mapped, 'op=finish', 'layer=practices-cpp')
    k(run, mapped, 'op=create', 'layer=draft', 'variable=Drafts.', 'mutable=true', 'hideable=true', *PROVENANCE)
    join = Store('proj').joins('code.timer.kitchen').results[0]
    k(run, mapped, 'op=refine', f'id={join.join_id}', 'ef=Plays a loud tone.', 'reason=r')

    def rows(*args):
        lines = run('map', *args, cwd=mapped).stdout.splitlines()
        starts = {len(line) - len(line[len(line.split()[0]):].lstrip()) for line in lines}
        assert len(starts) == 1, lines
        return {line.split()[0]: line.split() for line in lines}
    layers = rows('layers')
    assert layers['intake-1'] == ['intake-1', 'intake', 'intake', 'ready', 'on']
    assert layers['practices-cpp'] == ['practices-cpp', 'layer', 'test', 'practices', 'ready', 'on']
    assert layers['draft'] == ['draft', 'layer', 'test', 'building', 'off']
    assert sorted(layers) == ['draft', 'intake-1', 'practices-cpp']  # refining makes no layer, LAYER-025
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
    corrected = json.loads(k(run, mapped, 'op=refine', f'id={join.join_id}', 'purpose=Fixed.',
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
    empty = ('purpose', 'ef')
    assert said(joined) == [(field, f'{field} is missing; stored empty.') for field in empty]
    stored = {join.join_id: join for join in Store('proj').joins('code.timer.kitchen', raw=True).results}
    assert stored[joined['join_id']].layer == 'bare'
    assert [getattr(stored[joined['join_id']], field) for field in empty] == [None, None]

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

    intake_join = Store('proj').joins('code.timer.kitchen').results[0]
    corrected = json.loads(k(run, mapped, 'op=refine', f'id={intake_join.join_id}',
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
        ('layer', ['knowledge', 'op=discard']),
        ('layer', ['knowledge', 'op=add-plan', 'element=code.alarm.audible']),
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
        ('id', ['knowledge', 'op=refine', 'reason=r']),
        ('op', ['work', 'op=paint']),
        ('node', ['work', 'op=add', 'condition=missing']),
        ('id', ['work', 'op=edit', 'condition=missing']),
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
@pytest.mark.req('STORE-011')
def test_add_join_and_add_subtype_keep_purpose_ef_and_verb_in_their_own_fields(run, mapped):
    k(run, mapped, 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true', *PROVENANCE)
    joined = json.loads(k(run, mapped, 'op=add-join', 'layer=notes', 'receiver=code.timer.kitchen',
                          'provider=code.alarm.audible', 'name=done alarm', 'purpose=Get attention.',
                          'ef=Plays a tone.', 'verb=rings').stdout)
    assert (joined['name'], joined['verb'], joined['extra'], joined['notices']) == (
        'done alarm', 'rings', None, [])
    inside = json.loads(k(run, mapped, 'op=add-subtype', 'layer=notes', f'join={joined["join_id"]}',
                          'address=code.alarm.audible.piezo', 'name=buzzer', 'purpose=Make the end audible.',
                          'ef=Buzzes.', 'verb=buzzes').stdout)
    assert (inside['name'], inside['purpose'], inside['verb'], inside['extra'], inside['notices']) == (
        'buzzer', 'Make the end audible.', 'buzzes', None, [])
    store = Store('proj')
    stored = {join.join_id: join for join in store.joins('code.timer.kitchen', raw=True).results}[joined['join_id']]
    assert (stored.name, stored.verb, stored.extra) == ('done alarm', 'rings', None)
    (subtype,) = store.subtypes(joined['join_id'], raw=True).results
    assert (subtype.name, subtype.purpose, subtype.verb, subtype.extra) == (
        'buzzer', 'Make the end audible.', 'buzzes', None)


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
    added = j(run, 'work', 'op=add', 'node=code.alarm.audible', 'condition=missing', 'note=in the spec, not built',
              'task=build the piezo driver', 'held=true', cwd=mapped)
    assert (added['kind'], added['address'], added['condition'], added['held'], added['reviewed'], added['done']) == (
        'element', 'code.alarm.audible', 'missing', True, False, None)
    on_join = j(run, 'work', 'op=add', f'node=join:{join.join_id}', 'condition=broken', 'task=fix the tone', cwd=mapped)
    assert (on_join['kind'], on_join['receiver_address'], on_join['provider_address']) == (
        'join', 'code.timer.kitchen', 'code.alarm.audible')
    listed = j(run, 'work', cwd=mapped)['results']
    assert [(row['condition'], row['held']) for row in listed] == [('missing', True), ('broken', False)]
    assert [row['work_id'] for row in j(run, 'work', 'open=true', 'condition=missing', cwd=mapped)['results']] == [added['work_id']]
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
    refused = run('map', 'work', 'op=add', 'condition=missing', '--json', cwd=mapped, ok=False)
    assert refused.returncode == 2 and 'node' in refused.stderr
    unknown = run('map', 'work', 'op=add', 'node=element:code.alarm.audible', 'condition=exclude', 'later=yes', '--json',
                  cwd=mapped, ok=False)
    assert unknown.returncode == 2 and "does not take 'later=yes'" in unknown.stderr  # the chassis grammar, BASE-043
    assert j(run, 'work', 'op=done', f'id={on_join["work_id"]}', 'task=ignored here', cwd=mapped)['notices'][0]['where'] == 'task'
    assert run('help', 'map', 'work', cwd=mapped).stdout.count('missing') >= 1


@pytest.mark.req('BASE-038')
@pytest.mark.req('MAP-003')
@pytest.mark.req('MAP-030')
def test_knowledge_edit_moves_a_join_by_its_receiver_and_absorbs_it_by_its_parent(run, mapped):
    k(run, mapped, 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true', *PROVENANCE)
    k(run, mapped, 'op=add-element', 'layer=notes', 'address=code.alarm.visual')
    first = json.loads(k(run, mapped, 'op=add-join', 'layer=notes', 'receiver=code.timer.kitchen',
                         'provider=code.alarm.visual', 'purpose=See the end.', 'ef=Flashes.').stdout)
    moved = json.loads(k(run, mapped, 'op=edit', 'layer=notes', f'id={first["join_id"]}',
                         'receiver=stakeholder.cook.home').stdout)
    assert moved['notices'] == []
    store = Store('proj')
    assert first['join_id'] in [join.join_id for join in store.joins('stakeholder.cook.home', raw=True).results]
    assert first['join_id'] not in [join.join_id for join in store.joins('code.timer.kitchen', raw=True).results]
    parent = store.joins('stakeholder.cook.home').results[0].join_id
    k(run, mapped, 'op=edit', 'layer=notes', f'id={first["join_id"]}', f'parent={parent}')
    held = store.subtypes(parent, raw=True).results
    assert [(sub.join_id, sub.address, sub.purpose, sub.extra) for sub in held] == [
        (first['join_id'], 'code.alarm.visual', 'See the end.', None)]  # absorbed, it keeps its purpose as its own
    assert first['join_id'] not in [join.join_id for join in store.joins('stakeholder.cook.home', raw=True).results]


@pytest.mark.req('BASE-038')
@pytest.mark.req('BASE-044')
@pytest.mark.req('STORE-012')
def test_a_ref_that_is_not_a_key_and_a_value_both_text_is_kept_in_the_extra_and_never_refused(run, mapped):
    k(run, mapped, 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true', *PROVENANCE)
    joined = json.loads(k(run, mapped, 'op=add-join', 'layer=notes', 'receiver=code.timer.kitchen',
                          'provider=code.alarm.audible', 'purpose=p', 'ef=f',
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


@pytest.fixture
def described(run, tmp_path):
    """A registered project whose intake map has a non_goal, relations, a subtype join and paths."""
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    store = Store('proj')
    with store.atomic():
        layer = store.layer('intake-1', 'intake', 'The functional map.', kind='intake', mutable=False,
                            hideable=False, provenance={'module': 'intake'}, ready=True)
        store.add_element(layer.name, 'stakeholder.cook.home', name_length=2, role='CQU')
        store.add_element(layer.name, 'code.timer.kitchen', name_length=2, role='DE')
        store.add_element(layer.name, 'code.alarm.audible', name_length=2, role='SE')
        store.add_element(layer.name, 'code.display.digit', name_length=2, role='SE',
                          refs=[('path', 'src/display.py'), ('spec', 'DISP-001')])
        store.add_join(layer.name, 'stakeholder.cook.home', 'code.timer.kitchen', name='kitchen timer',
                       purpose='Know when a dish is done.', ef='learns from the timer when a dish is done')
        store.add_join(layer.name, 'code.timer.kitchen', 'code.alarm.audible', purpose='Get attention.',
                       ef='rings for the timer')
        join = store.add_join(layer.name, 'code.timer.kitchen', 'code.display.digit', purpose='See the time left.',
                              ef='shows the time left to the timer', verb='shows',
                              non_goal='It keeps no time itself.')
        store.add_subtype(layer.name, join.join_id, 'code.driver.segment', name_length=2, role='SE',
                          ef='lights each digit')
    return folder


@pytest.mark.req('MAP-052')
def test_the_markdown_document_orients_and_leaves_the_detail_in_the_files(run, described):
    """The document holds what a reader finds its way by: each join's ef where it showed the relation, Rich
    2026-10-02, and the purpose and non_goal."""
    text = run('map', 'markdown', cwd=described).stdout
    for address in ('stakeholder.cook.home', 'code.timer.kitchen', 'code.alarm.audible', 'code.display.digit'):
        assert f'`{address}`' in text
    for name in ('home cook', 'kitchen timer', 'audible alarm', 'digit display'):
        assert name in text
    assert 'DE' in text and 'CQU' in text
    assert 'Paths: src/display.py' in text and 'DISP-001' not in text
    assert 'kitchen timer receives from digit display' in text
    # Rich, 2026-10-02: no subject rule; ef is shown as written, where the relation was.
    lines = text.splitlines()
    assert 'shows the time left to the timer' in lines and 'learns from the timer when a dish is done' in lines
    assert 'digit display shows' not in text and 'home cook learns' not in text
    assert 'Why: See the time left.' in text and 'Why: Know when a dish is done.' in text
    assert 'Not: It keeps no time itself.' in text
    assert '- segment driver: lights each digit' in lines and 'rings for the timer' in lines
    assert text.index('## kitchen timer') < text.index('rings for the timer') < \
        text.index('shows the time left to the timer') < text.index('## audible alarm')  # each ef under its own join
    assert text.index('home cook') < text.index('## kitchen timer') < text.index('## audible alarm')


@pytest.mark.req('MAP-052')
def test_the_markdown_document_of_an_address_shows_all_around_it(run, described):
    """At one address: the element, what it relies on and what relies on it, and nothing of the rest of the map."""
    text = run('map', 'markdown', 'address=code.timer.kitchen', cwd=described).stdout
    assert '## kitchen timer' in text
    assert 'kitchen timer receives from audible alarm' in text and 'kitchen timer receives from digit display' in text
    assert 'home cook receives from kitchen timer' in text and 'Why: Know when a dish is done.' in text
    assert '## audible alarm' not in text and '## digit display' not in text


@pytest.mark.req('MAP-052')
def test_the_markdown_document_is_written_to_a_file_when_one_is_named(run, described, tmp_path):
    target = tmp_path / 'out' / 'map.md'
    target.parent.mkdir()
    said = run('map', 'markdown', f'file={target}', cwd=described).stdout
    assert str(target) in said and '## kitchen timer' not in said
    assert target.read_text(encoding='utf-8') == run('map', 'markdown', cwd=described).stdout


@pytest.mark.req('MAP-052')
@pytest.mark.req('CLI-037')
def test_the_markdown_document_is_a_command_and_never_a_tool(run, described, home, monkeypatch):
    """Writing a document is a person's or an orchestrator's act; it adds nothing to what an agent meets."""
    monkeypatch.setenv('METAFORM_HOME', str(home))
    from metaform.modules.mcp import server
    names = set(server.tools(described))
    assert 'map_where' in names and 'map_markdown' not in names


@pytest.mark.req('MAP-046')
@pytest.mark.req('MAP-049')
def test_an_agent_that_takes_a_task_marks_the_part_as_being_worked_on_until_it_is_done(run, mapped):
    """Taking a task says work has started on the part: a part to be built is in progress, a broken one is being
    fixed, and the record no longer waits to be taken. Done, the part is as any other."""
    store = Store('proj')
    build = store.add_work(Node('element', 'code.alarm.audible'), 'missing', task='build it', held=True)
    fix = store.add_work(Node('element', 'code.timer.kitchen'), 'broken', task='fix it', held=True)
    taken = json.loads(run('map', 'work', 'op=take', f'id={build.work_id}', '--json', cwd=mapped).stdout)
    assert (taken['condition'], taken['held'], bool(taken['taken'])) == ('missing', False, True)  # it keeps its kind, VIEW-035
    assert json.loads(run('map', 'work', 'op=take', f'id={fix.work_id}', '--json', cwd=mapped).stdout)[
        'condition'] == 'broken'  # a broken one taken keeps its kind; the viewer reads it as fixing
    assert j(run, 'element', 'code.alarm.audible', cwd=mapped)['open_work'] == ['in-progress']
    listed = json.loads(run('map', 'work', 'condition=in-progress', '--json', cwd=mapped).stdout)['results']
    assert [record['work_id'] for record in listed] == [build.work_id]
    again = run('map', 'work', 'op=take', f'id={build.work_id}', '--json', cwd=mapped, ok=False)
    assert again.returncode != 0 and 'already' in again.stderr + again.stdout
    run('map', 'work', 'op=done', f'id={build.work_id}', 'resolution=built', cwd=mapped)
    assert j(run, 'element', 'code.alarm.audible', cwd=mapped).get('open_work', []) == []



@pytest.mark.req('MAP-050')
def test_a_question_and_a_note_are_asked_told_answered_and_read_at_the_node(run, mapped):
    """A question comes in plain words with the answers the agent suggests, the one it recommends first, so the user
    answers with one click. A note asks for nothing and waits to be read. Neither is the condition of a part, so
    neither is a work record."""
    asked = j(run, 'ask', 'code.alarm.audible', 'Is the quiet tone still wanted?',
              'suggestions=["Yes, keep it", "No, make it louder"]', 'by=builder', cwd=mapped)
    assert (asked['kind'], asked['address'], asked['text'], asked['suggestions'], asked['by'], asked['closed']) == (
        'question', 'code.alarm.audible', 'Is the quiet tone still wanted?', ['Yes, keep it', 'No, make it louder'],
        'builder', None)
    assert said(asked) == []
    bare = j(run, 'ask', 'code.alarm.audible', 'Which one?', cwd=mapped)  # told to suggest, never refused
    assert bare['suggestions'] == [] and [where for where, _ in said(bare)] == ['suggestions']
    told = j(run, 'tell', 'code.alarm.audible', 'The driver is written.', cwd=mapped)
    assert (told['kind'], told['text'], told['closed']) == ('message', 'The driver is written.', None)
    waiting = j(run, 'messages', 'open=true', cwd=mapped)['results']
    assert [one['message_id'] for one in waiting] == [asked['message_id'], bare['message_id'], told['message_id']]
    assert [one['kind'] for one in j(run, 'messages', 'kind=question', cwd=mapped)['results']] == ['question', 'question']
    assert j(run, 'element', 'code.alarm.audible', cwd=mapped)['open_work'] == ['question', 'question', 'message']
    assert j(run, 'work', 'node=element:code.alarm.audible', cwd=mapped)['results'] == []  # no work record was made
    replied = j(run, 'reply', asked['message_id'], 'answer=No, make it louder', cwd=mapped)
    assert (replied['answer'], bool(replied['closed'])) == ('No, make it louder', True)
    again = j(run, 'reply', asked['message_id'], 'answer=Yes, keep it', cwd=mapped)  # the first answer is kept
    assert again['answer'] == 'No, make it louder' and [where for where, _ in said(again)] == ['message_id']
    at_node = j(run, 'messages', 'node=element:code.alarm.audible', 'open=false', cwd=mapped)['results']
    assert [(one['text'], one['answer']) for one in at_node] == [('Is the quiet tone still wanted?', 'No, make it louder')]
    where = j(run, 'where', 'code.alarm.audible', cwd=mapped)
    assert [(one['kind'], one['text']) for one in where['messages']] == [('question', 'Which one?'),
                                                                        ('message', 'The driver is written.')]
    old = run('map', 'work', 'op=add', 'node=code.alarm.audible', 'condition=question', 'note=Old form.', '--json',
              cwd=mapped)  # a question is no condition of a part; the agent is told how to ask
    assert 'metaform map ask' in ' '.join(message for _, message in said(json.loads(old.stdout)))


@pytest.mark.req('STORE-025')
@pytest.mark.req('LAYER-005')
def test_where_shows_the_properties_that_apply_at_the_address_and_those_visible_there(run, mapped):
    """An agent is told to read a part with where before it changes it. A property linked toward the trunk applies at
    the part, so where shows it; an agent that read only where would otherwise never learn of it."""
    k(run, mapped, 'op=create', 'layer=media', 'variable=Which language is each part written in?', 'mutable=true',
      'hideable=true', *PROVENANCE)
    k(run, mapped, 'op=add-property', 'layer=media', 'element=type:code', 'value="C"')
    k(run, mapped, 'op=add-property', 'layer=media', 'element=code.timer.kitchen', 'value="assembly"')
    k(run, mapped, 'op=finish', 'layer=media')
    kitchen = j(run, 'where', 'code.timer.kitchen', cwd=mapped)['properties']
    assert [(one['value'], one['address']) for one in kitchen['applying']] == [('C', 'code'), ('assembly', 'code.timer.kitchen')]
    assert 'visible' not in kitchen                                  # nothing is linked toward the leaves from it
    alarm = j(run, 'where', 'code.alarm.audible', cwd=mapped)['properties']
    assert [(one['value'], one['address']) for one in alarm['applying']] == [('C', 'code')]
    trunk = j(run, 'where', 'code', cwd=mapped)['properties']
    assert [(one['value'], one['address']) for one in trunk['visible']] == [('assembly', 'code.timer.kitchen')]
    in_context = j(run, 'context', 'code.timer.kitchen', cwd=mapped)['applying']  # the same, as context reads them
    assert [(one['value'], one['address'], one['layer']) for one in in_context] \
        == [(one['value'], one['address'], one['layer']) for one in kitchen['applying']]
    assert 'properties' not in j(run, 'where', 'stakeholder.cook.home', cwd=mapped)  # none apply and none are visible


@pytest.mark.req('MAP-053')
@pytest.mark.req('MAP-049')
def test_an_agent_says_how_many_steps_it_plans_and_reports_each_as_it_finishes_it(run, mapped):
    """The map shows how far a part is by the share of its steps that are done, and a share needs the whole. The count
    is a plan, and the agent changes it when the plan changes."""
    store = Store('proj')
    task = store.add_work(Node('element', 'code.alarm.audible'), 'missing', task='build it')
    assert (task.steps, task.steps_done, task.said) == (None, 0, ())
    taken = j(run, 'work', 'op=take', f'id={task.work_id}', 'steps=3', cwd=mapped)
    assert (taken['condition'], taken['steps'], taken['steps_done'], taken['said']) == ('missing', 3, 0, [])
    first = j(run, 'work', 'op=step', f'id={task.work_id}', 'said=The driver is written.', cwd=mapped)
    assert (first['steps'], first['steps_done']) == (3, 1) and said(first) == []
    assert [(one['number'], one['said']) for one in first['said']] == [(1, 'The driver is written.')]
    assert first['said'][0]['at']
    changed = j(run, 'work', 'op=plan', f'id={task.work_id}', 'steps=5', cwd=mapped)  # the plan changed
    assert (changed['steps'], changed['steps_done']) == (5, 1)
    for text in ('The tone is set.', 'The test passes.'):
        j(run, 'work', 'op=step', f'id={task.work_id}', f'said={text}', cwd=mapped)
    lowered = j(run, 'work', 'op=plan', f'id={task.work_id}', 'steps=3', cwd=mapped)
    assert (lowered['steps'], lowered['steps_done']) == (3, 3)
    beyond = j(run, 'work', 'op=step', f'id={task.work_id}', 'said=One more than planned.', cwd=mapped)
    assert (beyond['steps'], beyond['steps_done']) == (4, 4)          # nothing is refused: the count follows
    assert [where for where, _ in said(beyond)] == ['steps']
    read = [row for row in j(run, 'work', 'node=element:code.alarm.audible', cwd=mapped)['results']
            if row['work_id'] == task.work_id][0]
    assert [one['said'] for one in read['said']] == ['The driver is written.', 'The tone is set.', 'The test passes.',
                                                     'One more than planned.']
    plain = store.add_work(Node('element', 'code.timer.kitchen'), 'missing', task='no count')
    took = j(run, 'work', 'op=take', f'id={plain.work_id}', cwd=mapped)
    assert (took['steps'], took['steps_done'], took['said']) == (None, 0, [])  # a task with no count has no steps
    untaken = store.add_work(Node('element', 'code.timer.kitchen'), 'missing', task='not taken')
    early = j(run, 'work', 'op=step', f'id={untaken.work_id}', 'said=Done before it was taken.', cwd=mapped)
    assert early['steps_done'] == 1 and [where for where, _ in said(early)] == ['condition']


@pytest.mark.req('MAP-048')
def test_a_ticket_is_moved_across_the_board_and_links_other_nodes_for_reference(run, mapped):
    """Rich, 2026-10-01: assign and track work via Metaform like a kanban; the ticket is on the functionality it is
    assigned to, and links other nodes for reference. It keeps its kind in every column."""
    made = json.loads(run('map', 'work', 'op=add', 'node=code.alarm.audible', 'condition=flawed', 'task=quieter tone',
                          'links=["element:code.timer.kitchen"]', 'held=true', '--json', cwd=mapped).stdout)
    assert ([link['address'] for link in made['links']], made['held']) == (['code.timer.kitchen'], True)
    doing = json.loads(run('map', 'work', 'op=move', f'id={made["work_id"]}', 'column=doing', 'by=codex', '--json',
                           cwd=mapped).stdout)
    assert (doing['condition'], doing['taken_by'], doing['held'], bool(doing['taken'])) == ('flawed', 'codex', False, True)
    done = json.loads(run('map', 'work', 'op=move', f'id={made["work_id"]}', 'column=done', '--json', cwd=mapped).stdout)
    assert done['done'] and done['condition'] == 'flawed'


@pytest.mark.req('LAYER-025')
@pytest.mark.req('MAP-020')
def test_refining_a_join_changes_its_verb_and_ifd(run, mapped):
    """An intake of Metaform found that knowledge edit and refine dropped verb, Rich 2026-10-01: if you see issues you
    can fix them. It changes with the rest of a join's fields, and so does its IFD."""
    from metaform.data import Store
    join = Store('proj').joins('code.timer.kitchen').results[0]
    refined = json.loads(k(run, mapped, 'op=refine', f'id={join.join_id}', 'verb=sounds',
                           'ifd=sends', 'reason=The alarm is what the timer encounters.').stdout)
    assert not [notice for notice in refined.get('notices', []) if notice['where'] in ('verb', 'ifd')]
    now = next(held for held in Store('proj').joins('code.timer.kitchen').results if held.join_id == join.join_id)
    assert (now.verb, now.ifd) == ('sounds', 'sends')


@pytest.mark.req('MAP-020')
def test_the_map_knowledge_tool_takes_no_perspective():
    """Rich, 2026-10-02: "drop perspective drop the duality , EF infers fine". Neither add-join, add-subtype, edit
    nor refine takes one."""
    from metaform.modules.map import FIELDS, MODULE, READS
    knowledge = next(verb for verb in MODULE.verbs if verb.name == 'knowledge')
    assert 'perspective' not in {noun.name for noun in knowledge.nouns}
    assert 'perspective' not in FIELDS and all('perspective' not in reads for reads in READS.values())


@pytest.mark.req('MAP-048')
@pytest.mark.req('STORE-042')
def test_map_work_with_an_id_and_no_op_reads_that_one_ticket_with_what_the_map_holds_there(run, described):
    """Reported 2026-10-02 by the first agent to work a ticket: `map work id=<id>` failed with a TypeError, and an
    agent had to parse the whole work list to read its ticket. The read hands it the ticket with its node's where
    read, its refs and its open questions, and the same for each node it links."""
    run('map', 'ask', 'code.display.digit', 'Four digits or six?', 'suggestions=["Four", "Six"]', cwd=described)
    made = j(run, 'work', 'op=add', 'node=code.display.digit', 'condition=flawed', 'task=dim the digits at night',
             'links=["element:code.timer.kitchen"]', cwd=described)
    read = run('map', 'work', f'id={made["work_id"]}', '--json', cwd=described)
    assert read.returncode == 0 and 'TypeError' not in read.stderr
    ticket = json.loads(read.stdout)
    assert (ticket['work_id'], ticket['task'], ticket['condition']) == (made['work_id'], 'dim the digits at night',
                                                                       'flawed')
    at = ticket['at']
    assert at['element']['address'] == 'code.display.digit'
    assert at['element']['refs'] == [{'key': 'path', 'value': 'src/display.py'}, {'key': 'spec', 'value': 'DISP-001'}]
    assert [(one['kind'], one['text']) for one in at['messages']] == [('question', 'Four digits or six?')]
    assert [join['receiver'] for join in at['provides']] == ['code.timer.kitchen']
    assert [linked['element']['address'] for linked in ticket['linked']] == ['code.timer.kitchen']
    text = run('map', 'work', f'id={made["work_id"]}', cwd=described).stdout
    assert 'Four digits or six?' in text and 'src/display.py' in text


@pytest.mark.req('MAP-048')
def test_map_work_reading_a_ticket_names_the_list_nouns_it_does_not_read_and_an_unknown_id(run, mapped):
    made = j(run, 'work', 'op=add', 'node=code.alarm.audible', 'condition=missing', 'task=wire it', cwd=mapped)
    read = j(run, 'work', f'id={made["work_id"]}', 'condition=broken', cwd=mapped)
    assert read['work_id'] == made['work_id'] and [notice['where'] for notice in read['notices']] == ['condition']
    unknown = run('map', 'work', 'id=nothing', '--json', cwd=mapped, ok=False)
    assert unknown.returncode == 2 and 'TypeError' not in unknown.stderr
    assert unknown.stderr.splitlines()[-1] == 'Next: metaform map work open=true'


@pytest.mark.req('BASE-044')
@pytest.mark.req('STORE-042')
def test_a_work_list_given_a_noun_it_does_not_read_lists_with_a_notice(run, mapped):
    """The TypeError behind `map work id=<id>`: a list read given a noun it does not read failed to add its notice
    to the page."""
    run('map', 'work', 'op=add', 'node=code.alarm.audible', 'condition=missing', 'task=wire it', cwd=mapped)
    listed = j(run, 'work', 'said=nothing', cwd=mapped)
    assert len(listed['results']) == 1 and [notice['where'] for notice in listed['notices']] == ['said']


@pytest.mark.req('MAP-048')
@pytest.mark.req('STORE-025')
def test_map_where_shows_each_ticket_at_the_address_with_its_work_id(run, mapped):
    made = j(run, 'work', 'op=add', 'node=code.alarm.audible', 'condition=missing', 'task=wire it', cwd=mapped)
    assert [one['work_id'] for one in j(run, 'where', 'code.alarm.audible', cwd=mapped)['work']] == [made['work_id']]
    assert made['work_id'] in run('map', 'where', 'code.alarm.audible', cwd=mapped).stdout
