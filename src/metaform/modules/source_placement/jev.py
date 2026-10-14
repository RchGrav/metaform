"""Optional Jev association pass over explicitly supplied evidence, without map writes.

Nothing is sent unless the person has turned on the person-only setting `jev`: a key in the environment is not
consent. Requests go through `metaform.jev`, so `jev_endpoint`, `jev_model`, the endpoint's key and `jev_decisions`
(as the module decision point `source_placement.associate`) govern them as they govern every other Jev caller.
"""
from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from typing import Any, cast

from metaform import jev as shared
from metaform import settings

DECISION = 'source_placement.associate'
OFF = 'jev is off; only the person turns it on.'
# Conservative UTF-8 byte budgets, not token estimates. Reserve space below the
# provider's 32k state+question and 64k request limits for framing/token overhead.
STATE_QUESTION_BYTES = 30_000
REQUEST_BYTES = 62_000


def configured(folder: Path) -> shared.Config:
    """The folder's Jev configuration; ValueError, before anything is sent, when the person has not turned jev on or
    Jev is unavailable for this decision point."""
    if not settings.value('jev', folder):
        raise ValueError(OFF)
    cfg = shared.config(folder, DECISION)
    if cfg is None:
        raise ValueError(f'Jev is unavailable: {DECISION} is left out of jev_decisions, the key jev_endpoint names is '
                         'not in the environment, jsonschema is missing, or a request failed in the last minute.')
    return cfg


def eligible_provider(provider: str) -> bool:
    """The artifact root and external components are not implementation categories."""
    return provider != 'code' and provider.split('.')[0] not in {'upstream', 'downstream'}


def encode(value: object) -> bytes:
    """Use the exact wire representation when checking batch sizes."""
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')


def _named(value: object, name: str) -> dict[str, object]:
    records = _object(value, name)
    if not records:
        raise ValueError(f'{name} must contain named records.')
    if any(not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', key)
           for key in cast(dict[object, object], records)):
        raise ValueError(f'{name} IDs must use letters, numbers, underscores or hyphens.')
    for key, record in records.items():
        _object(record, f'{name}.{key}')
    try:
        encode(records)  # reject non-JSON evidence and non-finite numbers before sending anything
    except (ValueError, TypeError) as error:
        raise ValueError(f'{name} must contain finite JSON data.') from error
    return records


def category_criteria(candidates: object) -> dict[str, str]:
    """Present provider namespaces in reading order, followed by their verbatim EFs."""
    records = _named(candidates, 'candidates')
    if len(records) > 255:
        raise ValueError('Supply at most 255 categories.')
    criteria: dict[str, str] = {}
    for key, value in records.items():
        record = _object(value, f'candidates.{key}')
        provider = record.get('provider')
        ef = record.get('ef')
        if not isinstance(provider, str) or not provider or any(not part for part in provider.split('.')):
            raise ValueError(f'candidates.{key}.provider must be a dotted namespace.')
        descriptions = [ef] if isinstance(ef, str) else ef
        if (not isinstance(descriptions, list) or not descriptions
                or any(not isinstance(text, str) or not text.strip() for text in cast(list[object], descriptions))):
            raise ValueError(f'candidates.{key}.ef must be nonempty text or a list of EF texts.')
        words = ['Program Code' if part == 'code' else part.replace('_', ' ').title()
                 for part in reversed(provider.split('.'))]
        criteria[key] = 'Category: ' + ' '.join(words) + '\n' + '\n'.join(dict.fromkeys(cast(list[str], descriptions)))
    return criteria


def _question(item: str, criteria: dict[str, str]) -> dict[str, object]:
    return {'type': 'choice', 'instructions': f'Which category does the code in `items.{item}` belong to?',
            'criteria': criteria}


def _payload(items: dict[str, object], questions: dict[str, object]) -> dict[str, Any]:
    # The model is added when sent; REQUEST_BYTES keeps room for it.
    return {'state': {'items': items}, 'questions': questions}


def _fits(payload: dict[str, Any]) -> bool:
    questions: dict[str, object] = payload['questions']
    return len(encode(payload)) <= REQUEST_BYTES and all(
        len(encode({**payload, 'questions': {key: question}})) <= STATE_QUESTION_BYTES
        for key, question in questions.items())


def prepare_batches(items: object, candidates: object) -> list[dict[str, Any]]:
    """Ask once per item with all categories, splitting only the items to fit the budget."""
    items = _named(items, 'items')
    criteria = category_criteria(candidates)
    batches: list[dict[str, Any]] = []
    batch_items: dict[str, object] = {}
    questions: dict[str, object] = {}
    for item_id, item in items.items():
        question = _question(item_id, criteria)
        if not _fits(_payload({item_id: item}, {item_id: question})):
            raise ValueError(f'Item {item_id} with the full category list is too large for one Jev request.')
        trial = _payload({**batch_items, item_id: item}, {**questions, item_id: question})
        if questions and not _fits(trial):
            batches.append(_payload(batch_items, questions))
            batch_items, questions = {}, {}
        batch_items[item_id] = item
        questions[item_id] = question
    if questions:
        batches.append(_payload(batch_items, questions))
    return batches


def _unit(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number between 0 and 1.')
    if not 0 <= value <= 1:
        raise ValueError(f'{name} must be a finite number between 0 and 1.')
    return float(value)


def send(cfg: shared.Config, payload: dict[str, Any]) -> dict[str, Any]:
    """Send a typed request through the shared Jev transport, with the configured model."""
    try:
        result: object = shared.post(cfg, {**payload, 'model': cfg.model})
    except OSError as error:
        raise RuntimeError(f'Jev request failed: {error}') from error
    return _object(result, 'Jev response')


def _object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f'{name} must be an object.')  # noqa: TRY004 - invalid remote/input data
    return cast(dict[str, Any], value)


def associate(items: object, candidates: object, cfg: shared.Config, *,
              threshold: float = .90) -> dict[str, object]:
    """Select one provider category per code item, with confidence and full probabilities.

    Calling this function sends the supplied records to the endpoint `cfg` names; only `configured` gives one.
    The caller owns selection of that evidence.
    """
    items = _named(items, 'items')
    candidates = _named(candidates, 'candidates')
    threshold = _unit(threshold, 'threshold')
    batches = prepare_batches(items, candidates)
    criteria = category_criteria(candidates)
    decisions: list[dict[str, object]] = []
    reports: list[dict[str, object]] = []
    totals: dict[str, float] = {}
    started = time.perf_counter()
    for payload in batches:
        batch_started = time.perf_counter()
        result = send(cfg, payload)
        answers = _object(result.get('answers'), 'Jev answers')
        if set(answers) != set(payload['questions']):
            raise ValueError('Jev answers must contain exactly the requested question IDs.')
        for question_id in payload['questions']:
            answer = _object(answers[question_id], f'Jev answer {question_id}')
            if answer.get('type') != 'choice':
                raise ValueError(f'Jev answer {question_id} must be a choice.')
            choice: Any = answer.get('choice')
            if not isinstance(choice, str) or choice not in criteria:
                raise ValueError(f'Jev answer {question_id} has an unknown choice.')
            confidence = _unit(answer.get('confidence'), f'{question_id} confidence')
            probabilities = _object(answer.get('probabilities'), f'{question_id} probabilities')
            if set(probabilities) != set(criteria):
                raise ValueError(f'Jev answer {question_id} has invalid probabilities.')
            for probability in probabilities.values():
                _unit(probability, f'{question_id} probability')
            status = 'review' if confidence < threshold else 'matched'
            decisions.append({'item_id': question_id, 'candidate_id': choice,
                              'status': status, 'choice': choice, 'confidence': confidence,
                              'probabilities': probabilities})
        usage = _object(result.get('usage', {}), 'Jev usage')
        for name, amount in usage.items():
            if isinstance(amount, (int, float)) and not isinstance(amount, bool) and math.isfinite(amount):
                totals[name] = totals.get(name, 0) + amount
        reports.append({'questions': len(payload['questions']), 'usage': usage,
                        'elapsed_seconds': time.perf_counter() - batch_started})
    return {'model': cfg.model, 'threshold': threshold, 'decisions': decisions, 'batches': reports,
            'usage': totals, 'elapsed_seconds': time.perf_counter() - started}
