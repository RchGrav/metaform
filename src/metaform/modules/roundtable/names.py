"""Each seat's short name, BASE-066: the word the seat goes by at its table, in its bubble, in the controls and in the
record, in place of its id.

A name is the model's family word, capitalised: the first word of the model's id that names it rather than its maker's
line, its version or its size, so `acp:codex/gpt-6-astra` is Astra, `google/gemini-4-argon` Gemini,
`anthropic/claude-haiku-5.5` Haiku and `deepseek/deepseek-v4.1-flash` DeepSeek. A word with no vowel is an acronym
and is written in capitals, GLM; a few brands keep their own capitals. An agent seat, `agent:<name>`, goes by its own
name. Names are unique at a table: a second seat with the same name is that name with 2, the third with 3. The head
agent, when it chairs, goes by a name made the same way from the model its harness runs, `head`.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

# Words that name a maker's line, a size or a release rather than the model, passed over for the next word.
LINE_WORDS = frozenset({
    'gpt', 'claude', 'chat', 'chatgpt', 'instruct', 'preview', 'latest', 'exp', 'experimental', 'flash', 'lite',
    'pro', 'mini', 'nano', 'turbo', 'max', 'plus', 'free', 'beta', 'alpha', 'base', 'it', 'hf', 'thinking', 'fast',
    'large', 'medium', 'small', 'high', 'low', 'online', 'vision', 'code', 'coder', 'open', 'ai'})
# Brands written with their own capitals.
BRANDS = {'deepseek': 'DeepSeek', 'minimax': 'MiniMax', 'openchat': 'OpenChat', 'internlm': 'InternLM',
          'chatglm': 'ChatGLM', 'openai': 'OpenAI', 'xai': 'xAI'}
VOWELS = frozenset('aeiouy')


def word(text: str) -> str:
    """One word as a name is written: a brand's own capitals, an acronym in capitals, else capitalised."""
    low = text.lower()
    if low in BRANDS:
        return BRANDS[low]
    if not VOWELS & set(low):
        return low.upper()
    return low[:1].upper() + low[1:]


def base(seat: Mapping[str, str]) -> str:
    """The name a seat goes by before its table makes it unique."""
    given = str(seat.get('id') or '')
    if seat.get('kind') == 'agent':
        own = given.partition(':')[2].strip() or 'Agent'
        return own[:1].upper() + own[1:]
    model = str(seat.get('model') or '') if seat.get('kind') == 'acp' else given.rpartition('/')[2]
    model = model or given.rpartition('/')[2]
    # the words, each with its trailing version or size cut off: qwen3.8 is qwen, k3 nothing
    words = [found for found in (re.sub(r'\d.*$', '', part) for part in re.split(r'[^A-Za-z0-9]+', model)) if found]
    words = [one for one in words if len(one) > 1]
    chosen = next((one for one in words if one.lower() not in LINE_WORDS), words[0] if words else 'Seat')
    return word(chosen)


def names(seats: Sequence[Mapping[str, str]]) -> list[str]:
    """Every seat's name, in the seats' order, unique at the table: a repeat takes 2, then 3."""
    found: list[str] = []
    for seat in seats:
        found.append(unique(base(seat), found))
    return found


def unique(name: str, taken: Sequence[str]) -> str:
    """The name, with 2, then 3, when the table already has it."""
    count = 1
    while (name if count == 1 else f'{name} {count}') in taken:
        count += 1
    return name if count == 1 else f'{name} {count}'


def head(agent: str, model: str | None, taken: Sequence[str] = ()) -> str:
    """The head agent's name: its model's family word as a seat's (Opus for opus, or for a model named Opus 5.5),
    else its harness's (Claude), unique against the seats' names."""
    if model:
        named = base({'kind': 'acp', 'id': f'acp:{agent}/{model}', 'agent': agent, 'model': model})
    else:
        named = word(re.split(r'[^A-Za-z0-9]+', agent)[0] or 'Chair')
    return unique(named, taken)


def harness_of(seat: Mapping[str, str]) -> str:
    """The harness or maker a seat runs on, as the page's figures name them."""
    given = str(seat.get('id') or '')
    if seat.get('kind') == 'acp':
        return str(seat.get('agent') or 'other')
    maker = given.partition('/')[0].lower()
    return {'anthropic': 'claude', 'openai': 'codex', 'google': 'gemini'}.get(maker, 'other')
