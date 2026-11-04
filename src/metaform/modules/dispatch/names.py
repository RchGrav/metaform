"""Each agent session's name: two words of the lists in resources/names, an adjective then a noun, each capitalized
and joined with nothing between, `StableComet`, worked out from the session's own id. The same id always gives the
same name, so a resumed session keeps its name, and a person points at an agent, and calls its context back, by a
name rather than an id.

The id's UTF-8 bytes are hashed with 32-bit FNV-1a and the hash is XOR-folded to 16 bits: the high byte indexes the
adjectives and the low byte the nouns, 256 words each, as the person's reference does. That gives 65,536 names, and
two live sessions sharing one is accepted: nothing avoids a clash or rehashes. The name is kept on the session's state
line, `name`, and read back with it wherever the state is read: no table changes.
"""
from __future__ import annotations

import json
from importlib import resources
from typing import Any, cast

FOLDER = 'names'  # resources/names: adjectives.txt and nouns.txt, one lower-case word a line, as the person gave them
WORDS = 256  # one word in each list for every value of a byte
FNV_BASIS = 2166136261  # 32-bit FNV-1a: the offset basis and the prime
FNV_PRIME = 16777619


def words(which: str) -> tuple[str, ...]:
    """The list `which`, adjectives or nouns, as shipped in resources/names: exactly 256 words, one a byte value."""
    text = (resources.files(__package__ or 'metaform.modules.dispatch') / 'resources' / FOLDER / f'{which}.txt') \
        .read_text(encoding='utf-8')
    listed = tuple(line.strip() for line in text.splitlines() if line.strip())
    assert len(listed) == WORDS, f'There must be exactly {WORDS} words in {which}.txt'
    return listed


ADJECTIVES = words('adjectives')  # read once, at load, so a wrong list fails the module and never one session's name
NOUNS = words('nouns')
CAPITALS = frozenset(noun.capitalize() for noun in NOUNS)  # the nouns as a name carries them


def session_name(session_id: str) -> str:
    """The name of the session with this id, a pure function of it: 32-bit FNV-1a of the id's UTF-8 bytes, XOR-folded
    to 16 bits; the high byte picks the adjective and the low byte the noun, each capitalized, `StableComet`."""
    hashed = FNV_BASIS
    for byte in session_id.encode('utf-8'):
        hashed = ((hashed ^ byte) * FNV_PRIME) & 0xFFFFFFFF
    folded = (hashed ^ (hashed >> 16)) & 0xFFFF
    return ADJECTIVES[folded >> 8].capitalize() + NOUNS[folded & 0xFF].capitalize()


def is_name(text: Any) -> bool:
    """Whether `text` is a name this module gives: a capitalized adjective of the list followed at once by a
    capitalized noun of the list, every adjective that starts the text tried."""
    given = str(text)
    return any(given.startswith(adjective.capitalize()) and given[len(adjective):] in CAPITALS
               for adjective in ADJECTIVES)


def state_of(tx: Any, session_id: str) -> dict[str, Any]:
    """A session's state line, read in the caller's transaction; empty when it kept none or it does not read."""
    row = tx.get('session_lines', {'session_id': session_id, 'name': 'state'})
    try:
        held: Any = json.loads(str(row['text'])) if row is not None else None
    except ValueError:
        held = None
    return cast(dict[str, Any], held) if isinstance(held, dict) else {}


def latest(tx: Any, name: str) -> dict[str, Any] | None:
    """The latest session of the project with this name, its row; None when no session has it. Read newest first,
    each state line by its key, until one holds the name, since a name is asked for its latest context."""
    mark = f'"name": {json.dumps(name)}'
    for row in reversed(tx.rows('agent_sessions', by=('seq',), limit=0).results):
        line = tx.get('session_lines', {'session_id': row['session_id'], 'name': 'state'})
        if line is not None and mark in str(line['text']) and state_of(tx, str(row['session_id'])).get('name') == name:
            return dict(row)
    return None
