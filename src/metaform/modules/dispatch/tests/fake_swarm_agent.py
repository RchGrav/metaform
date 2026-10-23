"""Deterministic ACP swarm, using real public Metaform CLI calls and no model or network.

Each launched adapter receives its real runner identity and authored role. Progress is kept per work id outside the
adapter process, so a suspension or session/load cannot accidentally restart a contribution. The log contains exact
ACP recipient prompts, tool inputs/results, candidate observations and the public admission ledger at each turn.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path

LOG = Path(os.environ['FAKE_ACP_LOG'])
STATE = Path(os.environ['FAKE_SWARM_STATE'])
STATE.mkdir(parents=True, exist_ok=True)
SCENARIO = os.environ.get('FAKE_SWARM_SCENARIO', 'nested')
WORK = os.environ.get('METAFORM_WORK', 'catalog-prime')
ROLE_URI = os.environ.get('METAFORM_AUTHORED_ROLE', '')
ROLE = ROLE_URI.removeprefix('metaform://role/').removeprefix('metaform://specialist/')
SESSION = ''
MCP_SERVER = None
DUTY = ''
WRITING = threading.Lock()
CANCELLED = threading.Event()
PROGRESS = STATE / f'{WORK}.json'
CANDIDATE = {'revision': 'fake-swarm-candidate-1', 'path': 'candidate.txt'}
SPECIALIST_RESULT = 'SPECIALIST_RESULT: the route preserves its functional result after resumption.'
OPERATIVE = 'Preserve the functional return; restore retained work before continuing.\n'
CORRECTION = 'CORRECTIVE_RESULT: restored retained work before continuing.\n'
MODEL = ['swarm-light']
EFFORT = ['low']


def config_options():
    return [{'id': 'model', 'name': 'Model', 'type': 'select', 'category': 'model', 'currentValue': MODEL[0],
             'options': [
                 {'value': 'swarm-light', 'name': 'Fixture light',
                  'description': 'Lightweight model for lookups and precise implementation.'},
                 {'value': 'swarm-deep', 'name': 'Fixture deep',
                  'description': 'Highest capability model for planning and complex analysis.'}]},
            {'id': 'reasoning', 'name': 'Effort', 'type': 'select', 'category': 'thought_level',
             'currentValue': EFFORT[0],
             'options': [{'value': value, 'name': value.title()}
                         for value in ('off', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra')]}]


def log(**entry):
    record = {'pid': os.getpid(), 'role': ROLE, 'work': WORK, 'session': SESSION, 'scenario': SCENARIO,
              'runner_identity': os.environ.get('METAFORM_SESSION'), 'time_ns': time.time_ns(), **entry}
    data = (json.dumps(record, ensure_ascii=False) + '\n').encode()
    with WRITING:
        descriptor = os.open(LOG, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(descriptor, data)
        finally:
            os.close(descriptor)


def send(message):
    with WRITING:
        sys.stdout.buffer.write(json.dumps(message).encode() + b'\n')
        sys.stdout.buffer.flush()


def update(body):
    send({'jsonrpc': '2.0', 'method': 'session/update', 'params': {'sessionId': SESSION, 'update': body}})


def cli(module, verb, *, expect_error=False, **nouns):
    rendered = {key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list, bool)) else str(value)
                for key, value in nouns.items()}
    words = [module, verb, *(f'{key}={value}' for key, value in rendered.items()), '--json']
    ident = uuid.uuid4().hex[:12]
    update({'sessionUpdate': 'tool_call', 'toolCallId': ident, 'title': f'metaform {module} {verb}',
            'kind': 'execute', 'status': 'in_progress', 'rawInput': {'arguments': words}})
    result = subprocess.run([sys.executable, '-m', 'metaform', *words], capture_output=True, text=True,
                            check=False, timeout=45)
    try:
        value = json.loads(result.stdout)
    except ValueError:
        value = result.stdout
    log(tool={'module': module, 'verb': verb, 'nouns': nouns, 'code': result.returncode,
              'result': value, 'stderr': result.stderr})
    update({'sessionUpdate': 'tool_call_update', 'toolCallId': ident,
            'status': 'failed' if result.returncode else 'completed', 'rawOutput': value,
            'content': [{'type': 'content', 'content': {'type': 'text', 'text': result.stdout}}]})
    if expect_error:
        assert result.returncode, f'The expected refusal succeeded: {words}'
        return {'code': result.returncode, 'error': value, 'stderr': result.stderr}
    if result.returncode:
        raise RuntimeError(f'{words}: {result.stdout}{result.stderr}')
    return value


def mcp_call(name, arguments):
    """Use the stdio server and identity supplied by the actual runner, not an in-process tool invocation."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    assert MCP_SERVER is not None
    environment = {one['name']: one['value'] for one in MCP_SERVER.get('env', [])}
    assert environment['METAFORM_SESSION'] == os.environ['METAFORM_SESSION']
    parameters = StdioServerParameters(command=MCP_SERVER['command'], args=MCP_SERVER.get('args', []),
        cwd=str(Path.cwd()), env={**os.environ, **environment})
    ident = uuid.uuid4().hex[:12]
    update({'sessionUpdate': 'tool_call', 'toolCallId': ident, 'title': name, 'kind': 'other',
            'status': 'in_progress', 'rawInput': arguments})

    async def invoke():
        async with stdio_client(parameters) as (read, write), ClientSession(read, write) as client:
            await client.initialize()
            result = await client.call_tool(name, arguments)
            needed = result.structured_content
            if needed is None:
                try:
                    needed = json.loads('\n'.join(one.text for one in result.content if one.type == 'text'))
                except ValueError:
                    needed = None
            if result.is_error and isinstance(needed, dict) and needed.get('error') == 'instructions_required':
                instruction = needed['read_tool']
                guide = await client.call_tool(instruction['tool'], instruction['arguments'])
                if guide.is_error:
                    return guide
                result = await client.call_tool(name, arguments)
            return result

    result = asyncio.run(invoke())
    value = result.structured_content
    if value is None:
        text = '\n'.join(one.text for one in result.content if one.type == 'text')
        try:
            value = json.loads(text)
        except ValueError:
            value = text
    log(mcp_tool={'name': name, 'arguments': arguments, 'result': value, 'is_error': result.is_error,
                  'runner_identity': environment['METAFORM_SESSION'],
                  'server_command': parameters.command, 'server_args': parameters.args})
    update({'sessionUpdate': 'tool_call_update', 'toolCallId': ident,
            'status': 'failed' if result.is_error else 'completed', 'rawOutput': value})
    if result.is_error:
        raise RuntimeError(f'{name}: {value}')
    return value


def progress(**changes):
    held = json.loads(PROGRESS.read_text()) if PROGRESS.exists() else {'stage': 0}
    if changes:
        held.update(changes)
        temporary = PROGRESS.with_suffix('.new')
        temporary.write_text(json.dumps(held))
        os.replace(temporary, PROGRESS)
    return held


def check(state, summary, **nouns):
    candidate = current_candidate()
    return cli('orchestration', 'check-in', state=state, summary=summary, candidate=candidate,
               evidence=[{'candidate': candidate, 'observation': summary}], **nouns)


def current_candidate():
    path = Path('candidate.txt')
    return {**CANDIDATE, **({'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} if path.exists() else {})}


def suspend():
    log(awaiting_suspension=True)
    if not CANCELLED.wait(50):
        raise RuntimeError('The recorded suspension did not cancel its actual adapter turn.')


def original_gc(assignment, stage):
    if stage == 0:
        progress(stage=1)
        check('running', 'GC_OWNERSHIP: functional delivery claimed.', work_so_far='GC retained delivery plan.')
        cli('orchestration', 'call', role='implementer', task='Produce candidate.txt using a specialist contribution.',
            result='A candidate validated by its worker.', key='worker')
        suspend()
        return
    team = cli('orchestration', 'team')
    members = team['members']
    if SCENARIO == 'generated':
        requests = cli('orchestration', 'role_requests')
        requested = next((one for one in requests if one['gc_assignment_id'] == assignment['assignment_id']
                          and one['state'] == 'requested'), None)
        if requested:
            log(gc_commission=requested)
            cli('orchestration', 'commission', request=requested['request_id'], wait=True)
            suspend()
            return
    worker = next(one for one in members if one['parent_assignment_id'] == assignment['assignment_id']
                  and one['authored_role_uri'] == 'metaform://role/implementer')
    if worker['state'] not in ('returned', 'delivered'):
        check('waiting', 'GC follows the pending requested worker contribution.')
        suspend()
        return
    actual = Path('candidate.txt').read_text()
    log(gc_validation={'candidate': current_candidate(), 'actual': actual, 'worker_result': worker['result']})
    assert SPECIALIST_RESULT in actual
    if SCENARIO in ('adaptive', 'strict'):
        if stage == 1:
            progress(stage=2)
            cli('orchestration', 'assess', summary='GC_VALIDATED: candidate behavior and evidence for independent FQC.',
                candidate=current_candidate(), evidence=[{'observation': actual}], key='pre-delivery-assessment')
            check('waiting', 'Waiting for independent functional findings before integration.')
            suspend()
            return
        corrections = [one for one in team['related_corrections']
                       if one['parent_assignment_id'] == assignment['assignment_id']]
        if any(one['state'] not in ('returned', 'delivered') for one in corrections):
            check('waiting', 'Tracking the recorded functional correction to delivery.')
            suspend()
            return
        operative = Path('OPERATIVE.md').read_text()
        assert operative == (OPERATIVE if SCENARIO == 'adaptive' else 'Use the original restoration sequence.\n')
        if SCENARIO == 'adaptive':
            assert assignment['attempt'] == 2
            if CORRECTION not in actual:
                Path('candidate.txt').write_text(actual + CORRECTION)
                actual = Path('candidate.txt').read_text()
                log(correction_delivered={'work_id': WORK, 'actual': actual, 'candidate': current_candidate()})
            assert CORRECTION in actual
        log(gc_change_received={'operative': operative, 'pending_direction': assignment['pending_direction'],
                                'corrections': corrections})
    progress(stage=99)
    check('delivered', 'GC_VALIDATED: requested candidate delivered with specialist evidence.',
          key='gc-delivery')


def worker(stage):
    if stage == 0:
        progress(stage=1)
        check('running', 'WORKER_PROGRESS: contribution underway.', work_so_far='RETAINED_WORKER_DRAFT')
        if SCENARIO == 'stopped':
            log(stoppable_worker=True)
            gate('finish-stopped-worker')
            return
        mcp_call('orchestration_call', {
            'role': 'route_specialist' if SCENARIO == 'generated' else 'investigator',
            'task': 'Establish the route behavior needed by this worker.', 'key': 'specialist-first',
            'contribution': 'Verify functional return behavior.', 'context': {'worker_draft': 'RETAINED_WORKER_DRAFT'}})
        suspend()
        return
    members = cli('orchestration', 'team')['members']
    returned = [one for one in members if one['work_id'] != WORK and
                one['authored_role_uri'] in ('metaform://role/investigator', 'metaform://specialist/route_specialist')
                and one['state'] in ('returned', 'delivered')]
    assert returned and all(SPECIALIST_RESULT in str(one['result']) for one in returned)
    log(worker_received={'stage': stage, 'results': returned})
    if SCENARIO == 'generated' and stage == 1:
        progress(stage=2)
        cli('orchestration', 'call', role='route_specialist', task='Reuse the registered duty for a second check.',
            key='specialist-reuse')
        suspend()
        return
    Path('candidate.txt').write_text('\n'.join(str(one['result']) for one in returned) + '\n')
    progress(stage=99)
    check('returned', 'WORKER_INTEGRATED: ' + SPECIALIST_RESULT, key='worker-result')


def specialist():
    if SCENARIO == 'direct':
        Path('candidate.txt').write_text(SPECIALIST_RESULT)
    # This is actual context delivery through the functional entry, rather than a fixture reading receipt rows.
    memory = cli('memory', 'open_nodes', names=['route-grounding'], node=f'element:{os.environ["METAFORM_NODE"]}')
    log(specialist_grounding=memory)
    progress(stage=99)
    check('delivered' if SCENARIO == 'direct' else 'returned', SPECIALIST_RESULT, key='specialist-result')


def creator(assignment):
    assert 'metaform://specialists' in DUTY and '<metaprompt name="role_creation">' in DUTY
    assert 'orchestration_publish_role' in DUTY and '<system_prompt>' in DUTY
    # the commission is one line naming the request it publishes against, its role when the request names one, and
    # whether it asks only for the ticket's agent, model and thinking level
    commission = re.search(r'specialist for \S+?(?:, role ([\w.]+))?(, runtime only)?, request (\w+)\.$', assignment['task'])
    assert commission, assignment['task']
    brief = {'request_id': commission.group(3), 'role': commission.group(1), 'runtime_only': bool(commission.group(2))}
    request = next(one for one in cli('orchestration', 'role_requests')
                   if one['request_id'] == brief['request_id'])
    caller = next(one for one in cli('orchestration', 'team')['members']
                  if one['assignment_id'] == request['caller_assignment_id'])
    selected = cli('orchestration', 'runtime', work=caller['work_id'])
    if selected['state'] == 'needs_choice':
        # These fixture actors have fixed responsibilities. This is their deterministic
        # full-model reply, not a production classifier or a default for unknown work.
        task_type, agent, effort = {
            'gc': ('planning', 'claude', 'ultra'),
            'implementer': ('coding', 'codex', 'medium'),
            'investigator': ('lookup', 'codex', 'low'),
            'route_specialist': ('lookup', 'codex', 'low'),
            'functionality': ('analysis', 'claude', 'high'),
            'bmad.bmm.dev': ('lookup', 'codex', 'low'),
        }[caller['authored_role_uri'].removeprefix('metaform://role/').removeprefix('metaform://specialist/')]
        choices = selected['catalog']
        # A preference is usable only once this adapter advertised its controls. Direct-start
        # scenarios may have primed just the current harness, which can perform every fixture role.
        if not choices.get(agent, {}).get('models'):
            agent = next(name for name, offered in choices.items() if offered.get('models'))
        catalog = choices[agent]
        efforts = catalog.get('efforts') or []
        effort = effort if effort in efforts else next(iter(efforts), None)
        model = next((value for value, description in catalog['models'].items()
                      if ('Highest capability' in description) == (task_type in ('planning', 'analysis'))),
                     next(iter(catalog['models'])))
        selected = cli('orchestration', 'runtime', work=caller['work_id'], choice={
            'agent': agent, 'model': model, 'effort': effort, 'task_type': task_type, 'confidence': 1.0,
            'reason': 'The deterministic fixture actor chooses its declared scenario responsibility.'})
        assert selected['state'] == 'selected'
    log(runtime_choice={'target': caller['work_id'], 'selected': selected})
    if brief['runtime_only']:
        progress(stage=99)
        cli('orchestration', 'publish_role', request=request['request_id'], role=request['role'],
            match_reason='Runtime selection preserves the assigned scenario responsibility.')
        return
    duty = ('You are the Route Specialist. Independently establish route behavior for your immediate caller. '
            'Preserve its functional result across suspension and return candidate-specific evidence. '
            'Your delivery GC retains swarm ownership. Use the public module action bindings you receive.')
    progress(stage=99)
    cli('orchestration', 'publish_role', request=request['request_id'], role=request['role'] or 'route_specialist',
        purpose='Diagnose and verify routing behavior.', duty=duty, match_reason='Routing behavior needs domain expertise.')


def gc_requests_role(assignment, stage, text):
    if stage == 0:
        progress(stage=1)
        check('running', 'GC_SELF_REQUEST: delivery needs a new specialist contribution.',
              work_so_far='RETAINED_GC_SPECIALIST_PLAN')
        mcp_call('orchestration_call', {
            'role': 'route_specialist', 'task': 'Establish the route behavior needed by this GC.',
            'key': 'gc-specialist', 'contribution': 'Verify functional return behavior.',
            'context': {'gc_plan': 'RETAINED_GC_SPECIALIST_PLAN'}})
        request = next(one for one in cli('orchestration', 'role_requests')
                       if one['caller_assignment_id'] == assignment['assignment_id'])
        actual = cli('orchestration', 'inspect')
        log(gc_self_request={'request': request, 'assignment': actual, 'cancelled': CANCELLED.is_set()})
        assert request['state'] in ('commissioned', 'published'), 'Missing roles commission automatically.'
        suspend()
        return
    specialist = next(one for one in cli('orchestration', 'team')['members']
                      if one['authored_role_uri'] == 'metaform://specialist/route_specialist')
    if specialist['state'] not in ('returned', 'delivered'):
        check('waiting', 'GC follows the pending generated specialist contribution.',
              work_so_far='RETAINED_GC_SPECIALIST_PLAN')
        suspend()
        return
    # A checkpoint-only resume can arrive after the result has landed in the assignment.
    # The explicit team read above supplies it; the prompt must not need a duplicate copy.
    assert SPECIALIST_RESULT in str(specialist['result'])
    assert ' complete' in text or f'Resume ticket {assignment["work_id"]}' in text
    assert 'RETAINED_GC_SPECIALIST_PLAN' not in text
    assert 'RETAINED_GC_SPECIALIST_PLAN' in json.dumps(assignment)
    Path('candidate.txt').write_text(str(specialist['result']) + '\n')
    log(gc_self_received={'result': specialist['result'], 'assignment': assignment, 'text': text,
                          'candidate': current_candidate()})
    progress(stage=99)
    check('delivered', 'GC_VALIDATED: generated specialist returned to its commissioning GC.',
          key='gc-self-delivery')


def assessment(assignment):
    try:
        reviewed = json.loads(assignment['task'])
    except ValueError:  # the assessment's task is words now: what to assess and where to read its report
        reviewed = assignment['task']
    actual = Path('candidate.txt').read_text()
    assert SPECIALIST_RESULT in actual
    log(fqc_observation={'reviewed': reviewed, 'actual': actual,
                         'reviewed_assignment_id': assignment['reviewed_assignment_id'],
                         'team_id': assignment['team_id']})
    if SCENARIO in ('adaptive', 'strict') and not (STATE / 'adapted').exists():
        (STATE / 'adapted').write_text(WORK)
        specification = Path('OPERATIVE.md')
        cli('orchestration', 'change', content=OPERATIVE,
            reason='C(T) requires the caller to retain its functional result; restoring retained work first serves '
                   'that core across interruptions.', specification={'uri': 'file:OPERATIVE.md'},
            base=hashlib.sha256(specification.read_bytes()).hexdigest(),
            observed_limitation='The original sequence resumes before '
                   'restoring the retained work.', key='restoration-order')
        progress(stage=99)
        findings = [{'task': 'Correct the candidate to restore retained work before continuing.',
                     'title': 'Functional restoration correction'}] if SCENARIO == 'adaptive' else []
        check('returned', 'FQC_FINDING: restoration order affects functional continuity.',
              findings=findings, key='fqc-finding')
        return
    progress(stage=99)
    check('returned', 'FQC_ACCEPTED: independently observed candidate preserves requested behavior.',
          key='fqc-result')


def corrective_gc(assignment):
    before = Path('candidate.txt').read_text()
    assert SPECIALIST_RESULT in before
    Path('candidate.txt').write_text(before + CORRECTION)
    log(correction_delivered={'parent_assignment_id': assignment['parent_assignment_id'],
                              'actual': Path('candidate.txt').read_text(), 'candidate': current_candidate()})
    progress(stage=99)
    check('delivered', 'CORRECTIVE_GC_DELIVERED: restored retained work and verified the functional result.',
          key='corrective-delivery')


def installed_bmad(assignment, stage, text):
    if ROLE == 'gc':
        if stage == 0:
            progress(stage=1)
            log(bmad_discovery=cli('orchestration', 'bmad'))
            cli('orchestration', 'call', role='bmad.bmm.dev', task='CR: review timer controls',
                context={'interaction': 'Preserve the functional return after resumption.'}, key='installed-review')
            suspend()
            return
        child = next(one for one in cli('orchestration', 'team')['members']
                     if one['authored_role_uri'] == 'metaform://specialist/bmad.bmm.dev')
        assert child['state'] == 'returned' and 'BMAD_INSTALLED_REVIEW' in str(child['result'])
        Path('candidate.txt').write_text(str(child['result']) + '\n')
        log(bmad_caller_received={'result': child['result'], 'text': text})
        progress(stage=99)
        check('delivered', 'GC_VALIDATED: installed BMAD menu contribution reached its immediate caller.',
              key='bmad-delivery')
    elif ROLE == 'bmad.bmm.dev':
        source = Path('_bmad/bmm/agents/dev.md').read_text()
        assert source in DUTY and 'This assignment uses an installed BMAD specialty.' in DUTY
        assert 'CR: review timer controls' in assignment['task'] and 'fixture-installed-version' in DUTY
        assert hashlib.sha256(source.encode()).hexdigest() in DUTY
        log(bmad_installed_observation={'source': source, 'task': assignment['task'], 'text': text})
        progress(stage=99)
        check('returned', 'BMAD_INSTALLED_REVIEW: ' + SPECIALIST_RESULT, key='installed-review-result')
    else:
        assessment(assignment)


def compacted_gc(stage, text, assignment):
    if stage == 0:
        progress(stage=1)
        check('running', 'GC retains delivery through context compaction.', work_so_far='RETAINED_COMPACTION_PLAN')
        log(compaction_grounding=cli('memory', 'open_nodes', names=['route-grounding'],
                                    node=f'element:{os.environ["METAFORM_NODE"]}'))
        log(compaction_ready=True)
        gate('compact')
        update({'sessionUpdate': 'compaction_update', 'compactionId': 'swarm-compaction-1', 'status': 'in_progress'})
        update({'sessionUpdate': 'compaction_update', 'compactionId': 'swarm-compaction-1', 'status': 'completed'})
        log(compaction_completed=True)
        gate('compaction-release')
        return
    memory = cli('memory', 'open_nodes', names=['route-grounding'], node=f'element:{os.environ["METAFORM_NODE"]}')
    log(compaction_restored={'text': text, 'memory': memory, 'assignment': assignment})
    assert 'RETAINED_COMPACTION_PLAN' not in text and 'The adapter reported context compaction.' in text
    assert 'RETAINED_COMPACTION_PLAN' in json.dumps(assignment)
    assert memory['entities']
    Path('candidate.txt').write_text(SPECIALIST_RESULT + '\n')
    progress(stage=99)
    check('delivered', 'GC_VALIDATED: functional grounding and retained assignment survived compaction.',
          key='compacted-delivery')


def gate(name):
    """The test releases a specific actor transition; this is fixture control, never a runtime polling loop."""
    deadline = time.monotonic() + 90
    while not (STATE / name).exists() and not CANCELLED.wait(0.05):
        if time.monotonic() > deadline:
            raise RuntimeError(f'Test did not release {name}.')


def communications(assignment, stage, text):
    if ROLE == 'gc':
        if stage:
            log(gc_peer_turn=text)
            return
        progress(stage=1)
        cli('orchestration', 'delegate', role='implementer', task='Coordinate the worker-called specialist.',
            key='communicating-worker')
        log(gc_ready=True)
        gate('broadcast')
        if CANCELLED.is_set():
            return
        discovery = cli('dispatch', 'peers')
        sent = cli('dispatch', 'broadcast', text='GC_SWARM_BROADCAST: preserve the requested functional result.')
        log(gc_broadcast=sent, all_agent_discovery=discovery)
        gate('interrupt')
        if CANCELLED.is_set():
            return
        member = next(one for one in cli('orchestration', 'team')['members']
                      if one['authored_role_uri'] == 'metaform://role/investigator')
        sent = cli('dispatch', 'interrupt', id=member['work_id'], session=member['owner_session_id'],
                   direction='NEW_GC_DIRECTION: keep the retained specialist state and validate the restored result.')
        log(gc_owned_interruption=sent)
        gate('finish-gc')
    elif ROLE == 'implementer':
        if stage:
            log(worker_peer_turn=text)
            return
        progress(stage=1)
        cli('orchestration', 'delegate', role='investigator', task='Retain the specialist result while peers coordinate.',
            key='communicating-specialist')
        log(worker_ready=True)
        gate('peer-note')
        if CANCELLED.is_set():
            return
        member = next(one for one in cli('orchestration', 'team')['members']
                      if one['authored_role_uri'] == 'metaform://role/investigator')
        discovery = cli('dispatch', 'peers')
        refused = cli('dispatch', 'interrupt', id=member['work_id'], direction='An ordinary peer must not interrupt.',
                      expect_error=True)
        broadcast = cli('dispatch', 'broadcast', text='An ordinary worker must not broadcast.', expect_error=True)
        log(peer_request_ready=True, peer_interrupt_refused=refused, worker_broadcast_refused=broadcast,
            all_agent_discovery=discovery)
        note = cli('dispatch', 'note', to=member['owner_session_id'], wait=30,
                   text='PEER_NOTE: report the retained result.')
        log(peer_note_sent=note, peer_interrupt_refused=refused, worker_broadcast_refused=broadcast,
            all_agent_discovery=discovery)
        gate('worker-release')
    elif ROLE == 'investigator':
        if stage == 0:
            progress(stage=1)
            log(specialist_grounding=cli('memory', 'open_nodes', names=['route-grounding'],
                                        node=f'element:{os.environ["METAFORM_NODE"]}'))
            check('running', 'Specialist retains work while coordinating.', work_so_far='RETAINED_SPECIALIST_STATE')
            log(specialist_ready=True, all_agent_discovery=cli('dispatch', 'peers'))
            gate('specialist-release')
        elif stage == 1 and 'PEER_NOTE:' in text:
            assert (STATE / 'peer-note-id').exists()
            reply = cli('dispatch', 'note', reply=(STATE / 'peer-note-id').read_text(),
                        text='PEER_REPLY: the retained result is available.')
            progress(stage=2)
            log(specialist_reply=reply, peer_context=text)
            gate('finish-specialist')
        elif stage >= 2 and ('NEW_GC_DIRECTION:' in text or any(  # a direction retained across a crash is read
                'NEW_GC_DIRECTION' in str(one.get('body')) for one in assignment.get('pending_direction') or [])):
            assert 'RETAINED_SPECIALIST_STATE' not in text
            assert 'RETAINED_SPECIALIST_STATE' in json.dumps(assignment)
            log(interrupted_recipient={'assignment': assignment, 'text': text})
            check('running', 'Following NEW_GC_DIRECTION with retained specialist work.',
                  work_so_far='RETAINED_SPECIALIST_STATE')
            gate('finish-directed-specialist')
        else:
            log(specialist_peer_turn=text)
    else:
        raise RuntimeError(f'Unexpected communicating role {ROLE!r}.')


def read_duty():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    environment = {one['name']: one['value'] for one in MCP_SERVER.get('env', [])}
    parameters = StdioServerParameters(command=MCP_SERVER['command'], args=MCP_SERVER.get('args', []),
        cwd=str(Path.cwd()), env={**os.environ, **environment})

    async def read():
        async with stdio_client(parameters) as (incoming, outgoing), ClientSession(incoming, outgoing) as client:
            await client.initialize()
            return await client.read_resource(ROLE_URI)
    resource = asyncio.run(read())
    log(role_resource=resource.model_dump(mode='json'))
    return '\n'.join(getattr(one, 'text', '') for one in resource.contents)


def turn(ident, text):
    global DUTY
    try:
        log(recipient_context=text)
        checkpoint = re.search(r'Startup context checkpoint: ([0-9a-f]+)', text)
        if checkpoint:
            key = re.search(r'Retain this context key: ([0-9a-f]+)', text)
            if key:
                progress(context_key=key[1])
            retained = progress().get('context_key')
            cli('agents', 'confirm', checkpoint=checkpoint[1], **({'key': retained} if retained else {}))
        if f'Your assigned duty is {ROLE_URI}' in text:
            DUTY = f'{text}\n\n{read_duty()}'  # An explicit reread can omit components already supplied inline.
        capacity = cli('dispatch', 'agents')['slots']
        if ROLE == 'triage':
            # The Liaison observes actual recipient context. It neither replays fixture work nor edits the graph.
            log(pm_observation=text, capacity=capacity, all_agent_discovery=cli('dispatch', 'peers'))
            return
        assignment = cli('orchestration', 'inspect')
        log(assignment_context=assignment, capacity=capacity, runtime_config={'model': MODEL[0], 'effort': EFFORT[0]})
        held = progress()
        if ROLE in ('facilitator', 'role_creator'):
            if held['stage'] == 99:
                log(maintenance_turn=True)
            else:
                creator(assignment)
        elif SCENARIO == 'bmad':
            installed_bmad(assignment, held['stage'], text)
        elif SCENARIO == 'compaction' and ROLE == 'gc':
            compacted_gc(held['stage'], text, assignment)
        elif SCENARIO == 'communications':
            communications(assignment, held['stage'], text)
        elif held['stage'] == 99 or assignment['state'] in ('waiting', 'suspended', 'queued'):
            log(maintenance_turn=True)
        elif ROLE == 'gc':
            if SCENARIO == 'gc-generated':
                gc_requests_role(assignment, held['stage'], text)
            elif assignment['parent_assignment_id']:
                corrective_gc(assignment)
            else:
                original_gc(assignment, held['stage'])
        elif ROLE == 'implementer':
            worker(held['stage'])
        elif ROLE in ('investigator', 'route_specialist'):
            specialist()
        elif ROLE == 'functionality':
            assessment(assignment)
        else:
            raise RuntimeError(f'Unexpected authored role {ROLE!r}.')
        update({'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': f'{ROLE} turn complete.'}})
    except Exception as error:  # noqa: BLE001  fixture errors become visible assertions in the parent test
        log(fixture_error=f'{type(error).__name__}: {error}\n{traceback.format_exc()}')
        update({'sessionUpdate': 'agent_message_chunk', 'content': {'type': 'text', 'text': str(error)}})
    finally:
        send({'jsonrpc': '2.0', 'id': ident, 'result': {
            'stopReason': 'cancelled' if CANCELLED.is_set() else 'end_turn'}})


def terminated(signum, frame):
    log(terminated=signum)
    os._exit(0)


signal.signal(signal.SIGTERM, terminated)
log(boot=True)
for raw in sys.stdin.buffer:
    message = json.loads(raw)
    log(message=message)
    method, ident = message.get('method'), message.get('id')
    if method == 'initialize':
        send({'jsonrpc': '2.0', 'id': ident, 'result': {
            'protocolVersion': 1, 'agentCapabilities': {'loadSession': True},
            'agentInfo': {'name': 'fake-swarm-agent', 'version': '1'}, 'authMethods': []}})
    elif method == 'session/new':
        MCP_SERVER = next((one for one in message['params'].get('mcpServers', []) if one['name'] == 'metaform'), None)
        SESSION = 'swarm-' + uuid.uuid4().hex[:16]
        log(**{'session_created' if ROLE else 'catalog_primed': SESSION})
        send({'jsonrpc': '2.0', 'id': ident, 'result': {'sessionId': SESSION, 'configOptions': config_options()}})
    elif method == 'session/load':
        MCP_SERVER = next((one for one in message['params'].get('mcpServers', []) if one['name'] == 'metaform'), None)
        SESSION = message['params']['sessionId']
        log(session_loaded=SESSION)
        send({'jsonrpc': '2.0', 'id': ident, 'result': {'configOptions': config_options()}})
    elif method == 'session/set_config_option':
        params = message['params']
        option = next(one for one in config_options() if one['id'] == params['configId'])
        assert params['value'] in {one['value'] for one in option['options']}
        (MODEL if params['configId'] == 'model' else EFFORT)[0] = params['value']
        log(config_applied={'id': params['configId'], 'value': params['value']})
        send({'jsonrpc': '2.0', 'id': ident, 'result': {'configOptions': config_options()}})
    elif method == 'session/prompt':
        CANCELLED.clear()
        text = '\n'.join(block.get('text', '') for block in message['params']['prompt'])
        threading.Thread(target=turn, args=(ident, text), daemon=True).start()
    elif method == 'session/cancel':
        CANCELLED.set()
    elif ident is not None:
        send({'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32601, 'message': 'Method not found'}})
