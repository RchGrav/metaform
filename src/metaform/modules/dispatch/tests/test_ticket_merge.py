"""Explicit saved-candidate integration, cleanup and completion in temporary repositories."""
from __future__ import annotations

import importlib
from datetime import UTC, datetime

import pytest

from metaform.data import Store
from metaform.module import context
from metaform.modules.dispatch.tests.test_merge import dispatch as dispatch  # noqa: PLC0414
from metaform.modules.dispatch.tests.test_merge import git, worked
from metaform.modules.dispatch.tests.test_merge import repo as repo  # noqa: PLC0414

pytestmark = [pytest.mark.kind('simulation'), pytest.mark.req('VIEW-044')]
merge = importlib.import_module('metaform.modules.dispatch.merge')


def saved_open(dispatch, repo):
    [saved] = worked(dispatch, repo)
    dispatch.store.move_work(dispatch.id, 'doing')
    with Store('proj', module='map').tables() as tx:
        fields = {'landed': datetime.now(UTC).isoformat()}
        if tx.update('ticket_settings', {'work_id': dispatch.id}, fields) is None:
            tx.insert('ticket_settings', {'work_id': dispatch.id, **fields})
    assert not dispatch.ticket().done and dispatch.ticket().resolution
    return saved


def integrate(dispatch, repo, saved):
    return merge.merge_due(context('dispatch', repo, project='proj'), dispatch.store, dispatch.id,
                           expected_head=saved['head'])


def state(dispatch):
    with Store('proj', module='dispatch').tables(write=False) as tx:
        return dict(tx.get('merges', {'work_id': dispatch.id}))


@pytest.mark.parametrize('already_done', [False, True])
def test_ticket_click_integrates_once_cleans_and_keeps_result_without_full_auto(
        dispatch, repo, monkeypatch, already_done):
    saved = worked(dispatch, repo)[0] if already_done else saved_open(dispatch, repo)
    resolution, completed = dispatch.ticket().resolution, dispatch.ticket().done
    (repo / 'README.md').write_text('peer staged\n', encoding='utf-8')
    git(repo, 'add', 'README.md')
    (repo / 'peer.txt').write_text('peer untracked\n', encoding='utf-8')
    staged = git(repo, 'diff', '--cached')
    monkeypatch.setattr(merge, 'push_ticket', lambda *args: pytest.fail('No publishing was requested.'))
    result = integrate(dispatch, repo, saved)
    assert result['merged'] and result['done'] and not result['pushed'], result
    assert result['cleanup']['state'] == 'complete'
    assert not (repo / saved['worktree']).exists()
    assert (repo / 'feature.txt').read_text() == 'ticket feature\n'
    assert (repo / 'peer.txt').read_text() == 'peer untracked\n'
    assert git(repo, 'diff', '--cached') == staged
    assert dispatch.ticket().resolution == resolution
    if already_done:
        assert dispatch.ticket().done == completed
    assert state(dispatch)['evidence']['verification'] == saved['evidence']['verification']
    head = git(repo, 'rev-parse', 'HEAD')
    assert integrate(dispatch, repo, saved)['done']
    assert git(repo, 'rev-parse', 'HEAD') == head
    assert git(repo, 'rev-parse', saved['branch']) == saved['head']
    assert not context('dispatch', repo).setting('dispatch_autostart')


def test_committed_branch_conflict_retains_open_ticket_and_candidate(dispatch, repo):
    saved = saved_open(dispatch, repo)
    (repo / 'feature.txt').write_text('other committed feature\n')
    git(repo, 'add', 'feature.txt')
    git(repo, 'commit', '-qm', 'Concurrent feature')
    head = git(repo, 'rev-parse', 'HEAD')
    result = integrate(dispatch, repo, saved)
    assert not result['merged'] and 'conflict' in result['why'].lower()
    assert not dispatch.ticket().done
    assert (repo / saved['worktree']).exists()
    assert git(repo, 'rev-parse', 'HEAD') == head
    assert git(repo, 'rev-parse', saved['branch']) == saved['head']
    assert state(dispatch)['reason'] == result['why']


def test_clashing_shared_untracked_file_does_not_claim_success_or_close(dispatch, repo):
    saved = saved_open(dispatch, repo)
    (repo / 'feature.txt').write_text('local untracked feature\n')
    head = git(repo, 'rev-parse', 'HEAD')
    result = integrate(dispatch, repo, saved)
    assert not result['merged'] and 'feature.txt' in result['why']
    assert not dispatch.ticket().done
    assert git(repo, 'rev-parse', 'HEAD') == head
    assert (repo / 'feature.txt').read_text() == 'local untracked feature\n'
    assert (repo / saved['worktree']).exists()


@pytest.mark.parametrize('dirty', ['tracked', 'staged', 'untracked', 'ignored'])
def test_cleanup_retains_dirty_candidate_then_retries_without_a_second_merge(dispatch, repo, dirty):
    saved = saved_open(dispatch, repo)
    folder = repo / saved['worktree']
    path = folder / ('README.md' if dirty in ('tracked', 'staged') else 'scratch.txt')
    if dirty == 'ignored':
        excluded = merge.git(folder, 'rev-parse', '--git-path', 'info/exclude').stdout.strip()
        with open(excluded, 'a') as stream:
            stream.write('\nscratch.txt\n')
    path.write_text('Recover this work.\n')
    if dirty == 'staged':
        git(folder, 'add', 'README.md')
    result = integrate(dispatch, repo, saved)
    assert result['merged'] and not result['done'], result
    assert result['cleanup']['state'] == 'pending' and 'files remain' in result['why']
    assert not dispatch.ticket().done and path.read_text() == 'Recover this work.\n'
    head = git(repo, 'rev-parse', 'HEAD')
    if dirty in ('tracked', 'staged'):
        git(folder, 'restore', '--source=HEAD', '--staged', '--worktree', 'README.md')
    else:
        path.unlink()
    result = integrate(dispatch, repo, saved)
    assert result['merged'] and result['done'] and result['cleanup']['state'] == 'complete', result
    assert git(repo, 'rev-parse', 'HEAD') == head
    assert not folder.exists()


def test_stale_candidate_and_moved_branch_are_rejected(dispatch, repo):
    saved = saved_open(dispatch, repo)
    assert 'changed' in merge.merge_due(context('dispatch', repo), dispatch.store, dispatch.id,
                                         expected_head='0' * 40)['why']
    folder = repo / saved['worktree']
    (folder / 'later.txt').write_text('Later unsaved implementation.\n')
    git(folder, 'add', 'later.txt')
    git(folder, 'commit', '-qm', 'Later candidate')
    result = integrate(dispatch, repo, saved)
    assert not result['merged'] and 'branch changed' in result['why']
    assert not dispatch.ticket().done and folder.exists()


def test_active_worker_blocks_merge_and_new_worker_during_checks_blocks_landing(dispatch, repo, monkeypatch):
    saved = saved_open(dispatch, repo)
    own = Store('proj', module='dispatch')

    def worker():
        with own.tables() as tx:
            tx.insert('sessions', {'session_id': 'active-worker', 'work_id': dispatch.id, 'agent': 'codex',
                                   'state': 'running', 'started': '2026-10-21T00:00:00Z', 'seq': 1})
    worker()
    assert 'agent still owns' in integrate(dispatch, repo, saved)['why']
    with own.tables() as tx:
        tx.delete('sessions', {'session_id': 'active-worker'})
    real = merge.tests_pass

    def during_check(folder, command):
        worker()
        return real(folder, command)
    monkeypatch.setattr(merge, 'tests_pass', during_check)
    result = integrate(dispatch, repo, saved)
    assert not result['merged'] and 'agent still owns' in result['why']
    assert not (repo / 'feature.txt').exists()
    assert not dispatch.ticket().done


def test_repeat_request_while_lock_is_held_does_no_git_work(dispatch, repo):
    saved = saved_open(dispatch, repo)
    head = git(repo, 'rev-parse', 'HEAD')
    with merge.Queued(repo) as held:
        assert held
        result = integrate(dispatch, repo, saved)
    assert not result['merged'] and 'under way' in result['why']
    assert git(repo, 'rev-parse', 'HEAD') == head
    assert integrate(dispatch, repo, saved)['done']


def test_other_ticket_worktree_is_never_removed(dispatch, repo):
    saved = saved_open(dispatch, repo)
    other = merge.worktree_for(repo, 'different-ticket-1234')
    with Store('proj', module='dispatch').tables() as tx:
        tx.update('merges', {'work_id': dispatch.id}, {'worktree': str(other)})
    result = integrate(dispatch, repo, saved)
    assert result['merged'] and result['cleanup']['state'] == 'pending'
    assert 'ownership cannot be proved' in result['why'] and other.exists()
    assert not dispatch.ticket().done


@pytest.mark.parametrize('conflict', [False, True])
def test_abandoned_cleanup_preserves_failed_candidates_and_pending_cleanup(dispatch, repo, conflict):
    [saved] = worked(dispatch, repo)
    folder = repo / saved['worktree']
    (folder / 'recovery.txt').write_text('Do not discard.\n')
    if conflict:
        (repo / 'feature.txt').write_text('Other committed feature.\n')
        git(repo, 'add', 'feature.txt')
        git(repo, 'commit', '-qm', 'Concurrent feature')
    result = integrate(dispatch, repo, saved)
    assert result['merged'] is not conflict
    assert merge.abandoned(dispatch.store, repo, 0) == []
    assert (folder / 'recovery.txt').read_text() == 'Do not discard.\n'
    assert git(repo, 'rev-parse', saved['branch']) == saved['head']


def test_admitted_resume_without_running_session_preserves_worktree(dispatch, repo, monkeypatch):
    from metaform.modules import dispatch as module
    saved = saved_open(dispatch, repo)
    monkeypatch.setattr(module, 'launches', lambda: [{'project': 'proj', 'work_id': dispatch.id}])
    result = integrate(dispatch, repo, saved)
    assert not result['merged'] and 'admitted agent' in result['why'].lower()
    assert (repo / saved['worktree']).exists() and not dispatch.ticket().done


def test_explicit_stop_is_respected_even_with_a_saved_result(dispatch, repo, monkeypatch):
    from metaform.modules.dispatch import orchestration
    saved = saved_open(dispatch, repo)
    monkeypatch.setattr(orchestration, 'assignment', lambda *args, **kwargs: {'stop': {'reason': 'User stop'}})
    result = integrate(dispatch, repo, saved)
    assert not result['merged'] and 'explicitly stopped' in result['why']
    assert (repo / saved['worktree']).exists() and not dispatch.ticket().done


def test_replaced_candidate_during_verification_is_not_integrated(dispatch, repo, monkeypatch):
    saved = saved_open(dispatch, repo)
    real = merge.tests_pass

    def replace(folder, command):
        with Store('proj', module='dispatch').tables() as tx:
            tx.update('merges', {'work_id': dispatch.id}, {'head': '0' * 40, 'seq': saved['seq'] + 1})
        return real(folder, command)
    monkeypatch.setattr(merge, 'tests_pass', replace)
    result = integrate(dispatch, repo, saved)
    assert not result['merged'] and 'candidate changed' in result['why']
    assert state(dispatch)['head'] == '0' * 40
    assert not dispatch.ticket().done and not (repo / 'feature.txt').exists()


def test_cleanup_recovers_scratch_worktree_after_landed_journal_crash(dispatch, repo, monkeypatch):
    saved = saved_open(dispatch, repo)
    real = merge._dropped

    def crash(project, work_id):
        if state(dispatch)['state'] == merge.MERGED:
            raise RuntimeError('Crash after integration journal')
        return real(project, work_id)
    monkeypatch.setattr(merge, '_dropped', crash)
    with pytest.raises(RuntimeError, match='Crash after integration journal'):
        integrate(dispatch, repo, saved)
    head = git(repo, 'rev-parse', 'HEAD')
    assert merge.merging_folder(repo, dispatch.id).exists() and not dispatch.ticket().done
    monkeypatch.setattr(merge, '_dropped', real)
    result = integrate(dispatch, repo, saved)
    assert result['done'] and result['cleanup']['state'] == 'complete'
    assert not merge.merging_folder(repo, dispatch.id).exists()
    assert not (repo / saved['worktree']).exists()
    assert git(repo, 'rev-parse', 'HEAD') == head


def test_cleanup_failure_records_precise_state_without_repeating_integration(dispatch, repo, monkeypatch):
    from metaform.modules.dispatch import ticket_merge
    saved = saved_open(dispatch, repo)
    real = ticket_merge.cleanup

    def fail(*args):
        raise OSError('Worktree filesystem is unavailable')
    monkeypatch.setattr(ticket_merge, 'cleanup', fail)
    result = integrate(dispatch, repo, saved)
    assert result['merged'] and not result['done']
    assert 'Worktree filesystem is unavailable' in result['why']
    assert state(dispatch)['evidence']['cleanup'] == result['cleanup']
    head = git(repo, 'rev-parse', 'HEAD')
    monkeypatch.setattr(ticket_merge, 'cleanup', real)
    assert integrate(dispatch, repo, saved)['done']
    assert git(repo, 'rev-parse', 'HEAD') == head
