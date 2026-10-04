"""Regression proof for stranded runners and status shared by all dispatch readers."""
import asyncio
import json
import os
import signal
import socket

import pytest

from metaform import home as homes
from metaform import nonce, relay, sqlite
from metaform.data import DataConnection, Store
from metaform.modules.dispatch import sessions, work_read
from metaform.modules.dispatch.tests.test_dispatch import Dispatch, alive, eventually

pytestmark = [pytest.mark.kind('simulation'), pytest.mark.req('BASE-052'), pytest.mark.req('VIEW-039')]


@pytest.fixture
def dispatch(run, home, project_folder, tmp_path):
    from metaform.modules.dispatch import end_group
    made = Dispatch(run, home, project_folder, tmp_path)
    try:
        yield made
    finally:
        made.close()
        for pid in made.logged('pid'):
            end_group(pid)


@pytest.mark.parametrize('trigger', ['change', 'agent_exit', 'stop'])
def test_schema_change_cannot_strand_a_runner_or_its_resources(dispatch, trigger):
    dispatch.start('ask')
    eventually(dispatch.questions)
    held = dispatch.session().extra
    agent_pid = dispatch.logged('pid')[0]
    path = homes.store_path('proj', dispatch.store.active_metaform().metaform_id)
    with DataConnection(path) as db:
        db.execute("UPDATE meta SET value=? WHERE key='schema_version'", (str(int(sqlite.SCHEMA_VERSION) + 1),))
    try:
        if trigger == 'change':
            relay.deliver('map.changed', {'project': 'proj'})
        elif trigger == 'agent_exit':
            os.kill(agent_pid, signal.SIGTERM)
        else:
            from metaform.modules.dispatch import tell
            try:
                tell(held, 'stop', limit=3)
            except (OSError, ValueError):
                pass
        eventually(lambda: dispatch.process.poll() is not None, limit=20)
        assert not alive(agent_pid), 'the ACP adapter must end even when persistence fails'
        with pytest.raises(OSError):
            socket.create_connection(('127.0.0.1', held['port']), timeout=1)
        assert not list((dispatch.home / 'run' / 'listeners').glob(f'dispatch-{held["pid"]}-*.json'))
        assert not nonce.read(held['nonce']).open
    finally:
        with DataConnection(path) as db:
            db.execute("UPDATE meta SET value=? WHERE key='schema_version'", (sqlite.SCHEMA_VERSION,))
    # The failed old-schema write leaves a historical running row; readers must verify it.
    assert dispatch.session().extra['state'] == 'running'
    [found] = sessions(Store('proj', module='dispatch'))
    assert found['state'] == 'ended'


def test_completed_ticket_and_runner_death_have_one_status_on_every_surface(dispatch, run):
    from types import SimpleNamespace

    from metaform.modules.mcp.tests.test_mcp import called, session, text

    dispatch.start('ask')
    eventually(dispatch.questions)
    raw = dispatch.session().extra
    run('enable', 'mcp')

    async def read(client, _):
        return json.loads(text(await called(client, 'dispatch_sessions', {'thread': False}))[-1])['sessions']

    def shown():
        cli = json.loads(run('dispatch', 'sessions', 'thread=false', '--json', cwd=dispatch.folder).stdout)['sessions']
        mcp = session(dispatch.home, dispatch.folder, read)
        record = work_read(SimpleNamespace(store=Store('proj', module='dispatch')), dispatch.ticket())['sessions']
        assert cli == mcp == record
        assert not {'pid', 'port', 'token', 'nonce'} & set(cli[0])
        return cli[0]

    assert shown()['state'] == 'running'
    # Kill only the test runner, leaving the same stale row the original failure left.
    dispatch.process.kill()
    dispatch.process.wait()
    assert shown()['state'] == 'ended'
    run('map', 'work', 'op=done', f'id={dispatch.work_id}', 'resolution=closed elsewhere', cwd=dispatch.folder)
    assert shown()['state'] == 'ended'
    assert raw['state'] == 'running'  # reads do not rewrite history
    from metaform.modules.dispatch import end_group
    end_group(dispatch.logged('pid')[0])


def test_live_runner_checks_adapter_and_completed_ticket_without_waiting_for_a_turn(dispatch):
    from metaform.modules.dispatch import tell

    dispatch.start('ask')
    eventually(dispatch.questions)
    held = dispatch.session().extra
    found = tell(held, 'status', limit=2)
    assert found['session_id'] == held['session_id'] and found['state'] == 'running'
    assert found['agent_alive'] is True
    # Suppress the relay so the read itself has to see that the ticket is done.
    dispatch.store.finish_work(dispatch.work_id, 'done without announcing')
    [found] = sessions(Store('proj', module='dispatch'))
    assert found['state'] == 'ended' and found['how'] == 'the ticket is done'
    assert dispatch.session().extra['state'] == 'running'


def test_stop_releases_the_runner_when_its_client_disconnects_before_the_reply(dispatch):
    from types import SimpleNamespace

    from metaform.modules.dispatch.runner import Session

    class Disconnected:
        def write(self, data):
            assert json.loads(data)['stopped'] is True

        async def drain(self):
            raise BrokenPipeError('the stop client disconnected')

        def close(self):
            pass

    async def stop():
        held = Session(SimpleNamespace(), Store('proj', module='dispatch'), dispatch.ticket(), 'claude', [])
        reader = asyncio.StreamReader()
        reader.feed_data(json.dumps({'op': 'stop', 'token': held.token}).encode() + b'\n')
        await held.control(reader, Disconnected())
        assert held.over.is_set() and held.ended.is_set()

    asyncio.run(stop())


@pytest.mark.req('VIEW-040')
def test_an_older_runner_without_status_whose_pid_is_that_runner_reads_running_and_keeps_its_glyph(
        dispatch, run, monkeypatch):
    """Found 2026-10-03 with the ghost agents: an older runner that cannot answer status is running when its recorded
    pid is that runner for that work id; it is not given a state of its own."""
    from types import SimpleNamespace

    from metaform.module import Stop
    from metaform.modules import dispatch as module
    from metaform.modules.dispatch.tests.test_dispatch import glyphed

    run('map', 'work', 'op=edit', f'id={dispatch.work_id}', 'glyph=kite', cwd=dispatch.folder)
    [later] = glyphed(dispatch, run, ('Later', 'kite', False))
    dispatch.start('ask')
    eventually(dispatch.questions)
    monkeypatch.setattr(module, 'tell', lambda *args, **kwargs: {'error': 'No request status.'})
    [found] = module.sessions(Store('proj', module='dispatch'))
    assert found['state'] == 'running'
    ctx = SimpleNamespace(folder=dispatch.folder, project='proj')
    with pytest.raises(Stop, match=dispatch.work_id):
        module.startable(ctx, dispatch.store, dispatch.store.ticket(later).work)
    assert dispatch.session().extra['state'] == 'running'


def test_a_recorded_pid_that_is_not_that_runner_for_that_work_id_reads_ended(dispatch, monkeypatch):
    """Found 2026-10-03 with the ghost agents: af6baee6's recorded pid belonged to another process, and 4c7dd809's
    pid ran the runner of 4ed7c64f; each was shown as an agent at work."""
    from metaform.data import Node
    from metaform.modules import dispatch as module

    dispatch.start('ask')
    eventually(dispatch.questions)
    held = dispatch.session().extra
    store = Store('proj', module='dispatch')
    assert module.session_status(store, held)['state'] == 'running'
    other = os.getpid()  # this test's own process, alive and no runner
    assert module.session_status(store, {**held, 'pid': other})['state'] == 'ended'
    assert module.session_status(store, {**held, 'session_id': 'another'})['state'] == 'ended', \
        'a port that answers for another session is not this session\'s runner'
    elsewhere = dispatch.store.add_work(Node('element', 'code.engine'), 'missing', task='Another ticket').work_id
    with monkeypatch.context() as older:  # a runner with no status to give
        older.setattr(module, 'tell', lambda *args, **kwargs: {'error': 'No request status.'})
        assert module.session_status(store, held)['state'] == 'running'
        assert module.session_status(store, {**held, 'work_id': elsewhere})['state'] == 'ended', \
            "a runner's pid recorded for another work id, with no reply of that session, is not that ticket's runner"
    dispatch.stop()


def test_turn_activity_waits_ends_and_resumes_without_ending_the_session(dispatch, run):
    from metaform.modules.dispatch import tell

    dispatch.start('ask', FAKE_ACP_HOLD_LATER='1')
    [question] = eventually(dispatch.questions)
    held = dispatch.session().extra
    assert tell(held, 'status')['activity'] == 'waiting'
    run('map', 'reply', question.message_id, 'answer=Allow once', cwd=dispatch.folder)
    eventually(lambda: tell(held, 'status').get('activity') == 'idle')
    [shown] = sessions(Store('proj', module='dispatch'))
    assert shown['state'] == 'running' and shown['activity'] == 'idle'
    assert alive(held['pid']) and dispatch.ticket().taken_by == 'claude fake-session-1'

    assert tell(held, 'message', text='Continue')['sent'] is True
    eventually(lambda: len(dispatch.received('session/prompt')) == 2)
    assert tell(held, 'status')['activity'] == 'working'
    [shown] = sessions(Store('proj', module='dispatch'))
    assert shown['state'] == 'running' and shown['activity'] == 'working'
    assert shown['pid'] == held['pid'], 'one live process spans idle and working turns'
    dispatch.stop()


@pytest.mark.parametrize('tied', [False, True])
def test_legacy_activity_uses_transcript_evidence_without_rewriting_lifecycle(dispatch, monkeypatch, tied):
    from metaform.modules import dispatch as module

    dispatch.start('ask')
    [question] = eventually(dispatch.questions)
    dispatch.run('map', 'reply', question.message_id, 'answer=Allow once', cwd=dispatch.folder)
    eventually(lambda: [item for item in dispatch.items('note') if item.extra['update'] == 'turn'])
    monkeypatch.setattr(module, 'tell', lambda *args, **kwargs: {'error': 'No request status.'})
    store = Store('proj', module='dispatch')
    [shown] = module.sessions(store)
    assert shown['state'] == 'running' and shown['activity'] == 'idle'
    assert dispatch.session().extra['state'] == 'running'
    held = dispatch.session().extra
    with store.tables() as tx:
        tx.insert('lines', {'session_id': held['session_id'], 'name': 'later', 'work_id': dispatch.work_id,
                            'kind': 'agent_message_chunk', 'text': 'Resuming', 'seq': 1000})
        if tied:
            tx.insert('lines', {'session_id': held['session_id'], 'name': 'zz-turn', 'work_id': dispatch.work_id,
                                'kind': 'turn', 'text': 'The turn ended: end_turn.', 'seq': 1000})
    [shown] = module.sessions(store)
    assert shown['state'] == 'running' and shown['activity'] == 'unknown'
    assert 'activity' not in dispatch.session().extra
    dispatch.stop()


def test_working_turn_end_and_resume_publish_activity_without_an_adapter_restart(dispatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from metaform.modules.dispatch.runner import Session

    async def exercise():
        changed = AsyncMock()
        held = Session(SimpleNamespace(publish_async=changed), Store('proj', module='dispatch'),
                       dispatch.ticket(), 'claude', [])
        held.session_id = 'controlled-turn'
        held.process = SimpleNamespace(returncode=None)
        answer = asyncio.get_running_loop().create_future()
        held.conn = SimpleNamespace()

        # A controlled remote turn lets us observe both sides of end_turn without racing a fast adapter.
        async def prompt(**kwargs):
            return await answer

        held.conn.prompt = prompt
        replies = []

        class Writer:
            def write(self, data):
                replies.append(json.loads(data))

            async def drain(self):
                pass

            def close(self):
                pass

        async def status():
            reader = asyncio.StreamReader()
            reader.feed_data(json.dumps({'op': 'status', 'token': held.token}).encode() + b'\n')
            await held.control(reader, Writer())
            return replies[-1]

        held.turn('First turn')
        assert (await status())['activity'] == 'working'
        await asyncio.sleep(0)
        answer.set_result(SimpleNamespace(stop_reason='end_turn'))
        await asyncio.gather(*tuple(held.tasks))
        idle = await status()
        assert idle['state'] == 'running' and idle['activity'] == 'idle' and idle['agent_alive'] is True
        assert changed.await_count >= 2, 'turn start and end both announce a dispatch refresh'

        answer = asyncio.get_running_loop().create_future()
        held.turn('Resume')
        assert (await status())['activity'] == 'working'
        await asyncio.sleep(0)
        answer.set_result(SimpleNamespace(stop_reason='end_turn'))
        await asyncio.gather(*tuple(held.tasks))
        assert (await status())['activity'] == 'idle'
        assert dispatch.ticket().done is None

    asyncio.run(exercise())
