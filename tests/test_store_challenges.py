"""Challenge states and plans are kept beside the critic's layer, never as edits to it."""
from __future__ import annotations

import pytest
from storekit import dump, knowledge, small_map, store_file

from metaform.data import Node, StoreError

pytestmark = pytest.mark.kind('fixture')


def critic(store):
    small_map(store)
    layer = knowledge(store, 'challenge.blind')
    store.add_element(layer.name, 'code.watchdog')
    store.add_join(layer.name, 'code.timer.kitchen', 'code.watchdog', purpose='recover from a hang',
                   ef='restarts the loop')
    challenge = store.add_item(layer.name, Node('element', 'code.watchdog'), 'Nothing recovers a hung loop.')
    other = store.add_item(layer.name, Node('element', 'code.alarm.audible'), 'The alarm has no volume control.')
    store.finish(layer.name)
    return challenge, other


@pytest.mark.req('STORE-040')
@pytest.mark.req('LAYER-015')
def test_a_c_answer_without_a_link_is_stored_with_a_notice_and_approval_needs_b(home, store):
    challenge, other = critic(store)
    before = dump(store_file(home, store))
    unlinked = store.answer(other.id, 'C')
    assert unlinked.state == 'C' and [notice.where for notice in unlinked.notices] == ['link']
    with pytest.raises(StoreError):
        store.approve(challenge.id)
    assert dump(store_file(home, store)) != before
    store.answer(other.id, 'C', link=Node('element', 'code.alarm.audible'))
    store.answer(challenge.id, 'A')
    with pytest.raises(StoreError):
        store.approve(challenge.id)
    with pytest.raises(StoreError):
        store.approve(other.id)


@pytest.mark.req('STORE-040')
@pytest.mark.req('LAYER-015')
def test_approval_makes_a_plan_and_leaves_the_critics_layer_unchanged(home, store):
    challenge, _ = critic(store)
    store.answer(challenge.id, 'B')
    layer_rows = {name: rows for name, rows in dump(store_file(home, store)).items()
                  if name in ('items', 'elements', 'joins')}
    store.approve(challenge.id)
    assert {name: rows for name, rows in dump(store_file(home, store)).items()
            if name in ('items', 'elements', 'joins')} == layer_rows
    view = store.node(Node('element', 'code.watchdog'))
    group = next(group for group in view.layers if group.layer == 'challenge.blind')
    assert group.items[0].state == 'plan'
    assert store.element('code.watchdog').state == 'plan'
    watchdog_join = next(join for join in store.joins('code.timer.kitchen').results
                         if [each.address for each in join.elements] == ['code.watchdog'])
    assert watchdog_join.state == 'plan'


@pytest.mark.req('STORE-040')
@pytest.mark.req('LAYER-015')
def test_a_plan_added_directly_needs_no_approval(store):
    small_map(store)
    layer = knowledge(store, 'plans')
    element = store.add_element(layer.name, 'code.logger')
    join = store.add_join(layer.name, 'code.timer.kitchen', 'code.logger', purpose='keep a record',
                          ef='writes each countdown')
    store.add_plan(layer.name, element.id, join.id)
    store.finish(layer.name)
    assert store.element('code.logger').state == 'plan'


@pytest.mark.req('STORE-040')
def test_every_read_of_a_challenge_shows_its_state(store):
    # Showing 'open' for an unanswered challenge waits on how a blind-spot layer is recognized, BUILD-QUESTIONS.
    _, other = critic(store)
    store.answer(other.id, 'A')
    view = store.node(Node('element', 'code.alarm.audible'))
    group = next(group for group in view.layers if group.layer == 'challenge.blind')
    assert group.items[0].state == 'A'
