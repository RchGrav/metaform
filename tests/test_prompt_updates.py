"""Requested prompt changes merge against selected versions, preserving author register and immutable history."""
from __future__ import annotations

import dataclasses
import re
from concurrent.futures import ThreadPoolExecutor

import pytest

from metaform import prompt_files, prompt_review, skills
from metaform.data import prompts

pytestmark = pytest.mark.kind('fixture')


def authored_source(name):
    owner, component = prompt_files.split_address(name)
    colon = bool(owner)
    if not colon:
        source = prompt_files.shipped('skills', name)
        assert source is not None
        return prompt_files.rendered(source), 'text'
    if owner == 'skill':
        return skills.procedure(component), 'text'
    source = prompt_files.shipped(owner, component)
    assert source is not None
    return prompt_files.plain(source), 'xml'


def source_of(name):
    """An exact migration-target fixture, independent of later authored prompt refinements.

    Old migration records keep supporting the selected versions they were written for. Their replacement spans
    need not remain verbatim in today's source. Retain the current template and reconstruct only missing target
    spans in this isolated test fixture, so every historical old/new merge remains exercised.
    """
    current, format = authored_source(name)
    for edit in prompt_files.prompt_updates()[name]['edits']:
        if edit['new'] not in current:
            current = (current.replace(edit['old'], edit['new'], 1) if current.count(edit['old']) == 1
                       else current + '\n\n' + edit['new'])
    return current, format


def before_of(name, current):
    before = current
    for edit in reversed(prompt_files.prompt_updates()[name]['edits']):
        assert before.count(edit['new']) == 1, (name, edit)
        before = before.replace(edit['new'], edit['old'], 1)
    return before


def seed_selected(name, old, format, *, suffix='User-authored register stays exact.'):
    selected = old + '\n\n' + suffix
    declared = re.findall(r'<([\w.-]+)\s*/>', old)
    stored = prompt_files.encode(old, declared) if format == 'xml' else old
    original = prompts.shipped(name, format, stored)
    saved = prompts.save_prompt(name, prompt_files.encode(selected, declared) if format == 'xml' else selected,
                                format=format)
    return original, saved


@pytest.mark.parametrize('name', list(prompt_files.prompt_updates()))
def test_every_requested_source_merge_uses_selected_parent_and_preserves_register(home, name):
    current, format = source_of(name)
    before = before_of(name, current)
    original, selected = seed_selected(name, before, format)
    if format == 'text':
        served = prompt_files.served_text(name, current)
    else:
        served = prompt_files.resolve(name)['text']
    expected = current + '\n\nUser-authored register stays exact.'
    if format == 'xml':
        expected = prompt_files.rendered(prompt_files.encode(expected, re.findall(r'<([\w.-]+)\s*/>', current)))
    assert served == expected
    integrated = prompts.prompt_version(name)
    assert integrated.prompt_id == original.prompt_id == selected.prompt_id
    assert integrated.parent_id == selected.version_id and integrated.number == 3
    assert prompts.prompt_version(name, 2).text == selected.text
    evidence = prompts.prompt_merges(name)[0]
    assert evidence['state'] == 'applied'
    assert evidence['before_version_id'] == selected.version_id
    assert evidence['after_version_id'] == integrated.version_id
    assert evidence['source']['baseline'] == prompt_files.prompt_updates()[name]['baseline']
    # A later explicit user edit is the new selection even when it intentionally restores an earlier clause.
    latest = prompts.save_prompt(name, selected.text + '\nNewer user direction.', format=format)
    prompt_files.merge_selected_updates(name)
    assert prompts.prompt_version(name).version_id == latest.version_id


def test_new_context_fill_places_remain_operational_after_selected_merge(home):
    name = 'prompt.mcp:role_worker'
    current, format = source_of(name)
    seed_selected(name, before_of(name, current), format)
    selected = prompt_files.resolve(name, assignment='assignment actual-7', authored_role='metaform://role/planner',
                                     categories='Actual enabled tools')
    assert 'assignment actual-7' in selected['text']
    assert 'metaform://role/planner' in selected['text']
    assert 'Actual enabled tools' in selected['text']
    assert '<assignment' not in selected['text']


def test_ambiguous_or_unmatched_custom_selection_is_reported_and_not_changed(home):
    name = 'prompt.skills:lib_quality'
    current, format = source_of(name)
    old = before_of(name, current)
    _, selected = seed_selected(name, old + '\n' + old, format)
    actual = prompt_files.resolve(name)
    assert actual['actual_version_id'] == selected.version_id and not actual['problems']
    assert actual['notices'] and 'selected edit is retained' in actual['notices'][0]
    assert prompts.prompt_merges(name)[0]['state'] == 'conflict'
    assert len(prompts.prompt_versions(name)) == 2


def test_concurrent_resolvers_append_only_one_migration_version(home):
    name = 'prompt.skills:workflow-prompt'
    current, format = source_of(name)
    seed_selected(name, before_of(name, current), format)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: prompt_files.resolve(name), range(8)))
    assert len({one['actual_version_id'] for one in results}) == 1
    assert len(prompts.prompt_versions(name)) == 3
    assert len(prompts.prompt_merges(name)) == 1


@pytest.mark.parametrize('name', ['prompt.mcp:role_worker', 'prompt.skill.workflow-builder', 'prompt.skills:workflow-prompt', 'prompt.skills:metaform-tools'])
def test_explicit_user_edit_before_first_serving_stays_newer_than_shipped_migration(home, name):
    current, format = source_of(name)
    intentional = before_of(name, current) + '\nThis is an explicit newer instruction.'
    selected, _ = prompt_files.save_edit(name, intentional, format=format)
    actual = prompt_files.resolve(name)
    assert actual['actual_version_id'] == selected.version_id
    assert 'This is an explicit newer instruction.' in actual['text']
    assert len(prompts.prompt_versions(name)) == 2


@pytest.mark.parametrize(('name', 'library'), [('prompt.skills:workflow-prompt', 'lib_workflow'), ('prompt.skills:metaform-tools', 'lib_metaform')])
def test_legacy_selected_skill_section_reaches_the_actual_library_and_deployment(home, name, library):
    current, format = source_of(name)
    _, selected = seed_selected(name, before_of(name, current), format)
    actual = skills.library(library)
    integrated = prompts.prompt_version(name)
    assert current in actual and 'User-authored register stays exact.' in actual
    assert integrated.parent_id == selected.version_id and integrated.prompt_id == selected.prompt_id
    files = skills.deployment_files(skills.get('workflow-builder'))
    assert 'User-authored register stays exact.' in files[f'references/{library}.md'].decode('utf-8')


@pytest.mark.parametrize('name', ['prompt.skills:workflow-prompt', 'prompt.skill.workflow-builder'])
def test_prompt_review_explicit_edit_uses_the_same_selected_version_gate(home, tmp_path, name):
    current, format = source_of(name)
    seed_selected(name, before_of(name, current), format)
    entries = prompt_review.catalog()
    found = next(one for one in entries if one.key == name or one.key == f'store:{name}')
    copy = tmp_path / ('procedure.axiom' if name.startswith('prompt.skill.') else 'prompts.xml')
    copy.write_text(current if name.startswith('prompt.skill.') else found.source.read_text('utf-8'),
                    encoding='utf-8')
    found = dataclasses.replace(found, source=copy)
    intentional = prompt_files.readable(prompts.prompt_version(name)) + '\nNewer explicit review direction.'
    prompt_review.save_edit(found, intentional)
    latest = prompts.prompt_version(name)
    actual = (prompt_files.served_text(name, current) if name.startswith('prompt.skill.')
              else prompt_files.resolve(name)['text'])
    assert actual == intentional
    assert latest.number == 4 and latest.parent_id == prompts.prompt_version(name, 3).version_id
    assert prompts.prompt_version(name).version_id == latest.version_id


@pytest.mark.parametrize('historical_format', ['text', 'xml'])
def test_selected_skill_procedure_is_the_file_deployed_and_read_by_the_harness(home, historical_format):
    name = 'prompt.skill.workflow-builder'
    current, _ = source_of(name)
    old = before_of(name, current)
    prompts.shipped(name, 'text', old)
    selected = prompts.save_prompt(name, old + '\n\nAuthor register with literal <value> & context.',
                                   format=historical_format)
    sent = prompt_files.collect()
    try:
        loaded = skills.load('workflow-builder')
        files = skills.deployment_files(skills.get('workflow-builder'))
        read = skills.read('workflow-builder', 'references/procedure.axiom').strip()
    finally:
        prompt_files.release(sent)
    expected = current + '\n\nAuthor register with literal <value> & context.'
    assert loaded['procedure'] == files['references/procedure.axiom'].decode('utf-8').strip() == read == expected
    assert not sent  # artifact preparation has not claimed an agent received this duty
    integrated = prompts.prompt_version(name)
    assert integrated.prompt_id == selected.prompt_id and integrated.parent_id == selected.version_id
    sent = prompt_files.collect()
    try:
        assert expected in skills.served('workflow-builder')
    finally:
        prompt_files.release(sent)
    actual = next(one for one in sent if one.name == name)
    assert actual.version_id == integrated.version_id and actual.rendered_text == expected


@pytest.mark.parametrize('own_metadata', [False, True])
def test_update_metadata_uses_entry_baseline_with_manifest_fallback(tmp_path, monkeypatch, own_metadata):
    import json

    manifest = {'baseline': 'global-source', 'reviewed_baseline': 'global-review',
                'updates': [{'name': 'prompt.example:entry', 'id': 'fixture-update', 'edits': []}]}
    if own_metadata:
        manifest['updates'][0].update(baseline='entry-source', reviewed_baseline='entry-review')
    folder = tmp_path / 'resources'
    folder.mkdir()
    (folder / 'prompt_updates.json').write_text(json.dumps(manifest))
    prompt_files.prompt_updates.cache_clear()
    try:
        with monkeypatch.context() as patched:
            patched.setattr(prompt_files.resources, 'files', lambda _: tmp_path)
            actual = prompt_files.prompt_updates()['prompt.example:entry']
        assert actual['baseline'] == ('entry-source' if own_metadata else 'global-source')
        assert actual['reviewed_baseline'] == ('entry-review' if own_metadata else 'global-review')
    finally:
        prompt_files.prompt_updates.cache_clear()


@pytest.mark.parametrize('anchor_state', ['exact', 'missing', 'ambiguous'])
def test_memory_audit_merge_preserves_selected_source_and_records_conflicts_once(home, anchor_state):
    name = 'prompt.memory:instructions'
    update = prompt_files.prompt_updates()[name]
    prefix = 'Use the prepared functional knowledge. Preserve this exact newer retrieval instruction.'
    selected_text = prefix + '\n\n' + '\n\n'.join(edit['old'] for edit in update['edits'])
    if anchor_state == 'missing':
        selected_text = selected_text.replace(update['edits'][1]['old'], 'A different authored maintenance rule.')
    elif anchor_state == 'ambiguous':
        selected_text += '\n\n' + update['edits'][1]['old']
    original, selected = seed_selected(name, selected_text, 'xml', suffix='Bespoke register stays exact.')
    result = prompt_files.merge_selected_updates(name)
    assert result is not None
    assert result['source']['baseline'] == update['baseline']
    assert result['source']['reviewed_baseline'] == update['reviewed_baseline']
    assert prompts.prompt_version(name, selected.number).text == selected.text
    current = prompts.prompt_version(name)
    if anchor_state == 'exact':
        expected = prompt_files.plain(selected.text)
        for edit in update['edits']:
            expected = expected.replace(edit['old'], edit['new'], 1)
        assert result['state'] == 'applied'
        assert prompt_files.plain(current.text) == expected
        assert current.prompt_id == original.prompt_id and current.parent_id == selected.version_id
    else:
        assert result['state'] == 'conflict' and result['conflicts']
        assert current.version_id == selected.version_id and current.text == selected.text
    assert prompt_files.merge_selected_updates(name) == result
    assert len(prompts.prompt_merges(name)) == 1
    assert len(prompts.prompt_versions(name)) == (3 if anchor_state == 'exact' else 2)


def test_selected_migration_retains_fill_places_introduced_by_its_own_replacement(home, monkeypatch):
    name = 'prompt.dispatch:peer_note'
    _, selected = seed_selected(name, 'Earlier authored envelope.', 'xml')
    update = {'id': 'fixture-introduced-fill', 'source': 'fixture', 'baseline': 'entry-source',
              'reviewed_baseline': 'entry-review',
              'edits': [{'old': 'Earlier authored envelope.', 'new': 'Useful evidence: <new_context/>'}]}
    monkeypatch.setattr(prompt_files, 'prompt_updates', lambda: {name: update})
    actual = prompt_files.resolve(name, new_context='Exact candidate evidence.')
    assert actual['text'] == 'Useful evidence: Exact candidate evidence.\n\nUser-authored register stays exact.'
    integrated = prompts.prompt_version(name)
    assert 'new_context' in prompt_files.places(integrated.text)
    assert integrated.parent_id == selected.version_id
