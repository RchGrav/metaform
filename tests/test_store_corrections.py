"""The correction stack: the only way to change the metaform, applied in order, peeled only from the top."""
from __future__ import annotations

import pytest

from metaform.data import Node
from storekit import correction, dump, intake, knowledge, small_map, store_file, values

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


@pytest.mark.req('STORE-009')
def test_address_lookup_returns_the_highest_correction(store):
    small_map(store)
    element_id = store.element('code.alarm.audible').element_id
    first = correction(store, 'fix-1')
    store.correct(first.name, element_id, {'address': 'code.alarm.tone'}, reason='it plays a tone')
    store.finish(first.name)
    second = correction(store, 'fix-2')
    store.correct(second.name, element_id, {'address': 'code.alarm.buzzer'}, reason='it buzzes')
    store.finish(second.name)
    assert store.element('code.alarm.buzzer').element_id == element_id
    assert store.element('code.alarm.tone') is None and store.element('code.alarm.audible') is None


@pytest.mark.req('STORE-017')
@pytest.mark.req('LAYER-011')
def test_only_the_top_correction_peels_and_peeling_restores_the_reads(home, store):
    _, outer, _ = small_map(store)
    first = correction(store, 'fix-1')
    store.correct(first.name, outer.join_id, {'function': 'Counts down.'}, reason='r1')
    store.finish(first.name)
    between = reads(store)
    second = correction(store, 'fix-2')
    store.correct(second.name, store.element('code.timer.kitchen').element_id, {'address': 'code.timer.egg'},
                  reason='r2')
    store.finish(second.name)
    before = dump(store_file(home, store))
    below = store.peel(first.name)
    assert 'fix-2' in below.notices[0].message
    assert dump(store_file(home, store)) == before
    peeled = store.peel(second.name)
    assert peeled.ready is None
    assert reads(store) == between
    store.finish(second.name)
    assert store.element('code.timer.egg') is not None


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
def test_a_correction_never_changes_a_joins_receiver_and_names_what_it_did_not_apply(home, store):
    _, outer, _ = small_map(store)
    fix = correction(store, 'fix-1')
    before = dump(store_file(home, store))
    receiver = store.correct(fix.name, outer.join_id, {'receiver': 'code.alarm.audible'}, reason='no')
    colour = store.correct(fix.name, outer.join_id, {'colour': 'blue'}, reason='no')
    assert [notice.where for notice in receiver.notices] == ['receiver']
    assert [notice.where for notice in colour.notices] == ['colour']
    assert dump(store_file(home, store)) == before
    both = store.correct(fix.name, outer.join_id, {'receiver': 'code.alarm.audible', 'purpose': 'Fixed.'},
                         reason='r')
    assert [notice.where for notice in both.notices] == ['receiver'] and both.fields['purpose'] == 'Fixed.'
    store.finish(fix.name)
    join = store.joins('stakeholder.cook.home').results[0]
    assert join.purpose == 'Fixed.' and join.receiver_address == 'stakeholder.cook.home'


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
def test_a_retype_onto_an_address_another_element_holds_stays_unapplied_and_the_rest_applies(home, store):
    _, outer, _ = small_map(store)
    fix = correction(store, 'fix-1')
    alarm = store.element('code.alarm.audible').element_id
    store.correct(fix.name, alarm, {'address': 'code.timer.kitchen'}, reason='merge')
    store.correct(fix.name, outer.join_id, {'function': 'Counts down and rings loudly.'}, reason='louder')
    finished = store.finish(fix.name)
    assert [notice.where for notice in finished.notices] == [alarm]
    assert store.element('code.alarm.audible').element_id == alarm
    assert store.joins('stakeholder.cook.home').results[0].function == 'Counts down and rings loudly.'


@pytest.mark.req('STORE-034')
@pytest.mark.req('BASE-044')
def test_two_retypes_onto_one_free_address_apply_the_first_and_leave_the_second_unapplied(home, store):
    small_map(store)
    fix = correction(store, 'fix-1')
    kitchen = store.element('code.timer.kitchen').element_id
    alarm = store.element('code.alarm.audible').element_id
    store.correct(fix.name, kitchen, {'address': 'code.device.timer'}, reason='rename')
    store.correct(fix.name, alarm, {'address': 'code.device.timer'}, reason='rename')
    finished = store.finish(fix.name)
    assert finished.ready is not None
    assert [notice.where for notice in finished.notices] == [alarm]
    assert store.element('code.device.timer').element_id == kitchen
    assert store.element('code.alarm.audible').element_id == alarm


@pytest.mark.req('STORE-017')
@pytest.mark.req('MAP-015')
@pytest.mark.req('STORE-007')
def test_relocating_an_element_carries_its_items_and_drops_its_joins(store):
    small_map(store)
    kitchen = store.element('code.timer.kitchen')
    notes = knowledge(store, 'notes')
    store.add_item(notes.name, Node('element', kitchen.element_id), 'first')
    store.add_item(notes.name, Node('element', kitchen.element_id), 'second')
    store.finish(notes.name)
    fix = correction(store, 'fix-1')
    store.correct(fix.name, kitchen.element_id, {'address': 'code.timer.egg'}, reason='egg timer')
    store.finish(fix.name)
    moved = store.element('code.timer.egg')
    assert moved.element_id == kitchen.element_id
    assert sorted(values(store.node(Node('element', 'code.timer.egg')), 'notes')) == ['first', 'second']
    assert store.joins('code.timer.egg').results == () and store.joins('code.timer.egg', as_='provider').results == ()


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


@pytest.mark.req('STORE-017')
def test_a_relocation_removes_metaform_joins_and_orphans_knowledge_joins_until_peeled(home, store):
    _, _, inner = small_map(store)
    extra = knowledge(store, 'extra')
    store.add_element(extra.name, 'code.helper')
    known = store.add_join(extra.name, 'code.timer.kitchen', 'code.helper', purpose='p', function='f',
                           relation='r', observation='o')
    store.finish(extra.name)
    knowledge_rows = dump(store_file(home, store))['joins']
    kitchen = store.element('code.timer.kitchen').element_id
    fix = correction(store, 'fix-1')
    store.correct(fix.name, kitchen, {'address': 'code.timer.egg'}, reason='egg timer')
    store.finish(fix.name)
    rows = store.history(inner.join_id).results
    assert [(version.layer, version.op) for version in rows][-1] == ('fix-1', 'remove')
    assert store.joins(kitchen).results == ()
    raw = {join.join_id: join for join in store.joins(kitchen, raw=True).results}
    assert inner.join_id not in raw and raw[known.join_id].orphaned is True
    assert {row for row in dump(store_file(home, store))['joins'] if row[2] == extra.layer_id} == \
        {row for row in knowledge_rows if row[2] == extra.layer_id}
    store.peel(fix.name)
    assert {join.join_id for join in store.joins(kitchen).results} == {inner.join_id, known.join_id}
    assert store.element(kitchen).address == 'code.timer.kitchen'
