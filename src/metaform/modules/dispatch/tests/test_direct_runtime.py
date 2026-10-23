"""An actual ACP/MCP repair proceeds from a missing role through independent verification."""
import asyncio
import json
import sys
from pathlib import Path

import pytest

from metaform.data import Store
from metaform.module import context
from metaform.modules.dispatch.tests.test_dispatch import Dispatch, eventually
from metaform.modules.orchestration.state import SERVICE

pytestmark = pytest.mark.kind('simulation')


def test_resumed_startup_batches_returns_and_preserves_exact_human_priority(store, project_folder, monkeypatch):
    from metaform.modules.dispatch.runner import Session

    async def exercise():
        held = Session(context('dispatch', project_folder, project='proj'), store, None, 'claude', [],
                       system=True, work_id='conversation-priority', resume='retained-session')
        started = []

        async def capture():
            started.append(list(held.pending))

        monkeypatch.setattr(held, 'prompted', capture)
        held.turn('First child complete', peers=[('first-child', 'worker-one')])
        held.turn('Second child complete', peers=[('second-child', 'worker-two')])
        message = 'Keep these exact words.\nStart with my new direction.'
        held.turn(message, first=True, typed=True, word={'id': 'human-direction'})
        assert not started and held.turns == 0
        assert list(held.pending) == [message, 'First child complete\n\nSecond child complete']
        assert list(held.typed) == [True, False]
        assert list(held.peered) == [[], [('first-child', 'worker-one'), ('second-child', 'worker-two')]]
        held.prompts_ready = True
        held.start_pending()
        held.start_pending()
        await asyncio.gather(*held.tasks)
        assert started == [[message, 'First child complete\n\nSecond child complete']]

    asyncio.run(exercise())


@pytest.mark.parametrize('selection', ['named', 'unnamed', 'automatic'])
def test_missing_specialist_reads_uri_and_delivers_one_canonical_ticket(
        run, home, project_folder, tmp_path, monkeypatch, selection):
    live = Dispatch(run, home, project_folder, tmp_path, orchestration=True)
    fake = Path(__file__).with_name('fake_swarm_agent.py')
    for agent in ('claude', 'codex', 'antigravity'):
        run('set', f'--dispatch-{agent}', f'"{sys.executable}" "{fake}"', cwd=project_folder)
    run('set', '--dispatch-agents', '1', '--dispatch-machine-agents', '1', '--dispatch-autostart',
        '--dispatch-record-on-finish', 'off', '--orchestration-reviews', '1', cwd=project_folder)  # one assessment, waited for
    for name, value in live.env('ask', FAKE_SWARM_SCENARIO='direct', FAKE_SWARM_STATE=str(tmp_path / 'state')).items():
        if name.startswith('FAKE_'):
            monkeypatch.setenv(name, value)
    ctx = context('orchestration', project_folder, project='proj', nouns={
        'work': live.id, **({'role': 'route_specialist'} if selection == 'named' else {'create': True})})
    if selection == 'automatic':
        monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
        monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
        ctx.nouns = {}
        SERVICE.queue_routing(ctx, [live.id])
        assert SERVICE.route_pending(ctx)[0]['state'] == 'creating'
        assigned = SERVICE.assignment(ctx, work_id=live.id)
    else:
        assigned = SERVICE.claim(ctx)
    try:
        SERVICE.drain(ctx)
        def finished():
            errors = live.logged('fixture_error')
            assert not errors, errors
            with Store('proj', module='orchestration').tables(write=False) as tx:
                assignments = tx.rows('assignments', limit=0).results
            deliveries = [one for one in assignments if one['authored_role_uri'] != 'metaform://role/facilitator']
            return assignments if len(deliveries) == 2 and len(assignments) >= 3 and all(
                one['state'] in ('returned', 'delivered') for one in assignments) else None
        assignments = eventually(finished, limit=120)
        assert {one['authored_role_uri'] for one in assignments} == {
            'metaform://role/facilitator', 'metaform://role/route_specialist', 'metaform://role/functionality'}
        assert sum(one['authored_role_uri'] == 'metaform://role/route_specialist' for one in assignments) == 1
        assert sum(one['authored_role_uri'] == 'metaform://role/functionality' for one in assignments) == 1
        root = SERVICE.assignment(ctx, work_id=live.id)
        assert root['assignment_id'] == assigned['assignment_id']
        assert root['evidence'] and root['candidate']['sha256']
        assert live.store.ticket(live.id).work.done
        assert live.logged('role_resource') and 'metaform://role/route_specialist' in json.dumps(live.logged('role_resource'))
        assert live.logged('fqc_observation')
        assert 'SPECIALIST_RESULT' in (project_folder / 'candidate.txt').read_text()
    finally:
        run('dispatch', 'stop-all', cwd=project_folder, ok=False)
        live.close()


@pytest.mark.parametrize('fail_before_accept', [False, True])
@pytest.mark.parametrize('human_before_delta', [False, True])
def test_cross_card_delta_rides_the_first_actual_turn_without_reordering_human_messages(
        store, project_folder, monkeypatch, fail_before_accept, human_before_delta):
    import hashlib
    from types import SimpleNamespace

    from metaform import prompt_files
    from metaform.modules.dispatch import runner

    async def exercise():
        called = context('dispatch', project_folder, project='proj', nouns={'system': True, 'talk': 'thread:old'})
        held = runner.Session(called, store, None, 'claude', [], prep=True, system=True,
                              work_id='current-card', resume='retained-session')
        held.session_id = 'retained-session'
        held.context_checked = True
        delta = 'Current contribution: card B, workspace and source references.'
        first = 'Keep this exact text.\nMy first new direction.'
        second = 'My second direction keeps its original order.'
        requests = []
        receipts, carried = [], []
        source = {'kind': 'shipped', 'path': 'dispatch/resources/prompts.xml', 'shipped_identity': 'source-revision'}
        version = prompt_files.Sent('prompt.dispatch:episode_delta', 2, 'shipped', 'actual-version',
                                    selected_version_id='selected-version',
                                    rendered_fingerprint=hashlib.sha256(delta.encode()).hexdigest(),
                                    bindings={'work': 'current-card'}, problems=('selected-edit-fallback',),
                                    rendered_text=delta, source=source)
        fragment = prompt_files.Sent('prompt.dispatch:startup_fragment', 1, 'shipped', 'fragment-version',
                                     rendered_text='Current contribution: card B', source=source)

        async def deliver(session_id, prompt):
            requests.append(prompt[0].text)
            if fail_before_accept and len(requests) == 1:
                raise OSError('Transport failed before accepting the prompt')
            held.context_delivered()
            return SimpleNamespace(stop_reason='end_turn', usage=None)

        async def nothing(*args, **kwargs):
            return None

        held.conn = SimpleNamespace(prompt=deliver)
        for name in ('changed', 'note', 'flush', 'save_state', 'spend', 'peer_marked'):
            monkeypatch.setattr(held, name, nothing)
        for name in ('hush', 'arm', 'intake_clock', 'trace'):
            monkeypatch.setattr(held, name, lambda *args, **kwargs: None)
        monkeypatch.setattr(runner, 'provided', lambda *args: [])
        monkeypatch.setattr(runner, 'agent_context_epoch', lambda *args, **kwargs: 7)
        monkeypatch.setattr(runner, 'record_agent_context', lambda *args, **kwargs: receipts.append(
            {'request': len(requests), 'components': args[2], **kwargs}))
        monkeypatch.setattr(held, 'carried', lambda taken: carried.append(taken))
        monkeypatch.setattr(held, 'pending_peer', lambda note_id: {
            'id': note_id, 'kind': 'result', 'text': 'Original child evidence is ready.',
            'from': {'agent': 'worker', 'session_id': 'child'}})
        held.sent.append(fragment)
        if human_before_delta:
            held.turn(first, first=True, typed=True, word={'id': 'human-first'})
        held.sent.append(version)
        held.queue_startup_context(delta)
        assert {one.name for one in held.pending_episode_versions} == {version.name, fragment.name}
        assert all(not versions for versions in held.prompt_versions)
        held.turn('Original child evidence is ready.', peers=[('original-child', 'child')])
        if not human_before_delta:
            held.turn(first, first=True, typed=True, word={'id': 'human-first'})
        held.turn(second, first=True, typed=True, word={'id': 'human-second'})
        assert list(held.pending)[:2] == [first, second]
        assert list(held.worded)[:2] == [{'id': 'human-first'}, {'id': 'human-second'}]
        assert receipts == carried == [], 'Queuing and rendering establish no delivery'
        held.prompts_ready = True
        held.start_pending()
        await asyncio.gather(*held.tasks)
        assert len(requests) == 3, 'An empty startup placeholder must not add a model turn'
        assert requests[0] == f'{delta}\n\n{first}'
        assert requests[1] == (f'{delta}\n\n{second}' if fail_before_accept else second)
        assert 'Original child evidence is ready.' in requests[2] and delta not in requests[2]
        assert held.pending_episode_delta == ''
        assert held.pending_episode_versions == []
        assert len(receipts) == len(carried) == 1
        assert receipts[0]['request'] == (2 if fail_before_accept else 1)
        assert receipts[0]['epoch'] == 7 and receipts[0]['channel'] == 'acp_prompt'
        actual = next(one for one in receipts[0]['components'] if one['name'] == version.name)
        assert actual['text'] == delta
        assert actual['actual_version_id'] == 'actual-version' and actual['selected_version_id'] == 'selected-version'
        assert actual['rendered_fingerprint'] == version.rendered_fingerprint and actual['source'] == source
        assert actual['bindings'] == {'work': 'current-card'} and actual['problems'] == ['selected-edit-fallback']
        sent = next(one for one in carried[0] if one.name == version.name)
        assert sent == version

    asyncio.run(exercise())
