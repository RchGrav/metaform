"""Map construction uses exact canonical grammar, with separately versioned operation guidance."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest

from metaform import prompt_files
from metaform.module import context
from metaform.modules.map import guidance

pytestmark = pytest.mark.kind('fixture')


def test_construction_guide_preserves_served_grammar_and_original_xml_examples(project_folder):
    actual = guidance.construction_component(context('map', project_folder))
    axiom = (guidance.INTAKE / 'intake.axiom').read_bytes().decode('utf-8')
    xml = (guidance.INTAKE / 'intake.xml').read_bytes().decode('utf-8')
    start = axiom.index('@CONSTRAINT:')
    assert axiom[start:axiom.index('@CONDITION (INTAKE_STATUS)', start)].strip() in actual['text']
    for marker, following in (('@CONDITION (NS_VALID)', '@CONDITION (CQU_VALID)'),
                              ('@CONDITION (CQU_VALID)', '@CONDITION (ROLE_ASSIGN)'),
                              ('@CONDITION (ROLE_ASSIGN)', '@CONDITION (STATE_MARK)')):
        start = axiom.index(marker)
        assert axiom[start:axiom.index(following, start)].strip() in actual['text']
    start = xml.index('<namespace_rules>')
    assert xml[start:xml.index('</namespace_rules>', start) + len('</namespace_rules>')] in actual['text']
    assert 'ASD-STE100' in actual['text']
    for declaration in ('{Roots}', '{Roles}', '{Purpose_Types}', '{IFD}'):
        assert next(line for line in axiom.splitlines() if line.lstrip().startswith(declaration)) in actual['text']
    for term in ('OP', 'EF', 'RE', 'PE', 'CQU'):
        assert f'<concept term="{term}"' in actual['text']
    assert 'code.engine.game.platformer' in actual['text'] and 'code.engine.game.fps' in actual['text']
    assert actual['source']['canonical']['sha256'] == hashlib.sha256(axiom.encode()).hexdigest()
    assert actual['source']['reference']['sha256'] == hashlib.sha256(xml.encode()).hexdigest()
    assert actual['rendered_fingerprint'] == hashlib.sha256(actual['text'].encode()).hexdigest()


def test_selected_operation_wrapper_retains_exact_canonical_source_and_provenance(project_folder):
    first = guidance.construction_component(context('map', project_folder))
    source = prompt_files.shipped('map', 'construction_guide')
    assert source is not None
    selected, notices = prompt_files.save_edit(guidance.NAME,
        prompt_files.plain(source) + '\nCurrent operation-specific reasoning remains available.')
    assert not notices
    actual = guidance.construction_component(context('map', project_folder))
    assert actual['actual_version_id'] == actual['selected_version_id'] == selected.version_id
    assert actual['source']['wrapper']['kind'] == 'selected_edit'
    assert actual['source']['canonical'] == first['source']['canonical']
    assert actual['source']['reference'] == first['source']['reference']
    assert actual['text'].endswith('Current operation-specific reasoning remains available.')
    assert actual['rendered_fingerprint'] != first['rendered_fingerprint']


def test_canonical_excerpt_changes_refresh_guide_identity_without_copying_rules(project_folder, tmp_path, monkeypatch):
    copied = Path(tmp_path / 'canonical')
    copied.mkdir()
    for name in ('intake.axiom', 'intake.xml'):
        (copied / name).write_bytes((guidance.INTAKE / name).read_bytes())
    monkeypatch.setattr(guidance, 'INTAKE', copied)
    first = guidance.construction_component(context('map', project_folder))
    path = copied / 'intake.axiom'
    path.write_text(path.read_text().replace('@CONDITION (NS_VALID)',
                                           '@CONDITION (NS_VALID) // source revision', 1))
    actual = guidance.construction_component(context('map', project_folder))
    assert '// source revision' in actual['text']
    assert actual['source']['canonical']['sha256'] != first['source']['canonical']['sha256']
    assert actual['actual_version_id'] == first['actual_version_id']  # the wrapper did not change
    assert actual['rendered_fingerprint'] != first['rendered_fingerprint']


def test_cli_and_explicit_resource_read_share_complete_guide_and_queue_only_delivery(run, project_folder):
    from metaform.modules.mcp.server import read_resource_text

    ctx = context('map', project_folder, session='guide-reader', surface='mcp')
    expected = guidance.construction_component(ctx)
    assert ctx.context_receipts == []
    assert guidance.guide(ctx) == expected['text']
    assert len(ctx.context_receipts) == 1
    assert ctx.context_receipts[0]['component'] == expected
    assert run('map', 'guide', cwd=project_folder).stdout.strip() == expected['text']
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
