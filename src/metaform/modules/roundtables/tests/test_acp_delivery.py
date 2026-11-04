"""A successful native transport send consumes the queued input even if its reply is lost."""
import asyncio
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from acp.connection import Connection, StreamDirection, StreamEvent

pytestmark = pytest.mark.kind('simulation')


@pytest.mark.parametrize('protocol', [1, 2])
@pytest.mark.parametrize('sent', [False, True])
def test_native_transport_disconnect_records_exactly_the_inputs_physically_sent(protocol, sent):
    harness = importlib.import_module('metaform.modules.roundtables.roundtable.harness')
    seats = importlib.import_module('metaform.modules.roundtables.roundtable.seat')

    async def check():
        delivered = asyncio.Event()

        class Transport:
            async def send(self, payload):
                if not sent:
                    raise ConnectionError('Transport refused before sending')
                delivered.set()

            async def close(self):
                return None

        session = harness.Session(1, {'position': 0, 'agent': 'claude', 'model': 'haiku'}, '/tmp')
        session.protocol = protocol
        session.session_id = 'native-session'
        session.process = SimpleNamespace(returncode=None, wait=AsyncMock(side_effect=asyncio.Event().wait))
        connection = Connection(AsyncMock(), Transport(), listening=False, observers=[session.stream_event])

        async def prompt(**kwargs):
            return await connection.send_request('session/prompt', {
                'sessionId': kwargs['session_id'],
                'prompt': [block.model_dump(mode='json', by_alias=True) for block in kwargs['prompt']]})

        session.conn = SimpleNamespace(prompt=prompt)

        class NativeSeat(seats.Seat):
            async def exchange(self, text, seconds):
                reply, usage = await session.prompt(text, seconds)
                return seats.Reply(reply, usage)

        seat = NativeSeat({'number': 1}, {'position': 0, 'id': 'claude', 'name': 'Claude'}, lambda cost: None)
        session.on_sent = seat.delivered
        receipts = []
        seat.on_delivered = lambda: receipts.append([dict(message) for message in seat.messages])
        task = asyncio.create_task(seat.reply('This queued input is given once.', 2))
        try:
            if sent:
                await delivered.wait()
                assert receipts == [[{'role': 'user', 'content': 'This queued input is given once.'}]]
                assert not task.done(), 'The send receipt precedes a remote reply.'
                # A user-message echo is an update, not a second queue delivery.
                session.stream_event(StreamEvent(StreamDirection.INCOMING, {
                    'method': 'session/update', 'params': {'sessionId': 'native-session', 'update': {
                        'sessionUpdate': 'user_message', 'messageId': 'native-inserted-id'}}}))
                await connection.close()
            with pytest.raises(seats.Gone) as failure:
                await task
            assert failure.value.delivered is sent
            assert len(receipts) == int(sent)
            assert len(seat.messages) == int(sent)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await connection.close()

    asyncio.run(asyncio.wait_for(check(), 5))


@pytest.mark.parametrize('protocol', [1, 2])
def test_cancellation_after_send_keeps_receipt_and_never_appends_prompt_twice(protocol):
    harness = importlib.import_module('metaform.modules.roundtables.roundtable.harness')
    seats = importlib.import_module('metaform.modules.roundtables.roundtable.seat')

    async def check():
        sent = asyncio.Event()
        session = harness.Session(1, {'position': 0, 'agent': 'codex', 'model': 'sol'}, '/tmp')
        session.protocol = protocol
        session.session_id = 'native-session'
        session.process = SimpleNamespace(returncode=None, wait=AsyncMock(side_effect=asyncio.Event().wait))
        session.cancel_turn = AsyncMock()

        async def prompt(**kwargs):
            event = StreamEvent(StreamDirection.OUTGOING, {'method': 'session/prompt',
                'params': {'sessionId': kwargs['session_id'], 'prompt': []}})
            session.stream_event(event)
            session.stream_event(event)
            sent.set()
            await asyncio.Event().wait()

        session.conn = SimpleNamespace(prompt=prompt)

        class NativeSeat(seats.Seat):
            async def exchange(self, text, seconds):
                reply, usage = await session.prompt(text, seconds)
                return seats.Reply(reply, usage)

        seat = NativeSeat({'number': 1}, {'position': 0, 'id': 'codex', 'name': 'Codex'}, lambda cost: None)
        session.on_sent = seat.delivered
        receipts = []
        seat.on_delivered = lambda: receipts.append(list(seat.messages))
        task = asyncio.create_task(seat.reply('A sent instruction remains consumed.', 2))
        await sent.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        session.cancel_turn.assert_awaited_once()
        assert receipts == [[{'role': 'user', 'content': 'A sent instruction remains consumed.'}]]
        assert seat.messages == receipts[0]
        assert seat.inflight_prompt is None

    asyncio.run(asyncio.wait_for(check(), 5))


def test_successful_reply_adds_one_user_message_and_one_assistant_message():
    seats = importlib.import_module('metaform.modules.roundtables.roundtable.seat')

    class NativeSeat(seats.Seat):
        async def exchange(self, text, seconds):
            self.delivered()
            self.delivered()
            return seats.Reply('The reply.')

    seat = NativeSeat({'number': 1}, {'position': 0, 'id': 'codex', 'name': 'Codex'}, lambda cost: None)
    receipts = []
    seat.on_delivered = lambda: receipts.append(list(seat.messages))
    asyncio.run(seat.reply('The instruction.', 1))
    assert len(receipts) == 1
    assert seat.messages == [{'role': 'user', 'content': 'The instruction.'},
                             {'role': 'assistant', 'content': 'The reply.'}]
