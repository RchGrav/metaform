"""Panel turns skip busy agents and return ready agents to a fair rotation."""
import asyncio
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from metaform.modules.roundtables.roundtable import budget, judge, render, runner, store
from metaform.modules.roundtables.roundtable.seat import Gone, NoReply, Reply, Seat

pytestmark = pytest.mark.kind('simulation')


@pytest.fixture
def panel(tmp_path, monkeypatch):
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    handlers = {}
    opening = {}
    active = set()
    calls = []

    class Fake(Seat):
        async def open(self):
            if self.position in opening:
                await opening[self.position].wait()
            self.session = self.session or f'panel-{self.position}'

        async def exchange(self, text, seconds):
            await self.open()
            assert self.position not in active, 'An agent received overlapping panel prompts.'
            active.add(self.position)
            calls.append(self.position)
            try:
                if self.position in handlers:
                    return Reply(await handlers[self.position](self, text))
                return Reply('PASS')
            finally:
                active.remove(self.position)

        async def report(self, record, seconds):
            return 'Fixture panel report.'

    monkeypatch.setitem(runner.KINDS, 'acp', Fake)
    seats = [{'kind': 'acp', 'id': f'acp:claude/{name}', 'agent': 'claude', 'model': name}
             for name in ('haiku', 'sonnet', 'opus')]
    number = store.opened({'subject': 'panel', 'opening': 'Discuss the evidence.', 'folder': str(tmp_path),
                           'chair_key': None, 'chair_token': 'fixture', 'reporter': seats[0]['id'],
                           'rounds': 0, 'spend': 1}, seats, judging=False)
    return number, handlers, opening, active, calls


def test_panel_skips_permission_blocked_seat_and_lets_other_seats_continue(panel):
    number, handlers, _, active, calls = panel

    async def scenario():
        permission_needed, permission_answered, others_continued = asyncio.Event(), asyncio.Event(), asyncio.Event()
        count = {1: 0, 2: 0}

        async def blocked(seat, text):
            permission_needed.set()
            await permission_answered.wait()
            return 'PASS'

        async def continuing(seat, text):
            count[seat.position] += 1
            if min(count.values()) >= 2:
                others_continued.set()
            return f'New evidence from seat {seat.position}.' if count[seat.position] == 1 else 'PASS'

        handlers.update({0: blocked, 1: continuing, 2: continuing})
        task = asyncio.create_task(runner.Table(number).run())
        try:
            await asyncio.wait_for(permission_needed.wait(), 1)
            await asyncio.wait_for(others_continued.wait(), 1)
            assert 0 in active
            assert store.discussion(number)['state'] == 'running'
            assert store.discussion(number)['round'] == 1
            assert calls.count(0) == 1
            permission_answered.set()
            result = await asyncio.wait_for(task, 5)
            assert result['state'] == 'ended', result
            assert store.discussion(number)['round'] >= 2
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())
    assert active == set()


def test_panel_startup_does_not_wait_for_one_agents_file_access(panel):
    number, handlers, opening, _, calls = panel

    async def scenario():
        reading, another_spoke = asyncio.Event(), asyncio.Event()
        opening[0] = reading

        async def spoke(seat, text):
            another_spoke.set()
            return 'PASS'

        handlers[1] = spoke
        task = asyncio.create_task(runner.Table(number).run())
        try:
            await asyncio.wait_for(another_spoke.wait(), 1)
            assert 0 not in calls
            reading.set()
            assert (await asyncio.wait_for(task, 5))['state'] == 'ended'
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())


def test_panel_ready_seats_rejoin_before_a_fast_seat_gets_another_rotation(panel):
    number, handlers, _, _, _ = panel

    async def scenario():
        requested = asyncio.Queue()

        async def controlled(seat, text):
            response = asyncio.get_running_loop().create_future()
            await requested.put((seat.position, response))
            return await response

        handlers.update({position: controlled for position in range(3)})
        task = asyncio.create_task(runner.Table(number).run())
        try:
            first = [await asyncio.wait_for(requested.get(), 1) for _ in range(3)]
            assert [position for position, _ in first] == [0, 1, 2]
            responses = dict(first)
            responses[1].set_result('First evidence from seat one.')
            position, fast = await asyncio.wait_for(requested.get(), 1)
            assert position == 1
            responses[0].set_result('Evidence from the returning seat.')
            responses[2].set_result('Evidence from seat two.')
            returned = [await asyncio.wait_for(requested.get(), 1) for _ in range(2)]
            assert [position for position, _ in returned] == [2, 0]
            fast.set_result('PASS')
            for _, response in returned:
                response.set_result('PASS')
            handlers.clear()
            assert (await asyncio.wait_for(task, 5))['state'] == 'ended'
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())


@pytest.mark.parametrize('action', ['hold', 'advance', 'end'])
def test_all_busy_panel_wakes_for_chair_control_and_ignores_unrelated_events(panel, monkeypatch, action):
    number, handlers, _, active, _ = panel
    callbacks = []
    monkeypatch.setattr(runner.events, 'listen',
                        lambda module, callback: callbacks.append(callback) or SimpleNamespace(close=lambda: None))
    read = Mock(wraps=store.discussion)
    monkeypatch.setattr(store, 'discussion', read)

    async def scenario():
        everyone_busy = asyncio.Event()

        async def blocked(seat, text):
            if len(active) == 3:
                everyone_busy.set()
            await asyncio.Event().wait()

        handlers.update({position: blocked for position in range(3)})
        table = runner.Table(number)
        task = asyncio.create_task(table.run())
        try:
            await asyncio.wait_for(everyone_busy.wait(), 1)
            await asyncio.sleep(0)
            before = read.call_count
            for _ in range(250):
                callbacks[0]({'kinds': ['roundtables:control:another-table']})
            await asyncio.sleep(0)
            assert read.call_count == before
            transitions = {'hold': {'state': 'held', 'reason': 'Held by the person.'},
                           'advance': {'advance_asked': True},
                           'end': {'state': 'ending', 'reason': 'Ended by the person.'}}
            store.change(number, **transitions[action])
            callbacks[0]({'kinds': [f'roundtables:control:{number}']})
            result = await asyncio.wait_for(task, 1)
            assert result['state'] == ('held' if action == 'hold' else 'ended')
            assert not table.panel_work and not active
            assert not store.submissions(number)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())


def test_completed_replies_survive_a_jev_hold_without_prompting_agents_again(panel, monkeypatch):
    number, handlers, _, _, calls = panel
    names = [row['name'] for row in store.seats(number)]
    store.change(number, snapshot=render.snapshot(names, judging=True))
    contributions = ['Evidence about exact geometry.', 'Evidence about physics integration.',
                     'Evidence about context delivery.']

    async def contribute(seat, text):
        return contributions[seat.position] if calls.count(seat.position) == 1 else 'PASS'

    handlers.update({position: contribute for position in range(3)})
    monkeypatch.setattr(judge, 'ask', lambda *args, **kw: judge.Asked(request={}, error='Fixture Jev failure.'))
    first = asyncio.run(runner.Table(number).run())
    assert first['state'] == 'held'
    assert store.discussion(number)['unjudged']['text'] == contributions[0]
    assert [row['extra']['panel_reply']['original'] for row in store.seats(number)[1:]] == contributions[1:]
    assert calls == [0, 1, 2]
    monkeypatch.setattr(judge, 'ask', lambda state, criteria, **kwargs: judge.Asked(
        request={'state': state}, criteria=criteria, nouls={name: .99 for name in criteria}))
    store.change(number, state='running', reason=None)
    second = asyncio.run(runner.Table(number).run())
    assert second['state'] == 'ended', second
    assert [row['text'] for row in store.submissions(number) if row['kind'] == 'seat'] == contributions
    assert calls == [0, 1, 2, 0, 1, 2, 0, 1, 2]


@pytest.mark.parametrize('ready_passes', [False, True])
def test_busy_participant_does_not_count_toward_two_judged_quiet_rounds(panel, monkeypatch, ready_passes):
    number, handlers, _, _, calls = panel
    names = [row['name'] for row in store.seats(number)]
    store.change(number, snapshot=render.snapshot(names, judging=True))
    monkeypatch.setattr(judge, 'ask', lambda state, criteria, **options: judge.Asked(
        request={'state': state}, criteria=criteria, nouls={name: .1 for name in criteria}))

    async def scenario():
        blocked, continued, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        spoken = {1: 0, 2: 0}

        async def slow(seat, text):
            if calls.count(0) == 1:
                blocked.set()
                await release.wait()
            return 'PASS'

        async def ready(seat, text):
            spoken[seat.position] += 1
            if min(spoken.values()) >= 2:
                continued.set()
            if ready_passes and seat.position == 1:
                return 'PASS'
            return f'Rejected position from seat {seat.position}, attempt {spoken[seat.position]}.'

        handlers.update({0: slow, 1: ready, 2: ready})
        task = asyncio.create_task(runner.Table(number).run())
        try:
            await asyncio.wait_for(blocked.wait(), 2)
            await asyncio.wait_for(continued.wait(), 2)
            assert store.discussion(number)['round'] == 1
            assert store.discussion(number)['quiet_rounds'] == 0
            assert not task.done() and calls.count(0) == 1
            release.set()
            result = await asyncio.wait_for(task, 5)
            assert result['state'] == 'ended', result
            assert store.discussion(number)['round'] == 2
            assert store.discussion(number)['quiet_rounds'] == 2
            assert calls.count(0) == 2
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())


@pytest.mark.parametrize('corrected', [False, True])
def test_late_pass_veto_gets_one_correction_turn_while_finished_peers_are_skipped(panel, monkeypatch, corrected):
    number, handlers, _, _, calls = panel
    names = [row['name'] for row in store.seats(number)]
    store.change(number, snapshot=render.snapshot(names, judging=True))
    monkeypatch.setattr(judge, 'ask', lambda state, criteria, **options: judge.Asked(
        request={'state': state}, criteria=criteria, nouls={name: .1 for name in criteria}))
    prompts = []

    async def scenario():
        offered, release = asyncio.Event(), asyncio.Event()

        async def passed(seat, text):
            return 'PASS'

        async def vetoed(seat, text):
            return 'A rejected position.'

        async def late_veto(seat, text):
            prompts.append(text)
            count = calls.count(2)
            if count == 1:
                return 'PASS'
            if count == 2:
                return 'A late rejected position.'
            assert count == 3, 'The correction is one new opportunity, not a forced series of replies.'
            offered.set()
            await release.wait()
            return 'A rejected correction.' if corrected else 'PASS'

        handlers.update({0: passed, 1: vetoed, 2: late_veto})
        task = asyncio.create_task(runner.Table(number).run())
        try:
            await asyncio.wait_for(offered.wait(), 3)
            found = store.discussion(number)
            assert found['state'] == 'running' and found['quiet_rounds'] == 2 and found['round'] == 3
            assert [calls.count(position) for position in range(3)] == [2, 2, 3]
            blocked = [row for row in store.submissions(number) if row['position'] == 2 and row['kind'] == 'seat'][-1]
            reason = render.status(blocked)
            assert prompts[-1].startswith(reason) and prompts[-1].count(reason) == 1
            release.set()
            result = await asyncio.wait_for(task, 5)
            assert result['state'] == 'ended', result
            assert result['reason'] == 'The round ended because there was nothing new to add.'
            assert [calls.count(position) for position in range(3)] == [2, 2, 3]
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())


def test_a_finished_models_saved_reply_is_judged_once_before_it_can_be_skipped(panel, monkeypatch):
    number, _, _, _, calls = panel
    seated = store.seats(number)
    store.change(number, snapshot=render.snapshot([row['name'] for row in seated], judging=True))
    table = runner.Table(number)
    for cycle in range(2):
        for row in seated:
            outcome = 'V' if row['position'] == 2 and cycle == 1 else 'P'
            store.record(number, table.entry(table.row(), row, 'PASS' if outcome == 'P' else 'Rejected.',
                                             kind='pass' if outcome == 'P' else 'seat'))
        store.close_round(number, 'Exhausted.')
    assert table.row()['quiet_rounds'] == 2
    pending = {'original': 'Saved positive reply awaiting Jev.', 'use': {'completion_tokens': 7},
               'round': table.row()['round'], 'topic': 0, 'pass_after': table.row()['pass_after'],
               'usage_id': 'durable-positive-reply'}
    store.seat_change(number, 0, extra={'panel_reply': pending})
    asked = Mock(side_effect=lambda state, criteria, **options: judge.Asked(
        request={'state': state}, criteria=criteria, nouls={name: .99 for name in criteria}))
    monkeypatch.setattr(judge, 'ask', asked)
    result = asyncio.run(table.run())
    assert result['state'] == 'ended', result
    assert asked.call_count == 1
    assert len([row for row in store.submissions(number) if row['text'] == pending['original']]) == 1
    assert budget.progress(table.row())['participants'][0]['tokens'] == 7
    accepted = next(row for row in store.submissions(number) if row['text'] == pending['original'])
    new_passes = [row for row in store.submissions(number)
                  if row['position'] == 0 and row['number'] > accepted['number'] and row['kind'] == 'pass']
    # The acceptance may land during a partial cycle; every physical call is a new PASS, never a replay of it.
    assert calls.count(0) == len(new_passes) >= 2


def test_unavailable_seats_wait_for_their_actual_retry_deadline_without_repeating_healthy_turns(panel, monkeypatch):
    number, _, _, _, calls = panel
    retry_at = time.time() + .08
    for position in (1, 2):
        store.seat_change(number, position, availability='unavailable', retry_at=retry_at, failing='transient')
    probes = []
    original = runner.Table.probed

    async def probed(table, row):
        if runner.health.due(row):
            probes.append(time.time())
        return await original(table, row)

    monkeypatch.setattr(runner.Table, 'probed', probed)
    result = asyncio.run(runner.Table(number).run())
    assert result['state'] == 'ended', result
    assert calls == [0, 1, 2]
    assert len(probes) == 2 and min(probes) >= retry_at


def test_gone_participant_holds_without_inventing_a_pass(panel):
    number, _, _, _, calls = panel
    store.seat_change(number, 0, gone='Agent exited.', availability='unavailable', retry_at=None)
    result = asyncio.run(runner.Table(number).run())
    assert result['state'] == 'held'
    assert calls == [1, 2]
    assert store.discussion(number)['round'] == 1
    assert not any(row['position'] == 0 for row in store.submissions(number))


@pytest.mark.parametrize('recoverable', [False, True])
def test_last_uncovered_seats_failure_does_not_complete_its_round(panel, monkeypatch, recoverable):
    number, handlers, _, _, calls = panel
    original_value = runner.config.value
    monkeypatch.setattr(runner.config, 'value',
                        lambda key: .04 if key == 'probe_wait' else original_value(key))
    observed = []
    original_failing = runner.Table.failing

    def failing(table, row, error):
        original_failing(table, row, error)
        failure = store.submissions(number)[-1]
        observed.append((table.row()['round'], list(calls), failure))

    async def fails(seat, text):
        if calls.count(2) == 1:
            if recoverable:
                raise NoReply('Endpoint refused its first request.', kind='refused')
            raise Gone('The last participant exited.')
        return 'PASS'

    monkeypatch.setattr(runner.Table, 'failing', failing)
    handlers[2] = fails
    result = asyncio.run(runner.Table(number).run())
    # Observe the recorded failure before any retry, independent of whether its
    # deadline expires during database work or requires recover() to wait.
    assert observed[0][:2] == (1, [0, 1, 2])
    failure = observed[0][2]
    assert failure['position'] == 2 and failure['kind'] == 'none'
    if recoverable:
        assert result['state'] == 'ended', result
        assert any(row['position'] == 2 and row['kind'] == 'pass' and row['number'] > failure['number']
                   for row in store.submissions(number))
    else:
        assert result['state'] == 'held'
        assert store.discussion(number)['round'] == 1
        assert calls == [0, 1, 2]
