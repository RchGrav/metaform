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


def test_a_ticket_already_taken_or_done_is_not_taken_again(store):
    small_map(store)
    ticket = store.add_work(ALARM, 'broken', task='wire the tone')
    store.take_work(ticket.work_id, by='codex')
    with pytest.raises(StoreError, match='already taken'):
        store.take_work(ticket.work_id, by='claude')
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
