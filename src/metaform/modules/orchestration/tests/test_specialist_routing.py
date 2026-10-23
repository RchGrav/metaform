"""Expertise selection and credit fallback with real stores and deterministic provider replies."""
import io
import json
from types import SimpleNamespace

import pytest

from metaform import jev
from metaform.data import Node, functional_context
from metaform.module import Stop, agent_role_name, context
from metaform.modules.agents.roles import SERVICE as ROLES
from metaform.modules.orchestration import routing
from metaform.modules.orchestration.runtime import choose as choose_runtime
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
    assert inventory[0]['uri'] == 'metaform://specialist/alarm_engineering'
    assert 'Diagnose timing' not in json.dumps(inventory)
    assert ROLES.resolve(ctx, 'implementer')['specialist'] is False


def test_jev_selects_expertise_from_local_functional_graph_without_duty_dump(case, monkeypatch):
    ctx, store, work = case
    expert(ctx)
    sent = []
    monkeypatch.setattr(jev, 'config', lambda *a: SimpleNamespace(endpoint=SimpleNamespace(name='typesafe')))

    def choose(folder, question, options, state, **kwargs):
        sent.append((options, state))
        return SimpleNamespace(sure=True, answer='metaform://specialist/alarm_engineering')
    monkeypatch.setattr(jev, 'pick_one', choose)
    routing.queue(ctx, [work.id])
    found = SERVICE.route_pending(ctx)
    assert found[0]['role'] == 'metaform://specialist/alarm_engineering'
    assert not store.ticket(work.id).work.taken
    assert 'metaform://role/implementer' not in sent[0][0]
    assert sent[0][1]['function']['requirements'][0]['purpose'] == 'Get attention when a countdown ends.'
    assert 'Diagnose timing' not in json.dumps(sent)
    assert SERVICE.route_pending(ctx) == []
    assert SERVICE.route(ctx, work.id)['role'] == found[0]['role']
    assert len(sent) == 1
    assigned = SERVICE.ensure(ctx, work.id)
    assert assigned['authored_role_uri'] == found[0]['role']
    assert not store.ticket(work.id).work.taken


@pytest.mark.parametrize('balance', ['unknown', 'exhausted'])
def test_credit_unavailable_commissions_facilitator_without_paid_selection(case, monkeypatch, balance):
    ctx, store, work = case
    expert(ctx)
    monkeypatch.setattr(jev, 'config', lambda *a: SimpleNamespace(endpoint=SimpleNamespace(name='openrouter')))
    monkeypatch.setattr(jev, 'openrouter_credits', lambda: {'status': balance})
    monkeypatch.setattr(jev, 'pick_one', lambda *a, **kw: pytest.fail('No paid selection without credit'))
    found = SERVICE.route(ctx, work.id)
    assert found['state'] == 'creating' and found['role'] is None
    assert not store.ticket(work.id).work.taken
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
    assert not store.ticket(work.id).work.taken


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
    ticket, title, _ = store.numbers_of('work', [work.id])[work.id]  # one line naming the ticket, none of its content
    role = agent_role_name(owner['authored_role_uri'])
    assert creator['task'] == f'{role} {ticket}: {title}: Select or create a specialist for {ticket}, ' \
        f'request {request["request_id"]}.', creator['task']
    assert '\n' not in creator['task'] and work.task not in creator['task']
    with pytest.raises(Stop, match='waiting for its specialist'):
        SERVICE.bind(ctx, owner['assignment_id'], 'premature-worker')
    SERVICE.bind(ctx, creator['assignment_id'], 'facilitator')
    duty = '<system_prompt><role_and_identity>You are a timer diagnostics specialist.</role_and_identity></system_prompt>'
    writer = context('orchestration', ctx.folder, project='proj', session='facilitator', nouns={
        'request': request['request_id'], 'role': 'timer_diagnostics',
        'purpose': 'Diagnose timer behavior.', 'duty': duty})
    result = publish_role(writer)
    assert result['role']['uri'] == 'metaform://specialist/timer_diagnostics'
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
    answers.append('metaform://specialist/alarm_engineering')
    with own(ctx).tables() as tx:
        tx.update('routing', {'work_id': work.id}, {'updated': '2026-10-20T00:00:00Z'})
    [routed] = SERVICE.route_pending(ctx)  # the agent starter's pass finds the stale creating route
    assert routed['state'] == 'selected' and routed['role'] == 'metaform://specialist/alarm_engineering', routed
    assert SERVICE.routing_status(ctx, work.id)['state'] != 'creating'
    assigned = SERVICE.assignment(ctx, work_id=work.id)
    assert assigned['assignment_id'] == owner['assignment_id'] and assigned['state'] == 'queued'
    assert assigned['authored_role_uri'] == 'metaform://specialist/alarm_engineering'
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
        assert routed['role'] == 'metaform://specialist/alarm_engineering'
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
    store.move_work(work.id, 'backlog', kept=True, hold_reason='Wait for the requested release.')
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
    # the owner's design of 2026-10-20: assign a listed specialist, else create one and return to assign it
    assert [one.attrib['name'] for one in workflow.findall('./procedure')] == ['assign_specialist', 'create_specialist']
    assert [one.attrib['name'] for one in workflow.findall('./procedure/part')] == [
        'name', 'short_description', 'key_skills_and_behaviors']
    assert 'metaform://specialists' in duty and 'orchestration_publish_role' in duty
    assert '<system_prompt>' in workflow.find('system_prompt_template').text
    assert '<result>' in workflow.find('./output_format/template').text


@pytest.fixture
def runtime_catalog():
    # Deliberately put the strongest model first in one catalog and last in the other.
    # Capability comes from descriptions; identifiers carry no ranking information.
    return {
        'claude': {'models': {'option-z': 'Highest capability model for deep architecture and planning.',
                              'option-a': 'Fast lightweight model for straightforward work.'},
                   'efforts': ['low', 'medium', 'high', 'xhigh', 'max']},
        'codex': {'models': {'option-z': 'Fast lightweight model for straightforward work.',
                             'option-a': 'Highest capability model for deep architecture and planning.'},
                  'efforts': ['low', 'medium', 'high', 'xhigh', 'ultra']},
    }


def runtime_reply(monkeypatch, task_type, agent, *, effort=None, strongest=False):
    """Exercise real typed decisions with deterministic, order-independent provider replies."""
    seen = []
    cfg = jev.Config(jev.ENDPOINTS['typesafe'], 'fixture-jev', 'fixture-private-key')
    monkeypatch.setattr(jev, 'config', lambda *args: cfg)

    def answer(config, state, questions):
        seen.append(state)
        replies = {}
        for name, question in questions.items():
            options = question.criteria
            if 'planning' in options:
                chosen = task_type
            else:
                eligible = [key for key in options if json.loads(key)[0] == agent
                            and (effort is None or json.loads(key)[2] == effort)]
                if strongest:
                    eligible = [key for key in eligible if 'Highest capability' in options[key]]
                chosen = min(eligible)
            replies[name] = jev.Answer('choice', chosen,
                                       {key: float(key == chosen) for key in options}, 0.93, 'fixture-jev')
        return replies

    monkeypatch.setattr(jev, '_request', answer)
    return seen


@pytest.mark.parametrize(('task_type', 'agent', 'task'), [
    ('frontend', 'claude', 'Polish the settings panel layout and interaction states.'),
    ('coding', 'codex', 'Reject expired tokens in auth.validate, preserving valid tokens. Verify expiry boundaries.'),
])
def test_ticket_runtime_uses_model_selected_advertised_choice(case, monkeypatch, runtime_catalog,
                                                           task_type, agent, task):
    from metaform import settings

    ctx, _, work = case
    # The simulated catalog does not enable dispatch itself. Supply its declared person setting
    # when this worker has loaded only the orchestration module, independent of test ordering.
    monkeypatch.setattr(settings, 'SCHEMA', dict(settings.SCHEMA))
    strength_key = f'dispatch_{agent}_strengths'
    if strength_key not in settings.SCHEMA:
        settings.text(strength_key, '', owner='dispatch', scope='folder')
    supplied_strengths = 'The person supplied research matching this runtime to the requested contribution.'
    settings.put(strength_key, supplied_strengths, ctx.folder)
    sent = runtime_reply(monkeypatch, task_type, agent, effort='medium')
    ticket = {'id': work.id, 'title': 'Assigned runtime', 'kind': 'enhancement',
              'address': work.address, 'task': task}
    found = choose_runtime(ctx, ticket, runtime_catalog)
    assert found['agent'] == agent and found['effort'] == 'medium'
    assert found['decider'] == 'jev' and found['confidence'] == pytest.approx(0.93)
    assert {key: value for key, value in sent[0].items() if key != 'strengths'} == {
        'title': ticket['title'], 'kind': 'enhancement', 'node': work.address, 'task': task}
    # the person's own account of each agent, dispatch_<agent>_strengths, goes with the state (2026-10-21)
    assert set(sent[0]['strengths']) <= set(runtime_catalog)
    assert sent[0]['strengths'][agent] == supplied_strengths
    assert found['model'] in runtime_catalog[agent]['models']
    assert jev.items_at(ctx.folder, work.address, None, 10, project=ctx.project)


@pytest.mark.parametrize(('agent', 'model', 'effort'), [
    ('claude', 'option-z', 'max'), ('codex', 'option-a', 'ultra'),
])
def test_planning_runtime_uses_strongest_advertised_model_and_highest_effort(case, monkeypatch, runtime_catalog,
                                                                         agent, model, effort):
    ctx, _, work = case
    runtime_reply(monkeypatch, 'planning', agent, effort=effort, strongest=True)
    ticket = {'id': work.id, 'title': 'Plan acceptance work', 'kind': 'enhancement',
              'address': work.address, 'task': 'Build the concrete specification, goal, tickets and their order.'}
    found = choose_runtime(ctx, ticket, runtime_catalog)
    assert found['agent'] == agent and found['model'] == model and found['effort'] == effort


@pytest.mark.parametrize(('task_type', 'expected'), [('lookup', 'low'), ('routing', 'low')])
def test_helpers_and_routing_use_lowest_appropriate_offered_effort(case, monkeypatch, runtime_catalog,
                                                                task_type, expected):
    ctx, _, work = case
    runtime_reply(monkeypatch, task_type, 'codex', effort=expected)
    found = choose_runtime(ctx, {'id': work.id, 'title': 'Collect API facts', 'task': 'Look up request limits.'},
                           runtime_catalog)
    assert found['effort'] == expected
    if task_type == 'routing':
        runtime_catalog['codex']['efforts'].append('off')
        runtime_reply(monkeypatch, 'routing', 'codex', effort='off')
        found = choose_runtime(ctx, {'id': work.id, 'title': 'Check status', 'task': 'Report current status.'},
                               runtime_catalog)
        assert found['effort'] == 'off'


def test_cross_workstream_planning_is_a_separate_contribution(case, monkeypatch, runtime_catalog):
    ctx, _, work = case
    runtime_reply(monkeypatch, 'needs_plan', 'codex', effort='ultra', strongest=True)
    found = choose_runtime(ctx, {'id': work.id, 'title': 'Coordinate authentication rollout',
                                'task': 'Plan dependent changes across identity, browser sessions and clients.'},
                           runtime_catalog)
    assert found['task_type'] == 'needs_plan'


@pytest.mark.parametrize('status', ['exhausted', 'unknown'])
def test_runtime_credit_unavailable_immediately_requests_facilitator(case, monkeypatch, runtime_catalog, status):
    ctx, _, work = case
    monkeypatch.setattr(jev, 'config', lambda *args: jev.Config(jev.ENDPOINTS['openrouter'], 'fixture', 'key'))
    monkeypatch.setattr(jev, 'openrouter_credits', lambda: {'status': status})
    monkeypatch.setattr(jev, 'pick_one', lambda *args, **kwargs: pytest.fail('No paid runtime choice without credit'))
    assert choose_runtime(ctx, work, runtime_catalog) is None
    supplied = {'agent': 'codex', 'model': 'option-z', 'effort': 'medium', 'confidence': 0.88,
                'task_type': 'coding', 'reason': 'Precise implementation needs standard reasoning.'}
    found = choose_runtime(ctx, work, runtime_catalog, fallback=supplied)
    assert found == {**supplied, 'decider': 'facilitator'}


@pytest.mark.parametrize('reply', [None, SimpleNamespace(sure=False, answer='coding', confidence=0.2)])
def test_runtime_unanswered_or_uncertain_jev_immediately_requests_facilitator(case, monkeypatch,
                                                                         runtime_catalog, reply):
    ctx, _, work = case
    monkeypatch.setattr(jev, 'config', lambda *args: jev.Config(jev.ENDPOINTS['typesafe'], 'fixture', 'key'))
    monkeypatch.setattr(jev, 'pick_one', lambda *args, **kwargs: reply)
    assert choose_runtime(ctx, work, runtime_catalog) is None


def test_runtime_jev_off_immediately_requests_facilitator(case, monkeypatch, runtime_catalog):
    ctx, _, work = case
    monkeypatch.setattr(jev, 'config', lambda *args: None)
    monkeypatch.setattr(jev, 'pick_one', lambda *args, **kwargs: pytest.fail('Disabled Jev cannot receive requests'))
    assert choose_runtime(ctx, work, runtime_catalog) is None


@pytest.mark.parametrize('changes', [
    {'agent': 'unknown'}, {'model': 'unoffered-model'}, {'effort': 'unoffered'},
    {'confidence': float('nan')}, {'confidence': 1.1}, {'confidence': True}, {'reason': ''}, {'task_type': []},
])
def test_facilitator_runtime_must_satisfy_policy_and_offered_catalog(case, monkeypatch, runtime_catalog, changes):
    ctx, _, work = case
    monkeypatch.setattr(jev, 'config', lambda *args: pytest.fail('A supplied fallback never repeats Jev'))
    supplied = {'agent': 'codex', 'model': 'option-z', 'effort': 'medium', 'confidence': 0.88,
                'task_type': 'coding', 'reason': 'Precise implementation needs standard reasoning.'}
    assert choose_runtime(ctx, work, runtime_catalog, fallback={**supplied, **changes}) is None


@pytest.fixture
def runtime_transport(case, monkeypatch, runtime_catalog):
    settings = {}

    class RuntimeTransport:
        def runtime_catalog(self, ctx, work_id):
            return runtime_catalog

        def runtime_settings(self, ctx, work_id):
            return settings.get(work_id, {})

        def keep_runtime(self, ctx, work_id, choice):
            saved = {**{key: choice[key] for key in ('agent', 'model', 'effort')},
                     'decision': {key: choice.get(key) for key in
                                  ('decider', 'confidence', 'task_type', 'reason', 'task_fingerprint',
                                   'source_work_id', 'source_decider')}}
            settings[work_id] = saved
            return saved

    # The module loader reloads modules between test homes; patch the provider bound to this service instance.
    namespace = SERVICE.runtime.__func__.__globals__
    original = namespace['provided']
    monkeypatch.setitem(namespace, 'provided', lambda folder, kind: [('fixture', RuntimeTransport())]
                        if kind == 'orchestration.transport' else original(folder, kind))
    return settings


@pytest.mark.parametrize(('invalid', 'field'), [
    ({'task_type': 'bogus'}, 'task_type'),
    ({'task_type': []}, 'task_type'),
    ({'confidence': -0.1}, 'confidence'),
    ({'confidence': 1.1}, 'confidence'),
    ({'confidence': float('nan')}, 'confidence'),
    ({'confidence': float('inf')}, 'confidence'),
    ({'confidence': True}, 'confidence'),
    ({'confidence': '0.88'}, 'confidence'),
    ({'agent': 'unknown'}, 'agent/model/effort'),
    ({'model': 'unoffered-model'}, 'model'),
    ({'effort': 'unoffered'}, 'agent/model/effort'),
    ({'reason': ''}, 'reason'),
    ({'reason': '  '}, 'reason'),
    ({'reason': None}, 'reason'),
])
def test_assignment_credit_failure_commissions_full_model_and_records_its_choice(case, monkeypatch,
                                                                                runtime_transport, invalid, field):
    from dataclasses import replace

    from metaform.modules.orchestration.state import own, role_options

    ctx, _, work = case
    expert(ctx)
    monkeypatch.setattr(jev, 'config', lambda *args: jev.Config(jev.ENDPOINTS['openrouter'], 'fixture', 'key'))
    monkeypatch.setattr(jev, 'openrouter_credits', lambda: {'status': 'exhausted'})
    monkeypatch.setattr(jev, 'pick_one', lambda *args, **kwargs: pytest.fail('Credit failure cannot wait on Jev'))
    assigned = SERVICE.claim(replace(ctx, nouns={'work': work.id, 'role': 'alarm_engineering'}))
    assert assigned['state'] == 'waiting'
    with own(ctx).tables(write=False) as tx:
        requests = tx.rows('role_requests', {'caller_assignment_id': assigned['assignment_id']}, limit=0).results
    assert len(requests) == 1 and role_options(requests[0])['runtime_only']
    creator = SERVICE.assignment(ctx, assignment_id=requests[0]['creator_assignment_id'])
    assert creator['authored_role_uri'] == 'metaform://role/facilitator'
    choice = {'agent': 'codex', 'model': 'option-z', 'effort': 'medium', 'confidence': 0.88,
              'task_type': 'coding', 'reason': 'The ticket specifies concrete alarm behavior.'}
    creator_ctx = replace(ctx, nouns={'assignment': creator['assignment_id']})
    from metaform.modules.orchestration.runtime import TASKS

    needed = SERVICE.runtime(creator_ctx, work.id)
    assert needed['state'] == 'needs_choice'
    assert needed['task_types'] == TASKS
    rejected = SERVICE.runtime(creator_ctx, work.id, {**choice, **invalid})
    assert rejected['state'] == 'needs_choice'
    assert field in rejected['reason']
    assert rejected['task_types'] == TASKS
    assert rejected['catalog'] == needed['catalog']
    assert work.id not in runtime_transport
    selected = SERVICE.runtime(creator_ctx, work.id, choice)
    assert selected['state'] == 'selected'
    assert runtime_transport[work.id]['decision']['decider'] == 'facilitator'
    published = SERVICE.publish_role(replace(creator_ctx, nouns={**creator_ctx.nouns,
        'request': requests[0]['request_id'], 'role': 'alarm_engineering'}))
    assert published['assignment']['assignment_id'] == assigned['assignment_id']
    assert SERVICE.assignment(ctx, work_id=work.id)['state'] == 'queued'
    assert SERVICE.prepare_runtime(ctx, SERVICE.assignment(ctx, work_id=work.id))


@pytest.mark.parametrize('plan_state', ['returned', 'failed'])
def test_separate_plan_returns_once_without_rewriting_original_ticket(case, monkeypatch, runtime_transport,
                                                                    plan_state):
    from dataclasses import replace

    from metaform.modules.orchestration.state import own

    ctx, store, work = case
    expert(ctx)
    runtime_reply(monkeypatch, 'needs_plan', 'codex', effort='ultra', strongest=True)
    assigned = SERVICE.claim(replace(ctx, nouns={'work': work.id, 'role': 'alarm_engineering'}))
    assert assigned['state'] == 'waiting'
    children = [one for one in SERVICE.members(ctx, assigned['team_id'])
                if one['parent_assignment_id'] == assigned['assignment_id']]
    assert len(children) == 1 and children[0]['authored_role_uri'] == 'metaform://role/planner'
    assert runtime_transport[children[0]['work_id']]['decision']['task_type'] == 'planning'
    assert runtime_transport[children[0]['work_id']]['model'] == 'option-a'
    assert not store.ticket(work.id).work.done
    assert not SERVICE.prepare_runtime(ctx, assigned)
    assert len(SERVICE.members(ctx, assigned['team_id'])) == 2
    original = store.ticket(work.id).work.task
    plan = 'Reject alarms after expiry. Verify exact expiry boundary.'
    SERVICE.returned(ctx, children[0]['work_id'], plan, evidence=['Expiry path traced.'], state=plan_state)
    monkeypatch.setattr(jev, 'config', lambda *args: pytest.fail('A returned plan needs no repeated classification'))
    resumed = SERVICE.assignment(ctx, work_id=work.id)
    assert SERVICE.prepare_runtime(ctx, resumed)
    assert SERVICE.prepare_runtime(ctx, resumed)
    assert store.ticket(work.id).work.task == original
    assert resumed['plan']['result'] == plan
    assert resumed['plan']['evidence'] == ['Expiry path traced.']
    assert len(SERVICE.members(ctx, assigned['team_id'])) == 2
    with own(ctx).tables(write=False) as tx:
        assert not tx.rows('role_requests', limit=0).results


def test_person_runtime_survives_assignment_without_another_jev_request(case, monkeypatch, runtime_transport):
    from dataclasses import replace

    ctx, _, work = case
    expert(ctx)
    runtime_transport[work.id] = {'agent': 'claude', 'model': 'option-z', 'effort': 'max',
                                'decision': {'decider': 'person', 'confidence': 1.0}}
    monkeypatch.setattr(jev, 'config', lambda *args: pytest.fail('Person runtime is already chosen'))
    assigned = SERVICE.claim(replace(ctx, nouns={'work': work.id, 'role': 'alarm_engineering'}))
    assert assigned['state'] == 'queued'
    assert runtime_transport[work.id]['agent'] == 'claude'


def test_person_runtime_before_catalog_priming_stays_selected(case, monkeypatch, runtime_transport,
                                                           runtime_catalog):
    from dataclasses import replace

    ctx, _, work = case
    expert(ctx)
    runtime_catalog['claude'] = {'models': {}, 'efforts': []}
    runtime_transport[work.id] = {'agent': 'claude', 'model': 'person-model', 'effort': 'person-level',
                                'decision': {'decider': 'person', 'confidence': 1.0}}
    monkeypatch.setattr(jev, 'config', lambda *args: pytest.fail('Preserve an explicit unchecked choice'))
    assigned = SERVICE.claim(replace(ctx, nouns={'work': work.id, 'role': 'alarm_engineering'}))
    assert assigned['state'] == 'queued'
    assert runtime_transport[work.id]['model'] == 'person-model'
    assert runtime_transport[work.id]['effort'] == 'person-level'


def test_partial_person_agent_override_can_complete_a_coding_runtime(case, monkeypatch, runtime_catalog):
    ctx, _, work = case
    runtime_reply(monkeypatch, 'coding', 'claude', effort='medium')
    selected = choose_runtime(ctx, work, runtime_catalog, overrides={'agent': 'claude'})
    assert selected['agent'] == 'claude' and selected['effort'] == 'medium'
    assert selected['decider'] == 'jev'


@pytest.mark.parametrize(('agent', 'efforts', 'effort'), [
    ('claude', [], None), ('alternate', ['adaptive'], 'adaptive'), ('claude', ['low'], 'low'),
])
@pytest.mark.parametrize('task_type', ['coding', 'frontend', 'planning', 'analysis', 'routing'])
def test_runtime_keeps_alternate_agents_and_adapter_defined_effort(case, monkeypatch, agent, efforts, effort,
                                                                task_type):
    """The audit's no-control/alternate-agent cases must reach selection and validation."""
    ctx, _, work = case
    catalog = {agent: {'models': {'only': 'The installed capable runtime.'}, 'efforts': efforts}}
    runtime_reply(monkeypatch, task_type, agent, effort=effort)
    chosen = choose_runtime(ctx, work, catalog)
    assert chosen is not None
    assert (chosen['agent'], chosen['model'], chosen['effort']) == (agent, 'only', effort)
    supplied = {key: value for key, value in chosen.items() if key != 'decider'}
    if effort is None:
        supplied.pop('effort')  # A harness with no thinking control does not need a synthetic value.
    assert choose_runtime(ctx, work, catalog, fallback=supplied)['effort'] == effort


def test_local_implementation_uncertainty_does_not_require_another_agent(case, monkeypatch, runtime_transport):
    from dataclasses import replace

    ctx, store, work = case
    expert(ctx)
    store.edit_work(work.id, {'task': 'Improve the alarm error message using the existing interaction conventions.'})
    runtime_reply(monkeypatch, 'coding', 'claude', effort='low')
    assigned = SERVICE.claim(replace(ctx, nouns={'work': work.id, 'role': 'alarm_engineering'}))
    assert assigned['state'] == 'queued'
    assert len(SERVICE.members(ctx, assigned['team_id'])) == 1
    assert runtime_transport[work.id]['agent'] == 'claude'


def test_absent_effort_runtime_is_cached_without_another_model_request(case, monkeypatch,
                                                                     runtime_transport, runtime_catalog):
    from dataclasses import replace

    ctx, _, work = case
    expert(ctx)
    runtime_catalog['claude']['efforts'] = []
    runtime_reply(monkeypatch, 'coding', 'claude')
    assigned = SERVICE.claim(replace(ctx, nouns={'work': work.id, 'role': 'alarm_engineering'}))
    assert assigned['state'] == 'queued'
    assert runtime_transport[work.id]['effort'] is None
    monkeypatch.setattr(jev, 'config', lambda *args: pytest.fail('Retained runtime is already selected'))
    assert SERVICE.prepare_runtime(ctx, assigned)


def test_cached_runtime_reselects_when_dynamic_catalog_excludes_previous_agent(case, monkeypatch,
                                                                             runtime_transport, runtime_catalog):
    from dataclasses import replace

    ctx, _, work = case
    expert(ctx)
    runtime_reply(monkeypatch, 'coding', 'codex', effort='medium')
    assigned = SERVICE.claim(replace(ctx, nouns={'work': work.id, 'role': 'alarm_engineering'}))
    assert assigned['state'] == 'queued'
    runtime_catalog.pop('codex')
    runtime_reply(monkeypatch, 'coding', 'claude', effort='medium')
    assert SERVICE.prepare_runtime(ctx, assigned)
    assert runtime_transport[work.id]['agent'] == 'claude'


def test_related_card_retains_runtime_without_another_classifier(case, monkeypatch, runtime_transport):
    from dataclasses import replace

    ctx, store, work = case
    expert(ctx)
    runtime_reply(monkeypatch, 'coding', 'claude', effort='medium')
    first = SERVICE.claim(replace(ctx, nouns={'work': work.id, 'role': 'alarm_engineering'}))
    SERVICE.bind(ctx, first['assignment_id'], 'retained-worker')
    SERVICE.returned(ctx, work.id, 'First result established.')
    related = store.add_work(Node('element', 'code.timer.kitchen'), None, task='Continue the alarm contribution.')
    monkeypatch.setattr(jev, 'config', lambda *args: pytest.fail('Related work retains its runtime'))
    second = SERVICE.claim(replace(ctx, nouns={
        'work': related.id, 'role': 'alarm_engineering', 'continue_from': work.id}))
    assert second['state'] == 'queued'
    assert runtime_transport[related.id]['agent'] == 'claude'
    assert runtime_transport[related.id]['decision']['decider'] == 'continuation'
    assert runtime_transport[related.id]['decision']['source_work_id'] == work.id
    assert runtime_transport[related.id]['decision']['source_decider'] == 'jev'


@pytest.mark.parametrize('explicit_new_plan', [False, True])
def test_continuation_reuses_consumed_plan_unless_person_requests_new_planning(case, monkeypatch,
                                                                           runtime_transport, explicit_new_plan):
    from dataclasses import replace

    from metaform.modules.orchestration.state import fingerprint

    ctx, store, work = case
    expert(ctx)
    runtime_reply(monkeypatch, 'needs_plan', 'codex', effort='ultra', strongest=True)
    first = SERVICE.claim(replace(ctx, nouns={'work': work.id, 'role': 'alarm_engineering'}))
    planner = next(one for one in SERVICE.members(ctx, first['team_id'])
                   if one['authored_role_uri'] == 'metaform://role/planner')
    plan_result = 'Apply the shared alarm deadline interface before implementing consumers.'
    SERVICE.returned(ctx, planner['work_id'], plan_result, evidence=['Consumer dependencies established.'])
    SERVICE.bind(ctx, first['assignment_id'], 'planned-worker-0')
    SERVICE.returned(ctx, work.id, 'Initial contribution delivered with the retained plan.')
    if explicit_new_plan:
        related = store.add_work(Node('element', 'code.timer.kitchen'), None,
                                 task='Plan a new cross-workstream dependency before continuing.')
        runtime_transport[related.id] = {'agent': 'claude', 'model': 'option-z', 'effort': 'max', 'decision': {
            'decider': 'person', 'confidence': 1.0, 'task_type': 'needs_plan',
            'task_fingerprint': fingerprint(related.task)}}
        runtime_reply(monkeypatch, 'planning', 'codex', effort='ultra', strongest=True)
        assigned = SERVICE.claim(replace(ctx, nouns={
            'work': related.id, 'role': 'alarm_engineering', 'continue_from': work.id}))
        assert assigned['state'] == 'waiting' and assigned['plan'] is None
        new_planner = next(one for one in SERVICE.members(ctx, assigned['team_id'])
                           if one['authored_role_uri'] == 'metaform://role/planner')
        assert new_planner['assignment_id'] != planner['assignment_id']
        return
    monkeypatch.setattr(jev, 'config', lambda *args: pytest.fail('Continuing consumed planning needs no new model'))
    previous = work.id
    for index in (1, 2):
        related = store.add_work(Node('element', 'code.timer.kitchen'), None,
                                 task=f'Continue alarm consumer {index} under the established plan.')
        assigned = SERVICE.claim(replace(ctx, nouns={
            'work': related.id, 'role': 'alarm_engineering', 'continue_from': previous}))
        assert assigned['state'] == 'queued'
        assert len(SERVICE.members(ctx, assigned['team_id'])) == 1
        assert assigned['plan']['assignment_id'] == planner['assignment_id']
        assert assigned['plan']['revision'] == fingerprint(work.task)
        assert assigned['plan']['continued_for'] == fingerprint(related.task)
        assert assigned['plan']['source_work_id'] == work.id
        assert assigned['plan']['result'] == plan_result
        assert runtime_transport[related.id]['decision']['task_type'] == 'needs_plan'
        SERVICE.bind(ctx, assigned['assignment_id'], f'planned-worker-{index}')
        SERVICE.returned(ctx, related.id, 'Related consumer delivered.')
        previous = related.id


def test_bound_facilitator_can_send_vague_implementation_to_planner(case, monkeypatch, runtime_transport):
    from dataclasses import replace

    from metaform.modules.orchestration.state import own

    ctx, _, work = case
    expert(ctx)
    monkeypatch.setattr(jev, 'config', lambda *args: None)
    assigned = SERVICE.claim(replace(ctx, nouns={'work': work.id, 'role': 'alarm_engineering'}))
    with own(ctx).tables(write=False) as tx:
        request = tx.rows('role_requests', {'caller_assignment_id': assigned['assignment_id']}, limit=0).results[0]
    creator = SERVICE.bind(ctx, request['creator_assignment_id'], 'facilitator-session')
    creator_ctx = replace(ctx, session='facilitator-session', nouns={'assignment': creator['assignment_id']})
    supplied = {'agent': 'codex', 'model': 'option-a', 'effort': 'ultra', 'confidence': 0.9,
                'task_type': 'needs_plan', 'reason': 'The ticket needs concrete implementation requirements.'}
    assert SERVICE.runtime(creator_ctx, work.id, supplied)['state'] == 'selected'
    SERVICE.publish_role(replace(creator_ctx, nouns={**creator_ctx.nouns,
        'request': request['request_id'], 'role': 'alarm_engineering'}))
    children = [one for one in SERVICE.members(ctx, assigned['team_id'])
                if one['authored_role_uri'] == 'metaform://role/planner']
    assert len(children) == 1
    assert SERVICE.assignment(ctx, assignment_id=creator['assignment_id'])['state'] == 'returned'
    assert SERVICE.assignment(ctx, work_id=work.id)['state'] == 'waiting'


def test_complete_person_overrides_do_not_freeze_planner_classification(case, monkeypatch, runtime_transport):
    from dataclasses import replace

    from metaform.modules.orchestration.state import fingerprint

    ctx, store, work = case
    expert(ctx)
    fixed = {'agent': 'claude', 'model': 'option-z', 'effort': 'max'}
    runtime_transport[work.id] = {**fixed, 'decision': {
        'decider': 'person', 'confidence': 1.0, 'task_type': 'needs_plan', 'overrides': fixed,
        'task_fingerprint': fingerprint(work.task), 'reason': 'The person changed the ticket runtime.'}}
    runtime_reply(monkeypatch, 'planning', 'codex', effort='ultra', strongest=True)
    assigned = SERVICE.claim(replace(ctx, nouns={'work': work.id, 'role': 'alarm_engineering'}))
    planner = next(one for one in SERVICE.members(ctx, assigned['team_id'])
                   if one['authored_role_uri'] == 'metaform://role/planner')
    assert runtime_transport[planner['work_id']]['decision']['decider'] == 'jev'
    store.edit_work(work.id, {'task': 'Reject expired alarms and verify the exact expiry boundary.'})
    runtime_reply(monkeypatch, 'coding', 'claude', effort='max')
    assert SERVICE.prepare_runtime(ctx, assigned)
    assert all(runtime_transport[work.id][key] == value for key, value in fixed.items())
    assert runtime_transport[work.id]['decision']['task_type'] == 'coding'


def test_explicit_restart_replaces_stopped_runtime_chooser_without_reopening_it(case, monkeypatch,
                                                                              runtime_transport):
    from dataclasses import replace

    from metaform.modules.orchestration.state import own

    ctx, _, work = case
    expert(ctx)
    monkeypatch.setattr(jev, 'config', lambda *args: None)
    assigned = SERVICE.claim(replace(ctx, nouns={'work': work.id, 'role': 'alarm_engineering'}))
    with own(ctx).tables(write=False) as tx:
        original = tx.rows('role_requests', {'caller_assignment_id': assigned['assignment_id']}, limit=0).results[0]
    SERVICE.stopped(ctx, work_id=work.id, by='user')
    SERVICE.reopen(ctx, work.id)
    assert not SERVICE.prepare_runtime(ctx, SERVICE.assignment(ctx, work_id=work.id))
    with own(ctx).tables(write=False) as tx:
        assert len(tx.rows('role_requests', limit=0).results) == 1
    SERVICE.ensure(ctx, work.id, persons=True)
    with own(ctx).tables(write=False) as tx:
        previous = tx.get('role_requests', {'request_id': original['request_id']})
        replacement = next(one for one in tx.rows('role_requests', limit=0).results
                           if one['state'] == 'commissioned')
    assert previous['state'] == 'superseded'
    old_creator = SERVICE.assignment(ctx, assignment_id=original['creator_assignment_id'])
    new_creator = SERVICE.assignment(ctx, assignment_id=replacement['creator_assignment_id'])
    assert old_creator['state'] == 'stopped' and old_creator['stop']
    assert new_creator['state'] == 'queued' and not new_creator['stop'] and new_creator['persons_start']
    SERVICE.ensure(ctx, work.id, persons=True)
    with own(ctx).tables(write=False) as tx:
        assert len(tx.rows('role_requests', limit=0).results) == 2


@pytest.mark.parametrize('protection', ['caller_stop', 'caller_ended', 'creator_stop', 'creator_ended', 'held', 'closed'])
def test_missing_expertise_request_preserves_stops_and_holds(case, monkeypatch, routing_transport, protection):
    from metaform.modules.orchestration.state import own

    ctx, store, work = case
    monkeypatch.setattr(jev, 'config', lambda *args: None)
    SERVICE.route(ctx, work.id)
    caller = SERVICE.assignment(ctx, work_id=work.id)
    with own(ctx).tables() as tx:
        request, = tx.rows('role_requests', limit=0).results
        tx.delete('role_requests', {'request_id': request['request_id']})
        if protection.startswith(('caller_', 'creator_')):
            target = caller['assignment_id'] if protection.startswith('caller_') else request['creator_assignment_id']
            tx.update('assignments', {'assignment_id': target}, {
                'state': 'stopped' if protection.endswith('_stop') else 'returned',
                'stop': {'by': 'person'} if protection.endswith('_stop') else None})
    if protection == 'held':
        store.move_work(work.id, 'backlog', kept=True, hold_reason='Wait for person to release this ticket.')
    elif protection == 'closed':
        store.finish_work(work.id, 'Person cancelled this work.', outcome='cancelled')
    before = {one.id for one in store.work(limit=0).results}

    assert not SERVICE.prepare_runtime(ctx, caller)

    assert {one.id for one in store.work(limit=0).results} == before
    with own(ctx).tables(write=False) as tx:
        assert not tx.rows('role_requests', limit=0).results


def test_missing_unpinned_role_commissions_without_reusing_historical_publication(case, routing_transport):
    from dataclasses import replace

    from metaform.modules.orchestration.state import own

    ctx, _, work = case
    expert(ctx)
    caller = SERVICE.claim(replace(ctx, nouns={
        'work': work.id, 'role': 'alarm_engineering', 'automatic': True}))
    old = SERVICE.request_role(replace(ctx, nouns={
        'task': work.task, 'key': 'expertise', 'context': {'assign_in_place': True}}), caller, 'missing_alarm_domain')
    with own(ctx).tables() as tx:
        tx.update('role_requests', {'request_id': old['request_id']}, {'state': 'published'})
        tx.update('assignments', {'assignment_id': caller['assignment_id']}, {
            'authored_role_uri': 'metaform://role/missing_alarm_domain', 'role_snapshot': None})

    assert not SERVICE.prepare_runtime(ctx, caller)
    assert not SERVICE.prepare_runtime(ctx, caller)

    with own(ctx).tables(write=False) as tx:
        pending = tx.rows('role_requests', {'role': 'missing_alarm_domain', 'state': 'commissioned'}, limit=0).results
    assert len(pending) == 1
    assert pending[0]['role'] == 'missing_alarm_domain'
    assert pending[0]['request_id'] != old['request_id']
    assert pending[0]['caller_assignment_id'] == caller['assignment_id']


@pytest.mark.parametrize('protection', ['held', 'closed'])
def test_publication_preserves_ticket_protected_during_commission(case, monkeypatch, routing_transport, protection):
    from dataclasses import replace

    from metaform.modules.orchestration.state import own

    ctx, store, work = case
    monkeypatch.setattr(jev, 'config', lambda *args: None)
    registered = expert(ctx)
    SERVICE.route(ctx, work.id)
    with own(ctx).tables(write=False) as tx:
        request, = tx.rows('role_requests', limit=0).results
    SERVICE.drain(ctx)
    creator = SERVICE.assignment(ctx, assignment_id=request['creator_assignment_id'])
    if protection == 'held':
        store.move_work(work.id, 'backlog', kept=True, hold_reason='Await revised acceptance conditions.')
    else:
        store.finish_work(work.id, 'Person cancelled this work.', outcome='cancelled')
    before = store.ticket(work.id).work
    monkeypatch.setattr(SERVICE, 'prepare_runtime',
                        lambda *args, **kwargs: pytest.fail('Protected publication cannot prepare follow-up work'))

    SERVICE.publish_role(replace(ctx, session=creator['owner_session_id'], nouns={
        'request': request['request_id'], 'role': registered['uri']}))

    after = store.ticket(work.id).work
    assert (after.held, after.done, after.outcome) == (before.held, before.done, before.outcome)
    assert not any(one['kind'] == 'launch' for one in SERVICE.pending(ctx, [work.id]))


@pytest.mark.parametrize('creator_state', ['running', 'stopped', 'returned'])
def test_lost_runtime_request_reuses_surviving_creator(case, monkeypatch, runtime_transport, creator_state):
    from dataclasses import replace

    from metaform.modules.orchestration.state import own

    ctx, store, work = case
    expert(ctx)
    monkeypatch.setattr(jev, 'config', lambda *args: None)
    assigned = SERVICE.claim(replace(ctx, nouns={'work': work.id, 'role': 'alarm_engineering'}))
    with own(ctx).tables() as tx:
        request, = tx.rows('role_requests', limit=0).results
        tx.delete('role_requests', {'request_id': request['request_id']})
    creator = SERVICE.bind(ctx, request['creator_assignment_id'], 'runtime-creator')
    if creator_state != 'running':
        with own(ctx).tables() as tx:
            tx.update('assignments', {'assignment_id': creator['assignment_id']}, {
                'state': creator_state, 'stop': {'by': 'person'} if creator_state == 'stopped' else None})
    before = {one.id for one in store.work(limit=0).results}

    assert not SERVICE.prepare_runtime(ctx, assigned)

    with own(ctx).tables(write=False) as tx:
        restored, = tx.rows('role_requests', limit=0).results
    assert restored['creator_assignment_id'] == creator['assignment_id']
    assert restored['request_id'] == request['request_id']
    assert SERVICE.assignment(ctx, assignment_id=creator['assignment_id'])['owner_session_id'] == 'runtime-creator'
    assert SERVICE.assignment(ctx, assignment_id=creator['assignment_id'])['state'] == creator_state
    assert {one.id for one in store.work(limit=0).results} == before


@pytest.mark.parametrize('automatic_request', [True, False])
def test_revised_ticket_runtime_gets_new_request_and_launch(case, monkeypatch, runtime_transport,
                                                         automatic_request):
    from dataclasses import replace

    from metaform.modules.orchestration.state import fingerprint, own

    ctx, store, work = case
    expert(ctx)
    monkeypatch.setattr(jev, 'config', lambda *args: None)
    assigned = SERVICE.claim(replace(ctx, nouns={'work': work.id, 'role': 'alarm_engineering'}))
    choice = {'agent': 'codex', 'model': 'option-z', 'effort': 'medium', 'confidence': 0.88,
              'task_type': 'coding', 'reason': 'Concrete alarm expiry requirements.'}

    def publish(request):
        creator_ctx = replace(ctx, nouns={'assignment': request['creator_assignment_id']})
        assert SERVICE.runtime(creator_ctx, work.id, choice)['state'] == 'selected'
        return SERVICE.publish_role(replace(creator_ctx, nouns={**creator_ctx.nouns,
            'request': request['request_id'], 'role': 'alarm_engineering'}))

    with own(ctx).tables(write=False) as tx:
        first = tx.rows('role_requests', {'caller_assignment_id': assigned['assignment_id']}, limit=0).results[0]
    publish(first)
    for event in SERVICE.pending(ctx, [work.id]):
        SERVICE.delivered(ctx, event['transition_id'], {'state': 'completed'})
    assert not SERVICE.pending(ctx, [work.id])

    revised = 'Reject expired alarms and verify the exact expiry boundary.'
    store.edit_work(work.id, {'task': revised})
    if automatic_request:
        assert not SERVICE.prepare_runtime(ctx, assigned)
    else:
        # Isolate publication from request identity so both losses fail independently.
        SERVICE.request_role(replace(ctx, nouns={
            'task': revised, 'key': 'runtime:' + fingerprint(revised),
            'context': {'assign_in_place': True, 'runtime_only': True}}), assigned, 'alarm_engineering')
    with own(ctx).tables(write=False) as tx:
        pending = [one for one in tx.rows('role_requests', {
            'caller_assignment_id': assigned['assignment_id']}, limit=0).results if one['state'] == 'commissioned']
    assert len(pending) == 1
    assert pending[0]['task'].startswith(revised)
    assert pending[0]['request_id'] != first['request_id']
    published = publish(pending[0])
    assert published['assignment']['assignment_id'] == assigned['assignment_id']
    launches = [event for event in SERVICE.pending(ctx, [work.id]) if event['kind'] == 'launch']
    assert len(launches) == 1
    assert launches[0]['payload']['role_request_id'] == pending[0]['request_id']
    SERVICE.publish_role(replace(ctx, nouns={
        'assignment': pending[0]['creator_assignment_id'], 'request': pending[0]['request_id'],
        'role': 'alarm_engineering'}))
    assert [event for event in SERVICE.pending(ctx, [work.id]) if event['kind'] == 'launch'] == launches
    assert SERVICE.prepare_runtime(ctx, assigned)
    assert runtime_transport[work.id]['decision']['task_fingerprint'] == fingerprint(revised)


@pytest.fixture
def routing_transport(case, monkeypatch):
    from metaform.modules.orchestration.tests.test_orchestration import Transport

    made = Transport(capacity=5)
    namespace = SERVICE.drain.__func__.__globals__
    original = namespace['provided']
    monkeypatch.setitem(namespace, 'provided', lambda folder, kind: [('fixture', made)]
                        if kind == 'orchestration.transport' else original(folder, kind))
    return made


def test_pinned_specialist_survives_removal_from_current_registry(case, routing_transport):
    from dataclasses import replace

    ctx, _, work = case
    expert(ctx)
    assigned = SERVICE.claim(replace(ctx, nouns={
        'work': work.id, 'role': 'alarm_engineering', 'automatic': True}))
    snapshot = assigned['role_snapshot']
    with context('agents', ctx.folder, project='proj').require_store().tables() as tx:
        tx.delete('definitions', {'name': 'alarm_engineering'})
    assert 'metaform://specialist/alarm_engineering' not in {one['uri'] for one in ROLES.specialists(ctx)}

    assert SERVICE.selected_specialist(ctx, work.id) == 'metaform://specialist/alarm_engineering'
    SERVICE.drain(ctx)
    bound = SERVICE.assignment(ctx, work_id=work.id)
    assert bound['assignment_id'] == assigned['assignment_id']
    assert bound['role_snapshot'] == snapshot
    assert bound['state'] == 'running'
    assert [one[0]['work_id'] for one in routing_transport.launches] == [work.id]


@pytest.mark.parametrize('loss', ['none', 'creator', 'commission', 'request', 'request_with_stopped_history'])
def test_fresh_routing_commissions_publishes_and_continues_once(case, monkeypatch, routing_transport,
                                                             loss):
    from dataclasses import replace

    from metaform.modules.orchestration.state import own

    ctx, store, work = case
    monkeypatch.setattr(jev, 'config', lambda *args: None)
    registered = expert(ctx)
    existing = store.add_work(Node('element', 'code.alarm.audible'), None, task='Keep existing expertise.')
    preserved = SERVICE.claim(replace(ctx, nouns={
        'work': existing.id, 'role': 'alarm_engineering', 'automatic': True}))
    work_changed({'project': 'proj', 'tables': ['work'], 'kinds': ['filed'],
                  'work_ids': [work.id, existing.id]}, ctx)
    assert SERVICE.route_pending(ctx)[0]['state'] == 'creating'
    owner = SERVICE.assignment(ctx, work_id=work.id)
    with own(ctx).tables(write=False) as tx:
        request, = tx.rows('role_requests', limit=0).results
    assert request['caller_assignment_id'] == owner['assignment_id']
    if loss != 'none':
        if loss.startswith('request'):
            SERVICE.drain(ctx)
        historical = store.add_work(Node('element', 'code.timer.kitchen'), None, task='Stopped old commission.') \
            if loss == 'request_with_stopped_history' else None
        with own(ctx).tables() as tx:
            if not loss.startswith('request'):
                tx.delete('assignments', {'assignment_id': request['creator_assignment_id']})
            if loss == 'commission' or loss.startswith('request'):
                tx.delete('role_requests', {'request_id': request['request_id']})
            if loss == 'request_with_stopped_history':
                active = tx.get('assignments', {'assignment_id': request['creator_assignment_id']})
                tx.insert('assignments', {**active, 'assignment_id': 'f' * 32, 'work_id': historical.id,
                    'state': 'stopped', 'stop': {'by': 'person'}, 'owner_session_id': None,
                    'created': '2099-01-01T00:00:00Z',
                    'return_to': {'assignment_id': owner['assignment_id'], 'role_request_id': 'historical-request'}})
        assert not SERVICE.prepare_runtime(ctx, owner)
    SERVICE.queue_routing(ctx, [work.id, existing.id])
    assert SERVICE.route_pending(ctx) == []
    assert not SERVICE.prepare_runtime(ctx, owner)
    with own(ctx).tables(write=False) as tx:
        current, = tx.rows('role_requests', limit=0).results
    if loss != 'commission':
        assert current['request_id'] == request['request_id']
    assert (current['creator_assignment_id'] != request['creator_assignment_id']) == (loss in ('creator', 'commission'))

    SERVICE.drain(ctx)
    creator = SERVICE.assignment(ctx, assignment_id=current['creator_assignment_id'])
    assert creator['state'] == 'running' and not creator['persons_start']
    assert SERVICE.assignment(ctx, work_id=existing.id)['role_snapshot'] == preserved['role_snapshot']
    writer = replace(ctx, session=creator['owner_session_id'], nouns={
        'request': current['request_id'], 'role': registered['uri'],
        'match_reason': 'Existing alarm expertise covers this ticket.'})
    published = SERVICE.publish_role(writer)
    assert published['assignment']['assignment_id'] == owner['assignment_id']
    assert published['assignment']['work_id'] == work.id
    SERVICE.publish_role(writer)
    SERVICE.queue_routing(ctx, [work.id, existing.id])
    SERVICE.route_pending(ctx)
    SERVICE.drain(ctx)
    SERVICE.drain(ctx)
    assert SERVICE.assignment(ctx, work_id=work.id)['state'] == 'running'
    assert SERVICE.assignment(ctx, work_id=work.id)['role_snapshot']['uri'] == registered['uri']
    assert [one[0]['work_id'] for one in routing_transport.launches].count(work.id) == 1
    assert [one[0]['work_id'] for one in routing_transport.launches].count(existing.id) == 1
    with own(ctx).tables(write=False) as tx:
        assert len(tx.rows('role_requests', limit=0).results) == 1
