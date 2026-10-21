"""Local integration preserves working files and staged content independently."""
import importlib
import os
import subprocess

import pytest

from metaform.modules.dispatch.tests.test_dispatch import dispatch as dispatch  # noqa: PLC0414
from metaform.modules.dispatch.tests.test_merge import git
from metaform.modules.dispatch.tests.test_merge import repo as repo  # noqa: PLC0414

merge = importlib.import_module('metaform.modules.dispatch.merge')
pytestmark = pytest.mark.kind('simulation')


def index_bytes(folder, path, stage=0):
    result = subprocess.run(['git', 'show', f':{stage}:{path}'], cwd=folder, capture_output=True, check=False)
    return result.stdout if result.returncode == 0 else None


def candidate(repo, base, incoming):
    for path, content in base.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_bytes(content)
    git(repo, 'add', '-A')
    git(repo, 'commit', '-qm', 'landing base')
    before = git(repo, 'rev-parse', 'HEAD')
    tree = merge.worktree_for(repo, 'dirty-landing')
    assert tree is not None
    for path, content in incoming.items():
        if content is None:
            (tree / path).unlink()
        else:
            (tree / path).parent.mkdir(parents=True, exist_ok=True)
            (tree / path).write_bytes(content)
    git(tree, 'add', '-A')
    git(tree, 'commit', '-qm', 'incoming feature')
    return before, git(tree, 'rev-parse', 'HEAD')


def test_landing_preserves_local_symlink_and_its_outside_target(repo, tmp_path):
    before, landed = candidate(repo, {'owned.txt': b'base\n'}, {'owned.txt': b'landed\n'})
    outside = tmp_path / 'outside.txt'
    outside.write_bytes(b'base\n')
    local = repo / 'owned.txt'
    local.unlink()
    try:
        local.symlink_to(outside)
    except OSError as error:
        pytest.skip(f'Symlinks unavailable: {error}')

    passed, report = merge.advance(repo, landed, before)

    assert local.is_symlink() and os.readlink(local) == str(outside)
    assert outside.read_bytes() == b'base\n'
    assert index_bytes(repo, 'owned.txt') == b'base\n'
    assert passed and 'owned.txt' in report
    assert git(repo, 'rev-parse', 'HEAD') == landed


def test_landing_preserves_empty_staged_blob_with_restored_working_file(repo):
    before, landed = candidate(repo, {'owned.txt': b'base\n'}, {'owned.txt': b'landed\n'})
    local = repo / 'owned.txt'
    local.write_bytes(b'')
    git(repo, 'add', 'owned.txt')
    local.write_bytes(b'base\n')

    passed, report = merge.advance(repo, landed, before)

    assert index_bytes(repo, 'owned.txt') == b''
    assert local.read_bytes() == b'base\n'
    assert passed and 'owned.txt' in report


def test_landing_preserves_symlinked_parent_and_its_outside_files(repo, tmp_path):
    path = 'nested/owned.txt'
    before, landed = candidate(repo, {path: b'base\n'}, {path: b'landed\n'})
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'owned.txt').write_bytes(b'base\n')
    (repo / path).unlink()
    (repo / 'nested').rmdir()
    try:
        (repo / 'nested').symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f'Symlinks unavailable: {error}')

    passed, report = merge.advance(repo, landed, before)

    assert (outside / 'owned.txt').read_bytes() == b'base\n'
    assert (repo / 'nested').is_symlink()
    assert os.readlink(repo / 'nested') == str(outside)
    assert index_bytes(repo, path) == b'base\n'
    assert passed and path in report


def test_landing_preserves_unmerged_index_stages_and_working_contents(repo, tmp_path):
    before, landed = candidate(repo, {'owned.txt': b'base\n'}, {'owned.txt': b'landed\n'})
    ours_file = tmp_path / 'ours.txt'
    ours_file.write_bytes(b'local stage\n')
    ours = git(repo, 'hash-object', '-w', str(ours_file))
    base = git(repo, 'rev-parse', f'{before}:owned.txt')
    theirs = git(repo, 'rev-parse', f'{landed}:owned.txt')
    git(repo, 'update-index', '--force-remove', '--', 'owned.txt')
    entries = f'100644 {base} 1\towned.txt\n100644 {ours} 2\towned.txt\n100644 {theirs} 3\towned.txt\n'
    subprocess.run(['git', 'update-index', '--index-info'], cwd=repo, input=entries.encode(), check=True)
    working = b'<<<<<<< local\nlocal stage\n=======\nlanded\n>>>>>>> incoming\n'
    (repo / 'owned.txt').write_bytes(working)
    index_before = git(repo, 'ls-files', '--stage', '-z')

    passed, report = merge.advance(repo, landed, before)

    assert (repo / 'owned.txt').read_bytes() == working
    assert git(repo, 'ls-files', '--stage', '-z') == index_before
    assert index_bytes(repo, 'owned.txt', 1) == b'base\n'
    assert index_bytes(repo, 'owned.txt', 2) == b'local stage\n'
    assert index_bytes(repo, 'owned.txt', 3) == b'landed\n'
    assert passed and 'owned.txt' in report


def test_landing_preserves_staged_deletion_with_retained_working_file(repo):
    before, landed = candidate(repo, {'owned.txt': b'base\n'}, {'owned.txt': b'landed\n'})
    git(repo, 'rm', '--cached', '-q', 'owned.txt')

    passed, report = merge.advance(repo, landed, before)

    assert index_bytes(repo, 'owned.txt') is None
    assert (repo / 'owned.txt').read_bytes() == b'base\n'
    assert passed and 'owned.txt' in report


def test_incoming_addition_preserves_different_staged_content(repo):
    before, landed = candidate(repo, {'other.txt': b'base\n'}, {'added.txt': b'landed\n'})
    local = repo / 'added.txt'
    local.write_bytes(b'peer staged\n')
    git(repo, 'add', 'added.txt')
    local.write_bytes(b'landed\n')

    passed, report = merge.advance(repo, landed, before)

    assert index_bytes(repo, 'added.txt') == b'peer staged\n'
    assert local.read_bytes() == b'landed\n'
    assert passed and 'added.txt' in report


def test_incoming_addition_preserves_ignored_untracked_local_file(repo):
    before, landed = candidate(repo, {'other.txt': b'base\n'}, {'owned.txt': b'landed\n'})
    with (repo / '.git' / 'info' / 'exclude').open('a') as exclude:
        exclude.write('\nowned.txt\n')
    (repo / 'owned.txt').write_bytes(b'ignored peer draft\n')
    assert git(repo, 'status', '--porcelain', '--', 'owned.txt') == ''

    passed, report = merge.advance(repo, landed, before)

    assert (repo / 'owned.txt').read_bytes() == b'ignored peer draft\n'
    assert index_bytes(repo, 'owned.txt') is None
    assert passed and 'owned.txt' in report
    assert git(repo, 'rev-parse', 'HEAD') == landed
    assert git(repo, 'show', 'HEAD:owned.txt') == 'landed'


def test_later_checkout_failure_restores_earlier_clean_paths(repo, monkeypatch):
    original = {'a.txt': b'first base\n', 'b.txt': b'second base\n'}
    before, landed = candidate(repo, original, {'a.txt': b'first landed\n', 'b.txt': b'second landed\n'})
    real = merge.git

    def fail_later_checkout(folder, *words, **kwargs):
        if words == ('checkout', landed, '--', 'b.txt'):
            return subprocess.CompletedProcess(['git', *words], 1, '', 'injected checkout failure')
        return real(folder, *words, **kwargs)

    monkeypatch.setattr(merge, 'git', fail_later_checkout)
    passed, report = merge.advance(repo, landed, before)

    assert not passed and 'injected checkout failure' in report
    assert git(repo, 'rev-parse', 'HEAD') == before
    for path, content in original.items():
        assert (repo / path).read_bytes() == content
        assert index_bytes(repo, path) == content


@pytest.mark.parametrize('path', ['owned.txt', 'owned file.txt'])
def test_nonoverlapping_staged_and_unstaged_edits_keep_separate_contents(repo, path):
    base = b'first\n\n\nmiddle\n\n\nlast\n'
    incoming = base.replace(b'first', b'landed first')
    staged = base.replace(b'middle', b'staged middle')
    working = staged.replace(b'last', b'unstaged last')
    before, landed = candidate(repo, {path: base}, {path: incoming})
    local = repo / path
    local.write_bytes(staged)
    git(repo, 'add', path)
    local.write_bytes(working)

    passed, report = merge.advance(repo, landed, before)

    assert passed and not report
    assert git(repo, 'rev-parse', 'HEAD') == landed
    assert index_bytes(repo, path) == staged.replace(b'first', b'landed first')
    assert local.read_bytes() == working.replace(b'first', b'landed first')


def test_clean_path_with_spaces_takes_incoming_file_and_index_contents(repo):
    path = 'owned file.txt'
    before, landed = candidate(repo, {path: b'base\n'}, {path: b'landed\n'})

    passed, report = merge.advance(repo, landed, before)

    assert passed and not report
    assert (repo / path).read_bytes() == b'landed\n'
    assert index_bytes(repo, path) == b'landed\n'
    assert git(repo, 'rev-parse', 'HEAD') == landed


@pytest.mark.skipif(os.name == 'nt', reason='Executable file modes require POSIX chmod semantics.')
def test_staged_executable_mode_survives_nonoverlapping_incoming_content(repo):
    base = b'first\n\n\nmiddle\n\n\nlast\n'
    staged = base.replace(b'middle', b'staged middle')
    before, landed = candidate(repo, {'owned.txt': base}, {'owned.txt': base.replace(b'first', b'landed first')})
    local = repo / 'owned.txt'
    local.write_bytes(staged)
    local.chmod(local.stat().st_mode | 0o111)
    git(repo, 'add', 'owned.txt')

    passed, report = merge.advance(repo, landed, before)

    expected = staged.replace(b'first', b'landed first')
    assert passed and not report
    assert index_bytes(repo, 'owned.txt') == expected
    assert git(repo, 'ls-files', '-s', '--', 'owned.txt').split()[0] == '100755'
    assert local.read_bytes() == expected
    assert local.stat().st_mode & 0o111


@pytest.mark.skipif(os.name == 'nt', reason='Executable file modes require POSIX chmod semantics.')
def test_incoming_executable_mode_keeps_unstaged_peer_content(repo):
    base = b'first\n\n\nmiddle\n\n\nlast\n'
    before, _ = candidate(repo, {'owned.txt': base, 'marker.txt': b'base\n'}, {'marker.txt': b'landed\n'})
    tree = merge.worktree_for(repo, 'dirty-landing')
    incoming = tree / 'owned.txt'
    incoming.chmod(incoming.stat().st_mode | 0o111)
    git(tree, 'add', 'owned.txt')
    git(tree, 'commit', '-qm', 'incoming executable mode')
    landed = git(tree, 'rev-parse', 'HEAD')
    local = repo / 'owned.txt'
    working = base.replace(b'last', b'unstaged last')
    local.write_bytes(working)

    passed, report = merge.advance(repo, landed, before)

    assert passed and not report
    assert index_bytes(repo, 'owned.txt') == base
    assert git(repo, 'ls-files', '-s', '--', 'owned.txt').split()[0] == '100755'
    assert local.read_bytes() == working
    assert local.stat().st_mode & 0o111


def test_compare_and_swap_failure_restores_file_and_index_contents(repo, monkeypatch):
    base = b'first\n\n\nmiddle\n\n\nlast\n'
    staged = base.replace(b'middle', b'staged middle')
    working = staged.replace(b'last', b'unstaged last')
    before, landed = candidate(repo, {'a.txt': b'clean base\n', 'owned.txt': base},
                               {'a.txt': b'clean landed\n', 'owned.txt': base.replace(b'first', b'landed first')})
    local = repo / 'owned.txt'
    local.write_bytes(staged)
    git(repo, 'add', 'owned.txt')
    local.write_bytes(working)
    real = merge.git

    def fail_compare_and_swap(folder, *words, **kwargs):
        if words == ('update-ref', 'refs/heads/dev', landed, before):
            return subprocess.CompletedProcess(['git', *words], 1, '', 'injected compare-and-swap failure')
        return real(folder, *words, **kwargs)

    monkeypatch.setattr(merge, 'git', fail_compare_and_swap)
    passed, report = merge.advance(repo, landed, before)

    assert not passed and 'injected compare-and-swap failure' in report
    assert git(repo, 'rev-parse', 'HEAD') == before
    assert (repo / 'a.txt').read_bytes() == b'clean base\n'
    assert index_bytes(repo, 'a.txt') == b'clean base\n'
    assert local.read_bytes() == working
    assert index_bytes(repo, 'owned.txt') == staged
