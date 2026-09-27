"""Counts and lists as a person reads them, PROJ-025: every string a person reads is written properly."""
from __future__ import annotations

from typing import Any

NUMBERS = ('no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine')


def count(number: int) -> str:
    """A number as a person reads it: no, one, two, ... nine, then 10 and up in digits."""
    return NUMBERS[number] if 0 <= number < len(NUMBERS) else str(number)


def counted(number: int, noun: str, plural: str) -> str:
    """A count with its noun: no metaforms, one metaform, two metaforms, 12 metaforms."""
    return f'{count(number)} {noun if number == 1 else plural}'


def odd_refs_notice(odd: list[Any]) -> str:
    """The notice for refs that are not a key and a value, both text, kept in a record's extra, STORE-012."""
    return (f'A ref is a key and a value, both text; {count(len(odd))} {"was" if len(odd) == 1 else "were"} not, '
            'and kept in the extra under refs.')


def listed(names: tuple[str, ...]) -> str:
    """Names as a person reads them: main, main and fresh, main, fresh and draft."""
    return names[0] if len(names) == 1 else f'{", ".join(names[:-1])} and {names[-1]}'
