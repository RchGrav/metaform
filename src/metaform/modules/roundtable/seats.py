"""The seats at a table, BASE-066: who they are, and a model's turn through OpenRouter.

A seat is a kind and an id. Version one seats two kinds: `openrouter`, a model called through OpenRouter's chat
completions with OPENROUTER_API_KEY, written as its model id, `anthropic/claude-haiku-5.5`; and `agent`, an agent
that joins over MCP or the command line and submits its own turns, written `agent:<name>`. A harness dispatch runs
over ACP, `acp:<agent>`, and an A2A peer, `a2a:<peer>`, MCP-040, are seats the record names and are not built yet.

Whoever opens a table names its seats; there is no default line-up.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from typing import Any, cast

from metaform.module import Stop

KINDS = ('openrouter', 'agent')
LATER = ('acp', 'a2a')  # seats the record names, not built in version one
CHAT_URL = 'https://openrouter.ai/api/v1/chat/completions'
KEY = 'OPENROUTER_API_KEY'
TIMEOUT = 180.0  # seconds one model may take for one turn
SEAT_TOKENS = 4_000  # room for a reasoning model's thinking before its reply of at most 512 characters
REPORT_TOKENS = 12_000


def parse(given: str) -> dict[str, str]:
    """One seat as written: `agent:<name>`, `openrouter:<model>` or a bare model id."""
    text = given.strip()
    kind, sep, rest = text.partition(':')
    if sep and kind in LATER:
        raise Stop(f'{text}: an {kind} seat is not built yet; version one seats models through OpenRouter and agents '
                   'that submit their own turns.', 'metaform help roundtable open')
    if sep and kind == 'agent' and rest.strip():
        return {'kind': 'agent', 'id': f'agent:{rest.strip()}'}
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
                raise Stop('seats is a JSON list, such as ["anthropic/claude-haiku-5.5", "agent:me"].',
                           'metaform help roundtable open') from None
        else:
            value = text.split(',')
    if not isinstance(value, list):
        raise Stop('seats is a list of seats.', 'metaform help roundtable open')
    return [str(one).strip() for one in cast(list[Any], value) if str(one).strip()]


class Silent(Exception):
    """A model gave no reply; the message says why."""


def chat(model: str, messages: Sequence[Mapping[str, str]], *, tokens: int = SEAT_TOKENS) -> str:
    """One reply of a model through OpenRouter's chat completions; Silent when it fails or says nothing."""
    key = os.environ.get(KEY, '').strip()
    if not key:
        raise Silent(f'{KEY} is not set in the environment.')
    body = json.dumps({'model': model, 'messages': list(messages), 'max_tokens': tokens}).encode()
    request = urllib.request.Request(CHAT_URL, data=body, method='POST', headers={
        'Authorization': f'Bearer {key}', 'Content-Type': 'application/json',
        'X-Title': 'Metaform roundtable'})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            reply: Any = json.load(response)
        text = reply['choices'][0]['message'].get('content') or ''
    except urllib.error.HTTPError as error:
        raise Silent(f'HTTP {error.code}: {error.read(300).decode(errors="replace")}') from None
    except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
        raise Silent(str(error) or type(error).__name__) from None
    if not str(text).strip():
        raise Silent('the reply was empty.')
    return str(text).strip()


def missing_key(seats: Sequence[Mapping[str, str]]) -> bool:
    return any(seat['kind'] == 'openrouter' for seat in seats) and not os.environ.get(KEY, '').strip()
