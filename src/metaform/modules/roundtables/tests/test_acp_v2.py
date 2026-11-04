"""ACP v2 acceptance, foreground completion, cancellation and agent-neutral workspaces."""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import acp
import pytest
from acp import schema as legacy
from acp.connection import StreamDirection, StreamEvent
from acp.experimental.v2 import schema

from metaform.modules.roundtables.roundtable import harness, permissions, store
from metaform.modules.roundtables.roundtable.seat import Gone, NoReply

pytestmark = pytest.mark.kind('simulation')


class Process:
    returncode = None

    def __init__(self):
        self.ended = asyncio.Event()

    async def wait(self):
        await self.ended.wait()
        return self.returncode


def made():
    session = harness.Session(1, {'position': 0, 'agent': 'claude', 'model': 'opus'}, '/tmp')
    session.process = Process()
    session.session_id = 'seat'
    session.reported = 'opus'
    session.conn = SimpleNamespace(prompt=None, cancel_session=AsyncMock())
    return session


async def state(session, activity, **given):
    raw = {'sessionUpdate': 'state_update', 'state': activity, **given}
    session.stream_event(StreamEvent(StreamDirection.INCOMING, {
        'method': 'session/update', 'params': {'sessionId': 'seat', 'update': raw}}))
    cls = {'running': schema.RunningSessionStateUpdate, 'requires_action': schema.RequiresActionSessionStateUpdate,
           'idle': schema.IdleSessionStateUpdate}[activity]
    await session.session_update('seat', cls.model_validate(raw))


async def text(session, ident, value, *, replacement=False):
    if replacement:
        update = schema.AgentMessageUpdate(message_id=ident, content=[schema.TextContentBlock(text=value)])
    else:
        update = schema.AgentMessageChunk(message_id=ident, content=schema.TextContentBlock(text=value))
    await session.session_update('seat', update)


def test_prompt_ack_and_tool_completion_do_not_complete_foreground_work():
    async def check():
        session = made()
        accepted = asyncio.Event()

        async def prompt(**kwargs):
            await state(session, 'running')
            accepted.set()
            return schema.PromptResponse(message_id='user')

        session.conn.prompt = prompt
        running = asyncio.create_task(session.prompt('Question', 1))
        await accepted.wait()
        assert not running.done()
        await text(session, 'reply', 'Old text')
        await text(session, 'reply', 'New', replacement=True)
        await text(session, 'reply', ' reply')
        await session.session_update('seat', schema.SessionToolCallUpdate(tool_call_id='read', status='completed'))
        assert not running.done()
        await state(session, 'idle', stopReason='end_turn', usage={
            'totalTokens': 15, 'inputTokens': 10, 'outputTokens': 5})
        answer, usage = await running
        assert answer == 'New reply'
        assert usage['prompt_tokens'] == 10 and usage['completion_tokens'] == 5
    asyncio.run(check())


def test_idle_before_prompt_ack_is_retained_without_losing_the_reply():
    async def check():
        session = made()

        async def prompt(**kwargs):
            await state(session, 'running')
            await text(session, 'reply', 'Already complete')
            await state(session, 'idle', stopReason='end_turn')
            return schema.PromptResponse(message_id='user')

        session.conn.prompt = prompt
        answer, _ = await session.prompt('Question', 1)
        assert answer == 'Already complete'
    asyncio.run(check())


def test_waiting_for_person_does_not_consume_the_agent_deadline():
    async def check():
        session = made()
        waiting = asyncio.Event()

        async def prompt(**kwargs):
            await state(session, 'running')
            await state(session, 'requires_action')
            waiting.set()
            return schema.PromptResponse(message_id='user')

        session.conn.prompt = prompt
        running = asyncio.create_task(session.prompt('Question', .02))
        await waiting.wait()
        await asyncio.sleep(.05)  # one deadline proof, not a state polling loop
        assert not running.done()
        session.conn.cancel_session.assert_not_awaited()
        await state(session, 'running')
        await text(session, 'reply', 'Permission answered')
        await state(session, 'idle', stopReason='end_turn')
        assert (await running)[0] == 'Permission answered'
    asyncio.run(check())


def test_v1_permission_wait_does_not_consume_the_agent_deadline(monkeypatch):
    async def check():
        from metaform.modules.roundtables.roundtable import permissions as active_permissions
        session = made()
        session.protocol = 1
        waiting, answered = asyncio.Event(), asyncio.Event()
        session.conn.cancel = AsyncMock(side_effect=lambda **kwargs: answered.set())

        async def person(*args, **kwargs):
            waiting.set()
            await answered.wait()
            return 'allow'

        monkeypatch.setattr(active_permissions, 'request', person)

        async def prompt(**kwargs):
            response = await harness.V1Client(session).request_permission(
                'seat', legacy.ToolCallUpdate(tool_call_id='write', title='Write notes'),
                [legacy.PermissionOption(option_id='allow', name='Allow once', kind='allow_once')])
            assert response.outcome.option_id == 'allow'
            await session.session_update('seat', legacy.AgentMessageChunk(
                content=legacy.TextContentBlock(text='Permission answered')))
            return legacy.PromptResponse(stop_reason='end_turn')

        session.conn.prompt = prompt
        running = asyncio.create_task(session.prompt('Question', .02))
        await waiting.wait()
        await asyncio.sleep(.05)
        assert not running.done()
        answered.set()
        assert (await running)[0] == 'Permission answered'

    asyncio.run(asyncio.wait_for(check(), 1))


def test_cancelling_prompt_sends_acp_cancel_and_waits_for_idle():
    async def check():
        session = made()
        accepted = asyncio.Event()

        async def prompt(**kwargs):
            await state(session, 'running')
            accepted.set()
            return schema.PromptResponse(message_id='user')

        async def cancel(**kwargs):
            await state(session, 'idle', stopReason='cancelled')

        session.conn.prompt = prompt
        session.conn.cancel_session.side_effect = cancel
        running = asyncio.create_task(session.prompt('Question', 1))
        await accepted.wait()
        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            await running
        session.conn.cancel_session.assert_awaited_once_with(session_id='seat')
        assert session.activity == 'idle'
    asyncio.run(check())


def test_v2_error_after_acceptance_preserves_agent_error_details():
    async def check():
        session = made()

        async def prompt(**kwargs):
            await state(session, 'running')
            await state(session, 'idle', stopReason='error', error={'code': -32000, 'message': 'Provider offline'})
            return schema.PromptResponse(message_id='user')

        session.conn.prompt = prompt
        with pytest.raises(NoReply, match='Provider offline') as error:
            await session.prompt('Question', 1)
        assert error.value.delivered
    asyncio.run(check())


def test_prompt_rejection_is_not_recorded_as_inserted():
    async def check():
        session = made()
        session.conn.prompt = AsyncMock(side_effect=acp.RequestError(-32602, 'Invalid prompt'))
        with pytest.raises(NoReply, match='Invalid prompt') as error:
            await session.prompt('Question', 1)
        assert not error.value.delivered
    asyncio.run(check())


def test_session_state_does_not_confuse_other_sessions_or_background_work():
    async def check():
        session = made()
        session.completion = asyncio.get_running_loop().create_future()
        await session.session_update('child', schema.RunningSessionStateUpdate())
        assert session.activity == 'idle'
        await state(session, 'running')
        await state(session, 'idle', stopReason='end_turn', background=[{'type': 'tool_call', 'toolCallId': 'task'}])
        assert session.activity == 'idle'
        assert session.background == [{'type': 'tool_call', 'toolCallId': 'task'}]
        assert session.completion.done()
    asyncio.run(check())


@pytest.mark.parametrize('agent', ['claude', 'codex', 'antigravity'])
def test_fake_wire_uses_v2_without_agent_specific_tool_permissions(tmp_path, monkeypatch, agent):
    project, private = tmp_path / 'project', tmp_path / 'private'
    project.mkdir()
    private.mkdir()
    log = tmp_path / 'wire.jsonl'
    fake = Path(__file__).with_name('fake_agent.py')
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    monkeypatch.setenv(f'ROUNDTABLE_AGENT_{agent.upper()}', f'{sys.executable} {fake}')
    monkeypatch.setenv('FAKE_ACP_LOG', str(log))
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'must-not-reach-the-agent')
    monkeypatch.delenv('FAKE_ACP_PERMISSION', raising=False)
    monkeypatch.delenv('FAKE_ACP_MCP', raising=False)

    async def check():
        session = harness.Session(1, {'position': 0, 'agent': agent, 'model': 'opus'}, str(private),
                                  reads=str(project), notes=str(project / 'notes'))
        try:
            await session.start()
            reply, usage = await session.prompt('Inspect the project', 5)
            assert reply.startswith('opus on turn 1:')
            assert usage['completion_tokens'] == 20
        finally:
            await session.close()

    asyncio.run(check())
    rows = [json.loads(one) for one in log.read_text().splitlines()]
    messages = [one['message'] for one in rows if 'message' in one]
    init = next(one for one in messages if one.get('method') == 'initialize')['params']
    assert init['protocolVersion'] == 2
    assert 'info' in init and 'clientCapabilities' not in init
    new = next(one for one in messages if one.get('method') == 'session/new')['params']
    assert new['cwd'] == str(project)
    assert 'claudeCode' not in new and '_meta' not in new
    assert not any(one.get('api_key') for one in rows)
    assert any(one.get('method') == 'session/close' for one in messages)


@pytest.mark.parametrize('setting', ['FAKE_ACP_PROTOCOL', 'FAKE_ACP_LEGACY_INITIALIZE', 'FAKE_ACP_UNSUPPORTED_V2'])
def test_initialize_negotiates_v1_on_a_fresh_connection(tmp_path, monkeypatch, setting):
    project = tmp_path / 'project'
    project.mkdir()
    log = tmp_path / 'wire.jsonl'
    fake = Path(__file__).with_name('fake_agent.py')
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    monkeypatch.setenv('ROUNDTABLE_AGENT_ANTIGRAVITY', f'{sys.executable} {fake}')
    monkeypatch.setenv('FAKE_ACP_LOG', str(log))
    monkeypatch.setenv(setting, '1')

    async def check():
        session = harness.Session(1, {'position': 0, 'agent': 'antigravity', 'model': 'opus'}, str(project))
        try:
            await session.start()
            assert session.protocol == 1
            assert (await session.prompt('Inspect the project', 5))[0].startswith('opus on turn 1:')
        finally:
            await session.close()

    asyncio.run(check())
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    initialized = [one for one in rows if one.get('message', {}).get('method') == 'initialize']
    assert [one['message']['params']['protocolVersion'] for one in initialized] == [2, 1]
    assert initialized[0]['pid'] != initialized[1]['pid']
    assert 'info' in initialized[0]['message']['params']
    assert 'clientInfo' in initialized[1]['message']['params']
    created = [one for one in rows if one.get('message', {}).get('method') == 'session/new']
    assert len(created) == 1 and created[0]['pid'] == initialized[1]['pid']


@pytest.mark.parametrize('setting,reason', [('FAKE_ACP_PROTOCOL', 'unsupported ACP protocol 3'),
                                            ('FAKE_ACP_INIT_ERROR', 'Authentication required'),
                                            ('FAKE_ACP_SESSION_ERROR', 'Authentication required')])
def test_unrelated_errors_and_unsupported_versions_do_not_trigger_a_protocol_retry(tmp_path, monkeypatch,
                                                                                  setting, reason):
    project = tmp_path / 'project'
    project.mkdir()
    log = tmp_path / 'wire.jsonl'
    fake = Path(__file__).with_name('fake_agent.py')
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    monkeypatch.setenv('ROUNDTABLE_AGENT_CODEX', f'{sys.executable} {fake}')
    monkeypatch.setenv('FAKE_ACP_LOG', str(log))
    monkeypatch.setenv(setting, '3' if setting == 'FAKE_ACP_PROTOCOL' else '1')

    async def check():
        session = harness.Session(1, {'position': 0, 'agent': 'codex', 'model': 'opus'}, str(project))
        with pytest.raises(Gone, match=reason):
            await session.start()
        assert not session.alive()

    asyncio.run(check())
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    initialized = [one for one in rows if one.get('message', {}).get('method') == 'initialize']
    assert len(initialized) == 1



@pytest.mark.parametrize('protocol', [1, 2])
def test_fake_wire_permission_reaches_person_and_returns_exact_selected_option(tmp_path, monkeypatch, protocol):
    project, private = tmp_path / 'project', tmp_path / 'private'
    project.mkdir()
    private.mkdir()
    log = tmp_path / 'wire.jsonl'
    fake = Path(__file__).with_name('fake_agent.py')
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    monkeypatch.setenv('ROUNDTABLE_AGENT_CLAUDE', f'{sys.executable} {fake}')
    monkeypatch.setenv('FAKE_ACP_LOG', str(log))
    monkeypatch.setenv('FAKE_ACP_PROTOCOL', str(protocol))
    monkeypatch.setenv('FAKE_ACP_PERMISSION', '1')
    monkeypatch.delenv('FAKE_ACP_MCP', raising=False)
    seats = [{'kind': 'acp', 'id': 'acp:claude/opus', 'agent': 'claude', 'model': 'opus'}]
    role = {**seats[0], 'name': 'Opus'}
    number = store.opened({'subject': 'Wire fixture', 'opening': 'Inspect the notes.', 'folder': str(project),
                           'chair_key': None, 'chair_token': 'fixture', 'reporter': seats[0]['id'],
                           'host': role, 'synthesizer': role, 'rounds': 1, 'spend': 0}, seats, judging=False)

    async def check():
        visible = asyncio.Event()
        loop = asyncio.get_running_loop()
        payload = {}

        def published(given):
            nonlocal payload
            if given['state'] == 'waiting':
                payload = given
                loop.call_soon_threadsafe(visible.set)

        session = harness.Session(number, {'position': 0, 'agent': 'claude', 'model': 'opus'}, str(private),
                                  reads=str(project), permission_event=published)
        running = None
        try:
            await session.start()
            running = asyncio.create_task(session.prompt('Inspect the notes', 5))
            await asyncio.wait_for(visible.wait(), 5)
            assert not running.done()
            assert payload['title'] == 'Write notes.txt'
            assert payload['subject']['toolCall']['toolCallId'] == 'w1'
            assert [one['optionId'] for one in payload['options']] == ['allow', 'reject']
            script = ('import sys; from metaform.modules.roundtables.roundtable import permissions; '
                      'from metaform import relay; number=int(sys.argv[1]); '
                      'permissions.answer(number,sys.argv[2],"allow"); '
                      'relay.deliver("map.changed",{"kinds":[permissions.topic(number)]})')
            result = await asyncio.to_thread(subprocess.run, [sys.executable, '-c', script,
                                                              str(number), payload['request']],
                                             env=os.environ.copy(), capture_output=True, text=True, timeout=15)
            assert result.returncode == 0, result.stderr
            answer, _ = await asyncio.wait_for(running, 5)
            assert answer.startswith('opus on turn 1:')
            saved = permissions.get(number, payload['request'])
            assert saved['state'] == 'answered' and saved['chosen'] == 'allow'
        finally:
            if running is not None and not running.done():
                running.cancel()
                await asyncio.gather(running, return_exceptions=True)
            await session.close()

    asyncio.run(check())
    rows = [json.loads(one) for one in log.read_text().splitlines()]
    permission = next(one['permission'] for one in rows if 'permission' in one)
    assert permission == {'outcome': {'optionId': 'allow', 'outcome': 'selected'}}


@pytest.mark.parametrize('protocol', [1, 2])
def test_fake_wire_cancellation_uses_the_negotiated_completion_contract(tmp_path, monkeypatch, protocol):
    project = tmp_path / 'project'
    project.mkdir()
    log = tmp_path / 'wire.jsonl'
    fake = Path(__file__).with_name('fake_agent.py')
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    monkeypatch.setenv('ROUNDTABLE_AGENT_CODEX', f'{sys.executable} {fake}')
    monkeypatch.setenv('FAKE_ACP_LOG', str(log))
    monkeypatch.setenv('FAKE_ACP_PROTOCOL', str(protocol))
    monkeypatch.setenv('FAKE_ACP_BLOCK', '1')
    monkeypatch.delenv('FAKE_ACP_PERMISSION', raising=False)

    async def check():
        blocked = asyncio.Event()
        session = harness.Session(1, {'position': 0, 'agent': 'codex', 'model': 'opus'}, str(project))
        original = session.session_update

        async def observed(session_id, update, **kwargs):
            await original(session_id, update, **kwargs)
            if getattr(update, 'tool_call_id', None) == 'blocked':
                blocked.set()

        session.session_update = observed
        running = None
        try:
            await session.start()
            running = asyncio.create_task(session.prompt('Work until cancelled', 5))
            await asyncio.wait_for(blocked.wait(), 5)
            assert not running.done()
            running.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(running, 5)
            assert session.activity == 'idle'
            assert session.alive()
        finally:
            if running is not None and not running.done():
                running.cancel()
                await asyncio.gather(running, return_exceptions=True)
            await session.close()

    asyncio.run(check())
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert sum(one.get('message', {}).get('method') == 'session/cancel' for one in rows) == 1
