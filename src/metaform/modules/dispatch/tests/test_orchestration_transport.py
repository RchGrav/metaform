"""Transport gates and event costs in addition to the full fake swarm scenarios."""
from __future__ import annotations

import inspect
import json
import os
import time
from pathlib import Path

import pytest

from metaform.data import Store
from metaform.module import context
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


@pytest.mark.skipif(not os.environ.get('METAFORM_IDLE_EVIDENCE'), reason='Explicit 60-second CPU evidence run.')
@pytest.mark.kind('simulation')
def test_idle_cpu_evidence(run, home, project_folder, tmp_path):
    """Run the same measurement on the exact base and candidate source; no queries during the idle interval."""
    options = {'orchestration': True} if 'orchestration' in inspect.signature(Dispatch).parameters else {}
    dispatch = Dispatch(run, home, project_folder, tmp_path, **options)
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
