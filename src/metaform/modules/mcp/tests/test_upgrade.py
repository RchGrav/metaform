"""Schema upgrades must not strand the host's live MCP connection, work 6efd6c19."""
import asyncio
import os
import shutil
import sys
import time
from contextlib import closing
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from metaform import home as chassis_home
from metaform import sqlite
from metaform.data import Store

pytestmark = [pytest.mark.kind('simulation'), pytest.mark.req('MCP-002'), pytest.mark.req('STORE-029')]


@pytest.fixture
def installation(run, home, tmp_path):
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    store = Store('proj')
    layer = store.layer('intake', 'intake', 'The map.', kind='intake', ready=True, mutable=False, hideable=False)
    store.add_element(layer.name, 'code.alarm.audible', name_length=2, role='SE')
    import metaform
    from metaform.sqlite import SCHEMA_VERSION
    copied = tmp_path / 'package' / 'metaform'
    shutil.copytree(Path(metaform.__file__).parent, copied, ignore=shutil.ignore_patterns('tests', '__pycache__'))
    parameters = StdioServerParameters(command=sys.executable, args=['-m', 'metaform', 'mcp', 'serve'],
                                       cwd=folder, env={**os.environ, 'METAFORM_HOME': str(home),
                                                        'PYTHONPATH': str(copied.parent)})
    database = chassis_home.project_folder('proj') / 'main.metaform.sqlite3'
    return folder, copied, parameters, database, SCHEMA_VERSION


def upgrade(installation, changed=True):
    _, copied, _, database, old = installation
    newer = str(int(old) + 1)
    if changed:
        source = copied / 'sqlite.py'
        source.write_text(source.read_text().replace(f"SCHEMA_VERSION = '{old}'", f"SCHEMA_VERSION = '{newer}'"))
        # Python bytecode validates whole-second mtimes, unlike the recovery fingerprint.
        state = source.stat()
        os.utime(source, (state.st_atime, state.st_mtime + 2))
    with closing(sqlite.connect(database)) as db:
        db.execute("UPDATE meta SET value=? WHERE key='schema_version'", (newer,))


REQUEST = {'command': 'work', 'arguments': {'op': 'add', 'node': 'code.alarm.audible',
                                          'condition': '', 'task': 'One recovered write.'}}


@pytest.mark.parametrize(('changed', 'recovery'), [(True, 'relay'), (False, 'relay'), (True, 'manual')])
def test_live_connection_recovers_only_when_newer_code_is_available(run, installation, changed, recovery):
    folder, _, parameters, database, _ = installation
    run('set', '--mcp-recovery', recovery, cwd=folder)

    async def check():
        async with stdio_client(parameters) as (read, write), ClientSession(read, write, 10) as client:
            await client.initialize()
            # Force the live process to read the original project's schema before replacing its source.
            before = await client.call_tool('map', {'command': 'work', 'arguments': {'open': True}})
            assert not before.is_error
            upgrade(installation, changed)
            async with asyncio.timeout(20):
                result = await client.call_tool('map', REQUEST)
                following = await client.call_tool('map', {'command': 'work', 'arguments': {'open': True}})
            if changed and recovery == 'relay':
                assert not result.is_error, result
                assert not following.is_error, following
                # Check durable rows directly: replay must create exactly one work record.
                with closing(sqlite.connect(database)) as db:
                    assert db.execute('SELECT count(*) FROM work').fetchone()[0] == 1
            else:
                assert result.is_error and following.is_error
                assert 'schema version' in result.content[0].text
                assert 'Next: install the Metaform release that wrote it' in result.content[0].text

    asyncio.run(check())


@pytest.mark.parametrize('wire', ['legacy', 'july'])
def test_failed_replacement_keeps_the_connection_and_independent_commands_usable(installation, wire):
    folder, copied, parameters, database, _ = installation

    def damage():
        upgrade(installation)
        # The running server retains working code, but its replacement cannot import this damaged package.
        with (copied / 'modules' / 'mcp' / 'server.py').open('a') as source:
            source.write('\nthis is deliberately invalid Python !!!\n')

    if wire == 'july':
        from metaform.probe import Session, discover
        client = Session([parameters.command, *parameters.args], cwd=folder, env=parameters.env)
        try:
            discover(client, limit=10)
            damage()
            refusal = client.call('map', REQUEST, limit=10)
            assert refusal.get('isError'), refusal
            assert 'schema version' in refusal['content'][0]['text']
            assert not client.call('metaform', {'command': 'instructions'}, limit=10).get('isError')
            assert client.call('map', REQUEST, limit=10).get('isError')
            with closing(sqlite.connect(database)) as db:
                assert db.execute('SELECT count(*) FROM work').fetchone()[0] == 0
        finally:
            client.close()
        return

    async def check():
        async with stdio_client(parameters) as (read, write), ClientSession(read, write, 10) as client:
            await client.initialize()
            damage()
            refusal = await client.call_tool('map', REQUEST)
            assert refusal.is_error
            assert 'schema version' in refusal.content[0].text
            following = await client.call_tool('metaform', {'command': 'instructions'})
            assert not following.is_error, following
            assert (await client.call_tool('map', REQUEST)).is_error
            with closing(sqlite.connect(database)) as db:
                assert db.execute('SELECT count(*) FROM work').fetchone()[0] == 0

    asyncio.run(check())


def test_hand_over_finishes_an_active_call_without_repeating_its_committed_write(installation, user_module):
    folder, _, parameters, database, _ = installation
    user_module('delayed', '''
        import anyio
        from metaform.module import Module, Verb
        from metaform.data import Node
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        async def commit(ctx):
            ticket = ctx.require_store().add_work(Node('element', 'code.alarm.audible'), None,
                                                 task='Already committed.')
            (ctx.folder / 'committed').write_text(ticket.id)
            while not (ctx.folder / 'finish').exists():
                await anyio.sleep(0.01)
            return ticket.id
        MODULE = Module(id='delayed', summary='Delayed response.', purpose='A concurrent write fixture.',
                        verbs=(Verb('commit', commit, 'Commit before waiting.'),))
    ''')

    async def check():
        async with stdio_client(parameters) as (read, write), ClientSession(read, write, 10) as client:
            await client.initialize()
            first = asyncio.create_task(client.call_tool('delayed', {'command': 'commit'}))
            try:
                async with asyncio.timeout(10):
                    while not (folder / 'committed').exists():
                        await asyncio.sleep(0.01)
                upgrade(installation)
                second = asyncio.create_task(client.call_tool('map', REQUEST))
                # The committed call remains active when the newer-schema refusal reaches the relay.
                await asyncio.sleep(0.1)
                (folder / 'finish').touch()
                await first
                result = await second
                assert not result.is_error, result
                with closing(sqlite.connect(database)) as db:
                    assert db.execute('SELECT count(*) FROM work').fetchone()[0] == 2
                    assert db.execute("SELECT count(*) FROM work WHERE task='Already committed.'").fetchone()[0] == 1
            finally:
                (folder / 'finish').touch()
                await first

    asyncio.run(check())


def test_july_connection_and_subscription_finish_across_an_upgrade(installation):
    from metaform.probe import Session, discover
    folder, _, parameters, database, _ = installation
    client = Session([parameters.command, *parameters.args], cwd=folder, env=parameters.env)
    try:
        discover(client, limit=10)
        client.open('subscriptions/listen', {'notifications': {'tools_list_changed': True}})
        upgrade(installation)
        result = client.call('map', REQUEST, limit=10)
        assert not result.get('isError'), result
        assert not client.call('map', {'command': 'work', 'arguments': {'open': True}}, limit=10).get('isError')
        with closing(sqlite.connect(database)) as db:
            assert db.execute('SELECT count(*) FROM work').fetchone()[0] == 1
    finally:
        client.close()


def test_cancellation_settles_active_and_buffered_calls_before_hand_over(installation, user_module):
    from metaform.probe import Session, discover
    folder, _, parameters, database, _ = installation
    user_module('waiting', '''
        import anyio
        from metaform.module import Module, Verb
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        async def wait(ctx):
            (ctx.folder / 'waiting').touch()
            try:
                await anyio.sleep_forever()
            finally:
                with anyio.CancelScope(shield=True):
                    await anyio.sleep(0.1)
                    (ctx.folder / 'settled').touch()
        MODULE = Module(id='waiting', summary='Waiting fixture.', purpose='A cancellation fixture.',
                        verbs=(Verb('wait', wait, 'Wait for cancellation.'),))
    ''')
    client = Session([parameters.command, *parameters.args], cwd=folder, env=parameters.env)
    try:
        discover(client, limit=10)
        active = client.open('tools/call', {'name': 'waiting', 'arguments': {'command': 'wait'}})
        deadline = time.monotonic() + 10
        while not (folder / 'waiting').exists():
            assert time.monotonic() < deadline
            time.sleep(0.01)
        upgrade(installation)
        client.open('tools/call', {'name': 'map', 'arguments': REQUEST})
        time.sleep(0.1)  # the waiting call prevents replacement while another request is buffered
        cancelled = client.open('tools/call', {'name': 'map', 'arguments': {
            **REQUEST, 'arguments': {**REQUEST['arguments'], 'task': 'Cancelled before dispatch.'}}})
        client.notify('notifications/cancelled', {'requestId': cancelled})
        client.notify('notifications/cancelled', {'requestId': active})
        result = client.call('map', {'command': 'work', 'arguments': {'open': True}}, limit=10)
        assert not result.get('isError'), result
        assert (folder / 'settled').exists()
        with closing(sqlite.connect(database)) as db:
            assert db.execute('SELECT count(*) FROM work').fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM work WHERE task='Cancelled before dispatch.'").fetchone()[0] == 0
    finally:
        client.close()


def test_flat_project_override_recovers_the_selected_store(run, installation):
    folder, _, parameters, database, _ = installation
    other = folder.parent / 'other'
    other.mkdir()
    run('add', 'project', 'other', str(other))
    parameters = parameters.model_copy(update={'cwd': other})

    async def check():
        async with stdio_client(parameters) as (read, write), ClientSession(read, write, 10) as client:
            await client.initialize()
            upgrade(installation)
            result = await client.call_tool('map', {**REQUEST, 'project': 'proj'})
            assert not result.is_error, result
            with closing(sqlite.connect(database)) as db:
                assert db.execute('SELECT count(*) FROM work').fetchone()[0] == 1

    asyncio.run(check())
