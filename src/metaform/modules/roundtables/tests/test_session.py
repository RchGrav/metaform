"""Session phases keep busy work alive and score participants without exposing their scorecards."""
import asyncio
import json
import time
from pathlib import Path

import pytest

from metaform.modules.roundtables.roundtable import budget, export, render, runner, server, stages, store
from metaform.modules.roundtables.roundtable.seat import Reply, Seat

pytestmark = pytest.mark.kind('simulation')


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    calls = []
    handlers = {}
    materials = tmp_path / 'materials'
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
            if found['stage'] == 'scoring':
                others = [row['name'] for row in store.seats(self.number) if row['position'] != self.position]
                return Reply(json.dumps({name: {**{category: 5 for category in stages.CATEGORIES}, 'bonus': False}
                                         for name in others}) + '\nDone')
            if found['stage'] == 'collaboration' and found['topic'] == 0:
                (materials / 'next-topic.md').write_text('Explore the second topic.', encoding='utf-8')
            return Reply('Done')

    monkeypatch.setitem(runner.KINDS, 'acp', Fake)

    def make(total=1):
        seats = [{'kind': 'acp', 'id': 'acp:claude/haiku', 'agent': 'claude', 'model': 'haiku'},
                 {'kind': 'acp', 'id': 'acp:codex/sol', 'agent': 'codex', 'model': 'sol'}]
        return store.opened({'subject': 'session', 'opening': 'Original session instructions.',
                             'folder': str(tmp_path), 'chair_key': None, 'chair_token': 'fixture',
                             'reporter': seats[0]['id'], 'rounds': 0, 'spend': 1}, seats,
                            [{'name': 'first', 'title': 'First topic', 'text': 'Explore the first topic.'}],
                            judging=False, reply_limit=80,
                            session={'total': total, 'folder': str(materials), 'between': 'Collaborate after {index}.',
                                     'score': 'Send your anonymous scorecard.', 'farewell': 'Say farewell.'})

    return make, handlers, calls, materials


def test_busy_seat_keeps_working_while_another_speaks_and_session_finishes(session):
    make, handlers, calls, materials = session
    number = make(total=2)

    async def scenario():
        slow_started, fast_started, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        active = 0

        async def slow(seat, text):
            nonlocal active
            active += 1
            assert active == 1, 'A busy seat received an overlapping prompt.'
            slow_started.set()
            await release.wait()
            active -= 1
            return 'Done'

        async def fast(seat, text):
            fast_started.set()
            (materials / 'next-topic.md').write_text('Explore the second topic.', encoding='utf-8')
            return 'Done'

        handlers[('collaboration', 0, 0)] = slow
        handlers[('collaboration', 0, 1)] = fast
        table = runner.Table(number)
        task = asyncio.create_task(table.run())
        await asyncio.wait_for(slow_started.wait(), 2)
        await asyncio.wait_for(fast_started.wait(), 2)
        assert not task.done()
        assert store.discussion(number)['stage'] == 'collaboration'
        assert 0 in table.working and not table.working[0].done()
        assert not any(row['kind'] == 'pass' and row['topic'] == 1 for row in store.submissions(number))
        release.set()
        result = await asyncio.wait_for(task, 5)
        assert not table.working
        return result

    result = asyncio.run(scenario())
    assert result['state'] == 'ended', result
    assert len(store.topics(number)) == 2
    assert (materials / 'topics' / '02.md').read_text() == 'Explore the second topic.'
    assert {stage for stage, _, _, _ in calls} >= {'discussion', 'collaboration', 'scoring', 'farewell'}
    assert len(store.scorecards(number)) == 2
    assert all(row['kind'] != 'score' for row in export.build(number)['submissions'])
    for stage, _, _, text in calls:
        if stage in ('scoring', 'farewell'):
            assert '{"Sol":' not in text and '{"Haiku":' not in text
    assert all('{"Sol":' not in message['content'] and '{"Haiku":' not in message['content']
               for row in store.seats(number) for message in row['messages'])
    assert store.profile('claude/haiku')['score'] == 100
    assert store.profile('codex/sol')['score'] == 100


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


@pytest.mark.parametrize('stage', ['scoring', 'farewell'])
def test_advance_after_discussion_names_the_panel_and_preserves_held_later_phase(session, monkeypatch, stage):
    make, _, _, _ = session
    number = make(total=5)
    store.change(number, topic=3)
    store.change(number, stage=stage, state='held', reason='held by its chair.')
    before = store.discussion(number)
    monkeypatch.setattr(server.runner, 'spawn', lambda *_: pytest.fail('Advance must not start a later phase.'))
    with pytest.raises(server.ToolError, match=rf'Panel 4.*{stage}') as error:
        server.advanced(before)
    assert f'Roundtable {number}' not in str(error.value)
    assert store.discussion(number) == before


@pytest.mark.parametrize('held', [False, True])
@pytest.mark.parametrize('total', [1, 2])
def test_end_discussion_advances_collaboration_and_preserves_completed_and_stopping_work(
        session, home, monkeypatch, held, total):
    make, handlers, calls, materials = session
    number = make(total=total)
    role = {'kind': 'acp', 'id': 'acp:claude/haiku', 'agent': 'claude', 'model': 'haiku', 'name': 'Haiku'}
    store.change(number, host=role, synthesizer=role)
    table = runner.Table(number)
    table.collaboration(table.row())
    document = materials / 'saved.md'
    document.write_text('Keep these shared materials.', encoding='utf-8')
    if total > 1:
        (materials / 'next-topic.md').write_text('The agreed next topic.', encoding='utf-8')
    spawned = []
    monkeypatch.setattr(server.runner, 'spawn', lambda given: spawned.append(given))

    async def scenario():
        completed, started, cancelled = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def fast(seat, text):
            completed.set()
            return 'Kept completed work. Done'

        async def slow(seat, text):
            seat.delivered()
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                return 'Finished while cancellation landed.'

        handlers[('collaboration', 0, 0)] = fast
        handlers[('collaboration', 0, 1)] = slow
        active = asyncio.create_task(table.run())
        await asyncio.wait_for(completed.wait(), 2)
        await asyncio.wait_for(started.wait(), 2)
        if held:
            store.change(number, state='held', reason='held by its chair.')
            await table.unseat()
            await asyncio.wait_for(active, 2)
            transition = runner.Table(number)
        else:
            transition = table
        original = transition.phase_done

        async def stop_at_transition(found, stage, seated, phase, *, forced=False):
            await original(found, stage, seated, phase, forced=forced)
            store.change(number, state='held', reason='Fixture stops at the new phase.')

        monkeypatch.setattr(transition, 'phase_done', stop_at_transition)
        store.change(number, handoff={'after': 0})
        answer = await asyncio.to_thread(server.advanced, store.discussion(number))
        assert answer['state'] == 'running'
        if held:
            active = asyncio.create_task(transition.run())
        result = await asyncio.wait_for(active, 3)
        assert result['state'] == 'held'
        assert cancelled.is_set() and not transition.working

    asyncio.run(scenario())
    found = store.discussion(number)
    assert found['stage'] == ('discussion' if total > 1 else 'scoring')
    assert found['topic'] == (1 if total > 1 else 0)
    assert not found['advance_asked'] and found['handoff'] is None
    assert document.read_text(encoding='utf-8') == 'Keep these shared materials.'
    replies = [row['text'] for row in store.submissions(number) if row['kind'] == 'collab']
    assert replies == ['Kept completed work. Done', 'Finished while cancellation landed.']
    assert [(stage, topic, position) for stage, topic, position, _ in calls] == [
        ('collaboration', 0, 0), ('collaboration', 0, 1)]
    assert spawned == [number]
    if total > 1:
        assert (materials / 'topics' / '02.md').read_text() == 'The agreed next topic.'


def test_end_collaboration_without_a_submitted_topic_opens_scoring_without_inventing_one(session, home, monkeypatch):
    make, _, calls, _ = session
    number = make(total=2)
    role = {'kind': 'acp', 'id': 'acp:claude/haiku', 'agent': 'claude', 'model': 'haiku', 'name': 'Haiku'}
    store.change(number, host=role, synthesizer=role)
    table = runner.Table(number)
    table.collaboration(table.row())
    monkeypatch.setattr(server.runner, 'spawn', lambda *_: None)
    server.advanced(store.discussion(number))
    asyncio.run(table.finish_collaboration(table.row()))
    assert store.discussion(number)['state'] == 'running'
    assert store.discussion(number)['stage'] == 'scoring'
    assert not store.discussion(number)['advance_asked']
    assert any('No next topic was submitted' in row['text'] for row in store.submissions(number))
    assert len(store.topics(number)) == 1 and not calls


def test_end_collaboration_refuses_an_old_live_runner_before_changing_state(session, monkeypatch):
    make, _, _, _ = session
    number = make(total=2)
    table = runner.Table(number)
    table.collaboration(table.row())
    store.change(number, state='held', reason='held by its chair.', runner='old-runner', beat=time.time())
    before = store.discussion(number)
    monkeypatch.setattr(server.runner, 'spawn', lambda *_: pytest.fail('The old runner must not receive advance.'))
    with pytest.raises(server.ToolError, match=r'Panel 1.*reload'):
        server.advanced(before)
    assert store.discussion(number) == before


@pytest.mark.parametrize('stage', ['discussion', 'collaboration'])
@pytest.mark.parametrize('percent', [50, 80, 100, 120])
def test_winddown_thresholds_keep_running_and_only_120_percent_advances(session, stage, percent):
    make, _, calls, materials = session
    number = make(total=2)
    table = runner.Table(number)
    if stage == 'collaboration':
        table.collaboration(table.row())
        (materials / 'next-topic.md').write_text('The submitted next topic.', encoding='utf-8')
    found = table.row()
    store.change(number, snapshot={**found['snapshot'], 'token_budget': 100})
    budget.record_reply(table.row(), store.seats(number)[0], {'completion_tokens': percent}, 'winddown-reply')
    advanced = asyncio.run(table.enforce_budget(table.row()))
    found = table.row()
    assert found['state'] == 'running'
    assert advanced is (percent == 120)
    if percent < 120:
        assert found['stage'] == stage and found['topic'] == 0
    else:
        assert found['stage'] == ('collaboration' if stage == 'discussion' else 'discussion')
        assert found['topic'] == (0 if stage == 'discussion' else 1)
    assert calls == []


@pytest.mark.parametrize('held', [False, True])
def test_end_session_from_collaboration_saves_record_and_documents_without_more_agent_turns(
        session, monkeypatch, held):
    make, _, calls, materials = session
    number = make(total=5)
    role = {'kind': 'acp', 'id': 'acp:claude/haiku', 'agent': 'claude', 'model': 'haiku', 'name': 'Haiku'}
    store.change(number, host=role, synthesizer=role)
    table = runner.Table(number)
    table.collaboration(table.row())
    store.record(number, {'topic': 0, 'round': 1, 'position': 0, 'kind': 'collab',
                          'seat': 'acp:claude/haiku', 'name': 'Haiku', 'text': 'Saved work before ending.'})
    document = materials / 'decisions.md'
    document.write_text('Decisions remain saved.', encoding='utf-8')
    if held:
        store.change(number, state='held', reason='held by its chair.')
    spawned = []
    monkeypatch.setattr(server.runner, 'spawn', lambda given: spawned.append(given))
    answer = server.ended(store.discussion(number))
    assert answer['state'] == 'ending' and spawned == [number]
    result = asyncio.run(table.run())
    assert result['state'] == 'ended'
    found = store.discussion(number)
    assert found['runner'] is None
    assert document.read_text() == 'Decisions remain saved.'
    assert Path(found['report']).is_file()
    assert Path(found['export']).is_file()
    exported = json.loads(Path(found['export']).read_text())
    assert any(row['text'] == 'Saved work before ending.' for row in exported['submissions'])
    assert len(store.topics(number)) == 1
    assert calls == []


def test_future_session_context_contains_only_aggregate_profile_scores(session):
    make, _, _, _ = session
    first, second = make(), make()
    row = store.seats(first)[0]
    initial = render.system(store.discussion(first), ['Haiku', 'Sol'], row['name'])
    assert 'Your profile score is unscored.' in initial
    store.rated('claude/haiku', row['name'], [100, 55], discussion=first)
    carried = render.system(store.discussion(second), ['Haiku', 'Sol'], row['name'])
    assert 'Your profile score is 155.' in carried
    assert '2 ratings across 1 earlier sessions' in carried
    assert 'accolade' not in carried.casefold()


def test_unavailable_participant_never_implies_done(session):
    make, _, _, _ = session
    number = make()
    table = runner.Table(number)
    table.collaboration(table.row())
    store.seat_change(number, 1, gone='Agent exited.', availability='unavailable')

    async def scenario():
        for _ in range(3):
            await table.collaborate(table.row())
            await asyncio.sleep(0)
        await table.unseat()

    asyncio.run(scenario())
    found = store.discussion(number)
    assert found['state'] == 'held'
    assert found['stage'] == 'collaboration'
    assert not store.scorecards(number)


def test_missing_next_topic_requests_the_file_and_continues_without_a_manual_resume(session):
    make, handlers, calls, materials = session
    number = make(total=2)

    async def done(seat, text):
        if seat.position == 0 and 'No next topic was submitted.' in text:
            (materials / 'next-topic.md').write_text('Explore the next topic.', encoding='utf-8')
        return 'Done'

    handlers[('collaboration', 0, 0)] = done
    handlers[('collaboration', 0, 1)] = done
    finished = asyncio.run(runner.Table(number).run())
    assert finished['state'] == 'ended'
    assert len(store.topics(number)) == 2
    assert len([row for row in store.submissions(number) if 'No next topic was submitted.' in row['text']]) == 1
    assert all(sum('No next topic was submitted.' in text for stage, topic, position, text in calls
                   if stage == 'collaboration' and topic == 0 and position == seat) == 1 for seat in (0, 1))


def test_non_done_replies_do_not_finish_after_an_arbitrary_turn_count(session):
    make, handlers, _, _ = session
    number = make()
    count = 0

    async def still_working(seat, text):
        nonlocal count
        count += 1
        return 'I am still checking the materials.' if count < 5 else 'Done'

    handlers[('collaboration', 0, 0)] = still_working
    result = asyncio.run(runner.Table(number).run())
    assert result['state'] == 'ended', result
    assert count >= 5


def test_unseat_cancels_and_drains_active_phase_work(session):
    make, handlers, _, _ = session
    number = make()

    async def scenario():
        started, cancelled = asyncio.Event(), asyncio.Event()

        async def blocked(seat, text):
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        handlers[('collaboration', 0, 0)] = blocked
        table = runner.Table(number)
        table.collaboration(table.row())
        await table.collaborate(table.row())
        await started.wait()
        await asyncio.wait_for(table.unseat(), 2)
        assert cancelled.is_set()
        assert table.working == {}
        assert table.seated == {}

    asyncio.run(scenario())


@pytest.mark.parametrize('bonus', ['false', 1, None])
def test_scorecard_bonus_requires_a_boolean(bonus):
    card = {'Sol': {**{name: 5 for name in stages.CATEGORIES}, 'bonus': bonus}}
    assert stages.scorecard(json.dumps(card), ['Sol']) is None
