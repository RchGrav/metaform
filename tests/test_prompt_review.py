"""The prompt review, STORE-044: every authored prompt says what it is for, and a saved edit leaves a packet an agent
can apply without the session that made it."""
from __future__ import annotations

import pytest

from metaform import prompt_review

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('STORE-044')]


def test_every_authored_prompt_has_a_purpose_comment_above_it(home):
    authored = [entry for entry in prompt_review.catalog() if entry.owner != 'store']
    assert authored
    assert [entry.key for entry in authored if not entry.purpose] == []


def test_a_saved_edit_writes_a_packet_naming_where_the_text_lives_and_what_replaces_it(home, tmp_path):
    entry = next(entry for entry in prompt_review.catalog() if entry.key == 'chassis:work_reminder')
    folder = tmp_path / 'edits'
    packet = prompt_review.save_edit(entry, 'A new reminder.', folder)
    text = packet.read_text(encoding='utf-8')
    for held in (str(entry.source), '<work_reminder>', entry.text, 'A new reminder.'):
        assert held in text
    assert packet.name in (folder / 'README.md').read_text(encoding='utf-8')
