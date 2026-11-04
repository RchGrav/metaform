"""Reported phase budgets are per participant, durable, and independent of PASS/DONE votes."""
import asyncio
import json

import pytest

from metaform.modules.roundtables.roundtable import budget, judge, runner, stages, store
from metaform.modules.roundtables.roundtable.seat import NoReply, Reply, Seat

pytestmark = pytest.mark.kind('simulation')


@pytest.fixture
def phase_table(tmp_path, monkeypatch):
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

    def make(maximum=100, total=1, judging=False):
        seats = [{'kind': 'acp', 'id': f'acp:claude/{name}', 'agent': 'claude', 'model': name}
                 for name in ('haiku', 'sonnet', 'opus')]
        return store.opened({'subject': 'phase budget', 'opening': 'Preserve original session instructions.',
                             'folder': str(tmp_path), 'chair_key': None, 'chair_token': 'fixture',
                             'reporter': seats[0]['id'], 'rounds': 0, 'spend': 1}, seats,
                            [{'name': 'first', 'title': 'First topic', 'text': 'Explore the first topic.'}],
                            judging=judging, token_budget=maximum,
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


def test_phase_usage_survives_restart_and_limit_changes_but_resets_for_each_phase_and_topic(phase_table):
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
    assert all(budget.prompt(found, position).text == '' for position in range(3))
    assert store.submissions(number) == [] and store.discussion(number)['pass_after'] == 0


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


def test_caps_cancel_busy_participants_and_advance_both_phases_without_done(phase_table):
    make, handlers, calls, cancelled, materials = phase_table
    number = make(total=2)
    note = materials / 'retained-proof.txt'
    note.write_text('Keep these completed materials.', encoding='utf-8')
    table = runner.Table(number)

    async def scenario():
        entered = {}
        gates = {}

        async def busy(seat, text):
            found = table.row()
            phase_key = (found['stage'], found['topic'])
            entered[phase_key] = entered.get(phase_key, 0) + 1
            gate = gates.setdefault(phase_key, asyncio.Event())
            if entered[phase_key] == 3:
                gate.set()
            await gate.wait()
            if seat.position:
                await asyncio.Event().wait()
            if found['stage'] == 'discussion' and found['topic'] == 0:
                store.change(number, handoff={'after': 0})
                store.record(number, table.entry(found, store.seats(number)[0], 'Keep the saved handoff note.',
                                                 kind='carry'))
            if found['stage'] == 'collaboration' and found['topic'] == 0:
                (materials / 'next-topic.md').write_text('Agents submitted this next topic.', encoding='utf-8')
            return Reply(f'Completed material from {found["stage"]}.', {'prompt_tokens': 100, 'completion_tokens': 20})

        for phase_key in [('discussion', 0), ('collaboration', 0), ('collaboration', 1)]:
            for position in range(3):
                handlers[(*phase_key, position)] = busy
        result = await asyncio.wait_for(table.run(), 5)
        assert result['state'] == 'ended', result

    asyncio.run(scenario())
    assert len(store.topics(number)) == 2
    assert store.topics(number)[0]['advanced_by'] == 'budget'
    assert store.discussion(number)['handoff'] is None
    assert any(row['kind'] == 'carry' and row['text'] == 'Keep the saved handoff note.'
               for row in store.submissions(number))
    assert note.read_text() == 'Keep these completed materials.'
    assert (materials / 'topics' / '02.md').read_text() == 'Agents submitted this next topic.'
    assert all(phase_key in {(stage, topic) for stage, topic, _ in cancelled}
               for phase_key in [('discussion', 0), ('collaboration', 0), ('collaboration', 1)])
    assert any(row['kind'] == 'collab' and 'Completed material' in row['text'] for row in store.submissions(number))
    assert not table.panel_work and not table.working
    assert any(stage == 'scoring' for stage, _, _, _ in calls)


def test_collaboration_cap_with_no_next_topic_holds_without_inventing_one(phase_table):
    make, _, _, _, materials = phase_table
    number = make(total=2)
    table = runner.Table(number)
    table.collaboration(table.row())
    received(number, 0, 120, 'collab-cap')
    store.change(number, handoff={'after': 0})
    assert asyncio.run(table.enforce_budget(table.row())) is True
    found = table.row()
    assert found['state'] == 'held' and found['stage'] == 'collaboration'
    assert 'next topic' in found['reason'].casefold()
    assert len(store.topics(number)) == 1 and not (materials / 'next-topic.md').exists()
    assert found['handoff'] is None


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
    table.collaboration(table.row())
    store.record(number, table.entry(table.row(), rows[1], 'Old collaboration.', kind='collab', prompt_tokens=20,
                                     cached_tokens=30, completion_tokens=10))
    assert [row['tokens'] for row in budget.status(table.row())['participants']] == [0, 60, 0]


@pytest.mark.parametrize('phase', ['panel', 'collaboration'])
@pytest.mark.parametrize('action', ['hold', 'disable'])
def test_phase_cap_respects_person_changes_while_busy_work_is_closing(phase_table, monkeypatch, phase, action):
    make, _, _, _, materials = phase_table
    number = make(total=2)
    table = runner.Table(number)
    if phase == 'collaboration':
        table.collaboration(table.row())
    received(number, 0, 120, 'cap-before-control')
    submitted = materials / 'next-topic.md'
    submitted.write_text('The submitted next topic.', encoding='utf-8')

    async def stopped():
        found = table.row()
        if action == 'hold':
            store.change(number, state='held', reason='Held by the person.')
        else:
            store.change(number, snapshot={**found['snapshot'], 'token_budget': 0})

    monkeypatch.setattr(table, 'unseat', stopped)
    assert asyncio.run(table.enforce_budget(table.row())) is True
    assert table.row()['stage'] == ('discussion' if phase == 'panel' else 'collaboration')
    assert submitted.is_file()
    assert len(store.topics(number)) == 1
