"""Ticket completion saves verified feature commits without publishing shared branches."""
import importlib
import subprocess
import time
from pathlib import Path

import pytest

from metaform.data import Store
from metaform.module import context
from metaform.modules.dispatch.tests.test_dispatch import dispatch as dispatch  # noqa: PLC0414
from metaform.modules.dispatch.tests.test_merge import repo as repo  # noqa: PLC0414

merge = importlib.import_module('metaform.modules.dispatch.merge')
pytestmark = pytest.mark.kind('simulation')


def git(folder, *args):
    return subprocess.run(['git', *args], cwd=folder, check=True, text=True, capture_output=True).stdout.strip()


@pytest.mark.parametrize('remote_configured', [False, True])
@pytest.mark.parametrize('development_branch', ['dev', 'main'])
def test_done_saves_one_ticket_commit_without_publishing_beside_peer_staging(dispatch, repo, remote_configured,
                                                                         development_branch, monkeypatch):
    if development_branch == 'main':
        git(repo, 'branch', '-m', 'main')
        git(repo, 'push', '-qu', 'origin', 'main')
    remote = Path(git(repo, 'remote', 'get-url', 'origin'))
    before = git(repo, 'rev-parse', 'HEAD')
    remote_before = git(remote, 'rev-parse', development_branch)
    if not remote_configured:
        git(repo, 'remote', 'remove', 'origin')
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    from metaform.modules.dispatch import activation

    def publish_forbidden(*args, **kwargs):
        pytest.fail('Ticket completion must save without publishing or activation.')

    monkeypatch.setattr(merge, 'push_ticket', publish_forbidden)
    monkeypatch.setattr(activation, 'delivered', publish_forbidden)
    tree = merge.worktree_for(repo, dispatch.id)
    assert tree is not None
    (tree / 'feature.txt').write_text('ticket feature\n')
    git(tree, 'add', 'feature.txt')
    git(tree, 'commit', '-qm', 'ticket step')
    tip = git(tree, 'rev-parse', 'HEAD')
    (repo / 'README.md').write_text('staged peer\n')
    git(repo, 'add', 'README.md')
    (repo / 'README.md').write_text('unstaged peer\n')
    dispatch.store.finish_work(dispatch.id, 'Feature verified')
    result = merge.finished(context('dispatch', repo, project='proj'), dispatch.store,
                            dispatch.store.ticket(dispatch.id).work, tree)
    assert result['state'] == 'committed' and not result['reason'], result
    assert result['head'] == git(tree, 'rev-parse', 'HEAD')
    assert result['evidence']['verification']['passed'] is True
    assert result['evidence']['verification']['command'] == 'true'
    assert result['evidence']['artifacts'] == ['feature.txt']
    assert dispatch.store.complete_delivery(dispatch.id).done
    assert git(remote, 'rev-parse', development_branch) == remote_before
    assert git(repo, 'rev-parse', 'HEAD') == before
    assert git(repo, 'rev-list', '--count', 'HEAD') == '1'
    assert git(tree, 'diff', '--name-only', before, 'HEAD') == 'feature.txt'
    assert git(repo, 'show', ':README.md') == 'staged peer'
    assert (repo / 'README.md').read_text() == 'unstaged peer\n'
    assert not (repo / 'feature.txt').exists()
    assert git(tree, 'merge-base', '--is-ancestor', tip, 'HEAD') == ''
    delivered = git(tree, 'rev-parse', 'HEAD')
    merge.finished(context('dispatch', repo, project='proj'), dispatch.store,
                   dispatch.store.ticket(dispatch.id).work, tree)
    assert git(tree, 'rev-parse', 'HEAD') == delivered, 'Repeated completion creates no second feature commit'
    assert git(repo, 'rev-parse', 'HEAD') == before
    assert not dispatch.store.work(open=True, limit=0).results


def test_recovery_excludes_snapshot_and_never_commits_later_worktree_edits(dispatch, repo, tmp_path):
    tree = merge.worktree_for(repo, dispatch.id)
    assert tree is not None
    (tree / 'snapshot.txt').write_text('peer snapshot\n')
    git(tree, 'add', '.')
    git(tree, 'commit', '-qm', 'legacy snapshot')
    start = git(tree, 'rev-parse', 'HEAD')
    git(repo, 'update-ref', f'{merge.SNAPSHOTS}/{merge.branch_of(dispatch.id)}', start)
    (tree / 'feature.txt').write_text('ticket feature\n')
    git(tree, 'add', 'feature.txt')
    git(tree, 'commit', '-qm', 'ticket step')
    (tree / 'draft.txt').write_text('later peer draft\n')
    dispatch.store.finish_work(dispatch.id, 'Feature verified')
    own = Store(dispatch.store.project_id, module='dispatch')
    with own.tables() as tx:
        tx.insert('merges', {'work_id': dispatch.id, 'branch': merge.branch_of(dispatch.id),
                            'worktree': str(tree), 'state': merge.READY, 'reason': '',
                            'ready': time.time(), 'deadline': time.time(), 'seq': time.time_ns()})
    result = merge.merge_due(context('dispatch', repo, project='proj'), dispatch.store, dispatch.id)
    assert result['merged'] and result['pushed'], result
    assert not (repo / 'snapshot.txt').exists()
    assert not (repo / 'draft.txt').exists()
    assert (tree / 'draft.txt').read_text() == 'later peer draft\n'
    assert git(repo, 'show', '--format=', '--name-only', 'HEAD') == 'feature.txt'
    assert git(repo, 'rev-list', '--count', 'HEAD') == '2'


def test_advance_refuses_overlapping_uncommitted_files(repo):
    before = git(repo, 'rev-parse', 'HEAD')
    tree = Path(merge.worktree_for(repo, 'advance-test'))
    (tree / 'README.md').write_text('ticket\n')
    git(tree, 'commit', '-qam', 'ticket')
    (repo / 'README.md').write_text('peer\n')
    passed, reason = merge.advance(repo, git(tree, 'rev-parse', 'HEAD'), before)
    assert not passed and 'README.md' in reason
    assert git(repo, 'rev-parse', 'HEAD') == before
    assert (repo / 'README.md').read_text() == 'peer\n'
