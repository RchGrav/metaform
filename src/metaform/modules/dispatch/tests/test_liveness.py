"""Regression proof for stranded runners and status shared by all dispatch readers."""
import asyncio
import errno
import json
import os
import signal
import socket
import sys

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


@pytest.mark.parametrize('done', [False, True])
def test_mid_turn_messages_wait_in_order_and_cannot_replace_a_prompt(dispatch, run, tmp_path, done):
    gates = tmp_path / 'turns'
    gates.mkdir()
    dispatch.start('replace', FAKE_ACP_TURN_GATES=str(gates))
    eventually(lambda: dispatch.received('session/prompt'))
    for text in ('First message', 'Second message'):
        sent = json.loads(run('dispatch', 'message', dispatch.id, text, '--json', cwd=dispatch.folder).stdout)
        assert sent['sent'] is True
    assert len(dispatch.received('session/prompt')) == 1, 'messages must wait for the active turn'
    for number, text in ((1, 'First message'), (2, 'Second message')):
        (gates / str(number)).touch()
        prompts = eventually(lambda number=number: dispatch.received('session/prompt')
                             if len(dispatch.received('session/prompt')) == number + 1 else None)
        assert prompts[-1]['params']['prompt'] == [{'type': 'text', 'text': text}]
        assert prompts[-1]['params']['sessionId'] == 'fake-session-1'
    if done:
        run('map', 'work', 'op=done', f'id={dispatch.id}', 'resolution=Finished', cwd=dispatch.folder)
    (gates / '3').touch()
    if done:
        assert dispatch.process.wait(15) == 0, dispatch.process.stderr.read().decode()
        assert dispatch.session().extra['how'] == 'the ticket is done'
    else:  # the turn ended with the ticket open: the session stays, idle, and the ticket stays taken
        from metaform.modules.dispatch import tell
        eventually(lambda: tell(dispatch.session().extra, 'status')['activity'] == 'idle' or None)
        assert dispatch.process.poll() is None
        assert dispatch.ticket().taken
        dispatch.stop()
        dispatch.process.wait(15)
    assert not dispatch.logged('replaced'), 'no adapter request was abandoned'


def test_stop_discards_messages_waiting_for_the_active_turn(dispatch, run, tmp_path):
    gates = tmp_path / 'turns'
    gates.mkdir()
    dispatch.start('replace', FAKE_ACP_TURN_GATES=str(gates))
    eventually(lambda: dispatch.received('session/prompt'))
    run('dispatch', 'message', dispatch.id, 'Queued message', cwd=dispatch.folder)
    assert len(dispatch.received('session/prompt')) == 1
    assert json.loads(dispatch.stop().stdout)['stopped'] is True
    assert dispatch.process.wait(15) == 0
    assert len(dispatch.received('session/prompt')) == 1
    assert len(dispatch.received('session/cancel')) == 1
    assert not dispatch.logged('replaced')


def test_stop_during_queued_turn_start_does_not_send_a_prompt_after_cancel(dispatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from metaform.modules.dispatch.runner import Session

    async def exercise():
        held = Session(SimpleNamespace(nouns={}), Store('proj', module='dispatch'), dispatch.ticket(), 'codex', [])
        held.session_id = 'controlled-turn'
        held.prep = True
        held.conn = SimpleNamespace(prompt=AsyncMock(return_value=SimpleNamespace(stop_reason='end_turn')),
                                    close=AsyncMock())
        held.note = AsyncMock()
        starting, proceed = asyncio.Event(), asyncio.Event()
        calls = 0

        async def changed(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                starting.set()
                await proceed.wait()

        held.changed = changed
        held.turn('First turn')
        held.turn('Queued message')
        await asyncio.wait_for(starting.wait(), 5)
        await held.end('stopped by the person')
        proceed.set()
        await asyncio.wait_for(asyncio.gather(*tuple(held.tasks)), 5)
        assert [call.kwargs['prompt'][0].text for call in held.conn.prompt.await_args_list] == ['First turn']
        assert held.turns == 0 and held.idle.is_set() and not held.pending

    asyncio.run(exercise())


def test_interrupt_during_turn_start_prevents_the_prompt_and_keeps_chat_usable(dispatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from metaform.modules.dispatch.runner import Session

    async def exercise():
        held = Session(SimpleNamespace(nouns={}), Store('proj', module='dispatch'), dispatch.ticket(), 'codex', [])
        held.session_id = 'controlled-interrupt'
        held.prep = True
        held.process = SimpleNamespace(returncode=None)
        held.conn = SimpleNamespace(prompt=AsyncMock(return_value=SimpleNamespace(stop_reason='end_turn')),
                                    cancel=AsyncMock())
        held.note = AsyncMock()
        starting, proceed = asyncio.Event(), asyncio.Event()
        calls = 0

        async def changed(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                starting.set()
                await proceed.wait()

        held.changed = changed
        server = await asyncio.start_server(held.control, '127.0.0.1', 0)
        port = server.sockets[0].getsockname()[1]

        async def control(op, **given):
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            try:
                writer.write(json.dumps({'token': held.token, 'op': op, **given}).encode() + b'\n')
                await writer.drain()
                return json.loads(await asyncio.wait_for(reader.readline(), 5))
            finally:
                writer.close()
                await writer.wait_closed()

        try:
            assert (await control('message', text='First message'))['sent'] is True
            await asyncio.wait_for(starting.wait(), 5)
            first_turn = tuple(held.tasks)
            assert (await control('interrupt'))['requested'] is True
            proceed.set()
            await asyncio.wait_for(asyncio.gather(*first_turn), 5)
            assert held.conn.prompt.await_count == 0, 'the interrupted turn must never reach the adapter'
            status = await control('status')
            assert status['state'] == 'running' and status['activity'] == 'idle'
            assert (await control('interrupt'))['requested'] is False
            assert (await control('message', text='Continue the conversation'))['sent'] is True
            await asyncio.wait_for(asyncio.gather(*tuple(held.tasks)), 5)
            assert [call.kwargs['prompt'][0].text for call in held.conn.prompt.await_args_list] == [
                'Continue the conversation']
            status = await control('status')
            assert status['state'] == 'running' and status['activity'] == 'idle'

            later_started = asyncio.Event()
            later_answer = asyncio.get_running_loop().create_future()

            async def later_prompt(**kwargs):
                later_started.set()
                return await later_answer

            attempts = 0

            async def cancel(**kwargs):
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise OSError('Cancellation transport failed')

            held.conn.prompt.side_effect = later_prompt
            held.conn.cancel.side_effect = cancel
            assert (await control('message', text='A turn to interrupt'))['sent'] is True
            await asyncio.wait_for(later_started.wait(), 5)
            later_turn = tuple(held.tasks)
            failed = await control('interrupt')
            assert 'Cancellation transport failed' in failed['error']
            status = await control('status')
            assert status['state'] == 'running' and status['activity'] == 'working'
            assert status['interrupting'] is False, 'a failed request must leave interruption available to retry'
            assert (await control('interrupt'))['requested'] is True
            status = await control('status')
            assert status['activity'] == 'working' and status['interrupting'] is True
            later_answer.set_result(SimpleNamespace(stop_reason='cancelled'))
            await asyncio.wait_for(asyncio.gather(*later_turn), 5)
            assert attempts == 2 and later_answer.done()
            status = await control('status')
            assert status['state'] == 'running' and status['activity'] == 'idle'
        finally:
            proceed.set()
            if 'later_answer' in locals() and not later_answer.done():
                later_answer.set_result(SimpleNamespace(stop_reason='end_turn'))
            await asyncio.gather(*tuple(held.tasks), return_exceptions=True)
            server.close()
            await server.wait_closed()

    asyncio.run(exercise())


@pytest.mark.parametrize('trigger', ['change', 'agent_exit', 'stop'])
def test_schema_change_cannot_strand_a_runner_or_its_resources(dispatch, trigger):
    dispatch.start('ask')
    eventually(dispatch.questions)
    held = dispatch.session().extra
    agent_pid = dispatch.logged('pid')[0]
    path = homes.store_path('proj', dispatch.store.active_base().id)
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


def upgraded(dispatch):
    """The store at the next schema version, as a newer Metaform on disk leaves it under a runner started earlier."""
    path = homes.store_path('proj', dispatch.store.active_base().id)
    with DataConnection(path) as db:
        db.execute("UPDATE meta SET value=? WHERE key='schema_version'", (str(int(sqlite.SCHEMA_VERSION) + 1),))
    return path


@pytest.mark.req('MAP-049')
def test_dead_runner_recovery_defaults_to_manual_and_preserves_ownership(dispatch, run):
    dispatch.start('hold', FAKE_ACP_ORPHAN_HOLD='1')
    eventually(lambda: dispatch.logged('grandchild'))
    dispatch.process.kill()
    dispatch.process.wait()
    before = dispatch.ticket()
    result = json.loads(run('dispatch', 'recover', '--json', cwd=dispatch.folder).stdout)
    assert result['policy'] == 'manual' and result['released'] == []
    assert dispatch.ticket().taken_by == before.taken_by
    assert dispatch.session().extra['state'] == 'running'


@pytest.mark.req('MAP-049')
@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='safe live group cleanup requires Linux pidfds')
def test_automatic_recovery_stops_orphans_before_returning_ticket_and_preserves_progress(dispatch, run):
    from metaform.modules.dispatch.tests.test_dispatch import gone

    run('set', '--dispatch-recovery=automatic', cwd=dispatch.folder)
    run('map', 'work', 'op=plan', f'id={dispatch.id}', 'steps=2', cwd=dispatch.folder)
    run('map', 'work', 'op=step', f'id={dispatch.id}', 'said=Found the cause', cwd=dispatch.folder)
    dispatch.start('hold', FAKE_ACP_ORPHAN_HOLD='1')
    eventually(lambda: dispatch.logged('grandchild'))
    before = dispatch.ticket()
    held = dispatch.session().extra
    dispatch.process.kill()
    dispatch.process.wait()
    transcript = [(item.extra, item.value) for item in dispatch.items('note')]
    # Automatic recovery must remain a command action, never a side effect of reading a ticket or its sessions.
    shown = json.loads(run('dispatch', 'sessions', 'thread=false', '--json', cwd=dispatch.folder).stdout)
    assert shown['sessions'][0]['state'] == 'ended'
    assert dispatch.ticket().taken_by == before.taken_by
    result = json.loads(run('dispatch', 'recover', '--json', cwd=dispatch.folder).stdout)
    assert result['released'] == [dispatch.id], result
    assert gone(dispatch.logged('pid') + dispatch.logged('grandchild')), 'no abandoned worker may run on a returned ticket'
    after = dispatch.ticket()
    assert after.taken is None and after.taken_by is None and not after.held and after.done is None
    assert (after.steps, after.steps_done, after.said, after.position) == (
        before.steps, before.steps_done, before.said, before.position)
    assert dispatch.session().extra['state'] == 'ended'
    assert [(item.extra, item.value) for item in dispatch.items('note') if item.extra['kind'] != 'signal'] == transcript
    assert {'not-smooth', 'requeue'} <= {json.loads(item.value)['signal'] for item in dispatch.items('note')
                                        if item.extra['kind'] == 'signal'}
    assert not nonce.read(held['nonce']).open
    again = json.loads(run('dispatch', 'recover', '--json', cwd=dispatch.folder).stdout)
    assert again['released'] == []


@pytest.mark.req('MAP-049')
def test_automatic_recovery_leaves_live_runner_and_adapter_working(dispatch, run):
    run('set', '--dispatch-recovery=automatic', cwd=dispatch.folder)
    dispatch.start('hold', FAKE_ACP_ORPHAN_HOLD='1')
    eventually(lambda: dispatch.logged('grandchild'))
    before = dispatch.ticket()
    result = json.loads(run('dispatch', 'recover', '--json', cwd=dispatch.folder).stdout)
    assert result['released'] == []
    assert dispatch.ticket().taken_by == before.taken_by
    assert alive(dispatch.logged('pid')[0]) and dispatch.process.poll() is None
    dispatch.stop()


@pytest.mark.req('MAP-049')
@pytest.mark.parametrize('unsafe', ['legacy', 'changed_owner', 'unknown_process', 'reused_adapter'])
def test_automatic_recovery_keeps_tickets_when_safe_cleanup_cannot_be_proved(dispatch, run, monkeypatch, unsafe):
    from metaform.module import context
    from metaform.modules.dispatch import recovery

    run('set', '--dispatch-recovery=automatic', cwd=dispatch.folder)
    dispatch.start('hold', FAKE_ACP_ORPHAN_HOLD='1')
    eventually(lambda: dispatch.logged('grandchild'))
    held = dispatch.session().extra
    dispatch.process.kill()
    dispatch.process.wait()
    if unsafe == 'legacy':
        value = nonce.read(held['nonce']).value
        nonce.update(held['nonce'], value={key: value[key] for key in ('work_id', 'agent', 'session_id')})
    elif unsafe == 'changed_owner':
        dispatch.store.move_work(dispatch.id, 'todo')
        dispatch.store.take_work(dispatch.id, None, 'another agent')
    elif unsafe == 'unknown_process':
        monkeypatch.setattr(recovery, 'identity', lambda pid: None)
    else:
        value = nonce.read(held['nonce']).value
        value['recovery']['adapter_identity'] = 'a different process birth'
        nonce.update(held['nonce'], value=value)
    before = dispatch.ticket()
    result = recovery.recover(context('dispatch', dispatch.folder, project='proj'))
    assert result['released'] == []
    assert dispatch.ticket().taken_by == before.taken_by
    assert alive(dispatch.logged('pid')[0]), 'uncertain or reassigned resources must not be killed'
    if unsafe != 'changed_owner':
        [deferred] = result['deferred']
        assert deferred['work_id'] == dispatch.id and deferred['reason']
        assert deferred['next'] == f'metaform map work op=move id={dispatch.id} column=todo'


@pytest.mark.req('MAP-049')
@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='safe live group cleanup requires Linux pidfds')
def test_automatic_recovery_runs_before_autostart_selection_even_with_autostart_off(dispatch, run):
    run('set', '--dispatch-recovery=automatic', cwd=dispatch.folder)
    dispatch.start('hold', FAKE_ACP_ORPHAN_HOLD='1')
    eventually(lambda: dispatch.logged('grandchild'))
    dispatch.process.kill()
    dispatch.process.wait()
    result = json.loads(run('dispatch', 'autostart', '--json', cwd=dispatch.folder).stdout)
    assert result['started'] == []
    assert dispatch.ticket().taken is None


@pytest.mark.kind('fixture')
@pytest.mark.req('MAP-049')
def test_recovery_cannot_kill_an_adapter_pid_replaced_during_process_inspection(monkeypatch):
    from metaform.modules.dispatch import recovery

    inspected = []
    monkeypatch.setattr(recovery.os, 'name', 'posix')
    monkeypatch.setattr(recovery, 'identity', lambda pid: 'replacement' if inspected else 'original')
    monkeypatch.setattr(recovery, 'group_members', lambda pid: inspected.append(pid) or [pid])
    monkeypatch.setattr(recovery.os, 'getpgid', lambda pid: pid)

    def unexpected_kill(*args):
        pytest.fail('a recycled PID must never authorize signalling its replacement')

    monkeypatch.setattr(recovery.os, 'killpg', unexpected_kill)
    with pytest.raises(ValueError, match='cannot be verified'):
        recovery.stop_adapter({'adapter_pid': 12345, 'adapter_identity': 'original'})


@pytest.mark.kind('fixture')
@pytest.mark.req('MAP-049')
@pytest.mark.parametrize('unsupported', [False, True])
def test_recovery_signals_a_stable_group_handle_and_closes_it_on_failure(monkeypatch, unsupported):
    from metaform.modules.dispatch import recovery

    calls = []
    monkeypatch.setattr(recovery.os, 'name', 'posix')
    monkeypatch.setattr(recovery.sys, 'platform', 'linux')
    monkeypatch.setattr(recovery, 'identity', lambda pid: 'original')
    monkeypatch.setattr(recovery, 'group_members', lambda pid: [pid])
    monkeypatch.setattr(recovery.os, 'getpgid', lambda pid: pid, raising=False)
    monkeypatch.setattr(recovery.os, 'pidfd_open', lambda pid: calls.append(('open', pid)) or 42, raising=False)
    monkeypatch.setattr(recovery.os, 'close', lambda fd: calls.append(('close', fd)))

    def numeric_signal(*args):
        pytest.fail('a PID reused after the last identity check must never receive a signal')

    def stable_signal(fd, sig, info, flags):
        calls.append(('signal', fd, sig, info, flags))
        if unsupported:
            raise OSError(errno.EINVAL, 'group scope is unsupported on this kernel')
        # The recorded process exits after inspection. A stable handle cannot target its PID's replacement.
        raise ProcessLookupError('the recorded process exited')

    monkeypatch.setattr(recovery.os, 'killpg', numeric_signal, raising=False)
    monkeypatch.setattr(recovery.signal, 'pidfd_send_signal', stable_signal, raising=False)
    with pytest.raises(ValueError if unsupported else ProcessLookupError):
        recovery.stop_adapter({'adapter_pid': 12345, 'adapter_identity': 'original'})
    assert calls == [('open', 12345), ('signal', 42, signal.SIGKILL, None, 4), ('close', 42)]


@pytest.mark.kind('fixture')
@pytest.mark.req('MAP-049')
@pytest.mark.parametrize('platform', ['darwin', 'win32', 'linux'])
def test_recovery_without_safe_group_signalling_defers_without_killing(monkeypatch, platform):
    from metaform.modules.dispatch import recovery

    monkeypatch.setattr(recovery.os, 'name', 'nt' if platform == 'win32' else 'posix')
    monkeypatch.setattr(recovery.sys, 'platform', platform)
    monkeypatch.setattr(recovery, 'identity', lambda pid: 'original')
    monkeypatch.setattr(recovery, 'group_members', lambda pid: [pid])
    monkeypatch.setattr(recovery.os, 'getpgid', lambda pid: pid, raising=False)
    monkeypatch.delattr(recovery.os, 'pidfd_open', raising=False)
    monkeypatch.setattr(recovery.platform, 'machine', lambda: 'unsupported-ABI')

    def unexpected_signal(*args, **kwargs):
        pytest.fail('an unsupported platform must retain the ticket rather than signal a numeric PID')

    monkeypatch.setattr(recovery.os, 'killpg', unexpected_signal, raising=False)
    monkeypatch.setattr(recovery.subprocess, 'run', unexpected_signal)
    with pytest.raises(ValueError, match='safe process-group signalling is unavailable'):
        recovery.stop_adapter({'adapter_pid': 12345, 'adapter_identity': 'original'})


@pytest.mark.req('QUAL-015')
@pytest.mark.req('MAP-049')
@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='safe live group cleanup requires Linux pidfds')
def test_recovery_keeps_ownership_until_cleanup_finishes_without_blocking_other_writes(dispatch, run, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from metaform.module import context
    from metaform.modules.dispatch import recovery

    run('set', '--dispatch-recovery=automatic', cwd=dispatch.folder)
    dispatch.start('hold', FAKE_ACP_ORPHAN_HOLD='1')
    eventually(lambda: dispatch.logged('grandchild'))
    original = dispatch.ticket().taken_by
    dispatch.process.kill()
    dispatch.process.wait()
    reached, resume = Event(), Event()
    cleanup = recovery.stop_adapter

    def pause(held):
        reached.set()
        assert resume.wait(10)
        cleanup(held)
        assert dispatch.ticket().taken_by == original, 'release must happen only after cleanup succeeds'

    monkeypatch.setattr(recovery, 'stop_adapter', pause)
    ctx = context('dispatch', dispatch.folder, project='proj')
    with ThreadPoolExecutor(max_workers=2) as workers:
        recovering = workers.submit(recovery.recover, ctx)
        try:
            assert reached.wait(5)
            assert dispatch.ticket().taken_by == original
            # A slow OS cleanup must not hold a project write transaction or block another ticket's progress.
            writing = workers.submit(Store('proj').add_work, dispatch.node, 'unbuilt', task='Independent work')
            assert writing.result(timeout=2).id
        finally:
            resume.set()
        assert recovering.result(timeout=10)['released'] == [dispatch.id]


@pytest.mark.req('MAP-049')
@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='safe live group cleanup requires Linux pidfds')
def test_recovery_preserves_new_ownership_assigned_during_orphan_cleanup(dispatch, run, monkeypatch):
    from metaform.module import context
    from metaform.modules.dispatch import recovery

    run('set', '--dispatch-recovery=automatic', cwd=dispatch.folder)
    dispatch.start('hold', FAKE_ACP_ORPHAN_HOLD='1')
    eventually(lambda: dispatch.logged('grandchild'))
    dispatch.process.kill()
    dispatch.process.wait()
    cleanup = recovery.stop_adapter

    def reassign(held):
        cleanup(held)
        dispatch.store.move_work(dispatch.id, 'todo')
        dispatch.store.take_work(dispatch.id, None, 'new owner')

    monkeypatch.setattr(recovery, 'stop_adapter', reassign)
    result = recovery.recover(context('dispatch', dispatch.folder, project='proj'))
    assert result['released'] == []
    assert dispatch.ticket().taken_by == 'new owner'


@pytest.mark.req('MAP-049')
@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='safe live group cleanup requires Linux pidfds')
def test_autostart_can_select_recovered_ticket_only_after_old_workers_are_stopped(dispatch, run, monkeypatch):
    from metaform.module import context
    from metaform.modules import dispatch as module

    run('set', '--dispatch-recovery=automatic', '--dispatch-autostart', cwd=dispatch.folder)
    dispatch.start('hold', FAKE_ACP_ORPHAN_HOLD='1')
    eventually(lambda: dispatch.logged('grandchild'))
    dispatch.process.kill()
    dispatch.process.wait()
    selected = []

    def start(ctx):
        assert not any(alive(pid) for pid in dispatch.logged('pid') + dispatch.logged('grandchild'))
        assert dispatch.ticket().taken is None
        selected.append(ctx.nouns['id'])
        return {'work_id': ctx.nouns['id']}

    monkeypatch.setattr(module, 'start', start)
    result = module.autostart(context('dispatch', dispatch.folder, project='proj'))
    assert selected == [dispatch.id] and result['started'] == [{'work_id': dispatch.id}]


@pytest.mark.skipif(os.name == 'nt', reason='Windows ends a process without a signal it can handle')
def test_a_terminated_runner_on_a_store_upgraded_under_it_releases_through_the_code_on_disk(
        dispatch, tmp_path, monkeypatch):
    """The runner keeps the code it started with; the code on disk is newer and reads the upgraded store. Terminated,
    it still gives its ticket back and records its session ended."""
    import subprocess
    import sys
    newer = tmp_path / 'newer'
    newer.mkdir()
    (newer / 'sitecustomize.py').write_text(
        'import metaform.sqlite as s\ns.SCHEMA_VERSION = str(int(s.SCHEMA_VERSION) + 1)\n', encoding='utf-8')
    started_with = (f'import metaform.sqlite as s; s.SCHEMA_VERSION = {sqlite.SCHEMA_VERSION!r}; import runpy, sys; '
                    f"sys.argv = ['metaform', 'dispatch', 'run', {dispatch.id!r}, 'claude']; "
                    "runpy.run_module('metaform', run_name='__main__', alter_sys=True)")
    env = dispatch.env('hold', PYTHONPATH=os.pathsep.join(filter(None, [str(newer), os.environ.get('PYTHONPATH')])))
    dispatch.process = subprocess.Popen([sys.executable, '-c', started_with], cwd=dispatch.folder, env=env,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    eventually(lambda: dispatch.logged('grandchild'))
    assert dispatch.ticket().taken
    path = upgraded(dispatch)
    monkeypatch.setattr(sqlite, 'SCHEMA_VERSION', str(int(sqlite.SCHEMA_VERSION) + 1))
    try:
        dispatch.process.send_signal(signal.SIGTERM)
        assert dispatch.process.wait(20) == 0, dispatch.process.stderr.read().decode()
        assert dispatch.ticket().taken, 'a stopped agent\'s ticket waits for the person'
        assert dispatch.ticket().done is None
        assert dispatch.session().extra['state'] == 'ended'
    finally:
        with DataConnection(path) as db:
            db.execute("UPDATE meta SET value=? WHERE key='schema_version'", (str(int(sqlite.SCHEMA_VERSION) - 1),))


@pytest.mark.skipif(os.name == 'nt', reason='Windows ends a process without a signal it can handle')
def test_a_runner_that_cannot_release_its_ticket_says_so_and_how_to_put_it_back(dispatch):
    dispatch.start('hold')
    eventually(lambda: dispatch.logged('grandchild'))
    path = upgraded(dispatch)
    try:
        dispatch.process.send_signal(signal.SIGTERM)
        dispatch.process.wait(20)
        said = dispatch.process.stderr.read().decode()
        assert f'metaform map work op=move id={dispatch.id} column=todo' in said
    finally:
        with DataConnection(path) as db:
            db.execute("UPDATE meta SET value=? WHERE key='schema_version'", (sqlite.SCHEMA_VERSION,))
    assert dispatch.ticket().taken  # the record says what is left, and nothing moved it


def test_termination_during_adapter_creation_waits_for_startup_resources(dispatch, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from metaform.modules.dispatch.runner import TERMINATED, Session
    from metaform.modules.dispatch.tests.test_dispatch import FAKE

    async def exercise():
        import sys

        loop = asyncio.get_running_loop()
        created, resume = asyncio.Event(), asyncio.Event()
        launch = loop.subprocess_exec
        handler = {}
        listener = SimpleNamespace(close=Mock())
        ctx = SimpleNamespace(nouns={}, listen=lambda callback: listener, publish_async=AsyncMock())
        held = Session(ctx, Store('proj', module='dispatch'), dispatch.ticket(), 'claude', [sys.executable, str(FAKE)])

        async def paused_launch(*args, **kwargs):
            found = await launch(*args, **kwargs)
            created.set()
            await resume.wait()
            return found

        monkeypatch.setattr(loop, 'subprocess_exec', paused_launch)
        monkeypatch.setattr(loop, 'add_signal_handler', lambda sig, callback: handler.update(terminate=callback))
        monkeypatch.setattr(loop, 'remove_signal_handler', lambda sig: True)
        for key, value in dispatch.env('hold').items():
            monkeypatch.setenv(key, value)
        running = asyncio.create_task(held.run())
        try:
            await asyncio.wait_for(created.wait(), 5)
            handler['terminate']()
            # Let the termination task reach cleanup while adapter creation is still in flight.
            for _ in range(10):
                await asyncio.sleep(0)
            resume.set()
            result = await asyncio.wait_for(running, 15)
            assert result['ended'] == TERMINATED
            assert held.process.returncode is not None, 'startup must not leave an adapter after cleanup'
            assert dispatch.ticket().taken is None  # terminated before it took the ticket
            assert held.number is None or not nonce.read(held.number).open
            assert not held.recorded or dispatch.session().extra['state'] == 'ended'
        finally:
            resume.set()
            if not running.done():
                running.cancel()
            await asyncio.gather(running, return_exceptions=True)
            if held.process is not None:
                from metaform.modules.dispatch import end_group
                end_group(held.process.pid)
                await held.process.wait()

    asyncio.run(exercise())


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
    run('map', 'work', 'op=done', f'id={dispatch.id}', 'resolution=closed elsewhere', cwd=dispatch.folder)
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
    dispatch.store.finish_work(dispatch.id, 'done without announcing')
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
        held = Session(SimpleNamespace(nouns={}), Store('proj', module='dispatch'), dispatch.ticket(), 'claude', [])
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

    run('map', 'work', 'op=edit', f'id={dispatch.id}', 'glyph=kite', cwd=dispatch.folder)
    [later] = glyphed(dispatch, run, ('Later', 'kite', False))
    dispatch.start('ask')
    eventually(dispatch.questions)
    monkeypatch.setattr(module, 'tell', lambda *args, **kwargs: {'error': 'No request status.'})
    [found] = module.sessions(Store('proj', module='dispatch'))
    assert found['state'] == 'running'
    ctx = SimpleNamespace(folder=dispatch.folder, project='proj')
    with pytest.raises(Stop, match=dispatch.id):
        module.startable(ctx, dispatch.store, dispatch.store.ticket(later).work, 'claude')
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
    elsewhere = dispatch.store.add_work(Node('element', 'code.engine'), 'unbuilt', task='Another ticket').id
    with monkeypatch.context() as older:  # a runner with no status to give
        older.setattr(module, 'tell', lambda *args, **kwargs: {'error': 'No request status.'})
        assert module.session_status(store, held)['state'] == 'running'
        assert module.session_status(store, {**held, 'work_id': elsewhere})['state'] == 'ended', \
            "a runner's pid recorded for another work id, with no reply of that session, is not that ticket's runner"
    dispatch.stop()


def test_turn_activity_waits_then_a_turn_ending_with_the_ticket_open_leaves_the_session_idle(dispatch, run):
    from metaform.modules.dispatch import tell

    dispatch.start('ask', FAKE_ACP_HOLD_LATER='1')
    [question] = eventually(dispatch.questions)
    held = dispatch.session().extra
    assert tell(held, 'status')['activity'] == 'waiting'
    run('map', 'reply', question.id, 'answer=Allow once', cwd=dispatch.folder)
    eventually(lambda: tell(held, 'status')['activity'] == 'idle' or None)
    [shown] = sessions(Store('proj', module='dispatch'))
    assert shown['state'] == 'running' and alive(held['pid']) and dispatch.ticket().taken
    dispatch.stop()


@pytest.mark.parametrize('tied', [False, True])
def test_legacy_activity_uses_transcript_evidence_without_rewriting_lifecycle(dispatch, monkeypatch, tied):
    from metaform.modules import dispatch as module

    dispatch.start('hold')
    eventually(lambda: dispatch.logged('grandchild'))
    monkeypatch.setattr(module, 'tell', lambda *args, **kwargs: {'error': 'No request status.'})
    store = Store('proj', module='dispatch')
    held = dispatch.session().extra
    with store.tables() as tx:  # the transcript of an older runner whose turn ended
        tx.insert('lines', {'session_id': held['session_id'], 'name': 'turn', 'work_id': dispatch.id,
                            'kind': 'turn', 'text': 'The turn ended: end_turn.', 'seq': 900})
    [shown] = module.sessions(store)
    assert shown['state'] == 'running' and shown['activity'] == 'idle'
    assert dispatch.session().extra['state'] == 'running'
    held = dispatch.session().extra
    with store.tables() as tx:
        tx.insert('lines', {'session_id': held['session_id'], 'name': 'later', 'work_id': dispatch.id,
                            'kind': 'agent_message_chunk', 'text': 'Resuming', 'seq': 1000})
        if tied:
            tx.insert('lines', {'session_id': held['session_id'], 'name': 'zz-turn', 'work_id': dispatch.id,
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
        held = Session(SimpleNamespace(publish_async=changed, nouns={}), Store('proj', module='dispatch'),
                       dispatch.ticket(), 'claude', [])
        held.session_id = 'controlled-turn'
        held.chat_question = 'chat'  # a person's chat session lives between turns; a work session ends at the turn
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
