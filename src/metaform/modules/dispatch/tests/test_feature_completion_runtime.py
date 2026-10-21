"""Full Auto closes resolved work, integrates Git features locally, and releases dependencies."""
import json
import sys

import pytest

from metaform import events
from metaform.data import Store
from metaform.modules.dispatch.merge import branch_of, git
from metaform.modules.dispatch.tests.test_completion_commit import initialize
from metaform.modules.dispatch.tests.test_dispatch import dispatch as dispatch  # noqa: PLC0414
from metaform.modules.dispatch.tests.test_dispatch import eventually, gone
from metaform.modules.web.server import Server, projects_started

pytestmark = [pytest.mark.req('BASE-052'), pytest.mark.req('VIEW-042'), pytest.mark.kind('simulation')]


@pytest.mark.parametrize(('board', 'development_branch', 'condition'), [
    ('repair-queue', 'main', 'broken'), ('verification-lab', 'trunk', 'trouble'),
])
@pytest.mark.parametrize('repository_present', [True, False], ids=['git', 'non-git'])
def test_fresh_board_automatically_saves_verified_fault_and_releases_dependency(
        dispatch, run, monkeypatch, board, development_branch, condition, repository_present):
    original = None
    if repository_present:
        initialize(dispatch.folder)
        assert git(dispatch.folder, 'branch', '-m', development_branch).returncode == 0
        if development_branch != 'main':
            assert git(dispatch.folder, 'branch', 'main').returncode == 0
        original = git(dispatch.folder, 'rev-parse', 'HEAD').stdout.strip()
        assert not git(dispatch.folder, 'remote').stdout.strip()
    run('map', 'boards', 'op=add', f'name={board}', cwd=dispatch.folder)
    run('set', '--board', board, cwd=dispatch.folder)
    first = dispatch.id
    dispatch.store.edit_work(first, {'condition': condition, 'kind': 'broken'})
    second = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Verify dependent feature').id
    for work_id in (first, second):
        run('map', 'work', 'op=edit', f'id={work_id}', f'board={board}', cwd=dispatch.folder)
    run('map', 'work', 'op=edit', f'id={second}', f'after_work={json.dumps([first])}', cwd=dispatch.folder)
    check = f'"{sys.executable}" -c "from pathlib import Path; assert Path(\'feature.txt\').is_file()"'
    run('set', '--dispatch-autostart', '--dispatch-agents=1', '--dispatch-worktrees',
        '--no-dispatch-stay-connected', '--dispatch-record-on-finish=off',
        f'--dispatch-test-command={check}', cwd=dispatch.folder)
    monkeypatch.setenv('FAKE_ACP_MODE', 'done')
    monkeypatch.setenv('FAKE_ACP_LOG', str(dispatch.log))
    monkeypatch.setenv('FAKE_ACP_EDIT', 'feature.txt')
    # Match normal server startup: register its change listener, then reconcile registered projects.
    with Server('127.0.0.1', 0, 'fixture') as server, events.listen('web', server.changed):
        try:
            projects_started(server)

            def completed():
                with Store('proj', module='dispatch').tables(write=False) as tables:
                    sessions = [row for row in tables.rows('agent_sessions', limit=0).results
                                if row['work_id'] in (first, second)]
                return len(sessions) == 2 and all(row['state'] == 'ended' for row in sessions) \
                    and all(dispatch.store.ticket(work_id).work.done for work_id in (first, second))

            eventually(completed, limit=45)
            with Store('proj', module='dispatch').tables(write=False) as tables:
                sessions = [row for row in tables.rows('agent_sessions', limit=0).results
                            if row['work_id'] in (first, second)]
                receipts = [tables.get('merges', {'work_id': work_id}) for work_id in (first, second)]
                assert not tables.rows('activations', limit=0).results
            assert {row['work_id'] for row in sessions} == {first, second}
            assert gone([row['pid'] for row in sessions], limit=20)
            for work_id, receipt in zip((first, second), receipts, strict=True):
                assert receipt['work_id'] == work_id
                assert receipt['state'] == ('merged' if repository_present else 'committed')
                assert receipt['evidence']['verification']['passed'] is True
                assert receipt['evidence']['verification']['command'] == check
                assert receipt['evidence']['repository'] is repository_present
                if repository_present:
                    assert receipt['branch'] == branch_of(work_id)
                    assert receipt['head'] == git(receipt['worktree'], 'rev-parse', 'HEAD').stdout.strip()
                    assert receipt['evidence']['artifacts'] == ['feature.txt'] if work_id == first \
                        else set(receipt['evidence']['artifacts']) <= {'feature.txt'}
                    assert f'Metaform-Ticket: {work_id}' in git(
                        receipt['worktree'], 'log', '-1', '--format=%B').stdout
                else:
                    assert receipt['head'] is None and receipt['branch'] == ''
                    assert receipt['worktree'] == str(dispatch.folder)
                    assert receipt['evidence']['artifacts'] == []
            one, two = (dispatch.store.ticket(work_id).work for work_id in (first, second))
            assert one.done <= two.taken, 'the dependent worker started before fault closure'
            assert not dispatch.store.where('code.engine').work
            if repository_present:
                assert git(dispatch.folder, 'rev-parse', 'HEAD').stdout.strip() != original
                assert git(dispatch.folder, 'show', 'HEAD:feature.txt').stdout == 'changed by the fake agent\n'
                for receipt in receipts:
                    assert git(dispatch.folder, 'diff', '--quiet', receipt['head'], 'HEAD',
                               '--', 'feature.txt').returncode == 0
            else:
                assert not (dispatch.folder / '.git').exists()
                assert (dispatch.folder / 'feature.txt').read_text() == 'changed by the fake agent\n'
        finally:
            run('dispatch', 'stop-all', cwd=dispatch.folder)
            server.close_backgrounds()
            if server.deaths is not None:
                server.deaths.close()
            server.vouch.close()
