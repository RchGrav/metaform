"""Specialist URI migration preserves pinned work and its delivery history."""
from __future__ import annotations

import copy
from dataclasses import replace

import pytest

from metaform import prompt_files
from metaform.data import Node, prompts
from metaform.module import Stop, context, provided
from metaform.modules.orchestration import routing
from metaform.modules.orchestration.state import migrate_specialist_references, new_assignment, own
from tests.storekit import small_map

pytestmark = pytest.mark.kind('fixture')


@pytest.fixture
def case(store, project_folder):
    small_map(store)
    ctx = context('orchestration', project_folder, project='proj')
    service = provided(project_folder, 'orchestration')[0][1]
    registry = provided(project_folder, 'agent.role')[0][1]
    specialist = registry.publish(ctx, 'namespace_expert', 'Inspect namespace identity.', 'Pinned original duty.')
    duty = specialist['components'][-1]
    selected, _ = prompt_files.save_edit(duty['name'], 'Current person-selected duty, preserved separately.')
    work = store.add_work(Node('element', 'code.timer.kitchen'), None, task='Keep this exact task.')
    return ctx, store, service, registry, specialist, selected, work


def test_full_migration_updates_only_operational_identity_and_preserves_pins_and_audit(case):
    ctx, store, service, _, specialist, selected, work = case
    old, new = 'metaform://role/namespace_expert', 'metaform://specialist/namespace_expert'
    pinned = {**specialist, 'uri': old}
    payload = {'authored_role_uri': old, 'role_snapshot': pinned, 'caller_text': old}
    with own(ctx).tables() as tx:
        row = new_assignment(tx, work, 'namespace_expert', task=work.task, result=work.task,
            locations=[{'kind': 'element', 'address': work.address}], return_to={'resource': old, 'kind': 'pm'})
        row = tx.update('assignments', {'assignment_id': row['assignment_id']}, {
            'role_snapshot': pinned, 'state': 'stopped', 'stop': {'by': 'person'},
            'result': {'source': old}, 'evidence': [{'reference': old}]})
        tx.insert('routing', {'work_id': work.id, 'state': 'selected', 'role': old,
                             'fingerprint': 'unchanged-source', 'updated': '2026-10-23T00:00:00Z'})
        tx.insert('role_requests', {'request_id': 'retained-publication',
            'caller_assignment_id': row['assignment_id'], 'gc_assignment_id': row['assignment_id'],
            'role': 'namespace_expert', 'purpose': 'Unchanged purpose.', 'task': work.task,
            'requested_result': work.task, 'context': {'caller_text': old}, 'functional_locations': [],
            'creator_assignment_id': row['assignment_id'], 'child_assignment_id': row['assignment_id'],
            'state': 'published', 'source': pinned, 'created': '2026-10-23T00:00:00Z'})
        for state in ('pending', 'delivered'):
            tx.insert('transitions', {'transition_id': state, 'assignment_id': row['assignment_id'],
                'work_id': work.id, 'kind': 'launch', 'state': state, 'payload': payload,
                'delivery': {'resource': old}, 'created': '2026-10-23T00:00:00Z', 'updated': '2026-10-23T00:00:00Z'})
        before = {table: list(tx.rows(table, limit=0).results)
                  for table in ('assignments', 'routing', 'role_requests', 'transitions', 'sessions')}
    before = copy.deepcopy(before)
    store.finish_work(work.id, 'The person cancelled this ticket.', outcome='cancelled')
    versions = prompts.prompt_versions(specialist['components'][-1]['name'])
    counts = migrate_specialist_references(ctx)
    assert counts == {'assignments': 1, 'routing': 1, 'role_requests': 1, 'pending_launches': 1}
    with own(ctx).tables(write=False) as tx:
        after = {table: list(tx.rows(table, limit=0).results) for table in before}
    expected = copy.deepcopy(before)
    expected['assignments'][0].update(authored_role_uri=new, role_snapshot={**pinned, 'uri': new})
    expected['routing'][0]['role'] = new
    expected['role_requests'][0]['source']['uri'] = new
    pending = next(item for item in expected['transitions'] if item['state'] == 'pending')
    pending['payload'].update(authored_role_uri=new, role_snapshot={**pinned, 'uri': new})
    assert after == expected
    assert prompts.prompt_versions(specialist['components'][-1]['name']) == versions
    assert prompts.prompt_version(specialist['components'][-1]['name']).version_id == selected.version_id
    assert service.assignment(ctx, work_id=work.id)['role_snapshot']['components'] == specialist['components']
    assert store.ticket(work.id).work.outcome == 'cancelled'
    assert not any(migrate_specialist_references(ctx).values())


def test_assignment_read_persists_old_pin_without_resolving_or_replacing_its_duty(case, monkeypatch):
    ctx, _, service, registry, specialist, selected, work = case
    old = 'metaform://role/namespace_expert'
    with own(ctx).tables() as tx:
        original = new_assignment(tx, work, 'namespace_expert', task=work.task, result=work.task,
            locations=[{'kind': 'element', 'address': work.address}])
        original = tx.update('assignments', {'assignment_id': original['assignment_id']},
                             {'role_snapshot': {**specialist, 'uri': old}})
    monkeypatch.setattr(registry, 'resolve', lambda *args, **kwargs: pytest.fail('Pinned migration must not resolve bodies'))
    migrated = service.assignment(ctx, work_id=work.id)
    assert migrated == {**original, 'authored_role_uri': specialist['uri'], 'role_snapshot': specialist}
    with own(ctx).tables(write=False) as tx:
        assert tx.get('assignments', {'assignment_id': original['assignment_id']}) == migrated
    assert prompts.prompt_version(specialist['components'][-1]['name']).version_id == selected.version_id
    # A canonical read does not even consult the registry metadata or open a migration write.
    monkeypatch.setattr(registry, 'specialists', lambda *args: pytest.fail('Canonical rows need no migration lookup'))
    assert service.assignment(ctx, work_id=work.id) == migrated


def test_existing_routing_identity_migrates_and_new_claim_and_ensure_keep_the_namespace(case):
    ctx, store, service, _, specialist, _, work = case
    with own(ctx).tables() as tx:
        tx.insert('routing', {'work_id': work.id, 'state': 'selected', 'role': 'metaform://role/namespace_expert',
                             'updated': '2026-10-23T00:00:00Z'})
    assert routing.selected(ctx, work.id) == specialist['uri']
    with own(ctx).tables(write=False) as tx:
        assert tx.get('routing', {'work_id': work.id})['role'] == specialist['uri']
    claimed = service.claim(replace(ctx, nouns={'work': work.id, 'role': specialist['uri']}))
    assert claimed['authored_role_uri'] == specialist['uri']
    second = store.add_work(Node('element', 'code.timer.kitchen'), None, task='Second exact task.')
    ensured = service.ensure(ctx, second.id, role='namespace_expert')
    assert ensured['authored_role_uri'] == specialist['uri']


def test_explicit_wrong_namespace_is_rejected_before_claiming_or_creating_work(case):
    ctx, _, service, _, _, _, work = case
    with pytest.raises(Stop, match='metaform://specialist/namespace_expert'):
        service.claim(replace(ctx, nouns={'work': work.id, 'role': 'metaform://role/namespace_expert'}))
    assert service.assignment(ctx, work_id=work.id) is None


def test_procedural_role_identity_and_unknown_request_names_remain_unchanged(case):
    ctx, _, service, registry, _, _, work = case
    procedural = registry.resolve(ctx, 'planner')
    with own(ctx).tables() as tx:
        row = new_assignment(tx, work, procedural['uri'], task=work.task, result=work.task,
            locations=[{'kind': 'element', 'address': work.address}])
        row = tx.update('assignments', {'assignment_id': row['assignment_id']}, {'role_snapshot': procedural})
    assert not any(migrate_specialist_references(ctx).values())
    assert service.assignment(ctx, work_id=work.id) == row
    assert row['authored_role_uri'] == 'metaform://role/planner'


@pytest.mark.parametrize('requested', ['metaform://role/namespace_expert', 'metaform://specialist/namespace_expert'])
def test_delegation_preserves_namespace_and_wrong_prefix_creates_no_commission(case, requested):
    ctx, _, service, registry, specialist, _, work = case
    with own(ctx).tables() as tx:
        parent = new_assignment(tx, work, 'gc', task=work.task, result=work.task,
            locations=[{'kind': 'element', 'address': work.address}], session='namespace-parent')
        tx.update('assignments', {'assignment_id': parent['assignment_id']}, {'role_snapshot': registry.resolve(ctx, 'gc')})
    caller = replace(ctx, session='namespace-parent', nouns={'role': requested, 'task': 'A bounded contribution.',
                                                           'key': 'namespace-delegation'})
    if requested.startswith('metaform://role/'):
        with pytest.raises(Stop, match='metaform://specialist/namespace_expert'):
            service.delegate(caller)
        with own(ctx).tables(write=False) as tx:
            assert len(tx.rows('assignments', limit=0).results) == 1
            assert not tx.rows('role_requests', limit=0).results
            assert not tx.rows('transitions', limit=0).results
            assert len(tx.rows('sessions', limit=0).results) == 1
    else:
        child = service.delegate(caller)
        assert child['authored_role_uri'] == specialist['uri']
        assert child['return_to']['assignment_id'] == parent['assignment_id']


def test_retried_published_request_reuses_the_old_pin_and_new_uri_without_starting_work(case):
    ctx, store, service, registry, specialist, selected, work = case
    creator_work = store.add_work(Node('element', 'code.timer.kitchen'), None, task='Previously published expertise.')
    old = 'metaform://role/namespace_expert'
    pinned = {**specialist, 'uri': old}
    with own(ctx).tables() as tx:
        child = new_assignment(tx, work, 'namespace_expert', task=work.task, result=work.task,
            locations=[{'kind': 'element', 'address': work.address}])
        child = tx.update('assignments', {'assignment_id': child['assignment_id']}, {
            'role_snapshot': pinned, 'state': 'stopped', 'stop': {'by': 'person'}})
        creator = new_assignment(tx, creator_work, 'facilitator', task=creator_work.task, result='Reusable expertise.',
            locations=child['functional_locations'], session='publication-creator')
        tx.update('assignments', {'assignment_id': creator['assignment_id']}, {
            'role_snapshot': registry.resolve(ctx, 'facilitator'), 'state': 'returned',
            'result': {'published_role': {'uri': old}}})
        tx.insert('role_requests', {'request_id': 'published-retry', 'caller_assignment_id': child['assignment_id'],
            'gc_assignment_id': child['assignment_id'], 'role': 'namespace_expert', 'purpose': specialist['purpose'],
            'task': work.task, 'requested_result': work.task, 'context': {'publication': {'source': 'created'}},
            'functional_locations': child['functional_locations'], 'creator_assignment_id': creator['assignment_id'],
            'child_assignment_id': child['assignment_id'], 'state': 'published', 'source': pinned,
            'created': '2026-10-23T00:00:00Z'})
        before_sessions = list(tx.rows('sessions', limit=0).results)
    result = service.publish_role(replace(ctx, session='publication-creator', nouns={'request': 'published-retry'}))
    assert result['role'] == specialist
    assert result['assignment'] == {**child, 'authored_role_uri': specialist['uri'], 'role_snapshot': specialist}
    with own(ctx).tables(write=False) as tx:
        assert len(tx.rows('assignments', limit=0).results) == 2
        assert not tx.rows('transitions', limit=0).results
        assert list(tx.rows('sessions', limit=0).results) == before_sessions
    assert prompts.prompt_version(specialist['components'][-1]['name']).version_id == selected.version_id
