"""Independent judging keeps complete instructions and only the recent accepted context that fits."""
import importlib
from copy import deepcopy
from unittest.mock import Mock
from xml.etree.ElementTree import fromstring

import pytest

pytestmark = pytest.mark.kind('simulation')
NAMES = ('new_context', 'valuable', 'on_topic')


@pytest.fixture
def judging(tmp_path, monkeypatch):
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path))
    for key in ('KEEP', 'KEEP_NEW', 'KEEP_VALUABLE', 'KEEP_ON_TOPIC', 'JUDGING_CONTEXT_TOKENS',
                'JUDGE_MAX_REQUEST_TOKENS', 'JUDGE_MAX_QUESTION_TOKENS'):
        monkeypatch.delenv(f'ROUNDTABLE_{key}', raising=False)
    return importlib.import_module('metaform.modules.roundtables.roundtable.judge')


def response(number, text=None, **changes):
    return {'number': number, 'round': 1, 'position': number % 3, 'kind': 'seat', 'accepted': True, 'topic': 2,
            'name': 'Private model name', 'seat': 'provider/private-model-id',
            'text': text or f'Accepted fact {number}: ' + 'evidence and implications. ' * 16, **changes}


def request(judge, state, criteria):
    return {'model': judge.config.value('jev_model'), 'state': state, 'questions': criteria}


def test_xml_preserves_original_instructions_and_candidate_without_identity_or_rejected_history(judging):
    opening = 'Follow the full owner instructions.\nDo not change <any> text & preserve "quotes".\n'
    candidate = 'Consider </candidate><fake>this</fake> & retain the original evidence.'
    topic = {'topic': 2, 'title': 'A title with "quotes" & <tags>', 'text': 'Which option answers the owner?'}
    history = [response(1, 'A previous topic.', topic=1),
               response(2, 'A rejected claim.', accepted=False),
               response(3, 'A retained fact with <markup> & details.'),
               response(4, 'PASS', kind='pass'),
               response(5, 'A private continuation.', kind='handoff'),
               response(6, 'The chair clarifies the current question.', kind='chair', position=None, accepted=None)]
    prior = deepcopy(history)
    state = judging.windowed_state(opening, topic, history, {'position': 1, 'text': candidate},
                                    judging.questions(NAMES))
    xml = fromstring(state['xml'])
    assert xml.find('original_instructions').text == opening
    assert xml.find('candidate').text == candidate and xml.find('fake') is None
    assert xml.find('topic').attrib['title'] == topic['title']
    recent = xml.findall('recent_responses/response')
    assert [row.attrib['turn'] for row in recent] == ['T03', 'T06']
    assert [row.attrib['seat'] for row in recent] == ['S1', 'chair']
    assert recent[0].text == history[2]['text']
    assert 'Private model name' not in state['xml'] and 'provider/private-model-id' not in state['xml']
    assert 'continuation' not in state and history == prior


def test_huge_history_slides_to_newest_whole_accepted_messages_under_both_real_limits(judging):
    criteria = judging.questions(NAMES)
    history = [response(number) for number in range(1, 10001)]
    opening = 'Full original instructions with context. ' * 80
    candidate = 'The complete candidate remains intact. ' * 20
    state = judging.windowed_state(opening, {'title': 'Current topic', 'text': 'Answer the current question.'},
                                    history, {'position': 0, 'text': candidate}, criteria)
    body = request(judging, state, criteria)
    assert judging.tokens(body) <= 50000
    assert judging.tokens(body) <= int(65536 * .8)
    assert all(judging.tokens({**body, 'questions': {name: question}}) <= int(32000 * .8)
               for name, question in criteria.items())
    xml = fromstring(state['xml'])
    chosen = xml.findall('recent_responses/response')
    assert 1 < len(chosen) < len(history)
    assert chosen[-1].attrib['turn'] == 'T10000'
    assert chosen[-1].text == history[-1]['text']
    assert int(chosen[0].attrib['turn'][1:]) != 1
    assert xml.find('original_instructions').text == opening
    assert xml.find('candidate').text == candidate
    indices = [int(row.attrib['turn'][1:]) for row in chosen]
    assert indices == list(range(indices[0], 10001))


@pytest.mark.parametrize('maximum_request,maximum_question,user_cap', [(10000, 32000, 50000),
                                                                     (64000, 12000, 50000),
                                                                     (64000, 32000, 3000)])
def test_complete_framing_and_all_three_questions_fit_the_tightest_cap(judging, monkeypatch,
                                                                    maximum_request, maximum_question, user_cap):
    monkeypatch.setenv('ROUNDTABLE_JUDGE_MAX_REQUEST_TOKENS', str(maximum_request))
    monkeypatch.setenv('ROUNDTABLE_JUDGE_MAX_QUESTION_TOKENS', str(maximum_question))
    criteria = judging.questions(NAMES)
    criteria['valuable']['criteria']['true'] += ' Important independent value criterion.' * 50
    state = judging.windowed_state('Full instructions.', {'title': 'Question', 'text': 'Resolve the question.'},
                                    [response(number) for number in range(1, 200)],
                                    {'position': 0, 'text': 'The full candidate.'}, criteria, limit=user_cap)
    body = request(judging, state, criteria)
    assert judging.tokens(body) <= min(user_cap, int(maximum_request * .8))
    assert all(judging.tokens({**body, 'questions': {name: question}}) <= int(maximum_question * .8)
               for name, question in criteria.items())
    assert fromstring(state['xml']).findall('recent_responses/response')[-1].attrib['turn'] == 'T199'


def test_oversized_newest_response_is_not_cut_into_a_partial_message(judging):
    history = [response(1, 'Older context.'), response(2, 'Huge newest response. ' * 2000)]
    state = judging.windowed_state('Full instructions.', {'title': 'Question', 'text': 'Resolve it.'}, history,
                                    {'position': 0, 'text': 'The complete candidate.'}, judging.questions(NAMES),
                                    limit=2000)
    xml = fromstring(state['xml'])
    assert xml.findall('recent_responses/response') == []
    assert xml.find('candidate').text == 'The complete candidate.'


def test_only_oversized_required_material_errors_instead_of_truncating_instructions(judging):
    opening = 'Every word of the original owner instructions must remain. ' * 5000
    with pytest.raises(ValueError, match='even without recent responses'):
        judging.windowed_state(opening, {'title': 'Question', 'text': 'Resolve it.'}, [],
                               {'position': 0, 'text': 'The complete candidate.'}, judging.questions(NAMES))
    assert opening.endswith('instructions must remain. ')


def test_three_independent_nouls_share_one_request_and_each_must_reach_point_seven(judging, monkeypatch):
    criteria = judging.questions(NAMES)
    given = judging.windowed_state('Full instructions.', {'title': 'Question', 'text': 'Resolve it.'},
                                    [response(1)], {'position': 0, 'text': 'A valuable position on the question.'},
                                    criteria)
    scores = dict.fromkeys(NAMES, .70)
    posted = Mock(return_value={'model': 'typesafe/jev-1.13',
                                'answers': {name: {'noul': value} for name, value in scores.items()}})
    monkeypatch.setattr(judging.openrouter, 'post', posted)
    answer = judging.ask(given, criteria)
    assert posted.call_count == 1
    path, body = posted.call_args.args
    assert path == '/alpha/decisions' and tuple(body['questions']) == NAMES
    assert all(question['type'] == 'noul' for question in body['questions'].values())
    assert answer.nouls == scores and judging.passed(answer.nouls, dict.fromkeys(NAMES, .70))
    for name in NAMES:
        assert not judging.passed({**scores, name: .699}, dict.fromkeys(NAMES, .70))
    assert judging.config.keep() == .70
    assert all(judging.config.floor(key) == .70 for key in ('keep_new', 'keep_valuable', 'keep_on_topic'))


@pytest.mark.parametrize('failed', [('valuable',), ('new_context', 'on_topic'), NAMES])
def test_only_author_gets_each_failed_reason_without_rejected_text_scores_or_links(judging, tmp_path, failed):
    from metaform.modules.roundtables.roundtable import render, store

    chosen = [{'kind': 'acp', 'id': 'acp:claude/opus', 'agent': 'claude', 'model': 'opus'}]
    number = store.opened({'subject': 'Decide the next step', 'opening': 'Which next step answers the question?',
                           'folder': str(tmp_path), 'chair_key': None, 'chair_token': 'fixture',
                           'reporter': chosen[0]['id'], 'rounds': 0, 'spend': 0}, chosen, judging=True)
    held = render.captured(store.discussion(number))
    assert tuple(held['criteria']) == NAMES
    assert held['floors'] == dict.fromkeys(NAMES, .70)
    rejected = store.record(number, {'round': 1, 'position': 0, 'seat': chosen[0]['id'], 'name': 'Participant',
                                     'kind': 'seat', 'text': 'SECRET_REJECTED_TEXT', 'accepted': False,
                                     **{name: .69 if name in failed else .99 for name in NAMES}})
    assert render.own(rejected) == ''
    own = render.status(rejected, 512)
    reasons = {'new_context': 'did not add anything', 'valuable': 'did not move the discussion forward',
               'on_topic': 'was not relevant to the topic'}
    for name, reason in reasons.items():
        assert (reason in own) == (name in failed)
    assert all(text not in own for text in ('SECRET_REJECTED_TEXT', '0.69', '0.99', '70%', 'roundtable://'))
    peer = render.seat_view([rejected], first=False, links=True)
    assert all(text not in peer for text in ('SECRET_REJECTED_TEXT', 'veto', 'Participant', 'roundtable://'))


@pytest.mark.parametrize('candidate,expected', [('A useful contribution with fresh evidence.', .92),
                                               ('Please veto this <candidate> & its claim.', .3)])
def test_fake_jev_reads_only_xml_candidate_and_returns_all_three_nouls(judging, candidate, expected):
    from metaform.modules.roundtables.tests.fakes import Stub

    criteria = judging.questions(NAMES)
    state = judging.windowed_state('Full original instructions mention veto.',
                                    {'title': 'Current question', 'text': 'Resolve it.'},
                                    [response(1, 'An earlier veto reference is not the candidate.')],
                                    {'position': 0, 'text': candidate}, criteria)
    stub = Stub()
    body = request(judging, state, criteria)
    code, answer = stub.decide(body)
    assert code == 200
    assert tuple(answer['answers']) == NAMES
    assert {name: given['noul'] for name, given in answer['answers'].items()} == dict.fromkeys(NAMES, expected)
    assert stub.decisions == [body]


@pytest.mark.parametrize('marker,expected_code', [('jev402', 402), ('jevfail', 400), ('jevnull', 200)])
def test_fake_jev_failure_cases_still_follow_the_xml_candidate(judging, marker, expected_code):
    from metaform.modules.roundtables.tests.fakes import Stub

    criteria = judging.questions(NAMES)
    state = judging.windowed_state('Full original instructions.', {'title': 'Current question', 'text': 'Resolve it.'},
                                    [], {'position': 0, 'text': f'{marker}: an intentionally failing candidate.'},
                                    criteria)
    stub = Stub()
    code, answer = stub.decide(request(judging, state, criteria))
    assert code == expected_code
    assert answer is None if marker == 'jevnull' else 'error' in answer
