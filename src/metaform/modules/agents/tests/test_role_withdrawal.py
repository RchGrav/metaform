"""Removed procedural identities stay absent while chosen expertise and historical evidence survive."""
from __future__ import annotations

import asyncio

import pytest

from metaform import prompt_files
from metaform.module import context, resolve_agent_role
from metaform.modules.agents.migration import upgrade_tables
from metaform.modules.agents.roles import SERVICE
from metaform.modules.mcp import server

pytestmark = pytest.mark.kind('simulation')

REMOVED = ('investigator', 'requirements', 'interviewer', 'specialist', 'implementer', 'verifier',
           'reviewer', 'integrator', 'designer', 'synthesizer', 'dogfood', 'release')


@pytest.mark.parametrize('name', REMOVED)
def test_removed_roles_have_neither_registration_nor_shipped_duty(project_folder, name):
    resolved = resolve_agent_role(project_folder, name)
    assert resolved['missing'] and not resolved['components']
    assert prompt_files.shipped('orchestration', name) is None
    with pytest.raises(server.Missing):
        asyncio.run(server.read_resource_text(project_folder, f'metaform://role/{name}', session='absent-role'))


def test_upgrade_withdraws_live_roles_and_injected_duty_without_rewriting_history(project_folder):
    ctx = context('agents', project_folder)
    published = SERVICE.publish(ctx, 'alarm_engineer', 'Work on alarms.', 'Preserve the selected alarm behavior.')
    with ctx.require_store().tables() as tx:
        original = tx.get('definitions', {'name': 'alarm_engineer'})
        history = tx.rows('definition_history', limit=0).results
        stale = ['orchestration:common', 'orchestration:specialist', original['prompts'][-1]]
        tx.update('definitions', {'name': 'alarm_engineer'}, {'prompts': stale})
        tx.update('role_sources', {'name': 'alarm_engineer', 'provider': 'agents'}, {'prompts': stale})
        for name in REMOVED:
            tx.insert('definitions', {**original, 'name': name})
            tx.insert('role_sources', {'name': name, 'provider': 'orchestration',
                                      'purpose': 'Withdrawn duty.', 'prompts': [f'prompt.orchestration:{name}']})
        upgrade_tables(tx, 4)
        upgrade_tables(tx, 4)  # Retrying the migration does not damage retained definitions.
        assert [row['name'] for row in tx.rows('definitions', limit=0).results] == ['alarm_engineer']
        assert [row['name'] for row in tx.rows('role_sources', limit=0).results] == ['alarm_engineer']
        assert tx.rows('definition_history', limit=0).results == history
    resolved = resolve_agent_role(project_folder, 'alarm_engineer')
    assert not resolved['problems']
    assert [one['name'] for one in resolved['components']] == list(original['prompts'])
    assert resolved['components'][-1]['actual_version_id'] == published['version_id']
