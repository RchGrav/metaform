"""The correction stack: the only way to change the metaform, applied in order, peeled only from the top."""
from __future__ import annotations

import pytest
from storekit import correction, dump, intake, knowledge, memory, small_map, store_file, values

from metaform.data import Node

pytestmark = pytest.mark.kind('fixture')

KITCHEN = Node('element', 'code.timer.kitchen')


def reads(store):
    """What agents read about the small map, in context."""
    kitchen = store.element('code.timer.kitchen')
    return {
        'kitchen': kitchen.to_dict() if kitchen else None,
        'owned': [join.to_dict() for join in store.joins('code.timer.kitchen').results] if kitchen else None,
        'cook': [join.to_dict() for join in store.joins('stakeholder.cook.home').results],
        'node': store.node(KITCHEN).to_dict() if kitchen else None,
    }


@pytest.mark.req('STORE-017')
@pytest.mark.req('STORE-009')
@pytest.mark.req('LAYER-011')
def test_later_corrections_win_and_history_keeps_every_version(store):
    _, outer, _ = small_map(store)
    first = correction(store, 'fix-1')
    store.correct(first.name, outer.join_id, {'purpose': 'Know when each dish is ready.'}, reason='wording')
    store.finish(first.name)
    second = correction(store, 'fix-2')
    store.correct(second.name, outer.join_id, {'purpose': 'Serve each dish on time.'}, reason='sharper')
    store.finish(second.name)
    assert store.joins('stakeholder.cook.home').results[0].purpose == 'Serve each dish on time.'
    history = store.history(outer.join_id).results
    assert [(version.layer, version.op, version.fields['purpose']) for version in history] == [
        ('intake-1', 'add', 'Know when each dish is done.'),
        ('fix-1', 'change', 'Know when each dish is ready.'),
        ('fix-2', 'change', 'Serve each dish on time.')]
    assert [version.position for version in history] == [None, 1, 2]
    assert [layer.name for layer in store.stack().results] == ['fix-1', 'fix-2']


@pytest.mark.req('STORE-034')
@pytest.mark.req('STORE-009')
@pytest.mark.req('STORE-025')
@pytest.mark.req('MAP-020')
def test_a_correction_changes_an_elements_name_length_and_role_and_a_joins_name(store):
    _, outer, _ = small_map(store)
    kitchen = store.element('code.timer.kitchen').element_id
    fix = correction(store, 'fix-1')
    store.correct(fix.name, kitchen, {'name_length': 1, 'role': 'SE'}, reason='one word says it')
    store.correct(fix.name, outer.join_id, {'name': 'dish timer'}, reason='what the cook calls it')
    store.finish(fix.name)
    element = store.element('code.timer.kitchen')
    assert (element.element_id, element.name_length, element.role, element.short_name) == (kitchen, 1, 'SE', 'kitchen')
    assert store.joins('stakeholder.cook.home').results[0].name == 'dish timer'
    assert [(version.layer, version.fields['role'], version.fields['name_length'])
            for version in store.history(kitchen).results] == [('intake-1', 'DE', 2), ('fix-1', 'SE', 1)]
    assert [entry.element.address for entry in store.roots().entry] == ['stakeholder.cook.home']
    store.peel(fix.name)
    assert store.element('code.timer.kitchen', raw=True).role == 'DE'
    assert store.joins('stakeholder.cook.home', raw=True).results[0].name == 'kitchen timer'


@pytest.mark.req('STORE-009')
def test_address_lookup_returns_the_highest_correction(store):
    small_map(store)
    element_id = store.element('code.alarm.audible').element_id
    first = correction(store, 'fix-1')
    store.correct(first.name, element_id, {'role': 'NE'}, reason='it states a demand')
    store.finish(first.name)
    second = correction(store, 'fix-2')
    store.correct(second.name, element_id, {'role': 'DE', 'name_length': 1}, reason='it defines the timer')
    store.finish(second.name)
    found = store.element('code.alarm.audible')
    assert (found.element_id, found.role, found.name_length) == (element_id, 'DE', 1)


@pytest.mark.req('STORE-017')
@pytest.mark.req('LAYER-011')
def test_only_the_top_correction_peels_and_peeling_restores_the_reads(home, store):
    _, outer, _ = small_map(store)
    first = correction(store, 'fix-1')
    store.correct(first.name, outer.join_id, {'function': 'Counts down.'}, reason='r1')
    store.finish(first.name)
    between = reads(store)
    second = correction(store, 'fix-2')
    inner = store.joins('code.timer.kitchen').results[0].join_id
    store.correct(second.name, inner, {'receiver': 'stakeholder.cook.home'}, reason='r2')
    store.finish(second.name)
    before = dump(store_file(home, store))
    below = store.peel(first.name)
    assert 'fix-2' in below.notices[0].message
    assert dump(store_file(home, store)) == before
    peeled = store.peel(second.name)
    assert peeled.ready is None
    assert reads(store) == between
    store.finish(second.name)
    assert inner in [join.join_id for join in store.joins('stakeholder.cook.home').results]


@pytest.mark.req('STORE-017')
@pytest.mark.req('LAYER-011')
def test_correction_layers_are_never_toggled(home, store):
    small_map(store)
    fix = correction(store, 'fix-1')
    store.finish(fix.name)
    before = dump(store_file(home, store))
    for act in (lambda: store.select('code', fix.name), lambda: store.mask('code', fix.name),
                lambda: store.hide(fix.name)):
        assert act().notices
    assert dump(store_file(home, store)) == before


@pytest.mark.req('STORE-017')
def test_a_removed_join_is_gone_from_every_read_and_kept_in_history(store):
    _, outer, inner = small_map(store)
    fix = correction(store, 'fix-1')
    store.correct(fix.name, inner.join_id, remove=True, reason='not a real join')
    store.finish(fix.name)
    assert store.joins('code.timer.kitchen').results == ()
    assert store.joins('code.timer.kitchen', raw=True).results == ()
    assert store.identity('code.alarm.audible').results == ()
    assert [version.op for version in store.history(inner.join_id).results] == ['add', 'remove']


@pytest.mark.req('STORE-017')
@pytest.mark.req('STORE-034')
@pytest.mark.req('LAYER-011')
def test_removing_an_element_orphans_knowledge_on_it_and_putting_it_back_restores_it(home, store):
    _, outer, _ = small_map(store)
    alarm = store.element('code.alarm.audible')
    notes = knowledge(store, 'notes')
    item = store.add_item(notes.name, Node('element', alarm.element_id), 'too loud at night')
    store.add_property(notes.name, alarm.element_id, 'hardware')
    store.finish(notes.name)
    knowledge_rows = {name: rows for name, rows in dump(store_file(home, store)).items()
                      if name in ('items', 'properties')}
    fix = correction(store, 'fix-1')
    store.correct(fix.name, alarm.element_id, remove=True, reason='not part of the artifact')
    for join in store.joins(alarm.element_id, as_='provider').results:
        store.correct(fix.name, join.join_id, remove=True, reason='its provider is gone')
    store.finish(fix.name)
    assert store.node(Node('element', alarm.element_id)) is None
    raw = store.node(Node('element', alarm.element_id), raw=True)
    orphans = [entry for group in raw.layers for entry in group.items if entry.item_id == item.item_id]
    assert orphans and orphans[0].orphaned is True
    store.peel(fix.name)
    assert values(store.node(Node('element', alarm.element_id)), 'notes') == ['too loud at night']
    store.discard(fix.name)
    again = correction(store, 'fix-2')
    store.correct(again.name, alarm.element_id, remove=True, reason='gone')
    for join in store.joins(alarm.element_id, as_='provider').results:
        store.correct(again.name, join.join_id, remove=True, reason='its provider is gone')
    store.finish(again.name)
    back = correction(store, 'fix-3')
    restored = store.add_element(back.name, 'code.alarm.audible')
    store.finish(back.name)
    assert store.element('code.alarm.audible').element_id == alarm.element_id == restored.element_id
    assert values(store.node(Node('element', 'code.alarm.audible')), 'notes') == ['too loud at night']
    assert [prop.value for prop in store.context('code.alarm.audible').applying] == ['hardware']
    after = {name: rows for name, rows in dump(store_file(home, store)).items() if name in ('items', 'properties')}
    assert after == knowledge_rows


@pytest.mark.req('STORE-034')
@pytest.mark.req('MAP-015')
def test_a_correction_never_moves_an_element_and_names_the_address_it_did_not_apply(home, store):
    small_map(store)
    kitchen = store.element('code.timer.kitchen')
    notes = memory(store)
    store.add_item(notes.name, Node('element', kitchen.element_id), 'rings twice')
    fix = correction(store, 'fix-1')
    before = dump(store_file(home, store))
    address = store.correct(fix.name, kitchen.element_id, {'address': 'code.timer.egg'}, reason='egg timer')
    colour = store.correct(fix.name, kitchen.element_id, {'colour': 'blue'}, reason='no')
    assert [notice.where for notice in address.notices] == ['address']
    assert 'cannot be moved' in address.notices[0].message
    assert [notice.where for notice in colour.notices] == ['colour']
    assert dump(store_file(home, store)) == before
    both = store.correct(fix.name, kitchen.element_id, {'address': 'code.timer.egg', 'role': 'SE'}, reason='r')
    assert [notice.where for notice in both.notices] == ['address']
    assert (both.fields['address'], both.fields['role']) == ('code.timer.kitchen', 'SE')
    store.finish(fix.name)
    assert store.element('code.timer.egg') is None
    found = store.element('code.timer.kitchen')
    assert (found.element_id, found.role) == (kitchen.element_id, 'SE')
    assert values(store.node(Node('element', 'code.timer.kitchen')), 'memory') == ['rings twice']


@pytest.mark.req('STORE-034')
def test_finishing_a_removal_that_leaves_a_join_behind_orphans_it_and_names_it(home, store):
    _, _, inner = small_map(store)
    alarm = store.element('code.alarm.audible')
    fix = correction(store, 'fix-1')
    store.correct(fix.name, alarm.element_id, remove=True, reason='gone')
    finished = store.finish(fix.name)
    assert inner.join_id in ' '.join(notice.message for notice in finished.notices)
    assert finished.ready is not None and store.element('code.alarm.audible') is None
    assert store.joins('code.timer.kitchen').results == ()
    orphan = store.joins('code.timer.kitchen', raw=True).results[0]
    assert orphan.join_id == inner.join_id and orphan.orphaned


@pytest.mark.req('STORE-034')
@pytest.mark.req('STORE-017')
@pytest.mark.req('MAP-003')
def test_a_correction_moves_a_join_to_another_receiver_and_peeling_moves_it_back(home, store):
    _, _, inner = small_map(store)
    notes = knowledge(store, 'notes')
    store.add_item(notes.name, Node('join', inner.join_id), 'rings too long')
    store.finish(notes.name)
    knowledge_rows = {row for row in dump(store_file(home, store))['items']}
    fix = correction(store, 'fix-1')
    moved = store.correct(fix.name, inner.join_id, {'receiver': 'stakeholder.cook.home'}, reason='the cook hears it')
    assert moved.notices == ()
    store.finish(fix.name)
    assert inner.join_id in [join.join_id for join in store.joins('stakeholder.cook.home').results]
    assert store.joins('code.timer.kitchen').results == ()
    assert values(store.node(Node('join', inner.join_id)), 'notes') == ['rings too long']
    assert {row for row in dump(store_file(home, store))['items']} == knowledge_rows
    assert [(version.layer, version.op) for version in store.history(inner.join_id).results] == [
        ('intake-1', 'add'), ('fix-1', 'change')]
    store.peel(fix.name)
    assert [join.join_id for join in store.joins('code.timer.kitchen').results] == [inner.join_id]
    assert values(store.node(Node('join', inner.join_id)), 'notes') == ['rings too long']


@pytest.mark.req('STORE-034')
@pytest.mark.req('STORE-017')
@pytest.mark.req('MAP-030')
def test_a_correction_absorbs_a_join_into_its_parents_join_and_peeling_restores_it(store):
    with store.atomic():
        base = intake(store)
        store.add_element(base.name, 'stakeholder.cook', role='VE')
        store.add_element(base.name, 'code.timer', role='DE')
        store.add_element(base.name, 'code.alarm', role='SE')
        parent = store.add_join(base.name, 'stakeholder.cook', 'code.timer', purpose='Know when a dish is done.',
                                function='Counts down and rings.', relation='r', observation='o')
        part = store.add_join(base.name, 'stakeholder.cook', 'code.alarm', purpose='Hear the end.', function='Rings.',
                              relation='r', observation='o')
    fix = correction(store, 'fix-1')
    store.correct(fix.name, part.join_id, {'parent': parent.join_id}, reason='the alarm is part of the timer')
    store.finish(fix.name)
    assert [join.join_id for join in store.joins('stakeholder.cook').results] == [parent.join_id]
    held = store.subtypes(parent.join_id).results
    assert [(sub.join_id, sub.address, sub.purpose, sub.extra) for sub in held] == [
        (part.join_id, 'code.alarm', 'Hear the end.', None)]  # absorbed, it keeps its purpose as its own, STORE-011
    assert 'code.alarm' not in [root.address for root in store.roots().elements]
    store.peel(fix.name)
    assert sorted(join.join_id for join in store.joins('stakeholder.cook').results) == sorted(
        [parent.join_id, part.join_id])
    assert store.subtypes(parent.join_id).results == ()
    assert {join.join_id: join.purpose for join in store.joins('stakeholder.cook').results}[part.join_id] == \
        'Hear the end.'


@pytest.mark.req('STORE-017')
@pytest.mark.req('MAP-015')
@pytest.mark.req('STORE-007')
def test_a_correction_records_an_element_at_a_better_address_and_moves_its_join_to_it(store):
    _, _, inner = small_map(store)
    alarm = store.element('code.alarm.audible')
    notes = memory(store)
    store.add_item(notes.name, Node('join', inner.join_id), 'rings too long')
    store.add_item(notes.name, Node('element', alarm.element_id), 'a piezo')
    fix = correction(store, 'fix-1')
    better = store.add_element(fix.name, 'code.alarm.audible.tone', name_length=2, role='SE')
    store.correct(fix.name, inner.join_id, {'provider': 'code.alarm.audible.tone'}, reason='it plays a tone')
    store.finish(fix.name)
    moved = store.joins('code.timer.kitchen').results
    assert [(join.join_id, join.provider_address) for join in moved] == [(inner.join_id, 'code.alarm.audible.tone')]
    assert store.element('code.alarm.audible.tone').element_id == better.element_id
    assert values(store.node(Node('join', inner.join_id)), 'memory') == ['rings too long']
    assert store.element('code.alarm.audible').element_id == alarm.element_id
    assert values(store.node(Node('element', 'code.alarm.audible')), 'memory') == ['a piezo']


@pytest.mark.req('STORE-012')
def test_a_corrected_ref_list_keeps_the_old_version_whole(store):
    with store.atomic():
        base = intake(store)
        store.add_element(base.name, 'code.a', role='DE')
        store.add_element(base.name, 'code.b', role='SE')
        join = store.add_join(base.name, 'code.a', 'code.b', purpose='p', function='f', relation='r',
                              observation='o', refs=[('path', 'a'), ('path', 'b')])
    fix = correction(store, 'fix-1')
    store.correct(fix.name, join.join_id, {'refs': [('path', 'b')]}, reason='a is stale')
    store.finish(fix.name)
    assert [(ref.key, ref.value) for ref in store.joins('code.a').results[0].refs] == [('path', 'b')]
    first = store.history(join.join_id).results[0]
    assert [(ref.key, ref.value) for ref in first.refs] == [('path', 'a'), ('path', 'b')]


@pytest.mark.req('STORE-021')
def test_extension_fields_survive_a_correction_that_does_not_touch_them(store):
    with store.atomic():
        base = intake(store)
        store.add_element(base.name, 'code.a', role='DE')
        store.add_element(base.name, 'code.b', role='SE')
        join = store.add_join(base.name, 'code.a', 'code.b', purpose='p', function='f', relation='r',
                              observation='o', extra={'latency_budget': '5 ms'})
    fix = correction(store, 'fix-1')
    store.correct(fix.name, join.join_id, {'purpose': 'q'}, reason='wording')
    store.finish(fix.name)
    assert store.joins('code.a').results[0].extra == {'latency_budget': '5 ms'}


@pytest.mark.req('STORE-036')
def test_finishing_a_correction_marks_the_layers_built_from_what_it_changed(home, store):
    _, outer, _ = small_map(store)
    built = knowledge(store, 'challenge', sources=('intake-1',))
    unrelated = knowledge(store, 'other')
    store.finish(built.name)
    store.finish(unrelated.name)
    fix = correction(store, 'fix-1')
    store.correct(fix.name, outer.join_id, {'purpose': 'new'}, reason='r')
    store.finish(fix.name)
    marked = {layer.name: layer.reexamine for layer in store.layers().results}
    assert marked['challenge'] is True and marked['other'] is False
    store.reexamined(built.name)
    assert {layer.name: layer.reexamine for layer in store.layers().results}['challenge'] is False


@pytest.mark.req('VIEW-014')
@pytest.mark.req('STORE-017')
def test_the_peel_preview_names_what_removing_a_correction_layer_would_change_and_writes_nothing(home, store):
    _, _, inner = small_map(store)
    alarm = store.element('code.alarm.audible').element_id
    notes = knowledge(store, 'notes')
    store.add_item(notes.name, Node('element', alarm), 'loud enough?')
    store.finish(notes.name)
    first = correction(store, 'fix-1')
    store.add_element(first.name, 'code.alarm.audible.tone', role='SE')
    store.correct(first.name, inner.join_id, {'provider': 'code.alarm.audible.tone'}, reason='it plays a tone')
    added = store.add_join(first.name, 'stakeholder.cook.home', 'code.alarm.audible', purpose='Hear it.',
                           function='Rings.', relation='The alarm tells the cook.', observation='Loud.')
    store.finish(first.name)
    later = knowledge(store, 'later')
    store.add_item(later.name, Node('join', added.join_id), 'rings twice')
    store.finish(later.name)
    second = correction(store, 'fix-2')
    store.correct(second.name, alarm, remove=True, reason='no alarm')
    store.finish(second.name)
    before = dump(store_file(home, store))
    top = store.peel_preview('fix-2')
    below = store.peel_preview('fix-1')
    assert dump(store_file(home, store)) == before
    assert top.top is True and below.top is False
    assert [(change.kind, change.what, change.effect) for change in top.changes] == [
        ('element', 'code.alarm.audible', 'comes back'), ('item', 'loud enough?', 'shows again')]
    found = {(change.kind, change.what, change.effect): change.detail for change in below.changes}
    assert found[('join', 'code.timer.kitchen -> code.alarm.audible.tone', 'moves back')] == \
        'to code.timer.kitchen -> code.alarm.audible'
    assert ('element', 'code.alarm.audible.tone', 'disappears') in found
    assert ('join', 'stakeholder.cook.home -> code.alarm.audible', 'disappears') in found
    assert ('item', 'rings twice', 'becomes orphaned') in found
    assert store.peel_preview('notes').changes == () and store.peel_preview('notes').notices


@pytest.mark.req('MAP-020')
@pytest.mark.req('STORE-017')
def test_a_joins_and_a_subtypes_ef_is_kept_through_every_correction_and_move(store):
    with store.atomic():
        base = intake(store)
        store.add_element(base.name, 'code.a', role='DE')
        store.add_element(base.name, 'code.b', role='SE')
        join = store.add_join(base.name, 'code.a', 'code.b', purpose='p', function='f', ef='Encounter', relation='r',
                              observation='o')
        tick = store.add_subtype(base.name, join.join_id, 'code.loop.tick', function='g', ef='Function',
                                 relation='r', observation='o', role='SE')
    assert (join.ef, tick.ef, join.notices, tick.notices) == ('Encounter', 'Function', (), ())
    fix = correction(store, 'fix-1')
    store.correct(fix.name, join.join_id, {'purpose': 'q'}, reason='wording')
    store.correct(fix.name, tick.join_id, {'ef': 'Encounter'}, reason='relabel')
    store.finish(fix.name)
    kept = store.joins('code.a').results[0]
    assert (kept.purpose, kept.ef, store.subtypes(kept.join_id).results[0].ef) == ('q', 'Encounter', 'Encounter')
    move = correction(store, 'fix-2')
    store.add_element(move.name, 'code.c', role='DE')
    store.correct(move.name, join.join_id, {'receiver': 'code.c'}, reason='moved')
    store.finish(move.name)
    moved = store.history(join.join_id).results[-1]
    assert (moved.op, moved.fields['ef']) == ('change', 'Encounter')
    assert [sub.ef for sub in store.subtypes(store.joins('code.c').results[0].join_id).results] == ['Encounter']


@pytest.mark.req('MAP-020')
@pytest.mark.req('BASE-044')
def test_ef_holds_only_function_or_encounter_and_any_other_word_is_kept_in_extra_with_a_notice(store):
    with store.atomic():
        base = intake(store)
        store.add_element(base.name, 'code.a', role='DE')
        store.add_element(base.name, 'code.b', role='SE')
        join = store.add_join(base.name, 'code.a', 'code.b', purpose='p', function='f', ef='Both', relation='r',
                              observation='o')
        tick = store.add_subtype(base.name, join.join_id, 'code.loop.tick', function='g', ef='function',
                                 relation='r', observation='o', role='SE')
    assert (join.ef, join.extra, [notice.where for notice in join.notices]) == (None, {'ef': 'Both'}, ['ef'])
    assert (tick.ef, tick.extra, [notice.where for notice in tick.notices]) == (None, {'ef': 'function'}, ['ef'])
    stored = store.joins('code.a').results[0]
    stored_tick = store.subtypes(stored.join_id).results[0]
    assert (stored.ef, stored.extra, stored_tick.ef, stored_tick.extra) == (None, {'ef': 'Both'}, None, {'ef': 'function'})


@pytest.mark.req('MAP-020')
@pytest.mark.req('STORE-017')
def test_a_joins_and_a_subtypes_verb_is_stored_as_given_and_kept_through_corrections_and_moves(store):
    with store.atomic():
        base = intake(store)
        store.add_element(base.name, 'code.a', role='DE')
        store.add_element(base.name, 'code.b', role='SE')
        join = store.add_join(base.name, 'code.a', 'code.b', purpose='p', function='f', ef='Encounter',
                              relation='People drive the a through the b.', verb='drive', observation='o')
        tick = store.add_subtype(base.name, join.join_id, 'code.loop.tick', function='g', ef='Function',
                                 relation='The tick loop advances every countdown.', verb='advances', observation='o',
                                 role='SE')
    assert (join.verb, tick.verb, join.notices, tick.notices) == ('drive', 'advances', (), ())
    fix = correction(store, 'fix-1')
    store.correct(fix.name, join.join_id, {'purpose': 'q'}, reason='wording')
    store.correct(fix.name, tick.join_id, {'verb': 'moves'}, reason='plainer')
    store.finish(fix.name)
    kept = store.joins('code.a').results[0]
    assert (kept.purpose, kept.verb, store.subtypes(kept.join_id).results[0].verb) == ('q', 'drive', 'moves')
    move = correction(store, 'fix-2')
    store.add_element(move.name, 'code.c', role='DE')
    store.correct(move.name, join.join_id, {'receiver': 'code.c'}, reason='moved')
    store.finish(move.name)
    assert store.history(join.join_id).results[-1].fields['verb'] == 'drive'
    assert store.history(tick.join_id).results[-1].fields['verb'] == 'moves'



@pytest.mark.req('MAP-032')
@pytest.mark.req('STORE-034')
@pytest.mark.req('STORE-017')
def test_a_correction_absorbing_a_join_that_holds_a_subtype_join_passes_it_to_the_new_parent(store):
    with store.atomic():
        base = intake(store)
        store.add_element(base.name, 'stakeholder.cook', role='VE')
        store.add_element(base.name, 'code.timer', role='DE')
        store.add_element(base.name, 'code.alarm', role='SE')
        parent = store.add_join(base.name, 'stakeholder.cook', 'code.timer', purpose='Know when a dish is done.',
                                function='Counts down and rings.', relation='r', observation='o')
        part = store.add_join(base.name, 'stakeholder.cook', 'code.alarm', purpose='Hear the end.', function='Rings.',
                              relation='r', observation='o')
        piezo = store.add_subtype(base.name, part.join_id, 'code.alarm.piezo', function='Buzzes.', role='SE',
                                  refs=[('path', 'src/piezo.c')])
    fix = correction(store, 'fix-1')
    absorbed = store.correct(fix.name, part.join_id, {'parent': parent.join_id}, reason='the alarm is the timer\'s')
    assert piezo.join_id in ' '.join(notice.message for notice in absorbed.notices)
    store.finish(fix.name)
    assert sorted(sub.join_id for sub in store.subtypes(parent.join_id).results) == sorted(
        [part.join_id, piezo.join_id])
    moved = {sub.join_id: sub for sub in store.subtypes(parent.join_id).results}[piezo.join_id]
    assert (moved.parent, moved.function, [(ref.key, ref.value) for ref in moved.refs]) == (
        parent.join_id, 'Buzzes.', [('path', 'src/piezo.c')])
    assert [(version.layer, version.op, version.fields['parent']) for version in store.history(piezo.join_id).results] \
        == [('intake-1', 'add', part.join_id), ('fix-1', 'change', parent.join_id)]
    store.peel(fix.name)
    assert [sub.join_id for sub in store.subtypes(part.join_id).results] == [piezo.join_id]
    assert [sub.join_id for sub in store.subtypes(parent.join_id).results] == []
