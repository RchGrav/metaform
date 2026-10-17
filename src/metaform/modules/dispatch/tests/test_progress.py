"""BASE-056 bounds automatic rework using recorded ticket progress, without a model."""
import json
import sys

import pytest

from metaform.data import Store
from metaform.module import context
from metaform.modules.dispatch.tests.test_dispatch import dispatch as dispatch  # noqa: PLC0414
from metaform.modules.dispatch.tests.test_dispatch import eventually

pytestmark = [pytest.mark.kind('simulation'), pytest.mark.req('BASE-056')]


def attempt(dispatch, runner, *, execute=True, how='the agent ended with exit code 1'):
    from metaform.modules.dispatch.progress import begin, executed, finish
    store = Store('proj', module='dispatch')
    begin(store, dispatch.ticket(), 'same-session', runner)
    if execute:
        executed(store, dispatch.id, runner)
    finish(store, dispatch.id, runner, how)
    return store


def test_limit_survives_new_stores_and_counts_resumes_once(dispatch):
    from metaform.modules.dispatch.progress import blocked, finish, refresh
    ctx = context('dispatch', dispatch.folder, project='proj')
    for number in range(3):
        store = attempt(dispatch, f'runner-{number}')
        finish(store, dispatch.id, f'runner-{number}', 'duplicate fallback release')
        assert blocked(ctx, Store('proj', module='dispatch'), dispatch.ticket()) == (number == 2)
    refresh(ctx, store, dispatch.ticket())
    refresh(ctx, store, dispatch.ticket())
    from metaform.modules.dispatch.signals import rows
    [signal] = [one for one in rows(store, dispatch.id) if one['signal'] == 'rework-limit']
    assert (signal['attempts'], signal['limit']) == (3, 3)


def test_only_steps_and_completion_clear_a_streak(dispatch):
    from metaform.modules.dispatch.progress import blocked, refresh
    from metaform.modules.dispatch.signals import rows
    ctx = context('dispatch', dispatch.folder, project='proj')
    for number in range(3):
        store = attempt(dispatch, f'first-{number}')
    refresh(ctx, store, dispatch.ticket())
    dispatch.store.edit_work(dispatch.id, {'note': 'More explanation.'})
    dispatch.store.plan_work(dispatch.id, 9)
    assert blocked(ctx, store, dispatch.ticket())
    dispatch.store.step_work(dispatch.id, 'Completed a necessary investigation.')
    refresh(ctx, store, dispatch.ticket())
    assert not blocked(ctx, store, dispatch.ticket())
    assert not [one for one in rows(store, dispatch.id) if one['signal'] == 'rework-limit']
    for number in range(3):
        attempt(dispatch, f'second-{number}')
    refresh(ctx, store, dispatch.ticket())
    assert len([one for one in rows(store, dispatch.id) if one['signal'] == 'rework-limit']) == 1
    dispatch.store.finish_work(dispatch.id, 'Finished.', 'The required result exists.')
    refresh(ctx, store, dispatch.ticket())
    assert not blocked(ctx, store, dispatch.ticket())
    assert not [one for one in rows(store, dispatch.id) if one['signal'] == 'rework-limit']


def test_idle_resumes_person_stops_and_stale_runners_do_not_count(dispatch):
    from metaform.modules.dispatch.progress import begin, blocked, executed, finish
    ctx = context('dispatch', dispatch.folder, project='proj')
    store = attempt(dispatch, 'idle', execute=False)
    for number in range(4):
        attempt(dispatch, f'stopped-{number}', how='stopped by the person')
    begin(store, dispatch.ticket(), 'same-session', 'current')
    executed(store, dispatch.id, 'current')
    finish(store, dispatch.id, 'old-runner', 'late cleanup')
    assert not blocked(ctx, store, dispatch.ticket())
    finish(store, dispatch.id, 'current', 'failed')
    attempt(dispatch, 'second')
    assert not blocked(ctx, store, dispatch.ticket())
    attempt(dispatch, 'third')
    assert blocked(ctx, store, dispatch.ticket())


def test_progress_during_an_attempt_does_not_count_as_a_failure(dispatch):
    from metaform.modules.dispatch.progress import begin, blocked, executed, finish, refresh
    ctx = context('dispatch', dispatch.folder, project='proj')
    for number in range(2):
        store = attempt(dispatch, f'failed-{number}')
    begin(store, dispatch.ticket(), 'same-session', 'productive')
    executed(store, dispatch.id, 'productive')
    dispatch.store.step_work(dispatch.id, 'Implemented a required part.')
    refresh(ctx, store, dispatch.ticket())
    finish(store, dispatch.id, 'productive', 'failed after progress')
    for number in range(2):
        attempt(dispatch, f'next-{number}')
    assert not blocked(ctx, store, dispatch.ticket())


def test_limit_can_be_disabled_without_erasing_observed_attempts(dispatch, run):
    from metaform.modules.dispatch.progress import blocked, refresh
    from metaform.modules.dispatch.signals import rows
    ctx = context('dispatch', dispatch.folder, project='proj')
    for number in range(3):
        store = attempt(dispatch, str(number))
    refresh(ctx, store, dispatch.ticket())
    run('set', '--dispatch-rework-limit=0', cwd=dispatch.folder)
    assert not blocked(ctx, store, dispatch.ticket())
    assert not [one for one in rows(store, dispatch.id) if one['signal'] == 'rework-limit']
    run('set', '--dispatch-rework-limit=3', cwd=dispatch.folder)
    assert blocked(ctx, store, dispatch.ticket())


def test_a_real_fake_worker_end_records_an_attempt_and_step_events_clear_it(dispatch, run):
    from metaform.modules.dispatch import end_group
    from metaform.modules.dispatch.progress import blocked
    run('set', '--dispatch-rework-limit=1', cwd=dispatch.folder)
    dispatch.start('hold')
    eventually(lambda: dispatch.logged('grandchild'))
    end_group(dispatch.logged('pid')[0])
    assert dispatch.process.wait(30) == 0
    ctx = context('dispatch', dispatch.folder, project='proj')
    store = Store('proj', module='dispatch')
    assert blocked(ctx, store, dispatch.ticket())
    shown = json.loads(run('dispatch', 'signals', f'id={dispatch.id}', '--json', cwd=dispatch.folder).stdout)
    assert [one for one in shown['signals'] if one['signal'] == 'rework-limit']
    run('map', 'work', 'op=step', f'id={dispatch.id}', 'said=Completed a required step.', cwd=dispatch.folder)
    assert not blocked(ctx, store, dispatch.ticket())
    shown = json.loads(run('dispatch', 'signals', f'id={dispatch.id}', '--json', cwd=dispatch.folder).stdout)
    assert not [one for one in shown['signals'] if one['signal'] == 'rework-limit']


def test_automatic_queue_glyph_and_supervisor_wait_but_explicit_start_can_finish(dispatch, run, monkeypatch):
    from metaform.modules import dispatch as module
    from metaform.modules.dispatch.progress import blocked
    run('set', '--dispatch-autostart', '--dispatch-rework-limit=1', cwd=dispatch.folder)
    run('map', 'work', 'op=edit', f'id={dispatch.id}', 'glyph=kite', cwd=dispatch.folder)
    store = attempt(dispatch, 'failed')
    ctx = context('dispatch', dispatch.folder, project='proj')
    started = []
    monkeypatch.setattr(module, 'run_reserved', lambda ctx, reservation: started.append(ctx.nouns['id']) or {})
    assert module.start_work(ctx, dispatch.store, {})['started'] == []
    assert started == [] and module.next_ticket(ctx, dispatch.store, 'kite', agent='claude') is None
    dispatch.store.take_work(dispatch.id, by='claude same-session')
    with store.tables() as tx:
        tx.insert('agent_sessions', {'session_id': 'same-session', 'work_id': dispatch.id, 'agent': 'claude', 'state': 'ended',
                               'how': 'the agent ended with exit code 1', 'started': '2026-10-14T00:00:00Z', 'seq': 1,
                               'origin': module.origin()})
    assert module.retry(ctx, dispatch.store) == {'retried': []}
    assert blocked(ctx, store, dispatch.ticket())
    run('map', 'work', 'op=move', f'id={dispatch.id}', 'column=todo', cwd=dispatch.folder)
    run('set', '--no-dispatch-autostart', cwd=dispatch.folder)
    dispatch.start('done')  # an explicit run is available even with the automatic rework gate closed
    assert dispatch.process.wait(30) == 0
    assert dispatch.ticket().done
    assert not blocked(ctx, store, dispatch.ticket())


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='safe live group cleanup requires Linux pidfds')
def test_verified_dead_recovery_counts_once_and_keeps_recovery_available_at_limit(dispatch, run):
    from metaform.modules.dispatch.progress import blocked
    run('set', '--dispatch-recovery=automatic', '--dispatch-rework-limit=1', cwd=dispatch.folder)
    dispatch.start('hold', FAKE_ACP_ORPHAN_HOLD='1')
    eventually(lambda: dispatch.logged('grandchild'))
    dispatch.process.kill()
    dispatch.process.wait()
    recovered = json.loads(run('dispatch', 'recover', '--json', cwd=dispatch.folder).stdout)
    assert recovered['released'] == [dispatch.id]
    assert not dispatch.ticket().taken
    ctx = context('dispatch', dispatch.folder, project='proj')
    assert blocked(ctx, Store('proj', module='dispatch'), dispatch.ticket())
    again = json.loads(run('dispatch', 'recover', '--json', cwd=dispatch.folder).stdout)
    assert again['released'] == []
    shown = json.loads(run('dispatch', 'signals', f'id={dispatch.id}', '--json', cwd=dispatch.folder).stdout)
    [signal] = [one for one in shown['signals'] if one['signal'] == 'rework-limit']
    assert signal['attempts'] == 1


def test_stale_snapshot_cannot_raise_an_alert_after_progress(dispatch):
    from metaform.modules.dispatch.progress import refresh
    from metaform.modules.dispatch.signals import rows
    for number in range(3):
        store = attempt(dispatch, str(number))
    stale = dispatch.ticket()
    dispatch.store.step_work(dispatch.id, 'A real step completed before the queued refresh.')
    refresh(context('dispatch', dispatch.folder, project='proj'), store, stale)
    assert not [one for one in rows(store, dispatch.id) if one['signal'] == 'rework-limit']


def test_manual_requeue_and_reset_cannot_lose_or_duplicate_an_executed_attempt(dispatch, run, monkeypatch):
    from metaform.modules import dispatch as module
    from metaform.modules.dispatch.progress import begin, blocked, executed
    run('set', '--dispatch-rework-limit=1', cwd=dispatch.folder)
    ctx = context('dispatch', dispatch.folder, project='proj')
    store = Store('proj', module='dispatch')
    dispatch.store.take_work(dispatch.id, by='claude same-session')
    begin(store, dispatch.ticket(), 'same-session', 'dead-runner')
    executed(store, dispatch.id, 'dead-runner')
    with store.tables() as tx:
        tx.insert('agent_sessions', {'session_id': 'same-session', 'work_id': dispatch.id, 'agent': 'claude', 'state': 'running',
                               'runner': 'dead-runner', 'started': '2026-10-14T00:00:00Z', 'seq': 1})
    monkeypatch.setattr(module, 'sessions', lambda *args, **kwargs: [])  # verified gone, no process is launched here
    assert module.reset(ctx)['released'] == [dispatch.id]
    assert blocked(ctx, store, dispatch.ticket())
    dispatch.store.step_work(dispatch.id, 'Prepared a different execution approach.')
    dispatch.store.take_work(dispatch.id, by='claude new-session')
    begin(store, dispatch.ticket(), 'new-session', 'new-runner')
    executed(store, dispatch.id, 'new-runner')
    run('map', 'work', 'op=move', f'id={dispatch.id}', 'column=todo', cwd=dispatch.folder)
    assert blocked(ctx, store, dispatch.ticket())
    module.release(store, dispatch.id, 'claude new-session', True, None, 'late cleanup', runner='new-runner')


def test_nonactive_base_signal_is_raised_and_cleared_only_in_its_own_base(dispatch):
    from metaform.modules.dispatch.progress import blocked, changed
    from metaform.modules.dispatch.signals import rows
    for number in range(3):
        attempt(dispatch, str(number))
    first = dispatch.store.bound_base()
    assert first is not None
    other = dispatch.store.add_base('other')
    original = Store('proj', base=first.id)  # a map store for the counter's base, while another base is active
    ctx = context('dispatch', dispatch.folder, project='proj')
    changed({'base_id': first.id, 'tables': ['work']}, ctx)
    assert blocked(ctx, original, original.ticket(dispatch.id).work)
    assert [one for one in rows(original, dispatch.id) if one['signal'] == 'rework-limit']
    assert not rows(Store('proj', base=other.id, module='dispatch'), dispatch.id)
    original.step_work(dispatch.id, 'Completed work on the nonactive base.')
    changed({'base_id': first.id, 'tables': ['work']}, ctx)
    assert not [one for one in rows(original, dispatch.id) if one['signal'] == 'rework-limit']
    assert not rows(Store('proj', base=other.id, module='dispatch'), dispatch.id)


def test_late_release_cannot_end_a_resumed_worker_or_clear_its_permissions(dispatch, run):
    from metaform.modules.dispatch import release
    from metaform.modules.dispatch.progress import begin, blocked, executed
    from metaform.modules.dispatch.signals import publish, rows
    run('set', '--dispatch-rework-limit=1', cwd=dispatch.folder)
    ctx = context('dispatch', dispatch.folder, project='proj')
    store = Store('proj', module='dispatch')
    dispatch.store.take_work(dispatch.id, by='claude same-session')
    begin(store, dispatch.ticket(), 'same-session', 'resumed-runner')
    executed(store, dispatch.id, 'resumed-runner')
    with store.tables() as tx:
        tx.insert('agent_sessions', {'session_id': 'same-session', 'work_id': dispatch.id, 'agent': 'claude', 'state': 'running',
                               'runner': 'resumed-runner', 'started': '2026-10-14T00:00:00Z', 'seq': 1})
    publish(ctx, 'permission-waiting', work_id=dispatch.id, session_id='same-session', key='permission',
            message_id='permission')
    release(store, dispatch.id, 'claude same-session', True, 'same-session', 'late cleanup', runner='old-runner')
    with store.tables(write=False) as tx:
        assert tx.get('agent_sessions', {'session_id': 'same-session'})['state'] == 'running'
    assert [one for one in rows(store, dispatch.id) if one['signal'] == 'permission-waiting']
    assert not blocked(ctx, store, dispatch.ticket())
    for _ in range(2):
        release(store, dispatch.id, 'claude same-session', True, 'same-session', 'failed', runner='resumed-runner')
    assert blocked(ctx, store, dispatch.ticket())
    assert not [one for one in rows(store, dispatch.id) if one['signal'] == 'permission-waiting']
    [signal] = [one for one in rows(store, dispatch.id) if one['signal'] == 'rework-limit']
    assert signal['attempts'] == 1


def test_reset_of_a_dead_intake_needs_no_ticket_or_progress_counter(dispatch, monkeypatch):
    from metaform.modules import dispatch as module
    store = Store('proj', module='dispatch')
    with store.tables() as tx:
        tx.insert('agent_sessions', {'session_id': 'intake-session', 'work_id': 'intake-dead', 'agent': 'claude',
                               'state': 'running', 'runner': 'dead-runner', 'started': '2026-10-14T00:00:00Z', 'seq': 1})
    monkeypatch.setattr(module, 'sessions', lambda *args, **kwargs: [])
    result = module.reset(context('dispatch', dispatch.folder, project='proj'))
    assert result == {'released': [], 'sessions_ended': ['intake-dead'], 'still_working': [], 'kept_for_you': [],
                      'deferred': []}
    with store.tables(write=False) as tx:
        assert tx.get('agent_sessions', {'session_id': 'intake-session'})['state'] == 'ended'


@pytest.mark.req('QUAL-015')
def test_a_burst_of_note_edits_reads_no_progress_and_a_refresh_with_nothing_to_do_takes_no_write_lock(dispatch,
                                                                                                    monkeypatch):
    """UX review round 1, runaway F3: a ticket's words change no progress, so the handler reads nothing for them; a
    step still reconciles; and a reconcile that finds nothing to change writes nothing."""
    from metaform import changes, events
    from metaform.modules.dispatch import progress
    ctx = context('dispatch', dispatch.folder, project='proj')
    for number in range(3):
        attempt(dispatch, f'runner-{number}')  # a streak, so the ticket has progress to read
    fired: list[dict] = []
    monkeypatch.setattr(events, 'publish', lambda topic, payload, source: fired.append(payload) or [])
    changes.announce(dispatch.folder, 'cli')
    fired.clear()
    for number in range(100):
        dispatch.store.edit_work(dispatch.id, {'note': f'Note {number}.'})
        changes.announce(dispatch.folder, 'cli')
    burst = [one for one in fired if one.get('base_id')]
    assert len(burst) == 100 and all(one['kinds'] == ['note'] for one in burst), burst[:2]
    reads = []
    opened = Store.tables

    def counted(self, *args, **kwargs):
        reads.append(self.module)
        return opened(self, *args, **kwargs)

    monkeypatch.setattr(Store, 'tables', counted)
    for payload in burst:
        progress.changed(payload, ctx)
    assert reads == [], 'a note edit reads no progress'
    fired.clear()
    monkeypatch.setattr(Store, 'tables', opened)
    dispatch.store.step_work(dispatch.id, 'A step.')
    changes.announce(dispatch.folder, 'cli')
    [stepped] = [one for one in fired if one.get('base_id')]
    monkeypatch.setattr(Store, 'tables', counted)
    progress.changed(stepped, ctx)
    assert reads, 'a step is read and reconciled'
    locks = []
    atomic = Store.atomic
    monkeypatch.setattr(Store, 'atomic', lambda self: locks.append(1) or atomic(self))
    progress.refresh(ctx, Store('proj', module='dispatch'), dispatch.ticket())  # reconciled already: nothing to do
    assert locks == [], 'a refresh with nothing to change takes no write lock'
