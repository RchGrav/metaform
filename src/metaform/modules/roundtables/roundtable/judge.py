"""Jev's judgments: of each seat submission, and at a table with topics of each round of the open topic.

Jev is TypeSafe's Jev, asked through OpenRouter's decisions route with OPENROUTER_API_KEY, at the fixed version the
table captured from `jev_model` when it opened, so the bars stay tied to one model; an alias (latest, preview,
router) is refused with no call. Its state names every field and never relies on a list position.

Before Jev is asked, the code takes off a `T###:` label a seat wrote at the head of its reply (the record keeps the
original) and compares what is left, normalised, with every submission on the topic, kept or vetoed: an exact or
near-exact match is vetoed as a repeat with no call, since Jev does not count.

At a table with topics a submission is judged on two nouls, `new_context` and `on_topic`, against the open topic and
every turn kept on it, never a window of them, each seat under a neutral label (S1 and on) so that Jev judges what
was said and not who said it. After each round a separate request on the same state, with the round just ended as
`latest_round`, asks `round_added` and `covered`. A table without topics is judged as it always was: four nouls
against the opening and the discussion as it entered, each turn under its seat's name, the oldest entries dropped
over 24,000 tokens and the drop logged.

Every call comes back as an `Asked`, paid or failed: the request exactly as sent, the raw answer, the model that
answered, the nouls read, the usage and cost, the latency and attempts, and the error when there was one. The runner
writes it as a row of `judgments` in the same transaction as the decision it causes. Jev failing is never a fallback:
the table holds and says why, since nothing enters unjudged. One judgment's attempts and the waits between them share
one deadline, `jev_wait`; a 402 holds the table until a probe finds credits again, never ending it.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import logging
import math
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, cast

from . import config, openrouter
from .prompts import said
from .render import turn, who
from .store import ENOUGH, NOULS

log = logging.getLogger(__name__)

STATE_TOKENS = 24_000  # past this the oldest entries leave a table without topics' state, inside Jev's 32,000
CHARS_PER_TOKEN = 3  # an estimate on the safe side
NEAR = 0.95  # how alike two submissions' words are, at least, for the later to be a repeat of the earlier
SUFFICIENCY = ENOUGH  # the two nouls of a round
MODEL_VERSION = re.compile(r'(?:typesafe/)?jev-\d+\.\d+(?:\.\d+)?(?:-\d{8})?')  # a fixed version, never an alias
LABEL = re.compile(r'^\s*(?:\*\*)?\s*(T\d+)\s*(?:\*\*)?\s*[:.)\]–—-]\s*(?:\*\*)?\s*', re.IGNORECASE)


def tokens(value: Any) -> int:
    return math.ceil(len(json.dumps(value, ensure_ascii=False)) / CHARS_PER_TOKEN)


# ----------------------------------------------------------------------------------------------- before Jev

def unlabeled(text: str) -> tuple[str, str | None]:
    """A reply without the `T###:` label its seat wrote at its head, and the label; the reply as given when it has
    none."""
    found = LABEL.match(text)
    if found is None:
        return text, None
    return text[found.end():], found.group(1).upper()


def normal(text: str) -> str:
    """A submission as the repeat check compares it: without its label, lower case, words only."""
    return ' '.join(re.findall(r'[^\W_]+', unlabeled(text)[0].casefold()))


def repeat(text: str, rows: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """The earliest seat submission among `rows`, kept or vetoed, that `text` repeats exactly or nearly, compared word
    by word, so a short text differing in one word is never a repeat; None when it repeats none."""
    mine = normal(text).split()
    if not mine:
        return None
    for row in rows:
        if row['kind'] != 'seat' or not row['text']:
            continue
        theirs = normal(str(row['text'])).split()
        if mine == theirs:
            return row
        matcher = difflib.SequenceMatcher(None, mine, theirs, autojunk=False)
        if matcher.real_quick_ratio() >= NEAR and matcher.quick_ratio() >= NEAR and matcher.ratio() >= NEAR:
            return row
    return None


# ----------------------------------------------------------------------------------------------- the request

def questions(names: Sequence[str] = NOULS) -> dict[str, dict[str, Any]]:
    """The nouls by name, each one condition phrased so that true means keep: the four of a table without topics,
    or the two of a submission or of a round at a table with topics."""
    return {name: {'type': 'noul', 'instructions': said(f'jev_{name}'),
                   'criteria': {'true': said(f'jev_{name}_true'), 'false': said(f'jev_{name}_false')}}
            for name in names}


def state(opening: str, entered: Sequence[Mapping[str, Any]], seat: str, text: str) -> dict[str, Any]:
    """A table without topics' state: the opening, the discussion as it entered, and the contribution judged."""
    held = list(entered)
    while True:
        built = {'opening': opening,
                 'discussion': {turn(int(row['number'])): {'seat': who(row), 'text': row['text']} for row in held},
                 'contribution': {'seat': seat, 'text': text}}
        if tokens(built) <= STATE_TOKENS or not held:
            return built
        log.info('Turn %s left Jev\'s state, which was over %s tokens.', held[0]['number'], STATE_TOKENS)
        held = held[1:]


def neutral(row: Mapping[str, Any]) -> str:
    """A turn's author as Jev sees it at a table with topics: a seat by its place, S1 and on, or the chair."""
    return 'chair' if row['kind'] == 'chair' else f'S{int(row["position"]) + 1}'


def topic_state(topic: Mapping[str, Any], entered: Sequence[Mapping[str, Any]],
                contribution: Mapping[str, Any] | None = None, latest_round: int | None = None) -> dict[str, Any]:
    """A table with topics' state: the open topic and every turn kept on it, each with its round and its author's
    neutral label; then the contribution judged, `{position, text}`, or the round just ended."""
    built: dict[str, Any] = {
        'topic': {'title': topic['title'], 'text': topic['text']},
        'discussion': {turn(int(row['number'])): {'round': int(row['round']), 'seat': neutral(row),
                                                  'text': row['text']} for row in entered}}
    if contribution is not None:
        built['contribution'] = {'seat': neutral({'kind': 'seat', **contribution}), 'text': contribution['text']}
    if latest_round is not None:
        built['latest_round'] = latest_round
    return built


def round_state(topic: Mapping[str, Any], entered: Sequence[Mapping[str, Any]], latest_round: int) -> dict[str, Any]:
    """The state a round's sufficiency is judged on: the topic's, the same as a submission's, with the round just
    ended in place of the contribution."""
    return topic_state(topic, entered, latest_round=latest_round)


def sha(criteria: Mapping[str, Any]) -> str:
    """A hash of the questions' text as sent, so a judgment says which wording it answered."""
    return hashlib.sha256(json.dumps(criteria, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def passed(nouls: Mapping[str, float], floors: Mapping[str, float]) -> bool:
    return all(nouls[name] >= floors[name] for name in floors)


# ----------------------------------------------------------------------------------------------- the call

@dataclass
class Asked:
    """One call to Jev, paid or failed, as its judgment row records it."""
    request: dict[str, Any]
    response: Any = None
    model: str | None = None
    nouls: dict[str, float] | None = None
    usage: Any = None
    cost: float = 0.0
    latency_ms: int = 0
    attempts: int = 0
    error: str | None = None
    unpaid: bool = False  # OpenRouter refused the call for want of credits, HTTP 402
    criteria: dict[str, Any] = field(default_factory=dict[str, Any])

    def row(self, kind: str, floors: Mapping[str, float], decision: str | None, **where: Any) -> dict[str, Any]:
        """The judgment row; `where` its topic, round, position and submission."""
        return {**where, 'kind': kind, 'request': self.request, 'prompts_sha': sha(self.criteria),
                'response': self.response, 'model': self.model, 'nouls': self.nouls, 'floors': dict(floors),
                'decision': decision, 'usage': self.usage, 'cost': round(self.cost, 6),
                'state_tokens': tokens(self.request.get('state')), 'latency_ms': self.latency_ms,
                'attempts': self.attempts, 'error': self.error}


def dedup(earlier: Mapping[str, Any], **where: Any) -> dict[str, Any]:
    """The judgment row of a repeat the code caught with no call: what it repeats, and nothing paid."""
    return {**where, 'kind': 'dedup', 'decision': 'repeat', 'response': {'repeat_of': int(earlier['number'])},
            'cost': 0.0, 'attempts': 0}


def ask(given: Mapping[str, Any], criteria: Mapping[str, Any], *, model: str | None = None) -> Asked:
    """Jev's nouls on the state `given` for the questions `criteria`, by name, with everything the call was and
    gave, its answer as it came; its error when Jev did not answer usably, `unpaid` too when OpenRouter is out of
    credits. `model` is the Jev version the table captured at open, else the `jev_model` setting; one that is not a
    fixed version (an alias such as latest, preview or router) is refused with no call."""
    model = str(config.value('jev_model') if model is None else model)
    body: dict[str, Any] = {'model': model, 'state': dict(given), 'questions': dict(criteria)}
    asked = Asked(request=body, criteria=dict(criteria))
    if not MODEL_VERSION.fullmatch(model):
        asked.error = (f'{model!r} is not a fixed Jev version; jev_model must name a version such as '
                       'typesafe/jev-1.13, so the bars stay tied to one model')
        return asked
    trace: dict[str, Any] = {}

    def tried() -> None:
        asked.attempts += 1

    started = time.monotonic()
    reply: Any = None
    try:
        reply = openrouter.post('/alpha/decisions', body, tried=tried, trace=trace,
                                deadline=started + float(config.value('jev_wait')))
    except TimeoutError:
        asked.error = f'Jev gave no answer within {config.value("jev_wait")} seconds'
        return asked
    except openrouter.Unpaid as error:
        asked.error, asked.unpaid = str(error), True
        return asked
    except openrouter.Silent as error:
        asked.error = str(error)
        return asked
    finally:
        asked.latency_ms = round((time.monotonic() - started) * 1000)
        asked.response = trace.get('raw', json.dumps(reply) if reply is not None else None)
    if not isinstance(reply, dict):
        asked.error = f'the answer was not a JSON object: {json.dumps(reply)[:300]}'
        return asked
    answer = cast(dict[str, Any], reply)
    asked.model = str(answer.get('model') or '') or None
    asked.usage = answer.get('usage')
    asked.cost = openrouter.cost(answer)
    try:
        raw = cast(dict[str, Any], answer['answers'])
        found = {name: float(cast(dict[str, Any], raw[name])['noul']) for name in criteria}
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        asked.error = f'the answer was not {len(criteria)} nouls: {error}: {json.dumps(answer)[:300]}'
        return asked
    if not all(0 <= value <= 1 for value in found.values()):
        asked.error = f'a noul fell outside 0 to 1: {found}'
        return asked
    asked.nouls = found
    return asked
