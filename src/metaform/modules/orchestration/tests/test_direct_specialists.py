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
                  surface='mcp', nouns={'work': work.id, 'role': 'planner'})
    assigned = SERVICE.claim(ctx)
    assert assigned['owner_session_id'] is None and assigned['state'] == 'queued'
    assert not store.ticket(work.id).work.taken
    assert any(one['kind'] == 'launch' for one in SERVICE.pending(ctx, [work.id]))


@pytest.mark.parametrize('reserved', [False, True])
def test_sessionless_ensure_preserves_dispatch_ownership(store, project_folder, reserved):
    small_map(store)
    work = store.add_work(Node('element', 'code.timer.kitchen'), None, task='Check the alarm.')
    if reserved:
        store.take_work(work.id, by='dispatch starting runner')
    ctx = context('orchestration', project_folder, project='proj')
    assigned = SERVICE.ensure(ctx, work.id, role='planner', queue=True)
    assert assigned['owner_session_id'] is None and assigned['state'] == 'queued'
    assert store.ticket(work.id).work.taken_by == ('dispatch starting runner' if reserved else None)


def test_waiting_worker_keeps_its_ticket_in_doing(store, project_folder):
    small_map(store)
    work = store.add_work(Node('element', 'code.timer.kitchen'), None, task='Check the alarm.')
    ctx = context('orchestration', project_folder, project='proj', session='worker',
                  nouns={'work': work.id, 'role': 'planner', 'session': 'worker'})
    SERVICE.claim(ctx)
    ctx.nouns.update(state='waiting', summary='Waiting for timing evidence.')
    SERVICE.check_in(ctx)
    assert SERVICE.assignment(ctx, work_id=work.id)['state'] == 'waiting'
    assert store.ticket(work.id).work.column == 'doing'
    assert store.ticket(work.id).work.taken_by == 'worker'


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
    assert creator['authored_role_uri'] == 'metaform://role/facilitator'
    from metaform.module import Stop
    publish.nouns = {'role': 'harsh_critic', 'task': 'Review delivered work.',
                     'context': {'reviewed_work': work.id}}
    with pytest.raises(Stop, match='active review caller'):
        SERVICE.delegate(publish)
    with own(ctx).tables(write=False) as tx:
        assert len(tx.rows('assignments', limit=0).results) == 2


def test_review_reopens_canonical_ticket_without_a_recursive_chain(store, project_folder):
    from metaform import settings
    small_map(store)
    ctx = context('orchestration', project_folder, project='proj')
    work = store.add_work(Node('element', 'code.timer.kitchen'), None, task='Keep selection while adjusting time.')
    service(ctx, 'agent.role').publish(ctx, 'alarm_engineering', 'Countdown alarm systems.',
                                     'Verify timing and audible notification behavior.')
    settings.put('orchestration_reviews', 1, project_folder)
    ctx.nouns.update(work=work.id, role='alarm_engineering')
    assigned = SERVICE.claim(ctx)
    assert assigned['authored_role_uri'] == 'metaform://specialist/alarm_engineering'
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


@pytest.mark.parametrize('verdict', ['APPROVE', 'REJECT'])
def test_harsh_critic_returns_to_caller_and_routes_new_corrections(store, project_folder, verdict):
    from metaform.modules.orchestration.state import verb
    small_map(store)
    ctx = context('orchestration', project_folder, project='proj')
    verb(ctx, 'map', 'boards', op='add', name='timer-build')
    work = store.add_work(Node('element', 'code.timer.kitchen'), None, task='Keep selection while adjusting time.')
    verb(ctx, 'map', 'work', op='edit', id=work.id, board='timer-build')
    ctx.nouns.update(work=work.id, role='researcher')
    caller = SERVICE.claim(ctx)
    SERVICE.bind(ctx, caller['assignment_id'], 'caller')
    review_ctx = context('orchestration', project_folder, project='proj', session='caller', nouns={
        'role': 'harsh_critic', 'task': 'Review selection preservation.', 'key': 'review'})
    critic = SERVICE.delegate(review_ctx)
    assert critic['reviewed_assignment_id'] == caller['assignment_id']
    SERVICE.bind(ctx, critic['assignment_id'], 'critic')
    finding = {'title': 'Selection resets.', 'summary': 'Selection resets after adjustment.',
               'requirement': 'Preserve selection across repeated adjustments.', 'evidence': 'Second click resets.',
               'impact': 'Users lose current selection.', 'remediation': ['Retain selection across updates.'],
               'expected_behavior': 'Selection survives both adjustments.', 'verify': 'Adjust time twice.'}
    report_ctx = context('orchestration', project_folder, project='proj', session='critic', nouns={
        'state': 'returned', 'summary': verdict, 'findings': [finding] if verdict == 'REJECT' else [],
        'evidence': ['Observed actual controls.']})
    if verdict == 'REJECT':
        from metaform.module import Stop
        with pytest.raises(Stop, match='concrete findings'):
            SERVICE.returned(ctx, critic['work_id'], 'REJECT')
        assert not store.ticket(critic['work_id']).work.done
    result = SERVICE.check_in(report_ctx)
    corrections = result.get('findings_filed') or []
    assert len(corrections) == (1 if verdict == 'REJECT' else 0)
    if corrections:
        correction = store.ticket(corrections[0]).work
        assert correction.id != work.id and not correction.done
        assert all(value in correction.task for value in [finding['requirement'], finding['expected_behavior'],
                                                         finding['evidence'], finding['verify']])
        map_store = context('map', project_folder, project='proj').require_store()
        with map_store.tables(write=False) as tx:
            assert tx.get('after', {'work_id': correction.id})['works'] == [work.id]
            assert tx.get('ticket_settings', {'work_id': correction.id})['board'] == 'timer-build'
        assignment = SERVICE.assignment(ctx, work_id=correction.id)
        assert assignment['state'] == 'waiting'
        assert assignment['return_to']['assignment_id'] == caller['assignment_id']
        with own(ctx).tables(write=False) as tx:
            request = tx.rows('role_requests', {'caller_assignment_id': assignment['assignment_id']}, limit=0).results[0]
            facilitator = tx.get('assignments', {'assignment_id': request['creator_assignment_id']})
        assert facilitator['authored_role_uri'] == 'metaform://role/facilitator'
    repeated = SERVICE.check_in(report_ctx)
    assert repeated.get('findings_filed') == result.get('findings_filed')
    pending = SERVICE.pending(ctx)
    assert any(one['kind'] == 'send' and one['assignment_id'] == caller['assignment_id']
               and one['payload']['sender_assignment_id'] == critic['assignment_id'] for one in pending)
    assert store.ticket(work.id).work.done is None


def test_facilitator_critic_reviews_delivered_ticket_and_keeps_correction_return(store, project_folder, monkeypatch):
    from metaform.module import Stop
    from metaform.modules.orchestration.state import verb
    from metaform.modules.orchestration.tests.test_orchestration import Transport
    small_map(store)
    ctx = context('orchestration', project_folder, project='proj')
    actual = Transport(capacity=8)
    namespace = SERVICE.drain.__func__.__globals__
    original = namespace['provided']
    monkeypatch.setitem(namespace, 'provided', lambda folder, kind: [('dispatch', actual)]
                        if kind == 'orchestration.transport' else original(folder, kind))
    actual.running.add('facilitator')
    commission = store.add_work(Node('element', 'code.timer.kitchen'), None, task='Assign alarm expertise.')
    caller = SERVICE.ensure(ctx, commission.id, role='facilitator', session_id='facilitator')
    verb(ctx, 'map', 'boards', op='add', name='delivered-board')
    delivered = store.add_work(Node('element', 'code.timer.kitchen'), None, task='Preserve alarm selection.')
    verb(ctx, 'map', 'work', op='edit', id=delivered.id, board='delivered-board')
    built = SERVICE.ensure(ctx, delivered.id, role='researcher', session_id='builder')
    SERVICE.returned(ctx, delivered.id, 'Built.', state='delivered')
    request = context('orchestration', project_folder, project='proj', session='facilitator', nouns={
        'role': 'harsh_critic', 'task': 'Review delivered selection behavior.'})
    with pytest.raises(Stop, match='delivered ticket identity'):
        SERVICE.delegate(request)
    request.nouns['context'] = {'reviewed_work': delivered.id}
    critic = SERVICE.delegate(request)
    assert critic['reviewed_assignment_id'] == built['assignment_id']
    assert critic['return_to']['assignment_id'] == caller['assignment_id']
    rejected = SERVICE.returned(ctx, critic['work_id'], 'REJECT', findings=[{
        'summary': 'Selection resets.', 'remediation': 'Preserve selection.', 'verify': 'Adjust twice.'}])
    correction_id = rejected['findings_filed'][0]
    map_store = context('map', project_folder, project='proj').require_store()
    with map_store.tables(write=False) as tx:
        assert tx.get('after', {'work_id': correction_id})['works'] == [delivered.id]
        assert tx.get('ticket_settings', {'work_id': correction_id})['board'] == 'delivered-board'
    assert store.ticket(delivered.id).work.done
    correction = SERVICE.assignment(ctx, work_id=correction_id)
    with own(ctx).tables(write=False) as tx:
        commission = tx.rows('role_requests', {'caller_assignment_id': correction['assignment_id']}, limit=0).results[0]
    SERVICE.bind(ctx, commission['creator_assignment_id'], 'correction-facilitator')
    SERVICE.publish_role(context('orchestration', project_folder, project='proj', session='correction-facilitator',
                                nouns={'request': commission['request_id'], 'role': 'selection_engineering',
                                       'purpose': 'Maintain stable selection across control updates.',
                                       'duty': 'Preserve selection during control updates.'}))
    SERVICE.bind(ctx, correction['assignment_id'], 'correction-builder')
    SERVICE.check_in(context('orchestration', project_folder, project='proj', session='correction-builder', nouns={
        'state': 'returned', 'summary': 'Corrected.', 'evidence': ['Adjust twice passed.']}))
    SERVICE.drain(ctx, [caller['work_id']])
    assert any(assignment_id == caller['assignment_id'] and envelope['work_id'] == correction_id
               for assignment_id, envelope in actual.messages)
