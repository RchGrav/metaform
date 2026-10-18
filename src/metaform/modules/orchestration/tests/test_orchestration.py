"""Real work/store transitions with a deterministic dispatch transport; no model claims."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from metaform.data import Node, StoreError
from metaform.module import Stop, context
from metaform.modules.orchestration import assess, change
from metaform.modules.orchestration import state as implementation
from metaform.modules.orchestration.state import SERVICE, Orchestration, fingerprint, work_changed
from tests.storekit import small_map

pytestmark = pytest.mark.kind('simulation')
NODE = 'code.timer.kitchen'


@pytest.fixture
def project(store, project_folder):
    small_map(store)
    return store, project_folder


def ctx(project, session=None, **nouns):
    _, folder = project
    return context('orchestration', folder, project='proj', session=session, nouns=nouns)


def root(project, session='gc-one', **nouns):
    store, _ = project
    work = store.add_work(Node('element', NODE), None, task='Preserve countdown and alarm behavior.',
                          title='Timer delivery')
    return SERVICE.claim(ctx(project, session, work=work.id, **nouns))


class Transport:
    def __init__(self, capacity=1):
        self.capacity = capacity
        self.running = set()
        self.launches = []
        self.messages = []
        self.chat = []
        self.suspensions = []
        self.maximum = 0

    def launch(self, ctx, assignment, transition_id):
        if len(self.running) >= self.capacity:
            return {'state': 'queued', 'reason': 'Configured capacity is occupied.'}
        session_id = 'session-' + transition_id
        self.running.add(session_id)
        self.maximum = max(self.maximum, len(self.running))
        self.launches.append((assignment, session_id))
        return {'state': 'running', 'session_id': session_id, 'runner': 'runner-' + transition_id}

    def suspend(self, ctx, assignment, reason):
        self.running.discard(assignment['owner_session_id'])
        self.suspensions.append((assignment['assignment_id'], reason))
        return {'state': 'suspended'}

    def send(self, ctx, assignment, envelope):
        if assignment['owner_session_id'] not in self.running:
            return {'state': 'queued'}
        self.messages.append((assignment['assignment_id'], envelope))
        return {'state': 'delivered'}

    def notify_user(self, ctx, message, change_id):
        if not any(one[0] == change_id for one in self.chat):
            self.chat.append((change_id, message))
        return {'state': 'delivered'}


def transport(monkeypatch, project, capacity=1):
    made = Transport(capacity)
    original = implementation.provided

    def providers(folder, kind):
        return [('dispatch', made)] if kind == 'orchestration.transport' else original(folder, kind)
    monkeypatch.setattr(implementation, 'provided', providers)
    return made


def test_atomic_gc_claim_race_keeps_one_owner(project):
    store, _ = project
    work = store.add_work(Node('element', NODE), None, task='Deliver the requested timer.', title='One delivery')

    def take(session):
        try:
            return SERVICE.claim(ctx(project, session, work=work.id))
        except (Stop, StoreError):
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(take, ['gc-a', 'gc-b']))
    owned = [one for one in results if one]
    assert len(owned) == 1
    assert store.ticket(work.id).work.taken_by == owned[0]['owner_session_id']
    assert SERVICE.assignment(ctx(project), work_id=work.id)['assignment_id'] == owned[0]['assignment_id']


def test_capacity_one_nested_call_releases_parent_and_returns_to_immediate_worker(project, monkeypatch):
    gc = root(project)
    actual = transport(monkeypatch, project)
    actual.running.add('gc-one')
    worker = SERVICE.delegate(ctx(project, 'gc-one', role='implementer', task='Implement countdown updates.',
                                  key='worker'), waiting=True)
    SERVICE.drain(ctx(project))
    worker_session = SERVICE.assignment(ctx(project), assignment_id=worker['assignment_id'])['owner_session_id']
    child = SERVICE.delegate(ctx(project, worker_session, role='investigator', task='Trace alarm behavior.',
                                 key='specialist'), waiting=True)
    SERVICE.drain(ctx(project))
    child_session = SERVICE.assignment(ctx(project), assignment_id=child['assignment_id'])['owner_session_id']
    assert child['parent_assignment_id'] == worker['assignment_id']
    assert child['team_id'] == worker['team_id'] == gc['team_id']
    SERVICE.returned(ctx(project, child_session), child['work_id'], 'Alarm uses current duration.',
                     evidence=['Observed candidate rev-a ringing at zero.'])
    actual.running.discard(child_session)
    Orchestration().drain(ctx(project))
    assert actual.messages[-1][0] == worker['assignment_id']
    assert 'Alarm uses current duration.' in actual.messages[-1][1]['result']
    assert not project[0].ticket(gc['work_id']).work.done
    assert actual.maximum == 1
    worker_now = SERVICE.assignment(ctx(project), assignment_id=worker['assignment_id'])
    assert worker_now['owner_session_id'] != worker_session
    assert SERVICE.assignment(ctx(project), session_id='runner-' + actual.launches[-1][0]['continuation'][
        'transition_id'])['assignment_id'] == worker['assignment_id']
    launches = len(actual.launches)
    Orchestration().drain(ctx(project))
    assert len(actual.launches) == launches


def test_new_specialist_gc_commission_publication_reuse_and_original_return(project, monkeypatch):
    gc = root(project)
    worker = SERVICE.delegate(ctx(project, 'gc-one', role='implementer', task='Implement timing.'))
    SERVICE.bind(ctx(project), worker['assignment_id'], 'worker')
    request = SERVICE.delegate(ctx(project, 'worker', role='alarm_domain', task='Review timer alarm timing.',
                                   result='Return alarm constraints.', contribution='Alarm domain diagnosis.'), waiting=True)
    assert request['state'] == 'requested'
    assert request['gc_assignment_id'] == gc['assignment_id']
    with pytest.raises(Stop, match='delivery GC'):
        SERVICE.commission(ctx(project, 'worker', request=request['request_id']))
    creator = SERVICE.commission(ctx(project, 'gc-one', request=request['request_id']))
    assert creator['authored_role_uri'] == 'metaform://role/role_creator'
    SERVICE.bind(ctx(project), creator['assignment_id'], 'creator')
    published = SERVICE.publish_role(ctx(project, 'creator', request=request['request_id'],
        duty='Investigate alarm timing against the requested user outcome. Return evidence to the calling worker.'))
    specialist = published['assignment']
    assert specialist['parent_assignment_id'] == worker['assignment_id']
    assert specialist['team_id'] == gc['team_id']
    assert specialist['return_to']['assignment_id'] == worker['assignment_id']
    resolution = implementation.resolve(ctx(project), 'alarm_domain')
    assert not resolution['problems']
    assert resolution['components'][-1]['name'] == 'agents:generated_proj_alarm_domain'
    duty_version = resolution['components'][-1]['actual_version_id']
    reused = SERVICE.delegate(ctx(project, 'worker', role='alarm_domain', task='Review a second alarm.', key='reuse'))
    assert reused['authored_role_uri'] == specialist['authored_role_uri']
    assert implementation.resolve(ctx(project), 'alarm_domain')['components'][-1]['actual_version_id'] == duty_version
    duplicate = SERVICE.publish_role(ctx(project, 'creator', request=request['request_id'],
        duty='Investigate alarm timing against the requested user outcome. Return evidence to the calling worker.'))
    assert duplicate['assignment']['assignment_id'] == specialist['assignment_id']
    assert implementation.resolve(ctx(project), 'alarm_domain')['components'][-1]['actual_version_id'] == duty_version


def test_post_delivery_fqc_missing_role_gets_commission_gc_and_retains_original_return(project, monkeypatch):
    gc = root(project, candidate={'revision': 'delivered-timer'})
    SERVICE.returned(ctx(project), gc['work_id'], 'Timer outcome delivered.', state='delivered')
    review = SERVICE.assessment(ctx(project), gc, {'summary': 'Assess the delivered timer.'}, 'after-delivery')
    SERVICE.bind(ctx(project), review['assignment_id'], 'fqc')
    request_ctx = ctx(project, 'fqc', role='focus_observer', task='Observe keyboard focus while changing duration.',
                      context={'interaction': 'duration control with keyboard'}, key='focus-specialist')
    request = SERVICE.delegate(request_ctx, waiting=True)
    commissioner = SERVICE.assignment(ctx(project), assignment_id=request['gc_assignment_id'])
    assert commissioner['assignment_id'] != gc['assignment_id']
    assert commissioner['gc_assignment_id'] == commissioner['team_id'] == commissioner['assignment_id']
    assert commissioner['parent_assignment_id'] == gc['assignment_id']
    assert commissioner['root_work_id'] == gc['work_id']
    assert request['context']['responsible_gc_assignment_id'] == gc['assignment_id']
    assert SERVICE.assignment(ctx(project), work_id=gc['work_id'])['state'] == 'delivered'
    assert project[0].ticket(gc['work_id']).work.done
    assert SERVICE.delegate(request_ctx, waiting=True)['request_id'] == request['request_id']
    SERVICE.bind(ctx(project), commissioner['assignment_id'], 'commission-gc')
    with pytest.raises(Stop, match='delivery GC'):
        SERVICE.commission(ctx(project, 'gc-one', request=request['request_id']))
    creator = SERVICE.commission(ctx(project, 'commission-gc', request=request['request_id'], wait=True))
    SERVICE.bind(ctx(project), creator['assignment_id'], 'creator', runner='creator-runner')
    with monkeypatch.context() as environment:
        environment.setenv('METAFORM_SESSION', 'creator-runner')
        published = SERVICE.publish_role(ctx(project, request=request['request_id'],
            duty='Observe keyboard focus and return candidate-specific evidence to the requesting assessor.'))
    assert published['role']['source']['creator_session_id'] == 'creator'
    assert published['role']['source']['creator_caller_id'] == 'creator-runner'
    specialist = published['assignment']
    assert specialist['team_id'] == review['team_id']
    assert specialist['return_to']['assignment_id'] == review['assignment_id']
    assert 'duration control with keyboard' in specialist['task']
    assert SERVICE.delegate(request_ctx, waiting=True)['assignment_id'] == specialist['assignment_id']
    SERVICE.bind(ctx(project), specialist['assignment_id'], 'focus-specialist')
    SERVICE.check_in(ctx(project, 'focus-specialist', state='returned', summary='Keyboard focus remains on duration.',
                         evidence=['Tab position stayed on the selected duration control.']))
    return_event = next(one for one in SERVICE.pending(ctx(project)) if one['assignment_id'] == review['assignment_id']
                        and one['kind'] == 'send' and one['payload'].get('kind') == 'result')
    assert return_event['payload']['sender_assignment_id'] == specialist['assignment_id']
    assert return_event['payload']['result'] == 'Keyboard focus remains on duration.'
    assert any(one['kind'] == 'launch' and one['assignment_id'] == review['assignment_id']
               for one in SERVICE.pending(ctx(project)))
    assert not any(one['kind'] == 'launch' and one['assignment_id'] == gc['assignment_id']
                   for one in SERVICE.pending(ctx(project)))
    SERVICE.stopped(ctx(project), work_id=gc['work_id'], by='user', direction='Stop the remaining review.')
    with pytest.raises(Stop, match='stopped'):
        SERVICE.delegate(ctx(project, 'fqc', role='new_after_stop', task='Do not launch.'))
    assert SERVICE.assignment(ctx(project), work_id=gc['work_id'])['state'] == 'delivered'


def test_fqc_independent_candidate_findings_corrective_gc_continuation(project, run):
    gc = root(project, candidate={'revision': 'candidate-a'})
    review = assess(ctx(project, 'gc-one', summary='Timer candidate validated.',
                        candidate={'revision': 'candidate-a'}, evidence=['Countdown integration test passes.'],
                        key='review-a'))
    assert review['team_id'] != gc['team_id']
    assert review['parent_assignment_id'] is None
    assert review['reviewed_assignment_id'] == gc['assignment_id']
    assert 'Countdown integration test passes.' in review['task']
    assert SERVICE.same_team(ctx(project), gc['work_id'], review['work_id'])  # coordinated reference claim only
    SERVICE.bind(ctx(project), review['assignment_id'], 'fqc')
    assert not SERVICE.owns(ctx(project), 'gc-one', 'fqc')
    specialist = SERVICE.delegate(ctx(project, 'fqc', role='verifier', task='Observe the complete adjustment flow.'))
    SERVICE.bind(ctx(project), specialist['assignment_id'], 'fqc-verifier')
    assert specialist['team_id'] == review['team_id']
    assert specialist['team_id'] != gc['team_id']
    assert SERVICE.same_team(ctx(project), gc['work_id'], specialist['work_id'])
    assert not SERVICE.owns(ctx(project), 'gc-one', 'fqc-verifier')
    assert project[0].ticket(gc['work_id']).work.taken_by == 'gc-one'
    run('enable', 'dispatch', cwd=project[1])
    claim = implementation.verb(ctx(project), 'dispatch', 'claim', name='Timer delivery reservation',
                                nodes=[NODE], work=[gc['work_id']])
    from metaform.modules.dispatch import claimed
    unrelated = project[0].add_work(Node('element', NODE), None, task='An unrelated ticket.', title='Other ticket')
    assert claimed(project[0], NODE, unrelated.id)['claim_id'] == claim['claim_id']
    assert claimed(project[0], NODE, specialist['work_id']) is None
    result = SERVICE.check_in(ctx(project, 'fqc', state='returned', summary='Selection resets while adjusting duration.',
        candidate={'revision': 'candidate-a'}, evidence=['Observed selection reset.'], findings=[{
            'task': 'Preserve the current selection while duration changes.', 'title': 'Preserve selection'}]))
    assert result['state'] == 'returned'
    pending = SERVICE.pending(ctx(project))
    gc_return = [one for one in pending if one['assignment_id'] == gc['assignment_id'] and one['kind'] == 'send']
    assert gc_return[0]['payload']['evidence'] == ['Observed selection reset.']
    corrections = [one for one in pending if one['payload'].get('kind') == 'functional_correction']
    assert len(corrections) == 1
    correction = SERVICE.assignment(ctx(project), assignment_id=corrections[0]['assignment_id'])
    assert correction['authored_role_uri'] == 'metaform://role/gc'
    assert correction['parent_assignment_id'] == gc['assignment_id']
    assert correction['team_id'] != gc['team_id']
    assert correction['root_work_id'] == gc['work_id']
    assert any(one['kind'] == 'user_message' and one['payload']['kind'] == 'functional_assessment' for one in pending)


def test_adaptive_publication_actual_spec_user_chat_current_context_and_restart(project, monkeypatch):
    _, folder = project
    path = folder / 'timer-spec.md'
    path.write_text('Rebuild the timer view on each change.', encoding='utf-8')
    gc = root(project, specification={'uri': 'file:timer-spec.md', 'revision': fingerprint(path.read_text())})
    worker = SERVICE.delegate(ctx(project, 'gc-one', role='implementer', task='Keep the timer visible.'))
    review = assess(ctx(project, 'gc-one', summary='View rebuild drops selection.', evidence=['Selection lost.'], key='r'))
    SERVICE.bind(ctx(project), review['assignment_id'], 'fqc')
    change_ctx = ctx(project, 'fqc', content='Update timer state while preserving selection.',
        reason='The receiving user can monitor the countdown continuously; preserving selection serves that purpose.',
        observed_limitation='Rebuilds discard the current selection.', key='adaptation')
    changed = change(change_ctx)
    assert changed['state'] == 'published'
    assert path.read_text() == 'Update timer state while preserving selection.'
    assert changed['current_revision'] == fingerprint(path.read_text())
    current = SERVICE.context(ctx(project), work_id=worker['work_id'])
    assert current['specification']['revision'] == changed['current_revision']
    assert current['pending_direction'][0]['change_id'] == changed['change_id']
    actual = transport(monkeypatch, project, capacity=5)
    actual.running.update(('gc-one', 'fqc'))
    Orchestration().drain(ctx(project))
    assert len(actual.chat) == 1
    assert changed['current_revision'] in actual.chat[0][1]['body']
    assert changed['reason'] in actual.chat[0][1]['body']
    assert any(recipient == gc['assignment_id'] and message['kind'] == 'change_order'
               for recipient, message in actual.messages)
    Orchestration().drain(ctx(project))
    assert len(actual.chat) == 1


def test_strict_publication_reads_latest_mode_and_new_user_direction_still_applies(project):
    _, folder = project
    path = folder / 'spec.md'
    path.write_text('Old approach.', encoding='utf-8')
    gc = root(project, specification={'uri': 'file:spec.md'})
    review = assess(ctx(project, 'gc-one', summary='Review old approach.', key='r'))
    SERVICE.bind(ctx(project), review['assignment_id'], 'fqc')
    SERVICE.mode(ctx(project, assignment=gc['assignment_id'], mode='strict'))
    recommendation = change(ctx(project, 'fqc', content='Better approach.', reason='Preserves the receiving purpose.'))
    assert recommendation['state'] == 'recommendation'
    assert path.read_text() == 'Old approach.'
    instructed = change(ctx(project, assignment=gc['assignment_id'], content='New user instruction.',
                             reason='The user changed the requested behavior.', user_instruction='Use this approach.'))
    assert instructed['state'] == 'published'
    assert path.read_text() == 'New user instruction.'
    with pytest.raises(Stop, match='advanced'):
        change(ctx(project, 'fqc', content='Stale assessment.', base=fingerprint('Old approach.'), reason='Stale.'))


def test_stopped_descendants_and_interrupt_direction_survive_recovery(project, monkeypatch):
    gc = root(project)
    child = SERVICE.delegate(ctx(project, 'gc-one', role='implementer', task='Implement countdown.'))
    SERVICE.bind(ctx(project), child['assignment_id'], 'child')
    grandchild = SERVICE.delegate(ctx(project, 'child', role='investigator', task='Trace countdown.'))
    SERVICE.interrupted(ctx(project), 'child', {'kind': 'change_order', 'body': 'Preserve the current selection.'})
    restored = Orchestration().context(ctx(project), work_id=child['work_id'])
    assert restored['pending_direction'][-1]['body'] == 'Preserve the current selection.'
    assert project[0].ticket(child['work_id']).work.task == 'Implement countdown.'
    stopped = SERVICE.stopped(ctx(project), work_id=gc['work_id'], by='user', direction='Stop this ticket.')
    assert set(stopped) == {gc['work_id'], child['work_id'], grandchild['work_id']}
    actual = transport(monkeypatch, project)
    Orchestration().drain(ctx(project))
    assert not actual.launches
    with pytest.raises(Stop, match='stopped'):
        SERVICE.bind(ctx(project), grandchild['assignment_id'], 'too-late')


def test_unrelated_change_burst_reads_no_assignment(project, monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail('An unrelated event read orchestration state.')
    monkeypatch.setattr(SERVICE, 'assignment', unexpected)
    for _ in range(100):
        work_changed({'project': 'proj', 'tables': ['memory.entities'], 'work_ids': ['irrelevant']}, ctx(project))
        work_changed({'project': 'proj', 'tables': ['memory.entities']}, ctx(project))


def test_public_board_completion_with_mixed_write_routes_child_and_gc_assessment(project):
    from metaform import changes
    gc = root(project, candidate={'revision': 'board-candidate'})
    child = SERVICE.delegate(ctx(project, 'gc-one', role='implementer', task='Keep the timer selection.'))
    SERVICE.bind(ctx(project), child['assignment_id'], 'worker')
    SERVICE.check_in(ctx(project, 'worker', state='running', summary='The implemented interaction passes.',
        evidence=['Selected control remains selected after duration changes.']))
    map_context = context('map', project[1], project='proj')

    def finish_with_settings_write(work_id, result):
        # The actual public completion shares its command with a module write that has no concern annotation.
        implementation.verb(ctx(project), 'map', 'work', op='done', id=work_id,
                            resolution=result, why='The requested behavior was observed on the candidate.')
        with map_context.require_store().tables() as tx:
            tx.insert('ticket_settings', {'work_id': work_id, 'hold': 0})

    _, child_events = changes.announced(project[1], 'cli', finish_with_settings_write,
                                        child['work_id'], 'The worker retained selection.')
    changed = next(event for event in child_events if 'work' in event.get('tables', ()))
    assert 'work_ids' not in changed
    assert SERVICE.assignment(ctx(project), work_id=child['work_id'])['state'] == 'returned'
    result = next(one for one in SERVICE.pending(ctx(project)) if one['kind'] == 'send' and
                  one['payload'].get('sender_assignment_id') == child['assignment_id'] and
                  one['payload'].get('kind') == 'result')
    assert result['assignment_id'] == gc['assignment_id']
    assert result['payload']['evidence'] == ['Selected control remains selected after duration changes.']
    SERVICE.check_in(ctx(project, 'gc-one', state='running', summary='GC integrated and validated the outcome.',
        candidate={'revision': 'board-candidate'}, evidence=['Countdown, alarm and adjustment interaction passed.']))
    _, gc_events = changes.announced(project[1], 'cli', finish_with_settings_write,
                                     gc['work_id'], 'The GC delivered the timer outcome.')
    assert any('work' in event.get('tables', ()) and 'work_ids' not in event for event in gc_events)
    assert SERVICE.assignment(ctx(project), work_id=gc['work_id'])['state'] == 'delivered'
    pending = SERVICE.pending(ctx(project))
    assessment = next(one for one in pending if one['kind'] == 'assessment')
    assert assessment['payload']['report']['candidate'] == {'revision': 'board-candidate'}
    assert assessment['payload']['report']['evidence'] == ['Countdown, alarm and adjustment interaction passed.']
    assert project[0].ticket(gc['work_id']).work.done
    # Replayed mixed events cannot re-close work, duplicate its result, or create another assessment.
    before = [one['transition_id'] for one in pending]
    work_changed(changed, ctx(project))
    assert [one['transition_id'] for one in SERVICE.pending(ctx(project))] == before
    assert map_context.require_store().ticket(child['work_id']).work.resolution == 'The worker retained selection.'


def test_reserved_role_calls_preserve_independent_assessment_and_gc_commission(project):
    gc = root(project)
    for role, route in [('functionality', 'assess'), ('role_creator', 'commission')]:
        with pytest.raises(Stop) as stopped:
            SERVICE.delegate(ctx(project, 'gc-one', role=role, task='Review this candidate.'))
        assert route in stopped.value.next_step
    assert SERVICE.members(ctx(project), gc['team_id']) == [gc]


def test_repeated_result_key_from_distinct_specialist_calls_reaches_worker(project, monkeypatch):
    root(project)
    worker = SERVICE.delegate(ctx(project, 'gc-one', role='implementer', task='Implement timer controls.'))
    SERVICE.bind(ctx(project), worker['assignment_id'], 'worker')
    actual = transport(monkeypatch, project)
    actual.running.add('worker')
    children = []
    for number in range(2):
        caller = SERVICE.assignment(ctx(project), work_id=worker['work_id'])['owner_session_id']
        child = SERVICE.delegate(ctx(project, caller, role='investigator', task=f'Investigate case {number}.',
                                     key=f'call-{number}'), waiting=True)
        SERVICE.drain(ctx(project))
        session = SERVICE.assignment(ctx(project), work_id=child['work_id'])['owner_session_id']
        SERVICE.check_in(ctx(project, session, state='returned', summary=f'Observed result {number}.',
                             key='specialist-result'))
        actual.running.discard(session)
        SERVICE.drain(ctx(project))
        children.append(child['assignment_id'])
    returns = [envelope for recipient, envelope in actual.messages if recipient == worker['assignment_id'] and
               envelope.get('sender_assignment_id') in children]
    assert [one['result'] for one in returns] == ['Observed result 0.', 'Observed result 1.']
    assert len({one['transition_id'] for one in returns}) == 2
    assert actual.maximum == 1


def test_gc_delivery_closes_root_and_restart_activates_fqc_once(project, monkeypatch):
    gc = root(project)
    SERVICE.returned(ctx(project, 'gc-one'), gc['work_id'], 'Timer outcome delivered.',
                     state='delivered', candidate={'revision': 'integrated-candidate'},
                     evidence=['Actual countdown and alarm interactions passed.'])
    assert project[0].ticket(gc['work_id']).work.done
    actual = transport(monkeypatch, project)
    Orchestration().drain(ctx(project))
    assessment, _ = actual.launches[0]
    assert assessment['authored_role_uri'] == 'metaform://role/functionality'
    assert assessment['team_id'] != gc['team_id']
    assert 'integrated-candidate' in assessment['task']
    assert 'Actual countdown and alarm interactions passed.' in assessment['task']
    assert 'Timer outcome delivered.' in actual.chat[0][1]['body']
    assert 'Actual countdown and alarm interactions passed.' in actual.chat[0][1]['body']
    SERVICE.returned(ctx(project), gc['work_id'], 'Duplicate completion event.', state='delivered')
    Orchestration().drain(ctx(project))
    assert len(actual.launches) == 1
    assert SERVICE.assignment(ctx(project), work_id=gc['work_id'])['state'] == 'delivered'


def test_blocker_crash_retains_report_and_full_capacity_assessment_progresses(project, monkeypatch):
    root(project)
    SERVICE.check_in(ctx(project, 'gc-one', state='waiting', summary='Waiting for the worker.'))
    worker = SERVICE.delegate(ctx(project, 'gc-one', role='implementer', task='Preserve view state.'))
    SERVICE.bind(ctx(project), worker['assignment_id'], 'worker')
    original = SERVICE.assessment

    def crash(*args, **kwargs):
        raise OSError('Controller lost after the blocker commit.')
    monkeypatch.setattr(SERVICE, 'assessment', crash)
    with pytest.raises(OSError, match='blocker commit'):
        SERVICE.check_in(ctx(project, 'worker', state='blocked', summary='View selection is reset.',
                             work_so_far='Candidate working tree and trace retained.', key='blocked-once'))
    monkeypatch.setattr(SERVICE, 'assessment', original)
    retained = SERVICE.context(ctx(project), work_id=worker['work_id'])
    assert retained['last_check_in']['work_so_far'] == 'Candidate working tree and trace retained.'
    actual = transport(monkeypatch, project)
    actual.running.add('worker')
    Orchestration().drain(ctx(project))
    assert actual.maximum == 1
    assert len(actual.launches) == 1
    assert actual.launches[0][0]['authored_role_uri'] == 'metaform://role/functionality'
    assert 'Candidate working tree and trace retained.' in actual.launches[0][0]['task']


def test_workflow_revision_preserves_frozen_history_variables_and_return_route(project, run):
    from metaform.module import context as workflow_context
    from metaform.modules.workflow import catalog, executor, runs
    from metaform.modules.workflow.revisions import revise
    store, folder = project
    run('enable', 'workflow', cwd=folder)
    old = '@STATE_INIT:\n {target} := PARAM\n@RETURN:\n RETURN TRUE\n'
    new = '@STATE_INIT:\n {target} := PARAM\n@RETURN:\n RETURN FALSE\n'
    catalog.submit_logic(store, NODE, 'procedures', 'inspect', old)
    catalog.submit_logic(store, NODE, 'procedures', 'outer', old)
    lookup = lambda address, name: catalog.lookup(store, address, name)
    caller = executor.start(store, f'({{ok}}) := {NODE}.outer(target=7)', {}, None, lookup,
                            {'project': 'proj', 'folder': str(folder)})
    original = executor.call(store, caller, f'{{ok}} := {NODE}.inspect(target=7)',
                             {'caller_progress': 'retained'}, lookup, fresh=True)
    state = runs.held(store, original).value
    state['frames'][-1]['variables'] = executor.pack({'target': 7, 'steps_completed': 2})
    runs.save(store, original, state)
    catalog.submit_logic(store, NODE, 'procedures', 'inspect', new)
    revision_ctx = workflow_context('workflow', folder, project='proj', nouns={
        'run': original, 'change': 'change-workflow', 'address': NODE, 'name': 'inspect',
        'layer': 'procedures', 'revision': '2'})
    moved = revise(revision_ctx)
    assert executor.view(store, moved['run'])['logic']['content'] == new
    assert executor.view(store, moved['run'])['variables']['steps_completed'] == 2
    history = runs.read(store, original)
    assert history.state == 'cancelled'
    assert history.value['frames'][-1]['call']['logic']['content'] == old
    assert history.result['successor'] == moved['run']
    assert revise(revision_ctx)['run'] == moved['run']
    result = executor.complete(store, moved['run'], 'RETURN TRUE', {'target': 7})
    assert result == {'resume': caller}
    assert executor.view(store, caller)['variables'] == {'caller_progress': 'retained', 'ok': True}
    assert runs.read(store, moved['run']).state == 'completed'


def test_workflow_adaptation_keeps_user_pause_and_binds_operative_successor(project, run):
    from metaform.modules.workflow import catalog, executor, runs
    store, folder = project
    run('enable', 'workflow', cwd=folder)
    old = '@STATE_INIT:\n {target} := PARAM\n@RETURN:\n RETURN TRUE\n'
    new = old + '# Preserve the current selection.\n'
    catalog.submit_logic(store, NODE, 'procedures', 'inspect', old)
    lookup = lambda address, name: catalog.lookup(store, address, name)
    original = executor.start(store, f'({{ok}}) := {NODE}.inspect(target=7)', {}, None, lookup,
                              {'project': 'proj', 'folder': str(folder)})
    runs.pause(store, original, 'Which duration did you request?')
    gc = root(project, specification={'kind': 'workflow', 'address': NODE, 'name': 'inspect',
                                      'layer': 'procedures', 'revision': '1', 'run': original})
    review = assess(ctx(project, 'gc-one', summary='Review selected workflow.', key='review'))
    SERVICE.bind(ctx(project), review['assignment_id'], 'fqc')
    published = change(ctx(project, 'fqc', content=new, reason='Retain the receiving user\'s selection.', key='revision'))
    assert published['state'] == 'published'
    successor = published['specification']['run']
    assert successor != original
    assert runs.read(store, successor).state == 'input_required'
    assert runs.read(store, successor).message == 'Which duration did you request?'
    assert SERVICE.context(ctx(project), work_id=gc['work_id'])['specification']['run'] == successor
    assert change(ctx(project, 'fqc', content=new, reason='Same retry.', key='revision'))['change_id'] == \
        published['change_id']


@pytest.mark.parametrize('crash', [False, True])
def test_workflow_recovery_follows_successor_and_newer_source_without_reopening_completed_run(
        project, run, monkeypatch, crash):
    from metaform.modules.orchestration import specifications
    from metaform.modules.workflow import catalog, executor, runs
    store, folder = project
    run('enable', 'workflow', cwd=folder)
    old = '@STATE_INIT:\n {target} := PARAM\n@RETURN:\n RETURN TRUE\n'
    proposed = old + '# Preserve selection during duration adjustment.\n'
    newer = old + '# Newer direction: preserve selection and keyboard focus.\n'
    catalog.submit_logic(store, NODE, 'procedures', 'inspect', old)
    lookup = lambda address, name: catalog.lookup(store, address, name)
    original = executor.start(store, f'({{ok}}) := {NODE}.inspect(target=7)', {}, None, lookup,
                              {'project': 'proj', 'folder': str(folder)})
    gc = root(project, specification={'kind': 'workflow', 'address': NODE, 'name': 'inspect',
                                      'layer': 'procedures', 'revision': '1', 'run': original})
    review = assess(ctx(project, 'gc-one', summary='Observe selection and keyboard focus.', key='review'))
    SERVICE.bind(ctx(project), review['assignment_id'], 'fqc')
    invoke = specifications.verb
    advanced = []

    def racing(ctx, module_id, operation, **nouns):
        result = invoke(ctx, module_id, operation, **nouns)
        if operation == 'revise' and not advanced:
            advanced.append(result['run'])
            catalog.submit_logic(store, NODE, 'procedures', 'inspect', newer)
            if crash:
                raise OSError('Controller ended after the frozen successor committed.')
        return result

    monkeypatch.setattr(specifications, 'verb', racing)
    called = ctx(project, 'fqc', content=proposed, reason='Preserve the receiving interaction.', key='racing-revision')
    if crash:
        with pytest.raises(OSError, match='successor committed'):
            specifications.change(called, SERVICE)
    else:
        assert specifications.change(called, SERVICE)['state'] == 'operative'
    monkeypatch.setattr(specifications, 'verb', invoke)
    with implementation.own(called).tables(write=False) as tx:
        recorded = tx.rows('changes', limit=0).results[0]
    assert recorded['state'] == 'operative'
    assert recorded['current_revision'] == '2'
    assert runs.read(store, original).state == 'cancelled'
    recovered = specifications.finish_publication(called, Orchestration(), recorded['change_id'])
    assert recovered['state'] == 'completed'
    current = SERVICE.context(ctx(project), work_id=gc['work_id'])['specification']
    assert current['revision'] == '3'
    assert executor.view(store, current['run'])['logic']['content'] == newer
    assert runs.read(store, advanced[0]).state == 'cancelled'
    orders = [one['payload'] for one in SERVICE.pending(called) if one['kind'] == 'send' and
              one['payload'].get('change_id') == recorded['change_id']]
    assert orders[0]['published_revision'] == '2'
    assert orders[0]['current_revision'] == '3'
    assert orders[0]['superseded']
    assert newer in orders[0]['body']
    assert orders[0]['specification']['run'] == current['run']

    executor.complete(store, current['run'], 'RETURN TRUE', {'target': 7})
    later = change(ctx(project, 'fqc', content=newer + '# Future adjustments retain focus too.\n',
                       reason='Retain the delivered interaction in later uses.', key='after-delivery'))
    assert later['state'] == 'published'
    assert later['specification']['run'] is None
    assert later['specification']['previous_run'] == current['run']
    assert runs.read(store, current['run']).state == 'completed'


def test_corrective_gc_owns_team_returns_evidence_to_pm_and_receives_independent_assessment(project, monkeypatch):
    gc = root(project)
    SERVICE.returned(ctx(project), gc['work_id'], 'Initial timer delivered.', state='delivered')
    actual = transport(monkeypatch, project)
    SERVICE.drain(ctx(project))
    review, session = actual.launches[-1]
    SERVICE.returned(ctx(project), review['work_id'], 'The duration selection resets.', findings=[{
        'task': 'Preserve duration selection while adjusting the timer.'}])
    actual.running.discard(session)
    SERVICE.drain(ctx(project))
    correction, session = actual.launches[-1]
    assert correction['authored_role_uri'] == 'metaform://role/gc'
    assert correction['team_id'] == correction['gc_assignment_id'] == correction['assignment_id']
    assert correction['team_id'] != gc['team_id']
    assert SERVICE.assignment(ctx(project), work_id=gc['work_id'])['state'] == 'delivered'
    SERVICE.returned(ctx(project), correction['work_id'], 'Duration selection is preserved.', state='delivered',
                     candidate={'revision': 'corrected-b'}, evidence=['Changed duration during active countdown.'])
    actual.running.discard(session)
    SERVICE.drain(ctx(project))
    followup = actual.launches[-1][0]
    assert followup['authored_role_uri'] == 'metaform://role/functionality'
    assert followup['reviewed_assignment_id'] == correction['assignment_id']
    assert followup['team_id'] != correction['team_id']
    assert 'corrected-b' in followup['task']
    notice = next(message for _, message in actual.chat if message['kind'] == 'functional_correction')
    assert 'Duration selection is preserved.' in notice['body']
    assert 'corrected-b' in notice['body']
    assert 'Changed duration during active countdown.' in notice['body']
    stopped = SERVICE.stopped(ctx(project), work_id=gc['work_id'], by='user')
    assert {gc['work_id'], review['work_id'], correction['work_id'], followup['work_id']} <= set(stopped)
    assert SERVICE.assignment(ctx(project), work_id=gc['work_id'])['state'] == 'delivered'
    assert SERVICE.assignment(ctx(project), work_id=review['work_id'])['state'] == 'returned'
    assert SERVICE.assignment(ctx(project), work_id=correction['work_id'])['state'] == 'delivered'
    assert SERVICE.assignment(ctx(project), work_id=followup['work_id'])['state'] == 'stopped'
    assert SERVICE.assignment(ctx(project), work_id=gc['work_id'])['stop']['by'] == 'user'
    assert actual.maximum == 1


def test_workflow_successor_retains_completed_branch_and_active_child_returns(project, run):
    from metaform.module import context as workflow_context
    from metaform.modules.workflow import catalog, executor, runs
    from metaform.modules.workflow.revisions import revise
    store, folder = project
    run('enable', 'workflow', cwd=folder)
    old = '@STATE_INIT:\n {target} := PARAM\n@RETURN:\n RETURN TRUE\n'
    catalog.submit_logic(store, NODE, 'procedures', 'inspect', old)
    lookup = lambda address, name: catalog.lookup(store, address, name)
    original = executor.start(store, f'{{ok}} := {NODE}.inspect(target=7)', {}, None, lookup,
                              {'project': 'proj', 'folder': str(folder)})
    children = executor.parallel(store, original, [f'{{first}} := {NODE}.inspect(target=1)',
        f'{{second}} := {NODE}.inspect(target=2)'], {'target': 7, 'progress': 'kept'}, lookup)
    assert executor.complete(store, children[0], 'RETURN TRUE', {}) == {'caller': original, 'state': 'waiting'}
    catalog.submit_logic(store, NODE, 'procedures', 'inspect', old + '# Keep the selected duration.\n')
    successor = revise(workflow_context('workflow', folder, project='proj', nouns={
        'run': original, 'change': 'parallel-revision', 'address': NODE, 'name': 'inspect',
        'layer': 'procedures', 'revision': '2'}))['run']
    assert runs.read(store, successor).state == 'waiting'
    assert runs.read(store, children[0]).value['parent'] == original  # completed history is immutable
    assert runs.read(store, children[1]).value['parent'] == successor
    assert executor.complete(store, children[1], 'RETURN FALSE', {}) == {'resume': successor}
    current = executor.view(store, successor)
    assert current['variables'] == {'target': 7, 'progress': 'kept', 'first': True, 'second': False}
    assert current['branches'] == [{'run': children[0], 'value': True}, {'run': children[1], 'value': False}]
    assert executor.complete(store, successor, 'RETURN TRUE', current['variables'])['value'] is True


def test_worker_handoff_keeps_return_route_and_closes_transferred_work_once(project):
    gc = root(project, candidate={'revision': 'in-progress'})
    worker = SERVICE.delegate(ctx(project, 'gc-one', role='implementer', task='Implement the timer.'))
    SERVICE.bind(ctx(project), worker['assignment_id'], 'worker')
    investigation = SERVICE.delegate(ctx(project, 'worker', role='investigator', task='Trace the alarm.'))
    successor = SERVICE.handoff(ctx(project, 'worker', role='integrator', task='Integrate the current timer.'))
    assert successor['candidate'] == {'revision': 'in-progress'}
    assert successor['return_to']['assignment_id'] == gc['assignment_id']
    retained = SERVICE.assignment(ctx(project), work_id=worker['work_id'])
    assert retained['state'] == 'transferred'
    assert retained['successor_assignment_id'] == successor['assignment_id']
    assert not project[0].ticket(worker['work_id']).work.done
    SERVICE.returned(ctx(project), investigation['work_id'], 'Alarm trace retained.')
    routes = SERVICE.pending(ctx(project), [successor['work_id']])
    assert any(one['kind'] == 'send' and one['payload'].get('result') == 'Alarm trace retained.' for one in routes)
    SERVICE.bind(ctx(project), successor['assignment_id'], 'integrator')
    final = SERVICE.handoff(ctx(project, 'integrator', role='verifier', task='Verify the integrated timer.'))
    SERVICE.returned(ctx(project), final['work_id'], 'Timer integration verified.', evidence=['Alarm remains audible.'])
    assert project[0].ticket(worker['work_id']).work.done
    assert project[0].ticket(successor['work_id']).work.done
    assert not project[0].ticket(gc['work_id']).work.done
    routes = SERVICE.pending(ctx(project), [gc['work_id']])
    received = [one for one in routes if one['kind'] == 'send' and one['payload'].get('result') ==
                'Timer integration verified.']
    assert len(received) == 1
    SERVICE.returned(ctx(project), final['work_id'], 'Duplicate return.')
    assert len(SERVICE.pending(ctx(project), [gc['work_id']])) == len(routes)


def test_gc_handoff_preserves_gc_validation_and_user_restart_preserves_descendant_stops(project):
    gc = root(project)
    specialist = SERVICE.handoff(ctx(project, 'gc-one', role='verifier', task='Verify delivery.'))
    assert SERVICE.assignment(ctx(project), work_id=gc['work_id'])['state'] == 'waiting'
    assert specialist['return_to']['assignment_id'] == gc['assignment_id']
    SERVICE.directed(ctx(project), 'gc-one', {'id': 'user-new-direction', 'body': 'Keep the alarm volume.'})
    SERVICE.directed(ctx(project), 'gc-one', {'id': 'user-new-direction', 'body': 'Keep the alarm volume.'})
    SERVICE.stopped(ctx(project), work_id=gc['work_id'], by='user', direction='Pause delivery.')
    reopened = SERVICE.reopen(ctx(project), gc['work_id'])
    assert reopened['state'] == 'queued' and reopened['stop'] is None
    assert reopened['stop_history'][-1]['direction'] == 'Pause delivery.'
    assert reopened['pending_direction'] == [{'id': 'user-new-direction', 'body': 'Keep the alarm volume.'}]
    assert SERVICE.assignment(ctx(project), work_id=specialist['work_id'])['stop']['by'] == 'user'
    SERVICE.bind(ctx(project), gc['assignment_id'], 'resumed-gc')
    assert SERVICE.context(ctx(project), session_id='resumed-gc')['pending_direction'] == reopened['pending_direction']


def test_cli_agent_cannot_claim_user_source_to_bypass_strict_mode(project, monkeypatch):
    _, folder = project
    spec = folder / 'timer-spec.md'
    spec.write_text('Keep the requested timer behavior.', encoding='utf-8')
    root(project, mode='strict', specification={'uri': str(spec)})
    review = assess(ctx(project, 'gc-one', summary='Review strict mode.', key='strict-review'))
    SERVICE.bind(ctx(project), review['assignment_id'], 'fqc', runner='fqc-runner')
    monkeypatch.setenv('METAFORM_SESSION', 'fqc-runner')
    proposal = change(ctx(project, assignment=review['assignment_id'], content='Proposed replacement.',
                           reason='A proposed approach.', user_instruction='The agent wrote this noun.'))
    assert proposal['source'] == 'agent' and proposal['state'] == 'recommendation'
    assert spec.read_text(encoding='utf-8') == 'Keep the requested timer behavior.'


def test_sessionless_agent_is_not_classified_as_new_user_instruction(project, monkeypatch):
    from metaform.modules.orchestration import specifications
    _, folder = project
    spec = folder / 'timer-spec.md'
    spec.write_text('Keep the requested timer behavior.', encoding='utf-8')
    gc = root(project, mode='strict', specification={'uri': str(spec)})
    monkeypatch.setattr(specifications, 'agent_caller', lambda: 'The caller is an external agent.')
    proposal = specifications.change(ctx(project, assignment=gc['assignment_id'], content='Proposed replacement.',
        reason='An agent proposal.', user_instruction='An agent supplied this noun without a session.'), SERVICE)
    assert proposal['source'] == 'agent' and proposal['state'] == 'recommendation'
    assert spec.read_text(encoding='utf-8') == 'Keep the requested timer behavior.'


def test_same_finding_from_two_reviews_at_one_node_gives_one_open_ticket_with_both_evidence(project):
    gc = root(project)
    SERVICE.returned(ctx(project), gc['work_id'], 'Timer outcome delivered.', state='delivered')
    for name, summary in (('a', 'Selection resets while duration changes.'),
                          ('b', '  selection RESETS while duration changes ')):
        review = SERVICE.assessment(ctx(project), gc, {'summary': 'Assess the delivered timer.'}, name)
        SERVICE.returned(ctx(project), review['work_id'], 'The selection resets.', evidence=[f'Observed in {name}.'],
                         findings=[{'summary': summary, 'remediation': ['Keep the selection.']}])
    covering = [one for one in project[0].work(node=Node('element', NODE), open=True, limit=0).results
                if 'Selection resets' in (one.task or '')]
    assert len(covering) == 1
    assert 'Observed in a.' in covering[0].note and 'Observed in b.' in covering[0].note


def test_finding_given_as_dict_yields_prose_title_and_task(project):
    gc = root(project)
    SERVICE.returned(ctx(project), gc['work_id'], 'Timer outcome delivered.', state='delivered')
    review = SERVICE.assessment(ctx(project), gc, {'summary': 'Assess the delivered timer.'}, 'prose')
    SERVICE.returned(ctx(project), review['work_id'], 'One finding.', findings=[{
        'id': 'F1', 'severity': 'medium', 'summary': 'The alarm stays silent\nat zero.',
        'remediation': ['Ring the alarm at zero.', {'file': 'alarm.js', 'step': 'Call ring().'}],
        'verify': 'Count down to zero and hear the alarm.'}])
    launch = next(one for one in SERVICE.pending(ctx(project)) if one['payload'].get('kind') == 'functional_correction')
    work_id = SERVICE.assignment(ctx(project), assignment_id=launch['assignment_id'])['work_id']
    title, task = project[0].numbers_of('work', [work_id])[work_id][1], project[0].ticket(work_id).work.task
    assert title == 'The alarm stays silent at zero.'
    assert '1. Ring the alarm at zero.' in task and 'Verify: Count down to zero' in task
    assert not set('{}') & set(title + task)


def test_assessment_calling_assess_on_its_own_work_queues_nothing(project):
    gc = root(project)
    SERVICE.returned(ctx(project), gc['work_id'], 'Timer outcome delivered.', state='delivered')
    review = SERVICE.assessment(ctx(project), gc, {'summary': 'Assess the delivered timer.'}, 'delivered')
    SERVICE.bind(ctx(project), review['assignment_id'], 'fqc')
    before = SERVICE.pending(ctx(project))
    for session in ('fqc', 'gc-one'):
        again = assess(ctx(project, session, summary='Assess my own review of this work.'))
        assert again['queued'] is False and again['assignment_id'] == review['assignment_id']
    with implementation.own(ctx(project)).tables(write=False) as tx:
        reviews = tx.rows('assignments', {'reviewed_assignment_id': gc['assignment_id']}, limit=0).results
    assert [one['assignment_id'] for one in reviews] == [review['assignment_id']]
    assert SERVICE.pending(ctx(project)) == before


def test_result_sent_twice_reaches_its_recipient_once(project, monkeypatch):
    gc = root(project)
    actual = transport(monkeypatch, project)
    actual.running.add('gc-one')
    for key in ('first', 'second'):
        SERVICE.queue_message(ctx(project), gc['assignment_id'], {'kind': 'result', 'body': 'Alarm rings at zero.',
                              'sender_assignment_id': 'worker'}, key=key)
    other = root(project, session='gc-two')
    for held in (gc, other):
        SERVICE.returned(ctx(project), held['work_id'], 'Timer outcome delivered.', state='delivered')
    SERVICE.drain(ctx(project))
    assert [envelope['body'] for _, envelope in actual.messages] == ['Alarm rings at zero.']
    # one work's result once, but two works' alike results both reach the person
    assert [message['body'] for _, message in actual.chat] == ['Timer outcome delivered.'] * 2


def test_alike_words_from_different_senders_all_arrive(project, monkeypatch):
    gc = root(project)
    actual = transport(monkeypatch, project)
    actual.running.add('gc-one')
    for key, envelope in (('n1', {'id': 'n1', 'kind': 'peer', 'text': 'yes', 'from': {'session': 'peer-a'}}),
                          ('n2', {'id': 'n2', 'kind': 'peer', 'text': 'yes', 'from': {'session': 'peer-b'}}),
                          ('b1', {'id': 'b1', 'kind': 'gc_broadcast', 'text': 'yes', 'from': {'session': 'peer-a'}}),
                          ('n3', {'id': 'n3', 'kind': 'peer', 'text': 'yes', 'from': {'session': 'peer-a'}})):
        SERVICE.queue_message(ctx(project), gc['assignment_id'], envelope, key=key)
    SERVICE.drain(ctx(project))
    # peer-a's note, peer-b's alike note and peer-a's broadcast all arrive; peer-a's repeat of its own note does not
    assert sorted(envelope['id'] for _, envelope in actual.messages) == ['b1', 'n1', 'n2']


def test_review_superseded_by_persons_decision_closes_without_filing_work(project):
    gc = root(project)
    SERVICE.returned(ctx(project), gc['work_id'], 'Timer outcome delivered.', state='delivered')
    review = SERVICE.assessment(ctx(project), gc, {'summary': 'Assess the delivered timer.'}, 'decided')
    SERVICE.directed(ctx(project), 'gc-one', {'kind': 'user_direction', 'id': 'decision', 'at': implementation.now(),
                                              'text': 'Keep the alarm as it is.', 'from': {'kind': 'user'}})
    returned = SERVICE.returned(ctx(project), review['work_id'], 'The alarm could be louder.',
                                findings=[{'summary': 'Make the alarm louder.'}])
    assert returned['state'] == 'returned' and project[0].ticket(review['work_id']).work.done
    assert not [one for one in project[0].work(node=Node('element', NODE), open=True, limit=0).results
                if 'louder' in (one.task or '')]
    assert not [one for one in SERVICE.pending(ctx(project)) if one['payload'].get('kind') == 'functional_correction']
