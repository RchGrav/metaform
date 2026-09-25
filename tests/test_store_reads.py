"""Reads: every read goes through an index, every join names its layer, errors name one next step."""
from __future__ import annotations

import sqlite3

import pytest

from metaform.data import Node, Store, StoreError
from storekit import correction, knowledge, memory, plans, scans, small_map, store_file

pytestmark = pytest.mark.kind('fixture')

def populated(store):
    layer, outer, inner = small_map(store)
    notes = knowledge(store, 'notes', tags=('practices',))
    store.add_item(notes.name, Node('element', 'code.timer.kitchen'), 'keep the loop small',
                   link=Node('element', 'code.alarm.audible'), refs=[('path', 'src/timer.c')])
    store.add_item(notes.name, Node('join', inner.join_id), 'the tone is quiet')
    store.add_property(notes.name, 'code.timer.kitchen', 'C')
    store.add_element(notes.name, 'code.timer.kitchen.display', flag='missing', flag_note='not wired yet')
    store.add_join(notes.name, 'code.timer.kitchen.display', 'code.timer.kitchen', purpose='show time',
                   function='reports remaining time', relation='The timer feeds the display.', observation='LCD',
                   flag='broken')
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
        'layer_items': lambda: store.layer_items('notes').results,
        'layer_items at node': lambda: store.layer_items('notes', kitchen).results,
        'node': lambda: store.node(kitchen),
        'node raw': lambda: store.node(kitchen, raw=True),
        'node join': lambda: store.node(Node('join', inner.join_id)),
        'node subtype': lambda: store.node(Node('subtype', 'code.loop.tick')),
        'context': lambda: store.context('code.timer'),
        'links_to': lambda: store.links_to(Node('element', 'code.alarm.audible')).results,
        'citing': lambda: store.citing('path', 'src/tick.c').results,
        'history': lambda: store.history(inner.join_id).results,
        'stack': lambda: store.stack().results,
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
        'findings': lambda: store.findings().results,
        'findings by flag': lambda: store.findings(flag='broken').results,
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