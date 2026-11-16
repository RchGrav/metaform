"""dispatch's ACP client, `dispatch/acp`: the same behaviours run against both adapters, each over the fake agent
(fake_agent.py) speaking the version under test, so no model is called. Version 1 is reached as a v1-only harness
reaches it, asked for v2 and selecting 1."""
import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from metaform.modules.dispatch.acp import (
    IDLE,
    REQUIRES_ACTION,
    RUNNING,
    BaseClient,
    Offer,
    OptionValue,
    Unsupported,
    connect,
    starter,
)

pytestmark = pytest.mark.kind('simulation')
FAKE = Path(__file__).with_name('fake_agent.py')
BOTH = pytest.mark.parametrize('version', [1, 2])
INFO = {'name': 'metaform-test', 'version': '0'}


class Recorder(BaseClient):
    """A client that keeps every event and answers each permission request with one option."""

    def __init__(self, answer='allow'):
        self.events, self.asked, self.answer = [], [], answer

    def changed(self, event):
        self.events.append(event)

    async def permission(self, request):
        self.asked.append(request)
        return self.answer

    def turns(self, session):
        return [event.record.state for event in self.events if event.kind == 'turn' and event.session_id == session]


def logged(folder):
    return [json.loads(line) for line in (folder / 'fake.jsonl').read_text(encoding='utf-8').splitlines()]


def received(folder, method):
    return [entry['message'] for entry in logged(folder) if entry.get('message', {}).get('method') == method]


async def opened(folder, version, client, *, v2=True, offer=None, tools=None, **switches):
    env = {**os.environ, 'FAKE_ACP_LOG': str(folder / 'fake.jsonl'), 'FAKE_ACP_MODE': 'plain',
           **({'FAKE_ACP_V2': '1'} if version == 2 else {}), **switches}
    return await connect(starter([sys.executable, str(FAKE)], cwd=str(folder), env=env), client, info=INFO, v2=v2,
                         offer=offer, tools=tools, timeout=30)


def ran(work):
    return asyncio.run(asyncio.wait_for(work, 60))


@BOTH
def test_a_turn_runs_to_its_end_with_its_messages_and_tool_calls_by_id(tmp_path, version):
    client = Recorder()

    async def work():
        harness = await opened(tmp_path, version, client)
        try:
            session = (await harness.new_session(str(tmp_path), [])).session_id
            made = harness.prompt(session, [{'type': 'text', 'text': 'hi'}])
            prompted = await made.accepted
            turn = await made.ended
            return harness.protocol, session, prompted, turn, harness.sessions[session]
        finally:
            await harness.close()
    protocol, session, prompted, turn, state = ran(work())
    assert protocol == version
    assert (turn.state, turn.stop_reason) == (IDLE, 'end_turn')
    assert client.turns(session) == [RUNNING, IDLE], 'the work began and ended, in both versions'
    assert state.messages[('user', prompted)].text == 'hi', 'the prompt is the user message it was accepted as'
    said = [message.text for (role, _), message in state.messages.items() if role == 'agent']
    calls = {ident: call.status for ident, call in state.tool_calls.items()}
    if version == 1:  # chunks without ids are one message until another kind of update, tool_call its first update
        assert said == ['Hello from fake'] and calls == {'t1': 'completed'}
        assert [message.text for (role, _), message in state.messages.items() if role == 'thought'] == \
            ['Thinking it over']
    else:  # the streamed message replaced whole by its upsert
        assert said == ['Hello v2'] and calls == {'fake-edit': 'completed'}
        assert prompted == 'fake-user-1'


@BOTH
def test_a_cancel_ends_the_work_cancelled(tmp_path, version):
    client = Recorder()

    async def work():
        harness = await opened(tmp_path, version, client, FAKE_ACP_HOLD_LATER='1')
        try:
            session = (await harness.new_session(str(tmp_path), [])).session_id
            await harness.run(session, [{'type': 'text', 'text': 'first'}])
            held = harness.prompt(session, [{'type': 'text', 'text': 'wait'}])
            await held.accepted
            await harness.cancel(session)
            return await held.ended
        finally:
            await harness.close()
    turn = ran(work())
    assert (turn.state, turn.stop_reason) == (IDLE, 'cancelled')
    assert received(tmp_path, 'session/cancel')


@BOTH
def test_a_permission_request_waits_on_the_client_and_its_answer_reaches_the_agent(tmp_path, version):
    client = Recorder('allow')

    async def work():
        harness = await opened(tmp_path, version, client, FAKE_ACP_MODE='ask', FAKE_ACP_V2_MODE='ask')
        try:
            session = (await harness.new_session(str(tmp_path), [])).session_id
            return session, await harness.run(session, [{'type': 'text', 'text': 'write it'}])
        finally:
            await harness.close()
    session, turn = ran(work())
    assert turn.stop_reason == 'end_turn'
    [asked] = client.asked
    assert asked.session_id == session and asked.subject == 'tool_call' and asked.tool_call.tool_call_id == 't2'
    assert asked.tool_call.fields['kind'] == 'edit', 'the request is read with the call it belongs to'
    assert [option.option_id for option in asked.options] == ['allow', 'reject']
    states = client.turns(session)
    assert states[states.index(REQUIRES_ACTION) + 1] == RUNNING, 'waiting on the person, then working again'
    [answer] = [entry['permission'] for entry in logged(tmp_path) if 'permission' in entry]
    assert answer == {'outcome': {'outcome': 'selected', 'optionId': 'allow'}}


@BOTH
def test_a_resume_with_replay_rebuilds_the_history_and_says_where_it_ends(tmp_path, version):
    client = Recorder()

    async def work():
        harness = await opened(tmp_path, version, client, FAKE_ACP_LOAD='1')
        try:
            await harness.resume_session('earlier', str(tmp_path), [], replay=True)
            replayed = [(event.kind, event.replay) for event in client.events if event.session_id == 'earlier']
            texts = {key: message.text for key, message in harness.sessions['earlier'].messages.items()}
            try:
                await harness.resume_session('earlier', str(tmp_path), [])
                plain = 'resumed'
            except Unsupported as refused:
                plain = refused.feature
            return replayed, texts, plain
        finally:
            await harness.close()
    replayed, texts, plain = ran(work())
    assert ('message', True) in replayed, 'the history arrived marked as replay'
    assert replayed[replayed.index(('replay', False)) - 1] == ('message', True), 'and the replay says where it ends'
    if version == 1:  # session/load replays; the fake offers no session/resume, so a resume without replay is refused
        assert received(tmp_path, 'session/load')[0]['params']['sessionId'] == 'earlier'
        assert list(texts.values()) == ['Replayed history']
        assert plain == 'a resume without replay'
    else:
        [first, second] = received(tmp_path, 'session/resume')
        assert first['params']['replayFrom'] == {'type': 'start'} and 'replayFrom' not in second['params']
        assert texts == {('user', 'fake-user-old'): 'Earlier question', ('agent', 'fake-agent-old'): 'Earlier answer'}
        assert plain == 'resumed'


@BOTH
def test_config_options_are_set_by_their_id_and_a_mode_is_one_of_them(tmp_path, version):
    client = Recorder()

    async def work():
        harness = await opened(tmp_path, version, client, FAKE_ACP_RICH='1')
        try:
            setup = await harness.new_session(str(tmp_path), [], options=[OptionValue('reasoning', 'high'),
                                                                          OptionValue('missing', 'x')])
            first = {one.config_id: (one.category, one.current) for one in setup.options}
            await harness.set_option(setup.session_id, 'model', 'large')
            final = await harness.set_option(setup.session_id, 'mode', 'plan')
            return setup, first, {one.config_id: one.current for one in final}
        finally:
            await harness.close()
    setup, first, final = ran(work())
    assert first == {'mode': ('mode', 'default'), 'model': ('model', 'small'), 'reasoning': ('thought_level', 'high')}
    assert [(one.config_id, reason) for one, reason in setup.ignored] == \
        [('missing', 'the session offers no such option')], 'a value the session does not have is said, not dropped'
    assert final == {'mode': 'plan', 'model': 'large', 'reasoning': 'high'}
    if version == 1:  # the session's modes, one option of category mode, set with session/set_mode
        assert received(tmp_path, 'session/set_mode')[0]['params']['modeId'] == 'plan'
        assert all('type' not in one['params'] for one in received(tmp_path, 'session/set_config_option'))
    else:
        assert not received(tmp_path, 'session/set_mode')
        assert {(one['params']['configId'], one['params']['type'])
                for one in received(tmp_path, 'session/set_config_option')} == \
            {('reasoning', 'id'), ('model', 'id'), ('mode', 'id')}


def test_a_v1_only_harness_asked_for_v2_is_started_again_and_initialized_in_v1(tmp_path):
    """It selects 1 for the v2 request, which it read without v1's client capabilities, so it is started afresh and
    initialized in v1 with them; with v2 turned off it is asked for v1 alone."""
    async def work(v2):
        harness = await opened(tmp_path, 1, Recorder(), v2=v2, offer=Offer(terminal_login=True))
        await harness.close()
        return harness.protocol
    assert ran(work(True)) == 1
    asked = received(tmp_path, 'initialize')
    assert [one['params']['protocolVersion'] for one in asked] == [2, 1]
    assert 'info' in asked[0]['params'] and asked[1]['params']['clientCapabilities']['auth'] == {'terminal': True}
    assert len([entry for entry in logged(tmp_path) if 'pid' in entry]) == 2, 'two processes, one per handshake'
    (tmp_path / 'fake.jsonl').unlink()
    assert ran(work(False)) == 1
    assert [one['params']['protocolVersion'] for one in received(tmp_path, 'initialize')] == [1]


def test_a_session_needing_client_files_asks_for_v1_and_a_v2_only_harness_says_it_cannot(tmp_path):
    """Client files exist only in v1, so v1 is asked for at once; a harness that answers only v2 is spoken to in v2,
    with the files listed as what the connection could not give."""
    class Tools:
        pass

    async def work(version):
        harness = await opened(tmp_path, version, Recorder(), offer=Offer(files=True), tools=Tools())
        await harness.close()
        return harness.protocol, harness.unsupported, harness.capabilities.client_files
    assert ran(work(1)) == (1, [], True)
    [asked] = received(tmp_path, 'initialize')
    assert asked['params']['clientCapabilities']['fs'] == {'readTextFile': True, 'writeTextFile': True}
    (tmp_path / 'fake.jsonl').unlink()
    assert ran(work(2)) == (2, ['client files'], False)
    assert [one['params']['protocolVersion'] for one in received(tmp_path, 'initialize')] == [1, 2]
