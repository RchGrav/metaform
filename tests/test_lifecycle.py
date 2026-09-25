"""Module lifecycle where the standard names a real risk: unload, reload, shutdown and cancel, BASE-018 and QUAL-010."""
from __future__ import annotations

import asyncio
import json
import sys
import textwrap
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.kind('fixture')

OS = "SUPPORTED_OS = ('linux', 'macos', 'windows')"


def _entry_package(site: Path, name: str, files: dict[str, str]) -> None:
    package = site / name
    package.mkdir(parents=True)
    for file, body in files.items():
        (package / file).write_text(textwrap.dedent(body), encoding='utf-8')
    info = site / f'{name}-1.0.dist-info'
    info.mkdir()
    (info / 'METADATA').write_text(f'Metadata-Version: 2.1\nName: {name}\nVersion: 1.0\n', encoding='utf-8')
    (info / 'entry_points.txt').write_text(f'[metaform.modules]\n{name} = {name}\n', encoding='utf-8')


@pytest.mark.req('BASE-018')
@pytest.mark.req('QUAL-010')
def test_a_cli_verb_that_spawns_a_task_shuts_down_cleanly_with_the_task_finished_before_stop(run, user_module,
                                                                                             tmp_path):
    marks = tmp_path / 'marks.txt'
    user_module('spawner', f'''
        import asyncio
        from pathlib import Path
        from metaform.module import Module, Verb
        {OS}
        MARKS = Path({str(marks)!r})
        async def forever():
            try:
                await asyncio.sleep(3600)
            finally:
                with MARKS.open('a') as out:
                    out.write('task finished\\n')
        async def work(ctx):
            ctx.spawn(forever())
            return 'spawned'
        def stop(ctx):
            with MARKS.open('a') as out:
                out.write('stop\\n')
        MODULE = Module(id='spawner', summary='x', purpose='Spawns. Details: metaform help spawner.',
                        verbs=(Verb('work', work, 'Spawn a task.'),), stop=stop)
    ''')
    result = run('spawner', 'work')
    assert result.stdout == 'spawned'
    assert 'destroyed' not in result.stderr and 'Event loop is closed' not in result.stderr, result.stderr
    assert marks.read_text().splitlines() == ['task finished', 'stop']


@pytest.mark.req('BASE-018')
@pytest.mark.req('QUAL-010')
def test_unload_waits_for_tasks_then_stops_and_a_failing_stop_is_reported(home, user_module):
    from metaform import loader, settings
    from metaform.module import Context
    user_module('fragile', f'''
        import asyncio
        from metaform import settings
        from metaform.module import Module, Verb
        {OS}
        settings.text('fragile_word', 'x')
        EVENTS = []
        async def forever():
            try:
                await asyncio.sleep(3600)
            finally:
                EVENTS.append('task finished')
        async def work(ctx):
            ctx.spawn(forever())
        def stop(ctx):
            EVENTS.append('stop')
            raise RuntimeError('stop failed')
        MODULE = Module(id='fragile', summary='x', purpose='Fragile. Details: metaform help fragile.',
                        verbs=(Verb('work', work, 'Spawn.'),), stop=stop)
    ''')
    loader.reset()
    found = next(item for item in loader.discover() if item.id == 'fragile')
    namespace = sys.modules[found.import_name]
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(found.module.verbs[0].run(Context(module='fragile', folder=home)))
        loader.unload('fragile')
    finally:
        loop.close()
    assert namespace.EVENTS == ['task finished', 'stop']
    assert 'RuntimeError: stop failed' in found.problem
    assert found.module is None and found.import_name not in sys.modules
    assert 'fragile_word' not in settings.SCHEMA
    loader.reset()


@pytest.mark.req('BASE-018')
@pytest.mark.req('QUAL-010')
def test_a_reload_runs_changed_submodules_and_keeps_each_setting_once(home, user_module):
    from metaform import loader, settings
    folder = user_module('parted', f'''
        from metaform.module import Module
        from . import parts
        {OS}
        MODULE = Module(id='parted', summary='x', purpose='Parted. Details: metaform help parted.')
    ''')
    (folder / 'parts.py').write_text("from metaform import settings\nsettings.text('parted_word', 'one')\n")
    loader.reset()
    loader.discover()
    assert settings.SCHEMA['parted_word'].default == 'one'
    (folder / 'parts.py').write_text("from metaform import settings\nsettings.text('parted_word', 'second')\n")
    loader.reset()
    loader.discover()
    assert settings.SCHEMA['parted_word'].default == 'second'
    loader.reset()
    assert 'parted_word' not in settings.SCHEMA


@pytest.mark.req('BASE-018')
@pytest.mark.req('CLI-024')
def test_an_entry_point_modules_settings_return_with_every_load(home, tmp_path, monkeypatch):
    from metaform import loader, settings
    site = tmp_path / 'site'
    _entry_package(site, 'shelved', {'__init__.py': f'''
        from metaform import settings
        from metaform.module import Module
        {OS}
        settings.text('shelved_word', 'x', help='A word.')
        MODULE = Module(id='shelved', summary='x', purpose='Shelved. Details: metaform help shelved.')
    '''})
    monkeypatch.syspath_prepend(str(site))
    for _ in range(3):
        loader.reset()
        assert next(item for item in loader.discover() if item.id == 'shelved').module is not None
        assert settings.SCHEMA['shelved_word'].owner == 'shelved'
    loader.reset()
    assert 'shelved_word' not in settings.SCHEMA


@pytest.mark.req('BASE-015')
@pytest.mark.req('BASE-037')
def test_a_module_whose_dependency_is_not_installed_is_reported_and_not_imported(module_row, user_module):
    user_module('needy', '''
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        DEPENDENCIES = ('surely-not-an-installed-distribution>=1.0',)
        raise SystemExit('must not run')
    ''')
    row = module_row('needy')
    assert row[1] == 'error' and 'surely-not-an-installed-distribution' in row[3]


@pytest.mark.req('MCP-017')
def test_a_failed_proof_stops_the_server_and_keeps_its_reason(tmp_path):
    from metaform.probe import probe
    beat = tmp_path / 'beat'
    script = tmp_path / 'server.py'
    script.write_text(textwrap.dedent(f'''
        import sys, time, pathlib
        sys.stderr.write('boom: the server cannot answer\\n')
        sys.stderr.flush()
        beat = pathlib.Path({str(beat)!r})
        while True:
            beat.write_text(str(time.monotonic()))
            time.sleep(0.05)
    '''), encoding='utf-8')
    proof = probe([sys.executable, str(script)], cwd=tmp_path, limit=1.0)
    assert not proof.ok and 'boom' in proof.reason
    last = beat.read_text()
    time.sleep(0.5)
    assert beat.read_text() == last


@pytest.mark.req('LAYER-006')
@pytest.mark.req('LAYER-007')
@pytest.mark.req('STORE-019')
def test_hidden_and_masked_memory_reaches_no_read_path(run, tmp_path):
    from metaform.data import Node, Store
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    store = Store('proj')
    with store.atomic():
        layer = store.layer('intake-1', 'intake', 'The map.', kind='intake', mutable=False, hideable=False,
                            provenance={'module': 'intake'}, ready=True)
        store.add_element(layer.name, 'code.manager.route', role='DE')
        store.add_element(layer.name, 'code.probe.echo', role='SE')
    run('memory', 'add-observations', 'element:code.manager.route', 'Routes are ejected.', cwd=folder)
    run('memory', 'create-relations', 'element:code.probe.echo', 'checks', 'element:code.manager.route', cwd=folder)

    def reads():
        graph = json.loads(run('memory', 'read-graph', '--json', cwd=folder).stdout)
        found = json.loads(run('memory', 'search-nodes', 'ejected', '--json', cwd=folder).stdout)
        opened = json.loads(run('memory', 'open-nodes', 'element:code.manager.route', '--json', cwd=folder).stdout)
        return (graph['nodes'], found['nodes'], opened['nodes'][0]['observations'], opened['relations'],
                store.search('ejected', 'memory').results,
                store.links_to(Node('element', 'code.manager.route'), 'memory').results)
    assert all(reads())
    run('map', 'hide', 'memory', '--confirm', cwd=folder)
    assert not any(reads())
    assert store.search('ejected', 'memory', raw=True).results
    run('map', 'unhide', 'memory', cwd=folder)
    run('map', 'mask', 'code', 'memory', cwd=folder)
    assert not any(reads())
    run('map', 'clear', 'code', 'memory', 'mask', cwd=folder)
    assert all(reads())


@pytest.mark.req('STORE-027')
@pytest.mark.req('STORE-006')
def test_an_import_is_one_unit_and_a_metaform_owned_by_another_project_is_refused_first(home, tmp_path):
    from metaform import home as metaform_home
    from metaform.data import Store, StoreError, export_document, import_document
    for name in ('one', 'two'):
        (tmp_path / name).mkdir()
        metaform_home.add_project(name, tmp_path / name)
    Store('one').layer('notes', 'test', 'Notes.', mutable=True, hideable=True, provenance={'module': 'test'})
    document = export_document(['one'])
    listing = sorted(str(path.relative_to(home)) for path in home.rglob('*'))
    with pytest.raises(StoreError) as refused:
        import_document(document, 'two')
    assert 'one' in str(refused.value) and refused.value.next_step
    assert sorted(str(path.relative_to(home)) for path in home.rglob('*')) == listing
    assert [form.name for form in metaform_home.metaforms('two')] == []


@pytest.mark.req('STORE-027')
@pytest.mark.req('BASE-044')
def test_a_layer_export_whose_requires_are_missing_imports_what_it_can_with_notices(home, tmp_path, monkeypatch):
    from metaform import home as metaform_home
    from metaform.data import Node, Store, export_document, import_document
    (tmp_path / 'proj').mkdir()
    metaform_home.add_project('proj', tmp_path / 'proj')
    store = Store('proj')
    with store.atomic():
        intake = store.layer('intake-1', 'intake', 'The map.', kind='intake', mutable=False, hideable=False,
                             provenance={'module': 'intake'}, ready=True)
        store.add_element(intake.name, 'code.timer', role='DE')
    notes = store.layer('notes', 'test', 'Notes.', mutable=True, hideable=True, provenance={'module': 'test'})
    store.add_item(notes.name, Node('element', 'code.timer'), 'keep it small')
    document = export_document(['proj'], layers=['notes'])
    monkeypatch.setenv('METAFORM_HOME', str(tmp_path / 'other'))
    report = import_document(document)
    assert report['layers_added'] == 1
    assert report['notices'] and 'metaform import' in report['notices'][0]['message']
    moved = Store('proj')
    item = moved.layer_items('notes').results[0]
    assert item.value == 'keep it small' and item.orphaned is True


@pytest.mark.req('STORE-027')
def test_registering_a_project_whose_folder_another_holds_is_refused_by_name(home, tmp_path):
    from metaform import home as metaform_home
    from metaform.data import StoreError
    (tmp_path / 'proj').mkdir()
    metaform_home.add_project('proj', tmp_path / 'proj')
    with pytest.raises(StoreError) as refused:
        metaform_home.register(metaform_home.Project('twin', str(tmp_path / 'proj'), 'path', str(tmp_path / 'proj')))
    assert 'proj' in str(refused.value)
