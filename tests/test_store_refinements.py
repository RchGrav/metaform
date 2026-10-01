"""Refining the metaform: every change is a new version in its own intake layer, and no change makes a layer,
LAYER-025."""
from __future__ import annotations

import pytest
from storekit import dump, intake, knowledge, memory, small_map, store_file, values

from metaform.data import Node

pytestmark = pytest.mark.kind('fixture')


def layer_names(store):
    return [layer.name for layer in store.layers().results]


@pytest.mark.req('LAYER-025')
@pytest.mark.req('STORE-009')
def test_each_refinement_is_a_version_in_the_intake_layer_and_makes_no_layer(store):
    _, outer, _ = small_map(store)
    before = layer_names(store)
    first = store.refine(outer.join_id, {'purpose': 'Know when each dish is ready.'}, reason='wording')
    assert first.notices == ()
    store.refine(outer.join_id, {'purpose': 'Serve each dish on time.'}, reason='sharper', evidence='the menu')
    assert store.joins('stakeholder.cook.home').results[0].purpose == 'Serve each dish on time.'
    assert [(version.layer, version.op, version.fields['purpose'], version.reason, version.evidence)
            for version in store.history(outer.join_id).results] == [
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
    refused = store.refine(element.element_id, {'role': 'DE'}, reason='r')
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
@pytest.mark.req('MAP-020')
def test_a_refinement_changes_an_elements_name_length_and_role_and_a_joins_name(store):
    _, outer, _ = small_map(store)
    kitchen = store.element('code.timer.kitchen').element_id
    store.refine(kitchen, {'name_length': 1, 'role': 'SE'}, reason='one word says it')
    store.refine(outer.join_id, {'name': 'dish timer'}, reason='what the cook calls it')
    element = store.element('code.timer.kitchen')
    assert (element.element_id, element.name_length, element.role, element.short_name) == (kitchen, 1, 'SE', 'kitchen')
    assert store.joins('stakeholder.cook.home').results[0].name == 'dish timer'
    assert [(version.layer, version.fields['role'], version.fields['name_length'])
            for version in store.history(kitchen).results] == [('intake-1', 'DE', 2), ('intake-1', 'SE', 1)]
    assert [entry.element.address for entry in store.roots().entry] == ['stakeholder.cook.home']


@pytest.mark.req('LAYER-025')
@pytest.mark.req('STORE-009')
def test_address_lookup_returns_the_newest_refinement(store):
    small_map(store)
    element_id = store.element('code.alarm.audible').element_id
    store.refine(element_id, {'role': 'NE'}, reason='it states a demand')
    store.refine(element_id, {'role': 'DE', 'name_length': 1}, reason='it defines the timer')
    found = store.element('code.alarm.audible')
    assert (found.element_id, found.role, found.name_length) == (element_id, 'DE', 1)


@pytest.mark.req('LAYER-025')
@pytest.mark.req('STORE-034')
def test_a_removed_join_is_gone_from_every_read_and_kept_in_history(store):
    _, outer, inner = small_map(store)
    store.refine(inner.join_id, remove=True, reason='not a real join')
    assert store.joins('code.timer.kitchen').results == ()
    assert store.joins('code.timer.kitchen', raw=True).results == ()
    assert store.identity('code.alarm.audible').results == ()
    assert [version.op for version in store.history(inner.join_id).results] == ['add', 'remove']


@pytest.mark.req('LAYER-025')
@pytest.mark.req('STORE-034')
def test_removing_an_element_orphans_knowledge_on_it_and_putting_it_back_restores_it(home, store):
    small_map(store)
    alarm = store.element('code.alarm.audible')
    notes = knowledge(store, 'notes')
    item = store.add_item(notes.name, Node('element', alarm.element_id), 'too loud at night')
    store.add_property(notes.name, alarm.element_id, 'hardware')
    store.finish(notes.name)
    knowledge_rows = {name: rows for name, rows in dump(store_file(home, store)).items()
                      if name in ('items', 'properties')}
    store.refine(alarm.element_id, remove=True, reason='not part of the artifact')
    for join in store.joins(alarm.element_id, as_='provider').results:
        store.refine(join.join_id, remove=True, reason='its provider is gone')
    assert [version.op for version in store.history(alarm.element_id).results] == ['add', 'remove']
    assert store.node(Node('element', alarm.element_id)) is None
    raw = store.node(Node('element', alarm.element_id), raw=True)
    orphans = [entry for group in raw.layers for entry in group.items if entry.item_id == item.item_id]
    assert orphans and orphans[0].orphaned is True
    restored = store.add_element('intake-1', 'code.alarm.audible')
    assert store.element('code.alarm.audible').element_id == alarm.element_id == restored.element_id
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
    store.add_item(notes.name, Node('element', kitchen.element_id), 'rings twice')
    before = dump(store_file(home, store))
    address = store.refine(kitchen.element_id, {'address': 'code.timer.egg'}, reason='egg timer')
    colour = store.refine(kitchen.element_id, {'colour': 'blue'}, reason='no')
    assert [notice.where for notice in address.notices] == ['address']
    assert 'cannot be moved' in address.notices[0].message
    assert [notice.where for notice in colour.notices] == ['colour']
    assert dump(store_file(home, store)) == before
    both = store.refine(kitchen.element_id, {'address': 'code.timer.egg', 'role': 'SE'}, reason='r')
    assert [notice.where for notice in both.notices] == ['address']
    assert (both.fields['address'], both.fields['role']) == ('code.timer.kitchen', 'SE')
    assert store.element('code.timer.egg') is None
    found = store.element('code.timer.kitchen')
    assert (found.element_id, found.role) == (kitchen.element_id, 'SE')
    assert values(store.node(Node('element', 'code.timer.kitchen')), 'memory') == ['rings twice']


@pytest.mark.req('LAYER-025')
@pytest.mark.req('STORE-034')
def test_a_removal_that_leaves_a_join_behind_orphans_it_and_names_it(store):
    _, _, inner = small_map(store)
    alarm = store.element('code.alarm.audible')
    removed = store.refine(alarm.element_id, remove=True, reason='gone')
    assert inner.join_id in ' '.join(notice.message for notice in removed.notices)
    assert store.element('code.alarm.audible') is None
    assert store.joins('code.timer.kitchen').results == ()
    orphan = store.joins('code.timer.kitchen', raw=True).results[0]
    assert orphan.join_id == inner.join_id and orphan.orphaned


@pytest.mark.req('LAYER-025')
@pytest.mark.req('STORE-034')
@pytest.mark.req('MAP-003')
def test_a_refinement_moves_a_join_to_another_receiver_and_what_is_attached_stays_with_it(home, store):
    _, _, inner = small_map(store)
    notes = knowledge(store, 'notes')
    store.add_item(notes.name, Node('join', inner.join_id), 'rings too long')
    store.finish(notes.name)
    knowledge_rows = {row for row in dump(store_file(home, store))['items']}
    moved = store.refine(inner.join_id, {'receiver': 'stakeholder.cook.home'}, reason='the cook hears it')
    assert moved.notices == ()
    assert inner.join_id in [join.join_id for join in store.joins('stakeholder.cook.home').results]
    assert store.joins('code.timer.kitchen').results == ()
    assert values(store.node(Node('join', inner.join_id)), 'notes') == ['rings too long']
    assert {row for row in dump(store_file(home, store))['items']} == knowledge_rows
    assert [(version.layer, version.op) for version in store.history(inner.join_id).results] == [
        ('intake-1', 'add'), ('intake-1', 'change')]


@pytest.mark.req('LAYER-025')
@pytest.mark.req('STORE-034')
@pytest.mark.req('MAP-030')
def test_a_refinement_absorbs_a_join_into_its_parents_join(store):
    with store.atomic():
        base = intake(store)
        store.add_element(base.name, 'stakeholder.cook', role='CQU')
        store.add_element(base.name, 'code.timer', role='DE')
        store.add_element(base.name, 'code.alarm', role='SE')
        parent = store.add_join(base.name, 'stakeholder.cook', 'code.timer', purpose='Know when a dish is done.',
                                ef='Counts down and rings.', relation='r', observation='o')
        part = store.add_join(base.name, 'stakeholder.cook', 'code.alarm', purpose='Hear the end.', ef='Rings.',
                              relation='r', observation='o')
    store.refine(part.join_id, {'parent': parent.join_id}, reason='the alarm is part of the timer')
    assert [join.join_id for join in store.joins('stakeholder.cook').results] == [parent.join_id]
    held = store.subtypes(parent.join_id).results
    assert [(sub.join_id, sub.address, sub.purpose, sub.extra) for sub in held] == [
        (part.join_id, 'code.alarm', 'Hear the end.', None)]  # absorbed, it keeps its purpose as its own, STORE-011
    assert 'code.alarm' not in [root.address for root in store.roots().elements]


@pytest.mark.req('LAYER-025')
@pytest.mark.req('MAP-015')
@pytest.mark.req('STORE-007')
def test_the_metaform_grows_an_element_at_a_better_address_and_a_join_moves_to_it(store):
    _, _, inner = small_map(store)
    alarm = store.element('code.alarm.audible')
    notes = memory(store)
    store.add_item(notes.name, Node('join', inner.join_id), 'rings too long')
    store.add_item(notes.name, Node('element', alarm.element_id), 'a piezo')
    before = layer_names(store)
    better = store.add_element('intake-1', 'code.alarm.audible.tone', name_length=2, role='SE')
    store.refine(inner.join_id, {'provider': 'code.alarm.audible.tone'}, reason='it plays a tone')
    assert layer_names(store) == before
    moved = store.joins('code.timer.kitchen').results
    assert [(join.join_id, join.provider_address) for join in moved] == [(inner.join_id, 'code.alarm.audible.tone')]
    assert store.element('code.alarm.audible.tone').element_id == better.element_id
    assert store.element('code.alarm.audible.tone').layer == 'intake-1'
    assert values(store.node(Node('join', inner.join_id)), 'memory') == ['rings too long']
    assert store.element('code.alarm.audible').element_id == alarm.element_id
    assert values(store.node(Node('element', 'code.alarm.audible')), 'memory') == ['a piezo']


@pytest.mark.req('LAYER-025')
def test_the_finished_metaform_takes_new_joins_and_their_refs(store):
    small_map(store)
    before = layer_names(store)
    added = store.add_join('intake-1', 'stakeholder.cook.home', 'code.alarm.audible', purpose='Hear it.',
                           ef='Rings.', relation='The alarm tells the cook.', observation='Loud.')
    assert added.notices == () and added.layer == 'intake-1'
    store.add_ref(added.join_id, 'path', 'src/alarm.c')
    found = {join.join_id: join for join in store.joins('stakeholder.cook.home').results}[added.join_id]
    assert [(ref.key, ref.value) for ref in found.refs] == [('path', 'src/alarm.c')]
    assert layer_names(store) == before


@pytest.mark.req('LAYER-025')
def test_the_finished_metaform_takes_new_subtype_joins_and_properties(store):
    _, outer, _ = small_map(store)
    before = layer_names(store)
    held = store.add_subtype('intake-1', outer.join_id, 'code.timer.kitchen.dial', purpose='Set the time.',
                             ef='Turns to a number of minutes.', role='SE', name_length=1)
    assert held.layer == 'intake-1'
    assert held.join_id in [sub.join_id for sub in store.subtypes(outer.join_id).results]
    added = store.add_property('intake-1', 'code.timer', 'battery powered')
    assert added.layer == 'intake-1'
    assert 'battery powered' in [prop.value for prop in store.context('code.timer.kitchen').applying]
    assert layer_names(store) == before


@pytest.mark.req('LAYER-025')
@pytest.mark.req('STORE-012')
def test_a_refined_ref_list_keeps_the_old_version_whole(store):
    with store.atomic():
        base = intake(store)
        store.add_element(base.name, 'code.a', role='DE')
        store.add_element(base.name, 'code.b', role='SE')
        join = store.add_join(base.name, 'code.a', 'code.b', purpose='p', ef='f', relation='r',
                              observation='o', refs=[('path', 'a'), ('path', 'b')])
    store.refine(join.join_id, {'refs': [('path', 'b')]}, reason='a is stale')
    assert [(ref.key, ref.value) for ref in store.joins('code.a').results[0].refs] == [('path', 'b')]
    first = store.history(join.join_id).results[0]
    assert [(ref.key, ref.value) for ref in first.refs] == [('path', 'a'), ('path', 'b')]


@pytest.mark.req('LAYER-025')
@pytest.mark.req('STORE-021')
def test_extension_fields_survive_a_refinement_that_does_not_touch_them(store):
    with store.atomic():
        base = intake(store)
        store.add_element(base.name, 'code.a', role='DE')
        store.add_element(base.name, 'code.b', role='SE')
        join = store.add_join(base.name, 'code.a', 'code.b', purpose='p', ef='f', relation='r',
                              observation='o', extra={'latency_budget': '5 ms'})
    store.refine(join.join_id, {'purpose': 'q'}, reason='wording')
    assert store.joins('code.a').results[0].extra == {'latency_budget': '5 ms'}


@pytest.mark.req('LAYER-025')
@pytest.mark.req('STORE-036')
def test_a_refinement_marks_the_layers_built_from_what_it_changed(store):
    _, outer, _ = small_map(store)
    built = knowledge(store, 'challenge', sources=('intake-1',))
    unrelated = knowledge(store, 'other')
    store.finish(built.name)
    store.finish(unrelated.name)
    store.refine(outer.join_id, {'purpose': 'new'}, reason='r')
    marked = {layer.name: layer.reexamine for layer in store.layers().results}
    assert marked['challenge'] is True and marked['other'] is False
    store.reexamined(built.name)
    assert {layer.name: layer.reexamine for layer in store.layers().results}['challenge'] is False


@pytest.mark.req('LAYER-025')
@pytest.mark.req('MAP-020')
def test_a_joins_and_a_subtypes_perspective_is_kept_through_every_refinement_and_move(store):
    with store.atomic():
        base = intake(store)
        store.add_element(base.name, 'code.a', role='DE')
        store.add_element(base.name, 'code.b', role='SE')
        join = store.add_join(base.name, 'code.a', 'code.b', purpose='p', ef='f', perspective='Encounter', relation='r',
                              observation='o')
        tick = store.add_subtype(base.name, join.join_id, 'code.loop.tick', ef='g', perspective='Function',
                                 relation='r', observation='o', role='SE')
    assert (join.perspective, tick.perspective, join.notices, tick.notices) == ('Encounter', 'Function', (), ())
    store.refine(join.join_id, {'purpose': 'q'}, reason='wording')
    store.refine(tick.join_id, {'perspective': 'Encounter'}, reason='relabel')
    kept = store.joins('code.a').results[0]
    assert (kept.purpose, kept.perspective, store.subtypes(kept.join_id).results[0].perspective) == ('q', 'Encounter', 'Encounter')
    store.add_element('intake-1', 'code.c', role='DE')
    store.refine(join.join_id, {'receiver': 'code.c'}, reason='moved')
    moved = store.history(join.join_id).results[-1]
    assert (moved.op, moved.fields['perspective']) == ('change', 'Encounter')
    assert [sub.perspective for sub in store.subtypes(store.joins('code.c').results[0].join_id).results] == ['Encounter']


@pytest.mark.req('MAP-020')
@pytest.mark.req('BASE-044')
def test_ef_holds_only_function_or_encounter_and_any_other_word_is_kept_in_extra_with_a_notice(store):
    with store.atomic():
        base = intake(store)
        store.add_element(base.name, 'code.a', role='DE')
        store.add_element(base.name, 'code.b', role='SE')
        join = store.add_join(base.name, 'code.a', 'code.b', purpose='p', ef='f', perspective='Both', relation='r',
                              observation='o')
        tick = store.add_subtype(base.name, join.join_id, 'code.loop.tick', ef='g', perspective='ef',
                                 relation='r', observation='o', role='SE')
    assert (join.perspective, join.extra, [notice.where for notice in join.notices]) == (None, {'perspective': 'Both'}, ['perspective'])
    assert (tick.perspective, tick.extra, [notice.where for notice in tick.notices]) == (None, {'perspective': 'ef'}, ['perspective'])
    stored = store.joins('code.a').results[0]
    stored_tick = store.subtypes(stored.join_id).results[0]
    assert (stored.perspective, stored.extra, stored_tick.perspective, stored_tick.extra) == (None, {'perspective': 'Both'}, None, {'perspective': 'ef'})


@pytest.mark.req('LAYER-025')
@pytest.mark.req('MAP-020')
def test_a_joins_and_a_subtypes_verb_is_stored_as_given_and_kept_through_refinements_and_moves(store):
    with store.atomic():
        base = intake(store)
        store.add_element(base.name, 'code.a', role='DE')
        store.add_element(base.name, 'code.b', role='SE')
        join = store.add_join(base.name, 'code.a', 'code.b', purpose='p', ef='f', perspective='Encounter',
                              relation='People drive the a through the b.', verb='drive', observation='o')
        tick = store.add_subtype(base.name, join.join_id, 'code.loop.tick', ef='g', perspective='Function',
                                 relation='The tick loop advances every countdown.', verb='advances', observation='o',
                                 role='SE')
    assert (join.verb, tick.verb, join.notices, tick.notices) == ('drive', 'advances', (), ())
    store.refine(join.join_id, {'purpose': 'q'}, reason='wording')
    store.refine(tick.join_id, {'verb': 'moves'}, reason='plainer')
    kept = store.joins('code.a').results[0]
    assert (kept.purpose, kept.verb, store.subtypes(kept.join_id).results[0].verb) == ('q', 'drive', 'moves')
    store.add_element('intake-1', 'code.c', role='DE')
    store.refine(join.join_id, {'receiver': 'code.c'}, reason='moved')
    assert store.history(join.join_id).results[-1].fields['verb'] == 'drive'
    assert store.history(tick.join_id).results[-1].fields['verb'] == 'moves'


@pytest.mark.req('LAYER-025')
@pytest.mark.req('MAP-032')
@pytest.mark.req('STORE-034')
def test_a_refinement_absorbing_a_join_that_holds_a_subtype_join_passes_it_to_the_new_parent(store):
    with store.atomic():
        base = intake(store)
        store.add_element(base.name, 'stakeholder.cook', role='CQU')
        store.add_element(base.name, 'code.timer', role='DE')
        store.add_element(base.name, 'code.alarm', role='SE')
        parent = store.add_join(base.name, 'stakeholder.cook', 'code.timer', purpose='Know when a dish is done.',
                                ef='Counts down and rings.', relation='r', observation='o')
        part = store.add_join(base.name, 'stakeholder.cook', 'code.alarm', purpose='Hear the end.', ef='Rings.',
                              relation='r', observation='o')
        piezo = store.add_subtype(base.name, part.join_id, 'code.alarm.piezo', ef='Buzzes.', role='SE',
                                  refs=[('path', 'src/piezo.c')])
    absorbed = store.refine(part.join_id, {'parent': parent.join_id}, reason='the alarm is the timer\'s')
    assert piezo.join_id in ' '.join(notice.message for notice in absorbed.notices)
    assert sorted(sub.join_id for sub in store.subtypes(parent.join_id).results) == sorted(
        [part.join_id, piezo.join_id])
    moved = {sub.join_id: sub for sub in store.subtypes(parent.join_id).results}[piezo.join_id]
    assert (moved.parent, moved.ef, [(ref.key, ref.value) for ref in moved.refs]) == (
        parent.join_id, 'Buzzes.', [('path', 'src/piezo.c')])
    assert [(version.layer, version.op, version.fields['parent']) for version in store.history(piezo.join_id).results] \
        == [('intake-1', 'add', part.join_id), ('intake-1', 'change', parent.join_id)]
