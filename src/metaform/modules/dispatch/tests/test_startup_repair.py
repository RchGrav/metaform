"""Startup faults reach the existing system session through grouped fault events."""
import subprocess
import sys

import pytest

from metaform.modules.dispatch.tests.test_dispatch import dispatch, eventually, read  # noqa: F401

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('BASE-068')]


@pytest.mark.parametrize('automatic', [True, False])
def test_startup_failure_wakes_once_and_recurrence_wakes_again(dispatch, run, tmp_path, automatic, request):  # noqa: F811
    from metaform.data import Store
    from metaform.module import context

    run('enable', 'autoticket')
    sources = dispatch.store.layer('fault-sources', 'test', 'Fault ownership', mutable=True, hideable=True, ready=True)
    dispatch.store.add_item(sources.name, dispatch.node, 'Startup implementation',
                            refs=[('path', 'src/metaform/modules/dispatch/runner.py')])
    run('set', '--dispatch-autostart' if automatic else '--no-dispatch-autostart', cwd=dispatch.folder)
    request.addfinalizer(lambda: run('set', '--no-dispatch-autostart', cwd=dispatch.folder))
    gates = tmp_path / 'turns'
    gates.mkdir()
    for number in range(1, 6):
        (gates / str(number)).touch()
    dispatch.start('replace', 'system=true', FAKE_ACP_TURN_GATES=str(gates))

    def prompts():
        return [one['params']['prompt'][0]['text'] for one in dispatch.received('session/prompt')
                if one['params']['sessionId'] == 'fake-session-1']

    def idle():
        return read(run, dispatch)['sessions'][-1].get('activity') == 'idle'

    def groups():
        with Store('proj', module='autoticket').tables(write=False) as tx:
            return [dict(row) for row in tx.rows('groups', limit=0).results]

    eventually(lambda: len(prompts()) == 1 and idle())
    failed = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Exercise failed startup').id
    result = subprocess.run(
        [sys.executable, '-m', 'metaform', 'dispatch', 'run', failed, 'claude'], cwd=dispatch.folder,
        env=dispatch.env('replace', FAKE_ACP_START_FAIL='1'), capture_output=True, text=True, timeout=40, check=False)
    assert 'fixture startup failure' in result.stdout + result.stderr
    group = next(row for row in groups() if row['source'] == 'start')
    work = group['work_id']
    item = dispatch.store.numbers_of('work', [work])[work][0]
    phrase = f'{item}: blocks agent starts -> fix it now in your own session'
    def wakes():
        return [text for text in prompts() if phrase in text]

    eventually(lambda: len(wakes()) == 1, limit=10)
    eventually(idle)
    ctx = context('autoticket', dispatch.folder, project='proj')
    repeated = {'source': 'start', 'message': group['example'].splitlines()[0],
                'file': 'src/metaform/modules/dispatch/runner.py', 'detail': group['example'],
                'work_id': failed}
    ctx.publish('fault.raised', {'faults': [repeated] * 10})
    assert len(wakes()) == 1
    assert len(groups()) == 1

    # Ordinary faults stay in the inbox without starting a turn.
    ctx.publish('fault.raised', {'source': 'web', 'message': 'ordinary fixture failure',
                               'file': 'src/metaform/modules/dispatch/runner.py'})
    if automatic:
        ordinary = next(row for row in groups() if row['source'] == 'web')
        ref = dispatch.store.numbers_of('work', [ordinary['work_id']])[ordinary['work_id']][0]
        eventually(lambda: any(f'{ref}: fault filed' in one.value for one in dispatch.items('note')))
        assert not any(f'{ref}: fault filed' in text for text in prompts())
    assert len(wakes()) == 1

    # Proven completion rearms the canonical fault group.
    dispatch.store.finish_work(work, 'Fixture fix', proven=True)
    assert dispatch.store.ticket(work).work.done
    ctx.publish('fault.raised', repeated)
    eventually(lambda: len(wakes()) == 2, limit=10)
    assert not dispatch.store.ticket(work).work.done
    assert len([row for row in groups() if row['source'] == 'start']) == 1

    # Removing the fixture failure permits a real adapter session and completed worker prompt.
    run('set', '--no-dispatch-autostart', cwd=dispatch.folder)
    success = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Confirm startup recovery').id
    recovered = subprocess.run(
        [sys.executable, '-m', 'metaform', 'dispatch', 'run', success, 'claude'], cwd=dispatch.folder,
        env=dispatch.env('done', FAKE_ACP_WORK=success), capture_output=True, text=True, timeout=40, check=False)
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    assert dispatch.store.ticket(success).work.done


def test_pre_runner_fault_bypasses_full_filing_queue_and_preserves_cancellation(dispatch, run):  # noqa: F811
    from metaform.data import Store
    from metaform.module import context
    from metaform.modules import dispatch as module
    from metaform.modules.dispatch.signals import rows

    run('enable', 'autoticket')
    run('set', '--autoticket-open-most=1', cwd=dispatch.folder)
    layer = dispatch.store.layer('fault-sources', 'test', 'Fault ownership', mutable=True, hideable=True, ready=True)
    dispatch.store.add_item(layer.name, dispatch.node, 'Startup implementation',
                            refs=[('path', 'src/metaform/modules/dispatch/runner.py')])
    ctx = context('dispatch', dispatch.folder, project='proj')
    ctx.publish('fault.raised', {'source': 'web', 'message': 'Ordinary failure',
                               'file': 'src/metaform/modules/dispatch/runner.py'})
    for _ in range(10):
        module.start_failed(ctx, dispatch.store, dispatch.id, 'claude', 'Store upgrade refused')
    with Store('proj', module='autoticket').tables(write=False) as tx:
        groups = [dict(row) for row in tx.rows('groups', limit=0).results]
    assert len(groups) == 2
    group = next(row for row in groups if row['source'] == 'start')
    assert group['work_id'] and group['count'] == 10
    urgent = [one for one in rows(dispatch.store) if one.get('urgent')]
    assert len(urgent) == 1
    dispatch.store.finish_work(group['work_id'], 'Cancelled', outcome='cancelled')
    module.start_failed(ctx, dispatch.store, dispatch.id, 'claude', 'Store upgrade refused')
    assert dispatch.store.ticket(group['work_id']).work.outcome == 'cancelled'
    assert len([one for one in rows(dispatch.store) if one.get('urgent')]) == 1


def test_unrelated_changes_do_not_read_startup_faults():
    from types import SimpleNamespace

    from metaform.modules.dispatch import board

    def refused(*args, **kwargs):
        raise AssertionError('Unrelated events must not read fault or session state')

    ctx = SimpleNamespace(setting=refused, require_store=refused)
    for _ in range(10):
        board.fault_filed({'tables': ['memory.entities'], 'work_id': 'ordinary'}, ctx)


@pytest.mark.parametrize('failure', ['newer', 'upgrade', 'admission'])
def test_early_upgrade_refusal_reports_fault_but_admission_refusal_does_not(dispatch, monkeypatch, failure):  # noqa: F811
    import asyncio

    from metaform.data import NewerStore, StoreError
    from metaform.module import context
    from metaform.modules.dispatch import Refused, runner

    ctx = context('dispatch', dispatch.folder, project='proj', nouns={'id': dispatch.id, 'agent': 'claude'})
    error_type = {'newer': NewerStore, 'upgrade': StoreError, 'admission': Refused}[failure]
    error = error_type('Store upgrade refused' if failure != 'admission' else 'Stopped', 'resume')

    def refused(*args):
        raise error

    faults = []
    monkeypatch.setattr(runner, 'admit_self', refused)
    monkeypatch.setattr(runner, 'startup_fault', lambda *args: faults.append(args[-1]))
    monkeypatch.setattr(runner, 'given_back', lambda *args: None)
    with pytest.raises(type(error)):
        asyncio.run(runner.dispatch(ctx))
    assert bool(faults) == (failure != 'admission')


def test_missing_adapter_reports_startup_fault(dispatch, run, monkeypatch):  # noqa: F811
    from metaform.module import Stop, context
    from metaform.modules import dispatch as module

    run('set', '--dispatch-claude', '/missing/metaform-fixture-adapter', cwd=dispatch.folder)
    faults = []
    monkeypatch.setattr(module, 'startup_fault', lambda *args: faults.append(args[-1]))
    with pytest.raises(Stop, match='start command of claude is not found'):
        module.runnable(context('dispatch', dispatch.folder, project='proj', nouns={'id': dispatch.id}), 'claude')
    assert len(faults) == 1


def test_ordinary_fault_inbox_entry_does_not_wake():
    from metaform.modules.dispatch.runner import inbox_entry

    held = {'kind': 'board', 'board': 'fault:1:new', 'text': 'code.engine#1: fault filed',
            'from': {'agent': 'metaform'}}
    assert inbox_entry(held)[1] is False
