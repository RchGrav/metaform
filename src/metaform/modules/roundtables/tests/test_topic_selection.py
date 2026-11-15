"""Private topic selection batches canonical similarity questions and preserves real probability evidence."""
import importlib
from unittest.mock import Mock

import pytest

pytestmark = pytest.mark.kind('simulation')


@pytest.fixture
def private_table(run, tmp_path, monkeypatch, request):
    folder = tmp_path / 'project'
    folder.mkdir()
    run('add', 'project', 'private-topics', str(folder))
    run('enable', 'dispatch', cwd=folder)
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    store = importlib.import_module('metaform.modules.roundtables.roundtable.store')
    topics = importlib.import_module('metaform.modules.roundtables.roundtable.topics')
    chosen = [{'kind': 'acp', 'id': f'acp:claude/model-{at}', 'agent': 'claude', 'model': f'model-{at}'}
              for at in range(getattr(request, 'param', 3))]
    number = store.opened({'subject': 'Private proposals', 'opening': 'Keep original instructions.',
                           'folder': str(folder), 'chair_key': None, 'chair_token': 'fixture',
                           'reporter': chosen[0]['id'], 'rounds': 0, 'spend': 1}, chosen,
                          [{'name': 'first', 'title': 'First', 'text': 'The current topic.'}], judging=False,
                          session={'total': 2, 'folder': str(tmp_path / 'materials')})
    found = store.discussion(number)
    topics.seed(found, store.seats(number))
    return topics, store, found


def save(given, position, text):
    topics, _, found = given
    receipt = topics.begin_proposal(found, position)
    assert receipt
    topics.finish_proposal(found, position, receipt, text, {'prompt_tokens': 10, 'completion_tokens': 5})


def test_all_unordered_pairs_share_one_request_and_each_probability_credits_both_proposals(private_table, monkeypatch):
    topics, store, found = private_table
    for position, text in enumerate(('Alpha proposal.', 'Beta proposal.', 'Gamma proposal.')):
        save(private_table, position, text)
    posted = Mock(return_value={'answers': {'p0_1': {'noul': .62}, 'p0_2': {'noul': .20}, 'p1_2': {'noul': .40}},
                                'usage': {'cost': .0001, 'input_tokens': 30}})
    monkeypatch.setattr(topics.openrouter, 'post', posted)
    decision = topics.decide(found, 'The current topic.')
    assert decision['text'] == 'Beta proposal.'
    assert decision['scores'] == {'0': .41, '1': .51, '2': .30}
    assert decision['scores']['1'] < .70, 'There is no topic eligibility cutoff.'
    assert posted.call_count == 1
    path, body = posted.call_args.args
    assert path == '/alpha/decisions' and posted.call_args.kwargs['retry'] is False
    assert list(body['questions']) == ['p0_1', 'p0_2', 'p1_2']
    assert all(question['type'] == 'noul' for question in body['questions'].values())
    assert all('similar' in question['instructions']['question'].casefold() for question in body['questions'].values())
    assert 'model-0' not in str(body) and 'claude' not in str(body)
    assert topics.decide(found, 'The current topic.')['text'] == 'Beta proposal.'
    assert posted.call_count == 1
    assert store.discussion(found['number'])['spent'] == .0001
    assert not any('proposal.' in row['text'] for row in store.submissions(found['number']))


@pytest.mark.parametrize('private_table', [2], indirect=True)
def test_two_proposals_always_receive_the_same_pair_score_and_ties_keep_both_verbatim(private_table, monkeypatch):
    topics, _, found = private_table
    save(private_table, 0, '  First proposal <unchanged>.\n')
    save(private_table, 1, 'Second proposal & evidence.')
    posted = Mock(return_value={'answers': {'p0_1': {'noul': .001}}})
    monkeypatch.setattr(topics.openrouter, 'post', posted)
    decision = topics.decide(found, 'Current topic.')
    assert decision['scores'] == {'0': .001, '1': .001}
    assert decision['text'] == '  First proposal <unchanged>.\n\n\nSecond proposal & evidence.'


def test_exact_means_are_compared_without_rounding_before_ranking(private_table):
    topics, _, _ = private_table
    rows = [{'position': index, 'text': f'Proposal {index}'} for index in range(3)]
    result = topics.rank(rows, {'answers': {'p0_1': {'noul': .5001}, 'p0_2': {'noul': .5002},
                                         'p1_2': {'noul': .5003}}})
    assert result['text'] == 'Proposal 2'
    tied = topics.rank(rows, {'answers': {'p0_1': {'noul': .1}, 'p0_2': {'noul': .2}, 'p1_2': {'noul': .2}}})
    assert tied['text'] == 'Proposal 2'
    tied = topics.rank(rows, {'answers': {'p0_1': {'noul': .4}, 'p0_2': {'noul': .2}, 'p1_2': {'noul': .2}}})
    assert tied['text'] == 'Proposal 0\n\nProposal 1'


@pytest.mark.parametrize('private_table', [1], indirect=True)
def test_sole_proposal_wins_without_a_jev_call(private_table, monkeypatch):
    topics, _, found = private_table
    save(private_table, 0, 'The sole proposal wins directly.')
    posted = Mock(side_effect=AssertionError('A sole proposal needs no comparison.'))
    monkeypatch.setattr(topics.openrouter, 'post', posted)
    assert topics.decide(found, 'Current topic.')['text'] == 'The sole proposal wins directly.'
    posted.assert_not_called()


def test_missing_pair_answer_preserves_error_and_usage_without_publishing_or_repaying(private_table, monkeypatch):
    topics, store, found = private_table
    for position in range(3):
        save(private_table, position, f'Proposal {position}')
    posted = Mock(return_value={'answers': {'p0_1': {'noul': .9}}, 'usage': {'cost': .0001}})
    monkeypatch.setattr(topics.openrouter, 'post', posted)
    for _ in range(2):
        with pytest.raises(ValueError, match='every private topic-pair probability'):
            topics.decide(found, 'Current topic.')
    assert posted.call_count == 1 and store.discussion(found['number'])['spent'] == .0001
    with store.connect() as db:
        saved = store.plain(db.execute('SELECT * FROM topic_decisions WHERE discussion=?', (found['number'],)).fetchone())
    assert saved['state'] == 'error' and saved['text'] is None and saved['scores'] is None
    assert saved['response']['answers']['p0_1']['noul'] == .9
    assert len(store.topics(found['number'])) == 1


@pytest.mark.parametrize('private_table', [2], indirect=True)
def test_unsent_comparison_after_missing_key_can_retry_without_reasking_or_double_charging(private_table, monkeypatch):
    topics, store, found = private_table
    save(private_table, 0, 'A completed private proposal.')
    save(private_table, 1, 'Another completed private proposal.')
    proposals = topics.proposals(found['number'], found['topic'])
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    transport = Mock(side_effect=AssertionError('Missing credentials must not reach the network.'))
    monkeypatch.setattr(topics.openrouter.urllib.request, 'urlopen', transport)
    with pytest.raises(ValueError, match='OPENROUTER_API_KEY is not set'):
        topics.decide(found, 'Current topic.')
    transport.assert_not_called()
    with store.connect() as db:
        unsent = store.plain(db.execute('SELECT * FROM topic_decisions WHERE discussion=?',
                                       (found['number'],)).fetchone())
    assert unsent['state'] == 'pending' and unsent['response'] is None
    assert store.discussion(found['number'])['spent'] == 0
    monkeypatch.setenv('OPENROUTER_API_KEY', 'fake-test-key')

    def answer(path, body, **kwargs):
        assert topics.config.openrouter_key() == 'fake-test-key'
        kwargs['tried']()
        return {'answers': {'p0_1': {'noul': .72}}, 'usage': {'cost': .0001}}

    posted = Mock(side_effect=answer)
    monkeypatch.setattr(topics.openrouter, 'post', posted)
    chosen = topics.decide(found, 'Current topic.')
    assert chosen['state'] == 'ready' and chosen['scores'] == {'0': .72, '1': .72}
    assert chosen['text'] == 'A completed private proposal.\n\nAnother completed private proposal.'
    assert topics.decide(found, 'Current topic.')['text'] == chosen['text']
    assert posted.call_count == 1 and store.discussion(found['number'])['spent'] == .0001
    assert topics.proposals(found['number'], found['topic']) == proposals


@pytest.mark.parametrize('private_table', [2], indirect=True)
def test_legacy_missing_key_error_is_known_unsent_and_can_retry_the_comparison(private_table, monkeypatch):
    topics, store, found = private_table
    save(private_table, 0, 'One preserved proposal.')
    save(private_table, 1, 'Another preserved proposal.')
    with store.connect() as db:
        store.insert(db, 'topic_decisions', {'discussion': found['number'], 'topic': found['topic'],
                     'state': 'error', 'request': {'recorded': 'before credential preflight'}, 'response': None,
                     'error': 'Silent: OPENROUTER_API_KEY is not set in the environment.', 'created': store.stamp()})

    def answer(path, body, **kwargs):
        kwargs['tried']()
        return {'answers': {'p0_1': {'noul': .64}}, 'usage': {'cost': .0002}}

    posted = Mock(side_effect=answer)
    monkeypatch.setattr(topics.openrouter, 'post', posted)
    chosen = topics.decide(found, 'Current topic.')
    assert chosen['state'] == 'ready' and chosen['scores'] == {'0': .64, '1': .64}
    assert topics.decide(found, 'Current topic.')['text'] == chosen['text']
    assert posted.call_count == 1 and store.discussion(found['number'])['spent'] == .0002
    assert len(store.topics(found['number'])) == 1


@pytest.mark.parametrize('private_table', [2], indirect=True)
def test_unknown_sent_comparison_is_not_replayed_or_mistaken_for_an_actual_tie(private_table, monkeypatch):
    topics, store, found = private_table
    save(private_table, 0, 'One proposal.')
    save(private_table, 1, 'Another proposal.')
    with store.connect() as db:
        store.insert(db, 'topic_decisions', {'discussion': found['number'], 'topic': found['topic'],
                     'state': 'sent', 'request': {'recorded': 'before transport'}, 'created': store.stamp()})
    posted = Mock(side_effect=AssertionError('A sent request is never replayed.'))
    monkeypatch.setattr(topics.openrouter, 'post', posted)
    with pytest.raises(ValueError, match='not resent'):
        topics.decide(found, 'Current topic.')
    posted.assert_not_called()
    assert len(store.topics(found['number'])) == 1


def test_exhausted_proposal_is_excluded_from_the_comparison_without_an_invented_score(private_table, monkeypatch):
    topics, store, found = private_table
    save(private_table, 0, 'A valid proposal.')
    save(private_table, 1, 'Another valid proposal.')
    for _ in range(2):
        receipt = topics.begin_proposal(found, 2)
        assert receipt
        topics.finish_proposal(found, 2, receipt, None, {'error': 'No reply returned.'})
    assert topics.begin_proposal(found, 2) is None
    posted = Mock(return_value={'answers': {'p0_1': {'noul': .75}}})
    monkeypatch.setattr(topics.openrouter, 'post', posted)
    decision = topics.decide(found, 'Current topic.')
    assert decision['text'] == 'A valid proposal.\n\nAnother valid proposal.'
    assert decision['scores'] == {'0': .75, '1': .75}
    assert list(posted.call_args.args[1]['questions']) == ['p0_1']
    assert posted.call_args.args[1]['state']['proposals'] == {
        'P1': 'A valid proposal.', 'P2': 'Another valid proposal.'}
    assert len(store.topics(found['number'])) == 1


def test_comparison_waits_while_a_missing_proposer_still_has_a_retry_in_progress(private_table, monkeypatch):
    topics, _, found = private_table
    save(private_table, 0, 'First completed proposal.')
    save(private_table, 1, 'Second completed proposal.')
    receipt = topics.begin_proposal(found, 2)
    topics.finish_proposal(found, 2, receipt, None, {'error': 'The first request timed out.'})
    posted = Mock(side_effect=AssertionError('The missing participant still has an attempt remaining.'))
    monkeypatch.setattr(topics.openrouter, 'post', posted)
    with pytest.raises(ValueError, match='still being collected'):
        topics.decide(found, 'Current topic.')
    retry = topics.begin_proposal(found, 2)
    assert retry
    with pytest.raises(ValueError, match='still being collected'):
        topics.decide(found, 'Current topic.')
    posted.assert_not_called()


def test_interrupted_proposal_retries_with_a_new_receipt_without_overwriting_a_ready_proposal(private_table):
    topics, _, found = private_table
    receipt = topics.begin_proposal(found, 0)
    assert receipt and topics.begin_proposal(found, 0) is None
    topics.recover(found, {0})
    assert topics.proposals(found['number'], found['topic'])[0]['state'] == 'sent'
    topics.recover(found, set())
    replacement = topics.begin_proposal(found, 0)
    assert replacement and replacement != receipt
    assert topics.finish_proposal(found, 0, receipt, 'The obsolete response.', {}) is False
    assert topics.finish_proposal(found, 0, replacement, 'The recovered proposal.', {'completion_tokens': 5}) is True
    assert topics.finish_proposal(found, 0, replacement, None, {'error': 'Late failure.'}) is False
    assert topics.begin_proposal(found, 0) is None
    saved = topics.proposals(found['number'], found['topic'])[0]
    assert saved['state'] == 'ready' and saved['text'] == 'The recovered proposal.'
    assert saved['receipt'] == replacement and saved['usage']['completion_tokens'] == 5
    assert saved['attempts'] == 2


@pytest.mark.parametrize('text', [None, '', ' ', 'PASS', 'done'])
def test_missing_or_invalid_proposal_can_be_retried_without_reasking_ready_participants(private_table, text):
    topics, _, found = private_table
    save(private_table, 0, 'An already returned proposal.')
    before = topics.proposals(found['number'], found['topic'])[0]
    receipt = topics.begin_proposal(found, 1)
    assert receipt
    assert topics.finish_proposal(found, 1, receipt, text, {'error': 'No usable proposal.'}) is False
    assert topics.proposals(found['number'], found['topic'])[1]['state'] == 'pending'
    save(private_table, 1, 'The retry succeeded.')
    topics.recover(found, set())
    assert topics.proposals(found['number'], found['topic'])[0] == before
    assert topics.begin_proposal(found, 0) is None and topics.begin_proposal(found, 1) is None


def test_historical_failed_proposal_is_retryable_after_recovery(private_table):
    topics, store, found = private_table
    save(private_table, 0, 'Keep the completed proposal.')
    receipt = topics.begin_proposal(found, 1)
    with store.connect() as db:
        store.update(db, 'topic_proposals', {'discussion': found['number'], 'topic': found['topic'], 'position': 1},
                     {'state': 'error', 'usage': {'error': '300 seconds'}})
    topics.recover(found, set())
    assert topics.proposals(found['number'], found['topic'])[1]['usage']['error'] == '300 seconds'
    replacement = topics.begin_proposal(found, 1)
    assert replacement and replacement != receipt
    assert topics.begin_proposal(found, 0) is None


def test_attempt_migration_preserves_proposals_receipts_and_unused_allowances(private_table):
    topics, store, found = private_table
    save(private_table, 0, 'Keep the ready proposal and its usage.')
    failed_receipt = topics.begin_proposal(found, 1)
    with store.connect() as db:
        store.update(db, 'topic_proposals', {'discussion': found['number'], 'topic': found['topic'], 'position': 1},
                     {'state': 'error', 'usage': {'error': '300 seconds'}})
        db.execute('ALTER TABLE topic_proposals DROP COLUMN attempts')
    path = str(store.config.home() / 'roundtable.sqlite3')
    store._migrated.discard(path)
    migrated = topics.proposals(found['number'], found['topic'])
    assert [row['attempts'] for row in migrated] == [1, 1, 0]
    assert migrated[0]['text'] == 'Keep the ready proposal and its usage.'
    assert migrated[0]['usage']['completion_tokens'] == 5
    assert migrated[1]['receipt'] == failed_receipt and migrated[1]['usage'] == {'error': '300 seconds'}
    topics.recover(found, set())
    replacement = topics.begin_proposal(found, 1)
    assert replacement and replacement != failed_receipt
    topics.finish_proposal(found, 1, replacement, None, {'error': 'Retry timed out.'})
    store._migrated.discard(path)
    assert topics.proposals(found['number'], found['topic'])[1]['attempts'] == 2
    assert topics.begin_proposal(found, 1) is None


def test_interrupted_second_attempt_is_terminal_across_repeated_recovery(private_table):
    topics, _, found = private_table
    first = topics.begin_proposal(found, 0)
    assert first
    topics.recover(found, set())
    second = topics.begin_proposal(found, 0)
    assert second and second != first
    for _ in range(3):
        topics.recover(found, set())
        assert topics.begin_proposal(found, 0) is None
    saved = topics.proposals(found['number'], found['topic'])[0]
    assert saved['attempts'] == 2 and saved['state'] == 'error'
    assert topics.finish_proposal(found, 0, second, 'A late response after recovery.', {}) is False


def test_sole_valid_proposal_after_other_attempts_exhausted_wins_without_comparison(private_table, monkeypatch):
    topics, _, found = private_table
    save(private_table, 1, 'The only returned proposal.')
    for position in (0, 2):
        for _ in range(2):
            receipt = topics.begin_proposal(found, position)
            topics.finish_proposal(found, position, receipt, 'PASS', {})
    posted = Mock(side_effect=AssertionError('No pair exists to compare.'))
    monkeypatch.setattr(topics.openrouter, 'post', posted)
    decision = topics.decide(found, 'Current topic.')
    assert decision['text'] == 'The only returned proposal.'
    assert decision['scores'] == {'1': None}
    posted.assert_not_called()


def test_no_returned_proposal_does_not_invent_a_next_topic(private_table, monkeypatch):
    topics, store, found = private_table
    for position in range(3):
        for _ in range(2):
            receipt = topics.begin_proposal(found, position)
            topics.finish_proposal(found, position, receipt, None, {'error': 'Timed out.'})
    posted = Mock(side_effect=AssertionError('There are no proposals to compare.'))
    monkeypatch.setattr(topics.openrouter, 'post', posted)
    with pytest.raises(ValueError, match='(?i)no .*proposal'):
        topics.decide(found, 'Current topic.')
    posted.assert_not_called()
    assert len(store.topics(found['number'])) == 1


def test_explicit_reseat_recovers_only_remaining_proposal_attempt_without_a_candidate(private_table):
    topics, store, found = private_table
    first = topics.begin_proposal(found, 0)
    topics.finish_proposal(found, 0, first, None, {'error': 'Native connection ended.'})
    store.seat_change(found['number'], 0, gone='Native connection ended.', availability='unavailable',
                      session='keep-this-native-session', messages=[{'role': 'user', 'content': 'Keep this history.'}],
                      seen=7)
    topics.skip(found, {0})
    for position in (1, 2):
        for _ in range(2):
            receipt = topics.begin_proposal(found, position)
            topics.finish_proposal(found, position, receipt, None, {'error': 'No proposal.'})
    exhausted = topics.proposals(found['number'], found['topic'])[1:]
    topics.recover(found, set())
    assert topics.proposals(found['number'], found['topic'])[0]['state'] == 'skipped'
    store.reseat(found['number'], 0, fresh=False)
    topics.recover(found, set())
    second = topics.begin_proposal(found, 0)
    assert second and second != first
    topics.finish_proposal(found, 0, second, 'A proposal after the explicit reseat.', {})
    assert topics.decide(found, 'Current topic.')['text'] == 'A proposal after the explicit reseat.'
    assert topics.proposals(found['number'], found['topic'])[1:] == exhausted
    assert topics.begin_proposal(found, 0) is None
    restored = store.seats(found['number'])[0]
    assert restored['session'] == 'keep-this-native-session' and restored['seen'] == 7
    assert restored['messages'] == [{'role': 'user', 'content': 'Keep this history.'}]


def test_reseat_cannot_reopen_a_skipped_proposal_when_a_valid_candidate_already_exists(private_table):
    topics, store, found = private_table
    save(private_table, 0, 'Keep this valid candidate.')
    topics.skip(found, {1})
    store.reseat(found['number'], 1, fresh=False)
    topics.recover(found, set())
    assert topics.proposals(found['number'], found['topic'])[1]['state'] == 'skipped'
    assert topics.begin_proposal(found, 1) is None


def test_single_attempt_transport_option_never_replays_after_a_network_failure(monkeypatch):
    module = importlib.import_module('metaform.modules.roundtables.roundtable.openrouter')
    monkeypatch.setattr(module.config, 'openrouter_key', lambda: 'fake-test-key')
    transport = Mock(side_effect=ConnectionError('Unknown remote acceptance'))
    monkeypatch.setattr(module.urllib.request, 'urlopen', transport)
    with pytest.raises(module.Silent, match='Unknown remote acceptance'):
        module.post('/alpha/decisions', {'questions': {}}, retry=False)
    transport.assert_called_once()
