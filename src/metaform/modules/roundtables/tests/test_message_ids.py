"""Public contribution IDs omit private attempts and survive topic changes, restarts and receipt retries."""
import asyncio
import os
import re
import subprocess
import sys
from xml.etree.ElementTree import fromstring

import pytest

from metaform.modules.roundtables.roundtable import budget, judge, render, runner, store
from metaform.modules.roundtables.roundtable.seat import NoReply, Reply, Seat

pytestmark = pytest.mark.kind('simulation')


@pytest.fixture
def table_factory(tmp_path, monkeypatch):
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    handlers, prompts = {}, []
    active = set()

    class Fake(Seat):
        kind = 'acp'

        async def open(self):
            self.session = self.session or f'fake-{self.position}'

        async def exchange(self, text, seconds):
            await self.open()
            assert self.position not in active, 'The same participant received overlapping prompts.'
            active.add(self.position)
            prompts.append((self.position, text))
            try:
                if self.position in handlers:
                    return Reply(await handlers[self.position](self, text))
                return Reply('PASS')
            finally:
                active.remove(self.position)

        async def report(self, record, seconds):
            return 'Fixture report.'

    monkeypatch.setitem(runner.KINDS, 'acp', Fake)

    def make(*, standalone=False):
        seats = [{'kind': 'acp', 'id': f'acp:claude/{model}', 'agent': 'claude', 'model': model}
                 for model in ('haiku', 'sonnet', 'opus')]
        role = {**seats[0], 'name': 'Fixture host'}
        number = store.opened({'subject': 'Public IDs', 'opening': 'Retain accepted evidence.',
                               'folder': str(tmp_path), 'chair_token': 'fixture', 'reporter': seats[0]['id'],
                               'host': role, 'synthesizer': role, 'rounds': 0, 'spend': 1}, seats,
                              [] if standalone else [
                                  {'name': 'first', 'title': 'First', 'text': 'The first question.'},
                                  {'name': 'second', 'title': 'Second', 'text': 'The second question.'}],
                              judging=False)
        return number

    return make, handlers, prompts


def recorded(number, position, text, *, kind='seat', accepted=False, receipt=None):
    found = store.discussion(number)
    row = store.seats(number)[position] if position is not None else {'id': 'chair', 'name': None}
    saved = store.record(number, {'topic': found['topic'] if found['stage'] else None, 'round': found['round'],
                                  'position': position, 'seat': row['id'], 'name': row['name'],
                                  'kind': kind, 'text': text, 'accepted': accepted}, receipt=receipt)
    return store.submission(number, saved['number'])


def test_rejected_and_non_contribution_attempts_do_not_leave_public_number_gaps(table_factory):
    make, _, _ = table_factory
    number = make()
    rejected = recorded(number, 0, 'PRIVATE_REJECTED')
    passed = recorded(number, 1, 'PASS', kind='pass')
    failed = recorded(number, 2, 'PRIVATE_ENDPOINT_FAILURE', kind='none')
    first = recorded(number, 1, 'ACCEPTED_FIRST', accepted=True)
    another_rejection = recorded(number, 2, 'PRIVATE_REJECTED_AGAIN')
    second = recorded(number, 2, 'ACCEPTED_SECOND', accepted=True)
    assert [row['message_id'] for row in (rejected, passed, failed, another_rejection)] == [None] * 4
    assert [first['message_id'], second['message_id']] == ['R1-1', 'R1-2']
    assert [row['number'] for row in store.submissions(number)] == list(range(1, 7))
    assert [first['number'], second['number']] == [4, 6], 'Owner cursors retain the private attempt sequence.'
    table = runner.Table(number)
    row = store.seats(number)[0]
    peer_view = table.topic_view(table.row(), row, table.seat(row), store.submissions(number))
    assert re.findall(r'(?m)^(R\d+-\d+)\s', peer_view) == ['R1-1', 'R1-2']
    assert not re.search(r'\bT\d+\b', peer_view)
    assert 'PRIVATE_REJECTED' not in peer_view and 'PRIVATE_ENDPOINT_FAILURE' not in peer_view


def test_chair_comments_share_the_public_counter_but_phase_and_private_artifacts_do_not(table_factory):
    make, _, _ = table_factory
    number = make()
    first = recorded(number, 0, 'ACCEPTED_FIRST', accepted=True)
    comment = recorded(number, None, 'A visible chair clarification.', kind='chair')
    store.phase(number, 'collaboration', 'Phase opening without a contribution number.')
    opening = store.submissions(number)[-1]
    assert opening['message_id'] is None
    public_opening = render.entry(opening)
    assert opening['text'] in public_opening
    assert not re.search(r'\b(?:R\d+-\d+|T\d+)\b', public_opening)
    for kind in ('carry', 'handoff', 'farewell'):
        artifact = recorded(number, 0, f'Artifact: {kind}.', kind=kind, accepted=True)
        assert artifact['message_id'] is None
    store.scorecard_record(number, 0, 'A private scorecard.')
    contribution = recorded(number, 1, 'ACCEPTED_COLLABORATION', kind='collab', accepted=True)
    assert [row['message_id'] for row in (first, comment, contribution)] == ['R1-1', 'R1-2', 'R1-3']


def test_public_ids_persist_across_runner_restart_and_start_at_one_on_the_next_topic(table_factory):
    make, _, _ = table_factory
    number = make()
    first = recorded(number, 0, 'First accepted contribution.', accepted=True)
    script = '''import sys
from metaform.modules.roundtables.roundtable import store
number = int(sys.argv[1])
found, row = store.discussion(number), store.seats(number)[1]
saved = store.record(number, {'topic': found['topic'], 'round': found['round'], 'position': row['position'],
                             'seat': row['id'], 'name': row['name'], 'kind': 'seat',
                             'text': 'Second accepted contribution.', 'accepted': True})
print(saved['message_id'])
'''
    answer = subprocess.run([sys.executable, '-', str(number)], input=script, capture_output=True, text=True,
                            check=True, timeout=15,
                            env={**os.environ, 'PYTHONPATH': os.pathsep.join(sys.path)})
    assert answer.stdout.strip() == 'R1-2'
    restarted = runner.Table(number)
    second = store.submissions(number)[-1]
    assert [first['message_id'], second['message_id']] == ['R1-1', 'R1-2']
    restarted.next_topic(restarted.row())
    next_topic = recorded(number, 2, 'First contribution on topic two.', accepted=True)
    assert next_topic['message_id'] == 'R2-1'
    assert store.submission(number, first['number'])['message_id'] == 'R1-1'
    assert store.submission(number, second['number'])['message_id'] == 'R1-2'


def test_concurrent_recovery_of_one_physical_receipt_allocates_one_public_id(table_factory):
    make, _, _ = table_factory
    number = make()
    budget.record_reply(store.discussion(number), store.seats(number)[0], {'completion_tokens': 7}, 'one-reply')

    async def duplicate_receipt():
        return await asyncio.gather(*(
            asyncio.to_thread(recorded, number, 0, 'Accepted response delivered once.', accepted=True,
                              receipt='one-reply') for _ in range(2)))

    recovered = asyncio.run(duplicate_receipt())
    assert [row['message_id'] for row in recovered] == ['R1-1', 'R1-1']
    assert len({row['number'] for row in recovered}) == 1
    recorded(number, 1, 'A hidden rejection.')
    following = recorded(number, 2, 'The next actual public contribution.', accepted=True)
    assert following['message_id'] == 'R1-2'
    assert len(store.submissions(number)) == 3
    assert budget.progress(store.discussion(number))['participants'][0]['tokens'] == 7


def test_concurrent_accepted_contributions_receive_distinct_contiguous_ids(table_factory):
    make, _, _ = table_factory
    number = make()

    async def simultaneous():
        return await asyncio.gather(*(
            asyncio.to_thread(recorded, number, position, f'Accepted contribution {position}.', accepted=True)
            for position in range(3)))

    rows = asyncio.run(simultaneous())
    assert sorted(row['message_id'] for row in rows) == ['R1-1', 'R1-2', 'R1-3']
    assert len({row['number'] for row in rows}) == 3


def test_judge_history_uses_public_ids_and_preserves_legacy_labels(table_factory):
    make, _, _ = table_factory
    number = make()
    recorded(number, 0, 'Private rejection.')
    first = recorded(number, 1, 'Accepted fact.', accepted=True)
    recorded(number, 0, 'PASS', kind='pass')
    second = recorded(number, 2, 'Another accepted fact.', accepted=True)
    state = judge.windowed_state('Original instructions.', store.topics(number)[0], store.submissions(number),
                                  {'position': 0, 'text': 'A new candidate.'}, judge.questions(store.CHECKS))
    assert [row.attrib['turn'] for row in fromstring(state['xml']).findall('recent_responses/response')] == [
        first['message_id'], second['message_id']]
    legacy = make()
    found = store.discussion(legacy)
    snapshot = dict(found['snapshot'])
    snapshot.pop('message_ids')
    store.change(legacy, snapshot=snapshot)
    old = recorded(legacy, 0, 'A historical contribution.', accepted=True)
    assert old['message_id'] is None
    assert render.entry(old).startswith(render.turn(old['number']) + ' ')


@pytest.mark.parametrize('contribute', [False, True])
def test_returning_busy_participant_receives_one_latest_batch_and_can_answer_once_or_pass(table_factory, contribute):
    make, handlers, prompts = table_factory
    number = make(standalone=True)
    counts = {0: 0, 1: 0, 2: 0}

    async def scenario():
        blocked, ready, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def busy(seat, text):
            counts[0] += 1
            if counts[0] == 1:
                blocked.set()
                await release.wait()
                return 'PASS'
            if counts[0] == 2 and contribute:
                return 'ONE_OPTIONAL_RETURNING_RESPONSE'
            return 'PASS'

        async def other(seat, text):
            counts[seat.position] += 1
            at = counts[seat.position]
            if seat.position == 1 and at == 1:
                raise NoReply('Private failed endpoint attempt.', delivered=False)
            first = 2 if seat.position == 1 else 1
            if at == first:
                return f'QUEUED_PUBLIC_EVIDENCE_{seat.position}'
            public = [row for row in store.submissions(number) if row['accepted']]
            if len(public) >= 2:
                ready.set()
            return 'PASS'

        handlers.update({0: busy, 1: other, 2: other})
        task = asyncio.create_task(runner.Table(number).run())
        try:
            await asyncio.wait_for(blocked.wait(), 2)
            await asyncio.wait_for(ready.wait(), 2)
            assert counts[0] == 1 and not task.done()
            release.set()
            assert (await asyncio.wait_for(task, 5))['state'] == 'ended'
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())
    returning = [text for position, text in prompts if position == 0]
    # The optional new contribution needs one later full-round PASS, never a reply for every queued message.
    assert len(returning) == 2 + int(contribute)
    batch = returning[1]
    assert re.findall(r'(?m)^(R\d+-\d+)\s', batch) == ['R1-1', 'R1-2']
    assert not re.search(r'\bT\d+\b', batch)
    for position in (1, 2):
        marker = f'QUEUED_PUBLIC_EVIDENCE_{position}'
        assert sum(text.count(marker) for text in returning) == 1
    assert 'Private failed endpoint attempt' not in batch
    own = [row for row in store.submissions(number) if row['text'] == 'ONE_OPTIONAL_RETURNING_RESPONSE']
    assert len(own) == int(contribute)
    assert [row['message_id'] for row in store.submissions(number) if row['accepted']] == [
        f'R1-{at}' for at in range(1, 4 if contribute else 3)]
