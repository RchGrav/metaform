"""Each agent session's name: one adjective and one noun from the lists in resources/names, `brisk-lantern`, chosen
for the most significant words of its ticket's title and task, so the name says what the agent is for and a person can
point at it, and call its context back, by a name rather than an id.

Jev judges which words of the lists fit the ticket when it is on, every word a question of its own over the one
ticket, asked in one request and kept in Jev's cache; without Jev the task's own words are matched to the lists,
title words weighing most. Either way the pairs come best first, and the first one no running session of the project
holds is taken, in the same write that records the session, so two sessions starting at once never share one. The
name is kept on the session's state line, `name`, and read back with it wherever the state is read: no table changes.
"""
from __future__ import annotations

import hashlib
import heapq
import json
import re
from collections.abc import Iterator
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any, cast

FOLDER = 'names'  # resources/names: adjectives.txt and nouns.txt, one lower-case word a line, as the person gave them
TITLE_WEIGHT = 3  # a word of the ticket's title counts three times one of its task, being the most significant
TASK_SENT = 4000  # the characters of the task Jev reads beside the title, well inside its context
WORD = re.compile(r'[a-z]+')
# Words that say nothing of what a ticket is for, left out of the deterministic match.
STOP = frozenset((
    'a', 'about', 'above', 'after', 'again', 'all', 'also', 'an', 'and', 'any', 'are', 'as', 'at', 'be', 'been',
    'before', 'being', 'but', 'by', 'can', 'could', 'did', 'do', 'does', 'done', 'each', 'every', 'for', 'from', 'had',
    'has', 'have', 'how', 'if', 'in', 'into', 'is', 'it', 'its', 'just', 'may', 'more', 'most', 'must', 'no', 'not',
    'now', 'of', 'on', 'once', 'one', 'only', 'or', 'other', 'our', 'out', 'over', 'own', 'same', 'should', 'so',
    'some', 'such', 'than', 'that', 'the', 'their', 'them', 'then', 'there', 'these', 'they', 'this', 'those',
    'through', 'to', 'too', 'under', 'until', 'up', 'very', 'was', 'we', 'were', 'what', 'when', 'where', 'which',
    'while', 'who', 'whose', 'why', 'will', 'with', 'would', 'you', 'your'))


@cache
def words(which: str) -> tuple[str, ...]:
    """The list `which`, adjectives or nouns, as shipped in resources/names."""
    text = (resources.files(__package__ or 'metaform.modules.dispatch') / 'resources' / FOLDER / f'{which}.txt') \
        .read_text(encoding='utf-8')
    return tuple(line.strip() for line in text.splitlines() if line.strip())


def is_name(text: Any) -> bool:
    """Whether `text` is a name this module gives: an adjective of the list, a hyphen, a noun of the list."""
    adjective, dash, noun = str(text).partition('-')
    return bool(dash) and adjective in words('adjectives') and noun in words('nouns')


def stem(word: str) -> str:
    """The word without the commonest English endings, so `naming`, `named` and `names` meet `name`."""
    for ending, put in (('ings', ''), ('ing', ''), ('ies', 'y'), ('ied', 'y'), ('ers', ''), ('er', ''), ('ed', ''),
                        ('es', ''), ('ly', ''), ('s', '')):
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            return word[:len(word) - len(ending)] + put
    return word


def likeness(listed: str, word: str) -> float:
    """How far a word of the ticket is the listed word: the same, the same stem, or one the start of the other."""
    if listed == word:
        return 1.0
    if stem(listed) == stem(word):
        return 0.8
    short, long = sorted((listed, word), key=len)
    return 0.5 if len(short) >= 4 and long.startswith(short) else 0.0


def weights(title: str, task: str) -> dict[str, int]:
    """The significant words of the ticket, each with its weight: every time it is said, in the title three times."""
    found: dict[str, int] = {}
    for text, weight in ((title, TITLE_WEIGHT), (task, 1)):
        for word in WORD.findall(text.lower()):
            if len(word) >= 3 and word not in STOP:
                found[word] = found.get(word, 0) + weight
    return found


def matched(which: str, said: dict[str, int]) -> dict[str, float]:
    """Each listed word's score against the ticket's words: the weight of every word it is like, by how like."""
    return {listed: sum(weight * likeness(listed, word) for word, weight in said.items())
            for listed in words(which)}


def judged(folder: Path, title: str, task: str) -> tuple[dict[str, float], dict[str, float]] | None:
    """Jev's judgement of every listed word, the probability it fits a name for the agent on this ticket; None when
    Jev is off, has no key or credit, or does not answer in time."""
    from metaform import jev

    from . import prompt
    state = {'ticket': {'title': title, 'task': task[:TASK_SENT]}}
    criteria = {'true': prompt('name_true'), 'false': prompt('name_false')}
    asked = {which: prompt(f'name_{which[:-1]}', word='\0') for which in ('adjectives', 'nouns')}
    questions = {f'{which[0]}_{word}': jev.Question('noul', asked[which].replace('\0', word), criteria)
                 for which in ('adjectives', 'nouns') for word in words(which)}
    try:
        with jev.within(jev.DEADLINE):
            got = jev.ask(folder, state, questions)
    except Exception:  # noqa: BLE001  Jev never keeps a session from its name: the plain match names it
        return None
    if got is None:
        return None
    adjectives = {word: float(got[f'a_{word}'].value) for word in words('adjectives')}
    return adjectives, {word: float(got[f'n_{word}'].value) for word in words('nouns')}


def ordered(scores: dict[str, float], seed: str) -> list[tuple[str, float]]:
    """The words best first; words that score the same in an order fixed by the seed, the work id, so tickets that
    match nothing still differ, and the same ticket always gives the same order."""
    def drawn(word: str) -> str:
        return hashlib.sha256(f'{seed}:{word}'.encode()).hexdigest()
    return sorted(scores.items(), key=lambda pair: (-pair[1], drawn(pair[0])))


Ranking = tuple[list[tuple[str, float]], list[tuple[str, float]]]  # the adjectives and the nouns, each best first


def ranked(folder: Path | None, title: str, task: str, seed: str) -> Ranking:
    """The two lists, each best first for this ticket, through Jev when it is on and answers, else the plain match:
    the ranking a session's name is picked from, `free`."""
    found = judged(folder, title, task) if folder is not None else None
    said = weights(title, task)
    adjectives, nouns = found if found is not None else (matched('adjectives', said), matched('nouns', said))
    return ordered(adjectives, seed), ordered(nouns, seed)


def pairs(adjectives: list[tuple[str, float]], nouns: list[tuple[str, float]]) -> Iterator[str]:
    """Every adjective-noun pair, best first by the two words' scores together; a word in both lists is never
    paired with itself."""
    heap = [(-(score + nouns[0][1]), at, 0) for at, (_, score) in enumerate(adjectives)]
    heapq.heapify(heap)
    while heap:
        _, at, to = heapq.heappop(heap)
        adjective, noun = adjectives[at][0], nouns[to][0]
        if adjective != noun:
            yield f'{adjective}-{noun}'
        if to + 1 < len(nouns):
            heapq.heappush(heap, (-(adjectives[at][1] + nouns[to + 1][1]), at, to + 1))


def state_of(tx: Any, session_id: str) -> dict[str, Any]:
    """A session's state line, read in the caller's transaction; empty when it kept none or it does not read."""
    row = tx.get('session_lines', {'session_id': session_id, 'name': 'state'})
    try:
        held: Any = json.loads(str(row['text'])) if row is not None else None
    except ValueError:
        held = None
    return cast(dict[str, Any], held) if isinstance(held, dict) else {}


def held(tx: Any, besides: str | None = None) -> set[str]:
    """The names the project's running sessions hold, besides the session `besides`."""
    return {str(state['name']) for row in tx.rows('agent_sessions', by=('seq',), limit=0).results
            if row['state'] == 'running' and row['session_id'] != besides
            and (state := state_of(tx, str(row['session_id']))).get('name')}


def free(tx: Any, ranking: Ranking, session_id: str) -> str:
    """The best pair of the ranking no other running session of the project holds, read in the write transaction
    that records the session, so a session starting beside it reads this one's name: a clash takes the next pair."""
    taken = held(tx, besides=session_id)
    return next(name for name in pairs(*ranking) if name not in taken)


def latest(tx: Any, name: str) -> dict[str, Any] | None:
    """The latest session of the project with this name, its row; None when no session has it. Read newest first,
    each state line by its key, until one holds the name, since a name is asked for its latest context."""
    mark = f'"name": {json.dumps(name)}'
    for row in reversed(tx.rows('agent_sessions', by=('seq',), limit=0).results):
        line = tx.get('session_lines', {'session_id': row['session_id'], 'name': 'state'})
        if line is not None and mark in str(line['text']) and state_of(tx, str(row['session_id'])).get('name') == name:
            return dict(row)
    return None
