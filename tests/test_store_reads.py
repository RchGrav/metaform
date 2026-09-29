"""Reads: every read goes through an index, every join names its layer, errors name one next step."""
from __future__ import annotations

import pytest
from storekit import correction, knowledge, memory, plans, scans, small_map

from metaform.data import Node, Store

pytestmark = pytest.mark.kind('fixture')

def populated(store):
    layer, outer, inner = small_map(store)
    notes = knowledge(store, 'notes', tags=('practices',))
    store.add_item(notes.name, Node('element', 'code.timer.kitchen'), 'keep the loop small',
                   link=Node('element', 'code.alarm.audible'), refs=[('path', 'src/timer.c')])
    store.add_item(notes.name, Node('join', inner.join_id), 'the tone is quiet')
    store.add_property(notes.name, 'code.timer.kitchen', 'C')
    store.add_element(notes.name, 'code.timer.kitchen.display')
    shown = store.add_join(notes.name, 'code.timer.kitchen.display', 'code.timer.kitchen', purpose='show time',
                          function='reports remaining time', relation='The timer feeds the display.', observation='LCD')
    store.add_work(Node('element', 'code.timer.kitchen.display'), 'tbd', note='not wired yet', task='wire it')
    store.add_work(Node('join', shown.join_id), 'broken', task='fix the LCD')
    store.finish(notes.name)
    store.mask('code.alarm', notes.name)
    store.select('code.alarm.audible', notes.name)
    notes_memory = memory(store)
    store.add_item(notes_memory.name, Node('element', 'code.timer.kitchen'), 'drifts under load')
    fix = correction(store, 'fix-1')
    store.correct(fix.name, inner.join_id, {'function': 'Plays a loud tone.'}, reason='louder')
    store.finish(fix.name)
    return layer, outer, inner


@pytest.mark.req('STORE-005')
@pytest.mark.req('STORE-025')
@pytest.mark.req('STORE-033')
def test_every_read_is_answered_through_an_index(home, store, traced):
    _, outer, inner = populated(store)
    kitchen = Node('element', 'code.timer.kitchen')
    reads = {
        'element': lambda: store.element('code.timer.kitchen'),
        'element by id': lambda: store.element(store.element('code.alarm.audible').element_id),
        'joins': lambda: store.joins('code.timer.kitchen').results,
        'joins provider': lambda: store.joins('code.timer.kitchen', as_='provider').results,
        'joins raw': lambda: store.joins('code.timer.kitchen', raw=True).results,
        'identity': lambda: store.identity('code.timer.kitchen').results,
        'subtypes': lambda: store.subtypes(outer.join_id).results,
        'where element': lambda: store.where('code.timer.kitchen'),
        'where subtype': lambda: store.where('code.loop.tick'),
        'children': lambda: store.children('code.timer').results,
        'children of the top': lambda: store.children('').results,
        'layer_items': lambda: store.layer_items('notes').results,
        'layer_items at node': lambda: store.layer_items('notes', kitchen).results,
        'node': lambda: store.node(kitchen),
        'node raw': lambda: store.node(kitchen, raw=True),
        'node join': lambda: store.node(Node('join', inner.join_id)),
        'node subtype join': lambda: store.node(Node('join', store.subtypes(outer.join_id).results[0].join_id)),
        'node of the element a subtype join holds': lambda: store.node(Node('element', 'code.loop.tick')),
        'context': lambda: store.context('code.timer'),
        'links_to': lambda: store.links_to(Node('element', 'code.alarm.audible')).results,
        'citing': lambda: store.citing('path', 'src/tick.c').results,
        'history': lambda: store.history(inner.join_id).results,
        'stack': lambda: store.stack().results,
        'peel_preview': lambda: store.peel_preview('fix-1'),
        'graph': lambda: store.graph(limit=2),
        'layers': lambda: store.layers().results,
        'layers by tag': lambda: store.layers(tag='practices').results,
        'provenance': lambda: store.provenance('notes'),
        'effective_selection': lambda: store.effective_selection('code.alarm.audible'),
        'search': lambda: store.search('drifts').results,
        'has_intake': lambda: store.has_intake(),
        'metaforms': lambda: store.metaforms().results,
        'active_metaform': lambda: store.active_metaform(),
        'project': lambda: store.project(),
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
        issued = plans(home, store, traced)
        assert issued, f'{name} issued no query'
        for statement, plan_lines in issued:
            if bad := scans(plan_lines):
                failures.setdefault(name, []).append((statement, bad))
    assert failures == {}


@pytest.mark.req('STORE-010')
def test_the_identity_read_uses_the_provider_index_among_many_joins(home, store, traced):
    layer = knowledge(store, 'many')
    with store.atomic():
        store.add_element(layer.name, 'code.target')
        for n in range(1000):
            store.add_element(layer.name, f'code.r{n}')
        for n in range(100000):
            store.add_join(layer.name, f'code.r{n % 1000}', 'code.target' if n < 50 else f'code.r{(n + 1) % 1000}',
                           purpose='p', function='f', relation='r', observation='o')
    store.finish(layer.name)
    traced.clear()
    assert len(store.identity('code.target').results) == 50
    lines = [line for _, plan_lines in plans(home, store, traced) for line in plan_lines]
    assert any('current_joins_by_provider' in line for line in lines)


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
    assert (cook.join_id, cook.purpose, cook.function, cook.name, cook.layer) == (
        outer.join_id, 'Know when each dish is done.', 'Counts down and rings.', 'kitchen timer', 'intake-1')
    assert [(sub.address, sub.short_name, sub.function) for sub in cook.subtypes] == [
        ('code.loop.tick', 'tick loop', 'Advances each countdown.')]
    assert relying['code.timer.kitchen.display'].layer == 'notes'
    assert [(join.join_id, join.provider_address, join.function, join.layer) for join in kitchen.receives] == [
        (inner.join_id, 'code.alarm.audible', 'Plays a loud tone.', 'fix-1')]
    assert kitchen.subtype is None and kitchen.join is None and kitchen.work == ()
    assert {group.layer: ([item.value for item in group.items], [prop.value for prop in group.properties])
            for group in kitchen.layers} == {'notes': (['keep the loop small'], ['C']),
                                             'memory': (['drifts under load'], [])}
    display = store.where('code.timer.kitchen.display')
    assert [(record.condition, record.note, record.task) for record in display.work] == [
        ('tbd', 'not wired yet', 'wire it')]
    assert [join.provider_address for join in display.receives] == ['code.timer.kitchen']
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


@pytest.mark.req('STORE-025')
@pytest.mark.req('MAP-031')
def test_the_read_of_a_held_element_shows_the_subtype_join_and_the_join_it_sits_in(store):
    _, outer, _ = populated(store)
    tick = store.where('code.loop.tick')
    held = store.subtypes(outer.join_id).results[0]
    assert (tick.kind, tick.subtype.join_id, tick.join.join_id, tick.provides, tick.receives) == (
        'subtype', held.join_id, outer.join_id, (), ())
    extra = knowledge(store, 'extra')
    store.add_element(extra.name, 'code.clock')
    store.add_join(extra.name, 'code.loop.tick', 'code.clock', purpose='keep time', function='ticks',
                   relation='r', observation='o')
    store.finish(extra.name)
    tick = store.where('code.loop.tick')
    assert (tick.kind, tick.subtype.join_id, tick.join.join_id) == ('element', held.join_id, outer.join_id)
    assert [join.provider_address for join in tick.receives] == ['code.clock']


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
    assert 'provider' not in cook and cook['name'] == 'kitchen timer' and cook['layer'] == 'intake-1'
    assert cook['subtypes'] == [{'element': 'code.loop.tick', 'reading': 'tick loop code', 'short_name': 'tick loop',
                                 'name': 'tick loop', 'name_length': 2, 'role': 'SE', 'type': 'subtype',
                                 'function': 'Advances each countdown.', 'relation': 'The tick loop drives the timer.',
                                 'observation': 'One tick per second.', 'refs': [{'key': 'path', 'value': 'src/tick.c'}],
                                 'layer': 'intake-1'}]
    assert small['receives'] == [{'provider': 'code.alarm.audible', 'type': 'purpose',
                                  'purpose': 'Get attention when a countdown ends.', 'function': 'Plays a loud tone.',
                                  'relation': 'The alarm rings for the timer.', 'observation': 'A piezo speaker.',
                                  'name': 'audible alarm', 'layer': 'fix-1'}]
    assert [group['layer'] for group in small['layers']] == ['notes', 'memory']
    alarm = store.element('code.alarm.audible').element_id
    assert small['layers'][0]['items'] == [{'layer': 'notes', 'value': 'keep the loop small',
                                            'link': {'kind': 'element', 'id': alarm},
                                            'refs': [{'key': 'path', 'value': 'src/timer.c'}]}]
    display = store.where('code.timer.kitchen.display').to_dict()
    assert display['work'] == [{'condition': 'tbd', 'note': 'not wired yet', 'task': 'wire it'}]
    tick = store.where('code.loop.tick').to_dict()
    assert set(tick) == {'kind', 'element', 'held'} and set(tick['held']) == {'subtype', 'join'}
    assert tick['held']['join']['receiver'] == 'stakeholder.cook.home'
    full = store.where('code.timer.kitchen', full=True).to_dict()
    assert full['element']['element_id'] == store.element('code.timer.kitchen').element_id
    assert [join['join_id'] for join in full['receives']] == [inner.join_id]
    assert full['receives'][0]['ef'] is None and full['held'] is None and full['work'] == []
    assert outer.join_id in [join['join_id'] for join in full['provides']]


@pytest.mark.req('STORE-025')
@pytest.mark.req('LAYER-016')
def test_every_join_carries_the_name_of_its_layer(store):
    _, outer, inner = populated(store)
    joins = [*store.joins('code.timer.kitchen').results, *store.joins('code.timer.kitchen', as_='provider').results,
             *store.joins('code.timer.kitchen.display').results, *store.identity('code.timer.kitchen').results,
             *store.joins('code.timer.kitchen', raw=True).results, store.where('code.loop.tick').join]
    assert joins
    layer_names = {layer.layer_id: layer.name for layer in store.layers().results}
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
                   function='signals the end', relation='The timer tells the alarm to stop.', observation='a pin')
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
    join = store.add_join(extra.name, 'code.timer.kitchen', 'code.probe.echo', purpose='p', function='f',
                          relation='r', observation='o')
    assert [notice.where for notice in join.notices] == ['provider']
    assert 'code.probe.echo' in join.notices[0].message and extra.name in join.notices[0].message
    echo = store.element('code.probe.echo', raw=True)
    assert echo is not None and echo.layer == extra.name and echo.role is None
    plain = store.add_join(extra.name, 'code.timer.kitchen', 'code.alarm.audible', purpose='',
                           function='bananas are yellow', relation='', observation='')
    assert plain.notices == ()
    assert plain.join_id in [found.join_id for found in store.joins('code.timer.kitchen', raw=True).results]
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
    assert addresses == ['code.alarm.audible', 'code.timer.kitchen', 'code.timer.kitchen.display',
                         'stakeholder.cook.home']
    assert {entry.element.address: entry.parent for entry in entries} == {
        'code.alarm.audible': None, 'code.timer.kitchen': None, 'code.timer.kitchen.display': 'code.timer.kitchen',
        'stakeholder.cook.home': None}
    assert all(entry.element == store.element(entry.element.address) for entry in entries)
    everything = store.graph(limit=0)
    assert [entry.element.address for entry in everything.elements] == addresses and everything.next is None
    for entry in everything.elements:
        held = [join for join in everything.joins if join.receiver == entry.element.element_id]
        assert [join.join_id for join in held] == [join.join_id for join in store.joins(entry.element.address).results]
        for join in held:
            assert join.subtypes == store.subtypes(join.join_id, limit=0).results
    assert 'code.timer.kitchen.display' not in [e.element.address for e in store.graph(selection=['intake-1']).elements]
    secret = knowledge(store, 'secret')
    store.add_element(secret.name, 'code.timer.kitchen.secret')
    hidden = store.add_join(secret.name, 'code.timer.kitchen.secret', 'code.timer.kitchen', purpose='p', function='f',
                            relation='r', observation='o')
    store.finish(secret.name)
    store.hide(secret.name)
    assert 'code.timer.kitchen.secret' not in [entry.element.address for entry in store.graph(limit=0).elements]
    assert hidden.join_id not in [join.join_id for join in store.graph(limit=0).joins]
    raw = store.graph(raw=True, limit=0)
    assert set(addresses) | {'code.timer.kitchen.secret'} == {entry.element.address for entry in raw.elements}
    assert hidden.join_id in [join.join_id for join in raw.joins]
