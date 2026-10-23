"""Provider resolution and context delivery exercised through the actual loader, store and MCP resource path."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys

import pytest

from metaform import prompt_files
from metaform.data import prompts
from metaform.module import (
    AgentRoleDefinition,
    advance_agent_context,
    agent_context_epoch,
    begin_agent_context_check,
    context,
    finish_agent_context_check,
    prepare_agent_context,
    provided,
    record_agent_context,
    resolve_agent_role,
)

pytestmark = pytest.mark.kind('fixture')


def service(folder):
    return provided(folder, 'agent.role')[0][1]


def read_resource(folder, uri, session):
    from metaform.modules.mcp.server import read_resource_text
    return asyncio.run(read_resource_text(folder, uri, session=session))


def test_native_responsibility_inventory_and_selected_identity(project_folder, monkeypatch):
    roles = [one for _, values in provided(project_folder, 'agent.roles') if isinstance(values, tuple) for one in values]
    assert len(roles) == 23
    assert any(role.name == 'roundtable_follow_through' for role in roles)
    assert {one.name for one in roles} >= {'triage', 'gc', 'functionality', 'facilitator', 'role_creator'}
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    for definition in roles:
        resolved = resolve_agent_role(project_folder, definition.name)
        assert not resolved['problems'], resolved
        assert [one['name'] for one in resolved['components']] == list(definition.prompts)
        assert all(one['actual_version_id'] and one['rendered_fingerprint'] for one in resolved['components'])
    assert os.environ['METAFORM_ROLE'] == 'worker'
    prompts.save_prompt('prompt.dispatch:system', 'User register retained. <mascot/>')
    triage = resolve_agent_role(project_folder, 'triage', bindings={'mascot': 'Chirping.'})
    assert triage['components'][-1]['name'] == 'prompt.dispatch:system'
    assert 'User register retained.' in triage['components'][-1]['text']


@pytest.mark.parametrize('role', ['interviewer', 'researcher', 'architect', 'planner', 'decomposer',
                                  'specialist', 'harsh_critic'])
def test_preparation_and_delivery_duties_resolve_as_role_resources(project_folder, role):
    resolved = resolve_agent_role(project_folder, role)
    assert not resolved['missing'] and not resolved['problems']
    body = read_resource(project_folder, f'metaform://role/{role}', f'read-{role}')[0]
    assert resolved['components'][-1]['text'] in body


def test_generated_role_has_no_xml_and_retains_source_and_version_history(project_folder):
    ctx = context('agents', project_folder)
    first = service(project_folder).publish(ctx, 'protocol_auditor', 'Inspect protocol transitions.',
                                            'Read caller context & report <actual> transitions.',
                                            {'commission': 'gc-1', 'requester': 'worker-2'})
    assert not first['problems']
    assert [one['name'] for one in first['components'][:2]] == [
        'prompt.orchestration:common', 'prompt.orchestration:specialist']
    assert first['components'][-1]['text'] == 'Read caller context & report <actual> transitions.'
    name = first['components'][-1]['name']
    assert prompt_files.shipped('agents', name.partition(':')[2]) is None
    # Existing definitions stored before shared Specialist composition gain it on their next resolution.
    with ctx.require_store().tables() as tx:
        tx.update('definitions', {'name': 'protocol_auditor'}, {'prompts': ['prompt.orchestration:common', name]})
    restored = resolve_agent_role(project_folder, 'protocol_auditor')
    assert restored['components'][1]['name'] == 'prompt.orchestration:specialist'
    second = service(project_folder).publish(ctx, 'protocol_auditor', 'Inspect protocol transitions.',
                                             'Read caller context and return state-transition evidence.',
                                             {'commission': 'gc-1', 'requester': 'worker-3'})
    assert second['version_id'] != first['version_id']
    assert len(prompts.prompt_versions(name)) == 2
    with ctx.require_store().tables(write=False) as tx:
        history = tx.rows('definition_history', {'name': 'protocol_auditor'}, limit=0).results
    assert {row['source']['requester'] for row in history} == {'worker-2', 'worker-3'}
    reused = resolve_agent_role(project_folder, 'metaform://role/protocol_auditor')
    assert reused['components'][-1]['actual_version_id'] == second['version_id']


def test_custom_provider_lifecycle_and_conflicts_are_visible(run, project_folder, monkeypatch):
    run('enable', 'hello', cwd=project_folder)
    resolved = resolve_agent_role(project_folder, 'hello.greeter')
    assert resolved['provider'] == 'hello' and not resolved['problems']
    run('disable', 'hello', cwd=project_folder)
    unavailable = resolve_agent_role(project_folder, 'hello.greeter')
    assert unavailable['missing'] is False and 'unavailable' in unavailable['problems'][0]
    assert resolve_agent_role(project_folder, 'never_registered')['missing'] is True
    namespace = service(project_folder).resolve.__func__.__globals__
    real = namespace['provided']

    def duplicate(folder, kind):
        held = real(folder, kind)
        return [*held, ('other', (AgentRoleDefinition('gc', 'Conflicting duty.', ('other:duty',)),))] \
            if kind == 'agent.roles' else held
    monkeypatch.setitem(namespace, 'provided', duplicate)
    conflict = resolve_agent_role(project_folder, 'gc')
    assert not conflict['missing'] and 'orchestration, other' in conflict['problems'][0]


def test_inline_and_mcp_share_receipts_and_role_inspection_does_not_rebind(project_folder, monkeypatch):
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    monkeypatch.setenv('METAFORM_AUTHORED_ROLE', 'metaform://role/gc')
    resolved = resolve_agent_role(project_folder, 'gc')
    prepared = prepare_agent_context(project_folder, 'worker-context', resolved['components'])
    assert len(prepared['components']) == 2
    # Merely preparing or resolving cannot consume the component for its recipient.
    assert len(prepare_agent_context(project_folder, 'worker-context', resolved['components'])['components']) == 2
    record_agent_context(project_folder, 'worker-context', prepared['components'], epoch=prepared['epoch'],
                         channel='first_turn')
    same, _ = read_resource(project_folder, 'metaform://role/gc', 'worker-context')
    assert 'You are the GC' not in same
    other, _ = read_resource(project_folder, 'metaform://role/verifier', 'worker-context')
    assert 'You are the Verifier' in other
    assert 'Work through the project\'s functional namespace.' not in other
    assert os.environ['METAFORM_AUTHORED_ROLE'] == 'metaform://role/gc'
    fresh, _ = read_resource(project_folder, 'metaform://role/verifier', 'replacement-context')
    assert 'Work through the project\'s functional namespace.' in fresh


def test_receipts_survive_a_separate_process_and_compaction_reopens_context(project_folder):
    resolved = resolve_agent_role(project_folder, 'gc')
    record_agent_context(project_folder, 'stable-runner', resolved['components'], channel='first_turn')
    script = '''import json,sys
from pathlib import Path
from metaform.module import resolve_agent_role,prepare_agent_context
p=Path(sys.argv[1]); c=resolve_agent_role(p,'gc')['components']
print(json.dumps(prepare_agent_context(p,'stable-runner',c)))
'''
    completed = subprocess.run([sys.executable, '-c', script, str(project_folder)], check=True,
                               capture_output=True, text=True, env=dict(os.environ))
    cross_process = json.loads(completed.stdout)
    assert cross_process['components'] == [] and len(cross_process['previous']) == 2
    context('dispatch', project_folder).publish('session.compacted', {'session': 'stable-runner'})
    assert agent_context_epoch(project_folder, 'stable-runner') == 1
    stale = record_agent_context(project_folder, 'stable-runner', resolved['components'], epoch=0)
    assert stale['recorded'] == 0 and stale['stale'] is True
    assert len(prepare_agent_context(project_folder, 'stable-runner', resolved['components'])['components']) == 2
    assert agent_context_epoch(project_folder, 'other-context') == 0
    assert advance_agent_context(project_folder, 'stable-runner', reason='unretained_recovery') == 2


def test_changed_duty_and_actual_fallback_versions(project_folder):
    original = resolve_agent_role(project_folder, 'gc')
    record_agent_context(project_folder, 'gc-context', original['components'])
    saved, _ = prompt_files.save_edit('prompt.orchestration:gc', 'Custom GC duty retaining delivery ownership.')
    changed = resolve_agent_role(project_folder, 'gc')
    due = prepare_agent_context(project_folder, 'gc-context', changed['components'])
    assert [one['name'] for one in due['components']] == ['prompt.orchestration:gc']
    assert due['components'][0]['actual_version_id'] == saved.version_id
    bad = prompts.save_prompt('prompt.orchestration:gc', '<unclosed>')
    fallback = resolve_agent_role(project_folder, 'gc')
    assert not fallback['problems'] and fallback['notices']
    duty = fallback['components'][-1]
    assert duty['actual_version_id'] == original['components'][-1]['actual_version_id']
    assert duty['selected_version_id'] == bad.version_id and duty['problems']
    assert duty['rendered_fingerprint'] == original['components'][-1]['rendered_fingerprint']
    assert prepare_agent_context(project_folder, 'gc-context', fallback['components'])['components'] == []
    actual, _ = read_resource(project_folder, 'metaform://role/gc', 'fallback-recipient')
    assert duty['text'] in actual and '<unclosed>' not in actual


def test_content_is_not_repeated_under_an_alias_or_after_version_reversion(project_folder):
    first = prompt_files.component('one', 'Retained instruction A.')
    second = prompt_files.component('one', 'Changed instruction B.')
    record_agent_context(project_folder, 'retained', [first])
    record_agent_context(project_folder, 'retained', [second])
    alias = {**first, 'name': 'alias', 'rendered_fingerprint': 'untrusted-label'}
    restored = prepare_agent_context(project_folder, 'retained', [first, alias])
    assert len(restored['components']) == 1 and 'Retained instruction A.' not in restored['text']
    assert restored['components'][0]['reference']['name'] == 'one'
    record_agent_context(project_folder, 'retained', restored['components'])
    assert prepare_agent_context(project_folder, 'retained', [first, alias])['components'] == []
    fresh = prepare_agent_context(project_folder, 'other', [first, alias])
    assert len(fresh['components']) == 1, 'Duplicate bodies in one batch also count once.'
    advance_agent_context(project_folder, 'retained')
    assert len(prepare_agent_context(project_folder, 'retained', [alias])['components']) == 1


def test_startup_marker_is_diagnostic_and_does_not_invalidate_delivered_context(project_folder):
    from metaform.modules.agents.roles import confirm_context
    instruction = prompt_files.component('prompt.test:duty', 'A retained duty that must not be dumped.')
    record_agent_context(project_folder, 'retained', [instruction])
    first = begin_agent_context_check(project_folder, 'retained')
    ctx = context('agents', project_folder, session='retained',
                  nouns={'checkpoint': first['checkpoint'], 'key': first['marker']})
    assert confirm_context(ctx)['confirmed']
    assert finish_agent_context_check(project_folder, 'retained', first['checkpoint'])['confirmed']
    resumed = begin_agent_context_check(project_folder, 'retained')
    assert resumed['marker'] == first['marker'] and resumed['checkpoint'] != first['checkpoint']
    assert finish_agent_context_check(project_folder, 'retained', first['checkpoint'])['stale']
    assert prepare_agent_context(project_folder, 'retained', [instruction])['components'] == []
    missed = finish_agent_context_check(project_folder, 'retained', resumed['checkpoint'])
    assert not missed['marker_match'] and missed['semantic_retention'] == 'unknown'
    assert missed['epoch'] == 0 and 'eligible' not in missed
    finish_agent_context_check(project_folder, 'retained', resumed['checkpoint'])
    assert agent_context_epoch(project_folder, 'retained') == 0, 'A missing marker does not prove content loss.'
    assert prepare_agent_context(project_folder, 'retained', [instruction])['components'] == []
    record_agent_context(project_folder, 'retained', [instruction])
    assert prepare_agent_context(project_folder, 'retained', [instruction])['components'] == []
    next_check = begin_agent_context_check(project_folder, 'retained')
    advance_agent_context(project_folder, 'retained')
    assert finish_agent_context_check(project_folder, 'retained', next_check['checkpoint'])['stale']
    assert agent_context_epoch(project_folder, 'retained') == 1, 'Compaction is not counted again as failed marker.'


def test_memory_instruction_body_is_shared_between_inline_and_resource(project_folder):
    from metaform.modules.mcp.server import memory_text
    text = memory_text(project_folder)
    assert text
    component = prompt_files.component('prompt.memory:instructions', text)
    record_agent_context(project_folder, 'memory-context', [component], channel='first_turn')
    second, _ = read_resource(project_folder, 'metaform://memory', 'memory-context')
    assert text not in second
    receipt = prepare_agent_context(project_folder, 'memory-context', [component])['previous']['prompt.memory:instructions']
    assert receipt['channel'] == 'first_turn'


def test_action_bindings_follow_surface_and_adapter_without_authored_role_permissions(run, project_folder, monkeypatch):
    from metaform.modules.mcp.server import action_bindings
    run('enable', 'dispatch', cwd=project_folder)
    run('enable', 'workflow', cwd=project_folder)
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    monkeypatch.setenv('METAFORM_AUTHORED_ROLE', 'metaform://role/verifier')
    bindings = action_bindings(context('mcp', project_folder), {'execution_role': 'worker', 'session_cancel': True})
    assert bindings['execution_role'] == 'worker'
    assert bindings['adapter']['session_cancel'] is True
    assert {'dispatch_peers', 'dispatch_note', 'agents_resolve', 'workflow_run'} <= set(bindings['tools'])
    assert 'workflow_handoff' not in bindings['tools']  # no workflow run has opened its continuation verbs
    declared = {f'{module.id}_{verb.name}' for module in __import__('metaform.module', fromlist=['surface']).surface(
        project_folder) for verb in module.verbs}
    assert all(name in declared or name.startswith('metaform_') for name in bindings['tools'])


def test_effective_manifest_reports_actual_source_selection_and_native_uncertainty(project_folder, tmp_path,
                                                                                  monkeypatch):
    from metaform.modules.agents import record, sent

    name = 'prompt.orchestration:gc'
    shipped = prompt_files.resolve(name)
    edited, _ = prompt_files.save_edit(name, 'Use my selected GC responsibility.')
    selected = prompt_files.resolve(name)
    assert selected['source']['kind'] == 'selected_edit'
    assert selected['source']['shipped_identity'] == shipped['source']['shipped_identity']
    assert selected['actual_version_id'] == edited.version_id
    malformed = prompts.save_prompt(name, '<unclosed>')
    fallback = prompt_files.resolve(name)
    assert fallback['source']['kind'] == 'fallback'
    assert fallback['selected_version_id'] == malformed.version_id
    assert fallback['actual_version_id'] == shipped['actual_version_id']
    trial = tmp_path / 'trial.xml'
    trial.write_text('<prompts><gc>Trial GC responsibility.</gc></prompts>')
    monkeypatch.setenv(prompt_files.TRIAL, str(trial))
    tried = prompt_files.resolve(name)
    assert tried['source']['kind'] == 'trial' and tried['source']['path'] == str(trial)
    assert tried['source']['shipped_identity'] == shipped['source']['shipped_identity']
    # Changing a selected store version does not change the observed outgoing snapshot.
    ctx = context('agents', project_folder, nouns={'session': 'manifest-session'})
    record({'session_id': 'manifest-session', 'prompts': [{**fallback, 'text': '',
            'version_id': fallback['actual_version_id'], 'delivery_path': 'acp_prompt', 'snapshot': True}]}, ctx)
    manifest = sent(ctx)
    effective = manifest['effective_instructions'][0]
    assert effective['selected_version_id'] == malformed.version_id
    assert effective['source']['kind'] == 'fallback' and effective['snapshot'] is True
    assert effective['delivery_path'] == 'acp_prompt'
    assert 'rendered_digest' in effective
    assert manifest['native_instructions']['loaded_sources'] == 'unknown'
    assert 'current semantic retention is unknown' in manifest['observation_scope']


def test_named_shown_history_does_not_infer_context_loss_from_age(project_folder):
    from metaform import home, shown

    shown.swap('long-episode', 'around:entry', {'purpose': 'Prepared grounding.'})
    shown.swap('long-episode', 'catalog:map', True)
    shown.swap('long-episode', 'guide:workflow', True)
    with home.chassis(write=True) as db:
        db.execute('UPDATE shown SET at=? WHERE session=?', ('2000-01-01T00:00:00Z', 'long-episode'))
    shown.swap('another-session', 'around:other', {})
    assert shown.peek('long-episode', 'around:entry') == {'purpose': 'Prepared grounding.'}
    # Observed compaction resets content hints, while host/discovery history has its separate scope.
    assert shown.forget('long-episode') == 1
    assert shown.peek('long-episode', 'around:entry') is None
    assert shown.peek('long-episode', 'catalog:map') is True
    assert shown.peek('long-episode', 'guide:workflow') is True


def test_generated_role_resolves_selected_override_without_rewriting_definition_history(project_folder):
    from metaform.modules.agents import override

    ctx = context('agents', project_folder)
    authored = service(project_folder)
    original = authored.publish(ctx, 'selected_auditor', 'Inspect transitions.', 'The original authored duty.')
    duty = original['components'][-1]
    saved = override(context('agents', project_folder, nouns={
        'name': duty['name'], 'text': 'Selected edit keeps <literal> & exact text.'}))
    selected = authored.resolve(ctx, 'selected_auditor')
    assert not selected['problems']
    active = selected['components'][-1]
    assert active['text'] == 'Selected edit keeps <literal> & exact text.'
    assert active['number'] == saved['revision']
    assert active['actual_version_id'] != duty['actual_version_id']
    assert active['source']['definition_version_id'] == original['version_id']
    with ctx.require_store().tables(write=False) as tx:
        definition = tx.get('definitions', {'name': 'selected_auditor'})
        history = tx.rows('definition_history', {'name': 'selected_auditor'}, limit=0).results
    assert definition['source']['duty'] == 'The original authored duty.'
    assert len(history) == 1 and history[0]['version_id'] == original['version_id']
    # Historical assignment snapshots retain the exact original component.
    assert duty['text'] == 'The original authored duty.'


def test_changed_role_references_require_consumed_body_and_accepted_notice(project_folder):
    ctx = context('agents', project_folder)
    authored = service(project_folder)
    original = authored.publish(ctx, 'changing_auditor', 'Inspect transitions.', 'Original instruction.')
    assert authored.changes(ctx, 'not-started', 'changing_auditor') == []
    record_agent_context(project_folder, 'consumer', original['components'])
    name = original['components'][-1]['name']
    first, _ = prompt_files.save_edit(name, 'First revised instruction.')
    references = authored.changes(ctx, 'consumer', 'changing_auditor')
    assert len(references) == 1 and references[0]['name'] == name
    assert references[0]['actual_version_id'] == first.version_id
    assert references[0]['read'] == {'tool': 'agents_resolve', 'arguments': {'name': 'changing_auditor'}}
    assert 'text' not in references[0]
    assert authored.changes(ctx, 'consumer', 'changing_auditor') == references
    second, _ = prompt_files.save_edit(name, 'Latest revised instruction.')
    authored.delivered_changes(ctx, 'consumer', references)
    current = authored.changes(ctx, 'consumer', 'changing_auditor')
    assert len(current) == 1 and current[0]['actual_version_id'] == second.version_id
    authored.delivered_changes(ctx, 'consumer', current)
    assert authored.changes(ctx, 'consumer', 'changing_auditor') == []
    # References cannot acknowledge any body, and a canonical role read still returns the exact new duty.
    body, _ = read_resource(project_folder, 'metaform://role/changing_auditor', 'consumer')
    assert 'Latest revised instruction.' in body
    assert authored.changes(ctx, 'consumer', 'changing_auditor') == []
    prompt_files.save_edit(name, 'Original instruction.')
    assert len(authored.changes(ctx, 'consumer', 'changing_auditor')) == 1


def test_equal_rendered_role_revision_does_not_create_a_change_reference(project_folder):
    ctx = context('agents', project_folder)
    authored = service(project_folder)
    resolved = authored.resolve(ctx, 'gc')
    record_agent_context(project_folder, 'consumer', resolved['components'])
    component = resolved['components'][-1]
    prompt_files.save_edit(component['name'], component['text'])
    assert authored.changes(ctx, 'consumer', 'gc') == []
    # Existing malformed selected XML continues to fall back honestly without inventing a changed body.
    bad = prompts.save_prompt(component['name'], '<unclosed>')
    fallback = authored.resolve(ctx, 'gc')['components'][-1]
    assert fallback['selected_version_id'] == bad.version_id
    assert fallback['source']['kind'] == 'fallback' and fallback['problems']
    assert authored.changes(ctx, 'consumer', 'gc') == []


def test_portable_generated_definition_fallback_is_honest_and_selected_store_still_wins(project_folder,
                                                                                      monkeypatch):
    from metaform.data import StoreError

    ctx = context('agents', project_folder)
    authored = service(project_folder)
    original = authored.publish(ctx, 'portable_auditor', 'Inspect portable state.', 'Portable original duty.')
    name = original['components'][-1]['name']
    selected, _ = prompt_files.save_edit(name, 'Use the available selected duty.')
    resolve = prompt_files.resolve

    def missing(reference, **fills):
        if reference == name:
            raise StoreError('The generated component is unavailable in this home.', 'inspect the prompt source')
        return resolve(reference, **fills)

    monkeypatch.setattr(prompt_files, 'resolve', missing)
    fallback = authored.resolve(ctx, 'portable_auditor')['components'][-1]
    assert fallback['text'] == 'Portable original duty.'
    assert fallback['source']['kind'] == 'definition_fallback'
    assert fallback['source']['definition_version_id'] == original['version_id']
    assert fallback['actual_version_id'] == original['version_id'] and fallback['selected_version_id'] is None
    assert fallback['problems'] and 'unavailable' in fallback['problems'][0]
    monkeypatch.setattr(prompt_files, 'resolve', resolve)
    available = authored.resolve(ctx, 'portable_auditor')['components'][-1]
    assert available['text'] == 'Use the available selected duty.'
    assert available['actual_version_id'] == available['selected_version_id'] == selected.version_id


def test_changed_source_reference_reaches_current_text_without_rebinding_pinned_assignment(project_folder, store):
    from metaform.data import Node
    from metaform.modules.mcp.server import answer, assigned_role
    from metaform.modules.orchestration.state import SERVICE
    from tests.storekit import small_map

    small_map(store)
    ctx = context('agents', project_folder, project='proj')
    authored = service(project_folder)
    original = authored.publish(ctx, 'pinned_source_auditor', 'Inspect source revisions.', 'Original pinned duty.')
    work = store.add_work(Node('element', 'code.timer.kitchen'), None, task='Inspect a source revision.')
    bound = SERVICE.ensure(context('orchestration', project_folder, project='proj'), work.id,
                           role='pinned_source_auditor', session_id='pinned-recipient', runner='pinned-runner')
    pinned = bound['role_snapshot']
    original_read, _ = read_resource(project_folder, original['uri'], 'pinned-runner')
    assert 'Original pinned duty.' in original_read
    duty = original['components'][-1]
    revised, _ = prompt_files.save_edit(duty['name'], 'New source text for explicit inspection.')
    references = authored.changes(ctx, 'pinned-runner', original['name'])
    assert len(references) == 1 and references[0]['actual_version_id'] == revised.version_id
    assert assigned_role(project_folder, original['uri'], 'pinned-runner') == pinned
    reference = references[0]['read']
    assert reference == {'tool': 'agents_resolve', 'arguments': {'name': original['name']}}
    result = asyncio.run(answer(project_folder, reference['tool'], reference['arguments'], session='pinned-runner'))
    assert result[0] is False, result[1]
    assert 'New source text for explicit inspection.' in json.dumps(result[2])
    assert result[2]['components'][-1]['actual_version_id'] == revised.version_id
    assert assigned_role(project_folder, original['uri'], 'pinned-runner') == pinned
    authored.delivered_changes(ctx, 'pinned-runner', references)
    assert authored.changes(ctx, 'pinned-runner', original['name']) == []
