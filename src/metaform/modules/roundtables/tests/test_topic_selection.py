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


def test_failed_proposal_never_becomes_a_zero_score_or_silent_subset_winner(private_table, monkeypatch):
    topics, store, found = private_table
    save(private_table, 0, 'A valid proposal.')
    save(private_table, 1, 'Another valid proposal.')
    receipt = topics.begin_proposal(found, 2)
    topics.finish_proposal(found, 2, receipt, None, {'error': 'No reply returned.'})
    posted = Mock(side_effect=AssertionError('No subset comparison is allowed.'))
    monkeypatch.setattr(topics.openrouter, 'post', posted)
    with pytest.raises(ValueError, match='Not every participant'):
        topics.decide(found, 'Current topic.')
    posted.assert_not_called()
    assert len(store.topics(found['number'])) == 1


def test_one_model_attempt_and_private_usage_survive_restart(private_table):
    topics, _, found = private_table
    receipt = topics.begin_proposal(found, 0)
    assert receipt and topics.begin_proposal(found, 0) is None
    topics.recover(found, set())
    assert topics.begin_proposal(found, 0) is None
    saved = topics.proposals(found['number'], found['topic'])[0]
    assert saved['state'] == 'error' and saved['receipt'] == receipt
    save(private_table, 1, 'A returned proposal.')
    assert topics.proposals(found['number'], found['topic'])[1]['usage']['completion_tokens'] == 5


def test_single_attempt_transport_option_never_replays_after_a_network_failure(monkeypatch):
    module = importlib.import_module('metaform.modules.roundtables.roundtable.openrouter')
    monkeypatch.setattr(module.config, 'openrouter_key', lambda: 'fake-test-key')
    transport = Mock(side_effect=ConnectionError('Unknown remote acceptance'))
    monkeypatch.setattr(module.urllib.request, 'urlopen', transport)
    with pytest.raises(module.Silent, match='Unknown remote acceptance'):
        module.post('/alpha/decisions', {'questions': {}}, retry=False)
    transport.assert_called_once()
