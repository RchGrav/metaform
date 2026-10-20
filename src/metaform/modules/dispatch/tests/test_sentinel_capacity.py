"""Sentinel admission stays independent of work and temporary helper capacity."""
import asyncio
import json
import os

import pytest

from metaform.modules.dispatch.tests.test_dispatch import NODE, dispatch  # noqa: F401

pytestmark = pytest.mark.kind('fixture')


def test_sentinel_starts_with_worker_and_helper_capacity_full(dispatch, run, monkeypatch):  # noqa: F811
    from metaform.module import context
    from metaform.modules import dispatch as module

    run('set', '--dispatch-agents=1', '--dispatch-machine-agents=1', cwd=dispatch.folder)
    ctx = context('dispatch', dispatch.folder, project='proj')
    entries = [{'pid': 1000 + i, 'project': 'proj', 'kind': 'summoned', 'work_id': f'chat-{i}'}
               for i in range(module.HELPERS_MOST)]
    entries.append({'pid': 2000, 'project': 'proj', 'kind': 'worker', 'work_id': dispatch.id})
    monkeypatch.setattr(module, 'launches', lambda: entries)
    monkeypatch.setattr(module, 'in_use', lambda *args: [])
    starts = []

    def start(ctx, store, work_id, agent, words, name, **kwargs):
        kind = module.capacity_kind(ctx, work_id, module.launch_kind(words))
        module.admit(ctx, store, work_id, kind, auto=True)
        starts.append(kind)
        return {'pid': 3000, 'log': 'unused'}

    monkeypatch.setattr(module, 'start_runner', start)
    result = module.raise_issue(context('dispatch', dispatch.folder, project='proj',
                                        nouns={'node': NODE, 'text': ['Investigate latency.']}))
    assert result['state'] == 'starting'
    assert starts == ['sentinel']
    assert module.slots(ctx, dispatch.store)['room'] == 0


def test_failed_runner_releases_live_ledger_and_lease(dispatch, monkeypatch):  # noqa: F811
    from metaform.module import context
    from metaform.modules import dispatch as module
    from metaform.modules.dispatch import runner
    from metaform.modules.dispatch.recovery import identity

    work_id = 'helper-failed'
    module._recorded(os.getpid(), {'pid': os.getpid(), 'born': identity(os.getpid()),
                                  'project': 'proj', 'work_id': work_id, 'kind': 'helper'})
    token, lease, descriptor = module._leased()
    assert token
    if descriptor is not None:
        os.close(descriptor)
    monkeypatch.setenv(module.LEASE_VARIABLE, str(lease))
    ctx = context('dispatch', dispatch.folder, project='proj', nouns={'id': work_id, 'agent': 'claude'})
    assert module.slots(ctx, dispatch.store)['helpers'] == 1

    async def fail(ctx):
        raise RuntimeError('startup failed')

    monkeypatch.setattr(runner, 'sessions_run', fail)
    monkeypatch.setattr(runner, 'start_failed', lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, 'given_back', lambda *args, **kwargs: None)
    with pytest.raises(RuntimeError, match='startup failed'):
        asyncio.run(runner.dispatch(ctx))
    assert module.slots(ctx, dispatch.store)['helpers'] == 0
    assert not lease.exists()


def test_legacy_sentinel_and_advisor_entries_hold_no_helper_slot(dispatch):  # noqa: F811
    from metaform.module import context
    from metaform.modules import dispatch as module
    from metaform.modules.dispatch.recovery import identity

    for i, subject in enumerate(('sentinel=code.dispatcher.agent', 'system')):
        path = module.ledger() / f'{os.getpid()}-legacy-{i}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'pid': os.getpid(), 'born': identity(os.getpid()), 'project': 'proj',
                                    'work_id': f'legacy-{i}', 'kind': 'summoned', 'subject': subject}))
    held = module.slots(context('dispatch', dispatch.folder, project='proj'), dispatch.store)
    assert held['helpers'] == held['workers'] == 0
    assert held['room'] == module.HELPERS_MOST


def test_ended_helper_releases_slot_before_runner_exits(dispatch):  # noqa: F811
    from metaform.module import context
    from metaform.modules import dispatch as module
    from metaform.modules.dispatch import runner
    from metaform.modules.dispatch.recovery import identity

    work_id = 'helper-ended'
    ctx = context('dispatch', dispatch.folder, project='proj')
    module._recorded(os.getpid(), {'pid': os.getpid(), 'born': identity(os.getpid()),
                                  'project': 'proj', 'work_id': work_id, 'kind': 'helper'})
    assert module.slots(ctx, dispatch.store)['helpers'] == 1
    session = runner.Session(ctx, dispatch.store, None, 'claude', ['unused'], prep=True, work_id=work_id)
    asyncio.run(session.end('its brief is done'))
    assert session.over.is_set()
    assert module.slots(ctx, dispatch.store)['helpers'] == 0


def test_sentinel_process_starts_while_all_capacity_is_held(dispatch, run, dispatch_runners):  # noqa: F811
    from metaform.module import context
    from metaform.modules import dispatch as module
    from metaform.modules.dispatch.recovery import identity
    from metaform.modules.dispatch.tests.test_dispatch import eventually

    run('set', '--dispatch-agents=1', '--dispatch-machine-agents=1', cwd=dispatch.folder)
    folder = module.ledger()
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(module.HELPERS_MOST + 1):
        (folder / f'{os.getpid()}-capacity-{i}.json').write_text(json.dumps({
            'pid': os.getpid(), 'born': identity(os.getpid()), 'project': 'proj',
            'work_id': f'capacity-{i}', 'kind': 'worker' if i == 0 else 'helper'}))
    started = json.loads(run('dispatch', 'raise', NODE, '--json', '--', 'Investigate full capacity.',
                             cwd=dispatch.folder, env=dispatch.env('hold')).stdout)
    dispatch_runners.append((started, dispatch.folder, dispatch.log))
    assert started['state'] == 'starting'
    eventually(lambda: dispatch.received('session/prompt'))
    held = module.slots(context('dispatch', dispatch.folder, project='proj'), dispatch.store)
    assert held['workers'] == 1
    assert held['helpers'] == module.HELPERS_MOST
    assert any(entry['work_id'] == started['work_id'] and entry['kind'] == 'sentinel'
               for entry in module.launches())
    run('dispatch', 'stop', started['work_id'], cwd=dispatch.folder)
