"""Storage of the map: identity, types, elements, joins and the elements they hold, and refs."""
from __future__ import annotations

import dataclasses
import re
import sqlite3

import pytest
from storekit import diff, dump, intake, knowledge, memory, ops, small_map, store_file, values

from metaform.data import Node, Store

pytestmark = pytest.mark.kind('fixture')

ID = re.compile(r'^[0-9a-f]{32}$')


@pytest.mark.req('STORE-004')
def test_adding_one_ref_to_an_item_with_a_thousand_writes_one_row(home, store):
    layer = knowledge(store, 'refs')
    store.add_element(layer.name, 'code.a')
    item = store.add_item(layer.name, Node('element', 'code.a'), 'a', refs=[('path', f'file{n}.c') for n in range(1000)])
    before = dump(store_file(home, store))
    store.add_ref(item.id, 'path', 'one-more.c')
    assert diff(before, dump(store_file(home, store))) == {'ops': (1, 0)}  # one op carries the refs, STORE-046


@pytest.mark.req('STORE-007')
def test_identity_ids_are_32_lowercase_hex(store):
    layer, outer, _ = small_map(store)
    element = store.element('code.timer.kitchen')
    assert ID.match(element.id) and ID.match(outer.id) and ID.match(layer.id)


@pytest.mark.req('STORE-008')
@pytest.mark.req('MAP-010')
def test_an_address_writes_itself_and_every_prefix_as_types(home, store):
    layer = knowledge(store, 'types')
    store.add_element(layer.name, 'code.engine.game.fps')
    with Store('proj')._read() as tx:  # the Type tree is read from the projection, STORE-046
        types = dict(tx.base.types)
    assert set(types.items()) == {
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
    assert store.where('Code..Engine', raw=True).element.id == odd.id
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
    assert item.target == Node('element', made.id) and item.value == 'A note about BOMs.'
    assert [notice.where for notice in item.notices] == ['target']
    assert 'data.bill_of_materials' in item.notices[0].message
    changed = diff(before, dump(store_file(home, store)))
    assert changed['ops'] == (2, 0) and changed['objects'] == (2, 0)  # the element and the item, STORE-046


@pytest.mark.req('STORE-009')
@pytest.mark.req('MAP-016')
def test_a_second_element_at_a_held_address_returns_the_first(home, store):
    layer = knowledge(store, 'els')
    first = store.add_element(layer.name, 'code.engine')
    before = dump(store_file(home, store))
    second = store.add_element(layer.name, 'code.engine')
    assert second.id == first.id and second.existing is True
    assert 'elements' not in diff(before, dump(store_file(home, store)))


@pytest.mark.req('STORE-009')
def test_an_element_recorded_again_at_its_address_is_the_same_element_with_its_joins(store):
    layer = knowledge(store, 'again')
    first = store.add_element(layer.name, 'code.engine')
    store.add_element(layer.name, 'code.loop.main')
    join = store.add_join(layer.name, 'code.loop.main', 'code.engine', purpose='p', ef='f')
    store.remove(first.id)
    assert store.joins('code.engine', as_='provider', raw=True).results == ()
    again = store.add_element(layer.name, 'code.engine')
    assert again.id == first.id
    store.finish(layer.name)
    # The join reads back with the element as provider again: in context, not orphaned, and by the address too.
    served = store.joins(first.id, as_='provider').results
    assert [(held.id, [each.address for each in held.elements], held.orphaned) for held in served] == [
        (join.id, ['code.engine'], False)]
    assert [held.id for held in store.joins('code.engine', as_='provider').results] == [join.id]
    assert [held.id for held in store.joins('code.loop.main').results] == [join.id]
    assert store.joins('code.engine', as_='provider', raw=True).results[0].orphaned is False


@pytest.mark.req('STORE-009')
@pytest.mark.req('STORE-027')
def test_an_imported_elements_identity_comes_back_when_it_is_removed_and_recorded_again(store, monkeypatch,
                                                                                         tmp_path):
    from metaform.data import Store, export_document, import_document
    small_map(store)
    alarm = store.element('code.alarm.audible').id
    notes = memory(store)
    store.add_item(notes.name, Node('element', 'code.alarm.audible'), 'alarm memory')
    document = export_document(['proj'])
    monkeypatch.setenv('METAFORM_HOME', str(tmp_path / 'other-home'))
    import_document(document)
    moved = Store('proj')
    moved.refine(alarm, remove=True, reason='gone')
    assert moved.element('code.alarm.audible') is None
    put = moved.add_element('intake-1', 'code.alarm.audible', role='SE')
    assert put.id == alarm and moved.element('code.alarm.audible').id == alarm
    assert values(moved.node(Node('element', 'code.alarm.audible')), 'memory') == ['alarm memory']
    assert [held.id for held in moved.joins('code.timer.kitchen').results] == [
        held.id for held in store.joins('code.timer.kitchen').results]


@pytest.mark.req('STORE-009')
def test_an_item_attached_to_an_element_reads_back_after_it_is_removed_and_recorded_again(store):
    layer = knowledge(store, 'again')
    first = store.add_element(layer.name, 'code.engine')
    notes = memory(store)
    store.add_item(notes.name, Node('element', 'code.engine'), 'The engine idles at 3am.')
    store.remove(first.id)
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
        store.add_element(layer.name, 'code.timer.kitchen', name_length=2, role='DE')
    changed = diff(before, dump(store_file(home, store)))
    assert changed == {'ops': (2, 0), 'objects': (1, 0)}  # the layer and the element alone: no ref, no item, STORE-046
    element = store.element('code.timer.kitchen')
    assert (element.address, element.name_length, element.role, element.short_name, element.reading) == (
        'code.timer.kitchen', 2, 'DE', 'kitchen timer', 'kitchen timer code')
    # Rich, 2026-10-04: an element is its address, name_length, name and role; its refs are in the sources layer
    assert 'refs' not in element.to_dict() and 'extra' not in element.to_dict()
    # Rich, 2026-10-01: a name goes anywhere there is a namespace and name length; it is the element's own field
    assert 'descriptors' not in element.to_dict() and element.name is None
    [made] = [op for op in ops(store_file(home, store), 'element') if op['id'] == element.id]
    assert {'name_length', 'name', 'role'} <= set(made['data'])  # the element's own fields, on its op


@pytest.mark.req('STORE-009')
@pytest.mark.req('MAP-017')
@pytest.mark.req('BASE-044')
def test_a_role_given_to_an_element_of_a_knowledge_layer_is_kept_in_that_layer_and_never_on_the_element(store):
    """A role is the intake's classification of the artifact, D48: one given in a knowledge layer is not the element's
    role; it is kept as an item of that layer at the element and named in a notice, BASE-044."""
    from metaform.data import Node
    layer = knowledge(store, 'notes')
    made = store.add_element(layer.name, 'code.cache.page', name_length=2, role='SE')
    assert (made.name_length, made.role) == (2, None)
    assert [notice.where for notice in made.notices] == ['role']
    assert [item.value for item in store.layer_items(layer.name, Node('element', 'code.cache.page')).results] == [
        {'role': 'SE'}]
    assert store.element('code.cache.page', raw=True).short_name == 'page cache'


@pytest.mark.req('STORE-009')
@pytest.mark.req('BASE-044')
def test_an_element_another_layer_holds_keeps_its_own_name_length_and_role(home, store):
    small_map(store)
    notes = knowledge(store, 'notes')
    before = dump(store_file(home, store))
    again = store.add_element(notes.name, 'code.timer.kitchen', name_length=1, role='SE')
    assert again.existing is True and again.differs is True
    assert (again.name_length, again.role, again.short_name) == (2, 'DE', 'kitchen timer')
    assert [notice.where for notice in again.notices] == ['name_length', 'role']
    assert all('intake-1' in notice.message for notice in again.notices)
    assert diff(before, dump(store_file(home, store))) == {}
    same = store.add_element(notes.name, 'code.timer.kitchen', name_length=2, role='DE', name='kitchen timer')
    assert same.existing is True and same.differs is False and same.notices == ()



@pytest.mark.req('STORE-010')
@pytest.mark.req('MAP-002')
@pytest.mark.req('MAP-003')
def test_two_elements_may_each_receive_from_the_other(store):
    layer = knowledge(store, 'mutual')
    store.add_element(layer.name, 'code.a')
    store.add_element(layer.name, 'code.b')
    ab = store.add_join(layer.name, 'code.a', 'code.b', purpose='A needs B', ef='B serves A')
    ba = store.add_join(layer.name, 'code.b', 'code.a', purpose='B needs A', ef='A serves B')
    owned = store.joins('code.a', raw=True).results
    provided = store.joins('code.a', as_='provider', raw=True).results
    assert [join.id for join in owned] == [ab.id]
    assert [join.id for join in provided] == [ba.id]
    assert (owned[0].purpose, provided[0].purpose) == ('A needs B', 'B needs A')








@pytest.mark.req('MAP-021')
def test_refs_keep_their_order_and_are_found_by_key_and_value(store):
    small_map(store)
    sources = knowledge(store, 'sources')
    grouped = store.add_item(sources.name, Node('element', 'code.loop.tick'), 'code.loop.tick',
                             refs=[('path', 'c.c'), ('path', 'a.c'), ('path', 'b.c')])
    held = store.layer_items(sources.name, Node('element', 'code.loop.tick')).results
    assert [ref.value for ref in held[0].refs] == ['c.c', 'a.c', 'b.c']
    cited = store.citing('path', 'a.c').results
    assert [(hit.kind, hit.object_id, hit.address, hit.layer) for hit in cited] == [
        ('item', grouped.id, 'code.loop.tick', 'sources')]


@pytest.mark.req('MAP-020')
def test_a_join_reads_back_every_field_as_written(store):
    layer = knowledge(store, 'full')
    store.add_element(layer.name, 'code.a')
    store.add_element(layer.name, 'code.b')
    store.add_element(layer.name, 'code.c')
    store.add_join(layer.name, 'code.a', ['code.b', 'code.c'], purpose='the why', ef='serves a', ifd='receives')
    join = store.joins('code.a', raw=True).results[0]
    assert (join.type, join.purpose, join.ef, join.ifd, [each.address for each in join.elements]) == (
        'purpose', 'the why', 'serves a', 'receives', ['code.b', 'code.c'])


@pytest.mark.req('MAP-020')
def test_a_join_holds_no_relation_and_no_observation(store):
    """Rich, 2026-10-02: "observation was not my design. I didn't ask for observation"; "Neither was relation". The
    metaform is a map that points to the code, never documentation: neither field is stored, read or taken."""
    from metaform.data import Join
    from metaform.data.schema import STORE_SCHEMA
    fields = {field.name for field in dataclasses.fields(Join)}
    assert not {'relation', 'observation'} & fields
    assert 'relation' not in STORE_SCHEMA and 'observation' not in STORE_SCHEMA
    layer = knowledge(store, 'full')
    store.add_element(layer.name, 'code.a')
    store.add_element(layer.name, 'code.b')
    for name in ('relation', 'observation'):
        with pytest.raises(TypeError):
            store.add_join(layer.name, 'code.a', 'code.b', purpose='p', ef='f', **{name: 'text'})


@pytest.mark.req('STORE-033')
def test_history_takes_a_bare_id_of_any_kind(store):
    _, outer, _ = small_map(store)
    notes = memory(store)
    item = store.add_item(notes.name, Node('element', 'code.timer.kitchen'), 'x')
    element = store.element('code.timer.kitchen')
    for thing, kind in ((element.id, 'element'), (outer.id, 'join'), (item.id, 'item')):
        versions = store.history(thing).results
        assert [version.kind for version in versions] == [kind]
        assert versions[0].op == 'add'


def failsafe(store, name='notes'):
    """A knowledge layer where a daemon receives from a gateway failsafe and from an echo probe the failsafe could
    absorb, and an alarm receives from the probe too."""
    layer = knowledge(store, name)
    for address in ('code.daemon', 'code.failsafe.gateway', 'code.probe.echo', 'code.alarm'):
        store.add_element(layer.name, address, name_length=1)
    parent = store.add_join(layer.name, 'code.daemon', 'code.failsafe.gateway',
                            purpose='Catch a dead gateway.', ef='Probes the gateway and fails over.')
    probe = store.add_join(layer.name, 'code.daemon', 'code.probe.echo',
                           purpose='Know the gateway answers.', ef='Sends an echo each second.')
    other = store.add_join(layer.name, 'code.alarm', 'code.probe.echo', purpose='Hear a dead gateway.',
                           ef='Reports a lost echo.')
    return layer, parent, probe, other


@pytest.mark.req('MAP-003')
@pytest.mark.req('STORE-010')
@pytest.mark.req('STORE-007')
def test_a_join_moved_to_another_receiver_keeps_its_id_and_its_memory(store):
    layer = knowledge(store, 'notes')
    for address in ('code.a', 'code.b', 'code.c'):
        store.add_element(layer.name, address)
    join = store.add_join(layer.name, 'code.a', 'code.b', purpose='p', ef='f')
    notes = memory(store)
    store.add_item(notes.name, Node('join', join.id), 'watch this one')
    moved = store.edit(join.id, {'receiver': 'code.c'})
    assert moved.notices == ()
    found = store.joins('code.c', raw=True).results
    assert [(held.id, held.receiver_address, held.purpose) for held in found] == [(join.id, 'code.c', 'p')]
    assert store.joins('code.a', raw=True).results == ()
    assert values(store.node(Node('join', join.id), raw=True), 'memory') == ['watch this one']






@pytest.mark.req('STORE-029')
@pytest.mark.req('STORE-010')
def test_a_join_holds_its_elements_in_rows_of_their_own_and_a_joins_identity_holds_no_receiver(home, store):
    small_map(store)
    db = sqlite3.connect(store_file(home, store))
    try:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        version = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
    finally:
        db.close()
    assert not {'subtypes', 'subtype_ids', 'unapplied', 'current_subtypes', 'joins', 'join_elements'} & tables
    joins = ops(store_file(home, store), 'join')
    assert {op['data']['type'] for op in joins} == {'purpose'}  # MAP-054 adds the optional promotion address.
    assert sum(len(op['data']['held']) for op in joins) == 3  # a join holds its elements in order, STORE-046
    assert all(set(op['data']) >= {'type', 'receiver', 'purpose', 'ef', 'ifd', 'element', 'held'} for op in joins)
    assert version == '21'
    assert 'correction_stack' not in tables


@pytest.mark.req('MAP-020')
def test_a_join_has_no_perspective_field_anywhere_in_the_store(home, store):
    """Rich, 2026-10-02: "drop perspective drop the duality , EF infers fine". No column, record field, editable field
    or word list holds it; a perspective given to a refinement is not a field of a join, so it is named and not
    applied, as any other unknown key is, STORE-034."""
    import dataclasses

    from metaform import data
    from metaform.data import Join, rows
    _, outer, _ = small_map(store)
    db = sqlite3.connect(store_file(home, store))
    try:
        columns = [row[1] for row in db.execute('PRAGMA table_info(joins)')]
    finally:
        db.close()
    assert 'perspective' not in columns
    assert not hasattr(data, 'PERSPECTIVES')
    assert 'perspective' not in {field.name for field in dataclasses.fields(Join)}
    assert 'perspective' not in rows.EDITABLE['join']
    assert 'perspective' not in store.where('code.timer.kitchen', full=True).to_dict()['provides'][0]
    refined = store.refine(outer.id, {'perspective': 'Encounter', 'purpose': 'Know when it is done.'}, reason='r')
    assert [notice.where for notice in refined.notices] == ['perspective']
    kept = next(join for join in store.joins('stakeholder.cook.home').results if join.id == outer.id)
    assert kept.purpose == 'Know when it is done.'
