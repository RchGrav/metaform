"""Typed responsibility/expertise resources preserve real registry bodies, snapshots and receipts."""
from __future__ import annotations

import asyncio
import copy
import json
import os
from pathlib import Path

import pytest

from metaform import prompt_files
from metaform.data import Node, prompts
from metaform.module import context, prepare_agent_context, record_agent_context, resolve_agent_role
from metaform.modules.agents import roles as role_inventory
from metaform.modules.agents.roles import SERVICE
from metaform.modules.mcp import server
from metaform.modules.orchestration.state import SERVICE as ASSIGNMENTS
from metaform.modules.orchestration.state import new_assignment, own
from tests.storekit import small_map

pytestmark = pytest.mark.kind('simulation')


def read(folder, uri, session):
    return asyncio.run(server.read_resource_text(folder, uri, session=session))


def unavailable(folder, uri, session):
    try:
        result = read(folder, uri, session)
    except server.Missing:
        return
    assert result is None, f'{uri} exposed a body from the wrong namespace'


def definition_state(ctx):
    with ctx.require_store().tables(write=False) as tx:
        definitions = list(tx.rows('definitions', by=('name',), limit=0).results)
        history = list(tx.rows('definition_history', by=('name', 'seq'), limit=0).results)
    versions = {row['name']: [one.to_dict() if hasattr(one, 'to_dict') else one
                              for one in prompts.prompt_versions(row['prompts'][-1])] for row in definitions}
    return copy.deepcopy((definitions, history, versions))


def test_all_39_specialties_have_their_own_namespace_without_rewriting_duties_or_history(store, project_folder):
    small_map(store)
    ctx = context('agents', project_folder, project='proj')
    artifact = Path(__file__).resolve().parents[5] / 'docs/reviews/context-management-role-inventory.json'
    exported = json.loads(artifact.read_text(encoding='utf-8'))
    entries = exported['specialties']
    assert len(entries) == 39
    for index, entry in enumerate(entries):
        SERVICE.publish(ctx, entry['name'], entry['purpose'],
                        f'Specialist duty {index}: preserve its exact entity and version.')
    chosen = SERVICE.resolve(ctx, entries[0]['name'])
    duty = chosen['components'][-1]['name']
    edited, _ = prompt_files.save_edit(duty, 'Selected specialist duty. Preserve <literal> & source identity.')
    before = definition_state(ctx)
    roster = SERVICE.specialists(ctx)
    assert {one['name'] for one in roster} == {one['name'] for one in entries}
    assert all(one['uri'] == f'metaform://specialist/{one["name"]}' for one in roster)
    assert all(set(one) == {'name', 'purpose', 'uri', 'provider'} for one in roster)
    public = role_inventory(ctx)
    assert len(public['authored']) == 23
    assert {one['role'] for one in public['authored']}.isdisjoint(one['name'] for one in entries)
    assert all(one['uri'].startswith('metaform://role/') for one in public['authored'])
    assert {one['name']: one for one in public['specialists']} == {one['name']: one for one in roster}
    for entry in entries:
        name = entry['name']
        resolved = resolve_agent_role(project_folder, name)
        explicit = resolve_agent_role(project_folder, f'metaform://specialist/{name}')
        assert not resolved['missing'] and not resolved['problems']
        assert explicit == resolved and resolved['uri'] == f'metaform://specialist/{name}'
        wrong = resolve_agent_role(project_folder, f'metaform://role/{name}')
        assert (wrong['missing'] or wrong['problems']) and not wrong['components']
    for entry in public['authored']:
        name = entry['role']
        resolved = resolve_agent_role(project_folder, name)
        assert resolved['uri'] == f'metaform://role/{name}'
        wrong = resolve_agent_role(project_folder, f'metaform://specialist/{name}')
        assert (wrong['missing'] or wrong['problems']) and not wrong['components']
    selected = SERVICE.resolve(ctx, entries[0]['name'])['components'][-1]
    assert selected['text'] == 'Selected specialist duty. Preserve <literal> & source identity.'
    assert selected['actual_version_id'] == selected['selected_version_id'] == edited.version_id
    assert definition_state(ctx) == before


def test_specialist_resources_share_existing_component_receipts_and_reject_role_exposure(
        store, project_folder, monkeypatch):
    small_map(store)
    ctx = context('agents', project_folder, project='proj')
    published = SERVICE.publish(ctx, 'receipt_expert', 'Inspect exact resource delivery.', 'A distinct specialist body.')
    assert published['uri'] == 'metaform://specialist/receipt_expert'
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    monkeypatch.setenv('METAFORM_AUTHORED_ROLE', 'metaform://role/gc')
    # An earlier inline delivery has the same prompt components regardless of the resource namespace spelling.
    record_agent_context(project_folder, 'retained-context', published['components'], channel='legacy_assignment')
    same = read(project_folder, published['uri'], 'retained-context')
    assert same and 'A distinct specialist body.' not in same[0]
    fresh = read(project_folder, published['uri'], 'fresh-context')
    assert fresh and 'A distinct specialist body.' in fresh[0]
    assert not prepare_agent_context(project_folder, 'fresh-context', published['components'])['components']
    repeated = read(project_folder, published['uri'], 'fresh-context')
    assert repeated and 'A distinct specialist body.' not in repeated[0]
    unavailable(project_folder, 'metaform://role/receipt_expert', 'old-role-reader')
    unavailable(project_folder, 'metaform://specialist/gc', 'wrong-specialist-reader')
    procedure = read(project_folder, 'metaform://role/gc', 'procedure-reader')
    assert procedure and 'You are the GC' in procedure[0]
    assert os.environ['METAFORM_AUTHORED_ROLE'] == 'metaform://role/gc'


@pytest.mark.parametrize('legacy_reference', [False, True])
def test_assigned_specialist_resource_keeps_exact_pinned_version_after_selected_edit(
        store, project_folder, legacy_reference):
    small_map(store)
    ctx = context('agents', project_folder, project='proj')
    pinned = SERVICE.publish(ctx, 'pinned_expert', 'Preserve candidate-specific expertise.',
                             'PINNED specialist duty: retain the exact assignment source.')
    canonical_uri = 'metaform://specialist/pinned_expert'
    if legacy_reference:
        pinned = {**pinned, 'uri': 'metaform://role/pinned_expert'}
    source = pinned['components'][-1]['name']
    task = 'Keep this contribution unchanged.'
    work = store.add_work(Node('element', 'code.timer.kitchen'), None, task=task)
    assigned_ctx = context('orchestration', project_folder, project='proj', session='assigned-specialist')
    with own(assigned_ctx).tables() as tx:
        assigned = new_assignment(tx, work, 'pinned_expert', task=task, result=task,
                                  locations=[{'kind': 'element', 'id': work.node_id, 'address': work.address}],
                                  session=assigned_ctx.session)
        tx.update('assignments', {'assignment_id': assigned['assignment_id']},
                  {'authored_role_uri': pinned['uri'], 'role_snapshot': pinned})
        before = copy.deepcopy(tx.get('assignments', {'assignment_id': assigned['assignment_id']}))
    selected, _ = prompt_files.save_edit(source, 'CURRENT specialist duty for later assignments.')
    body = read(project_folder, 'metaform://specialist/pinned_expert', assigned_ctx.session)
    assert body and 'PINNED specialist duty' in body[0] and 'CURRENT specialist duty' not in body[0]
    assert not prepare_agent_context(project_folder, assigned_ctx.session, pinned['components'])['components']
    current = SERVICE.resolve(ctx, 'pinned_expert')
    assert current['components'][-1]['actual_version_id'] == selected.version_id
    other = read(project_folder, current['uri'], 'different-assignment')
    assert other and 'CURRENT specialist duty' in other[0] and 'PINNED specialist duty' not in other[0]
    expected = copy.deepcopy(before)
    expected['authored_role_uri'] = canonical_uri
    expected['role_snapshot']['uri'] = canonical_uri
    assert ASSIGNMENTS.assignment(assigned_ctx) == expected
