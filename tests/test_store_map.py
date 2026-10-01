"""Storage of the map: identity, types, elements, joins, subtypes and refs."""
from __future__ import annotations

import re
import sqlite3

import pytest
from storekit import diff, dump, intake, knowledge, memory, small_map, store_file, values

from metaform.data import Node, StoreError

pytestmark = pytest.mark.kind('fixture')

ID = re.compile(r'^[0-9a-f]{32}$')


@pytest.mark.req('STORE-004')
def test_adding_one_ref_to_a_join_with_a_thousand_writes_one_row(home, store):
    layer = knowledge(store, 'refs')
    store.add_element(layer.name, 'code.a')
    store.add_element(layer.name, 'code.b')
    join = store.add_join(layer.name, 'code.a', 'code.b', purpose='p', ef='f', relation='r',
                          observation='o', refs=[('path', f'file{n}.c') for n in range(1000)])
    before = dump(store_file(home, store))
    store.add_ref(join.join_id, 'path', 'one-more.c')
    assert diff(before, dump(store_file(home, store))) == {'refs': (1, 0)}


@pytest.mark.req('STORE-007')
def test_identity_ids_are_32_lowercase_hex(store):
    layer, outer, _ = small_map(store)
    element = store.element('code.timer.kitchen')
    assert ID.match(element.element_id) and ID.match(outer.join_id) and ID.match(layer.layer_id)
    assert all(ID.match(sub.join_id) for sub in store.subtypes(outer.join_id).results)


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
    store.add_element(layer.name, 'exterior.person')
    assert store.children('').results == ('code', 'exterior')


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
def test_an_element_recorded_again_at_its_address_is_the_same_element_with_its_joins(store):
    layer = knowledge(store, 'again')
    first = store.add_element(layer.name, 'code.engine')
    store.add_element(layer.name, 'code.loop.main')
    join = store.add_join(layer.name, 'code.loop.main', 'code.engine', purpose='p', ef='f',
                          relation='runs the engine.', observation='o')
    store.remove(first.element_id)
    assert store.joins('code.engine', as_='provider', raw=True).results == ()
    again = store.add_element(layer.name, 'code.engine')
    assert again.element_id == first.element_id
    store.finish(layer.name)
    # The join reads back with the element as provider again: in context, not orphaned, and by the address too.
    served = store.joins(first.element_id, as_='provider').results
    assert [(held.join_id, held.provider_address, held.orphaned) for held in served] == [
        (join.join_id, 'code.engine', False)]
    assert [held.join_id for held in store.joins('code.engine', as_='provider').results] == [join.join_id]
    assert [held.join_id for held in store.joins('code.loop.main').results] == [join.join_id]
    assert store.joins('code.engine', as_='provider', raw=True).results[0].orphaned is False


@pytest.mark.req('STORE-009')
@pytest.mark.req('STORE-027')
def test_an_imported_elements_identity_comes_back_when_it_is_removed_and_recorded_again(store, monkeypatch,
                                                                                         tmp_path):
    from metaform.data import Store, export_document, import_document
    small_map(store)
    alarm = store.element('code.alarm.audible').element_id
    notes = memory(store)
    store.add_item(notes.name, Node('element', 'code.alarm.audible'), 'alarm memory')
    document = export_document(['proj'])
    monkeypatch.setenv('METAFORM_HOME', str(tmp_path / 'other-home'))
    import_document(document)
    moved = Store('proj')
    moved.refine(alarm, remove=True, reason='gone')
    assert moved.element('code.alarm.audible') is None
    put = moved.add_element('intake-1', 'code.alarm.audible', role='SE')
    assert put.element_id == alarm and moved.element('code.alarm.audible').element_id == alarm
    assert values(moved.node(Node('element', 'code.alarm.audible')), 'memory') == ['alarm memory']
    assert [held.join_id for held in moved.joins('code.timer.kitchen').results] == [
        held.join_id for held in store.joins('code.timer.kitchen').results]


@pytest.mark.req('STORE-009')
def test_an_item_attached_to_an_element_reads_back_after_it_is_removed_and_recorded_again(store):
    layer = knowledge(store, 'again')
    first = store.add_element(layer.name, 'code.engine')
    notes = memory(store)
    store.add_item(notes.name, Node('element', 'code.engine'), 'The engine idles at 3am.')
    store.remove(first.element_id)
    assert store.node(Node('element', 'code.engine'), raw=True) is None
    store.add_element(layer.name, 'code.engine')
    assert values(store.node(Node('element', 'code.engine'), raw=True), 'memory') == ['The engine idles at 3am.']


@pytest.mark.req('STORE-009')
@pytest.mark.req('MAP-015')
@pytest.mark.req('MAP-012')
def test_an_element_is_its_address_name_length_and_role(home, store):
    """Rich, 2026-09-27: the namespace address is the name index, the element was meant to be only its address and
    name_length, and roles stay on the element; its proper noun is its address read backward through name_length."""
    knowledge(store, 'first')
    before = dump(store_file(home, store))
    with store.atomic():
        layer = intake(store)
        store.add_element(layer.name, 'code.timer.kitchen', name_length=2, role='DE', refs=[('path', 'src/main.c')])
    changed = diff(before, dump(store_file(home, store)))
    assert changed['elements'] == (1, 0) and changed['refs'] == (1, 0) and 'items' not in changed
    element = store.element('code.timer.kitchen')
    assert (element.address, element.name_length, element.role, element.short_name, element.reading) == (
        'code.timer.kitchen', 2, 'DE', 'kitchen timer', 'kitchen timer code')
    assert [(ref.key, ref.value) for ref in element.refs] == [('path', 'src/main.c')]
    # Rich, 2026-10-01: a name goes anywhere there is a namespace and name length; it is the element's own field
    assert 'descriptors' not in element.to_dict() and element.name is None
    columns = {row[1] for row in sqlite3.connect(store_file(home, store)).execute('PRAGMA table_info(elements)')}
    assert {'name_length', 'name', 'role'} <= columns


@pytest.mark.req('STORE-009')
@pytest.mark.req('MAP-017')
@pytest.mark.req('BASE-044')
def test_an_element_a_knowledge_layer_adds_carries_no_role_and_keeps_a_given_one_in_its_extra(store):
    layer = knowledge(store, 'notes')
    made = store.add_element(layer.name, 'code.cache.page', name_length=2, role='SE')
    assert (made.name_length, made.role, made.extra) == (2, None, {'role': 'SE'})
    assert [notice.where for notice in made.notices] == ['role']
    assert store.element('code.cache.page', raw=True).short_name == 'page cache'


@pytest.mark.req('STORE-009')
@pytest.mark.req('BASE-044')
def test_an_element_another_layer_holds_keeps_its_own_name_length_and_role(home, store):
    small_map(store)
    notes = knowledge(store, 'notes')
    before = dump(store_file(home, store))
    again = store.add_element(notes.name, 'code.timer.kitchen', name_length=1, role='SE', refs=[('path', 'x.c')])
    assert again.existing is True and again.differs is True
    assert (again.name_length, again.role, again.short_name) == (2, 'DE', 'kitchen timer')
    assert [notice.where for notice in again.notices] == ['name_length', 'role', 'refs']
    assert all('intake-1' in notice.message for notice in again.notices)
    assert diff(before, dump(store_file(home, store))) == {}
    same = store.add_element(notes.name, 'code.timer.kitchen', name_length=2, role='DE')
    assert same.existing is True and same.differs is False and same.notices == ()


@pytest.mark.req('STORE-010')
@pytest.mark.req('MAP-020')
def test_a_join_carries_the_projects_name_for_its_functionality(home, store):
    """Rich, 2026-09-27: the project's own name for a functionality goes on the join, which speaks to the artifact."""
    layer = knowledge(store, 'named')
    store.add_element(layer.name, 'code.a')
    store.add_element(layer.name, 'code.b')
    named = store.add_join(layer.name, 'code.a', 'code.b', name='the b service', purpose='p', ef='f',
                           relation='B serves A.', observation='o')
    plain = store.add_join(layer.name, 'code.b', 'code.a', purpose='q', ef='g', relation='A serves B.',
                           observation='o')
    assert (named.name, plain.name) == ('the b service', None)
    assert [join.name for join in store.joins('code.a', raw=True).results] == ['the b service']
    assert [join.name for join in store.joins('code.a', as_='provider', raw=True).results] == [None]
    store.edit(plain.join_id, {'name': 'the a service'})
    assert [join.name for join in store.joins('code.a', as_='provider', raw=True).results] == ['the a service']
    columns = {row[1] for row in sqlite3.connect(store_file(home, store)).execute('PRAGMA table_info(joins)')}
    assert 'name' in columns


@pytest.mark.req('STORE-010')
@pytest.mark.req('MAP-002')
@pytest.mark.req('MAP-003')
def test_two_elements_may_each_receive_from_the_other(store):
    layer = knowledge(store, 'mutual')
    store.add_element(layer.name, 'code.a')
    store.add_element(layer.name, 'code.b')
    ab = store.add_join(layer.name, 'code.a', 'code.b', purpose='A needs B', ef='B serves A',
                        relation='B serves A.', observation='o1')
    ba = store.add_join(layer.name, 'code.b', 'code.a', purpose='B needs A', ef='A serves B',
                        relation='A serves B.', observation='o2')
    owned = store.joins('code.a', raw=True).results
    provided = store.joins('code.a', as_='provider', raw=True).results
    assert [join.join_id for join in owned] == [ab.join_id]
    assert [join.join_id for join in provided] == [ba.join_id]
    assert (owned[0].purpose, provided[0].purpose) == ('A needs B', 'B needs A')


@pytest.mark.req('STORE-010')
@pytest.mark.req('MAP-031')
@pytest.mark.req('MAP-030')
def test_a_subtype_join_is_never_a_join_end_and_the_element_it_holds_is_an_ordinary_element(home, store):
    _, outer, _ = small_map(store)
    subtype = store.subtypes(outer.join_id).results[0]
    layer = knowledge(store, 'ends')
    before = dump(store_file(home, store))
    with pytest.raises(StoreError) as refused:
        store.add_join(layer.name, 'code.timer.kitchen', subtype.join_id, purpose='p', ef='f',
                       relation='r', observation='o')
    assert refused.value.next_step
    assert dump(store_file(home, store)) == before
    stored = store.add_join(layer.name, 'code.timer.kitchen', 'code.loop.tick', purpose='p', ef='f',
                            relation='r', observation='o')
    assert stored.notices == () and stored.provider == subtype.element_id
    assert store.element('code.loop.tick', raw=True).layer == 'intake-1'


@pytest.mark.req('STORE-011')
@pytest.mark.req('MAP-030')
@pytest.mark.req('MAP-031')
def test_a_subtype_join_is_read_only_through_its_join(store):
    _, outer, _ = small_map(store)
    subtypes = store.subtypes(outer.join_id).results
    assert [(sub.address, sub.ef, sub.parent, sub.type) for sub in subtypes] == [
        ('code.loop.tick', 'Advances each countdown.', outer.join_id, 'subtype')]
    tick = subtypes[0].join_id
    reads = [*store.joins('code.timer.kitchen').results, *store.joins('code.timer.kitchen', as_='provider').results,
             *store.identity('code.timer.kitchen').results, *store.joins('code.loop.tick', raw=True).results,
             *store.joins('code.loop.tick', as_='provider', raw=True).results,
             *(join for entry in store.roots().entry for join in entry.joins)]
    assert reads and tick not in [join.join_id for join in reads]
    where = store.where('code.loop.tick')
    assert where.kind == 'subtype' and where.join.join_id == outer.join_id and where.subtype.join_id == tick
    assert (where.join.receiver_address, where.join.provider_address) == ('stakeholder.cook.home', 'code.timer.kitchen')


@pytest.mark.req('STORE-011')
@pytest.mark.req('MAP-030')
def test_a_subtype_join_holds_the_purpose_it_is_given_as_its_own(home, store):
    _, outer, _ = small_map(store)
    layer = knowledge(store, 'subs')
    stored = store.add_subtype(layer.name, outer.join_id, 'code.loop.other', ef='f', purpose='its own why')
    assert stored.purpose == 'its own why' and stored.extra is None and stored.notices == ()
    read = lambda: next(sub for sub in store.subtypes(outer.join_id, raw=True).results if sub.join_id == stored.join_id)
    assert read().purpose == 'its own why'
    changed = store.edit(stored.join_id, {'purpose': 'a better why'})
    assert changed.notices == () and read().purpose == 'a better why'
    assert store.element('code.loop.other', raw=True).element_id == stored.element_id


@pytest.mark.req('STORE-011')
@pytest.mark.req('MAP-031')
@pytest.mark.req('LAYER-003')
def test_an_item_at_a_subtype_join_is_read_at_that_join_and_one_at_its_element_at_the_element(store):
    _, outer, _ = small_map(store)
    subtype = store.subtypes(outer.join_id).results[0]
    notes = memory(store)
    store.add_item(notes.name, Node('join', subtype.join_id), 'The tick drifts under load.')
    store.add_item(notes.name, Node('element', 'code.loop.tick'), 'One loop for every timer.')
    assert values(store.node(Node('join', subtype.join_id)), 'memory') == ['The tick drifts under load.']
    assert values(store.node(Node('element', 'code.loop.tick')), 'memory') == ['One loop for every timer.']
    assert values(store.node(Node('join', outer.join_id)), 'memory') == []
    assert values(store.node(Node('element', 'code.timer.kitchen')), 'memory') == []


@pytest.mark.req('STORE-011')
@pytest.mark.req('MAP-032')
def test_an_element_held_by_a_subtype_join_held_again_is_stored_with_a_notice_naming_the_first(store):
    _, outer, inner = small_map(store)
    tick = store.subtypes(outer.join_id).results[0]
    layer = knowledge(store, 'subs')
    twice = store.add_subtype(layer.name, inner.join_id, 'code.loop.tick', ef='f', name_length=1)
    assert twice.element_id == tick.element_id
    assert tick.join_id in ' '.join(notice.message for notice in twice.notices)
    assert 'name_length' in [notice.where for notice in twice.notices]
    assert store.element('code.loop.tick').name_length == 2
    alarm = store.add_subtype(layer.name, outer.join_id, 'code.alarm.audible', ef='f')
    assert alarm.notices == () and alarm.element_id == store.element('code.alarm.audible').element_id


@pytest.mark.req('STORE-012')
@pytest.mark.req('LAYER-025')
def test_add_ref_on_the_finished_intake_adds_the_ref_to_the_current_version(store):
    _, outer, _ = small_map(store)
    added = store.add_ref(outer.join_id, 'path', 'more.c')
    assert (added.key, added.value) == ('path', 'more.c')
    assert [(ref.key, ref.value) for ref in store.joins('stakeholder.cook.home').results[0].refs] == [
        ('path', 'src'), ('path', 'more.c')]


@pytest.mark.req('MAP-021')
def test_refs_keep_their_order_and_are_found_by_key_and_value(store):
    layer, outer, _ = small_map(store)
    extra = knowledge(store, 'group')
    store.add_element(extra.name, 'code.x')
    store.add_element(extra.name, 'code.y')
    grouped = store.add_join(extra.name, 'code.x', 'code.y', purpose='p', ef='f', relation='r',
                             observation='o', refs=[('path', 'c.c'), ('path', 'a.c'), ('path', 'b.c')])
    assert [ref.value for ref in store.joins('code.x', raw=True).results[0].refs] == ['c.c', 'a.c', 'b.c']
    cited = store.citing('path', 'src/tick.c').results
    tick = store.subtypes(outer.join_id).results[0]
    assert [(hit.kind, hit.id) for hit in cited] == [('join', tick.join_id)]
    assert [hit.id for hit in store.citing('path', 'a.c').results] == [grouped.join_id]


@pytest.mark.req('MAP-020')
def test_a_join_reads_back_every_field_as_written(store):
    layer = knowledge(store, 'full')
    store.add_element(layer.name, 'code.a')
    store.add_element(layer.name, 'code.b')
    store.add_join(layer.name, 'code.a', 'code.b', name='b', purpose='the why', ef='the how',
                   relation='B serves A.', observation='what is there', non_goal='not this',
                   refs=[('path', 'a.c'), ('doc', 'README')])
    join = store.joins('code.a', raw=True).results[0]
    assert (join.type, join.name, join.purpose, join.ef, join.relation, join.observation, join.non_goal) == (
        'purpose', 'b', 'the why', 'the how', 'B serves A.', 'what is there', 'not this')
    assert [(ref.key, ref.value) for ref in join.refs] == [('path', 'a.c'), ('doc', 'README')]


@pytest.mark.req('STORE-033')
def test_history_takes_a_bare_id_of_any_kind(store):
    layer, outer, _ = small_map(store)
    notes = memory(store)
    item = store.add_item(notes.name, Node('element', 'code.timer.kitchen'), 'x')
    element = store.element('code.timer.kitchen')
    subtype = store.subtypes(outer.join_id).results[0]
    for thing, kind in ((element.element_id, 'element'), (outer.join_id, 'join'),
                        (subtype.join_id, 'join'), (item.item_id, 'item')):
        versions = store.history(thing).results
        assert [version.kind for version in versions] == [kind]
        assert versions[0].op == 'add'


def failsafe(store, name='notes'):
    """A knowledge layer where a daemon receives from a gateway failsafe and from an echo probe the failsafe could
    absorb, and an alarm receives from the probe too."""
    layer = knowledge(store, name)
    for address in ('code.daemon', 'code.failsafe.gateway', 'code.probe.echo', 'code.alarm'):
        store.add_element(layer.name, address, name_length=1)
    parent = store.add_join(layer.name, 'code.daemon', 'code.failsafe.gateway', name='gateway failsafe',
                            purpose='Catch a dead gateway.', ef='Probes the gateway and fails over.',
                            relation='The failsafe watches the gateway.', observation='Two probes.')
    probe = store.add_join(layer.name, 'code.daemon', 'code.probe.echo', name='echo probe',
                           purpose='Know the gateway answers.', ef='Sends an echo each second.', perspective='Function',
                           relation='The echo probe pings the gateway.', verb='pings', observation='ICMP echo.',
                           non_goal='Measure latency.', refs=[('path', 'src/echo.c')])
    other = store.add_join(layer.name, 'code.alarm', 'code.probe.echo', purpose='Hear a dead gateway.',
                           ef='Reports a lost echo.', relation='The echo probe tells the alarm.',
                           observation='One report per loss.')
    return layer, parent, probe, other


@pytest.mark.req('MAP-003')
@pytest.mark.req('STORE-010')
@pytest.mark.req('STORE-007')
def test_a_join_moved_to_another_receiver_keeps_its_id_and_its_memory(store):
    layer = knowledge(store, 'notes')
    for address in ('code.a', 'code.b', 'code.c'):
        store.add_element(layer.name, address)
    join = store.add_join(layer.name, 'code.a', 'code.b', name='b', purpose='p', ef='f', relation='r',
                          observation='o')
    notes = memory(store)
    store.add_item(notes.name, Node('join', join.join_id), 'watch this one')
    moved = store.edit(join.join_id, {'receiver': 'code.c'})
    assert moved.notices == ()
    found = store.joins('code.c', raw=True).results
    assert [(held.join_id, held.receiver_address, held.name) for held in found] == [(join.join_id, 'code.c', 'b')]
    assert store.joins('code.a', raw=True).results == ()
    assert values(store.node(Node('join', join.join_id), raw=True), 'memory') == ['watch this one']


@pytest.mark.req('MAP-030')
@pytest.mark.req('MAP-003')
@pytest.mark.req('STORE-034')
def test_absorbing_a_join_makes_it_a_subtype_join_with_its_id_its_fields_and_what_is_attached(store):
    layer, parent, probe, other = failsafe(store)
    notes = memory(store)
    store.add_item(notes.name, Node('join', probe.join_id), 'The echo is lost under load.')
    element = store.element('code.probe.echo', raw=True)
    absorbed = store.edit(probe.join_id, {'parent': parent.join_id})
    assert other.join_id in ' '.join(notice.message for notice in absorbed.notices)
    held = store.subtypes(parent.join_id, raw=True).results
    assert [sub.join_id for sub in held] == [probe.join_id]
    sub = held[0]
    assert (sub.parent, sub.type, sub.element_id, sub.address, sub.name, sub.ef, sub.perspective, sub.relation, sub.verb,
            sub.observation, sub.non_goal) == (
        parent.join_id, 'subtype', element.element_id, 'code.probe.echo', 'echo probe', 'Sends an echo each second.',
        'Function', 'The echo probe pings the gateway.', 'pings', 'ICMP echo.', 'Measure latency.')
    assert [(ref.key, ref.value) for ref in sub.refs] == [('path', 'src/echo.c')]
    assert sub.purpose == 'Know the gateway answers.' and sub.extra is None  # absorbed, it keeps its purpose
    assert [join.join_id for join in store.joins('code.daemon', raw=True).results] == [parent.join_id]
    assert [join.join_id for join in store.joins('code.alarm', raw=True).results] == [other.join_id]
    assert store.element('code.probe.echo', raw=True) == element
    assert values(store.node(Node('join', probe.join_id), raw=True), 'memory') == ['The echo is lost under load.']


@pytest.mark.req('MAP-031')
@pytest.mark.req('STORE-011')
@pytest.mark.req('STORE-025')
def test_an_element_held_only_by_subtype_joins_is_no_root_and_no_node_of_the_outer_map(store):
    _, outer, _ = small_map(store)
    tick = store.element('code.loop.tick')
    assert tick is not None and (tick.name_length, tick.role, tick.short_name) == (2, 'SE', 'tick loop')
    sub = store.subtypes(outer.join_id).results[0]
    assert (sub.element_id, sub.address, sub.name_length, sub.role, sub.short_name) == (
        tick.element_id, 'code.loop.tick', 2, 'SE', 'tick loop')
    assert 'code.loop.tick' not in [root.address for root in store.roots().elements]
    graph = store.graph()
    assert 'code.loop.tick' not in [placed.element.address for placed in graph.elements]
    assert [held.join_id for join in graph.joins for held in join.subtypes] == [sub.join_id]
    where = store.where('code.loop.tick')
    assert (where.kind, where.element.element_id, where.subtype.join_id, where.join.join_id) == (
        'subtype', tick.element_id, sub.join_id, outer.join_id)
    extra = knowledge(store, 'extra')
    store.add_element(extra.name, 'code.clock')
    store.add_join(extra.name, 'code.loop.tick', 'code.clock', purpose='p', ef='f', relation='r',
                   observation='o')
    store.finish(extra.name)
    assert 'code.loop.tick' in [placed.element.address for placed in store.graph().elements]
    tick_now = store.where('code.loop.tick')
    assert (tick_now.kind, tick_now.subtype.join_id, tick_now.join.join_id) == ('element', sub.join_id, outer.join_id)


@pytest.mark.req('MAP-032')
@pytest.mark.req('STORE-011')
def test_a_subtype_join_sits_only_inside_a_join_held_by_a_receiver(home, store):
    _, outer, _ = small_map(store)
    sub = store.subtypes(outer.join_id).results[0]
    layer, _, probe, _ = failsafe(store)
    before = dump(store_file(home, store))
    for attempt in (lambda: store.add_subtype(layer.name, sub.join_id, 'code.loop.inner', ef='f'),
                    lambda: store.edit(probe.join_id, {'parent': sub.join_id}),
                    lambda: store.edit(probe.join_id, {'parent': probe.join_id})):
        with pytest.raises(StoreError) as refused:
            attempt()
        assert refused.value.next_step
    assert dump(store_file(home, store)) == before


@pytest.mark.req('MAP-032')
@pytest.mark.req('STORE-034')
def test_absorbing_a_join_that_holds_a_subtype_join_passes_that_one_to_the_new_parent(store):
    layer = knowledge(store, 'notes')
    for address in ('code.a', 'code.p', 'code.q', 'code.t'):
        store.add_element(layer.name, address)
    parent = store.add_join(layer.name, 'code.a', 'code.p', purpose='p', ef='f', relation='r', observation='o')
    part = store.add_join(layer.name, 'code.a', 'code.q', purpose='q', ef='g', relation='r', observation='o')
    inner = store.add_subtype(layer.name, part.join_id, 'code.t', ef='h')
    absorbed = store.edit(part.join_id, {'parent': parent.join_id})
    assert inner.join_id in ' '.join(notice.message for notice in absorbed.notices)
    assert sorted(sub.join_id for sub in store.subtypes(parent.join_id, raw=True).results) == sorted(
        [part.join_id, inner.join_id])
    assert store.subtypes(part.join_id, raw=True).results == ()


@pytest.mark.req('STORE-029')
@pytest.mark.req('STORE-010')
@pytest.mark.req('STORE-011')
def test_a_subtype_join_is_a_row_of_joins_and_a_joins_identity_holds_no_receiver(home, store):
    small_map(store)
    db = sqlite3.connect(store_file(home, store))
    try:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        columns = {table: [row[1] for row in db.execute(f'PRAGMA table_info({table})')]
                   for table in ('join_ids', 'joins', 'current_elements', 'current_subtypes')}
        version = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
        kinds = {row[0] for row in db.execute('SELECT type FROM joins')}
    finally:
        db.close()
    assert 'subtypes' not in tables and 'subtype_ids' not in tables and 'unapplied' not in tables
    assert columns['join_ids'] == ['join_id'] and 'parent' in columns['joins'] and 'stack_at' not in columns['joins']
    assert 'moved' not in columns['current_elements']
    assert columns['current_subtypes'] == ['join_id', 'row', 'parent', 'provider']
    assert version == '10' and kinds == {'purpose', 'subtype'}  # layout 9: tickets keep their kind, D92; 8 kept every version in its layer, LAYER-025
    assert 'correction_stack' not in tables
