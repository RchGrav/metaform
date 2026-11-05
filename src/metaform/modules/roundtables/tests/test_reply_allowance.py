"""Reply promises bank PASS and genuinely missed accepted messages, without revealing private vetoes."""
import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock, Mock
from xml.etree.ElementTree import fromstring

import pytest

from metaform.modules.roundtables.roundtable import allowance, budget, config, judge, openrouter, render, runner, store
from metaform.modules.roundtables.roundtable.seat import Reply, Seat

pytestmark = pytest.mark.kind('simulation')


@pytest.fixture
def panel(run, tmp_path, monkeypatch):
    run('enable', 'dispatch', cwd=tmp_path)
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    handlers, prompts, active = {}, [], set()

    class Fake(Seat):
        kind = 'acp'

        async def exchange(self, text, seconds):
            assert self.position not in active, 'Only one reply or PASS may be outstanding per participant.'
            active.add(self.position)
            prompts.append((self.position, text))
            self.delivered()
            try:
                return Reply(await handlers[self.position](self, text)) if self.position in handlers else Reply('PASS')
            finally:
                active.remove(self.position)

    monkeypatch.setitem(runner.KINDS, 'acp', Fake)

    def make(*, judging=False, staged=True, base=512):
        seats = [{'kind': 'acp', 'id': f'acp:claude/{model}', 'agent': 'claude', 'model': model}
                 for model in ('haiku', 'sonnet', 'opus')]
        return store.opened({'subject': 'Reply credit', 'opening': 'Discuss the evidence.', 'folder': str(tmp_path),
                             'chair_token': 'fixture', 'reporter': seats[0]['id'], 'rounds': 0, 'spend': 1}, seats,
                            [{'name': 'first', 'title': 'First question', 'text': 'Discuss the first question.'},
                             {'name': 'second', 'title': 'Second question', 'text': 'Discuss the next question.'}]
                            if staged else [], reply_limit=base, judging=judging)

    return make, handlers, prompts


def recorded(number, position, *, kind='seat', accepted=False, text='A contribution.', receipt=None):
    found = store.discussion(number)
    seat = store.seats(number)[position] if position is not None else {'id': 'chair', 'name': None}
    if receipt:
        budget.record_reply(found, seat, {}, receipt)
    return store.record(number, {'round': found['round'], 'topic': found['topic'] if found['stage'] else None,
                                  'position': position, 'seat': seat['id'], 'name': seat['name'],
                                  'kind': kind, 'accepted': accepted, 'text': text}, receipt=receipt)


def state(number, position):
    return store.seats(number)[position]['extra']['reply_allowance']


def bank_passes(number, position, count):
    for _ in range(count):
        offer = allowance.begin(number, position)
        recorded(number, position, kind='pass', text='PASS', receipt=offer.receipt)


def test_three_passes_offer_2048_and_acceptance_consumes_the_offered_bank(panel):
    make, _, _ = panel
    number = make()
    bank_passes(number, 0, 3)
    offer = allowance.begin(number, 0)
    assert offer.limit == 2048 and offer.offered == 3
    allowance.delivered(number, 0, offer.receipt)
    allowance.delivered(number, 0, offer.receipt)
    assert state(number, 0)['credit'] == 3 and state(number, 0)['pending']['delivered'] is True
    recorded(number, 0, accepted=True, receipt=offer.receipt)
    assert allowance.begin(number, 0).limit == 512


def test_veto_and_other_private_attempts_do_not_change_a_busy_peers_allowance(panel):
    make, _, _ = panel
    limits = []
    for private_attempts in (0, 25):
        number = make()
        offer = allowance.begin(number, 0)
        for _ in range(private_attempts):
            recorded(number, 1, text='PRIVATE_VETOED_TEXT')
        for kind in ('pass', 'none', 'carry', 'handoff'):
            recorded(number, 1, kind=kind)
        recorded(number, None, kind='chair', text='Chair instruction.')
        assert state(number, 0)['credit'] == 0
        recorded(number, 1, accepted=True)
        assert state(number, 0)['credit'] == 1
        recorded(number, 0, receipt=offer.receipt)
        limits.append(allowance.begin(number, 0).limit)
    assert limits == [1024, 1024], 'Only the same accepted message is observable in the next allowance.'


def test_pass_adds_one_and_veto_adds_zero_without_consuming_existing_credit(panel):
    make, _, _ = panel
    number = make()
    bank_passes(number, 0, 1)
    for _ in range(2):
        offer = allowance.begin(number, 0)
        assert offer.limit == 1024
        recorded(number, 0, receipt=offer.receipt)
        assert state(number, 0)['credit'] == 1
    offer = allowance.begin(number, 0)
    recorded(number, 1, accepted=True)
    recorded(number, 0, kind='pass', text='PASS', receipt=offer.receipt)
    assert allowance.begin(number, 0).limit == 2048


@pytest.mark.parametrize('staged', [False, True])
def test_real_busy_reply_keeps_its_promise_and_banks_three_accepted_peer_messages_for_next_turn(panel, staged):
    make, handlers, prompts = panel
    number = make(staged=staged)
    table = runner.Table(number)

    async def scenario():
        busy, release = asyncio.Event(), asyncio.Event()

        async def slow(seat, text):
            busy.set()
            await release.wait()
            return 'x' * 700

        async def peer(seat, text):
            return f'Fresh accepted evidence from participant {seat.position}.'

        handlers.update({0: slow, 1: peer, 2: peer})
        task = asyncio.create_task(table.turn(table.row(), store.seats(number)[0]))
        try:
            await asyncio.wait_for(busy.wait(), 1)
            for position in (1, 2, 1):
                assert await table.turn(table.row(), store.seats(number)[position])
            assert not task.done() and state(number, 0)['credit'] == 3
            assert state(number, 0)['pending']['limit'] == 512
            release.set()
            assert await asyncio.wait_for(task, 1)
            first = [row for row in store.submissions(number) if row['position'] == 0][-1]
            assert first['text'] == 'x' * 512 and first['truncated']
            assert state(number, 0)['credit'] == 3

            async def expanded(seat, text):
                return 'y' * 2500

            handlers[0] = expanded
            assert await table.turn(table.row(), store.seats(number)[0])
            second = store.submissions(number)[-1]
            assert second['text'] == 'y' * 2048 and second['truncated']
            assert state(number, 0)['credit'] == 0
            own_prompts = [text for position, text in prompts if position == 0]
            assert '512 characters' in own_prompts[0] and '2048 characters' in own_prompts[1]
        finally:
            release.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())


def test_waiting_for_jev_is_not_busy_native_work(panel):
    make, _, _ = panel
    number = make()
    offer = allowance.begin(number, 0)
    allowance.delivered(number, 0, offer.receipt)
    allowance.answered(number, 0, offer.receipt)
    for _ in range(3):
        recorded(number, 1, accepted=True)
    assert state(number, 0)['credit'] == 0
    recorded(number, 0, accepted=True, receipt=offer.receipt)
    assert allowance.begin(number, 0).limit == 512


def test_peer_acceptance_between_begin_and_history_read_is_missed_then_shown_once_with_earned_space(
        panel, monkeypatch):
    make, handlers, prompts = panel
    number = make()
    begin = allowance.begin
    injected = False
    peer_text = 'ACCEPTED_AFTER_THE_PROMPT_BOUNDARY'

    def between(number, position, base=512):
        nonlocal injected
        offer = begin(number, position, base)
        if position == 0 and not injected:
            injected = True
            recorded(number, 1, accepted=True, text=peer_text)
            recorded(number, 2, text='PRIVATE_VETO_AFTER_BOUNDARY')
        return offer

    monkeypatch.setattr('metaform.modules.roundtables.roundtable.allowance.begin', between)

    async def reply(seat, text):
        return 'Own accepted contribution.'

    handlers[0] = reply
    table = runner.Table(number)
    for _ in range(3):
        assert asyncio.run(table.turn(table.row(), store.seats(number)[0]))
    own = [text for position, text in prompts if position == 0]
    assert injected, 'Exercise the mutation between the runner\'s begin and history read.'
    assert peer_text not in own[0] and '512 characters' in own[0]
    assert own[1].count(peer_text) == 1 and own[1].startswith('Your limit for this turn is 1024 characters.')
    assert peer_text not in own[2] and own[2].startswith('Your limit for this turn is 512 characters.')
    assert all('PRIVATE_VETO_AFTER_BOUNDARY' not in prompt and 'T02' not in prompt for prompt in own)
    assert state(number, 0)['credit'] == 0


def test_new_physical_continuation_refreshes_old_boundary_without_replacing_its_receipt_or_limit(panel):
    make, _, _ = panel
    number = make()
    recorded(number, 1, accepted=True, text='Already shown.')
    store.seat_change(number, 0, seen=1)
    offer = allowance.begin(number, 0)
    allowance.delivered(number, 0, offer.receipt)
    with store.connect() as db:
        extra = store.plain(db.execute('SELECT extra FROM seats WHERE discussion=? AND position=0',
                                       (number,)).fetchone())['extra']
        extra['reply_allowance']['pending'].pop('through')
        store.update(db, 'seats', {'discussion': number, 'position': 0}, {'extra': extra})
    recorded(number, 1, accepted=True, text='Missed after delivery.')
    restored = allowance.begin(number, 0)
    assert restored.receipt == offer.receipt and restored.limit == offer.limit and restored.offered == offer.offered
    assert restored.through == 2
    assert state(number, 0)['credit'] == 1
    assert state(number, 0)['pending']['delivered'] is True


def test_receipts_and_pending_promises_survive_restart_without_double_banking_or_peer_credit(panel):
    make, _, _ = panel
    number = make()
    first = allowance.begin(number, 0)
    watcher = allowance.begin(number, 1)
    recorded(number, 0, kind='pass', text='PASS', receipt=first.receipt)
    repeated = recorded(number, 0, kind='pass', text='PASS', receipt=first.receipt)
    assert repeated['number'] == 1 and state(number, 0)['credit'] == 1
    offer = allowance.begin(number, 0)
    assert allowance.begin(number, 0) == offer
    assert render.reply_limit(runner.Table(number).row(), 0) == 1024
    recorded(number, 0, accepted=True, receipt=offer.receipt)
    recorded(number, 0, accepted=True, receipt=offer.receipt)
    assert state(number, 1)['credit'] == 1
    continued = allowance.begin(number, 1)
    assert continued.receipt == watcher.receipt and continued.limit == watcher.limit
    assert continued.through == 2
    assert len(store.submissions(number)) == 2


def test_credited_text_is_the_jev_candidate_and_its_captured_limit_survives_judging_retry(panel, monkeypatch):
    make, handlers, prompts = panel
    number = make(judging=True)
    bank_passes(number, 0, 3)
    calls = []

    def asked(given, criteria, **kwargs):
        calls.append(given)
        return judge.Asked(request={'state': given}, criteria=criteria,
                           nouls=None if len(calls) == 1 else {name: .99 for name in criteria},
                           error='Fixture temporary judgment failure.' if len(calls) == 1 else None)

    monkeypatch.setattr(judge, 'ask', Mock(side_effect=asked))

    async def reply(seat, text):
        return 'z' * 2300

    handlers[0] = reply
    assert not asyncio.run(runner.Table(number).turn(store.discussion(number), store.seats(number)[0]))
    held = store.discussion(number)
    assert held['state'] == 'held' and held['unjudged']['allowance_limit'] == 2048
    assert state(number, 0)['credit'] == 3 and state(number, 0)['pending']['busy'] is False
    store.change(number, state='running', snapshot={**held['snapshot'], 'reply_limit': 80})
    assert asyncio.run(runner.Table(number).turn(store.discussion(number), store.seats(number)[0]))
    assert [fromstring(call['xml']).find('candidate').text for call in calls] == ['z' * 2048] * 2
    assert len(prompts) == 1, 'A judgment retry must not request another model reply.'
    assert store.submissions(number)[-1]['text'] == 'z' * 2048
    assert state(number, 0)['credit'] == 0


@pytest.mark.parametrize('unfinished', ['panel_reply', 'unjudged'])
def test_restart_after_committed_reply_clears_only_the_matching_receipt_without_another_jev_call(
        panel, monkeypatch, unfinished):
    make, handlers, _ = panel
    number = make(judging=True)
    bank_passes(number, 0, 3)
    durable = []
    change = store.seat_change

    def keep(number, position, **changes):
        pending = (changes.get('extra') or {}).get('panel_reply')
        if pending:
            durable.append(deepcopy(pending))
        change(number, position, **changes)

    monkeypatch.setattr(store, 'seat_change', keep)
    asked = Mock(side_effect=lambda given, criteria, **_: judge.Asked(
        request={'state': given}, criteria=criteria, nouls={name: .99 for name in criteria}))
    monkeypatch.setattr(judge, 'ask', asked)

    async def reply(seat, text):
        return 'q' * 2300

    handlers[0] = reply
    assert asyncio.run(runner.Table(number).turn(store.discussion(number), store.seats(number)[0]))
    assert state(number, 0)['credit'] == 0
    pending = durable[-1]
    if unfinished == 'panel_reply':
        store.seat_change(number, 0, extra={**store.seats(number)[0]['extra'], 'panel_reply': pending})
    else:
        store.change(number, unjudged={'position': 0, 'text': 'q' * 2048, 'original': pending['original'],
                                      'use': {}, 'usage_id': pending['usage_id'], 'allowance_limit': 2048})

    async def no_reply(seat, text):
        pytest.fail('A committed receipt must not request another native reply.')

    handlers[0] = no_reply
    assert asyncio.run(runner.Table(number).turn(store.discussion(number), store.seats(number)[0]))
    assert asked.call_count == 1 and len(store.submissions(number)) == 4
    assert store.discussion(number)['unjudged'] is None
    assert store.seats(number)[0]['extra'].get('panel_reply') is None
    assert state(number, 0)['credit'] == 0
    newer = allowance.begin(number, 0)
    assert allowance.completed(number, pending['usage_id'], 0)
    assert state(number, 0)['pending']['receipt'] == newer.receipt


def test_private_failed_condition_precedes_one_effective_allowance_and_public_context(panel, monkeypatch):
    make, handlers, prompts = panel
    number = make(judging=True)
    bank_passes(number, 0, 1)
    outcomes = iter((.1, .99))

    def asked(given, criteria, **kwargs):
        probability = next(outcomes)
        return judge.Asked(request={'state': given}, criteria=criteria,
                           nouls={name: probability for name in criteria})

    monkeypatch.setattr(judge, 'ask', asked)

    async def reply(seat, text):
        return 'A proposal to compare evidence.'

    handlers[0] = reply
    table = runner.Table(number)
    assert asyncio.run(table.turn(table.row(), store.seats(number)[0]))
    failed = store.submissions(number)[-1]
    reason = render.status(failed, 1024)
    assert asyncio.run(table.turn(table.row(), store.seats(number)[0]))
    prompt = [text for position, text in prompts if position == 0][-1]
    assert prompt.startswith(reason + '\n\nYour limit for this turn is 1024 characters.')
    assert prompt.count(reason) == 1 and prompt.count('Your limit for this turn is') == 1
    assert 'A proposal to compare evidence.' not in prompt


def test_native_output_budget_grows_with_the_promised_credit_without_contacting_a_model(panel):
    make, _, _ = panel
    number = make()
    found, row = store.discussion(number), store.seats(number)[0]
    seat = openrouter.ModelSeat(found, row, lambda cost: None)
    seat.ask = AsyncMock(return_value=Reply('Fixture response.'))
    asyncio.run(seat.exchange('Base prompt.', 1))
    base_tokens = seat.ask.call_args.args[1]
    assert base_tokens == config.value('seat_tokens')
    bank_passes(number, 0, 3)
    offer = allowance.begin(number, 0)
    recorded(number, 1, accepted=True)
    assert allowance.limit(found, 0) == offer.limit == 2048
    asyncio.run(seat.exchange('Credited prompt.', 1))
    assert seat.ask.call_args.args[1] > base_tokens
    assert seat.ask.call_args.args[1] >= 4 * (offer.limit - 512) + base_tokens


def test_new_topic_and_explicit_reset_clear_banks_without_stale_extra_resurrecting_them(panel):
    make, _, _ = panel
    number = make()
    bank_passes(number, 0, 2)
    stale = store.seats(number)[0]['extra']
    with store.connect() as db:
        allowance.reset(db, number)
    store.seat_change(number, 0, extra=stale)
    assert state(number, 0)['credit'] == 0 and state(number, 0)['pending'] is None
    bank_passes(number, 0, 2)
    old = allowance.begin(number, 0)
    store.change(number, topic=1)
    fresh = allowance.begin(number, 0)
    assert fresh.limit == 512 and fresh.receipt != old.receipt and state(number, 0)['topic'] == 1


def test_legacy_tables_keep_their_fixed_custom_base_and_new_tables_have_no_arbitrary_credit_cap(panel):
    make, _, _ = panel
    number = make(base=80)
    found = store.discussion(number)
    store.change(number, snapshot={**found['snapshot'], 'reply_credits': False})
    for _ in range(3):
        recorded(number, 0, kind='pass')
    assert allowance.begin(number, 0, 80).limit == 80
    assert render.reply_limit(store.discussion(number), 0) == 80
    number = make()
    bank_passes(number, 0, 24)
    assert allowance.begin(number, 0).limit == 512 * 25
