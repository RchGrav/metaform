"""A part's stage and a ticket's kind are kept apart, MAP-046 as amended 2026-10-08."""
from __future__ import annotations

import pytest
from storekit import small_map

from metaform.data import Node, StoreError

pytestmark = [pytest.mark.req('MAP-046'), pytest.mark.kind('fixture')]


def test_a_ticket_keeps_its_kind_apart_from_the_parts_stage_and_an_unknown_kind_is_refused(store):
    """They shared one field, so setting one wiped the other; a kind outside the closed list writes nothing."""
    small_map(store)
    alarm = Node('element', 'code.alarm.audible')
    ticket = store.add_work(alarm, None, task='Make the tone louder', kind='enhancement')
    assert (ticket.kind, ticket.condition) == ('enhancement', '')
    edited = store.edit_work(ticket.id, {'kind': 'flawed'})
    assert (edited.kind, edited.condition) == ('flawed', '')
    with pytest.raises(StoreError, match="'sideways' is not a kind of ticket"):
        store.add_work(alarm, None, task='x', kind='sideways')
    assert [record.id for record in store.work(alarm, None, True, limit=0).results] == [ticket.id]
    assert [record.id for record in store.work(None, None, True, kind='flawed', limit=0).results] == [ticket.id]


def test_taking_a_ticket_starts_building_an_unbuilt_part_and_finishing_it_never_marks_it_built(store):
    """A ticket must not grade its own work: taking it says the part is being built, and only the person or the
    intake says it is built."""
    small_map(store)
    alarm = Node('element', 'code.alarm.audible')
    state = store.add_work(alarm, 'unbuilt', note='No alarm yet.')
    ticket = store.add_work(alarm, None, task='Build the alarm', kind=None)
    store.take_work(ticket.id, by='an agent')
    assert store.ticket(state.id).work.condition == 'under-construction'
    store.finish_work(ticket.id, 'Built it.')
    after = store.ticket(state.id).work
    assert (after.condition, after.done) == ('under-construction', None)  # still open: built is the person's to say
    assert store.element('code.alarm.audible').open_work == ('under-construction',)
