"""Explicit work holds require fresh reasons and release without losing context."""
from __future__ import annotations

import pytest
from storekit import small_map

from metaform import changes, home
from metaform.data import Node, Store, StoreError
from metaform.modules.map.holds import unhold_all_project

pytestmark = pytest.mark.kind('fixture')
KITCHEN = Node('element', 'code.timer.kitchen')


@pytest.mark.parametrize('reason', [None, '', ' \n\t '])
@pytest.mark.parametrize('action', ['add', 'held', 'hold', 'backlog'])
def test_every_explicit_hold_requires_a_fresh_nonblank_reason(store, action, reason):
    small_map(store)
    ticket = store.add_work(KITCHEN, None, task='Repair timer.', note='Existing note cannot explain this hold.')
    with pytest.raises(StoreError, match='hold_reason'):
        if action == 'add':
            store.add_work(KITCHEN, None, task='Repair alarm.', held=True, hold_reason=reason)
        elif action == 'held':
            store.edit_work(ticket.id, {'held': True, 'hold_reason': reason})
        elif action == 'hold':
            store.set_work_hold(ticket.id, hold=True, hold_reason=reason)
        else:
            store.move_work(ticket.id, 'backlog', hold_reason=reason)
    assert not store.ticket(ticket.id).work.held


def test_saved_reason_cannot_substitute_for_a_new_reason(store):
    small_map(store)
    ticket = store.add_work(KITCHEN, None, task='Repair timer.', held=True, hold_reason='Wait for hardware.')
    store.edit_work(ticket.id, {'held': False})
    with pytest.raises(StoreError, match='hold_reason'):
        store.edit_work(ticket.id, {'held': True})
    with Store(store.project_id, module='map').tables() as tx:
        assert tx.get('ticket_settings', {'work_id': ticket.id})['hold_reason'] == 'Wait for hardware.'


def test_unhold_clears_both_flags_preserves_context_and_names_changed_tickets_once(store):
    small_map(store)
    backlog = store.add_work(KITCHEN, None, task='Repair timer.', held=True, hold_reason='Wait for hardware.')
    active = store.add_work(KITCHEN, None, task='Repair alarm.')
    done = store.add_work(KITCHEN, None, task='Completed work.')
    chat = store.add_work(KITCHEN, None, task='Conversation with the system agent', held=True)
    stage = store.add_work(KITCHEN, 'unbuilt', held=True, hold_reason='Legacy stage hold.')
    editors = store.add_work(KITCHEN, None, task='Sessions from editors', held=True)
    for record in (backlog, active, done, chat, editors, stage):
        store.set_work_hold(record.id, hold=True, hold_reason='Wait for review.')
    store.take_work(active.id, by='owner')
    store.step_work(active.id, 'Recorded investigation.')
    store.finish_work(done.id, 'Completed repair.')
    with Store(store.project_id, module='map').tables() as tx:
        tx.update('ticket_settings', {'work_id': backlog.id}, {'board': 'Repairs'})
        tx.insert('after', {'work_id': backlog.id, 'works': [active.id]})
    before = {record.id: store.ticket(record.id).work for record in (backlog, active, done, chat, editors, stage)}
    changes.take()
    assert store.unhold_all_work() == 2
    announced = changes.take()
    base_id = next(iter(announced[store.project_id]))
    assert changes.concerns(store.project_id, base_id) == {
        'work_ids': sorted([backlog.id, active.id]), 'session_ids': [], 'kinds': ['ticket']}
    for record in (backlog, active):
        after = store.ticket(record.id).work
        assert not after.held
        assert (after.position, after.taken, after.taken_by, after.said, after.note) == (
            before[record.id].position, before[record.id].taken, before[record.id].taken_by,
            before[record.id].said, before[record.id].note)
    for record in (done, chat, editors, stage):
        assert store.ticket(record.id).work == before[record.id]
    with Store(store.project_id, module='map').tables() as tx:
        for record in (backlog, active):
            settings = tx.get('ticket_settings', {'work_id': record.id})
            assert settings['hold'] == 0 and settings['hold_reason'] == 'Wait for review.'
        assert tx.get('ticket_settings', {'work_id': backlog.id})['board'] == 'Repairs'
        assert tx.get('after', {'work_id': backlog.id})['works'] == [active.id]
        reasons = store.work_hold_history(backlog.id)
        assert {row['reason'] for row in reasons} == {'Wait for hardware.', 'Wait for review.'}
    changes.take()
    assert store.unhold_all_work() == 0
    assert changes.take() == {}


def test_project_release_reaches_other_bases_and_leaves_other_projects_held(store, tmp_path):
    small_map(store)
    first = store.add_work(KITCHEN, None, task='First base repair.', held=True, hold_reason='Wait for inspection.')
    second_base = home.add_base(store.project_id, 'second')
    second_store = Store(store.project_id, base=second_base.id)
    small_map(second_store)
    second = second_store.add_work(KITCHEN, None, task='Second base repair.', held=True,
                                   hold_reason='Wait for inspection.')
    foreign_folder = tmp_path / 'foreign'
    foreign_folder.mkdir()
    home.add_project('foreign', foreign_folder)
    foreign_store = Store('foreign')
    small_map(foreign_store)
    untouched = foreign_store.add_work(KITCHEN, None, task='Other project repair.', held=True,
                                      hold_reason='Wait for inspection.')
    assert unhold_all_project(store) == 2
    first_store = Store(store.project_id, base=next(base.id for base in home.bases(store.project_id)
                                                  if base.name == 'main'))
    assert not first_store.ticket(first.id).work.held
    assert not second_store.ticket(second.id).work.held
    assert foreign_store.ticket(untouched.id).work.held
    assert unhold_all_project(store) == 0


def test_release_rolls_back_both_flags_when_transaction_fails(store, monkeypatch):
    from metaform.data import operations
    small_map(store)
    ticket = store.add_work(KITCHEN, None, task='Repair timer.', held=True, hold_reason='Wait for inspection.')
    store.set_work_hold(ticket.id, hold=True, hold_reason='Wait for inspection.')
    def fail(*args, **kwargs):
        raise RuntimeError('transaction failed')
    operation = operations.operation('unhold_all_work')
    assert operation is not None
    monkeypatch.setitem(operation.run.__globals__, '_ticket_changed', fail)
    with pytest.raises(RuntimeError, match='transaction failed'):
        store.unhold_all_work()
    assert store.ticket(ticket.id).work.held
    with Store(store.project_id, module='map').tables(write=False) as tx:
        assert tx.get('ticket_settings', {'work_id': ticket.id})['hold'] == 1
