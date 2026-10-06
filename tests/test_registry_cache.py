"""Registry caching keeps request reads coherent and sees subsequent writers."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from metaform import home as registry
from metaform import settings

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('STORE-029')]


def test_registry_checks_files_once_and_reuses_lookup_results(home, tmp_path, monkeypatch):
    folder = tmp_path / 'source'
    folder.mkdir()
    registry.add_project('p', folder)
    registry.set_module_state('hello', True)
    with registry.registry_scope():
        registry.project('p')
        registry.folder_project(folder / 'child')
        registry.module_state('hello')
    def unexpected(*args, **kwargs):
        pytest.fail('a warm registry lookup opened a transaction')
    monkeypatch.setattr(registry, '_transaction', unexpected)
    with registry.registry_scope():
        for _ in range(5):
            assert registry.project('p').path == str(folder)
            assert registry.project_folder('p') is not None
            assert registry.folder_project(folder / 'child') == 'p'
            assert registry.module_state('hello') is True


def test_external_wal_commit_is_seen_on_next_request(home):
    registry.set_module_state('hello', True)
    with registry.registry_scope():
        assert registry.module_state('hello') is True
        with sqlite3.connect(registry.base_path()) as other:
            other.execute("UPDATE module_state SET enabled=0 WHERE module_id='hello'")
        assert registry.module_state('hello') is True
    with registry.registry_scope():
        assert registry.module_state('hello') is False


def test_local_write_invalidates_reads_in_the_same_request(home):
    with registry.registry_scope():
        assert registry.module_state('hello') is None
        registry.set_module_state('hello', True)
        assert registry.module_state('hello') is True


def test_local_write_invalidates_an_older_active_registry_scope(home):
    registry.set_module_state('hello', True)
    with registry.registry_scope():
        assert registry.module_state('hello') is True
        with sqlite3.connect(registry.base_path()) as other:
            other.execute("INSERT INTO module_state VALUES ('external_registry_change', 1)")
        with registry.registry_scope(fresh=True):
            assert registry.module_state('external_registry_change') is True
            registry.set_module_state('hello', False)
            assert registry.module_state('hello') is False
        assert registry.module_state('hello') is False


def test_local_write_invalidates_an_older_concurrent_registry_scope(home):
    registry.set_module_state('hello', True)
    ready = Event()
    committed = Event()

    def older_request():
        with registry.registry_scope():
            assert registry.module_state('hello') is True
            ready.set()
            assert committed.wait(5)
            return registry.module_state('hello')

    with ThreadPoolExecutor(max_workers=1) as workers:
        result = workers.submit(older_request)
        try:
            assert ready.wait(5)
            with sqlite3.connect(registry.base_path()) as other:
                other.execute("INSERT INTO module_state VALUES ('external_registry_change', 1)")
            with registry.registry_scope(fresh=True):
                assert registry.module_state('external_registry_change') is True
                registry.set_module_state('hello', False)
        finally:
            committed.set()
        assert result.result(timeout=5) is False


def test_project_added_elsewhere_invalidates_cached_absence(home, tmp_path):
    folder = tmp_path / 'source'
    folder.mkdir()
    with registry.registry_scope():
        assert registry.folder_project(folder) is None
        with registry.registry_scope(fresh=True):
            registry.add_project('p', folder)
    with registry.registry_scope():
        assert registry.folder_project(folder) == 'p'


def test_setting_scope_moves_after_external_write_and_values_are_defensive(home, tmp_path):
    folder = tmp_path / 'source'
    child = folder / 'child'
    child.mkdir(parents=True)
    registry.add_project('p', folder)
    scope = registry.path_key(folder)
    registry.save(scope, 'chassis', 'layers', ['first'])
    with registry.registry_scope():
        assert settings.value('layers', child) == ['first']
        got = registry.stored(scope, 'chassis', 'layers')
        got.append('caller edit')
        assert registry.stored(scope, 'chassis', 'layers') == ['first']
    path = registry.project_folder('p') / registry.PROJECT_DB
    with sqlite3.connect(path) as other:
        other.execute('INSERT INTO settings(scope, owner, key, position, value) VALUES (?, ?, ?, ?, ?)',
                      (registry.path_key(child), 'chassis', 'layers', 0, '"second"'))
    with registry.registry_scope():
        assert settings.value('layers', child) == ['second']


def test_changed_registry_version_is_refused_before_serving_cached_record(home, tmp_path):
    folder = tmp_path / 'source'
    folder.mkdir()
    registry.add_project('p', folder)
    path = registry.project_folder('p') / registry.PROJECT_DB
    with registry.registry_scope():
        assert registry.project('p') is not None
    with sqlite3.connect(path) as other:
        other.execute("UPDATE meta SET value='999' WHERE key='schema_version'")
    with pytest.raises(registry.StoreError, match='999'), registry.registry_scope():
        registry.project('p')
