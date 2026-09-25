"""Challenge states and plans are kept beside the critic's layer, never as edits to it."""
from __future__ import annotations

import pytest

from metaform.data import Node, StoreError
from storekit import dump, knowledge, small_map, store_file

pytestmark = pytest.mark.kind('fixture')


def critic(store):
    small_map(store)
    layer = knowledge(store, 'challenge.blind')
    store.add_element(layer.name, 'code.watchdog')
    store.add_join(layer.name, 'code.timer.kitchen', 'code.watchdog', purpose='recover from a hang',
                   function='restarts the loop', relation='The watchdog restarts the timer.', observation='none')
    challenge = store.add_item(layer.name, Node('element', 'code.watchdog'), 'Nothing recovers a hung loop.')
    other = store.add_item(layer.name, Node('element', 'code.alarm.audible'), 'The alarm has no volume control.')
    store.finish(layer.name)
    return challenge, other


@pytest.mark.req('STORE-040')
@pytest.mark.req('LAYER-015')
def test_a_c_answer_needs_a_link_and_approval_needs_b(home, store):
    challenge, other = critic(store)
    before = dump(store_file(home, store))
    with pytest.raises(StoreError):
        store.answer(other.item_id, 'C')
    with pytest.raises(StoreError):
        store.approve(challenge.item_id)
    assert dump(store_file(home, store)) == before
    store.answer(other.item_id, 'C', link=Node('element', 'code.alarm.audible'))
    store.answer(challenge.item_id, 'A')
    with pytest.raises(StoreError):
        store.approve(challenge.item_id)
    with pytest.raises(StoreError):
        store.approve(other.item_id)


@pytest.mark.req('STORE-040')
@pytest.mark.req('LAYER-015')
def test_approval_makes_a_plan_and_leaves_the_critics_layer_unchanged(home, store):
    challenge, _ = critic(store)
    store.answer(challenge.item_id, 'B')
    layer_rows = {name: rows for name, rows in dump(store_file(home, store)).items()
                  if name in ('items', 'elements', 'joins')}
    store.approve(challenge.item_id)
    assert {name: rows for name, rows in dump(store_file(home, store)).items()
            if name in ('items', 'elements', 'joins')} == layer_rows
    view = store.node(Node('element', 'code.watchdog'))
    group = next(group for group in view.layers if group.layer == 'challenge.blind')
    assert group.items[0].state == 'plan'
    assert store.element('code.watchdog').state == 'plan'
    watchdog_join = next(join for join in store.joins('code.timer.kitchen').results if join.provider_address == 'code.watchdog')
    assert watchdog_join.state == 'plan'


@pytest.mark.req('STORE-040')
@pytest.mark.req('LAYER-015')
def test_a_plan_added_directly_needs_no_approval(store):
    small_map(store)
    layer = knowledge(store, 'plans')
    element = store.add_element(layer.name, 'code.logger')
    join = store.add_join(layer.name, 'code.timer.kitchen', 'code.logger', purpose='keep a record',
                          function='writes each countdown', relation='The logger records the timer.',
                          observation='none yet')
    store.add_plan(layer.name, element.element_id, join.join_id)
    store.finish(layer.name)
    assert store.element('code.logger').state == 'plan'


@pytest.mark.req('STORE-040')
def test_every_read_of_a_challenge_shows_its_state(store):
    # Showing 'open' for an unanswered challenge waits on how a blind-spot layer is recognized, BUILD-QUESTIONS.
    challenge, other = critic(store)
    store.answer(other.item_id, 'A')
    view = store.node(Node('element', 'code.alarm.audible'))
    group = next(group for group in view.layers if group.layer == 'challenge.blind')
    assert group.items[0].state == 'A'
    assert challenge
