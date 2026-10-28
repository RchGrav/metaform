"""Control remains available under load without making worker calls into user commands."""
from collections import deque
from types import SimpleNamespace

import pytest

from metaform.modules import dispatch
from metaform.modules.dispatch.runner import Session

pytestmark = pytest.mark.kind('fixture')


def test_human_messages_keep_fifo_ahead_of_background_work():
    queues = ('pending', 'prompt_versions', 'prompt_contexts', 'voiced', 'peered', 'typed')
    held = SimpleNamespace(**{name: deque() for name in queues}, sent=[], priority_count=0,
                           handing=False, ending=False, replaying=False, turns=1, queued_peer_ids=set())
    Session.turn(held, 'background one')
    Session.turn(held, 'human one', first=True)
    Session.turn(held, 'background two')
    Session.turn(held, 'human two', first=True)
    assert list(held.pending) == ['human one', 'human two', 'background one', 'background two']
    assert {len(getattr(held, name)) for name in queues} == {4}


def test_typed_turn_is_bare_once_the_conversation_has_its_duty():
    """The person's words go as typed, except as a new conversation's first turn, which carries the role; a failed
    send's leftover context is never recorded as delivered by a typed turn, and stays due for the next turn."""
    import asyncio

    queues = ('pending', 'prompt_versions', 'prompt_contexts', 'voiced', 'peered', 'typed')
    held = SimpleNamespace(**{name: deque() for name in queues}, sent=[], priority_count=0, handing=False,
                           ending=False, replaying=False, turns=1, prep=True, role='system', opening=True,
                           probe=True, resume=None, link_asked=True, recompacted=False, spoken=False,
                           inflight_context=None, inflight_versions=[], inflight_peers=[], attached=[],
                           active_turn=None, interrupted=False, session_id='s', acp={'tokens': None},
                           queued_peer_ids=set())
    sent: list[tuple[str, object]] = []

    def guidance(text, supplied):
        held.inflight_context = {'components': ['orchestration:role_resource']}
        return f'ROLE\n\n{text}'

    async def prompt(session_id, prompt):
        sent.append((prompt[0].text, held.inflight_context))
        Session.context_delivered(held)
        return SimpleNamespace(stop_reason='end_turn', usage=None)

    async def nothing(*args, **kwargs):
        return None

    held.guidance, held.conn = guidance, SimpleNamespace(prompt=prompt)
    held.changed = held.flush = held.note = held.save_state = held.peer_marked = held.spend = nothing
    held.arm = held.hush = held.trace = lambda *args, **kwargs: None
    held.context_delivered = lambda: Session.context_delivered(held)

    async def turns():
        held.lock, held.interrupt_lock, held.idle = asyncio.Lock(), asyncio.Lock(), asyncio.Event()
        for text, typed, stale in (('hello', True, False), ('again', True, True), ('note', False, False)):
            if stale:  # as a send that failed before its bytes went out leaves it
                held.inflight_context = {'components': ['stale']}
            held.turns = 1  # queued only: the turn is run here, not spawned
            Session.turn(held, text, first=typed, typed=typed)
            await Session.prompted(held)
    asyncio.run(turns())
    assert sent == [('ROLE\n\nhello', {'components': ['orchestration:role_resource']}), ('again', None),
                    ('ROLE\n\nnote', {'components': ['orchestration:role_resource']})]


def test_workers_share_global_capacity_but_helpers_do_not_take_worker_slots(home, store, monkeypatch):
    entries = [{'pid': 100, 'project': store.project_id, 'work_id': 'a', 'kind': 'worker'},
               {'pid': 101, 'project': 'elsewhere', 'work_id': 'b', 'kind': 'worker'},
               {'pid': 102, 'project': store.project_id, 'work_id': 'advisor', 'kind': 'summoned'},
               {'pid': 103, 'project': store.project_id, 'work_id': 'role', 'kind': 'helper'}]
    monkeypatch.setattr(dispatch, 'launches', lambda: entries)
    monkeypatch.setattr(dispatch, 'sessions', lambda *a, **kw: [])
    ctx = SimpleNamespace(setting=lambda key: {'dispatch_agents': 2, 'dispatch_machine_agents': 2}[key])
    counts = dispatch.slots(ctx, store)
    assert (counts['used'], counts['machine_used'], counts['free']) == (1, 2, 0)
    assert counts['room'] > 0 and counts['own_room'] > 0
    entries.pop(1)
    assert dispatch.slots(ctx, store)['free'] == 1


@pytest.mark.kind('simulation')
def test_live_triage_yields_active_work_and_preserves_human_message_order(run, home, project_folder, tmp_path):
    import json
    import time

    from metaform.modules.dispatch.tests.test_dispatch import Dispatch, eventually

    live = Dispatch(run, home, project_folder, tmp_path)
    gates = tmp_path / 'turn-gates'
    gates.mkdir()
    try:
        live.start('replace', 'system=true', FAKE_ACP_TURN_GATES=str(gates))
        eventually(lambda: live.received('session/prompt'))
        began = time.monotonic()
        result = json.loads(run('dispatch', 'message', live.id, '--json', '--', 'Human priority one',
                                cwd=live.folder).stdout)
        assert result['sent'] and time.monotonic() - began < 5
        eventually(lambda: live.received('session/cancel'))
        eventually(lambda: len(live.received('session/prompt')) >= 2)
        run('dispatch', 'message', live.id, '--', 'Human priority two', cwd=live.folder)
        prompts = eventually(lambda: live.received('session/prompt') if len(live.received('session/prompt')) >= 3 else None)
        bodies = [json.dumps(one['params']['prompt']) for one in prompts]
        assert 'Human priority one' in bodies[1] and 'Human priority two' in bodies[2]
        assert live.process.poll() is None
    finally:
        live.close()
