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
        db.execute("UPDATE meta SET value=? WHERE key IN ('schema_version', 'compatible_from')", (newer,))


# One durable write an agent may make over the tool, MAP-050: a ticket is the person's to write, so the write under
# test is a tag on the intake layer, one op in the log.
REQUEST = {'layer': 'intake', 'tag': 'recovered'}
WRITTEN = "SELECT count(*) FROM ops WHERE data LIKE '%recovered%'"



@pytest.mark.parametrize(('changed', 'recovery'), [(True, 'relay'), (False, 'relay'), (True, 'manual')])
def test_live_connection_recovers_only_when_newer_code_is_available(run, installation, changed, recovery):
    folder, _, parameters, database, _ = installation
    run('set', '--mcp-recovery', recovery, cwd=folder)

    async def check():
        async with stdio_client(parameters) as (read, write), ClientSession(read, write, 10) as client:
            await client.initialize()
            # Force the live process to read the original project's schema before replacing its source.
            before = await client.call_tool('map_work', {'open': True})
            assert not before.is_error
            upgrade(installation, changed)
            async with asyncio.timeout(20):
                result = await client.call_tool('map_tag', REQUEST)
                following = await client.call_tool('map_work', {'open': True})
            if changed and recovery == 'relay':
                assert not result.is_error, result
                assert not following.is_error, following
                # Check durable rows directly: replay must write the tag exactly once.
                with closing(sqlite.connect(database)) as db:
                    assert db.execute(WRITTEN).fetchone()[0] == 1
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
            refusal = client.call('map_tag', REQUEST, limit=10)
            assert refusal.get('isError'), refusal
            # every block: the old server answers it, and a once-per-session notice may come first
            assert 'schema version' in ' '.join(block['text'] for block in refusal['content'])
            assert not client.call('metaform_instructions', {}, limit=10).get('isError')
            assert client.call('map_tag', REQUEST, limit=10).get('isError')
            with closing(sqlite.connect(database)) as db:
                assert db.execute('SELECT count(*) FROM work').fetchone()[0] == 0
        finally:
            client.close()
        return

    async def check():
        async with stdio_client(parameters) as (read, write), ClientSession(read, write, 10) as client:
            await client.initialize()
            damage()
            refusal = await client.call_tool('map_tag', REQUEST)
            assert refusal.is_error
            assert 'schema version' in ' '.join(block.text for block in refusal.content)
            following = await client.call_tool('metaform_instructions', {})
            assert not following.is_error, following
            assert (await client.call_tool('map_tag', REQUEST)).is_error
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
            first = asyncio.create_task(client.call_tool('delayed_commit', {}))
            try:
                async with asyncio.timeout(10):
                    while not (folder / 'committed').exists():
                        await asyncio.sleep(0.01)
                upgrade(installation)
                second = asyncio.create_task(client.call_tool('map_tag', REQUEST))
                # The committed call remains active when the newer-schema refusal reaches the relay.
                await asyncio.sleep(0.1)
                (folder / 'finish').touch()
                await first
                result = await second
                assert not result.is_error, result
                with closing(sqlite.connect(database)) as db:
                    assert db.execute('SELECT count(*) FROM work').fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM work WHERE task='Already committed.'").fetchone()[0] == 1
                    assert db.execute(WRITTEN).fetchone()[0] == 1
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
        result = client.call('map_tag', REQUEST, limit=10)
        assert not result.get('isError'), result
        assert not client.call('map_work', {'open': True}, limit=10).get('isError')
        with closing(sqlite.connect(database)) as db:
            assert db.execute(WRITTEN).fetchone()[0] == 1
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
        active = client.open('tools/call', {'name': 'waiting_wait', 'arguments': {}})
        deadline = time.monotonic() + 10
        while not (folder / 'waiting').exists():
            assert time.monotonic() < deadline
            time.sleep(0.01)
        upgrade(installation)
        client.open('tools/call', {'name': 'map_tag', 'arguments': REQUEST})
        time.sleep(0.1)  # the waiting call prevents replacement while another request is buffered
        cancelled = client.open('tools/call', {'name': 'map_tag', 'arguments': {
            **REQUEST, 'tag': 'cancelled'}})
        client.notify('notifications/cancelled', {'requestId': cancelled})
        client.notify('notifications/cancelled', {'requestId': active})
        result = client.call('map_work', {'open': True}, limit=10)
        assert not result.get('isError'), result
        assert (folder / 'settled').exists()
        with closing(sqlite.connect(database)) as db:
            assert db.execute(WRITTEN).fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM ops WHERE data LIKE '%cancelled%'").fetchone()[0] == 0
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
            result = await client.call_tool('map_tag', {**REQUEST, 'project': 'proj'})
            assert not result.is_error, result
            with closing(sqlite.connect(database)) as db:
                assert db.execute(WRITTEN).fetchone()[0] == 1

    asyncio.run(check())


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='reads the server\'s children with ps --ppid')
def test_a_code_change_on_disk_is_served_by_one_successor_replaced_in_place(installation):
    """A server keeps the code it imported, so one an agent started hours before served old code, or a file it read
    half written. A tool call after the package's code changed on disk is served by a successor on that code, with no
    schema change; a second change replaces that successor rather than adding a third process."""
    import subprocess

    from metaform.probe import Session, discover
    folder, copied, parameters, _, _ = installation
    source = copied / 'modules' / 'mcp' / 'catalog.py'
    original = source.read_text()

    def change(mark):
        source.write_text(original.replace("return prompt_files.module('mcp', 'category_'",
                                           f"return '{mark} ' + prompt_files.module('mcp', 'category_'"))
        state = source.stat()
        os.utime(source, (state.st_atime, state.st_mtime + 2))  # bytecode checks whole seconds

    def listed():
        return ' '.join(block['text'] for block in client.call('metaform_catalog', {}, limit=20)['content'])

    def successors():
        found = subprocess.run(['ps', '--ppid', str(client.process.pid), '-o', 'pid=,args='], capture_output=True,
                               text=True, check=False).stdout.splitlines()
        return [line.split()[0] for line in found if 'mcp serve' in line]
    client = Session([parameters.command, *parameters.args], cwd=folder, env=parameters.env)
    try:
        discover(client, limit=10)
        assert 'CHANGED' not in listed() and successors() == []
        change('CHANGED')
        assert 'CHANGED' in listed()
        first = successors()
        assert len(first) == 1
        change('CHANGED AGAIN')
        assert 'CHANGED AGAIN' in listed()
        second = successors()
        assert len(second) == 1 and second != first
    finally:
        client.close()


@pytest.mark.parametrize('opening', ['initialize', 'discover, then a refused initialize'])
def test_a_successor_serves_in_the_era_the_client_opened(installation, opening):
    """The client's first request fixes the connection's era, so a successor taking over after a code change must open
    in that era. Claude Code probes with server/discover and, when the probe times out on a server slow to start,
    sends initialize as well; the server had read the probe first, so it refuses the initialize and the connection
    stays July. Before 2026-10-19 the relay replayed that refused initialize to the successor, which then served the
    handshake era and refused every enveloped request, an agent's check-in among them (code.server.tool#24)."""
    folder, copied, parameters, _, _ = installation
    source = copied / 'modules' / 'mcp' / 'catalog.py'
    original = source.read_text()

    def change():
        source.write_text(original.replace("return prompt_files.module('mcp', 'category_'",
                                           "return 'CHANGED ' + prompt_files.module('mcp', 'category_'"))
        state = source.stat()
        os.utime(source, (state.st_atime, state.st_mtime + 2))  # bytecode checks whole seconds

    if opening == 'initialize':
        async def check():
            async with stdio_client(parameters) as (read, write), ClientSession(read, write, 10) as client:
                await client.initialize()
                assert not (await client.call_tool('metaform_catalog', {})).is_error
                change()
                async with asyncio.timeout(20):
                    served = await client.call_tool('metaform_catalog', {})
                    following = await client.call_tool('metaform_catalog', {})
                assert not served.is_error and not following.is_error, served
                assert 'CHANGED' in ' '.join(block.text for block in served.content)

        asyncio.run(check())
        return

    from metaform.probe import Session, discover
    client = Session([parameters.command, *parameters.args], cwd=folder, env=parameters.env)
    try:
        discover(client, limit=10)
        with pytest.raises(RuntimeError, match='initialize failed'):
            client.request('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {},
                                          'clientInfo': {'name': 'claude-code', 'version': '2.1.300'}},
                           deadline=time.monotonic() + 10)
        discover(client, limit=10)
        assert not client.call('metaform_catalog', {}, limit=10).get('isError')
        change()
        served = client.call('metaform_catalog', {}, limit=20)
        assert not served.get('isError'), served
        assert 'CHANGED' in ' '.join(block['text'] for block in served['content'])
        assert not client.call('metaform_catalog', {}, limit=10).get('isError')
    finally:
        client.close()
