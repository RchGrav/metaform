"""An actual ACP/MCP repair proceeds from a missing role through independent verification."""
import json
import sys
from pathlib import Path

import pytest

from metaform.data import Store
from metaform.module import context
from metaform.modules.dispatch.tests.test_dispatch import Dispatch, eventually
from metaform.modules.orchestration.state import SERVICE

pytestmark = pytest.mark.kind('simulation')


@pytest.mark.parametrize('selection', ['named', 'unnamed', 'automatic'])
def test_missing_specialist_reads_uri_and_delivers_one_canonical_ticket(
        run, home, project_folder, tmp_path, monkeypatch, selection):
    live = Dispatch(run, home, project_folder, tmp_path, orchestration=True)
    fake = Path(__file__).with_name('fake_swarm_agent.py')
    for agent in ('claude', 'codex', 'gemini'):
        run('set', f'--dispatch-{agent}', f'"{sys.executable}" "{fake}"', cwd=project_folder)
    run('set', '--dispatch-agents', '1', '--dispatch-machine-agents', '1', '--dispatch-autostart',
        '--dispatch-record-on-finish', 'off', '--orchestration-reviews', '1', cwd=project_folder)  # one assessment, waited for
    for name, value in live.env('ask', FAKE_SWARM_SCENARIO='direct', FAKE_SWARM_STATE=str(tmp_path / 'state')).items():
        if name.startswith('FAKE_'):
            monkeypatch.setenv(name, value)
    ctx = context('orchestration', project_folder, project='proj', nouns={
        'work': live.id, **({'role': 'route_specialist'} if selection == 'named' else {'create': True})})
    if selection == 'automatic':
        monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
        monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
        ctx.nouns = {}
        SERVICE.queue_routing(ctx, [live.id])
        assert SERVICE.route_pending(ctx)[0]['state'] == 'creating'
        assigned = SERVICE.assignment(ctx, work_id=live.id)
    else:
        assigned = SERVICE.claim(ctx)
    try:
        SERVICE.drain(ctx)
        def finished():
            errors = live.logged('fixture_error')
            assert not errors, errors
            with Store('proj', module='orchestration').tables(write=False) as tx:
                assignments = tx.rows('assignments', limit=0).results
            return assignments if len(assignments) == 3 and all(one['state'] in ('returned', 'delivered') for one in assignments) else None
        assignments = eventually(finished, limit=120)
        assert {one['authored_role_uri'] for one in assignments} == {
            'metaform://role/facilitator', 'metaform://role/route_specialist', 'metaform://role/functionality'}
        root = SERVICE.assignment(ctx, work_id=live.id)
        assert root['assignment_id'] == assigned['assignment_id']
        assert root['evidence'] and root['candidate']['sha256']
        assert live.store.ticket(live.id).work.done
        assert live.logged('role_resource') and 'metaform://role/route_specialist' in json.dumps(live.logged('role_resource'))
        assert live.logged('fqc_observation')
        assert 'SPECIALIST_RESULT' in (project_folder / 'candidate.txt').read_text()
    finally:
        run('dispatch', 'stop-all', cwd=project_folder, ok=False)
        live.close()
