"""The retired organization exposes historical records without an execution surface."""
from __future__ import annotations

import pytest

from metaform import loader
from metaform.data import Store
from metaform.module import Stop, context, provided, surface
from metaform.modules import tasks
from metaform.modules.orchestration.records import TABLES

pytestmark = pytest.mark.kind('fixture')


def test_discovery_exposes_history_without_roles_or_automatic_execution(project_folder):
    discovered = loader.discover()
    assert not [(item.id, item.problem) for item in discovered if item.problem]
    organization = next(module for module in surface(project_folder) if module.id == 'orchestration')
    assert {verb.name for verb in organization.verbs} == {'history'}
    assert organization.verbs[0].effect == 'read'
    assert organization.subscriptions == ()
    assert organization.provides == ()
    assert organization.resources == ()
    assert provided(project_folder, 'agent.roles') == []
    assert provided(project_folder, 'agent.role') == []
    assert provided(project_folder, 'orchestration') == []
    assert not {'commission', 'delegate', 'claim'} & {verb.name for verb in organization.verbs}


def historical_assignment(identifier, work, role):
    declaration = TABLES.table('assignments')
    values = {}
    for column in declaration.columns:
        if column.required and column.default is None:
            values[column.name] = {} if column.kind == 'json' else f'historical-{column.name}'
    values.update(assignment_id=identifier, work_id=work, authored_role_uri=f'metaform://role/{role}',
                  task='Preserve this existing assignment.', requested_result='Historical evidence.',
                  mode='autonomous', state='working', role_snapshot={'name': role, 'text': 'Historical body.'},
                  created='2026-10-20T10:00:00Z', updated='2026-10-20T10:00:00Z')
    return values


def test_history_reads_existing_assignment_rows_without_mutation_or_launch(project_folder, monkeypatch):
    store = Store('proj', module='orchestration')
    store.add_base('historical-map')
    with store.tables() as tx:
        tx.insert('assignments', historical_assignment('historic-gc', 'historic-work-a', 'gc'))
        tx.insert('assignments', historical_assignment('historic-triage', 'historic-work-b', 'triage'))
    with store.tables(write=False) as tx:
        before = [dict(row) for row in tx.rows('assignments', limit=0).results]

    def no_launch(*args, **kwargs):
        pytest.fail('Reading historical records must not execute a task or start an agent.')

    from metaform.modules.tasks import runtime
    monkeypatch.setattr(runtime.Lifecycle, 'assign', no_launch)
    monkeypatch.setattr(runtime, 'transport', no_launch)
    organization = next(module for module in surface(project_folder) if module.id == 'orchestration')
    history = next(verb for verb in organization.verbs if verb.name == 'history')
    result = history.run(context('orchestration', project_folder))
    assert result == {'assignments': before}
    filtered = history.run(context('orchestration', project_folder, nouns={'work': 'historic-work-b'}))
    assert filtered == {'assignments': [row for row in before if row['work_id'] == 'historic-work-b']}
    missing = history.run(context('orchestration', project_folder, nouns={'work': 'absent-work'}))
    assert missing == {'assignments': []}
    with store.tables(write=False) as tx:
        assert [dict(row) for row in tx.rows('assignments', limit=0).results] == before
        assert tx.rows('transitions', limit=0).results == ()
        assert tx.rows('sessions', limit=0).results == ()


@pytest.mark.parametrize('name', ['gc', 'triage'])
def test_retired_roles_cannot_resolve_or_reappear_as_task_definitions(project_folder, name):
    from metaform import module

    assert not hasattr(module, 'resolve_agent_role')
    assert not hasattr(module, 'AgentRoleDefinition')
    ctx = context('tasks', project_folder, nouns={'name': name})
    with pytest.raises(Stop, match=f'No task definition {name}'):
        tasks.definition(ctx)
    with pytest.raises(Stop, match=f'No task definition {name}'):
        tasks.assign(ctx)
    agent_module = next(module for module in surface(project_folder) if module.id == 'agents')
    assert not {'publish', 'resolve', 'roles', 'role', 'specialists'} & {verb.name for verb in agent_module.verbs}
