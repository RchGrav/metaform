"""Transport gates and event costs in addition to the full fake swarm scenarios."""
from __future__ import annotations

import inspect
import json
import os
import time
from pathlib import Path

import pytest

from metaform import prompt_files
from metaform.data import Store
from metaform.module import Stop, context
from metaform.modules.dispatch.tests.test_dispatch import UNCONCERNED, Dispatch, eventually


@pytest.fixture
def dispatch(run, home, project_folder, tmp_path):
    made = Dispatch(run, home, project_folder, tmp_path)
    yield made
    made.close()


@pytest.mark.kind('fixture')
def test_orchestration_and_memory_event_filters_read_nothing_for_unrelated_bursts(dispatch, monkeypatch):
    from metaform.modules.dispatch import orchestration, runner

    ctx = context('dispatch', dispatch.folder, project='proj')
    session = runner.Session(ctx, Store('proj', module='dispatch'), dispatch.ticket(), 'claude', ['true'])
    reads, scheduled, drained = [], [], []
    original = Store.tables

    def counted(self, *args, **kwargs):
        reads.append((self.module, args, kwargs))
        return original(self, *args, **kwargs)

    def scheduled_call(coro):
        scheduled.append(coro.__name__)
        coro.close()

    monkeypatch.setattr(Store, 'tables', counted)
    monkeypatch.setattr(session, 'spawn', scheduled_call)
    monkeypatch.setattr(orchestration, 'drain', lambda ctx, work_ids=None: drained.append(work_ids))
    burst = [*UNCONCERNED, {'project': 'proj', 'tables': ['orchestration.assignments'],
                           'kinds': ['orchestration.assignment'], 'work_ids': ['other']}]
    for payload in burst * 50:
        orchestration.changed(payload, ctx)
        session.changed_elsewhere(payload)
    assert reads == scheduled == drained == [], '350 unrelated events must cause zero reads or scheduled work'

    # A command that combines work and transitions may lose all aggregate concerns. The transition table remains
    # sufficient evidence for the dispatcher and relay recipient; an acknowledgement alone triggers no new drain.
    mixed = {'project': 'proj', 'tables': ['work', 'orchestration.assignments', 'orchestration.transitions']}
    orchestration.changed(mixed, ctx)
    session.changed_elsewhere(mixed)
    assert drained == [None] and 'orchestration_changes' in scheduled
    drained.clear()
    orchestration.changed({**mixed, 'kinds': ['orchestration.delivery']}, ctx)
    assert drained == []


MEMORY_CHANGED = {'project': 'proj', 'tables': ['memory.entities', 'memory.observations', 'memory.entry_revisions'],
                  'kinds': ['memory.changed', 'memory:code.store.memory']}


def sent(monkeypatch, session, guide=None):
    """Run the session's queued turns against a stub agent, returning the prompt texts it was sent."""
    import asyncio
    from types import SimpleNamespace

    prompts: list[str] = []

    async def prompt(session_id, prompt):
        prompts.append(prompt[0].text)
        session.context_delivered()  # what the connection's observer does once the prompt is sent
        return SimpleNamespace(stop_reason='end_turn', usage=None)

    async def nothing(*args, **kwargs):
        return None

    session.conn, session.session_id, session.prep, session.link_asked = SimpleNamespace(prompt=prompt), 's', True, True
    session.context_checked = True  # These delivery tests represent a recipient past its startup checkpoint.
    for name in ('changed', 'note', 'flush', 'save_state', 'spend', 'peer_marked'):
        monkeypatch.setattr(session, name, nothing)
    for name in ('hush', 'arm', 'intake_clock', 'trace'):
        monkeypatch.setattr(session, name, lambda *args, **kwargs: None)
    monkeypatch.setattr(session, 'guidance', guide or (lambda text, supplied: text))
    session.turns = 1
    asyncio.run(session.prompted())
    return prompts


def busy(dispatch):
    """A session in the middle of a long turn: what is queued now waits for the turn after it."""
    from metaform.modules.dispatch import runner

    ctx = context('dispatch', dispatch.folder, project='proj')
    session = runner.Session(ctx, Store('proj', module='dispatch'), dispatch.ticket(), 'claude', ['true'])
    session.turns = 1
    return session


@pytest.mark.kind('fixture')
@pytest.mark.parametrize('completion_kind', ['result', 'role_publication', 'functional_assessment',
                                            'functional_correction'])
@pytest.mark.parametrize('completion_state', ['returned', 'delivered', 'completed'])
def test_peer_wire_carries_only_message_and_keeps_details_available(
        dispatch, monkeypatch, completion_kind, completion_state):
    """A completion reaches its recipient once as a ticket reference. Routing survives without report copies."""
    import asyncio

    worker = busy(dispatch)
    worker.session_id, worker.spoken = 'recipient', True
    detail = 'FULL TICKET AND EVIDENCE ' * 1000
    line = {'id': 'brief-result', 'text': 'Fixed selection. Three interaction checks pass.',
            'kind': completion_kind, 'state': completion_state, 'candidate': detail, 'evidence': [detail],
            'from': {'session_id': 'sender', 'work_id': 'source', 'agent': 'claude',
                     'item': 'code.dispatcher.agent#7d'},
            'to': [{'session_id': 'recipient', 'work_id': worker.work_id}],
            'context_components': [{'name': 'irrelevant', 'text': detail}]}
    asyncio.run(worker.peer_note({'line': line, 'deliver': True}))
    assert list(worker.pending) == ['code.dispatcher.agent#7d complete']
    assert list(worker.prompt_contexts) == [[]]
    with worker.store.tables(write=False) as tx:
        kept = json.loads(tx.get('session_lines', {'session_id': 'recipient', 'name': 'peer:brief-result'})['text'])
    assert not {'evidence', 'candidate', 'context_components'} & kept.keys()
    assert kept['from']['session_id'] == 'sender'

    def no_context(*args):
        pytest.fail('A message must not rebuild the assignment or append its context.')

    assert sent(monkeypatch, worker, guide=no_context) == ['code.dispatcher.agent#7d complete']


@pytest.mark.kind('fixture')
def test_first_peer_turn_still_initializes_a_fresh_context(dispatch, monkeypatch):
    worker = busy(dispatch)
    worker.spoken = False
    worker.turn('A required result.', peers=[('result', 'sender')])
    initialized = []

    def guide(text, components):
        initialized.append(text)
        return f'Initial instructions.\n{text}'

    assert sent(monkeypatch, worker, guide=guide) == ['Initial instructions.\nA required result.']
    assert initialized == ['A required result.']


@pytest.mark.kind('fixture')
def test_startup_checkpoint_is_small_and_retained_key_is_not_repeated_on_resume(dispatch):
    import asyncio

    from metaform.module import agent_context_epoch, context
    from metaform.modules.agents.roles import confirm_context

    worker = busy(dispatch)
    worker.runner = 'retention-test'
    first = worker.context_checkpoint('Do the requested work.')
    check = dict(worker.context_check)
    assert check['marker'] in first and check['checkpoint'] in first
    worker.context_delivered()
    proof = context('agents', dispatch.folder, project='proj', session=worker.runner,
                    nouns={'checkpoint': check['checkpoint'], 'key': check['marker']})
    assert confirm_context(proof)['confirmed']
    asyncio.run(worker.context_check_finished())
    assert worker.context_checkpoint('Next message.') == 'Next message.'

    resumed = busy(dispatch)
    resumed.runner, resumed.resume = worker.runner, 'retained-session'
    again = resumed.context_checkpoint('Resume requested work.')
    assert check['marker'] not in again, 'A resume challenge cannot reveal the answer it tests.'
    assert resumed.context_check['checkpoint'] in again
    resumed.context_delivered()
    asyncio.run(resumed.context_check_finished())  # No acknowledgement: eligibility changes, nothing is queued.
    assert agent_context_epoch(dispatch.folder, worker.runner, project='proj') == 1
    assert not resumed.pending and not resumed.prompt_contexts


@pytest.mark.kind('fixture')
def test_rules_reach_an_agent_once_per_context_epoch(dispatch, monkeypatch):
    """The output rules head the first turn, are left out while the epoch holds them, and come again once after the
    agent's context is compacted."""
    import asyncio

    rules = prompt_files.module('mcp', 'connect_rules')
    worker = busy(dispatch)
    worker.runner = 'rules-test'
    worker.turn('First task.')
    worker.turn('Second task.')
    first, second = sent(monkeypatch, worker)
    assert first == f'{rules}\n\nFirst task.' and second == 'Second task.'

    worker.recompacted, worker.epoch_moved = True, asyncio.Event()  # as ACP's completed compaction_update sets them
    monkeypatch.setattr(worker, 'compaction_line', lambda: '')
    from metaform.modules.dispatch import runner
    forget = runner.forget_shown

    def slow_forget(session):  # the bus is late, as it can be: the turn must still wait for the new epoch
        time.sleep(0.5)
        return forget(session)

    monkeypatch.setattr(runner, 'forget_shown', slow_forget)
    queued = worker.prompted

    async def compaction_then_turns():
        worker.spawn(worker.compacted())  # the new epoch starts on the bus while the next turn is already waiting
        await queued()

    worker.turns = 1  # still in a turn, so these queue
    worker.turn('After compaction.')
    worker.turn('Later still.')
    monkeypatch.setattr(worker, 'prompted', compaction_then_turns)
    again, later = sent(monkeypatch, worker)
    assert again.count(rules) == 1 and again.endswith('After compaction.') and later == 'Later still.'


@pytest.mark.kind('fixture')
def test_compaction_does_not_rebuild_assignment_or_actions(dispatch, monkeypatch):
    worker = busy(dispatch)
    worker.spoken, worker.recompacted = True, True
    worker.turn('Continue the requested action.')

    def no_dump(*args):
        pytest.fail('Compaction permits contextual reads, never a bulk guidance dump.')

    [text] = sent(monkeypatch, worker, guide=no_dump)
    assert text.endswith('Continue the requested action.')


@pytest.mark.kind('fixture')
def test_the_system_agents_reports_wait_in_its_inbox_and_its_next_turn_carries_one_line(dispatch, monkeypatch, run):
    """code.dispatcher.agent#72: a burst of 20 GC results, reviews, board needs and memory changes starts no turn in
    the person's system agent and puts no body and no memory notice in its conversation; the person's next message
    carries one 'new in your inbox' line naming each by ticket and kind, the turn after it none; the inbox lists them
    all, one short line each, and gives one whole on request. A question still wakes it, as that one line alone, and a
    worker receives only the completion reference. Memory changes cause no read in any session."""
    import asyncio

    from metaform.modules.dispatch import board, origin, peering, runner

    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('agent_sessions', {'session_id': 'sys', 'work_id': dispatch.id, 'agent': 'claude', 'state': 'running',
                                     'pid': os.getpid(), 'runner': 'r-sys', 'started': '2026-10-19T00:00:00Z',
                                     'seq': 1, 'origin': origin()})
        tx.insert('session_lines', {'session_id': 'sys', 'name': 'state', 'work_id': dispatch.id, 'kind': 'state',
                                    'text': json.dumps({'about': 'system', 'role': 'system'}), 'seq': 1})
    ctx = context('dispatch', dispatch.folder, project='proj', nouns={'system': True})
    system = runner.Session(ctx, Store('proj', module='dispatch'), dispatch.ticket(), 'claude', ['true'])
    system.session_id, system.runner = 'sys', 'r-sys'
    started: list[str] = []

    def spawned(coro):
        started.append(coro.__name__)
        coro.close()
    monkeypatch.setattr(system, 'spawn', spawned)
    rest = ' '.join(['Evidence: pytest -n 0 ran 41 tests and every one passed on the working tree.'] * 30)

    def result(number, kind='project_update', **more):
        return {'id': f'gc-{number}', 'kind': kind, 'update': 'result', 'state': 'returned', 'epoch': 1000.0 + number,
                'at': f'2026-10-19T08:{number:02d}:00Z', 'text': f'The held cap counts only open tickets {number}. {rest}',
                'evidence': [rest], 'from': {'item': f'code.router.assignment#{number}', 'title': f'Held cap {number}',
                                             'agent': 'claude', 'session_id': f'gc-session-{number}',
                                             'work_id': f'gc-work-{number}'},
                'to': [{'work_id': dispatch.id, 'session_id': 'sys'}], **more}

    run('set', '--dispatch-autostart', cwd=dispatch.folder)  # board needs are raised only while Full Auto is on
    run_ctx = context('dispatch', dispatch.folder, project='proj')

    async def burst():
        for number in range(20):
            update = 'progress' if number % 2 else 'result'
            await system.peer_note({'line': result(number, update=update), 'deliver': True})
            system.changed_elsewhere({**MEMORY_CHANGED, 'session_ids': ['r-sys']})
        await system.board()
    for number in range(3):  # what the board needs, raised by the changes that made it
        board.raised(run_ctx, f'finished:{dispatch.id}-{number}', f'{number} was finished: {rest}',
                     work_id=dispatch.id, start=False)
    asyncio.run(burst())
    assert 'prompted' not in started and not system.pending, 'A burst must start no turn of the system agent.'
    assert len(system.inbox) == 23

    system.turns = 1  # the person writes; their message is the turn that goes anyway
    system.turn('What is new?', first=True, typed=True)
    system.turn('And now?', first=True, typed=True)
    prompts = sent(monkeypatch, system)
    head, line = prompts[0].removeprefix(prompt_files.module('mcp', 'connect_rules') + '\n\n').split('\n\n')
    assert head == 'What is new?' and '\n' not in line, prompts[0]
    assert line.startswith('23 new in your inbox: code.router.assignment#0 complete, Ticket 1 — '
                           'progress, ') and 'and 13 more' in line, line
    assert 'Evidence' not in line and 'held cap' not in line and 'memories' not in line and len(line) < 600, line
    assert prompts[1] == 'And now?', 'Nothing new since the line was carried: no line.'

    monkeypatch.setattr(peering, 'caller', lambda store: (None, peering.sessions(store, dispatch.id)[0]))
    listed = peering.notes(context('dispatch', dispatch.folder, project='proj', nouns={'limit': 30}))['notes']
    assert [one['note'] for one in listed if one['kind'] != 'board'] == [f'gc-{number}' for number in reversed(range(20))]
    assert sum(one['kind'] == 'board' for one in listed) == 3
    first = next(one for one in listed if one['note'] == 'gc-19')['summary']
    assert len(first) <= 300 and 'Evidence' not in first, first
    assert first == 'Ticket 19 — progress'
    whole = peering.notes(context('dispatch', dispatch.folder, project='proj', nouns={'note': 'gc-6'}))['notes']
    assert whole[0]['text'] == 'code.router.assignment#6 complete'
    assert 'evidence' not in whole[0], 'Completion reports remain on their tickets.'

    started.clear()
    system.spoken = True  # its turns went out, as the agent's ACP connection says
    asyncio.run(system.peer_note({'line': result(30, kind='question', ask=True), 'deliver': True}))
    assert 'prompted' in started and list(system.pending) == [''], 'A question starts a turn of its own.'
    [woken] = sent(monkeypatch, system)
    assert woken == '1 new in your inbox: Ticket 30 — question, note gc-30.', woken
    assert '\n' not in woken and 'Evidence' not in woken, woken

    worker = busy(dispatch)
    worker.session_id = 'w'
    asyncio.run(worker.peer_note({'line': result(40), 'deliver': True}))
    assert worker.pending[0] == 'code.router.assignment#40 complete'
    assert not worker.inbox


@pytest.mark.kind('fixture')
def test_a_burst_of_memory_changes_gives_no_session_a_turn_or_a_read(dispatch, monkeypatch):
    """Memory notices are never pushed (code.dispatcher.agent#72): a burst of memory changes naming a worker and the
    person's system agent among their recipients reads nothing and queues nothing in either; an agent hears of unread
    memory only when it reads its own node."""
    from metaform.modules.dispatch import runner

    reads = []
    original = Store.tables

    def counted(self, *args, **kwargs):
        reads.append(self.module)
        return original(self, *args, **kwargs)
    worker = busy(dispatch)
    worker.session_id, worker.runner = 'w', 'r-w'
    system = runner.Session(context('dispatch', dispatch.folder, project='proj', nouns={'system': True}),
                            Store('proj', module='dispatch'), dispatch.ticket(), 'claude', ['true'])
    system.session_id, system.runner = 'sys', 'r-sys'
    scheduled = []
    for one in (worker, system):
        monkeypatch.setattr(one, 'spawn', lambda coro: (scheduled.append(coro.__name__), coro.close()))
    monkeypatch.setattr(Store, 'tables', counted)
    for _ in range(100):
        for one in (worker, system):
            one.changed_elsewhere({**MEMORY_CHANGED, 'session_ids': ['r-w', 'r-sys']})
            one.changed_elsewhere({'project': 'proj', 'tables': ['memory.entry_revisions']})
    assert reads == scheduled == [] and not worker.pending and not system.pending and not system.inbox


@pytest.mark.kind('simulation')
def test_fork_creation_and_later_turns_use_configured_capacity(dispatch, run):
    run('set', '--dispatch-agents', '1', '--dispatch-machine-agents', '1', cwd=dispatch.folder)
    dispatch.start('hold', FAKE_ACP_FORK='1')
    eventually(lambda: dispatch.received('session/prompt'))
    refused = run('dispatch', 'fork', dispatch.id, '--json', '--', 'A side contribution.',
                  cwd=dispatch.folder, ok=False)
    assert refused.returncode != 0 and 'dispatch_machine_agents' in refused.stdout + refused.stderr
    assert not dispatch.received('session/fork'), 'Admission must happen before ACP creates the fork.'
    run('set', '--dispatch-agents', '2', '--dispatch-machine-agents', '2', cwd=dispatch.folder)
    forked = json.loads(run('dispatch', 'fork', dispatch.id, '--json', cwd=dispatch.folder).stdout)
    run('set', '--dispatch-machine-agents', '1', cwd=dispatch.folder)
    later = run('dispatch', 'fork', dispatch.id, f'fork={forked["fork"]}', '--json', '--', 'Continue the side task.',
                cwd=dispatch.folder, ok=False)
    assert later.returncode != 0 and 'dispatch_machine_agents' in later.stdout + later.stderr
    assert not any(one['params']['sessionId'] == forked['fork'] for one in dispatch.received('session/prompt'))
    dispatch.stop()


@pytest.mark.kind('fixture')
def test_peer_identity_distinguishes_shared_ticket_sessions_and_follows_the_same_restarted_owner(
        dispatch, monkeypatch):
    from metaform.modules.dispatch import peering

    ctx = context('dispatch', dispatch.folder, project='proj')
    first = {'work_id': 'editor-work', 'session_id': 'first', 'runner': 'runner-first',
             'assignment_id': None, 'files': [], 'agent': 'claude'}
    other = {**first, 'session_id': 'second', 'runner': 'runner-second'}
    monkeypatch.setenv('METAFORM_SESSION', 'runner-first')
    monkeypatch.setenv('METAFORM_WORK', 'editor-work')
    monkeypatch.setattr(peering, 'working', lambda *args: [first, other])
    assert [one['session_id'] for one in peering.peers(ctx)['peers'] if one.get('yours')] == ['first']

    resumed = {**other, 'session_id': 'new-acp-session', 'assignment_id': 'same-assignment'}
    unrelated = {**other, 'session_id': 'unrelated-owner', 'assignment_id': 'other-assignment'}
    question = {'id': 'question', 'from': {'work_id': 'editor-work', 'session_id': 'old-acp-session',
                                        'assignment_id': 'same-assignment'}}
    monkeypatch.setattr(peering, 'working', lambda *args: [first, resumed, unrelated])
    monkeypatch.setattr(peering, 'peer_lines', lambda *args: [question])
    ctx.nouns['reply'] = 'question'
    assert peering.chosen(ctx, dispatch.store, 'editor-work', 'first')[2] == [resumed]

    # Two registered editor sessions may share a work id: one reply must not satisfy both recipients.
    answers = [{'id': 'one', 'reply_to': 'question', 'from': {'work_id': 'editor-work', 'session_id': 'second'}}]
    monkeypatch.setattr(peering, 'peer_lines', lambda *args: answers)
    assert peering.replies(dispatch.store, 'editor-work', 'question', {'first'}) == []
    assert peering.replies(dispatch.store, 'editor-work', 'question', {'second'}) == answers


@pytest.mark.kind('fixture')
def test_a_review_finding_resumes_the_worker_with_its_reopened_ticket_its_own(dispatch, monkeypatch):
    """Ticket ca815c74, 2026-10-19: an FQC finding moved the done ticket back to To do, untaken, and the launch
    resumed the worker's session in place, whose runner then refused: no longer taken by that session."""
    import metaform.modules.dispatch as package
    from metaform.modules.dispatch import orchestration

    ctx = context('dispatch', dispatch.folder, project='proj')
    store = dispatch.store
    store.take_work(dispatch.id, by='claude worker-session')
    store.move_work(dispatch.id, 'done')
    store.move_work(dispatch.id, 'todo', kept=True)  # what the review finding's correction does
    spawned = []

    def resumed(store, work, agent, extra, name, **_):
        spawned.append((Store('proj').ticket(work).work.taken_by, extra))
        return {'pid': 1}

    monkeypatch.setattr(package, 'launches', list)
    monkeypatch.setattr(package, 'session_state', lambda store, session: {'capabilities': {'resume': True}})
    monkeypatch.setattr(package, 'resume_spawn', resumed)
    monkeypatch.setattr(orchestration, '_row', lambda ctx, held: {'session_id': 'worker-session', 'agent': 'claude'})
    held = {'work_id': dispatch.id, 'assignment_id': 'assignment'}
    assert orchestration.Transport().launch(ctx, held, 'transition')['state'] == 'queued'
    assert spawned and spawned[0][0] == 'claude worker-session', 'The runner must find the ticket its own.'
    assert 'resume=worker-session' in spawned[0][1]

    # A start the gate refuses gives the ticket back where it waited; a done ticket resumes nothing.
    store.move_work(dispatch.id, 'todo', kept=True)
    monkeypatch.setattr(package, 'resume_spawn', lambda *args, **kwargs: (_ for _ in ()).throw(Stop('full', 'next')))
    with pytest.raises(Stop):
        orchestration.Transport().launch(ctx, held, 'transition')
    assert not Store('proj').ticket(dispatch.id).work.taken
    store.take_work(dispatch.id, by='claude worker-session')
    store.move_work(dispatch.id, 'done')
    assert orchestration.Transport().launch(ctx, held, 'transition')['state'] == 'completed'


@pytest.mark.kind('fixture')
def test_a_delivery_the_person_started_launches_with_full_auto_off(dispatch, monkeypatch):
    """2026-10-20: the system agent claimed a ticket on the person's word, and the Role Creator it commissioned never
    launched: every orchestration launch was automatic, so Full Auto off refused it."""
    import metaform.modules.dispatch as package
    from metaform.modules.dispatch import orchestration

    ctx = context('dispatch', dispatch.folder, project='proj')
    asked = []
    monkeypatch.setattr(package, 'launches', list)
    monkeypatch.setattr(orchestration, '_row', lambda ctx, held: None)
    monkeypatch.setattr(package, 'admit', lambda *args, auto, **_: asked.append(auto))
    monkeypatch.setattr(package, 'start_runner', lambda *args, **_: {'pid': 1})
    for persons in (True, False):
        dispatch.store.move_work(dispatch.id, 'todo', kept=True)
        orchestration.Transport().launch(ctx, {'work_id': dispatch.id, 'assignment_id': 'a',
                                               'persons_start': persons}, 'transition')
    assert asked == [False, True], 'only a delivery nobody asked for waits on Full Auto'


@pytest.mark.skipif(not os.environ.get('METAFORM_IDLE_EVIDENCE'), reason='Explicit 60-second CPU evidence run.')
@pytest.mark.kind('simulation')
def test_idle_cpu_evidence(run, home, project_folder, tmp_path):
    """Run the same measurement on the exact base and candidate source; no queries during the idle interval."""
    options = {'orchestration': True} if 'orchestration' in inspect.signature(Dispatch).parameters else {}
    dispatch = Dispatch(run, home, project_folder, tmp_path, **options)
    if options:
        from metaform.modules.agents.roles import SERVICE as roles
        from metaform.modules.orchestration.state import SERVICE
        ctx = context('orchestration', project_folder, project='proj')
        roles.publish(ctx, 'timing_engineering', 'Timing systems and countdown alarms.',
                      'Establish timing behavior through reproducible observations.')
        SERVICE.ensure(ctx, dispatch.id, role='timing_engineering')
        dispatch.store.move_work(dispatch.id, 'todo', kept=True)
    dispatch.start('hold')
    try:
        eventually(lambda: dispatch.logged('grandchild'))
        eventually(lambda: dispatch.received('session/prompt'))
        assert dispatch.process is not None
        processes = {'runner': dispatch.process.pid, 'adapter': dispatch.logged('pid')[0]}
        ticks = os.sysconf('SC_CLK_TCK')

        def cpu(pid):
            fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
            return (int(fields[11]) + int(fields[12])) / ticks

        # The first turn is already in flight. Both processes are blocked on real I/O with retained work.
        before = {name: cpu(pid) for name, pid in processes.items()}
        began = time.monotonic()
        time.sleep(60)
        elapsed = time.monotonic() - began
        consumed = {name: cpu(pid) - before[name] for name, pid in processes.items()}
        import metaform

        evidence = {'label': os.environ.get('METAFORM_CANDIDATE_LABEL'), 'source': str(Path(metaform.__file__).parent),
                    'interval_seconds': elapsed, 'cpu_seconds': consumed,
                    'cpu_percent_of_one_core': {name: used / elapsed * 100 for name, used in consumed.items()},
                    'native_orchestration': bool(options)}
        path = Path(os.environ['METAFORM_IDLE_EVIDENCE'])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(evidence, indent=2) + '\n')
        print(json.dumps(evidence))
    finally:
        dispatch.stop()
        dispatch.close()


@pytest.mark.kind('fixture')
def test_transport_drops_assignment_copies_but_keeps_authenticated_routes(dispatch, monkeypatch):
    from metaform.modules import dispatch as module
    from metaform.modules.dispatch import orchestration

    ctx = context('dispatch', dispatch.folder, project='proj')
    held = {'assignment_id': 'recipient-assignment'}
    row = {'state': 'running', 'session_id': 'recipient', 'work_id': 'work', 'agent': 'claude'}
    delivered = []
    monkeypatch.setattr(orchestration, '_row', lambda *args: row)
    monkeypatch.setattr(module, 'tell', lambda target, command, **fields: delivered.append(fields['line']) or
                        {'noted': True})
    source = {'assignment_id': 'sender-assignment', 'session_id': 'sender', 'agent': 'codex'}
    envelope = {'message_id': 'message', 'text': 'code.dispatcher.agent#7d complete', 'from': source,
                'sender_assignment_id': 'sender-assignment', 'sender_session_id': 'sender',
                'return_to': {'session_id': 'lead'}, 'state': 'completed', 'kind': 'result',
                'assignment': {'role_snapshot': 'private role' * 1000},
                'context_components': [{'text': 'context' * 1000}], 'report': {'body': 'ticket report'}}
    assert orchestration.TRANSPORT.send(ctx, held, envelope)['accepted']
    [line] = delivered
    assert line['text'] == envelope['text'] and line['from'] == source
    assert line['sender_assignment_id'] == 'sender-assignment'
    assert line['return_to'] == {'session_id': 'lead'}
    assert line['to'][0]['assignment_id'] == 'recipient-assignment'
    assert not {'assignment', 'context_components', 'report'} & line.keys()
    assert len(json.dumps(line)) < 800


@pytest.mark.kind('fixture')
def test_completion_inbox_names_the_ticket_without_its_report():
    from metaform.modules.dispatch.orchestration import inbox_status

    assert inbox_status({'update': 'result', 'state': 'completed',
                         'from': {'item': 'code.dispatcher.agent#7d'},
                         'text': 'Private report'}) == 'code.dispatcher.agent#7d complete'

    assert inbox_status({'kind': 'role_publication', 'state': 'completed', 'work_id': 'opaque-id',
                         'body': 'code.dispatcher.agent#7d complete'}) == 'code.dispatcher.agent#7d complete'


@pytest.mark.kind('fixture')
def test_delivered_completion_notification_stores_only_ticket_reference(dispatch, monkeypatch):
    from metaform.modules import dispatch as module
    from metaform.modules.dispatch import orchestration

    monkeypatch.setattr(module, 'sessions', lambda *args, **kwargs: [])
    ctx = context('dispatch', dispatch.folder, project='proj')
    message = {'message_id': 'delivered-completion', 'kind': 'functional_correction', 'state': 'delivered',
               'work_id': 'opaque-id', 'from': {'item': 'code.dispatcher.agent#7d'},
               'body': 'Private report', 'report': {'body': 'Private report'},
               'assignment': {'role_snapshot': 'Private role'}}
    result = orchestration.TRANSPORT._notify_user(ctx, message, 'change')
    assert result['text'] == 'code.dispatcher.agent#7d complete'
    with Store('proj', module='dispatch').tables(write=False) as tx:
        rows = tx.rows('session_lines', {'session_id': orchestration.UPDATES}, limit=0).results
    stored = json.dumps(rows)
    assert 'Private report' not in stored and 'Private role' not in stored
    assert 'code.dispatcher.agent#7d complete' in stored
