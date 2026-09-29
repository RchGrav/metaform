"""Stamp the version of the next update, BASE-020: the date and the count of updates made that day.

    python -m scripts.calver

The version is `YYYY.M.D.N`. N counts the commits of that day from 1, so the update about to be committed on a day
with 30 commits is `.31`. It is written into `pyproject.toml` and `src/metaform/__init__.py`, which the update then
carries. Run it before each commit.
"""
from __future__ import annotations

import datetime
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAMPED = ((ROOT / 'pyproject.toml', r'(?m)^version = "[^"]*"', 'version = "{}"'),
           (ROOT / 'src' / 'metaform' / '__init__.py', r"(?m)^__version__ = '[^']*'", "__version__ = '{}'"))


def version(day: datetime.date, *, earlier_that_day: int) -> str:
    return f'{day.year}.{day.month}.{day.day}.{earlier_that_day + 1}'


def commits_on(day: datetime.date) -> int:
    """The commits reachable from HEAD made on this day, by the committer's own clock."""
    dates = subprocess.run(['git', 'log', '--format=%cd', '--date=format-local:%Y-%m-%d'], cwd=ROOT, check=True,
                           capture_output=True, text=True).stdout.split()
    return dates.count(day.isoformat())


def stamp() -> str:
    today = datetime.date.today()
    stamped = version(today, earlier_that_day=commits_on(today))
    for path, pattern, line in STAMPED:
        text = path.read_text(encoding='utf-8')
        changed, count = re.subn(pattern, line.format(stamped), text, count=1)
        if count != 1:
            raise SystemExit(f'No version line in {path}.')
        path.write_text(changed, encoding='utf-8')
    return stamped


if __name__ == '__main__':
    print(stamp())
