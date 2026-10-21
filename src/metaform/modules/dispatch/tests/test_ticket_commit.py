"""Ticket commits preserve peer edits and integrate upstream without rewriting history."""
import importlib
import subprocess
import time
from types import SimpleNamespace

import pytest

from metaform.modules.dispatch.tests.test_dispatch import dispatch as dispatch  # noqa: PLC0414 fixture re-export

merge = importlib.import_module("metaform.modules.dispatch.merge")

pytestmark = pytest.mark.kind("simulation")


def git(folder, *args):
    return subprocess.run(['git', *args], cwd=folder, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    folder = tmp_path / 'project'
    folder.mkdir()
    git(folder, 'init', '-q', '-b', 'dev')
    git(folder, 'config', 'user.name', 'Test')
    git(folder, 'config', 'user.email', 'test@example.com')
    for name in ('own.txt', 'peer.txt'):
        (folder / name).write_text('base\n')
    git(folder, 'add', '.')
    git(folder, 'commit', '-qm', 'base')
    return folder


def finish(repo, baseline, *names):
    return merge.complete_ticket(repo, 'ticket-id', 'Feature\n\nMetaform-Ticket: ticket-id',
                                 {name: merge.file_fingerprint(repo, name) for name in names}, baseline)


def test_only_owned_paths_commit_preserving_peer_index(repo):
    (repo / 'peer.txt').write_text('peer staged\n')
    git(repo, 'add', 'peer.txt')
    (repo / 'peer.txt').write_text('peer unstaged\n')
    baseline = merge.capture_state(repo)
    (repo / 'own.txt').write_text('ticket\n')
    (repo / 'scratch.log').write_text('diagnostic\n')
    result = finish(repo, baseline, 'own.txt', 'scratch.log')
    assert result['committed'], result
    assert git(repo, 'show', '--format=', '--name-only', 'HEAD') == 'own.txt'
    assert git(repo, 'show', ':peer.txt') == 'peer staged'
    assert (repo / 'peer.txt').read_text() == 'peer unstaged\n'
    assert git(repo, 'log', '-1', '--format=%B') == 'Feature\n\nMetaform-Ticket: ticket-id'


def test_preexisting_same_file_edits_block_commit(repo):
    (repo / 'own.txt').write_text('earlier writer\n')
    baseline = merge.capture_state(repo)
    (repo / 'own.txt').write_text('earlier writer\nticket\n')
    result = finish(repo, baseline, 'own.txt')
    assert result['committed'] is None
    assert 'Pre-existing' in result['why']
    assert git(repo, 'log', '-1', '--format=%s') == 'base'


def test_later_peer_edit_blocks_commit(repo):
    baseline = merge.capture_state(repo)
    (repo / 'own.txt').write_text('ticket\n')
    owned = {'own.txt': merge.file_fingerprint(repo, 'own.txt')}
    (repo / 'own.txt').write_text('peer replaced ticket\n')
    result = merge.complete_ticket(repo, 'id', 'Title', owned, baseline)
    assert result['committed'] is None
    assert 'changed after' in result['why']


def test_retry_saves_new_owned_artifact_with_unchanged_completion_message(repo):
    baseline = merge.capture_state(repo)
    (repo / 'own.txt').write_text('ticket\n')
    first = finish(repo, baseline, 'own.txt')
    (repo / 'new_test.py').write_text('assert True\n')
    second = finish(repo, baseline, 'own.txt', 'new_test.py')
    assert second['committed'] != first['committed']
    assert not second['why']
    assert git(repo, 'show', 'HEAD:new_test.py') == 'assert True'


def upstream(repo, tmp_path):
    remote = tmp_path / 'remote.git'
    git(tmp_path, 'init', '--bare', '-q', str(remote))
    git(repo, 'remote', 'add', 'origin', str(remote))
    git(repo, 'push', '-qu', 'origin', 'dev')
    peer = tmp_path / 'peer'
    git(tmp_path, 'clone', '-q', '-b', 'dev', str(remote), str(peer))
    git(peer, 'config', 'user.name', 'Peer')
    git(peer, 'config', 'user.email', 'peer@example.com')
    return remote, peer


def test_ordinary_completion_never_pushes_configured_upstream(repo, tmp_path, monkeypatch):
    remote, _ = upstream(repo, tmp_path)
    before = git(remote, 'rev-parse', 'dev')
    baseline = merge.capture_state(repo)
    (repo / 'own.txt').write_text('ticket\n')
    monkeypatch.setattr(merge, 'push_ticket', lambda *_: pytest.fail('Ordinary completion must not push.'))
    result = finish(repo, baseline, 'own.txt')
    assert result['committed'] and not result['why'], result
    assert not result['pushed']
    assert git(remote, 'rev-parse', 'dev') == before


def test_rejected_push_merges_upstream_without_rewriting(repo, tmp_path):
    remote, peer = upstream(repo, tmp_path)
    baseline = merge.capture_state(repo)
    (peer / 'peer.txt').write_text('remote change\n')
    git(peer, 'commit', '-qam', 'peer')
    peer_commit = git(peer, 'rev-parse', 'HEAD')
    git(peer, 'push', '-q')
    (repo / 'own.txt').write_text('ticket\n')
    result = finish(repo, baseline, 'own.txt')
    result.update(merge.push_ticket(repo))  # publishing is explicitly requested
    assert result['pushed'], result
    git(repo, 'merge-base', '--is-ancestor', peer_commit, 'HEAD')
    git(repo, 'merge-base', '--is-ancestor', result['committed'], 'HEAD')
    assert git(remote, 'rev-parse', 'dev') == git(repo, 'rev-parse', 'HEAD')


def test_upstream_conflict_reports_once_without_losing_ticket(repo, tmp_path):
    _, peer = upstream(repo, tmp_path)
    baseline = merge.capture_state(repo)
    (peer / 'own.txt').write_text('peer change\n')
    git(peer, 'commit', '-qam', 'peer')
    git(peer, 'push', '-q')
    (repo / 'own.txt').write_text('ticket\n')
    result = finish(repo, baseline, 'own.txt')
    result.update(merge.push_ticket(repo))  # publishing is explicitly requested
    assert result['committed'] and result['conflict'] and not result['pushed'], result
    assert (repo / 'own.txt').read_text() == 'ticket\n'
    assert merge.capture_state(repo) == {}


def test_rejected_push_merges_beside_unrelated_peer_edits(repo, tmp_path):
    _, peer = upstream(repo, tmp_path)
    (repo / 'local.txt').write_text('base\n')
    git(repo, 'add', 'local.txt')
    git(repo, 'commit', '-qm', 'local file')
    git(repo, 'push', '-q')
    git(peer, 'pull', '--ff-only', '-q')
    (repo / 'local.txt').write_text('uncommitted peer work\n')
    baseline = merge.capture_state(repo)
    (peer / 'peer.txt').write_text('remote change\n')
    git(peer, 'commit', '-qam', 'peer')
    git(peer, 'push', '-q')
    (repo / 'own.txt').write_text('ticket\n')
    result = finish(repo, baseline, 'own.txt')
    result.update(merge.push_ticket(repo))  # publishing is explicitly requested
    assert result['pushed'], result
    assert (repo / 'local.txt').read_text() == 'uncommitted peer work\n'
    assert git(repo, 'show', 'HEAD:local.txt') == 'base'


def test_ticket_subject_uses_stored_display_title():
    store = SimpleNamespace(numbers_of=lambda _kind, _ids: {'id': ('code.feature#7', 'Feature title', None)})
    record = SimpleNamespace(id='id', address='code.feature', receiver_address=None, provider_address=None,
                             task='Long assignment body', note=None, condition='')
    assert merge.ticket_title(store, record) == 'code.feature#7 Feature title'


def test_retry_recovers_committed_ticket_then_pushes_when_remote_returns(repo, tmp_path):
    remote, _ = upstream(repo, tmp_path)
    baseline = merge.capture_state(repo)
    (repo / 'own.txt').write_text('ticket\n')
    files = {'own.txt': merge.file_fingerprint(repo, 'own.txt')}
    unavailable = tmp_path / 'unavailable.git'
    remote.rename(unavailable)
    message = 'Feature title\n\nMetaform-Ticket: recover-id'
    first = merge.complete_ticket(repo, 'recover-id', message, files, baseline)
    assert first['committed'] and not first['pushed'] and not first['why'], first
    unavailable.rename(remote)
    second = merge.complete_ticket(repo, 'recover-id', message, files, None)
    assert second['committed'] == first['committed'] and not second['pushed'], second
    assert merge.push_ticket(repo)['pushed']
    assert git(repo, 'rev-list', '--count', 'HEAD') == '2'
    assert git(remote, 'rev-parse', 'dev') == first['committed']


def test_worktree_push_journal_recovers_crash_and_allows_explicit_retry(dispatch, tmp_path):
    from metaform.data import Store
    from metaform.module import context

    folder = dispatch.folder
    git(folder, 'init', '-q', '-b', 'dev')
    git(folder, 'config', 'user.name', 'Test')
    git(folder, 'config', 'user.email', 'test@example.com')
    (folder / 'own.txt').write_text('ticket\n')
    git(folder, 'add', 'own.txt')
    git(folder, 'commit', '-qm', 'ticket')
    remote, _ = upstream(folder, tmp_path)
    own = Store(dispatch.store.project_id, module='dispatch')
    with own.tables() as tx:
        tx.insert('merges', {'work_id': dispatch.id, 'branch': 'already-removed', 'worktree': 'already-removed',
                            'state': merge.MERGED, 'reason': merge.PUSH_PENDING, 'ready': time.time(),
                            'deadline': time.time(), 'seq': time.time_ns()})
    assert merge.due(dispatch.store) == [], 'Publishing retries require an explicit request.'
    unavailable = tmp_path / 'unavailable.git'
    remote.rename(unavailable)
    ctx = context('dispatch', folder, project='proj')
    failed = merge.merge_due(ctx, dispatch.store, dispatch.id, publish=True)
    assert failed['merged'] and failed['why'] and not failed['pushed'], failed
    assert merge.due(dispatch.store) == [], 'Transport failures require explicit retry, preventing event loops.'
    unavailable.rename(remote)
    retried = merge.merge_due(ctx, dispatch.store, dispatch.id, publish=True)
    assert retried['merged'] and retried['pushed'], retried
    assert git(folder, 'rev-list', '--count', 'HEAD') == '1'


@pytest.mark.parametrize('later_peer_stage', [False, True])
def test_crash_before_index_reset_preserves_peer_staging(repo, monkeypatch, later_peer_stage):
    (repo / 'peer.txt').write_text('peer staged\n')
    git(repo, 'add', 'peer.txt')
    baseline = merge.capture_state(repo)
    (repo / 'own.txt').write_text('ticket\n')
    files = {'own.txt': merge.file_fingerprint(repo, 'own.txt')}
    real_git = merge.git

    def crash_before_reset(folder, *words, **kwargs):
        if words and words[0] == 'reset':
            raise SystemExit('crash before index refresh')
        return real_git(folder, *words, **kwargs)

    monkeypatch.setattr(merge, 'git', crash_before_reset)
    with pytest.raises(SystemExit, match='crash before index refresh'):
        merge.complete_ticket(repo, 'crash-id', 'Feature\n\nMetaform-Ticket: crash-id', files, baseline)
    monkeypatch.setattr(merge, 'git', real_git)
    assert git(repo, 'show', ':own.txt') == 'base'
    if later_peer_stage:
        (repo / 'own.txt').write_text('later peer stage\n')
        git(repo, 'add', 'own.txt')
    recovered = merge.complete_ticket(repo, 'crash-id', 'Feature\n\nMetaform-Ticket: crash-id', files, None)
    assert recovered['committed'], recovered
    assert git(repo, 'show', ':peer.txt') == 'peer staged'
    assert git(repo, 'show', ':own.txt') == ('later peer stage' if later_peer_stage else 'ticket')
    assert git(repo, 'rev-list', '--count', 'HEAD') == '2'


def test_rejected_push_never_merges_peer_staging_into_history(repo, tmp_path):
    _, peer = upstream(repo, tmp_path)
    (repo / 'peer.txt').write_text('private peer stage\n')
    git(repo, 'add', 'peer.txt')
    baseline = merge.capture_state(repo)
    (peer / 'remote.txt').write_text('remote feature\n')
    git(peer, 'add', 'remote.txt')
    git(peer, 'commit', '-qm', 'remote feature')
    git(peer, 'push', '-q')
    (repo / 'own.txt').write_text('ticket\n')
    result = finish(repo, baseline, 'own.txt')
    result.update(merge.push_ticket(repo))  # publishing is explicitly requested
    assert result['committed'], result
    assert git(repo, 'show', 'HEAD:peer.txt') == 'base'
    assert git(repo, 'show', ':peer.txt') == 'private peer stage'
    assert (repo / 'peer.txt').read_text() == 'private peer stage\n'


def test_capture_state_detects_rewrites_of_already_dirty_files(repo):
    (repo / 'own.txt').write_text('first edit\n')
    before = merge.capture_state(repo)
    (repo / 'own.txt').write_text('second edit\n')
    after = merge.capture_state(repo)
    assert before.keys() == after.keys()
    assert before['own.txt'] != after['own.txt']
