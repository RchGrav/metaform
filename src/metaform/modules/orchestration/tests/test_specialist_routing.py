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
def test_credit_unavailable_preserves_ticket_for_triage_without_generic_worker(case, monkeypatch, balance):
    ctx, store, work = case
    expert(ctx)
    monkeypatch.setattr(jev, 'config', lambda *a: SimpleNamespace(endpoint=SimpleNamespace(name='openrouter')))
    monkeypatch.setattr(jev, 'openrouter_credits', lambda: {'status': balance})
    monkeypatch.setattr(jev, 'pick_one', lambda *a, **kw: pytest.fail('No paid selection without credit'))
    found = SERVICE.route(ctx, work.id)
    assert found['state'] == 'triage' and found['role'] is None
    assert not store.ticket(work.id).work.taken
    with pytest.raises(Stop, match='specialist'):
        SERVICE.ensure(ctx, work.id)
    assert SERVICE.assignment(ctx, work_id=work.id) is None


def test_filed_event_only_queues_and_no_specialist_requests_reusable_role(case, monkeypatch):
    ctx, store, work = case
    monkeypatch.setattr(jev, 'pick_one', lambda *a, **kw: pytest.fail('Filing cannot call models'))
    work_changed({'project': 'proj', 'tables': ['work'], 'kinds': ['filed'], 'work_ids': [work.id]}, ctx)
    assert SERVICE.route_pending(ctx)[0]['state'] == 'triage'
    assert not store.ticket(work.id).work.taken
    ctx.nouns.update(work=work.id, role='alarm_engineering', purpose='Reliable countdown alarms.')
    assigned = SERVICE.claim(ctx)
    assert assigned['role_request']['state'] == 'commissioned'
    assert assigned['authored_role_uri'] == 'metaform://role/alarm_engineering'


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
