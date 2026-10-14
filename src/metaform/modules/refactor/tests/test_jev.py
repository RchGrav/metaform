"""Bulk classification retains every alternative and keeps uncertain decisions visible."""
import copy
import io
import json

import pytest

from metaform.modules.refactor import jev

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('BASE-063')]

CANDIDATES = {
    'session': {'provider': 'code.controller.session', 'ef': 'Receives session updates.'},
    'memory': {'provider': 'code.management.memory', 'ef': ['Stores memories.', 'Recalls memories.']},
}


def response(payload, choices=None):
    choices = choices or {}
    answers = {}
    for key, question in payload['questions'].items():
        choice, confidence = choices.get(key, ('session', .9))
        answers[key] = {'type': 'choice', 'choice': choice, 'confidence': confidence,
                        'probabilities': {candidate: float(candidate == choice)
                                          for candidate in question['criteria']}}
    return {'answers': answers, 'usage': {'cost': .001}}


def test_category_criteria_preserves_encounter_functions():
    candidates = copy.deepcopy(CANDIDATES)
    candidates['session']['ef'] = 'Receives SESSION updates.\n  Keeps spacing.'
    assert jev.category_criteria(candidates) == {
        'session': 'Category: Session Controller Program Code\nReceives SESSION updates.\n  Keeps spacing.',
        'memory': 'Category: Memory Management Program Code\nStores memories.\nRecalls memories.',
    }


def test_one_choice_per_item_and_uncertain_answers(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-only')
    calls = []
    choices = {'symbol_A': ('session', .9), 'symbol_B': ('memory', .82),
               'symbol_C': ('memory', .95), 'symbol_D': ('session', .5)}

    def send(request, timeout):
        payload = json.loads(request.data)
        calls.append(payload)
        return io.BytesIO(json.dumps(response(payload, choices)).encode())

    monkeypatch.setattr(jev.urllib.request, 'urlopen', send)
    items = {key: {'symbol': key} for key in choices}
    candidates = copy.deepcopy(CANDIDATES)
    before = copy.deepcopy((items, candidates))
    result = jev.associate(items, candidates)
    decisions = result['decisions']
    assert [d['item_id'] for d in decisions] == list(items)
    assert [d['status'] for d in decisions] == ['matched', 'review', 'matched', 'review']
    assert [d['candidate_id'] for d in decisions] == ['session', 'memory', 'memory', 'session']
    assert [d['choice'] for d in decisions] == ['session', 'memory', 'memory', 'session']
    assert decisions[0]['probabilities'] == {'session': 1., 'memory': 0.}
    assert len(calls) == 1
    assert set(calls[0]['questions']) == set(items)
    assert result['usage']['cost'] == .001
    assert (items, candidates) == before
    assert 'items.symbol_A' in calls[0]['questions']['symbol_A']['instructions']
    assert all(q['criteria'] == jev.category_criteria(candidates) for q in calls[0]['questions'].values())


def test_split_items_retains_full_alternatives_and_bounds(monkeypatch):
    items = {'A': {'code': 'é' * 1000}, 'B': {'code': 'b' * 2000}}
    singles = [jev.prepare_batches({key: value}, CANDIDATES)[0] for key, value in items.items()]
    state_limit = max(len(jev.encode(batch)) for batch in singles) + 10
    monkeypatch.setattr(jev, 'STATE_QUESTION_BYTES', state_limit)
    monkeypatch.setattr(jev, 'REQUEST_BYTES', state_limit * 2)
    batches = jev.prepare_batches(items, CANDIDATES)
    assert len(batches) == 2
    assert [key for batch in batches for key in batch['questions']] == list(items)
    for batch in batches:
        assert len(jev.encode(batch)) <= state_limit * 2
        assert max(len(jev.encode({**batch, 'questions': {key: question}}))
                   for key, question in batch['questions'].items()) <= state_limit
        assert all(q['criteria'] == jev.category_criteria(CANDIDATES) for q in batch['questions'].values())


def test_oversized_item_fails_before_sending(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-only')
    monkeypatch.setattr(jev.urllib.request, 'urlopen', lambda *a, **k: pytest.fail('network called'))
    with pytest.raises(ValueError):
        jev.associate({'small': {'code': 'ok'}, 'large': {'code': 'x' * 64000}}, CANDIDATES)


def test_oversized_full_criteria_fails_before_sending(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-only')
    monkeypatch.setattr(jev.urllib.request, 'urlopen', lambda *a, **k: pytest.fail('network called'))
    candidates = {'session': {'provider': 'code.controller.session', 'ef': 'x' * 64000}}
    with pytest.raises(ValueError):
        jev.associate({'item': {'code': 'code'}}, candidates)


def test_255_candidates_cap():
    candidates = {f'c{i}': {'provider': f'code.c{i}', 'ef': 'Handles input.'} for i in range(255)}
    criteria = jev.category_criteria(candidates)
    assert len(criteria) == 255
    assert set(criteria) == set(candidates)
    candidates['overflow'] = {'provider': 'code.extra', 'ef': 'Handles more input.'}
    with pytest.raises(ValueError):
        jev.category_criteria(candidates)


@pytest.mark.parametrize('change', [
    lambda r: r['answers'].clear(),
    lambda r: r['answers'].update(extra=r['answers']['item']),
    lambda r: r['answers']['item'].update(confidence=float('nan')),
    lambda r: r['answers']['item'].update(confidence=True),
    lambda r: r['answers']['item'].update(choice='invented'),
    lambda r: r['answers']['item'].update(type='score'),
    lambda r: r['answers']['item'].pop('probabilities'),
    lambda r: r['answers']['item']['probabilities'].pop('memory'),
    lambda r: r['answers']['item']['probabilities'].update(session=float('inf')),
])
def test_malformed_answer_is_never_accepted(monkeypatch, change):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-only')

    def send(request, timeout):
        result = response(json.loads(request.data))
        change(result)
        return io.BytesIO(json.dumps(result).encode())

    monkeypatch.setattr(jev.urllib.request, 'urlopen', send)
    with pytest.raises(ValueError):
        jev.associate({'item': {'code': 'code'}}, CANDIDATES)


@pytest.mark.parametrize('threshold', [-1, 1.1, float('nan'), True])
def test_invalid_threshold(threshold):
    with pytest.raises(ValueError, match='threshold'):
        jev.associate({'item': {'code': 'code'}}, CANDIDATES, threshold=threshold)


@pytest.mark.parametrize('items', [[], 'text', None, {}, {1: {}}, {'bad.id': {}}, {'id': 'text'},
                                   {'id': {'code': float('inf')}}])
def test_invalid_records_do_not_send(monkeypatch, items):
    monkeypatch.setattr(jev.urllib.request, 'urlopen', lambda *a, **k: pytest.fail('network called'))
    with pytest.raises(ValueError):
        jev.associate(items, CANDIDATES)


@pytest.mark.parametrize('candidates', [
    {'bad': {'provider': 'code.session'}},
    {'bad': {'provider': 'code.session', 'ef': []}},
    {'bad': {'provider': 'code.session', 'ef': ['valid', 5]}},
])
def test_invalid_candidates_do_not_send(monkeypatch, candidates):
    monkeypatch.setattr(jev.urllib.request, 'urlopen', lambda *a, **k: pytest.fail('network called'))
    with pytest.raises(ValueError):
        jev.associate({'item': {'code': 'code'}}, candidates)


def test_missing_key_does_not_send(monkeypatch):
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    monkeypatch.setattr(jev.urllib.request, 'urlopen', lambda *a, **k: pytest.fail('network called'))
    with pytest.raises(ValueError, match='OPENROUTER_API_KEY'):
        jev.associate({'item': {'code': 'code'}}, CANDIDATES)


def test_http_error_preserves_status_and_body(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'test-only')

    def fail(*args, **kwargs):
        raise jev.urllib.error.HTTPError(jev.URL, 429, 'rate limited', {}, io.BytesIO(b'quota exceeded'))

    monkeypatch.setattr(jev.urllib.request, 'urlopen', fail)
    with pytest.raises(RuntimeError, match='Jev HTTP 429: quota exceeded'):
        jev.associate({'item': {'code': 'code'}}, CANDIDATES)
