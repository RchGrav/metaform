"""A knowledge item's flags, LAYER-021: read_first and always_show are stored on the item, and an item flagged task adds
a ticket at its node instead of storing the flag. Rich, 2026-10-03, D91 and D92."""
from __future__ import annotations

import sqlite3

import pytest
from storekit import knowledge, small_map, store_file, values

from metaform.data import Node

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('LAYER-021'), pytest.mark.req('STORE-015')]

KITCHEN, ALARM = Node('element', 'code.timer.kitchen'), Node('element', 'code.alarm.audible')


def test_an_item_keeps_its_read_first_and_always_show_flags_and_an_edit_changes_them(store):
    small_map(store)
    critic = knowledge(store, 'critic')
    flagged = store.add_item(critic.name, KITCHEN, 'Read the timer spec first.', read_first=True, always_show=True)
    note = store.add_item(critic.name, KITCHEN, 'The tick loop was rewritten once.')
    assert (flagged.read_first, flagged.always_show) == (True, True)
    assert (note.read_first, note.always_show) == (False, False)
    edited = store.edit(flagged.id, {'read_first': False})
    assert (edited.fields['read_first'], edited.fields['always_show']) == (False, True)
    raised = store.edit(note.id, {'read_first': True})
    assert (raised.fields['read_first'], raised.fields['always_show']) == (True, False)
    store.finish(critic.name)
    read = {item.value: (item.read_first, item.always_show) for group in store.node(KITCHEN).layers
            for item in group.items}
    assert read == {'Read the timer spec first.': (False, True), 'The tick loop was rewritten once.': (True, False)}


@pytest.mark.req('STORE-042')
def test_an_item_flagged_task_adds_a_ticket_at_its_node_and_does_not_store_the_flag(home, store):
    small_map(store)
    critic = knowledge(store, 'critic')
    item = store.add_item(critic.name, KITCHEN, 'Make the alarm stop after a minute.', task=True, condition='missing')
    assert not hasattr(item, 'task') and 'task' not in (item.extra or {})
    tickets = store.work(KITCHEN, open=True).results
    assert [(ticket.condition, ticket.task) for ticket in tickets] == [('missing', 'Make the alarm stop after a minute.')]
    told = [notice for notice in item.notices if notice.where == 'task']
    assert len(told) == 1 and tickets[0].id in told[0].message
    store.finish(critic.name)
    assert values(store.node(KITCHEN), 'critic') == ['Make the alarm stop after a minute.']
    db = sqlite3.connect(store_file(home, store))
    assert 'task' not in [row[1] for row in db.execute('PRAGMA table_info(items)')]
    db.close()


def test_an_item_not_flagged_task_adds_no_ticket(store):
    small_map(store)
    critic = knowledge(store, 'critic')
    store.add_item(critic.name, KITCHEN, 'A plain note.', read_first=True)
    assert store.work(KITCHEN).results == ()


@pytest.mark.req('LAYER-007')
def test_an_always_show_item_shows_at_its_node_where_its_layer_does_not_reach(store):
    small_map(store)
    critic = knowledge(store, 'critic')
    store.add_item(critic.name, KITCHEN, 'Never block the tick loop.', always_show=True)
    store.add_item(critic.name, KITCHEN, 'Optional reading.')
    store.finish(critic.name)
    store.mask('code.timer', critic.name)
    assert critic.id not in store.effective_selection('code.timer.kitchen').layer_ids
    assert values(store.node(KITCHEN), 'critic') == ['Never block the tick loop.']
    assert [item.value for item in store.where('code.timer.kitchen').layers[0].items] == ['Never block the tick loop.']


@pytest.mark.req('LAYER-006')
def test_an_always_show_item_shows_when_its_layer_is_hidden_or_left_out_of_the_selection(store):
    layer, _, _ = small_map(store)
    critic = knowledge(store, 'critic')
    store.add_item(critic.name, KITCHEN, 'Never block the tick loop.', always_show=True)
    store.add_item(critic.name, KITCHEN, 'Optional reading.')
    store.finish(critic.name)
    assert values(store.node(KITCHEN, selection=[layer.name]), 'critic') == ['Never block the tick loop.']
    store.hide(critic.name)
    assert values(store.node(KITCHEN), 'critic') == ['Never block the tick loop.']


def test_an_always_show_item_of_a_layer_still_being_built_does_not_show(store):
    small_map(store)
    critic = knowledge(store, 'critic')
    store.add_item(critic.name, KITCHEN, 'Never block the tick loop.', always_show=True)
    assert values(store.node(KITCHEN), 'critic') == []


@pytest.mark.req('MAP-048')
def test_a_ticket_read_returns_the_read_first_items_of_its_node_and_its_linked_nodes_ahead_of_at(store):
    small_map(store)
    critic = knowledge(store, 'critic')
    store.add_item(critic.name, KITCHEN, 'Read the timer spec first.', read_first=True)
    store.add_item(critic.name, KITCHEN, 'A note, not read first.')
    store.add_item(critic.name, ALARM, 'Read the alarm wiring first.', read_first=True)
    store.finish(critic.name)
    ticket = store.add_work(KITCHEN, 'missing', task='stop the alarm', links=[ALARM])
    read = store.ticket(ticket.id)
    assert [item.value for item in read.read_first] == ['Read the timer spec first.', 'Read the alarm wiring first.']
    plain = read.to_dict()
    keys = list(plain)
    assert keys.index('read_first') < keys.index('at')
    assert [item['value'] for item in plain['read_first']] == ['Read the timer spec first.',
                                                               'Read the alarm wiring first.']
