"""Worker completion requires a current saved commit with successful verification."""
import asyncio
import time

import pytest

from metaform.data import Store
from metaform.modules.dispatch import work_over
from metaform.modules.dispatch.tests.test_completion_commit import session_for
from metaform.modules.dispatch.tests.test_dispatch import dispatch as dispatch  # noqa: PLC0414

pytestmark = [pytest.mark.req('BASE-052'), pytest.mark.kind('simulation')]


def receipt(dispatch, *, state='committed', reason='', head='1234567890abcdef', passed=True, evidence=True, ready=None):
    with Store('proj', module='dispatch').tables() as tx:
        row = {'work_id': dispatch.id, 'branch': 'metaform/test', 'worktree': str(dispatch.folder),
               'state': state, 'reason': reason, 'head': head,
               'evidence': {'verification': {'passed': passed, 'command': '', 'output': '', 'source': 'worker',
                                              'report': 'Verified behavior.'}, 'artifacts': []} if evidence else None,
               'ready': time.time() if ready is None else ready, 'deadline': time.time(), 'seq': 1}
        if tx.update('merges', {'work_id': dispatch.id}, row) is None:
            tx.insert('merges', row)


def test_worker_done_without_saved_commit_stays_open_and_names_missing_evidence(dispatch, monkeypatch):
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    record = dispatch.store.finish_work(dispatch.id, 'Fixed.', 'Verified behavior.')
    assert record.done is None
    assert work_over(dispatch.store, record)
    assert any('verified' in notice.message.lower() and 'commit' in notice.message.lower() for notice in record.notices)
    with Store('proj', module='map').tables(write=False) as tx:
        held = tx.get('ticket_settings', {'work_id': dispatch.id})
    assert held['landed'] and not held['proof']
    assert dispatch.store.complete_delivery(dispatch.id).done is None
    with Store('proj', module='map').tables(write=False) as tx:
        assert tx.get('ticket_settings', {'work_id': dispatch.id})['landed'] == held['landed']


@pytest.mark.parametrize('reason', ['Verification failed.', 'Git commit failed.'])
def test_ticket_waits_for_successful_commit_and_verification(dispatch, monkeypatch, reason):
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    dispatch.store.finish_work(dispatch.id, 'Fixed.', 'Verified behavior.')
    receipt(dispatch, reason=reason)
    pending = dispatch.store.complete_delivery(dispatch.id)
    assert pending.done is None
    assert reason in pending.notices[0].message
    receipt(dispatch)
    closed = dispatch.store.complete_delivery(dispatch.id)
    assert closed.done and closed.resolution == 'Fixed.'


def test_saved_verified_commit_closes_without_merge_approval_or_push(dispatch, monkeypatch):
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    dispatch.store.finish_work(dispatch.id, 'Fixed.', 'Verified behavior.')
    receipt(dispatch)
    assert dispatch.store.complete_delivery(dispatch.id).done


@pytest.mark.parametrize('fields', [{'evidence': False}, {'head': ''}, {'passed': False}, {'passed': 'true'},
                                  {'state': 'merged', 'evidence': False}])
def test_incomplete_or_failed_verification_cannot_close_ticket(dispatch, monkeypatch, fields):
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    dispatch.store.finish_work(dispatch.id, 'Fixed.', 'Verified behavior.')
    receipt(dispatch, **fields)
    assert dispatch.store.complete_delivery(dispatch.id).done is None


def test_legacy_merged_record_requires_current_verification(dispatch, monkeypatch):
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    dispatch.store.finish_work(dispatch.id, 'Fixed.', 'Verified behavior.')
    receipt(dispatch, state='merged')
    assert dispatch.store.complete_delivery(dispatch.id).done


def test_stale_saved_commit_cannot_close_new_result(dispatch, monkeypatch):
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    dispatch.store.finish_work(dispatch.id, 'Fixed.', 'Verified behavior.')
    receipt(dispatch, ready=time.time() - 60)
    pending = dispatch.store.complete_delivery(dispatch.id)
    assert pending.done is None
    assert 'older than this result' in pending.notices[0].message


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
    receipt(dispatch, passed=False)
    assert dispatch.store.complete_delivery(dispatch.id).done is None
    assert any(work.id == dispatch.id and work.condition == 'broken'
               for work in dispatch.store.where('code.engine').work)
    receipt(dispatch)
    assert dispatch.store.complete_delivery(dispatch.id).done
    assert all(work.id != dispatch.id for work in dispatch.store.where('code.engine').work)
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
