"""Worker completion keeps tickets open until durable delivery succeeds."""
import asyncio
import time

import pytest

from metaform.data import Store
from metaform.modules.dispatch import work_over
from metaform.modules.dispatch.tests.test_completion_commit import session_for
from metaform.modules.dispatch.tests.test_dispatch import dispatch as dispatch  # noqa: PLC0414

pytestmark = [pytest.mark.req('BASE-052'), pytest.mark.kind('simulation')]


def receipt(dispatch, *, state='merged', reason=''):
    with Store('proj', module='dispatch').tables() as tx:
        row = {'work_id': dispatch.id, 'branch': 'metaform/test', 'worktree': str(dispatch.folder),
               'state': state, 'reason': reason, 'ready': time.time(), 'deadline': time.time(), 'seq': 1}
        if tx.update('merges', {'work_id': dispatch.id}, row) is None:
            tx.insert('merges', row)


def test_worker_done_without_merge_stays_open_and_names_missing_delivery(dispatch, monkeypatch):
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    record = dispatch.store.finish_work(dispatch.id, 'Fixed.', 'Verified behavior.')
    assert record.done is None
    assert work_over(dispatch.store, record)
    assert any('Merge this ticket' in notice.message for notice in record.notices)
    with Store('proj', module='map').tables(write=False) as tx:
        held = tx.get('ticket_settings', {'work_id': dispatch.id})
    assert held['landed'] and not held['proof']
    assert dispatch.store.complete_delivery(dispatch.id).done is None
    with Store('proj', module='map').tables(write=False) as tx:
        assert tx.get('ticket_settings', {'work_id': dispatch.id})['landed'] == held['landed']


@pytest.mark.parametrize('reason', ['push pending', 'Web restart failed.'])
def test_merged_ticket_waits_for_push_and_activation(dispatch, monkeypatch, reason):
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    dispatch.store.finish_work(dispatch.id, 'Fixed.', 'Verified behavior.')
    receipt(dispatch, reason=reason)
    pending = dispatch.store.complete_delivery(dispatch.id)
    assert pending.done is None
    assert reason in pending.notices[0].message
    receipt(dispatch)
    closed = dispatch.store.complete_delivery(dispatch.id)
    assert closed.done and closed.resolution == 'Fixed.'


def test_fault_ticket_closes_immediately_after_delivery(dispatch, monkeypatch):
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    dispatch.store.prove_work(dispatch.id)
    dispatch.store.finish_work(dispatch.id, 'Fixed.', 'Verified behavior.')
    receipt(dispatch)
    assert dispatch.store.complete_delivery(dispatch.id).done


def test_reopened_ticket_cannot_reuse_prior_delivery_receipt(dispatch, monkeypatch):
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    dispatch.store.finish_work(dispatch.id, 'First fix.', 'Verified behavior.')
    receipt(dispatch)
    assert dispatch.store.complete_delivery(dispatch.id).done
    dispatch.store.move_work(dispatch.id, 'todo')
    reopened = dispatch.store.finish_work(dispatch.id, 'Second fix.', 'Verified current behavior.')
    assert reopened.done is None
    assert dispatch.store.complete_delivery(dispatch.id).done is None
    receipt(dispatch)
    assert dispatch.store.complete_delivery(dispatch.id).done


def test_worker_fault_closes_after_delivery_even_without_autoticket(dispatch, monkeypatch):
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    dispatch.store.edit_work(dispatch.id, {'condition': 'broken', 'kind': 'broken'})
    dispatch.store.finish_work(dispatch.id, 'Fixed.', 'Verified behavior.')
    receipt(dispatch)
    assert dispatch.store.complete_delivery(dispatch.id).done
    assert dispatch.store.finish_work(dispatch.id, 'Delivery finished.').done
    with Store('proj', module='map').tables(write=False) as tx:
        assert tx.get('ticket_settings', {'work_id': dispatch.id})['proof']


@pytest.mark.parametrize('outcome', ['cancelled', 'failed'])
def test_cancelled_or_failed_worker_needs_no_delivery(dispatch, monkeypatch, outcome):
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    ended = dispatch.store.finish_work(dispatch.id, 'Stopped.', outcome=outcome)
    assert ended.done and ended.outcome == outcome


def test_human_board_close_preserves_explicit_authority(dispatch, monkeypatch):
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    dispatch.store.finish_work(dispatch.id, 'Fixed.', 'Verified behavior.')
    monkeypatch.delenv('METAFORM_ROLE')
    from metaform.data import operations
    owner = operations.operation('finish_work').run.__globals__
    monkeypatch.setitem(owner, 'page_vouched', lambda: True)
    assert dispatch.store.move_work(dispatch.id, 'done').done


def test_pending_delivery_does_not_send_completion_or_end_ownership(dispatch, monkeypatch):
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    dispatch.store.finish_work(dispatch.id, 'Fixed.', 'Verified behavior.')
    made = session_for(dispatch)
    turns = []

    async def committed():
        pass

    async def ended(*args):
        pytest.fail('Delivery still needs work.')

    monkeypatch.setattr(made, 'commit_done', committed)
    monkeypatch.setattr(made, 'end', ended)
    monkeypatch.setattr(made, 'record_prompt', lambda: pytest.fail('Completion prompt was premature.'))
    monkeypatch.setattr(made, 'turn', turns.append)
    asyncio.run(made.ticket_done())
    asyncio.run(made.ticket_done())
    assert len(turns) == 1 and 'Your ticket stays open.' in turns[0]
    assert not made.ending
