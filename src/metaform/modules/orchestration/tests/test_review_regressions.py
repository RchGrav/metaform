"""Review regressions for GC self-requests and configured role-commission authority."""
from __future__ import annotations

import pytest

from metaform import settings
from metaform.data import Node
from metaform.module import Stop, context
from metaform.modules.orchestration import state
from metaform.modules.orchestration.state import SERVICE, own, verb
from metaform.modules.orchestration.tests.test_orchestration import Transport
from tests.storekit import small_map

pytestmark = pytest.mark.kind('simulation')
NODE = 'code.timer.kitchen'


@pytest.fixture
def project(store, project_folder, monkeypatch):
    small_map(store)
    actual = Transport(capacity=1)
    provided = state.provided

    def providers(folder, kind):
        return [('dispatch', actual)] if kind == 'orchestration.transport' else provided(folder, kind)

    monkeypatch.setattr(state, 'provided', providers)
    return store, project_folder, actual


def called(project, session=None, surface='cli'):
    return context('orchestration', project[1], project='proj', session=session, surface=surface)


def claim(project):
    work = project[0].add_work(Node('element', NODE), None,
                               task='Preserve countdown and audible alarm.', title='Timer delivery')
    gc = verb(called(project, 'gc'), 'orchestration', 'claim', work=work.id, role='gc', session='gc')
    project[2].running.add('gc')
    return SERVICE.assignment(called(project), assignment_id=gc['assignment_id'])


def snapshot(project):
    with own(called(project)).tables(write=False) as tx:
        recorded = {name: list(tx.rows(name, limit=0).results)
                    for name in ('assignments', 'role_requests', 'transitions')}
    return recorded, project[0].work(limit=0).results


def test_gc_missing_specialist_request_can_reach_its_own_commission(project):
    """Draining a self-request must leave a GC able to act on the recorded request."""
    gc = claim(project)
    actual = project[2]
    request = verb(called(project, 'gc'), 'orchestration', 'call', role='alarm_domain',
                   task='Establish the audible alarm constraints.', result='Return the alarm constraints.',
                   key='gc-alarm-specialist')
    assert request['caller_assignment_id'] == request['gc_assignment_id'] == gc['assignment_id']
    assert request['state'] == 'commissioned'
    assert verb(called(project, 'gc'), 'orchestration', 'call', role='alarm_domain',
                task='Establish the audible alarm constraints.', result='Return the alarm constraints.',
                key='gc-alarm-specialist')['request_id'] == request['request_id']

    SERVICE.drain(called(project))
    assert actual.running, {
        'gc': SERVICE.assignment(called(project), assignment_id=gc['assignment_id']),
        'pending': SERVICE.pending(called(project)),
        'suspensions': actual.suspensions,
    }
    creator = SERVICE.assignment(called(project), assignment_id=request['creator_assignment_id'])
    assert actual.launches[-1][0]['assignment_id'] == creator['assignment_id']
    assert creator['authored_role_uri'] == 'metaform://role/facilitator'
    assert creator['gc_assignment_id'] == gc['assignment_id']
    assert SERVICE.assignment(called(project), work_id=gc['work_id'])['state'] == 'suspended'
    assert actual.maximum == 1


def test_role_commission_obeys_current_blacklist_without_mutating_work(project, monkeypatch):
    gc = claim(project)
    worker = verb(called(project, 'gc'), 'orchestration', 'delegate',
                  role='implementer', task='Implement the countdown.')
    SERVICE.bind(called(project), worker['assignment_id'], 'worker')
    request = verb(called(project, 'worker'), 'orchestration', 'call',
                   role='alarm_domain', task='Establish alarm constraints.', key='worker-alarm-specialist')
    assert request['caller_assignment_id'] == worker['assignment_id']
    assert request['gc_assignment_id'] == gc['assignment_id']

    settings.put('roles_without_authority', ['worker'], project[1])
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    before = snapshot(project)
    for surface in ('cli', 'mcp'):
        with pytest.raises(Stop, match='roles_without_authority.*worker'):
            verb(called(project, 'gc', surface), 'orchestration', 'delegate',
                 role='investigator', task='Trace the countdown.')
        with pytest.raises(Stop, match='roles_without_authority.*worker'):
            verb(called(project, 'gc', surface), 'orchestration', 'commission',
                 request=request['request_id'], wait=True)
        assert snapshot(project) == before

    with monkeypatch.context() as person:
        person.delenv('METAFORM_ROLE')
        settings.put('roles_without_authority', ['none'], project[1])
    creator = verb(called(project, 'gc'), 'orchestration', 'commission',
                   request=request['request_id'], wait=True)
    assert creator['gc_assignment_id'] == gc['assignment_id']
    assert creator['authored_role_uri'] == 'metaform://role/facilitator'
    assert verb(called(project), 'orchestration', 'role_requests', request=request['request_id'])[
        'creator_assignment_id'] == creator['assignment_id']
