"""A model seat's turn through OpenRouter's chat completions, with prompt caching.

Each seat is its system message, fixed for the table's life and first in every request, then one running
conversation that only grows within a topic: every request is the conversation kept so far plus the new message, so
each request's prefix is the last one's byte for byte, and the provider's cache holds it. When a topic opens the
conversation begins again after the system message (`Seat.rebuild`). Every request of a seat carries the seat's own
`session_id`, so OpenRouter routes it to the same provider endpoint while the cache is warm. Providers that cache on
their own (OpenAI, DeepSeek, Moonshot, Z.AI, Grok, Gemini) need nothing more; Qwen and Anthropic cache only when
asked, so the outgoing copies of the system message and of the newest message are marked `cache_control` ephemeral at
their last text block, for `cache_ttl`, and the conversation kept is never marked. What each call read from the cache
and wrote to it, its prompt, completion and reasoning tokens, why it stopped and its cost come back with it and are
added up per turn in `Use`.

A turn asks for `seat_tokens` of output at the `seat_reasoning` effort; a reply that spent them all thinking and wrote
no text, `finish_reason` `length`, is asked once more with reasoning off.

A call that fails for a moment is asked again: a timeout (408), a rate limit (429), any server failure (5xx), and a
connection that drops or resets, `http.client.HTTPException` among them, with a wait that doubles from BACKOFF and is
jittered, never shorter than a `Retry-After` asks, and all of it inside the one deadline its turn has. A request that
asking again cannot help, 400, 401, 404, 413 and every other 4xx, is never retried; 402, out of credits, is `Unpaid`.
A reply read is returned even when the deadline passed while it was read: it was paid for.

https://openrouter.ai/docs/features/prompt-caching
"""
from __future__ import annotations

import asyncio
import email.utils
import http.client
import json
import random
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from . import config
from .seat import Late, NoReply, Reply, Seat

TIMEOUT = 180.0  # seconds per socket attempt, capped by the turn's remaining time
RETRIED = frozenset({408, 429})  # with every 5xx; any other 4xx, 400, 401, 404 and 413 among them, is never retried
BACKOFF = (2.0, 4.0, 8.0)  # doubling seconds between attempts, each jittered down to half and stretched to a Retry-After
ASKED = ('qwen/', 'anthropic/')  # the providers that cache a prompt only when the request asks


class Silent(Exception):
    """A model gave no reply; the message says why, `code` the HTTP status when there was one, and `kind` its class
    as a seat's failures are counted: `transient`, `refused`, `empty` or `failed`."""

    def __init__(self, message: str, code: int | None = None, kind: str = 'failed') -> None:
        super().__init__(message)
        self.code = code
        self.kind = kind


class Unpaid(Silent):  # never a NoReply: only its seat is out, or the table holds when Jev is refused
    """OpenRouter refused the call for want of credits, HTTP 402; asking again cannot help until the person adds
    some, so a seat refused is unavailable and a table whose Jev is refused holds, each going on once `credited`
    finds credits again."""

    def __init__(self, message: str) -> None:
        super().__init__(message, 402, 'credits')


Paid = Callable[[float], None]  # told what each answered call cost in US dollars


@dataclass
class Use:
    """What a seat's calls in one turn used, added up from the usage OpenRouter returns with each."""
    prompt_tokens: int = 0
    cached_tokens: int = 0
    cache_write_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    finish_reason: str | None = None  # why the latest call stopped: stop, length, …
    cost: float = 0.0
    model: str | None = None  # the model OpenRouter says answered

    def add(self, reply: Any) -> None:
        if not isinstance(reply, dict):  # a body that is not a JSON object says nothing of what it used
            return
        given = cast(dict[str, Any], reply)
        self.model = str(given.get('model') or self.model or '') or None
        self.finish_reason = finished(reply) or self.finish_reason
        usage: Any = given.get('usage')
        if not isinstance(usage, dict):
            return
        used = cast(dict[str, Any], usage)
        details: Any = used.get('prompt_tokens_details')
        held = cast(dict[str, Any], details) if isinstance(details, dict) else {}
        written: Any = used.get('completion_tokens_details')
        thought = cast(dict[str, Any], written) if isinstance(written, dict) else {}
        try:
            self.prompt_tokens += int(used.get('prompt_tokens') or 0)
            self.cached_tokens += int(held.get('cached_tokens') or 0)
            self.cache_write_tokens += int(held.get('cache_write_tokens') or 0)
            self.completion_tokens += int(used.get('completion_tokens') or 0)
            self.reasoning_tokens += int(thought.get('reasoning_tokens') or 0)
        except (TypeError, ValueError):
            pass
        self.cost += cost(reply)

    def columns(self) -> dict[str, Any]:
        return {'prompt_tokens': self.prompt_tokens, 'cached_tokens': self.cached_tokens,
                'cache_write_tokens': self.cache_write_tokens, 'completion_tokens': self.completion_tokens,
                'reasoning_tokens': self.reasoning_tokens, 'finish_reason': self.finish_reason,
                'cost': round(self.cost, 6), 'model': self.model}


def finished(reply: Any) -> str | None:
    """Why a reply's first choice stopped, `finish_reason`; None when it does not say."""
    try:
        return str(reply['choices'][0].get('finish_reason') or '') or None
    except (KeyError, IndexError, TypeError, AttributeError):
        return None


def cost(reply: Any) -> float:
    """What a reply says its call cost in US dollars; 0 when it says nothing, or is not a JSON object."""
    if not isinstance(reply, dict):
        return 0.0
    usage: Any = cast(dict[str, Any], reply).get('usage')
    try:
        return float(cast(dict[str, Any], usage).get('cost') or 0) if isinstance(usage, dict) else 0.0
    except (TypeError, ValueError):
        return 0.0


def marked(messages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The messages with a breakpoint after the system message and at the newest message: the last text block of
    each marked `cache_control` ephemeral; a copy, so the conversation kept is never marked."""
    found = [dict(one) for one in messages]
    ttl = str(config.value('cache_ttl')).strip()
    ends: set[int] = {len(found) - 1} if found else set()
    if found and found[0].get('role') == 'system':
        ends.add(0)
    for at in sorted(ends):
        content: Any = found[at].get('content')
        parts: list[dict[str, Any]] = ([{'type': 'text', 'text': content}] if isinstance(content, str) else
                 [dict(part) for part in cast(list[dict[str, Any]], content or [])])
        for part in reversed(parts):
            if part.get('type') == 'text' and part.get('text'):
                part['cache_control'] = {'type': 'ephemeral', **({'ttl': ttl} if ttl else {})}
                found[at]['content'] = parts
                break
    return found


def remaining(deadline: float | None) -> float:
    """Seconds left on a monotonic deadline; TimeoutError once it expires."""
    seconds = TIMEOUT if deadline is None else deadline - time.monotonic()
    if seconds <= 0:
        raise TimeoutError
    return seconds


def retried(code: int) -> bool:
    """Whether an HTTP status is worth asking again: a timeout, a rate limit or a server failure."""
    return code in RETRIED or 500 <= code < 600


def retry_after(headers: Any) -> float | None:
    """The seconds a Retry-After header asks for, given as seconds or as an HTTP date; None when there is none."""
    said: Any = headers.get('Retry-After') if headers is not None else None
    if not said:
        return None
    try:
        return max(0.0, float(said))
    except ValueError:
        pass
    try:
        when = email.utils.parsedate_to_datetime(str(said))
    except (TypeError, ValueError):
        return None
    return max(0.0, when.timestamp() - time.time())


def post(path: str, body: Mapping[str, Any], *, deadline: float | None = None,
         tried: Callable[[], None] | None = None, stop: threading.Event | None = None,
         trace: dict[str, Any] | None = None) -> dict[str, Any]:
    """One POST to OpenRouter and its JSON reply, asked again with a jittered, doubling wait on a timeout, a rate
    limit, a server failure or a dropped connection, never sooner than a Retry-After asks; Unpaid on HTTP 402,
    Silent on any other failure, on the last attempt's, or when a Retry-After asks past the time left. Every wait
    ends by the optional monotonic deadline; TimeoutError when it expires before an attempt, or `stop` is set. `tried` is told of each attempt, and
    a `trace` given is told the last body read as it came, whole, under `raw`, an error's body too."""
    key = config.openrouter_key()
    if not key:
        raise Silent(f'{config.KEY} is not set in the environment.')
    url = config.value('openrouter_url').rstrip('/') + path
    data = json.dumps(body).encode()
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json', 'X-Title': 'roundtable'}
    for backoff in [*BACKOFF, None]:
        if stop is not None and stop.is_set():
            raise TimeoutError
        timeout = min(TIMEOUT, remaining(deadline))
        if tried is not None:
            tried()
        request = urllib.request.Request(url, data=data, method='POST', headers=headers)
        asked: float | None = None  # what a refusal's Retry-After asks
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                read = response.read()
            if trace is not None:
                trace['raw'] = read.decode(errors='replace')
            return cast(dict[str, Any], json.loads(read))  # past the deadline too: it was paid for
        except urllib.error.HTTPError as error:
            try:
                given = error.read(1 << 20).decode(errors='replace')
            except (OSError, http.client.HTTPException):
                given = ''
            if trace is not None:
                trace['raw'] = given or None
            said = message(given) if given else ''
            if error.code == 402:
                raise Unpaid(f'HTTP 402: {said}') from None
            if not retried(error.code):
                raise Silent(f'HTTP {error.code}: {said}', error.code, 'refused') from None
            failure = Silent(f'HTTP {error.code}: {said}', error.code, 'transient')
            asked = retry_after(error.headers)
        except (OSError, ValueError, http.client.HTTPException) as error:
            failure = Silent(str(error) or type(error).__name__, kind='transient')
        if backoff is None:
            raise failure
        if asked is not None and deadline is not None and asked >= deadline - time.monotonic():
            raise Silent(f'{failure} (its Retry-After of {asked:.0f} seconds is past the turn\'s time)', failure.code,
                         failure.kind)
        pause = max(backoff * random.uniform(0.5, 1.0), asked or 0.0)
        if deadline is not None:  # never past the turn's one deadline; the next attempt then finds it spent
            pause = min(pause, remaining(deadline))
        if stop is not None:
            if stop.wait(pause):
                raise TimeoutError
        else:
            time.sleep(pause)
    raise Silent('OpenRouter did not answer.', kind='transient')


def price(pricing: Mapping[str, Any], key: str) -> float | None:
    """A price per token in US dollars, as OpenRouter's model list gives it; None when it gives none."""
    try:
        return float(pricing[key]) if pricing.get(key) not in (None, '') else None
    except (TypeError, ValueError):
        return None


def models() -> list[dict[str, Any]]:
    """Every model OpenRouter lists, as a seat is chosen from it: its id and name, its price per token for the
    prompt, the completion and a cache read, its context size, whether it takes images and whether it caches (it
    prices a cache read). Silent when the list cannot be read."""
    request = urllib.request.Request(config.value('openrouter_url').rstrip('/') + '/v1/models', headers={
        **({'Authorization': f'Bearer {config.openrouter_key()}'} if config.openrouter_key() else {}),
        'X-Title': 'roundtable'})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            listed: Any = json.load(response)
    except (OSError, ValueError) as error:
        raise Silent(f'the model list was not read: {error}') from None
    data: Any = cast(dict[str, Any], listed).get('data') if isinstance(listed, dict) else None
    found: list[dict[str, Any]] = []
    for given in cast(list[dict[str, Any]], data or []):
        pricing = cast(dict[str, Any], given.get('pricing') or {})
        shape = cast(dict[str, Any], given.get('architecture') or {})
        taken = [str(one) for one in cast(list[Any], shape.get('input_modalities') or [])]
        read = price(pricing, 'input_cache_read')
        found.append({'id': str(given.get('id') or ''), 'name': str(given.get('name') or given.get('id') or ''),
                      'prompt': price(pricing, 'prompt'), 'completion': price(pricing, 'completion'),
                      'cache_read': read, 'cache_write': price(pricing, 'input_cache_write'),
                      'context': given.get('context_length'), 'images': 'image' in taken,
                      'caches': read is not None and read > 0})
    return sorted((one for one in found if one['id']), key=lambda one: one['id'])


def credited() -> None:
    """A probe, free of charge, of whether OpenRouter takes a paid call again: the key's own limit, then the account's
    credits where the key may read them. Unpaid while either is spent; Silent when OpenRouter cannot be asked."""
    def read(path: str) -> dict[str, Any]:
        request = urllib.request.Request(config.value('openrouter_url').rstrip('/') + path, headers={
            'Authorization': f'Bearer {config.openrouter_key()}', 'X-Title': 'roundtable'})
        with urllib.request.urlopen(request, timeout=30) as response:
            given: Any = json.load(response)
        data: Any = cast(dict[str, Any], given).get('data') if isinstance(given, dict) else None
        return cast(dict[str, Any], data) if isinstance(data, dict) else {}

    if not config.openrouter_key():
        raise Silent(f'{config.KEY} is not set in the environment.')
    try:
        key = read('/v1/key')
        left: Any = key.get('limit_remaining')
        if left is not None and float(left) <= 0:
            raise Unpaid('the key\'s credit limit is spent')
        try:
            credits = read('/v1/credits')
        except urllib.error.HTTPError as error:
            if error.code in (401, 403):  # a key that may not read the account's credits: its own limit decides
                return
            raise
        if credits and float(credits.get('total_credits') or 0) - float(credits.get('total_usage') or 0) <= 0:
            raise Unpaid('the account has no credits left')
    except urllib.error.HTTPError as error:
        if error.code == 402:
            raise Unpaid(f'HTTP 402: {message(error.read(2000).decode(errors="replace"))}') from None
        raise Silent(f'HTTP {error.code}') from None
    except (OSError, ValueError, TypeError) as error:
        raise Silent(str(error) or type(error).__name__) from None


def message(body: str) -> str:
    """What an error body says: its error's message when it is OpenRouter's JSON, else its first 400 characters."""
    try:
        found: Any = json.loads(body)
        return str(found['error']['message'])
    except (ValueError, KeyError, TypeError):
        return body[:400]


def chat(model: str, messages: Sequence[Mapping[str, Any]], *, tokens: int, session: str | None = None,
         paid: Paid | None = None, use: Use | None = None, deadline: float | None = None,
         stop: threading.Event | None = None, effort: str = '') -> str:
    """One reply of a model to the conversation, asked at the reasoning `effort` when one is given; its cost told to
    `paid` and its usage added to `use`. An empty reply cut off at `tokens` is asked once more with reasoning off.
    Silent when it fails or says nothing, Unpaid when OpenRouter is out of credits."""
    asked: dict[str, Any] = {'model': model, 'messages': marked(messages) if model.startswith(ASKED)
                             else list(messages), 'max_tokens': tokens, 'usage': {'include': True}}
    if session:
        asked['session_id'] = session
    if effort:
        asked['reasoning'] = {'effort': effort}
    for again in (False, True):
        reply = post('/v1/chat/completions', asked, deadline=deadline, stop=stop)
        if paid is not None:
            paid(cost(reply))
        if use is not None:
            use.add(reply)
        try:
            text = str(reply['choices'][0]['message'].get('content') or '').strip()
        except (KeyError, IndexError, TypeError, AttributeError):
            raise Silent(f'the reply had no message: {json.dumps(reply)[:300]}', kind='empty') from None
        if text:
            return text
        if again or finished(reply) != 'length':
            break
        asked = {**asked, 'reasoning': {'effort': 'none'}}  # it thought until it ran out: once more, without
    raise Silent('the reply was empty.', kind='empty')


class ModelSeat(Seat):
    """A model through OpenRouter: its system message and its conversation since the topic opened, sent each turn
    under the seat's own session_id, so the provider's cache holds the part sent before."""
    kind = 'openrouter'
    system_role = True

    def session_id(self) -> str:
        return f'roundtable-{self.number}-{self.position}'

    async def ask(self, text: str, tokens: int, seconds: float, effort: str = '') -> Reply:
        """One turn under one deadline for every attempt and wait, at the reasoning `effort` when one is given. When
        the turn's time runs out first the worker is told to stop, and a call it still had paid for is told to the
        seat's accounting once it finishes."""
        deadline = time.monotonic() + seconds
        system = [{'role': 'system', 'content': self.system}] if self.system else []
        use = Use()
        costs: list[float] = []  # the worker never changes the seat or calls its accounting callback
        told = 0
        stop = threading.Event()  # set when the turn ends, so the worker starts no further attempt or wait

        def settle(done: asyncio.Future[str] | None = None) -> None:  # on the loop: each paid cost told once
            nonlocal told
            if done is not None and not done.cancelled():
                done.exception()  # retrieved, so an abandoned worker's failure is not logged as unhandled
            for spent in costs[told:]:
                self.paid(spent)
            told = len(costs)

        worker = asyncio.ensure_future(asyncio.to_thread(
            chat, self.id, [*system, *self.messages, {'role': 'user', 'content': text}], tokens=tokens,
            session=self.session_id(), paid=costs.append, use=use, deadline=deadline, stop=stop, effort=effort))
        try:
            answer = await asyncio.wait_for(asyncio.shield(worker), timeout=max(0, deadline - time.monotonic()))
        except TimeoutError:
            # A socket read can outlive its timeout. Its worker's eventual answer is ignored; its cost is not.
            raise Late(seconds, delivered=False) from None
        except Unpaid:
            raise
        except Silent as error:  # nothing was taken: the seat's next turn carries these turns again
            raise NoReply(str(error), kind=error.kind) from None
        finally:
            stop.set()
            settle()
            if not worker.done():
                worker.add_done_callback(settle)
        self.reported = use.model or self.reported
        return Reply(answer, use.columns())

    async def probe(self, kind: str) -> None:
        """Free of charge: after a 402, whether OpenRouter has credits again; after a refused request, whether the
        key is good and the model still listed. After any other failure the seat's next turn is the probe."""
        try:
            if kind in ('credits', 'refused'):
                await asyncio.to_thread(credited)
            if kind == 'refused' and self.id not in {one['id'] for one in await asyncio.to_thread(models)}:
                raise NoReply(f'OpenRouter no longer lists {self.id}', kind='refused')
        except Silent as error:
            raise NoReply(str(error), kind=error.kind) from None

    async def exchange(self, text: str, seconds: float) -> Reply:
        return await self.ask(text, int(config.value('seat_tokens')), seconds,
                              str(config.value('seat_reasoning') or '').strip())

    async def report(self, record: str, seconds: float) -> str:
        return (await self.ask(record, int(config.value('report_tokens')), seconds)).text
