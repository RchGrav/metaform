"""Stable ACP cwd with per-card Git candidates and preserved prior artifacts."""
from __future__ import annotations

import importlib
import subprocess

import pytest

pytestmark = pytest.mark.kind('simulation')
merge = importlib.import_module('metaform.modules.dispatch.merge')

FIRST = 'aaaaaaaaaaaa11111111111111111111'
NEXT = 'bbbbbbbbbbbb22222222222222222222'


def git(folder, *words):
    return subprocess.run(['git', *words], cwd=folder, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def workspace(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    git(project, 'init', '-q', '-b', 'dev')
    git(project, 'config', 'user.email', 'test@example.com')
    git(project, 'config', 'user.name', 'Test')
    (project / 'shared.txt').write_text('initial\n')
    git(project, 'add', '.')
    git(project, 'commit', '-qm', 'Initial state')
    cwd = merge.worktree_for(project, FIRST)
    (cwd / 'first.txt').write_text('First candidate\n')
    git(cwd, 'add', '.')
    git(cwd, 'commit', '-qm', 'First candidate')
    return project, cwd, git(cwd, 'rev-parse', 'HEAD')


def test_integrated_source_uses_current_dev_without_changing_cwd_or_shared_checkout(workspace):
    project, cwd, source = workspace
    git(project, 'merge', '--ff-only', merge.branch_of(FIRST))
    (project / 'shared.txt').write_text('Parallel change after first integration\n')
    git(project, 'commit', '-qam', 'Parallel contribution')
    (project / 'uncommitted.txt').write_text('Shared user data\n')
    before = git(project, 'status', '--porcelain'), git(project, 'rev-parse', 'HEAD')
    prepared = merge.episode_workspace(project, NEXT, cwd, FIRST)
    assert prepared['cwd'] == str(cwd.resolve())
    assert prepared['baseline'] == before[1]
    assert prepared['source_candidate'] == source and prepared['source_branch'] == merge.branch_of(FIRST)
    assert git(project, 'rev-parse', merge.branch_of(FIRST)) == source
    assert git(cwd, 'branch', '--show-current') == merge.branch_of(NEXT)
    assert (cwd / 'shared.txt').read_text() == 'Parallel change after first integration\n'
    assert not (cwd / 'uncommitted.txt').exists()
    assert (git(project, 'status', '--porcelain'), git(project, 'rev-parse', 'HEAD')) == before
    (cwd / 'next.txt').write_text('Only the next card\n')
    git(cwd, 'add', '.')
    git(cwd, 'commit', '-qm', 'Next candidate')
    assert git(project, 'diff', '--name-only', prepared['baseline'], merge.branch_of(NEXT)) == 'next.txt'


def test_unintegrated_source_is_retained_as_an_explicit_candidate_and_per_card_baseline(workspace):
    project, cwd, source = workspace
    root = git(project, 'rev-parse', 'HEAD')
    prepared = merge.episode_workspace(project, NEXT, cwd, FIRST)
    assert prepared['source_candidate'] == prepared['baseline'] == source
    assert merge.snapshot_of(project, merge.branch_of(NEXT)) == source
    assert git(project, 'rev-parse', 'HEAD') == root
    assert (cwd / 'first.txt').read_text() == 'First candidate\n'
    (cwd / 'next.txt').write_text('Dependent continuation\n')
    git(cwd, 'add', '.')
    git(cwd, 'commit', '-qm', 'Next candidate')
    assert git(project, 'diff', '--name-only', prepared['baseline'], merge.branch_of(NEXT)) == 'next.txt'
    # Source integration remains independently addressable and precedes the dependent candidate.
    git(project, 'merge', '--ff-only', prepared['source_branch'])
    git(project, 'merge', '--ff-only', merge.branch_of(NEXT))
    assert (project / 'first.txt').exists() and (project / 'next.txt').exists()


@pytest.mark.parametrize('path', ['shared.txt', 'untracked.txt'])
def test_dirty_workspace_remains_untouched_for_fresh_context(workspace, path):
    project, cwd, source = workspace
    (cwd / path).write_text('Preserve this local work\n')
    before = git(cwd, 'status', '--porcelain')
    assert merge.episode_workspace(project, NEXT, cwd, FIRST) is None
    assert git(cwd, 'branch', '--show-current') == merge.branch_of(FIRST)
    assert git(cwd, 'rev-parse', 'HEAD') == source
    assert (cwd / path).read_text() == 'Preserve this local work\n'
    assert git(cwd, 'status', '--porcelain') == before


def test_target_branch_checked_out_elsewhere_is_not_taken_over(workspace):
    project, cwd, source = workspace
    other = merge.worktree_for(project, NEXT)
    assert merge.episode_workspace(project, NEXT, cwd, FIRST) is None
    assert git(cwd, 'rev-parse', 'HEAD') == source
    assert git(other, 'branch', '--show-current') == merge.branch_of(NEXT)
    assert git(cwd, 'branch', '--show-current') == merge.branch_of(FIRST)


def test_retry_keeps_its_original_baseline_and_frozen_source(workspace):
    project, cwd, source = workspace
    prepared = merge.episode_workspace(project, NEXT, cwd, FIRST)
    (cwd / 'next.txt').write_text('Partial next contribution\n')
    git(cwd, 'add', '.')
    git(cwd, 'commit', '-qm', 'Next partial candidate')
    assert merge.episode_workspace(project, NEXT, cwd, FIRST) == prepared
    assert merge.snapshot_of(project, merge.branch_of(NEXT)) == source
    assert git(project, 'rev-parse', merge.branch_of(FIRST)) == source


def test_reopening_the_first_card_gets_its_own_branch_without_displacing_the_episode(workspace):
    project, cwd, source = workspace
    merge.episode_workspace(project, NEXT, cwd, FIRST)
    reopened = merge.worktree_for(project, FIRST)
    assert reopened != cwd and reopened.is_dir()
    assert git(reopened, 'branch', '--show-current') == merge.branch_of(FIRST)
    assert git(reopened, 'rev-parse', 'HEAD') == source
    assert git(cwd, 'branch', '--show-current') == merge.branch_of(NEXT)
    assert merge.worktree_for(project, NEXT) == cwd


def test_ignored_local_data_is_not_overwritten_when_the_target_tracks_its_path(workspace):
    project, cwd, _ = workspace
    (cwd / '.gitignore').write_text('private.txt\n')
    git(cwd, 'add', '.')
    git(cwd, 'commit', '-qm', 'Ignore private data')
    git(project, 'merge', '--ff-only', merge.branch_of(FIRST))
    (project / 'private.txt').write_text('Tracked new project content\n')
    git(project, 'add', '-f', 'private.txt')
    git(project, 'commit', '-qm', 'Track new project path')
    (cwd / 'private.txt').write_text('Private local data\n')
    assert merge.episode_workspace(project, NEXT, cwd, FIRST) is None
    assert (cwd / 'private.txt').read_text() == 'Private local data\n'
    assert git(cwd, 'branch', '--show-current') == merge.branch_of(FIRST)


def test_saved_delivery_contains_only_the_current_card_delta(workspace, store, run):
    from metaform.data import Node
    from tests.storekit import small_map

    run('enable', 'dispatch', cwd=store.project().path)
    small_map(store)
    project, cwd, source = workspace
    work = store.add_work(Node('element', 'code.timer.kitchen'), None, task='Continue from the source candidate.')
    prepared = merge.episode_workspace(project, work.id, cwd, FIRST)
    (cwd / 'next.txt').write_text('Current card evidence\n')
    git(cwd, 'add', '.')
    git(cwd, 'commit', '-qm', f'Current candidate\n\nMetaform-Ticket: {work.id}')
    record = store.finish_work(work.id, 'Current contribution completed.', 'Save the isolated candidate delta.')
    candidate = git(cwd, 'rev-parse', 'HEAD')
    saved = merge._saved(store, record, cwd, prepared['branch'], candidate,
                         {'passed': True, 'output': '', 'source': 'worker'}, prepared['baseline'])
    assert saved['evidence']['artifacts'] == ['next.txt']
    assert saved['head'] == candidate and saved['branch'] == merge.branch_of(work.id)
    assert git(project, 'rev-parse', merge.branch_of(FIRST)) == prepared['source_candidate'] == source


def test_abandoned_first_card_does_not_delete_the_active_episode_workspace(workspace, store, run, monkeypatch):
    from types import SimpleNamespace

    run('enable', 'dispatch', cwd=store.project().path)
    project, cwd, source = workspace
    merge.episode_workspace(project, NEXT, cwd, FIRST)
    monkeypatch.setattr(store, 'work', lambda **kwargs: SimpleNamespace(results=[SimpleNamespace(id=FIRST)]))
    assert merge.abandoned(store, project, 0) == []
    assert cwd.is_dir() and git(cwd, 'branch', '--show-current') == merge.branch_of(NEXT)
    assert git(project, 'rev-parse', merge.branch_of(FIRST)) == source
