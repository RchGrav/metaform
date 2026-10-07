"""Command/request refreshes follow module changes without repeating discovery checks for each DAO read."""
from __future__ import annotations

import asyncio
import sqlite3

import pytest

from metaform import home as registry
from metaform import loader, settings
from metaform.data import Store

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('BASE-037')]


def prepared(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    registry.add_project('project', project)
    loader.discover()
    return Store('project')


def checks(monkeypatch):
    selected = loader._selected_project
    calls = []

    def counted():
        calls.append(None)
        return selected()

    monkeypatch.setattr(loader, '_selected_project', counted)
    return calls


def module(user_module):
    user_module('request_watch', '''
        from metaform.module import Module
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        MODULE = Module(id='request_watch', summary='Request watcher.',
                        purpose='Request watcher. Details: metaform help request_watch.')
    ''')
    registry.set_module_state('request_watch', True)


def disable_externally():
    with sqlite3.connect(registry.chassis_path()) as connection:
        connection.execute("INSERT OR REPLACE INTO module_state VALUES('request_watch', 0)")


def test_nested_request_checks_modules_once_for_many_store_reads(home, tmp_path, monkeypatch):
    store = prepared(tmp_path)
    calls = checks(monkeypatch)
    with loader.request_scope():
        store.roots()
        with loader.request_scope():
            store.layers()
            store.bases()
        store.roots()
    assert len(calls) == 1
    with loader.request_scope():
        store.layers()
    assert len(calls) == 2


def test_next_request_follows_external_module_disable(home, tmp_path, user_module):
    module(user_module)
    store = prepared(tmp_path)
    with loader.request_scope():
        assert loader.get('request_watch').module is not None
        store.roots()
    disable_externally()
    with loader.request_scope():
        store.roots()
        assert loader.get('request_watch').module is None


def test_local_project_selection_refreshes_modules_in_the_same_request(home, tmp_path, monkeypatch):
    projects = {}
    for project_id in ('first', 'second'):
        folder = tmp_path / project_id
        folder.mkdir()
        registry.add_project(project_id, folder)
        module_id = project_id + '_watch'
        place = folder / '.metaform' / 'modules' / module_id
        place.mkdir(parents=True)
        (place / '__init__.py').write_text(
            "from metaform.module import Module\n"
            "SUPPORTED_OS = ('linux', 'macos', 'windows')\n"
            f"MODULE = Module(id='{module_id}', summary='Project watcher.', "
            f"purpose='Project watcher. Details: metaform help {module_id}.')\n",
            encoding='utf-8')
        projects[project_id] = folder
    monkeypatch.chdir(projects['first'])
    store = Store('first')
    with loader.request_scope():
        store.roots()
        assert 'first_watch' in {module.id for module in loader.enabled()}
        settings.assign('project', 'second', projects['first'])
        store.roots()
        loaded = {module.id for module in loader.enabled()}
        assert 'second_watch' in loaded
        assert 'first_watch' not in loaded


def test_direct_store_calls_follow_external_module_disable(home, tmp_path, user_module):
    module(user_module)
    store = prepared(tmp_path)
    assert loader.get('request_watch').module is not None
    disable_externally()
    store.roots()
    assert loader.get('request_watch').module is None


def test_scope_is_released_after_failure(home, tmp_path, monkeypatch):
    prepared(tmp_path)
    calls = checks(monkeypatch)
    with pytest.raises(ValueError), loader.request_scope():
        loader.follow_enabled()
        raise ValueError('failed command')
    assert not loader.in_request_scope()
    with loader.request_scope():
        loader.follow_enabled()
    assert len(calls) == 2


def test_fresh_request_refreshes_inside_long_lived_command(home, tmp_path, monkeypatch):
    prepared(tmp_path)
    calls = checks(monkeypatch)
    with loader.request_scope():
        loader.follow_enabled()
        for _ in range(2):
            with loader.request_scope(fresh=True):
                loader.follow_enabled()
    assert len(calls) == 3


def test_async_requests_share_refresh_with_worker_threads_but_not_each_other(home, tmp_path, monkeypatch):
    store = prepared(tmp_path)
    calls = checks(monkeypatch)

    async def request():
        with loader.request_scope(fresh=True):
            await asyncio.to_thread(store.roots)
            await asyncio.to_thread(loader.follow_enabled)

    async def both():
        with loader.request_scope():
            loader.follow_enabled()
            await asyncio.gather(request(), request())

    asyncio.run(both())
    assert len(calls) == 3


def test_background_task_outliving_request_resumes_refresh(home, tmp_path, monkeypatch):
    store = prepared(tmp_path)
    calls = checks(monkeypatch)

    async def background(ready):
        await ready.wait()
        assert not loader.in_request_scope()
        store.roots()

    async def launch():
        ready = asyncio.Event()
        with loader.request_scope():
            loader.follow_enabled()
            task = asyncio.create_task(background(ready))
        ready.set()
        await task

    asyncio.run(launch())
    assert len(calls) == 2
