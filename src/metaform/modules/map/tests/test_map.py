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
        store.add_element(layer.name, 'code.timer.kitchen', name_length=2, role='DE', name='kitchen timer')
        store.add_element(layer.name, 'code.alarm.audible', name_length=2, role='SE')
        store.add_join(layer.name, 'stakeholder.cook.home', 'code.timer.kitchen',
                       purpose='Know when a dish is done.',
                       ef='Counts down and rings.')
        store.add_join(layer.name, 'code.timer.kitchen', 'code.alarm.audible', purpose='Get attention.',
                       ef='Plays a tone.')
    return folder


def j(run, *args, cwd):
    return json.loads(run('map', *args, '--json', cwd=cwd).stdout)


# The parts of the question form map ask refuses a question without, MAP-050; suggestions= is given per call.
FORM = ('specs=09-viewer.md', 'not_option=A tone is wanted or not.',
        'rich_said=None; the decision and its reason are described in the question.', 'by=builder')
YES_NO = 'suggestions=["Yes", "No"]'


@pytest.mark.req('MAP-054')
def test_promote_command_keeps_the_purpose_and_creates_an_ordinary_element(run, mapped):
    store = Store('proj')
    original = store.joins('code.timer.kitchen').results[0]
    ends = ('receiver=code.timer.kitchen', 'provider=code.alarm.audible')
    run('memory', 'create_entities', json.dumps([{
        'name': 'delivery insight', 'entityType': 'finding',
        'observations': ['The cook needs an audible signal.']}]), *ends, cwd=mapped)
    before = json.loads(run('memory', 'open_nodes', '["delivery insight"]', *ends,
                            '--json', cwd=mapped).stdout)
    made = j(run, 'promote', 'receiver=code.timer.kitchen', 'provider=code.alarm.audible',
             'address=code.delivery', 'name=countdown delivery', cwd=mapped)
    assert made['id'] == original.id and made['element'] == 'code.delivery'
    assert store.element('code.delivery').name == 'countdown delivery'
    assert store.join_ends(original.id) == ('code.timer.kitchen', 'code.alarm.audible')
    after = json.loads(run('memory', 'open_nodes', '["delivery insight"]', *ends,
                           '--json', cwd=mapped).stdout)
    assert before == after and before['entities'][0]['observations'] == ['The cook needs an audible signal.']
    repeated = j(run, 'promote', 'receiver=code.timer.kitchen', 'provider=code.alarm.audible',
                 'address=code.delivery', cwd=mapped)
    assert repeated['id'] == original.id
    assert len(store.history(original.id).results) == 2
    missing = j(run, 'promote', 'receiver=code.timer.kitchen', 'provider=code.missing',
                'address=code.unused', cwd=mapped)
    assert missing['notices'] and store.element('code.unused', raw=True) is None
    help_text = run('help', 'map', 'promote', cwd=mapped).stdout
    assert all(field in help_text for field in ('receiver', 'provider', 'address', 'name', 'reason'))


@pytest.mark.req('LAYER-026')
@pytest.mark.req('STORE-041')
def test_collapse_command_preserves_current_map_and_switches_back_to_its_history(run, mapped):
    def without_layer(value):
        # Collapse gives records a fresh intake layer while preserving their identity and meaning.
        if isinstance(value, dict):
            return {key: without_layer(inner) for key, inner in value.items() if key not in ('layer', 'layer_id')}
        if isinstance(value, list):
            return [without_layer(inner) for inner in value]
        return value

    store = Store('proj')
    old = store.active_base()
    join = store.joins('stakeholder.cook.home').results[0]
    store.refine(join.id, {'purpose': 'Finish cooking on time.'}, reason='schedule the meal')
    current = store.roots().to_dict()
    before = store.history(join.id).to_dict()

    made = j(run, 'collapse', 'fresh', cwd=mapped)
    assert made['name'] == 'fresh' and made['active']
    assert made['id'] != old.id
    assert any('stay with' in notice['message'] for notice in made['notices'])
    assert without_layer(store.roots().to_dict()) == without_layer(current)
    assert [(layer.name, layer.kind) for layer in store.layers().results] == [('base', 'base')]
    assert len(store.history(join.id).results) == 1
    assert {form['name']: form['active'] for form in j(run, 'bases', cwd=mapped)['results']} == {
        old.name: False, 'fresh': True}

    j(run, 'activate', old.name, cwd=mapped)
    assert store.active_base().id == old.id
    assert store.history(join.id).to_dict() == before


def k(run, cwd, *args, ok=True):
    return run('map', 'knowledge', *args, '--json', cwd=cwd, ok=ok)


def refined_by(run, cwd, *args, ok=True):
    return run('map', 'refine', *args, '--json', cwd=cwd, ok=ok)


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
                          'elements=["code.watchdog"]', 'purpose=Recover from a hang.', 'ef=Restarts the loop.').stdout)
    k(run, mapped, 'op=edit', 'layer=practices-cpp', f'id={added["id"]}', 'value="Prefer steady_clock always."')
    k(run, mapped, 'op=remove', 'layer=practices-cpp', f'id={doomed["id"]}')

    def seen(cwd):
        view = j(run, 'node', 'element:code.timer.kitchen', cwd=cwd)
        return [item['value'] for group in view['layers'] if group['layer'] == 'practices-cpp' for item in group['items']]
    assert seen(other) == []
    assert [item['value'] for item in j(run, 'layer', 'practices-cpp', cwd=mapped)['results']] == \
        ['Prefer steady_clock always.']
    k(run, mapped, 'op=finish', 'layer=practices-cpp')
    assert seen(other) == ['Prefer steady_clock always.']
    receiver_joins = j(run, 'joins', 'code.timer.kitchen', cwd=other)['results']
    assert {(join['elements'][0]['address'], join['layer']) for join in receiver_joins} == {
        ('code.alarm.audible', 'intake-1'), ('code.watchdog', 'practices-cpp')}
    k(run, mapped, 'op=edit', 'layer=practices-cpp', f'id={added["id"]}', 'value="Use steady_clock."')
    assert seen(other) == ['Use steady_clock.']
    run('set', '--layers', 'intake-1', cwd=other)
    assert seen(other) == []
    assert joined['id'] not in [join['id'] for join in j(run, 'joins', 'code.timer.kitchen', cwd=other)['results']]
    raw = json.loads(run('map', 'joins', 'code.timer.kitchen', '--raw', '--json', cwd=other).stdout)['results']
    assert joined['id'] in [join['id'] for join in raw]


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
    k(run, mapped, 'op=add-join', 'layer=challenge.blind', 'receiver=code.timer.kitchen', 'elements=["code.watchdog"]',
      'purpose=Recover.', 'ef=Restarts.')
    challenge = json.loads(k(run, mapped, 'op=add-item', 'layer=challenge.blind', 'node=element:code.watchdog',
                             'value="Nothing recovers a hung loop."').stdout)
    k(run, mapped, 'op=finish', 'layer=challenge.blind')
    unlinked = run('map', 'answer', challenge['id'], 'C', cwd=mapped)
    assert re.search(r'^Notice: link: ', unlinked.stdout, re.MULTILINE)
    refused = run('map', 'approve', challenge['id'], cwd=mapped, ok=False)
    assert refused.returncode == 2
    run('map', 'answer', challenge['id'], 'B', cwd=mapped)
    run('map', 'approve', challenge['id'], cwd=mapped)
    assert j(run, 'element', 'code.watchdog', cwd=mapped)['state'] == 'plan'
    listed = run('help', 'map', cwd=mapped).stdout
    assert 'approve' in listed


def _intake_snapshot():
    """The intake layer's record, provenance, elements and joins, read raw."""
    store = Store('proj')
    layer = next(layer for layer in store.layers().results if layer.name == 'intake-1')
    addresses = ('stakeholder.cook.home', 'code.timer.kitchen', 'code.alarm.audible')
    return (layer.to_dict(), store.provenance('intake-1'), [store.element(a, raw=True) for a in addresses],
            [store.joins(a, raw=True).results for a in addresses])


def _critic_run(run, mapped, *args):
    """Run `map critic` once; its served text and the one layer it added."""
    before = {layer.name for layer in Store('proj').layers().results}
    served = run('map', 'critic', *args, cwd=mapped).stdout
    added = {layer.name for layer in Store('proj').layers().results} - before
    assert len(added) == 1, added
    return served, added.pop()


@pytest.mark.req('LAYER-014')
@pytest.mark.req('LAYER-015')
@pytest.mark.req('MCP-031')
def test_each_critic_run_adds_one_layer_blinded_by_its_type_and_is_given_the_whole_metaform(run, mapped):
    from importlib import resources

    from metaform import prompt_files
    folder = resources.files('metaform.modules.map')
    intake = _intake_snapshot()
    metaform = run('map', 'markdown', cwd=mapped).stdout.strip()
    blind, blind_layer = _critic_run(run, mapped)
    sighted, sighted_layer = _critic_run(run, mapped, '--critic')
    _again, again_layer = _critic_run(run, mapped)
    assert len({blind_layer, sighted_layer, again_layer}) == 3
    assert blind_layer.startswith('blind_spot_fast_') and sighted_layer.startswith('blind_spot_critic_')
    store = Store('proj')
    assert (store.provenance(blind_layer).blinded, store.provenance(blind_layer).role) == (True, 'critic')
    assert (store.provenance(sighted_layer).blinded, store.provenance(sighted_layer).role) == (False, 'critic')
    assert store.provenance(again_layer).blinded is True
    assert {(store.provenance(name).module, store.provenance(name).prompt)
            for name in (blind_layer, sighted_layer, again_layer)} == {('map', 'blind_spot_challenge')}
    # Rich's prompt as written, then the mode's run: its layer and the whole metaform the intake agent built.
    challenge = prompt_files.required(folder, 'blind_spot_challenge')
    assert blind.strip() == challenge + '\n\n' + prompt_files.required(folder, 'critic_fast', layer=blind_layer,
                                                                        metaform=metaform)
    assert sighted.strip() == challenge + '\n\n' + prompt_files.required(folder, 'critic_critic',
                                                                          layer=sighted_layer, metaform=metaform)
    assert metaform in blind and metaform in sighted
    assert _intake_snapshot() == intake


@pytest.mark.req('LAYER-015')
@pytest.mark.req('STORE-040')
def test_the_answer_prompt_gives_each_challenge_of_a_layer_with_its_state(run, mapped):
    from importlib import resources

    from metaform import prompt_files
    _, layer = _critic_run(run, mapped)
    hang = json.loads(k(run, mapped, 'op=add-item', f'layer={layer}', 'node=element:code.timer.kitchen',
                        'value="Nothing recovers a hung loop."').stdout)
    volume = json.loads(k(run, mapped, 'op=add-item', f'layer={layer}', 'node=element:code.alarm.audible',
                          'value="The alarm has no volume control."').stdout)
    linked = json.loads(k(run, mapped, 'op=add-item', f'layer={layer}', 'node=element:code.alarm.audible',
                          'value="Nobody hears the alarm."').stdout)
    waiting = json.loads(k(run, mapped, 'op=add-item', f'layer={layer}', 'node=element:code.timer.kitchen',
                           'value="The timer forgets its count on power loss."').stdout)
    k(run, mapped, 'op=finish', f'layer={layer}')
    run('map', 'answer', volume['id'], 'A', cwd=mapped)
    run('map', 'answer', hang['id'], 'B', cwd=mapped)
    run('map', 'answer', linked['id'], 'C', 'link=element:code.alarm.audible', cwd=mapped)
    run('map', 'approve', hang['id'], cwd=mapped)
    served = run('map', 'challenges', layer, cwd=mapped).stdout
    opening, closing = prompt_files.required(resources.files('metaform.modules.map'), 'answer_challenges',
                                             layer=layer, challenges='\0').split('\0')
    # The whole fixed text, the three answers included, comes from the XML, on both sides of the challenges.
    assert opening and served.startswith(opening) and served.rstrip().endswith(closing)
    lines = {item: next(line for line in served.splitlines() if item in line)
             for item in (hang['id'], volume['id'], linked['id'], waiting['id'])}
    assert 'Nothing recovers a hung loop.' in lines[hang['id']] and 'plan' in lines[hang['id']].split()
    assert 'The alarm has no volume control.' in lines[volume['id']]
    assert 'A' in lines[volume['id']].split()
    assert 'C' in lines[linked['id']].split()
    assert 'open' in lines[waiting['id']].split()
    assert 'code.timer.kitchen' in lines[hang['id']]


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
    assert [(join['receiver'], join['purpose'], join['ef'], [held['address'] for held in join['elements']])
            for join in kitchen['provides']] == [
        ('stakeholder.cook.home', 'Know when a dish is done.', 'Counts down and rings.', ['code.timer.kitchen'])]
    assert [([held['address'] for held in join['elements']], join['ef'], join['layer'])
            for join in kitchen['receives']] == [(['code.alarm.audible'], 'Plays a tone.', 'intake-1')]
    alarm = j(run, 'where', 'code.alarm.audible', cwd=mapped)
    assert alarm['work'] == [{'id': Store('proj').work().results[0].id, 'condition': 'missing',
                              'note': 'no speaker yet', 'task': 'wire the piezo'}]
    assert 'element_id' not in alarm['element'] and 'join_id' not in alarm['provides'][0]
    full = j(run, 'where', 'code.alarm.audible', 'full=true', cwd=mapped)
    store = Store('proj')
    assert full['element']['id'] == store.element('code.alarm.audible').id
    assert full['provides'][0]['id'] == store.joins('code.timer.kitchen').results[0].id
    assert full['work'][0]['id']
    assert 'map_where' in run('help', 'map', cwd=mapped).stdout or 'where' in run('help', 'map', cwd=mapped).stdout


@pytest.mark.req('BASE-038')
def test_each_read_verb_returns_what_its_operation_returns(run, mapped):
    store = Store('proj')
    kitchen = store.element('code.timer.kitchen')
    assert j(run, 'element', 'code.timer.kitchen', cwd=mapped)['id'] == kitchen.id
    assert j(run, 'identity', 'code.timer.kitchen', cwd=mapped) == json.loads(json.dumps(
        store.identity('code.timer.kitchen').to_dict()))
    assert j(run, 'where', 'code.alarm.audible', cwd=mapped)['element']['address'] == 'code.alarm.audible'
    assert [form['name'] for form in j(run, 'bases', cwd=mapped)['results']] == ['main']
    join = store.joins('code.timer.kitchen').results[0]
    assert j(run, 'history', join.id, cwd=mapped)['results'][0]['op'] == 'add'
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
@pytest.mark.req('STORE-009')
@pytest.mark.req('BASE-043')
def test_a_knowledge_layer_names_an_element_in_its_own_name_field(run, mapped):
    """Rich, 2026-10-01: a name goes anywhere there is a namespace and name length, the element's own field beside
    name_length; Rich, 2026-10-04: a join holds no name, its shape is its type, purpose, ef and ifd."""
    k(run, mapped, 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true', *PROVENANCE)
    element = json.loads(k(run, mapped, 'op=add-element', 'layer=notes', 'address=code.display.lcd',
                           'name=time display', 'name_length=2').stdout)
    assert (element['short_name'], element['name_length'], element['name'], element.get('extra')) == (
        'lcd display', 2, 'time display', None)
    assert element['notices'] == []
    assert Store('proj').element('code.display.lcd', raw=True).name == 'time display'


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
    kitchen = store.element('code.timer.kitchen').id
    layers = [layer.name for layer in store.layers(limit=0).results]
    moved = run('map', 'refine', f'receiver={join.receiver_address}', f'provider={join.elements[0].address}', 'purpose=First fix.',
                'to_receiver=stakeholder.cook.home', 'reason=r', cwd=mapped)
    assert 'Notice:' not in moved.stdout
    kept = run('map', 'refine', 'address=code.timer.kitchen', 'to_address=code.timer.egg', 'reason=r', cwd=mapped)
    assert re.search(r'^Notice: to_address: ', kept.stdout, re.MULTILINE)
    after = {found.id: found for found in Store('proj').joins('stakeholder.cook.home').results}[join.id]
    assert (after.purpose, after.receiver_address, after.layer) == ('First fix.', 'stakeholder.cook.home', 'intake-1')
    assert Store('proj').element('code.timer.kitchen').id == kitchen
    assert Store('proj').element('code.timer.egg') is None
    assert [layer.name for layer in Store('proj').layers(limit=0).results] == layers
    history = j(run, 'history', join.id, cwd=mapped)['results']
    assert [(version['layer'], version['op'], version['fields']['purpose']) for version in history] == [
        ('intake-1', 'add', join.purpose), ('intake-1', 'change', 'First fix.')]


@pytest.mark.req('LAYER-025')
def test_knowledge_creates_no_correction_layer_and_offers_no_correct_or_peel(run, mapped):
    refused = run('map', 'knowledge', 'op=create', 'layer=fix-a', 'kind=correction', 'variable=Fixes.',
                  'mutable=false', 'hideable=false', *PROVENANCE, cwd=mapped, ok=False)
    assert refused.returncode != 0 and 'kind=layer' in refused.stdout + refused.stderr
    for op in ('correct', 'peel', 'refine'):
        gone = run('map', 'knowledge', f'op={op}', 'layer=intake', 'id=x', 'reason=r', cwd=mapped, ok=False)
        assert gone.returncode != 0 and 'not a knowledge operation' in gone.stdout + gone.stderr
    page = run('help', 'map', 'knowledge', cwd=mapped).stdout
    # Rich, 2026-10-03: refining the metaform under knowledge read as touching a knowledge layer, which it does not.
    assert 'op=refine' not in page and 'correction' not in page and 'peel' not in page
    assert 'refine' not in run('help', 'map', 'knowledge', cwd=mapped).stdout.split('Switches')[1].split('\n')[1]
    assert 'refine' in run('help', 'map', 'refine', cwd=mapped).stdout
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
    at_join = json.loads(k(run, mapped, 'op=add-property', 'layer=notes', f'element=join:{join.id}',
                           'value="c"').stdout)
    assert at_join['orphaned'] and at_join['extra'] == {'target': f'join:{join.id}'} and at_join['notices']
    store = Store('proj')
    assert [store.where(address, raw=True) for address in ('type:code', f'join:{join.id}')] == [None, None]


@pytest.mark.req('CLI-033')
@pytest.mark.req('LAYER-019')
@pytest.mark.req('BASE-036')
def test_layers_and_metaforms_read_as_one_aligned_row_each(run, mapped):
    k(run, mapped, 'op=create', 'layer=practices-cpp', 'variable=C++ practice here.', 'mutable=true', 'hideable=true',
      'tags=["practices"]', *PROVENANCE)
    k(run, mapped, 'op=finish', 'layer=practices-cpp')
    k(run, mapped, 'op=create', 'layer=draft', 'variable=Drafts.', 'mutable=true', 'hideable=true', *PROVENANCE)
    join = Store('proj').joins('code.timer.kitchen').results[0]
    refined_by(run, mapped, f'receiver={join.receiver_address}', f'provider={join.elements[0].address}', 'ef=Plays a loud tone.', 'reason=r')

    def rows(*args):
        lines = run('map', *args, cwd=mapped).stdout.splitlines()
        starts = {len(line) - len(line[len(line.split()[0]):].lstrip()) for line in lines}
        assert len(starts) == 1, lines
        return {line.split()[0]: line.split() for line in lines}
    layers = rows('layers')
    assert layers['intake-1'] == ['intake-1', 'base', 'intake', 'ready', 'on']
    assert layers['practices-cpp'] == ['practices-cpp', 'layer', 'test', 'practices', 'ready', 'on']
    assert layers['draft'] == ['draft', 'layer', 'test', 'building', 'off']
    assert sorted(layers) == ['draft', 'intake-1', 'practices-cpp']  # refining makes no layer, LAYER-025
    metaforms = rows('bases')
    assert metaforms['main'][-1] == 'active'
    assert {layer['name'] for layer in j(run, 'layers', cwd=mapped)['results']} == set(layers)


@pytest.mark.req('BASE-044')
@pytest.mark.req('BASE-043')
def test_a_noun_the_operation_does_not_read_is_kept_in_extra_or_named_as_ignored(run, mapped):
    k(run, mapped, 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true', *PROVENANCE)
    made = json.loads(k(run, mapped, 'op=add-property', 'layer=notes', 'element=code.timer.kitchen', 'value="v"',
                        'key=path').stdout)
    assert made['extra'] == {'key': 'path'} and [notice['where'] for notice in made['notices']] == ['key']
    finished = json.loads(k(run, mapped, 'op=finish', 'layer=notes', 'variable=x').stdout)
    assert [notice['where'] for notice in finished['notices']] == ['variable']
    assert 'ignored' in finished['notices'][0]['message'] and finished['ready']


@pytest.mark.req('BASE-043')
@pytest.mark.req('LAYER-025')
def test_refine_refuses_a_word_it_does_not_take_and_writes_nothing(run, mapped):
    """refine has no extra, so the command line has nowhere to keep a word it does not know: it refuses it, as the
    chassis grammar does for every verb with no extra, BASE-043, and the metaform keeps every version as it was."""
    store = Store('proj')
    join = store.joins('code.timer.kitchen', raw=True).results[0]
    before = [version.to_dict() for version in store.history(join.id, limit=0).results]
    refused = run('map', 'refine', 'receiver=code.timer.kitchen', 'provider=code.alarm.audible', 'ef=Plays loudly.',
                  'reason=louder', 'variable=x', cwd=mapped, ok=False)
    assert refused.returncode == 2 and "does not take 'variable=x'" in refused.stderr
    assert [version.to_dict() for version in store.history(join.id, limit=0).results] == before
    assert store.joins('code.timer.kitchen', raw=True).results[0].ef == 'Plays a tone.'


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
                          'elements=["code.alarm.audible"]').stdout)
    empty = ('purpose', 'ef')
    assert said(joined) == [(field, f'{field} is missing; stored empty.') for field in empty]
    stored = {join.id: join for join in Store('proj').joins('code.timer.kitchen', raw=True).results}
    assert stored[joined['id']].layer == 'bare'
    assert [getattr(stored[joined['id']], field) for field in empty] == [None, None]

    item = json.loads(k(run, mapped, 'op=add-item', 'layer=bare', 'node=element:code.timer.kitchen').stdout)
    held = json.loads(k(run, mapped, 'op=add-property', 'layer=bare', 'element=code.timer.kitchen').stdout)
    for written in (item, held):
        assert written['value'] is None and said(written) == [('value', 'value is missing; stored empty.')]

    ref = json.loads(k(run, mapped, 'op=add-ref', 'layer=bare', f'owner={item["id"]}').stdout)
    assert (ref['key'], ref['value']) == ('', '')
    assert said(ref) == [('key', 'key is missing; stored empty.'), ('value', 'value is missing; stored empty.')]
    numbered = json.loads(k(run, mapped, 'op=add-ref', 'layer=bare', f'owner={item["id"]}', 'key=line',
                            'value=12').stdout)
    assert (numbered['key'], numbered['value']) == ('line', '12') and [where for where, _ in said(numbered)] == ['value']
    stored = {found.id: found for found in Store('proj').layer_items('bare').results if hasattr(found, 'target')}
    assert [(found.key, found.value) for found in stored[item['id']].refs] == [('', ''), ('line', '12')]

    edited = json.loads(k(run, mapped, 'op=edit', f'id={item["id"]}', 'value="Set later."').stdout)
    removed = json.loads(k(run, mapped, 'op=remove', f'id={held["id"]}').stdout)
    assert [where for where, _ in said(edited)] == ['layer'] and [where for where, _ in said(removed)] == ['layer']
    assert [found.value for found in Store('proj').layer_items('bare').results] == ['Set later.']

    intake_join = Store('proj').joins('code.timer.kitchen').results[0]
    corrected = json.loads(refined_by(run, mapped, f'receiver={intake_join.receiver_address}',
                                      f'provider={intake_join.elements[0].address}',
                             'purpose=Get the cook back.').stdout)
    assert said(corrected) == [('reason', 'reason is missing; stored empty.')]


@pytest.mark.req('BASE-038')
@pytest.mark.req('BASE-044')
@pytest.mark.req('STORE-042')
def test_a_map_write_missing_what_its_record_cannot_be_stored_without_stops_once_and_writes_nothing(run, mapped):
    k(run, mapped, 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true', *PROVENANCE)
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
        ('receiver', ['knowledge', 'op=add-join', 'elements=["code.alarm.audible"]', 'purpose=p']),
        ('elements', ['knowledge', 'op=add-join', 'layer=notes', 'receiver=code.timer.kitchen']),
        ('element', ['knowledge', 'op=add-property', 'layer=notes', 'value="v"']),
        ('element', ['knowledge', 'op=add-plan', 'layer=notes']),
        ('node', ['knowledge', 'op=add-item', 'layer=notes', 'value="v"']),
        ('owner', ['knowledge', 'op=add-ref', 'layer=notes', 'key=path', 'value="alarm.c"']),
        ('id', ['knowledge', 'op=edit', 'layer=notes', 'value="v"']),
        ('id', ['knowledge', 'op=remove', 'layer=notes']),
        ('address', ['refine', 'reason=r']),
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
@pytest.mark.req('BASE-044')
@pytest.mark.req('STORE-042')
def test_a_work_record_sent_without_a_condition_is_stored_empty_with_a_notice(run, mapped):
    added = j(run, 'work', 'op=add', 'node=element:code.alarm.audible', 'task=decide what it is', cwd=mapped)
    assert (added['condition'], added['task'], added['done']) == ('', 'decide what it is', None)
    assert said(added) == [('condition', 'condition is missing; stored empty.')]
    listed = j(run, 'work', 'node=element:code.alarm.audible', cwd=mapped)['results']
    assert [(row['id'], row['condition']) for row in listed] == [(added['id'], '')]


@pytest.mark.req('MAP-049')
@pytest.mark.req('MAP-053')
def test_the_work_list_holds_open_rows_without_their_logs_and_the_ticket_read_holds_everything(run, mapped):
    """A bare `map work` was 758,000 characters on a project of 220 tickets, mostly the done ones' logs."""
    store = Store('proj')
    alarm = Node('element', 'code.alarm.audible')
    waiting = store.add_work(alarm, 'missing', task='build the driver').id
    finished = store.add_work(alarm, 'broken', task='fix the tone').id
    j(run, 'work', 'op=take', f'id={finished}', 'steps=1', cwd=mapped)
    j(run, 'work', 'op=step', f'id={finished}', 'said=The tone is fixed.', cwd=mapped)
    store.finish_work(finished, 'tone set in alarm.c')
    listed = j(run, 'work', cwd=mapped)['results']
    assert [row['id'] for row in listed] == [waiting]
    done = j(run, 'work', 'open=false', cwd=mapped)['results']
    assert [row['id'] for row in done] == [finished]
    assert all(not {'said', 'resolution', 'task'} & set(row) for row in [*listed, *done])
    read = j(run, 'work', f'id={finished}', cwd=mapped)
    assert ([one['said'] for one in read['said']], read['resolution'], read['task']) == (
        ['The tone is fixed.'], 'tone set in alarm.c', 'fix the tone')


@pytest.mark.req('BASE-038')
@pytest.mark.req('MAP-046')
@pytest.mark.req('STORE-042')
def test_work_records_are_added_edited_listed_and_done_through_one_verb_and_never_change_the_map(run, mapped):
    store = Store('proj')
    join = store.joins('code.timer.kitchen').results[0]
    before = json.loads(run('query', 'graph', 'limit=0', '--json', cwd=mapped).stdout)
    added = j(run, 'work', 'op=add', 'node=code.alarm.audible', 'condition=missing', 'note=in the spec, not built',
              'task=build the piezo driver', 'held=true', cwd=mapped)
    assert (added['node_kind'], added['address'], added['condition'], added['held'], added['reviewed'], added['done']) == (
        'element', 'code.alarm.audible', 'missing', True, False, None)
    on_join = j(run, 'work', 'op=add', f'node=join:{join.id}', 'condition=broken', 'task=fix the tone', cwd=mapped)
    assert (on_join['node_kind'], on_join['receiver_address'], on_join['provider_address']) == (
        'join', 'code.timer.kitchen', 'code.alarm.audible')
    listed = j(run, 'work', cwd=mapped)['results']
    assert [(row['condition'], row['held']) for row in listed] == [('missing', True), ('broken', False)]
    assert [row['id'] for row in j(run, 'work', 'open=true', 'condition=missing', cwd=mapped)['results']] == [added['id']]
    # The alarm provides the join, so its ticket is listed at the alarm too, ticket dd2a9caf.
    assert [row['id'] for row in j(run, 'work', 'node=element:code.alarm.audible', cwd=mapped)['results']] == [
        added['id'], on_join['id']]
    edited = j(run, 'work', 'op=edit', f'id={added["id"]}', 'reviewed=true', 'held=false', cwd=mapped)
    assert (edited['reviewed'], edited['held'], edited['task']) == (True, False, 'build the piezo driver')
    done = j(run, 'work', 'op=done', f'id={added["id"]}', 'resolution=driver in alarm.c', cwd=mapped)
    assert done['done'] is not None and done['resolution'] == 'driver in alarm.c'
    assert [row['id'] for row in j(run, 'work', 'open=false', cwd=mapped)['results']] == [added['id']]
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
    assert j(run, 'work', 'op=done', f'id={on_join["id"]}', 'task=ignored here', cwd=mapped)['notices'][0]['where'] == 'task'
    assert run('help', 'map', 'work', cwd=mapped).stdout.count('missing') >= 1


@pytest.mark.req('BASE-038')
@pytest.mark.req('MAP-003')
def test_knowledge_edit_moves_a_join_by_its_receiver(run, mapped):
    k(run, mapped, 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true', *PROVENANCE)
    k(run, mapped, 'op=add-element', 'layer=notes', 'address=code.alarm.visual')
    first = json.loads(k(run, mapped, 'op=add-join', 'layer=notes', 'receiver=code.timer.kitchen',
                         'elements=["code.alarm.visual"]', 'purpose=See the end.', 'ef=Flashes.').stdout)
    moved = json.loads(k(run, mapped, 'op=edit', 'layer=notes', f'id={first["id"]}',
                         'receiver=stakeholder.cook.home').stdout)
    assert moved['notices'] == []
    store = Store('proj')
    assert first['id'] in [join.id for join in store.joins('stakeholder.cook.home', raw=True).results]
    assert first['id'] not in [join.id for join in store.joins('code.timer.kitchen', raw=True).results]


@pytest.fixture
def described(run, tmp_path):
    """A registered project whose intake map has a join holding two elements, and paths in the sources layer."""
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
        store.add_element(layer.name, 'code.display.digit', name_length=2, role='SE')
        store.add_element(layer.name, 'code.driver.segment', name_length=2, role='SE')
        store.add_join(layer.name, 'stakeholder.cook.home', 'code.timer.kitchen',
                       purpose='Know when a dish is done.', ef='learns from the timer when a dish is done')
        store.add_join(layer.name, 'code.timer.kitchen', 'code.alarm.audible', purpose='Get attention.',
                       ef='rings for the timer')
        store.add_join(layer.name, 'code.timer.kitchen', ['code.display.digit', 'code.driver.segment'],
                       purpose='See the time left.', ef='shows the time left to the timer')
        sources = store.layer('sources', 'intake', 'refs', mutable=True, hideable=True, ready=True)
        store.add_item(sources.name, Node('element', 'code.display.digit'), 'code.display.digit',
                       refs=[('path', 'src/display.py'), ('spec', 'DISP-001')])
    return folder


@pytest.mark.req('MAP-052')
def test_the_markdown_document_orients_and_leaves_the_detail_in_the_files(run, described):
    """The document holds what a reader finds its way by: each join's ef where it showed the relation, Rich
    2026-10-02, its purpose and the elements it holds, and the paths the sources layer holds."""
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
    assert 'kitchen timer receives from digit display, segment driver' in text and 'rings for the timer' in lines
    for ef in ('rings for the timer', 'shows the time left to the timer'):  # each ef under its own join
        assert text.index('## kitchen timer') < text.index(ef) < text.index('## audible alarm')
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
@pytest.mark.req('MAP-059')
@pytest.mark.req('CLI-037')
def test_the_markdown_document_is_a_command_and_never_a_tool(run, described, home, monkeypatch):
    """Writing a document is a person's or an orchestrator's act; it adds nothing to what an agent meets."""
    monkeypatch.setenv('METAFORM_HOME', str(home))
    from metaform.modules.mcp import server
    names = set(server.tools(described))
    assert 'map_where' in names and 'map_markdown' not in names and 'map_xml' not in names


@pytest.fixture(params=['timer-first', 'alarm-first'])
def recorded(run, tmp_path, monkeypatch, request):
    """An intake in Rich's shape: an AUE, a CQU receiving from the DE, the DE receiving from an alarm and from a
    display with its driver, the cook receiving from the alarm too; refs in the sources layer; a finding on the alarm
    and one on the display's join."""
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    store = Store('proj')
    with store.atomic():
        layer = store.layer('intake-1', 'intake', 'The functional map.', kind='intake', mutable=False,
                            hideable=False, provenance={'module': 'intake'}, ready=True)
        store.add_element(layer.name, 'code.appliance.kitchen', name_length=2, role='AUE', name='Kitchen timer app')
        store.add_element(layer.name, 'stakeholder.cook.home', name_length=2, role='CQU')
        store.add_element(layer.name, 'code.timer.kitchen', name_length=2, role='DE', name='kitchen timer')
        store.add_element(layer.name, 'code.alarm.audible', name_length=2, role='SE')
        store.add_element(layer.name, 'code.display.digit', name_length=2, role='SE')
        store.add_element(layer.name, 'code.driver.segment', name_length=1, role='NE')
        # UUID order need not match creation order. Exercise both sibling orders without relying on random IDs.
        positions = [1, 2, 3, 4] if request.param == 'timer-first' else [4, 3, 2, 1]
        join_ids = iter(f'000000000000400080000000000000{position:02x}' for position in positions)
        with monkeypatch.context() as controlled:
            controlled.setattr('metaform.data.writes.new_id', lambda: next(join_ids))
            store.add_join(layer.name, 'stakeholder.cook.home', 'code.timer.kitchen',
                           purpose='Know when a dish is done.', ef='learns from the timer when a dish is done',
                           ifd='receives')
            store.add_join(layer.name, 'stakeholder.cook.home', 'code.alarm.audible', purpose='Hear it from the hall.',
                           ef='rings loud enough for the hall', ifd='receives')
            store.add_join(layer.name, 'code.timer.kitchen', 'code.alarm.audible', purpose='Get attention.',
                           ef='rings for the timer', ifd='sends')
            shown = store.add_join(layer.name, 'code.timer.kitchen', ['code.display.digit', 'code.driver.segment'],
                                   purpose='See the time left.', ef='shows the time left to the timer', ifd='both')
        sources = store.layer('sources', 'intake', 'refs', mutable=True, hideable=True, ready=True)
        store.add_item(sources.name, Node('element', 'code.display.digit'), 'code.display.digit',
                       refs=[('path', 'src/display.py'), ('spec', 'DISP-001')])
    store.add_work(Node('element', 'code.alarm.audible'), 'broken', note='rings too quietly')
    store.add_work(Node('join', shown.id), 'missing', note='no blank between digits')
    return folder


def xml_of(run, *args, cwd):
    import xml.etree.ElementTree as ET
    return ET.fromstring(run('map', 'xml', *args, cwd=cwd).stdout)


@pytest.mark.req('MAP-059')
def test_the_xml_document_holds_every_field_the_intake_recorded_in_the_finish_shape(run, recorded):
    """Review requires every recorded field and finding in the Finish shape, with joins under their receivers and
    providers under their joins. MAP-059 does not require sibling joins to follow creation order."""
    store = Store('proj')
    document = xml_of(run, cwd=recorded)
    metaform = store.active_base()
    assert document.tag == 'metaform' and document.get('id') == metaform.id
    assert document.get('name') == metaform.name
    aue = document.find('element')
    assert aue.get('namespace_address') == 'code.appliance.kitchen' and aue.get('role') == 'AUE'
    cook = document.findall('element')[1]
    assert cook.get('namespace_address') == 'stakeholder.cook.home' and cook.get('role') == 'CQU'
    cook_joins = {join.find('element').get('namespace_address'): join for join in cook.findall('join')}
    assert set(cook_joins) == {'code.timer.kitchen', 'code.alarm.audible'}
    timer_join = cook_joins['code.timer.kitchen']
    assert (timer_join.get('type'), timer_join.get('ifd')) == ('purpose', 'receives')
    assert timer_join.findtext('purpose') == 'Know when a dish is done.'
    assert timer_join.findtext('ef') == 'learns from the timer when a dish is done'
    timer = timer_join.find('element')
    assert timer.get('namespace_address') == 'code.timer.kitchen'
    for node in document.iter('element'):  # every element carries the four fields the store holds for it
        stored = store.element(node.get('namespace_address'))
        assert (node.get('name_length'), node.get('name'), node.get('role')) == (
            str(stored.name_length), stored.name or '', stored.role), node.get('namespace_address')
    joins = {join.findtext('purpose'): join for join in document.iter('join')}
    assert len(joins) == 4
    assert (joins['Get attention.'].get('ifd'), joins['See the time left.'].get('ifd')) == ('sends', 'both')
    held = [element.get('namespace_address') for element in joins['See the time left.'].findall('element')]
    assert held == ['code.display.digit', 'code.driver.segment']
    display = joins['See the time left.'].find('element')
    assert [(ref.get('key'), ref.get('value')) for ref in display.findall('ref')] == [
        ('path', 'src/display.py'), ('spec', 'DISP-001')]
    assert [(work.get('condition'), work.text) for work in joins['See the time left.'].findall('work')] == [
        ('missing', 'no blank between digits')]
    alarms = [element for element in document.iter('element') if element.get('namespace_address') == 'code.alarm.audible']
    assert len(alarms) == 2  # held by two joins; the first holds what it has, the other refers to it
    full, bare = alarms
    assert [(work.get('condition'), work.text) for work in full.findall('work')] == [('broken', 'rings too quietly')]
    assert len(bare) == 0


@pytest.mark.req('MAP-059')
def test_the_xml_document_of_an_address_is_that_element_and_all_it_receives(run, recorded):
    document = xml_of(run, 'address=code.timer.kitchen', cwd=recorded)
    assert [element.get('namespace_address') for element in document.findall('element')] == ['code.timer.kitchen']
    assert {join.findtext('purpose') for join in document.iter('join')} == {'Get attention.', 'See the time left.'}
    assert 'stakeholder.cook.home' not in {element.get('namespace_address') for element in document.iter('element')}


@pytest.mark.req('MAP-059')
def test_the_xml_document_is_written_to_a_file_when_one_is_named(run, recorded, tmp_path):
    target = tmp_path / 'out' / 'map.xml'
    target.parent.mkdir()
    said = run('map', 'xml', f'file={target}', cwd=recorded).stdout
    assert str(target) in said and 'code.timer.kitchen' not in said
    assert target.read_text(encoding='utf-8') == run('map', 'xml', cwd=recorded).stdout


@pytest.mark.req('MAP-046')
@pytest.mark.req('MAP-049')
def test_an_agent_that_takes_a_task_marks_the_part_as_being_worked_on_until_it_is_done(run, mapped):
    """Taking a task says work has started on the part: a part to be built is in progress, a broken one is being
    fixed, and the record no longer waits to be taken. Done, the part is as any other."""
    store = Store('proj')
    build = store.add_work(Node('element', 'code.alarm.audible'), 'missing', task='build it', held=True)
    fix = store.add_work(Node('element', 'code.timer.kitchen'), 'broken', task='fix it', held=True)
    taken = json.loads(run('map', 'work', 'op=take', f'id={build.id}', '--json', cwd=mapped).stdout)
    assert (taken['condition'], taken['held'], bool(taken['taken'])) == ('missing', False, True)  # it keeps its kind, VIEW-035
    assert json.loads(run('map', 'work', 'op=take', f'id={fix.id}', '--json', cwd=mapped).stdout)[
        'condition'] == 'broken'  # a broken one taken keeps its kind; the viewer reads it as fixing
    assert j(run, 'element', 'code.alarm.audible', cwd=mapped)['open_work'] == ['in-progress']
    listed = json.loads(run('map', 'work', 'condition=in-progress', '--json', cwd=mapped).stdout)['results']
    assert [record['id'] for record in listed] == [build.id]
    again = run('map', 'work', 'op=take', f'id={build.id}', '--json', cwd=mapped, ok=False)
    assert again.returncode != 0 and 'already' in again.stderr + again.stdout
    assert f'metaform map work op=plan id={build.id}' in again.stderr + again.stdout  # the way to resume
    run('map', 'work', 'op=done', f'id={build.id}', 'resolution=built', cwd=mapped)
    assert j(run, 'element', 'code.alarm.audible', cwd=mapped).get('open_work', []) == []


@pytest.mark.req('MAP-049')
@pytest.mark.req('MAP-053')
def test_an_agent_takes_a_record_with_no_condition_reports_steps_and_says_it_waits_on_the_person(run, mapped):
    """A drift finding the intake writes with no condition is taken, planned and stepped through the CLI as a record
    with a condition is, and a step says the agent waits on the person."""
    drift = Store('proj').add_work(Node('element', 'code.timer.kitchen'), None, task='the timer drifts')
    taken = json.loads(run('map', 'work', 'op=take', f'id={drift.id}', 'by=claude', '--json', cwd=mapped).stdout)
    assert (taken['condition'], taken['taken_by']) == ('', 'claude')
    assert json.loads(run('map', 'work', 'op=plan', f'id={drift.id}', 'steps=2', '--json',
                          cwd=mapped).stdout)['steps'] == 2
    waiting = json.loads(run('map', 'work', 'op=step', f'id={drift.id}',
                             'said=Asked the person which is right; waiting on the answer.', '--json',
                             cwd=mapped).stdout)
    assert not waiting.get('notices')
    read = json.loads(run('map', 'work', f'id={drift.id}', '--json', cwd=mapped).stdout)
    assert (read['taken_by'], read['steps'], read['steps_done'], read['said'][-1]['said']) == (
        'claude', 2, 1, 'Asked the person which is right; waiting on the answer.')
    again = run('map', 'work', 'op=take', f'id={drift.id}', '--json', cwd=mapped, ok=False)
    assert again.returncode != 0 and 'already taken' in again.stderr + again.stdout



@pytest.mark.req('MAP-050')
def test_a_question_and_a_note_are_asked_told_answered_and_read_at_the_node(run, mapped):
    """A question comes in plain words with the answers the agent suggests, the one it recommends first, so the user
    answers with one click. A note asks for nothing and waits to be read. Neither is the condition of a part, so
    neither is a work record."""
    asked = j(run, 'ask', 'code.alarm.audible', 'Is the quiet tone still wanted?',
              'suggestions=["Yes, keep it", "No, make it louder"]', *FORM, cwd=mapped)
    form = ('Is the quiet tone still wanted?\n\n#1 Specifications reviewed:\n09-viewer.md\n\n'
            '#2 Why this is not a configuration option:\nA tone is wanted or not.\n\n'
            '#3 Unexplained "Rich said":\nNone; the decision and its reason are described in the question.')
    assert (asked['kind'], asked['address'], asked['text'], asked['suggestions'], asked['by'], asked['closed']) == (
        'question', 'code.alarm.audible', form, ['Yes, keep it', 'No, make it louder'], 'builder', None)
    assert said(asked) == [] and asked['said'].startswith('Your question is recorded at the node.')
    assert [one['text'] for one in j(run, 'messages', 'limit=0', cwd=mapped)['results']] == [form]
    told = j(run, 'tell', 'code.alarm.audible', 'The driver is written.', cwd=mapped)
    assert (told['kind'], told['text'], told['closed']) == ('message', 'The driver is written.', None)
    waiting = j(run, 'messages', 'open=true', cwd=mapped)['results']
    assert [one['id'] for one in waiting] == [asked['id'], told['id']]
    assert [one['kind'] for one in j(run, 'messages', 'kind=question', cwd=mapped)['results']] == ['question']
    assert j(run, 'element', 'code.alarm.audible', cwd=mapped)['open_work'] == ['question', 'message']
    assert j(run, 'work', 'node=element:code.alarm.audible', cwd=mapped)['results'] == []  # no work record was made
    replied = j(run, 'reply', asked['id'], 'answer=No, make it louder', cwd=mapped)
    assert (replied['answer'], bool(replied['closed'])) == ('No, make it louder', True)
    again = j(run, 'reply', asked['id'], 'answer=Yes, keep it', cwd=mapped)  # the first answer is kept
    assert again['answer'] == 'No, make it louder' and [where for where, _ in said(again)] == ['id']
    at_node = j(run, 'messages', 'node=element:code.alarm.audible', 'open=false', cwd=mapped)['results']
    assert [(one['text'], one['answer']) for one in at_node] == [(form, 'No, make it louder')]
    where = j(run, 'where', 'code.alarm.audible', cwd=mapped)
    assert [(one['kind'], one['text']) for one in where['messages']] == [('message', 'The driver is written.')]
    old = run('map', 'work', 'op=add', 'node=code.alarm.audible', 'condition=question', 'note=Old form.', '--json',
              cwd=mapped)  # a question is no condition of a part; the agent is told how to ask
    assert 'metaform map ask' in ' '.join(message for _, message in said(json.loads(old.stdout)))

    # a bare question is recorded with a notice for each part of the form not filled, never refused, MAP-050
    bare = j(run, 'ask', 'code.alarm.audible', 'Which one?', cwd=mapped)
    assert bare['text'] == 'Which one?' and {where for where, _ in said(bare)} >= {'specs', 'not_option', 'suggestions'}
    assert 'Which one?' in [one['text'] for one in j(run, 'messages', 'open=true', cwd=mapped)['results']]

@pytest.mark.req('MAP-050')
def test_where_gives_each_open_message_its_id_so_it_is_answered_from_that_read(run, mapped):
    """perspective-agent, 2026-10-02: where listed the open questions with no message_id, and replying took a second
    call to find it. The where read gives each one its id, and the id it gives answers the question."""
    asked = j(run, 'ask', 'code.alarm.audible', 'Is the quiet tone still wanted?', YES_NO, *FORM, cwd=mapped)
    told = j(run, 'tell', 'code.alarm.audible', 'The driver is written.', cwd=mapped)
    where = j(run, 'where', 'code.alarm.audible', cwd=mapped)
    assert [one.get('id') for one in where['messages']] == [asked['id'], told['id']]
    replied = j(run, 'reply', where['messages'][0]['id'], 'answer=Yes', cwd=mapped)
    assert (replied['text'], replied['answer']) == (asked['text'], 'Yes')


@pytest.mark.req('MAP-050')
def test_a_question_answered_by_mistake_is_reopened_and_waits_again_with_its_suggestions(run, mapped):
    """Rich, 2026-10-03: "How do I reopen a question when I hit the wrong button". The answer is cleared and the
    question waits again, so the right answer can be given."""
    asked = j(run, 'ask', 'code.alarm.audible', 'Is the quiet tone still wanted?',
              'suggestions=["Yes, keep it", "No, make it louder"]', *FORM, cwd=mapped)
    j(run, 'reply', asked['id'], 'answer=No, make it louder', cwd=mapped)
    reopened = j(run, 'reopen', asked['id'], cwd=mapped)
    assert (reopened['closed'], reopened['answer'], reopened['suggestions']) == (
        None, None, ['Yes, keep it', 'No, make it louder'])
    assert said(reopened) == []
    waiting = j(run, 'messages', 'open=true', cwd=mapped)['results']
    assert [(one['id'], one['suggestions']) for one in waiting] == [
        (asked['id'], ['Yes, keep it', 'No, make it louder'])]
    assert j(run, 'element', 'code.alarm.audible', cwd=mapped)['open_work'] == ['question']
    replied = j(run, 'reply', asked['id'], 'answer=Yes, keep it', cwd=mapped)  # the second answer is kept
    assert (replied['answer'], bool(replied['closed'])) == ('Yes, keep it', True)
    j(run, 'reopen', asked['id'], cwd=mapped)
    still = j(run, 'reopen', asked['id'], cwd=mapped)  # already open: left as it is, and said
    assert still['closed'] is None and [where for where, _ in said(still)] == ['id']
    assert (still['text'], still['suggestions'], still['created'], still['by']) == (
        asked['text'], asked['suggestions'], asked['created'], asked['by'])
    told = j(run, 'tell', 'code.alarm.audible', 'The driver is written.', cwd=mapped)
    j(run, 'reply', told['id'], cwd=mapped)
    refused = run('map', 'reopen', told['id'], cwd=mapped, ok=False)  # only a question is reopened
    assert refused.returncode != 0 and 'Only a question is reopened' in refused.stderr + refused.stdout
    assert j(run, 'messages', 'kind=message', 'open=false', cwd=mapped)['results'][0]['id'] == told['id']


@pytest.mark.req('MAP-050')
def test_the_agent_that_asks_is_told_how_to_record_an_answer_it_got_another_way(run, mapped):
    """Work ca18a108, 2026-10-02: Rich answered a question through the coordinator, and the agent that asked found no
    way to close it, so the node glowed for a settled question. map reply closes it; ask's help must say so."""
    page = run('help', 'map', 'ask', cwd=mapped).stdout
    assert 'metaform map reply <id> answer=' in page.split('Details')[1]


@pytest.mark.req('MAP-050')
@pytest.mark.req('CLI-037')
def test_reopening_a_question_is_a_command_and_never_a_tool(run, described, home, monkeypatch):
    """Reopening is the person's act, from the page and the command line; it adds nothing to what an agent meets."""
    monkeypatch.setenv('METAFORM_HOME', str(home))
    from metaform.modules.mcp import server
    names = set(server.tools(described))
    assert 'map_reply' in names and 'map_reopen' not in names
    served = server.entries(described)['map'][1]  # the commands the map tool lists over MCP
    assert 'reply' in served and 'reopen' not in served


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
    taken = j(run, 'work', 'op=take', f'id={task.id}', 'steps=3', cwd=mapped)
    assert (taken['condition'], taken['steps'], taken['steps_done'], taken['said']) == ('missing', 3, 0, [])
    first = j(run, 'work', 'op=step', f'id={task.id}', 'said=The driver is written.', cwd=mapped)
    assert (first['steps'], first['steps_done']) == (3, 1) and said(first) == []
    assert [(one['number'], one['said']) for one in first['said']] == [(1, 'The driver is written.')]
    assert first['said'][0]['at']
    changed = j(run, 'work', 'op=plan', f'id={task.id}', 'steps=5', cwd=mapped)  # the plan changed
    assert (changed['steps'], changed['steps_done']) == (5, 1)
    for text in ('The tone is set.', 'The test passes.'):
        j(run, 'work', 'op=step', f'id={task.id}', f'said={text}', cwd=mapped)
    lowered = j(run, 'work', 'op=plan', f'id={task.id}', 'steps=3', cwd=mapped)
    assert (lowered['steps'], lowered['steps_done']) == (3, 3)
    beyond = j(run, 'work', 'op=step', f'id={task.id}', 'said=One more than planned.', cwd=mapped)
    assert (beyond['steps'], beyond['steps_done']) == (4, 4)          # nothing is refused: the count follows
    assert [where for where, _ in said(beyond)] == ['steps']
    read = j(run, 'work', f'id={task.id}', cwd=mapped)  # the list leaves the log out, MAP-053
    assert [one['said'] for one in read['said']] == ['The driver is written.', 'The tone is set.', 'The test passes.',
                                                     'One more than planned.']
    plain = store.add_work(Node('element', 'code.timer.kitchen'), 'missing', task='no count')
    took = j(run, 'work', 'op=take', f'id={plain.id}', cwd=mapped)
    assert (took['steps'], took['steps_done'], took['said']) == (None, 0, [])  # a task with no count has no steps
    untaken = store.add_work(Node('element', 'code.timer.kitchen'), 'missing', task='not taken')
    early = j(run, 'work', 'op=step', f'id={untaken.id}', 'said=Done before it was taken.', cwd=mapped)
    assert early['steps_done'] == 1 and [where for where, _ in said(early)] == ['condition']


@pytest.mark.req('MAP-048')
def test_a_ticket_is_moved_across_the_board_and_links_other_nodes_for_reference(run, mapped):
    """Rich, 2026-10-01: assign and track work via Metaform like a kanban; the ticket is on the functionality it is
    assigned to, and links other nodes for reference. It keeps its kind in every column."""
    made = json.loads(run('map', 'work', 'op=add', 'node=code.alarm.audible', 'condition=flawed', 'task=quieter tone',
                          'links=["element:code.timer.kitchen"]', 'held=true', '--json', cwd=mapped).stdout)
    assert ([link['address'] for link in made['links']], made['held']) == (['code.timer.kitchen'], True)
    doing = json.loads(run('map', 'work', 'op=move', f'id={made["id"]}', 'column=doing', 'by=codex', '--json',
                           cwd=mapped).stdout)
    assert (doing['condition'], doing['taken_by'], doing['held'], bool(doing['taken'])) == ('flawed', 'codex', False, True)
    done = json.loads(run('map', 'work', 'op=move', f'id={made["id"]}', 'column=done', '--json', cwd=mapped).stdout)
    assert done['done'] and done['condition'] == 'flawed'


def glyph_of(record):
    """The glyph the map module keeps on a work record, shown under its own id, BASE-035; None when it keeps none."""
    return (record.get('map') or {}).get('glyph')


@pytest.mark.req('VIEW-040')
def test_distributing_over_n_agents_gives_the_first_n_glyphs_in_turn_to_the_tickets_not_taken_or_done(run, mapped):
    """Rich, 2026-10-03: "using glyphs on tasks can signify 1 single agent meaning perform these tasks one at a timne
    since they all have the same glyph, add a button to distribute work over N agents hitting it will evenly assign
    work using N glyphs". To do first, then Backlog, each in its board order; a ticket taken or done keeps its glyph,
    and an exclude record is not a ticket."""
    from metaform.modules.map import AGENT_GLYPHS
    store = Store('proj')
    kitchen, alarm = Node('element', 'code.timer.kitchen'), Node('element', 'code.alarm.audible')
    todo = [store.add_work(kitchen, 'missing', task=f'todo {number}') for number in range(5)]
    backlog = [store.add_work(alarm, 'enhancement', task=f'backlog {number}', held=True) for number in range(2)]
    store.move_work(todo[4].id, 'todo', position=0)                   # the board's order, not the rows'
    store.move_work(backlog[1].id, 'backlog', position=0)
    taken = store.add_work(alarm, 'broken', task='being worked')
    j(run, 'work', 'op=edit', f'id={taken.id}', 'glyph=owl', cwd=mapped)
    store.take_work(taken.id, by='claude')
    done = store.add_work(alarm, 'flawed', task='finished')
    j(run, 'work', 'op=edit', f'id={done.id}', 'glyph=snail', cwd=mapped)  # outside the first three dealt
    store.finish_work(done.id, 'fixed')
    outside = store.add_work(kitchen, 'exclude', note='vendored')
    given = j(run, 'work', 'op=distribute', 'agents=3', cwd=mapped)['results']
    order = [todo[4], todo[0], todo[1], todo[2], todo[3], backlog[1], backlog[0]]
    assert [record['id'] for record in given] == [record.id for record in order]
    first = AGENT_GLYPHS[:3]
    assert 'owl' not in first and 'snail' not in first
    assert [glyph_of(record) for record in given] == [first[0], first[1], first[2], first[0], first[1], first[2],
                                                      first[0]]
    read = {record['id']: record for given_open in ('true', 'false')
            for record in j(run, 'work', 'limit=0', f'open={given_open}', cwd=mapped)['results']}
    assert [glyph_of(read[record.id]) for record in order] == [glyph_of(record) for record in given]
    assert [glyph_of(read[one.id]) for one in (taken, done, outside)] == ['owl', 'snail', None]
    again = j(run, 'work', 'op=distribute', 'agents=1', cwd=mapped)['results']  # one agent: every open ticket in one lane
    assert {glyph_of(record) for record in again} == {AGENT_GLYPHS[0]} and len(again) == 7
    read = {record['id']: record for given_open in ('true', 'false')
            for record in j(run, 'work', 'limit=0', f'open={given_open}', cwd=mapped)['results']}
    assert [glyph_of(read[one.id]) for one in (taken, done, outside)] == ['owl', 'snail', None]


@pytest.mark.req('VIEW-040')
@pytest.mark.req('BASE-035')
def test_a_tickets_glyph_is_set_by_edit_shown_on_its_read_and_a_name_that_is_no_glyph_is_kept_with_a_notice(run,
                                                                                                         mapped):
    ticket = Store('proj').add_work(Node('element', 'code.timer.kitchen'), 'missing', task='a lane of its own')
    assert 'map' not in j(run, 'work', f'id={ticket.id}', cwd=mapped)   # nothing at all when it keeps none
    edited =j(run, 'work', 'op=edit', f'id={ticket.id}', 'glyph=moth', cwd=mapped)
    assert glyph_of(edited) == 'moth' and not edited.get('notices')
    assert glyph_of(j(run, 'work', f'id={ticket.id}', cwd=mapped)) == 'moth'
    odd = j(run, 'work', 'op=edit', f'id={ticket.id}', 'glyph=dragon', cwd=mapped)
    assert glyph_of(odd) == 'dragon' and [notice['where'] for notice in odd['notices']] == ['glyph']
    assert glyph_of(j(run, 'work', f'id={ticket.id}', cwd=mapped)) == 'dragon'
    untouched = j(run, 'work', 'op=edit', f'id={ticket.id}', 'task=still its lane', cwd=mapped)
    assert glyph_of(untouched) == 'dragon' and untouched['task'] == 'still its lane'
    # the glyph is written in one transaction with the work record's own changes: a refused edit leaves no glyph row
    assert run('map', 'work', 'op=edit', 'id=' + '0' * 32, 'glyph=moth', cwd=mapped, ok=False).returncode != 0
    with Store('proj', module='map').tables(write=False) as tx:
        assert tx.get('glyphs', {'work_id': '0' * 32}) is None


@pytest.mark.req('VIEW-040')
@pytest.mark.req('BASE-035')
def test_every_map_work_result_shows_the_tickets_glyph(run, mapped):
    """VIEW-040: every `map work` result shows each record's glyph under `map`, so an agent taking, planning, stepping,
    moving or finishing a ticket reads which agent's lane it is in."""
    ticket = Store('proj').add_work(Node('element', 'code.timer.kitchen'), 'missing', task='a lane of its own')
    j(run, 'work', 'op=edit', f'id={ticket.id}', 'glyph=moth', cwd=mapped)
    for verb in (['op=take', 'by=claude'], ['op=plan', 'steps=2'], ['op=step', 'said=Traced it.'],
                 ['op=move', 'column=doing'], ['op=done', 'resolution=built']):
        assert glyph_of(j(run, 'work', *verb, f'id={ticket.id}', cwd=mapped)) == 'moth', verb


@pytest.mark.req('VIEW-040')
def test_distributing_over_no_agents_or_more_than_there_are_glyphs_is_refused_and_changes_nothing(run, mapped):
    store = Store('proj')
    ticket = store.add_work(Node('element', 'code.timer.kitchen'), 'missing', task='waiting')
    lane = store.add_work(Node('element', 'code.timer.kitchen'), 'missing', task='in a lane already')
    j(run, 'work', 'op=edit', f'id={lane.id}', 'glyph=moth', cwd=mapped)
    for agents in ('0', '18'):
        refused = run('map', 'work', 'op=distribute', f'agents={agents}', cwd=mapped, ok=False)
        assert refused.returncode != 0 and '1 to 17' in refused.stderr + refused.stdout
    assert run('map', 'work', 'op=distribute', 'agents=two', cwd=mapped, ok=False).returncode != 0
    assert glyph_of(j(run, 'work', f'id={ticket.id}', cwd=mapped)) is None
    assert glyph_of(j(run, 'work', f'id={lane.id}', cwd=mapped)) == 'moth'


@pytest.mark.req('VIEW-040')
@pytest.mark.req('STORE-045')
@pytest.mark.req('BASE-046')
def test_a_tickets_glyph_is_kept_in_the_map_modules_own_table_keyed_by_the_work_id_and_not_in_the_work_table(run,
                                                                                                           mapped):
    """Ticket 90430bba: a feature's field belongs in a module table keyed by the work id through the public table API,
    STORE-045, and the chassis is the fixed part, BASE-046. The glyph is a row of the map module's table beside the
    map, and the work table holds no glyph column."""
    store = Store('proj')
    ticket = store.add_work(Node('element', 'code.timer.kitchen'), 'missing', task='a lane of its own')
    other = store.add_work(Node('element', 'code.timer.kitchen'), 'missing', task='no lane')
    j(run, 'work', 'op=edit', f'id={ticket.id}', 'glyph=moth', cwd=mapped)
    with Store('proj', module='map').tables(write=False) as tx:
        assert tx.get('glyphs', {'work_id': ticket.id}) == {'work_id': ticket.id, 'glyph': 'moth'}
        assert tx.get('glyphs', {'work_id': other.id}) is None
        assert tx.place == 'metaform'                                   # beside the work records, in the map's store
    from metaform.modules.map import TABLES
    work_table = TABLES.table('work').schema.split('CREATE TABLE IF NOT EXISTS work(')[1].split(');')[0]
    assert 'glyph' not in [line.split()[0] for line in work_table.strip().splitlines()]


@pytest.mark.req('VIEW-040')
def test_the_map_modules_glyphs_are_the_seventeen_the_page_draws_in_its_order():
    """The glyph a ticket holds is drawn by the page, so the names and their order are the page's, VIEW-035."""
    from pathlib import Path

    import metaform
    from metaform.modules.map import AGENT_GLYPHS
    page = (Path(metaform.__file__).parent / 'modules' / 'web' / 'page' / 'agents3d.js').read_text(encoding='utf-8')
    listed = re.search(r'export const GLYPHS = \[(.*?)\];', page, re.DOTALL)
    assert listed is not None
    assert tuple(re.findall(r"'([a-z]+)'", listed.group(1))) == AGENT_GLYPHS
    assert len(AGENT_GLYPHS) == 17


@pytest.mark.req('LAYER-025')
@pytest.mark.req('MAP-020')
def test_refining_a_join_changes_its_ifd(run, mapped):
    """A join's IFD changes by refining with the rest of its fields, Rich 2026-10-01: if you see issues you can fix
    them."""
    join = Store('proj').joins('code.timer.kitchen').results[0]
    refined = json.loads(refined_by(run, mapped, f'receiver={join.receiver_address}', f'provider={join.elements[0].address}',
                           'ifd=sends', 'reason=The alarm is what the timer encounters.').stdout)
    assert not [notice for notice in refined.get('notices', []) if notice['where'] == 'ifd']
    now = next(held for held in Store('proj').joins('code.timer.kitchen').results if held.id == join.id)
    assert now.ifd == 'sends'


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
    read, its refs, which the sources layer holds, and its open questions, and the same for each node it links."""
    run('map', 'ask', 'code.display.digit', 'Four digits or six?', 'suggestions=["Four", "Six"]', *FORM, cwd=described)
    made = j(run, 'work', 'op=add', 'node=code.display.digit', 'condition=flawed', 'task=dim the digits at night',
             'links=["element:code.timer.kitchen"]', cwd=described)
    read = run('map', 'work', f'id={made["id"]}', '--json', cwd=described)
    assert read.returncode == 0 and 'TypeError' not in read.stderr
    ticket = json.loads(read.stdout)
    assert (ticket['id'], ticket['task'], ticket['condition']) == (made['id'], 'dim the digits at night',
                                                                       'flawed')
    at = ticket['at']
    assert at['element']['address'] == 'code.display.digit'
    assert [ref for group in at['layers'] if group['layer'] == 'sources' for item in group['items']
            for ref in item['refs']] == [{'key': 'path', 'value': 'src/display.py'}, {'key': 'spec', 'value': 'DISP-001'}]
    assert [(one['kind'], one['text'].split('\n')[0]) for one in at['messages']] == [('question', 'Four digits or six?')]
    assert [join['receiver'] for join in at['provides']] == ['code.timer.kitchen']
    assert [linked['element']['address'] for linked in ticket['linked']] == ['code.timer.kitchen']
    text = run('map', 'work', f'id={made["id"]}', cwd=described).stdout
    assert 'Four digits or six?' in text and 'src/display.py' in text


@pytest.mark.req('MAP-048')
@pytest.mark.req('LAYER-012')
@pytest.mark.parametrize('on_join', [False, True])
def test_ticket_handoff_includes_module_memories_at_its_node_and_linked_nodes(run, mapped, on_join):
    store = Store('proj')
    target = (Node('join', store.joins('code.timer.kitchen').results[0].id) if on_join else
              Node('element', 'code.timer.kitchen'))
    from tests.storekit import page_note  # the note is the person's, written from the page, VIEW-034
    page_note('proj', str(target), 'Check the circuit before replacing the timer.')
    page_note('proj', 'element:code.alarm.audible', 'The tone driver was rewired.')
    ticket = store.add_work(target, 'broken', task='repair the timer', links=[Node('element', 'code.alarm.audible')])
    read = j(run, 'work', f'id={ticket.id}', cwd=mapped)
    assert read['at']['memory']['note']['text'] == 'Check the circuit before replacing the timer.'
    assert read['linked'][0]['memory']['note']['text'] == 'The tone driver was rewired.'


@pytest.mark.req('BASE-035')
@pytest.mark.req('MAP-048')
def test_a_work_read_hook_that_raises_is_named_in_the_ticket_read_and_one_that_returns_none_adds_nothing(
        run, mapped, user_module):
    """Work f6adbefd, 2026-10-03: what a module keeps on a work record shows in `map work id=<id>` under its id; a
    failing hook does not stop the read."""
    user_module('breaks', '''
        from metaform.module import Module
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        def work_read(ctx, record):
            raise ValueError(f'no field for {record.id}')
        MODULE = Module(id='breaks', summary='x', purpose='Breaks. Details: metaform help breaks.',
                        work_read=work_read)
    ''')
    user_module('quiet', '''
        from metaform.module import Module
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        MODULE = Module(id='quiet', summary='x', purpose='Quiet. Details: metaform help quiet.',
                        work_read=lambda ctx, record: None)
    ''')
    user_module('zz', '''
        from metaform.module import Module
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        MODULE = Module(id='zz', summary='x', purpose='Last. Details: metaform help zz.',
                        work_read=lambda ctx, record: {'condition': record.condition})
    ''')
    user_module('linked', '''
        from metaform.module import Module
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        MODULE = Module(id='linked', summary='x', purpose='Clashes. Details: metaform help linked.',
                        work_read=lambda ctx, record: 'replaced')
    ''')
    made = j(run, 'work', 'op=add', 'node=code.alarm.audible', 'condition=missing', 'task=wire it', cwd=mapped)
    ticket = j(run, 'work', f'id={made["id"]}', cwd=mapped)
    assert ticket['task'] == 'wire it' and ticket['at']['element']['address'] == 'code.alarm.audible'
    assert ticket['breaks'] == {'failed': f'ValueError: no field for {made["id"]}'}
    assert ticket['zz'] == {'condition': 'missing'}, 'the read goes on past a failing hook'
    assert list(ticket).index('breaks') < list(ticket).index('zz'), 'module id order'
    assert 'quiet' not in ticket
    assert ticket['linked'] == [], 'a field the read holds already is never replaced'


@pytest.mark.req('MAP-048')
def test_map_work_reading_a_ticket_names_the_list_nouns_it_does_not_read_and_an_unknown_id(run, mapped):
    made = j(run, 'work', 'op=add', 'node=code.alarm.audible', 'condition=missing', 'task=wire it', cwd=mapped)
    read = j(run, 'work', f'id={made["id"]}', 'condition=broken', cwd=mapped)
    assert read['id'] == made['id'] and [notice['where'] for notice in read['notices']] == ['condition']
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
    assert [one['id'] for one in j(run, 'where', 'code.alarm.audible', cwd=mapped)['work']] == [made['id']]
    assert made['id'] in run('map', 'where', 'code.alarm.audible', cwd=mapped).stdout


@pytest.mark.req('LAYER-025')
@pytest.mark.req('MAP-005')
def test_refine_names_what_it_changes_by_address_and_never_hands_an_agent_an_id(run, mapped):
    """Rich, 2026-10-03: what an agent names is most easily inferred from what it already read, an address; an id it
    must look up and copy is an extra step and the string a model garbles first. Refine takes no id and returns none;
    two purposes its addresses cannot tell apart are both named, and neither is changed."""
    nouns = {noun.name for verb in __import__('metaform.modules.map', fromlist=['MODULE']).MODULE.verbs
             if verb.name == 'refine' for noun in verb.nouns}
    assert 'id' not in nouns and {'receiver', 'provider', 'address'} <= nouns
    store = Store('proj')
    join = store.joins('code.timer.kitchen').results[0]
    done = json.loads(refined_by(run, mapped, f'receiver={join.receiver_address}', f'provider={join.elements[0].address}',
                                 'purpose=Changed by address.', 'reason=r').stdout)
    element = json.loads(refined_by(run, mapped, 'address=code.alarm.audible', 'role=NE', 'reason=r').stdout)
    for result in (done, element):
        assert not re.search(r'[0-9a-f]{32}', json.dumps(result)), result
    assert [found.purpose for found in Store('proj').joins('code.timer.kitchen').results
            if found.id == join.id] == ['Changed by address.']
    assert Store('proj').element('code.alarm.audible').role == 'NE'
    k(run, mapped, 'op=add-join', 'layer=intake-1', f'receiver={join.receiver_address}',
      f'elements={json.dumps([join.elements[0].address])}', 'purpose=A second why.', 'ef=f')
    both = json.loads(refined_by(run, mapped, f'receiver={join.receiver_address}', f'provider={join.elements[0].address}',
                                 'purpose=Which one?', 'reason=r').stdout)
    message = ' '.join(notice['message'] for notice in both['notices'])
    assert 'Changed by address.' in message and 'A second why.' in message
    assert sorted(found.purpose for found in Store('proj').joins('code.timer.kitchen').results
                  if join.elements[0].address in [held.address for held in found.elements]) == [
        'A second why.', 'Changed by address.']


@pytest.mark.req('MAP-005')
@pytest.mark.req('MAP-046')
@pytest.mark.req('MAP-048')
def test_map_work_names_a_join_by_its_receiver_and_provider_and_an_element_it_holds_by_its_address(run, mapped):
    """Rich, 2026-10-03, ticket ad135d54: what an agent names is most easily inferred from what it already read; ids
    are internal. An agent names a join by its receiver and an element it holds, as refine does, and an element the
    join holds by address beside them, and never handles join:<id>, in the node a ticket is on and in the nodes it
    links."""
    store = Store('proj')
    join = store.joins('code.timer.kitchen').results[0]
    with store.atomic():
        store.add_element('intake-1', 'code.alarm.audible.piezo', name_length=3, role='SE')
        store.refine(join.id, {'elements': ['code.alarm.audible', 'code.alarm.audible.piezo']}, reason='r')
        store.add_element('intake-1', 'code.display.digit', name_length=2, role='SE')
        store.add_element('intake-1', 'code.display.digit.segment', name_length=3, role='SE')
        shown = store.add_join('intake-1', 'code.timer.kitchen', ['code.display.digit', 'code.display.digit.segment'],
                               purpose='Show the time left.')
    piezo = store.element('code.alarm.audible.piezo').id
    # The timer holds two joins, so the provider, not the order they are held in, picks one.
    named = ('receiver=code.timer.kitchen', 'provider=code.alarm.audible')
    display = ('receiver=code.timer.kitchen', 'provider=code.display.digit')
    on_join = j(run, 'work', 'op=add', *named, 'condition=broken', 'task=fix the tone', cwd=mapped)
    assert (on_join['node_kind'], on_join['receiver_address'], on_join['provider_address']) == (
        'join', 'code.timer.kitchen', 'code.alarm.audible')
    beside = j(run, 'work', 'op=add', *display, 'node=element:code.alarm.audible', 'condition=flawed', cwd=mapped)
    assert (beside['node_kind'], beside['provider_address']) == ('join', 'code.display.digit')
    assert said(beside) == [('node', 'receiver, provider and address name the node; node was not read.')]
    on_part = j(run, 'work', 'op=add', *named, 'address=code.alarm.audible.piezo', 'condition=missing', cwd=mapped)
    assert (on_part['node_kind'], on_part['address']) == ('element', 'code.alarm.audible.piezo')
    elsewhere = run('map', 'work', 'op=add', *named, 'address=code.display.digit.segment', 'condition=missing',
                    '--json', cwd=mapped, ok=False)
    assert elsewhere.returncode == 2 and 'code.display.digit.segment is not held by' in elsewhere.stderr
    on_element = j(run, 'work', 'op=add', 'address=code.alarm.audible', 'condition=flawed', cwd=mapped)
    assert (on_element['node_kind'], on_element['address']) == ('element', 'code.alarm.audible')
    assert [row['id'] for row in j(run, 'work', *named, cwd=mapped)['results']] == [on_join['id']]
    assert [row['id'] for row in j(run, 'work', *display, cwd=mapped)['results']] == [beside['id']]
    assert [row['id'] for row in j(run, 'work', f'node=join:{shown.id}', cwd=mapped)['results']] == [
        beside['id']]
    cook = {'receiver': 'stakeholder.cook.home', 'provider': 'code.timer.kitchen'}
    linked = j(run, 'work', 'op=add', 'node=code.alarm.audible', 'condition=flawed',
               f'links={json.dumps([cook, "code.timer.kitchen"])}', cwd=mapped)
    cook_id = store.joins('stakeholder.cook.home').results[0].id
    assert [(link['kind'], link['id']) for link in linked['links']] == [
        ('join', cook_id), ('element', store.element('code.timer.kitchen').id)]
    edited = j(run, 'work', 'op=edit', f'id={linked["id"]}',
               'links=[{"receiver": "code.timer.kitchen", "provider": "code.alarm.audible", '
               '"address": "code.alarm.audible.piezo"}, {"receiver": "code.timer.kitchen", '
               '"provider": "code.display.digit"}]', cwd=mapped)
    assert [(link['kind'], link['id']) for link in edited['links']] == [('element', piezo), ('join', shown.id)]
    unheld = run('map', 'work', 'op=add', 'receiver=code.timer.kitchen', 'provider=code.nosuch.node',
                 'condition=missing', '--json', cwd=mapped, ok=False)
    assert unheld.returncode == 2 and 'code.timer.kitchen has no purpose served by code.nosuch.node' in unheld.stderr
    assert len(j(run, 'work', 'limit=0', cwd=mapped)['results']) == 5


@pytest.mark.req('MAP-046')
@pytest.mark.req('STORE-042')
def test_map_work_at_an_element_lists_the_tickets_on_the_joins_it_receives_or_provides(run, mapped):
    """Ticket dd2a9caf, 2026-10-02: an agent told its node could not find its ticket on a join at that node. An
    element lists its own tickets and those on the joins it receives and on the joins that hold it."""
    store = Store('proj')
    alarm = store.joins('code.timer.kitchen').results[0]
    with store.atomic():
        store.add_element('intake-1', 'code.alarm.audible.piezo', name_length=3, role='SE')
        store.refine(alarm.id, {'elements': ['code.alarm.audible', 'code.alarm.audible.piezo']}, reason='r')
        store.add_element('intake-1', 'code.display.digit', name_length=2, role='SE')
        shown = store.add_join('intake-1', 'code.timer.kitchen', 'code.display.digit', purpose='Show the time left.')
    cook = store.joins('stakeholder.cook.home').results[0]
    on_alarm = store.add_work(Node('element', 'code.alarm.audible'), 'flawed', task='on the element').id
    on_cook = store.add_work(Node('join', cook.id), 'broken', task='on the cook join').id
    on_join = store.add_work(Node('join', alarm.id), 'missing', task='on the alarm join').id
    on_part = store.add_work(Node('element', 'code.alarm.audible.piezo'), 'missing', task='on the piezo').id
    on_display = store.add_work(Node('join', shown.id), 'flawed', task='on the display join').id
    finished = store.add_work(Node('join', alarm.id), 'broken', task='done already').id
    store.finish_work(finished, 'fixed')

    def listed(*given):
        return [row['id'] for row in j(run, 'work', *given, 'limit=0', cwd=mapped)['results']]
    assert listed('node=element:code.alarm.audible.piezo') == [on_join, on_part]  # open, the default, MAP-049
    assert listed('node=element:code.alarm.audible', 'open=false') == [finished]
    assert listed('node=code.alarm.audible', 'open=true') == [on_alarm, on_join]
    assert listed('address=code.alarm.audible', 'open=true') == [on_alarm, on_join]
    assert listed('node=element:code.timer.kitchen', 'open=true') == [on_cook, on_join, on_display]
    assert listed('node=element:code.timer.kitchen', 'condition=missing') == [on_join]
    assert listed(f'node=join:{alarm.id}', 'open=true') == [on_join]
    # The web panel's read of one object stays that object's own records.
    assert [row.id for row in store.work(Node('element', 'code.alarm.audible'), limit=0).results] == [on_alarm]


@pytest.mark.req('MAP-005')
def test_map_work_ask_and_tell_never_tell_an_agent_to_name_a_node_by_a_join_id(run, mapped):
    """What an agent reads of a verb: its help on the command line and its MCP schema, which carries each noun's
    help, a required one's included."""
    from metaform.modules.map import MODULE
    from metaform.modules.mcp.server import verb_schema
    verbs = {verb.name: verb for verb in MODULE.verbs}
    for name in ('work', 'ask', 'tell'):
        assert 'join:<id>' not in run('help', 'map', name, cwd=mapped).stdout, name
        assert 'join:<id>' not in json.dumps(verb_schema(verbs[name], mapped)), name


@pytest.mark.req('MAP-005')
@pytest.mark.req('MAP-050')
def test_ask_and_tell_take_node_first_and_provider_beside_it_names_the_purpose_node_holds(run, mapped):
    """Rich, 2026-10-03, ticket ad135d54: keep node first; provider= beside it names the join node holds, node
    being the receiver. An element the join holds is named by address beside them, as in memory and map work."""
    store = Store('proj')
    join = store.joins('code.timer.kitchen').results[0]
    with store.atomic():
        store.add_element('intake-1', 'code.alarm.audible.piezo', name_length=3, role='SE')
        store.refine(join.id, {'elements': ['code.alarm.audible', 'code.alarm.audible.piezo']}, reason='r')
        piezo = store.element('code.alarm.audible.piezo').id
        store.add_element('intake-1', 'code.display.digit', name_length=2, role='SE')
        shown = store.add_join('intake-1', 'code.timer.kitchen', 'code.display.digit', purpose='Show the time left.')
    asked = j(run, 'ask', 'code.timer.kitchen', 'Is the display still wanted?', 'provider=code.display.digit',
              YES_NO, *FORM, cwd=mapped)
    assert (asked['node_kind'], asked['node_id'], asked['receiver_address'], asked['provider_address']) == (
        'join', shown.id, 'code.timer.kitchen', 'code.display.digit')
    told = j(run, 'tell', 'element:code.timer.kitchen', 'The piezo is quiet.', 'provider=code.alarm.audible',
             'address=code.alarm.audible.piezo', cwd=mapped)
    assert (told['node_kind'], told['node_id']) == ('element', piezo)
    plain = j(run, 'ask', 'code.alarm.audible', 'Louder?', YES_NO, *FORM, cwd=mapped)
    assert (plain['node_kind'], plain['address']) == ('element', 'code.alarm.audible')
    alone = j(run, 'tell', 'code.alarm.audible', 'Quiet.', 'address=code.alarm.audible.piezo', cwd=mapped)
    assert (alone['node_kind'], alone['address']) == ('element', 'code.alarm.audible')
    assert said(alone) == [('address', 'address names an element a join holds only with provider; it was not read.')]
    unheld = run('map', 'tell', 'code.timer.kitchen', 'x', 'provider=code.nosuch.node', '--json', cwd=mapped, ok=False)
    assert unheld.returncode == 2 and 'code.timer.kitchen has no purpose served by code.nosuch.node' in unheld.stderr
    assert [message['node_id'] for message in j(run, 'messages', 'limit=0', cwd=mapped)['results']] == [
        shown.id, piezo, plain['node_id'], alone['node_id']]


@pytest.mark.req('STORE-042')
@pytest.mark.req('MAP-050')
def test_tickets_links_and_questions_move_between_nodes_through_metaform(run, mapped):
    """Work 71470758: relocating work and questions must not require direct SQL or recreate their records."""
    store = Store('proj')
    join = store.joins('code.timer.kitchen').results[0]
    with store.atomic():
        store.add_element('intake-1', 'code.alarm.audible.piezo', name_length=3, role='SE')
        store.refine(join.id, {'elements': ['code.alarm.audible', 'code.alarm.audible.piezo']}, reason='r')
    piezo = store.element('code.alarm.audible.piezo').id
    ticket = j(run, 'work', 'op=add', 'node=code.timer.kitchen', 'condition=broken', 'task=fix the drift',
               'links=["code.timer.kitchen", "code.alarm.audible"]', cwd=mapped)
    j(run, 'work', 'op=take', f'id={ticket["id"]}', 'steps=2', 'by=codex', cwd=mapped)
    j(run, 'work', 'op=step', f'id={ticket["id"]}', 'said=Measured the drift.', cwd=mapped)
    j(run, 'work', 'op=edit', f'id={ticket["id"]}', 'glyph=moth', cwd=mapped)
    question = j(run, 'ask', 'code.timer.kitchen', 'Keep the tone?', YES_NO, *FORM, cwd=mapped)
    answered = j(run, 'reply', question['id'], 'answer=Yes', cwd=mapped)
    moved = j(run, 'work', 'op=edit', f'id={ticket["id"]}', 'node=code.alarm.audible',
              'links=["code.alarm.audible", "code.alarm.audible"]', cwd=mapped)
    assert not moved['notices'] and moved['address'] == 'code.alarm.audible'
    assert [link['address'] for link in moved['links']] == ['code.alarm.audible', 'code.alarm.audible']
    assert (moved['taken_by'], moved['steps_done'], moved['said'][0]['said'], moved['map']['glyph']) == (
        'codex', 1, 'Measured the drift.', 'moth')
    named = ['receiver=code.timer.kitchen', 'provider=code.alarm.audible', 'address=code.alarm.audible.piezo']
    moved = j(run, 'work', 'op=edit', f'id={ticket["id"]}', *named, cwd=mapped)
    assert not moved['notices'] and (moved['node_kind'], moved['node_id']) == ('element', piezo)
    moved_question = j(run, 'messages', 'op=move', f'id={question["id"]}', 'node=code.timer.kitchen',
                       'provider=code.alarm.audible', 'address=code.alarm.audible.piezo', cwd=mapped)
    assert not moved_question['notices'] and (moved_question['node_kind'], moved_question['node_id']) == (
        'element', piezo)
    assert (moved_question['suggestions'], moved_question['answer'], moved_question['closed']) == (
        question['suggestions'], 'Yes', answered['closed'])
    assert not j(run, 'messages', 'node=code.timer.kitchen', cwd=mapped)['results']
    at = j(run, 'work', f'id={ticket["id"]}', cwd=mapped)['at']
    assert at['element']['address'] == 'code.alarm.audible.piezo'
    assert [one.id for one in store.work(Node('element', 'code.timer.kitchen')).results] == []
    assert store.element('code.timer.kitchen').address == 'code.timer.kitchen'


@pytest.mark.req('LAYER-021')
@pytest.mark.req('MAP-048')
def test_knowledge_add_item_takes_the_flags_and_a_task_item_adds_a_ticket_at_its_node(run, mapped):
    """Rich, 2026-10-03, D91 and D92: read_first and always_show are stored on the item; task adds a ticket at the
    item's node and is not stored on the item. The ticket read returns the read_first items ahead of at."""
    k(run, mapped, 'op=create', 'layer=critic', 'variable=What the critic says at each node.', 'mutable=true',
      'hideable=true', *PROVENANCE)
    first = json.loads(k(run, mapped, 'op=add-item', 'layer=critic', 'node=element:code.timer.kitchen',
                         'value="Read the timer spec first."', 'read_first=true', 'always_show=true').stdout)
    assert (first['read_first'], first['always_show']) == (True, True)
    task = json.loads(k(run, mapped, 'op=add-item', 'layer=critic', 'node=element:code.timer.kitchen',
                        'value="Stop the alarm after a minute."', 'task=true', 'condition=missing').stdout)
    assert 'task' not in task and (task['read_first'], task['always_show']) == (False, False)
    tickets = j(run, 'work', 'node=element:code.timer.kitchen', 'open=true', cwd=mapped)['results']
    assert [ticket['condition'] for ticket in tickets] == ['missing']
    assert j(run, 'work', f'id={tickets[0]["id"]}', cwd=mapped)['task'] == 'Stop the alarm after a minute.'
    told = [notice for notice in task['notices'] if notice['where'] == 'task']
    assert len(told) == 1 and tickets[0]['id'] in told[0]['message']
    k(run, mapped, 'op=finish', 'layer=critic')
    read = j(run, 'work', f'id={tickets[0]["id"]}', cwd=mapped)
    assert [item['value'] for item in read['read_first']] == ['Read the timer spec first.']
    assert list(read).index('read_first') < list(read).index('at')


# ------------------------------------------------------------------ eligible agents, ticket bd96cbd1

def eligible_of(record):
    """The agent types eligible for a ticket, as the map module shows them under its own id, BASE-035; None when the
    ticket keeps none, which is any agent."""
    return (record.get('map') or {}).get('eligible')


@pytest.mark.req('MAP-058')
@pytest.mark.req('STORE-045')
@pytest.mark.req('BASE-046')
def test_any_agent_is_eligible_by_default_and_the_eligible_agents_are_kept_in_the_map_modules_own_table(run, mapped):
    """Rich, ticket bd96cbd1: any agent is eligible by default unless the user specifies otherwise, and existing
    tickets default to Any. The user's choice is one or more agent types, shown on the ticket; like the glyph it is
    the map module's own field, a row keyed by the work id, and the work table has no column for it."""
    old = Store('proj').add_work(Node('element', 'code.timer.kitchen'), 'missing', task='written before the setting')
    assert eligible_of(j(run, 'work', f'id={old.id}', cwd=mapped)) is None
    made = j(run, 'work', 'op=add', 'node=code.alarm.audible', 'condition=flawed', 'task=quieter tone',
             'eligible=["claude"]', cwd=mapped)
    assert eligible_of(made) == ['claude']
    assert eligible_of(j(run, 'work', f'id={made["id"]}', cwd=mapped)) == ['claude']
    both = j(run, 'work', 'op=edit', f'id={made["id"]}', 'eligible=["claude", "codex"]', cwd=mapped)
    assert eligible_of(both) == ['claude', 'codex'] and not both.get('notices')
    listed = {record['id']: record for record in j(run, 'work', 'limit=0', cwd=mapped)['results']}
    assert eligible_of(listed[made['id']]) == ['claude', 'codex'] and eligible_of(listed[old.id]) is None
    untouched = j(run, 'work', 'op=edit', f'id={made["id"]}', 'task=quieter still', cwd=mapped)
    assert eligible_of(untouched) == ['claude', 'codex']
    with Store('proj', module='map').tables(write=False) as tx:
        assert tx.get('eligible', {'work_id': made['id']}) is not None
        assert tx.get('eligible', {'work_id': old.id}) is None
    from metaform.modules.map import TABLES
    work_table = TABLES.table('work').schema.split('CREATE TABLE IF NOT EXISTS work(')[1].split(');')[0]
    assert 'eligible' not in [line.split()[0] for line in work_table.strip().splitlines()]
    anyone = j(run, 'work', 'op=edit', f'id={made["id"]}', 'eligible=[]', cwd=mapped)
    assert eligible_of(anyone) is None, 'an empty choice is any agent again'
    odd = j(run, 'work', 'op=edit', f'id={made["id"]}', 'eligible=["cursor"]', cwd=mapped)
    assert eligible_of(odd) == ['cursor'] and [notice['where'] for notice in odd['notices']] == ['eligible']


@pytest.mark.req('MAP-058')
def test_a_direct_claim_on_the_command_line_is_honored_by_the_agent_its_by_names(run, mapped):
    """Ticket bd96cbd1: direct agent claims honor the choice. On the command line the claiming agent is the first
    word of by, as the dispatch runner writes it, `claude <session id>`. An agent not on the list, or a by naming
    no agent, is refused and the ticket stays untaken; an agent on it takes the ticket. A ticket with no choice is
    taken by anyone, as before. A person moving the card to Doing is not an agent's claim and is not refused."""
    store = Store('proj')
    kitchen = Node('element', 'code.timer.kitchen')
    gui = store.add_work(kitchen, 'missing', task='GUI work')
    j(run, 'work', 'op=edit', f'id={gui.id}', 'eligible=["claude"]', cwd=mapped)
    for by in ('codex 9f2c', 'someone', None):
        refused = run('map', 'work', 'op=take', f'id={gui.id}', *([f'by={by}'] if by else []), cwd=mapped,
                      ok=False)
        said = refused.stdout + refused.stderr
        assert refused.returncode != 0 and 'claude' in said, (by, said)
        assert store.ticket(gui.id).work.taken is None
    took = j(run, 'work', 'op=take', f'id={gui.id}', 'by=claude 41ab', cwd=mapped)
    assert took['taken_by'] == 'claude 41ab'
    loose = store.add_work(kitchen, 'missing', task='anyone')
    assert j(run, 'work', 'op=take', f'id={loose.id}', 'by=someone', cwd=mapped)['taken_by'] == 'someone'
    person = store.add_work(kitchen, 'missing', task='the person takes it')
    j(run, 'work', 'op=edit', f'id={person.id}', 'eligible=["codex"]', cwd=mapped)
    moved = j(run, 'work', 'op=move', f'id={person.id}', 'column=doing', 'by=user', cwd=mapped)
    assert moved['taken_by'] == 'user'
