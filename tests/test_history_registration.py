"""Registration retains enough source and history to survive losing the source, PROJ-026/029."""
import json
import shutil
import subprocess

import pytest

from metaform import __version__
from metaform import home as registry
from metaform.data import Store, history

pytestmark = pytest.mark.kind('fixture')
LIMIT = 10 * 1024 * 1024


def git(folder, *args):
    return subprocess.run(['git', '-C', str(folder), *args], check=True, capture_output=True).stdout.strip()


@pytest.mark.req('PROJ-026')
@pytest.mark.req('PROJ-029')
@pytest.mark.parametrize('repository', [False, True])
def test_registration_captures_origin_provenance_and_dirty_work_before_source_loss(home, tmp_path, repository,
                                                                                 monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'main.txt').write_bytes(b'baseline\r\nwithout final newline')
    (source / 'asset.bin').write_bytes(b'\x00asset')
    commit = None
    if repository:
        git(source, 'init', '-q')
        git(source, 'config', 'user.email', 'test@example.com')
        git(source, 'config', 'user.name', 'Test')
        git(source, 'config', 'core.autocrlf', 'false')
        git(source, 'add', '.')
        git(source, 'commit', '-qm', 'baseline')
        commit = git(source, 'rev-parse', 'HEAD').decode()
        (source / 'main.txt').write_bytes(b'dirty work')
    registry.add_project('app', source)
    store = Store('app')
    [origin] = store.origins()
    folder = registry.project_folder('app')
    provenance_file = folder / '.metaform' / 'provenance.json'
    provenance_bytes = provenance_file.read_bytes()
    provenance = json.loads(provenance_bytes)
    assert provenance['source'] == str(source)
    assert provenance['commit'] == commit
    assert provenance['content_hash'] == origin.origin_sha256
    assert provenance['registered'] and provenance['metaform'] == __version__
    assert (folder / 'origin' / 'main.txt').read_bytes() == b'baseline\r\nwithout final newline'
    assert not (folder / 'origin' / '.git').exists()
    if repository:
        [made] = store.variants()
    else:
        (source / 'main.txt').write_bytes(b'dirty work')
        made = store.add_variant(source, provenance={'module': 'workflow', 'model': 'test', 'role': 'worker'})
        assert (made.module, made.model, made.role) == ('workflow', 'test', 'worker')
    registry.add_project('app', source)
    assert provenance_file.read_bytes() == provenance_bytes
    other_home = tmp_path / 'other-home'
    shutil.copytree(folder, other_home / 'projects' / folder.name)
    shutil.rmtree(source)
    monkeypatch.setenv('METAFORM_HOME', str(other_home))

    def unavailable(*args, **kwargs):
        raise AssertionError('reconstruction must not call git')

    monkeypatch.setattr(history, '_git', unavailable)
    store = Store('app')
    assert history.origin_files('app', store.origins()[0])['main.txt'][0] == b'baseline\r\nwithout final newline'
    store.extract([made.variant_id], tmp_path / 'out')
    assert (tmp_path / 'out' / 'main.txt').read_bytes() == b'dirty work'
    assert (tmp_path / 'out' / 'asset.bin').read_bytes() == b'\x00asset'


@pytest.mark.req('PROJ-029')
@pytest.mark.req('PROJ-018')
@pytest.mark.parametrize('size', [4 * 1024 * 1024, LIMIT - 1, LIMIT, LIMIT + 1])
def test_history_policy_counts_all_source_and_small_variants_are_complete(home, tmp_path, size, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    # The unchanged binary determines the size, even though the changed text is tiny.
    (source / 'asset.bin').write_bytes(b'\0' * (size - 4))
    (source / 'main.txt').write_bytes(b'old\n')
    registry.add_project('app', source)
    store = Store('app')
    (source / 'main.txt').write_bytes(b'new\n')
    made = store.add_variant(source)
    small = size < LIMIT
    assert next(file.storage for file in made.files if file.path == 'main.txt') == ('whole' if small else 'diff')
    unit = registry.project_folder('app') / 'origins' / store.origins()[0].mform_sha_id
    payload = unit / 'variants' / made.variant_id
    if small:
        assert (payload / 'files' / 'asset.bin').read_bytes() == b'\0' * (size - 4)
        assert not (payload / 'diffs').exists()
        # A whole variation opens on its own, even without its origin payload.
        shutil.rmtree(unit / 'origin')
        shutil.rmtree(registry.project_folder('app') / 'origin')
    shutil.rmtree(source)
    monkeypatch.setattr(history, '_git', lambda *args, **kwargs: pytest.fail('git called during extraction'))
    store.extract([made.variant_id], tmp_path / 'out')
    assert (tmp_path / 'out' / 'main.txt').read_bytes() == b'new\n'
    assert (tmp_path / 'out' / 'asset.bin').stat().st_size == size - 4


@pytest.mark.req('PROJ-026')
@pytest.mark.req('PROJ-029')
def test_built_files_are_neither_copied_nor_counted(home, tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'main.py').write_bytes(b'old\n')
    for name in ('__pycache__', 'build', 'dist', '.git'):
        (source / name).mkdir()
        (source / name / 'generated.bin').write_bytes(b'\0' * LIMIT)
    (source / 'main.pyc').write_bytes(b'\0' * LIMIT)
    registry.add_project('app', source)
    store = Store('app')
    [origin] = store.origins()
    assert set(history.origin_files('app', origin)) == {'main.py'}
    (source / 'main.py').write_bytes(b'new\n')
    made = store.add_variant(source)
    store.extract([made.variant_id], tmp_path / 'out')
    assert {path.name for path in (tmp_path / 'out').iterdir()} == {'main.py'}
    assert made.files[0].storage == 'whole'


@pytest.mark.req('PROJ-026')
def test_failed_origin_capture_does_not_register_a_partial_project(home, tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'main.txt').write_bytes(b'baseline')

    def failed(*args, **kwargs):
        raise OSError('capture failed')

    with monkeypatch.context() as patched:
        patched.setattr(history, 'add_origin', failed)
        with pytest.raises(OSError, match='capture failed'):
            registry.add_project('app', source)
    assert registry.project('app') is None
    assert list((home / 'projects').iterdir()) == []
    registry.add_project('app', source)
    assert len(Store('app').origins()) == 1


@pytest.mark.req('PROJ-026')
@pytest.mark.req('PROJ-029')
@pytest.mark.req('PROJ-018')
def test_large_source_diff_reconstructs_additions_removals_and_binary_changes(home, tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'asset.bin').write_bytes(b'\0' * LIMIT)
    (source / 'old.txt').write_bytes(b'removed')
    (source / 'text.txt').write_bytes(b'first\r\nlast')
    registry.add_project('app', source)
    store = Store('app')
    (source / 'old.txt').unlink()
    (source / 'added.txt').write_bytes(b'added\r\nwithout newline')
    (source / 'text.txt').write_bytes(b'changed\r\nlast')
    (source / 'asset.bin').write_bytes(b'\0' * LIMIT + b'changed')
    monkeypatch.setenv('GIT_CONFIG_COUNT', '1')
    monkeypatch.setenv('GIT_CONFIG_KEY_0', 'core.autocrlf')
    monkeypatch.setenv('GIT_CONFIG_VALUE_0', 'true')
    made = store.add_variant(source)
    assert {(file.path, file.change, file.storage) for file in made.files} == {
        ('asset.bin', 'modified', 'whole'), ('old.txt', 'removed', None),
        ('added.txt', 'added', 'diff'), ('text.txt', 'modified', 'diff')}
    shutil.rmtree(source)
    monkeypatch.setattr(history, '_git', lambda *args, **kwargs: pytest.fail('git called during extraction'))
    store.extract([made.variant_id], tmp_path / 'out')
    assert not (tmp_path / 'out' / 'old.txt').exists()
    assert (tmp_path / 'out' / 'text.txt').read_bytes() == b'changed\r\nlast'
    assert (tmp_path / 'out' / 'added.txt').read_bytes() == b'added\r\nwithout newline'
    assert (tmp_path / 'out' / 'asset.bin').read_bytes() == b'\0' * LIMIT + b'changed'
