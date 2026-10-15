"""The ledger's command line: add an entry, or show a month's totals."""
from pathlib import Path

from .amounts import format_cents, parse_amount
from .report import month_totals
from .store import Entry, Ledger

USAGE = 'usage: ledger add <date> <category> <amount> | ledger month <yyyy-mm>'


def main(args: list[str], folder: Path | None = None) -> int:
    ledger = Ledger((folder or Path.cwd()) / 'ledger.json')
    if len(args) == 4 and args[0] == 'add':
        _, day, category, amount = args
        ledger.append(Entry(day=day, category=category, cents=parse_amount(amount)))
        print(f'Added {format_cents(parse_amount(amount))} to {category} on {day}.')
        return 0
    if len(args) == 2 and args[0] == 'month':
        totals = month_totals(ledger.entries(), args[1])
        for category, cents in sorted(totals.items()):
            print(f'{category:<12} {format_cents(cents):>10}')
        print(f'{"total":<12} {format_cents(sum(totals.values())):>10}')
        return 0
    print(USAGE)
    return 2
