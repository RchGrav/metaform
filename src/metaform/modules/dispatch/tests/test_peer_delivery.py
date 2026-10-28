"""Equal peers use real session stores and inbox queues without an adapter or service."""
from __future__ import annotations

import asyncio
import json
from copy import deepcopy

import pytest

from metaform import home, loader
from metaform.data import Store
from metaform.module import Stop, context
from metaform.modules.dispatch import peering, runner

pytestmark = pytest.mark.kind('fixture')


@pytest.fixture
def peers(project_folder, monkeypatch):
    home.set_module_state('dispatch', True)
    loader.reset()
    store = Store('proj', module='dispatch')
    ctx = context('dispatch', project_folder)
    made = {}
    for index, name in enumerate(('sender', 'recipient', 'unrelated'), start=1):
        work = f'task-{name}'
        session = runner.Session(ctx, store, None, 'codex', ['unused-test-adapter'], work_id=work)
        session.session_id = f'session-{name}'
        session.runner = f'runner-{name}'
        session.role = 'worker'
        session.spoken = True
        session.turns = 1  # a message must wait for the real turn boundary
        made[name] = session
        with store.tables() as tx:
            tx.insert('agent_sessions', {'session_id': session.session_id, 'work_id': work, 'agent': 'codex',
                      'runner': session.runner, 'state': 'running', 'started': '2026-10-24T10:00:00Z', 'seq': index})
    monkeypatch.setenv('METAFORM_WORK', made['sender'].work_id)
    monkeypatch.setenv('METAFORM_SESSION', made['sender'].runner)
    monkeypatch.setattr(peering, 'session_status', lambda store, row, **kwargs: {**row, 'activity': 'working'})

    async def quiet_lines(session):
        pass

    def no_prompt(session, coroutine):
        name = coroutine.__name__
        coroutine.close()
        assert name != 'prompted', 'This test must not start a model turn.'

    monkeypatch.setattr(runner.Session, 'lines_changed', quiet_lines)
    monkeypatch.setattr(runner.Session, 'spawn', no_prompt)
    # Sending publishes an informational change; exercise delivery without invoking unrelated subscribers.
    monkeypatch.setattr(type(ctx), 'publish', lambda *args, **kwargs: None)
    delivered = []

    def tell(row, op, **given):
        assert op == 'note'
        delivered.append((row['session_id'], deepcopy(given)))
        session = next(one for one in made.values() if one.session_id == row['session_id'])
        return asyncio.run(session.peer_note(given))

    monkeypatch.setattr(peering, 'tell', tell)
    return ctx, store, made, delivered


def test_plain_peer_invitation_reaches_exact_worker_with_provenance(peers, monkeypatch):
    ctx, store, made, delivered = peers
    ctx.nouns['to'] = made['recipient'].session_id
    text = 'Join me to inspect the failing request and discuss the fix.'
    sent = peering.send(ctx, store, text, 0)
    assert sent['sent'] is True
    assert [one['session_id'] for one in sent['to']] == [made['recipient'].session_id]
    assert [session_id for session_id, _ in delivered] == [made['sender'].session_id, made['recipient'].session_id]
    recipient = made['recipient']
    assert len(recipient.pending) == 1
    assert 'Join me to inspect the failing request' in recipient.pending[0]
    assert not made['unrelated'].pending
    with store.tables(write=False) as tx:
        sender_copy = json.loads(tx.get('session_lines', {
            'session_id': made['sender'].session_id, 'name': f'peer:{sent["note"]}'})['text'])
        recipient_copy = json.loads(tx.get('session_lines', {
            'session_id': recipient.session_id, 'name': f'peer:{sent["note"]}'})['text'])
        marker = tx.get('session_lines', {'session_id': recipient.session_id,
                                        'name': f'peer_delivery:{sent["note"]}'})
    assert sender_copy == recipient_copy
    assert sender_copy['text'] == text
    assert sender_copy['from']['session_id'] == made['sender'].session_id
    assert sender_copy['from']['runner'] == made['sender'].runner
    assert sender_copy['from']['work_id'] == made['sender'].work_id
    assert sender_copy['kind'] == 'peer'
    assert 'decision' not in sender_copy
    assert 'assignment_id' not in sender_copy['from']
    assert marker is not None
    assert recipient.queued_peer_ids == {sent['note']}
    duplicate = asyncio.run(recipient.peer_note(delivered[-1][1]))
    assert duplicate['reused'] is True
    assert len(recipient.pending) == 1


def test_unregistered_sender_cannot_forge_peer_provenance(peers, monkeypatch):
    ctx, store, made, delivered = peers
    ctx.nouns['to'] = made['recipient'].session_id
    monkeypatch.setenv('METAFORM_SESSION', 'unregistered-runner')
    with pytest.raises(Stop, match='Your session is not running here'):
        peering.send(ctx, store, 'Forged invitation.', 0)
    assert delivered == []
    assert not made['recipient'].pending


def test_explicit_session_target_does_not_redirect_to_another_worker(peers):
    ctx, store, made, delivered = peers
    with store.tables() as tx:
        tx.update('agent_sessions', {'session_id': made['recipient'].session_id}, {'state': 'ended'})
    ctx.nouns['to'] = made['recipient'].session_id
    with pytest.raises(Stop, match='No agent is at work'):
        peering.send(ctx, store, 'This invitation belongs to the named session.', 0)
    assert delivered == []
    assert not made['unrelated'].pending


def test_worker_reply_preserves_exact_sender_route_and_receipts(peers, monkeypatch):
    ctx, store, made, delivered = peers
    ctx.nouns['to'] = made['recipient'].session_id
    original = peering.send(ctx, store, 'Please join the investigation.', 0)
    monkeypatch.setenv('METAFORM_WORK', made['recipient'].work_id)
    monkeypatch.setenv('METAFORM_SESSION', made['recipient'].runner)
    ctx.nouns.clear()
    ctx.nouns['reply'] = original['note']
    reply = peering.send(ctx, store, 'I will inspect the request handling.', 0)
    assert [one['session_id'] for one in reply['to']] == [made['sender'].session_id]
    assert len(made['sender'].pending) == 1
    assert not made['unrelated'].pending
    with store.tables(write=False) as tx:
        received = json.loads(tx.get('session_lines', {
            'session_id': made['sender'].session_id, 'name': f'peer:{reply["note"]}'})['text'])
        source = json.loads(tx.get('session_lines', {
            'session_id': made['sender'].session_id, 'name': f'peer:{original["note"]}'})['text'])
    assert received['reply_to'] == original['note']
    assert received['from']['session_id'] == made['recipient'].session_id
    assert source['session_states'][made['recipient'].session_id] == 'replied'
    assert delivered[-1][0] == made['sender'].session_id
