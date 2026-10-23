"""Real work/store transitions with a deterministic dispatch transport; no model claims."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from metaform.data import Node, StoreError
from metaform.module import Stop, context, work_reads
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
    called = ctx(project, session, work=work.id, role='gc', **nouns)
    called.nouns['session'] = session
    return SERVICE.claim(called)


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
            called = ctx(project, session, work=work.id, role='gc')
            called.nouns['session'] = session
            return SERVICE.claim(called)
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
    assert actual.messages[-1][1]['body'].endswith(' complete')
    assert 'result' not in actual.messages[-1][1]
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
    assert request['state'] == 'commissioned'
    assert request['gc_assignment_id'] == gc['assignment_id']
    with pytest.raises(Stop, match='delivery GC'):
        SERVICE.commission(ctx(project, 'worker', request=request['request_id']))
    creator = SERVICE.commission(ctx(project, 'gc-one', request=request['request_id']))
    assert creator['authored_role_uri'] == 'metaform://role/facilitator'
    ticket = project[0].numbers_of('work', [worker['work_id']])[worker['work_id']][0]
    assert '\n' not in creator['task'] and creator['task'].startswith(f'implementer {ticket}: ') and \
        creator['task'].endswith(f'for {ticket}, role alarm_domain, request {request["request_id"]}.'), creator['task']
    SERVICE.bind(ctx(project), creator['assignment_id'], 'creator')
    published = SERVICE.publish_role(ctx(project, 'creator', request=request['request_id'],
        duty='Investigate alarm timing against the requested user outcome. Return evidence to the calling worker.'))
    specialist = published['assignment']
    assert specialist['parent_assignment_id'] == worker['assignment_id']
    assert specialist['team_id'] == gc['team_id']
    assert specialist['return_to']['assignment_id'] == worker['assignment_id']
    resolution = implementation.resolve(ctx(project), 'alarm_domain')
    assert not resolution['problems']
    assert resolution['components'][-1]['name'] == 'prompt.agents:generated_proj_alarm_domain'
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
    assert request['gc_assignment_id'] == gc['assignment_id']
    assert SERVICE.assignment(ctx(project), work_id=gc['work_id'])['state'] == 'delivered'
    assert project[0].ticket(gc['work_id']).work.done
    assert SERVICE.delegate(request_ctx, waiting=True)['request_id'] == request['request_id']
    creator = SERVICE.assignment(ctx(project), assignment_id=request['creator_assignment_id'])
    assert creator['parent_assignment_id'] == review['assignment_id']
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
                        and one['kind'] == 'send' and one['payload'].get('kind') == 'result' and
                        one['payload'].get('sender_assignment_id') == specialist['assignment_id'])
    assert return_event['payload']['sender_assignment_id'] == specialist['assignment_id']
    item = project[0].numbers_of('work', [specialist['work_id']])[specialist['work_id']][0]
    assert return_event['payload']['body'] == f'{item} complete', 'a return is one line; its report stays on the ticket'
    assert return_event['payload']['body'].endswith(' complete')
    assert 'result' not in return_event['payload']
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
    assert review['evidence'] == ['Countdown integration test passes.']
    assert gc['assignment_id'] in review['task']
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
    assert 'evidence' not in gc_return[0]['payload']
    assert SERVICE.assignment(ctx(project), work_id=review['work_id'])['evidence'] == ['Observed selection reset.']
    corrections = [one for one in pending if one['payload'].get('kind') == 'functional_correction']
    assert len(corrections) == 1
    correction = SERVICE.assignment(ctx(project), assignment_id=corrections[0]['assignment_id'])
    assert correction['authored_role_uri'] == 'metaform://role/gc'
    assert correction['assignment_id'] == gc['assignment_id']
    assert correction['team_id'] == gc['team_id']
    assert correction['root_work_id'] == gc['work_id']
    assert not any(one['kind'] == 'user_message' for one in pending)


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


def test_strict_publication_reads_latest_mode_and_new_user_direction_still_applies(project, monkeypatch):
    from metaform.modules.orchestration import specifications
    monkeypatch.setattr(specifications, "agent_caller", lambda: None)
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
    instructed = change(context('orchestration', folder, project='proj', surface='web', nouns={
        'assignment': gc['assignment_id'], 'content': 'New user instruction.',
        'reason': 'The user changed the requested behavior.', 'user_instruction': 'Use this approach.'}))
    assert instructed['state'] == 'published'
    assert path.read_text() == 'New user instruction.'
    with pytest.raises(Stop, match='advanced'):
        change(ctx(project, 'fqc', content='Stale assessment.', base=fingerprint('Old approach.'), reason='Stale.'))


def test_an_amendment_changes_one_record_and_never_erases_the_others(project):
    _, folder = project
    path = folder / 'spec.md'
    records = '# Timer\n\n### TIM-001 Show the countdown\n\nAlways visible.\n\n### TIM-002 Ring once\n\nOne alarm.\n'
    questions = '\n## Open questions\n\nNone yet.\n'
    path.write_text(records + questions, encoding='utf-8')
    root(project, specification={'uri': 'file:spec.md'})
    review = assess(ctx(project, 'gc-one', summary='Review the alarm.', key='r'))
    SERVICE.bind(ctx(project), review['assignment_id'], 'fqc')
    amendment = '### TIM-003 Keep the selection\n\nAdjusting the duration keeps the selection.\n'
    change(ctx(project, 'fqc', section='TIM-003', content=amendment, reason='Adds the record.', key='add'))
    assert path.read_text(encoding='utf-8') == records + '\n' + amendment + questions
    replaced = change(ctx(project, 'fqc', section='TIM-002', content='### TIM-002 Ring twice\n\nTwo alarms.\n',
                          reason='Replaces the record.', key='replace'))
    assert path.read_text(encoding='utf-8') == records.replace('Ring once\n\nOne alarm.', 'Ring twice\n\nTwo alarms.') \
        + '\n' + amendment + questions
    told = next(one['payload']['body'] for one in SERVICE.pending(ctx(project)) if one['kind'] == 'user_message'
                and one['payload'].get('change_id') == replaced['change_id'])
    assert '@@ TIM-002 Ring twice @@' in told and '+Two alarms.' in told and '-One alarm.' in told
    assert 'TIM-001' not in told and 'None yet.' not in told
    kept = path.read_text(encoding='utf-8')
    for section, content, refusal in (
            ('TIM-02', '### TIM-002 Ring twice\n\nThree alarms.\n', "section='TIM-002 Ring twice'"),
            ('TIM-002', '### TIM-002 Ring twice\n\nTwo.\n\n' + amendment, 'holds 2 records'),
            ('TIM-002', '### TIM-001 Show the countdown\n\nHidden.\n', 'TIM-001 Show the countdown')):
        with pytest.raises(Stop) as refused:
            change(ctx(project, 'fqc', section=section, content=content, reason='Duplicates a record.', key=section))
        assert refusal in f'{refused.value} {refused.value.next_step}'
        assert path.read_text(encoding='utf-8') == kept
    with pytest.raises(Stop, match='drop 4 of its records') as refused:
        change(ctx(project, 'fqc', content=amendment, reason='The amendment alone.', key='whole'))
    assert "section='TIM-003 Keep the selection'" in refused.value.next_step
    assert path.read_text(encoding='utf-8') == kept
    with pytest.raises(Stop, match='TIM-002 Ring twice'):
        change(ctx(project, 'fqc', content='# Timer\n\n' + amendment, removing=['TIM-001', 'Open questions'],
                   reason='Unnamed.', key='w'))
    change(ctx(project, 'fqc', content='# Timer\n\n' + amendment, removing=['TIM-001', 'TIM-002', 'Open questions'],
               reason='Removes the three records it names.', key='named'))
    assert path.read_text(encoding='utf-8') == '# Timer\n\n' + amendment


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


def test_stop_all_preserves_existing_descendant_stops(project):
    gc = root(project)
    child = SERVICE.delegate(ctx(project, 'gc-one', role='implementer', task='Implement countdown.'))
    SERVICE.bind(ctx(project), child['assignment_id'], 'child')
    grandchild = SERVICE.delegate(ctx(project, 'child', role='investigator', task='Trace countdown.'))
    unrelated = root(project, 'other-gc')
    SERVICE.stopped(ctx(project), work_id=child['work_id'], by='user', direction='Keep this ticket stopped.')
    before = {one['work_id']: SERVICE.assignment(ctx(project), work_id=one['work_id'])
              for one in (child, grandchild)}

    SERVICE.stopped(ctx(project), work_id=gc['work_id'], by='user', every=True)

    assert SERVICE.assignment(ctx(project), work_id=gc['work_id'])['stop']['every']
    for work_id, original in before.items():
        retained = SERVICE.assignment(ctx(project), work_id=work_id)
        assert retained['stop'] == original['stop']
        assert retained['stop_history'] == original['stop_history']
    SERVICE.reopen(ctx(project), gc['work_id'])
    assert all(SERVICE.assignment(ctx(project), work_id=work_id)['state'] == 'stopped' for work_id in before)
    assert SERVICE.assignment(ctx(project), work_id=unrelated['work_id'])['stop'] is None


def test_unrelated_change_burst_reads_no_assignment(project, monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail('An unrelated event read orchestration state.')
    monkeypatch.setattr(SERVICE, 'assignment', unexpected)
    for _ in range(100):
        work_changed({'project': 'proj', 'tables': ['memory.entities'], 'work_ids': ['irrelevant']}, ctx(project))
        work_changed({'project': 'proj', 'tables': ['memory.entities']}, ctx(project))


def test_public_board_completion_with_mixed_write_routes_child_and_gc_assessment(project):
    from metaform import settings
    settings.put('orchestration_reviews', 1, project[1])
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
    assert 'evidence' not in result['payload']
    assert SERVICE.assignment(ctx(project), work_id=child['work_id'])['evidence'] == [
        'Selected control remains selected after duration changes.']
    SERVICE.check_in(ctx(project, 'gc-one', state='running', summary='GC integrated and validated the outcome.',
        candidate={'revision': 'board-candidate'}, evidence=['Countdown, alarm and adjustment interaction passed.']))
    _, gc_events = changes.announced(project[1], 'cli', finish_with_settings_write,
                                     gc['work_id'], 'The GC delivered the timer outcome.')
    assert any('work' in event.get('tables', ()) and 'work_ids' not in event for event in gc_events)
    assert SERVICE.assignment(ctx(project), work_id=gc['work_id'])['state'] == 'delivered'
    pending = SERVICE.pending(ctx(project))
    assessment = next(one for one in pending if one['kind'] == 'assessment')
    assert assessment['payload']['report'] == {}
    retained = SERVICE.assignment(ctx(project), work_id=gc['work_id'])
    assert retained['candidate'] == {'revision': 'board-candidate'}
    assert retained['evidence'] == ['Countdown, alarm and adjustment interaction passed.']
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
    assert len(returns) == 2
    assert all(one['body'].endswith(' complete') and 'result' not in one for one in returns)
    assert len({one['transition_id'] for one in returns}) == 2
    assert actual.maximum == 1


def test_gc_delivery_closes_root_and_restart_activates_fqc_once(project, monkeypatch):
    from metaform import settings
    settings.put('orchestration_reviews', 1, project[1])
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
    assert gc['work_id'] in assessment['task']
    assert gc['assignment_id'] in assessment['task']
    assert actual.chat == []
    retained = SERVICE.assignment(ctx(project), work_id=gc['work_id'])
    assert retained['candidate'] == {'revision': 'integrated-candidate'}
    assert retained['evidence'] == ['Actual countdown and alarm interactions passed.']
    SERVICE.returned(ctx(project), gc['work_id'], 'Duplicate completion event.', state='delivered')
    Orchestration().drain(ctx(project))
    assert len(actual.launches) == 1
    assert SERVICE.assignment(ctx(project), work_id=gc['work_id'])['state'] == 'delivered'


def assessment_board(project, work_id):
    from metaform.data import Store
    with Store('proj', module='map').tables(write=False) as tx:
        return (tx.get('ticket_settings', {'work_id': work_id}) or {}).get('board')


def assessment_parent(project):
    from metaform.modules.map import boards, work
    boards(context('map', project[1], project='proj', nouns={'op': 'add', 'name': 'delivery'}))
    boards(context('map', project[1], project='proj', nouns={'op': 'add', 'name': 'aside'}))
    gc = root(project)
    work(context('map', project[1], project='proj', nouns={
        'op': 'edit', 'id': gc['work_id'], 'board': 'delivery'}))
    return gc


def test_assessment_inherits_owner_board_instead_of_active_board(project):
    gc = assessment_parent(project)
    review = SERVICE.assessment(ctx(project), gc, {}, 'board')
    assert assessment_board(project, review['work_id']) == 'delivery'
    assert SERVICE.assessment(ctx(project), gc, {}, 'board')['work_id'] == review['work_id']


@pytest.mark.parametrize('recovery', ['assessment', 'launch'])
@pytest.mark.parametrize('placement', [None, '', 'aside', 'legacy_first'])
def test_generated_assessment_recovery_preserves_explicit_placement(project, monkeypatch, recovery, placement):
    from metaform.data import Store
    from metaform.modules.map import work
    gc = assessment_parent(project)
    review = SERVICE.assessment(ctx(project), gc, {}, 'board')
    # A generated child with no settings row has provably never received canonical board placement.
    with Store('proj', module='map').tables() as tx:
        tx.delete('ticket_settings', {'work_id': review['work_id']})
        if placement == 'legacy_first':
            # Old canonical board='' edits stored NULL, indistinguishable from runtime-only settings rows.
            tx.insert('ticket_settings', {'work_id': review['work_id'], 'board': None, 'agent': 'codex'})
    if placement is not None and placement != 'legacy_first':
        work(context('map', project[1], project='proj', nouns={
            'op': 'edit', 'id': review['work_id'], 'board': placement}))
    unrelated = project[0].add_work(Node('element', NODE), None, task='Keep set-aside work.')
    actual = transport(monkeypatch, project)
    if recovery == 'assessment':
        assert Orchestration().assessment(ctx(project), gc, {}, 'board')['work_id'] == review['work_id']
    else:
        Orchestration().drain(ctx(project))
        assert len(actual.launches) == 1
    expected = 'delivery' if placement is None else None if placement == 'legacy_first' else placement
    assert assessment_board(project, review['work_id']) == expected
    before = project[0].ticket(review['work_id']).work
    Orchestration().assessment(ctx(project), gc, {}, 'board')
    assert project[0].ticket(review['work_id']).work == before
    assert assessment_board(project, unrelated.id) is None


@pytest.mark.parametrize('stop_owner', [False, True])
def test_generated_assessment_recovery_preserves_person_stop(project, monkeypatch, stop_owner):
    from metaform.data import Store
    gc = assessment_parent(project)
    review = SERVICE.assessment(ctx(project), gc, {}, 'stopped')
    with Store('proj', module='map').tables() as tx:
        tx.delete('ticket_settings', {'work_id': review['work_id']})
    SERVICE.stopped(ctx(project), work_id=gc['work_id'] if stop_owner else review['work_id'], by='user')
    stopped = SERVICE.assignment(ctx(project), work_id=review['work_id'])
    actual = transport(monkeypatch, project)
    Orchestration().assessment(ctx(project), gc, {}, 'stopped')
    Orchestration().drain(ctx(project))
    assert actual.launches == []
    assert SERVICE.assignment(ctx(project), work_id=review['work_id'])['stop'] == stopped['stop']
    assert assessment_board(project, review['work_id']) is None


def test_blocker_crash_retains_report_and_full_capacity_assessment_progresses(project, monkeypatch):
    from metaform import settings
    settings.put('orchestration_reviews', 1, project[1])
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
    assert actual.launches[0][0]['last_check_in']['work_so_far'] == 'Candidate working tree and trace retained.'


@pytest.mark.parametrize('outcome', ['cancelled', 'completed'])
@pytest.mark.parametrize('source', ['commission', 'delivery'])
def test_blocked_commission_under_closed_gc_creates_no_assessment(project, outcome, source):
    store, _ = project
    gc = root(project)
    session = 'gc-one'
    if source == 'commission':
        request = SERVICE.delegate(ctx(project, 'gc-one', role='unpublished_alarm_expertise', task='Inspect alarm.'))
        SERVICE.bind(ctx(project), request['creator_assignment_id'], 'creator')
        session = 'creator'
    store.finish_work(gc['work_id'], 'Closed by the person.', outcome=outcome)
    before = {one.id for one in store.work(limit=0).results}

    SERVICE.check_in(ctx(project, session, state='blocked', summary='Publication held.', key='held'))
    transport_events = SERVICE.pending(ctx(project))

    assert {one.id for one in store.work(limit=0).results} == before
    assert not any(one['kind'] == 'assessment' for one in transport_events)


@pytest.mark.parametrize('source', ['commission', 'assessment', 'assessment_specialist', 'assessment_commission'])
def test_blocked_helper_chain_never_reassesses_live_gc(project, source):
    store, _ = project
    gc = root(project)
    if source == 'commission':
        request = SERVICE.delegate(ctx(project, 'gc-one', role='unpublished_alarm_expertise', task='Inspect alarm.'))
        blocked = SERVICE.assignment(ctx(project), assignment_id=request['creator_assignment_id'])
    else:
        blocked = assess(ctx(project, 'gc-one', summary='Inspect countdown.', key='first-review'))
        SERVICE.bind(ctx(project), blocked['assignment_id'], 'reviewer')
        if source == 'assessment_specialist':
            blocked = SERVICE.delegate(ctx(project, 'reviewer', role='verifier', task='Inspect alarm.'))
        elif source == 'assessment_commission':
            request = SERVICE.delegate(ctx(project, 'reviewer', role='unpublished_alarm_expertise', task='Inspect alarm.'))
            blocked = SERVICE.assignment(ctx(project), assignment_id=request['creator_assignment_id'])
    SERVICE.bind(ctx(project), blocked['assignment_id'], 'blocked-helper')
    before = {one.id for one in store.work(limit=0).results}

    SERVICE.check_in(ctx(project, 'blocked-helper', state='blocked', summary='Cannot continue.', key='held'))

    assert {one.id for one in store.work(limit=0).results} == before
    assert not any(one['kind'] == 'assessment' for one in SERVICE.pending(ctx(project)))
    assert not store.ticket(gc['work_id']).work.done


@pytest.mark.parametrize('outcome', ['cancelled', 'completed'])
def test_closed_ticket_never_requests_runtime_commission(project, monkeypatch, outcome):
    store, _ = project
    gc = root(project)
    store.finish_work(gc['work_id'], 'Closed by the person.', outcome=outcome)

    def unexpected_runtime(*args, **kwargs):
        pytest.fail('Closed work reached runtime selection.')

    monkeypatch.setattr(SERVICE, 'runtime', unexpected_runtime)
    before = {one.id for one in store.work(limit=0).results}
    assert not SERVICE.prepare_runtime(ctx(project), gc)
    assert {one.id for one in store.work(limit=0).results} == before


def test_missing_runtime_creator_is_recommissioned_once(project):
    gc = root(project)
    request = SERVICE.request_role(ctx(project, task='Choose runtime.', key='runtime-recovery',
        context={'assign_in_place': True, 'runtime_only': True}), gc, 'gc')
    store = implementation.own(ctx(project))
    with store.tables() as tx:
        tx.delete('assignments', {'assignment_id': request['creator_assignment_id']})

    assert not SERVICE.prepare_runtime(ctx(project), gc)
    with store.tables(write=False) as tx:
        recovered = tx.get('role_requests', {'request_id': request['request_id']})
        creator = implementation.row_for(tx, assignment_id=recovered['creator_assignment_id'])
    assert creator is not None
    assert creator['assignment_id'] != request['creator_assignment_id']
    assert creator['parent_assignment_id'] == gc['assignment_id']
    assert creator['return_to']['role_request_id'] == request['request_id']
    launches = [one for one in SERVICE.pending(ctx(project))
                if one['assignment_id'] == creator['assignment_id'] and one['kind'] == 'launch']
    assert len(launches) == 1
    before = {one.id for one in project[0].work(limit=0).results}
    assert not SERVICE.prepare_runtime(ctx(project), gc)
    assert {one.id for one in project[0].work(limit=0).results} == before


@pytest.mark.parametrize('protection', ['caller_stop', 'creator_stop', 'creator_ended', 'held', 'closed'])
def test_missing_runtime_recovery_preserves_deliberate_waits(project, protection):
    gc = root(project)
    request = SERVICE.request_role(ctx(project, task='Choose runtime.', key='runtime-recovery',
        context={'assign_in_place': True, 'runtime_only': True}), gc, 'gc')
    store = implementation.own(ctx(project))
    with store.tables() as tx:
        if protection.startswith('creator_'):
            tx.update('assignments', {'assignment_id': request['creator_assignment_id']},
                      {'state': 'stopped' if protection == 'creator_stop' else 'returned',
                       'stop': {'by': 'person'} if protection == 'creator_stop' else None})
        else:
            tx.delete('assignments', {'assignment_id': request['creator_assignment_id']})
        if protection == 'caller_stop':
            tx.update('assignments', {'assignment_id': gc['assignment_id']}, {'stop': {'by': 'person'}})
    if protection == 'held':
        project[0].move_work(gc['work_id'], 'backlog', kept=True, hold_reason='Wait for user direction.')
    elif protection == 'closed':
        project[0].finish_work(gc['work_id'], 'Cancelled by the person.', outcome='cancelled')
    before = {one.id for one in project[0].work(limit=0).results}
    assert not SERVICE.prepare_runtime(ctx(project), gc)
    assert {one.id for one in project[0].work(limit=0).results} == before


@pytest.mark.parametrize('outcome', ['cancelled', 'completed'])
def test_closed_ticket_consumes_stale_launch_before_runtime_selection(project, monkeypatch, outcome):
    from metaform.modules.dispatch.orchestration import Transport as DispatchTransport

    store, _ = project
    gc = root(project)
    with implementation.own(ctx(project)).tables() as tx:
        implementation.transition(tx, gc, 'launch', {}, 'stale')
    store.finish_work(gc['work_id'], 'Closed by the person.', outcome=outcome)
    actual = DispatchTransport()

    def unexpected_runtime(*args, **kwargs):
        pytest.fail('A stale launch reached runtime selection.')

    monkeypatch.setattr(SERVICE, 'prepare_runtime', unexpected_runtime)
    monkeypatch.setattr(implementation, 'provided', lambda folder, kind: [('dispatch', actual)])
    SERVICE.drain(ctx(project))

    assert not any(one['kind'] == 'launch' for one in SERVICE.pending(ctx(project)))


def test_pending_blocked_assessment_skips_gc_closed_before_recovery(project, monkeypatch):
    store, _ = project
    gc = root(project)
    worker = SERVICE.delegate(ctx(project, 'gc-one', role='implementer', task='Preserve view state.'))
    SERVICE.bind(ctx(project), worker['assignment_id'], 'worker')
    with monkeypatch.context() as patch:
        patch.setattr(SERVICE, 'assessment', lambda *args, **kwargs: None)
        SERVICE.check_in(ctx(project, 'worker', state='blocked', summary='View selection resets.', key='block'))
    store.finish_work(gc['work_id'], 'Cancelled by the person.', outcome='cancelled')
    before = {one.id for one in store.work(limit=0).results}
    transport(monkeypatch, project)

    SERVICE.drain(ctx(project))

    assert {one.id for one in store.work(limit=0).results} == before
    assert not any(one['kind'] == 'assessment' for one in SERVICE.pending(ctx(project)))


def test_runtime_selection_cannot_commission_after_concurrent_cancellation(project, monkeypatch):
    store, _ = project
    gc = root(project)

    def cancelled_during_selection(*args, **kwargs):
        store.finish_work(gc['work_id'], 'Cancelled during runtime selection.', outcome='cancelled')
        return {'state': 'needs_choice'}

    monkeypatch.setattr(SERVICE, 'runtime', cancelled_during_selection)
    before = {one.id for one in store.work(limit=0).results}
    with pytest.raises(Stop, match='closed before its role request'):
        SERVICE.prepare_runtime(ctx(project), gc)
    assert {one.id for one in store.work(limit=0).results} == before


@pytest.mark.parametrize('source', ['delivery', 'commission', 'assessment', 'cancelled', 'completed'])
def test_legacy_blocked_transition_recovers_source_before_assessment(project, monkeypatch, source):
    from metaform import settings
    settings.put('orchestration_reviews', 1, project[1])
    store, _ = project
    gc = root(project)
    if source == 'commission':
        request = SERVICE.delegate(ctx(project, 'gc-one', role='unpublished_alarm_expertise', task='Inspect alarm.'))
        blocked = SERVICE.assignment(ctx(project), assignment_id=request['creator_assignment_id'])
    elif source == 'assessment':
        blocked = assess(ctx(project, 'gc-one', summary='Inspect alarm.', key='original'))
    else:
        blocked = SERVICE.delegate(ctx(project, 'gc-one', role='implementer', task='Inspect alarm.'))
    SERVICE.bind(ctx(project), blocked['assignment_id'], 'blocked-worker')
    with monkeypatch.context() as patch:
        patch.setattr(SERVICE, 'assessment', lambda *args, **kwargs: None)
        SERVICE.check_in(ctx(project, 'blocked-worker', state='blocked', summary='Alarm cannot ring.', key='legacy'))
    held = SERVICE.assignment(ctx(project), assignment_id=blocked['assignment_id'])
    key = implementation.identity(blocked['assignment_id'], 'check_in', 'legacy')
    payload = {'report': held['last_check_in'], 'key': key}
    with implementation.own(ctx(project)).tables() as tx:
        event = implementation.transition(tx, gc, 'assessment', payload, key)
        tx.update('transitions', {'transition_id': event['transition_id']}, {'payload': payload})
    if source in ('cancelled', 'completed'):
        store.finish_work(gc['work_id'], 'Closed before recovery.', outcome=source)
    before = {one.id for one in store.work(limit=0).results}
    transport(monkeypatch, project)

    SERVICE.drain(ctx(project))

    after = {one.id for one in store.work(limit=0).results}
    assert len(after - before) == (1 if source == 'delivery' else 0)
    assert not any(one['kind'] == 'assessment' for one in SERVICE.pending(ctx(project)))


def test_workflow_revision_preserves_frozen_history_variables_and_return_route(project, run):
    from metaform.module import context as workflow_context
    from metaform.modules.workflow import catalog, executor, runs
    from metaform.modules.workflow.revisions import revise
    store, folder = project
    run('enable', 'workflow', cwd=folder)
    old = '@STATE_INIT:\n {target} := PARAM\n@RETURN:\n RETURN TRUE\n'
    new = '@STATE_INIT:\n {target} := PARAM\n@RETURN:\n RETURN FALSE\n'
    catalog.submit_prompt(store, NODE, 'procedures', 'inspect', old)
    catalog.submit_prompt(store, NODE, 'procedures', 'outer', old)
    lookup = lambda address, name: catalog.lookup(store, address, name)
    caller = executor.start(store, f'({{ok}}) := {NODE}.outer(target=7)', {}, None, lookup,
                            {'project': 'proj', 'folder': str(folder)})
    original = executor.call(store, caller, f'{{ok}} := {NODE}.inspect(target=7)',
                             {'caller_progress': 'retained'}, lookup, fresh=True)
    state = runs.held(store, original).value
    state['frames'][-1]['variables'] = executor.pack({'target': 7, 'steps_completed': 2})
    runs.save(store, original, state)
    catalog.submit_prompt(store, NODE, 'procedures', 'inspect', new)
    revision_ctx = workflow_context('workflow', folder, project='proj', nouns={
        'run': original, 'change': 'change-workflow', 'address': NODE, 'name': 'inspect',
        'layer': 'procedures', 'revision': '2'})
    moved = revise(revision_ctx)
    assert executor.view(store, moved['run'])['prompt']['content'] == new
    assert executor.view(store, moved['run'])['variables']['steps_completed'] == 2
    history = runs.read(store, original)
    assert history.state == 'cancelled'
    assert history.value['frames'][-1]['call']['prompt']['content'] == old
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
    catalog.submit_prompt(store, NODE, 'procedures', 'inspect', old)
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
    catalog.submit_prompt(store, NODE, 'procedures', 'inspect', old)
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
            catalog.submit_prompt(store, NODE, 'procedures', 'inspect', newer)
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
    assert executor.view(store, current['run'])['prompt']['content'] == newer
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


def test_corrective_gc_keeps_ticket_evidence_without_system_notifications(project, monkeypatch):
    from metaform import settings
    settings.put('orchestration_reviews', 1, project[1])
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
    assert correction['work_id'] == gc['work_id']
    assert SERVICE.assignment(ctx(project), work_id=gc['work_id'])['state'] == 'running'
    SERVICE.returned(ctx(project), correction['work_id'], 'Duration selection is preserved.', state='delivered',
                     candidate={'revision': 'corrected-b'}, evidence=['Changed duration during active countdown.'])
    actual.running.discard(session)
    launches = len(actual.launches)
    SERVICE.drain(ctx(project))
    assert len(actual.launches) == launches, 'The configured review budget prevents a recursive review chain.'
    assert actual.chat == []
    retained = SERVICE.assignment(ctx(project), work_id=correction['work_id'])
    assert retained['candidate'] == {'revision': 'corrected-b'}
    assert retained['evidence'] == ['Changed duration during active countdown.']
    stopped = SERVICE.stopped(ctx(project), work_id=gc['work_id'], by='user')
    assert {gc['work_id'], review['work_id']} <= set(stopped)
    assert SERVICE.assignment(ctx(project), work_id=gc['work_id'])['state'] == 'delivered'
    assert SERVICE.assignment(ctx(project), work_id=gc['work_id'])['stop']['by'] == 'user'
    assert actual.maximum == 1


def test_workflow_successor_retains_completed_branch_and_active_child_returns(project, run):
    from metaform.module import context as workflow_context
    from metaform.modules.workflow import catalog, executor, runs
    from metaform.modules.workflow.revisions import revise
    store, folder = project
    run('enable', 'workflow', cwd=folder)
    old = '@STATE_INIT:\n {target} := PARAM\n@RETURN:\n RETURN TRUE\n'
    catalog.submit_prompt(store, NODE, 'procedures', 'inspect', old)
    lookup = lambda address, name: catalog.lookup(store, address, name)
    original = executor.start(store, f'{{ok}} := {NODE}.inspect(target=7)', {}, None, lookup,
                              {'project': 'proj', 'folder': str(folder)})
    children = executor.parallel(store, original, [f'{{first}} := {NODE}.inspect(target=1)',
        f'{{second}} := {NODE}.inspect(target=2)'], {'target': 7, 'progress': 'kept'}, lookup)
    assert executor.complete(store, children[0], 'RETURN TRUE', {}) == {'caller': original, 'state': 'waiting'}
    catalog.submit_prompt(store, NODE, 'procedures', 'inspect', old + '# Keep the selected duration.\n')
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
    assert any(one['kind'] == 'send' and one['payload'].get('work_id') == investigation['work_id'] for one in routes)
    SERVICE.bind(ctx(project), successor['assignment_id'], 'integrator')
    final = SERVICE.handoff(ctx(project, 'integrator', role='verifier', task='Verify the integrated timer.'))
    SERVICE.returned(ctx(project), final['work_id'], 'Timer integration verified.', evidence=['Alarm remains audible.'])
    assert project[0].ticket(worker['work_id']).work.done
    assert project[0].ticket(successor['work_id']).work.done
    assert not project[0].ticket(gc['work_id']).work.done
    routes = SERVICE.pending(ctx(project), [gc['work_id']])
    received = [one for one in routes if one['kind'] == 'send' and one['payload'].get('work_id') == final['work_id']]
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


@pytest.mark.parametrize('given', [({'uri': 'file:missing.md'}), 'None'])
def test_change_to_a_missing_specification_file_stops_with_an_answer(project, given):
    gc = root(project)
    with pytest.raises(Stop, match='No specification file at'):
        change(ctx(project, assignment=gc['assignment_id'], content='Revised.', reason='The file is not there.',
                   specification=given))


@pytest.mark.parametrize('given', [None, {'kind': 'file'}, {'uri': ''}])
def test_change_on_a_ticket_without_a_specification_revises_its_task(project, given):
    store, folder = project
    gc = root(project)
    review = assess(ctx(project, 'gc-one', summary='Review the timer.', key='r'))
    SERVICE.bind(ctx(project), review['assignment_id'], 'fqc')
    changed = change(ctx(project, 'fqc', content='Preserve countdown, alarm and selection.',
                         reason='Keeping the selection serves the person setting the timer.', specification=given))
    assert changed['state'] == 'published'
    assert changed['specification']['uri'] == f'work:{gc["work_id"]}'
    assert changed['before_content'] == 'Preserve countdown and alarm behavior.'
    assert store.ticket(gc['work_id']).work.task == 'Preserve countdown, alarm and selection.'
    assert not (folder / 'None').exists()
    told = next(one['payload']['body'] for one in SERVICE.pending(ctx(project)) if one['kind'] == 'user_message'
                and one['payload'].get('change_id') == changed['change_id'])
    assert 'Preserve countdown, alarm and selection.' in told and '@@' not in told  # a task is told whole, not as a diff
    again = change(ctx(project, 'fqc', content='Preserve countdown, alarm, selection and volume.',
                       reason='The volume too.', key='second'))
    assert again['previous_revision'] == changed['current_revision']
    assert store.ticket(gc['work_id']).work.task == 'Preserve countdown, alarm, selection and volume.'


def test_same_finding_from_two_reviews_at_one_node_gives_one_open_ticket_with_both_evidence(project):
    gc = root(project)
    SERVICE.returned(ctx(project), gc['work_id'], 'Timer outcome delivered.', state='delivered')
    for name, summary in (('a', 'Selection resets while duration changes.'),
                          ('b', '  selection RESETS while duration changes ')):
        review = SERVICE.assessment(ctx(project), gc, {'summary': 'Assess the delivered timer.'}, name)
        SERVICE.returned(ctx(project), review['work_id'], 'The selection resets.', evidence=[f'Observed in {name}.'],
                         findings=[{'summary': summary, 'remediation': ['Keep the selection.']}])
    covering = [one for one in project[0].work(node=Node('element', NODE), open=True, limit=0).results
                if one.id == gc['work_id']]
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
    title = project[0].numbers_of('work', [work_id])[work_id][1]
    assert work_id == gc['work_id'] and title == 'Timer delivery'
    note = project[0].ticket(work_id).work.note
    assert '1. Ring the alarm at zero.' in note and 'Verify: Count down to zero' in note
    assert not set('{}') & set(note)


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
    # dispatch envelopes carry no sender assignment: each note, reply or broadcast arrives by its own id, even when
    # one peer says the same words twice
    for key, envelope in (('n1', {'id': 'n1', 'kind': 'peer', 'text': 'yes', 'from': {'session': 'peer-a'}}),
                          ('n2', {'id': 'n2', 'kind': 'peer', 'text': 'yes', 'from': {'session': 'peer-a'},
                                  'reply_to': 'q2'}),
                          ('b1', {'id': 'b1', 'kind': 'gc_broadcast', 'text': 'yes', 'from': {'session': 'peer-b'}})):
        SERVICE.queue_message(ctx(project), gc['assignment_id'], envelope, key=key)
    SERVICE.drain(ctx(project))
    assert sorted(envelope.get('body') or envelope['id'] for _, envelope in actual.messages) == [
        'Alarm rings at zero.', 'b1', 'n1', 'n2']


def test_component_name_in_user_direction_never_discards_review_findings(project, monkeypatch):
    read = []
    rows = implementation.TableTx.rows
    monkeypatch.setattr(implementation.TableTx, 'rows', lambda tx, table, *a, **k: read.append((table, a, k)) or
                        rows(tx, table, *a, **k))

    _, folder = project
    (folder / 'spec.md').write_text('Old approach.', encoding='utf-8')

    def reviewed(session, said, finding, ordered=False):
        gc = root(project, session=session, **({'specification': {'uri': 'file:spec.md'}} if ordered else {}))
        SERVICE.returned(ctx(project), gc['work_id'], 'Timer outcome delivered.', state='delivered')
        review = SERVICE.assessment(ctx(project), gc, {'summary': 'Assess the delivered timer.'}, session)
        if ordered:
            change(context('orchestration', folder, project='proj', surface='web', nouns={
                'assignment': gc['assignment_id'], 'content': 'New approach.',
                'reason': 'The person decided.', 'user_instruction': said}))
        else:
            SERVICE.directed(ctx(project), session, {'kind': 'user_direction', 'id': session,
                                                     'at': implementation.now(), 'text': said,
                                                     'from': {'kind': 'user'}})
        read.clear()
        returned = SERVICE.returned(ctx(project), review['work_id'], 'The alarm could be louder.',
                                    findings=[{'summary': finding}])
        assert returned['state'] == 'returned' and project[0].ticket(review['work_id']).work.done
        assert not [one for one in read if one[0] == 'changes']
        held = SERVICE.assignment(ctx(project), assignment_id=gc['assignment_id'])
        return [one for one in held['pending_direction'] if one.get('kind') == 'review_finding'
                and one.get('reviewed_assignment_id') == review['assignment_id']]

    # the person's word about another part is not a decision about this one: the finding is filed
    assert reviewed('gc-one', 'Leave code.loop.tick as it is.', 'Make the alarm louder.')
    # Naming the reviewed component does not supersede its individual defects.
    assert reviewed('gc-two', 'Keep code.timer.kitchen as it is.', 'Make the countdown visible.')
    # Short names have no stronger implication than exact component addresses.
    assert reviewed('gc-three', 'Leave the loop tick alone.', 'Make the alarm flash.')
    assert reviewed('gc-four', 'Keep the kitchen timer as it is.', 'Show the time left.')
    # A change order requires a reasoned per-finding reconciliation too.
    assert reviewed('gc-five', 'Keep the kitchen timer as it is.', 'Ring twice.', ordered=True)


def test_relayed_user_decision_preserves_review_findings_without_explicit_reconciliation(
        project, run, monkeypatch):
    """A note the person's own system agent marks decision=true, in the turn the person's message started, is kept
    on the GC's assignment as a user_direction with that message. Findings remain actionable until individually
    reconciled against that message. Marked so in any other turn, it is refused."""
    from metaform.modules.dispatch import peering
    store, folder = project
    run('enable', 'dispatch', cwd=folder)
    gc = root(project)
    SERVICE.returned(ctx(project), gc['work_id'], 'Timer outcome delivered.', state='delivered')
    review = SERVICE.assessment(ctx(project), gc, {'summary': 'Assess the delivered timer.'}, 'decided')
    words = 'Keep code.timer.kitchen as it is.'
    asked = {'id': 'person-1', 'text': words, 'at': implementation.now()}
    mine = {'work_id': 'system-work', 'session_id': 'system-session', 'runner': 'system-runner', 'agent': 'claude'}
    entry = {'work_id': gc['work_id'], 'session_id': 'gc-one', 'item': 'gc', 'agent': 'claude', '_row': {}}
    monkeypatch.setattr(peering, 'caller', lambda _: (None, mine))
    monkeypatch.setattr(peering, 'side', lambda *_: {'session_id': 'system-session', 'agent': 'claude'})
    monkeypatch.setattr(peering, 'chosen', lambda *_: (gc['work_id'], 'to', [entry], None))
    monkeypatch.setattr(peering, 'told', lambda *_, **__: {'noted': True})
    monkeypatch.setattr(peering, 'persons_word', lambda *_, **__: None)
    with pytest.raises(Stop, match='Only the person\'s own system agent relays their decision'):
        peering.send(context('dispatch', folder, project='proj', nouns={'decision': True}), store, words, 0)
    monkeypatch.setattr(peering, 'persons_word', lambda *_, **__: dict(asked))
    sent = peering.send(context('dispatch', folder, project='proj', nouns={'decision': True}), store, words, 0)
    [direction] = SERVICE.assignment(ctx(project), session_id='gc-one')['pending_direction']
    assert direction['kind'] == 'user_direction' and direction['id'] == sent['note']
    assert direction['message'] == asked and direction['from']['kind'] == 'user'
    returned = SERVICE.returned(ctx(project), review['work_id'], 'The alarm could be louder.',
                                findings=[{'summary': 'Make the alarm louder.'}])
    assert returned['state'] == 'returned' and store.ticket(review['work_id']).work.done
    assert returned['findings'][0]['disposition'] == 'correction'
    held = SERVICE.assignment(ctx(project), assignment_id=gc['assignment_id'])
    assert any(one.get('kind') == 'review_finding' and 'louder' in one['body']
               for one in held['pending_direction'])


def test_a_tickets_read_shows_its_gc_steps_result_and_linked_assessment(project, monkeypatch):
    from metaform import settings
    settings.put('orchestration_reviews', 1, project[1])
    """The board shows whether work was done: the steps and result of a ticket's GC assignment are on that ticket,
    and its read links the assessment that reviewed it, by assignment and ticket, with its state and result."""
    store, folder = project
    gc = root(project)
    store.plan_work(gc['work_id'], 2)
    store.step_work(gc['work_id'], 'Traced the alarm.')
    store.step_work(gc['work_id'], 'Fixed the countdown.')
    SERVICE.returned(ctx(project, 'gc-one'), gc['work_id'], 'Timer outcome delivered.', state='delivered',
                     evidence=['The alarm rang at zero.'])
    transport(monkeypatch, project)
    Orchestration().drain(ctx(project))
    review = SERVICE.related(ctx(project), gc['assignment_id'])['independent_assessments'][0]
    SERVICE.returned(ctx(project), review['work_id'], 'Countdown and alarm pass.', evidence=['Observed the alarm.'])
    work = store.ticket(gc['work_id']).work
    assert (work.steps, work.steps_done, work.resolution) == (2, 2, 'Timer outcome delivered.')
    read = work_reads(folder, work, project='proj')['orchestration']
    assert (read['assignment_id'], read['state'], read['result']) == (
        gc['assignment_id'], 'delivered', 'Timer outcome delivered.')
    assert [(one['assignment_id'], one['work_id'], one['state'], one['result'])
            for one in read['independent_assessments']] == [
        (review['assignment_id'], review['work_id'], 'returned', 'Countdown and alarm pass.')]


def test_a_tickets_read_shows_the_open_ticket_its_reviews_finding_was_folded_into(project):
    """A finding an open ticket at the node already covers goes into that ticket's note; the reviewed ticket's read
    names that ticket under the assessment, so work landing elsewhere points back."""
    store, folder = project
    gc = root(project)
    covering = store.add_work(Node('element', NODE), None, task='Selection resets while duration changes.',
                              title='Selection resets')
    SERVICE.returned(ctx(project), gc['work_id'], 'Timer outcome delivered.', state='delivered')
    review = SERVICE.assessment(ctx(project), gc, {'summary': 'Assess the delivered timer.'}, 'fold')
    SERVICE.returned(ctx(project), review['work_id'], 'The selection resets.',
                     findings=[{'summary': 'Selection resets while duration changes.'}])
    read = work_reads(folder, store.ticket(gc['work_id']).work, project='proj')['orchestration']
    assert [one['findings_filed'] for one in read['independent_assessments']] == [[covering.id]]
    assert 'related_corrections' not in read


@pytest.mark.parametrize('start', ['claim', 'ensure'])
@pytest.mark.parametrize('state', ['returned', 'delivered', 'failed'])
def test_default_delivery_keeps_report_on_ticket_without_notifications(project, monkeypatch, start, state):
    from metaform import settings
    from metaform.modules.orchestration import claim
    assert settings.value('orchestration_reviews', project[1]) == 0
    work = project[0].add_work(Node('element', NODE), None, task='Preserve alarm behavior.', title='Alarm')
    called = ctx(project, 'owner', work=work.id, role='implementer')
    called.nouns['session'] = 'owner'
    if start == 'claim':
        assigned = claim(called)
        assert set(assigned) == {'assignment_id', 'state'}
    else:
        SERVICE.ensure(ctx(project), work.id, role='implementer', session_id='owner')
    assert SERVICE.assignment(ctx(project), work_id=work.id)['return_to'] is None
    SERVICE.check_in(ctx(project, 'owner', state=state, summary='Measured alarm remains audible.',
                         candidate={'revision': 'alarm-a'}, evidence=['Alarm at zero.']))
    pending = SERVICE.pending(ctx(project))
    assert not any(one['kind'] in ('assessment', 'send', 'user_message') for one in pending)
    assert project[0].ticket(work.id).work.resolution == 'Measured alarm remains audible.'
    assert project[0].ticket(work.id).work.outcome == ('failed' if state == 'failed' else 'completed')
    retained = work_reads(project[1], project[0].ticket(work.id).work, project='proj')['orchestration']
    assert retained['result'] == 'Measured alarm remains audible.'
    assert retained['candidate'] == {'revision': 'alarm-a'}
    assert retained['evidence'] == ['Alarm at zero.']
    actual = transport(monkeypatch, project)
    SERVICE.drain(ctx(project))
    assert actual.launches == []
    assert actual.chat == []


def test_child_completion_never_wakes_closed_caller(project):
    gc = root(project)
    child = SERVICE.delegate(ctx(project, 'gc-one', role='investigator', task='Inspect the caller contribution.',
                                 key='closed-caller'), waiting=True)
    project[0].finish_work(gc['work_id'], 'The request was withdrawn.', 'No continuation remains.', outcome='cancelled')
    before = SERVICE.pending(ctx(project))
    SERVICE.returned(ctx(project), child['work_id'], 'Retained child evidence.', key='child-complete')
    after = SERVICE.pending(ctx(project))
    assert [one for one in after if one['assignment_id'] == gc['assignment_id']] == [
        one for one in before if one['assignment_id'] == gc['assignment_id']]
    assert SERVICE.assignment(ctx(project), assignment_id=child['assignment_id'])['result'] == 'Retained child evidence.'


def test_request_sources_preserve_exact_user_revisions_separate_from_interpretation(project):
    from metaform.modules.map import work as map_work
    store, folder = project
    exact = '  Keep “Fast” OFF.\nDo not reset my choice.\n'
    original = map_work(context('map', folder, project='proj', surface='web', nouns={
        'op': 'add', 'node': NODE, 'title': 'Preserve fast choice',
        'task': 'Persist the explicit false selection.', 'source': {'text': exact, 'reference': 'chat:request-1'}}))
    work_id = original['id']
    revised = 'Keep Fast off after restarting too.\n'
    map_work(context('map', folder, project='proj', surface='web', nouns={
        'op': 'edit', 'id': work_id, 'task': 'Persist Fast off across restart.',
        'source': {'text': revised, 'reference': 'chat:request-2'}}))
    sources = map_work(context('map', folder, project='proj', nouns={'op': 'sources', 'id': work_id}))
    assert [(one['sequence'], one['text'], one['interpretation']) for one in sources] == [
        (1, exact, 'Persist the explicit false selection.'),
        (2, revised, 'Persist Fast off across restart.')]
    assert all(one['provenance']['author'] == 'user' for one in sources)
    assert sources[0]['task_revision'] != sources[1]['task_revision']
    selected = map_work(context('map', folder, project='proj', nouns={
        'op': 'sources', 'id': work_id, 'source_id': sources[0]['source_id']}))
    assert selected == sources[:1]
    assert store.ticket(work_id).work.task == 'Persist Fast off across restart.'
    map_work(context('map', folder, project='proj', session='agent-session', nouns={
        'op': 'edit', 'id': work_id, 'task': 'Use the persisted explicit false value.',
        'source': {'text': 'Agent refinement', 'author': 'user'}}))
    after = store.work_sources(work_id)
    assert [one['text'] for one in after[:2]] == [exact, revised]
    assert after[-1]['provenance']['author'] == 'agent'
    assert after[-1]['interpretation'] == 'Use the persisted explicit false value.'


def test_ticket_edit_directions_distinguish_user_agent_and_change_order(project):
    store, _ = project
    assigned = root(project)
    for number, source in enumerate(('agent', 'change_order', 'user')):
        store.edit_work(assigned['work_id'], {'task': f'Execution revision {number}'},
                        provenance={'author': source, 'reference': str(number)})
        SERVICE.ticket_edited(ctx(project), assigned['work_id'], str(number), source=source,
                              source_reference=str(number))
    directions = SERVICE.assignment(ctx(project), assignment_id=assigned['assignment_id'])['pending_direction']
    assert [(one['kind'], one['source']) for one in directions] == [
        ('ticket_revision', 'agent'), ('ticket_revision', 'change_order'), ('user_direction', 'user')]
    assert 'an agent' in directions[0]['body']
    assert 'adaptive change order' in directions[1]['body']
    assert 'the user' in directions[2]['body']
    assert [one['text'] for one in store.work_sources(assigned['work_id'])][-3:] == [
        'Execution revision 0', 'Execution revision 1', 'Execution revision 2']


def test_review_retains_candidate_revision_and_each_finding_disposition(project):
    gc = root(project)
    store, _ = project
    SERVICE.returned(ctx(project), gc['work_id'], 'Candidate delivered.', candidate={'revision': 'r1'}, state='delivered')
    gc = SERVICE.assignment(ctx(project), assignment_id=gc['assignment_id'])
    review = SERVICE.assessment(ctx(project), gc, {}, 'revision-review')
    SERVICE.directed(ctx(project), 'gc-one', {'kind': 'user_direction', 'id': 'new-volume',
        'at': implementation.now(), 'text': 'Change the kitchen timer volume.', 'from': {'kind': 'user'}})
    findings = [
        {'finding_id': 'volume-default', 'summary': 'Restore the original volume default.',
         'disposition': 'superseded', 'superseded_by': 'new-volume',
         'supersession_reason': 'The new user direction explicitly changes the previous volume requirement.'},
        {'finding_id': 'selection-loss', 'summary': 'Selection resets after changing duration.',
         'evidence': 'Observed a selected value disappear.'},
        {'finding_id': 'unsupported', 'summary': 'The alarm never rings.',
         'disposition': 'superseded', 'superseded_by': 'invented-direction',
         'supersession_reason': 'Claimed change with no retained source.'}]
    returned = SERVICE.returned(ctx(project), review['work_id'], 'Three findings.', findings=findings)
    assert [one['disposition'] for one in returned['findings']] == ['superseded', 'correction', 'correction']
    assert [one['finding'] for one in returned['findings']] == findings
    assert returned['reviewed_snapshot']['candidate'] == {'revision': 'r1'}
    assert returned['reviewed_snapshot']['task_revision'] == fingerprint(gc['task'])
    assert not store.ticket(gc['work_id']).work.done
    directions = SERVICE.assignment(ctx(project), assignment_id=gc['assignment_id'])['pending_direction']
    assert [one['finding_id'] for one in directions if one['kind'] == 'review_finding'] == [
        'selection-loss', 'unsupported']


def test_generic_finding_title_does_not_fold_distinct_defects(project):
    store, _ = project
    gc = root(project)
    unrelated = store.add_work(Node('element', NODE), None, task='Regression', title='Regression')
    SERVICE.returned(ctx(project), gc['work_id'], 'Candidate delivered.', state='delivered')
    review = SERVICE.assessment(ctx(project), gc, {}, 'generic-title')
    returned = SERVICE.returned(ctx(project), review['work_id'], 'Two defects.', findings=[
        {'title': 'Regression', 'detail': 'The selection clears.', 'file': 'selection.py', 'evidence': 'Value becomes null.'},
        {'title': 'Regression', 'detail': 'The alarm stays silent.', 'file': 'alarm.py', 'evidence': 'No audio at zero.'}])
    assert returned['findings_filed'] == [gc['work_id']]
    assert unrelated.id not in returned['findings_filed']
    directions = SERVICE.assignment(ctx(project), assignment_id=gc['assignment_id'])['pending_direction']
    assert len([one for one in directions if one['kind'] == 'review_finding']) == 2
    assert 'selection.py' in store.ticket(gc['work_id']).work.note
    assert 'alarm.py' in store.ticket(gc['work_id']).work.note


def test_linked_operative_change_supersedes_only_its_individual_finding(project):
    store, folder = project
    (folder / 'reviewed-spec.md').write_text('Alarm starts loud.', encoding='utf-8')
    gc = root(project, specification={'uri': 'file:reviewed-spec.md'})
    SERVICE.returned(ctx(project), gc['work_id'], 'Alarm delivered.', state='delivered')
    review = SERVICE.assessment(ctx(project), gc, {}, 'new-spec')
    changed = change(context('orchestration', folder, project='proj', surface='web', nouns={
        'assignment': gc['assignment_id'], 'content': 'Alarm starts quietly.', 'reason': 'User chose quiet.',
        'user_instruction': 'Start the kitchen timer alarm quietly.'}))
    returned = SERVICE.returned(ctx(project), review['work_id'], 'Volume and selection findings.', findings=[
        {'finding_id': 'volume', 'summary': 'Restore loud initial alarm.', 'disposition': 'superseded',
         'superseded_by': changed['change_id'],
         'supersession_reason': 'The operative specification now explicitly requests a quiet initial alarm.'},
        {'finding_id': 'selection', 'summary': 'Changing volume must preserve the selected duration.'}])
    assert [one['disposition'] for one in returned['findings']] == ['superseded', 'correction']
    assert returned['reviewed_snapshot']['requirements'] == 'Alarm starts loud.'
    assert returned['reviewed_snapshot']['requirements_revision'] == fingerprint('Alarm starts loud.')
    assert (folder / 'reviewed-spec.md').read_text(encoding='utf-8') == 'Alarm starts quietly.'
    assert store.ticket(gc['work_id']).work.column == 'todo'
    assert returned['findings_filed'] == [gc['work_id']]


def test_direction_already_in_reviewed_source_cannot_claim_later_supersession(project):
    gc = root(project)
    SERVICE.directed(ctx(project), 'gc-one', {'kind': 'user_direction', 'id': 'existing-requirement',
        'at': implementation.now(), 'text': 'Preserve the selected timer duration.', 'from': {'kind': 'user'}})
    SERVICE.returned(ctx(project), gc['work_id'], 'Candidate delivered.', state='delivered')
    gc = SERVICE.assignment(ctx(project), assignment_id=gc['assignment_id'])
    review = SERVICE.assessment(ctx(project), gc, {}, 'existing-direction')
    returned = SERVICE.returned(ctx(project), review['work_id'], 'Selection clears.', findings=[{
        'summary': 'Selected duration clears.', 'disposition': 'superseded',
        'superseded_by': 'existing-requirement', 'supersession_reason': 'Claimed to be a later instruction.'}])
    assert returned['findings'][0]['disposition'] == 'correction'
    assert returned['reviewed_snapshot']['direction_references'] == ['existing-requirement']
