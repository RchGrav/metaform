"""Jev, Metaform's optional decision service, CHANGE-ORDER-2026-10-07 item 6 (P185): typed judgements asked of a
decision model, never generated text.

Jev, TypeSafe's System One model, reads a state and answers typed questions about it: a `choice` picks one option, a
`noul` is the probability that a statement is true, a `score` places the state on ordered levels. It answers with
probabilities and a confidence and writes no prose. Sources: the TypeSafe HTTP API, https://docs.typesafe.ai/api.md;
its models, limits and price, https://docs.typesafe.ai/models.md; OpenRouter's decisions route,
https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-questions-and-answers-request.

It is off until the person turns on the setting `jev`, since it sends project text to a third party. The key is read
from the environment, OPENROUTER_API_KEY or TYPESAFE_API_KEY, and never stored. Off, with no key, or on any failure,
every function here returns None and the caller keeps its plain fallback: nothing in Metaform depends on Jev.

The price rewards one state with many questions: input tokens are charged and output tokens are free, so a state is
paid once per request however many questions ride on it, https://docs.typesafe.ai/cookbooks/parallel_questions.md.
`ask` sends every question over one state in one request, split only when the 64,000-token request limit is near, and a
cache in the home keeps each answer under its endpoint, model, state and question, so the same question over the same
state is never paid twice.

The typed decisions, `pick_one`, `pick_some`, `rank`, `yes_no` and `label`, check every answer against a JSON Schema of
the API's answer shapes, give a reason built from the probabilities and the criterion chosen, and, given an Address,
keep the decision there as a numbered item with its title and why, MCP-037, read back at `metaform://<address>#<n>`.
Only a decision a person or an agent acts on is kept: a view such as an order of items is not knowledge, and keeping it
would fill a node with bookkeeping and push its latest item out of its brief. So `choose_agents` keeps each ticket's
agent, model and thinking level at the ticket's Address, `intake_coverage` is kept at the trunk only when a part is
missing, `session_drift` only when it finds drift, and `rank_items`, `triage` and the start order never.

As the change order decided: Jev decides and code owns every threshold; an answer that is not sure goes back to the
caller, which keeps its own behaviour; no answer gates an agent's inference or hides anything from the person.

Jev's documented weak points shape the code, https://docs.typesafe.ai/model-jaggedness/jev-1.13.md: it leans toward the
option that comes first (#choice-option-order), so a single choice is asked in both orders and is sure only when they
agree; it does not count (#math-and-numbers), so counting stays in code; accuracy falls as unrelated state grows
(#large-state-full-of-irrelevant-detail), so MAX_CONTEXT stays well below the 32,000-token limit; and state is
data that can argue for its own answer (#adversarial-content), so no decision ever hides anything from the person;
nor does it count reliably (#counting), so where a judgement is a share of many things, each thing is its own question
and code adds up the answers.

The decision points other modules call, `choose_agents` (with `start_order`), `rank_items`, `triage`,
`intake_coverage` and `session_drift`, each turned off one by one with the setting `jev_decisions`, take what Jev is
asked from `<jev>` in the chassis's `resources/prompts.xml`. A request has a deadline, `within(seconds)` bounds every
request made inside its block together, and a failed request turns Jev off for the process for a minute, so an outage
costs one wait, not one per caller.
"""
from __future__ import annotations

import contextvars
import email.utils
import hashlib
import json
import logging
import math
import os
import re
import sqlite3
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Collection, Generator, Mapping, Sequence
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal, cast

from . import home, prompt_files, settings, sqlite

log = logging.getLogger(__name__)

Kind = Literal['choice', 'noul', 'score']
DecisionKind = Literal['pick_one', 'pick_some', 'rank', 'yes_no', 'label']


@dataclass(frozen=True)
class Endpoint:
    """Where Jev is asked: the route, the environment variable holding its key, and the model asked by default."""
    name: str
    url: str
    key: str
    model: str


# Both routes take the same body, {model, state, questions}, and answer {model, answers, usage}; OpenRouter adds the
# request's cost in US dollars to usage. The default is a dated snapshot, as https://docs.typesafe.ai/models.md#aliases
# asks when thresholds are tuned against a model; OpenRouter answered typesafe/jev-1.13-20260917 by that name on
# 2026-10-12. A person may set an alias such as typesafe/jev-1.13 in jev_model, so the cache records the model that
# answered each name and drops the answers of an earlier one once the name answers as another.
ENDPOINTS = {
    'openrouter': Endpoint('openrouter', 'https://openrouter.ai/api/alpha/decisions', 'OPENROUTER_API_KEY',
                           'typesafe/jev-1.13-20260917'),
    'typesafe': Endpoint('typesafe', 'https://api.typesafe.ai/v1/systemone', 'TYPESAFE_API_KEY', 'jev-1.13.0'),
}
REQUEST_TOKENS = 64_000  # a whole request, https://docs.typesafe.ai/models.md; the state's own limit is MAX_CONTEXT
# The tokens of state, plus its longest question, one request carries. Jev's accuracy falls as a state fills with detail
# the question does not need, so this is well below its limit of 32,000; a larger pile is split across requests, and a
# state that cannot fit is not sent. Settings cleanup 2026-10-15 made it fixed: a larger value only lowers accuracy.
MAX_CONTEXT = 8000
CHARS_PER_TOKEN = 3  # an estimate kept on the safe side of the usual four characters of English to a token
INPUT_PRICE = 0.042 / 1_000_000  # US dollars per input token; output is free, https://docs.typesafe.ai/models.md
TIMEOUT = 10.0  # seconds for each HTTP operation, the TypeSafe SDK's default
DEADLINE = 8.0  # seconds one request may take in all, retries and waits included; within() narrows it
BREAK = 60.0  # seconds Jev stays off for the process after a request fails
# 429 and 529 are retried with exponential backoff as https://docs.typesafe.ai/api.md asks, honouring Retry-After within
# the deadline; 503 is our own addition, since a gateway in front of either route may answer it; anything else fails.
RETRIED = frozenset({429, 503, 529})
BACKOFF = (0.5, 1.5)
CACHE = 'jev.sqlite3'
CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS answers(key TEXT PRIMARY KEY, answer TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS served(requested TEXT PRIMARY KEY, answered TEXT NOT NULL);
"""
# Decisions kept at an Address live in the project's own database beside its counters, given to a database made
# before them on the first decision kept, as the numbers table is, so the project database's layout version holds.
DECISIONS_TABLE = """CREATE TABLE IF NOT EXISTS decisions(
  address    TEXT NOT NULL,
  number     INTEGER NOT NULL,
  decision   TEXT NOT NULL,
  title      TEXT NOT NULL,
  why        TEXT NOT NULL,
  question   TEXT NOT NULL,
  choices    TEXT NOT NULL,
  answer     TEXT NOT NULL,
  confidence REAL NOT NULL,
  sure       INTEGER NOT NULL,
  reason     TEXT NOT NULL,
  model      TEXT NOT NULL,
  cost       REAL NOT NULL,
  created    TEXT NOT NULL,
  identity   TEXT,
  PRIMARY KEY (address, number)
);
"""
DECISIONS_IDENTITY = 'CREATE UNIQUE INDEX IF NOT EXISTS decisions_identity ON decisions(address, identity)'
SAFE_KEY = re.compile(r'[^A-Za-z0-9_]')


# ------------------------------------------------------------------------------------------------ configuration

@dataclass(frozen=True)
class Config:
    """The folder's Jev settings and the key found for them."""
    endpoint: Endpoint
    model: str
    key: str = field(repr=False)
    max_context: int = 8_000
    floor: float = 0.5


_until: contextvars.ContextVar[float | None] = contextvars.ContextVar('metaform_jev_until', default=None)
_down_until = 0.0  # time.monotonic() before which Jev is off for the process, after a failed request
_no_schema_said = False


@contextmanager
def within(seconds: float) -> Generator[None, None, None]:
    """Every Jev request made inside the block, together and retries included, ends within `seconds` of entering it,
    or fails to the fallback: for a caller that waits on the answer, however many requests a decision is split into. A
    block inside another only narrows the time left, never widens it."""
    end = time.monotonic() + seconds
    held = _until.get()
    token = _until.set(end if held is None else min(end, held))
    try:
        yield
    finally:
        _until.reset(token)


def _left() -> float:
    """The seconds the next request may take: DEADLINE, or less when a `within` block ends sooner."""
    until = _until.get()
    return DEADLINE if until is None else min(DEADLINE, until - time.monotonic())


def _schema_checker() -> bool:
    """Whether jsonschema can be imported. It comes with the mcp module, not the chassis, so without it Jev is off,
    said once, and every caller keeps its fallback."""
    global _no_schema_said
    try:
        import jsonschema  # noqa: F401  # pyright: ignore[reportUnusedImport]
    except ImportError:
        if not _no_schema_said:
            log.warning('Jev is off: jsonschema, which checks its answers, is not installed.')
            _no_schema_said = True
        return False
    return True


def config(folder: Path, decision: str | None = None) -> Config | None:
    """The folder's Jev configuration, or None when the setting jev is off, the decision point is left out of
    jev_decisions, the endpoint's key is not in the environment, jsonschema is missing, or a request failed in the
    last minute."""
    if time.monotonic() < _down_until:
        return None
    try:
        if not settings.value('jev', folder):
            return None
        chosen = cast(list[str], settings.value('jev_decisions', folder) or [])
        if decision is not None and chosen and decision not in chosen:
            return None
        endpoint = ENDPOINTS[str(settings.value('jev_endpoint', folder))]
        model = str(settings.value('jev_model', folder) or '').strip() or endpoint.model
        floor = int(settings.value('jev_confidence', folder)) / 100
    except Exception as error:  # noqa: BLE001  a setting that cannot be read leaves Jev off, never the caller broken
        log.warning('Jev is off: its settings could not be read: %s', error)
        return None
    key = os.environ.get(endpoint.key, '').strip()
    if not key or not _schema_checker():
        return None
    return Config(endpoint, model, key, MAX_CONTEXT, floor)


# ------------------------------------------------------------------------------------------------ questions, answers

@dataclass(frozen=True)
class Question:
    """One typed question, as the API takes it: its type, its instructions and its criteria. A choice's criteria map
    each option to what it means; a noul's map `true` and `false`; a score's are its levels, lowest first."""
    type: Kind
    instructions: str
    criteria: Mapping[str, str | None] | Sequence[str] | None = None

    def payload(self) -> dict[str, Any]:
        body: dict[str, Any] = {'type': self.type, 'instructions': self.instructions}
        if isinstance(self.criteria, Mapping):
            body['criteria'] = dict(self.criteria)
        elif self.criteria is not None:
            body['criteria'] = list(self.criteria)
        return body

    def options(self) -> list[str]:
        if isinstance(self.criteria, Mapping):
            return list(self.criteria)
        return [] if self.criteria is None else [str(level) for level in self.criteria]

    def schema(self) -> dict[str, Any]:
        """The JSON Schema its answer meets, from the answer shapes of https://docs.typesafe.ai/api.md."""
        unit = {'type': 'number', 'minimum': 0, 'maximum': 1}
        shape: dict[str, Any] = {'type': 'object', 'properties': {'type': {'const': self.type}}}
        if self.type == 'noul':
            shape['properties']['noul'] = unit
            shape['required'] = ['type', 'noul']
            return shape
        shape['required'] = ['type', self.type, 'probabilities', 'confidence']
        shape['properties']['confidence'] = unit
        shape['properties']['probabilities'] = {'type': 'object', 'additionalProperties': unit}
        if self.type == 'choice':
            shape['properties']['choice'] = {'enum': self.options()}
            shape['properties']['probabilities']['propertyNames'] = {'enum': self.options()}
        else:
            shape['properties']['score'] = {'type': 'number', 'minimum': 0, 'maximum': max(len(self.options()) - 1, 0)}
        return shape


@dataclass(frozen=True)
class Answer:
    """One checked answer: the option chosen, a noul's probability or a score; the probabilities; the confidence,
    Jev's own for a choice or score and, for a noul, how far its probability is from even, scaled to 0 to 1, as
    https://docs.typesafe.ai/confidence.md suggests; the model that answered, its share of the request's cost in US
    dollars, and whether it came from the cache."""
    type: Kind
    value: str | float
    probabilities: dict[str, float]
    confidence: float
    model: str
    cost: float = 0.0
    cached: bool = False

    def plain(self) -> dict[str, Any]:
        return {'type': self.type, 'value': self.value, 'probabilities': self.probabilities,
                'confidence': self.confidence, 'model': self.model}

    @classmethod
    def from_plain(cls, data: Mapping[str, Any]) -> Answer:
        return cls(cast(Kind, data['type']), data['value'], dict(data['probabilities']), float(data['confidence']),
                   str(data['model']), 0.0, True)


def checked(question: Question, raw: Any, model: str, cost: float = 0.0) -> Answer:
    """The answer `raw` to `question`, once it meets the question's JSON Schema; ValueError when not."""
    import jsonschema
    try:
        jsonschema.validate(raw, question.schema())
    except jsonschema.ValidationError as error:
        raise ValueError(f'the answer breaks its schema: {error.message}') from error
    found = cast(dict[str, Any], raw)
    if question.type == 'noul':
        p = float(found['noul'])
        return Answer('noul', p, {'true': p, 'false': 1 - p}, abs(p - 0.5) * 2, model, cost)
    probabilities = {str(key): float(value) for key, value in cast(dict[str, Any], found['probabilities']).items()}
    value = str(found['choice']) if question.type == 'choice' else float(found['score'])
    return Answer(question.type, value, probabilities, float(found['confidence']), model, cost)


# ------------------------------------------------------------------------------------------------ asking

def tokens(value: Any) -> int:
    """An estimate of the tokens `value` takes as JSON, on the safe side."""
    return math.ceil(len(json.dumps(value, ensure_ascii=False)) / CHARS_PER_TOKEN)


def ask(folder: Path, state: Any, questions: Mapping[str, Question], *,
        decision: str | None = None) -> dict[str, Answer] | None:
    """Every question over the one state, answered and checked, keyed as asked; None when Jev is off for the folder
    or the decision point, the state cannot fit, or any request fails. Answers already paid for come from the cache;
    the rest go together, one request for as many questions as fit."""
    found = config(folder, decision)
    return None if found is None or not questions else asked(found, state, questions)


def asked(cfg: Config, state: Any, questions: Mapping[str, Question], *,
          cached_only: bool = False) -> dict[str, Answer] | None:
    """`ask` with the configuration already found; with `cached_only`, None unless every answer is in the cache, so a
    read path never waits on the network."""
    keys = {name: cache_key(cfg, state, question) for name, question in questions.items()}
    answers = recalled(cfg, keys)
    pending = {name: question for name, question in questions.items() if name not in answers}
    if not pending:
        return answers
    if cached_only:
        return None
    held = tokens(state)
    if held + max(tokens(question.payload()) for question in pending.values()) > cfg.max_context:
        log.info('Jev was not asked: the state takes about %s tokens, past MAX_CONTEXT %s.', held, cfg.max_context)
        return None
    for group in _groups(pending, REQUEST_TOKENS - held):
        got = _request(cfg, state, group)
        if got is None:
            return None
        remember(cfg, {keys[name]: answer for name, answer in got.items()})
        answers.update(got)
    return answers


def _groups(questions: Mapping[str, Question], room: int) -> list[dict[str, Question]]:
    """The questions in as few requests as the room left beside the state allows, in the order given."""
    split = _split({name: tokens(question.payload()) for name, question in questions.items()}, room)
    return [{name: questions[name] for name in group} for group in split]


def _split(sizes: Mapping[str, int], room: int) -> list[list[str]]:
    """The keys, in the order given, in as few groups as fit `room` tokens each by their sizes; one too large for the
    room goes alone."""
    groups: list[list[str]] = [[]]
    used = 0
    for key, size in sizes.items():
        if groups[-1] and used + size > room:
            groups.append([])
            used = 0
        groups[-1].append(key)
        used += size
    return groups


def _request(cfg: Config, state: Any, questions: Mapping[str, Question]) -> dict[str, Answer] | None:
    global _down_until
    body = {'model': cfg.model, 'state': state,
            'questions': {name: question.payload() for name, question in questions.items()}}
    if _left() <= 0:  # the caller's time is spent; the endpoint is not at fault, so Jev stays on
        log.info('Jev was not asked: the time the caller allowed is spent.')
        return None
    with _span(cfg) as span:
        try:
            reply = post(cfg, body)
            usage = cast(dict[str, Any], reply.get('usage') or {})
            given = usage.get('cost')
            cost = float(given) if given is not None else int(usage.get('input_tokens') or 0) * INPUT_PRICE
            model = str(reply.get('model') or cfg.model)
            raw = cast(dict[str, Any], reply['answers'])
            answers = {name: checked(question, raw[name], model, cost / len(questions))
                       for name, question in questions.items()}
        except OSError as error:
            _down_until = time.monotonic() + BREAK
            _failed(span, error)
            log.warning('Jev did not answer, and is off for %.0f seconds: %s', BREAK, error)
            return None
        except (ValueError, KeyError, TypeError, ImportError) as error:
            _failed(span, error)
            log.warning('Jev gave no usable answer: %s', error)
            return None
        if span is not None:
            span.set_attribute('gen_ai.response.model', model)
            span.set_attribute('gen_ai.usage.input_tokens', int(usage.get('input_tokens') or 0))
            span.set_attribute('gen_ai.usage.output_tokens', int(usage.get('output_tokens') or 0))
    return answers


def post(cfg: Config, body: Mapping[str, Any]) -> dict[str, Any]:
    """One request to the endpoint and its JSON reply, within the deadline (DEADLINE, or `within`), retried on the
    statuses in RETRIED after Retry-After or the backoff; OSError naming the status and the body when it fails or the
    deadline passes. Tests replace this with a recorded or faked Jev."""
    data = json.dumps(body, ensure_ascii=False).encode()
    headers = {'Authorization': f'Bearer {cfg.key}', 'Content-Type': 'application/json'}
    allowed = _left()
    end = time.monotonic() + allowed
    for backoff in [*BACKOFF, None]:
        left = end - time.monotonic()
        if left <= 0:
            break
        request = urllib.request.Request(cfg.endpoint.url, data=data, headers=headers, method='POST')
        try:
            with urllib.request.urlopen(request, timeout=min(TIMEOUT, left)) as response:
                return cast(dict[str, Any], json.load(response))
        except urllib.error.HTTPError as error:
            said = f'HTTP {error.code} from {cfg.endpoint.name}: {error.read(500).decode(errors="replace")}'
            if error.code not in RETRIED or backoff is None:
                raise OSError(said) from error
            wait = _retry_after(error) or backoff
            if wait >= end - time.monotonic():
                raise OSError(f'{said}; a retry after {wait:.1f} s would pass the {allowed:.1f} s deadline') from error
            time.sleep(wait)
    raise OSError(f'{cfg.endpoint.name} did not answer within {allowed:.1f} s.')


def _retry_after(error: urllib.error.HTTPError) -> float | None:
    """The wait a Retry-After header asks for, in seconds or as an HTTP date, RFC 9110 section 10.2.3; None without
    one."""
    given = error.headers.get('Retry-After') if error.headers else None
    if not given:
        return None
    try:
        return max(float(given), 0.0)
    except ValueError:
        pass
    try:
        return max(email.utils.parsedate_to_datetime(given).timestamp() - time.time(), 0.0)
    except (TypeError, ValueError):
        return None


@contextmanager
def _span(cfg: Config) -> Generator[Any, None, None]:
    """An OpenTelemetry client span for one request when the OpenTelemetry API is installed, named and described as
    the GenAI semantic conventions say, github.com/open-telemetry/semantic-conventions-genai; with no SDK set up the
    API records nothing. None when the API is absent."""
    try:
        from opentelemetry import trace
    except ImportError:
        yield None
        return
    tracer = trace.get_tracer('metaform.jev')
    attributes = {'gen_ai.operation.name': 'decide', 'gen_ai.provider.name': cfg.endpoint.name,
                  'gen_ai.request.model': cfg.model}
    with tracer.start_as_current_span(f'decide {cfg.model}', kind=trace.SpanKind.CLIENT,
                                      attributes=attributes) as span:
        yield span


def _failed(span: Any, error: BaseException) -> None:
    """A failed request's span marked as the GenAI semantic conventions ask of an operation that ended in error: its
    `error.type`, conditionally required, and a status as Recording Errors says,
    https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md."""
    if span is None:
        return
    from opentelemetry.trace import Status, StatusCode
    span.set_attribute('error.type', type(error).__name__)
    span.set_status(Status(StatusCode.ERROR, str(error)))


# ------------------------------------------------------------------------------------------------ the cache

@contextmanager
def _cache(write: bool) -> Generator[sqlite3.Connection, None, None]:
    """One transaction on the answer cache, `<home>/jev.sqlite3`: answers by hash, never the state itself, and the
    model each requested name last answered as. Deleting the file only means paying again."""
    path = home.home() / CACHE
    home.mkdir_private(path.parent)
    sqlite.private(path)
    with sqlite.writer_lock(path) if write else nullcontext():
        db = sqlite.connect(path)
        try:
            db.executescript(CACHE_SCHEMA)
            db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            try:
                yield db
            except BaseException:
                db.execute('ROLLBACK')
                raise
            db.execute('COMMIT')
        finally:
            db.close()


def cache_key(cfg: Config, state: Any, question: Question) -> str:
    """The cache's key for one question over one state. The state is written with its keys sorted, so the same state
    built in another order is the same; the question keeps its options in the order asked, since Jev leans toward the
    first option and the order check asks the same options in both orders."""
    held = json.dumps(state, sort_keys=True, ensure_ascii=False)
    text = json.dumps([cfg.endpoint.name, cfg.model, held, question.payload()], ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()


def _requested(cfg: Config) -> str:
    return f'{cfg.endpoint.name}/{cfg.model}'


def recalled(cfg: Config, keys: Mapping[str, str]) -> dict[str, Answer]:
    """The answers already paid for, by question name, given by the model the requested name answers as now; none
    when the cache cannot be read."""
    if not keys:
        return {}
    try:
        with _cache(write=False) as db:
            marks = ','.join('?' * len(keys))
            rows = dict(db.execute(f'SELECT key, answer FROM answers WHERE key IN ({marks})',
                                   list(keys.values())).fetchall())
            served = db.execute('SELECT answered FROM served WHERE requested=?', (_requested(cfg),)).fetchone()
    except sqlite3.Error as error:
        log.warning('The Jev cache could not be read: %s', error)
        return {}
    found = {name: Answer.from_plain(json.loads(rows[key])) for name, key in keys.items() if key in rows}
    return found if served is None else {name: got for name, got in found.items() if got.model == served[0]}


def remember(cfg: Config, answers: Mapping[str, Answer]) -> None:
    try:
        with _cache(write=True) as db:
            db.executemany('INSERT OR REPLACE INTO answers(key, answer, created) VALUES (?, ?, ?)',
                           [(key, json.dumps(answer.plain()), home.now()) for key, answer in answers.items()])
            if answers:
                db.execute('INSERT OR REPLACE INTO served(requested, answered) VALUES (?, ?)',
                           (_requested(cfg), next(iter(answers.values())).model))
    except sqlite3.Error as error:
        log.warning('The Jev cache could not be written: %s', error)


# ------------------------------------------------------------------------------------------------ typed decisions

@dataclass(frozen=True)
class Decision:
    """One typed decision: what was asked and among what, the answer, its confidence, whether it is sure enough to act
    on (jev_confidence), its reason, the model, its cost in US dollars, whether every answer came from the cache, the
    choices Jev was unsure of, the probability of each choice (a noul's, per item, for the per-item kinds), and the
    item it was kept as, `<address>#<n>`, when it concerns an Address."""
    kind: DecisionKind
    title: str
    why: str
    question: str
    choices: tuple[str, ...]
    answer: Any
    confidence: float
    sure: bool
    reason: str
    model: str
    cost: float
    cached: bool
    unsure: tuple[str, ...] = ()
    probabilities: Mapping[str, float] = field(default_factory=lambda: cast(dict[str, float], {}))
    item: str | None = None


def _summed(answers: Mapping[str, Answer]) -> tuple[str, float, bool]:
    first = next(iter(answers.values()))
    return first.model, sum(answer.cost for answer in answers.values()), all(answer.cached for answer in answers.values())


def _identity(cfg: Config, state: Any, questions: Mapping[str, Question], model: str) -> str:
    """What makes a decision the same decision: its questions over its state, and the model that answered, so an
    alias that moves to a newer snapshot keeps the newer answer as a new item rather than the old one's number."""
    keys = sorted(cache_key(cfg, state, question) for question in questions.values())
    return hashlib.sha256((model + ''.join(keys)).encode()).hexdigest()


def _both(cfg: Config, first: Answer, again: Answer | None) -> tuple[str, float, bool]:
    """A choice asked in both orders: the first order's option, the lower confidence, and whether it is sure, the two
    agreeing and confident enough."""
    confidence = first.confidence if again is None else min(first.confidence, again.confidence)
    agreed = again is None or again.value == first.value
    return str(first.value), confidence, agreed and confidence >= cfg.floor


def _order_said(first: Answer, again: Answer | None) -> str:
    return '' if again is None else \
        f' · reversed order {"agreed" if again.value == first.value else f"chose {again.value}"}'


def _choice_reason(answer: Answer, options: Mapping[str, str | None]) -> str:
    ranked = sorted(answer.probabilities.items(), key=lambda pair: -pair[1])
    meaning = options.get(str(answer.value)) or str(answer.value)
    runner_up = f' · next {ranked[1][0]} p={ranked[1][1]:.2f}' if len(ranked) > 1 else ''
    return f'{answer.value} p={answer.probabilities.get(str(answer.value), 0):.2f} confidence={answer.confidence:.2f}' \
           f'{runner_up} · {meaning}'


def _noul_reason(key: str, answer: Answer, true: str, false: str) -> str:
    p = float(answer.value)
    return f'{key}: p={p:.2f} · {true if p >= 0.5 else false}'


def _one(cfg: Config, question: str, options: Mapping[str, str | None], state: Any, *, title: str, why: str,
         kind: DecisionKind = 'pick_one', check_order: bool = True) -> tuple[Decision, str] | None:
    """One choice among the options, asked twice in one request with the options reversed the second time, since
    Jev leans toward the option that comes first, https://docs.typesafe.ai/model-jaggedness/jev-1.13.md#choice-option-order;
    it is sure only when both agree and both are confident enough."""
    if not options:
        return None
    questions = {'pick': Question('choice', question, dict(options))}
    if check_order and len(options) > 1:
        questions['reversed'] = Question('choice', question, dict(reversed(list(options.items()))))
    answers = asked(cfg, state, questions)
    if answers is None:
        return None
    first, again = answers['pick'], answers.get('reversed')
    chosen, confidence, sure = _both(cfg, first, again)
    model, cost, cached = _summed(answers)
    decision = Decision(kind, title, why, question, tuple(options), chosen, confidence, sure,
                        _choice_reason(first, options) + _order_said(first, again), model, cost, cached,
                        () if sure else (chosen,), first.probabilities)
    return decision, _identity(cfg, state, questions, model)


def _safe_keys(keys: Sequence[str]) -> dict[str, str]:
    """Each key as a name Jev can be pointed at, `items.<name>`: never a list position, which Jev confuses past a few
    items (the jev skill's measurement of 2026-10-06), and unique."""
    safe: dict[str, str] = {}
    taken: set[str] = set()
    for key in keys:
        name = SAFE_KEY.sub('_', key)
        name = name if name[:1].isalpha() else f'k_{name}'
        base, n = name, 2
        while name in taken:
            name, n = f'{base}_{n}', n + 1
        taken.add(name)
        safe[key] = name
    return safe


def _per_item(cfg: Config, state: Mapping[str, Any], place: str, items: Mapping[str, Any],
              question: Callable[[str], str], true: str, false: str,
              cached_only: bool = False) -> tuple[dict[str, Answer], str] | None:
    """One noul per item, every item in the state under its own name at `state[place]`, as many items to a request as
    fit MAX_CONTEXT; the answers by the caller's keys and the identity of the whole decision."""
    safe = _safe_keys(list(items))
    criteria = {'true': true, 'false': false}
    asking = {key: Question('noul', question(f'{place}.{safe[key]}'), criteria) for key in items}
    room = cfg.max_context - tokens({**state, place: {}}) - max((tokens(q.payload()) for q in asking.values()), default=0)
    answers: dict[str, Answer] = {}
    identities: list[str] = []
    for group in _split({key: tokens({safe[key]: value}) for key, value in items.items()}, room):
        sub = {**state, place: {safe[key]: items[key] for key in group}}
        questions = {safe[key]: asking[key] for key in group}
        got = asked(cfg, sub, questions, cached_only=cached_only)
        if got is None:
            return None
        answers.update({key: got[safe[key]] for key in group})
        identities.append(_identity(cfg, sub, questions, _summed(got)[0]))
    return answers, hashlib.sha256(''.join(identities).encode()).hexdigest()


def _nouls(kind: DecisionKind, cfg: Config, question: Callable[[str], str], items: Mapping[str, Any], state: Any,
           *, place: str, true: str, false: str, title: str, why: str,
           cached_only: bool = False) -> tuple[Decision, str] | None:
    """The per-item nouls of a decision, with the yes answers it is sure of as its answer, most likely first."""
    if not items:
        return None
    held = cast(Mapping[str, Any], state) if isinstance(state, Mapping) else {'context': state}
    got = _per_item(cfg, held, place, items, question, true, false, cached_only)
    if got is None:
        return None
    answers, identity = got
    order = sorted(items, key=lambda key: -float(answers[key].value))
    unsure = tuple(key for key in order if answers[key].confidence < cfg.floor)
    model, cost, cached = _summed(answers)
    decision = Decision(kind, title, why, question(f'{place}.<item>'), tuple(items), order,
                        min(answer.confidence for answer in answers.values()), not unsure,
                        '\n'.join(_noul_reason(key, answers[key], true, false) for key in order), model, cost, cached,
                        unsure, {key: float(answers[key].value) for key in order})
    return decision, identity


def pick_one(folder: Path, question: str, options: Mapping[str, str | None], state: Any, *, title: str, why: str,
             address: str | None = None, decision: str | None = None, project: str | None = None,
             check_order: bool = True) -> Decision | None:
    """The one option, of `options` (each mapped to what it means), that answers `question` about `state`; the
    answer is the option's key. Asked in both orders unless `check_order` is off. None when Jev is off or fails."""
    cfg = config(folder, decision)
    got = None if cfg is None else _one(cfg, question, options, state, title=title, why=why, check_order=check_order)
    return None if got is None else keep(folder, got, address, project)


def pick_some(folder: Path, question: Callable[[str], str], options: Mapping[str, Any], state: Any, *, true: str,
              false: str, title: str, why: str, address: str | None = None, decision: str | None = None,
              project: str | None = None) -> Decision | None:
    """The options for which the statement `question(path)` holds, one noul each, since several may: `question` takes
    the option's place in the state, `options.<name>`, and `true` and `false` say what a yes and a no mean. The answer
    lists the options Jev is sure hold; the unsure ones are in `unsure`, and left out."""
    cfg = config(folder, decision)
    got = None if cfg is None else _nouls('pick_some', cfg, question, options, state, place='options', true=true,
                                          false=false, title=title, why=why)
    if got is None:
        return None
    found, identity = got
    yes = [key for key in found.answer if key not in found.unsure and found.probabilities[key] >= 0.5]
    return keep(folder, (replace(found, answer=yes), identity), address, project)


def rank(folder: Path, question: Callable[[str], str], items: Mapping[str, Any], state: Any, *, true: str, false: str,
         title: str, why: str, address: str | None = None, decision: str | None = None,
         project: str | None = None) -> Decision | None:
    """The items in order of how likely the statement `question(path)` holds of each, one noul per item at
    `items.<name>`, as https://docs.typesafe.ai/cookbooks/rerank_typesafe.md ranks. An order is a preference, so it is
    sure even when some items are unsure; those are named in `unsure`."""
    cfg = config(folder, decision)
    got = None if cfg is None else _nouls('rank', cfg, question, items, state, place='items', true=true, false=false,
                                          title=title, why=why)
    return None if got is None else keep(folder, (replace(got[0], sure=True), got[1]), address, project)


def yes_no(folder: Path, question: str, state: Any, *, true: str, false: str, title: str, why: str,
           address: str | None = None, decision: str | None = None, project: str | None = None) -> Decision | None:
    """Whether the statement `question` holds of `state`, True or False, with its confidence."""
    cfg = config(folder, decision)
    if cfg is None:
        return None
    questions = {'holds': Question('noul', question, {'true': true, 'false': false})}
    answers = asked(cfg, state, questions)
    if answers is None:
        return None
    answer = answers['holds']
    model, cost, cached = _summed(answers)
    found = Decision('yes_no', title, why, question, ('true', 'false'), float(answer.value) >= 0.5, answer.confidence,
                     answer.confidence >= cfg.floor, _noul_reason('holds', answer, true, false), model, cost, cached)
    return keep(folder, (found, _identity(cfg, state, questions, model)), address, project)


def label(folder: Path, question: str, labels: Mapping[str, str | None], state: Any, *, title: str, why: str,
          none: str | None = None, address: str | None = None, decision: str | None = None,
          project: str | None = None) -> Decision | None:
    """The one label of `labels` that fits `state`; with `none`, what it means that no label fits, offered as the
    option `none`, whose answer is None, since a choice with no way out picks a wrong label instead."""
    cfg = config(folder, decision)
    options = dict(labels) if none is None else {**labels, 'none': none}
    got = None if cfg is None else _one(cfg, question, options, state, title=title, why=why, kind='label')
    if got is None:
        return None
    found, identity = got
    return keep(folder, (replace(found, answer=None) if none is not None and found.answer == 'none' else found,
                         identity), address, project)


# ------------------------------------------------------------------------------------------------ keeping decisions

def keep(folder: Path, got: tuple[Decision, str], address: str | None, project: str | None = None) -> Decision:
    """The decision, kept as the next numbered item at `address` in the project's database when it concerns one, with
    its title and why, MCP-037. A decision asked again over the same state is the item kept the first time, found by
    its identity in the same transaction that would take its number, so it is neither paid for nor kept twice. Keeping
    it never fails it: a fault is logged and the decision returned unkept."""
    decision, identity = got
    if not address:
        return decision
    from . import changes
    from .context import project_for
    from .data import numbers
    try:
        project_id = project_for(folder, project)
        holder = home.project_folder(project_id) if project_id else None
        if holder is None:
            return decision
        with home.project_db(holder, write=True) as db:
            _decisions_table(db)
            row = db.execute('SELECT number FROM decisions WHERE address=? AND identity=?',
                             (address, identity)).fetchone()
            number = int(row[0]) if row is not None else numbers.take_in(db, address)
            if row is None:
                db.execute('INSERT INTO decisions(address, number, decision, title, why, question, choices, answer, '
                           'confidence, sure, reason, model, cost, created, identity) '
                           'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                           (address, number, decision.kind, decision.title, decision.why, decision.question,
                            json.dumps(list(decision.choices), ensure_ascii=False),
                            json.dumps(decision.answer, ensure_ascii=False), decision.confidence, int(decision.sure),
                            decision.reason, decision.model, decision.cost, home.now(), identity))
        if row is None and project_id:  # a new item at the address: announced when the command ends, as writes are
            changes.note(project_id, tables={TABLE})
    except Exception as error:  # noqa: BLE001  a decision is used whether or not it could be kept
        log.warning('A Jev decision at %s could not be kept: %s', address, error)
        return decision
    return replace(decision, item=numbers.reference(address, number))


def _decisions_table(db: sqlite3.Connection) -> None:
    """The decisions table, given to a project database made before it, and its identity column to one made before
    that column."""
    db.execute(DECISIONS_TABLE)
    if 'identity' not in {str(row[1]) for row in db.execute('PRAGMA table_info(decisions)').fetchall()}:
        db.execute('ALTER TABLE decisions ADD COLUMN identity TEXT')
    db.execute(DECISIONS_IDENTITY)


def item(folder: Path, address: str, number: int, *, project: str | None = None) -> dict[str, Any] | None:
    """The decision kept at `address` under `number`, as an item is read, MCP-037: kind, title, why, body and links;
    None when no decision holds that number there."""
    from .context import project_for
    try:
        project_id = project_for(folder, project)
        holder = home.project_folder(project_id) if project_id else None
        if holder is None:
            return None
        with home.project_db(holder) as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='decisions'").fetchone() is None:
                return None
            db.row_factory = sqlite3.Row
            row = db.execute('SELECT * FROM decisions WHERE address=? AND number=?', (address, number)).fetchone()
    except Exception:  # noqa: BLE001  another holder may have the item; this read's fault hides nothing
        return None
    if row is None:
        return None
    answer = json.loads(row['answer'])
    body = '\n'.join([f"question: {row['question']}",
                      f"choices: {', '.join(json.loads(row['choices']))}",
                      f"answer: {answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)}",
                      f"confidence: {row['confidence']:.2f}{'' if row['sure'] else ' (unsure)'}",
                      f"reason: {row['reason']}",
                      f"model: {row['model']} · cost ${row['cost']:.6f} · {row['created']}"])
    return {'kind': 'decision', 'title': row['title'], 'why': row['why'], 'body': body, 'links': [],
            'decision': row['decision'], 'answer': answer, 'sure': bool(row['sure'])}


TABLE = 'jev.decisions'  # how a change to the decisions kept names their table, as a module's own table is named
ITEM_KINDS = ('decision',)  # the kind of item a decision kept at an address is, so a list of other kinds skips them


def items_at(folder: Path, address: str, before: int | None, limit: int, *,
             project: str | None = None) -> list[dict[str, Any]]:
    """The decisions kept at `address` below `before`, newest first, at most `limit`, as items are listed, MCP-037:
    each one's number, kind, title and why, in one query; empty when none is kept there."""
    from .context import project_for
    try:
        project_id = project_for(folder, project)
        holder = home.project_folder(project_id) if project_id else None
        if holder is None:
            return []
        with home.project_db(holder) as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='decisions'").fetchone() is None:
                return []
            rows = db.execute('SELECT number, title, why FROM decisions WHERE address=? AND number<? '
                              'ORDER BY number DESC LIMIT ?',
                              (address, before if before is not None else 1 << 62, int(limit))).fetchall()
    except Exception:  # noqa: BLE001  as `item` reads: another holder may have the items
        return []
    return [{'number': int(row[0]), 'kind': 'decision', 'title': row[1], 'why': row[2]} for row in rows]


# ------------------------------------------------------------------------------------------------ decision points

def _wording(point: str, part: str, **fills: str) -> str:
    """What Jev is asked at a decision point, from `<jev>` in the chassis's prompts.xml."""
    return prompt_files.chassis(f'jev/{point}/{part}', **fills)


CATEGORIES = ('model', 'thought_level')  # the ACP session config categories an agent's choices are asked in


@dataclass(frozen=True)
class Assignments:
    """What `choose_agents` decided: each ticket's Decision by its id, and, when the start order was asked, its own
    Decision ranking the tickets the person has not placed, most worth starting first."""
    decisions: Mapping[str, Decision]
    order: Decision | None = None


def choose_agents(folder: Path, tickets: Mapping[str, Mapping[str, Any]], agents: Mapping[str, str],
                  options: Mapping[str, Mapping[str, Mapping[str, str | None]]] | None = None, *,
                  unplaced: Collection[str] = (), project: str | None = None) -> Assignments | None:
    """The agent, model and thinking level for each ticket, and the order to start the ones the person has not placed,
    from one paid state: `tickets` each ticket's id to it as plain data (title, task, Address); `agents` each eligible
    agent to what it does well; `options` each agent's choices by ACP category, `model` and `thought_level`, each value
    to what it means, as dispatch's catalog keeps them; `unplaced` the ids of tickets with no board position.

    Every ticket goes under its own name in `tickets` beside the agents and their options, and every question rides
    on that one state: per ticket, the agent in both orders, and each agent's model and thinking level in both orders,
    so the one asked after the agent needs no second request; with the decision point `start_order` on, a noul per
    unplaced ticket. A pile past MAX_CONTEXT is split into as few requests as fit. Each choice is sure only when
    both orders agree and both are confident enough; a model or level that is not sure is None.

    Each ticket's Decision answers {'agent', 'model', 'thought_level'} and is kept at its Address, where the person
    sees why. The order is never kept and orders only the unplaced tickets, so the board order the person set,
    VIEW-042, stays theirs. Fallback when None, or for a ticket whose decision is not sure: the ticket's own agent, or
    dispatch's default by its area, and the options the person set, as today."""
    choosing = config(folder, 'choose_agent') if agents else None
    ordering = config(folder, 'start_order') if unplaced else None
    cfg = choosing or ordering
    if cfg is None or not tickets:
        return None
    offered = {agent: {category: dict(values) for category in CATEGORIES
                       if (values := (options or {}).get(agent, {}).get(category))}
               for agent in agents}
    offered = {agent: each for agent, each in offered.items() if each}
    safe = _safe_keys(list(tickets))
    by_agent = _safe_keys(list(agents))
    first = {'true': _wording('start_order', 'true'), 'false': _wording('start_order', 'false')}

    def asking(ticket: str) -> dict[str, Question]:
        name, path = safe[ticket], f'tickets.{safe[ticket]}'
        questions: dict[str, Question] = {}
        if choosing is not None:
            questions.update(_choice_both(f'{name}__agent', _wording('choose_agent', 'ask', item=path), agents))
            for agent, each in offered.items():
                for category, values in each.items():
                    questions.update(_choice_both(
                        f'{name}__{by_agent[agent]}__{category}',
                        _wording('choose_agent', category, agent=agent, item=path), values))
        if ordering is not None and ticket in unplaced:
            questions[f'{name}__first'] = Question('noul', _wording('start_order', 'ask', item=path), first)
        return questions

    shared: dict[str, Any] = {'agents': dict(agents), 'options': offered} if choosing is not None else {}
    per_ticket = {ticket: asking(ticket) for ticket in tickets}
    longest = max((tokens(q.payload()) for qs in per_ticket.values() for q in qs.values()), default=0)
    room = cfg.max_context - tokens({**shared, 'tickets': {}}) - longest
    answers: dict[str, Answer] = {}
    for group in _split({ticket: tokens({safe[ticket]: dict(tickets[ticket])}) for ticket in tickets}, room):
        state = {**shared, 'tickets': {safe[ticket]: dict(tickets[ticket]) for ticket in group}}
        got = asked(cfg, state, {name: q for ticket in group for name, q in per_ticket[ticket].items()})
        if got is None:
            return None
        answers.update(got)
    decisions: dict[str, Decision] = {}
    if choosing is not None:
        for ticket, record in tickets.items():
            found = _assigned(choosing, ticket, agents, offered, safe[ticket], by_agent, answers)
            own = {name: q for name, q in per_ticket[ticket].items() if not name.endswith('__first')}
            identity = _identity(choosing, {**shared, 'ticket': dict(record)}, own, found.model)
            decisions[ticket] = keep(folder, (found, identity), record.get('address'), project)
    return Assignments(decisions, None if ordering is None else _start_order(ordering, unplaced, tickets, safe,
                                                                             answers, first))


def _choice_both(name: str, question: str, options: Mapping[str, str | None]) -> dict[str, Question]:
    """One choice asked in both orders, `<name>` and `<name>__r`, since Jev leans toward the option that comes first,
    https://docs.typesafe.ai/model-jaggedness/jev-1.13.md#choice-option-order."""
    asked_of = {name: Question('choice', question, dict(options))}
    if len(options) > 1:
        asked_of[f'{name}__r'] = Question('choice', question, dict(reversed(list(options.items()))))
    return asked_of


def _assigned(cfg: Config, ticket: str, agents: Mapping[str, str],
              offered: Mapping[str, Mapping[str, Mapping[str, str | None]]], name: str, by_agent: Mapping[str, str],
              answers: Mapping[str, Answer]) -> Decision:
    """One ticket's agent, and that agent's model and thinking level, from the answers of `choose_agents`."""
    first, again = answers[f'{name}__agent'], answers.get(f'{name}__agent__r')
    agent, confidence, sure = _both(cfg, first, again)
    answer: dict[str, str | None] = {'agent': agent, 'model': None, 'thought_level': None}
    reason = [_choice_reason(first, agents) + _order_said(first, again)]
    used = [first, *([again] if again else [])]
    for category, values in offered.get(agent, {}).items():
        key = f'{name}__{by_agent[agent]}__{category}'
        picked, again_picked = answers[key], answers.get(f'{key}__r')
        value, _, picked_sure = _both(cfg, picked, again_picked)
        answer[category] = value if picked_sure else None
        reason.append(f'{category} {_choice_reason(picked, values)}{_order_said(picked, again_picked)}')
        used += [picked, *([again_picked] if again_picked else [])]
    model, cost, cached = _summed({str(n): each for n, each in enumerate(used)})
    return Decision('pick_one', _wording('choose_agent', 'title', ticket=ticket), _wording('choose_agent', 'why'),
                    _wording('choose_agent', 'ask', item=f'tickets.{name}'), tuple(agents), answer, confidence, sure,
                    '\n'.join(reason), model, cost, cached, () if sure else (agent,), first.probabilities)


def _start_order(cfg: Config, unplaced: Collection[str], tickets: Mapping[str, Any], safe: Mapping[str, str],
                 answers: Mapping[str, Answer], meaning: Mapping[str, str]) -> Decision:
    """The unplaced tickets, most worth starting first; an order is a preference, so it is sure even when some
    tickets' answers are not, and those are named in `unsure`."""
    placed = [ticket for ticket in tickets if ticket in unplaced]
    got = {ticket: answers[f'{safe[ticket]}__first'] for ticket in placed}
    order = sorted(placed, key=lambda ticket: -float(got[ticket].value))
    model, cost, cached = _summed(got)
    return Decision('rank', _wording('start_order', 'title'), _wording('start_order', 'why'),
                    _wording('start_order', 'ask', item='tickets.<item>'), tuple(placed), order,
                    min(answer.confidence for answer in got.values()), True,
                    '\n'.join(_noul_reason(ticket, got[ticket], meaning['true'], meaning['false']) for ticket in order),
                    model, cost, cached, tuple(ticket for ticket in order if got[ticket].confidence < cfg.floor),
                    {ticket: float(got[ticket].value) for ticket in order})


def choose_agent(folder: Path, ticket: Mapping[str, Any], agents: Mapping[str, str],
                 options: Mapping[str, Mapping[str, Mapping[str, str | None]]] | None = None, *,
                 project: str | None = None) -> Decision | None:
    """`choose_agents` for one ticket, `ticket` holding its id; its Decision, or None."""
    ticket_id = str(ticket.get('id') or 'ticket')
    got = choose_agents(folder, {ticket_id: ticket}, agents, options, project=project)
    return None if got is None else got.decisions.get(ticket_id)


def rank_items(folder: Path, address: str, items: Mapping[str, str], node: Any, *,
               cached_only: bool = False) -> Decision | None:
    """A node's items in the order an agent at the node needs them, for its 2 KB brief: `items` each item's reference,
    `<address>#<n>`, to its title and why; `node` the node as plain data (Address, OP, EF, status). The answer is the
    references, most needed first. Never kept: an order is a view, and the cache already keeps it from being paid
    for twice. Asked when an item is written at the node, so the brief, a read path, asks with `cached_only` and never
    waits on the network.

    Fallback when None: the brief's own order, newest first."""
    def question(path: str) -> str:
        return _wording('rank_items', 'ask', item=path)
    cfg = config(folder, 'rank_items')
    got = None if cfg is None else _nouls('rank', cfg, question, items, {'node': node}, place='items',
                                          true=_wording('rank_items', 'true'), false=_wording('rank_items', 'false'),
                                          title=_wording('rank_items', 'title', address=address),
                                          why=_wording('rank_items', 'why'), cached_only=cached_only)
    return None if got is None else replace(got[0], sure=True)


def triage(folder: Path, messages: Mapping[str, str], *, questions: Collection[str] = ()) -> Decision | None:
    """Which messages or signals need the person and which an agent may answer: `messages` each one's id or reference
    to its text; `questions` the ids of questions put to the person, MAP-050, which are always the person's and never
    sent. The answer maps each to 'person' or 'agent'; one Jev is unsure of is the person's, and named in `unsure`.

    Triage orders and flags; it never hides. Every message stays on the person's list and in the web GUI, those that
    need the person first and the rest marked as ones an agent may answer, since the text judged is data that can
    argue for its own answer, https://docs.typesafe.ai/model-jaggedness/jev-1.13.md#adversarial-content. Never kept:
    the order is a view.

    Fallback when None: every message is the person's, in its own order, as today."""
    def question(path: str) -> str:
        return _wording('triage', 'ask', item=path)
    asked_of = {key: text for key, text in messages.items() if key not in questions}
    cfg = config(folder, 'triage')
    got = None if cfg is None or not asked_of else _nouls(
        'pick_some', cfg, question, asked_of, {}, place='messages', true=_wording('triage', 'true'),
        false=_wording('triage', 'false'), title=_wording('triage', 'title'), why=_wording('triage', 'why'))
    if got is None:
        return None
    found = got[0]
    sorted_to = {key: 'person' if key not in asked_of or key in found.unsure or found.probabilities[key] >= 0.5
                 else 'agent' for key in messages}
    return replace(found, answer=sorted_to)


def intake_coverage(folder: Path, parts: Mapping[str, str], outline: str, *, address: str | None = None,
                    project: str | None = None) -> Decision | None:
    """Whether every top-level part of the AUE is represented in the map: `parts` each top-level folder or part to
    what it holds, `outline` the map as Markdown, `metaform.outline.markdown`. The answer lists the parts Jev is sure
    are missing; the unsure ones are in `unsure`, for the agent or the person to check. Kept at `address`, the trunk,
    only when a part is missing.

    Fallback when None: no check, as today."""
    def question(path: str) -> str:
        return _wording('intake_coverage', 'ask', item=path)
    cfg = config(folder, 'intake_coverage')
    got = None if cfg is None else _nouls('pick_some', cfg, question, parts, {'map': outline}, place='parts',
                                          true=_wording('intake_coverage', 'true'),
                                          false=_wording('intake_coverage', 'false'),
                                          title=_wording('intake_coverage', 'title'),
                                          why=_wording('intake_coverage', 'why'))
    if got is None:
        return None
    found, identity = got
    missing = [key for key in parts if key not in found.unsure and found.probabilities[key] < 0.5]
    return keep(folder, (replace(found, answer=missing), identity), address if missing else None, project)


DRIFT = ('conclusions', 'off_task', 'repeating')
PLACES = {'conclusions': 'calls.<call>', 'off_task': 'calls.<call>', 'repeating': 'steps.<window>'}  # what each asks of
CALLS = 20  # the latest tool calls judged, one question each
LATER = 3  # calls after a conclusion is read before whether its source was opened is asked
WINDOW = 6  # filed steps judged together for repeats, as artifacts/jev-experiments/e5_spin.py measured
WINDOWS = 6  # the latest windows of steps sent
OFF_TASK = 0.6  # the share of calls judged, surely, not to serve the task at which the session is off task
UNREAD = 0.5  # the share of conclusions read, surely, with no later read of their source at which it is conclusion-reading
# What a tool call reads, judged in code so Jev judges what the agent does with it, not file names: a report, review,
# log, note or plan by its name and a text extension, any .log, or anything under a folder of conclusions. A source
# file is never a conclusion, whatever it is named.
CONCLUSION = re.compile(
    r'(?i)(?:^|[\s/\\"\'=:])(?:artifacts|reports|reviews|logs|handoff[^/\\\s]*)[/\\]'
    r'|\.log\b'
    r'|(?<![A-Za-z0-9])(?:reports?|reviews?|summar(?:y|ies)|findings|notes|handoffs?|plans?)(?![A-Za-z])'
    r'[^/\\\s]*\.(?:md|txt|json)\b')
METAFORM = re.compile(r'(?i)metaform(?:://|_|\s|__)|\bmcp__metaform')


def call_kind(call: str) -> str:
    """What one tool call, given as its title and input, reads: 'metaform' (the map, a node's brief, memories or
    items), 'conclusion' (a report, review, log, note or other conclusion drawn earlier) or 'other'."""
    if METAFORM.search(call):
        return 'metaform'
    return 'conclusion' if CONCLUSION.search(call) else 'other'


def _windows(steps: Sequence[str]) -> dict[str, list[str]]:
    """The latest steps in windows of WINDOW, the last one full, named by where each starts; none when the steps fill
    no more than one window, since a repeat needs something earlier to repeat."""
    kept = list(steps)[-WINDOW * WINDOWS:]
    if len(kept) <= WINDOW:
        return {}
    windows: dict[str, list[str]] = {}
    start = 0
    for end in reversed(range(len(kept), 0, -WINDOW)):
        windows[f'w{start}'] = kept[start:end]
        start = end
    return windows


def session_drift(folder: Path, session: str, calls: Sequence[str], task: str, *, steps: Sequence[str] = (),
                  address: str | None = None, project: str | None = None) -> Decision | None:
    """Whether an agent session reads conclusions in place of the AUE's source, strays from its task, or repeats
    work: `calls` its recent tool calls, each one line, its title and input, oldest first; `task` the ticket's task;
    `steps` the steps it filed on the ticket, the work record's said lines, oldest first.

    Jev does not count, https://docs.typesafe.ai/model-jaggedness/jev-1.13.md#counting, so each thing is asked on its
    own, every question in one request over one state: per call (the latest CALLS), whether it serves the task; per
    conclusion read with LATER calls after it, whether a later call opens the source it describes; per window of
    steps, whether it repeats work already reported, as e5_spin.py found on the four tickets that looped. Code adds
    up the sure answers and owns the thresholds: off task at OFF_TASK of the calls, conclusion-reading at UNREAD of
    the conclusions read, repeating when the latest window is surely a repeat. Each is True, False, or None when too
    few answers are sure or, for repeats, no steps were given.

    The answer maps 'conclusions', 'off_task' and 'repeating' to those. Kept at `address` only when one is True. This
    tells what dispatch_spin_calls cannot: that count is of tool calls since the last step filed, and never compares
    what the calls or steps do. Fallback when None: that count alone, as today."""
    cfg = config(folder, 'session_drift')
    recent = list(calls)[-CALLS:]
    windows = _windows(steps)
    if cfg is None or not (recent or windows):
        return None
    named = {f'c{n}': {'call': call, 'kind': call_kind(call)} for n, call in enumerate(recent)}
    read = [name for n, name in enumerate(named) if named[name]['kind'] == 'conclusion' and len(named) - n - 1 >= LATER]
    meaning = {part: {'true': _wording('session_drift', f'{part}/true'),
                      'false': _wording('session_drift', f'{part}/false')} for part in DRIFT}
    questions: dict[str, Question] = {}
    for part, things in (('off_task', list(named)), ('conclusions', read), ('repeating', list(windows))):
        for thing in things:
            path = PLACES[part].split('.')[0] + f'.{thing}'
            questions[f'{part}__{thing}'] = Question('noul', _wording('session_drift', f'{part}/ask', item=path),
                                                     meaning[part])
    state: dict[str, Any] = {'task': task, 'calls': named}
    if windows:
        state['steps'] = windows
    answers = asked(cfg, state, questions)
    if answers is None:
        return None

    def of(part: str) -> list[Answer]:
        return [answer for name, answer in answers.items() if name.startswith(f'{part}__')]

    def share_no(part: str, threshold: float) -> bool | None:
        """Whether the share of sure no answers reaches `threshold`; None when fewer than half are sure."""
        sure = [answer for answer in of(part) if answer.confidence >= cfg.floor]
        if not sure or len(sure) * 2 < len(of(part)):
            return None
        return sum(float(answer.value) < 0.5 for answer in sure) / len(sure) >= threshold

    latest = answers.get(f'repeating__{next(reversed(windows))}') if windows else None
    found: dict[str, bool | None] = {
        'conclusions': False if not read else share_no('conclusions', UNREAD),
        'off_task': share_no('off_task', OFF_TASK) if named else None,
        'repeating': None if latest is None or latest.confidence < cfg.floor else float(latest.value) >= 0.5}
    unsure = tuple(part for part in DRIFT if of(part) and found[part] is None)
    model, cost, cached = _summed(answers)
    decision = Decision('yes_no', _wording('session_drift', 'title', session=session), _wording('session_drift', 'why'),
                        '\n'.join(_wording('session_drift', f'{part}/ask', item=PLACES[part]) for part in DRIFT),
                        DRIFT, found, min(answer.confidence for answer in answers.values()), not unsure,
                        '\n'.join(_noul_reason(name, answer, meaning[name.split('__')[0]]['true'],
                                               meaning[name.split('__')[0]]['false'])
                                  for name, answer in answers.items()), model, cost, cached, unsure,
                        {name: float(answer.value) for name, answer in answers.items()})
    drifted = any(found.values())
    return keep(folder, (decision, _identity(cfg, state, questions, model)), address if drifted else None, project)
