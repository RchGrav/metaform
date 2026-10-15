"""A month's spending, totalled by category."""
from collections import defaultdict

from .store import Entry


def month_totals(entries: list[Entry], month: str) -> dict[str, int]:
    """Each category's total in whole cents for the month given as yyyy-mm."""
    totals: dict[str, int] = defaultdict(int)
    for entry in entries:
        if entry.day.startswith(month + '-'):
            totals[entry.category] += entry.cents
    return dict(totals)
