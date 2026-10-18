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
    context,
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
    assert len(roles) == 17
    assert {one.name for one in roles} >= {'triage', 'gc', 'functionality', 'role_creator'}
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    for definition in roles:
        resolved = resolve_agent_role(project_folder, definition.name)
        assert not resolved['problems'], resolved
        assert [one['name'] for one in resolved['components']] == list(definition.prompts)
        assert all(one['actual_version_id'] and one['rendered_fingerprint'] for one in resolved['components'])
    assert os.environ['METAFORM_ROLE'] == 'worker'
    prompts.save_prompt('dispatch:system', 'User register retained. <mascot/>')
    triage = resolve_agent_role(project_folder, 'triage', bindings={'mascot': 'Chirping.'})
    assert triage['components'][-1]['name'] == 'dispatch:system'
    assert 'User register retained.' in triage['components'][-1]['text']


def test_generated_role_has_no_xml_and_retains_source_and_version_history(project_folder):
    ctx = context('agents', project_folder)
    first = service(project_folder).publish(ctx, 'protocol_auditor', 'Inspect protocol transitions.',
                                            'Read caller context & report <actual> transitions.',
                                            {'commission': 'gc-1', 'requester': 'worker-2'})
    assert not first['problems']
    assert first['components'][-1]['text'] == 'Read caller context & report <actual> transitions.'
    name = first['components'][-1]['name']
    assert prompt_files.shipped('agents', name.partition(':')[2]) is None
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
    saved, _ = prompt_files.save_edit('orchestration:gc', 'Custom GC duty retaining delivery ownership.')
    changed = resolve_agent_role(project_folder, 'gc')
    due = prepare_agent_context(project_folder, 'gc-context', changed['components'])
    assert [one['name'] for one in due['components']] == ['orchestration:gc']
    assert due['components'][0]['actual_version_id'] == saved.version_id
    bad = prompts.save_prompt('orchestration:gc', '<unclosed>')
    fallback = resolve_agent_role(project_folder, 'gc')
    assert not fallback['problems'] and fallback['notices']
    duty = fallback['components'][-1]
    assert duty['actual_version_id'] == original['components'][-1]['actual_version_id']
    assert duty['selected_version_id'] == bad.version_id and duty['problems']
    assert duty['rendered_fingerprint'] == original['components'][-1]['rendered_fingerprint']
    assert prepare_agent_context(project_folder, 'gc-context', fallback['components'])['components'] == []
    actual, _ = read_resource(project_folder, 'metaform://role/gc', 'fallback-recipient')
    assert duty['text'] in actual and '<unclosed>' not in actual


def test_memory_instruction_body_is_shared_between_inline_and_resource(project_folder):
    from metaform.modules.mcp.server import memory_text
    text = memory_text(project_folder)
    assert text
    component = prompt_files.component('memory:instructions', text)
    record_agent_context(project_folder, 'memory-context', [component], channel='first_turn')
    second, _ = read_resource(project_folder, 'metaform://memory', 'memory-context')
    assert text not in second
    receipt = prepare_agent_context(project_folder, 'memory-context', [component])['previous']['memory:instructions']
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
