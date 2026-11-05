"""Private, once-only next-topic proposals and one batched set of unordered similarity questions."""
from __future__ import annotations

import json
import time
import uuid
from fractions import Fraction
from itertools import combinations
from typing import Any, cast

from . import config, judge, openrouter, store
from .prompts import said


def proposals(number: int, topic: int) -> list[dict[str, Any]]:
    with store.connect() as db:
        return [cast(dict[str, Any], store.plain(row)) for row in db.execute(
            'SELECT * FROM topic_proposals WHERE discussion=? AND topic=? ORDER BY position', (number, topic))]


def seed(found: dict[str, Any], seated: list[dict[str, Any]]) -> None:
    with store.connect() as db:
        store.fence(db, int(found['number']))
        for row in seated:
            db.execute('INSERT OR IGNORE INTO topic_proposals(discussion,topic,position,state,created) '
                       'VALUES (?,?,?,\'pending\',?)',
                       (found['number'], found['topic'], row['position'], store.stamp()))


def begin_proposal(found: dict[str, Any], position: int) -> str | None:
    """Persist the attempted delivery before calling a model; an interrupted attempt is never replayed."""
    receipt = uuid.uuid4().hex
    with store.connect() as db:
        store.fence(db, int(found['number']))
        took = db.execute('UPDATE topic_proposals SET state=\'sent\',receipt=? WHERE discussion=? AND topic=? '
                          'AND position=? AND state=\'pending\'',
                          (receipt, found['number'], found['topic'], position)).rowcount
    return receipt if took else None


def finish_proposal(found: dict[str, Any], position: int, receipt: str, text: str | None,
                    usage: dict[str, Any]) -> None:
    valid = bool(text and text.strip() and text.strip().casefold() not in ('pass', 'done'))
    with store.connect() as db:
        store.fence(db, int(found['number']))
        store.update(db, 'topic_proposals', {'discussion': found['number'], 'topic': found['topic'],
                                            'position': position, 'receipt': receipt},
                     {'state': 'ready' if valid else 'error', 'text': text if valid else None, 'usage': usage})


def recover(found: dict[str, Any], active: set[int]) -> None:
    """An old in-flight request has no recoverable reply; retain its receipt instead of sending it again."""
    with store.connect() as db:
        store.fence(db, int(found['number']))
        for row in db.execute('SELECT position FROM topic_proposals WHERE discussion=? AND topic=? AND state=\'sent\'',
                              (found['number'], found['topic'])):
            if int(row['position']) not in active:
                db.execute('UPDATE topic_proposals SET state=\'error\' WHERE discussion=? AND topic=? AND position=?',
                           (found['number'], found['topic'], row['position']))


def progress(found: dict[str, Any]) -> dict[str, Any]:
    rows = proposals(int(found['number']), int(found['topic']))
    return {'requested': len(rows), 'completed': sum(row['state'] == 'ready' for row in rows),
            'state': 'collecting' if any(row['state'] in ('pending', 'sent') for row in rows) else 'judging'}


def questions(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Each canonical unordered pair gets one Noul. Its one probability credits both proposals."""
    return {f'p{int(a["position"])}_{int(b["position"])}': {
        'type': 'noul', 'instructions': {'question': said('topic_similarity'),
            'proposal A': f'`proposals.P{int(a["position"]) + 1}`',
            'proposal B': f'`proposals.P{int(b["position"]) + 1}`'},
        'criteria': {'true': said('topic_similarity_true'), 'false': said('topic_similarity_false')}}
        for a, b in combinations(sorted(rows, key=lambda row: int(row['position'])), 2)}


def rank(rows: list[dict[str, Any]], response: Any) -> dict[str, Any]:
    """Average exact input probabilities, with no eligibility cutoff or pre-ranking rounding."""
    ordered = sorted(rows, key=lambda row: int(row['position']))
    totals = {int(row['position']): Fraction(0) for row in ordered}
    counts = dict.fromkeys(totals, 0)
    answer = cast(dict[str, Any], response) if isinstance(response, dict) else {}
    answers = cast(dict[str, Any], answer.get('answers') or {})
    for a, b in combinations(ordered, 2):
        left, right = int(a['position']), int(b['position'])
        try:
            score = Fraction(str(answers[f'p{left}_{right}']['noul']))
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            raise ValueError('Jev did not return every private topic-pair probability.') from None
        if not 0 <= score <= 1:
            raise ValueError('A private topic-pair probability is outside zero to one.')
        for position in (left, right):
            totals[position] += score
            counts[position] += 1
    averages = {position: total / counts[position] if counts[position] else None
                for position, total in totals.items()}
    available = [score for score in averages.values() if score is not None]
    best = max(available) if available else None
    winning = [row for row in ordered if averages[int(row['position'])] == best]
    return {'scores': {str(position): float(score) if score is not None else None
                       for position, score in averages.items()},
            'text': '\n\n'.join(str(row['text']) for row in winning)}


def decide(found: dict[str, Any], current_topic: str) -> dict[str, Any]:
    """One comparison request, or the recorded result; never reissue an ambiguously completed paid call."""
    number, topic = int(found['number']), int(found['topic'])
    rows = proposals(number, topic)
    if not rows or any(row['state'] != 'ready' or not row.get('text') for row in rows):
        raise ValueError('Not every participant returned its private next-topic proposal. '
                         'A previously sent request was not repeated.')
    criteria = questions(rows) if len(rows) > 1 else {}
    body: dict[str, Any] = {'model': str(cast(dict[str, Any], found.get('snapshot') or {}).get('jev_model') or
                                       config.value('jev_model')),
        'state': {'current_topic': current_topic,
                  'proposals': {f'P{int(row["position"]) + 1}': row['text'] for row in rows}},
        'questions': criteria}
    previous: dict[str, Any] | None = None
    with store.connect() as db:
        store.fence(db, number)
        previous = store.plain(db.execute('SELECT * FROM topic_decisions WHERE discussion=? AND topic=?',
                                         (number, topic)).fetchone())
        if previous is not None and previous['state'] == 'ready':
            return previous
        if previous is None:
            store.insert(db, 'topic_decisions', {'discussion': number, 'topic': topic, 'state': 'sent',
                                                'request': body, 'created': store.stamp()})
    reply: Any = None
    error: str | None = None
    trace: dict[str, Any] = {}
    if previous is not None:
        reply = previous.get('response')
        error = previous.get('error') or 'The earlier comparison has no recoverable response and was not resent.'
    elif criteria:
        try:
            if judge.tokens(body) > int(int(config.value('judge_max_request_tokens')) * .8) or any(
                judge.tokens({**body, 'questions': {key: question}}) >
                    int(int(config.value('judge_max_question_tokens')) * .8) for key, question in criteria.items()):
                raise ValueError('The private topic comparisons exceed Jev context limits.')
            reply = openrouter.post('/alpha/decisions', body, retry=False, trace=trace,
                                    deadline=time.monotonic() + float(config.value('jev_wait')))
        except (openrouter.Silent, TimeoutError, ValueError) as failure:
            error = f'{type(failure).__name__}: {failure}'
            with_json = trace.get('raw')
            if isinstance(with_json, str):
                try:
                    reply = json.loads(with_json)
                except ValueError:
                    pass
    try:
        selected = rank(rows, reply)
    except ValueError as failure:
        error = error or str(failure)
        selected = {'scores': None, 'text': None}
    given = cast(dict[str, Any], reply) if isinstance(reply, dict) else {}
    usage = cast(dict[str, Any], given.get('usage') or {})
    cost = openrouter.cost(reply)
    with store.connect() as db:
        store.fence(db, number)
        current = store.plain(db.execute('SELECT * FROM topic_decisions WHERE discussion=? AND topic=?',
                                        (number, topic)).fetchone())
        assert current is not None
        if current['state'] != 'ready':
            store.update(db, 'topic_decisions', {'discussion': number, 'topic': topic},
                         {'state': 'ready' if selected['text'] is not None else 'error', 'response': reply,
                          **selected, 'usage': usage, 'error': error})
            if cost > 0 and previous is None:
                db.execute('UPDATE discussions SET spent=spent+? WHERE number=?', (cost, number))
        result = cast(dict[str, Any], store.plain(db.execute(
            'SELECT * FROM topic_decisions WHERE discussion=? AND topic=?', (number, topic)).fetchone()))
    if result['state'] != 'ready':
        raise ValueError(str(result['error'] or 'The private topic comparison has no recoverable answer.'))
    return result
