"""Optional native compression retains the conversation and waits for a confirmed lifecycle outcome."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import acp
import pytest
from acp import schema as legacy
from acp.connection import Connection, StreamDirection, StreamEvent
from acp.experimental.v2 import schema

from metaform.modules.roundtables.roundtable import harness
from metaform.modules.roundtables.roundtable.seat import NoReply, Seat

pytestmark = pytest.mark.kind('simulation')


class Process:
    returncode = None

    def __init__(self):
        self.ended = asyncio.Event()

    async def wait(self):
        await self.ended.wait()
        return self.returncode


def native(protocol, monkeypatch, *, outcome='completed', command=True, summary=None):
    row = {'position': 0, 'id': 'acp:codex/sol', 'name': 'Participant', 'agent': 'codex', 'model': 'sol',
           'session': 'existing-native-conversation',
           'messages': [{'role': 'user', 'content': 'Earlier decisions and source references.'}]}
    seat = harness.AcpSeat({'number': 1, 'folder': '/tmp'}, row, lambda cost: None)
    seat.system = 'Original instructions.'
    session = harness.Session(1, row, '/tmp')
    session.protocol = protocol
    session.session_id = row['session']
    session.process = Process()
    session.reported = 'sol'
    session.on_sent = seat.delivered
    session.conn = SimpleNamespace(prompt=None, cancel_session=AsyncMock(), cancel=AsyncMock())
    seat.session_made = session
    calls = []
    monkeypatch.setattr(harness, 'said', lambda name, **values: 'Prepare for next topic: ' + values['topic'])
    models = schema if protocol == 2 else legacy

    async def state(activity, **values):
        if protocol == 2:
            cls = schema.RunningSessionStateUpdate if activity == 'running' else schema.IdleSessionStateUpdate
            await session.session_update(row['session'], cls.model_validate({'state': activity, **values}))

    async def prompt(**values):
        text = values['prompt'][0].text
        calls.append((values['session_id'], text))
        await state('running')
        if text == '/compact':
            if outcome:
                cls = schema.SessionCompactionUpdate if protocol == 2 else legacy.SessionUpdateCompactionUpdate
                await session.session_update(row['session'], cls(
                    compaction_id='native-compact', status=outcome,
                    **({'summary': [models.TextContentBlock(text=summary)]} if summary else {}),
                    **({'error': 'Compression was refused.'} if outcome == 'failed' else {})))
        else:
            await session.session_update(row['session'], models.AgentMessageChunk(
                **({'message_id': 'carry-note'} if protocol == 2 else {}),
                content=models.TextContentBlock(text='Retain the release decision and source path for the next topic.')))
        await state('idle', stopReason='end_turn')
        return schema.PromptResponse(message_id='command') if protocol == 2 else legacy.PromptResponse(stop_reason='end_turn')

    session.conn.prompt = prompt

    async def advertise():
        await session.session_update(row['session'], models.AvailableCommandsUpdate(available_commands=[
            models.AvailableCommand(name='compact', description='Compress this conversation.')] if command else []))

    return seat, session, calls, advertise


@pytest.mark.parametrize('protocol', [1, 2])
def test_native_compaction_prepares_the_selected_topic_without_replacing_the_conversation(monkeypatch, protocol):
    async def check():
        seat, session, calls, advertise = native(protocol, monkeypatch)
        await advertise()
        assert await seat.compress('Staying in sync: preserve event ordering and the open recovery question.', 1)
        assert [text for _, text in calls] == [
            'Prepare for next topic: Staying in sync: preserve event ordering and the open recovery question.', '/compact']
        assert all(ident == 'existing-native-conversation' for ident, _ in calls)
        assert seat.session == session.session_id == 'existing-native-conversation'
        assert seat.session_made is session and session.alive()
        assert len(seat.messages) == 2 and 'Original instructions.' in seat.messages[0]['content']
        assert 'Staying in sync' in seat.messages[0]['content']
        assert 'release decision' in seat.messages[1]['content']
        assert seat.extra['compaction_usage'] == {'prepare': {'model': 'sol'}, 'compact': {'model': 'sol'}}
    asyncio.run(check())


@pytest.mark.parametrize('protocol', [1, 2])
@pytest.mark.parametrize('outcome', ['failed', None])
def test_failed_or_unconfirmed_compaction_keeps_prior_history_and_native_session(monkeypatch, protocol, outcome):
    async def check():
        seat, session, _, advertise = native(protocol, monkeypatch, outcome=outcome)
        await advertise()
        original = list(seat.messages)
        with pytest.raises(NoReply, match='refused|did not confirm'):
            await seat.compress('The next topic.', 1)
        assert seat.messages[:len(original)] == original
        assert seat.session == session.session_id == 'existing-native-conversation'
        assert seat.session_made is session and session.alive()
        assert seat.extra['compaction_usage'] == {'prepare': {'model': 'sol'}, 'compact': None}
    asyncio.run(check())


@pytest.mark.parametrize('protocol', [1, 2])
def test_a_successful_textless_compact_command_does_not_make_an_empty_discussion_reply_valid(monkeypatch, protocol):
    async def check():
        _, session, _, advertise = native(protocol, monkeypatch)
        await advertise()
        assert (await session.prompt('/compact', 1, compact=True))[0] == ''
        with pytest.raises(NoReply, match='wrote no text'):
            await session.prompt('/compact', 1)
    asyncio.run(check())


@pytest.mark.parametrize('protocol', [1, 2])
def test_an_agent_without_native_compaction_is_left_untouched(monkeypatch, protocol):
    async def check():
        seat, session, calls, advertise = native(protocol, monkeypatch, command=False)
        await advertise()
        original = list(seat.messages)
        assert await seat.compress('The next topic.', 1) is False
        assert not calls and seat.messages == original
        assert seat.session == session.session_id == 'existing-native-conversation'
    asyncio.run(check())


@pytest.mark.parametrize('protocol', [1, 2])
def test_an_old_compaction_completion_cannot_confirm_a_later_command(monkeypatch, protocol):
    async def check():
        _, session, _, advertise = native(protocol, monkeypatch)
        await advertise()
        cls = schema.SessionCompactionUpdate if protocol == 2 else legacy.SessionUpdateCompactionUpdate
        await session.session_update('existing-native-conversation', cls(
            compaction_id='native-compact', status='completed'))
        with pytest.raises(NoReply, match='did not confirm'):
            await session.prompt('/compact', 1, compact=True)
    asyncio.run(check())


@pytest.mark.parametrize('protocol', [1, 2])
def test_native_retained_summary_is_the_local_context_estimate(monkeypatch, protocol):
    async def check():
        seat, _, _, advertise = native(protocol, monkeypatch, summary='The native retained summary and evidence.')
        await advertise()
        assert await seat.compress('Next topic.', 1)
        assert seat.messages[1]['content'] == 'The native retained summary and evidence.'
    asyncio.run(check())


def test_preparation_and_compaction_wait_for_native_completion_without_aborting_work(monkeypatch):
    async def check():
        seat, session, _, advertise = native(2, monkeypatch)
        await advertise()
        original = session.conn.prompt
        prepare_started, release_prepare = asyncio.Event(), asyncio.Event()
        compact_started = asyncio.Event()

        async def prompt(**values):
            if values['prompt'][0].text != '/compact':
                prepare_started.set()
                await release_prepare.wait()
                return await original(**values)
            await session.session_update(session.session_id, schema.RunningSessionStateUpdate())
            compact_started.set()
            return schema.PromptResponse(message_id='compact')

        session.conn.prompt = prompt
        session.close = AsyncMock()
        work = asyncio.create_task(seat.compress('Next topic.', .005))
        await prepare_started.wait()
        await asyncio.sleep(.02)
        assert not work.done()
        session.conn.cancel_session.assert_not_awaited()
        session.close.assert_not_awaited()
        release_prepare.set()
        await compact_started.wait()
        await asyncio.sleep(.02)
        assert not work.done()
        session.conn.cancel_session.assert_not_awaited()
        await session.session_update(session.session_id, schema.SessionCompactionUpdate(
            compaction_id='requested-compression', status='completed'))
        await session.session_update(session.session_id, schema.IdleSessionStateUpdate(stop_reason='end_turn'))
        assert await asyncio.wait_for(work, 1)
        assert seat.session == 'existing-native-conversation'
        session.close.assert_not_awaited()
    asyncio.run(check())


@pytest.mark.parametrize('protocol', [1, 2])
def test_native_discussion_survives_the_old_short_work_deadline(monkeypatch, protocol):
    async def check():
        seat, session, _, _ = native(protocol, monkeypatch)
        original = session.conn.prompt
        started, release = asyncio.Event(), asyncio.Event()

        async def prompt(**values):
            started.set()
            await release.wait()
            return await original(**values)

        session.conn.prompt = prompt
        session.close = AsyncMock()
        work = asyncio.create_task(seat.reply('Continue the design work.', .005))
        await started.wait()
        await asyncio.sleep(.02)
        assert not work.done() and seat.busy()
        session.conn.cancel_session.assert_not_awaited()
        session.conn.cancel.assert_not_awaited()
        session.close.assert_not_awaited()
        release.set()
        assert (await asyncio.wait_for(work, 1)).text.startswith('Retain the release decision')
        assert not seat.busy()
        assert seat.session == 'existing-native-conversation'
    asyncio.run(check())


def test_readiness_observers_do_not_cancel_work_and_wait_for_background_completion(monkeypatch):
    async def check():
        seat, session, _, _ = native(2, monkeypatch)
        session.close = AsyncMock()
        await session.session_update(session.session_id, schema.RunningSessionStateUpdate())
        observer = asyncio.create_task(seat.wait_ready())
        await asyncio.sleep(0)
        observer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await observer
        assert seat.busy()
        session.conn.cancel_session.assert_not_awaited()
        session.close.assert_not_awaited()
        waiting = asyncio.create_task(seat.wait_ready())
        raw = {'sessionUpdate': 'state_update', 'state': 'idle', 'stopReason': 'end_turn',
               'background': [{'type': 'tool_call', 'toolCallId': 'ongoing'}]}
        session.stream_event(StreamEvent(StreamDirection.INCOMING, {'method': 'session/update',
            'params': {'sessionId': session.session_id, 'update': raw}}))
        await session.session_update(session.session_id, schema.IdleSessionStateUpdate.model_validate(raw))
        await asyncio.sleep(0)
        assert seat.busy() and not waiting.done()
        raw = {'sessionUpdate': 'state_update', 'state': 'idle', 'background': []}
        session.stream_event(StreamEvent(StreamDirection.INCOMING, {'method': 'session/update',
            'params': {'sessionId': session.session_id, 'update': raw}}))
        await session.session_update(session.session_id, schema.IdleSessionStateUpdate.model_validate(raw))
        await asyncio.wait_for(waiting, 1)
        assert not seat.busy()
    asyncio.run(check())


@pytest.mark.parametrize('missing', ['omitted', 'null', 'malformed'])
def test_an_unknown_background_snapshot_does_not_complete_previously_reported_work(monkeypatch, missing):
    async def check():
        seat, session, _, _ = native(2, monkeypatch)

        async def snapshot(**values):
            raw = {'sessionUpdate': 'state_update', 'state': 'idle', **values}
            session.stream_event(StreamEvent(StreamDirection.INCOMING, {'method': 'session/update',
                'params': {'sessionId': session.session_id, 'update': raw}}))
            await session.session_update(session.session_id, schema.IdleSessionStateUpdate.model_validate(raw))

        unknown = {} if missing == 'omitted' else {'background': None if missing == 'null' else {'not': 'a list'}}
        await snapshot(**unknown)
        assert session.background is None and not seat.busy(), 'Initial unknown state invents no active work.'
        await snapshot(background=[{'type': 'future-work-type', 'id': 'unfinished'}])
        assert seat.busy()
        observer = asyncio.create_task(seat.wait_ready())
        await asyncio.sleep(0)
        await snapshot(**unknown)
        await asyncio.sleep(0)
        assert session.background is None, 'Missing data remains unknown rather than replaying an old snapshot.'
        assert seat.busy() and not observer.done(), 'Unknown does not acknowledge that reported work finished.'
        await snapshot(background=[])
        await asyncio.wait_for(observer, 1)
        assert not seat.busy() and session.background == []
        session.conn.cancel_session.assert_not_awaited()
        assert session.alive() and seat.session == 'existing-native-conversation'

    asyncio.run(check())


def test_process_exit_is_an_actual_readiness_failure_without_native_cancellation(monkeypatch):
    async def check():
        seat, session, _, _ = native(2, monkeypatch)
        await session.session_update(session.session_id, schema.RunningSessionStateUpdate())
        observer = asyncio.create_task(seat.wait_ready())
        await asyncio.sleep(0)
        session.process.returncode = 17
        session.process.ended.set()
        with pytest.raises(harness.Gone, match='exited with 17'):
            await asyncio.wait_for(observer, 1)
        session.conn.cancel_session.assert_not_awaited()
    asyncio.run(check())


@pytest.mark.parametrize('protocol', [1, 2])
def test_native_process_exit_is_distinct_from_a_provider_error(monkeypatch, protocol):
    async def check():
        seat, session, _, _ = native(protocol, monkeypatch)
        started = asyncio.Event()

        async def prompt(**values):
            started.set()
            await asyncio.Event().wait()

        session.conn.prompt = prompt
        work = asyncio.create_task(seat.reply('Continue the design work.', .005))
        await started.wait()
        session.process.returncode = 23
        session.process.ended.set()
        with pytest.raises(harness.Gone, match='exited with 23'):
            await asyncio.wait_for(work, 1)
        session.conn.cancel_session.assert_not_awaited()
        session.conn.cancel.assert_not_awaited()
        assert seat.session == 'existing-native-conversation'
    asyncio.run(check())


@pytest.mark.parametrize('protocol', [1, 2])
def test_actual_provider_failure_is_reported_without_cancelling_the_native_session(monkeypatch, protocol):
    async def check():
        seat, session, _, _ = native(protocol, monkeypatch)

        async def prompt(**values):
            if protocol == 1:
                raise acp.RequestError(-32000, 'Provider unavailable')
            await session.session_update(session.session_id, schema.RunningSessionStateUpdate())
            raw = {'sessionUpdate': 'state_update', 'state': 'idle', 'stopReason': 'error',
                   'error': {'code': -32000, 'message': 'Provider unavailable'}}
            session.stream_event(StreamEvent(StreamDirection.INCOMING, {'method': 'session/update',
                'params': {'sessionId': session.session_id, 'update': raw}}))
            await session.session_update(session.session_id, schema.IdleSessionStateUpdate.model_validate(raw))
            return schema.PromptResponse(message_id='inserted')

        session.conn.prompt = prompt
        with pytest.raises(NoReply, match='Provider unavailable') as failed:
            await seat.reply('Continue the design work.', .005)
        assert not isinstance(failed.value, harness.Gone)
        session.conn.cancel_session.assert_not_awaited()
        session.conn.cancel.assert_not_awaited()
        assert session.alive() and seat.session == 'existing-native-conversation'
    asyncio.run(check())


@pytest.mark.parametrize('protocol', [1, 2])
def test_a_cancelled_transport_request_does_not_cancel_the_native_foreground_work(monkeypatch, protocol):
    async def check():
        seat, session, _, _ = native(protocol, monkeypatch)
        session.close = AsyncMock()

        async def prompt(**values):
            cancelled = asyncio.get_running_loop().create_future()
            cancelled.cancel()
            return await cancelled

        session.conn.prompt = prompt
        with pytest.raises(NoReply, match='request was cancelled') as failed:
            await seat.reply('Continue the design work.', .005)
        assert failed.value.kind == 'transient'
        assert asyncio.current_task().cancelling() == 0
        session.conn.cancel_session.assert_not_awaited()
        session.conn.cancel.assert_not_awaited()
        session.close.assert_not_awaited()
        assert seat.session == 'existing-native-conversation'
    asyncio.run(check())


@pytest.mark.parametrize('protocol', [1, 2])
@pytest.mark.parametrize('sdk_failure', ['cancelled', 'timeout'])
def test_lost_sdk_future_keeps_the_original_wire_request_and_delivers_its_late_reply(monkeypatch, protocol, sdk_failure):
    async def check():
        seat, session, _, _ = native(protocol, monkeypatch)
        sent, followup_sent = asyncio.Event(), asyncio.Event()
        outgoing = []
        models = schema if protocol == 2 else legacy

        class Transport:
            async def send(self, payload):
                outgoing.append(payload)
                (sent if len(outgoing) == 1 else followup_sent).set()

            async def close(self):
                return None

        connection = Connection(AsyncMock(), Transport(), listening=False, observers=[session.stream_event])

        async def prompt(**values):
            result = await connection.send_request('session/prompt', {
                'sessionId': values['session_id'],
                'prompt': [block.model_dump(mode='json', by_alias=True) for block in values['prompt']]})
            return models.PromptResponse.model_validate(result)

        def receive(payload):
            connection._notify_observers(StreamDirection.INCOMING, payload)
            connection._process_message(payload)

        async def message(text):
            await session.session_update(session.session_id, models.AgentMessageChunk(
                **({'message_id': text} if protocol == 2 else {}), content=models.TextContentBlock(text=text)))

        session.conn.prompt = prompt
        session.close = AsyncMock()
        work = asyncio.create_task(seat.reply('The original design request.', .005))
        followup = None
        try:
            await sent.wait()
            if protocol == 2:
                await session.session_update(session.session_id, schema.RunningSessionStateUpdate())
            request_id = outgoing[0]['id']
            if sdk_failure == 'cancelled':
                session.inflight.cancel()
            else:
                connection._pending[request_id].set_exception(TimeoutError('SDK request deadline'))
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            assert not work.done() and session.busy() and seat.busy()
            assert session.activity == 'running'
            session.stream_event(StreamEvent(StreamDirection.INCOMING, {
                'id': request_id, 'method': 'session/request_permission', 'params': {}}))
            assert not session.prompt_response.done(), 'Agent and client RPC ids are separate namespaces.'
            followup = asyncio.create_task(session.prompt('A later design request.'))
            await asyncio.sleep(0)
            assert len(outgoing) == 1, 'No later prompt may replace uncertain native ownership.'
            if protocol == 2:
                receive({'jsonrpc': '2.0', 'id': request_id, 'result': {'messageId': 'original-input'}})
                await asyncio.sleep(0)
                assert not work.done(), 'A recovered v2 acknowledgement is still not foreground completion.'
            await message('The recovered original answer.')
            if protocol == 1:
                receive({'jsonrpc': '2.0', 'id': request_id, 'result': {'stopReason': 'end_turn'}})
            else:
                await session.session_update(session.session_id, schema.IdleSessionStateUpdate(stop_reason='end_turn'))
            assert (await asyncio.wait_for(work, 1)).text == 'The recovered original answer.'
            await asyncio.wait_for(followup_sent.wait(), 1)
            if protocol == 2:
                await session.session_update(session.session_id, schema.RunningSessionStateUpdate())
            await message('The later answer.')
            receive({'jsonrpc': '2.0', 'id': outgoing[1]['id'], 'result':
                     {'messageId': 'later-input'} if protocol == 2 else {'stopReason': 'end_turn'}})
            if protocol == 2:
                await session.session_update(session.session_id, schema.IdleSessionStateUpdate(stop_reason='end_turn'))
            assert (await asyncio.wait_for(followup, 1))[0] == 'The later answer.'
            session.conn.cancel_session.assert_not_awaited()
            session.conn.cancel.assert_not_awaited()
            session.close.assert_not_awaited()
            assert seat.session == 'existing-native-conversation'
        finally:
            for task in (work, followup):
                if task is not None and not task.done():
                    task.cancel()
            await asyncio.gather(*(task for task in (work, followup) if task is not None), return_exceptions=True)
            await connection.close()

    asyncio.run(asyncio.wait_for(check(), 5))


@pytest.mark.parametrize('protocol', [1, 2])
def test_lost_sdk_future_ends_on_actual_connection_eof_without_cancelling_native_work(monkeypatch, protocol):
    async def check():
        seat, session, _, _ = native(protocol, monkeypatch)
        sent, incoming = asyncio.Event(), asyncio.Queue()
        models = schema if protocol == 2 else legacy

        class Transport:
            async def send(self, payload):
                sent.set()

            async def receive(self):
                return await incoming.get()

            async def close(self):
                return None

        connection = Connection(AsyncMock(), Transport(), observers=[session.stream_event])

        async def prompt(**values):
            result = await connection.send_request('session/prompt', {
                'sessionId': values['session_id'],
                'prompt': [block.model_dump(mode='json', by_alias=True) for block in values['prompt']]})
            return models.PromptResponse.model_validate(result)

        session.on_connect(SimpleNamespace(_conn=connection, prompt=prompt,
                                          cancel=AsyncMock(), cancel_session=AsyncMock()))
        session.close = AsyncMock()
        work = asyncio.create_task(seat.reply('Continue productive work.', .005))
        try:
            await sent.wait()
            session.inflight.cancel()
            await asyncio.sleep(0)
            assert not work.done() and session.busy()
            incoming.put_nowait(None)
            with pytest.raises(harness.Gone, match='closed its connection'):
                await asyncio.wait_for(work, 1)
            assert session.process.returncode is None, 'An actual EOF must not be implemented by killing the process.'
            session.conn.cancel.assert_not_awaited()
            session.conn.cancel_session.assert_not_awaited()
            session.close.assert_not_awaited()
            assert seat.session == 'existing-native-conversation'
        finally:
            if not work.done():
                work.cancel()
                await asyncio.gather(work, return_exceptions=True)
            await connection.close()

    asyncio.run(asyncio.wait_for(check(), 5))


def test_disconnected_background_work_keeps_its_cleanup_handle_without_holding_the_scheduler_busy(monkeypatch):
    async def check():
        seat, session, _, _ = native(2, monkeypatch)
        assert (await seat.reply('Complete foreground work.', .005)).text.startswith('Retain the release decision')
        incoming = asyncio.Queue()

        class Transport:
            async def send(self, payload):
                return None

            async def receive(self):
                return await incoming.get()

            async def close(self):
                return None

        connection = Connection(AsyncMock(), Transport(), observers=[session.stream_event])
        session.conn._conn = connection
        session.on_connect(session.conn)
        raw = {'sessionUpdate': 'state_update', 'state': 'idle',
               'background': [{'type': 'tool_call', 'toolCallId': 'background-work'}]}
        session.stream_event(StreamEvent(StreamDirection.INCOMING, {'method': 'session/update',
            'params': {'sessionId': session.session_id, 'update': raw}}))
        await session.session_update(session.session_id, schema.IdleSessionStateUpdate.model_validate(raw))
        session.close = AsyncMock()
        assert seat.busy()
        observer = asyncio.create_task(seat.wait_ready())
        try:
            await asyncio.sleep(0)
            incoming.put_nowait(None)
            with pytest.raises(harness.Gone, match='closed its connection'):
                await asyncio.wait_for(observer, 1)
            assert not seat.busy() and session.alive()
            assert seat.session_made is session, 'Explicit End must still own the live process handle.'
            with pytest.raises(harness.Gone, match='closed its connection'):
                await seat.open()
            session.conn.cancel_session.assert_not_awaited()
            session.close.assert_not_awaited()
            await seat.close()
            session.close.assert_awaited_once()
            assert seat.session_made is None and seat.session == 'existing-native-conversation'
        finally:
            await connection.close()
    asyncio.run(check())


def test_a_lost_compaction_connection_preserves_history_and_process_ownership_until_explicit_close(monkeypatch):
    async def check():
        seat, session, _, advertise = native(2, monkeypatch)
        await advertise()
        original = session.conn.prompt

        async def prompt(**values):
            if values['prompt'][0].text == '/compact':
                session.connection_lost.set()
                raise ConnectionError('Native connection ended.')
            return await original(**values)

        async def close():
            session.process.returncode = 1

        session.conn.prompt = prompt
        session.close = AsyncMock(side_effect=close)
        with pytest.raises(harness.Gone, match='Native connection ended'):
            await seat.compress('Next topic.', 1)
        assert seat.session == 'existing-native-conversation' and seat.session_made is session
        assert seat.messages[0]['content'] == 'Earlier decisions and source references.'
        session.close.assert_not_awaited()
        await seat.close()
        session.close.assert_awaited_once()
        assert seat.session == 'existing-native-conversation' and seat.session_made is None
    asyncio.run(check())


def test_a_non_native_seat_does_not_claim_to_compress_its_conversation():
    seat = Seat({'number': 1}, {'position': 0, 'id': 'model', 'name': 'Participant', 'session': 'saved'}, lambda cost: None)
    assert asyncio.run(seat.compress('The next topic.', 1)) is False
    assert seat.session == 'saved'
