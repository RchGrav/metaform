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


@pytest.mark.req('STORE-029')
def test_a_store_whose_tickets_have_steps_upgrades_to_the_kind_column_keeping_every_reference(home, store):
    """Found 2026-10-08: adding the kind column renamed the work table aside, which repointed the steps' and links'
    references at the copy, and dropping the copy broke them, so a store with steps refused to open."""
    import json
    import sqlite3

    from metaform import home as homes
    from metaform.data import Store
    small_map(store)
    ticket = store.add_work(Node('element', 'code.alarm.audible'), None, task='Wire the tone')
    store.take_work(ticket.id, steps=1, by='an agent')
    store.step_work(ticket.id, 'Traced the pin.')
    path = homes.store_path(store.project_id, homes.active_base(store.project_id).id)
    db = sqlite3.connect(path)  # back to version 8: the work table as it was, without the kind column
    recorded = json.loads(db.execute("SELECT value FROM meta WHERE key='module:map'").fetchone()[0])
    work = next(table for table in recorded['tables'] if table['name'] == 'work')
    work['columns'] = [column for column in work['columns'] if column[0] != 'kind']
    work['schema'] = work['schema'].replace(",\n  kind        TEXT NOT NULL DEFAULT ''", '')  # the table as v8 declared it
    assert 'kind        TEXT' not in work['schema']
    recorded['version'] = 8
    db.execute('PRAGMA foreign_keys=OFF')
    db.execute('ALTER TABLE work DROP COLUMN kind')
    db.execute("UPDATE meta SET value=? WHERE key='module:map'", (json.dumps(recorded),))
    db.commit()
    db.close()
    reopened = Store(store.project_id)
    [found] = reopened.work(None, None, True, limit=0).results
    assert (found.id, found.kind, found.steps_done) == (ticket.id, '', 1)
    check = sqlite3.connect(path)
    assert check.execute('PRAGMA foreign_key_check').fetchall() == []
    assert json.loads(check.execute("SELECT value FROM meta WHERE key='module:map'").fetchone()[0])['version'] >= 9  # upgraded on to the current layout
