"""The prompt review, STORE-044: every authored prompt says what it is for, and a saved edit leaves a packet an agent
can apply without the session that made it."""
from __future__ import annotations

import dataclasses

import pytest

from metaform import prompt_review

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('STORE-044')]


def test_every_authored_prompt_has_a_purpose_comment_above_it(home):
    authored = [entry for entry in prompt_review.catalog() if entry.owner != 'store']
    assert authored
    assert [entry.key for entry in authored if not entry.purpose] == []


def test_a_saved_edit_writes_a_packet_naming_where_the_text_lives_and_what_replaces_it(home, tmp_path):
    found = next(entry for entry in prompt_review.catalog() if entry.key == 'chassis:work_reminder')
    # A copy of its file, so the shipped one is never written; a bare < cannot be written into it exactly.
    copy = tmp_path / 'prompts.xml'
    copy.write_text(found.source.read_text(encoding='utf-8'), encoding='utf-8')
    entry = dataclasses.replace(found, source=copy)
    folder = tmp_path / 'edits'
    packet = prompt_review.save_edit(entry, 'A new reminder < now.', folder)
    text = packet.read_text(encoding='utf-8')
    assert copy.read_text(encoding='utf-8') == found.source.read_text(encoding='utf-8')
    for held in (str(entry.source), '<work_reminder>', entry.text, 'A new reminder < now.'):
        assert held in text
    assert packet.name in (folder / 'README.md').read_text(encoding='utf-8')


def test_a_saved_edit_is_written_between_its_tags_in_a_writable_prompts_file(home, tmp_path):
    source = tmp_path / 'prompts.xml'
    source.write_text('<prompts>\n<!-- A greeting. -->\n<greet>Hello <name/>.</greet>\n<other>Kept.</other>\n</prompts>\n',
                      encoding='utf-8')
    entry = prompt_review.Entry('demo', 'greet', source, 'Hello <name/>.', 'A greeting.')
    assert prompt_review.save_edit(entry, 'Hi <name/>.', tmp_path / 'edits') == source
    assert source.read_text(encoding='utf-8') == \
        '<prompts>\n<!-- A greeting. -->\n<greet>Hi <name/>.</greet>\n<other>Kept.</other>\n</prompts>\n'
    assert not (tmp_path / 'edits').exists()
