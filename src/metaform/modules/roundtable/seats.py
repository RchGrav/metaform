"""The seats at a table, BASE-066: who they are, and a model's turn through OpenRouter.

A seat is a kind and an id. Three kinds are seated: `openrouter`, a model called through OpenRouter's chat completions
with OPENROUTER_API_KEY, written as its model id, `anthropic/claude-haiku-5.5`; `agent`, an agent that joins over MCP
or the command line and submits its own turns, written `agent:<name>`; and `acp`, a harness dispatch runs over ACP on
the person's own login, Claude Code or Codex, written `acp:<agent>/<model>`, such as `acp:codex/gpt-6-astra`, its turns
taken by `harness`. An A2A peer, `a2a:<peer>`, MCP-040, is a seat the record names and is not built yet.

Whoever opens a table names its seats; there is no default line-up.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from metaform.module import Stop

KINDS = ('openrouter', 'agent', 'acp')
LATER = ('a2a',)  # a seat the record names, not built yet
CHAT_URL = 'https://openrouter.ai/api/v1/chat/completions'
KEY = 'OPENROUTER_API_KEY'
TIMEOUT = 180.0  # seconds one model may take for one turn
SEAT_TOKENS = 4_000  # room for a reasoning model's thinking before its reply of at most 512 characters
REPORT_TOKENS = 12_000


def parse(given: str) -> dict[str, str]:
    """One seat as written: `agent:<name>`, `acp:<agent>/<model>`, `openrouter:<model>` or a bare model id. An acp
    seat's agent and model are checked against dispatch when the table opens, `harness.check`."""
    text = given.strip()
    kind, sep, rest = text.partition(':')
    if sep and kind in LATER:
        raise Stop(f'{text}: an {kind} seat is not built yet; a table seats models through OpenRouter, harnesses '
                   'through dispatch and agents that submit their own turns.', 'metaform help roundtable open')
    if sep and kind == 'agent' and rest.strip():
        return {'kind': 'agent', 'id': f'agent:{rest.strip()}'}
    if sep and kind == 'acp':
        agent, slash, model = rest.strip().partition('/')
        if not (slash and re.fullmatch(r'[A-Za-z0-9._-]+', agent) and re.fullmatch(r'[A-Za-z0-9~._:-]+', model)):
            raise Stop(f'{text} is not a seat: write acp:<agent>/<model>, such as acp:claude/opus or '
                       'acp:codex/gpt-6-astra.', 'metaform dispatch agents')
        return {'kind': 'acp', 'id': f'acp:{agent}/{model}', 'agent': agent, 'model': model}
    model = rest if sep and kind == 'openrouter' else text
    if not re.fullmatch(r'[A-Za-z0-9~._-]+/[A-Za-z0-9._:-]+', model):
        raise Stop(f'{text} is not a seat: write a model id such as anthropic/claude-haiku-5.5, or agent:<name>.',
                   'metaform help roundtable open')
    return {'kind': 'openrouter', 'id': model}


def chosen(given: Any) -> list[dict[str, str]]:
    """The seats in order, as the one opening the table named them. A seat is named once."""
    listed = [parse(one) for one in words(given)]
    seats: list[dict[str, str]] = []
    for seat in listed:
        if all(seat['id'] != held['id'] for held in seats):
            seats.append(seat)
    if not seats:
        raise Stop('A table needs one seat at least.', 'metaform help roundtable open')
    return seats


def words(value: Any) -> list[str]:
    """A list noun: a JSON list, or text separated by commas."""
    if value is None or value == '':
        return []
    if isinstance(value, str):
        text = value.strip()
        if text.startswith('['):
            try:
                value = json.loads(text)
            except ValueError:
                raise Stop('seats is a JSON list, such as '
                           '["anthropic/claude-haiku-5.5", "acp:claude/opus", "agent:me"].',
                           'metaform help roundtable open') from None
        else:
            value = text.split(',')
    if not isinstance(value, list):
        raise Stop('seats is a list of seats.', 'metaform help roundtable open')
    return [str(one).strip() for one in cast(list[Any], value) if str(one).strip()]


class Silent(Exception):
    """A model gave no reply; the message says why."""


Paid = Callable[[float], None]  # told what each answered call cost in US dollars, from OpenRouter's usage

# The providers that cache a prompt only when the request asks, OpenRouter's prompt caching: Alibaba's Qwen and
# Anthropic. Every other provider a seat is likely to be (OpenAI, DeepSeek, Moonshot, Z.AI, Grok, Gemini) caches on
# its own.
ASKED = ('qwen/', 'anthropic/')
USE = ('prompt_tokens', 'cached_tokens', 'cache_write_tokens', 'cost')  # a submission's columns for what it used


@dataclass
class Use:
    """What a seat's calls in one turn used, added up from the usage OpenRouter returns with each: the prompt tokens
    sent, those read from the provider's cache and those written to it, and the US dollars."""
    prompt_tokens: int = 0
    cached_tokens: int = 0
    cache_write_tokens: int = 0
    cost: float = 0.0

    def add(self, reply: Any) -> None:
        usage: Any = cast(dict[str, Any], reply).get('usage') if isinstance(reply, dict) else None
        if not isinstance(usage, dict):
            return
        used = cast(dict[str, Any], usage)
        details: Any = used.get('prompt_tokens_details')
        held = cast(dict[str, Any], details) if isinstance(details, dict) else {}
        try:
            self.prompt_tokens += int(used.get('prompt_tokens') or 0)
            self.cached_tokens += int(held.get('cached_tokens') or 0)
            self.cache_write_tokens += int(held.get('cache_write_tokens') or 0)
        except (TypeError, ValueError):
            pass
        self.cost += cost(reply)

    def columns(self) -> dict[str, Any]:
        return {'prompt_tokens': self.prompt_tokens, 'cached_tokens': self.cached_tokens,
                'cache_write_tokens': self.cache_write_tokens, 'cost': round(self.cost, 6)}


def marked(messages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The messages with the newest one's last text block marked `cache_control` ephemeral, for a provider that
    caches only when asked; the messages kept are never marked, so what is cached is the conversation as sent."""
    found = [dict(one) for one in messages]
    if not found:
        return found
    content: Any = found[-1].get('content')
    parts = ([{'type': 'text', 'text': content}] if isinstance(content, str) else
             [dict(part) for part in cast(list[dict[str, Any]], content or [])])
    for part in reversed(parts):
        if part.get('type') == 'text' and part.get('text'):
            part['cache_control'] = {'type': 'ephemeral'}
            found[-1]['content'] = parts
            break
    return found


def complete(model: str, messages: Sequence[Mapping[str, Any]], *, tokens: int = SEAT_TOKENS,
             tools: Sequence[Mapping[str, Any]] = (), tool_choice: str = 'auto',
             paid: Paid | None = None, session: str | None = None, use: Use | None = None) -> dict[str, Any]:
    """One answer of a model through OpenRouter's chat completions, the assistant message itself, with the tools it
    may call; its cost, the usage cost OpenRouter returns, told to `paid`, and its usage added to `use`. `session`,
    a seat's own, routes every request of the seat to the same provider endpoint while it is warm, so its cache
    holds. Silent when it fails, Untooled when the model takes no tools, Unpaid when OpenRouter refuses it for want
    of credits, HTTP 402."""
    key = os.environ.get(KEY, '').strip()
    if not key:
        raise Silent(f'{KEY} is not set in the environment.')
    asked: dict[str, Any] = {'model': model, 'messages': marked(messages) if model.startswith(ASKED)
                             else list(messages), 'max_tokens': tokens, 'usage': {'include': True}}
    if session:
        asked['session_id'] = session
    if tools:
        asked.update(tools=list(tools), tool_choice=tool_choice)
    request = urllib.request.Request(CHAT_URL, data=json.dumps(asked).encode(), method='POST', headers={
        'Authorization': f'Bearer {key}', 'Content-Type': 'application/json',
        'X-Title': 'Metaform roundtable'})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            reply: Any = json.load(response)
        message = dict(reply['choices'][0]['message'])
    except urllib.error.HTTPError as error:
        said = error.read(300).decode(errors='replace')
        if error.code == 402:
            raise Unpaid(f'HTTP 402: {said}') from None
        if tools and error.code in (400, 404) and 'tool' in said.lower():
            raise Untooled(said) from None
        raise Silent(f'HTTP {error.code}: {said}') from None
    except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
        raise Silent(str(error) or type(error).__name__) from None
    if paid is not None:
        paid(cost(reply))
    if use is not None:
        use.add(reply)
    return message


def cost(reply: Any) -> float:
    """The US dollars a reply cost, from the usage OpenRouter returns with it; 0 when it gives none."""
    usage: Any = cast(dict[str, Any], reply).get('usage') if isinstance(reply, dict) else None
    try:
        return float(cast(dict[str, Any], usage).get('cost') or 0) if isinstance(usage, dict) else 0.0
    except (TypeError, ValueError):
        return 0.0


def chat(model: str, messages: Sequence[Mapping[str, Any]], *, tokens: int = SEAT_TOKENS,
         paid: Paid | None = None, session: str | None = None, use: Use | None = None) -> str:
    """One reply of a model through OpenRouter's chat completions; Silent when it fails or says nothing."""
    text = complete(model, messages, tokens=tokens, paid=paid, session=session, use=use).get('content') or ''
    if not str(text).strip():
        raise Silent('the reply was empty.')
    return str(text).strip()


class Untooled(Silent):
    """The model takes no tools; the message is OpenRouter's."""


class Unpaid(Silent):
    """OpenRouter refused the call for want of credits, HTTP 402; asking again cannot help until the person adds
    some, so the table holds rather than passing the turn."""


MODELS_URL = 'https://openrouter.ai/api/v1/models'
MODELS_DAY = 86_400  # seconds OpenRouter's model list is kept before it is read again


def sees(model: str) -> bool:
    """Whether the model takes pictures: image among its OpenRouter architecture's input_modalities; a model the list
    does not name, or a list that cannot be read, takes none."""
    return 'image' in listed_models().get(model, [])


def listed_models() -> dict[str, list[str]]:
    """OpenRouter's models, each id with its input modalities, kept in the home for a day; none when the list cannot
    be read."""
    from metaform import home
    cache = home.home() / 'cache' / 'roundtable-models.json'
    known: dict[str, Any] = {}
    try:
        if cache.is_file():
            known = json.loads(cache.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        known = {}
    if not known or time.time() - float(known.get('read') or 0) > MODELS_DAY:
        try:
            with urllib.request.urlopen(MODELS_URL, timeout=30) as response:
                listed: Any = json.load(response)
            known = {'read': time.time(), 'models': {
                str(one['id']): list(cast(dict[str, Any], one.get('architecture') or {}).get('input_modalities')
                                     or []) for one in cast(list[dict[str, Any]], listed['data'])}}
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(known), encoding='utf-8')
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return cast(dict[str, list[str]], known.get('models') or {})


def missing_key(seats: Sequence[Mapping[str, str]]) -> bool:
    return any(seat['kind'] == 'openrouter' for seat in seats) and not os.environ.get(KEY, '').strip()
