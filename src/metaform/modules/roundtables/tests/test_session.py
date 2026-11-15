"""Private next-topic selection keeps busy proposals, original artifacts and final scorecards intact."""
import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from metaform.modules.roundtables.roundtable import export, render, runner, server, stages, store, topics
from metaform.modules.roundtables.roundtable.seat import Gone, Late, NoReply, Reply, Seat

pytestmark = pytest.mark.kind('simulation')


async def until_held(table):
    """Explicitly stop a fixture after observing Hold; production Hold keeps native clients alive."""
    held = asyncio.Event()
    read = table.row

    def observed():
        found = read()
        if found['state'] == 'held':
            held.set()
        return found

    table.row = observed
    task = asyncio.create_task(table.run())
    waiting = asyncio.create_task(held.wait())
    try:
        await asyncio.wait_for(asyncio.wait({task, waiting}, return_when=asyncio.FIRST_COMPLETED), 8)
        return table.summary() if held.is_set() else task.result()
    finally:
        task.cancel()
        waiting.cancel()
        await asyncio.gather(task, waiting, return_exceptions=True)
        table.row = read


@pytest.fixture
def session(run, tmp_path, monkeypatch):
    folder = tmp_path / 'project'
    folder.mkdir()
    run('add', 'project', 'private-session', str(folder))
    run('enable', 'dispatch', cwd=folder)
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    calls, comparisons = [], []
    handlers = {}
    materials = folder / 'materials'
    materials.mkdir()

    class Fake(Seat):
        async def open(self):
            self.session = self.session or f'session-{self.position}'

        async def exchange(self, text, seconds):
            await self.open()
            found = store.discussion(self.number)
            key = (found['stage'], found['topic'], self.position)
            calls.append((*key, text))
            await asyncio.sleep(0)
            if key in handlers:
                return Reply(await handlers[key](self, text))
            if found['stage'] == 'discussion':
                return Reply('PASS')
            if found['stage'] == 'topic_selection':
                return Reply(f'Explore private proposal {self.position}.')
            if found['stage'] == 'scoring':
                others = [row['name'] for row in store.seats(self.number) if row['position'] != self.position]
                return Reply(json.dumps({name: {**{category: 5 for category in stages.CATEGORIES}, 'bonus': False}
                                         for name in others}) + '\nDone')
            return Reply('Done')

    def compare(path, body, **kwargs):
        assert path == '/alpha/decisions' and kwargs['retry'] is False
        comparisons.append(body)
        return {'model': body['model'], 'answers': {key: {'noul': .62} for key in body['questions']},
                'usage': {'cost': .0001}}

    monkeypatch.setitem(runner.KINDS, 'acp', Fake)
    monkeypatch.setattr(topics.openrouter, 'post', compare)

    def make(total=1, compress=False):
        seats = [{'kind': 'acp', 'id': 'acp:claude/haiku', 'agent': 'claude', 'model': 'haiku'},
                 {'kind': 'acp', 'id': 'acp:codex/sol', 'agent': 'codex', 'model': 'sol'}]
        role = {**seats[0], 'name': 'Haiku'}
        number = store.opened({'subject': 'session', 'opening': 'Original session instructions.',
                             'folder': str(folder), 'chair_key': None, 'chair_token': 'fixture',
                             'reporter': seats[0]['id'], 'host': role, 'synthesizer': role, 'rounds': 0, 'spend': 1}, seats,
                            [{'name': 'first', 'title': 'First topic', 'text': 'Explore the first topic.'}],
                            judging=False, reply_limit=80,
                            session={'total': total, 'folder': str(materials), 'compress_between_topics': compress,
                                     'score': 'Send your anonymous scorecard.', 'farewell': 'Say farewell.'})
        actual = store.seats(number)[0]
        store.change(number, host={**role, 'name': actual['name']}, synthesizer={**role, 'name': actual['name']})
        return number

    make.comparisons = comparisons
    return make, handlers, calls, materials


@pytest.mark.parametrize('enabled', [False, True])
def test_optional_compression_waits_for_the_selected_topic_and_preserves_native_sessions(session, monkeypatch, enabled):
    make, _, calls, materials = session
    number = make(total=2, compress=enabled)
    compressed = []
    document = materials / 'decisions.md'
    document.write_text('Keep the original decisions.', encoding='utf-8')

    async def scenario():
        all_started, release = asyncio.Event(), asyncio.Event()

        async def compress(seat, topic, seconds):
            assert enabled, 'Compression is off by default.'
            assert all(row['state'] == 'ready' for row in topics.proposals(number, 0))
            assert len(make.comparisons) == 1 and len(store.topics(number)) == 2
            assert topic in store.topics(number)[1]['text']
            assert store.discussion(number)['topic'] == 1
            assert seat.session == f'session-{seat.position}'
            compressed.append((seat.position, seat.session, topic))
            if len(compressed) == 2:
                all_started.set()
            await release.wait()
            return True

        monkeypatch.setattr(runner.KINDS['acp'], 'compress', compress)
        task = asyncio.create_task(runner.Table(number).run())
        if enabled:
            await asyncio.wait_for(all_started.wait(), 2)
            assert store.discussion(number)['stage'] == 'discussion'
            release.set()
        return await asyncio.wait_for(task, 5)

    result = asyncio.run(scenario())
    assert result['state'] == 'ended', result
    assert [position for position, _, _ in compressed] == ([0, 1] if enabled else [])
    assert len(make.comparisons) == 1 and len(store.topics(number)) == 2
    assert {position for stage, _, position, _ in calls if stage == 'discussion'} == {0, 1}
    assert [row['session'] for row in store.seats(number)] == ['session-0', 'session-1']
    assert document.read_text() == 'Keep the original decisions.'
    assert len([row for row in store.events(number) if row['kind'] == 'topic_compression']) == (2 if enabled else 0)


@pytest.mark.parametrize('error', [NoReply('Fixture native compression failed.'),
                                  ValueError('Fixture native compression failed.')])
def test_compression_failure_or_unsupported_transport_does_not_hold_or_repeat_the_request(session, monkeypatch, error):
    make, _, _, _ = session
    number = make(total=2, compress=True)
    compressed = []

    async def compress(seat, topic, seconds):
        compressed.append(seat.position)
        if seat.position == 0:
            raise error
        return False

    monkeypatch.setattr(runner.KINDS['acp'], 'compress', compress)
    result = asyncio.run(asyncio.wait_for(runner.Table(number).run(), 5))
    assert result['state'] == 'ended', result
    assert compressed == [0, 1] and len(make.comparisons) == 1
    assert [row['session'] for row in store.seats(number)] == ['session-0', 'session-1']
    assert all(row['extra']['compressed_for_topic'] == 1 for row in store.seats(number))
    events = [row for row in store.events(number) if row['kind'] == 'topic_compression']
    assert len(events) == 2 and any('Fixture native compression failed.' in row['text'] for row in events)
    assert not any('Fixture native compression failed.' in row['text'] for row in store.submissions(number))


@pytest.mark.parametrize('action', ['hold', 'end'])
def test_chair_interrupts_compression_and_resume_keeps_sessions_without_repeating_it(session, monkeypatch, action):
    make, _, _, materials = session
    number = make(total=2, compress=True)
    document = materials / 'decisions.md'
    document.write_text('Retain the authored decisions.', encoding='utf-8')
    compressed, cancelled = [], set()
    monkeypatch.setattr(server.runner, 'spawn', lambda *_: None)

    async def scenario():
        all_started, release, all_finished = asyncio.Event(), asyncio.Event(), asyncio.Event()
        finished = []

        async def compress(seat, topic, seconds):
            compressed.append((seat.position, seat.session))
            if len(compressed) == 2:
                all_started.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                cancelled.add(seat.position)
                raise
            finished.append(seat.position)
            if len(finished) == 2:
                all_finished.set()
            return True

        monkeypatch.setattr(runner.KINDS['acp'], 'compress', compress)
        table = runner.Table(number)
        task = asyncio.create_task(table.run())
        await asyncio.wait_for(all_started.wait(), 2)
        # The relay intentionally ignores its publisher's PID, so invoke the public control from another process.
        command = ('import sys\n'
                   'from metaform.modules.roundtables.roundtable import server, store\n'
                   'server.runner.spawn = lambda *_: None\n'
                   f'server.{"held" if action == "hold" else "ended"}(store.discussion(int(sys.argv[1])))\n')
        await asyncio.to_thread(subprocess.run, [sys.executable, '-c', command, str(number)],
                                check=True, capture_output=True, text=True, timeout=5)
        if action == 'hold':
            await asyncio.sleep(0)
            assert table.row()['state'] == 'held' and not task.done() and not cancelled
            release.set()
            await asyncio.wait_for(all_finished.wait(), 2)
            assert not task.done() and not cancelled
            await asyncio.to_thread(server.continued, table.row())
            table.control.set()
        result = await asyncio.wait_for(task, 5)
        assert result['state'] == 'ended'
        assert cancelled == (set() if action == 'hold' else {0, 1})
        assert [row['session'] for row in store.seats(number)] == ['session-0', 'session-1']
        assert all(row['extra']['compressed_for_topic'] == 1 for row in store.seats(number))
        return result

    assert asyncio.run(scenario())['state'] == 'ended'
    assert compressed == [(0, 'session-0'), (1, 'session-1')]
    assert len(make.comparisons) == 1
    assert document.read_text() == 'Retain the authored decisions.'


@pytest.mark.parametrize('mixed', [False, True])
def test_continuous_session_bypasses_legacy_context_handoff_for_every_lineup(session, monkeypatch, mixed):
    make, handlers, _, _ = session
    number = make(total=2)
    if mixed:
        with store.connect() as db:
            store.update(db, 'seats', {'discussion': number, 'position': 1},
                         {'kind': 'openrouter', 'id': 'fixture/model', 'agent': None, 'model': 'fixture/model'})
        monkeypatch.setitem(runner.KINDS, 'openrouter', runner.KINDS['acp'])
    store.change(number, state='held', reason='Seat context cannot fit the carry-forward request.', handoff={'after': 0})
    for position in (0, 1):
        store.seat_change(number, position, session=f'session-{position}',
                          messages=[{'role': 'user', 'content': 'Keep this existing native conversation.'}])
    context_due = Mock(return_value=True)
    handoff = Mock(side_effect=AssertionError('Continuous native sessions must retain their conversations.'))
    monkeypatch.setattr(runner.Table, 'context_due', context_due)
    monkeypatch.setattr(runner.Table, 'handoff', handoff)
    monkeypatch.setattr(server.runner, 'spawn', lambda *_: None)

    async def resumed(seat, text):
        assert store.discussion(number)['handoff'] is None
        assert any('Keep this existing native conversation.' in one['content'] for one in seat.messages)
        return 'PASS'

    handlers[('discussion', 0, 0)] = resumed
    assert server.continued(store.discussion(number))['state'] == 'running'
    result = asyncio.run(asyncio.wait_for(runner.Table(number).run(), 5))
    assert result['state'] == 'ended', result
    handoff.assert_not_called()
    assert [row['session'] for row in store.seats(number)] == ['session-0', 'session-1']
    assert not any(row['kind'] in ('carry', 'handoff') for row in store.submissions(number))


def test_private_topic_proposals_skip_busy_models_without_leaking_proposals_or_making_a_file(session):
    make, handlers, calls, materials = session
    number = make(total=2)
    document = materials / 'saved.md'
    document.write_text('Keep the participants\' artifacts.', encoding='utf-8')
    first = store.seats(number)[0]
    accepted = store.record(number, {'round': 1, 'position': 0, 'seat': first['id'], 'name': first['name'],
        'kind': 'seat', 'topic': 0, 'text': 'A public decision from the panel.', 'accepted': True})

    async def scenario():
        slow_started, fast_finished, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def slow(seat, text):
            assert 'Original session instructions.' not in text and 'A public decision from the panel.' not in text
            assert accepted['message_id'] in str(seat.messages)
            slow_started.set()
            await release.wait()
            return 'Keep the slow proposal verbatim.'

        async def fast(seat, text):
            assert 'Keep the slow proposal' not in text
            fast_finished.set()
            return 'Keep the fast proposal verbatim.'

        handlers[('topic_selection', 0, 0)] = slow
        handlers[('topic_selection', 0, 1)] = fast
        table = runner.Table(number)
        task = asyncio.create_task(table.run())
        await asyncio.wait_for(slow_started.wait(), 2)
        await asyncio.wait_for(fast_finished.wait(), 2)
        assert not task.done() and table.row()['stage'] == 'topic_selection'
        assert topics.progress(table.row())['requested'] == 2
        assert 'proposal verbatim' not in json.dumps(export.build(number))
        assert all('proposal verbatim' not in json.dumps(row['messages']) for row in store.seats(number))
        release.set()
        return await asyncio.wait_for(task, 5)

    result = asyncio.run(scenario())
    assert result['state'] == 'ended', result
    next_topic = store.topics(number)[1]['text']
    assert 'Keep the slow proposal verbatim.\n\nKeep the fast proposal verbatim.' in next_topic
    assert len(make.comparisons) == 1 and len(make.comparisons[0]['questions']) == 1
    assert sum(stage == 'topic_selection' for stage, _, _, _ in calls) == 2
    assert 'collaboration' not in {stage for stage, _, _, _ in calls}
    assert not (materials / 'next-topic.md').exists()
    assert document.read_text() == 'Keep the participants\' artifacts.'
    assert len(store.scorecards(number)) == 2
    assert all(row['kind'] != 'score' for row in export.build(number)['submissions'])
    assert all(store.profile(row['profile_key'])['score'] == 100 for row in store.seats(number))


def test_last_panel_goes_directly_to_private_scorecards_then_farewell(session):
    make, _, calls, _ = session
    number = make(total=1)
    assert asyncio.run(asyncio.wait_for(runner.Table(number).run(), 5))['state'] == 'ended'
    assert {stage for stage, _, _, _ in calls} == {'discussion', 'scoring', 'farewell'}
    assert topics.proposals(number, 0) == [] and make.comparisons == []


def test_unavailable_participant_does_not_block_scorecards_or_farewell(session):
    make, _, calls, _ = session
    number = make(total=1)
    retry = time.time() + 300
    store.seat_change(number, 0, availability='unavailable', failures=4, failing='timeout', retry_at=retry)
    result = asyncio.run(asyncio.wait_for(runner.Table(number).run(), 5))
    assert result['state'] == 'ended'
    assert {position for _, _, position, _ in calls} == {1}
    assert [card['position'] for card in store.scorecards(number)] == [1]
    assert store.seats(number)[0]['retry_at'] == retry
    assert not any(row['position'] == 0 for row in store.submissions(number))


@pytest.mark.parametrize('delayed_first', [False, True])
def test_collection_cutoff_preserves_native_work_and_late_private_proposal(session, monkeypatch, delayed_first):
    make, handlers, calls, _ = session
    number = make(total=2)
    topics.seed(store.discussion(number), store.seats(number))
    with store.connect() as db:
        db.execute('UPDATE topic_proposals SET created=? WHERE discussion=?',
                   ('2000-01-01T00:00:00+00:00', number))
    original = runner.config.value
    monkeypatch.setattr(runner.config, 'value', lambda key: .05 if key == 'topic_proposal_wait' else original(key))

    async def scenario():
        started, release, advanced, rejoined, finish, first_release = (asyncio.Event() for _ in range(6))
        cancelled = []

        async def slow(seat, text):
            started.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                cancelled.append(seat.position)
                raise
            return 'The late private proposal must stay private.'

        async def selected(seat, text):
            if delayed_first:
                await first_release.wait()
            return 'The selected private proposal.'

        async def current(seat, text):
            advanced.set()
            await finish.wait()
            return 'PASS'

        async def returning(seat, text):
            rejoined.set()
            return 'PASS'

        handlers.update({('topic_selection', 0, 0): selected, ('topic_selection', 0, 1): slow,
                         ('discussion', 1, 0): current, ('discussion', 1, 1): returning})
        table = runner.Table(number)
        task = asyncio.create_task(table.run())
        try:
            await asyncio.wait_for(started.wait(), 2)
            if delayed_first:
                await asyncio.sleep(.08)
                assert not task.done() and table.row()['stage'] == 'topic_selection'
                assert not cancelled
                first_release.set()
            await asyncio.wait_for(advanced.wait(), 2)
            assert not cancelled and not release.is_set()
            assert store.topics(number)[1]['text'].endswith('The selected private proposal.')
            proposal = topics.proposals(number, 0)[1]
            assert proposal['state'] == 'skipped' and proposal['attempts'] == 1
            assert sum(stage == 'topic_selection' and position == 1 for stage, _, position, _ in calls) == 1
            release.set()
            first_release.set()
            await asyncio.wait_for(rejoined.wait(), 2)
            late = topics.proposals(number, 0)[1]
            assert late['state'] == 'late' and late['text'] == 'The late private proposal must stay private.'
            assert store.topics(number)[1]['text'].endswith('The selected private proposal.')
            assert 'The late private proposal' not in json.dumps(export.build(number))
            assert [row['session'] for row in store.seats(number)] == ['session-0', 'session-1']
            finish.set()
            assert (await asyncio.wait_for(task, 5))['state'] == 'ended'
        finally:
            release.set()
            finish.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())


def test_hold_preserves_active_native_work_and_connections_until_continue(session, monkeypatch):
    make, handlers, calls, _ = session
    number = make(total=1)
    monkeypatch.setattr(runner, 'spawn', lambda *_: None)

    async def scenario():
        started, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()
        entered, returned, cancelled = [], [], []

        async def working(seat, text):
            entered.append(seat.position)
            if len(entered) == 2:
                started.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                cancelled.append(seat.position)
                raise
            returned.append(seat.position)
            if len(returned) == 2:
                finished.set()
            return 'PASS'

        handlers.update({('discussion', 0, 0): working, ('discussion', 0, 1): working})
        table = runner.Table(number)
        task = asyncio.create_task(table.run())
        try:
            await asyncio.wait_for(started.wait(), 2)
            await asyncio.to_thread(server.held, table.row())
            table.control.set()
            await asyncio.sleep(0)
            assert table.row()['state'] == 'held' and not task.done() and not cancelled
            release.set()
            await asyncio.wait_for(finished.wait(), 2)
            await asyncio.sleep(0)
            assert not task.done() and not cancelled
            assert [row['session'] for row in store.seats(number)] == ['session-0', 'session-1']
            assert len(calls) == 2
            await asyncio.to_thread(server.continued, table.row())
            table.control.set()
            assert (await asyncio.wait_for(task, 5))['state'] == 'ended'
            assert not cancelled
        finally:
            release.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())


def test_only_future_proposer_can_rejoin_after_other_seat_exhausts_its_attempts(session):
    make, handlers, calls, _ = session
    number = make(total=2)

    async def scenario():
        working, release, failed_twice, advanced, finish = (asyncio.Event() for _ in range(5))
        attempts = 0

        async def old_work(seat, text):
            working.set()
            await release.wait()
            return 'The old topic response.'

        async def failed(seat, text):
            nonlocal attempts
            attempts += 1
            if attempts == 2:
                failed_twice.set()
            raise NoReply('No proposal returned.')

        async def proposal(seat, text):
            return 'The previously busy participant proposes the next topic.'

        async def next_discussion(seat, text):
            advanced.set()
            await finish.wait()
            return 'PASS'

        handlers.update({('discussion', 0, 0): old_work, ('topic_selection', 0, 1): failed,
                         ('topic_selection', 0, 0): proposal, ('discussion', 1, 0): next_discussion})
        table = runner.Table(number)
        table.panel_work[0] = asyncio.create_task(table.turn(table.row(), store.seats(number)[0]))
        await asyncio.wait_for(working.wait(), 2)
        table.start_topic_selection(table.row())
        task = asyncio.create_task(table.run())
        try:
            await asyncio.wait_for(failed_twice.wait(), 2)
            assert table.row()['state'] == 'running' and table.row()['stage'] == 'topic_selection'
            untouched = topics.proposals(number, 0)[0]
            assert untouched['state'] == 'pending' and untouched['attempts'] == 0
            release.set()
            await asyncio.wait_for(advanced.wait(), 2)
            assert attempts == 2 and len(store.topics(number)) == 2
            assert 'previously busy participant' in store.topics(number)[1]['text']
            assert make.comparisons == []
            assert sum(stage == 'topic_selection' and position == 0 for stage, _, position, _ in calls) == 1
            finish.set()
            assert (await asyncio.wait_for(task, 5))['state'] == 'ended'
        finally:
            release.set()
            finish.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())


def test_held_completed_foreground_still_watches_native_background_readiness(session, monkeypatch):
    make, _, _, _ = session
    number = make(total=2)
    store.change(number, stage='topic_selection', state='held', reason=runner.said('held_by_chair'))
    monkeypatch.setattr(runner, 'spawn', lambda *_: None)

    async def scenario():
        watching, release, observed = asyncio.Event(), asyncio.Event(), asyncio.Event()
        background = {0}
        fake = runner.KINDS['acp']
        monkeypatch.setattr(fake, 'busy', lambda seat: seat.position in background)

        async def ready(seat):
            watching.set()
            await release.wait()
            background.discard(seat.position)
            observed.set()

        monkeypatch.setattr(fake, 'wait_ready', ready)
        closed = AsyncMock()
        monkeypatch.setattr(fake, 'close', closed)
        table = runner.Table(number)
        table.seat(store.seats(number)[0])
        table.recover = AsyncMock(side_effect=AssertionError('Native background work has a readiness event.'))

        async def completed():
            return None, 0, None

        table.working[0] = asyncio.create_task(completed())
        await table.working[0]
        table.work_phase[0] = ('topic_selection', 0)
        task = asyncio.create_task(table.run())
        try:
            await asyncio.wait_for(watching.wait(), 2)
            assert not task.done()
            release.set()
            await asyncio.wait_for(observed.wait(), 2)
            await asyncio.sleep(0)
            assert not task.done() and table.row()['state'] == 'held'
            closed.assert_not_awaited()
            table.recover.assert_not_awaited()
            await asyncio.to_thread(server.ended, table.row())
            table.control.set()
            assert (await asyncio.wait_for(task, 5))['state'] == 'ended'
        finally:
            release.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())


@pytest.mark.parametrize('stage', ['discussion', 'scoring', 'farewell'])
def test_departed_participant_does_not_block_final_phases_or_receive_fabricated_completion(session, stage):
    make, _, calls, materials = session
    number = make(total=1)
    document = materials / 'decisions.md'
    document.write_text('Preserve the session decisions.', encoding='utf-8')
    store.seat_change(number, 1, gone='The participant exited permanently.', availability='unavailable', retry_at=None)
    store.change(number, stage=stage)
    result = asyncio.run(asyncio.wait_for(runner.Table(number).run(), 5))
    assert result['state'] == 'ended', result
    assert calls and all(position == 0 for _, _, position, _ in calls)
    assert {row['position'] for row in store.scorecards(number)} == (set() if stage == 'farewell' else {0})
    rows = store.submissions(number)
    assert not any(row['position'] == 1 for row in rows)
    assert len([row for row in rows if row['position'] == 0 and row['kind'] == 'farewell']) == 1
    assert document.read_text() == 'Preserve the session decisions.'


def test_recovery_of_finished_panel_enters_private_selection_once_without_legacy_synthesis(session):
    make, _, calls, _ = session
    number = make(total=2)
    table = runner.Table(number)
    store.change(number, stage='synthesis')
    asyncio.run(table.stage(table.row()))
    assert table.row()['stage'] == 'topic_selection'
    before = store.submissions(number)
    table.start_topic_selection(table.row())
    assert store.submissions(number) == before and not calls


def test_native_fake_acp_proposals_reuse_existing_sessions_and_deliver_each_context_item_once(session, monkeypatch):
    from metaform.modules.roundtables.roundtable import harness

    make, _, _, materials = session
    number = make(total=2)
    fake = Path(__file__).with_name('fake_agent.py')
    for agent in ('CLAUDE', 'CODEX'):
        monkeypatch.setenv(f'ROUNDTABLE_AGENT_{agent}', f'"{sys.executable}" "{fake}"')
    monkeypatch.setenv('FAKE_ACP_LOG', str(materials / 'private-wire.jsonl'))
    monkeypatch.setenv('FAKE_ACP_MODELS', json.dumps([{'value': name, 'name': name} for name in ('haiku', 'sol')]))
    monkeypatch.delenv('FAKE_ACP_PERMISSION', raising=False)
    monkeypatch.delenv('FAKE_ACP_BLOCK', raising=False)
    monkeypatch.setitem(runner.KINDS, 'acp', harness.AcpSeat)
    table = runner.Table(number)
    next_topic = table.next_topic

    def stop_after_choice(found):
        next_topic(found)
        store.change(number, state='held', reason='Fixture stops at the chosen next panel.')

    monkeypatch.setattr(table, 'next_topic', stop_after_choice)

    async def check():
        for row in store.seats(number):
            seat = table.seat(row)
            await seat.reply('Unique already-delivered context.', 5)
            table.keep(seat, 0)
        table.start_topic_selection(table.row())
        return await until_held(table)

    assert asyncio.run(check())['state'] == 'held'
    assert len(store.topics(number)) == 2 and len(make.comparisons) == 1
    assert all(row['state'] == 'ready' and row['usage']['completion_tokens'] == 20
               for row in topics.proposals(number, 0))
    assert all(row['session'] is not None for row in store.seats(number))
    assert all('Explore the evidence and unresolved questions' not in str(row['messages'])
               for row in store.seats(number))
    wire = [json.loads(line) for line in (materials / 'private-wire.jsonl').read_text().splitlines()]
    methods = [row.get('message', {}).get('method') for row in wire]
    assert methods.count('session/new') == methods.count('session/close') == 2
    prompts = [row['message']['params']['prompt'][0]['text'] for row in wire
               if row.get('message', {}).get('method') == 'session/prompt']
    assert len(prompts) == 4
    assert sum('Unique already-delivered context.' in text for text in prompts) == 2
    assert sum('# Private next-topic proposal' in text for text in prompts) == 2
    assert len({row['pid'] for row in wire}) == 2


@pytest.mark.parametrize('state', ['sent', 'error'])
def test_restart_retries_only_the_missing_proposal_and_keeps_completed_work(session, state):
    make, _, calls, _ = session
    number = make(total=2)
    table = runner.Table(number)
    table.start_topic_selection(table.row())
    receipt = topics.begin_proposal(table.row(), 0)
    assert receipt
    if state == 'error':
        with store.connect() as db:
            store.update(db, 'topic_proposals', {'discussion': number, 'topic': 0, 'position': 0},
                         {'state': 'error', 'usage': {'error': '300 seconds'}})
    completed_receipt = topics.begin_proposal(table.row(), 1)
    topics.finish_proposal(table.row(), 1, completed_receipt, 'A proposal saved before restart.', {})
    completed = topics.proposals(number, 0)[1]
    assert asyncio.run(runner.Table(number).run())['state'] == 'ended'
    assert len([call for call in calls if call[:3] == ('topic_selection', 0, 0)]) == 1
    assert not [call for call in calls if call[:3] == ('topic_selection', 0, 1)]
    assert topics.proposals(number, 0)[0]['receipt'] != receipt
    assert topics.proposals(number, 0)[1] == completed
    assert len(store.topics(number)) == 2 and len(make.comparisons) == 1
    assert 'A proposal saved before restart.' in store.topics(number)[1]['text']


@pytest.mark.parametrize('failure', [Late(300), NoReply('Temporary disconnection.', kind='transient'), '', 'PASS'])
def test_failed_private_request_wakes_again_and_advances_without_repeating_other_proposals(session, failure):
    make, handlers, calls, materials = session
    number = make(total=2)
    document = materials / 'decisions.md'
    document.write_text('Preserve the participants\' work.', encoding='utf-8')
    attempts = 0

    async def flaky(seat, text):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            if isinstance(failure, Exception):
                raise failure
            return failure
        assert 'Explore private proposal 1.' not in text
        return 'A private proposal after recovery.'

    handlers[('topic_selection', 0, 0)] = flaky
    result = asyncio.run(asyncio.wait_for(runner.Table(number).run(), 5))
    assert result['state'] == 'ended', result
    assert attempts == 2
    assert len([call for call in calls if call[:3] == ('topic_selection', 0, 1)]) == 1
    assert len(make.comparisons) == 1 and len(store.topics(number)) == 2
    assert 'A private proposal after recovery.' in store.topics(number)[1]['text']
    assert document.read_text() == 'Preserve the participants\' work.'
    assert all(row['kind'] != 'score' for row in export.build(number)['submissions'])
    assert store.seats(number)[0]['failures'] == 0


def test_proposer_times_out_twice_then_session_continues_with_the_returned_proposal(session, monkeypatch):
    make, handlers, calls, _ = session
    number = make(total=2)
    monkeypatch.setenv('ROUNDTABLE_UNAVAILABLE_AFTER', '1')
    monkeypatch.setenv('ROUNDTABLE_PROBE_WAIT', '300')
    attempts = 0

    async def unresponsive(seat, text):
        nonlocal attempts
        attempts += 1
        raise Late(300)

    handlers[('topic_selection', 0, 0)] = unresponsive
    table = runner.Table(number)
    next_topic = table.next_topic

    def stop_at_next_discussion(found):
        next_topic(found)
        store.change(number, state='held', reason='Fixture stops at the chosen next panel.')

    monkeypatch.setattr(table, 'next_topic', stop_at_next_discussion)
    assert asyncio.run(until_held(table))['state'] == 'held'
    assert table.row()['topic'] == 1 and table.row()['stage'] == 'discussion'
    assert table.row()['reason'] == 'Fixture stops at the chosen next panel.'
    assert attempts == 2
    assert len([call for call in calls if call[:3] == ('topic_selection', 0, 1)]) == 1
    assert make.comparisons == [], 'The only returned proposal needs no comparison.'
    assert 'Explore private proposal 1.' in store.topics(number)[1]['text']
    failed = topics.proposals(number, 0)[0]
    assert failed['attempts'] == 2 and failed['state'] == 'error' and failed['text'] is None


def test_private_selection_wakes_missing_proposer_even_when_all_seats_are_unavailable(session, monkeypatch):
    make, _, calls, _ = session
    number = make(total=2)
    table = runner.Table(number)
    table.start_topic_selection(table.row())
    receipt = topics.begin_proposal(table.row(), 1)
    topics.finish_proposal(table.row(), 1, receipt, 'The saved proposal survives.', {})
    for position in (0, 1):
        store.seat_change(number, position, availability='unavailable', failures=4, failing='timeout',
                          retry_at=time.time() + 300)
    next_topic = table.next_topic

    def stop_at_next_discussion(found):
        next_topic(found)
        store.change(number, state='held', reason='Fixture stops at the chosen next panel.')

    monkeypatch.setattr(table, 'next_topic', stop_at_next_discussion)
    assert asyncio.run(until_held(table))['state'] == 'held'
    assert table.row()['topic'] == 1 and table.row()['reason'] == 'Fixture stops at the chosen next panel.'
    assert len([call for call in calls if call[:3] == ('topic_selection', 0, 0)]) == 1
    assert not [call for call in calls if call[:3] == ('topic_selection', 0, 1)]
    assert len(make.comparisons) == 1


def test_lost_adapter_waits_for_explicit_cleanup_without_restarting_its_session(session, monkeypatch):
    make, handlers, _, _ = session
    number = make(total=2)
    table = runner.Table(number)
    seat = table.seat(store.seats(number)[0])
    session_id, closed = 'saved-native-session', []
    seat.session = session_id
    attempts = 0

    async def close():
        closed.append(seat.session)

    async def disconnected_once(actual, text):
        nonlocal attempts
        attempts += 1
        assert actual.session == session_id
        assert attempts == 1, 'Transport loss is not permission to restart native work.'
        raise Gone('The ACP adapter exited.')

    monkeypatch.setattr(seat, 'close', close)
    handlers[('topic_selection', 0, 0)] = disconnected_once
    advance = table.next_topic

    def stop_before_cleanup(found):
        assert closed == []
        advance(found)
        store.change(number, state='held', reason='Observe native ownership before explicit fixture cleanup.')

    monkeypatch.setattr(table, 'next_topic', stop_before_cleanup)
    assert asyncio.run(until_held(table))['state'] == 'held'
    assert attempts == 1 and store.seats(number)[0]['session'] == session_id
    assert store.seats(number)[0]['gone']


@pytest.mark.parametrize('action', ['hold', 'end'])
def test_chair_controls_interrupt_a_private_proposal_retry(session, monkeypatch, action):
    make, handlers, _, _ = session
    number = make(total=2)
    monkeypatch.setattr(server.runner, 'spawn', lambda *_: None)

    async def scenario():
        waiting, cancelled = asyncio.Event(), asyncio.Event()
        attempts = 0

        async def blocked_retry(seat, text):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise Late(300)
            waiting.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        handlers[('topic_selection', 0, 0)] = blocked_retry
        table = runner.Table(number)
        task = asyncio.create_task(table.run())
        await asyncio.wait_for(waiting.wait(), 2)
        if action == 'hold':
            await asyncio.to_thread(server.held, table.row())
        else:
            await asyncio.to_thread(server.ended, table.row())
        # Deliver the control event independently of the cross-process event relay.
        table.control.set()
        if action == 'hold':
            await asyncio.sleep(0)
            assert table.row()['state'] == 'held' and not task.done() and not cancelled.is_set()
            await asyncio.to_thread(server.ended, table.row())
            table.control.set()
        result = await asyncio.wait_for(task, 2)
        assert cancelled.is_set() and attempts == 2
        return result

    result = asyncio.run(scenario())
    assert result['state'] == 'ended'
    assert len(store.topics(number)) == 1 and make.comparisons == []


def test_private_comparisons_need_spend_even_when_contribution_judging_is_off(session):
    make, _, calls, _ = session
    number = make(total=2)
    table = runner.Table(number)
    assert render.judging(table.row()) is False and not table.requires_payment(table.row())
    table.start_topic_selection(table.row())
    assert table.requires_payment(table.row())
    store.change(number, spent=1)
    assert asyncio.run(until_held(table))['state'] == 'held'
    assert calls == [] and make.comparisons == []


def test_unseat_cancels_and_drains_active_private_proposals(session):
    make, handlers, _, _ = session
    number = make(total=2)

    async def scenario():
        started, cancelled = asyncio.Event(), asyncio.Event()

        async def blocked(seat, text):
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        handlers[('topic_selection', 0, 0)] = blocked
        table = runner.Table(number)
        table.start_topic_selection(table.row())
        await table.select_topic(table.row())
        await started.wait()
        await asyncio.wait_for(table.unseat(), 2)
        assert cancelled.is_set() and table.working == {} and table.seated == {}
        assert topics.proposals(number, 0)[0]['receipt']

    asyncio.run(asyncio.wait_for(scenario(), 5))


@pytest.mark.parametrize('held', [False, True])
def test_end_session_from_private_selection_saves_documents_without_requesting_proposals(session, monkeypatch, held):
    make, _, calls, materials = session
    number = make(total=5)
    table = runner.Table(number)
    table.start_topic_selection(table.row())
    document = materials / 'decisions.md'
    document.write_text('Decisions remain saved.', encoding='utf-8')
    if held:
        store.change(number, state='held', reason='held by its chair.')
    monkeypatch.setattr(server.runner, 'spawn', lambda *_: None)
    assert server.ended(store.discussion(number))['state'] == 'ending'
    assert asyncio.run(table.run())['state'] == 'ended'
    found = store.discussion(number)
    assert document.read_text() == 'Decisions remain saved.'
    assert Path(found['report']).is_file() and Path(found['export']).is_file()
    assert len(store.topics(number)) == 1 and calls == []


@pytest.mark.parametrize('stage', ['topic_selection', 'scoring', 'farewell'])
def test_advance_cannot_skip_private_selection_or_final_phases(session, monkeypatch, stage):
    make, _, _, _ = session
    number = make(total=5)
    store.change(number, stage=stage, state='held', reason='held by its chair.')
    before = store.discussion(number)
    monkeypatch.setattr(server.runner, 'spawn', lambda *_: pytest.fail('Advance must not restart a private phase.'))
    with pytest.raises(server.ToolError):
        server.advanced(before)
    assert store.discussion(number) == before

def test_profile_scores_accumulate_once_per_session_and_start_unscored(session):
    make, _, _, _ = session
    first, second, third = make(), make(), make()
    assert store.profile('claude/haiku') is None
    assert store.rated('claude/haiku', 'Haiku', [], discussion=first)['score'] is None
    assert store.rated('claude/haiku', 'Haiku', [], discussion=second)['score'] is None
    assert store.rated('claude/haiku', 'Haiku', [100, 55], discussion=third)['score'] == 155
    assert store.rated('claude/haiku', 'Haiku', [100, 55], discussion=third)['score'] == 155
    assert store.profile('claude/haiku')['ratings'] == 2
    assert store.profile('claude/haiku')['sessions'] == 3


def test_participants_using_the_same_model_keep_independent_profile_ratings(session):
    make, _, _, _ = session
    number = make()
    first = store.seats(number)[0]
    store.seat_change(number, 1, kind=first['kind'], id=first['id'], agent=first['agent'], model=first['model'])
    seated = store.seats(number)
    assert seated[0]['profile_key'] != seated[1]['profile_key']
    cards = []
    for row, stars in zip(seated, (2, 5), strict=True):
        other = seated[1 - row['position']]
        card = {other['name']: {**{category: stars for category in stages.CATEGORIES}, 'bonus': False}}
        cards.append({'position': row['position'], 'kind': 'score', 'text': json.dumps(card)})
    runner.Table(number).results(seated, cards)
    assert store.profile(seated[0]['profile_key'])['score'] == 100
    assert store.profile(seated[1]['profile_key'])['score'] == 40
    assert all(store.profile(row['profile_key'])['ratings'] == 1 for row in seated)


def test_future_session_context_contains_only_aggregate_profile_scores(session):
    make, _, _, _ = session
    first, second = make(), make()
    row = store.seats(first)[0]
    names = [one['name'] for one in store.seats(first)]
    initial = render.system(store.discussion(first), names, row['name'])
    assert 'Your profile score is unscored.' in initial
    store.rated(row['profile_key'], row['name'], [100, 55], discussion=first)
    carried = render.system(store.discussion(second), names, row['name'])
    assert 'Your profile score is 155.' in carried
    assert '2 ratings across 1 earlier sessions' in carried
    assert 'accolade' not in carried.casefold()


@pytest.mark.parametrize('bonus', ['false', 1, None])
def test_scorecard_bonus_requires_a_boolean(bonus):
    card = {'Sol': {**{name: 5 for name in stages.CATEGORIES}, 'bonus': bonus}}
    assert stages.scorecard(json.dumps(card), ['Sol']) is None
