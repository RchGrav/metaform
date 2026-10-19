"""Explicit legacy coordinator roles remain usable; new tickets default to direct specialists."""
from __future__ import annotations

import hashlib
import json
import os
import signal
import sys
from pathlib import Path

import pytest

from metaform import events
from metaform.data import Store
from metaform.module import resolve_agent_role
from metaform.modules.dispatch.tests.test_dispatch import NODE, Dispatch, eventually

pytestmark = pytest.mark.kind('simulation')
FAKE = Path(__file__).with_name('fake_swarm_agent.py')
SPECIALIST_RESULT = 'SPECIALIST_RESULT: the route preserves its functional result after resumption.'


@pytest.fixture
def swarm(run, home, project_folder, tmp_path, request):
    made = Dispatch(run, home, project_folder, tmp_path, orchestration=True)
    for agent in ('claude', 'codex', 'gemini'):
        run('set', f'--dispatch-{agent}', f'"{sys.executable}" "{FAKE}"', cwd=project_folder)
    run('set', '--dispatch-agents', '1', '--dispatch-machine-agents', '1', cwd=project_folder)
    # The fixture adapter completes the explicit result/check-in work itself. An optional after-finish note turn
    # is a separate dispatch contract and would not add evidence to this delivery scenario.
    run('set', '--dispatch-record-on-finish', 'off', '--dispatch-autostart', cwd=project_folder)
    from metaform.module import context
    from metaform.modules.orchestration.state import SERVICE
    legacy_ctx = context('orchestration', project_folder, project='proj')
    legacy = SERVICE.ensure(legacy_ctx, made.id, role='gc')
    with Store('proj', module='orchestration').tables() as tx:
        tx.update('assignments', {'assignment_id': legacy['assignment_id']},
                  {'role_snapshot': resolve_agent_role(project_folder, 'gc', project='proj')})
    # Seed an explicit previously assigned duty without scheduling a second runner beside Dispatch.start().
    made.store.move_work(made.id, 'todo', kept=True)
    run('memory', 'create_entities', json.dumps([
        {'name': 'route-grounding', 'entityType': 'functional constraint',
         'observations': ['The caller retains ownership of its requested result.'],
         'why': 'Ground the delivery and nested calls.'}]), f'node=element:{NODE}', cwd=project_folder)
    made.swarm_state = tmp_path / 'swarm-progress'
    (project_folder / 'OPERATIVE.md').write_text('Use the original restoration sequence.\n')
    made.event_log = tmp_path / 'map-events.jsonl'

    def heard(payload):
        with made.event_log.open('a') as stream:
            stream.write(json.dumps({key: payload.get(key) for key in
                                     ('project', 'tables', 'kinds', 'work_ids', 'session_ids')}) + '\n')
    listener = events.listen('swarm-test-evidence', heard)
    yield made
    try:
        write_evidence(made, tmp_path, request.node.name)
    finally:
        run('dispatch', 'stop-all', cwd=project_folder, ok=False)
        listener.close()
        made.close()


def records(module, table):
    with Store('proj', module=module).tables(write=False) as tx:
        return [dict(one) for one in tx.rows(table, limit=0).results]


def write_evidence(swarm, folder, test):
    # Keep the final runtime records beside the exact ACP recipient and cross-process event logs. A caller can
    # retain all evidence with pytest --basetemp; these summaries never substitute for the recipient assertions.
    logged = swarm.entries()
    snapshot = {'test': test, 'root_work_id': swarm.id,
        'recipient_log': swarm.log.name, 'event_log': swarm.event_log.name,
        'assignments': records('orchestration', 'assignments'),
        'transitions': records('orchestration', 'transitions'),
        'role_requests': records('orchestration', 'role_requests'),
        'changes': records('orchestration', 'changes'),
        'generated_role_history': records('agents', 'definition_history'),
        'context_epochs': records('agents', 'contexts'),
        'context_receipts': [{key: value for key, value in one.items() if key != 'component'}
                             for one in records('agents', 'receipts')],
        'user_notifications': [one for one in records('dispatch', 'session_lines')
                               if one['session_id'] == 'conversation-orchestration-updates'
                               and one['kind'] == 'agent_message_chunk'],
        'capacities': [{key: one[key] for key in ('role', 'work', 'session', 'capacity', 'time_ns')}
                       for one in logged if 'capacity' in one],
        'fixture_errors': [one['fixture_error'] for one in logged if 'fixture_error' in one]}
    (folder / 'runtime-evidence.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))


def wait_for(swarm, check, limit=120):
    def observed():
        failures = [one['fixture_error'] for one in swarm.entries() if 'fixture_error' in one]
        assert not failures, '\n'.join(failures)
        if swarm.process is not None and swarm.process.poll() not in (None, 0):
            stdout, stderr = swarm.process.communicate()
            raise AssertionError(f'Initial runner failed: {stdout!r} {stderr!r}')
        return check()
    return eventually(observed, limit=limit)


def completed(swarm):
    def held():
        found = records('orchestration', 'assignments')
        return found if found and any(one['reviewed_assignment_id'] for one in found) and all(
            one['state'] in ('returned', 'delivered') for one in found) else None
    return wait_for(swarm, held)


def pm_evidence(swarm, scenario, expected):
    """An available PM gets inbox references, not update bodies; retained context does not announce them again."""
    wait_for(swarm, lambda: not any(one['state'] == 'running' and one['work_id'] != 'conversation-system'
                                  for one in records('dispatch', 'agent_sessions')))
    # Session end is recorded before its runner releases admission. Respect the same actual ledger as a launch.
    wait_for(swarm, lambda: json.loads(swarm.run('dispatch', 'agents', '--json', cwd=swarm.folder).stdout)[
        'slots']['machine_used'] == 0)
    environment = swarm.env('ask', FAKE_SWARM_SCENARIO=scenario, FAKE_SWARM_STATE=str(swarm.swarm_state))
    started = json.loads(swarm.run('dispatch', 'system', '--json', cwd=swarm.folder, env=environment).stdout)
    # Missing-key fallback may already have connected the PM while workers were active.
    # Address that available session instead of waiting for it to stop being available.
    swarm.run('dispatch', 'message', started['work_id'], 'PM_CONNECTED: report current delivery state.',
              cwd=swarm.folder)
    observed = wait_for(swarm, lambda: next((one for one in swarm.entries()
                                            if 'PM_CONNECTED:' in one.get('pm_observation', '')), None))
    assert observed['role'] == 'triage'
    seen = [one['pm_observation'] for one in swarm.entries()
            if 'pm_observation' in one and one['session'] == observed['session']]
    assert any('new in your inbox' in text for text in seen)
    bodies = [text for text in expected if text != 'C(T)']  # C(T) is in every role's instructions too
    assert not any(text in turn for text in bodies for turn in seen), 'No update body reaches its turns.'
    updates = '\n'.join(one['text'] for one in records('dispatch', 'session_lines')
                         if str(one['name']).startswith('notification:'))
    assert all(text in updates for text in expected), 'Each update stays whole where it is read.'
    assert observed['capacity']['machine_used'] == 0
    assert observed['capacity']['machine_limit'] == 1
    session = observed['session']
    swarm.run('dispatch', 'stop', started['work_id'], f'session={session}', cwd=swarm.folder)
    wait_for(swarm, lambda: any(one['session_id'] == session and one['state'] == 'ended'
                               for one in records('dispatch', 'agent_sessions')))
    resumed = json.loads(swarm.run('dispatch', 'resume', started['work_id'], f'session={session}', '--json',
                                   cwd=swarm.folder, env=environment).stdout)
    assert resumed['session_id'] == session
    wait_for(swarm, lambda: any(one.get('session_loaded') == session for one in swarm.entries()))
    swarm.run('dispatch', 'message', started['work_id'], 'PM_RECONNECTED: report current delivery state.',
              f'session={session}', cwd=swarm.folder)
    again = wait_for(swarm, lambda: next((one for one in reversed(swarm.entries())
                                         if 'PM_RECONNECTED:' in one.get('pm_observation', '')), None))
    assert again['session'] == session and again['pid'] != observed['pid']
    assert again['runner_identity'] == observed['runner_identity']
    assert 'new in your inbox' not in again['pm_observation'], 'Updates its inbox line named are not new again.'
    assert not swarm.questions(), 'The PM receives informational updates without introducing an approval wait.'


def delivery_evidence(swarm, scenario):
    swarm.start(FAKE_SWARM_SCENARIO=scenario, FAKE_SWARM_STATE=str(swarm.swarm_state))
    assignments = completed(swarm)
    wait_for(swarm, lambda: any('fqc_observation' in one for one in swarm.entries()))
    root = next(one for one in assignments if one['work_id'] == swarm.id)
    worker = next(one for one in assignments if one['authored_role_uri'] == 'metaform://role/implementer')
    specialists = [one for one in assignments if one['authored_role_uri'] in (
        'metaform://role/investigator', 'metaform://role/route_specialist')]
    critic = next(one for one in assignments if one['authored_role_uri'] == 'metaform://role/functionality')
    assert swarm.ticket().done and root['state'] == 'delivered'
    assert root['authored_role_uri'] == 'metaform://role/gc'
    assert worker['parent_assignment_id'] == root['assignment_id']
    assert all(one['parent_assignment_id'] == worker['assignment_id'] and
               one['return_to']['assignment_id'] == worker['assignment_id'] for one in specialists)
    assert {one['team_id'] for one in [root, worker, *specialists]} == {root['team_id']}
    assert critic['reviewed_assignment_id'] == root['assignment_id']
    assert critic['team_id'] != root['team_id'] and critic['parent_assignment_id'] is None
    assert root['candidate'] == critic['candidate']
    assert 'GC_VALIDATED' in json.loads(critic['task'])['report']['body']
    assert SPECIALIST_RESULT in (swarm.folder / 'candidate.txt').read_text()

    logged = swarm.entries()
    capacities = [one['capacity'] for one in logged if 'capacity' in one]
    assert capacities and all(one['limit'] == one['machine_limit'] == 1 and one['used'] == one['machine_used'] <= 1
                              for one in capacities)
    contexts = [one for one in logged if 'recipient_context' in one]
    assert {one['role'] for one in contexts} >= {'gc', 'implementer', 'functionality'}
    assert not any('"tools": {' in one['recipient_context'] for one in contexts)
    common = next(one['text'] for one in resolve_agent_role(swarm.folder, 'gc', project='proj')['components']
                  if one['name'] == 'orchestration:common')
    for role in ('gc', 'implementer'):
        own = [one for one in contexts if one['role'] == role]
        assert not any(common in one['recipient_context'] for one in own)
        resources = [one['role_resource'] for one in logged if one['role'] == role and 'role_resource' in one]
        assert sum(common in json.dumps(one, ensure_ascii=False).replace('\\n', '\n') for one in resources) == 1
    receipts = records('agents', 'receipts')
    assert any(one['name'] == 'orchestration:common' and one['actual_version_id'] and
               one['component']['text'] == common for one in receipts)
    resumed = [one for one in logged if 'session_loaded' in one]
    assert {'gc', 'implementer'} <= {one['role'] for one in resumed}
    worker_returns = [one for one in contexts if one['role'] == 'implementer' and
                      SPECIALIST_RESULT in one['recipient_context']]
    assert worker_returns, 'The immediate worker actually received its specialist result in an ACP prompt.'
    assert not any('RETAINED_WORKER_DRAFT' in one['recipient_context'] for one in worker_returns)
    assert any('RETAINED_WORKER_DRAFT' in json.dumps(one.get('assignment_context', {})) for one in logged
               if one['role'] == 'implementer')
    gc_returns = [one for one in contexts if one['role'] == 'gc' and 'WORKER_INTEGRATED' in one['recipient_context']]
    assert gc_returns, 'The GC actually received the integrated worker result.'
    assert any(one.get('specialist_grounding', {}).get('entities') for one in logged)
    assert any('GC_VALIDATED' in one.get('text', '') for one in records('dispatch', 'session_lines')
               if one['session_id'] == 'conversation-orchestration-updates')
    worker_calls = [one for one in logged if one.get('mcp_tool', {}).get('name') == 'orchestration_call']
    assert len(worker_calls) == 1 and worker_calls[0]['role'] == 'implementer'
    assert worker_calls[0]['mcp_tool']['runner_identity'] == worker_calls[0]['runner_identity']
    assert worker_calls[0]['mcp_tool']['is_error'] is False
    return assignments, logged


def test_capacity_one_gc_worker_specialist_return_and_independent_fqc(swarm):
    assignments, logged = delivery_evidence(swarm, 'nested')
    assert len(assignments) == 4
    assert len([one for one in logged if 'session_created' in one]) == 4
    assert len([one for one in logged if 'session_loaded' in one]) == 2
    transitions = records('orchestration', 'transitions')
    assert len([one for one in transitions if one['kind'] == 'suspend' and one['state'] == 'delivered']) == 2
    pm_evidence(swarm, 'nested', ['GC_VALIDATED', 'FQC_ACCEPTED'])


def test_worker_missing_role_returns_through_gc_creator_published_duty_and_registered_reuse(swarm):
    assignments, logged = delivery_evidence(swarm, 'generated')
    requests = records('orchestration', 'role_requests')
    assert len(requests) == 1 and requests[0]['state'] == 'published'
    requested = requests[0]
    creator = next(one for one in assignments if one['authored_role_uri'] == 'metaform://role/facilitator')
    worker = next(one for one in assignments if one['authored_role_uri'] == 'metaform://role/implementer')
    specialists = [one for one in assignments if one['authored_role_uri'] == 'metaform://role/route_specialist']
    assert requested['caller_assignment_id'] == worker['assignment_id']
    assert requested['creator_assignment_id'] == creator['assignment_id'] and len(specialists) == 2
    assert requested['context']['contribution'] == 'Verify functional return behavior.'
    assert requested['creator_assignment_id'], 'A missing role commissions its helper automatically.'
    received = [one['recipient_context'] for one in logged if one.get('role') == 'route_specialist'
                and 'recipient_context' in one]
    assert len(received) >= 2 and all('You are the Route Specialist.' not in one for one in received)
    duties = [one['role_resource'] for one in logged if one['role'] == 'route_specialist' and 'role_resource' in one]
    assert len(duties) >= 2 and all('You are the Route Specialist.' in json.dumps(one) for one in duties)
    generated = [one for one in records('agents', 'definitions') if one['name'] == 'route_specialist']
    assert len(generated) == 1
    assert requested['source']['name'] == 'route_specialist'
    history = [one for one in records('agents', 'definition_history') if one['name'] == 'route_specialist']
    assert len(history) == 1 and history[0]['version_id'] == generated[0]['version_id']
    duty_receipts = [one for one in records('agents', 'receipts')
                     if one['name'] == 'agents:generated_proj_route_specialist']
    assert len(duty_receipts) == 2 and {one['actual_version_id'] for one in duty_receipts} == {
        generated[0]['version_id']}


def test_capacity_one_gc_requests_and_commissions_own_missing_role_then_receives_specialist_and_fqc(swarm):
    swarm.start(FAKE_SWARM_SCENARIO='gc-generated', FAKE_SWARM_STATE=str(swarm.swarm_state))
    assignments = completed(swarm)
    root = next(one for one in assignments if one['work_id'] == swarm.id)
    creator = next(one for one in assignments if one['authored_role_uri'] == 'metaform://role/facilitator')
    specialist = next(one for one in assignments if one['authored_role_uri'] == 'metaform://role/route_specialist')
    critic = next(one for one in assignments if one['authored_role_uri'] == 'metaform://role/functionality')
    assert len(assignments) == 4 and root['state'] == 'delivered' and swarm.ticket().done
    assert creator['parent_assignment_id'] == specialist['parent_assignment_id'] == root['assignment_id']
    assert creator['team_id'] == specialist['team_id'] == root['team_id']
    assert specialist['return_to']['assignment_id'] == root['assignment_id']
    assert critic['reviewed_assignment_id'] == root['assignment_id']
    assert critic['team_id'] != root['team_id'] and critic['parent_assignment_id'] is None
    assert critic['candidate'] == root['candidate']
    assert 'GC_VALIDATED' in json.loads(critic['task'])['report']['body']

    logged = swarm.entries()
    requested = next(one['gc_self_request'] for one in logged if 'gc_self_request' in one)
    assert requested['request']['state'] in ('commissioned', 'published')
    assert requested['request']['caller_assignment_id'] == requested['request']['gc_assignment_id'] == \
        root['assignment_id']
    calls = [one for one in logged if one.get('mcp_tool', {}).get('name') in (
        'orchestration_call', 'orchestration_commission')]
    assert [one['mcp_tool']['name'] for one in calls] == ['orchestration_call']
    assert all(one['role'] == 'gc' and one['mcp_tool']['is_error'] is False and
               one['mcp_tool']['runner_identity'] == one['runner_identity'] for one in calls)
    received = next(one['gc_self_received'] for one in logged if 'gc_self_received' in one)
    # The GC may read the completed result before its queued notice arrives. Its explicit read
    # must supply the result without requiring the startup prompt to repeat it.
    assert SPECIALIST_RESULT in received['result'] and 'RETAINED_GC_SPECIALIST_PLAN' not in received['text']
    assert 'RETAINED_GC_SPECIALIST_PLAN' in json.dumps(received['assignment'])
    assert any(one.get('role') == 'gc' and 'session_loaded' in one for one in logged)
    assert any('fqc_observation' in one for one in logged)
    capacities = [one['capacity'] for one in logged if 'capacity' in one]
    assert capacities and all(one['limit'] == one['machine_limit'] == 1 and one['used'] == one['machine_used'] <= 1
                              for one in capacities)
    request = records('orchestration', 'role_requests')[0]
    assert request['state'] == 'published' and request['creator_assignment_id'] == creator['assignment_id']
    assert request['child_assignment_id'] == specialist['assignment_id']
    definition = next(one for one in records('agents', 'definitions') if one['name'] == 'route_specialist')
    duty = [one for one in records('agents', 'receipts')
            if one['name'] == 'agents:generated_proj_route_specialist']
    assert len(duty) == 1 and duty[0]['actual_version_id'] == definition['version_id']
    assert any('You are the Route Specialist.' in json.dumps(one.get('role_resource', {}))
               for one in logged if one['role'] == 'route_specialist')
    pm_evidence(swarm, 'gc-generated', ['GC_VALIDATED', 'FQC_ACCEPTED'])


def test_installed_bmad_menu_and_source_reach_managed_specialist_and_return_to_gc(swarm):
    installed = swarm.folder / '_bmad'
    (installed / '_config').mkdir(parents=True)
    (installed / 'bmm/agents').mkdir(parents=True)
    (installed / '_config/manifest.yaml').write_text('installation:\n  version: fixture-installed-version\n')
    (installed / '_config/agent-manifest.csv').write_text(
        'name,title,module,path\ndev,Developer,bmm,_bmad/bmm/agents/dev.md\n')
    source = ('# Installed BMAD developer\n<activation>Use the supplied menu input.</activation>\n'
              '<menu><item cmd="CR">Review timer controls and return the observed interaction evidence.</item>'
              '</menu>\nBMAD-INSTALLED-ENTRY-CR\n')
    (installed / 'bmm/agents/dev.md').write_text(source)
    swarm.start(FAKE_SWARM_SCENARIO='bmad', FAKE_SWARM_STATE=str(swarm.swarm_state))
    assignments = completed(swarm)
    gc = next(one for one in assignments if one['work_id'] == swarm.id)
    specialty = next(one for one in assignments if one['authored_role_uri'] == 'metaform://role/bmad.bmm.dev')
    assert specialty['parent_assignment_id'] == gc['assignment_id'] and specialty['team_id'] == gc['team_id']
    assert specialty['return_to']['assignment_id'] == gc['assignment_id']
    actual = next(one['bmad_installed_observation'] for one in swarm.entries() if 'bmad_installed_observation' in one)
    assert actual['source'] == source and actual['task'].startswith('CR: review timer controls')
    assert 'Preserve the functional return after resumption.' in actual['task']
    assert any('BMAD_INSTALLED_REVIEW' in one['bmad_caller_received']['text'] for one in swarm.entries()
               if 'bmad_caller_received' in one)
    discovery = next(one['bmad_discovery'] for one in swarm.entries() if 'bmad_discovery' in one)
    role = next(one for one in discovery['roles'] if one['name'] == 'bmad.bmm.dev')
    assert role['source_fingerprint'] == hashlib.sha256(source.encode()).hexdigest()
    assert role['installed_version'] == 'fixture-installed-version' and 'cmd="CR"' in role['menu']
    receipts = [one for one in records('agents', 'receipts') if one['name'] == role['prompt']]
    assert receipts and receipts[0]['actual_version_id'] == role['actual_version_id']
    assert source in receipts[0]['component']['text']
    capacities = [one['capacity'] for one in swarm.entries() if 'capacity' in one]
    assert len(assignments) == 3 and all(one['used'] == one['machine_used'] == 1 for one in capacities)


def test_actual_acp_compaction_recovers_role_assignment_and_memory_only_when_read(swarm):
    swarm.start(FAKE_SWARM_SCENARIO='compaction', FAKE_SWARM_STATE=str(swarm.swarm_state))
    first = wait_for(swarm, lambda: next((one for one in swarm.entries() if 'compaction_ready' in one), None))
    runner = first['runner_identity']
    common = next(one['text'] for one in resolve_agent_role(swarm.folder, 'gc', project='proj')['components']
                  if one['name'] == 'orchestration:common')
    (swarm.swarm_state / 'compact').touch()
    wait_for(swarm, lambda: any(one['session_id'] == runner and one['epoch'] == 1
                               for one in records('agents', 'contexts')))
    swarm.run('dispatch', 'message', swarm.id, 'COMPACTION_CONTINUE: validate the retained functional result.',
              cwd=swarm.folder)
    (swarm.swarm_state / 'compaction-release').touch()
    assignments = completed(swarm)
    restored = next(one['compaction_restored'] for one in swarm.entries() if 'compaction_restored' in one)
    assert common not in restored['text'] and 'orchestration_call' not in restored['text']
    assert 'RETAINED_COMPACTION_PLAN' not in restored['text']
    assert 'RETAINED_COMPACTION_PLAN' in json.dumps(restored['assignment'])
    before = next(one['compaction_grounding'] for one in swarm.entries() if 'compaction_grounding' in one)
    assert restored['memory']['entities'] == before['entities']
    receipts = [one for one in records('agents', 'receipts') if one['session_id'] == runner]
    for name in ('orchestration:common', 'memory:entity:route-grounding'):
        assert {one['epoch'] for one in receipts if one['name'] == name} == {0, 1}
    contexts = [one['recipient_context'] for one in swarm.entries()
                if one['role'] == 'gc' and 'recipient_context' in one]
    assert not any(common in text for text in contexts)
    duties = [one['role_resource'] for one in swarm.entries() if one['role'] == 'gc' and 'role_resource' in one]
    assert sum(common in json.dumps(one, ensure_ascii=False).replace('\\n', '\n') for one in duties) == 2
    assert len(assignments) == 2 and swarm.ticket().done
    capacities = [one['capacity'] for one in swarm.entries() if 'capacity' in one]
    assert capacities and all(one['used'] == one['machine_used'] == 1 for one in capacities)


def test_user_stops_a_suspended_gc_and_its_live_child_without_restarting_pending_work(swarm):
    swarm.start(FAKE_SWARM_SCENARIO='stopped', FAKE_SWARM_STATE=str(swarm.swarm_state))
    worker = wait_for(swarm, lambda: next((one for one in swarm.entries() if 'stoppable_worker' in one), None))
    before = records('orchestration', 'assignments')
    gc = next(one for one in before if one['work_id'] == swarm.id)
    assert gc['state'] in ('suspended', 'waiting')
    assert next(one for one in before if one['work_id'] == worker['work'])['state'] == 'running'
    swarm.run('dispatch', 'stop', swarm.id, cwd=swarm.folder)
    wait_for(swarm, lambda: not any(one['state'] == 'running' for one in records('dispatch', 'agent_sessions')))
    after = records('orchestration', 'assignments')
    assert len(after) == 2 and {one['state'] for one in after} == {'stopped'}
    assert all(one['stop']['by'] == 'user' for one in after)
    assert 'RETAINED_WORKER_DRAFT' in str(next(one for one in after if one['work_id'] == worker['work'])['last_check_in'])
    assert not any(one['state'] == 'pending' for one in records('orchestration', 'transitions'))
    assert not swarm.ticket().done
    slots = json.loads(swarm.run('dispatch', 'agents', '--json', cwd=swarm.folder).stdout)['slots']
    assert slots['used'] == slots['machine_used'] == 0
    assert not any('session_loaded' in one for one in swarm.entries()), 'Stopped delivery queued no automatic resume.'


@pytest.mark.parametrize('mode', ['adaptive', 'strict'])
def test_independent_fqc_change_order_reaches_gc_and_user_with_strict_recommendation_when_selected(swarm, mode):
    swarm.run('set', '--orchestration-mode', mode, cwd=swarm.folder)
    with Store('proj', module='orchestration').tables() as tx:
        root = next(one for one in tx.rows('assignments', limit=0).results if one['work_id'] == swarm.id)
        tx.update('assignments', {'assignment_id': root['assignment_id']}, {'mode': mode})
    swarm.start(FAKE_SWARM_SCENARIO=mode, FAKE_SWARM_STATE=str(swarm.swarm_state))
    assignments = completed(swarm)
    changes = records('orchestration', 'changes')
    assert len(changes) == 1
    change = changes[0]
    assert change['state'] == ('published' if mode == 'adaptive' else 'recommendation')
    assert change['user_message_state'] == 'delivered'
    assert 'C(T)' in change['reason'] and change['observed_limitation']
    logged = swarm.entries()
    returned = [one for one in logged if 'gc_change_received' in one]
    assert returned, 'The resumed GC read the actual operative state after the FQC result.'
    notice_lines = [one for one in records('dispatch', 'session_lines')
                    if one['session_id'] == 'conversation-orchestration-updates' and
                    one['kind'] == 'agent_message_chunk']
    assert any('C(T)' in one['text'] and change['reason'] in one['text'] for one in notice_lines)
    assert not swarm.questions(), 'Adaptive visibility is an actual message and does not ask approval.'
    contexts = [one['recipient_context'] for one in logged if one.get('role') == 'gc' and 'recipient_context' in one]
    if mode == 'adaptive':
        assert (swarm.folder / 'OPERATIVE.md').read_text() == change['content']
        assert any('change_order' in one and change['current_revision'] in one for one in contexts)
        root = next(one for one in assignments if one['work_id'] == swarm.id)
        assert root['attempt'] == 2 and root['state'] == 'delivered'
        assert not any(one['authored_role_uri'] == 'metaform://role/gc' and one['parent_assignment_id']
                       for one in assignments), 'Findings repair the original ticket without a coordinator tree.'
        assert len([one for one in assignments if one['reviewed_assignment_id'] == root['assignment_id']]) == 1
    else:
        assert (swarm.folder / 'OPERATIVE.md').read_text() == change['before_content']
        assert any('recommendation' in one for one in contexts)
        assert not any('correction_delivered' in one for one in logged)
    capacities = [one['capacity'] for one in logged if 'capacity' in one]
    assert capacities and all(one['used'] == one['machine_used'] == 1 for one in capacities)
    pm_evidence(swarm, mode, ['GC_VALIDATED', 'FQC_FINDING', change['reason'], 'C(T)'])


@pytest.mark.parametrize('restart', [False, True])
def test_discovery_threaded_peer_delivery_and_gc_descendant_broadcast_and_interruption(swarm, restart):
    swarm.run('set', '--dispatch-agents', '3', '--dispatch-machine-agents', '3', cwd=swarm.folder)
    swarm.start(FAKE_SWARM_SCENARIO='communications', FAKE_SWARM_STATE=str(swarm.swarm_state))
    wait_for(swarm, lambda: all(any(flag in one for one in swarm.entries())
                              for flag in ('gc_ready', 'worker_ready', 'specialist_ready')))
    (swarm.swarm_state / 'peer-note').touch()
    wait_for(swarm, lambda: any('peer_note_sent' in one for one in swarm.entries()))
    early = swarm.entries()
    assert not any(one.get('message', {}).get('method') in ('session/cancel', '_session/steering') for one in early)
    peer_sent = next(one for one in early if 'peer_note_sent' in one)
    assert peer_sent['peer_interrupt_refused']['code'] != 0
    assert peer_sent['worker_broadcast_refused']['code'] != 0
    assert not any('PEER_NOTE:' in one.get('recipient_context', '') for one in early if one['role'] == 'investigator')
    (swarm.swarm_state / 'broadcast').touch()
    wait_for(swarm, lambda: any('gc_broadcast' in one for one in swarm.entries()))
    broadcast = next(one['gc_broadcast'] for one in swarm.entries() if 'gc_broadcast' in one)
    assert len(broadcast['recipients']) == 2 and broadcast['steered'] is False
    assert broadcast['team_id'] == next(one['team_id'] for one in records('orchestration', 'assignments')
                                        if one['work_id'] == swarm.id)
    discovery = {one['role']: one['all_agent_discovery']['peers'] for one in swarm.entries()
                 if 'all_agent_discovery' in one}
    assert set(discovery) == {'gc', 'implementer', 'investigator'}
    for peers in discovery.values():
        assert {one['authored_role_uri'] for one in peers} == {
            'metaform://role/gc', 'metaform://role/implementer', 'metaform://role/investigator'}
        assert {one['session_id'] for one in peers} == {
            one['owner_session_id'] for one in records('orchestration', 'assignments')}
    (swarm.swarm_state / 'specialist-release').touch()
    wait_for(swarm, lambda: any('specialist_reply' in one for one in swarm.entries()))
    (swarm.swarm_state / 'worker-release').touch()
    wait_for(swarm, lambda: any('PEER_REPLY:' in one.get('worker_peer_turn', '') for one in swarm.entries()))
    before_interrupt = swarm.entries()
    assert not any(one.get('message', {}).get('method') in ('session/cancel', '_session/steering')
                   for one in before_interrupt)
    (swarm.swarm_state / 'interrupt').touch()
    wait_for(swarm, lambda: any('interrupted_recipient' in one for one in swarm.entries()))
    seen = swarm.entries()
    cancelled = [one for one in seen if one.get('message', {}).get('method') == 'session/cancel']
    assert cancelled and {one['role'] for one in cancelled} == {'investigator'}
    assert not any(one.get('message', {}).get('method') == '_session/steering' for one in seen)
    received = next(one['interrupted_recipient'] for one in seen if 'interrupted_recipient' in one)
    assert received['assignment']['pending_direction']
    assert 'NEW_GC_DIRECTION' in received['text'] and 'RETAINED_SPECIALIST_STATE' not in received['text']
    assert 'RETAINED_SPECIALIST_STATE' in json.dumps(received['assignment'])
    assert any('GC_SWARM_BROADCAST' in one.get('recipient_context', '') for one in seen
               if one['role'] == 'implementer')
    peer_rows = [json.loads(one['text']) for one in records('dispatch', 'session_lines') if one['kind'] == 'peer']
    original = next(one for one in peer_rows if one['text'].startswith('PEER_NOTE:'))
    replies = [one for one in peer_rows if one['text'].startswith('PEER_REPLY:')]
    assert replies and all(one['reply_to'] == original['id'] for one in replies)
    assert original['from']['authored_role_uri'] == 'metaform://role/implementer'
    assert {one['from']['authored_role_uri'] for one in replies} == {'metaform://role/investigator'}
    capacities = [one['capacity'] for one in seen if 'capacity' in one]
    assert capacities and max(one['used'] for one in capacities) == 3
    assert all(one['used'] <= one['limit'] == 3 and one['machine_used'] <= one['machine_limit'] == 3
               for one in capacities)
    if restart:
        from metaform.modules.dispatch import end_group

        def following():
            return next((one for one in records('orchestration', 'assignments')
                         if one['authored_role_uri'] == 'metaform://role/investigator' and
                         'Following NEW_GC_DIRECTION' in str(one['last_check_in'])), None)
        held = wait_for(swarm, following)
        session = held['owner_session_id']
        running = next(one for one in records('dispatch', 'agent_sessions') if one['session_id'] == session)
        adapter = next(one['pid'] for one in reversed(swarm.entries())
                       if one['session'] == session and 'interrupted_recipient' in one)
        # A real crash between turns: kill only this isolated fixture's identified runner and adapter group.
        os.kill(running['pid'], signal.SIGKILL)
        end_group(adapter)
        resumed = swarm.run('dispatch', 'resume', held['work_id'], f'session={session}', '--json', cwd=swarm.folder,
                            env=swarm.env('ask', FAKE_SWARM_SCENARIO='communications',
                                          FAKE_SWARM_STATE=str(swarm.swarm_state)))
        assert json.loads(resumed.stdout)['session_id'] == session
        wait_for(swarm, lambda: any(one['session'] == session and one['pid'] != adapter and
                                   'interrupted_recipient' in one for one in swarm.entries()))
        restored = next(one for one in reversed(swarm.entries()) if one['session'] == session and
                        one['pid'] != adapter and 'interrupted_recipient' in one)
        assert 'RETAINED_SPECIALIST_STATE' in restored['interrupted_recipient']['text']
        assert any(one.get('session_loaded') == session and one['pid'] != adapter for one in swarm.entries())
        assert following()['pending_direction'] == held['pending_direction']
