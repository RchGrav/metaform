"""The version is CalVer during development: the date and the count of updates made that day, BASE-020."""
import datetime
import re
import tomllib
from pathlib import Path

import pytest

from metaform import __version__

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('BASE-020')]
ROOT = Path(__file__).resolve().parents[1]


def test_the_version_is_a_date_and_the_count_of_updates_made_that_day():
    found = re.fullmatch(r'(\d{4})\.(\d{1,2})\.(\d{1,2})\.(\d+)', __version__)
    assert found, __version__
    year, month, day, count = (int(part) for part in found.groups())
    assert datetime.date(year, month, day) >= datetime.date(2026, 9, 28)  # a real date, no earlier than the format
    assert count >= 1                                                     # counted from 1
    assert __version__ == f'{year}.{month}.{day}.{count}'                 # no leading zeros, as packaging writes it


def test_the_package_declares_the_version_the_chassis_reports():
    declared = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    assert declared == __version__


def test_the_stamp_gives_the_date_of_the_update_and_its_place_in_that_day():
    from scripts import calver
    day = datetime.date(2026, 9, 28)
    assert calver.version(day, earlier_that_day=0) == '2026.9.28.1'
    assert calver.version(day, earlier_that_day=30) == '2026.9.28.31'
    assert calver.version(datetime.date(2027, 1, 5), earlier_that_day=2) == '2027.1.5.3'
