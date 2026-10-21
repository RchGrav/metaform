"""Pages of list reads: each page is one index range read, resumed after the last key, STORE-005 and STORE-025."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from ..errors import StoreError
from .records import Page

LIMIT = 500
T = TypeVar('T')


def _cursor(row: Any) -> str:
    """The key a row of a page is resumed after, read from its `key` column."""
    return str(row['key'])


def paged(fetch: Callable[[str | None, int], list[Any]], build: Callable[[Any], T | None], limit: int,
          after: str | None, *, key: Callable[[Any], str] | None = None) -> Page[T]:
    """Fill one page from index range reads, skipping rows the build step leaves out."""
    keyed = key or _cursor
    results: list[T] = []
    cursor = after
    batch = limit if limit else LIMIT
    while True:
        rows = fetch(cursor, batch)
        for row in rows:
            cursor = keyed(row)
            built = build(row)
            if built is None:
                continue
            results.append(built)
            if limit and len(results) >= limit:
                return Page(tuple(results), cursor if fetch(cursor, 1) else None)
        if len(rows) < batch:
            return Page(tuple(results), None)


def row_cursor(after: str | None) -> int:
    """The number a page resumes after, for lists keyed by row or position; a cursor no page returned, such as an
    id, is the caller's error with its next step, not a crash."""
    text = '' if after is None else str(after)
    if text and not (text.isascii() and text.isdigit()):
        raise StoreError(f'{after!r} is not a cursor of this list: a cursor is the next a page of it returned.',
                         'read the list again without after, then pass the next it returns')
    return int(text or 0)


def sliced(values: tuple[T, ...], limit: int, after: str | None) -> Page[T]:
    """A page of a list already read whole: for the few reads allowed to read their whole table, STORE-005. Its
    cursor is the position the next page starts at."""
    start = row_cursor(after)
    if not limit:
        return Page(values[start:], None)
    end = start + limit
    return Page(values[start:end], str(end) if end < len(values) else None)
