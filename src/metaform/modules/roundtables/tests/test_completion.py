"""Participant-controlled completion and lossless inline context handoff, without paid conversations."""
import asyncio
from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from metaform.modules.roundtables import follow
from metaform.modules.roundtables.roundtable import export, judge, render, runner, server, store
from metaform.modules.roundtables.roundtable.seat import NoReply, Reply, Seat

pytestmark = pytest.mark.kind('simulation')


@pytest.fixture
def scripted(tmp_path, monkeypatch):
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    monkeypatch.setenv('ROUNDTABLE_CONTEXT_TOKENS', '24000')
    monkeypatch.setenv('ROUNDTABLE_JUDGING_CONTEXT_TOKENS', '24000')
    calls = []
    replies = defaultdict(list)
    notes = {0: '  Alpha position.\nEvidence: src/a.py:4\nStill disagree.  ',
             1: 'Beta: preserve `x = 1`.\nOpen question: why?\n'}

    class Fake(Seat):
        kind = 'acp'

        async def open(self):
            self.session = self.session or f'fresh-{len(calls)}-{self.position}'

        async def exchange(self, text, seconds):
            await self.open()
            calls.append((self.position, self.session, text))
            if '# Carry-forward note' in text:
                return Reply(notes[self.position])
            if '# Shared continuation' in text:
                return Reply('Decision: keep evidence src/a.py:4. Alpha disagrees. Why remains open.')
            if '# Topic synthesis' in text:
                return Reply('I1. First idea: preserved evidence.\nI2. Second idea: unresolved disagreement.')
            if '# Rank collected ideas' in text:
                return Reply('I1, I2')
            if '# Explain your' in text:
                return Reply('Evidence and disagreement explain this ranking.')
            if '# Host summary' in text:
                return Reply('Saved host summary. Decision and disagreement remain open.')
            reply = replies[self.position].pop(0) if replies[self.position] else 'PASS'
            if isinstance(reply, Exception):
                raise reply
            return Reply(reply)

        async def report(self, record, seconds):
            return 'Fixture report.'

    monkeypatch.setitem(runner.KINDS, 'acp', Fake)

    def make(judging=False, staged=True, spend=1, reply_limit=80):
        seats = [{'kind': 'acp', 'id': f'acp:claude/{name}', 'agent': 'claude', 'model': name}
                 for name in ('haiku', 'opus')]
        role = {**seats[0], 'name': 'Haiku'}
        return store.opened({'subject': 'Fixture', 'opening': 'Original person instructions: retain evidence.',
                             'folder': str(tmp_path), 'chair_key': None, 'chair_token': 'fixture',
                             'reporter': seats[0]['id'], 'host': role, 'synthesizer': role,
                             'rounds': 8, 'spend': spend}, seats,
                            [{'name': 'topic', 'title': 'Topic', 'text': 'Explore disagreements.'}] if staged else [],
                            reply_limit=reply_limit, judging=judging)

    return make, replies, notes, calls


@pytest.mark.parametrize('staged', [True, False])
def test_only_unanimous_voluntary_passes_finish_one_full_round(scripted, staged):
    make, replies, _, _ = scripted
    number = make(staged=staged)
    replies[0] = ['PASS', NoReply('temporary failure'), 'PASS', 'PASS']
    replies[1] = ['Substantive disagreement.', 'PASS', 'Another objection.', 'PASS']
    result = asyncio.run(runner.Table(number).run())
    assert result['state'] == 'ended', result
    rows = store.submissions(number)
    # A failed attempt does not cover the seat: its real reply is required in that same round.
    assert len(rows) == 9
    assert [one['kind'] for one in rows if one['round'] == 2 and one['position'] == 0] == ['none', 'pass']
    assert [one['kind'] for one in rows[-2:]] == ['pass', 'pass']
    assert store.discussion(number)['round'] == 4
    assert store.judgments(number) == []
    if staged:
        assert store.topics(number)[0]['advanced_by'] == 'passes'


@pytest.mark.parametrize('staged', [True, False])
def test_veto_only_rounds_finish_after_two_complete_opportunities_per_participant(scripted, monkeypatch, staged):
    make, replies, _, _ = scripted
    number = make(judging=True, staged=staged)
    asked = Mock(side_effect=lambda state, criteria, **kw: judge.Asked(
        request={'state': state}, criteria=criteria, nouls={name: .1 for name in criteria}))
    monkeypatch.setattr(judge, 'ask', asked)
    replies[0] = [f'Alpha rejected point {n}.' for n in range(11)]
    replies[1] = [f'Beta rejected objection {n}.' for n in range(11)]
    result = asyncio.run(runner.Table(number).run())
    assert result['state'] == 'ended', result
    assert store.discussion(number)['round'] == 2
    assert store.discussion(number)['quiet_rounds'] == 2
    assert asked.call_count == 4
    assert all(not row['accepted'] for row in store.submissions(number))
    assert [one['kind'] for one in store.submissions(number)] == ['seat'] * 4
    assert not any(one['kind'] == 'sufficiency' for one in store.judgments(number))
    assert all('latest_round' not in call.args[0] for call in asked.call_args_list)
    if staged:
        assert store.topics(number)[0]['advanced_by'] == 'exhausted'


@pytest.mark.parametrize('staged', [True, False])
def test_judged_passes_also_require_two_complete_quiet_rounds(scripted, staged):
    make, _, _, _ = scripted
    number = make(judging=True, staged=staged)
    result = asyncio.run(runner.Table(number).run())
    assert result['state'] == 'ended', result
    assert [one['kind'] for one in store.submissions(number)] == ['pass'] * 4
    assert store.discussion(number)['round'] == 2
    assert store.discussion(number)['quiet_rounds'] == 2


@pytest.mark.parametrize('pairs', [('PP', 'VV'), ('VV', 'VP'), ('VP', 'PP')])
def test_each_model_can_finish_with_a_different_terminal_pair(scripted, pairs):
    make, _, _, _ = scripted
    number = make(judging=True)
    table = runner.Table(number)
    for cycle in range(2):
        for row, pair in zip(store.seats(number), pairs, strict=True):
            outcome = pair[cycle]
            store.record(number, table.entry(table.row(), row, 'PASS' if outcome == 'P' else 'Rejected position.',
                                             kind='pass' if outcome == 'P' else 'seat'))
        asyncio.run(table.round_over(table.row()))
    assert table.row()['stage'] == 'synthesis'
    assert table.row()['quiet_rounds'] == 2
    assert store.topics(number)[0]['why'] == 'The round ended because there was nothing new to add.'


@pytest.mark.parametrize('correction', ['P', 'V'])
def test_pass_then_veto_requires_a_targeted_correction_after_the_second_quiet_cycle(scripted, correction):
    make, _, _, _ = scripted
    number = make(judging=True)
    table = runner.Table(number)
    for cycle in range(2):
        for row in store.seats(number):
            outcome = 'V' if row['position'] == 1 and cycle == 1 else 'P'
            store.record(number, table.entry(table.row(), row, 'PASS' if outcome == 'P' else 'Rejected position.',
                                             kind='pass' if outcome == 'P' else 'seat'))
        asyncio.run(table.round_over(table.row()))
    assert table.row()['stage'] == 'discussion' and table.row()['round'] == 3
    assert table.row()['quiet_rounds'] == 2
    row = store.seats(number)[1]
    store.record(number, table.entry(table.row(), row, 'PASS' if correction == 'P' else 'Rejected correction.',
                                     kind='pass' if correction == 'P' else 'seat'))
    asyncio.run(table.round_over(table.row()))
    assert table.row()['stage'] == 'synthesis'
    assert [one['position'] for one in store.submissions(number) if one['round'] == 3] == [1]


def test_late_accepted_correction_resets_every_models_terminal_pair(scripted):
    make, _, _, _ = scripted
    number = make(judging=True)
    table = runner.Table(number)
    seated = store.seats(number)
    for cycle in range(2):
        for row in seated:
            outcome = 'V' if row['position'] == 1 and cycle == 1 else 'P'
            store.record(number, table.entry(table.row(), row, 'PASS' if outcome == 'P' else 'Rejected.',
                                             kind='pass' if outcome == 'P' else 'seat'))
        asyncio.run(table.round_over(table.row()))
    store.record(number, table.entry(table.row(), seated[1], 'Accepted correction.', accepted=True))
    assert table.row()['quiet_rounds'] == 0
    store.close_round(number, 'Exhausted.')
    assert table.row()['stage'] == 'discussion' and table.row()['round'] == 3
    store.record(number, table.entry(table.row(), seated[0], 'PASS', kind='pass'))
    store.close_round(number, 'Exhausted.')
    for cycle in range(2):
        store.record(number, table.entry(table.row(), seated[0], 'PASS', kind='pass'))
        store.record(number, table.entry(table.row(), seated[1], 'Rejected.' if cycle == 0 else 'PASS',
                                         kind='seat' if cycle == 0 else 'pass'))
        store.close_round(number, 'Exhausted.')
        if cycle == 0:
            assert table.row()['stage'] == 'discussion' and table.row()['quiet_rounds'] == 1
    assert table.row()['stage'] == 'synthesis'


@pytest.mark.parametrize('departed', [False, True])
def test_normal_session_exhaustion_goes_to_private_topic_selection_instead_of_collaboration(scripted, tmp_path,
                                                                                         departed):
    make, _, _, calls = scripted
    number = make(judging=True)
    table = runner.Table(number)
    found = table.row()
    store.change(number, snapshot={**found['snapshot'], 'session': {'total': 2, 'folder': str(tmp_path)}})
    seated = store.seats(number)
    if departed:
        store.seat_change(number, seated[-1]['position'], gone='Participant exited permanently.',
                          availability='unavailable', retry_at=None)
        seated = seated[:-1]
    for _ in range(2):
        for row in seated:
            store.record(number, table.entry(table.row(), row, 'PASS', kind='pass'))
        asyncio.run(table.round_over(table.row()))
    assert table.row()['stage'] == 'topic_selection'
    assert store.topics(number)[0]['why'] == 'The round ended because there was nothing new to add.'
    assert calls == []


@pytest.mark.parametrize('staged', [False, True])
@pytest.mark.parametrize('actual', ['PASS', 'A rejected contribution.'])
def test_departed_seat_is_excluded_from_quiet_quorum_without_manufacturing_its_outcomes(scripted, staged, actual):
    make, _, _, _ = scripted
    number = make(judging=True, staged=staged)
    table = runner.Table(number)
    present, departed = store.seats(number)
    store.seat_change(number, departed['position'], gone='The agent exited.', availability='unavailable', retry_at=None)
    store.record(number, table.entry(table.row(), departed, '', kind='none', reason='The agent exited.'))
    for cycle in range(2):
        store.record(number, table.entry(table.row(), present, actual,
                                         kind='pass' if actual == 'PASS' else 'seat', accepted=False))
        store.close_round(number, 'Exhausted.')
        assert table.row()['quiet_rounds'] == cycle + 1
        if cycle == 0:
            assert table.row()['state'] == 'running' and table.row()['round'] == 2
            assert table.row()['stage'] == ('discussion' if staged else None)
    assert table.row()['stage'] == 'synthesis' if staged else table.row()['state'] == 'ending'
    rows = store.submissions(number)
    assert len([row for row in rows if row['position'] == present['position']]) == 2
    assert [row['kind'] for row in rows if row['position'] == departed['position']] == ['none']


def test_an_accepted_reply_resets_the_streak_and_repeated_positions_are_judged(scripted, monkeypatch):
    make, replies, _, calls = scripted
    number = make(judging=True)
    replies[0] = ['The same previously stated position.'] * 4
    replies[1] = ['The same previously stated position.'] * 4
    judgments = []

    def asked(state, criteria, **options):
        judgments.append(state)
        score = .99 if len(judgments) == 3 else .1
        return judge.Asked(request={'state': state}, criteria=criteria, nouls={name: score for name in criteria})

    monkeypatch.setattr(judge, 'ask', asked)
    result = asyncio.run(runner.Table(number).run())
    assert result['state'] == 'ended', result
    rows = store.submissions(number)
    assert store.discussion(number)['round'] == 4
    assert store.discussion(number)['quiet_rounds'] == 2
    assert len(judgments) == 8 and sum(row['accepted'] for row in rows) == 1
    assert all(set(state) == {'xml'} and state['xml'].count('Original person instructions: retain evidence.') == 1
               for state in judgments)
    assert all(row['repeat_of'] is None for row in rows)
    assert all(len({session for pos, session, text in calls if pos == position and '# Topic' not in text}) == 1
               for position in (0, 1))


def test_failed_available_seat_does_not_cover_round_but_unavailable_seat_is_skipped(scripted):
    make, _, _, _ = scripted
    number = make(judging=True)
    table = runner.Table(number)
    seated = store.seats(number)
    store.record(number, table.entry(table.row(), seated[0], 'A rejected contribution.', accepted=False))
    store.record(number, table.entry(table.row(), seated[1], '', kind='none', reason='Endpoint failed.'))
    store.close_round(number, 'Exhausted.')
    assert table.row()['round'] == 1 and table.row()['quiet_rounds'] == 0
    store.seat_change(number, 1, availability='unavailable')
    store.close_round(number, 'Exhausted.')
    assert table.row()['round'] == 2 and table.row()['quiet_rounds'] == 1
    assert table.row()['stage'] == 'discussion'
    store.record(number, table.entry(table.row(), seated[1], 'Its actual rejected reply.', accepted=False))
    store.close_round(number, 'Exhausted.')
    assert table.row()['round'] == 2 and table.row()['quiet_rounds'] == 1
    restarted = runner.Table(number)
    store.record(number, restarted.entry(restarted.row(), seated[0], 'Another rejected contribution.', accepted=False))
    store.close_round(number, 'Exhausted.')
    assert restarted.row()['stage'] == 'synthesis' and restarted.row()['quiet_rounds'] == 2


def test_acceptance_resets_immediately_and_pending_judgment_cannot_complete_a_round(scripted):
    make, _, _, _ = scripted
    number = make(judging=True)
    table = runner.Table(number)
    seated = store.seats(number)
    for row in seated:
        store.record(number, table.entry(table.row(), row, 'Rejected.', accepted=False))
    store.close_round(number, 'Exhausted.')
    assert table.row()['quiet_rounds'] == 1
    store.record(number, table.entry(table.row(), seated[0], 'Accepted new material.', accepted=True))
    assert table.row()['quiet_rounds'] == 0
    store.record(number, table.entry(table.row(), seated[1], 'Rejected.', accepted=False))
    store.change(number, unjudged={'position': 0, 'text': 'A later reply still awaiting its judgment.', 'use': {}})
    store.close_round(number, 'Exhausted.')
    assert table.row()['round'] == 2 and table.row()['quiet_rounds'] == 0
    store.change(number, unjudged=None)
    store.close_round(number, 'Exhausted.')
    assert table.row()['round'] == 3 and table.row()['quiet_rounds'] == 0


@pytest.mark.parametrize('staged', [True, False])
def test_block_reason_arrives_once_only_in_authors_next_turn(scripted, monkeypatch, staged):
    make, replies, _, calls = scripted
    number = make(judging=True, staged=staged)
    table = runner.Table(number)
    replies[0] = ['PRIVATE_REJECTED_POSITION', 'PASS']
    monkeypatch.setattr(judge, 'ask', lambda state, criteria, **options: judge.Asked(
        request={'state': state}, criteria=criteria, nouls={name: .1 for name in criteria}))
    asyncio.run(table.turn(table.row(), store.seats(number)[0]))
    rejection = store.submissions(number)[0]
    reason = render.status(rejection)
    assert reason and 'PRIVATE_REJECTED_POSITION' not in reason
    saved = store.seats(number)[0]['messages']
    assert all(reason not in message['content'] for message in saved)
    assert all('PRIVATE_REJECTED_POSITION' not in message['content'] for message in saved)
    asyncio.run(table.turn(table.row(), store.seats(number)[1]))
    assert reason not in calls[-1][2]
    asyncio.run(table.turn(table.row(), store.seats(number)[0]))
    prompt = calls[-1][2]
    assert prompt.count(reason) == 1
    assert 'PRIVATE_REJECTED_POSITION' not in prompt and 'roundtable://' not in prompt


@pytest.mark.parametrize('staged', [True, False])
def test_rejected_material_stays_private_and_is_not_written_into_shared_files(scripted, monkeypatch, tmp_path, staged):
    make, replies, notes, calls = scripted
    number = make(judging=True, staged=staged)
    table = runner.Table(number)
    replies[0] = ['PRIVATE_REJECTED_POSITION']
    monkeypatch.setattr(judge, 'ask', lambda state, criteria, **options: judge.Asked(
        request={'state': state}, criteria=criteria, nouls={name: .1 for name in criteria}))
    asyncio.run(table.turn(table.row(), store.seats(number)[0]))
    rejected = store.submissions(number)[0]
    asyncio.run(table.turn(table.row(), store.seats(number)[1]))
    peer = [text for position, session, text in calls if position == 1][-1]
    assert 'PRIVATE_REJECTED_POSITION' not in peer
    assert render.turn(rejected['number']) not in peer
    assert 'PRIVATE_REJECTED_POSITION' not in table.editor_view(table.row(), [])
    assert table.segment(table.row()) == []
    assert export.build(number)['submissions'][0]['text'] == 'PRIVATE_REJECTED_POSITION'
    assert not list(tmp_path.rglob('vetoed'))
    asyncio.run(table.handoff(table.row()))
    shared = render.shared(table.row())
    assert 'PRIVATE_REJECTED_POSITION' not in shared
    assert all(note in shared for note in notes.values())
    assert not list(tmp_path.rglob('vetoed'))
    reported = []

    async def report(found, record):
        reported.append(record)
        return 'Report from public context.'

    monkeypatch.setattr(table, 'report', report)
    asyncio.run(table.finish())
    assert reported and all('PRIVATE_REJECTED_POSITION' not in record for record in reported)
    assert export.build(number)['submissions'][0]['text'] == 'PRIVATE_REJECTED_POSITION'


@pytest.mark.parametrize('new_score', [.9, .3])
def test_veto_explanation_contains_only_failed_checks_and_their_recorded_cutoffs(scripted, new_score):
    make, _, _, _ = scripted
    number = make(judging=True)
    found = store.discussion(number)
    store.change(number, snapshot={**found['snapshot'], 'floors': {'new_context': .7, 'on_topic': .6}})
    saved = store.record(number, {'topic': 0, 'round': 1, 'position': 0, 'kind': 'seat',
                                  'seat': 'acp:claude/haiku', 'name': 'Haiku', 'text': 'Original contribution.',
                                  'accepted': False, 'new_context': new_score, 'on_topic': .42})
    reason = export.scored(store.submission(number, saved['number']))['veto_reason']
    assert 'Topic relevance scored 0.42, below the required 0.6.' in reason
    assert ('New information scored 0.3, below the required 0.7.' in reason) is (new_score < .7)
    assert '0.9' not in reason and 'http' not in reason


def test_budget_holds_without_turns_and_explicit_end_discussion_bypasses_hold(scripted, monkeypatch):
    make, _, _, calls = scripted
    number = make(judging=True, spend=0)
    async def stopped_after_hold():
        table = runner.Table(number)
        held = asyncio.Event()
        change = table.change

        def observe(**changes):
            found = change(**changes)
            if found['state'] == 'held':
                held.set()
            return found

        monkeypatch.setattr(table, 'change', observe)
        task = asyncio.create_task(table.run())
        try:
            await asyncio.wait_for(held.wait(), 2)
            return table.summary()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    result = asyncio.run(stopped_after_hold())
    assert result['state'] == 'held' and 'spending limit' in result['reason']
    assert store.submissions(number) == [] and not calls
    monkeypatch.setattr(runner, 'spawn', lambda number: None)
    advanced = server.advanced(store.discussion(number))
    assert advanced['state'] == 'running'
    result = asyncio.run(runner.Table(number).run())
    assert result['state'] == 'ended'
    assert store.topics(number)[0]['advanced_by'] == 'chair'


def test_comment_clears_prior_votes_and_stays_held(scripted, monkeypatch):
    make, _, _, _ = scripted
    number = make()
    held = runner.Table(number)
    found = held.row()
    for row in store.seats(number):
        store.record(number, held.entry(found, row, 'PASS', kind='pass'))
    store.change(number, state='held', position=2)
    monkeypatch.setattr(runner, 'spawn', lambda number: None)
    server.commented(held.row(), 'New person instruction.')
    held.enter_comments()
    assert held.row()['state'] == 'held'
    store.change(number, state='running')
    asyncio.run(held.round_over(held.row()))
    assert held.row()['stage'] == 'discussion'
    assert held.row()['round'] == 1


@pytest.mark.parametrize('judging', [False, True])
def test_handoff_keeps_notes_verbatim_refreshes_sessions_and_resets_votes(scripted, monkeypatch, judging):
    make, _, notes, calls = scripted
    number = make(judging=judging)
    held = runner.Table(number)
    found = held.row()
    for row in store.seats(number):
        store.record(number, held.entry(found, row, 'RAW HISTORY ' * 80, accepted=True))
        store.record(number, held.entry(found, row, 'PASS', kind='pass'))
        store.seat_change(number, row['position'], session=f'old-{row["position"]}',
                          messages=[{'role': 'user', 'content': 'OLD SESSION HISTORY'}])
    monkeypatch.setattr(judge, 'ask', Mock(side_effect=AssertionError('notes must bypass judging')))
    asyncio.run(held.handoff(held.row()))
    found = held.row()
    assert found['stage'] == 'discussion' and found['state'] == 'running'
    saved = [one for one in store.submissions(number) if one['kind'] == 'carry']
    assert [one['text'] for one in saved] == list(notes.values())
    assert all(not one['truncated'] for one in saved)
    assert all(f'Maximum {2 * render.reply_limit(found)} characters' in text
               for _, _, text in calls if '# Carry-forward note' in text)
    editor = next(text for _, _, text in calls if '# Shared continuation' in text)
    assert 'original instructions' in editor and 'RAW HISTORY' in editor
    assert all(note in editor for note in notes.values())
    assert all(row['session'] is None and row['messages'] == [] for row in store.seats(number))
    assert store.submissions(number)[-1]['kind'] == 'handoff'
    asyncio.run(held.round_over(found))
    assert held.row()['stage'] == 'discussion'
    for row in store.seats(number):
        asyncio.run(held.turn(held.row(), row))
    for position in (0, 1):
        session, text = [(session, text) for pos, session, text in calls if pos == position][-1]
        assert session != f'old-{position}'
        assert all(note in text for note in notes.values())
        assert 'Original person instructions' in text and 'RAW HISTORY' not in text
    assert store.judgments(number) == []
    exported = export.build(number)
    assert any(row['text'].startswith('RAW HISTORY') for row in exported['submissions'])


def test_handoff_uses_smallest_active_budget_without_jev(scripted, monkeypatch):
    make, _, _, _ = scripted
    number = make(judging=False)
    held = runner.Table(number)
    monkeypatch.setenv('ROUNDTABLE_CONTEXT_TOKENS', '50000')
    monkeypatch.setattr(runner.config, 'context_budgets', lambda: {'acp:claude/opus': 6000})
    assert held.context_limit(held.row()) == 6000
    monkeypatch.setattr(runner.config, 'context_budgets', dict)
    assert held.context_limit(held.row()) == 50000
    snapshot = held.row()['snapshot'] | {'judging': True}
    store.change(number, snapshot=snapshot)
    assert held.context_limit(held.row()) == 50000


@pytest.mark.parametrize('continuation_time', [None, '2000-01-01T00:00:00+00:00'])
def test_summary_continuation_preserves_identity_history_and_previous_outputs(scripted, monkeypatch,
                                                                            continuation_time):
    make, replies, _, calls = scripted
    number = make()
    asyncio.run(runner.Table(number).run())
    previous = store.submissions(number)
    outputs = store.staged(number)
    found = store.discussion(number)
    if continuation_time is not None:  # A clock correction cannot reorder the completed record.
        monkeypatch.setattr(store, 'stamp', lambda: continuation_time)
    store.change(number, unjudged={'position': 0, 'text': 'Pending paid reply retained after explicit end.', 'use': {}})
    folder, seats = found['folder'], [(row['id'], row['name']) for row in store.seats(number)]
    monkeypatch.setattr(runner, 'spawn', lambda number: None)
    result = server.continued(found)
    assert result['discussion'] == number and result['state'] == 'running'
    assert store.submissions(number)[:len(previous)] == previous
    assert any(one['text'] == 'Pending paid reply retained after explicit end.' for one in store.submissions(number))
    assert store.staged(number) == outputs
    assert store.discussion(number)['folder'] == folder
    assert [(row['id'], row['name']) for row in store.seats(number)] == seats
    assert all(row['session'] is None for row in store.seats(number))
    replies[0] = ['New point after completion.', 'PASS']
    asyncio.run(runner.Table(number).run())
    assert len(store.topics(number)) == 2
    assert store.staged(number)[:len(outputs)] == outputs
    first = next(text for _, _, text in calls if 'Shared continuation:' in text)
    assert 'Saved host summary' in first and 'Original person instructions' in first


def test_unjudged_acp_open_needs_no_credential_and_keeps_repeated_replies(scripted, monkeypatch):
    make, replies, _, _ = scripted
    monkeypatch.setattr(runner, 'spawn', lambda number: None)
    opened = asyncio.run(server.opened('Question', ['acp:claude/haiku'], None, 0, None, None, None,
                                       topics=['Topic'], host='acp:claude/haiku', judging=False))
    assert opened['judging'] is False
    number = make()
    replies[0] = ['Repeat this point.', 'Repeat this point.', 'PASS']
    replies[1] = ['Repeat this point.', 'Repeat this point.', 'PASS']
    asyncio.run(runner.Table(number).run())
    assert all(row['accepted'] for row in store.submissions(number) if row['kind'] == 'seat')
    assert not store.judgments(number)


def test_context_trigger_performs_inline_handoff_before_next_round(scripted, monkeypatch):
    make, _, notes, calls = scripted
    number = make()
    monkeypatch.setenv('ROUNDTABLE_CONTEXT_TOKENS', '5000')
    held = runner.Table(number)
    store.record(number, held.entry(held.row(), store.seats(number)[0], 'Context to compact. ' * 300, accepted=True))
    assert held.context_due(held.row())
    result = asyncio.run(held.run())
    assert result['state'] == 'ended', result
    assert len([one for one in store.submissions(number) if one['kind'] == 'handoff']) == 1
    assert [one['text'] for one in store.submissions(number) if one['kind'] == 'carry'] == list(notes.values())
    assert sum('# Shared continuation' in text for _, _, text in calls) == 1


def test_failed_judgment_holds_pending_reply_without_pass(scripted, monkeypatch):
    make, replies, _, _ = scripted
    number = make(judging=True)
    replies[0] = ['Substantive point.']
    monkeypatch.setattr(judge, 'ask', lambda *args, **kw: judge.Asked(request={}, error='fixture provider failed'))
    table = runner.Table(number)
    assert not asyncio.run(table.turn(table.row(), store.seats(number)[0]))
    assert table.row()['state'] == 'held'
    assert store.discussion(number)['unjudged']['text'] == 'Substantive point.'
    assert store.submissions(number) == []
    assert store.topics(number)[0]['discussed'] is None


def test_follower_error_holds_and_waits_for_seats_to_close(tmp_path, monkeypatch):
    follower = object.__new__(follow.Follower)
    follower.ctx = SimpleNamespace(folder=tmp_path)
    follower.table_id = 'fixture'
    follower.followed = {}
    emitted, observed, closed = [], [], []
    monkeypatch.setattr(follow.Follower, 'row', lambda self: {'chair': 'fixture-chair'})
    monkeypatch.setattr(follow.Follower, 'emit', lambda self, *args, **kw: emitted.append((args, kw)))
    monkeypatch.setattr(follow.Follower, 'follow', Mock(side_effect=RuntimeError('fixture stream failed')))
    called = Mock()
    monkeypatch.setattr(follow.engine, 'call', called)
    monkeypatch.setattr(follow.engine, 'folder_log', lambda: tmp_path)

    class Page:
        def __init__(self, *args):
            pass

        def changes(self, number):
            for state in ('running', 'stopped'):
                observed.append(state)
                yield {'state': 'held', 'runner': state}

        def close(self):
            closed.append(True)

    monkeypatch.setattr(follow.engine, 'Page', Page)
    follower.followed_to_end(7)
    assert [call.args[1] for call in called.call_args_list] == ['hold']
    assert observed == ['running', 'stopped'] and len(closed) == 2
    assert not any(args[0] == 'end' for args, _ in emitted)
    assert emitted[0][1]['changes']['state'] == 'held'
    assert any(args[0] == 'state' and values.get('state') == 'held' for args, values in emitted)
