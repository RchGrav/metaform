"""Resolved work closes directly, independently of delivery and verification records."""
import asyncio
import json
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
               'evidence': {'verification': {'passed': passed}, 'artifacts': []} if evidence else None,
               'ready': time.time() if ready is None else ready, 'deadline': time.time(), 'seq': 1}
        if tx.update('merges', {'work_id': dispatch.id}, row) is None:
            tx.insert('merges', row)


@pytest.mark.parametrize('operation', ['finish', 'move'])
def test_worker_closes_resolved_work_without_delivery_record(dispatch, monkeypatch, operation):
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    record = (dispatch.store.finish_work(dispatch.id, 'Fixed.', 'Verified behavior.') if operation == 'finish'
              else dispatch.store.move_work(dispatch.id, 'done'))
    assert record.done and work_over(dispatch.store, record)
    assert not any(notice.where == 'delivery' for notice in record.notices)
    with Store('proj', module='dispatch').tables(write=False) as tx:
        assert tx.get('merges', {'work_id': dispatch.id}) is None


@pytest.mark.parametrize('fields', [
    {'state': 'failed', 'reason': 'Verification failed.', 'passed': False},
    {'state': 'failed', 'reason': 'Git commit failed.', 'head': ''},
    {'state': 'merged', 'reason': 'push pending'},
    {'state': 'committed', 'evidence': False},
    {'state': 'committed', 'ready': 1.0},
    {'state': 'merged', 'reason': 'Runtime restart failed.'},
])
def test_delivery_failures_and_stale_evidence_do_not_gate_resolution(dispatch, monkeypatch, fields):
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    receipt(dispatch, **fields)
    closed = dispatch.store.finish_work(dispatch.id, 'Fixed.', 'Resolved behavior.')
    assert closed.done and closed.resolution == 'Fixed.'
    with Store('proj', module='dispatch').tables(write=False) as tx:
        kept = tx.get('merges', {'work_id': dispatch.id})
    assert kept['state'] == fields['state']
    assert kept['reason'] == fields.get('reason', '')


@pytest.mark.parametrize('role', ['worker', 'talk', None])
def test_retained_sessions_never_add_completion_requirements(dispatch, role):
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('agent_sessions', {'session_id': 'prior-session', 'work_id': dispatch.id, 'agent': 'codex',
                                     'state': 'ended', 'started': '2026-10-21', 'seq': 1})
        if role is not None:
            tx.insert('session_lines', {'session_id': 'prior-session', 'work_id': dispatch.id,
                                        'name': 'state', 'kind': 'state', 'text': json.dumps({'role': role}), 'seq': 1})
    assert dispatch.store.finish_work(dispatch.id, 'Resolved result.').done


def test_resolved_fault_disappears_without_delivery_or_manual_fault_clearing(dispatch, monkeypatch):
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    dispatch.store.edit_work(dispatch.id, {'condition': 'broken', 'kind': 'broken'})
    dispatch.store.prove_work(dispatch.id)  # Legacy proof metadata does not add a gate.
    assert any(work.id == dispatch.id for work in dispatch.store.where('code.engine').work)
    receipt(dispatch, state='failed', passed=False, reason='Verification failed.')
    assert dispatch.store.finish_work(dispatch.id, 'Fault resolved.').done
    assert all(work.id != dispatch.id for work in dispatch.store.where('code.engine').work)


@pytest.mark.parametrize('outcome', ['cancelled', 'failed'])
def test_cancelled_or_failed_worker_keeps_its_actual_outcome(dispatch, monkeypatch, outcome):
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    ended = dispatch.store.finish_work(dispatch.id, 'Stopped.', outcome=outcome)
    assert ended.done and ended.outcome == outcome
    repeated = dispatch.store.finish_work(dispatch.id, 'Another result.')
    assert repeated.resolution == 'Stopped.' and repeated.outcome == outcome


def test_recurrence_reopens_resolved_work_and_new_resolution_closes_directly(dispatch, monkeypatch):
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    first = dispatch.store.finish_work(dispatch.id, 'First fix.')
    assert first.done
    assert dispatch.store.move_work(dispatch.id, 'todo').done is None
    receipt(dispatch, ready=1.0, state='failed', reason='Previous delivery failed.')
    second = dispatch.store.finish_work(dispatch.id, 'Recurrence fixed.')
    assert second.done and second.resolution == 'Recurrence fixed.'
    repeated = dispatch.store.finish_work(dispatch.id, 'Do not overwrite resolution.')
    assert repeated.done == second.done and repeated.resolution == 'Recurrence fixed.'


def test_legacy_staged_result_closes_without_delivery_proof(dispatch, monkeypatch):
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    dispatch.store.take_work(dispatch.id, by='worker')
    with Store('proj', module='map')._write() as tx:
        tx.execute('UPDATE work SET resolution=? WHERE work_id=?', ('Legacy resolved result.', dispatch.id))
    with Store('proj', module='map').tables() as tables:
        values = {'landed': '2026-10-20T00:00:00Z', 'proof': 1}
        if tables.update('ticket_settings', {'work_id': dispatch.id}, values) is None:
            tables.insert('ticket_settings', {'work_id': dispatch.id, **values})
    receipt(dispatch, state='failed', passed=False, reason='Old delivery failed.')
    closed = dispatch.store.complete_delivery(dispatch.id)
    assert closed.done and closed.resolution == 'Legacy resolved result.'


def test_reset_closes_dead_legacy_result_and_preserves_unfinished_stop_semantics(dispatch, run):
    resolved = dispatch.id
    unfinished = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Unfinished work').id
    stopped = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Work the person stopped').id
    for work_id, session in ((resolved, 'resolved-session'), (unfinished, 'unfinished-session'),
                             (stopped, 'stopped-session')):
        dispatch.store.take_work(work_id, by=f'claude {session}')
    with dispatch.store._write() as tx:
        tx.execute('UPDATE work SET resolution=? WHERE work_id=?', ('Legacy fix resolved.', resolved))
    with Store('proj', module='map').tables() as tables:
        values = {'landed': '2026-10-20T00:00:00Z', 'proof': 1}
        if tables.update('ticket_settings', {'work_id': resolved}, values) is None:
            tables.insert('ticket_settings', {'work_id': resolved, **values})
    with Store('proj', module='dispatch').tables() as tables:
        for seq, (work_id, session) in enumerate(((resolved, 'resolved-session'),
                                                (unfinished, 'unfinished-session'), (stopped, 'stopped-session'))):
            tables.insert('agent_sessions', {'session_id': session, 'work_id': work_id, 'agent': 'claude',
                                             'state': 'ended' if work_id == stopped else 'running',
                                             'how': 'stopped by the person' if work_id == stopped else None,
                                             'pid': 2 ** 22 + 7, 'port': 9, 'token': 'fixture',
                                             'started': '2026-10-20T00:00:00Z', 'seq': seq})
    receipt(dispatch, state='failed', passed=False, reason='Old delivery failed.')
    assert dispatch.store.ticket(resolved).work.done is None

    result = json.loads(run('dispatch', 'reset', '--json', cwd=dispatch.folder).stdout)

    closed = dispatch.store.ticket(resolved).work
    assert closed.done and closed.resolution == 'Legacy fix resolved.'
    assert set(result['sessions_ended']) == {resolved, unfinished}
    assert result['released'] == [unfinished]
    assert result['kept_for_you'] == [stopped]
    assert 'pending_delivery' not in result
    remaining = dispatch.store.ticket(unfinished).work
    assert remaining.done is None and remaining.taken is None
    paused = dispatch.store.ticket(stopped).work
    assert paused.done is None and paused.taken_by == 'claude stopped-session'


def test_delivery_failure_does_not_keep_resolved_worker_session_open(dispatch, monkeypatch):
    from metaform.modules.dispatch import board

    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    dispatch.store.finish_work(dispatch.id, 'Fixed.')
    receipt(dispatch, state='failed', passed=False, reason='Verification failed.')
    made = session_for(dispatch)
    turns, ended = [], []

    async def committed():
        pass

    async def end(reason):
        ended.append(reason)
        made.ending = True

    monkeypatch.setattr(made, 'commit_done', committed)
    monkeypatch.setattr(made, 'end', end)
    monkeypatch.setattr(made, 'record_prompt', lambda: '')
    monkeypatch.setattr(made, 'turn', turns.append)
    monkeypatch.setattr(board, 'finished', lambda *args: None)
    asyncio.run(made.ticket_done())
    asyncio.run(made.ticket_done())
    assert ended == ['the ticket is done'] and not turns
