"""Tickets, D92 and VIEW-035: a work record keeps its kind while it is worked, records who took it, sits in a column
of the board in an order, and links other nodes for reference. Rich, 2026-10-01."""
from __future__ import annotations

import sqlite3

import pytest
from storekit import small_map, store_file

from metaform.data import Node, StoreError
from metaform.data.session import open_store
from metaform.sqlite import SCHEMA_VERSION

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('MAP-048')]

KITCHEN, ALARM = Node('element', 'code.timer.kitchen'), Node('element', 'code.alarm.audible')


def test_a_ticket_is_one_of_four_kinds_and_keeps_its_kind_while_it_is_worked(store):
    small_map(store)
    tickets = {kind: store.add_work(KITCHEN, kind, task=f'a {kind} ticket') for kind in
               ('missing', 'broken', 'flawed', 'enhancement')}
    assert all(not ticket.notices for ticket in tickets.values())
    for kind, ticket in tickets.items():
        taken = store.take_work(ticket.work_id, by='claude')
        assert (taken.condition, taken.taken_by, taken.column) == (kind, 'claude', 'doing')
        assert taken.taken is not None


@pytest.mark.req('MAP-049')
@pytest.mark.req('MAP-053')
def test_a_record_with_an_empty_condition_is_taken_worked_and_says_it_waits_on_the_person(store):
    """The intake writes a drift finding with no condition, FINDING_CLASS. The agent working it takes it, plans and
    reports its steps, and says in a step that it waits on the person, as it can on a record with a condition."""
    small_map(store)
    drift = store.add_work(KITCHEN, None, task='the timer drifts from its spec')
    assert drift.condition == ''
    taken = store.take_work(drift.work_id, steps=2, by='claude')
    assert (taken.condition, taken.taken_by, taken.column, taken.steps) == ('', 'claude', 'doing', 2)
    assert not taken.notices
    assert store.plan_work(drift.work_id, 3).steps == 3
    stepped = store.step_work(drift.work_id, 'Asked the person whether the spec or the timer is right; waiting on '
                                             'the answer.')
    assert not stepped.notices
    read = store.ticket(drift.work_id).work
    assert (read.steps, read.steps_done, read.said[-1].said) == (3, 1, 'Asked the person whether the spec or the '
                                                                       'timer is right; waiting on the answer.')
    with pytest.raises(StoreError, match='already taken'):
        store.take_work(drift.work_id, by='codex')


def test_an_exclude_record_still_has_no_task_to_take(store):
    small_map(store)
    outside = store.add_work(KITCHEN, 'exclude', note='vendored folder')
    with pytest.raises(StoreError, match='no task to take'):
        store.take_work(outside.work_id)


def test_a_ticket_moves_through_the_columns_of_the_board_in_order(store):
    small_map(store)
    first = store.add_work(KITCHEN, 'enhancement', task='first', held=True)
    second = store.add_work(KITCHEN, 'flawed', task='second')
    assert (first.column, second.column) == ('backlog', 'todo')
    moved = store.move_work(first.work_id, 'todo', position=0)
    assert moved.column == 'todo'
    order = [ticket.work_id for ticket in sorted(store.work(open=True, limit=0).results, key=lambda one: one.position or 0)
             if ticket.column == 'todo']
    assert order == [first.work_id, second.work_id]
    assert store.move_work(second.work_id, 'doing', by='Rich').taken_by == 'Rich'
    back = store.move_work(second.work_id, 'todo')
    assert (back.column, back.taken, back.taken_by) == ('todo', None, None)
    done = store.move_work(second.work_id, 'done')
    assert done.column == 'done' and done.done is not None


def test_a_ticket_links_other_nodes_for_reference(store):
    small_map(store)
    ticket = store.add_work(KITCHEN, 'missing', task='build the snooze', links=[ALARM])
    assert ticket.address == 'code.timer.kitchen'
    assert [link.address for link in ticket.links] == ['code.alarm.audible']
    edited = store.edit_work(ticket.work_id, {'links': []})
    assert edited.links == ()


@pytest.mark.req('VIEW-037')
@pytest.mark.parametrize('column', ['backlog', 'todo', 'doing', 'done'])
def test_reordering_a_ticket_preserves_its_assignment_progress_and_completion(store, column):
    from dataclasses import replace
    small_map(store)
    first = store.add_work(KITCHEN, 'enhancement', task='first', held=column == 'backlog')
    second = store.add_work(KITCHEN, 'flawed', task='second', held=column == 'backlog', links=[ALARM])
    if column == 'doing':
        store.take_work(first.work_id, by='claude')
        store.take_work(second.work_id, steps=3, by='codex')
        store.step_work(second.work_id, 'Traced the tone.')
    elif column == 'done':
        store.finish_work(first.work_id, 'built')
        store.edit_work(second.work_id, {'held': True})
        store.finish_work(second.work_id, 'fixed')
    before = store.ticket(second.work_id).work
    moved = store.move_work(second.work_id, column, position=0, by='user')
    assert replace(moved, position=before.position) == before
    assert moved.position == 0 and store.ticket(first.work_id).work.position == 1


@pytest.mark.req('STORE-042')
@pytest.mark.parametrize('destination', ['element', 'join'])
def test_moving_a_ticket_to_another_node_keeps_its_progress_and_links(store, destination):
    """Work 71470758: moving a ticket's attachment preserves the ticket and its work log, apart from map identity."""
    _, outer, _ = small_map(store)
    target = ALARM if destination == 'element' else Node('join', outer.join_id)
    ticket = store.add_work(KITCHEN, 'broken', note='drifts', task='fix the drift', reviewed=True, links=[ALARM])
    store.take_work(ticket.work_id, steps=2, by='codex')
    before = store.step_work(ticket.work_id, 'Measured the drift.').to_dict()
    moved = store.edit_work(ticket.work_id, {'node': target})
    assert not moved.notices
    assert (moved.kind, moved.id) == (target.kind, store.element(ALARM.id).element_id if destination == 'element'
                                      else target.id)
    fields = ('work_id', 'condition', 'note', 'task', 'held', 'reviewed', 'created', 'done', 'resolution', 'steps',
              'steps_done', 'said', 'taken', 'taken_by', 'position', 'links')
    assert {key: moved.to_dict()[key] for key in fields} == {key: before[key] for key in fields}
    assert store.work(KITCHEN).results == ()
    assert store.work(target).results[0].work_id == ticket.work_id
    assert store.element(KITCHEN.id).open_work == ()
    assert store.element(KITCHEN.id).address == KITCHEN.id
    store.finish_work(ticket.work_id, 'fixed')
    done = store.ticket(ticket.work_id).work
    back = store.edit_work(ticket.work_id, {'node': KITCHEN})
    assert (back.done, back.resolution, back.said) == (done.done, 'fixed', done.said)


@pytest.mark.req('MAP-050')
@pytest.mark.parametrize('kind', ['question', 'message'])
@pytest.mark.parametrize('closed', [False, True])
def test_moving_a_question_or_message_keeps_its_answers_and_state(store, kind, closed):
    """Work 71470758: a question can change nodes without being reasked or losing the user's answer."""
    _, _, inner = small_map(store)
    target = Node('join', inner.join_id)
    message = (store.ask(KITCHEN, 'Keep the tone?', suggestions=['Yes', 'No'], by='critic') if kind == 'question'
               else store.tell(KITCHEN, 'The tone is quiet.', by='critic'))
    if closed:
        message = store.reply(message.message_id, 'Yes' if kind == 'question' else None)
    moved = store.move_message(message.message_id, target)
    assert not moved.notices
    assert (moved.node_kind, moved.node_id, moved.receiver_address, moved.provider_address) == (
        'join', inner.join_id, KITCHEN.id, ALARM.id)
    fields = ('message_id', 'kind', 'text', 'suggestions', 'by', 'created', 'closed', 'answer')
    assert {key: moved.to_dict()[key] for key in fields} == {key: message.to_dict()[key] for key in fields}
    assert store.messages(KITCHEN).results == ()
    assert store.messages(target).results == (moved,)
    assert store.move_message(message.message_id, ALARM).address == ALARM.id


def test_a_ticket_already_taken_or_done_is_not_taken_again(store):
    small_map(store)
    ticket = store.add_work(ALARM, 'broken', task='wire the tone')
    store.take_work(ticket.work_id, by='codex')
    with pytest.raises(StoreError, match='already taken'):
        store.take_work(ticket.work_id, by='claude')
    with pytest.raises(StoreError) as again:
        store.take_work(ticket.work_id, by='codex')
    # The agent that took it and stopped resumes with op=plan, so the refusal names who holds it and points there.
    assert 'codex' in again.value.message and 'op=plan' in again.value.message
    assert again.value.next_step == f'metaform map work op=plan id={ticket.work_id} steps=<n>'
    store.finish_work(ticket.work_id, 'wired')
    with pytest.raises(StoreError, match='done'):
        store.take_work(ticket.work_id)


def test_the_viewer_still_reads_a_taken_missing_or_broken_ticket_as_in_progress_or_fixing(store):
    small_map(store)
    built = store.add_work(KITCHEN, 'missing', task='build it')
    fixed = store.add_work(ALARM, 'broken', task='fix it')
    store.take_work(built.work_id)
    store.take_work(fixed.work_id)
    assert store.element('code.timer.kitchen').open_work == ('in-progress',)
    assert store.element('code.alarm.audible').open_work == ('fixing',)


@pytest.mark.req('STORE-029')
def test_a_layout_8_store_opens_at_layout_9_with_taken_tickets_keeping_their_kind(home, store):
    small_map(store)
    built = store.add_work(KITCHEN, 'missing', task='build it')
    fixed = store.add_work(ALARM, 'broken', task='fix it')
    path = store_file(home, store)
    db = sqlite3.connect(path)
    db.executescript("""
        UPDATE work SET condition='in-progress' WHERE condition='missing';
        UPDATE work SET condition='fixing' WHERE condition='broken';
        DROP TABLE work_links;
        UPDATE meta SET value='8' WHERE key='schema_version';
    """)
    for column in ('taken', 'taken_by', 'position'):
        db.execute(f'ALTER TABLE work DROP COLUMN {column}')
    db.commit()
    db.close()
    with open_store(path, write=False) as opened:
        assert opened.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == SCHEMA_VERSION
    tickets = {ticket.work_id: ticket for ticket in store.work(limit=0).results}
    assert (tickets[built.work_id].condition, tickets[built.work_id].column) == ('missing', 'doing')
    assert (tickets[fixed.work_id].condition, tickets[fixed.work_id].column) == ('broken', 'doing')
    assert list((home / 'backups' / f'upgrade-{SCHEMA_VERSION}').glob('*/*/*.metaform.sqlite3'))


def test_one_ticket_is_read_by_its_id_with_what_the_map_holds_at_its_node_and_its_linked_nodes(store):
    """MAP-048, first piece: reading one ticket by id hands an agent the ticket with its node's where read, its refs
    and its open questions, and the same for each node it links, so it can start without parsing the work list."""
    _, outer, _ = small_map(store)
    store.ask(KITCHEN, 'Is the snooze still wanted?', suggestions=['Yes', 'No'], by='critic')
    ticket = store.add_work(KITCHEN, 'missing', task='build the snooze', links=[ALARM, Node('join', outer.join_id)])
    store.add_work(ALARM, 'flawed', task='a ticket at the other node')
    read = store.ticket(ticket.work_id)
    assert (read.work.work_id, read.work.task, [link.address for link in read.work.links]) == (
        ticket.work_id, 'build the snooze', ['code.alarm.audible', 'stakeholder.cook.home'])
    assert read.at.element.address == 'code.timer.kitchen'
    assert [join.receiver_address for join in read.at.provides] == ['stakeholder.cook.home']
    assert [one.text for one in read.at.messages] == ['Is the snooze still wanted?']
    assert [one.work_id for one in read.at.work] == [ticket.work_id]
    alarm, joined = read.linked
    assert alarm.element.address == 'code.alarm.audible' and [one.task for one in alarm.work] == [
        'a ticket at the other node']
    assert (joined.kind, joined.join.join_id, [each.address for each in joined.join.elements]) == (
        'join', outer.join_id, ['code.timer.kitchen', 'code.loop.tick'])
    plain = read.to_dict()
    assert (plain['work_id'], plain['at']['element']['address'], plain['linked'][1]['join']['receiver']) == (
        ticket.work_id, 'code.timer.kitchen', 'stakeholder.cook.home')
    assert plain['at']['messages'][0]['text'] == 'Is the snooze still wanted?'


def test_reading_a_ticket_by_an_id_no_ticket_has_names_the_list(store):
    small_map(store)
    with pytest.raises(StoreError, match='No work record has the id nothing') as refused:
        store.ticket('nothing')
    assert refused.value.next_step == 'metaform map work open=true'


def test_where_shows_each_ticket_at_the_address_with_its_work_id(store):
    small_map(store)
    first = store.add_work(KITCHEN, 'missing', task='build the snooze')
    second = store.add_work(KITCHEN, 'flawed', task='quieter')
    assert [one['work_id'] for one in store.where('code.timer.kitchen').to_dict()['work']] == [first.work_id,
                                                                                              second.work_id]


@pytest.mark.req('VIEW-040')
@pytest.mark.req('STORE-045')
@pytest.mark.req('BASE-046')
def test_the_chassis_work_record_holds_no_glyph_and_the_store_distributes_no_work(store, home):
    """Ticket 90430bba: the kanban glyph assignment is a feature's field, kept in the map module's own table keyed by
    the work id, STORE-045. The chassis is the fixed part, BASE-046: its work record, its work table and its data
    access object know no glyph, and an edit naming one is told the record has no such field and stores nothing."""
    import dataclasses

    from metaform.data import records
    from metaform.data.records import WorkRecord
    small_map(store)
    ticket = store.add_work(KITCHEN, 'missing', task='a lane of its own')
    assert 'glyph' not in {field.name for field in dataclasses.fields(WorkRecord)}
    assert [name for name in dir(store) if 'glyph' in name.lower() or 'distribut' in name.lower()] == []
    assert [name for name in dir(records) if 'glyph' in name.lower()] == []
    edited = store.edit_work(ticket.work_id, {'glyph': 'moth'})
    assert [(notice.where, notice.message) for notice in edited.notices] == [
        ('glyph', 'A work record has no field glyph; it was not stored.')]
    db = sqlite3.connect(store_file(home, store))
    try:
        # no chassis table or view holds a glyph; a module's own table has a dot in its name, STORE-045
        chassis = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")
                   if '.' not in row[0]]
        assert 'work' in chassis
        assert [name for name in chassis
                if 'glyph' in [column[1] for column in db.execute(f'PRAGMA table_info("{name}")')]] == []
    finally:
        db.close()
