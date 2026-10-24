"""Map guidance is editable instruction text, independent of intake prompt markup."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest

from metaform import prompt_files
from metaform.module import context
from metaform.modules.map import guidance

pytestmark = pytest.mark.kind('fixture')


def test_guide_does_not_read_or_parse_intake_instruction_files(project_folder, monkeypatch):
    first = guidance.construction_component(context('map', project_folder))
    read_bytes, read_text = Path.read_bytes, Path.read_text

    def guarded_bytes(path):
        if path.name == 'intake.xml':
            pytest.fail('Map guidance must not read or parse the intake instruction body.')
        return read_bytes(path)

    def guarded_text(path, *args, **kwargs):
        if path.name == 'intake.xml':
            pytest.fail('Map guidance must not read or parse the intake instruction body.')
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_bytes', guarded_bytes)
    monkeypatch.setattr(Path, 'read_text', guarded_text)
    actual = guidance.construction_component(context('map', project_folder))
    assert actual['text'] == first['text']
    assert actual['actual_version_id'] == first['actual_version_id']
    assert actual['rendered_fingerprint'] == first['rendered_fingerprint']


def test_selected_guide_edits_are_opaque_and_retain_their_selected_version(project_folder):
    first = guidance.construction_component(context('map', project_folder))
    edited = 'Use the supplied approach. <unclosed> & {prompt}\nNo required headings or method phases.'
    selected, notices = prompt_files.save_edit(guidance.NAME, edited)
    assert not notices
    actual = guidance.construction_component(context('map', project_folder))
    assert actual['actual_version_id'] == actual['selected_version_id'] == selected.version_id
    assert actual['text'] == edited
    assert actual['rendered_fingerprint'] == hashlib.sha256(edited.encode()).hexdigest()
    assert actual['rendered_fingerprint'] != first['rendered_fingerprint']


def test_editing_the_intake_task_does_not_rewrite_or_break_map_guidance(project_folder):
    from metaform.modules import tasks

    first = guidance.construction_component(context('map', project_folder))
    ctx = context('tasks', project_folder, nouns={'name': 'intake'})
    intake = tasks.definition(ctx)
    edited = 'Revised intake instructions with no XML sections. <malformed> & {prompt}\n'
    prompt_files.save_edit(intake['component']['name'], edited)
    assert tasks.definition(ctx)['instructions'] == edited
    actual = guidance.construction_component(context('map', project_folder))
    assert actual['text'] == first['text']
    assert actual['actual_version_id'] == first['actual_version_id']
    assert actual['rendered_fingerprint'] == first['rendered_fingerprint']


def test_cli_and_explicit_resource_read_share_complete_guide_and_queue_only_delivery(run, project_folder):
    from metaform.modules.mcp.server import read_resource_text

    ctx = context('map', project_folder, session='guide-reader', surface='mcp')
    expected = guidance.construction_component(ctx)
    assert ctx.context_receipts == []
    assert guidance.guide(ctx) == expected['text']
    assert len(ctx.context_receipts) == 1
    assert ctx.context_receipts[0]['component'] == expected
    assert run('map', 'guide', cwd=project_folder).stdout.rstrip('\n') == expected['text'].rstrip('\n')
    read = asyncio.run(read_resource_text(project_folder, guidance.URI, session='other-reader'))
    assert read is not None and read[0] == expected['text']


@pytest.mark.parametrize('tool,operation,construction', [
    ('map_refine', None, True), ('map_promote', None, True),
    ('map_knowledge', 'create', True), ('map_knowledge', 'add-element', True),
    ('map_knowledge', 'add-join', True), ('map_knowledge', 'add-item', True),
    ('map_where', None, False), ('map_joins', None, False), ('map_work', 'read', False),
])
def test_construction_reference_applies_to_construction_not_ordinary_reads(project_folder, tool, operation, construction):
    actual = guidance.instructions(context('map', project_folder), tool, operation)
    assert bool(actual) is construction
    if construction:
        assert actual[0]['name'] == guidance.NAME and actual[0]['read'] == {'uri': guidance.URI}
