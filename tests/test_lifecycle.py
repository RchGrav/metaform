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
@pytest.mark.cli_process
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
def test_enabling_another_module_keeps_live_registrations_and_tasks(home, user_module):
    from metaform import loader, settings
    user_module('steady', f'''
        from metaform import settings
        from metaform.module import Module
        {OS}
        settings.text('steady_word', 'kept')
        EVENTS = []
        def start(ctx):
            EVENTS.append('start')
        def stop(ctx):
            EVENTS.append('stop')
        MODULE = Module(id='steady', summary='Steady.', purpose='Keeps its state.', start=start, stop=stop)
    ''')
    user_module('neighbor', f'''
        from metaform.module import Module
        {OS}
        SHIPS_DISABLED = True
        MODULE = Module(id='neighbor', summary='Neighbor.', purpose='Loads separately.')
    ''')
    steady = loader.get('steady')
    namespace = sys.modules[steady.import_name]
    setting = settings.SCHEMA['steady_word']
    tasks = steady.tasks
    loop = asyncio.new_event_loop()

    async def spawn():
        task = loader.spawn('steady', asyncio.sleep(3600))
        await asyncio.sleep(0)
        return task

    task = loop.run_until_complete(spawn())
    try:
        loader.set_enabled('neighbor', True)
        assert loader.get('neighbor').module is not None
        assert loader.get('steady') is steady
        assert sys.modules[steady.import_name] is namespace
        assert settings.SCHEMA['steady_word'] is setting
        assert steady.tasks is tasks and task in tasks and not task.done()
        assert namespace.EVENTS == ['start']
    finally:
        loader.reset()
        loop.close()
    assert namespace.EVENTS == ['start', 'stop']
    assert task.done() and task.cancelled()


@pytest.mark.req('BASE-018')
def test_stop_can_refresh_on_another_thread_without_losing_retained_modules(home, user_module):
    from metaform import loader, settings
    user_module('steady', f'''
        from metaform import settings
        from metaform.module import Module
        {OS}
        settings.text('steady_word', 'kept')
        MODULE = Module(id='steady', summary='Steady.', purpose='Keeps its state.')
    ''')
    user_module('closing', f'''
        import threading
        from metaform import loader, settings
        from metaform.module import Module
        {OS}
        settings.text('closing_word', 'gone')
        EVENTS = []
        def stop(ctx):
            def refresh():
                loader.follow_enabled()
                EVENTS.append(settings.value('steady_word', ctx.folder))
            worker = threading.Thread(target=refresh, daemon=True)
            worker.start()
            worker.join(2)
            if worker.is_alive():
                raise RuntimeError('refresh blocked cleanup')
        MODULE = Module(id='closing', summary='Closing.', purpose='Cleans up.', stop=stop)
    ''')
    steady, closing = loader.get('steady'), loader.get('closing')
    namespace = sys.modules[closing.import_name]
    loader.set_enabled('closing', False)
    assert namespace.EVENTS == ['kept']
    assert closing.problem == ''
    assert loader.get('steady') is steady
    assert loader.get('closing').module is None
    assert closing.import_name not in sys.modules
    assert 'closing_word' not in settings.SCHEMA


@pytest.mark.req('BASE-018')
def test_explicit_enablement_change_during_stop_is_applied_before_refresh_returns(home, user_module):
    from metaform import home as registry
    from metaform import loader, settings
    user_module('steady', f'''
        from metaform import settings
        from metaform.module import Module
        {OS}
        settings.text('steady_word', 'kept')
        EVENTS = []
        def stop(ctx):
            EVENTS.append('stop')
        MODULE = Module(id='steady', summary='Steady.', purpose='Keeps its state.', stop=stop)
    ''')
    user_module('closing', f'''
        from metaform import loader
        from metaform.module import Module
        {OS}
        def stop(ctx):
            loader.set_enabled('steady', False)
        MODULE = Module(id='closing', summary='Closing.', purpose='Cleans up.', stop=stop)
    ''')
    steady = loader.get('steady')
    namespace = sys.modules[steady.import_name]
    loader.set_enabled('closing', False)
    assert registry.module_state('steady') is False
    assert loader.get('steady').module is None
    assert namespace.EVENTS == ['stop']
    assert 'steady_word' not in settings.SCHEMA


@pytest.mark.req('BASE-018')
@pytest.mark.req('PROJ-003')
def test_project_switch_replaces_project_modules_and_keeps_system_and_user_modules(home, user_module,
                                                                                 tmp_path, monkeypatch):
    from metaform import home as registry
    from metaform import loader, settings
    user_module('steady', f'''
        from metaform import settings
        from metaform.module import Module
        {OS}
        settings.text('steady_word', 'kept')
        MODULE = Module(id='steady', summary='Steady.', purpose='Keeps its state.')
    ''')
    projects = {}
    for name in ('first', 'second'):
        folder = tmp_path / name
        folder.mkdir()
        registry.add_project(name, folder)
        place = folder / '.metaform' / 'modules' / 'local'
        place.mkdir(parents=True)
        (place / '__init__.py').write_text(textwrap.dedent(f'''
            from metaform import settings
            from metaform.module import Module
            {OS}
            settings.text('local_word', {name!r})
            EVENTS = []
            def start(ctx):
                EVENTS.append('start')
            def stop(ctx):
                EVENTS.append('stop')
            MODULE = Module(id='local', summary='Local.', purpose='Belongs to its project.', start=start, stop=stop)
        '''), encoding='utf-8')
        projects[name] = folder
    monkeypatch.chdir(projects['first'])
    system, steady, local = loader.get('map'), loader.get('steady'), loader.get('local')
    namespace = sys.modules[local.import_name]
    setting = settings.SCHEMA['steady_word']
    settings.assign('project', 'second', projects['first'])
    loader.follow_enabled()
    assert loader.get('map') is system
    assert loader.get('steady') is steady
    assert settings.SCHEMA['steady_word'] is setting
    assert loader.get('local') is not local
    assert loader.get('local').path == projects['second'] / '.metaform' / 'modules' / 'local'
    assert settings.value('local_word', projects['second']) == 'second'
    assert namespace.EVENTS == ['start', 'stop']
    assert sys.modules[local.import_name].EVENTS == ['start']


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
def test_hidden_and_masked_memory_reaches_no_read_path(run, tmp_path, monkeypatch, capsys):
    from metaform import cli
    from metaform.data import Store
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    store = Store('proj')
    with store.atomic():
        layer = store.layer('intake-1', 'intake', 'The map.', kind='intake', mutable=False, hideable=False,
                            provenance={'module': 'intake'}, ready=True)
        store.add_element(layer.name, 'code.manager.route', role='DE')
        store.add_element(layer.name, 'code.probe.echo', role='SE')
    route, probe = 'node=element:code.manager.route', 'node=element:code.probe.echo'
    run('memory', 'create_entities', json.dumps([{'name': 'route', 'entityType': 'part',
                                                  'observations': ['Routes are ejected.'], 'why': 'Routes go.'}]),
        route, cwd=folder)
    run('memory', 'create_entities', json.dumps([{'name': 'probe', 'entityType': 'part', 'observations': [],
                                                  'title': 'The probe', 'why': 'It checks routes.'}]),
        probe, cwd=folder)
    run('memory', 'create_relations', json.dumps([{'from': 'probe', 'to': 'route', 'relationType': 'checks'}]),
        cwd=folder)

    monkeypatch.chdir(folder)

    def command(*args):  # the same CLI, in this process: twenty reads cost a second, not twenty
        capsys.readouterr()
        assert cli.main([*args, '--json']) == 0
        return json.loads(capsys.readouterr().out)

    def reads():
        def memory(*args):
            return command('memory', *args)
        graph, found = memory('read_graph'), memory('search_nodes', 'ejected')
        opened = memory('open_nodes', json.dumps(['route']))
        node = command('map', 'where', 'code.manager.route', 'contents=true').get('memory', {})
        return (graph['entities'], found['entities'], opened['entities'], opened['relations'],
                memory('read_graph', route)['entities'], node.get('entities'))
    assert all(reads())
    run('map', 'hide', 'memory', '--confirm', cwd=folder)
    assert not any(reads())
    run('map', 'unhide', 'memory', cwd=folder)
    run('map', 'mask', 'code', 'memory', cwd=folder)
    assert not any(reads())
    run('map', 'clear', 'code', 'memory', 'mask', cwd=folder)
    assert all(reads())


@pytest.mark.req('STORE-027')
@pytest.mark.req('STORE-026')
@pytest.mark.req('BASE-044')
def test_an_import_meeting_a_metaform_another_project_owns_writes_nothing_of_it_and_names_the_owner(home, tmp_path):
    from metaform import home as metaform_home
    from metaform.data import Store, export_document, import_document
    for name in ('one', 'two'):
        (tmp_path / name).mkdir()
        metaform_home.add_project(name, tmp_path / name)
    Store('one').layer('notes', 'test', 'Notes.', mutable=True, hideable=True, provenance={'module': 'test'})
    document = export_document(['one'])
    listing = sorted(str(path.relative_to(home)) for path in home.rglob('*'))
    report = import_document(document, 'two')
    assert (report['bases_added'], report['bases_skipped'], report['layers_added']) == (0, 1, 0)
    assert any('one' in notice['message'] for notice in report['notices'])
    assert sorted(str(path.relative_to(home)) for path in home.rglob('*')) == listing
    assert [form.name for form in metaform_home.bases('two')] == []


@pytest.mark.req('STORE-027')
def test_a_document_imports_into_another_registered_project_which_keeps_its_own_path(home, tmp_path, monkeypatch):
    from metaform import home as metaform_home
    from metaform.data import Store, export_document, import_document
    (tmp_path / 'one').mkdir()
    metaform_home.add_project('one', tmp_path / 'one')
    Store('one').layer('notes', 'test', 'Notes.', mutable=True, hideable=True, provenance={'module': 'test'})
    document = export_document(['one'])
    monkeypatch.setenv('METAFORM_HOME', str(tmp_path / 'other-home'))
    (tmp_path / 'two').mkdir()
    metaform_home.add_project('two', tmp_path / 'two')
    report = import_document(document, 'two')
    assert (report['bases_added'], report['layers_added']) == (1, 1)
    assert Store('two').layer_ref('notes').variable == 'Notes.'
    assert metaform_home.project('two').path == str(tmp_path / 'two') and metaform_home.project('one') is None


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


@pytest.mark.req('STORE-031')
def test_registering_a_project_whose_folder_another_holds_is_refused_by_name(home, tmp_path):
    from metaform import home as metaform_home
    from metaform.data import StoreError
    (tmp_path / 'proj').mkdir()
    metaform_home.add_project('proj', tmp_path / 'proj')
    with pytest.raises(StoreError) as refused:
        metaform_home.register(metaform_home.Project('twin', str(tmp_path / 'proj'), 'path', str(tmp_path / 'proj')))
    assert 'proj' in str(refused.value)
