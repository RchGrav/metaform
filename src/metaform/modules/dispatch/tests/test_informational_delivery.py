"""Informational records must cost zero model turns, including restart and busy queues."""
from __future__ import annotations

import asyncio
import json
import os
from types import SimpleNamespace

import pytest
from metaform.modules.dispatch.tests.test_orchestration_transport import sent

from metaform.data import Store
from metaform.module import context
from metaform.modules.dispatch.signals import add_line
from metaform.modules.dispatch.tests.test_dispatch import Dispatch

pytestmark = pytest.mark.kind('fixture')


@pytest.fixture
def dispatch(run, home, project_folder, tmp_path):
    made = Dispatch(run, home, project_folder, tmp_path)
    global orchestration, peering, runner
    from metaform.modules.dispatch import orchestration, peering, runner
    yield made
    made.close()


def recipient(dispatch, monkeypatch, role='worker', busy=True, work_id=None):
    ctx = context('dispatch', dispatch.folder, project='proj', nouns={'system': role == 'system'})
    store = Store('proj', module='dispatch')
    record = runner.ticket(store, work_id) if work_id else dispatch.ticket()
    session = runner.Session(ctx, store, record, 'codex', ['true'])
    session.session_id, session.spoken, session.turns = 's', True, int(busy)
    from metaform.modules.dispatch import origin
    with session.store.tables() as tx:
        if tx.get('agent_sessions', {'session_id': 's'}) is None:
            tx.insert('agent_sessions', {'session_id': 's', 'work_id': session.work_id, 'agent': 'codex',
                'state': 'running', 'pid': os.getpid(), 'runner': 'r', 'started': '2026-10-21T00:00:00Z',
                'seq': 1, 'origin': origin()})
    scheduled = []
    calls = {'prompt': 0, 'resume': 0, 'bytes': 0}

    async def prompt(**kwargs):
        calls['prompt'] += 1
        calls['bytes'] += sum(len(block.text.encode('utf-8')) for block in kwargs['prompt'])

    async def resume(**kwargs):
        calls['resume'] += 1

    session.conn = SimpleNamespace(prompt=prompt, resume_session=resume, load_session=resume, calls=calls)

    def spawn(coro):
        scheduled.append(coro.__name__)
        coro.close()

    monkeypatch.setattr(session, 'spawn', spawn)
    return session, scheduled


def envelope(session, ident='info', **extra):
    return {'id': ident, 'kind': 'peer', 'text': 'Historical details remain readable.',
            'from': {'session_id': 'sender', 'work_id': 'source', 'agent': 'codex'},
            'to': [{'session_id': session.session_id, 'work_id': session.work_id}], **extra}


def ownership(monkeypatch, session):
    target = {'assignment_id': 'parent', 'owner_session_id': session.session_id,
              'work_id': session.work_id, 'state': 'running', 'stop': None}
    source = {'assignment_id': 'child', 'owner_session_id': 'sender', 'work_id': 'source',
              'state': 'returned', 'stop': None, 'return_to': {'assignment_id': 'parent'},
              'gc_assignment_id': 'parent'}
    rows = {'parent': target, 'child': source}
    owner = SimpleNamespace(assignment=lambda ctx, assignment_id=None, session_id=None:
                            rows.get(assignment_id) if assignment_id else target)
    monkeypatch.setattr(orchestration, 'service', lambda ctx: owner)
    return target, source


@pytest.mark.parametrize('role', ['system', 'worker'])
@pytest.mark.parametrize('busy', [False, True])
@pytest.mark.parametrize('kind', ['peer', 'running', 'project_update', 'result', 'role_publication',
                                 'functional_assessment', 'functional_correction', 'plan_report', 'roundtable_result'])
def test_notifications_never_prompt_or_piggyback(dispatch, monkeypatch, role, busy, kind):
    session, scheduled = recipient(dispatch, monkeypatch, role, busy)
    line = envelope(session, kind=kind, state='completed')
    asyncio.run(session.peer_note({'line': line, 'deliver': True}))
    assert not session.pending and not session.inbox and 'prompted' not in scheduled
    assert session.conn.calls == {'prompt': 0, 'resume': 0, 'bytes': 0}
    session.turns = 1
    session.turn('Explain this function.', first=True, typed=True)
    assert sent(monkeypatch, session) == ['Explain this function.']
    assert session.acp['resumed'] is None
    with session.store.tables(write=False) as tx:
        kept = json.loads(tx.get('session_lines', {'session_id': 's', 'name': 'peer:info'})['text'])
    assert kept['session_states']['s'] == 'recorded'
    monkeypatch.setattr(peering, 'caller', lambda store: (None, {'work_id': session.work_id, 'session_id': 's'}))
    read = peering.notes(context('dispatch', dispatch.folder, project='proj', nouns={'note': 'info'}))
    assert read['notes'][0]['text'] == kept['text']


def test_history_is_readable_without_scanning_bodies_or_replaying(dispatch, monkeypatch):
    session, _ = recipient(dispatch, monkeypatch, 'system')
    with session.store.tables() as tx:
        for number in range(100):
            add_line(tx, 's', session.work_id, f'peer:old-{number}', 'peer', json.dumps(envelope(
                session, f'old-{number}', kind='question', ask=True, state='withdrawn')))
    orchestration.TRANSPORT.notify_user(session.ctx, {'kind': 'plan_report', 'text': 'Finished old plan.'}, 'old-plan')
    from metaform.data.tables import TableTx
    original = TableTx.rows
    reads = []

    def rows(tx, table, where=None, **kwargs):
        if table == 'session_lines':
            reads.append(where)
            assert where == {'session_id': 's', 'kind': 'peer_delivery'}
        return original(tx, table, where, **kwargs)

    monkeypatch.setattr(TableTx, 'rows', rows)
    asyncio.run(session.replay_peers())
    asyncio.run(session.updates_due())
    assert reads == [{'session_id': 's', 'kind': 'peer_delivery'}]
    assert orchestration.update_entries(session.ctx, ['old-plan']) == []
    assert not session.pending and not session.inbox
    with session.store.tables(write=False) as tx:
        assert 'Historical details' in tx.get('session_lines', {'session_id': 's', 'name': 'peer:old-0'})['text']


def test_only_owning_active_assignment_receives_result_once(dispatch, monkeypatch):
    session, _ = recipient(dispatch, monkeypatch)
    target, _source = ownership(monkeypatch, session)
    line = envelope(session, 'result', kind='result', state='returned', sender_assignment_id='child')
    assert orchestration.actionable(session.ctx, line, session_id=session.session_id)
    reply = asyncio.run(session.peer_note({'line': line, 'deliver': True}))
    assert reply.get('queued'), reply
    asyncio.run(session.peer_note({'line': line, 'deliver': True}))
    assert len(session.pending) == 1
    assert len(sent(monkeypatch, session)) == 1
    # Simulate the persisted receipt written at transport handoff.
    from metaform.modules.dispatch.signals import mark_peer
    with session.store.tables() as tx:
        mark_peer(tx, 's', 'result', session.work_id, 'delivered', 's')
    session.queued_peer_ids.clear()
    asyncio.run(session.replay_peers())
    assert not session.pending
    target['assignment_id'] = 'unrelated'
    asyncio.run(session.peer_note({'line': {**line, 'id': 'unrelated'}, 'deliver': True}))
    assert not session.pending
    target['assignment_id'], target['stop'] = 'parent', {'by': 'user'}
    asyncio.run(session.peer_note({'line': {**line, 'id': 'stopped'}, 'deliver': True}))
    assert not session.pending


@pytest.mark.parametrize('invalid', ['withdrawn', 'resolved', 'superseded', 'stopped', 'owner_changed'])
def test_queued_requests_are_revalidated_before_model_call(dispatch, monkeypatch, invalid):
    session, _ = recipient(dispatch, monkeypatch)
    _, source = ownership(monkeypatch, session)
    source['state'] = 'running'
    line = envelope(session, 'question', kind='question', ask=True, sender_assignment_id='child')
    asyncio.run(session.peer_note({'line': line, 'deliver': True}))
    assert session.pending
    if invalid == 'owner_changed':
        source['owner_session_id'] = 'replacement'
    else:
        source['state'] = invalid
    session.turn('Current user request.', first=True, typed=True)
    assert sent(monkeypatch, session) == ['Current user request.']


def test_current_question_and_blocker_survive(dispatch, monkeypatch):
    session, _ = recipient(dispatch, monkeypatch)
    _, source = ownership(monkeypatch, session)
    source['state'] = 'running'
    question = envelope(session, 'question', kind='question', ask=True, sender_assignment_id='child')
    asyncio.run(session.peer_note({'line': question, 'deliver': True}))
    with monkeypatch.context() as draining:
        assert len(sent(draining, session)) == 1
    source['state'] = 'blocked'
    blocker = envelope(session, 'blocker', kind='blocked', sender_assignment_id='child')
    asyncio.run(session.peer_note({'line': blocker, 'deliver': True}))
    assert len(sent(monkeypatch, session)) == 1


def test_user_direction_survives_and_restarts_once(dispatch, monkeypatch):
    session, _ = recipient(dispatch, monkeypatch)
    line = envelope(session, 'user', kind='user_direction', text='Stop that work.')
    asyncio.run(session.peer_note({'line': line, 'deliver': True}))
    restarted, _ = recipient(dispatch, monkeypatch)
    asyncio.run(restarted.replay_peers())
    assert sent(monkeypatch, restarted) == ['Stop that work.']


def test_project_updates_never_contact_model_transport(dispatch, monkeypatch):
    session, _ = recipient(dispatch, monkeypatch, 'system')
    def forbidden(*args, **kwargs):
        pytest.fail('UI notifications must not look up or contact model sessions.')
    monkeypatch.setattr(orchestration.TRANSPORT, 'send', forbidden)
    from metaform.modules import dispatch as package
    monkeypatch.setattr(package, 'system_sessions', forbidden)
    for kind in ('result', 'plan_report', 'roundtable_result', 'progress'):
        reply = orchestration.TRANSPORT.notify_user(session.ctx, {'kind': kind, 'text': kind}, kind)
        assert reply['pm'] == []
    assert not session.pending


@pytest.mark.parametrize('state', ['withdrawn', 'resolved', 'superseded'])
def test_recorded_request_withdrawal_prevents_restart_delivery(dispatch, monkeypatch, state):
    session, _ = recipient(dispatch, monkeypatch)
    _, source = ownership(monkeypatch, session)
    source['state'] = 'running'
    line = envelope(session, 'withdrawn', kind='question', ask=True, sender_assignment_id='child')
    asyncio.run(session.peer_note({'line': line, 'deliver': True}))
    with session.store.tables() as tx:
        tx.update('session_lines', {'session_id': 's', 'name': 'peer:withdrawn'},
                  {'text': json.dumps({**line, 'state': state})})
    restarted, scheduled = recipient(dispatch, monkeypatch)
    asyncio.run(restarted.replay_peers())
    assert not restarted.pending and 'prompted' not in scheduled
    assert sent(monkeypatch, restarted) == []


def test_pending_informational_transition_never_probes_or_resumes_session(dispatch, monkeypatch):
    session, _ = recipient(dispatch, monkeypatch)

    def forbidden(*args, **kwargs):
        pytest.fail('Informational transitions must not look up, prompt or resume a recipient.')

    monkeypatch.setattr(orchestration, '_row', forbidden)
    answer = orchestration.TRANSPORT.send(session.ctx, {'assignment_id': 'parent'},
                                         {'kind': 'peer', 'id': 'historical', 'text': 'Old informational note.'})
    assert answer == {'state': 'completed', 'accepted': True, 'record_only': True}
    assert session.conn.calls == {'prompt': 0, 'resume': 0, 'bytes': 0}


@pytest.mark.parametrize('kind', ['result', 'question'])
@pytest.mark.parametrize('reject_first', [False, True])
def test_accepted_delivery_receipts_survive_duplicate_entries_and_restart(dispatch, monkeypatch, kind, reject_first):
    session, _ = recipient(dispatch, monkeypatch)
    _, source = ownership(monkeypatch, session)
    source['state'] = 'returned' if kind == 'result' else 'running'
    line = envelope(session, 'once', kind=kind, ask=kind == 'question', sender_assignment_id='child')
    calls = {'prompt': 0, 'resume': 0, 'bytes': 0}
    tasks = []

    def state(note_id):
        with session.store.tables(write=False) as tx:
            row = tx.get('session_lines', {'session_id': 's', 'name': f'peer:{note_id}'})
        return json.loads(row['text']).get('session_states', {}).get('s')

    async def nothing(*args, **kwargs):
        return None

    async def resume(**kwargs):
        calls['resume'] += 1

    def configure():
        session.prep = session.link_asked = session.context_checked = True
        for name in ('changed', 'note', 'flush', 'save_state', 'spend'):
            monkeypatch.setattr(session, name, nothing)
        for name in ('hush', 'arm', 'trace'):
            monkeypatch.setattr(session, name, lambda *args, **kwargs: None)
        monkeypatch.setattr(session, 'spawn', lambda coro: tasks.append(asyncio.create_task(coro)))
        session.conn = SimpleNamespace(prompt=accepted, resume_session=resume, load_session=resume)

    async def accepted(**kwargs):
        assert state('once') not in ('delivered', 'read')
        calls['prompt'] += 1
        if reject_first and calls['prompt'] == 1:
            raise RuntimeError('Fake transport rejected bytes before acceptance.')
        calls['bytes'] += sum(len(block.text.encode('utf-8')) for block in kwargs['prompt'])
        session.context_delivered()
        return SimpleNamespace(stop_reason='end_turn', usage=None)

    async def scenario():
        nonlocal session
        await session.peer_note({'line': line, 'deliver': True})
        await session.peer_note({'line': line, 'deliver': True})
        await session.peer_note({'line': {**line, 'id': 'alias'}, 'deliver': True})
        assert len(session.pending) == 1
        assert state('once') not in ('delivered', 'read')
        assert state('alias') == 'recorded'
        assert calls == {'prompt': 0, 'resume': 0, 'bytes': 0}
        configure()
        await session.prompted()
        await asyncio.gather(*tasks)
        if reject_first:
            assert state('once') not in ('delivered', 'read')
            assert calls == {'prompt': 1, 'resume': 0, 'bytes': 0}
            session, _ = recipient(dispatch, monkeypatch, work_id=session.work_id)
            await session.replay_peers()
            assert len(session.pending) == 1
            configure()
            await session.prompted()
            await asyncio.gather(*tasks)
        assert state('once') == 'read'
        assert state('alias') == 'recorded'
        assert calls['prompt'] == 1 + int(reject_first) and calls['resume'] == 0 and calls['bytes'] > 0
        first_counts = calls.copy()
        await session.peer_note({'line': line, 'deliver': True})
        await session.replay_peers()
        assert not session.pending
        session.turns = 1
        await session.prompted()
        assert calls == first_counts
        restarted, _ = recipient(dispatch, monkeypatch, work_id=session.work_id)
        await restarted.replay_peers()
        await restarted.peer_note({'line': line, 'deliver': True})
        assert not restarted.pending
        print(f'{kind}, rejected first={reject_first}: {calls}')

    asyncio.run(scenario())
