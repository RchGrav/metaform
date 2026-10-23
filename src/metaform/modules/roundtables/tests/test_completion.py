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
    assert len(rows) == 8
    assert [one['kind'] for one in rows[-2:]] == ['pass', 'pass']
    assert store.discussion(number)['round'] == 4
    assert store.judgments(number) == []
    if staged:
        assert store.topics(number)[0]['advanced_by'] == 'passes'


def test_veto_only_rounds_continue_past_former_cap(scripted, monkeypatch):
    make, replies, _, _ = scripted
    number = make(judging=True)
    asked = Mock(side_effect=lambda state, criteria, **kw: judge.Asked(
        request={'state': state}, criteria=criteria, nouls={name: .1 for name in criteria}))
    monkeypatch.setattr(judge, 'ask', asked)
    replies[0] = [f'Alpha rejected point {n}.' for n in range(11)]
    replies[1] = [f'Beta rejected objection {n}.' for n in range(11)]
    result = asyncio.run(runner.Table(number).run())
    assert result['state'] == 'ended', result
    assert store.discussion(number)['round'] == 12
    assert all(not row['accepted'] for row in store.submissions(number))
    assert [one['kind'] for one in store.submissions(number)[-2:]] == ['pass', 'pass']
    assert not any(one['kind'] == 'sufficiency' for one in store.judgments(number))
    assert all('latest_round' not in call.args[0] for call in asked.call_args_list)


def test_budget_holds_without_turns_and_explicit_end_discussion_bypasses_hold(scripted, monkeypatch):
    make, _, _, calls = scripted
    number = make(judging=True, spend=0)
    result = asyncio.run(runner.Table(number).run())
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
    asyncio.run(held.run())
    assert held.row()['state'] == 'held'
    store.change(number, state='running')
    asyncio.run(held.round_over(held.row()))
    assert held.row()['stage'] == 'discussion'
    assert held.row()['round'] == 2


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
    assert 'Original person instructions' in editor and 'RAW HISTORY' in editor
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
    assert held.context_limit(held.row()) == 24000


def test_summary_continuation_preserves_identity_history_and_previous_outputs(scripted, monkeypatch):
    make, replies, _, calls = scripted
    number = make()
    asyncio.run(runner.Table(number).run())
    previous = store.submissions(number)
    outputs = store.staged(number)
    found = store.discussion(number)
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
    result = asyncio.run(runner.Table(number).run())
    assert result['state'] == 'held'
    assert store.discussion(number)['unjudged']['text'] == 'Substantive point.'
    assert store.submissions(number) == []
    assert store.topics(number)[0]['discussed'] is None


def test_follower_error_holds_and_waits_for_seats_to_close(tmp_path, monkeypatch):
    follower = object.__new__(follow.Follower)
    follower.ctx = SimpleNamespace(folder=tmp_path)
    follower.table_id = 'fixture'
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
