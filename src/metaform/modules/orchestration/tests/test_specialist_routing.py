"""Expertise selection and credit fallback with real stores and deterministic provider replies."""
import io
import json
from types import SimpleNamespace

import pytest

from metaform import jev
from metaform.data import Node, functional_context
from metaform.module import Stop, context
from metaform.modules.agents.roles import SERVICE as ROLES
from metaform.modules.orchestration import routing
from metaform.modules.orchestration.state import SERVICE, work_changed
from tests.storekit import small_map

pytestmark = pytest.mark.kind('simulation')


@pytest.fixture
def case(store, project_folder):
    small_map(store)
    ctx = context('orchestration', project_folder, project='proj')
    work = store.add_work(Node('element', 'code.timer.kitchen'), None, task='Fix the timer alarm.', title='Alarm')
    return ctx, store, work


def expert(ctx):
    return ROLES.publish(ctx, 'alarm_engineering', 'Reliable countdown alarms and audible notification.',
                         'Diagnose timing and notification behavior using reproducible observations.')


def test_specialist_inventory_excludes_framework_duties_and_keeps_reusable_urls(case):
    ctx, _, _ = case
    expert(ctx)
    inventory = ROLES.specialists(ctx)
    assert [one['name'] for one in inventory] == ['alarm_engineering']
    assert inventory[0]['uri'] == 'metaform://role/alarm_engineering'
    assert 'Diagnose timing' not in json.dumps(inventory)
    assert ROLES.resolve(ctx, 'implementer')['specialist'] is False


def test_jev_selects_expertise_from_local_functional_graph_without_duty_dump(case, monkeypatch):
    ctx, store, work = case
    expert(ctx)
    sent = []
    monkeypatch.setattr(jev, 'config', lambda *a: SimpleNamespace(endpoint=SimpleNamespace(name='typesafe')))

    def choose(folder, question, options, state, **kwargs):
        sent.append((options, state))
        return SimpleNamespace(sure=True, answer='metaform://role/alarm_engineering')
    monkeypatch.setattr(jev, 'pick_one', choose)
    routing.queue(ctx, [work.id])
    found = SERVICE.route_pending(ctx)
    assert found[0]['role'] == 'metaform://role/alarm_engineering'
    assert not store.ticket(work.id).work.taken
    assert 'metaform://role/implementer' not in sent[0][0]
    assert sent[0][1]['function']['requirements'][0]['purpose'] == 'Get attention when a countdown ends.'
    assert 'Diagnose timing' not in json.dumps(sent)
    assert SERVICE.route_pending(ctx) == []
    assert SERVICE.route(ctx, work.id)['role'] == found[0]['role']
    assert len(sent) == 1
    assigned = SERVICE.ensure(ctx, work.id)
    assert assigned['authored_role_uri'] == found[0]['role']


@pytest.mark.parametrize('balance', ['unknown', 'exhausted'])
def test_credit_unavailable_commissions_facilitator_without_paid_selection(case, monkeypatch, balance):
    ctx, store, work = case
    expert(ctx)
    monkeypatch.setattr(jev, 'config', lambda *a: SimpleNamespace(endpoint=SimpleNamespace(name='openrouter')))
    monkeypatch.setattr(jev, 'openrouter_credits', lambda: {'status': balance})
    monkeypatch.setattr(jev, 'pick_one', lambda *a, **kw: pytest.fail('No paid selection without credit'))
    found = SERVICE.route(ctx, work.id)
    assert found['state'] == 'creating' and found['role'] is None
    assert store.ticket(work.id).work.taken
    owner = SERVICE.ensure(ctx, work.id)
    assert owner['state'] == 'waiting' and owner['owner_session_id'] is None
    with pytest.raises(Stop, match='waiting for its specialist'):
        SERVICE.ensure(ctx, work.id, session_id='premature-worker')


def test_filed_event_only_queues_and_no_specialist_requests_reusable_role(case, monkeypatch):
    ctx, store, work = case
    monkeypatch.setattr(jev, 'pick_one', lambda *a, **kw: pytest.fail('Filing cannot call models'))
    work_changed({'project': 'proj', 'tables': ['work'], 'kinds': ['filed'], 'work_ids': [work.id]}, ctx)
    assert not store.ticket(work.id).work.taken
    assert SERVICE.assignment(ctx, work_id=work.id) is None
    assert SERVICE.route_pending(ctx)[0]['state'] == 'creating'
    assert SERVICE.assignment(ctx, work_id=work.id)['state'] == 'waiting'


def test_local_graph_lists_real_requirements_and_dependents(case):
    _, store, work = case
    graph = functional_context(store, work)
    assert graph['name'] == 'kitchen timer'
    assert graph['requirements'][0]['providers'] == ['code.alarm.audible']
    assert graph['dependents'][0]['receiver'] == 'stakeholder.cook.home'
    assert 'Know when each dish is done.' in graph['markdown']
    assert 'Get attention when a countdown ends.' in graph['markdown']
    assert graph['markdown'].startswith('```mermaid\n')


def test_stage_markers_are_never_sent_for_specialist_selection(case, monkeypatch):
    ctx, store, _ = case
    marker = store.add_work(Node('element', 'code.timer.kitchen'), 'under-construction', note='Checked.')
    monkeypatch.setattr(jev, 'config', lambda *a: pytest.fail('A stage marker is not a ticket to route'))
    routing.queue(ctx, [marker.id])
    assert SERVICE.route_pending(ctx) == []
    assert SERVICE.route(ctx, marker.id)['state'] == 'closed'


def test_routing_batches_leave_other_projects_and_triage_a_turn(case, monkeypatch):
    ctx, store, first = case
    second = store.add_work(Node('element', 'code.alarm.audible'), None, task='Test audible notifications.')
    routing.queue(ctx, [first.id, second.id])
    assert len(SERVICE.route_pending(ctx)) == 1
    assert SERVICE.routing_waiting(ctx)
    assert len(SERVICE.route_pending(ctx)) == 1
    assert not SERVICE.routing_waiting(ctx)
    from metaform.modules.dispatch import jev_choices
    monkeypatch.setattr(jev, 'config', lambda *a: pytest.fail('No harness decision before expertise is selected'))
    assert jev_choices(ctx, store, set()) == {}


def test_openrouter_credit_is_cached_debited_and_explicitly_refreshed(home, monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'fixture-private-key')
    calls = []

    def reply(request, **kwargs):
        calls.append(request.full_url)
        return io.BytesIO(b'{"data":{"total_credits":10,"total_usage":4}}')
    monkeypatch.setattr(jev.urllib.request, 'urlopen', reply)
    assert jev.openrouter_credits()['remaining'] == 6
    cfg = jev.Config(jev.ENDPOINTS['openrouter'], 'model', 'fixture-private-key')
    jev._debit_credit(cfg, 2)
    assert jev.openrouter_credits()['remaining'] == 4
    assert len(calls) == 1
    assert jev.openrouter_credits(refresh=True)['remaining'] == 6
    assert len(calls) == 2
    assert b'fixture-private-key' not in (home / jev.CACHE).read_bytes()


def test_confident_none_commissions_facilitator_and_publication_continues_original_ticket(case, monkeypatch):
    from metaform.modules.dispatch import capacity_kind
    from metaform.modules.orchestration import publish_role
    from metaform.modules.orchestration.state import own

    ctx, store, work = case
    expert(ctx)
    decisions = []
    monkeypatch.setattr(jev, 'config', lambda *a: SimpleNamespace(endpoint=SimpleNamespace(name='typesafe')))

    def choose(*args, **kwargs):
        decisions.append(True)
        return SimpleNamespace(sure=True, answer='none')
    monkeypatch.setattr(jev, 'pick_one', choose)
    assert SERVICE.route(ctx, work.id)['state'] == 'creating'
    owner = SERVICE.assignment(ctx, work_id=work.id)
    assert owner['state'] == 'waiting' and owner['owner_session_id'] is None
    assert SERVICE.routing_status(ctx, work.id) == {
        'state': 'creating', 'role': None, 'reason': 'Facilitator is selecting expertise.'}
    assert SERVICE.route(ctx, work.id, refresh=True)['state'] == 'creating'
    with own(ctx).tables(write=False) as tx:
        request, = tx.rows('role_requests', limit=0).results
    creator = SERVICE.assignment(ctx, assignment_id=request['creator_assignment_id'])
    assert creator['authored_role_uri'] == 'metaform://role/facilitator'
    assert capacity_kind(ctx, creator['work_id'], 'worker') == 'helper'
    assert creator['task'].count(work.task) == 1
    assert 'markdown' not in creator['task']
    with pytest.raises(Stop, match='waiting for its specialist'):
        SERVICE.bind(ctx, owner['assignment_id'], 'premature-worker')
    SERVICE.bind(ctx, creator['assignment_id'], 'facilitator')
    duty = '<system_prompt><role_and_identity>You are a timer diagnostics specialist.</role_and_identity></system_prompt>'
    writer = context('orchestration', ctx.folder, project='proj', session='facilitator', nouns={
        'request': request['request_id'], 'role': 'timer_diagnostics',
        'purpose': 'Diagnose timer behavior.', 'duty': duty})
    result = publish_role(writer)
    assert result['role']['uri'] == 'metaform://role/timer_diagnostics'
    assert result['assignment']['work_id'] == work.id
    assert result['assignment']['assignment_id'] == owner['assignment_id']
    assert result['assignment']['state'] == 'queued'
    assert result['continued'] == 1 and 'system_prompt' not in json.dumps(result)
    assert SERVICE.route(ctx, work.id)['role'] == result['role']['uri']
    bound = SERVICE.bind(ctx, owner['assignment_id'], 'specialist')
    assert duty in bound['role_snapshot']['text']
    assert bound['task'] == work.task and not store.ticket(work.id).work.done
    assert len(decisions) == 1
    replay = publish_role(writer)
    assert replay['role']['version_id'] == result['role']['version_id']
    with own(ctx).tables(write=False) as tx:
        launches = [one for one in tx.rows('transitions', {'assignment_id': owner['assignment_id']}, limit=0).results
                    if one['kind'] == 'launch']
        creator_result = tx.get('assignments', {'assignment_id': creator['assignment_id']})['result']
    assert len(launches) == 1 and 'system_prompt' not in json.dumps(creator_result)


def test_a_route_stuck_at_creating_with_no_creator_running_is_routed_again_and_jevs_pick_continues_the_ticket(
        case, monkeypatch):
    """2026-10-20: a ticket sat for hours at 'Facilitator is selecting expertise'. Jev was off when it was routed, so a
    creator was commissioned; Full Auto off never launched it; and a creating route was never looked at again once Jev
    was on. A creating route whose creator does not run is asked again after STUCK_AFTER, or when the ticket or the
    registry changed, never twice for the same state. When Jev picks registered expertise, the waiting request is
    published from the registry as the Facilitator's publication does it in place, the creator is stopped with its
    ticket cancelled, and the original ticket continues on its own assignment with its launch."""
    from metaform.modules.orchestration.state import own

    ctx, store, work = case
    expert(ctx)
    answers = ['none']
    asked = []
    monkeypatch.setattr(jev, 'config', lambda *a: SimpleNamespace(endpoint=SimpleNamespace(name='typesafe')))
    monkeypatch.setattr(jev, 'pick_one', lambda *a, **k: asked.append(True) or SimpleNamespace(sure=True,
                                                                                               answer=answers[-1]))
    assert SERVICE.route(ctx, work.id)['state'] == 'creating'
    owner = SERVICE.assignment(ctx, work_id=work.id)
    with own(ctx).tables(write=False) as tx:
        request, = tx.rows('role_requests', limit=0).results
    creator = SERVICE.assignment(ctx, assignment_id=request['creator_assignment_id'])
    assert creator['state'] != 'running', 'commissioned and never launched'
    assert SERVICE.route(ctx, work.id, refresh=True)['state'] == 'creating' and len(asked) == 1, \
        'the same state is never asked twice'
    with own(ctx).tables() as tx:  # STUCK_AFTER ago
        tx.update('routing', {'work_id': work.id}, {'updated': '2026-10-20T00:00:00Z'})
    assert SERVICE.route(ctx, work.id, refresh=True)['state'] == 'creating' and len(asked) == 2
    with own(ctx).tables(write=False) as tx:
        assert len(tx.rows('role_requests', limit=0).results) == 1, 'no second creator is commissioned'
        assert not _stale_row(tx.get('routing', {'work_id': work.id}))
    answers.append('metaform://role/alarm_engineering')
    with own(ctx).tables() as tx:
        tx.update('routing', {'work_id': work.id}, {'updated': '2026-10-20T00:00:00Z'})
    [routed] = SERVICE.route_pending(ctx)  # the agent starter's pass finds the stale creating route
    assert routed['state'] == 'selected' and routed['role'] == 'metaform://role/alarm_engineering', routed
    assert SERVICE.routing_status(ctx, work.id)['state'] != 'creating'
    assigned = SERVICE.assignment(ctx, work_id=work.id)
    assert assigned['assignment_id'] == owner['assignment_id'] and assigned['state'] == 'queued'
    assert assigned['authored_role_uri'] == 'metaform://role/alarm_engineering'
    with own(ctx).tables(write=False) as tx:
        request, = tx.rows('role_requests', limit=0).results
        launches = [one for one in tx.rows('transitions', {'assignment_id': owner['assignment_id']}, limit=0).results
                    if one['kind'] == 'launch' and one['state'] == 'pending']
    assert request['state'] == 'published' and request['context']['publication']['by'] == 'jev'
    assert launches, 'the original ticket continues'
    gone = SERVICE.assignment(ctx, assignment_id=creator['assignment_id'])
    assert gone['state'] == 'stopped' and store.ticket(creator['work_id']).work.outcome == 'cancelled'


def _stale_row(row):
    return routing._stale(row)


@pytest.mark.parametrize('existing', [True, False])
def test_no_jev_key_preserves_writer_assignment_or_automatically_hands_to_facilitator(case, monkeypatch, existing):
    from metaform import home
    from metaform.modules.orchestration.state import own
    ctx, _, work = case
    if existing:
        expert(ctx)
        ctx.nouns.update(work=work.id, role='alarm_engineering')
        assigned = SERVICE.claim(ctx)
    home.save(str(ctx.folder), 'chassis', 'jev', ['true'])
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    monkeypatch.setattr(jev, 'pick_one', lambda *a, **kw: pytest.fail('Missing key must not call JEV'))
    routed = SERVICE.route(ctx, work.id)
    if existing:
        assert routed['role'] == 'metaform://role/alarm_engineering'
        assert SERVICE.assignment(ctx, work_id=work.id) == assigned
        with own(ctx).tables(write=False) as tx:
            assert not tx.rows('role_requests', limit=0).results
    else:
        assert routed['state'] == 'creating'
        assigned = SERVICE.assignment(ctx, work_id=work.id)
        assert assigned['state'] == 'waiting'
        assert SERVICE.route(ctx, work.id, refresh=True)['state'] == 'creating'
        with own(ctx).tables(write=False) as tx:
            request, = tx.rows('role_requests', limit=0).results
        creator = SERVICE.assignment(ctx, assignment_id=request['creator_assignment_id'])
        assert creator['authored_role_uri'] == 'metaform://role/facilitator'


@pytest.mark.parametrize('decision', [None, SimpleNamespace(sure=False, answer='none')])
def test_failed_or_uncertain_selection_automatically_commissions_facilitator(case, monkeypatch, decision):
    ctx, _, work = case
    expert(ctx)
    monkeypatch.setattr(jev, 'config', lambda *a: SimpleNamespace(endpoint=SimpleNamespace(name='typesafe')))
    monkeypatch.setattr(jev, 'pick_one', lambda *a, **kw: decision)
    assert SERVICE.route(ctx, work.id)['state'] == 'creating'
    assert SERVICE.assignment(ctx, work_id=work.id)['state'] == 'waiting'


def test_persisted_triage_is_drained_once_without_repeating_cached_selection(case, monkeypatch):
    from metaform import home
    from metaform.modules.orchestration.state import fingerprint, own
    ctx, store, first = case
    expert(ctx)
    second = store.add_work(Node('element', 'code.alarm.audible'), None, task='Test audible notifications.')
    for work in (first, second):
        graph = functional_context(store, work)
        numbered = store.numbers_of('work', [work.id]).get(work.id)
        previous_input = {'title': numbered[1] if numbered else None, 'task': work.task, 'note': work.note,
                          'function': {key: value for key, value in graph.items() if key != 'markdown'}}
        with own(ctx).tables() as tx:
            tx.insert('routing', {'work_id': work.id, 'state': 'triage', 'updated': home.now(),
                'fingerprint': fingerprint(json.dumps([previous_input, ROLES.specialists(ctx)], sort_keys=True)),
                'reason': 'JEV is unavailable; triage must select expertise.'})
    monkeypatch.setattr(jev, 'config', lambda *a: pytest.fail('Recover the cached decision without another lookup'))
    assert SERVICE.routing_waiting(ctx)
    assert len(SERVICE.route_pending(ctx)) == 1
    assert SERVICE.routing_waiting(ctx)
    assert len(SERVICE.route_pending(ctx)) == 1
    assert not SERVICE.routing_waiting(ctx)
    assert SERVICE.route_pending(ctx) == []
    for work in (first, second):
        assert SERVICE.route(ctx, work.id, refresh=True)['state'] == 'creating'
        assert SERVICE.assignment(ctx, work_id=work.id)['state'] == 'waiting'
    with own(ctx).tables(write=False) as tx:
        requests = tx.rows('role_requests', limit=0).results
    assert len(requests) == 2


@pytest.mark.parametrize('owner', ['specialist', 'framework', 'stopped', 'legacy'])
def test_stale_triage_never_replaces_existing_ownership(case, monkeypatch, owner):
    from metaform import home
    from metaform.modules.orchestration.state import own
    ctx, store, work = case
    if owner == 'legacy':
        store.take_work(work.id, by='existing-agent')
        assigned = None
    else:
        expert(ctx)
        ctx.nouns.update(work=work.id, role='gc' if owner == 'framework' else 'alarm_engineering')
        assigned = SERVICE.claim(ctx)
        if owner == 'stopped':
            SERVICE.stopped(ctx, work_id=work.id, by='user')
            assigned = SERVICE.assignment(ctx, work_id=work.id)
    with own(ctx).tables() as tx:
        tx.insert('routing', {'work_id': work.id, 'state': 'triage', 'updated': home.now(),
                             'reason': 'JEV is unavailable; triage must select expertise.'})
    monkeypatch.setattr(jev, 'config', lambda *a: pytest.fail('An owned ticket must not be reclassified'))
    SERVICE.route_pending(ctx)
    assert SERVICE.assignment(ctx, work_id=work.id) == assigned
    assert not SERVICE.routing_waiting(ctx)
    with own(ctx).tables(write=False) as tx:
        assert not tx.rows('role_requests', limit=0).results


def test_empty_inventory_commissions_without_paying_for_an_empty_choice(case, monkeypatch):
    ctx, _, work = case
    monkeypatch.setattr(jev, 'config', lambda *a: SimpleNamespace(endpoint=SimpleNamespace(name='typesafe')))
    monkeypatch.setattr(jev, 'pick_one', lambda *a, **kw: pytest.fail('There is nothing to choose'))
    assert SERVICE.route(ctx, work.id)['state'] == 'creating'


def test_facilitators_choose_names_independently_and_reuse_already_published_expertise(case):
    from metaform.modules.orchestration import publish_role
    ctx, store, work = case
    second = store.add_work(Node('element', 'code.alarm.audible'), None, task='Measure audible alarm behavior.')
    requests = []
    for record in (work, second):
        ctx.nouns = {'work': record.id, 'create': True}
        requests.append(SERVICE.claim(ctx)['role_request'])
    assert requests[0]['creator_assignment_id'] != requests[1]['creator_assignment_id']
    registered = expert(ctx)  # Expertise becomes available after the commissions.
    for number, request in enumerate(requests):
        session = f'facilitator-{number}'
        SERVICE.bind(ctx, request['creator_assignment_id'], session)
        writer = context('orchestration', ctx.folder, project='proj', session=session, nouns={
            'request': request['request_id'], 'role': registered['uri']})
        result = publish_role(writer)
        assert result['role']['version_id'] == registered['version_id']
        assert result['assignment']['work_id'] in (work.id, second.id)
    assert ROLES.resolve(ctx, registered['name'])['version_id'] == registered['version_id']


def test_automatic_facilitator_reuses_without_editing_and_respects_backlog_placement(case, monkeypatch):
    from metaform.modules.orchestration import publish_role
    from metaform.modules.orchestration.state import own
    ctx, store, work = case
    registered = expert(ctx)
    monkeypatch.setattr(jev, 'config', lambda *a: None)
    assigned = SERVICE.ensure(ctx, work.id)
    with own(ctx).tables(write=False) as tx:
        request, = tx.rows('role_requests', limit=0).results
    SERVICE.bind(ctx, request['creator_assignment_id'], 'facilitator')
    writer = context('orchestration', ctx.folder, project='proj', session='facilitator', nouns={
        'request': request['request_id'], 'role': registered['uri'], 'duty': 'Do not overwrite existing expertise.',
        'column': 'backlog', 'match_reason': 'The registered role covers countdown alarm behavior.'})
    result = publish_role(writer)
    assert result['source'] == 'existing'
    assert result['board_placement'] == {'status': 'done', 'column': 'backlog', 'work_id': work.id}
    assert store.ticket(work.id).work.held and not store.ticket(work.id).work.taken
    assert ROLES.resolve(ctx, registered['name'])['version_id'] == registered['version_id']
    assert 'Do not overwrite' not in ROLES.resolve(ctx, registered['name'])['text']
    with own(ctx).tables(write=False) as tx:
        events = tx.rows('transitions', {'assignment_id': assigned['assignment_id']}, limit=0).results
    assert not any(one['kind'] == 'launch' for one in events)
    assert publish_role(writer)['board_placement']['column'] == 'backlog'


def test_specialist_registry_resource_has_names_and_urls_without_role_bodies(case):
    import asyncio

    from metaform.modules.mcp import server
    ctx, _, _ = case
    registered = expert(ctx)
    text = asyncio.run(server.read_resource_text(ctx.folder, 'metaform://specialists', session='facilitator'))[0]
    assert registered['uri'] in text and 'Reliable countdown alarms' in text
    assert 'Diagnose timing' not in text and 'metaform://role/implementer' not in text
    again = asyncio.run(server.read_resource_text(ctx.folder, 'metaform://specialists', session='facilitator'))[0]
    assert registered['uri'] not in again
    newer = ROLES.publish(ctx, 'timer_diagnostics', 'Diagnose countdown timing.', 'Measure timer behavior.')
    changed = asyncio.run(server.read_resource_text(ctx.folder, 'metaform://specialists', session='facilitator'))[0]
    assert newer['uri'] in changed
    server.compaction_state(ctx.folder, 'facilitator')
    restored = asyncio.run(server.read_resource_text(ctx.folder, 'metaform://specialists', session='facilitator'))[0]
    assert newer['uri'] in restored


@pytest.mark.parametrize('previous_state', ['pending', 'triage'])
def test_automatic_creation_waits_for_a_held_ticket_to_be_released(case, monkeypatch, previous_state):
    from metaform.modules.orchestration.state import own
    ctx, store, work = case
    routing.queue(ctx, [work.id])
    with own(ctx).tables() as tx:
        tx.update('routing', {'work_id': work.id}, {'state': previous_state})
    store.move_work(work.id, 'backlog', kept=True)
    with monkeypatch.context() as waiting:
        waiting.setattr(jev, 'config', lambda *a: pytest.fail('A held ticket must not spend on routing'))
        assert SERVICE.route_pending(ctx)[0]['state'] == 'held'
        assert not SERVICE.routing_waiting(ctx)
        assert SERVICE.assignment(ctx, work_id=work.id) is None
    store.move_work(work.id, 'todo', kept=True)
    routing.queue(ctx, [work.id])
    monkeypatch.setattr(jev, 'config', lambda *a: SimpleNamespace(endpoint=SimpleNamespace(name='typesafe')))
    assert SERVICE.route_pending(ctx)[0]['state'] == 'creating'


def test_facilitator_receives_the_complete_xml_workflow_through_role_resolution(case):
    from xml.etree import ElementTree
    ctx, _, _ = case
    role = ROLES.resolve(ctx, 'facilitator')
    assert not role['problems']
    duty = role['components'][-1]['text']
    workflow = ElementTree.fromstring(duty)
    assert workflow.tag == 'metaprompt'
    assert len(workflow.findall('./workflow/step')) == 6
    assert {section.attrib['tag'] for section in workflow.findall('./required_sections/section')} == {
        'role_and_identity', 'context_and_objective', 'core_rules_and_constraints',
        'key_skills_and_behaviors', 'output_formatting'}
    assert 'metaform://specialists' in duty and 'orchestration_publish_role' in duty
    assert '<system_prompt>' in workflow.find('system_prompt_template').text
    assert '<result>' in workflow.find('./output_format/template').text
