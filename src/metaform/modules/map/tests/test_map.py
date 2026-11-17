"""The map module: the data access object's map and layer operations as verbs, BASE-038, MAP and LAYER."""
from __future__ import annotations

import json
import re
import sqlite3
import subprocess
from pathlib import Path

import pytest

from metaform.data import Node, Store, StoreError

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
    return json.loads(run('map', *titled(args), '--json', cwd=cwd).stdout)


@pytest.mark.parametrize('board', ['', 'release'])
def test_filing_returns_active_board_column_and_reference(run, mapped, board):
    from metaform import settings

    if board:
        j(run, 'boards', 'op=add', f'name={board}', cwd=mapped)
    settings.put('board', board, mapped)
    added = j(run, 'work', 'op=add', 'node=code.timer.kitchen', 'task=Check alarm timing.', cwd=mapped)
    assert added['column'] == 'todo'
    assert added['map']['board'] == board
    assert added['map']['item'].startswith('code.timer.kitchen#')
    assert added['taken'] is None


def titled(args):
    """A ticket written or resolved here carries what such a write carries, MCP-037: op=add a title, op=done a why."""
    given = {arg.partition('=')[0] for arg in args if isinstance(arg, str)}
    if args[:1] == ('work',) and 'op=add' in args and 'title' not in given:
        args = (*args, 'title=A ticket')
    if args[:1] == ('work',) and 'op=done' in args and 'why' not in given:
        args = (*args, 'why=The work it asked for is done.')
    return args


# Who asks: map ask is the person's, on the command line; suggestions= is given per call. A question carries a title
# and a why, MCP-037.
FORM = ('by=builder', 'title=A question', 'why=It decides what is built.')
YES_NO = 'suggestions=["Yes", "No"]'


@pytest.mark.req('MAP-054')
def test_promote_command_keeps_the_purpose_and_creates_an_ordinary_element(run, mapped):
    store = Store('proj')
    original = store.joins('code.timer.kitchen').results[0]
    ends = ('receiver=code.timer.kitchen', 'provider=code.alarm.audible')
    run('memory', 'create_entities', json.dumps([{
        'name': 'delivery insight', 'entityType': 'finding',
        'observations': ['The cook needs an audible signal.'], 'why': 'It decides the alarm.'}]), *ends, cwd=mapped)
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

    made = j(run, 'collapse', 'fresh', '--confirm', cwd=mapped)
    assert made['name'] == 'fresh' and made['active']
    assert made['id'] != old.id
    assert any('stay with' in notice['message'] for notice in made['notices'])
    assert without_layer(store.roots().to_dict()) == without_layer(current)
    assert [(layer.name, layer.kind) for layer in store.layers().results] == [('base', 'base')]
    assert len(store.history(join.id).results) == 1
    assert {form['name']: form['active'] for form in j(run, 'bases', cwd=mapped)['results']} == {
        old.name: False, 'fresh': True}

    j(run, 'activate', old.name, '--confirm', cwd=mapped)
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
    # The authored prompt as written, then the mode's run: its layer and the whole metaform the intake agent built.
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
    run('map', 'work', 'op=add', 'title=A ticket', 'node=element:code.alarm.audible', 'condition=unbuilt', 'note=no speaker yet',
        'task=wire the piezo', cwd=mapped)
    kitchen = j(run, 'where', 'code.timer.kitchen', cwd=mapped)
    # The element and its joins by address with their purpose; what is held there is counted, MCP-039.
    assert set(kitchen) == {'kind', 'element', 'provides', 'receives', 'around'}
    assert (kitchen['element']['short_name'], kitchen['element']['role']) == ('kitchen timer', 'DE')
    assert kitchen['provides'] == [{'receiver': 'stakeholder.cook.home', 'purpose': 'Know when a dish is done.'}]
    assert [join['providers'] for join in kitchen['receives']] == [['code.alarm.audible']]
    held = j(run, 'where', 'code.timer.kitchen', 'contents=true', cwd=mapped)
    assert [(join['receiver'], join['purpose'], join['ef'], [one['address'] for one in join['elements']])
            for join in held['provides']] == [
        ('stakeholder.cook.home', 'Know when a dish is done.', 'Counts down and rings.', ['code.timer.kitchen'])]
    assert [([one['address'] for one in join['elements']], join['ef'], join['layer'])
            for join in held['receives']] == [(['code.alarm.audible'], 'Plays a tone.', 'intake-1')]
    alarm = j(run, 'where', 'code.alarm.audible', cwd=mapped)
    assert 'work' not in alarm and '1 open work' in alarm['around']
    assert 'metaform map work node=code.alarm.audible' in alarm['around']
    alarm = j(run, 'where', 'code.alarm.audible', 'contents=true', cwd=mapped)
    assert alarm['work'] == [{'id': Store('proj').work().results[0].id, 'condition': 'unbuilt',
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
    """A name goes anywhere there is a namespace and name length, the element's own field beside
    name_length; a join holds no name, its shape is its type, purpose, ef and ifd."""
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
    after = {found.id: found for found in Store('proj').joins('stakeholder.cook.home').results}[join.id]
    assert (after.purpose, after.receiver_address, after.layer) == ('First fix.', 'stakeholder.cook.home', 'intake-1')
    assert Store('proj').element('code.timer.kitchen').id == kitchen  # an element is renamed by to_address alone
    assert [layer.name for layer in Store('proj').layers(limit=0).results] == layers
    history = j(run, 'history', join.id, cwd=mapped)['results']
    assert [(version['layer'], version['op'], version['fields']['purpose']) for version in history] == [
        ('intake-1', 'add', join.purpose), ('intake-1', 'change', 'First fix.')]


@pytest.mark.req('LAYER-025')
def test_refine_adds_a_built_feature_to_the_map_under_the_intakes_rules_with_its_reason_evidence_and_author(
        run, mapped):
    """Refinement first (2026-10-17): an agent that built a feature puts it on the map in use with map refine, under
    the intake's rules and checks, with no intake: the element and the purpose record it serves land in the base's
    own layer, each version with its reason, evidence and author, and what does not fit the intake's form is named."""
    lacking = j(run, 'refine', 'address=code.alarm.snooze', 'reason=built', cwd=mapped)
    assert 'name_length=<n>' in lacking['notices'][0]['message'] and Store('proj').element('code.alarm.snooze') is None
    added = json.loads(refined_by(run, mapped, 'address=code.alarm.snooze', 'name_length=2', 'role=SE',
                                  'reason=built in ticket 1', 'evidence=src/snooze.py').stdout)
    assert added['op'] == 'add' and added['layer'] == 'intake-1'
    assert [notice['where'] for notice in added['notices']] == ['name']  # missing, stored empty, as the intake says
    joined = j(run, 'refine', 'receiver=code.timer.kitchen', 'elements=["code.alarm.snooze"]',
               'purpose=Ring again later.', 'ef=Delays the alarm.', 'ifd=sends', 'reason=built in ticket 1', cwd=mapped)
    assert joined['op'] == 'add' and joined['notices'] == []
    store = Store('proj')
    snooze = store.element('code.alarm.snooze')
    assert (snooze.layer, snooze.role) == ('intake-1', 'SE')
    [first] = store.history(snooze.id).results
    assert (first.reason, first.evidence, first.by) == ('built in ticket 1', 'src/snooze.py', 'cli')
    join = next(held for held in store.joins('code.timer.kitchen').results if held.purpose == 'Ring again later.')
    assert (join.layer, [each.address for each in join.elements]) == ('intake-1', ['code.alarm.snooze'])
    run('map', 'refine', 'receiver=code.timer.kitchen', 'provider=code.alarm.snooze', 'ifd=both', 'reason=checked',
        cwd=mapped, env={'METAFORM_WORK': 'w1', 'METAFORM_SESSION': 's1'})
    assert [(version.op, version.by) for version in store.history(join.id).results] == [
        ('add', 'cli'), ('change', 'work w1 session s1')]
    odd = j(run, 'refine', 'address=Code.Bad Address', 'role=XX', 'name=odd', 'reason=r', cwd=mapped)
    assert {notice['where'] for notice in odd['notices']} >= {'address', 'role'}  # the intake's own checks
    assert [layer.name for layer in store.layers(limit=0).results] == ['intake-1']  # no layer, no intake made


@pytest.mark.req('LAYER-025')
@pytest.mark.req('MAP-015')
def test_an_element_renamed_or_merged_by_refine_carries_its_joins_knowledge_tickets_and_memories(run, mapped):
    """An element renamed with to_address takes its purpose records, the knowledge at it, its tickets and its memories
    to the new address, so nothing is orphaned; merged into an element already there, the same, with no copies."""
    store = Store('proj')
    alarm = store.element('code.alarm.audible').id
    k(run, mapped, 'op=create', 'layer=sounds', 'variable=How it sounds.', 'mutable=true', 'hideable=true',
      *PROVENANCE)
    k(run, mapped, 'op=add-item', 'layer=sounds', 'node=element:code.alarm.audible', 'value="a bell"')
    ticket = j(run, 'work', 'op=add', 'node=element:code.alarm.audible', 'task=Make it louder.', cwd=mapped)['id']
    run('memory', 'create_entities', json.dumps([{'name': 'bell tone', 'entityType': 'finding',
                                                   'observations': ['Cooks hear 880 Hz best.'], 'why': 'Tone.'}]),
        'node=element:code.alarm.audible', cwd=mapped)
    moved = j(run, 'refine', 'address=code.alarm.audible', 'to_address=code.alarm.bell', 'reason=named for what it is',
              cwd=mapped)
    assert moved['op'] == 'move', moved
    store = Store('proj')
    bell = store.element('code.alarm.bell')
    assert store.element('code.alarm.audible') is None and bell.id != alarm and bell.role == 'SE'
    assert [each.address for each in store.joins('code.timer.kitchen').results[0].elements] == ['code.alarm.bell']
    assert [item.value for item in store.layer_items('sounds', Node('element', bell.id)).results] == ['a bell']
    assert store.work(Node('element', bell.id), limit=0).results[0].id == ticket
    assert json.loads(run('memory', 'orphaned', '--json', cwd=mapped).stdout)['joins'] == []
    held = json.loads(run('memory', 'open_nodes', '["bell tone"]', 'node=element:code.alarm.bell', '--json',
                          cwd=mapped).stdout)
    assert held['entities'][0]['observations'] == ['Cooks hear 880 Hz best.']
    merged = j(run, 'refine', 'address=code.alarm.bell', 'to_address=code.timer.kitchen', 'reason=one part',
               cwd=mapped)
    assert any(notice['where'] == 'to_address' for notice in merged['notices'])
    store = Store('proj')
    assert store.element('code.alarm.bell') is None
    assert store.work(Node('element', store.element('code.timer.kitchen').id), limit=0).results[0].id == ticket
    assert json.loads(run('memory', 'orphaned', '--json', cwd=mapped).stdout)['joins'] == []


@pytest.mark.req('LAYER-025')
def test_a_feature_recorded_in_a_knowledge_layer_is_adopted_into_the_base_keeping_its_id(run, mapped):
    k(run, mapped, 'op=create', 'layer=features', 'variable=Built features.', 'mutable=true', 'hideable=true',
      *PROVENANCE)
    made = json.loads(k(run, mapped, 'op=add-element', 'layer=features', 'address=code.alarm.repeat',
                        'name=repeat', 'name_length=2').stdout)
    refused = j(run, 'refine', 'address=code.alarm.repeat', 'name=again', 'reason=r', cwd=mapped)
    assert 'adopt=true' in refused['notices'][-1]['message']
    adopted = j(run, 'refine', 'address=code.alarm.repeat', 'adopt=true', 'reason=built', cwd=mapped)
    assert adopted['notices'][-1]['where'] == 'adopted'
    element = Store('proj').element('code.alarm.repeat')
    assert (element.id, element.layer) == (made['id'], 'intake-1')
    assert [version.layer for version in Store('proj').history(made['id']).results] == ['features', 'intake-1']


@pytest.mark.req('LAYER-025')
def test_finishing_a_ticket_says_when_its_work_is_not_on_the_map_with_the_refine_call(run, mapped):
    away = j(run, 'work', 'op=add', 'node=element:code.alarm.snooze', 'task=Build snooze.', cwd=mapped)['id']
    done = j(run, 'work', 'op=done', f'id={away}', 'resolution=built', cwd=mapped)
    assert any('map refine address=code.alarm.snooze' in notice['message'] for notice in done['notices']), done
    there = j(run, 'work', 'op=add', 'node=element:code.alarm.audible', 'task=Louder.', cwd=mapped)['id']
    assert j(run, 'work', 'op=done', f'id={there}', 'resolution=louder', cwd=mapped)['notices'] == []


@pytest.mark.req('MAP-046')
def test_a_ticket_removed_is_gone_with_its_steps_and_settings(run, mapped):
    """The person deletes a ticket for good, 2026-10-20: op=remove takes its row, its steps and what the map keeps on
    it; the list no longer holds it and a read of it is refused."""
    gone = j(run, 'work', 'op=add', 'node=element:code.alarm.audible', 'task=Delete me.', 'agent=codex', cwd=mapped)['id']
    j(run, 'work', 'op=plan', f'id={gone}', 'steps=2', cwd=mapped)
    j(run, 'work', 'op=step', f'id={gone}', 'said=One done.', cwd=mapped)
    removed = j(run, 'work', 'op=remove', f'id={gone}', cwd=mapped)
    assert removed['removed'] == gone and removed['address'] == 'code.alarm.audible'
    assert gone not in [one['id'] for one in j(run, 'work', cwd=mapped)['results']]
    refused = run('map', 'work', f'id={gone}', cwd=mapped, ok=False)
    assert refused.returncode != 0 and 'No work record' in refused.stderr


@pytest.mark.parametrize('board', ['', 'release'])
@pytest.mark.parametrize('dispatch_enabled', [True, False])
def test_archive_sheds_only_committed_tickets_and_resolves_their_numbers(
        run, mapped, monkeypatch, board, dispatch_enabled):
    from metaform.data import parse_reference
    from metaform.module import node_brief

    run('enable', 'dispatch', cwd=mapped)

    def git(*words):
        return subprocess.run(['git', *words], cwd=mapped, text=True, capture_output=True, check=True).stdout.strip()

    git('init', '-b', 'dev')
    git('config', 'user.email', 'tests@example.test')
    git('config', 'user.name', 'Test')
    git('commit', '--allow-empty', '-m', 'Initial')
    if board:
        j(run, 'boards', 'op=add', f'name={board}', cwd=mapped)
    store = Store('proj', module='map')

    def ticket(task, on=board):
        return j(run, 'work', 'op=add', 'node=code.alarm.audible', f'task={task}', f'board={on}', cwd=mapped)

    missing = ticket('Missing commit')
    side = ticket('Unmerged')
    mismatch = ticket('Wrong citation')
    other = ticket('Other board', '') if board else None
    opened = ticket('Still open')
    gone = ticket('Committed')
    j(run, 'work', 'op=edit', f'id={gone["id"]}', 'links=["code.timer.kitchen"]', cwd=mapped)
    j(run, 'work', 'op=plan', f'id={gone["id"]}', 'steps=1', cwd=mapped)
    j(run, 'work', 'op=step', f'id={gone["id"]}', 'said=Verified', cwd=mapped)
    for one in (gone, missing, side, mismatch, *([other] if other else [])):
        store.finish_work(one['id'], 'Delivered', 'Verified')
    dispatch = Store('proj', module='dispatch')
    with dispatch.tables() as tx:
        for one in (gone, missing):
            tx.insert('lines', {'session_id': 'monitor:progress', 'name': one['id'], 'work_id': one['id'],
                                'kind': 'progress', 'text': 'Done', 'seq': 1})
    with dispatch.tables() as tx:
        tx.insert('session_lines', {'session_id': 'conversation', 'name': 'message', 'work_id': gone['id'],
                                    'kind': 'peer', 'text': 'Retained conversation', 'seq': 1})
    if not dispatch_enabled:
        run('disable', 'dispatch', cwd=mapped)
    else:
        # An existing installation can still hold the old declaration before dispatch next writes its tables.
        from metaform import home
        with sqlite3.connect(home.store_path('proj', store.bound_base().id)) as db:
            declared = json.loads(db.execute("SELECT value FROM meta WHERE key='module:dispatch'").fetchone()[0])
            for table in declared['tables']:
                table.pop('on_remove', None)
            db.execute("UPDATE meta SET value=? WHERE key='module:dispatch'", (json.dumps(declared),))

    def commit(one, item=None):
        message = (f'Completed\n\nResolution: Delivered\n\nTicket state:\n{store.work_snapshot(one["id"])}\n\n'
                   f'Metaform-Ticket: {one["id"]}\n'
                   f'Metaform-Number: {item or one["map"]["item"]}\nMetaform-Node: code.alarm.audible\n'
                   f'Metaform-Board: {board}\nMetaform-Agent: test\n')
        git('add', 'feature.txt')
        git('commit', '--allow-empty', '-m', message)
        return git('rev-parse', 'HEAD')

    (mapped / 'feature.txt').write_text('Delivered\n')
    sha = commit(gone)
    commit(mismatch, 'code.alarm.audible#fff')
    git('checkout', '-b', 'unmerged')
    commit(side)
    git('checkout', 'dev')
    before = store.where('code.alarm.audible')
    assert len(before.past_work) == (5 if other else 4), 'Live records and commits count once'
    done = j(run, 'boards', 'op=line', f'name={board}', cwd=mapped)
    assert done['removed'] == [gone['id']]
    assert store.ticket(opened['id']).work.done is None
    assert {one['id'] for one in done['kept']} == {missing['id'], side['id'], mismatch['id']}
    assert all(one['fault'] for one in done['kept'])
    with pytest.raises(StoreError, match='No work record'):
        store.ticket(gone['id'])
    with store.tables(write=False) as tx:
        assert tx.get('ticket_settings', {'work_id': gone['id']}) is None
        assert tx.get('numbered', {'kind': 'work', 'item_id': gone['id']}) is None
        assert not tx.rows('work_steps', {'work_id': gone['id']}, limit=0).results
        assert not tx.rows('work_links', {'work_id': gone['id']}, limit=0).results
    if not dispatch_enabled:
        run('enable', 'dispatch', cwd=mapped)
    with dispatch.tables(write=False) as tx:
        assert [row['work_id'] for row in tx.rows('lines', limit=0).results] == [missing['id']]
    with dispatch.tables(write=False) as tx:
        assert tx.get('session_lines', {'session_id': 'conversation', 'name': 'message'})['text'] == 'Retained conversation'
    recovered = j(run, 'work', f'id={gone["map"]["item"]}', cwd=mapped)
    assert recovered['hash'] == sha and recovered['subject'] == 'Completed'
    assert 'Resolution: Delivered' in recovered['body'] and recovered['files'] == ['feature.txt']
    assert j(run, 'work', f'id={gone["id"]}', cwd=mapped)['hash'] == sha
    cited = j(run, 'item', gone['map']['item'], cwd=mapped)
    assert cited['hash'] == sha and cited['body'] == recovered['body']
    next_ticket = ticket('Next number')
    assert parse_reference(next_ticket['map']['item'])[1] > parse_reference(gone['map']['item'])[1]

    logs = []
    real_run = subprocess.run

    def counted(words, *args, **kwargs):
        if words[:2] == ['git', 'log'] and kwargs.get('cwd') == mapped:
            logs.append(words)
        return real_run(words, *args, **kwargs)

    monkeypatch.setattr(subprocess, 'run', counted)
    brief = node_brief(mapped, 'code.alarm.audible')
    assert f'{5 if other else 4} earlier runs' in brief
    assert len(logs) == 1
    after = store.where('code.alarm.audible')
    assert len(after.past_work) == len(before.past_work)
    assert len(logs) == 2, 'The next call reads Git again'
    commit(missing)
    retried = j(run, 'boards', 'op=line', f'name={board}', f'line={done["line"]}', cwd=mapped)
    assert retried['removed'] == [missing['id']], 'The same cutoff retries records after their commits arrive'
    j(run, 'boards', 'op=line', f'name={board}', f'line={done["was"] or ""}', cwd=mapped)
    assert store.ticket(side['id']).work.done


@pytest.mark.parametrize('detached', [False, True])
def test_archive_keeps_tickets_when_git_history_cannot_be_read(run, mapped, detached):
    if detached:
        for words in (('init', '-b', 'dev'), ('-c', 'user.name=Test', '-c', 'user.email=tests@example.test',
                                             'commit', '--allow-empty', '-m', 'Initial'),
                      ('checkout', '--detach')):
            subprocess.run(['git', *words], cwd=mapped, check=True, capture_output=True)
    ticket = j(run, 'work', 'op=add', 'node=code.alarm.audible', 'task=Keep completion evidence', cwd=mapped)
    store = Store('proj')
    store.finish_work(ticket['id'], 'Delivered')
    result = j(run, 'boards', 'op=line', cwd=mapped)
    assert result['removed'] == []
    assert len(result['kept']) == 1 and result['kept'][0]['id'] == ticket['id']
    assert result['kept'][0]['fault']
    assert store.ticket(ticket['id']).work.resolution == 'Delivered'


@pytest.mark.parametrize('same_second', [False, True])
def test_archive_preserves_join_history_and_keeps_reopened_tickets_without_current_commits(
        run, mapped, monkeypatch, same_second):
    from datetime import UTC, datetime, timedelta

    from metaform import home
    from metaform.modules.dispatch.merge import ticket_message

    def git(*words):
        return subprocess.run(['git', *words], cwd=mapped, capture_output=True, text=True, check=True).stdout.strip()

    git('init', '-b', 'dev')
    git('config', 'user.email', 'tests@example.test')
    git('config', 'user.name', 'Test')
    store = Store('proj')
    join = store.joins('code.timer.kitchen').results[0]
    earlier = (datetime.now(UTC) - timedelta(seconds=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
    later = (datetime.now(UTC) + timedelta(seconds=10)).strftime('%Y-%m-%dT%H:%M:%SZ')
    cutoff = (datetime.now(UTC) + timedelta(seconds=20)).strftime('%Y-%m-%dT%H:%M:%SZ')
    with monkeypatch.context() as clock:
        clock.setattr(home, 'now', lambda: earlier)
        attached = store.add_work(Node('join', join.id), None, task='Join work', title='Join work')
        legacy = store.add_work(Node('join', join.id), None, task='Legacy join', title='Legacy join')
        reopened = store.add_work(Node('element', 'code.timer.kitchen'), None, task='First attempt', title='Retry')
        for ticket in (attached, legacy, reopened):
            store.finish_work(ticket.id, 'First completion')
    for ticket in (attached, legacy, reopened):
        message = ticket_message(store, store.ticket(ticket.id).work)
        if ticket.id == legacy.id:
            message = '\n'.join(line for line in message.splitlines() if not line.startswith('Metaform-Target:'))
        git('commit', '--allow-empty', '-m', message)
    if same_second:
        later = datetime.fromisoformat(git('log', '-1', '--format=%cI')).strftime('%Y-%m-%dT%H:%M:%SZ')
    with monkeypatch.context() as clock:
        clock.setattr(home, 'now', lambda: later)
        store.move_work(reopened.id, 'todo')
        store.finish_work(reopened.id, 'Later completion without its commit')
    result = j(run, 'boards', 'op=line', f'line={cutoff}', cwd=mapped)
    assert result['removed'] == [attached.id]
    faults = {ticket['id']: ticket['fault'] for ticket in result['kept']}
    assert ('resolution' if same_second else 'predates') in faults[reopened.id]
    assert 'attachment' in faults[legacy.id]
    assert store.ticket(reopened.id).work.resolution == 'Later completion without its commit'
    assert len(store.where('code.timer.kitchen').past_work) == 1
    assert len(store.ticket(legacy.id).at.past_work) == 2


@pytest.mark.parametrize('changed', ['note', 'task', 'steps', 'links', 'settings'])
def test_archive_keeps_same_second_completion_until_current_ticket_state_is_committed(run, mapped, monkeypatch, changed):
    from datetime import UTC, datetime, timedelta

    from metaform import home
    from metaform.modules.dispatch.merge import ticket_message

    def git(*words):
        return subprocess.run(['git', *words], cwd=mapped, capture_output=True, text=True, check=True).stdout.strip()

    git('init', '-b', 'dev')
    git('config', 'user.email', 'tests@example.test')
    git('config', 'user.name', 'Test')
    store = Store('proj')
    ticket = j(run, 'work', 'op=add', 'node=code.timer.kitchen', 'task=Repeat verification', cwd=mapped)
    store.move_work(ticket['id'], 'todo')
    store.finish_work(ticket['id'], 'Verified')
    old = ticket_message(store, store.ticket(ticket['id']).work)
    git('commit', '--allow-empty', '-m', old)
    committed_at = datetime.fromisoformat(git('log', '-1', '--format=%cI')).astimezone(UTC)
    second = committed_at.strftime('%Y-%m-%dT%H:%M:%SZ')
    with monkeypatch.context() as clock:
        clock.setattr(home, 'now', lambda: second)
        store.move_work(ticket['id'], 'todo')
        if changed in ('note', 'task'):
            store.edit_work(ticket['id'], {changed: 'New verification evidence absent from completion commit'})
        elif changed == 'steps':
            store.step_work(ticket['id'], 'New verification evidence absent from completion commit')
        elif changed == 'links':
            store.edit_work(ticket['id'], {'links': [Node('element', 'code.alarm.audible')]})
        else:
            own = Store('proj', module='map')
            with own.tables() as tx:
                if tx.get('ticket_settings', {'work_id': ticket['id']}) is None:
                    tx.insert('ticket_settings', {'work_id': ticket['id'], 'hold': 1})
                else:
                    tx.update('ticket_settings', {'work_id': ticket['id']}, {'hold': 1})
                assert tx.get('ticket_settings', {'work_id': ticket['id']})['hold'] == 1
        store.finish_work(ticket['id'], 'Verified')
    cutoff = (committed_at + timedelta(seconds=20)).strftime('%Y-%m-%dT%H:%M:%SZ')
    held = j(run, 'boards', 'op=line', f'line={cutoff}', cwd=mapped)
    assert held['removed'] == []
    assert held['kept'][0]['id'] == ticket['id'] and 'state' in held['kept'][0]['fault']
    current = store.ticket(ticket['id']).work
    assert current.resolution == 'Verified' and current.done == second
    fresh = ticket_message(store, current)
    assert fresh != old
    git('commit', '--allow-empty', '-m', fresh)
    archived = j(run, 'boards', 'op=line', f'line={cutoff}', cwd=mapped)
    assert archived['removed'] == [ticket['id']]
    recovered = j(run, 'work', f'id={ticket["map"]["item"]}', cwd=mapped)
    assert 'Ticket state:\n' in recovered['body']


def test_archive_keeps_legacy_completion_without_state_but_still_resolves_its_citation(run, mapped):
    from metaform.modules.dispatch.merge import ticket_message

    def git(*words):
        return subprocess.run(['git', *words], cwd=mapped, capture_output=True, text=True, check=True).stdout.strip()

    git('init', '-b', 'dev')
    git('config', 'user.email', 'tests@example.test')
    git('config', 'user.name', 'Test')
    store = Store('proj')
    ticket = j(run, 'work', 'op=add', 'node=code.timer.kitchen', 'task=Legacy completion', cwd=mapped)
    store.finish_work(ticket['id'], 'Verified')
    message = ticket_message(store, store.ticket(ticket['id']).work)
    legacy = message.replace(f'\n\nTicket state:\n{store.work_snapshot(ticket["id"])}', '')
    git('commit', '--allow-empty', '-m', legacy)
    held = j(run, 'boards', 'op=line', cwd=mapped)
    assert held['removed'] == [] and 'state' in held['kept'][0]['fault']
    store.remove_work(ticket['id'])
    recovered = j(run, 'work', f'id={ticket["map"]["item"]}', cwd=mapped)
    assert recovered['hash'] == git('rev-parse', 'HEAD')
    assert recovered['body'].strip() == legacy.strip()


@pytest.mark.req('LAYER-025')
def test_knowledge_creates_no_correction_layer_and_offers_no_correct_or_peel(run, mapped):
    refused = run('map', 'knowledge', 'op=create', 'layer=fix-a', 'kind=correction', 'variable=Fixes.',
                  'mutable=false', 'hideable=false', *PROVENANCE, cwd=mapped, ok=False)
    assert refused.returncode != 0 and 'kind=layer' in refused.stdout + refused.stderr
    for op in ('correct', 'peel', 'refine'):
        gone = run('map', 'knowledge', f'op={op}', 'layer=intake', 'id=x', 'reason=r', cwd=mapped, ok=False)
        assert gone.returncode != 0 and 'not a knowledge operation' in gone.stdout + gone.stderr
    page = run('help', 'map', 'knowledge', cwd=mapped).stdout
    # Refining the metaform under knowledge read as touching a knowledge layer, which it does not.
    assert 'op=refine' not in page and 'correction' not in page and 'peel' not in page
    assert 'refine' not in run('help', 'map', 'knowledge', cwd=mapped).stdout.split('Switches')[1].split('\n')[1]
    assert 'refine' in run('help', 'map', 'refine', cwd=mapped).stdout
    assert 'stack' not in run('help', 'map', cwd=mapped).stdout.split()


@pytest.mark.req('LAYER-028')
def test_a_layer_named_a_project_root_is_refused_naming_the_rule(run, mapped):
    """A layer's name is a namespace root; one named code would collide with the map's code root."""
    refused = k(run, mapped, 'op=create', 'layer=code', 'variable=What is it?', 'mutable=true', 'hideable=true',
                *PROVENANCE, ok=False)
    assert refused.returncode != 0 and 'project root' in refused.stdout + refused.stderr
    assert 'LAYER-028' in refused.stdout + refused.stderr
    assert 'code' not in [layer['name'] for layer in j(run, 'layers', cwd=mapped)['results']]
    k(run, mapped, 'op=create', 'layer=port', 'variable=What is it?', 'mutable=true', 'hideable=true', *PROVENANCE)
    with pytest.raises(StoreError, match='LAYER-028'):
        Store('proj').rename_layer('port', 'data', 'test')


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
        ('node', ['work', 'op=add', 'condition=unbuilt']),
        ('id', ['work', 'op=edit', 'condition=unbuilt']),
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
    assert said(added) == []  # a plain task: no condition, no notice, MAP-046
    listed = j(run, 'work', 'node=element:code.alarm.audible', cwd=mapped)['results']
    assert [(row['id'], row['condition']) for row in listed] == [(added['id'], '')]


@pytest.mark.req('MAP-049')
@pytest.mark.req('MAP-053')
def test_the_work_list_holds_open_rows_without_their_logs_and_the_ticket_read_holds_everything(run, mapped):
    """A bare `map work` was 758,000 characters on a project of 220 tickets, mostly the done ones' logs."""
    store = Store('proj')
    alarm = Node('element', 'code.alarm.audible')
    waiting = store.add_work(alarm, 'unbuilt', task='build the driver').id
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


@pytest.mark.req('MAP-046')
@pytest.mark.parametrize('stage', ['unbuilt', 'under-construction'])
def test_public_planned_stage_is_visible_without_becoming_executable_work(run, mapped, stage):
    from metaform import settings

    added = j(run, 'work', 'op=add', 'node=code.alarm.audible', f'condition={stage}',
              'title=Planned audible notification', 'note=Its purpose is established; the mechanism is undecided.',
              cwd=mapped)
    assert added['condition'] == stage and added['is_work'] is False
    assert not added['task'] and added['held'] is False
    assert j(run, 'element', 'code.alarm.audible', cwd=mapped)['open_work'] == [stage]
    assert j(run, 'work', 'op=distribute', 'agents=1', cwd=mapped)['results'] == []
    run('enable', 'dispatch', cwd=mapped)
    settings.put('dispatch_autostart', True, mapped)
    started = json.loads(run('dispatch', 'autostart', '--json', cwd=mapped).stdout)
    assert started['started'] == [] and not started.get('continuations')
    record = Store('proj').ticket(added['id']).work
    assert record.task is None and record.taken is None and record.held is False


@pytest.mark.req('BASE-038')
@pytest.mark.req('MAP-046')
@pytest.mark.req('STORE-042')
def test_work_records_are_added_edited_listed_and_done_through_one_verb_and_never_change_the_map(run, mapped):
    store = Store('proj')
    join = store.joins('code.timer.kitchen').results[0]
    before = json.loads(run('query', 'graph', 'limit=0', '--json', cwd=mapped).stdout)
    added = j(run, 'work', 'op=add', 'node=code.alarm.audible', 'condition=unbuilt', 'note=in the spec, not built',
              'task=build the piezo driver', 'held=true', 'hold_reason=Await hardware inspection.', cwd=mapped)
    assert (added['node_kind'], added['address'], added['condition'], added['held'], added['reviewed'], added['done']) == (
        'element', 'code.alarm.audible', 'unbuilt', True, False, None)
    on_join = j(run, 'work', 'op=add', f'node=join:{join.id}', 'condition=broken', 'task=fix the tone', cwd=mapped)
    assert (on_join['node_kind'], on_join['receiver_address'], on_join['provider_address']) == (
        'join', 'code.timer.kitchen', 'code.alarm.audible')
    listed = j(run, 'work', cwd=mapped)['results']
    assert [(row['condition'], row['held']) for row in listed] == [('unbuilt', True), ('broken', False)]
    assert [row['id'] for row in j(run, 'work', 'open=true', 'condition=unbuilt', cwd=mapped)['results']] == [added['id']]
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
    refused = run('map', 'work', 'op=add', 'title=A ticket', 'condition=unbuilt', '--json', cwd=mapped, ok=False)
    assert refused.returncode == 2 and 'node' in refused.stderr
    # Empty normal states and notes are neither executable work nor a visible non-work stage.
    for given in ('condition=ok', 'condition=built', 'note=just a note'):
        empty = run('map', 'work', 'op=add', 'title=Works', 'node=element:code.alarm.audible', given, '--json',
                    cwd=mapped, ok=False)
        assert empty.returncode != 0 and 'the task is what an agent works from' in empty.stderr, given
    # The store refuses an open record nothing shows, whoever writes it, MAP-046, ticket 97085c0e: an ok, a built, a
    # note alone; a stage with no task is the part's state, drawn on its node, and is kept.
    stage = store.add_work(Node('element', store.element('code.alarm.audible').id), 'unbuilt')
    assert (stage.condition, stage.to_dict()['is_work']) == ('unbuilt', False)
    emptied = run('map', 'work', 'op=edit', f'id={on_join["id"]}', 'condition=none', 'task=', cwd=mapped, ok=False)
    assert emptied.returncode != 0 and 'is not work' in emptied.stderr
    assert j(run, 'work', f'id={on_join["id"]}', cwd=mapped)['task'] == 'fix the tone'  # the refused edit wrote nothing
    with pytest.raises(StoreError, match='is not work'):
        store.add_work(Node('element', store.element('code.alarm.audible').id), None, note='x')
    unknown = run('map', 'work', 'op=add', 'title=A ticket', 'node=element:code.alarm.audible', 'condition=broken', 'later=yes', '--json',
                  cwd=mapped, ok=False)
    assert unknown.returncode == 2 and "does not take 'later=yes'" in unknown.stderr  # the chassis grammar, BASE-043
    assert j(run, 'work', 'op=done', f'id={on_join["id"]}', 'task=ignored here', cwd=mapped)['notices'][0]['where'] == 'task'
    assert run('help', 'map', 'work', cwd=mapped).stdout.count('unbuilt') >= 1


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
    """The document holds what a reader finds its way by: each join's ef where it showed the relation,
    its purpose and the elements it holds, and the paths the sources layer holds."""
    text = run('map', 'markdown', cwd=described).stdout
    for address in ('stakeholder.cook.home', 'code.timer.kitchen', 'code.alarm.audible', 'code.display.digit'):
        assert f'`{address}`' in text
    for name in ('home cook', 'kitchen timer', 'audible alarm', 'digit display'):
        assert name in text
    assert 'DE' in text and 'CQU' in text
    assert 'Paths: src/display.py' in text and 'DISP-001' not in text
    assert 'kitchen timer receives from digit display' in text
    # No subject rule; ef is shown as written, where the relation was.
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


@pytest.fixture(params=['timer-first', 'alarm-first'])
def recorded(run, tmp_path, monkeypatch, request):
    """An intake in the metaform's shape: a CQU receiving from the DE, the DE receiving from an alarm and from a
    display with its driver, the cook receiving from the alarm too; refs in the sources layer; a finding on the alarm
    and one on the display's join."""
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
    store.add_work(Node('join', shown.id), 'unbuilt', note='no blank between digits')
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
    cook = document.find('element')
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
        ('unbuilt', 'no blank between digits')]
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
def test_an_agent_that_takes_a_task_leaves_the_parts_state_and_the_record_no_longer_waits(run, mapped):
    """Taking a task says an agent holds the work; the part's state is the intake's and the person's,
    MAP-046, so it stays as it was. Done, the part is as any other."""
    store = Store('proj')
    build = store.add_work(Node('element', 'code.alarm.audible'), 'unbuilt', task='build it', held=True)
    fix = store.add_work(Node('element', 'code.timer.kitchen'), 'broken', task='fix it', held=True)
    taken = json.loads(run('map', 'work', 'op=take', f'id={build.id}', '--json', cwd=mapped).stdout)
    assert (taken['condition'], taken['held'], bool(taken['taken'])) == ('unbuilt', False, True)
    assert json.loads(run('map', 'work', 'op=take', f'id={fix.id}', '--json', cwd=mapped).stdout)[
        'condition'] == 'broken'
    assert j(run, 'element', 'code.alarm.audible', cwd=mapped)['open_work'] == ['unbuilt']
    listed = json.loads(run('map', 'work', 'condition=unbuilt', '--json', cwd=mapped).stdout)['results']
    assert [record['id'] for record in listed] == [build.id]
    again = run('map', 'work', 'op=take', f'id={build.id}', '--json', cwd=mapped, ok=False)
    assert again.returncode != 0 and 'already' in again.stderr + again.stdout
    assert f'metaform map work op=plan id={build.id}' in again.stderr + again.stdout  # the way to resume
    run('map', 'work', 'op=done', 'why=The work it asked for is done.', f'id={build.id}', 'resolution=built', cwd=mapped)
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
    """A question the person writes comes with the answers to pick from. A note asks for nothing and waits to be
    read. Neither is the condition of a part, so neither is a work record."""
    asked = j(run, 'ask', 'code.alarm.audible', 'Is the quiet tone still wanted?',
              'suggestions=["Yes, keep it", "No, make it louder"]', *FORM, cwd=mapped)
    form = 'Is the quiet tone still wanted?'
    assert (asked['kind'], asked['address'], asked['text'], asked['suggestions'], asked['by'], asked['closed']) == (
        'question', 'code.alarm.audible', form, ['Yes, keep it', 'No, make it louder'], 'builder', None)
    assert said(asked) == [] and 'said' not in asked
    assert [one['text'] for one in j(run, 'messages', 'limit=0', cwd=mapped)['results']] == [form]
    told = Store('proj').tell(Node('element', 'code.alarm.audible'), 'The driver is written.')
    assert (told.kind, told.text, told.closed) == ('message', 'The driver is written.', None)
    waiting = j(run, 'messages', 'open=true', cwd=mapped)['results']
    assert [one['id'] for one in waiting] == [asked['id'], told.id]
    assert [one['kind'] for one in j(run, 'messages', 'kind=question', cwd=mapped)['results']] == ['question']
    assert j(run, 'element', 'code.alarm.audible', cwd=mapped)['open_work'] == ['question', 'message']
    assert j(run, 'work', 'node=element:code.alarm.audible', cwd=mapped)['results'] == []  # no work record was made
    replied = j(run, 'reply', asked['id'], 'answer=No, make it louder', cwd=mapped)
    assert (replied['answer'], bool(replied['closed'])) == ('No, make it louder', True)
    again = j(run, 'reply', asked['id'], 'answer=Yes, keep it', cwd=mapped)  # the first answer is kept
    assert again['answer'] == 'No, make it louder' and [where for where, _ in said(again)] == ['id']
    at_node = j(run, 'messages', 'node=element:code.alarm.audible', 'open=false', cwd=mapped)['results']
    assert [(one['text'], one['answer']) for one in at_node] == [(form, 'No, make it louder')]
    assert '1 message' in j(run, 'where', 'code.alarm.audible', cwd=mapped)['around']  # counted, MCP-039
    where = j(run, 'where', 'code.alarm.audible', 'contents=true', cwd=mapped)
    assert [(one['kind'], one['text']) for one in where['messages']] == [('message', 'The driver is written.')]
    old = run('map', 'work', 'op=add', 'title=A ticket', 'node=code.alarm.audible', 'condition=question', 'note=Old form.',
              cwd=mapped, ok=False)  # a question is no condition of a part: the closed list refuses it
    assert old.returncode != 0 and "'question' is not a condition" in old.stderr

    # a bare question is recorded with a notice that it has no suggestions, never refused, MAP-050
    bare = j(run, 'ask', 'code.alarm.audible', 'Which one?', *FORM, cwd=mapped)
    assert bare['text'] == 'Which one?' and {where for where, _ in said(bare)} == {'suggestions'}
    assert 'Which one?' in [one['text'] for one in j(run, 'messages', 'open=true', cwd=mapped)['results']]

@pytest.mark.req('MAP-050')
def test_where_gives_each_open_message_its_id_so_it_is_answered_from_that_read(run, mapped):
    """perspective-agent, 2026-10-02: where listed the open questions with no message_id, and replying took a second
    call to find it. The where read gives each one its id, and the id it gives answers the question."""
    asked = j(run, 'ask', 'code.alarm.audible', 'Is the quiet tone still wanted?', YES_NO, *FORM, cwd=mapped)
    told = Store('proj').tell(Node('element', 'code.alarm.audible'), 'The driver is written.')
    where = j(run, 'where', 'code.alarm.audible', 'contents=true', cwd=mapped)
    assert [one.get('id') for one in where['messages']] == [asked['id'], told.id]
    replied = j(run, 'reply', where['messages'][0]['id'], 'answer=Yes', cwd=mapped)
    assert (replied['text'], replied['answer']) == (asked['text'], 'Yes')


@pytest.mark.req('MAP-050')
def test_a_question_answered_by_mistake_is_reopened_and_waits_again_with_its_suggestions(run, mapped):
    """A question answered by mistake can be reopened. The answer is cleared and the
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
    told = Store('proj').tell(Node('element', 'code.alarm.audible'), 'The driver is written.')
    j(run, 'reply', told.id, cwd=mapped)
    refused = run('map', 'reopen', told.id, cwd=mapped, ok=False)  # only a question is reopened
    assert refused.returncode != 0 and 'Only a question is reopened' in refused.stderr + refused.stdout
    assert j(run, 'messages', 'kind=message', 'open=false', cwd=mapped)['results'][0]['id'] == told.id


@pytest.fixture
def stored(run, tmp_path, home):
    """`proj` held in the project store: the alarm and the timer there, none in the old store's map. Its
    single-writer service is stopped when the test ends."""
    from metaform.project import owner, service
    from metaform.project import run as command
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    for address, name in (('code.alarm.audible', 'audible alarm'), ('code.timer.kitchen', 'kitchen timer')):
        assert command({'add': {f'proj.{address}': {'technical_name': name, 'name': name,
                                                     'role': 'Supporting Element'}}}) == {'status': 'ok'}
    yield folder
    service.stop(home)
    owner.close_all()


@pytest.mark.req('MAP-050')
def test_questions_and_messages_of_a_project_in_the_project_store_are_its_questions_overlay_records(run, stored):
    """Decision t-legacy-keep: for a project held in the project store, ask, reply, reopen and messages read and write
    the records of its questions overlay at the element asked about, where the page reads them; the old store gets
    none. What has no place there, a join's purpose, is refused by name, and a change names the revision it found."""
    from metaform.module import Stop
    from metaform.modules.map import project_messages
    from metaform.project import overlay_records
    from metaform.project import run as command
    asked = j(run, 'ask', 'code.alarm.audible', 'Is the quiet tone still wanted?',
              'suggestions=["Yes, keep it", "No, make it louder"]', *FORM, cwd=stored)
    assert (asked['kind'], asked['address'], asked['suggestions'], asked['by'], asked['title'], asked['closed']) == (
        'question', 'code.alarm.audible', ['Yes, keep it', 'No, make it louder'], 'builder', 'A question', None)
    [record] = overlay_records('proj', 'questions')
    assert (record['element'], record['id'], record['revision']) == ('proj.code.alarm.audible', asked['id'], 1)
    assert not Store('proj').messages(limit=0).results  # the old store holds none
    told = project_messages.tell('proj', 'code.timer.kitchen', 'The driver is written.', by='builder')
    assert [one['id'] for one in j(run, 'messages', 'open=true', cwd=stored)['results']] == [asked['id'], told['id']]
    assert [one['id'] for one in j(run, 'messages', 'node=element:code.timer.kitchen', cwd=stored)['results']] == [
        told['id']]
    assert j(run, 'messages', 'node=join:1', cwd=stored)['results'] == []  # a join holds none there
    first = j(run, 'messages', 'limit=1', cwd=stored)
    assert [one['id'] for one in first['results']] == [asked['id']] and first['next'] == asked['id']
    assert [one['id'] for one in j(run, 'messages', 'after=' + first['next'], cwd=stored)['results']] == [told['id']]

    replied = j(run, 'reply', asked['id'], 'answer=No, make it louder', cwd=stored)
    assert (replied['answer'], bool(replied['closed']), replied['revision']) == ('No, make it louder', True, 2)
    again = j(run, 'reply', asked['id'], 'answer=Yes, keep it', cwd=stored)  # the first answer is kept
    assert again['answer'] == 'No, make it louder' and [where for where, _ in said(again)] == ['id']
    reopened = j(run, 'reopen', asked['id'], cwd=stored)
    assert (reopened['closed'], reopened['answer'], reopened['suggestions']) == (
        None, None, ['Yes, keep it', 'No, make it louder'])
    assert bool(j(run, 'reply', told['id'], cwd=stored)['closed'])  # a message is read
    refused = run('map', 'reopen', told['id'], cwd=stored, ok=False)
    assert refused.returncode != 0 and 'Only a question is reopened' in refused.stderr + refused.stdout

    moved = j(run, 'messages', 'op=move', f'id={asked["id"]}', 'node=code.timer.kitchen', cwd=stored)
    assert (moved['id'], moved['address'], moved['suggestions']) == (
        asked['id'], 'code.timer.kitchen', asked['suggestions'])
    assert [one['element'] for one in overlay_records('proj', 'questions')] == ['proj.code.timer.kitchen'] * 2

    for args, named in ((('ask', 'code.alarm.audible', 'Which?', YES_NO, 'provider=code.timer.kitchen', *FORM),
                         'provider names a join'),
                        (('ask', 'code.alarm.audible', 'Which?', YES_NO, 'work=t-none', *FORM), "No ticket 't-none'")):
        refused = run('map', *args, cwd=stored, ok=False)
        assert refused.returncode != 0 and named in refused.stderr + refused.stdout, args
    # a change names the record and revision it found: one changed meanwhile is refused, never overwritten
    found = next(one for one in overlay_records('proj', 'questions') if one['id'] == asked['id'])
    assert command({'update': {str(found['element']): {'questions': [
        {'position': found['position'], 'record': found['record'], 'title': 'Retitled'}]}}}) == {'status': 'ok'}
    with pytest.raises(Stop):
        project_messages._changed('proj', found, {'answer': 'Lands nowhere'})
    assert 'answer' not in next(one for one in overlay_records('proj', 'questions') if one['id'] == asked['id'])


@pytest.mark.req('STORE-025')
@pytest.mark.req('LAYER-005')
def test_where_shows_the_properties_that_apply_at_the_address_and_those_visible_there(run, mapped):
    """An agent is told to read a part with where before it changes it. A property linked toward the trunk applies at
    the part, so where shows it; an agent that read only where would otherwise never learn of it."""
    k(run, mapped, 'op=create', 'layer=language', 'variable=Which language is each part written in?', 'mutable=true',
      'hideable=true', *PROVENANCE)
    k(run, mapped, 'op=add-property', 'layer=language', 'element=type:code', 'value="C"')
    k(run, mapped, 'op=add-property', 'layer=language', 'element=code.timer.kitchen', 'value="assembly"')
    k(run, mapped, 'op=finish', 'layer=language')
    kitchen = j(run, 'where', 'code.timer.kitchen', 'contents=true', cwd=mapped)['properties']
    assert [(one['value'], one['address']) for one in kitchen['applying']] == [('C', 'code'), ('assembly', 'code.timer.kitchen')]
    assert 'visible' not in kitchen                                  # nothing is linked toward the leaves from it
    alarm = j(run, 'where', 'code.alarm.audible', 'contents=true', cwd=mapped)['properties']
    assert [(one['value'], one['address']) for one in alarm['applying']] == [('C', 'code')]
    trunk = j(run, 'where', 'code', 'contents=true', cwd=mapped)['properties']
    assert [(one['value'], one['address']) for one in trunk['visible']] == [('assembly', 'code.timer.kitchen')]
    in_context = j(run, 'context', 'code.timer.kitchen', cwd=mapped)['applying']  # the same, as context reads them
    assert [(one['value'], one['address'], one['layer']) for one in in_context] \
        == [(one['value'], one['address'], one['layer']) for one in kitchen['applying']]
    assert 'properties' not in j(run, 'where', 'stakeholder.cook.home', 'contents=true', cwd=mapped)  # none here
    assert '2 properties' in j(run, 'where', 'code.timer.kitchen', cwd=mapped)['around']  # counted, MCP-039


@pytest.mark.req('MAP-053')
@pytest.mark.req('MAP-049')
def test_an_agent_says_how_many_steps_it_plans_and_reports_each_as_it_finishes_it(run, mapped):
    """The map shows how far a part is by the share of its steps that are done, and a share needs the whole. The count
    is a plan, and the agent changes it when the plan changes."""
    store = Store('proj')
    task = store.add_work(Node('element', 'code.alarm.audible'), 'unbuilt', task='build it')
    assert (task.steps, task.steps_done, task.said) == (None, 0, ())
    taken = j(run, 'work', 'op=take', f'id={task.id}', 'steps=3', cwd=mapped)
    assert (taken['condition'], taken['steps'], taken['steps_done'], taken['said']) == ('unbuilt', 3, 0, [])
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
    plain = store.add_work(Node('element', 'code.timer.kitchen'), 'unbuilt', task='no count')
    took = j(run, 'work', 'op=take', f'id={plain.id}', cwd=mapped)
    assert (took['steps'], took['steps_done'], took['said']) == (None, 0, [])  # a task with no count has no steps
    untaken = store.add_work(Node('element', 'code.timer.kitchen'), 'unbuilt', task='not taken')
    early = j(run, 'work', 'op=step', f'id={untaken.id}', 'said=Done before it was taken.', cwd=mapped)
    assert early['steps_done'] == 1 and [where for where, _ in said(early)] == ['condition']


@pytest.mark.req('MAP-048')
def test_a_ticket_filed_with_no_board_lands_on_the_active_board(run, mapped):
    """The active board, the map setting `board`, 2026-10-21: a ticket filed with no board lands on it, board= empty
    names the first board on purpose, the boards list marks it, and removing it makes the first board active again."""
    run('map', 'boards', 'op=add', 'name=next', cwd=mapped)
    run('set', '--board', 'next', cwd=mapped)
    landed = json.loads(run('map', 'work', 'op=add', 'title=On the active board', 'node=code.alarm.audible',
                            'task=t', '--json', cwd=mapped).stdout)
    json.loads(run('map', 'work', 'op=add', 'title=On the first board', 'node=code.alarm.audible', 'task=t',
                   'board=', '--json', cwd=mapped).stdout)
    listed = json.loads(run('map', 'work', 'board=next', 'limit=0', '--json', cwd=mapped).stdout)['results']
    assert [one['id'] for one in listed] == [landed['id']]
    boards = json.loads(run('map', 'boards', '--json', cwd=mapped).stdout)['boards']
    assert [one['name'] for one in boards if one['active']] == ['next']
    run('map', 'work', 'op=edit', f'id={landed["id"]}', 'board=', cwd=mapped)
    run('map', 'boards', 'op=remove', 'name=next', cwd=mapped)
    boards = json.loads(run('map', 'boards', '--json', cwd=mapped).stdout)['boards']
    assert [one['name'] for one in boards if one['active']] == ['']


def test_wipe_backs_up_every_board_column_and_restores_ids_numbers_and_owned_rows(run, mapped, monkeypatch):
    """A person can empty a board without losing its map, then insert its tickets beside work made since the wipe.
    Each wipe keeps its own backup. Forty-four removed tickets produce one map.changed carrying all their ids."""
    from metaform import changes, events
    from metaform import home as metaform_home

    run('enable', 'dispatch', cwd=mapped)
    store = Store('proj', module='map')
    dispatch = Store('proj', module='dispatch')
    node = Node('element', 'code.alarm.audible')
    j(run, 'boards', 'op=add', 'name=past effort', cwd=mapped)
    records = []
    for column in ('backlog', 'todo', 'doing', 'done'):
        for number in range(11):
            record = store.add_work(node, 'broken', kind='flawed', task=f'{column} task {number}',
                                    title=f'{column} {number}',
                                    links=[Node('element', 'code.timer.kitchen')])
            with store.tables() as tx:
                tx.insert('ticket_settings', {'work_id': record.id, 'board': 'past effort'})
            store.move_work(record.id, column, by='codex', hold_reason='Keep this board for later review.')
            records.append(record)
    first = records[0].id
    j(run, 'work', 'op=edit', f'id={first}', 'agent=codex', 'hold=true', 'hold_reason=Await board review.', 'glyph=owl',
      'eligible=["codex"]', f'after_work=["{records[-1].id}"]', cwd=mapped)
    store.plan_work(first, 3)
    store.step_work(first, 'Keep this progress.')
    asked = store.ask(node, 'Keep this question?', work=first, title='A linked question', why='It follows the ticket.')
    with dispatch.tables() as tx:
        tx.insert('lines', {'session_id': 'monitor:progress', 'name': first, 'work_id': first,
                            'kind': 'progress', 'text': '{"progress":1}', 'seq': 1})
        tx.insert('claim_work', {'work_id': first, 'claim_id': 'past-claim'})

    tables = ('work', 'work_steps', 'work_links', 'ticket_settings', 'glyphs', 'eligible', 'after', 'question_work')
    with store.tables(write=False) as tx:
        saved = {table: [dict(row) for row in tx.rows(table, limit=0).results] for table in tables}
        board_row = dict(tx.get('boards', {'name': 'past effort'}))
        numbered = [dict(row) for row in tx.rows('numbered', {'kind': 'work'}, limit=0).results]
    citations = {row['item_id']: f'{row["address"]}#{row["number"]:x}' for row in numbered}
    ids = {record.id for record in records}
    assert len(ids) == 44
    addresses = ('stakeholder.cook.home', 'code.timer.kitchen', 'code.alarm.audible')
    before_map = [store.element(address).id for address in addresses]
    changes.take()
    published = []
    monkeypatch.setattr(events, 'publish', lambda topic, payload, source: published.append((topic, payload)) or [])
    wiped = j(run, 'boards', 'op=wipe', 'name=past effort', cwd=mapped)
    stamp = wiped['backup']
    assert wiped['tickets'] == 44 and wiped['columns'] == dict.fromkeys(('backlog', 'todo', 'doing', 'done'), 11)
    assert wiped['sessions_stopped'] == []
    changed = [payload for topic, payload in published if topic == 'map.changed']
    assert len(changed) == 1 and set(changed[0]['work_ids']) == ids
    backup = metaform_home.home() / 'backups' / 'wipe' / 'proj' / stamp / 'rows.json'
    assert backup.is_file()
    raw = json.loads(backup.read_text(encoding='utf-8'))
    assert raw['board'] == board_row and set(raw['work_ids']) == ids
    backed_up = {(part['module'], part['table']['name']): part['rows'] for part in raw['rows']}
    assert {row['work_id'] for row in backed_up['map', 'work']} == ids
    assert len(backed_up['map', 'work_links']) == 44
    assert backed_up['map', 'question_work'] == [{'message_id': asked.id, 'work_id': first}]
    assert backed_up['dispatch', 'claim_work'] == [{'work_id': first, 'claim_id': 'past-claim'}]
    assert backed_up['dispatch', 'lines'][0]['text'] == '{"progress":1}'
    listed = j(run, 'boards', cwd=mapped)
    assert [board['name'] for board in listed['boards']] == ['']
    assert any(wipe['stamp'] == stamp and wipe['board'] == 'past effort' and wipe['tickets'] == 44
               for wipe in listed['wipes'])
    assert not store.work(open=None, limit=0).results
    assert [store.element(address).id for address in addresses] == before_map
    for citation in citations.values():
        assert run('map', 'item', citation, cwd=mapped, ok=False).returncode != 0
    with store.tables(write=False) as tx:
        assert all(not tx.rows(table, limit=0).results for table in tables)
    with dispatch.tables(write=False) as tx:
        assert not tx.rows('claim_work', limit=0).results and not tx.rows('lines', limit=0).results
    listed_backups = run('list', 'backups', 'proj', cwd=mapped).stdout
    assert stamp in listed_backups and 'past effort' in listed_backups and '44' in listed_backups

    # An existing id is preserved, even when its current contents differ from its backed-up row.
    duplicate = dict(saved['work'][-1])
    duplicate['task'] = 'Already present. Keep this version.'
    with store.tables() as tx:
        tx.insert('work', duplicate)
    new = j(run, 'work', 'op=add', 'node=code.alarm.audible', 'task=Work since the wipe.', 'board=', cwd=mapped)
    assert int(new['map']['item'].rpartition('#')[2], 16) > max(row['number'] for row in numbered)
    published.clear()
    restored = j(run, 'boards', 'op=restore', 'name=past effort', f'backup={stamp}', cwd=mapped)
    assert set(restored['restored']) == ids - {duplicate['work_id']} and restored['skipped'] == [duplicate['work_id']]
    changed = [payload for topic, payload in published if topic == 'map.changed']
    assert len(changed) == 1 and set(changed[0]['work_ids']) == ids - {duplicate['work_id']}
    assert store.ticket(new['id']).work.task == 'Work since the wipe.'
    assert store.ticket(duplicate['work_id']).work.task == duplicate['task']
    for work_id, citation in citations.items():
        if work_id != duplicate['work_id']:
            assert j(run, 'item', citation, cwd=mapped)['id'] == work_id
    with store.tables(write=False) as tx:
        assert tx.get('boards', {'name': 'past effort'}) == board_row
        for table in tables:
            expected = [row for row in saved[table] if row.get('work_id') != duplicate['work_id']]
            actual = [dict(row) for row in tx.rows(table, limit=0).results
                      if row.get('work_id') in ids - {duplicate['work_id']}]
            assert actual == expected, table
    with dispatch.tables(write=False) as tx:
        assert tx.get('claim_work', {'work_id': first}) == {'work_id': first, 'claim_id': 'past-claim'}
        assert tx.get('lines', {'session_id': 'monitor:progress', 'name': first})['text'] == '{"progress":1}'

    # The first board remains available after its own wipe, retaining another permanent backup.
    published.clear()
    first_wipe = j(run, 'boards', 'op=wipe', 'name=', cwd=mapped)
    assert first_wipe['tickets'] == 2
    assert next(board for board in j(run, 'boards', cwd=mapped)['boards'] if board['first'])['tickets'] == 0
    assert backup.is_file() and first_wipe['backup'] != stamp


def test_a_ticket_is_moved_across_the_board_and_links_other_nodes_for_reference(run, mapped):
    """Assign and track work via Metaform like a kanban; the ticket is on the functionality it is
    assigned to, and links other nodes for reference. It keeps its kind in every column."""
    made = json.loads(run('map', 'work', 'op=add', 'title=A ticket', 'node=code.alarm.audible', 'condition=broken', 'task=quieter tone',
                          'links=["element:code.timer.kitchen"]', 'held=true', 'hold_reason=Await tone review.', '--json', cwd=mapped).stdout)
    assert ([link['address'] for link in made['links']], made['held']) == (['code.timer.kitchen'], True)
    doing = json.loads(run('map', 'work', 'op=move', f'id={made["id"]}', 'column=doing', 'by=codex', '--json',
                           cwd=mapped).stdout)
    assert (doing['condition'], doing['taken_by'], doing['held'], bool(doing['taken'])) == ('broken', 'codex', False, True)
    done = json.loads(run('map', 'work', 'op=move', f'id={made["id"]}', 'column=done', '--json', cwd=mapped).stdout)
    assert done['done'] and done['condition'] == 'broken'


@pytest.mark.req('BASE-053')
def test_a_ticket_taken_back_to_its_place_names_itself_alone_and_a_move_names_only_the_places_it_changes(mapped):
    """UX recheck 2026-10-17 at b410f6a5: a runner's take, a move back to To do then a take, named every open ticket,
    since the move wrote every place in the column. The take keeps every place; a move says only those it changes."""
    from metaform import changes
    store = Store('proj')
    ids = [store.add_work(Node('element', 'code.timer.kitchen'), 'unbuilt', task=f'task {n}').id for n in range(6)]
    taken = ids[2]
    for unplaced in (True, False):  # tickets as they are made, placed last in turn, then in an order the board gave
        if not unplaced:
            for place, work_id in enumerate(ids):
                store.move_work(work_id, 'todo', place)
        store.take_work(taken, by='dispatch starting r')
        changes.take()
        with store.atomic():  # the runner's take of its reservation
            store.move_work(taken, 'todo', kept=True)
            store.take_work(taken, None, 'claude')
        base = next(iter(changes.take()['proj']))
        assert changes.concerns('proj', base)['work_ids'] == [taken]
        if unplaced:
            assert sorted(record.position for record in store.work(Node('element', 'code.timer.kitchen'),
                                                                    limit=0).results) == [0, 1, 2, 3, 4, 5]
            changes.take()
            store.move_work(taken, 'todo')  # dropped at the end of a new To do: its place is the only one written
            assert changes.concerns('proj', next(iter(changes.take()['proj'])))['work_ids'] == [taken]
    store.move_work(taken, 'todo', 2)
    store.take_work(taken, by='dispatch starting r')
    changes.take()
    store.move_work(taken, 'todo', 2)  # given back to its own place, as a start that fails gives it back
    assert changes.concerns('proj', next(iter(changes.take()['proj'])))['work_ids'] == [taken]
    store.take_work(taken, by='dispatch starting r')
    changes.take()
    # to the top: the column holds places 0, 1, 3, 4 and 5 now, so the two above the taken one move down a place,
    # and the two below it, already at 3 and 4, keep theirs
    store.move_work(ids[5], 'todo', 0)
    assert changes.take()['proj'] and changes.concerns('proj', base)['work_ids'] == sorted([ids[5], *ids[:2]])
    todo = [record for record in store.work(Node('element', 'code.timer.kitchen'), limit=0).results
            if record.id != taken]
    assert [record.id for record in sorted(todo, key=lambda record: record.position)] == [ids[5], *ids[:2],
                                                                                          *ids[3:5]]


def glyph_of(record):
    """The glyph the map module keeps on a work record, shown under its own id, BASE-035; None when it keeps none."""
    return (record.get('map') or {}).get('glyph')


@pytest.mark.req('VIEW-040')
def test_distributing_over_n_agents_gives_the_first_n_glyphs_in_turn_to_the_tickets_not_taken_or_done(run, mapped):
    """Tickets with the same glyph are one agent's, done one at a time, and a button distributes work over N agents
    by assigning N glyphs evenly, over the tickets that start by themselves, in To do's board order; a ticket taken or
    done keeps its glyph, and an exclude record is not a ticket. A held Backlog ticket and one waiting on an open ticket
    are dealt none: a glyph agent took every held ticket after its own (UX review round 2, held-and-signals F3)."""
    from metaform.modules.map import AGENT_GLYPHS
    store = Store('proj')
    kitchen, alarm = Node('element', 'code.timer.kitchen'), Node('element', 'code.alarm.audible')
    todo = [store.add_work(kitchen, 'unbuilt', task=f'todo {number}') for number in range(5)]
    backlog = [store.add_work(alarm, None, task=f'backlog {number}', held=True) for number in range(2)]
    store.move_work(todo[4].id, 'todo', position=0)                   # the board's order, not the rows'
    store.move_work(backlog[1].id, 'backlog', position=0)
    taken = store.add_work(alarm, 'broken', task='being worked')
    j(run, 'work', 'op=edit', f'id={taken.id}', 'glyph=owl', cwd=mapped)
    store.take_work(taken.id, by='claude')
    done = store.add_work(alarm, None, task='finished')
    j(run, 'work', 'op=edit', f'id={done.id}', 'glyph=snail', cwd=mapped)  # outside the first three dealt
    store.finish_work(done.id, 'fixed')
    outside = store.add_work(kitchen, 'unbuilt', note='vendored')  # a stage, no task: never dealt, never started
    after = store.add_work(kitchen, 'unbuilt', task='after the first')
    j(run, 'work', 'op=edit', f'id={after.id}', f'after_work=["{todo[0].id}"]', cwd=mapped)
    given = j(run, 'work', 'op=distribute', 'agents=3', cwd=mapped)['results']
    order = [todo[4], todo[0], todo[1], todo[2], todo[3]]
    assert [record['id'] for record in given] == [record.id for record in order]
    first = AGENT_GLYPHS[:3]
    assert 'owl' not in first and 'snail' not in first
    assert [glyph_of(record) for record in given] == [first[0], first[1], first[2], first[0], first[1]]
    read = {record['id']: record for given_open in ('true', 'false')
            for record in j(run, 'work', 'limit=0', f'open={given_open}', cwd=mapped)['results']}
    assert [glyph_of(read[record.id]) for record in order] == [glyph_of(record) for record in given]
    assert [glyph_of(read[one.id]) for one in (taken, done, outside, *backlog, after)] == [
        'owl', 'snail', None, None, None, None]
    again = j(run, 'work', 'op=distribute', 'agents=1', cwd=mapped)['results']  # one agent: every ready ticket, one lane
    assert {glyph_of(record) for record in again} == {AGENT_GLYPHS[0]} and len(again) == 5
    read = {record['id']: record for given_open in ('true', 'false')
            for record in j(run, 'work', 'limit=0', f'open={given_open}', cwd=mapped)['results']}
    assert [glyph_of(read[one.id]) for one in (taken, done, outside, *backlog, after)] == [
        'owl', 'snail', None, None, None, None]


@pytest.mark.req('VIEW-040')
@pytest.mark.req('BASE-035')
def test_a_tickets_glyph_is_set_by_edit_shown_on_its_read_and_a_name_that_is_no_glyph_is_kept_with_a_notice(run,
                                                                                                         mapped):
    ticket = Store('proj').add_work(Node('element', 'code.timer.kitchen'), 'unbuilt', task='a lane of its own')
    # nothing but its number and title when it keeps nothing else, MCP-037
    assert set(j(run, 'work', f'id={ticket.id}', cwd=mapped)['map']) == {'item', 'title'}
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
    ticket = Store('proj').add_work(Node('element', 'code.timer.kitchen'), 'unbuilt', task='a lane of its own')
    j(run, 'work', 'op=edit', f'id={ticket.id}', 'glyph=moth', cwd=mapped)
    for verb in (['op=take', 'by=claude'], ['op=plan', 'steps=2'], ['op=step', 'said=Traced it.'],
                 ['op=move', 'column=doing'], ['op=done', 'resolution=built']):
        assert glyph_of(j(run, 'work', *verb, f'id={ticket.id}', cwd=mapped)) == 'moth', verb


@pytest.mark.req('VIEW-040')
def test_distributing_over_no_agents_or_more_than_there_are_glyphs_is_refused_and_changes_nothing(run, mapped):
    store = Store('proj')
    ticket = store.add_work(Node('element', 'code.timer.kitchen'), 'unbuilt', task='waiting')
    lane = store.add_work(Node('element', 'code.timer.kitchen'), 'unbuilt', task='in a lane already')
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
    ticket = store.add_work(Node('element', 'code.timer.kitchen'), 'unbuilt', task='a lane of its own')
    other = store.add_work(Node('element', 'code.timer.kitchen'), 'unbuilt', task='no lane')
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
    """A join's IFD changes by refining with the rest of its fields."""
    join = Store('proj').joins('code.timer.kitchen').results[0]
    refined = json.loads(refined_by(run, mapped, f'receiver={join.receiver_address}', f'provider={join.elements[0].address}',
                           'ifd=sends', 'reason=The alarm is what the timer encounters.').stdout)
    assert not [notice for notice in refined.get('notices', []) if notice['where'] == 'ifd']
    now = next(held for held in Store('proj').joins('code.timer.kitchen').results if held.id == join.id)
    assert now.ifd == 'sends'


@pytest.mark.req('MAP-020')
def test_the_map_knowledge_tool_takes_no_perspective():
    """A join carries no perspective. Neither add-join, add-subtype, edit
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
    made = j(run, 'work', 'op=add', 'node=code.display.digit', 'condition=broken', 'task=dim the digits at night',
             'links=["element:code.timer.kitchen"]', cwd=described)
    read = run('map', 'work', f'id={made["id"]}', '--json', cwd=described)
    assert read.returncode == 0 and 'TypeError' not in read.stderr
    ticket = json.loads(read.stdout)
    assert (ticket['id'], ticket['task'], ticket['condition']) == (made['id'], 'dim the digits at night',
                                                                       'broken')
    at = ticket['at']
    assert at['element']['address'] == 'code.display.digit'
    assert at['sources'] == ['path=src/display.py', 'spec=DISP-001']  # where the code is, for the agent to read
    # The question is counted with the call that reads it, never carried, MCP-039.
    assert 'messages' not in at and '1 message' in at['around']
    assert 'metaform map messages node=code.display.digit' in at['around']
    assert [join['receiver'] for join in at['provides']] == ['code.timer.kitchen']
    assert ticket['linked'] == ['code.timer.kitchen']
    text = run('map', 'work', f'id={made["id"]}', cwd=described).stdout
    assert 'Four digits or six?' not in text and 'src/display.py' in text


@pytest.mark.req('MAP-048')
@pytest.mark.req('LAYER-012')
@pytest.mark.parametrize('on_join', [False, True])
def test_ticket_read_counts_the_note_at_its_node_and_names_its_linked_nodes(run, mapped, on_join):
    """The person's note at a ticket's node is counted with the call that reads it, never carried, MCP-039; a linked
    node is named by its address."""
    store = Store('proj')
    target = (Node('join', store.joins('code.timer.kitchen').results[0].id) if on_join else
              Node('element', 'code.timer.kitchen'))
    from tests.storekit import page_note  # the note is the person's, written from the page, VIEW-034
    page_note('proj', str(target), 'Check the circuit before replacing the timer.')
    page_note('proj', 'element:code.alarm.audible', 'The tone driver was rewired.')
    ticket = store.add_work(target, 'broken', task='repair the timer', links=[Node('element', 'code.alarm.audible')])
    read = j(run, 'work', f'id={ticket.id}', cwd=mapped)
    assert 'Check the circuit' not in json.dumps(read) and 'The tone driver' not in json.dumps(read)
    assert read['linked'] == ['code.alarm.audible']
    if not on_join:
        assert '1 note' in read['at']['around'] and '<address>' not in read['at']['around']
        assert 'metaform memory note node=code.timer.kitchen' in read['at']['around']  # each address with a note


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
    made = j(run, 'work', 'op=add', 'node=code.alarm.audible', 'condition=unbuilt', 'task=wire it', cwd=mapped)
    ticket = j(run, 'work', f'id={made["id"]}', cwd=mapped)
    assert ticket['task'] == 'wire it' and ticket['at']['element']['address'] == 'code.alarm.audible'
    assert ticket['breaks'] == {'failed': f'ValueError: no field for {made["id"]}'}
    assert ticket['zz'] == {'condition': 'unbuilt'}, 'the read goes on past a failing hook'
    assert list(ticket).index('breaks') < list(ticket).index('zz'), 'module id order'
    assert 'quiet' not in ticket
    assert ticket['linked'] == [], 'a field the read holds already is never replaced'


@pytest.mark.req('MAP-048')
def test_map_work_reading_a_ticket_names_the_list_nouns_it_does_not_read_and_an_unknown_id(run, mapped):
    made = j(run, 'work', 'op=add', 'node=code.alarm.audible', 'condition=unbuilt', 'task=wire it', cwd=mapped)
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
    run('map', 'work', 'op=add', 'title=A ticket', 'node=code.alarm.audible', 'condition=unbuilt', 'task=wire it', cwd=mapped)
    listed = j(run, 'work', 'said=nothing', cwd=mapped)
    assert len(listed['results']) == 1 and [notice['where'] for notice in listed['notices']] == ['said']


@pytest.mark.req('MAP-048')
@pytest.mark.req('STORE-025')
def test_map_where_shows_each_ticket_at_the_address_with_its_work_id(run, mapped):
    made = j(run, 'work', 'op=add', 'node=code.alarm.audible', 'condition=unbuilt', 'task=wire it', cwd=mapped)
    assert [one['id'] for one in j(run, 'where', 'code.alarm.audible', 'contents=true', cwd=mapped)['work']] == [
        made['id']]
    assert made['id'] in run('map', 'where', 'code.alarm.audible', 'contents=true', cwd=mapped).stdout
    assert '1 open work' in run('map', 'where', 'code.alarm.audible', cwd=mapped).stdout  # counted, MCP-039


@pytest.mark.req('LAYER-025')
@pytest.mark.req('MAP-005')
def test_refine_names_what_it_changes_by_address_and_never_hands_an_agent_an_id(run, mapped):
    """What an agent names is most easily inferred from what it already read, an address; an id it
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
    """Ticket ad135d54: what an agent names is most easily inferred from what it already read; ids
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
    beside = j(run, 'work', 'op=add', *display, 'node=element:code.alarm.audible', 'condition=broken', cwd=mapped)
    assert (beside['node_kind'], beside['provider_address']) == ('join', 'code.display.digit')
    assert said(beside) == [('node', 'receiver, provider and address name the node; node was not read.')]
    on_part = j(run, 'work', 'op=add', *named, 'address=code.alarm.audible.piezo', 'condition=unbuilt',
                'task=build the piezo', cwd=mapped)
    assert (on_part['node_kind'], on_part['address']) == ('element', 'code.alarm.audible.piezo')
    elsewhere = run('map', 'work', 'op=add', 'title=A ticket', *named, 'address=code.display.digit.segment', 'condition=unbuilt',
                    '--json', cwd=mapped, ok=False)
    assert elsewhere.returncode == 2 and 'code.display.digit.segment is not held by' in elsewhere.stderr
    on_element = j(run, 'work', 'op=add', 'address=code.alarm.audible', 'condition=broken', cwd=mapped)
    assert (on_element['node_kind'], on_element['address']) == ('element', 'code.alarm.audible')
    assert [row['id'] for row in j(run, 'work', *named, cwd=mapped)['results']] == [on_join['id']]
    assert [row['id'] for row in j(run, 'work', *display, cwd=mapped)['results']] == [beside['id']]
    assert [row['id'] for row in j(run, 'work', f'node=join:{shown.id}', cwd=mapped)['results']] == [
        beside['id']]
    cook = {'receiver': 'stakeholder.cook.home', 'provider': 'code.timer.kitchen'}
    linked = j(run, 'work', 'op=add', 'node=code.alarm.audible', 'condition=broken',
               f'links={json.dumps([cook, "code.timer.kitchen"])}', cwd=mapped)
    cook_id = store.joins('stakeholder.cook.home').results[0].id
    assert [(link['kind'], link['id']) for link in linked['links']] == [
        ('join', cook_id), ('element', store.element('code.timer.kitchen').id)]
    edited = j(run, 'work', 'op=edit', f'id={linked["id"]}',
               'links=[{"receiver": "code.timer.kitchen", "provider": "code.alarm.audible", '
               '"address": "code.alarm.audible.piezo"}, {"receiver": "code.timer.kitchen", '
               '"provider": "code.display.digit"}]', cwd=mapped)
    assert [(link['kind'], link['id']) for link in edited['links']] == [('element', piezo), ('join', shown.id)]
    unheld = run('map', 'work', 'op=add', 'title=A ticket', 'receiver=code.timer.kitchen', 'provider=code.nosuch.node',
                 'condition=unbuilt', '--json', cwd=mapped, ok=False)
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
    on_alarm = store.add_work(Node('element', 'code.alarm.audible'), None, task='on the element').id
    on_cook = store.add_work(Node('join', cook.id), 'broken', task='on the cook join').id
    on_join = store.add_work(Node('join', alarm.id), 'unbuilt', task='on the alarm join').id
    on_part = store.add_work(Node('element', 'code.alarm.audible.piezo'), 'unbuilt', task='on the piezo').id
    on_display = store.add_work(Node('join', shown.id), None, task='on the display join').id
    finished = store.add_work(Node('join', alarm.id), 'broken', task='done already').id
    store.finish_work(finished, 'fixed')

    def listed(*given):
        return [row['id'] for row in j(run, 'work', *given, 'limit=0', cwd=mapped)['results']]
    assert listed('node=element:code.alarm.audible.piezo') == [on_join, on_part]  # open, the default, MAP-049
    assert listed('node=element:code.alarm.audible', 'open=false') == [finished]
    assert listed('node=code.alarm.audible', 'open=true') == [on_alarm, on_join]
    assert listed('address=code.alarm.audible', 'open=true') == [on_alarm, on_join]
    assert listed('node=element:code.timer.kitchen', 'open=true') == [on_cook, on_join, on_display]
    assert listed('node=element:code.timer.kitchen', 'condition=unbuilt') == [on_join]
    assert listed(f'node=join:{alarm.id}', 'open=true') == [on_join]
    # The web panel's read of one object stays that object's own records.
    assert [row.id for row in store.work(Node('element', 'code.alarm.audible'), limit=0).results] == [on_alarm]


@pytest.mark.req('MAP-005')
@pytest.mark.req('MAP-050')
def test_ask_and_tell_take_node_first_and_provider_beside_it_names_the_purpose_node_holds(run, mapped):
    """Ticket ad135d54: keep node first; provider= beside it names the join node holds, node
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
    told = j(run, 'ask', 'element:code.timer.kitchen', 'Is the piezo quiet?', 'provider=code.alarm.audible',
             'address=code.alarm.audible.piezo', YES_NO, *FORM, cwd=mapped)
    assert (told['node_kind'], told['node_id']) == ('element', piezo)
    plain = j(run, 'ask', 'code.alarm.audible', 'Louder?', YES_NO, *FORM, cwd=mapped)
    assert (plain['node_kind'], plain['address']) == ('element', 'code.alarm.audible')
    alone = j(run, 'ask', 'code.alarm.audible', 'Quiet?', 'address=code.alarm.audible.piezo', YES_NO, *FORM, cwd=mapped)
    assert (alone['node_kind'], alone['address']) == ('element', 'code.alarm.audible')
    assert said(alone) == [('address', 'address names an element a join holds only with provider; it was not read.')]
    unheld = run('map', 'ask', 'code.timer.kitchen', 'x?', 'provider=code.nosuch.node', *FORM, '--json', cwd=mapped,
                 ok=False)
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
    """D91 and D92: read_first and always_show are stored on the item; task adds a ticket at the
    item's node and is not stored on the item. The ticket read returns the read_first items ahead of at."""
    k(run, mapped, 'op=create', 'layer=critic', 'variable=What the critic says at each node.', 'mutable=true',
      'hideable=true', *PROVENANCE)
    first = json.loads(k(run, mapped, 'op=add-item', 'layer=critic', 'node=element:code.timer.kitchen',
                         'value="Read the timer spec first."', 'read_first=true', 'always_show=true').stdout)
    assert (first['read_first'], first['always_show']) == (True, True)
    task = json.loads(k(run, mapped, 'op=add-item', 'layer=critic', 'node=element:code.timer.kitchen',
                        'value="Stop the alarm after a minute."', 'task=true', 'condition=unbuilt').stdout)
    assert 'task' not in task and (task['read_first'], task['always_show']) == (False, False)
    tickets = j(run, 'work', 'node=element:code.timer.kitchen', 'open=true', cwd=mapped)['results']
    assert [ticket['condition'] for ticket in tickets] == ['unbuilt']
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
def test_antigravity_ticket_choices_normalize_legacy_input_before_runtime_transport(run, mapped, monkeypatch):
    from metaform.module import Context
    from metaform.modules import map as module

    made = j(run, 'work', 'op=add', 'node=code.alarm.audible', 'task=Use Antigravity.',
             'agent=antigravity', 'eligible=["antigravity"]', cwd=mapped)
    assert made['map']['agent'] == 'antigravity'
    assert eligible_of(made) == ['antigravity'] and not made.get('notices')
    seen = []

    class Transport:
        def edit_runtime(self, ctx, work_id, nouns):
            seen.append(dict(nouns))
            return {}

    monkeypatch.setattr(module, 'provided', lambda folder, service: [('dispatch', Transport())])
    store = Store('proj', module='map')
    ctx = Context(module='map', folder=mapped, store=store)
    notices = []
    module._keep(store, made['id'], {'agent': 'gemini', 'eligible': ['gemini', 'codex']}, notices, ctx)
    assert seen[0] == {'agent': 'antigravity', 'eligible': ['antigravity', 'codex']} and not notices
    with store.tables(write=False) as tx:
        assert tx.get('ticket_settings', {'work_id': made['id']})['agent'] == 'antigravity'
        assert tx.get('eligible', {'work_id': made['id']})['agents'] == ['antigravity', 'codex']
    chosen = module.TICKET_RUNTIME.save(ctx, made['id'], {
        'agent': 'gemini', 'model': 'retained-model', 'effort': 'high',
        'decision': {'agent': 'gemini', 'reason': 'Keep this evidence.', 'confidence': 0.9}})
    assert chosen == {'agent': 'antigravity', 'model': 'retained-model', 'effort': 'high',
                      'decision': {'agent': 'antigravity', 'reason': 'Keep this evidence.', 'confidence': 0.9},
                      'eligible': ['antigravity', 'codex']}
    claimed = j(run, 'work', 'op=take', f'id={made["id"]}', 'by=antigravity session', cwd=mapped)
    assert claimed['taken_by'] == 'antigravity session'


@pytest.mark.req('STORE-029')
@pytest.mark.req('MAP-058')
def test_map_agent_identity_upgrade_preserves_ticket_data_and_retries_atomically(run, mapped, monkeypatch):
    from metaform import home
    from metaform.data.tables import declared

    store = Store('proj', module='map')
    work = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='Retain all ticket fields.')
    untouched = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='Keep Codex.')
    decision = {'agent': 'gemini', 'model': 'gemini-model-kept', 'effort': 'high',
                'reason': 'gemini appears in evidence, not an agent field.', 'confidence': 0.85,
                'extra': {'agent': 'unrelated'}}
    with store.tables() as tx:
        tx.insert('ticket_settings', {'work_id': work.id, 'agent': 'gemini', 'hold': 1, 'proof': 1,
                                     'landed': '2026-10-20T00:00:00Z', 'epic': untouched.id, 'agents': 3,
                                     'board': 'keep-board', 'model': 'gemini-model-kept', 'effort': 'high',
                                     'decision': decision})
        tx.insert('eligible', {'work_id': work.id, 'agents': ['codex', 'gemini', 'cursor']})
        tx.insert('ticket_settings', {'work_id': untouched.id, 'agent': 'codex', 'decision': {'reason': 'Keep.'}})
        before = tx.get('ticket_settings', {'work_id': work.id})
        same = tx.get('ticket_settings', {'work_id': untouched.id})
    path = home.store_path('proj', store.bound_base().id)
    with sqlite3.connect(path) as db:
        recorded = json.loads(db.execute("SELECT value FROM meta WHERE key='module:map'").fetchone()[0])
        recorded['version'] = 22
        db.execute("UPDATE meta SET value=? WHERE key='module:map'", (json.dumps(recorded),))

    upgrade = declared('map').upgrade
    normalize = upgrade.__globals__['agent_name']

    def interrupted(value):
        if value == 'cursor':
            raise RuntimeError('migration interrupted')
        return normalize(value)

    with monkeypatch.context() as patch:
        patch.setitem(upgrade.__globals__, 'agent_name', interrupted)
        with pytest.raises(RuntimeError, match='migration interrupted'), store.tables() as tx:
            tx.get('ticket_settings', {'work_id': work.id})
    with sqlite3.connect(path) as db:
        assert json.loads(db.execute("SELECT value FROM meta WHERE key='module:map'").fetchone()[0])['version'] == 22
        assert db.execute('SELECT agent FROM "map.ticket_settings" WHERE work_id=?', (work.id,)).fetchone()[0] == 'gemini'
    with store.tables() as tx:
        after = tx.get('ticket_settings', {'work_id': work.id})
        assert after == {**before, 'agent': 'antigravity', 'decision': {**decision, 'agent': 'antigravity'}}
        assert tx.get('ticket_settings', {'work_id': untouched.id}) == same
        assert tx.get('eligible', {'work_id': work.id})['agents'] == ['codex', 'antigravity', 'cursor']
        upgrade(tx, 22)
        assert tx.get('ticket_settings', {'work_id': work.id}) == after
        assert tx.get('eligible', {'work_id': work.id})['agents'] == ['codex', 'antigravity', 'cursor']
    assert store.ticket(work.id).work.task == 'Retain all ticket fields.'


@pytest.mark.req('MAP-058')
@pytest.mark.req('STORE-045')
@pytest.mark.req('BASE-046')
def test_any_agent_is_eligible_by_default_and_the_eligible_agents_are_kept_in_the_map_modules_own_table(run, mapped):
    """Ticket bd96cbd1: any agent is eligible by default unless the user specifies otherwise, and existing
    tickets default to Any. The user's choice is one or more agent types, shown on the ticket; like the glyph it is
    the map module's own field, a row keyed by the work id, and the work table has no column for it."""
    old = Store('proj').add_work(Node('element', 'code.timer.kitchen'), 'unbuilt', task='written before the setting')
    assert eligible_of(j(run, 'work', f'id={old.id}', cwd=mapped)) is None
    made = j(run, 'work', 'op=add', 'node=code.alarm.audible', 'condition=broken', 'task=quieter tone',
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
    gui = store.add_work(kitchen, 'unbuilt', task='GUI work')
    j(run, 'work', 'op=edit', f'id={gui.id}', 'eligible=["claude"]', cwd=mapped)
    for by in ('codex 9f2c', 'someone', None):
        refused = run('map', 'work', 'op=take', f'id={gui.id}', *([f'by={by}'] if by else []), cwd=mapped,
                      ok=False)
        said = refused.stdout + refused.stderr
        assert refused.returncode != 0 and 'claude' in said, (by, said)
        assert store.ticket(gui.id).work.taken is None
    took = j(run, 'work', 'op=take', f'id={gui.id}', 'by=claude 41ab', cwd=mapped)
    assert took['taken_by'] == 'claude 41ab'
    loose = store.add_work(kitchen, 'unbuilt', task='anyone')
    assert j(run, 'work', 'op=take', f'id={loose.id}', 'by=someone', cwd=mapped)['taken_by'] == 'someone'
    person = store.add_work(kitchen, 'unbuilt', task='the person takes it')
    j(run, 'work', 'op=edit', f'id={person.id}', 'eligible=["codex"]', cwd=mapped)
    moved = j(run, 'work', 'op=move', f'id={person.id}', 'column=doing', 'by=user', cwd=mapped)
    assert moved['taken_by'] == 'user'


@pytest.mark.req('MAP-052')
def test_a_document_that_cannot_be_written_stops_with_its_next_step(run, described, tmp_path):
    target = tmp_path / 'no such folder' / 'map.md'
    said = run('map', 'markdown', f'file={target}', cwd=described, ok=False)
    assert said.returncode != 0 and str(target) in said.stderr and 'leave out file=' in said.stderr
    assert not target.parent.exists()


@pytest.mark.req('BASE-043')
def test_required_nouns_named_as_name_value_read_as_written(run, described):
    """`map citing key=path value=<file>` names its two required nouns and finds what the positional form finds,
    where it used to take `key=path` as the key and answer nothing."""
    named = json.loads(run('map', 'citing', 'key=path', 'value=src/display.py', '--json', cwd=described).stdout)
    positional = json.loads(run('map', 'citing', 'path', 'src/display.py', '--json', cwd=described).stdout)
    assert named == positional
    assert [one['address'] for one in named['results']] == ['code.display.digit']


@pytest.mark.req('BASE-043')
def test_a_positional_value_holding_an_equals_sign_stays_the_value(run, described):
    """`map citing path key=abc` keeps `path` as the key and `key=abc` as the value: the positional word before it
    already gave the key, so the later word is not read as a second one."""
    said = json.loads(run('map', 'citing', 'path', 'key=abc', '--json', cwd=described).stdout)
    assert said['results'] == []
    from metaform import loader
    from metaform.grammar import parse
    citing = next(verb for module in loader.enabled() if module.id == 'map' for verb in module.verbs
                  if verb.name == 'citing')
    assert parse('map', citing, ['path', 'key=abc']).nouns == {'key': 'path', 'value': 'key=abc'}


@pytest.mark.req('MCP-006')
@pytest.mark.req('BASE-038')
@pytest.mark.parametrize('address', ['code.timer', 'code.timer.kitchn'])
def test_where_on_an_address_that_is_no_element_stops_and_names_a_nearby_element(run, mapped, address):
    """A namespace prefix and a typo are both no element; silence left an agent unsure whether the read failed."""
    refused = run('map', 'where', address, cwd=mapped, ok=False)
    assert refused.returncode == 2
    assert f'No element {address} in context here.' in refused.stderr
    assert 'Nearest: code.timer.kitchen' in refused.stderr
    assert refused.stderr.splitlines()[-1] == 'Next: metaform map where code.timer.kitchen'


@pytest.mark.parametrize('visibility', ['building', 'hidden', 'masked'])
def test_missing_address_names_the_layer_and_a_raw_read(run, mapped, visibility):
    store = Store('proj')
    layer = store.layer('extra', 'map', 'Additional map elements.', mutable=True, hideable=True,
                        ready=visibility != 'building')
    store.add_element(layer.name, 'code.timer.extra', name_length=2, role='SE')
    if visibility == 'hidden':
        store.hide(layer.name)
    elif visibility == 'masked':
        store.mask('code.timer.extra', layer.name)
    stopped = run('map', 'where', 'code.timer.extra', cwd=mapped, ok=False)
    assert stopped.returncode == 2
    assert 'layer extra' in stopped.stderr
    assert stopped.stderr.splitlines()[-1] == 'Next: metaform map where code.timer.extra --raw'
    assert j(run, 'where', 'code.timer.extra', '--raw', cwd=mapped)['element']['address'] == 'code.timer.extra'


def test_missing_address_with_no_candidate_names_the_roots(run, mapped):
    stopped = run('map', 'where', 'xyz.abc', cwd=mapped, ok=False)
    assert stopped.returncode == 2
    assert stopped.stderr.splitlines()[-1] == "Next: metaform map children address=''"
    assert j(run, 'children', 'address=', cwd=mapped)['results']


def test_missing_address_recovery_is_shared_by_the_glossary(run, kitchen):
    for args in (('term', 'term=dish timer', 'node=code.timer.kitchn', 'definition=A timer.', 'why=Name the timer.'),):
        stopped = run('map', *args, cwd=kitchen, ok=False)
        assert stopped.returncode == 2
        assert 'Nearest: code.timer.kitchen' in stopped.stderr
        assert stopped.stderr.splitlines()[-1] == 'Next: metaform map where code.timer.kitchen'


def test_citing_a_path_outside_the_project_stops_and_an_uncited_path_finds_nothing(run, mapped):
    outside = str(mapped.parent / 'outside.py')
    stopped = run('map', 'citing', 'key=path', f'value={outside}', cwd=mapped, ok=False)
    assert stopped.returncode == 2
    assert f'{outside} is outside the project folder {mapped}' in stopped.stderr
    uncited = j(run, 'citing', 'key=path', 'value=./src/uncited.py', cwd=mapped)
    assert uncited == {'results': [], 'next': None}


@pytest.mark.req('BASE-038')
def test_where_shows_the_elements_id_so_its_history_is_read_from_there(run, mapped):
    found = j(run, 'where', 'code.alarm.audible', cwd=mapped)['element']
    assert found['id'] == Store('proj').element('code.alarm.audible').id
    assert j(run, 'history', found['id'], cwd=mapped)['results']


@pytest.mark.req('STORE-025')
def test_where_carries_the_code_attached_to_each_purpose_join(run, described):
    """An element's where read shows, under each join it provides, what the layers hold at that join: the sources item
    naming the code that realizes the purpose reaches an agent in the one read, not only through map node."""
    store = Store('proj')
    join_id = next(join.id for join in store.joins('stakeholder.cook.home').results)
    with store.atomic():
        store.add_item('sources', Node('join', join_id), {'realized_by': 'the timer loop'},
                       refs=[('qn', 'proj.src.timer.tick'), ('path', 'src/timer.c')])
    read = json.loads(run('map', 'where', 'code.timer.kitchen', '--json', cwd=described).stdout)
    provided = next(join for join in read['provides'] if join['receiver'] == 'stakeholder.cook.home')
    assert 'qn=proj.src.timer.tick' in provided['sources']  # a pointer to the code, in the compact read too
    read = json.loads(run('map', 'where', 'code.timer.kitchen', 'contents=true', '--json', cwd=described).stdout)
    provided = next(join for join in read['provides'] if join['receiver'] == 'stakeholder.cook.home')
    refs = [ref for group in provided['layers'] for item in group['items'] for ref in item.get('refs', [])]
    assert {'key': 'qn', 'value': 'proj.src.timer.tick'} in refs


@pytest.mark.req('MCP-039')
def test_the_counts_at_a_node_are_told_once_per_session_and_then_only_what_changed(run, mapped, monkeypatch):
    """An agent is told what is held at its node and around it once per session; a later read in that session says
    what changed. Counts and authored writes do not stand in for receiving a complete memory body."""
    def where(session: str) -> dict:
        monkeypatch.setenv('METAFORM_SESSION', session)
        return j(run, 'where', 'code.timer.kitchen', cwd=mapped)

    def remember(session: str, address: str, name: str) -> None:
        monkeypatch.setenv('METAFORM_SESSION', session)
        run('memory', 'create_entities', json.dumps([{'name': name, 'entityType': 'finding', 'observations': ['x'],
                                                      'why': 'Found at work.'}]),
            f'node={address}', cwd=mapped)

    first = where('agent-a')
    assert first['around'].splitlines()[:3] == ['Relied on by', '  └ stakeholder.cook.home',
                                                '▶ code.timer.kitchen  kitchen timer']
    again = where('agent-a')
    assert 'around' not in again and 'changed' not in again and again['element'] == first['element']
    # code.dispatcher.agent#72: unread memory is told only at the node the agent reads, as one line, and only while
    # some there is unread; a neighbour's new memory and the agent's own write say nothing
    remember('agent-b', 'code.alarm.audible', 'tone')
    assert 'changed' not in where('agent-a')
    remember('agent-a', 'code.timer.kitchen', 'mine')
    assert 'changed' not in where('agent-a'), 'its own write is read'
    remember('agent-b', 'code.timer.kitchen', 'theirs')
    [line] = where('agent-a')['changed']
    assert line.startswith('Unread memories here: 1. List titles with metaform memory read_unread '
                           'node=element:code.timer.kitchen. Search using'), line
    fresh = where('agent-c')['around']
    assert re.search(r'▶ code\.timer\.kitchen  kitchen timer +2 memories · 2 unread', fresh)
    assert re.search(r'└ code\.alarm\.audible +1 memory · 1 unread', fresh)
    assert 'Unread memories here: 2. List titles with metaform memory read_unread node=element:code.timer.kitchen' in fresh
    assert 'node=element:code.alarm.audible' not in fresh and '<address>' not in fresh
    monkeypatch.setenv('METAFORM_SESSION', 'agent-e')  # an agent that read everything at the node, then arrives
    run('memory', 'open_nodes', '["mine","theirs"]', 'node=element:code.timer.kitchen', cwd=mapped)
    arrived = where('agent-e')['around']
    assert re.search(r'▶ code\.timer\.kitchen  kitchen timer +2 memories', arrived), arrived
    assert '2 unread' not in arrived and 'Unread memories' not in arrived, arrived


@pytest.mark.req('MCP-039')
def test_the_counts_tree_aligns_its_counts_and_caps_each_side(tmp_path, monkeypatch):
    """The tree draws the node between what relies on it and what it relies on, the busiest neighbours first, at
    most eight a side and then how many more with the call that lists them, every count in one column."""
    from metaform.data import Element, Held, Join, Where
    from metaform.module import Context, Count
    from metaform.modules.map import around

    def join(receiver: str, provider: str) -> Join:
        return Join(id=receiver + provider, layer_id='l', layer='base', type='purpose', receiver=receiver,
                    receiver_address=receiver, purpose='p', ef='f', elements=(Held(provider, provider),))
    users = [f'code.user.n{index}' for index in range(11)]
    found = Where(kind='element', element=Element(id='hub', address='code.hub', layer_id='l', layer='base',
                                                  short_name='hub'),
                  provides=tuple(join(user, 'code.hub') for user in users),
                  receives=(join('code.hub', 'data.store'),))
    counted = Count('memory', 'memories', {'code.user.n3': (12, 2, 0), 'code.hub': (32, 5, 0), 'data.store': (1, 0, 0)},
                    legend='New = recorded by the last session here.')
    monkeypatch.setattr(around, 'node_counts', lambda *args, **kwargs: {'memory': counted})
    lines = around.Around(Context(module='map', folder=tmp_path), found).tree().splitlines()
    assert lines[0] == 'Relied on by' and lines[1].startswith('  ├ code.user.n3 ')
    assert len([line for line in lines if line.startswith(('  ├ code.user', '  └ code.user'))]) == 8
    assert lines[9] == '  └ and 3 more: metaform map joins element=code.hub as=provider'
    assert lines[10].startswith('▶ code.hub  hub') and lines[10].endswith('32 memories · 5 new')
    assert lines[11:] == [lines[11], lines[12], 'New = recorded by the last session here.']
    assert (lines[11], lines[12].split()[:2]) == ('Relies on', ['└', 'data.store'])
    assert lines[12].endswith(' 1 memory')
    column = {line.index(' memor') for line in lines if ' memor' in line and not line.startswith('New')}
    assert len(column) == 1, 'every count in one column'


@pytest.mark.req('MCP-039')
def test_busy_node_preserves_all_receiving_purposes_before_decorative_counts(tmp_path, monkeypatch):
    """A display target must not hide a governing receiver merely because it was stored after another."""
    from metaform.data import Element, Held, Item, Join, LayerGroup, Ref, Where
    from metaform.module import Context, Count
    from metaform.modules import map as module
    from metaform.modules.map import around

    def sources(name: str) -> tuple[LayerGroup, ...]:
        refs = tuple(Ref('path', f'src/{name}/part_{index}.py') for index in range(12))
        return (LayerGroup('s', 'sources', 'knowledge', items=(Item('i' + name, 's', 'sources', Node('join', name),
                                                                    name, refs=refs),)),)

    def join(receiver: str, provider: str) -> Join:
        return Join(id=receiver + provider, layer_id='l', layer='base', type='purpose', receiver=receiver,
                    receiver_address=receiver, purpose=f'Keep {receiver} served with a long stated purpose ' * 3,
                    ef='f', elements=(Held(provider, provider),))
    provides = tuple(join(f'code.user.n{index}', 'code.hub') for index in range(30))
    receives = tuple(join('code.hub', f'data.store.n{index}') for index in range(30))
    found = Where(kind='element', element=Element(id='hub', address='code.hub', layer_id='l', layer='base',
                                                  short_name='hub'),
                  provides=provides, receives=receives, layers=sources('hub'),
                  join_layers=tuple((one.id, sources(one.id)) for one in (*provides, *receives)))
    counted = Count('memory', 'memories', {one: (5, 1, 0) for one in ('code.hub', *(f'code.user.n{index}' for index in
                                                                                   range(30)))})
    monkeypatch.setattr(around, 'node_counts', lambda *args, **kwargs: {'memory': counted})
    told = module._oriented(Context(module='map', folder=tmp_path), found, Node('element', 'code.hub'))
    assert len(json.dumps(told, ensure_ascii=False).encode('utf-8')) > 2048
    assert told['element']['address'] == 'code.hub' and told['provides'][0]['receiver'] == 'code.user.n0'
    assert 'around' not in told
    assert len(told['provides']) == len(told['receives']) == 30
    assert told['provides'][-1]['receiver'] == 'code.user.n29'
    assert told['provides'][-1]['purpose'] == provides[-1].purpose
    assert any(line.endswith('source paths not shown: metaform map where address=code.hub contents=true')
               for line in told['more'])
    assert not any('joins' in line for line in told['more'])


@pytest.mark.req('MAP-050')
@pytest.mark.req('MCP-037')
def test_tickets_and_questions_take_the_next_number_at_their_node_with_their_title_and_why(run, mapped):
    """A ticket, a question and a memory at one address share its counter. A ticket carries a title and its resolution
    a why, a question both; a write without them is refused naming which. A ticket on a join is numbered at its
    receiver's address, and a question moved to another node takes the next number there."""
    def refused(*args):
        said = run('map', *args, '--json', cwd=mapped, ok=False)
        assert said.returncode == 2
        return said.stderr.splitlines()[-1]
    assert refused('work', 'op=add', 'node=code.alarm.audible', 'task=Wire it.') == (
        'Next: add title: one line saying what this is')
    ticket = j(run, 'work', 'op=add', 'node=code.alarm.audible', 'task=Wire it.', 'title=Wire the alarm', cwd=mapped)
    assert ticket['map'] == {'item': 'code.alarm.audible#1', 'title': 'Wire the alarm'}
    run('memory', 'create_entities', json.dumps([{'name': 'tone', 'entityType': 'fact', 'observations': ['Quiet.'],
                                                  'why': 'The cook misses it.'}]), 'node=code.alarm.audible',
        cwd=mapped)
    assert refused('ask', 'code.alarm.audible', 'Louder?', YES_NO, 'title=Louder') == (
        'Next: add why: one line saying why it is asked')
    asked = j(run, 'ask', 'code.alarm.audible', 'Louder?', YES_NO, 'title=Louder tone', 'why=The cook misses it.',
              cwd=mapped)
    assert (asked['item'], asked['title']) == ('code.alarm.audible#3', 'Louder tone')
    assert refused('work', 'op=done', f'id={ticket["id"]}', 'resolution=Wired.') == (
        'Next: add why: one line saying why it was resolved this way')
    j(run, 'work', 'op=done', f'id={ticket["id"]}', 'resolution=Wired.', 'why=The spec asks for it.', cwd=mapped)
    read = j(run, 'item', 'code.alarm.audible#1', cwd=mapped)
    assert (read['kind'], read['title'], read['why'], read['module']) == ('work', 'Wire the alarm', 'The spec asks for it.',
                                                                          'map')
    on_join = j(run, 'work', 'op=add', 'receiver=code.timer.kitchen', 'provider=code.alarm.audible',
                'task=Fix the tone.', 'title=Fix the tone', cwd=mapped)
    assert on_join['map']['item'] == 'code.timer.kitchen#1'
    moved = j(run, 'messages', 'op=move', f'id={asked["id"]}', 'node=code.timer.kitchen', cwd=mapped)
    assert moved['item'] == 'code.timer.kitchen#2'
    assert run('map', 'item', 'code.alarm.audible#3', cwd=mapped, ok=False).returncode == 2  # its old number is gone
    listed = j(run, 'messages', 'node=code.timer.kitchen', cwd=mapped)['results']
    assert [(one['item'], one['title']) for one in listed] == [('code.timer.kitchen#2', 'Louder tone')]


@pytest.mark.req('MCP-037')
def test_tickets_and_messages_written_before_numbers_are_numbered_once_in_the_order_they_were_made(run, mapped):
    """Map tables version 10 numbers what was written before: the first map read or write after it numbers every work
    record and message in creation order, titled from the first line of its task, note or text."""
    store = Store('proj')
    first = store.add_work(Node('element', 'code.alarm.audible'), None, task='First task.\nIn detail.')
    said = store.ask(Node('element', 'code.alarm.audible'), 'A question?')
    last = store.add_work(Node('element', 'code.alarm.audible'), 'unbuilt', note='Last note.')  # a stage, no task
    with Store('proj', module='map').tables() as tx:  # as a store written before numbering holds them
        tx.delete('numbered', {'kind': 'work'})
        tx.delete('numbered', {'kind': 'message'})
        tx.delete('numbering', {'name': 'items'})
    listed = j(run, 'work', 'node=code.alarm.audible', cwd=mapped)['results']
    numbers = {one['id']: int(one['map']['item'].rpartition('#')[2], 16) for one in listed}
    asked = j(run, 'messages', 'node=code.alarm.audible', cwd=mapped)['results'][0]
    numbers[said.id] = int(asked['item'].rpartition('#')[2], 16)
    # after the three numbers they held, in the order they were made; a message and a ticket made in the same second
    # are told apart by their kind
    assert sorted(numbers.values()) == [4, 5, 6] and numbers[first.id] < numbers[last.id]
    assert j(run, 'item', f'code.alarm.audible#{numbers[said.id]}', cwd=mapped)['id'] == said.id
    assert [one['map']['title'] for one in listed] == ['First task.', 'Last note.']
    j(run, 'work', 'node=code.alarm.audible', cwd=mapped)  # once: a second read numbers nothing again
    assert Store('proj').latest_number('code.alarm.audible') == 6


@pytest.fixture
def kitchen(run, tmp_path):
    """A project with a small map whose sources cite its files: the alarm's whole file, and the timer's lines."""
    folder = tmp_path / 'kitchen'
    folder.mkdir()
    run('add', 'project', 'kitchen', str(folder))
    store = Store('kitchen')
    with store.atomic():
        layer = store.layer('intake-1', 'intake', 'The functional map.', kind='intake', mutable=False,
                            hideable=False, provenance={'module': 'intake'}, ready=True)
        store.add_element(layer.name, 'stakeholder.cook.home', name_length=2, role='CQU')
        store.add_element(layer.name, 'code.timer.kitchen', name_length=2, role='DE')
        store.add_element(layer.name, 'code.alarm.audible', name_length=2, role='SE')
        store.add_element(layer.name, 'code.display.digit', name_length=2, role='SE')
        store.add_join(layer.name, 'stakeholder.cook.home', 'code.timer.kitchen', purpose='Know when a dish is done.')
        store.add_join(layer.name, 'code.timer.kitchen', 'code.alarm.audible', purpose='Get attention.')
        store.add_join(layer.name, 'code.timer.kitchen', 'code.display.digit', purpose='See the time left.')
        sources = store.layer('sources', 'intake', 'refs', mutable=True, hideable=True, ready=True)
        store.add_item(sources.name, Node('element', 'code.alarm.audible'), 'alarm',
                       refs=[('path', 'kitchen/alarm.py')])
        store.add_item(sources.name, Node('element', 'code.timer.kitchen'), 'timer',
                       refs=[('path', 'kitchen/timer.py:5-13')])
    return folder


def code(run, folder, *args, ok=True):
    done = run('map', *args, '--json', cwd=folder, ok=ok)
    return json.loads(done.stdout) if ok else done


@pytest.mark.req('MCP-037')
def test_the_brief_names_the_latest_item_and_what_the_last_other_session_added(run, mapped):
    """Under the node in its brief: the last number taken there with its title, and the numbers the last session
    other than the reader's own took there, as a range."""
    def add(session, title):
        run('map', 'work', 'op=add', 'node=code.timer.kitchen', f'title={title}', 'task=t', cwd=mapped,
            env={'METAFORM_SESSION': session})
    add('s1', 'Build the countdown')
    add('s2', 'Wire the tone')
    add('s2', 'Test the ring')
    said = j(run, 'where', 'code.timer.kitchen', cwd=mapped)['around']
    assert 'Latest: code.timer.kitchen#3  Test the ring; the last session added #2–#3' in said
    own = json.loads(run('map', 'where', 'code.timer.kitchen', '--json', cwd=mapped,
                         env={'METAFORM_SESSION': 's2'}).stdout)['around']
    assert 'the last session added #1' in own and '#2–#3' not in own  # its own writes are never news to it


@pytest.mark.req('MAP-021')
def test_the_glossary_follows_the_map_and_keeps_the_terms_added_with_their_why_and_source(run, mapped):
    """An element's name is a term defined by its EF and OP, in step with refine; an added term carries its
    definition, why and source and is numbered at its node; the block leads with the register standard as written
    and keeps to glossary_bytes, counting the rest."""
    refused = run('map', 'term', 'term=ding', 'definition=The tone at zero.', 'source=src/alarm.py:3', cwd=mapped,
                  ok=False)
    assert 'why' in refused.stdout + refused.stderr
    added = j(run, 'term', 'term=ding', 'definition=The tone at zero.', 'why=Cooks say ding.',
              'source=src/alarm.py:3', 'node=code.alarm.audible', cwd=mapped)
    assert added['item'] == 'code.alarm.audible#1' and added['kind'] == 'added'
    assert j(run, 'item', 'code.alarm.audible#1', cwd=mapped)['kind'] == 'term'
    listed = {one['term']: one for one in j(run, 'glossary', 'format=list', cwd=mapped)['results']}
    assert listed['kitchen timer']['definition'] == 'code.timer.kitchen — EF: Counts down and rings. OP: Get attention.'
    run('map', 'refine', 'address=code.timer.kitchen', 'name=dish timer', 'reason=the project says dish timer',
        cwd=mapped)
    block = run('map', 'glossary', cwd=mapped).stdout
    assert '{dish timer} := "code.timer.kitchen' in block and 'kitchen timer' not in block
    assert block.startswith('# Peer Register — Mandatory Project Standard') and '{ding} := "The tone at zero."' in block
    j(run, 'term', 'op=remove', 'term=dish timer', 'why=Not the project\'s word.', cwd=mapped)
    assert 'dish timer' not in run('map', 'glossary', '--glossary-register', 'none', cwd=mapped).stdout
    for number in range(6):
        run('map', 'term', f'term=dish stage {number}', f'definition=Stage {number} of a dish, as the cook counts it '
            'down on the kitchen timer.', 'why=Cooks name stages.', 'source=the cook', cwd=mapped)
    whole = run('map', 'glossary', cwd=mapped).stdout.strip()
    cap = len(whole.encode('utf-8')) - 200
    small = run('map', 'glossary', '--glossary-bytes', str(cap), cwd=mapped).stdout.strip()
    assert len(small.encode('utf-8')) <= cap and re.search(r'// \d+ more terms, by use: metaform map glossary', small)


@pytest.fixture
def in_store(run, tmp_path, home):
    """`proj` with its map in the project store: a dish menu wanting a kitchen timer wanting an alarm. Its single-writer
    service is stopped when the test ends."""
    from metaform.project import owner, service
    from metaform.project import run as command
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    assert command({'add': {'proj.code.alarm.audible': {
        'technical_name': 'audible alarm', 'name': 'alarm', 'role': 'Supporting Element'}}}) == {'status': 'ok'}
    assert command({'add': {'proj.code.timer.kitchen': {
        'technical_name': 'kitchen timer', 'name': 'kitchen timer', 'role': 'Defining Element',
        'wants': [{'element': 'proj.code.alarm.audible', 'why': 'get attention', 'how': 'plays a tone',
                   'direction': 'receive'}]}}}) == {'status': 'ok'}
    assert command({'add': {'proj.code.menu.dish': {
        'technical_name': 'dish menu', 'name': 'dish menu', 'role': 'Coupled Element',
        'wants': [{'element': 'proj.code.timer.kitchen', 'why': 'know when a dish is done',
                   'how': 'counts down and rings', 'direction': 'receive'}]}}}) == {'status': 'ok'}
    yield folder
    service.stop(home)
    owner.close_all()


@pytest.mark.req('MAP-021')
def test_the_glossary_of_a_project_in_the_project_store_reads_its_map_and_keeps_terms_in_its_glossary_overlay(
        run, in_store):
    """Decision t-legacy-keep: an element's name is a term defined by its wants; a term added, edited or removed is a
    record of the glossary overlay at its element, each change naming the record it found; a term for the whole
    project has no place there and is refused by name; the old store keeps none."""
    from metaform.data import Store
    from metaform.project import overlay_records

    def records():
        return {one['term']: one for one in overlay_records('proj', 'glossary') or []}
    listed = {one['term']: one for one in j(run, 'glossary', 'format=list', cwd=in_store)['results']}
    assert listed['kitchen timer']['definition'] == ('code.timer.kitchen — EF: counts down and rings. '
                                                     'OP: get attention.')
    whole = run('map', 'term', 'term=ding', 'definition=The tone at zero.', 'why=Cooks say ding.', 'source=the cook',
                cwd=in_store, ok=False)
    assert 'no place in the project store' in whole.stdout + whole.stderr and not records()
    added = j(run, 'term', 'term=ding', 'definition=The tone at zero.', 'why=Cooks say ding.', 'source=the cook',
              'node=code.alarm.audible', cwd=in_store)
    ding = records()['ding']
    assert ding['element'] == 'proj.code.alarm.audible' and ding['state'] == 'added'
    assert (added['kind'], added['node'], added['record']) == ('added', 'code.alarm.audible', ding['record'])
    assert '{ding} := "The tone at zero."' in run('map', 'glossary', cwd=in_store).stdout
    j(run, 'term', 'op=edit', 'term=ding', 'why=Heard at the timer.', 'node=code.timer.kitchen', cwd=in_store)
    moved = records()['ding']
    assert moved['element'] == 'proj.code.timer.kitchen' and moved['definition'] == 'The tone at zero.'
    j(run, 'term', 'op=edit', 'term=kitchen timer', 'definition=The countdown for one dish.',
      'why=The project says so.', cwd=in_store)
    timer = records()['kitchen timer']
    assert (timer['element'], timer['state']) == ('proj.code.timer.kitchen', 'edited')
    assert j(run, 'glossary', 'term=kitchen timer', cwd=in_store)['definition'] == 'The countdown for one dish.'
    j(run, 'term', 'op=edit', 'term=kitchen timer', 'source=the menu', 'why=Named on the menu.', cwd=in_store)
    again = records()['kitchen timer']
    assert (again['record'], again['revision'], again['source']) == (timer['record'], timer['revision'] + 1,
                                                                    'the menu')
    j(run, 'term', 'op=remove', 'term=ding', 'why=Not the project\'s word.', cwd=in_store)
    j(run, 'term', 'op=remove', 'term=kitchen timer', 'why=Not the project\'s word.', cwd=in_store)
    assert 'ding' not in records() and records()['kitchen timer']['state'] == 'removed'
    assert [one['term'] for one in j(run, 'glossary', 'format=list', cwd=in_store)['results']] == ['alarm', 'dish menu']
    with Store('proj', module='map').tables(write=False) as tx:
        assert not tx.rows('terms', limit=0).results


@pytest.mark.req('LAYER-014')
@pytest.mark.req('LAYER-015')
@pytest.mark.req('STORE-040')
def test_the_critic_of_a_project_in_the_project_store_keeps_its_challenges_in_its_challenges_overlay(run, in_store):
    """Decision t-legacy-keep: a critic run on a store project defines the challenges overlay and is given the map as
    one document; each blind spot is a record at its element, answered and approved on that record, naming the record
    it found; a link to a join has no place there and is refused by name; the old store gets no blind-spot layer."""
    from metaform.data import Store
    from metaform.modules.map import challenged
    from metaform.project import overlay_records
    from metaform.project import run as command

    def records():
        return {one['challenge']: one for one in overlay_records('proj', 'challenges') or []}
    served = run('map', 'critic', cwd=in_store).stdout
    blind = re.search(r'Your critic run is (blind_spot_fast_\w+)\.', served).group(1)
    assert 'BLIND SPOT CHALLENGE' in served and '"blinded": true' in served and 'proj.code.timer.kitchen' in served
    sighted = run('map', 'critic', '--critic', cwd=in_store).stdout
    assert re.search(r'Your critic run is blind_spot_critic_\w+\.', sighted) and '"blinded": false' in sighted
    assert not challenged(in_store)
    for address, fields in (('code.timer.kitchen', {'challenge': 'Nothing recovers a hung loop.'}),
                            ('code.timer.kitchen', {'challenge': 'Nobody hears it.', 'want': 'proj.code.alarm.audible'}),
                            ('code.alarm.audible', {'challenge': 'The alarm has no volume control.'})):
        assert command({'add': {f'proj.{address}': {'challenges': [{'run': blind, 'blinded': True, **fields}]}}}) == {
            'status': 'ok'}
    assert challenged(in_store)
    hang, heard, volume = (records()[one]['record'] for one in (
        'Nothing recovers a hung loop.', 'Nobody hears it.', 'The alarm has no volume control.'))
    listed = run('map', 'challenges', blind, cwd=in_store).stdout
    assert f'{heard}  open  element:code.timer.kitchen want:code.alarm.audible  Nobody hears it.' in listed
    assert run('map', 'answer', volume, 'A', cwd=in_store).returncode == 0
    unlinked = run('map', 'answer', heard, 'C', cwd=in_store)
    assert re.search(r'^Notice: link: ', unlinked.stdout, re.MULTILINE) and records()['Nobody hears it.']['answer'] == 'C'
    joined = run('map', 'answer', heard, 'C', 'link=join:j1', cwd=in_store, ok=False)
    assert 'no place in the project store' in joined.stdout + joined.stderr
    run('map', 'answer', heard, 'C', 'link=element:code.alarm.audible', cwd=in_store)
    assert records()['Nobody hears it.']['link'] == 'proj.code.alarm.audible'
    assert run('map', 'approve', volume, cwd=in_store, ok=False).returncode == 2
    planned = run('map', 'answer', hang, 'plan', cwd=in_store)
    assert 'nothing was written' in planned.stdout and 'answer' not in records()['Nothing recovers a hung loop.']
    run('map', 'answer', hang, 'B', cwd=in_store)
    answered = records()['Nothing recovers a hung loop.']
    run('map', 'approve', hang, cwd=in_store)
    approved = records()['Nothing recovers a hung loop.']
    assert (approved['record'], approved['revision'], approved['answer']) == (answered['record'],
                                                                              answered['revision'] + 1, 'plan')
    assert f'{hang}  plan  element:code.timer.kitchen  Nothing recovers a hung loop.' in run(
        'map', 'challenges', blind, cwd=in_store).stdout
    assert not [one for one in Store('proj').layers(limit=0).results if one.name.startswith('blind_spot_')]


@pytest.mark.req('MAP-021')
def test_the_layers_of_a_project_in_the_project_store_are_its_overlays_and_its_knowledge_their_records(run, in_store):
    """Decision t-legacy-keep: a knowledge layer is an overlay, an item a record at an element; the reads answer from
    the overlays, citing reads refs and links address fields; each edit names the record and revision it found; what
    has no place in the store is refused by name and writes nothing."""
    from metaform.project import overlay_records

    def refused(*args):
        answer = run('map', *args, cwd=in_store, ok=False)
        assert answer.returncode != 0, args
        return answer.stdout + answer.stderr
    assert {'tickets', 'wants'} <= {one['layer'] for one in j(run, 'layers', cwd=in_store)['results']}
    assert 'an overlay has no tags' in refused('tag', 'layer=tickets', 'tag=x')
    assert 'cannot be hidden' in refused('knowledge', 'op=create', 'layer=practices-cpp', 'variable=C++ here?',
                                         'hideable=true')
    made = j(run, 'knowledge', 'op=create', 'layer=practices-cpp', 'variable=C++ practice here.', 'mutable=true',
             'fields=["standard"]', cwd=in_store)
    assert (made['layer'], made['fields']) == ('practices_cpp', ['standard', 'value', 'link'])
    item = j(run, 'knowledge', 'op=add-item', 'layer=practices-cpp', 'node=element:code.timer.kitchen',
             'value={"standard": "C++17"}', 'link=element:code.alarm.audible', 'refs=[["path", "./src/timer.cc"]]',
             cwd=in_store)
    assert (item['node'], item['standard'], item['link'], item['ref']) == (
        'code.timer.kitchen', 'C++17', 'proj.code.alarm.audible', './src/timer.cc')
    j(run, 'knowledge', 'op=add-property', 'layer=practices_cpp', 'element=code.alarm.audible', 'value=7',
      cwd=in_store)
    assert [one['value'] for one in j(run, 'layer', 'layer=practices-cpp', 'node=element:code.alarm.audible',
                                      cwd=in_store)['results']] == ['7']
    assert [one['layer'] for one in j(run, 'node', 'element:code.timer.kitchen', cwd=in_store)['layers']] == [
        'practices_cpp', 'wants']
    below = j(run, 'context', 'code', cwd=in_store)
    assert not below['applying'] and {one['node'] for one in below['results']} == {
        'code.timer.kitchen', 'code.alarm.audible', 'code.menu.dish'}
    assert {(one['layer'], one['node']) for one in j(run, 'links', 'element:code.alarm.audible',
                                                      cwd=in_store)['results']} == {
        ('practices_cpp', 'code.timer.kitchen'), ('wants', 'code.timer.kitchen')}
    assert [one['node'] for one in j(run, 'citing', 'key=path', 'value=src/timer.cc', cwd=in_store)['results']] == [
        'code.timer.kitchen']
    edited = j(run, 'knowledge', 'op=edit', f'id={item["record"]}', 'value={"standard": "C++20"}', cwd=in_store)
    assert (edited['record'], edited['revision'], edited['standard'], edited['link']) == (
        item['record'], item['revision'] + 1, 'C++20', 'proj.code.alarm.audible')
    assert 'holds ./src/timer.cc already' in refused('knowledge', 'op=add-ref', f'owner={item["record"]}', 'key=path',
                                                     'value="src/other.cc"')
    for args, said in ((('op=finish', 'layer=practices-cpp'), 'no finished state'),
                       (('op=add-item', 'layer=practices-cpp', 'node=join:j1', 'value=1'), 'never by a join'),
                       (('op=add-item', 'layer=practices-cpp', 'node=element:code.menu.dish', 'value=1',
                         'read_first=true'), 'a record has no read_first')):
        assert said in refused('knowledge', *args), args
    assert len(overlay_records('proj', 'practices_cpp') or []) == 2
    j(run, 'knowledge', 'op=remove', f'id={item["record"]}', cwd=in_store)
    assert [one['element'] for one in overlay_records('proj', 'practices_cpp') or []] == ['proj.code.alarm.audible']


@pytest.mark.req('MAP-045')
def test_the_bases_of_a_project_in_the_project_store_are_its_databases_and_its_memory_goes_with_the_project(
        run, in_store, home):
    """Decision t-legacy-keep: a store project's bases are whole databases of the project store. add-base sets the
    active one aside with its tickets and makes an empty one active, which the memory layer moves into; activate
    brings the kept one back as it was; collapse carries the map as it is now without overlay records; remove-base
    keeps a copy and refuses the active base; history and promote refuse by name with the reason."""
    from metaform.project import drawn, memory, overlay_records

    def names() -> list[str]:
        found = memory('proj', 'read_graph', {})
        return [one['name'] for one in found['result']['entities']]
    j(run, 'work', 'op=add', 'node=element:code.alarm.audible', 'task=Make it louder.', cwd=in_store)
    memory('proj', 'create_entities', {'entities': [{'name': 'tone', 'entityType': 'fact', 'observations': ['rings']}]})
    whole = drawn('proj')
    assert [(one['name'], one['active'], one['mapped']) for one in j(run, 'bases', cwd=in_store)['results']] == [
        ('main', True, True)]
    made = j(run, 'add-base', 'name=fresh', '--confirm', cwd=in_store)
    assert (made['name'], made['active']) == ('fresh', True) and 'main is kept whole with 1 tickets record' in str(made)
    assert drawn('proj')['elements'] == [] and not overlay_records('proj', 'tickets') and names() == ['tone']
    memory('proj', 'create_entities', {'entities': [{'name': 'snooze', 'entityType': 'fact', 'observations': ['x']}]})
    again = run('map', 'activate', 'name=fresh', cwd=in_store, ok=False)
    assert 'already the active map' in again.stdout + again.stderr
    j(run, 'activate', 'name=main', '--confirm', cwd=in_store)
    assert drawn('proj') == whole and len(overlay_records('proj', 'tickets') or []) == 1
    assert names() == ['tone', 'snooze']
    collapsed = j(run, 'collapse', 'name=fresh', '--confirm', cwd=in_store)
    assert collapsed['name'] == 'fresh-2' and 'already has a base named fresh' in str(collapsed)
    now = drawn('proj')
    assert (now['elements'], now['wants']) == (whole['elements'], whole['wants'])
    assert 'tickets' in [one['key'] for one in now['overlays']] and not overlay_records('proj', 'tickets')
    listed = j(run, 'bases', cwd=in_store)['results']
    assert [(one['name'], one['active'], one['mapped']) for one in listed] == [
        ('main', False, True), ('fresh', False, False), ('fresh-2', True, True)]
    refused = run('map', 'remove-base', 'name=fresh-2', '--confirm', cwd=in_store, ok=False)
    assert 'not removed while it is active' in refused.stdout + refused.stderr
    removed = j(run, 'remove-base', 'name=fresh', '--confirm', cwd=in_store)
    assert Path(removed['kept']).exists() and [one['name'] for one in j(run, 'bases', cwd=in_store)['results']] == [
        'main', 'fresh-2']
    history = run('map', 'history', 'id=code.alarm.audible', cwd=in_store, ok=False)
    assert 'no earlier version' in history.stdout + history.stderr
    promote = run('map', 'promote', 'receiver=code.timer.kitchen', 'provider=code.alarm.audible',
                  'address=code.countdown.delivery', cwd=in_store, ok=False)
    assert 'no field to name an element of its own' in promote.stdout + promote.stderr


@pytest.mark.req('MAP-021')
def test_a_scoped_address_reads_what_one_layer_holds_there(run, kitchen):
    """`<scope>@<layer>` reads the layer at an Address, or at a join `<receiver>:<provider>`; a hidden layer resolves
    to nothing."""
    held = code(run, kitchen, 'where', 'code.alarm.audible@sources')
    assert held['element']['role'] == 'SE' and held['items'][0]['refs'] == ['path=kitchen/alarm.py']
    join = code(run, kitchen, 'where', 'code.timer.kitchen:code.alarm.audible@sources')
    assert join['scope'] == 'code.timer.kitchen:code.alarm.audible@sources' and join['items'] == []
    run('map', 'hide', 'sources', '--confirm', cwd=kitchen)
    hidden = code(run, kitchen, 'where', 'code.alarm.audible@sources', ok=False)
    assert 'resolves to nothing' in hidden.stdout + hidden.stderr


def test_explicit_work_receiver_keeps_its_source_before_incidental_relationship_detail(tmp_path):
    from types import SimpleNamespace

    from metaform.module import Context
    from metaform.modules.map import _fitted, _size

    data = {'kind': 'element', 'element': {'address': 'code.hub'}, 'provides': [
        {'receiver': 'receiver.first', 'purpose': 'An adjacent purpose.', 'sources': ['path=' + 'x' * 500]},
        {'receiver': 'receiver.governing', 'purpose': 'The linked outcome.', 'sources': ['path=governing.py']}]}
    result = _fitted(Context('map', tmp_path), SimpleNamespace(join=None), data, {}, _size(data) - 300,
                     focus=('receiver.governing',))
    assert result['provides'][-1]['sources'] == ['path=governing.py']
    assert 'sources' not in result['provides'][0]
    assert result['provides'][0]['purpose'] == 'An adjacent purpose.'
