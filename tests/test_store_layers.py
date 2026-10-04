"""Storage of layers: declared behavior, items, provenance, memory, selection, building, tags and properties."""
from __future__ import annotations

import sqlite3

import pytest
from storekit import PROVENANCE, diff, dump, intake, knowledge, memory, small_map, store_file, values

from metaform.data import Node, Store, StoreError

pytestmark = pytest.mark.kind('fixture')

KITCHEN = Node('element', 'code.timer.kitchen')


@pytest.mark.req('STORE-013')
@pytest.mark.req('LAYER-006')
def test_hiding_a_layer_that_is_not_hideable_changes_nothing_and_says_why(home, store):
    small_map(store)
    layer = knowledge(store, 'fixed', hideable=False)
    before = dump(store_file(home, store))
    assert 'not hideable' in store.hide(layer.name).notices[0].message
    assert store.hide('intake-1').notices
    assert dump(store_file(home, store)) == before


@pytest.mark.req('STORE-013')
@pytest.mark.req('LAYER-006')
def test_a_hidden_layer_is_absent_from_node_reads_and_present_by_name(store):
    small_map(store)
    notes = knowledge(store, 'notes')
    store.add_item(notes.name, KITCHEN, 'keep it simple')
    store.finish(notes.name)
    assert values(store.node(KITCHEN), 'notes') == ['keep it simple']
    store.hide(notes.name)
    assert values(store.node(KITCHEN), 'notes') == []
    assert [item.value for item in store.layer_items(notes.name).results] == ['keep it simple']
    store.unhide(notes.name)
    assert values(store.node(KITCHEN), 'notes') == ['keep it simple']


@pytest.mark.req('STORE-014')
@pytest.mark.req('LAYER-001')
def test_an_element_made_by_a_second_layer_follows_that_layers_selection(store):
    small_map(store)
    extra = knowledge(store, 'extra')
    store.add_element(extra.name, 'code.probe')
    store.finish(extra.name)
    assert store.node(Node('element', 'code.probe'), selection=['intake-1']) is None
    assert store.node(Node('element', 'code.probe'), selection=['intake-1', 'extra']) is not None
    assert store.element('code.probe').layer == 'extra'


@pytest.mark.req('LAYER-001')
def test_a_write_naming_a_layer_that_does_not_exist_cannot_be_read(store):
    small_map(store)
    with pytest.raises(StoreError):
        store.add_element('no-such-layer', 'code.x')
    with pytest.raises(StoreError):
        store.add_item('no-such-layer', KITCHEN, 'x')


@pytest.mark.req('STORE-015')
def test_items_are_read_by_layer_by_node_and_by_link(store):
    small_map(store)
    notes = knowledge(store, 'notes')
    to_alarm = store.add_item(notes.name, KITCHEN, 'calls the alarm', link=Node('element', 'code.alarm.audible'))
    back = store.add_item(notes.name, Node('element', 'code.alarm.audible'), 'is called by the timer', link=KITCHEN)
    store.finish(notes.name)
    assert {item.item_id for item in store.layer_items(notes.name).results} == {to_alarm.item_id, back.item_id}
    assert values(store.node(KITCHEN), 'notes') == ['calls the alarm']
    assert [item.item_id for item in store.links_to(KITCHEN).results] == [back.item_id]
    assert [item.item_id for item in store.links_to(Node('element', 'code.alarm.audible')).results] == [to_alarm.item_id]


@pytest.mark.req('STORE-015')
def test_an_item_on_a_missing_element_makes_it_and_an_extra_not_an_object_is_kept_as_its_value(home, store):
    small_map(store)
    notes = knowledge(store, 'notes')
    made = store.add_item(notes.name, Node('element', 'code.nowhere'), 'x')
    assert made.notices and store.element('code.nowhere', raw=True).layer == notes.name
    kept = store.add_item(notes.name, KITCHEN, 'x', extra=['not', 'an', 'object'])
    assert kept.extra == {'value': ['not', 'an', 'object']} and kept.notices


@pytest.mark.req('STORE-016')
@pytest.mark.req('LAYER-010')
def test_a_layer_has_exactly_one_provenance_record(home, store):
    small_map(store)
    notes = knowledge(store, 'notes')
    record = store.provenance(notes.name)
    for n in range(100):
        store.add_item(notes.name, KITCHEN, f'note {n}')
    assert store.provenance(notes.name) == record
    db = sqlite3.connect(store_file(home, store))
    assert db.execute('SELECT COUNT(*) FROM provenance WHERE layer_id=?', (notes.layer_id,)).fetchone() == (1,)
    assert (record.module, record.prompt, record.role, record.blinded) == (
        PROVENANCE['module'], PROVENANCE['prompt'], PROVENANCE['role'], False)


@pytest.mark.req('STORE-016')
@pytest.mark.req('LAYER-010')
@pytest.mark.req('LAYER-012')
def test_a_layer_without_provenance_gets_an_empty_record_and_a_notice_except_memory(home, store):
    small_map(store)
    bare = store.layer('bare', 'test', 'Something.', mutable=True, hideable=True)
    assert bare.notices
    record = store.provenance('bare')
    assert (record.module, record.workflow, record.prompt, record.model, record.role) == ('test', None, None, None,
                                                                                          None)
    notes = memory(store)
    db = sqlite3.connect(store_file(home, store))
    assert db.execute('SELECT COUNT(*) FROM provenance WHERE layer_id=?', (notes.layer_id,)).fetchone() == (0,)


@pytest.mark.req('LAYER-002')
def test_a_layer_without_a_variable_is_stored_with_a_notice(home, store):
    empty = store.layer('empty', 'test', '', mutable=True, hideable=True, provenance=PROVENANCE)
    assert empty.variable == '' and [notice.where for notice in empty.notices] == ['variable']


@pytest.mark.req('STORE-018')
@pytest.mark.req('LAYER-012')
def test_memory_changes_in_place_and_keeps_no_history(home, store):
    small_map(store)
    notes = memory(store)
    item = store.add_item(notes.name, KITCHEN, 'first')
    for n in range(10):
        store.update_item(item.item_id, f'version {n}')
    db = sqlite3.connect(store_file(home, store))
    assert db.execute('SELECT COUNT(*) FROM items WHERE item_id=?', (item.item_id,)).fetchone() == (1,)
    assert values(store.node(KITCHEN), 'memory') == ['version 9']
    store.delete_item(item.item_id)
    assert values(store.node(KITCHEN), 'memory') == []
    assert store.search('version').results == ()
    assert store.layer_items('memory').results == ()


@pytest.mark.req('STORE-019')
@pytest.mark.req('LAYER-007')
def test_a_mask_stops_a_layer_flowing_into_its_branch(store):
    layer = knowledge(store, 'map-els')
    for address in ('code.installer.bash', 'code.engine'):
        store.add_element(layer.name, address)
    store.finish(layer.name)
    practices = knowledge(store, 'c-practices')
    store.add_item(practices.name, Node('element', 'code.installer.bash'), 'use strict mode')
    store.add_item(practices.name, Node('element', 'code.engine'), 'no raw pointers')
    store.finish(practices.name)
    store.mask('code.installer', practices.name)
    assert values(store.node(Node('element', 'code.installer.bash')), 'c-practices') == []
    assert values(store.node(Node('element', 'code.engine')), 'c-practices') == ['no raw pointers']
    assert practices.layer_id not in store.effective_selection('code.installer.bash').layer_ids


@pytest.mark.req('STORE-019')
@pytest.mark.req('LAYER-007')
def test_a_select_toward_the_leaves_from_a_mask_turns_the_layer_on_again_there_and_nowhere_toward_the_trunk(store):
    layer = knowledge(store, 'map-els')
    for address in ('code.engine.renderer', 'code.engine.physics', 'code.engine'):
        store.add_element(layer.name, address)
    store.finish(layer.name)
    porting = knowledge(store, 'porting')
    for address in ('code.engine.renderer', 'code.engine.physics', 'code.engine'):
        store.add_item(porting.name, Node('element', address), f'port {address}')
    store.finish(porting.name)
    store.mask('code.engine', porting.name)
    store.select('code.engine.renderer', porting.name)
    assert values(store.node(Node('element', 'code.engine.renderer')), 'porting') == ['port code.engine.renderer']
    assert values(store.node(Node('element', 'code.engine')), 'porting') == []
    assert values(store.node(Node('element', 'code.engine.physics')), 'porting') == []
    store.clear('code.engine', porting.name, 'mask')
    assert values(store.node(Node('element', 'code.engine.physics')), 'porting') == ['port code.engine.physics']


@pytest.mark.req('STORE-019')
@pytest.mark.req('LAYER-007')
def test_a_layer_masked_at_the_receiver_does_not_reach_its_joins(store):
    _, _outer, inner = small_map(store)
    notes = knowledge(store, 'notes')
    store.add_item(notes.name, Node('join', inner.join_id), 'the tone is too quiet')
    store.finish(notes.name)
    assert values(store.node(Node('join', inner.join_id)), 'notes') == ['the tone is too quiet']
    store.mask('code.timer.kitchen', notes.name)
    assert values(store.node(Node('join', inner.join_id)), 'notes') == []


@pytest.mark.req('STORE-020')
def test_an_observation_on_a_node_with_no_memories_writes_one_item(home, store):
    small_map(store)
    notes = memory(store)
    store.add_item(notes.name, Node('element', 'code.alarm.audible'), 'first note elsewhere')
    before = dump(store_file(home, store))
    store.add_item(notes.name, KITCHEN, 'the timer keeps time in ticks')
    # One item: its version row and its current pointer. The full-text index is not a row.
    assert diff(before, dump(store_file(home, store))) == {'items': (1, 0), 'current_items': (1, 0),
                                                           'item_ids': (1, 0), 'identities': (1, 0)}


@pytest.mark.req('STORE-020')
@pytest.mark.req('LAYER-013')
def test_a_relation_shows_at_both_ends_and_search_finds_words(store):
    small_map(store)
    notes = memory(store)
    store.add_item(notes.name, KITCHEN, 'depends_on', link=Node('element', 'code.alarm.audible'))
    store.add_item(notes.name, KITCHEN, 'Ticks drift when the CPU is busy.')
    assert 'depends_on' in values(store.node(KITCHEN), 'memory')
    assert [item.value for item in store.links_to(Node('element', 'code.alarm.audible')).results] == ['depends_on']
    found = store.search('drift').results
    assert [item.value for item in found] == ['Ticks drift when the CPU is busy.']
    # The search text is words, never full-text query syntax: OR is a word no note holds.
    assert store.search('drift OR nothing').results == ()
    assert [item.value for item in store.search('drift"').results] == ['Ticks drift when the CPU is busy.']


@pytest.mark.req('STORE-032')
def test_an_intake_that_raises_inside_atomic_leaves_nothing(home, store):
    with pytest.raises(RuntimeError), store.atomic():
        layer = intake(store)
        store.add_element(layer.name, 'code.timer.kitchen', role='DE')
        raise RuntimeError('interrupted')
    assert store.has_intake() is False
    assert store.layers().results == ()
    assert store.element('code.timer.kitchen') is None


@pytest.mark.req('STORE-032')
@pytest.mark.req('LAYER-018')
def test_a_building_layer_is_invisible_in_context_until_finished(store):
    small_map(store)
    notes = knowledge(store, 'notes')
    store.add_item(notes.name, KITCHEN, 'draft')
    assert values(store.node(KITCHEN), 'notes') == []
    assert [item.value for item in store.layer_items(notes.name).results] == ['draft']
    assert values(store.node(KITCHEN, raw=True), 'notes') == ['draft']
    store.finish(notes.name)
    assert values(store.node(KITCHEN), 'notes') == ['draft']
    assert values(Store('proj', toggled=['intake-1']).node(KITCHEN), 'notes') == []


@pytest.mark.req('STORE-032')
@pytest.mark.req('LAYER-004')
@pytest.mark.req('LAYER-018')
def test_a_finished_knowledge_layer_stays_editable_and_the_intake_does_not(home, store):
    small_map(store)
    notes = knowledge(store, 'notes')
    item = store.add_item(notes.name, KITCHEN, 'draft')
    store.finish(notes.name)
    store.edit(item.item_id, {'value': 'final'})
    assert values(store.node(KITCHEN), 'notes') == ['final']
    db = sqlite3.connect(store_file(home, store))
    assert db.execute('SELECT COUNT(*) FROM items WHERE item_id=?', (item.item_id,)).fetchone() == (1,)
    kitchen = store.element('code.timer.kitchen')
    before = dump(store_file(home, store))
    untouched = store.edit(kitchen.element_id, {'role': 'SE'})
    assert 'metaform map refine' in untouched.notices[0].message
    assert dump(store_file(home, store)) == before


@pytest.mark.req('STORE-032')
def test_discarding_a_layer_keeps_identity_and_type_rows(home, store):
    small_map(store)
    draft = knowledge(store, 'draft')
    element = store.add_element(draft.name, 'code.probe.echo')
    item = store.add_item(draft.name, Node('element', 'code.probe.echo'), 'a draft note')
    store.discard(draft.name)
    db = sqlite3.connect(store_file(home, store))
    assert db.execute('SELECT COUNT(*) FROM element_ids WHERE element_id=?', (element.element_id,)).fetchone() == (1,)
    assert db.execute("SELECT COUNT(*) FROM types WHERE address='code.probe.echo'").fetchone() == (1,)
    assert db.execute('SELECT COUNT(*) FROM identities WHERE id=?', (item.item_id,)).fetchone() == (1,)
    assert store.element(element.element_id) is None
    assert store.search('draft').results == ()
    assert 'draft' not in [layer.name for layer in store.layers().results]
    assert store.discard('intake-1').notices and store.has_intake()


@pytest.mark.req('STORE-032')
def test_a_successful_intake_is_visible_whole(store):
    assert store.has_intake() is False
    small_map(store)
    assert store.has_intake() is True
    assert store.element('code.timer.kitchen').layer == 'intake-1'
    assert [join.layer for join in store.joins('code.timer.kitchen').results] == ['intake-1']


@pytest.mark.req('STORE-035')
@pytest.mark.req('LAYER-005')
@pytest.mark.req('MAP-022')
def test_properties_apply_toward_the_leaves_and_are_visible_toward_the_trunk(store):
    layer = knowledge(store, 'map-els')
    for address in ('code.engine', 'code.installer', 'code.installer.script', 'code'):
        store.add_element(layer.name, address)
    store.finish(layer.name)
    media = knowledge(store, 'media')
    store.add_property(media.name, 'code.engine', 'C++')
    store.add_property(media.name, 'code.installer', 'Bash')
    store.finish(media.name)
    at_code = store.context('code')
    assert sorted(item.value for item in at_code.visible) == ['Bash', 'C++']
    assert at_code.applying == ()
    assert [item.value for item in store.context('code.installer.script').applying] == ['Bash']
    assert 'C++' not in [item.value for item in store.context('code.installer').applying]
    assert store.context('code.engine').applying[0].value == 'C++'


@pytest.mark.req('STORE-035')
@pytest.mark.req('LAYER-004')
@pytest.mark.req('MAP-015')
def test_a_property_stays_with_its_element_which_never_moves_and_an_item_never_travels(store):
    with store.atomic():
        base = intake(store)
        store.add_element(base.name, 'code.engine', role='DE')
        store.add_element(base.name, 'code.engine.game', role='SE')
        store.add_element(base.name, 'code.runtime.game', role='SE')
    practices = knowledge(store, 'practices')
    store.add_property(practices.name, 'code.engine', 'profile before optimizing')
    store.add_item(practices.name, Node('element', 'code.engine'), 'not inherited')
    store.finish(practices.name)
    applying = [item.value for item in store.context('code.engine.game').applying]
    assert applying == ['profile before optimizing']
    assert values(store.node(Node('element', 'code.engine.game')), 'practices') == []
    tried = store.refine(store.element('code.engine').element_id, {'address': 'code.runtime'},
                         reason='It is the runtime.')
    assert [notice.where for notice in tried.notices] == ['address']
    assert [item.value for item in store.context('code.engine.game').applying] == ['profile before optimizing']
    assert store.context('code.runtime.game').applying == ()


@pytest.mark.req('STORE-038')
@pytest.mark.req('LAYER-019')
def test_tags_change_on_a_finished_layer_without_touching_it(home, store):
    small_map(store)
    notes = knowledge(store, 'notes', tags=('practices',))
    store.add_item(notes.name, KITCHEN, 'x')
    store.finish(notes.name)
    before = dump(store_file(home, store))
    store.tag(notes.name, 'review')
    store.tag(notes.name, 'review')
    assert diff(before, dump(store_file(home, store))) == {'layer_tags': (1, 0)}
    listed = {layer.name: layer for layer in store.layers(tag='practices').results}
    assert set(listed) == {'notes'} and set(listed['notes'].tags) == {'practices', 'review'}
    store.untag(notes.name, 'practices')
    assert store.layers(tag='practices').results == ()


@pytest.mark.req('LAYER-019')
@pytest.mark.req('STORE-035')
def test_the_toggled_layers_are_the_starting_selection(store):
    small_map(store)
    tagged = knowledge(store, 'a', tags=('practices',))
    plain = knowledge(store, 'b')
    store.add_item(tagged.name, KITCHEN, 'from a')
    store.add_item(plain.name, KITCHEN, 'from b')
    store.finish(tagged.name)
    store.finish(plain.name)
    narrowed = Store('proj', toggled=['practices'])
    assert values(narrowed.node(KITCHEN)) == {'a': ['from a']}
    everything = values(Store('proj').node(KITCHEN))
    assert everything['a'] == ['from a'] and everything['b'] == ['from b']
    on = {layer.name: layer.on for layer in narrowed.layers().results}
    assert on['a'] is True and on['b'] is False
    narrowed.mask('code.timer', tagged.name)
    assert values(narrowed.node(KITCHEN)) == {}


@pytest.mark.req('STORE-039')
@pytest.mark.req('MAP-022')
def test_a_property_attaches_only_to_an_element_and_writes_no_join(home, store):
    _, outer, _ = small_map(store)
    media = knowledge(store, 'media')
    before = dump(store_file(home, store))
    store.add_property(media.name, 'code.timer.kitchen', 'C')
    changed = diff(before, dump(store_file(home, store)))
    assert 'joins' not in changed and 'current_joins' not in changed and changed['properties'] == (1, 0)
    at_type = store.add_property(media.name, Node('type', 'code'), 'x')
    assert at_type.notices and at_type.address == 'code' and not at_type.orphaned
    stored = store.add_property(media.name, Node('join', outer.join_id), 'x')
    assert stored.notices and stored.orphaned
    assert 'joins' not in diff(before, dump(store_file(home, store)))


@pytest.mark.req('STORE-013')
@pytest.mark.req('LAYER-006')
def test_hiding_a_layer_hides_the_layers_built_from_it(store):
    small_map(store)
    source = knowledge(store, 'source')
    built = knowledge(store, 'built', sources=('source',))
    store.add_item(source.name, KITCHEN, 'from the source')
    store.add_item(built.name, KITCHEN, 'built on it')
    store.finish(source.name)
    store.finish(built.name)
    store.hide(source.name)
    assert values(store.node(KITCHEN), 'built') == []
    store.unhide(source.name)
    assert values(store.node(KITCHEN), 'built') == ['built on it']


@pytest.mark.req('STORE-004')
@pytest.mark.req('STORE-015')
def test_a_collection_in_a_value_or_an_extra_becomes_one_item_per_member(home, store):
    small_map(store)
    notes = knowledge(store, 'notes')
    before = dump(store_file(home, store))
    split = store.add_item(notes.name, KITCHEN, 'x', extra={'members': [{'a': 1}, {'b': 2}]})
    assert split.extra is None and split.notices
    listed = store.add_item(notes.name, KITCHEN, ['one answer', 'another answer'])
    assert listed.notices
    values_now = [item.value for item in store.layer_items(notes.name, KITCHEN).results]
    assert values_now == ['x', {'members': {'a': 1}}, {'members': {'b': 2}}, 'one answer', 'another answer']
    assert diff(before, dump(store_file(home, store)))['items'] == (5, 0)


@pytest.mark.req('STORE-032')
def test_discarding_a_layer_keeps_an_element_another_layer_still_has_something_at(home, store):
    """A layer made the element at `code` to hold its property, and a second layer then put its own property there.
    Found 2026-09-29: discarding the first took the element with it, and the second layer's property was gone from
    every read with nothing said. What another layer still holds at an element keeps the element."""
    small_map(store)
    first, second = knowledge(store, 'first'), knowledge(store, 'second')
    made = store.add_property(first.name, 'code', 'Python')
    kept = store.add_property(second.name, 'code', 'typed')
    noted = store.add_item(second.name, Node('element', 'code'), 'a note at the trunk')
    store.add_element(first.name, 'code.only.first')             # nothing else is at this one
    store.finish(first.name)
    store.finish(second.name)
    assert [one.value for one in store.context('code.timer.kitchen').applying] == ['Python', 'typed']
    done = store.discard(first.name)
    assert [notice.where for notice in done.notices] == ['element'] and 'code' in done.notices[0].message
    assert 'second' in done.notices[0].message
    element = store.element('code', raw=True)
    assert element is not None and (element.element_id, element.layer) == (made.element_id, 'second')
    assert [one.value for one in store.context('code.timer.kitchen').applying] == ['typed']
    assert [one.property_id for one in store.context('code').applying] == [kept.property_id]
    assert [item.item_id for group in store.node(Node('element', 'code'), raw=True).layers for item in group.items] \
        == [noted.item_id]
    assert store.element('code.only.first', raw=True) is None    # what nothing else holds goes with its layer
