"""How a roundtable's turns read, BASE-066: to a seat on its turn, to the head agent as each lands, in the review and
in the record the report is written from. Every word is a prompt of `resources/prompts.xml`, MCP-031.

A turn that entered, an accepted submission or a comment, reads as its text alone. A vetoed submission reads as its
verdict: the seat, Jev's four questions each with its noul, and the link that returns the text, so every seat sees
why it was left out and can read it if it chooses, MCP-039.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from importlib import resources
from typing import Any

from metaform import prompt_files

from .store import nouls

LIMIT = 512  # the most characters a seat's submission holds: one point a turn
PACKAGE = resources.files(__name__.rpartition('.')[0])


def said(name: str, **fills: Any) -> str:
    """The module's prompt `name` with its places filled."""
    return prompt_files.required(PACKAGE, name, **{key: str(value) for key, value in fills.items()})


def turn(number: int) -> str:
    return f'T{number:02d}'


def link(discussion: int, number: int) -> str:
    return f'metaform://roundtable/discussion{discussion}/submission{number}'


def who(row: Mapping[str, Any]) -> str:
    """Who a turn is credited to: its seat by the name it goes by at the table (its id, on a turn recorded before
    seats had names), the person for a comment, or the head agent for a comment by its name (the head agent, on one
    recorded before it had one)."""
    kind = row['kind']
    if kind == 'person':
        return said('name_person')
    if kind == 'head':
        return str(row.get('name') or said('name_head'))
    return str(row.get('name') or row['seat'])


def entered(row: Mapping[str, Any]) -> bool:
    """Whether the turn entered the discussion: an accepted submission or a comment."""
    return bool(row['accepted']) or row['kind'] in ('person', 'head')


def entry(row: Mapping[str, Any]) -> str:
    """One turn as every seat sees it: the text that entered, or the verdict on a vetoed submission."""
    number, discussion = int(row['number']), int(row['discussion'])
    if entered(row):
        return said('turn_entry', turn=turn(number), seat=who(row), text=row['text'])
    if row['kind'] == 'none':
        return said('verdict_none', turn=turn(number), seat=who(row), reason=row['reason'] or '')
    if row['over512']:
        return said('verdict_over', turn=turn(number), seat=who(row), limit=LIMIT, link=link(discussion, number))
    values = nouls(row) or [0.0] * 4
    return said('verdict', turn=turn(number), seat=who(row), new=f'{values[0]:.2f}', valuable=f'{values[1]:.2f}',
                relevant=f'{values[2]:.2f}', keep=f'{values[3]:.2f}', link=link(discussion, number))


def tidy(text: str) -> str:
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def seat_view(opening: str, rows: Sequence[Mapping[str, Any]], first: bool) -> str:
    """What a seat receives on its turn: on its first, the opening and every turn before its own; on each later turn,
    only the turns since its last reply. The limit closes it, and nothing else is said."""
    turns = '\n\n'.join(entry(row) for row in rows)
    if first:
        return tidy(said('seat_first', opening=opening, turns=turns, limit=LIMIT))
    return tidy(said('seat_next', turns=turns or said('nothing_since'), limit=LIMIT))


def chair_message(discussion: Mapping[str, Any], row: Mapping[str, Any]) -> str:
    """One turn as the head agent receives it in its own session: a vetoed one with its verdict and its text."""
    named = f'{discussion["number"]} ({discussion["address"]})'
    if entered(row) or row['kind'] == 'none':
        return said('chair_turn', discussion=named, entry=entry(row))
    return said('chair_vetoed', discussion=named, verdict=entry(row), text=row['text'])


def status_word(row: Mapping[str, Any]) -> str:
    if row['kind'] in ('person', 'head'):
        return said('status_comment')
    if row['kind'] == 'none':
        return said('status_none')
    if row['over512']:
        return said('status_over')
    return said('status_kept') if row['accepted'] else said('status_vetoed')


def review(discussion: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], keep: float) -> str:
    """The full review, metaform://roundtable/discussion<N>/review: what the four questions are and the array's
    order, then every submission in short form, its turn, seat, whether it was kept, its array and its link."""
    lines = [said('review_intro', discussion=discussion['number'], address=discussion['address'],
                  subject=discussion['subject'], keep=f'{keep:.2f}')]
    for row in rows:
        values = nouls(row)
        array = '[' + ', '.join(f'{value:.2f}' for value in values) + ']' if values else '[]'
        lines.append(said('review_line', turn=turn(int(row['number'])), seat=who(row), status=status_word(row),
                          array=array, link=link(int(row['discussion']), int(row['number']))))
    return '\n'.join(lines) + '\n'


def record(discussion: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> str:
    """The whole record the report is written from: the opening, then every turn with its status and its text."""
    lines = [said('record_opening', opening=discussion['opening'])]
    lines += [said('record_entry', turn=turn(int(row['number'])), seat=who(row), status=status_word(row),
                   text=row['text'] or row['reason'] or '') for row in rows]
    return said('report', address=discussion['address'], record='\n\n'.join(lines))


def slug(text: str, words: int = 6) -> str:
    """A file-name subject: the first words of the text, lowercase, joined by hyphens."""
    found = re.findall(r'[a-z0-9]+', text.lower())[:words]
    return '-'.join(found) or 'discussion'
