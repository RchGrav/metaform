"""The Roundtable 2 protocol (`docs/roundtable-2/ROUND_PROTOCOL.md`): a table's topics, opened one at a time in the
order given at open, and the stages each passes through:

    discussion → synthesis → ranking → top three → bottom three → host summary → the next topic … → report

- **discussion**: participant turns until every participant voluntarily replies PASS in one full round,
  or the chair explicitly chooses `advance`; context handoff continues discussion without ending it;
- **synthesis**: the synthesizer, in a fresh request holding only the topic and what entered its discussion, names
  every idea collected, and the code numbers them I1 and on;
- **ranking**: every seat, in its own conversation, ranks every idea best to worst; a ranking that is not every id
  exactly once gets one repair request, and one still not is kept as written, unread;
- **top three** and **bottom three**: every seat explains its top three in at most 2,048 characters and its bottom
  three in at most 1,024; a longer one is cut there and the record keeps the original;
- **host summary**: the host, in a fresh request, summarizes the seats' selections and reasons, and ranks nothing.

The synthesizer and the host are named at open; the synthesizer is the host unless named; the host is
`acp:codex/gpt-6` when Codex offers it, else the chair names one. Neither need sit at the table, and neither is ever an
outside agent seat, which has no conversation of its own to answer from. Raw rankings are the record; the export
adds a Borda count, labeled derived, which nothing in the protocol uses.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from . import names, seats
from .prompts import said
from .store import STAGES

EACH = ('ranking', 'top_three', 'bottom_three')  # the stages every seat answers in its own conversation
LIMITS = {'top_three': 2048, 'bottom_three': 1024}  # the most characters an explanation keeps
TOPICS = ('01_WORLD', '02_OBJECTS', '03_COLLABORATION')  # the Roundtable 2 topics, a table's when open names none
HOST = 'acp:codex/gpt-6'
IDEA = re.compile(r'^\s*(?:[-*]\s*)?(?:\*\*)?\s*I(\d+)\s*(?:\*\*)?\s*[.:)\]]\s*(?:\*\*)?\s*(.+?)\s*$', re.IGNORECASE)
ID = re.compile(r'\bI(\d+)\b', re.IGNORECASE)


def following(stage: str) -> str:
    """The stage after `stage` within a topic; `report` closes the last topic."""
    return STAGES[STAGES.index(stage) + 1]


# ----------------------------------------------------------------------------------------------- topics

def title(text: str) -> str:
    """A topic's title: its first line that says something, without a Markdown heading's marks."""
    first = next((line.strip() for line in text.splitlines() if line.strip()), '')
    return first.lstrip('#').strip()[:200] or 'Topic'


def topics_of(given: Sequence[str] | None) -> list[dict[str, str]]:
    """A table's topics in order, each its name, title and text: a Roundtable 2 topic by its name, as prompts.xml
    holds it now, or any other text as the topic itself. None given is the three Roundtable 2 topics; an empty list
    is no topics, a table that discusses its opening alone."""
    found: list[dict[str, str]] = []
    for one in (TOPICS if given is None else [str(one).strip() for one in given if str(one).strip()]):
        known = next((name for name in TOPICS if name.casefold() == one.casefold()), None)
        text = said(f'topic_{known}') if known else one
        found.append({'name': known or f'{len(found) + 1:02d}', 'title': title(text), 'text': text})
    return found


# ----------------------------------------------------------------------------------------------- roles

def role(given: str, what: str) -> dict[str, str]:
    """A synthesizer or a host, written as a seat is; seats.Refused when it cannot be one."""
    chosen, notices = seats.chosen([given])
    seat = chosen[0]
    if seat['kind'] == 'agent':
        raise seats.Refused(f'An outside agent seat cannot be the {what}: name an acp, OpenRouter or a2a seat.')
    return {**seat, 'name': names.base(seat), **({'notice': notices[0]} if notices else {})}


def roles(host: str | None, synthesizer: str | None) -> tuple[dict[str, str], dict[str, str], list[str]]:
    """The host and the synthesizer, and a notice for each whose model is checked only when its session starts. The
    host is the one named, else acp:codex/gpt-6 when Codex offers it; the synthesizer the one named, else the host."""
    if host and host.strip():
        hosted = role(host.strip(), 'host')
    else:
        try:
            hosted = role(HOST, 'host')
        except seats.Refused as error:
            raise seats.Refused(f'No host was named and {HOST} cannot host here ({error}); name one with host=.') \
                from None
    made = role(synthesizer.strip(), 'synthesizer') if synthesizer and synthesizer.strip() else dict(hosted)
    notices = list(dict.fromkeys(one.pop('notice') for one in (hosted, made) if 'notice' in one))
    return hosted, made, notices


# ----------------------------------------------------------------------------------------------- ideas and rankings

def ideas(text: str) -> list[dict[str, str]]:
    """The ideas a synthesis names, in its order, numbered I1 and on whatever numbers it wrote: each line that
    starts with an id begins an idea, `name: substance`, and the lines after it, up to the next, continue it."""
    found: list[dict[str, str]] = []
    for line in text.splitlines():
        matched = IDEA.match(line)
        if matched:
            rest = matched.group(2).replace('**', '').strip()
            split = re.search(r':| — | – | - ', rest)
            name, summary = (rest[:split.start()], rest[split.end():]) if split else (rest, '')
            found.append({'id': f'I{len(found) + 1}', 'name': name.strip(' *'), 'summary': summary.strip()})
        elif found and line.strip():
            found[-1]['summary'] = (found[-1]['summary'] + ' ' + line.strip()).strip()
    return [{**one, 'id': f'I{at}'} for at, one in enumerate((one for one in found if one['name']), 1)]


def ranked(text: str, ids: Sequence[str]) -> tuple[list[str] | None, str | None]:
    """A seat's ranking read from its reply: the ids it names, in order, when they are every idea exactly once;
    else None and what was wrong, in the words the repair request gives it."""
    given = [f'I{int(one)}' for one in ID.findall(text)]
    if not given:
        return None, said('ranking_empty')
    problems: list[str] = []
    missing = [one for one in ids if one not in given]
    repeated = list(dict.fromkeys(one for one in given if given.count(one) > 1))
    unknown = list(dict.fromkeys(one for one in given if one not in ids))
    if missing:
        problems.append(said('ranking_missing', ids=', '.join(missing)))
    if repeated:
        problems.append(said('ranking_repeated', ids=', '.join(repeated)))
    if unknown:
        problems.append(said('ranking_unknown', ids=', '.join(unknown)))
    return (None, '; '.join(problems)) if problems else (given, None)


def three(ranking: Sequence[str] | None, stage: str, listed: Sequence[Mapping[str, Any]]) -> str:
    """The line naming a seat's top or bottom three, by id and name, for its explanation's prompt; empty when its
    ranking could not be read."""
    if not ranking:
        return ''
    chosen = list(ranking[:3]) if stage == 'top_three' else list(ranking[-3:])
    named = {str(one['id']): str(one['name']) for one in listed}
    return said('stage_yours', ideas=', '.join(f'{one} ({named.get(one, "")})' for one in chosen))


def borda(listed: Sequence[Mapping[str, Any]], rankings: Sequence[Sequence[str] | None]) -> dict[str, Any]:
    """A Borda count over the rankings that were read, labeled derived: of n ideas, first earns n - 1 points and last
    none. Nothing in the protocol depends on it; the raw rankings are the record."""
    ids = [str(one['id']) for one in listed]
    counted = [list(one) for one in rankings if one]
    points = {one: 0 for one in ids}
    for ranking in counted:
        for at, one in enumerate(ranking):
            if one in points:
                points[one] += len(ids) - 1 - at
    return {'derived': True,
            'label': 'Derived: a Borda count over the rankings that were read (of n ideas, first earns n - 1 points, '
                     'last none). The raw rankings are the record; nothing in the protocol depends on this.',
            'rankings_counted': len(counted), 'points': points,
            'order': sorted(ids, key=lambda one: (-points[one], ids.index(one)))}
