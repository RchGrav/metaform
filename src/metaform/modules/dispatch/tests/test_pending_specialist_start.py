"""Pending expertise must not launch a worker before publication."""
import pytest

from metaform.module import context
from metaform.modules.dispatch.tests.test_dispatch import Dispatch


@pytest.mark.kind('fixture')
@pytest.mark.parametrize('automatic', [False, True])
@pytest.mark.parametrize('reserved', [False, True])
def test_start_waits_for_existing_specialist_commission(
        run, home, project_folder, tmp_path, monkeypatch, automatic, reserved):
    from metaform.modules import dispatch as package
    from metaform.modules.orchestration.state import SERVICE, own

    made = Dispatch(run, home, project_folder, tmp_path, orchestration=True)
    run('set', '--no-dispatch-autostart', cwd=project_folder)
    owner = context('orchestration', project_folder, project='proj', nouns={'work': made.id, 'create': True})
    pending = SERVICE.claim(owner)
    if not reserved:
        made.store.move_work(made.id, 'todo', kept=True)
    before = made.store.ticket(made.id).work.taken_by
    launched = []
    called = context('dispatch', project_folder, project='proj', surface='mcp' if automatic else 'cli',
                     nouns={'id': made.id, 'agent': 'claude'})
    monkeypatch.setattr(package, 'on_persons_word', lambda *args: None)
    monkeypatch.setattr(package, 'on_word', lambda *args: {})
    monkeypatch.setattr(package, 'mcp_server', lambda *args: None)
    monkeypatch.setattr(package, 'run_reserved', lambda *args, **kwargs: launched.append(True) or {'state': 'starting'})
    try:
        for _ in range(2):
            result = package.start(called)
            assert result['state'] == 'needs_specialist'
        assert launched == []
        assert made.store.ticket(made.id).work.taken_by == before
        held = SERVICE.assignment(owner, work_id=made.id)
        assert held['assignment_id'] == pending['assignment_id']
        assert held['state'] == 'waiting' and held['owner_session_id'] is None
        with own(owner).tables(write=False) as tx:
            request, = tx.rows('role_requests', limit=0).results
            assert request['state'] == 'commissioned'
    finally:
        made.close()


@pytest.mark.kind('fixture')
def test_runner_waits_before_opening_adapter_for_pending_specialist(
        run, home, project_folder, tmp_path, monkeypatch):
    import asyncio

    from metaform.data import Store
    from metaform.modules.dispatch import runner
    from metaform.modules.dispatch.orchestration import SUSPENDED
    from metaform.modules.orchestration.state import SERVICE

    made = Dispatch(run, home, project_folder, tmp_path, orchestration=True)
    run('set', '--no-dispatch-autostart', cwd=project_folder)
    owner = context('orchestration', project_folder, project='proj', nouns={'work': made.id, 'create': True})
    pending = SERVICE.claim(owner)
    ctx = context('dispatch', project_folder, project='proj')
    session = runner.Session(ctx, Store('proj', module='dispatch'), made.ticket(), 'claude', ['true'])

    async def forbidden(*args, **kwargs):
        pytest.fail('Pending expertise must not open an adapter.')

    monkeypatch.setattr(session, 'open_agent', forbidden)
    monkeypatch.setattr(runner, 'mcp_server', lambda *args: None)
    try:
        result = asyncio.run(session.run())
        assert result['ended'] == SUSPENDED
        assert session.how == SUSPENDED and session.ended.is_set()
        assert session.session_id is None
        held = SERVICE.assignment(owner, work_id=made.id)
        assert held['assignment_id'] == pending['assignment_id']
        assert held['state'] == 'waiting' and held['owner_session_id'] is None
    finally:
        made.close()
