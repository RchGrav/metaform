"""Private next-topic selection keeps busy proposals, original artifacts and final scorecards intact."""
import asyncio
import json
import sys
from pathlib import Path

import pytest

from metaform.modules.roundtables.roundtable import export, render, runner, server, stages, store, topics
from metaform.modules.roundtables.roundtable.seat import Reply, Seat

pytestmark = pytest.mark.kind('simulation')


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

    def make(total=1):
        seats = [{'kind': 'acp', 'id': 'acp:claude/haiku', 'agent': 'claude', 'model': 'haiku'},
                 {'kind': 'acp', 'id': 'acp:codex/sol', 'agent': 'codex', 'model': 'sol'}]
        role = {**seats[0], 'name': 'Haiku'}
        number = store.opened({'subject': 'session', 'opening': 'Original session instructions.',
                             'folder': str(folder), 'chair_key': None, 'chair_token': 'fixture',
                             'reporter': seats[0]['id'], 'host': role, 'synthesizer': role, 'rounds': 0, 'spend': 1}, seats,
                            [{'name': 'first', 'title': 'First topic', 'text': 'Explore the first topic.'}],
                            judging=False, reply_limit=80,
                            session={'total': total, 'folder': str(materials),
                                     'score': 'Send your anonymous scorecard.', 'farewell': 'Say farewell.'})
        actual = store.seats(number)[0]
        store.change(number, host={**role, 'name': actual['name']}, synthesizer={**role, 'name': actual['name']})
        return number

    make.comparisons = comparisons
    return make, handlers, calls, materials


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
    assert asyncio.run(runner.Table(number).run())['state'] == 'ended'
    assert {stage for stage, _, _, _ in calls} == {'discussion', 'scoring', 'farewell'}
    assert topics.proposals(number, 0) == [] and make.comparisons == []


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
        return await asyncio.wait_for(table.run(), 8)

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


def test_restart_keeps_a_missing_proposal_receipt_without_publishing_a_subset_winner(session):
    make, _, calls, _ = session
    number = make(total=2)
    table = runner.Table(number)
    table.start_topic_selection(table.row())
    receipt = topics.begin_proposal(table.row(), 0)
    assert receipt
    # This model's request was sent, but its reply was lost before it could be kept.
    assert asyncio.run(runner.Table(number).run())['state'] == 'held'
    assert not [call for call in calls if call[:3] == ('topic_selection', 0, 0)]
    assert len([call for call in calls if call[:3] == ('topic_selection', 0, 1)]) == 1
    assert len(store.topics(number)) == 1
    assert make.comparisons == [], 'Every participant must return its proposal before comparisons.'


def test_private_comparisons_need_spend_even_when_contribution_judging_is_off(session):
    make, _, calls, _ = session
    number = make(total=2)
    table = runner.Table(number)
    assert render.judging(table.row()) is False and not table.requires_payment(table.row())
    table.start_topic_selection(table.row())
    assert table.requires_payment(table.row())
    store.change(number, spent=1)
    assert asyncio.run(table.run())['state'] == 'held'
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
