"""Requested prompt changes merge against selected versions, preserving author register and immutable history."""
from __future__ import annotations

import dataclasses
import re
from concurrent.futures import ThreadPoolExecutor

import pytest

from metaform import prompt_files, prompt_review, skills
from metaform.data import prompts

pytestmark = pytest.mark.kind('fixture')


def source_of(name):
    owner, colon, component = name.partition(':')
    if not colon:
        source = prompt_files.shipped('skills', name)
        assert source is not None
        return prompt_files.rendered(source), 'text'
    if owner == 'skill':
        return skills.procedure(component), 'text'
    source = prompt_files.shipped(owner, component)
    assert source is not None
    return prompt_files.plain(source), 'xml'


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
    assert evidence['source']['baseline'] == '10e2984ea36231b474b197e30661712ff45e3765'
    # A later explicit user edit is the new selection even when it intentionally restores an earlier clause.
    latest = prompts.save_prompt(name, selected.text + '\nNewer user direction.', format=format)
    prompt_files.merge_selected_updates(name)
    assert prompts.prompt_version(name).version_id == latest.version_id


def test_new_context_fill_places_remain_operational_after_selected_merge(home):
    name = 'mcp:role_worker'
    current, format = source_of(name)
    seed_selected(name, before_of(name, current), format)
    selected = prompt_files.resolve(name, assignment='assignment actual-7', authored_role='metaform://role/verifier',
                                     categories='Actual enabled tools')
    assert 'assignment actual-7' in selected['text']
    assert 'metaform://role/verifier' in selected['text']
    assert 'Actual enabled tools' in selected['text']
    assert '<assignment' not in selected['text']


def test_ambiguous_or_unmatched_custom_selection_is_reported_and_not_changed(home):
    name = 'skills:lib_quality'
    current, format = source_of(name)
    old = before_of(name, current)
    _, selected = seed_selected(name, old + '\n' + old, format)
    actual = prompt_files.resolve(name)
    assert actual['actual_version_id'] == selected.version_id and not actual['problems']
    assert actual['notices'] and 'selected edit is retained' in actual['notices'][0]
    assert prompts.prompt_merges(name)[0]['state'] == 'conflict'
    assert len(prompts.prompt_versions(name)) == 2


def test_concurrent_resolvers_append_only_one_migration_version(home):
    name = 'skills:workflow-logic'
    current, format = source_of(name)
    seed_selected(name, before_of(name, current), format)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: prompt_files.resolve(name), range(8)))
    assert len({one['actual_version_id'] for one in results}) == 1
    assert len(prompts.prompt_versions(name)) == 3
    assert len(prompts.prompt_merges(name)) == 1


@pytest.mark.parametrize('name', ['mcp:role_worker', 'skill:workflow-builder', 'workflow-logic', 'metaform-tools'])
def test_explicit_user_edit_before_first_serving_stays_newer_than_shipped_migration(home, name):
    current, format = source_of(name)
    intentional = before_of(name, current) + '\nThis is an explicit newer instruction.'
    selected, _ = prompt_files.save_edit(name, intentional, format=format)
    actual = prompt_files.resolve(name)
    assert actual['actual_version_id'] == selected.version_id
    assert 'This is an explicit newer instruction.' in actual['text']
    assert len(prompts.prompt_versions(name)) == 2


@pytest.mark.parametrize(('name', 'library'), [('workflow-logic', 'lib_workflow'), ('metaform-tools', 'lib_metaform')])
def test_legacy_selected_skill_section_reaches_the_actual_library_and_deployment(home, name, library):
    current, format = source_of(name)
    _, selected = seed_selected(name, before_of(name, current), format)
    actual = skills.library(library)
    integrated = prompts.prompt_version(name)
    assert current in actual and 'User-authored register stays exact.' in actual
    assert integrated.parent_id == selected.version_id and integrated.prompt_id == selected.prompt_id
    files = skills.deployment_files(skills.get('workflow-builder'))
    assert 'User-authored register stays exact.' in files[f'references/{library}.md'].decode('utf-8')


@pytest.mark.parametrize('name', ['workflow-logic', 'skill:workflow-builder'])
def test_prompt_review_explicit_edit_uses_the_same_selected_version_gate(home, tmp_path, name):
    current, format = source_of(name)
    _, selected = seed_selected(name, before_of(name, current), format)
    entries = prompt_review.catalog()
    found = next(one for one in entries if one.key == name or one.key == f'store:{name}')
    if name.startswith('skill:'):
        copy = tmp_path / 'procedure.axiom'
        copy.write_text(current, encoding='utf-8')
        found = dataclasses.replace(found, source=copy)
    intentional = selected.text + '\nNewer explicit review direction.'
    prompt_review.save_edit(found, intentional)
    latest = prompts.prompt_version(name)
    actual = prompt_files.served_text(name, current)
    assert actual == intentional
    assert latest.number == 4 and latest.parent_id == prompts.prompt_version(name, 3).version_id
    assert prompts.prompt_version(name).version_id == latest.version_id


@pytest.mark.parametrize('historical_format', ['text', 'xml'])
def test_selected_skill_procedure_is_the_file_deployed_and_read_by_the_harness(home, historical_format):
    name = 'skill:workflow-builder'
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
