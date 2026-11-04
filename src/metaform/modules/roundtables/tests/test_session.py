"""Session phases keep busy work alive and score participants without exposing their scorecards."""
import asyncio
import json

import pytest

from metaform.modules.roundtables.roundtable import export, render, runner, server, stages, store
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


def test_advance_after_discussion_names_the_panel_and_preserves_held_collaboration(session, monkeypatch):
    make, _, _, _ = session
    number = make(total=5)
    store.change(number, topic=3)
    runner.Table(number).collaboration(store.discussion(number))
    store.change(number, state='held', reason='held by its chair.')
    before = store.discussion(number)
    monkeypatch.setattr(server.runner, 'spawn', lambda *_: pytest.fail('Advance must not start collaboration.'))
    with pytest.raises(server.ToolError, match=r'Panel 4.*collaboration') as error:
        server.advanced(before)
    assert f'Roundtable {number}' not in str(error.value)
    assert store.discussion(number) == before


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


def test_missing_next_topic_holds_and_can_resume_without_losing_the_session(session):
    make, handlers, _, materials = session
    number = make(total=2)

    async def done(seat, text):
        return 'Done'

    handlers[('collaboration', 0, 0)] = done
    handlers[('collaboration', 0, 1)] = done
    held = asyncio.run(runner.Table(number).run())
    assert held['state'] == 'held'
    assert store.discussion(number)['stage'] == 'collaboration'
    assert not store.scorecards(number)
    (materials / 'next-topic.md').write_text('Explore the next topic.', encoding='utf-8')
    store.change(number, state='running')
    finished = asyncio.run(runner.Table(number).run())
    assert finished['state'] == 'ended'
    assert len(store.topics(number)) == 2


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
