"""Reported phase budgets are per participant, durable, and independent of PASS/DONE votes."""
import asyncio
import json
from unittest.mock import Mock

import pytest

from metaform.modules.roundtables.roundtable import budget, judge, runner, server, stages, store, topics
from metaform.modules.roundtables.roundtable.seat import NoReply, Reply, Seat

pytestmark = pytest.mark.kind('simulation')


@pytest.fixture
def phase_table(run, tmp_path, monkeypatch):
    run('enable', 'dispatch', cwd=tmp_path)
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    materials = tmp_path / 'materials'
    materials.mkdir()
    handlers, calls, cancelled = {}, [], []

    class Fake(Seat):
        async def open(self):
            self.session = self.session or f'phase-{self.position}'

        async def exchange(self, text, seconds):
            await self.open()
            found = store.discussion(self.number)
            key = (found['stage'], found['topic'], self.position)
            calls.append((*key, text))
            await asyncio.sleep(0)
            try:
                if key in handlers:
                    return await handlers[key](self, text)
                if found['stage'] == 'discussion':
                    return Reply('PASS', {'prompt_tokens': 0, 'completion_tokens': 0})
                if found['stage'] == 'scoring':
                    others = [row['name'] for row in store.seats(self.number) if row['position'] != self.position]
                    return Reply(json.dumps({name: {**{category: 5 for category in stages.CATEGORIES}, 'bonus': False}
                                             for name in others}))
                return Reply('Done', {'prompt_tokens': 0, 'completion_tokens': 0})
            except asyncio.CancelledError:
                cancelled.append(key)
                raise

        async def report(self, text, seconds):
            return 'Fixture report.'

    monkeypatch.setitem(runner.KINDS, 'acp', Fake)

    def make(maximum=100, total=1, judging=False, token_basis='all'):
        seats = [{'kind': 'acp', 'id': f'acp:claude/{name}', 'agent': 'claude', 'model': name}
                 for name in ('haiku', 'sonnet', 'opus')]
        role = {**seats[0], 'name': 'Fixture host'}
        return store.opened({'subject': 'phase budget', 'opening': 'Preserve original session instructions.',
                             'folder': str(tmp_path), 'chair_key': None, 'chair_token': 'fixture',
                             'reporter': seats[0]['id'], 'host': role, 'synthesizer': role,
                             'rounds': 0, 'spend': 1}, seats,
                            [{'name': 'first', 'title': 'First topic', 'text': 'Explore the first topic.'}],
                            judging=judging, token_budget=maximum, token_basis=token_basis,
                            session={'total': total, 'folder': str(materials), 'between': 'Collaborate after {index}.',
                                     'score': 'Send your anonymous scorecard.', 'farewell': 'Say farewell.'})

    return make, handlers, calls, cancelled, materials


def received(number, position, amount, receipt, prepared=None):
    budget.record_reply(store.discussion(number), store.seats(number)[position],
                        {'prompt_tokens': amount, 'completion_tokens': 0}, receipt, prepared)


def test_transport_usage_counts_cache_input_once_and_does_not_add_reasoning_or_context_size():
    assert budget.tokens({'prompt_tokens': 30, 'cached_tokens': 40, 'cache_write_tokens': 10,
                          'completion_tokens': 20, 'reasoning_tokens': 15}, 'acp') == (100, True)
    assert budget.tokens({'prompt_tokens': 80, 'cached_tokens': 40, 'cache_write_tokens': 10,
                          'completion_tokens': 20, 'reasoning_tokens': 15}, 'openrouter') == (100, True)
    assert budget.tokens({'used': 90000, 'size': 200000, 'reasoning_tokens': 100}, 'acp') == (0, False)


def test_thresholds_are_inclusive_once_only_and_follow_first_participant_instead_of_sum(phase_table):
    make, _, _, _, _ = phase_table
    number = make()
    received(number, 0, 40, 'a')
    received(number, 1, 40, 'b')
    assert budget.status(store.discussion(number))['notices'] == []
    received(number, 1, 10, 'c')
    received(number, 1, 10, 'c')
    assert budget.status(store.discussion(number))['participants'][1]['tokens'] == 50
    assert budget.status(store.discussion(number))['notices'][0]['position'] == 1
    received(number, 0, 40, 'd')
    received(number, 2, 100, 'e')
    received(number, 2, 20, 'f')
    state = budget.status(store.discussion(number))
    assert [one['percent'] for one in state['notices']] == [50, 80, 100, 120]
    assert [one['position'] for one in state['notices']] == [1, 0, 2, 2]
    assert state['forced'] is True
    assert len([one for one in store.events(number) if one['kind'] == 'budget']) == 4
    assert store.submissions(number) == []
    assert store.discussion(number)['pass_after'] == 0


def test_historical_phase_usage_survives_restart_and_limit_changes_and_remains_separate(phase_table):
    make, _, _, _, _ = phase_table
    number = make(maximum=0)
    received(number, 0, 80, 'panel-first')
    assert budget.evaluate(store.discussion(number))['notices'] == []
    found = store.discussion(number)
    store.change(number, snapshot={**found['snapshot'], 'token_budget': 100})
    assert [one['percent'] for one in budget.evaluate(store.discussion(number))['notices']] == [50, 80]
    found = store.discussion(number)
    store.change(number, snapshot={**found['snapshot'], 'token_budget': 200})
    assert budget.status(runner.Table(number).row())['participants'][0]['tokens'] == 80
    store.phase(number, 'collaboration', 'Write the shared materials.')
    assert budget.status(store.discussion(number))['participants'][0]['tokens'] == 0
    received(number, 0, 30, 'collaboration-first')
    store.add_topic(number, 'Explore a second topic.')
    store.change(number, stage='discussion', topic=1)
    assert budget.status(store.discussion(number))['participants'][0]['tokens'] == 0
    received(number, 0, 25, 'panel-second')
    with store.connect() as db:
        rows = db.execute('SELECT topic,phase,tokens FROM phase_usage WHERE discussion=? ORDER BY topic,phase',
                          (number,)).fetchall()
    assert [(row['topic'], row['phase'], row['tokens']) for row in rows] == [
        (0, 'collaboration', 30), (0, 'panel', 80), (1, 'panel', 25)]


def test_progress_exposes_fresh_zero_and_actual_first_turn_without_seeding_or_mutation(phase_table, monkeypatch):
    make, _, _, _, _ = phase_table
    number = make(maximum=500000)
    role = store.seats(number)[0]
    store.change(number, host=role, synthesizer=role)
    received(number, 0, 715295, 'previous-panel')
    store.phase(number, 'collaboration', 'Start collaborating.')
    tables = ('phase_usage', 'phase_replies', 'phase_notices', 'phase_seed')

    def saved():
        with store.connect() as db:
            return {name: [tuple(row) for row in db.execute(f'SELECT * FROM {name} ORDER BY rowid')]
                    for name in tables}

    before = saved()
    with monkeypatch.context() as guard:
        def forbidden(*args, **kwargs):
            raise AssertionError('Reading progress must not initialize, evaluate or fence a runner.')
        guard.setattr(budget, '_initialize', forbidden)
        guard.setattr(budget, '_evaluate', forbidden)
        guard.setattr(store, 'fence', forbidden)
        fresh = budget.progress(store.discussion(number))
        assert fresh['phase'] == 'collaboration' and fresh['topic'] == 1
        assert fresh['limit'] == 500000
        assert fresh['basis'] == 'all'
        assert [one['tokens'] for one in fresh['participants']] == [0, 0, 0]
        assert fresh['notices'] == [] and not fresh['closing'] and not fresh['forced']
    assert saved() == before
    found = store.discussion(number)
    budget.record_reply(found, store.seats(number)[0], {'prompt_tokens': 12, 'cached_tokens': 462034,
                                                      'cache_write_tokens': 14223, 'completion_tokens': 3208},
                        'first-collaboration-turn')
    before = saved()
    current = server.status_of(store.discussion(number))['phase_budget']
    assert current['participants'][0]['tokens'] == 479477
    assert current['participants'][0]['reported']
    assert [one['percent'] for one in current['notices']] == [50, 80]
    assert saved() == before
    store.add_topic(number, 'Open the next panel.')
    store.change(number, topic=1, stage='discussion')
    next_panel = budget.progress(store.discussion(number))
    assert next_panel['phase'] == 'panel' and next_panel['topic'] == 2
    assert [one['tokens'] for one in next_panel['participants']] == [0, 0, 0]
    assert saved() == before


def test_budget_notices_identify_their_roundtable_and_phase(phase_table):
    make, _, _, _, _ = phase_table
    number = make()
    received(number, 0, 120, 'first-panel')
    assert all('roundtable 1' in one['text'].lower() and 'panel' in one['text'].lower()
               for one in budget.progress(store.discussion(number))['notices'])
    store.add_topic(number, 'A second topic.')
    store.change(number, topic=1)
    store.phase(number, 'collaboration', 'Collaborate on topic two.')
    received(number, 0, 120, 'second-collaboration')
    assert all('roundtable 2' in one['text'].lower() and 'collaboration' in one['text'].lower()
               for one in budget.progress(store.discussion(number))['notices'])


def test_whole_phase_closing_messages_do_not_reset_votes_and_are_delivered_on_safe_turns(phase_table):
    make, _, _, _, _ = phase_table
    number = make()
    received(number, 1, 100, 'first-closing-trigger')
    found = store.discussion(number)
    for position in range(3):
        notice = budget.prompt(found, position)
        assert notice.closing and notice.notice == 100 and notice.text
        assert budget.needs_closing(found, position)
        received(number, position, 0, f'closing-{position}', notice)
    assert all(not budget.needs_closing(found, position) for position in range(3))
    assert all(budget.prompt(found, position).closing and 'panel closing' in budget.prompt(found, position).text
               for position in range(3))
    assert store.submissions(number) == [] and store.discussion(number)['pass_after'] == 0


def test_midpoint_is_once_and_winddown_repeats_with_current_peak_until_topic_selection(phase_table):
    make, _, _, _, _ = phase_table
    number = make(total=2)
    table = runner.Table(number)
    received(number, 0, 50, 'midpoint')
    found = table.row()
    for row in store.seats(number):
        first = budget.prompt(found, row['position'])
        assert 'midpoint notice' in first.text and '(50%)' in first.text
        budget.delivered_prompt(found, row['position'], first)
        assert not budget.prompt(found, row['position']).text
    received(number, 0, 30, 'winddown')
    notice_count = len(store.events(number))
    for _ in range(2):
        winddown = budget.prompt(table.row(), 2)
        assert 'wind-down' in winddown.text and '(80%)' in winddown.text
        assert 'midpoint notice' not in winddown.text
        assert 'coordinator' in winddown.text
        assert 'PASS' in winddown.text
        budget.delivered_prompt(table.row(), 2, winddown)
    assert len(store.events(number)) == notice_count
    received(number, 1, 85, 'new-peak')
    peak = budget.prompt(table.row(), 2)
    assert '(85%)' in peak.text and store.seats(number)[1]['name'] in peak.text
    received(number, 1, 15, 'closing')
    closing = budget.prompt(table.row(), 2)
    assert 'closing:' in closing.text and '(100%)' in closing.text
    budget.delivered_prompt(table.row(), 2, closing)
    assert 'closing:' in budget.prompt(table.row(), 2).text
    assert table.row()['state'] == 'running'
    assert asyncio.run(table.enforce_budget(table.row())) is False
    received(number, 1, 19, 'still-closing')
    assert '(119%)' in budget.prompt(table.row(), 2).text
    assert asyncio.run(table.enforce_budget(table.row())) is False
    assert table.row()['state'] == 'running'
    received(number, 1, 1, 'advance')
    assert not budget.prompt(table.row(), 2).text
    assert asyncio.run(table.enforce_budget(table.row())) is True
    assert table.row()['state'] == 'running' and table.row()['stage'] == 'topic_selection'
    assert budget.progress(table.row())['participants'][0]['tokens'] == 0
    assert not budget.prompt(table.row(), 2).text
    with store.connect() as db:
        assert db.execute("SELECT tokens FROM phase_usage WHERE discussion=? AND topic=0 AND phase='panel' "
                          'AND position=1', (number,)).fetchone()[0] == 120


@pytest.mark.parametrize('total', [1, 2])
def test_warnings_keep_running_through_119_percent_and_120_finishes_the_panel(phase_table, total):
    make, _, _, _, _ = phase_table
    number = make(maximum=100, total=total)
    table = runner.Table(number)
    previous = 0
    for percent in (50, 80, 100, 119):
        received(number, 0, percent - previous, f'usage-{percent}')
        previous = percent
        assert asyncio.run(table.enforce_budget(table.row())) is False
        found = table.row()
        assert found['state'] == 'running' and found['stage'] == 'discussion'
        assert not found['advance_asked']
    received(number, 0, 1, 'usage-120')
    assert asyncio.run(table.enforce_budget(table.row())) is True
    found = table.row()
    assert found['state'] == 'running'
    assert found['stage'] == ('topic_selection' if total > 1 else 'scoring')
    assert not found['advance_asked']


def test_missing_usage_is_unknown_without_text_or_context_estimates(phase_table):
    make, _, _, _, _ = phase_table
    number = make(maximum=1)
    budget.record_reply(store.discussion(number), store.seats(number)[0], {'used': 900000}, 'unknown')
    own = budget.status(store.discussion(number))['participants'][0]
    assert own['tokens'] == 0 and own['reported'] is False and own['unreported'] == 1
    assert not budget.evaluate(store.discussion(number))['forced']


def test_jev_retry_does_not_count_a_physical_reply_twice(phase_table, monkeypatch):
    make, handlers, calls, _, _ = phase_table
    number = make(maximum=1000, judging=True)

    async def contribution(seat, text):
        return Reply('Evidence worth retaining.', {'prompt_tokens': 10, 'completion_tokens': 5})

    handlers[('discussion', 0, 0)] = contribution
    monkeypatch.setattr(judge, 'ask', lambda *args, **kwargs: judge.Asked(request={}, error='Fixture failure.'))
    first = runner.Table(number)
    assert asyncio.run(first.turn(first.row(), store.seats(number)[0])) is False
    assert budget.status(first.row())['participants'][0]['tokens'] == 15
    store.change(number, state='running', reason=None)
    monkeypatch.setattr(judge, 'ask', lambda state, criteria, **kwargs: judge.Asked(
        request={'state': state}, criteria=criteria, nouls={name: .99 for name in criteria}))
    second = runner.Table(number)
    assert asyncio.run(second.turn(second.row(), store.seats(number)[0])) is True
    assert len(calls) == 1
    assert budget.status(second.row())['participants'][0]['tokens'] == 15


def test_cap_preserves_native_work_and_selection_opens_a_zero_budget_panel(phase_table, monkeypatch):
    make, handlers, calls, cancelled, materials = phase_table
    number = make(total=2)
    note = materials / 'retained-proof.txt'
    table = runner.Table(number)
    compared = Mock(side_effect=AssertionError('The one available proposal needs no comparison.'))
    monkeypatch.setattr(topics.openrouter, 'post', compared)
    monkeypatch.setattr(runner, 'spawn', lambda *_: None)

    async def scenario():
        entered, everyone, release, opened, finished = set(), asyncio.Event(), asyncio.Event(), asyncio.Event(), asyncio.Event()
        returned = []
        original = table.next_topic

        def stop_at_new_panel(found):
            original(found)
            current = table.row()
            assert current['stage'] == 'discussion' and current['topic'] == 1
            assert all(row['tokens'] == 0 for row in budget.progress(current)['participants'])
            store.change(number, state='held', reason='Fixture stops before any new-panel work.')
            opened.set()

        monkeypatch.setattr(table, 'next_topic', stop_at_new_panel)

        async def busy(seat, text):
            found = table.row()
            seat.delivered()
            entered.add(seat.position)
            if len(entered) == 3:
                everyone.set()
            await everyone.wait()
            if seat.position:
                await release.wait()
                returned.append(seat.position)
                if len(returned) == 2:
                    finished.set()
                return Reply('Late completed inline work.', {'prompt_tokens': 6, 'completion_tokens': 1})
            note.write_text('Keep these completed inline materials.', encoding='utf-8')
            store.change(number, handoff={'after': 0})
            store.record(number, table.entry(found, store.seats(number)[0], 'Keep the saved handoff note.', kind='carry'))
            return Reply('Completed inline file work.', {'prompt_tokens': 100, 'completion_tokens': 20})

        async def propose(seat, text):
            assert budget.phase(table.row()) is None
            return Reply('The available participant proposes the next question.', {'completion_tokens': 10})

        for position in range(3):
            handlers[('discussion', 0, position)] = busy
            handlers[('topic_selection', 0, position)] = propose
        task = asyncio.create_task(table.run())
        try:
            await asyncio.wait_for(opened.wait(), 3)
            assert not cancelled and not task.done()
            assert set(table.panel_work) == {1, 2}
            assert [row['session'] for row in store.seats(number)] == ['phase-0', 'phase-1', 'phase-2']
            assert all(row['tokens'] == 0 for row in budget.progress(table.row())['participants'])
            release.set()
            await asyncio.wait_for(finished.wait(), 2)
            await asyncio.sleep(0)
            assert not cancelled and not task.done()
            with store.connect() as db:
                usage = [tuple(row) for row in db.execute('SELECT topic,phase,position,tokens FROM phase_usage '
                                                         'WHERE discussion=? ORDER BY topic,phase,position', (number,))]
            assert usage == [(0, 'panel', 0, 120), (0, 'panel', 1, 7), (0, 'panel', 2, 7)]
            await asyncio.to_thread(server.ended, table.row())
            table.control.set()
            assert (await asyncio.wait_for(task, 5))['state'] == 'ended'
        finally:
            release.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())
    assert len(store.topics(number)) == 2
    assert store.topics(number)[0]['advanced_by'] == 'budget'
    assert store.discussion(number)['handoff'] is None
    assert note.read_text() == 'Keep these completed inline materials.'
    assert not cancelled and not table.panel_work and not table.working
    compared.assert_not_called()
    assert [position for stage, topic, position, _ in calls if stage == 'topic_selection'] == [0]
    late = [row for row in store.submissions(number) if row['text'] == 'Late completed inline work.']
    assert len(late) == 2 and all(row['topic'] == 0 and row['unjudged'] for row in late)


def test_end_discussion_starts_private_selection_and_cannot_advance_selection(phase_table, monkeypatch):
    make, _, _, _, materials = phase_table
    number = make(total=2)
    table = runner.Table(number)
    note = materials / 'decisions.md'
    note.write_text('Keep the completed decisions.', encoding='utf-8')
    store.change(number, handoff={'after': 0})
    spawn = Mock()
    monkeypatch.setattr(server.runner, 'spawn', spawn)
    monkeypatch.setattr(server.events, 'publish', Mock())
    server.advanced(table.row())
    table.discussed(table.row(), 'chair')
    found = table.row()
    assert found['state'] == 'running' and found['stage'] == 'topic_selection'
    assert len(store.topics(number)) == 1 and not (materials / 'next-topic.md').exists()
    assert found['handoff'] is None
    assert note.read_text() == 'Keep the completed decisions.'
    spawn.assert_called_once_with(number)
    with pytest.raises(server.ToolError, match='topic selection'):
        server.advanced(found)
    assert table.row() == found
    spawn.assert_called_once_with(number)


def test_carry_forward_usage_is_counted_once_when_a_failed_editor_is_retried(phase_table, monkeypatch):
    make, _, _, _, _ = phase_table
    number = make(maximum=1000)
    calls = []

    class Carry(Seat):
        async def exchange(self, text, seconds):
            calls.append(self.position)
            if self.position < 0 and calls.count(self.position) == 1:
                raise NoReply('Fixture editor failure.')
            return Reply('Preserved note and evidence.', {'prompt_tokens': 20, 'completion_tokens': 10})

    monkeypatch.setitem(runner.KINDS, 'acp', Carry)
    first = runner.Table(number)
    asyncio.run(first.handoff(first.row()))
    assert first.row()['state'] == 'held'
    assert [row['tokens'] for row in budget.status(first.row())['participants']] == [30, 30, 30]
    store.change(number, state='running', reason=None)
    second = runner.Table(number)
    asyncio.run(second.handoff(second.row()))
    assert [row['tokens'] for row in budget.status(second.row())['participants']] == [30, 30, 30]
    assert [calls.count(position) for position in range(3)] == [1, 1, 1]


@pytest.mark.parametrize('staged', [False, True])
def test_non_session_caps_preserve_standalone_ending_or_topic_synthesis(phase_table, staged):
    make, _, _, _, _ = phase_table
    number = make()
    found = store.discussion(number)
    snapshot = {key: value for key, value in found['snapshot'].items() if key != 'session'}
    store.change(number, snapshot=snapshot, stage='discussion' if staged else None)
    received(number, 0, 120, 'legacy-cap')
    table = runner.Table(number)
    assert asyncio.run(table.enforce_budget(table.row())) is True
    assert table.row()['state'] == ('running' if staged else 'ending')
    assert table.row()['stage'] == ('synthesis' if staged else None)
    assert not store.scorecards(number)


def test_existing_saved_and_pending_panel_usage_is_seeded_once_without_context_estimates(phase_table):
    make, _, _, _, _ = phase_table
    number = make(maximum=0)
    table = runner.Table(number)
    rows = store.seats(number)
    store.record(number, table.entry(table.row(), rows[0], 'Historical contribution.', prompt_tokens=10,
                                     cached_tokens=30, cache_write_tokens=5, completion_tokens=5))
    store.record(number, table.entry(table.row(), rows[1], 'PASS', kind='pass', prompt_tokens=25, completion_tokens=5))
    pending = {'original': 'A completed reply waiting for Jev.', 'use': {'prompt_tokens': 40, 'completion_tokens': 10},
               'round': 1, 'topic': 0, 'pass_after': 0}
    store.seat_change(number, 2, extra={'panel_reply': pending})
    store.change(number, unjudged={'position': 2, 'text': pending['original'], 'use': pending['use']})
    first = budget.status(table.row())
    assert [row['tokens'] for row in first['participants']] == [50, 30, 50]
    assert [row['tokens'] for row in budget.status(table.row())['participants']] == [50, 30, 50]
    saved = store.seats(number)[2]['extra']['panel_reply']
    budget.record_reply(table.row(), rows[2], pending['use'], saved['usage_id'])
    assert [row['tokens'] for row in budget.status(table.row())['participants']] == [50, 30, 50]
    store.change(number, snapshot={**table.row()['snapshot'], 'token_budget': 100})
    assert [one['percent'] for one in budget.evaluate(table.row())['notices']] == [50]


def test_existing_collaboration_usage_seeds_independently_from_panel_records(phase_table):
    make, _, _, _, _ = phase_table
    number = make()
    table = runner.Table(number)
    rows = store.seats(number)
    store.record(number, table.entry(table.row(), rows[0], 'Old panel.', prompt_tokens=900))
    store.phase(number, 'collaboration', 'Historical collaboration opening.')
    store.record(number, table.entry(table.row(), rows[1], 'Old collaboration.', kind='collab', prompt_tokens=20,
                                     cached_tokens=30, completion_tokens=10))
    assert [row['tokens'] for row in budget.status(table.row())['participants']] == [0, 60, 0]


@pytest.mark.parametrize('action', ['hold', 'disable'])
def test_panel_cap_respects_person_changes_while_busy_work_is_closing(phase_table, monkeypatch, action):
    make, _, _, _, materials = phase_table
    number = make(total=2)
    table = runner.Table(number)
    received(number, 0, 120, 'cap-before-control')
    submitted = materials / 'next-topic.md'
    submitted.write_text('The submitted next topic.', encoding='utf-8')

    def stopped():
        found = table.row()
        if action == 'hold':
            store.change(number, state='held', reason='Held by the person.')
        else:
            store.change(number, snapshot={**found['snapshot'], 'token_budget': 0})

    monkeypatch.setattr(table, 'archive_panel', stopped)
    assert asyncio.run(table.enforce_budget(table.row())) is True
    assert table.row()['stage'] == 'discussion'
    assert submitted.is_file()
    assert len(store.topics(number)) == 1
