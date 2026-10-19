"""Direct ticket ownership, role version pinning and a bounded review loop."""
import pytest

from metaform.data import Node
from metaform.module import context
from metaform.modules.orchestration.state import SERVICE, own, service
from tests.storekit import small_map

pytestmark = pytest.mark.kind('simulation')


def test_triage_assigns_the_worker_without_taking_its_ticket_session(store, project_folder):
    small_map(store)
    work = store.add_work(Node('element', 'code.timer.kitchen'), None, task='Check the alarm.')
    ctx = context('orchestration', project_folder, project='proj', session='triage-request',
                  surface='mcp', nouns={'work': work.id, 'role': 'verifier'})
    assigned = SERVICE.claim(ctx)
    assert assigned['owner_session_id'] is None and assigned['state'] == 'queued'
    assert any(one['kind'] == 'launch' for one in SERVICE.pending(ctx, [work.id]))


def test_shared_role_creation_releases_waiters_without_resuming_stopped_work(store, project_folder):
    small_map(store)
    ctx = context('orchestration', project_folder, project='proj')
    assigned = []
    for task in ('Measure alarm timing.', 'Measure alarm volume.'):
        work = store.add_work(Node('element', 'code.timer.kitchen'), None, task=task)
        ctx.nouns.update(work=work.id, role='alarm_specialist')
        assigned.append(SERVICE.claim(ctx))
    first, second = assigned
    creator_id = first['role_request']['creator_assignment_id']
    assert second['role_request']['creator_assignment_id'] == creator_id
    SERVICE.stopped(ctx, work_id=first['work_id'], by='user')
    assert not SERVICE.assignment(ctx, assignment_id=creator_id)['stop']
    SERVICE.bind(ctx, creator_id, 'creator')
    publish = context('orchestration', project_folder, project='proj', session='creator', nouns={
        'request': first['role_request']['request_id'], 'duty': 'Measure the specified alarm behavior.'})
    SERVICE.publish_role(publish)
    assert SERVICE.assignment(ctx, work_id=first['work_id'])['state'] == 'stopped'
    assert SERVICE.assignment(ctx, work_id=second['work_id'])['state'] == 'queued'
    with own(ctx).tables(write=False) as tx:
        assert len(tx.rows('assignments', limit=0).results) == 3


def test_missing_root_role_continues_original_ticket_and_pins_duty(store, project_folder):
    small_map(store)
    ctx = context('orchestration', project_folder, project='proj')
    work = store.add_work(Node('element', 'code.timer.kitchen'), None, task='Verify alarm timing.')
    ctx.nouns.update(work=work.id, role='alarm_specialist')
    assigned = SERVICE.claim(ctx)
    request = assigned['role_request']
    assert assigned['state'] == 'waiting' and request['state'] == 'commissioned'
    creator = SERVICE.bind(ctx, request['creator_assignment_id'], 'creator')
    publish = context('orchestration', project_folder, project='proj', session='creator', nouns={
        'request': request['request_id'], 'duty': 'Measure alarm timing and return observations.'})
    result = SERVICE.publish_role(publish)
    assert result['assignment']['work_id'] == work.id
    bound = SERVICE.bind(ctx, assigned['assignment_id'], 'specialist')
    original = bound['role_snapshot']
    service(ctx, 'agent.role').publish(ctx, 'alarm_specialist', 'New revision.', 'New duty for future assignments.')
    rebound = SERVICE.bind(ctx, assigned['assignment_id'], 'resumed-specialist')
    assert rebound['role_snapshot'] == original
    from metaform.modules.mcp.server import assigned_role
    assert assigned_role(project_folder, bound['authored_role_uri'], 'resumed-specialist') == original
    assert creator['authored_role_uri'] == 'metaform://role/role_creator'
    with own(ctx).tables(write=False) as tx:
        assert len(tx.rows('assignments', limit=0).results) == 2


def test_review_reopens_canonical_ticket_without_a_recursive_chain(store, project_folder):
    small_map(store)
    ctx = context('orchestration', project_folder, project='proj')
    work = store.add_work(Node('element', 'code.timer.kitchen'), None, task='Keep selection while adjusting time.')
    ctx.nouns.update(work=work.id)
    assigned = SERVICE.claim(ctx)
    assert assigned['authored_role_uri'] == 'metaform://role/implementer'
    SERVICE.bind(ctx, assigned['assignment_id'], 'worker')
    SERVICE.returned(ctx, work.id, 'Implemented.', evidence=['Control test passed.'], state='delivered')
    review = SERVICE.assessment(ctx, assigned, {'summary': 'Review result.'}, 'one')
    SERVICE.returned(ctx, review['work_id'], 'Regression observed.', findings=[{
        'summary': 'Selection resets.', 'remediation': 'Preserve selection.', 'verify': 'Adjust time twice.'}])
    assert not store.ticket(work.id).work.done
    assert 'Adjust time twice.' in store.ticket(work.id).work.note
    assert SERVICE.assignment(ctx, work_id=work.id)['state'] == 'queued'
    SERVICE.bind(ctx, assigned['assignment_id'], 'repair')
    SERVICE.returned(ctx, work.id, 'Corrected.', evidence=['Repeated adjustment retains selection.'], state='delivered')
    with own(ctx).tables(write=False) as tx:
        assert len(tx.rows('assignments', limit=0).results) == 2
        assert len([one for one in tx.rows('transitions', limit=0).results if one['kind'] == 'assessment']) == 1
