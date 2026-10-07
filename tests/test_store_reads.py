"""Reads: every read goes through an index, every join names its layer, errors name one next step."""
from __future__ import annotations

import pytest
from storekit import knowledge, memory, small_map

from metaform.data import Node, Store

pytestmark = pytest.mark.kind('fixture')

def populated(store):
    layer, outer, inner = small_map(store)
    notes = knowledge(store, 'notes', tags=('practices',))
    store.add_item(notes.name, Node('element', 'code.timer.kitchen'), 'keep the loop small',
                   link=Node('element', 'code.alarm.audible'), refs=[('path', 'src/timer.c')])
    store.add_item(notes.name, Node('join', inner.id), 'the tone is quiet')
    store.add_property(notes.name, 'code.timer.kitchen', 'C')
    store.add_element(notes.name, 'code.timer.kitchen.display')
    shown = store.add_join(notes.name, 'code.timer.kitchen.display', 'code.timer.kitchen', purpose='show time',
                          ef='reports remaining time')
    store.add_work(Node('element', 'code.timer.kitchen.display'), 'missing', note='not wired yet', task='wire it')
    store.add_work(Node('join', shown.id), 'broken', task='fix the LCD')
    store.finish(notes.name)
    store.mask('code.alarm', notes.name)
    store.select('code.alarm.audible', notes.name)
    notes_memory = memory(store)
    store.add_item(notes_memory.name, Node('element', 'code.timer.kitchen'), 'drifts under load')
    store.refine(inner.id, {'ef': 'Plays a loud tone.'}, reason='louder')
    return layer, outer, inner


@pytest.mark.req('STORE-005')
@pytest.mark.req('STORE-025')
@pytest.mark.req('STORE-046')
def test_every_read_is_answered_from_the_graph_in_memory(home, store, traced):
    """A read never touches SQLite for structure: the only SQL it issues reads the ops past the sequence it applied,
    by the primary key, and the modules' own tables, STORE-046."""
    _, _, inner = populated(store)
    kitchen = Node('element', 'code.timer.kitchen')
    reads = {
        'element': lambda: store.element('code.timer.kitchen'),
        'element by id': lambda: store.element(store.element('code.alarm.audible').id),
        'joins': lambda: store.joins('code.timer.kitchen').results,
        'joins provider': lambda: store.joins('code.timer.kitchen', as_='provider').results,
        'joins raw': lambda: store.joins('code.timer.kitchen', raw=True).results,
        'identity': lambda: store.identity('code.timer.kitchen').results,
        'where element': lambda: store.where('code.timer.kitchen'),
        'where held element': lambda: store.where('code.loop.tick'),
        'children': lambda: store.children('code.timer').results,
        'children of the top': lambda: store.children('').results,
        'layer_items': lambda: store.layer_items('notes').results,
        'layer_items at node': lambda: store.layer_items('notes', kitchen).results,
        'node': lambda: store.node(kitchen),
        'node raw': lambda: store.node(kitchen, raw=True),
        'node join': lambda: store.node(Node('join', inner.id)),
        'node of an element a join holds': lambda: store.node(Node('element', 'code.loop.tick')),
        'context': lambda: store.context('code.timer'),
        'links_to': lambda: store.links_to(Node('element', 'code.alarm.audible')).results,
        'citing': lambda: store.citing('path', 'src/timer.c').results,
        'history': lambda: store.history(inner.id).results,
        'graph': lambda: store.graph(limit=2),
        'layers': lambda: store.layers().results,
        'layers by tag': lambda: store.layers(tag='practices').results,
        'provenance': lambda: store.provenance('notes'),
        'effective_selection': lambda: store.effective_selection('code.alarm.audible'),
        'search': lambda: store.search('drifts').results,
        'has_intake': lambda: store.has_intake(),
        'roots': lambda: store.roots(),
        'work': lambda: store.work().results,
        'work by condition': lambda: store.work(condition='broken').results,
        'work at node': lambda: store.work(node=kitchen).results,
        'work open': lambda: store.work(open=True).results,
    }
    failures = {}
    for name, read in reads.items():
        traced.clear()
        read()
        touched = [statement for statement in traced if statement.upper().startswith(('SELECT', 'WITH'))
                   and 'sqlite_master' not in statement and 'FROM meta' not in statement]
        structure = [statement for statement in touched if 'FROM ops' not in statement and 'FROM snapshots' not in statement
                     and not any(own in statement for own in ('work', 'messages', 'question_work', 'work_links',
                                                               'work_steps', 'eligible', 'glyphs', 'plans',
                                                               'challenge_states', 'reports', 'prompt_uses',
                                                               'prompt_versions', 'prompts', 'projects', 'bases',
                                                               'active_bases', 'settings', 'modules', 'harnesses'))]
        if structure:
            failures[name] = structure
        if not any('FROM ops' in statement and 'seq >' in statement for statement in touched):
            failures[name] = failures.get(name, []) + ['no catch-up read of the log']
    assert failures == {}


@pytest.mark.req('STORE-010')
@pytest.mark.req('STORE-046')
def test_the_identity_read_among_many_joins_answers_from_the_index_in_memory(home, store, traced):
    import time
    layer = knowledge(store, 'many')
    with store.atomic():
        store.add_element(layer.name, 'code.target')
        for n in range(1000):
            store.add_element(layer.name, f'code.r{n}')
        for n in range(100000):
            store.add_join(layer.name, f'code.r{n % 1000}', 'code.target' if n < 50 else f'code.r{(n + 1) % 1000}',
                           purpose='p', ef='f')
    store.finish(layer.name)
    traced.clear()
    started = time.monotonic()
    assert len(store.identity('code.target').results) == 50
    assert time.monotonic() - started < 2  # the index in memory, not a scan of a hundred thousand joins
    assert not any(table in statement for statement in traced
                   for table in ('FROM joins', 'FROM elements', 'current_joins', 'join_elements'))


@pytest.mark.req('STORE-025')
@pytest.mark.req('LAYER-017')
@pytest.mark.req('STORE-042')
def test_one_read_of_an_address_shows_what_relies_on_it_and_what_it_relies_on(store):
    _, outer, inner = populated(store)
    kitchen = store.where('code.timer.kitchen')
    assert (kitchen.kind, kitchen.element.address, kitchen.element.short_name, kitchen.element.role) == (
        'element', 'code.timer.kitchen', 'kitchen timer', 'DE')
    relying = {join.receiver_address: join for join in kitchen.provides}
    assert set(relying) == {'stakeholder.cook.home', 'code.timer.kitchen.display'}
    cook = relying['stakeholder.cook.home']
    assert (cook.id, cook.purpose, cook.ef, cook.layer) == (
        outer.id, 'Know when each dish is done.', 'Counts down and rings.', 'intake-1')
    assert [(held.address, held.short_name) for held in cook.elements] == [
        ('code.timer.kitchen', 'kitchen timer'), ('code.loop.tick', 'tick loop')]
    assert relying['code.timer.kitchen.display'].layer == 'notes'
    assert [(join.id, [held.address for held in join.elements], join.ef, join.layer)
            for join in kitchen.receives] == [(inner.id, ['code.alarm.audible'], 'Plays a loud tone.', 'intake-1')]
    assert kitchen.join is None and kitchen.work == ()
    assert {group.layer: ([item.value for item in group.items], [prop.value for prop in group.properties])
            for group in kitchen.layers} == {'notes': (['keep the loop small'], ['C']),
                                             'memory': (['drifts under load'], [])}
    display = store.where('code.timer.kitchen.display')
    assert [(record.condition, record.note, record.task) for record in display.work] == [
        ('missing', 'not wired yet', 'wire it')]
    assert [[held.address for held in join.elements] for join in display.receives] == [['code.timer.kitchen']]
    assert display.receives[0].open_work == ('broken',)


@pytest.mark.req('STORE-025')
@pytest.mark.req('LAYER-007')
def test_the_read_of_an_address_follows_the_reading_context(store):
    populated(store)
    store.mask('code.timer', 'notes')
    kitchen = store.where('code.timer.kitchen')
    assert [join.receiver_address for join in kitchen.provides] == ['stakeholder.cook.home']
    assert [group.layer for group in kitchen.layers] == ['memory']
    everything = store.where('code.timer.kitchen', raw=True)
    assert {join.receiver_address for join in everything.provides} == {'stakeholder.cook.home',
                                                                        'code.timer.kitchen.display'}
    assert [group.layer for group in everything.layers] == ['notes', 'memory']



@pytest.mark.req('STORE-010')
def test_one_join_read_by_id_gives_its_receiver_and_its_first_element_by_address(store):
    _, outer, inner = small_map(store)
    assert store.join_ends(outer.id) == ('stakeholder.cook.home', 'code.timer.kitchen')
    assert store.join_ends(inner.id) == ('code.timer.kitchen', 'code.alarm.audible')
    assert store.join_ends(store.element('code.timer.kitchen').id) is None
    notes = knowledge(store, 'notes')
    added = store.add_join(notes.name, 'code.alarm.audible', 'code.loop.tick', purpose='keep time', ef='ticks')
    assert store.join_ends(added.id) == ('code.alarm.audible', 'code.loop.tick')
    assert store.remove(added.id).notices == ()
    assert store.join_ends(added.id) is None


@pytest.mark.req('STORE-025')
@pytest.mark.req('BASE-036')
def test_the_read_of_an_address_leaves_ids_and_empty_fields_out_unless_asked(store):
    _, outer, inner = populated(store)
    small = store.where('code.timer.kitchen').to_dict()

    def keys(data):
        if isinstance(data, dict):
            for key, value in data.items():
                yield key, value
                yield from keys(value)
        elif isinstance(data, list):
            for value in data:
                yield from keys(value)
    # the properties that reach the address are part of the one read, STORE-025
    assert set(small) == {'kind', 'element', 'provides', 'receives', 'layers', 'properties'}
    assert not [key for key, _ in keys(small) if key.endswith('_id') or key in ('parent', 'target')]
    assert not [key for key, value in keys(small) if value in (None, '', [], {}, False)]
    cook = next(join for join in small['provides'] if join['receiver'] == 'stakeholder.cook.home')
    assert 'provider' not in cook and 'name' not in cook and cook['layer'] == 'intake-1'
    assert cook['elements'] == [
        {'address': 'code.timer.kitchen', 'short_name': 'kitchen timer', 'name_length': 2, 'name': 'kitchen timer',
         'role': 'DE'},
        {'address': 'code.loop.tick', 'short_name': 'tick loop', 'name_length': 2, 'name': 'tick loop', 'role': 'SE'}]
    assert small['receives'] == [{'type': 'purpose', 'purpose': 'Get attention when a countdown ends.',
                                  'ef': 'Plays a loud tone.', 'layer': 'intake-1',
                                  'elements': [{'address': 'code.alarm.audible', 'short_name': 'audible alarm',
                                                'name_length': 2, 'name': 'audible alarm', 'role': 'SE'}]}]
    assert [group['layer'] for group in small['layers']] == ['notes', 'memory']
    alarm = store.element('code.alarm.audible').id
    assert small['layers'][0]['items'] == [{'layer': 'notes', 'value': 'keep the loop small',
                                            'link': {'kind': 'element', 'id': alarm},
                                            'refs': [{'key': 'path', 'value': 'src/timer.c'}]}]
    display = store.where('code.timer.kitchen.display').to_dict()
    assert display['work'] == [{'id': store.work().results[0].id, 'condition': 'missing',
                                'note': 'not wired yet', 'task': 'wire it'}]
    tick = store.where('code.loop.tick').to_dict()
    assert set(tick) == {'kind', 'element', 'provides'}
    assert [join['receiver'] for join in tick['provides']] == ['stakeholder.cook.home']
    full = store.where('code.timer.kitchen', full=True).to_dict()
    assert full['element']['id'] == store.element('code.timer.kitchen').id
    assert [join['id'] for join in full['receives']] == [inner.id]
    assert 'held' not in full and full['work'] == []
    assert outer.id in [join['id'] for join in full['provides']]


@pytest.mark.req('STORE-025')
@pytest.mark.req('LAYER-016')
def test_every_join_carries_the_name_of_its_layer(store):
    _, _outer, _inner = populated(store)
    joins = [*store.joins('code.timer.kitchen').results, *store.joins('code.timer.kitchen', as_='provider').results,
             *store.joins('code.timer.kitchen.display').results, *store.identity('code.timer.kitchen').results,
             *store.joins('code.timer.kitchen', raw=True).results, *store.where('code.loop.tick').provides]
    assert joins
    layer_names = {layer.id: layer.name for layer in store.layers().results}
    for join in joins:
        assert join.layer and join.layer == layer_names[join.layer_id]
    assert {join.layer for join in store.joins('code.timer.kitchen.display').results} == {'notes'}
    assert {join.layer for join in store.joins('stakeholder.cook.home').results} == {'intake-1'}


@pytest.mark.req('STORE-025')
@pytest.mark.req('LAYER-016')
@pytest.mark.req('MAP-044')
def test_a_knowledge_layers_join_follows_its_toggle_and_the_receivers_mask(store):
    small_map(store)
    extra = knowledge(store, 'extra')
    store.add_join(extra.name, 'code.alarm.audible', 'code.timer.kitchen', purpose='know when to stop',
                   ef='signals the end')
    store.finish(extra.name)
    on = Store('proj', toggled=['intake-1', 'extra'])
    off = Store('proj', toggled=['intake-1'])
    assert [join.layer for join in on.joins('code.alarm.audible').results] == ['extra']
    assert off.joins('code.alarm.audible').results == ()
    assert [join.layer for join in off.joins('code.alarm.audible', raw=True).results] == ['extra']
    on.mask('code.alarm.audible', extra.name)
    assert on.joins('code.alarm.audible').results == ()
    assert [join.layer for join in on.joins('code.alarm.audible', raw=True).results] == ['extra']
    assert [join.layer for join in on.joins('code.timer.kitchen').results] == ['intake-1']
    on.mask('code.timer.kitchen', 'intake-1')
    assert on.joins('code.timer.kitchen').results == ()


@pytest.mark.req('MAP-044')
def test_a_new_element_with_no_join_reaches_no_in_context_read(store):
    small_map(store)
    extra = knowledge(store, 'extra')
    store.add_element(extra.name, 'code.lonely')
    store.finish(extra.name)
    reads = [store.joins('code.timer.kitchen').results, store.joins('code.timer.kitchen', as_='provider').results,
             store.identity('code.timer.kitchen').results, store.context('code.timer').applying,
             store.context('code.timer').visible]
    assert 'code.lonely' not in repr(reads)


@pytest.mark.req('STORE-026')
@pytest.mark.req('BASE-044')
def test_a_write_that_does_not_fit_is_stored_with_a_notice_and_text_is_never_judged(home, store):
    small_map(store)
    extra = knowledge(store, 'extra')
    join = store.add_join(extra.name, 'code.timer.kitchen', 'code.probe.echo', purpose='p', ef='f')
    assert [notice.where for notice in join.notices] == ['elements']
    assert 'code.probe.echo' in join.notices[0].message and extra.name in join.notices[0].message
    echo = store.element('code.probe.echo', raw=True)
    assert echo is not None and echo.layer == extra.name and echo.role is None
    plain = store.add_join(extra.name, 'code.timer.kitchen', 'code.alarm.audible', purpose='',
                           ef='bananas are yellow')
    assert plain.notices == ()
    assert plain.id in [found.id for found in store.joins('code.timer.kitchen', raw=True).results]
    odd = store.add_element(extra.name, 'Code..Engine')
    assert [notice.where for notice in odd.notices] == ['address'] and store.where('Code..Engine', raw=True)
    assert store.add_element(extra.name, 'media.photo.jpg').notices == ()

@pytest.mark.req('VIEW-010')
@pytest.mark.req('STORE-025')
def test_the_graph_read_pages_each_visible_element_with_its_nearest_parent_and_the_joins_it_receives(store):
    populated(store)
    entries, after, pages = [], None, 0
    while True:
        page = store.graph(limit=2, after=after)
        entries += page.elements
        pages += 1
        after = page.next
        if after is None:
            break
    addresses = [entry.element.address for entry in entries]
    assert pages > 1 and addresses == sorted(set(addresses))
    # an element a join holds is an element of the map as any other, Rich's shape, 2026-10-04
    assert addresses == ['code.alarm.audible', 'code.loop.tick', 'code.timer.kitchen', 'code.timer.kitchen.display',
                         'stakeholder.cook.home']
    assert {entry.element.address: entry.parent for entry in entries} == {
        'code.alarm.audible': None, 'code.loop.tick': None, 'code.timer.kitchen': None,
        'code.timer.kitchen.display': 'code.timer.kitchen', 'stakeholder.cook.home': None}
    assert all(entry.element == store.element(entry.element.address) for entry in entries)
    everything = store.graph(limit=0)
    assert [entry.element.address for entry in everything.elements] == addresses and everything.next is None
    for entry in everything.elements:
        held = [join for join in everything.joins if join.receiver == entry.element.id]
        assert [join.id for join in held] == [join.id for join in store.joins(entry.element.address).results]
        for join in held:
            assert join.elements == next(read for read in store.joins(entry.element.address).results
                                         if read.id == join.id).elements
    assert 'code.timer.kitchen.display' not in [e.element.address for e in store.graph(selection=['intake-1']).elements]
    secret = knowledge(store, 'secret')
    store.add_element(secret.name, 'code.timer.kitchen.secret')
    hidden = store.add_join(secret.name, 'code.timer.kitchen.secret', 'code.timer.kitchen', purpose='p', ef='f')
    store.finish(secret.name)
    store.hide(secret.name)
    assert 'code.timer.kitchen.secret' not in [entry.element.address for entry in store.graph(limit=0).elements]
    assert hidden.id not in [join.id for join in store.graph(limit=0).joins]
    raw = store.graph(raw=True, limit=0)
    assert set(addresses) | {'code.timer.kitchen.secret'} == {entry.element.address for entry in raw.elements}
    assert hidden.id in [join.id for join in raw.joins]
