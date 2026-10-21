"""A delivered repair clears its light. A recurring fault restores the same ticket."""
import time

import pytest

from metaform.data import Store
from metaform.modules.autoticket.tests.test_autoticket import (
    lights,
    mapped,
    tickets,
    web_fault,
)
from metaform.modules.autoticket.tests.test_autoticket import (
    project as project,  # noqa: PLC0414
)

pytestmark = pytest.mark.kind('simulation')


@pytest.fixture(autouse=True)
def dispatch_enabled(run, project):
    run('enable', 'dispatch', cwd=project)


def delivered(store, folder, work_id, *, state='merged', reason=''):
    with Store(store.project_id, module='dispatch').tables() as tx:
        row = {'work_id': work_id, 'branch': 'main', 'worktree': str(folder), 'state': state,
               'reason': reason, 'ready': time.time(), 'deadline': time.time(), 'seq': time.time_ns()}
        if tx.update('merges', {'work_id': work_id}, row) is None:
            tx.insert('merges', row)


def test_done_after_delivery_closes_fault_and_recurrence_restores_same_light(run, project):
    store = mapped(project)
    web_fault(project)
    [filed] = tickets(store)
    pending = store.finish_work(filed.id, 'Fixed the KeyError in graph.')
    assert pending.done is None and lights(store)
    delivered(store, project, filed.id)
    closed = store.finish_work(filed.id, 'Fixed the KeyError in graph.')
    assert closed.done and closed.outcome == 'completed'
    assert closed.resolution == 'Fixed the KeyError in graph.'
    assert lights(store) == []
    web_fault(project, 7)
    [reopened] = tickets(store)
    assert reopened.id == filed.id and reopened.condition == 'broken'
    assert 'Previous resolution' in reopened.note and "KeyError: 'node 7'" in reopened.note
    assert [record.id for record in lights(store)] == [filed.id]
    assert store.finish_work(filed.id, 'Second fix.').done is None
    delivered(store, project, filed.id)
    assert store.complete_delivery(filed.id).done
    assert lights(store) == []


@pytest.mark.parametrize(('state', 'reason'), [('ready', 'Merge missing.'), ('merged', 'Activation pending.')])
def test_fault_done_names_missing_delivery_and_keeps_light(run, project, state, reason):
    store = mapped(project)
    web_fault(project)
    [filed] = tickets(store)
    store.finish_work(filed.id, 'Fixed.')
    delivered(store, project, filed.id, state=state, reason=reason)
    pending = store.finish_work(filed.id, 'Fixed.', proven=True)
    assert pending.done is None and lights(store)
    assert reason in pending.notices[0].message


def test_board_done_after_delivery_closes_fault_immediately(run, project):
    store = mapped(project)
    web_fault(project)
    [filed] = tickets(store)
    store.finish_work(filed.id, 'Fixed.')
    delivered(store, project, filed.id)
    assert store.move_work(filed.id, 'done').done
    assert lights(store) == []


def test_old_code_fault_is_recorded_without_reopening_delivered_repair(run, project):
    from metaform.modules.autoticket.proof import seconds
    assert seconds('1970-01-01T00:00:01.125000Z') == 1.125
    store = mapped(project)
    web_fault(project)
    [filed] = tickets(store)
    store.finish_work(filed.id, 'Fixed.')
    delivered(store, project, filed.id)
    assert store.complete_delivery(filed.id).done
    web_fault(project, 4, loaded=time.time() - 3600)
    record = store.ticket(filed.id).work
    assert record.done and lights(store) == []
    assert 'seen from code loaded before the fix' in record.note
    web_fault(project, 5, loaded=time.time() + 1)
    assert not store.ticket(filed.id).work.done
    assert [record.id for record in lights(store)] == [filed.id]
