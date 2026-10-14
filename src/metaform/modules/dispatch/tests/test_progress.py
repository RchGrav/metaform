"""BASE-056 bounds automatic rework using recorded ticket progress, without a model."""
import json

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
    refresh(ctx, store, dispatch.ticket())
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
