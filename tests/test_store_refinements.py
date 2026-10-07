"""Refining the metaform: every change is a new version in its own intake layer, and no change makes a layer,
LAYER-025."""
from __future__ import annotations

import pytest
from storekit import dump, knowledge, memory, ops, small_map, store_file, values

from metaform.data import Node

pytestmark = pytest.mark.kind('fixture')


def layer_names(store):
    return [layer.name for layer in store.layers().results]


@pytest.mark.req('LAYER-025')
@pytest.mark.req('STORE-009')
def test_each_refinement_is_a_version_in_the_intake_layer_and_makes_no_layer(store):
    _, outer, _ = small_map(store)
    before = layer_names(store)
    first = store.refine(outer.id, {'purpose': 'Know when each dish is ready.'}, reason='wording')
    assert first.notices == ()
    store.refine(outer.id, {'purpose': 'Serve each dish on time.'}, reason='sharper', evidence='the menu')
    assert store.joins('stakeholder.cook.home').results[0].purpose == 'Serve each dish on time.'
    assert [(version.layer, version.op, version.fields['purpose'], version.reason, version.evidence)
            for version in store.history(outer.id).results] == [
        ('intake-1', 'add', 'Know when each dish is done.', None, None),
        ('intake-1', 'change', 'Know when each dish is ready.', 'wording', None),
        ('intake-1', 'change', 'Serve each dish on time.', 'sharper', 'the menu')]
    assert layer_names(store) == before
    assert store.joins('stakeholder.cook.home').results[0].layer == 'intake-1'


@pytest.mark.req('LAYER-025')
def test_a_refinement_with_no_intake_to_refine_writes_nothing_and_says_why(home, store):
    notes = knowledge(store, 'notes')
    element = store.add_element(notes.name, 'code.a')
    before = dump(store_file(home, store))
    refused = store.refine(element.id, {'role': 'DE'}, reason='r')
    assert [notice.where for notice in refused.notices] == ['id']
    assert dump(store_file(home, store)) == before


@pytest.mark.req('LAYER-025')
def test_the_kind_correction_is_not_a_layer_kind(store):
    small_map(store)
    with pytest.raises(Exception, match='not a layer kind'):
        store.layer('fix-1', 'test', 'Fixes.', kind='correction', mutable=False, hideable=False)


@pytest.mark.req('LAYER-025')
@pytest.mark.req('STORE-034')
@pytest.mark.req('STORE-025')
def test_a_refinement_changes_an_elements_name_length_role_and_name(store):
    small_map(store)
    kitchen = store.element('code.timer.kitchen').id
    store.refine(kitchen, {'name_length': 1, 'role': 'SE'}, reason='one word says it')
    store.refine(kitchen, {'name': 'dish timer'}, reason='what the cook calls it')
    element = store.element('code.timer.kitchen')
    assert (element.id, element.name_length, element.role, element.short_name) == (kitchen, 1, 'SE', 'kitchen')
    assert element.name == 'dish timer'
    assert [(version.layer, version.fields['role'], version.fields['name_length'])
            for version in store.history(kitchen).results] == [('intake-1', 'DE', 2), ('intake-1', 'SE', 1),
                                                               ('intake-1', 'SE', 1)]
    assert [entry.element.address for entry in store.roots().entry] == ['stakeholder.cook.home']


@pytest.mark.req('LAYER-025')
@pytest.mark.req('STORE-009')
def test_address_lookup_returns_the_newest_refinement(store):
    small_map(store)
    element_id = store.element('code.alarm.audible').id
    store.refine(element_id, {'role': 'NE'}, reason='it states a demand')
    store.refine(element_id, {'role': 'DE', 'name_length': 1}, reason='it defines the timer')
    found = store.element('code.alarm.audible')
    assert (found.id, found.role, found.name_length) == (element_id, 'DE', 1)


@pytest.mark.req('LAYER-025')
@pytest.mark.req('STORE-034')
def test_a_removed_join_is_gone_from_every_read_and_kept_in_history(store):
    _, _outer, inner = small_map(store)
    store.refine(inner.id, remove=True, reason='not a real join')
    assert store.joins('code.timer.kitchen').results == ()
    assert store.joins('code.timer.kitchen', raw=True).results == ()
    assert store.identity('code.alarm.audible').results == ()
    assert [version.op for version in store.history(inner.id).results] == ['add', 'remove']


@pytest.mark.req('LAYER-025')
@pytest.mark.req('STORE-034')
def test_removing_an_element_orphans_knowledge_on_it_and_putting_it_back_restores_it(home, store):
    small_map(store)
    alarm = store.element('code.alarm.audible')
    notes = knowledge(store, 'notes')
    item = store.add_item(notes.name, Node('element', alarm.id), 'too loud at night')
    store.add_property(notes.name, alarm.id, 'hardware')
    store.finish(notes.name)
    knowledge_rows = {name: rows for name, rows in dump(store_file(home, store)).items()
                      if name in ('items', 'properties')}
    store.refine(alarm.id, remove=True, reason='not part of the artifact')
    for join in store.joins(alarm.id, as_='provider').results:
        store.refine(join.id, remove=True, reason='its provider is gone')
    assert [version.op for version in store.history(alarm.id).results] == ['add', 'remove']
    assert store.node(Node('element', alarm.id)) is None
    raw = store.node(Node('element', alarm.id), raw=True)
    orphans = [entry for group in raw.layers for entry in group.items if entry.id == item.id]
    assert orphans and orphans[0].orphaned is True
    restored = store.add_element('intake-1', 'code.alarm.audible')
    assert store.element('code.alarm.audible').id == alarm.id == restored.id
    assert values(store.node(Node('element', 'code.alarm.audible')), 'notes') == ['too loud at night']
    assert [prop.value for prop in store.context('code.alarm.audible').applying] == ['hardware']
    after = {name: rows for name, rows in dump(store_file(home, store)).items() if name in ('items', 'properties')}
    assert after == knowledge_rows


@pytest.mark.req('LAYER-025')
@pytest.mark.req('STORE-034')
@pytest.mark.req('MAP-015')
def test_a_refinement_never_moves_an_element_and_names_the_address_it_did_not_apply(home, store):
    small_map(store)
    kitchen = store.element('code.timer.kitchen')
    notes = memory(store)
    store.add_item(notes.name, Node('element', kitchen.id), 'rings twice')
    before = dump(store_file(home, store))
    address = store.refine(kitchen.id, {'address': 'code.timer.egg'}, reason='egg timer')
    colour = store.refine(kitchen.id, {'colour': 'blue'}, reason='no')
    assert [notice.where for notice in address.notices] == ['address']
    assert 'cannot be moved' in address.notices[0].message
    assert [notice.where for notice in colour.notices] == ['colour']
    assert dump(store_file(home, store)) == before
    both = store.refine(kitchen.id, {'address': 'code.timer.egg', 'role': 'SE'}, reason='r')
    assert [notice.where for notice in both.notices] == ['address']
    assert (both.fields['address'], both.fields['role']) == ('code.timer.kitchen', 'SE')
    assert store.element('code.timer.egg') is None
    found = store.element('code.timer.kitchen')
    assert (found.id, found.role) == (kitchen.id, 'SE')
    assert values(store.node(Node('element', 'code.timer.kitchen')), 'memory') == ['rings twice']


@pytest.mark.req('LAYER-025')
@pytest.mark.req('STORE-034')
def test_a_removal_that_leaves_a_join_behind_orphans_it_and_names_it(store):
    _, _, inner = small_map(store)
    alarm = store.element('code.alarm.audible')
    removed = store.refine(alarm.id, remove=True, reason='gone')
    assert inner.id in ' '.join(notice.message for notice in removed.notices)
    assert store.element('code.alarm.audible') is None
    assert store.joins('code.timer.kitchen').results == ()
    orphan = store.joins('code.timer.kitchen', raw=True).results[0]
    assert orphan.id == inner.id and orphan.orphaned


@pytest.mark.req('LAYER-025')
@pytest.mark.req('STORE-034')
@pytest.mark.req('MAP-003')
def test_a_refinement_moves_a_join_to_another_receiver_and_what_is_attached_stays_with_it(home, store):
    _, _, inner = small_map(store)
    notes = knowledge(store, 'notes')
    store.add_item(notes.name, Node('join', inner.id), 'rings too long')
    store.finish(notes.name)
    knowledge_rows = {op['seq'] for op in ops(store_file(home, store), 'item')}
    moved = store.refine(inner.id, {'receiver': 'stakeholder.cook.home'}, reason='the cook hears it')
    assert moved.notices == ()
    assert inner.id in [join.id for join in store.joins('stakeholder.cook.home').results]
    assert store.joins('code.timer.kitchen').results == ()
    assert values(store.node(Node('join', inner.id)), 'notes') == ['rings too long']
    assert {op['seq'] for op in ops(store_file(home, store), 'item')} == knowledge_rows
    assert [(version.layer, version.op) for version in store.history(inner.id).results] == [
        ('intake-1', 'add'), ('intake-1', 'change')]



@pytest.mark.req('LAYER-025')
@pytest.mark.req('MAP-015')
@pytest.mark.req('STORE-007')
def test_the_metaform_grows_an_element_at_a_better_address_and_a_join_moves_to_it(store):
    _, _, inner = small_map(store)
    alarm = store.element('code.alarm.audible')
    notes = memory(store)
    store.add_item(notes.name, Node('join', inner.id), 'rings too long')
    store.add_item(notes.name, Node('element', alarm.id), 'a piezo')
    before = layer_names(store)
    better = store.add_element('intake-1', 'code.alarm.audible.tone', name_length=2, role='SE')
    store.refine(inner.id, {'elements': ['code.alarm.audible.tone']}, reason='it plays a tone')
    assert layer_names(store) == before
    moved = store.joins('code.timer.kitchen').results
    assert [(join.id, [each.address for each in join.elements]) for join in moved] == [
        (inner.id, ['code.alarm.audible.tone'])]
    assert store.element('code.alarm.audible.tone').id == better.id
    assert store.element('code.alarm.audible.tone').layer == 'intake-1'
    assert values(store.node(Node('join', inner.id)), 'memory') == ['rings too long']
    assert store.element('code.alarm.audible').id == alarm.id
    assert values(store.node(Node('element', 'code.alarm.audible')), 'memory') == ['a piezo']


@pytest.mark.req('LAYER-025')
def test_the_finished_metaform_takes_new_joins(store):
    small_map(store)
    before = layer_names(store)
    added = store.add_join('intake-1', 'stakeholder.cook.home', 'code.alarm.audible', purpose='Hear it.',
                           ef='Rings.')
    assert added.notices == () and added.layer == 'intake-1'
    found = {join.id: join for join in store.joins('stakeholder.cook.home').results}[added.id]
    assert [each.address for each in found.elements] == ['code.alarm.audible']
    assert layer_names(store) == before


@pytest.mark.req('LAYER-025')
def test_the_finished_metaform_takes_new_elements_held_by_its_joins_and_properties(store):
    _, outer, _ = small_map(store)
    before = layer_names(store)
    dial = store.add_element('intake-1', 'code.timer.kitchen.dial', role='SE', name_length=1)
    assert dial.layer == 'intake-1'
    store.refine(outer.id, {'elements': ['code.timer.kitchen', 'code.loop.tick', 'code.timer.kitchen.dial']},
                 reason='the dial sets the time')
    held = store.joins('stakeholder.cook.home').results[0].elements
    assert [each.address for each in held] == ['code.timer.kitchen', 'code.loop.tick', 'code.timer.kitchen.dial']
    added = store.add_property('intake-1', 'code.timer', 'battery powered')
    assert added.layer == 'intake-1'
    assert 'battery powered' in [prop.value for prop in store.context('code.timer.kitchen').applying]
    assert layer_names(store) == before




@pytest.mark.req('LAYER-025')
@pytest.mark.req('STORE-036')
def test_a_refinement_marks_the_layers_built_from_what_it_changed(store):
    _, outer, _ = small_map(store)
    built = knowledge(store, 'challenge', sources=('intake-1',))
    unrelated = knowledge(store, 'other')
    store.finish(built.name)
    store.finish(unrelated.name)
    store.refine(outer.id, {'purpose': 'new'}, reason='r')
    marked = {layer.name: layer.reexamine for layer in store.layers().results}
    assert marked['challenge'] is True and marked['other'] is False
    store.reexamined(built.name)
    assert {layer.name: layer.reexamine for layer in store.layers().results}['challenge'] is False

