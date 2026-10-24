"""Approved execution boards authorize existing work through their active Facilitator."""
from dataclasses import replace

import pytest

from metaform import settings
from metaform.data import Node
from metaform.module import context
from metaform.modules.orchestration.state import SERVICE, own, verb
from tests.storekit import small_map

pytestmark = pytest.mark.kind('simulation')
NODE = 'code.timer.kitchen'
SESSION = 'facilitator-session'
BOARD = 'approved-roundtable'


@pytest.fixture
def approved(store, project_folder, monkeypatch, run):
    run('enable', 'dispatch', cwd=project_folder)
    small_map(store)
    settings.put('dispatch_autostart', False, project_folder)
    from metaform.modules.orchestration import SERVICE as current_service
    from metaform.modules.orchestration.tests.test_orchestration import Transport
    monkeypatch.setitem(globals(), 'SERVICE', current_service)
    transport = Transport()
    namespace = SERVICE.claim.__func__.__globals__
    original = namespace['provided']
    monkeypatch.setitem(namespace, 'provided', lambda folder, purpose: [('fixture', transport)]
                        if purpose == 'orchestration.transport' else original(folder, purpose))
    monkeypatch.setitem(namespace, 'persons_word', lambda *args, **kwargs: None)
    monkeypatch.setitem(namespace, 'agent_caller', lambda: 'Worker session.')
    ctx = context('orchestration', project_folder, project='proj', surface='mcp')
    verb(ctx, 'map', 'boards', op='add', name=BOARD)
    verb(ctx, 'map', 'boards', op='add', name='unapproved-board')
    commission = store.add_work(Node('element', NODE), None, task='Facilitate the approved execution outline.')
    facilitator = SERVICE.claim(replace(ctx, consented=True, nouns={
        'work': commission.id, 'role': 'facilitator',
        'specification': {'approved_board': BOARD, 'roundtable': 'table-7', 'outline_digest': 'approved-outline'}}))
    facilitator = SERVICE.bind(ctx, facilitator['assignment_id'], SESSION)
    assert facilitator['persons_start'] and facilitator['state'] == 'running'
    assert settings.value('dispatch_autostart', project_folder) is False
    worker = replace(ctx, session=SESSION, consented=False)
    return store, worker, facilitator


def board_work(store, ctx, board=BOARD):
    work = store.add_work(Node('element', NODE), None, task='Verify the completed alarm behavior.')
    if board is not None:
        verb(ctx, 'map', 'work', op='edit', id=work.id, board=board)
    return work


def claim_work(ctx, work, **nouns):
    return SERVICE.claim(replace(ctx, nouns={
        'work': work.id, 'role': 'planner', 'pm_session': SESSION, **nouns}))


def test_active_facilitator_claims_approved_existing_ticket_through_native_facade(approved):
    from metaform.modules.orchestration import claim

    store, ctx, facilitator = approved
    work = board_work(store, ctx)
    result = claim(replace(ctx, nouns={'work': work.id, 'role': 'planner', 'pm_session': SESSION}))
    assigned = SERVICE.assignment(ctx, work_id=work.id)
    assert result == {'assignment_id': assigned['assignment_id'], 'state': assigned['state']}
    assert assigned['persons_start'] is True
    assert assigned['work_id'] == work.id and assigned['root_work_id'] == work.id
    assert assigned['parent_assignment_id'] is None
    assert assigned['return_to'] == {'session_id': SESSION, 'kind': 'pm'}
    assert assigned['owner_session_id'] is None
    assert assigned['state'] == 'queued'
    assert not store.ticket(work.id).work.taken
    launches = [one for one in SERVICE.pending(ctx, [work.id]) if one['kind'] == 'launch']
    assert len(launches) == 1 and launches[0]['assignment_id'] == assigned['assignment_id']
    assert SERVICE.assignment(ctx, assignment_id=facilitator['assignment_id'])['state'] == 'running'


@pytest.mark.parametrize('board', ['unapproved-board', None])
def test_approved_board_authority_does_not_cover_other_or_unplaced_work(approved, board):
    store, ctx, _ = approved
    work = board_work(store, ctx, board)
    assigned = claim_work(ctx, work, specification={'approved_board': BOARD})
    assert assigned['persons_start'] is False
    assert assigned['return_to'] == {'session_id': SESSION, 'kind': 'pm'}


@pytest.mark.parametrize('condition', ['stopped', 'returned', 'rebound', 'unrelated_session'])
def test_inactive_or_stale_facilitator_cannot_authorize_board_claim(approved, condition):
    store, ctx, facilitator = approved
    work = board_work(store, ctx)
    if condition == 'stopped':
        SERVICE.stopped(ctx, work_id=facilitator['work_id'], by='user')
    elif condition == 'returned':
        SERVICE.returned(ctx, facilitator['work_id'], 'Facilitation complete.', state='delivered')
    elif condition == 'rebound':
        SERVICE.bind(ctx, facilitator['assignment_id'], 'replacement-facilitator-session')
    else:
        ctx = replace(ctx, session='unrelated-session')
    assigned = claim_work(ctx, work)
    assert assigned['persons_start'] is False


def test_automatic_claim_does_not_inherit_board_approval(approved):
    store, ctx, _ = approved
    assigned = claim_work(ctx, board_work(store, ctx), automatic=True)
    assert assigned['persons_start'] is False
    assert assigned['return_to'] == {'session_id': SESSION, 'kind': 'pm'}


@pytest.mark.parametrize('missing', ['approval', 'persons_start', 'facilitator_role'])
def test_board_claim_requires_person_started_facilitator_with_recorded_approval(approved, missing):
    store, ctx, facilitator = approved
    fields = {'approval': {'specification': None}, 'persons_start': {'persons_start': False},
              'facilitator_role': {'authored_role_uri': 'metaform://role/planner'}}[missing]
    with own(ctx).tables() as tx:
        tx.update('assignments', {'assignment_id': facilitator['assignment_id']}, fields)
    assert claim_work(ctx, board_work(store, ctx))['persons_start'] is False


def test_authorized_missing_role_commission_retains_start_authority_and_return_route(approved):
    store, ctx, _ = approved
    work = board_work(store, ctx)
    assigned = claim_work(ctx, work, role=None, create=True)
    assert assigned['persons_start'] and assigned['state'] == 'waiting'
    assert assigned['return_to'] == {'session_id': SESSION, 'kind': 'pm'}
    request = assigned['role_request']
    assert request['state'] == 'commissioned'
    creator = SERVICE.assignment(ctx, assignment_id=request['creator_assignment_id'])
    assert creator['authored_role_uri'] == 'metaform://role/facilitator'
    assert creator['persons_start'] is True
    assert creator['parent_assignment_id'] == assigned['assignment_id']
    assert creator['return_to'] == {'assignment_id': assigned['assignment_id'],
                                    'role_request_id': request['request_id']}
    SERVICE.bind(ctx, creator['assignment_id'], 'role-creator-session')
    published = SERVICE.publish_role(replace(ctx, session='role-creator-session', nouns={
        'request': request['request_id'], 'role': 'alarm_roundtable_verifier',
        'purpose': 'Verify approved alarm behavior.',
        'duty': 'Measure alarm timing and compare observed behavior with the approved requirements.'}))
    specialist = published['assignment']
    assert specialist['assignment_id'] == assigned['assignment_id'] and specialist['work_id'] == work.id
    assert specialist['persons_start'] is True
    assert specialist['return_to'] == {'session_id': SESSION, 'kind': 'pm'}
    assert specialist['authored_role_uri'] == 'metaform://role/alarm_roundtable_verifier'


@pytest.mark.parametrize('authority', ['approved', 'automatic', 'stopped'])
def test_critic_repair_inherits_only_unstopped_delivery_authority(approved, authority):
    store, ctx, facilitator = approved
    work = board_work(store, ctx)
    built = claim_work(ctx, work, automatic=authority == 'automatic')
    assert built['persons_start'] is (authority != 'automatic')
    SERVICE.bind(ctx, built['assignment_id'], 'delivery-worker-session')
    SERVICE.returned(replace(ctx, session='delivery-worker-session'), work.id,
                     'Alarm behavior delivered.', state='delivered')
    if authority == 'stopped':
        SERVICE.stopped(ctx, work_id=work.id, by='user', direction='Stop this delivery.')
    critic = SERVICE.delegate(replace(ctx, nouns={
        'role': 'harsh_critic', 'task': 'Check the delivered alarm against approved requirements.',
        'context': {'reviewed_work': work.id}}))
    assert critic['reviewed_assignment_id'] == built['assignment_id']
    assert critic['return_to']['assignment_id'] == facilitator['assignment_id']
    SERVICE.bind(ctx, critic['assignment_id'], 'critic-session')
    result = SERVICE.returned(replace(ctx, session='critic-session'), critic['work_id'], 'REJECT', findings=[{
        'summary': 'Alarm stops before the required duration.',
        'evidence': 'Observed alarm ends after two seconds.',
        'requirement': 'Alarm sounds for five seconds.',
        'remediation': 'Preserve the required alarm duration.',
        'verify': 'Measure the alarm duration after timer expiry.'}])
    assert len(result['findings_filed']) == 1
    correction_id = result['findings_filed'][0]
    correction = SERVICE.assignment(ctx, work_id=correction_id)
    authorized = authority == 'approved'
    assert correction['persons_start'] is authorized
    assert correction['work_id'] == correction['root_work_id'] == correction_id
    assert correction_id != work.id and correction['parent_assignment_id'] is None
    assert correction['return_to'] == critic['return_to']
    assert correction['state'] == 'waiting'
    with own(ctx).tables(write=False) as tx:
        requests = tx.rows('role_requests', {'caller_assignment_id': correction['assignment_id']}, limit=0).results
    assert len(requests) == 1 and requests[0]['state'] == 'commissioned'
    commission = SERVICE.assignment(ctx, assignment_id=requests[0]['creator_assignment_id'])
    assert commission['persons_start'] is authorized
    assert commission['authored_role_uri'] == 'metaform://role/facilitator'
    assert commission['parent_assignment_id'] == correction['assignment_id']
    assert commission['return_to']['assignment_id'] == correction['assignment_id']
    with context('map', ctx.folder, project='proj').require_store().tables(write=False) as tx:
        assert tx.get('ticket_settings', {'work_id': correction_id})['board'] == BOARD
        assert tx.get('after', {'work_id': correction_id})['works'] == [work.id]
    assert store.ticket(work.id).work.done


def test_explicit_pm_result_reaches_selected_session_after_its_current_card_changes(approved):
    from metaform.modules.dispatch import orchestration as transport
    store, ctx, facilitator = approved
    delivery = claim_work(ctx, board_work(store, ctx))
    SERVICE.bind(ctx, delivery['assignment_id'], 'delivery-session')
    # The PM keeps the selected conversation while moving to another contribution in the same workstream.
    SERVICE.returned(ctx, facilitator['work_id'], 'Initial contribution complete.')
    next_work = board_work(store, ctx)
    current = SERVICE.claim(replace(ctx, consented=True, session=None, nouns={
        'work': next_work.id, 'role': 'facilitator', 'continue_from': facilitator['work_id']}))
    current = SERVICE.bind(ctx, current['assignment_id'], SESSION)
    SERVICE.returned(ctx, delivery['work_id'], 'Selected specialist result.')
    packets = [one for one in SERVICE.pending(ctx, [current['work_id']])
               if one['kind'] == 'send' and one['payload'].get('sender_assignment_id') == delivery['assignment_id']]
    assert len(packets) == 1
    envelope = packets[0]['payload']
    assert envelope['return_to'] == {'session_id': SESSION, 'kind': 'pm'}
    assert transport.actionable(ctx, envelope, session_id=SESSION, recipient=current)
    assert not transport.actionable(ctx, envelope, session_id='different-session', recipient=current)
