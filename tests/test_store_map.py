"""Storage of the map: identity, types, elements, joins, subtypes and refs."""
from __future__ import annotations

import re
import sqlite3

import pytest

from metaform.data import Node, StoreError
from storekit import diff, dump, knowledge, memory, small_map, store_file, values

pytestmark = pytest.mark.kind('fixture')

ID = re.compile(r'^[0-9a-f]{32}$')


@pytest.mark.req('STORE-004')
def test_adding_one_ref_to_a_join_with_a_thousand_writes_one_row(home, store):
    layer = knowledge(store, 'refs')
    store.add_element(layer.name, 'code.a')
    store.add_element(layer.name, 'code.b')
    join = store.add_join(layer.name, 'code.a', 'code.b', purpose='p', function='f', relation='r',
                          observation='o', refs=[('path', f'file{n}.c') for n in range(1000)])
    before = dump(store_file(home, store))
    store.add_ref(join.join_id, 'path', 'one-more.c')
    assert diff(before, dump(store_file(home, store))) == {'refs': (1, 0)}


@pytest.mark.req('STORE-007')
def test_identity_ids_are_32_lowercase_hex(store):
    layer, outer, _ = small_map(store)
    element = store.element('code.timer.kitchen')
    assert ID.match(element.element_id) and ID.match(outer.join_id) and ID.match(layer.layer_id)
    assert all(ID.match(sub.subtype_id) for sub in store.subtypes(outer.join_id).results)


@pytest.mark.req('STORE-008')
@pytest.mark.req('MAP-010')
def test_an_address_writes_itself_and_every_prefix_as_types(home, store):
    layer = knowledge(store, 'types')
    store.add_element(layer.name, 'code.engine.game.fps')
    db = sqlite3.connect(store_file(home, store))
    assert set(db.execute('SELECT address, parent FROM types')) == {
        ('code', None), ('code.engine', 'code'), ('code.engine.game', 'code.engine'),
        ('code.engine.game.fps', 'code.engine.game')}
    assert store.children('code').results == ('code.engine',)
    assert store.children('code.engine.game').results == ('code.engine.game.fps',)


@pytest.mark.req('STORE-008')
@pytest.mark.req('MAP-013')
def test_only_the_form_of_an_address_is_checked_and_a_bad_one_is_stored_with_a_notice(home, store):
    layer = knowledge(store, 'types')
    odd = store.add_element(layer.name, 'Code..Engine')
    assert [notice.where for notice in odd.notices] == ['address'] and 'form' in odd.notices[0].message
    assert store.where('Code..Engine', raw=True).element.element_id == odd.element_id
    jpg = store.add_element(layer.name, 'media.photo.jpg')
    assert jpg.address == 'media.photo.jpg' and jpg.notices == ()


@pytest.mark.req('STORE-008')
@pytest.mark.req('STORE-015')
def test_an_item_at_a_bare_type_address_makes_an_element_there_and_says_so(home, store):
    layer = knowledge(store, 'notes')
    store.add_element(layer.name, 'code.anchor')
    before = dump(store_file(home, store))
    item = store.add_item(layer.name, Node('type', 'data.bill_of_materials'), 'A note about BOMs.')
    made = store.element('data.bill_of_materials', raw=True)
    assert made is not None and made.layer == layer.name
    assert item.target == Node('element', made.element_id) and item.value == 'A note about BOMs.'
    assert [notice.where for notice in item.notices] == ['target']
    assert 'data.bill_of_materials' in item.notices[0].message
    changed = diff(before, dump(store_file(home, store)))
    assert changed['elements'] == (1, 0) and changed['items'] == (1, 0)


@pytest.mark.req('STORE-009')
@pytest.mark.req('MAP-016')
def test_a_second_element_at_a_held_address_returns_the_first(home, store):
    layer = knowledge(store, 'els')
    first = store.add_element(layer.name, 'code.engine')
    before = dump(store_file(home, store))
    second = store.add_element(layer.name, 'code.engine')
    assert second.element_id == first.element_id and second.existing is True
    assert 'elements' not in diff(before, dump(store_file(home, store)))


@pytest.mark.req('STORE-009')
@pytest.mark.req('MAP-015')
def test_an_intake_element_keeps_name_length_and_role_in_its_descriptor(home, store):
    small_map(store)
    element = store.element('code.timer.kitchen')
    assert (element.name, element.name_length, element.role) == ('kitchen timer', 2, 'DE')
    assert element.descriptors[0].layer == 'intake-1'
    columns = {row[1] for row in sqlite3.connect(store_file(home, store)).execute('PRAGMA table_info(elements)')}
    assert not {'name', 'name_length', 'role'} & columns


@pytest.mark.req('STORE-010')
@pytest.mark.req('MAP-002')
@pytest.mark.req('MAP-003')
def test_two_elements_may_each_receive_from_the_other(store):
    layer = knowledge(store, 'mutual')
    store.add_element(layer.name, 'code.a')
    store.add_element(layer.name, 'code.b')
    ab = store.add_join(layer.name, 'code.a', 'code.b', purpose='A needs B', function='B serves A',
                        relation='B serves A.', observation='o1')
    ba = store.add_join(layer.name, 'code.b', 'code.a', purpose='B needs A', function='A serves B',
                        relation='A serves B.', observation='o2')
    owned = store.joins('code.a', raw=True).results
    provided = store.joins('code.a', as_='provider', raw=True).results
    assert [join.join_id for join in owned] == [ab.join_id]
    assert [join.join_id for join in provided] == [ba.join_id]
    assert (owned[0].purpose, provided[0].purpose) == ('A needs B', 'B needs A')


@pytest.mark.req('STORE-010')
@pytest.mark.req('MAP-031')
def test_a_subtype_is_never_a_join_end(home, store):
    _, outer, _ = small_map(store)
    subtype = store.subtypes(outer.join_id).results[0]
    layer = knowledge(store, 'ends')
    before = dump(store_file(home, store))
    with pytest.raises(StoreError) as refused:
        store.add_join(layer.name, 'code.timer.kitchen', subtype.subtype_id, purpose='p', function='f',
                       relation='r', observation='o')
    assert refused.value.next_step
    assert dump(store_file(home, store)) == before
    stored = store.add_join(layer.name, 'code.timer.kitchen', 'code.loop.tick', purpose='p', function='f',
                            relation='r', observation='o')
    assert [notice.where for notice in stored.notices] == ['provider']
    assert stored.provider != subtype.subtype_id and store.element('code.loop.tick', raw=True).layer == 'ends'


@pytest.mark.req('STORE-011')
@pytest.mark.req('MAP-030')
@pytest.mark.req('MAP-031')
def test_a_subtype_is_read_only_through_its_join(store):
    _, outer, _ = small_map(store)
    subtypes = store.subtypes(outer.join_id).results
    assert [(sub.address, sub.function) for sub in subtypes] == [('code.loop.tick', 'Advances each countdown.')]
    assert store.element('code.loop.tick') is None
    joins = [*store.joins('code.timer.kitchen').results, *store.joins('code.timer.kitchen', as_='provider').results,
             *store.identity('code.timer.kitchen').results]
    assert all(getattr(join, 'subtype_id', None) is None for join in joins)
    where = store.where('code.loop.tick')
    assert where.kind == 'subtype' and where.join.join_id == outer.join_id
    assert (where.join.receiver_address, where.join.provider_address) == ('stakeholder.cook.home', 'code.timer.kitchen')


@pytest.mark.req('STORE-011')
@pytest.mark.req('MAP-030')
def test_a_subtype_given_a_purpose_keeps_it_in_its_extra_with_a_notice(home, store):
    _, outer, _ = small_map(store)
    layer = knowledge(store, 'subs')
    stored = store.add_subtype(layer.name, outer.join_id, 'code.loop.other', function='f', purpose='its own why')
    assert stored.extra == {'purpose': 'its own why'} and [notice.where for notice in stored.notices] == ['purpose']


@pytest.mark.req('STORE-011')
@pytest.mark.req('MAP-031')
@pytest.mark.req('LAYER-003')
def test_an_item_at_a_subtype_is_read_at_the_subtype_and_not_its_parent(store):
    _, outer, _ = small_map(store)
    subtype = store.subtypes(outer.join_id).results[0]
    notes = memory(store)
    store.add_item(notes.name, Node('subtype', subtype.subtype_id), 'The tick drifts under load.')
    assert values(store.node(Node('subtype', 'code.loop.tick')), 'memory') == ['The tick drifts under load.']
    assert values(store.node(Node('element', 'code.timer.kitchen')), 'memory') == []


@pytest.mark.req('STORE-011')
def test_a_subtype_address_held_by_another_is_stored_with_a_notice_naming_the_holder(home, store):
    _, outer, inner = small_map(store)
    tick = store.subtypes(outer.join_id).results[0]
    layer = knowledge(store, 'subs')
    twice = store.add_subtype(layer.name, inner.join_id, 'code.loop.tick', function='f')
    assert tick.subtype_id in twice.notices[0].message
    element = store.add_subtype(layer.name, inner.join_id, 'code.alarm.audible', function='f')
    assert 'element' in element.notices[0].message


@pytest.mark.req('STORE-012')
def test_add_ref_on_the_intake_layer_writes_nothing_and_names_a_correction(home, store):
    _, outer, _ = small_map(store)
    before = dump(store_file(home, store))
    untouched = store.add_ref(outer.join_id, 'path', 'more.c')
    assert [notice.where for notice in untouched.notices] == ['owner']
    assert 'op=correct' in untouched.notices[0].message
    assert dump(store_file(home, store)) == before


@pytest.mark.req('MAP-021')
def test_refs_keep_their_order_and_are_found_by_key_and_value(store):
    layer, outer, _ = small_map(store)
    extra = knowledge(store, 'group')
    store.add_element(extra.name, 'code.x')
    store.add_element(extra.name, 'code.y')
    grouped = store.add_join(extra.name, 'code.x', 'code.y', purpose='p', function='f', relation='r',
                             observation='o', refs=[('path', 'c.c'), ('path', 'a.c'), ('path', 'b.c')])
    assert [ref.value for ref in store.joins('code.x', raw=True).results[0].refs] == ['c.c', 'a.c', 'b.c']
    cited = store.citing('path', 'src/tick.c').results
    assert [(hit.kind, hit.address) for hit in cited] == [('subtype', 'code.loop.tick')]
    assert [hit.id for hit in store.citing('path', 'a.c').results] == [grouped.join_id]


@pytest.mark.req('MAP-020')
def test_a_join_reads_back_every_field_as_written(store):
    layer = knowledge(store, 'full')
    store.add_element(layer.name, 'code.a')
    store.add_element(layer.name, 'code.b')
    store.add_join(layer.name, 'code.a', 'code.b', purpose='the why', function='the how', relation='B serves A.',
                   observation='what is there', non_goal='not this', refs=[('path', 'a.c'), ('doc', 'README')])
    join = store.joins('code.a', raw=True).results[0]
    assert (join.type, join.purpose, join.function, join.relation, join.observation, join.non_goal) == (
        'purpose', 'the why', 'the how', 'B serves A.', 'what is there', 'not this')
    assert [(ref.key, ref.value) for ref in join.refs] == [('path', 'a.c'), ('doc', 'README')]


@pytest.mark.req('STORE-033')
def test_history_takes_a_bare_id_of_any_kind(store):
    layer, outer, _ = small_map(store)
    notes = memory(store)
    item = store.add_item(notes.name, Node('element', 'code.timer.kitchen'), 'x')
    element = store.element('code.timer.kitchen')
    subtype = store.subtypes(outer.join_id).results[0]
    for thing, kind in ((element.element_id, 'element'), (outer.join_id, 'join'),
                        (subtype.subtype_id, 'subtype'), (item.item_id, 'item')):
        versions = store.history(thing).results
        assert [version.kind for version in versions] == [kind]
        assert versions[0].op == 'add'
