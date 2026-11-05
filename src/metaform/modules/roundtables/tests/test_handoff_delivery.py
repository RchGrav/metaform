"""A carry request consumes each seat's queued context once, including recoverable failures."""
import asyncio
from types import SimpleNamespace

import pytest

from metaform.modules.roundtables.roundtable import budget, judge, permissions, render, runner, store
from metaform.modules.roundtables.roundtable.seat import NoReply, Reply, Seat

pytestmark = pytest.mark.kind('simulation')


@pytest.fixture
def inbox(run, tmp_path, monkeypatch):
    run('enable', 'dispatch', cwd=tmp_path)
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    monkeypatch.setenv('ROUNDTABLE_CONTEXT_TOKENS', '24000')
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    calls, answers = [], {}

    class Fake(Seat):
        kind = 'acp'

        async def exchange(self, text, seconds):
            calls.append((self.position, text))
            answer = answers.get(self.position, []).pop(0) if answers.get(self.position) else Reply(
                f'Intact note from seat {self.position}.')
            if callable(answer):
                return await answer(self, text)
            if isinstance(answer, Exception):
                raise answer
            return answer

    monkeypatch.setitem(runner.KINDS, 'acp', Fake)
    seats = [{'kind': 'acp', 'id': f'acp:codex/{model}', 'agent': 'codex', 'model': model}
             for model in ('sol', 'astra')]
    number = store.opened({'subject': 'Delivery', 'opening': 'ORIGINAL_OWNER_INSTRUCTIONS',
                           'folder': str(tmp_path), 'chair_token': 'fixture', 'reporter': seats[0]['id'],
                           'rounds': 0, 'spend': 1}, seats,
                          [{'name': 'first', 'title': 'First', 'text': 'TOPIC_ALREADY_RECEIVED'}],
                          judging=False, reply_limit=80,
                          session={'total': 1, 'folder': str(tmp_path), 'between': 'Collaborate.'})
    table = runner.Table(number)
    editors = []

    async def edited(found, role, text):
        editors.append(text)
        return Reply('Compact shared state.')

    monkeypatch.setattr(runner.Table, 'ask_fresh', lambda self, *args: edited(*args))
    return number, table, calls, answers, editors


def existing_context(number, table, *, large=False):
    found = table.row()
    continuation = {'topic': 0, 'through': 0, 'text': 'SAVED_SHARED_MARKER ' + ('x' * 30000 if large else ''),
                    'notes': [{'position': 0, 'name': 'Sol', 'text': 'SAVED_NOTE_MARKER'}]}
    store.change(number, continuation=continuation)
    shared = render.shared(table.row())
    history = {}
    for row in store.seats(number):
        system = table.seat(row).system
        messages = [{'role': 'user', 'content': system + '\n\n' + shared + '\nTOPIC_ALREADY_RECEIVED\n' +
                     ('h' * 10000 if large else '')},
                    {'role': 'assistant', 'content': f'OWN_REPLY_{row["position"]}'}]
        store.seat_change(number, row['position'], session=f'native-{row["position"]}', messages=messages,
                          extra={'topic': 0})
        history[row['position']] = '\n'.join(one['content'] for one in messages)
    table.seated.clear()
    for row in store.seats(number):
        store.record(number, table.entry(found, row, f'OWN_REPLY_{row["position"]}', accepted=True))
    queued = store.record(number, table.entry(found, store.seats(number)[1], 'NEW_QUEUED_EVIDENCE', accepted=True))
    return history, queued


def test_live_shaped_handoff_does_not_replay_continuation_or_own_reply(inbox):
    number, table, calls, answers, editors = inbox
    history, _ = existing_context(number, table, large=True)
    row = store.seats(number)[0]
    seat = table.seat(row)
    # The old guard counts the shared continuation and embedded system twice, reproducing held table 19.
    assert judge.tokens([seat.system, seat.messages, render.shared(table.row())]) + 2048 > 24000
    assert not table.context_due(table.row()), 'The already-delivered snapshot must not trigger another handoff.'
    asyncio.run(table.handoff(table.row()))
    assert table.row()['state'] == 'running', table.row()['reason']
    assert table.row()['handoff'] is None
    for position in (0, 1):
        delivered = history[position] + '\n' + '\n'.join(text for pos, text in calls if pos == position)
        assert delivered.count('SAVED_SHARED_MARKER') == 1
        assert delivered.count('SAVED_NOTE_MARKER') == 1
        assert delivered.count(f'OWN_REPLY_{position}') == 1
        assert delivered.count('ORIGINAL_OWNER_INSTRUCTIONS') == 1
    assert editors and editors[0].count('SAVED_NOTE_MARKER') == 1
    assert [one['text'] for one in store.submissions(number) if one['kind'] == 'carry'] == [
        'Intact note from seat 0.', 'Intact note from seat 1.']
    assert not any(one['kind'] == 'pass' for one in store.submissions(number))
    for row in store.seats(number):
        answers[row['position']] = [Reply('PASS')]
        asyncio.run(table.turn(table.row(), row))
        fresh = [text for position, text in calls if position == row['position']][-1]
        assert fresh.count('ORIGINAL_OWNER_INSTRUCTIONS') == 1
        assert fresh.count('TOPIC_ALREADY_RECEIVED') == 1
        for note in ('Intact note from seat 0.', 'Intact note from seat 1.'):
            assert fresh.count(note) == 1


@pytest.mark.parametrize('answer', [NoReply('accepted, then failed', delivered=True), Reply('  ')])
def test_delivered_failed_note_retries_only_new_queue_items_after_restart(inbox, answer):
    number, table, calls, answers, _ = inbox
    history, queued = existing_context(number, table)
    answers[0] = [answer]
    asyncio.run(table.handoff(table.row()))
    assert table.row()['state'] == 'held'
    assert store.seats(number)[0]['seen'] == queued['number']
    fresh = store.record(number, table.entry(table.row(), store.seats(number)[1], 'LATER_QUEUED_EVIDENCE', accepted=True))
    store.change(number, state='running', reason=None)
    restarted = runner.Table(number)
    asyncio.run(restarted.handoff(restarted.row()))
    assert restarted.row()['state'] == 'running', restarted.row()['reason']
    attempts = [text for position, text in calls if position == 0]
    assert len(attempts) == 2
    delivered = history[0] + '\n' + '\n'.join(attempts)
    for marker in ('SAVED_SHARED_MARKER', 'SAVED_NOTE_MARKER', 'OWN_REPLY_0',
                   'NEW_QUEUED_EVIDENCE', 'LATER_QUEUED_EVIDENCE', 'ORIGINAL_OWNER_INSTRUCTIONS'):
        assert delivered.count(marker) == 1, marker
    assert 'Complete the carry-forward note already requested' in attempts[1]
    assert len([one for one in store.submissions(number) if one['kind'] == 'carry']) == 2
    assert store.seats(number)[0]['seen'] >= fresh['number']


def test_rejected_before_delivery_keeps_the_queue_for_retry(inbox):
    number, table, calls, answers, _ = inbox
    _, queued = existing_context(number, table)
    answers[0] = [NoReply('rejected before insertion', delivered=False)]
    asyncio.run(table.handoff(table.row()))
    assert store.seats(number)[0]['seen'] < queued['number']
    store.change(number, state='running', reason=None)
    asyncio.run(runner.Table(number).handoff(store.discussion(number)))
    attempts = [text for position, text in calls if position == 0]
    assert len(attempts) == 2 and all(text.count('NEW_QUEUED_EVIDENCE') == 1 for text in attempts)
    assert 'Complete the carry-forward note already requested' not in attempts[1]


def test_panel_failure_only_consumes_delivered_queue_items(inbox):
    number, table, _, answers, _ = inbox
    _, queued = existing_context(number, table)
    found = table.row()
    row = store.seats(number)[0]

    async def attempt(delivered):
        answers[0] = [NoReply('fixture failure', delivered=delivered)]
        await table.turn(found, store.seats(number)[0])

    asyncio.run(attempt(False))
    assert store.seats(number)[0]['seen'] == row['seen'] < queued['number']
    latest = store.submissions(number)[-1]['number']
    asyncio.run(attempt(True))
    assert store.seats(number)[0]['seen'] == latest
    assert sum(message['content'].count('NEW_QUEUED_EVIDENCE')
               for message in store.seats(number)[0]['messages']) == 1


def test_handoff_send_receipt_survives_cancellation_without_replaying_batch(inbox):
    number, table, calls, answers, _ = inbox
    history, queued = existing_context(number, table)

    async def scenario():
        sent, blocked = asyncio.Event(), asyncio.Event()

        async def accepted_then_waiting(seat, text):
            seat.delivered()  # The same receipt ACP's outgoing transport observer invokes.
            sent.set()
            await blocked.wait()
            return Reply('Not reached.')

        answers[0] = [accepted_then_waiting]
        task = asyncio.create_task(table.handoff(table.row()))
        await asyncio.wait_for(sent.wait(), 2)
        row = store.seats(number)[0]
        assert row['seen'] == queued['number']
        assert row['extra']['carry_request'] == table.row()['handoff']['after']
        assert '\n'.join(one['content'] for one in row['messages']).count('NEW_QUEUED_EVIDENCE') == 1
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await table.unseat()
        restarted = runner.Table(number)
        await restarted.handoff(restarted.row())
        assert restarted.row()['state'] == 'running', restarted.row()['reason']

    asyncio.run(scenario())
    delivered = history[0] + '\n' + '\n'.join(text for position, text in calls if position == 0)
    for marker in ('SAVED_SHARED_MARKER', 'SAVED_NOTE_MARKER', 'OWN_REPLY_0', 'NEW_QUEUED_EVIDENCE'):
        assert delivered.count(marker) == 1, marker


def test_inline_permission_tool_work_and_queued_evidence_are_not_replayed_after_hold(inbox, tmp_path, monkeypatch):
    number, table, calls, answers, _ = inbox
    history, queued = existing_context(number, table)
    document = tmp_path / 'inline-work.md'
    requests = []
    listeners = []

    def listen(module, handler):
        listeners.append(handler)
        return SimpleNamespace(close=lambda: listeners.remove(handler))

    # The relay excludes its own process. Deliver the person's change directly in
    # this simulation while exercising the real permission records and wait.
    monkeypatch.setattr(permissions.events, 'listen', listen)

    async def scenario():
        permission_visible, written, blocked = asyncio.Event(), asyncio.Event(), asyncio.Event()
        loop = asyncio.get_running_loop()

        def notified(payload):
            if payload['state'] == 'waiting':
                requests.append(payload)
                loop.call_soon_threadsafe(permission_visible.set)

        async def inline_tool_work(seat, text):
            seat.delivered()
            chosen = await permissions.request(number, seat.position, {
                'toolCall': {'toolCallId': 'inline-write', 'title': 'Write shared materials', 'kind': 'edit'},
                'options': [{'optionId': 'allow', 'name': 'Allow once', 'kind': 'allow_once'}]}, notified)
            assert chosen == 'allow'
            document.write_text('Completed inline work remains saved.', encoding='utf-8')
            written.set()
            await blocked.wait()
            return Reply('Not reached.')

        answers[0] = [inline_tool_work]
        table.panel_work[0] = asyncio.create_task(table.turn(table.row(), store.seats(number)[0]))
        await asyncio.wait_for(permission_visible.wait(), 2)
        assert store.seats(number)[0]['seen'] == queued['number']
        assert not table.panel_work[0].done()
        answers[1] = [Reply('NEW_PEER_REPLY_WHILE_BUSY')]
        await table.turn(table.row(), store.seats(number)[1])
        fresh = store.submissions(number)[-1]

        def approved():
            permissions.answer(number, requests[0]['request'], 'allow')
            for listener in listeners:
                listener({'kinds': [permissions.topic(number)]})

        await asyncio.to_thread(approved)
        await asyncio.wait_for(written.wait(), 2)
        store.change(number, state='held', reason='The chair held this table.')
        await table.unseat()
        assert store.seats(number)[0]['seen'] == queued['number']
        store.change(number, state='running', reason=None)
        restarted = runner.Table(number)
        answers[0] = [Reply('PASS')]
        await restarted.turn(restarted.row(), store.seats(number)[0])
        assert store.seats(number)[0]['seen'] == fresh['number']
        assert restarted.row()['stage'] == 'discussion'
        await restarted.unseat()

    asyncio.run(scenario())
    attempts = [text for position, text in calls if position == 0]
    assert len(attempts) == 2
    assert attempts[0].count('NEW_QUEUED_EVIDENCE') == 1 and 'NEW_PEER_REPLY_WHILE_BUSY' not in attempts[0]
    assert 'NEW_QUEUED_EVIDENCE' not in attempts[1] and attempts[1].count('NEW_PEER_REPLY_WHILE_BUSY') == 1
    delivered = history[0] + '\n' + '\n'.join(attempts)
    for marker in ('ORIGINAL_OWNER_INSTRUCTIONS', 'SAVED_SHARED_MARKER', 'SAVED_NOTE_MARKER', 'OWN_REPLY_0'):
        assert delivered.count(marker) == 1
    assert document.read_text(encoding='utf-8') == 'Completed inline work remains saved.'
    assert len(requests) == 1 and permissions.get(number, requests[0]['request'])['state'] == 'answered'


@pytest.mark.parametrize('spent', [50, 80, 100])
def test_delivery_keeps_midpoint_once_and_repeats_wind_down_after_a_failed_reply(inbox, spent):
    number, table, calls, answers, _ = inbox
    found = table.row()
    store.change(number, snapshot={**found['snapshot'], 'token_budget': 100})
    row = store.seats(number)[0]
    budget.record_reply(table.row(), row, {'completion_tokens': spent}, 'fixture-first-reply')
    answers[0] = [NoReply('Sent, but no answer.', delivered=True), Reply('PASS')]
    asyncio.run(table.turn(table.row(), row))
    assert bool(budget.prompt(table.row(), 0).text) is (spent >= 80)
    if spent == 100:
        assert budget.needs_closing(table.row(), 0), 'Delivery alone does not complete the closing statement.'
    asyncio.run(table.turn(table.row(), store.seats(number)[0]))
    texts = [text for position, text in calls if position == 0]
    for notice in budget.status(table.row())['notices']:
        if notice['percent'] == 50:
            assert sum(text.count(notice['text']) for text in texts) == 1
    if spent >= 80:
        assert all('80%' in text if spent == 80 else '100%' in text for text in texts)
    if spent == 100:
        assert not budget.needs_closing(table.row(), 0)
