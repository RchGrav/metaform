"""BASE-057 reports trouble from events without giving detection code recovery authority."""
import asyncio
import json
import subprocess
import sys

import pytest

from metaform.module import context
from metaform.modules.dispatch.tests.test_dispatch import dispatch as dispatch  # noqa: PLC0414
from metaform.modules.dispatch.tests.test_dispatch import eventually

pytestmark = [pytest.mark.kind('simulation'), pytest.mark.req('BASE-057')]


def signals(dispatch, run, active=None):
    words = ['dispatch', 'signals', f'id={dispatch.id}', '--json']
    if active is not None:
        words.append(f'active={str(active).lower()}')
    return json.loads(run(*words, cwd=dispatch.folder).stdout)['signals']


def test_unfinished_fake_session_raises_not_smooth_and_no_requeue(dispatch, run):
    dispatch.start('plain')
    from metaform.modules.dispatch import tell
    held = dispatch.session().extra
    eventually(lambda: tell(held, 'status')['activity'] == 'idle' or None)  # the turn ended, the ticket open
    dispatch.stop()
    assert dispatch.process.wait(15) == 0
    found = signals(dispatch, run)
    assert 'not-smooth' in {row['signal'] for row in found} and 'requeue' not in {row['signal'] for row in found}
    assert all(row['work_id'] == dispatch.id for row in found)


def test_completed_fake_session_has_no_not_smooth(dispatch, run):
    dispatch.start('done')
    assert dispatch.process.wait(15) == 0
    assert not {'not-smooth', 'requeue'} & {row['signal'] for row in signals(dispatch, run)}


def test_permission_signal_is_cleared_by_its_answer(dispatch, run):
    dispatch.start('ask', FAKE_ACP_ASK_HOLD='1')
    [question] = eventually(dispatch.questions)
    waiting = eventually(lambda: [row for row in signals(dispatch, run) if row['signal'] == 'permission-waiting'])
    assert waiting[0]['message_id'] == question.id
    run('map', 'reply', question.id, 'answer=Allow once', cwd=dispatch.folder)
    eventually(lambda: dispatch.logged('permission'))
    assert not [row for row in signals(dispatch, run) if row['signal'] == 'permission-waiting']
    assert [row for row in signals(dispatch, run, False) if row['signal'] == 'permission-waiting']


@pytest.mark.cli_process
def test_thresholds_count_unique_calls_and_reset_on_real_steps(dispatch, run):
    from acp.schema import ToolCallProgress, ToolCallStart

    from metaform.data import Store
    from metaform.modules.dispatch.runner import Session
    run('set', '--dispatch-spin-calls', '3', '--dispatch-repeat-failures', '2', cwd=dispatch.folder)
    store = Store('proj', module='dispatch')
    store.take_work(dispatch.id, by='fake')
    session = Session(context('dispatch', dispatch.folder, project='proj'), store, dispatch.ticket(), 'claude', [])
    session.session_id = 'unit-session'
    session.turns = 1
    async def update(ident, status='pending', title='Read file'):
        await session.session_update('unit-session', ToolCallStart(session_update='tool_call', tool_call_id=ident,
                                      title=title, kind='read', status=status, raw_input={'path': title}))
    async def exercise():
        await update('1')
        await session.session_update('unit-session', ToolCallProgress(session_update='tool_call_update',
                                    tool_call_id='1', status='completed'))
        await update('2')
        assert not [row for row in signals(dispatch, run) if row['signal'] == 'spinning-calls']
        await update('3')
        assert len([row for row in signals(dispatch, run) if row['signal'] == 'spinning-calls']) == 1
        store.step_work(dispatch.id, 'Read the necessary files.')
        await update('4')
        assert not [row for row in signals(dispatch, run) if row['signal'] == 'spinning-calls']
        await update('5', 'failed', 'Fail file')
        await update('6', 'failed', 'Fail file')
        assert len([row for row in signals(dispatch, run) if row['signal'] == 'repeated-failure']) == 1
        await update('6', 'failed', 'Fail file')
        assert len([row for row in signals(dispatch, run) if row['signal'] == 'repeated-failure']) == 1
    asyncio.run(exercise())


@pytest.mark.cli_process
def test_elapsed_threshold_uses_the_next_event_and_not_a_timer(dispatch, run, monkeypatch):
    from acp.schema import AgentMessageChunk, TextContentBlock

    from metaform.data import Store
    from metaform.modules.dispatch import runner
    run('set', '--dispatch-spin-minutes', '2', cwd=dispatch.folder)
    store = Store('proj', module='dispatch')
    session = runner.Session(context('dispatch', dispatch.folder, project='proj'), store, dispatch.ticket(), 'claude', [])
    session.session_id = 'unit-session'
    session.turns = 1
    now = [0.0]
    monkeypatch.setattr(runner.time, 'monotonic', lambda: now[0])
    session.progress_at = 0.0
    async def exercise():
        for at in (119.0, 120.0, 121.0):
            now[0] = at
            await session.session_update('unit-session', AgentMessageChunk(session_update='agent_message_chunk',
                                         content=TextContentBlock(type='text', text='working')))
            found = [row for row in signals(dispatch, run) if row['signal'] == 'spinning-time']
            assert len(found) == (0 if at == 119.0 else 1)
        assert not session.tasks, 'detection schedules no background timer or poll'
    asyncio.run(exercise())


def test_manual_requeue_signals_only_a_real_column_transition(dispatch, run):
    run('map', 'work', 'op=take', f'id={dispatch.id}', 'by=claude', cwd=dispatch.folder)
    run('map', 'work', 'op=move', f'id={dispatch.id}', 'column=todo', cwd=dispatch.folder)
    [raised] = signals(dispatch, run)
    assert raised['signal'] == 'requeue' and raised['previous'] == 'doing'
    run('map', 'work', 'op=move', f'id={dispatch.id}', 'column=todo', 'position=0', cwd=dispatch.folder)
    assert signals(dispatch, run) == [raised]


def test_signals_verb_is_available_to_a_real_mcp_client(dispatch, home):
    from metaform.modules.mcp.tests.test_mcp import session
    context('dispatch', dispatch.folder, project='proj').publish('dispatch.rework-limit',
            {'work_id': dispatch.id, 'attempts': 3, 'limit': 3})
    async def check(client, init):
        offered = {tool.name: tool for tool in (await client.list_tools()).tools}
        assert 'dispatch_signals' in offered
        response = await client.call_tool('dispatch_signals', {'id': dispatch.id})
        assert not response.is_error
        assert 'rework-limit' in ''.join(block.text for block in response.content if hasattr(block, 'text'))
    session(home, dispatch.folder, check)


@pytest.mark.cli_process
def test_signal_events_reach_another_process_without_polling(dispatch, run):
    import threading

    from metaform.modules.dispatch.signals import publish
    observed, ready = [], threading.Event()
    def received(payload):
        if payload.get('signal', {}).get('signal') == 'requeue':
            observed.append(payload['signal'])
            ready.set()
    listener = context('dispatch', dispatch.folder, project='proj').listen(received)
    try:
        run('map', 'work', 'op=take', f'id={dispatch.id}', 'by=claude', cwd=dispatch.folder)
        run('map', 'work', 'op=move', f'id={dispatch.id}', 'column=todo', cwd=dispatch.folder)
        assert ready.wait(10), 'a committed signal wakes the existing relay listener'
        assert len(observed) == 1 and observed[0]['active']
        saved = signals(dispatch, run)
        assert json.loads(run('dispatch', 'sessions', '--json', cwd=dispatch.folder).stdout)['signals'] == saved
        read = json.loads(run('map', 'work', f'id={dispatch.id}', '--json', cwd=dispatch.folder).stdout)
        assert read['dispatch']['signals'] == saved
        ctx = context('dispatch', dispatch.folder, project='proj')
        publish(ctx, 'rework-limit', work_id=dispatch.id, attempts=3)
        publish(ctx, 'rework-limit', work_id=dispatch.id, attempts=3)
        assert len([row for row in signals(dispatch, run) if row['signal'] == 'rework-limit']) == 1
    finally:
        listener.close()


@pytest.mark.cli_process
def test_idle_chat_time_and_prep_failures_do_not_flag_ticket_progress(dispatch, run, monkeypatch):
    from acp.schema import AgentMessageChunk, TextContentBlock, ToolCallStart

    from metaform.data import Store
    from metaform.modules.dispatch import runner
    now = [600.0]
    monkeypatch.setattr(runner.time, 'monotonic', lambda: now[0])
    store = Store('proj', module='dispatch')
    held = runner.Session(context('dispatch', dispatch.folder, project='proj'), store, dispatch.ticket(), 'claude', [])
    held.session_id, held.progress_at = 'idle-session', 0.0
    async def exercise():
        await held.session_update(held.session_id, AgentMessageChunk(session_update='agent_message_chunk',
                                 content=TextContentBlock(type='text', text='idle')))
        assert not signals(dispatch, run)
        # The dispatcher is not run here: close the coroutine instead of starting a real prompt task.
        monkeypatch.setattr(held, 'spawn', lambda coroutine: coroutine.close())
        held.turn('Continue after the person replies.')
        assert held.progress_at == now[0]
        held.prep = True
        for n in range(3):
            await held.session_update(held.session_id, ToolCallStart(session_update='tool_call', tool_call_id=str(n),
                                     title='Read file', kind='read', status='failed', raw_input={'path': 'a'}))
        assert not signals(dispatch, run)
    asyncio.run(exercise())


def test_other_prompt_producers_are_persisted_without_rewriting_them(dispatch, run):
    run('enable', 'workflow', cwd=dispatch.folder)
    sent = {'signal': 'incomplete-prompt', 'module': 'workflow', 'call': 'Inspect',
            'notices': [{'message': 'The prompt has no @VERIFY.'}]}
    ctx = context('workflow', dispatch.folder, project='proj')
    deliveries = ctx.publish('signal.raised', sent)
    assert all(row['status'] == 'completed' for row in deliveries)
    ctx.publish('signal.raised', sent)
    [raised] = json.loads(run('dispatch', 'signals', '--json', cwd=dispatch.folder).stdout)['signals']
    assert raised['signal'] == sent['signal'] and raised['producer'] == 'workflow'
    assert raised['notices'] == sent['notices']


def test_release_clears_permission_signal_after_a_crashed_runner(dispatch, run):
    from metaform.data import Store
    from metaform.modules.dispatch import release
    from metaform.modules.dispatch.signals import publish
    own = Store('proj', module='dispatch')
    own.take_work(dispatch.id, by='claude crashed')
    publish(context('dispatch', dispatch.folder, project='proj'), 'permission-waiting', work_id=dispatch.id,
            session_id='crashed', key='permission', message_id='permission')
    release(own, dispatch.id, 'claude crashed', True, 'crashed', 'crash cleanup')
    assert not [row for row in signals(dispatch, run) if row['signal'] == 'permission-waiting']


def test_a_talk_first_turn_is_checked_like_the_handoff(dispatch, run):
    from metaform import axiom
    dispatch.process = subprocess.Popen(
        [sys.executable, '-m', 'metaform', 'dispatch', 'run', dispatch.id, 'claude', 'system=true',
         f'talk=ticket:{dispatch.id}'], cwd=dispatch.folder, env=dispatch.env('plain'),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    [sent] = eventually(lambda: dispatch.received('session/prompt'))
    expected = axiom.notices('prompt', sent['params']['prompt'][0]['text'])
    assert expected, 'the talk draft lacks @CONDITION today, so its first turn is flagged'
    eventually(lambda: [row for row in dispatch.items('note') if row.extra['update'] == 'notice'] or None)
    [notice] = [row.value for row in dispatch.items('note') if row.extra['update'] == 'notice']
    assert notice == ' '.join(one['message'] for one in expected)
    [raised] = [row for row in signals(dispatch, run) if row['signal'] == axiom.SIGNAL]
    assert raised['work_id'] == dispatch.id and raised['notices'] == expected


def test_a_turn_that_stops_with_the_ticket_open_raises_stopped_open(dispatch, run):
    from metaform.modules.dispatch import tell
    dispatch.start('plain')
    held = dispatch.session().extra
    eventually(lambda: tell(held, 'status')['activity'] == 'idle' or None)
    [raised] = eventually(lambda: [row for row in signals(dispatch, run) if row['signal'] == 'stopped-open'])
    assert raised['work_id'] == dispatch.id and raised['stop_reason'] == 'end_turn'
    dispatch.stop()
    assert dispatch.process.wait(15) == 0
    found = {row['signal'] for row in signals(dispatch, run)}
    assert 'stopped-open' not in found and 'not-smooth' in found, 'the ended session hands over to not-smooth'


def test_stopped_open_is_cleared_by_the_next_turn(dispatch, run):
    from metaform.modules.dispatch import tell
    dispatch.start('plain', FAKE_ACP_HOLD_LATER='1')
    held = dispatch.session().extra
    eventually(lambda: [row for row in signals(dispatch, run) if row['signal'] == 'stopped-open'])
    assert tell(held, 'message', text='Carry on with the ticket.')['sent'] is True
    eventually(lambda: tell(held, 'status')['activity'] == 'working' or None)
    eventually(lambda: not [row for row in signals(dispatch, run) if row['signal'] == 'stopped-open'] or None)
    assert [row for row in signals(dispatch, run, False) if row['signal'] == 'stopped-open']
    dispatch.stop()
