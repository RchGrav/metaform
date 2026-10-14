"""History: the artifact boundary, origins and their identity, variants and reconstruction, PROJ-010 to PROJ-024."""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

import pytest

from metaform import home as metaform_home
from metaform.data import Store

pytestmark = pytest.mark.kind('fixture')

POSIX = os.name != 'nt'


def units(project_id):
    """Where a project's origin units are: its own folder in the home, PROJ-026."""
    return metaform_home.project_folder(project_id) / 'origins'


def git(folder, *args):
    return subprocess.run(['git', '-C', str(folder), *args], check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path, home):
    """A repository with text, a binary, an executable script and an ignored build folder, registered as `app`."""
    folder = tmp_path / 'app'
    folder.mkdir()
    git(folder, 'init', '-q', '-b', 'main')
    git(folder, 'config', 'user.email', 'test@example.com')
    git(folder, 'config', 'user.name', 'Test')
    git(folder, 'config', 'core.autocrlf', 'false')
    (folder / 'src').mkdir()
    (folder / 'src' / 'main.py').write_text('print("hello")\n', encoding='utf-8')
    (folder / 'logo.png').write_bytes(bytes(range(256)) * 4)
    (folder / 'run.sh').write_text('#!/bin/sh\necho run\n', encoding='utf-8')
    if POSIX:
        (folder / 'run.sh').chmod(0o755)
    (folder / '.gitignore').write_text('build/\n', encoding='utf-8')
    (folder / 'build').mkdir()
    (folder / 'build' / 'out.bin').write_bytes(b'built')
    git(folder, 'add', '-A')
    git(folder, 'update-index', '--chmod=+x', 'run.sh')
    git(folder, 'commit', '-q', '-m', 'start')
    metaform_home.add_project('app', folder)
    return folder


@pytest.fixture
def photos(tmp_path, home):
    """A plain folder, outside any repository, registered as `photos`."""
    folder = tmp_path / 'photos'
    (folder / 'kitchen').mkdir(parents=True)
    (folder / 'kitchen' / 'one.jpg').write_bytes(b'\xff\xd8 one')
    (folder / 'notes.txt').write_text('two photos\n', encoding='utf-8')
    metaform_home.add_project('photos', folder)
    return folder


def manifest(files: dict[str, tuple[bytes, str]]) -> bytes:
    """PROJ-013's manifest, built here from the files themselves: path, SHA-256 and mode, sorted by path."""
    return ''.join(f'{path}\t{hashlib.sha256(data).hexdigest()}\t{mode}\n'
                   for path, (data, mode) in sorted(files.items())).encode('utf-8')


def committed(repo: Path) -> dict[str, tuple[bytes, str]]:
    return {'.gitignore': (b'build/\n', '644'), 'logo.png': (bytes(range(256)) * 4, '644'),
            'run.sh': (b'#!/bin/sh\necho run\n', '755'), 'src/main.py': (b'print("hello")\n', '644')}


@pytest.mark.req('PROJ-011')
def test_the_boundary_is_what_git_tracks_or_would_track_with_paths_in_slashes(repo):
    from metaform.data import history
    (repo / 'src' / 'new.py').write_text('x = 1\n', encoding='utf-8')
    found = {entry.path: entry.mode for entry in history.boundary(repo)}
    # A tracked file's mode is git's, so the executable bit holds on Windows too; an untracked file's is its own.
    assert found == {'.gitignore': '644', 'logo.png': '644', 'run.sh': '755', 'src/main.py': '644',
                     'src/new.py': '644'}


@pytest.mark.req('PROJ-011')
def test_outside_a_repository_the_boundary_is_every_file_but_a_git_folder(photos):
    from metaform.data import history
    (photos / '.git').mkdir()
    (photos / '.git' / 'config').write_text('x', encoding='utf-8')
    assert sorted(entry.path for entry in history.boundary(photos)) == ['kitchen/one.jpg', 'notes.txt']


@pytest.mark.req('PROJ-012')
@pytest.mark.req('PROJ-013')
@pytest.mark.req('PROJ-026')
def test_a_repository_origin_records_its_commit_and_a_digest_of_the_committed_files(repo, home):
    origin = Store('app').add_origin()
    assert origin.kind == 'repo' and origin.commit_id == git(repo, 'rev-parse', 'HEAD').strip()
    files = committed(repo)
    digest = hashlib.sha256(manifest(files)).hexdigest()
    assert origin.origin_sha256 == digest
    assert re.fullmatch(r'[0-9a-f]{64}', origin.mform_sha_id) and origin.mform_sha_id == digest[:60] + '0000'
    assert re.fullmatch(r'[0-9a-f]{16}', origin.mform_id) and origin.mform_id == digest[:12] + '0000'
    assert origin.suffix == '0000' and origin.source_path == str(repo)
    assert on_disk(units('app') / origin.mform_sha_id / 'origin') == {
        path: data for path, (data, _) in files.items()}


@pytest.mark.req('PROJ-012')
@pytest.mark.req('PROJ-013')
def test_a_folder_origin_copies_the_folder_and_later_changes_leave_the_copy(photos, home):
    origin = Store('photos').add_origin()
    assert origin.kind == 'folder' and origin.commit_id is None
    copy = units('photos') / origin.mform_sha_id / 'origin'
    assert sorted(str(path.relative_to(copy).as_posix()) for path in copy.rglob('*') if path.is_file()) == [
        'kitchen/one.jpg', 'notes.txt']
    (photos / 'notes.txt').write_text('changed\n', encoding='utf-8')
    assert (copy / 'notes.txt').read_text(encoding='utf-8') == 'two photos\n'
    expected = {'kitchen/one.jpg': (b'\xff\xd8 one', '644'), 'notes.txt': (b'two photos\n', '644')}
    assert origin.origin_sha256 == hashlib.sha256(manifest(expected)).hexdigest()


@pytest.mark.req('PROJ-013')
@pytest.mark.req('PROJ-026')
def test_the_same_content_in_another_project_is_its_own_first_instance_in_its_own_folder(photos, home, tmp_path):
    """Two projects are two paths, so two folders, and their origins cannot conflict. The next
    suffix is taken only on a conflict inside one project."""
    import shutil
    twin = tmp_path / 'twin'
    shutil.copytree(photos, twin)
    metaform_home.add_project('twin', twin)
    first, second = Store('photos').add_origin(), Store('twin').add_origin()
    assert first.origin_sha256 == second.origin_sha256
    assert (first.suffix, second.suffix) == ('0000', '0000')
    assert (units('photos') / first.mform_sha_id).is_dir() and (units('twin') / second.mform_sha_id).is_dir()
    assert [path.name for path in units('photos').iterdir()] == [first.mform_sha_id]


@pytest.mark.req('PROJ-014')
@pytest.mark.req('PROJ-018')
def test_an_origin_is_never_rewritten_and_a_new_baseline_is_a_new_unit(repo, home, tmp_path):
    store = Store('app')
    first = store.add_origin()
    worker = tmp_path / 'worker'
    git(repo, 'worktree', 'add', '-q', str(worker))
    (worker / 'logo.png').write_bytes(b'a variant of the first origin')
    early = store.add_variant(worker)
    unit = units('app') / first.mform_sha_id
    kept = {path.relative_to(unit).as_posix(): path.read_bytes() for path in unit.rglob('*') if path.is_file()}
    again = store.add_origin()
    assert again.mform_sha_id == first.mform_sha_id and [origin.mform_id for origin in store.origins()] == [
        first.mform_id]
    (repo / 'src' / 'main.py').write_text('print("hello, again")\n', encoding='utf-8')
    git(repo, 'commit', '-q', '-am', 'second')
    second = store.add_origin()
    assert second.mform_sha_id != first.mform_sha_id and second.commit_id != first.commit_id
    assert [origin.mform_id for origin in store.origins()] == [first.mform_id, second.mform_id]
    assert store.origins()[0].mform_sha_id == first.mform_sha_id and store.origins()[0].variants == 1
    assert {path.relative_to(unit).as_posix(): path.read_bytes() for path in unit.rglob('*') if path.is_file()} == kept
    store.extract([early.variant_id], tmp_path / 'out', origin=first.mform_id)
    assert (tmp_path / 'out' / 'logo.png').read_bytes() == b'a variant of the first origin'
    assert (tmp_path / 'out' / 'src' / 'main.py').read_bytes() == b'print("hello")\n'


@pytest.mark.req('PROJ-012')
@pytest.mark.req('PROJ-017')
def test_a_dirty_working_tree_is_collected_as_the_first_variant(repo):
    # Establish a new baseline after the origin already captured by registration.
    (repo / 'src' / 'main.py').write_text('print("new baseline")\n', encoding='utf-8')
    git(repo, 'commit', '-q', '-am', 'new baseline')
    (repo / 'src' / 'main.py').write_text('print("uncommitted")\n', encoding='utf-8')
    store = Store('app')
    origin = store.add_origin()
    assert origin.commit_id == git(repo, 'rev-parse', 'HEAD').strip()
    variants = store.variants(origin=origin.mform_id)
    assert [variant.variant_id for variant in variants] == ['v000001']
    assert [(change.path, change.change) for change in variants[0].files] == [('src/main.py', 'modified')]


def on_disk(folder: Path) -> dict[str, bytes]:
    return {path.relative_to(folder).as_posix(): path.read_bytes() for path in sorted(folder.rglob('*'))
            if path.is_file() and '.git' not in path.relative_to(folder).parts}


@pytest.fixture
def worktree(repo, tmp_path):
    """A git worktree of the repository at its commit, as a worker would get."""
    folder = tmp_path / 'worker'
    git(repo, 'worktree', 'add', '-q', str(folder))
    return folder


@pytest.mark.req('PROJ-011')
@pytest.mark.req('PROJ-016')
@pytest.mark.req('PROJ-017')
@pytest.mark.req('PROJ-018')
def test_a_worktrees_work_reconstructs_byte_identical_and_nothing_ignored_comes_with_it(repo, worktree, tmp_path):
    store = Store('app')
    store.add_origin()
    (worktree / 'logo.png').write_bytes(bytes(reversed(range(256))) * 4)
    (worktree / 'src' / 'extra.py').write_text('extra = True\n', encoding='utf-8')
    (worktree / 'run.sh').unlink()
    (worktree / 'src' / 'main.py').rename(worktree / 'src' / 'app.py')
    (worktree / 'build').mkdir()
    (worktree / 'build' / 'cache.bin').write_bytes(b'ignored')
    before = on_disk(worktree)
    made = store.add_variant(worktree, provenance={'workflow': 'mutate', 'prompt': 'Change things.', 'model': 'm',
                                                   'role': 'worker', 'blinded': False})
    assert on_disk(worktree) == before
    assert {(change.path, change.change, change.storage) for change in made.files} == {
        ('logo.png', 'modified', 'whole'), ('src/extra.py', 'added', 'whole'), ('run.sh', 'removed', None),
        ('src/main.py', 'removed', None), ('src/app.py', 'added', 'whole')}
    assert (made.workflow, made.prompt, made.model, made.role, made.blinded) == ('mutate', 'Change things.', 'm',
                                                                                 'worker', False)
    out = tmp_path / 'out'
    store.extract([made.variant_id], out)
    expected = {path: data for path, data in before.items() if not path.startswith('build/')}
    assert on_disk(out) == expected


@pytest.mark.req('PROJ-029')
@pytest.mark.req('PROJ-018')
def test_large_source_uses_diffs_even_for_small_text_edits_and_both_reconstruct(repo, tmp_path, home):
    big = ''.join(f'line {number} of a large source file\n' for number in range(320000)).encode('utf-8')
    assert len(big) > 10 * 1024 * 1024
    (repo / 'data.txt').write_bytes(big)
    git(repo, 'add', 'data.txt')
    git(repo, 'commit', '-q', '-m', 'big file')
    store = Store('app')
    origin = store.add_origin()
    small = tmp_path / 'small'
    git(repo, 'worktree', 'add', '-q', str(small))
    (small / 'src' / 'main.py').write_text('print("small change")\n', encoding='utf-8')
    large = tmp_path / 'large'
    git(repo, 'worktree', 'add', '-q', str(large))
    edited = big.replace(b'line 60000 of', b'LINE SIXTY THOUSAND of').replace(b'line 119999 of', b'last line of')
    (large / 'data.txt').write_bytes(edited)
    first, second = store.add_variant(small), store.add_variant(large)
    assert [(change.path, change.storage) for change in first.files] == [('src/main.py', 'diff')]
    assert [(change.path, change.storage) for change in second.files] == [('data.txt', 'diff')]
    payload = units('app') / origin.mform_sha_id / 'variants' / second.variant_id
    stored = (payload / 'diffs' / 'data.txt.diff').read_bytes()
    assert stored.startswith(f'base_sha256 {hashlib.sha256(big).hexdigest()}\n'.encode())
    assert len(stored) < 10000 and not (payload / 'files').exists()
    store.extract(['all'], tmp_path / 'out')
    assert (tmp_path / 'out' / first.variant_id / 'src' / 'main.py').read_bytes() == b'print("small change")\n'
    assert (tmp_path / 'out' / second.variant_id / 'data.txt').read_bytes() == edited


@pytest.mark.req('PROJ-016')
@pytest.mark.req('PROJ-018')
def test_a_file_whose_stored_bytes_do_not_match_their_hash_fails_naming_it(repo, worktree, tmp_path, home):
    store = Store('app')
    origin = store.add_origin()
    (worktree / 'logo.png').write_bytes(b'new logo')
    made = store.add_variant(worktree)
    stored = units('app') / origin.mform_sha_id / 'variants' / made.variant_id / 'files' / 'logo.png'
    stored.write_bytes(b'tampered')
    from metaform.data import StoreError
    with pytest.raises(StoreError, match='logo.png'):
        store.extract([made.variant_id], tmp_path / 'out')


@pytest.mark.req('PROJ-015')
@pytest.mark.req('PROJ-018')
def test_each_sibling_variant_extracts_alone_without_the_others_payload(repo, tmp_path, home):
    import shutil
    store = Store('app')
    origin = store.add_origin()
    made = []
    for number in range(3):
        folder = tmp_path / f'w{number}'
        git(repo, 'worktree', 'add', '-q', str(folder))
        (folder / 'src' / 'main.py').write_text(f'print({number})\n', encoding='utf-8')
        made.append(store.add_variant(folder))
    variants = units('app') / origin.mform_sha_id / 'variants'
    for other in (made[0], made[2]):
        shutil.rmtree(variants / other.variant_id)
    store.extract([made[1].variant_id], tmp_path / 'out')
    assert (tmp_path / 'out' / 'src' / 'main.py').read_bytes() == b'print(1)\n'
    assert [variant.variant_id for variant in made] == ['v000001', 'v000002', 'v000003']


@pytest.mark.req('PROJ-017')
def test_remove_takes_a_worktree_away_only_after_its_variant_holds_it_and_refuses_other_folders(repo, worktree,
                                                                                               tmp_path, photos):
    store = Store('app')
    store.add_origin()
    (worktree / 'src' / 'main.py').write_text('print("keep me")\n', encoding='utf-8')
    before = on_disk(worktree)
    made = store.add_variant(worktree, remove=True)
    assert not worktree.exists()
    store.extract([made.variant_id], tmp_path / 'out')
    assert on_disk(tmp_path / 'out') == before
    from metaform.data import StoreError
    plain = Store('photos')
    plain.add_origin()
    (photos / 'notes.txt').write_text('edited\n', encoding='utf-8')
    with pytest.raises(StoreError) as refused:
        plain.add_variant(photos, remove=True)
    assert refused.value.next_step == f'metaform add variant {photos}' and photos.exists()
    assert plain.variants() == ()  # a refusal collects nothing


@pytest.mark.req('PROJ-023')
def test_a_collection_that_fails_partway_leaves_no_rows_and_no_folder(repo, worktree, home, monkeypatch):
    store = Store('app')
    origin = store.add_origin()
    (worktree / 'logo.png').write_bytes(b'changed')
    from metaform.data import history

    def broken(*args, **kwargs):
        raise OSError('disk gone')
    with monkeypatch.context() as patched, pytest.raises(OSError):
        patched.setattr(history.os, 'replace', broken)
        store.add_variant(worktree)
    assert store.variants() == ()
    variants = units('app') / origin.mform_sha_id / 'variants'
    assert not variants.exists() or list(variants.iterdir()) == []


@pytest.mark.req('PROJ-010')
@pytest.mark.req('PROJ-024')
def test_the_history_commands_work_with_every_feature_module_off(run, repo, tmp_path):
    for module in ('intake', 'map', 'mcp', 'memory', 'web'):
        run('disable', module)
    none_yet = run('list', 'variants', cwd=repo)
    assert none_yet.stdout == ''  # registration already established the origin
    added = run('add', 'origin', cwd=repo).stdout
    mform_id = re.search(r'\b[0-9a-f]{16}\b', added).group(0)
    commit = git(repo, 'rev-parse', 'HEAD').strip()
    listed = run('list', 'origins', cwd=repo).stdout.split()
    assert listed[:3] == [mform_id, 'repo', commit] and listed[-2:] == ['0', 'variants']
    worker = tmp_path / 'worker'
    git(repo, 'worktree', 'add', '-q', str(worker))
    (worker / 'src' / 'main.py').write_text('print("from a worker")\n', encoding='utf-8')
    collected = run('add', 'variant', str(worker), 'workflow=mutate', 'prompt=Change it.', 'blinded=false',
                    cwd=repo).stdout
    assert 'v000001' in collected and mform_id in collected
    rows = run('list', 'variants', f'origin={mform_id}', cwd=repo).stdout.splitlines()
    assert len(rows) == 1 and rows[0].split()[0] == 'v000001' and rows[0].split()[-1] == 'mutate'
    assert str(worker) in rows[0]
    out = tmp_path / 'out'
    run('extract', 'v000001', str(out), cwd=repo)
    assert (out / 'src' / 'main.py').read_bytes() == b'print("from a worker")\n'
    run('extract', 'all', str(tmp_path / 'every'), cwd=repo)
    assert (tmp_path / 'every' / 'v000001' / 'src' / 'main.py').is_file()
    full = run('extract', 'v000001', str(out), cwd=repo, ok=False)
    assert full.returncode != 0 and full.stderr.splitlines()[-1] == 'Next: metaform extract v000001 <empty folder>'
    assert 'already' in run('add', 'origin', cwd=repo).stdout


@pytest.mark.req('PROJ-012')
def test_a_clean_tree_git_normalizes_line_endings_for_gets_no_first_variant(repo):
    git(repo, 'config', 'core.autocrlf', 'input')
    (repo / 'crlf.txt').write_bytes(b'one\r\ntwo\r\n')
    git(repo, 'add', 'crlf.txt')
    git(repo, 'commit', '-q', '-m', 'crlf')
    assert git(repo, 'status', '--porcelain') == ''
    store = Store('app')
    origin = store.add_origin()
    assert store.variants(origin=origin.mform_id) == ()


@pytest.mark.req('PROJ-023')
def test_a_variant_whose_rows_committed_before_its_folder_moved_is_completed_when_read(repo, worktree, home,
                                                                                      monkeypatch, tmp_path):
    store = Store('app')
    origin = store.add_origin()
    (worktree / 'logo.png').write_bytes(b'changed')
    from metaform.data import history
    real = history.os.replace

    def last_step_fails(source, target):
        if not Path(target).name.startswith('.'):
            raise OSError('power lost')
        real(source, target)
    with monkeypatch.context() as patched, pytest.raises(OSError):
        patched.setattr(history.os, 'replace', last_step_fails)
        store.add_variant(worktree)
    [made] = store.variants()
    store.extract([made.variant_id], tmp_path / 'out')
    assert (tmp_path / 'out' / 'logo.png').read_bytes() == b'changed'
    assert sorted(path.name for path in (units('app') / origin.mform_sha_id / 'variants').iterdir()) == [
        made.variant_id]


@pytest.mark.req('PROJ-023')
def test_a_leftover_folder_for_the_next_variant_id_does_not_block_collecting(repo, worktree, home):
    store = Store('app')
    origin = store.add_origin()
    stale = units('app') / origin.mform_sha_id / 'variants' / 'v000001'
    stale.mkdir(parents=True)
    (stale / 'left.txt').write_text('from an interrupted write', encoding='utf-8')
    (worktree / 'logo.png').write_bytes(b'changed')
    made = store.add_variant(worktree)
    assert made.variant_id == 'v000001' and not (stale / 'left.txt').exists()
    assert [change.path for change in made.files] == ['logo.png']


@pytest.mark.req('PROJ-014')
def test_two_origins_added_at_once_for_the_same_content_make_one(repo):
    import threading
    store = Store('app')
    start = threading.Barrier(4)
    made, errors = [], []

    def add():
        start.wait()
        try:
            made.append(store.add_origin().mform_id)
        except Exception as error:  # noqa: BLE001  the test reports any failure of a racing call
            errors.append(error)
    threads = [threading.Thread(target=add) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == [] and len(set(made)) == 1 and len(store.origins()) == 1
