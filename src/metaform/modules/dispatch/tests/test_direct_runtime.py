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


@pytest.mark.parametrize('continuation', [False, True])
@pytest.mark.parametrize('fail_before_accept', [False, True])
def test_assignment_region_rides_the_actual_turn_and_is_receipted_only_after_acceptance(
        store, project_folder, monkeypatch, continuation, fail_before_accept):
    from types import SimpleNamespace

    from metaform.data import Node, functional_context
    from metaform.module import prepare_agent_context
    from metaform.modules.dispatch import runner
    from tests.storekit import small_map

    layer, _, _ = small_map(store)
    for number in range(4):
        address = f'code.provider.input_{number}'
        store.add_element(layer.name, address, name=f'Input {number}')
        store.add_join(layer.name, 'code.timer.kitchen', address,
                       purpose=f'Regional purpose {number}', ef=f'Regional encounter {number}', ifd='receives')
    store.add_element(layer.name, 'code.timer.unrelated', name='Unrelated neighboring namespace')
    work = store.add_work(Node('element', 'code.timer.kitchen'), 'unbuilt', task='Build the assigned timer change.')
    graph = functional_context(store, work)

    async def exercise():
        called = context('dispatch', project_folder, project='proj')
        held = runner.Session(called, store, work, 'claude', [], prep=True,
                              resume='retained-thread' if continuation else None)
        held.runner = 'regional-recipient'
        held.session_id = 'regional-thread'
        held.episode_previous_work = 'previous-card' if continuation else ''
        requests, receipts = [], []
        accepted = runner.record_agent_context

        async def deliver(**request):
            text = request['prompt'][0].text
            requests.append(text)
            region = next((one for one in (held.inflight_context or {}).get('components', [])
                           if one['name'].startswith('map:functional_context:')), None)
            if region is not None:
                assert prepare_agent_context(project_folder, held.runner, [region], project='proj')['components'], \
                    'Rendering, queuing and transport entry must not acknowledge this region'
            if fail_before_accept and len(requests) == 1:
                raise OSError('Prompt transport rejected before acceptance')
            held.context_delivered()
            return SimpleNamespace(stop_reason='end_turn', usage=None)

        async def nothing(*args, **kwargs):
            return None

        def record(*args, **kwargs):
            receipts.extend(args[2])
            return accepted(*args, **kwargs)

        held.conn = SimpleNamespace(prompt=deliver)
        for name in ('changed', 'note', 'flush', 'save_state', 'spend', 'peer_marked'):
            monkeypatch.setattr(held, name, nothing)
        for name in ('hush', 'arm', 'intake_clock', 'trace', 'carried'):
            monkeypatch.setattr(held, name, lambda *args, **kwargs: None)
        monkeypatch.setattr(runner, 'provided', lambda *args: [])
        monkeypatch.setattr(runner, 'record_agent_context', record)
        # A human turn may already be waiting when assignment rendering finishes.
        first, second = 'My first exact direction.\nKeep its wording.', 'My second exact direction.'
        held.turn(first, first=True, typed=True, word={'id': 'first'})
        startup = held.episode_delta() if continuation else held.handed()
        if continuation:
            # Acceptance of an earlier turn cannot consume a region rendered for the upcoming assignment.
            pending = list(held.pending_episode_components)
            held.context_delivered()
            assert pending and held.pending_episode_components == pending
        held.queue_startup_context(startup)
        held.turn(second, first=True, typed=True, word={'id': 'second'})
        assert list(held.pending) == [first, second]
        assert not receipts
        held.prompts_ready = True
        held.start_pending()
        await asyncio.gather(*tuple(held.tasks))
        assert len(requests) == 2, 'Regional orientation must ride existing turns'
        assert first in requests[0] and second in requests[1]
        assert graph['markdown'] in requests[0]
        assert (graph['markdown'] in requests[1]) is fail_before_accept
        for number in range(4):
            assert f'Regional purpose {number}' in requests[0]
            assert f'Regional encounter {number}' in requests[0]
            assert f'code.provider.input_{number}' in requests[0]
        assert 'Functionality relying on this element' in requests[0]
        assert 'stakeholder.cook.home' in requests[0] and 'Counts down and rings.' in requests[0]
        assert 'IFD: receives' in requests[0] and 'IFD is recorded separately' in requests[0]
        assert 'Unrelated neighboring namespace' not in requests[0]
        [region] = [one for one in receipts if one['name'].startswith('map:functional_context:')]
        assert graph['markdown'] in region['text']
        assert not prepare_agent_context(project_folder, held.runner, [region], project='proj')['components']
        # Ordinary turns never render another graph. An unchanged related assignment also reuses its region.
        held.turn('Continue the current contribution.')
        await asyncio.gather(*tuple(held.tasks))
        assert len(requests) == 3 and graph['markdown'] not in requests[-1]
        assert requests[-1] == 'Continue the current contribution.'
        monkeypatch.setattr(held, 'episode_previous_work', work.id)
        repeated = held.episode_delta()
        assert graph['markdown'] not in repeated
        assert not held.pending_episode_components
        store.add_join(layer.name, 'code.timer.kitchen', 'code.alarm.audible',
                       purpose='A newly recorded regional requirement', ef='A new regional encounter', ifd='sends')
        changed = functional_context(store, work)
        held.queue_startup_context(held.episode_delta())
        await asyncio.gather(*tuple(held.tasks))
        assert len(requests) == 4 and changed['markdown'] in requests[-1]
        assert requests[-1].count('```mermaid') == 1
        assert work.task in requests[-1], 'The changed region travels with its actual assignment'
        assert len([one for one in receipts if one['name'].startswith('map:functional_context:')]) == 2

    asyncio.run(exercise())


@pytest.mark.parametrize('fail_before_accept', [False, True])
@pytest.mark.parametrize('assigned_role', [False, True])
def test_fresh_prompt_teaches_the_gateway_and_records_its_selected_source_only_after_acceptance(
        store, project_folder, monkeypatch, fail_before_accept, assigned_role):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from metaform import prompt_files
    from metaform.module import prepare_agent_context, resolve_agent_role
    from metaform.modules.dispatch import orchestration, runner

    name = 'prompt.mcp:connect_catalog'
    original = prompt_files.resolve(name)
    selected, _ = prompt_files.save_edit(name, f'{original["text"]}\nUse exact catalog command names.')
    expected = prompt_files.resolve(name)
    assert expected['actual_version_id'] == selected.version_id
    assert expected['source']['kind'] == 'selected_edit'
    rules_name = 'prompt.mcp:connect_rules'
    original_rules = prompt_files.resolve(rules_name)
    selected_rules, _ = prompt_files.save_edit(rules_name, f'{original_rules["text"]}\nSelected shared planning rules.')
    expected_rules = prompt_files.resolve(rules_name)
    snapshot = None
    wrapper = None
    if assigned_role:
        prompt_files.save_edit('prompt.orchestration:gc', 'Pinned duty for proj. Preserve this exact intent.')
        snapshot = resolve_agent_role(project_folder, 'gc', project='proj', bindings={'project': 'proj'})
        prompt_files.save_edit('prompt.orchestration:gc', 'A newer role revision belongs to later assignments.')
        assert snapshot['components'][-1]['text'] == 'Pinned duty for proj. Preserve this exact intent.'
        assert snapshot['components'][-1]['bindings']['project'] == 'proj'
        prompt_files.save_edit('prompt.dispatch:role_resource',
                               'Assigned pinned duty: <role/>. Use the supplied exact components.')
        wrapper = prompt_files.resolve('prompt.dispatch:role_resource', role=snapshot['uri'])
        assert wrapper['source']['kind'] == 'selected_edit'
        assert wrapper['bindings'] == {'role': snapshot['uri']}
        monkeypatch.setattr(orchestration, 'resume_context', lambda *args: {'role_snapshot': snapshot})
        monkeypatch.setattr(runner, 'resolve_agent_role', lambda *args, **kwargs: pytest.fail(
            'The existing assignment must use its pinned role, not a newer selected revision'))

    async def exercise():
        held = runner.Session(context('dispatch', project_folder, project='proj', nouns={'prep': True}),
                              store, None, 'codex', [], prep=True, work_id='gateway-onboarding')
        held.runner = 'gateway-context'
        held.session_id = 'native-thread'
        held.authored_role = snapshot['uri'] if snapshot else None
        outgoing, carried = [], []

        def due():
            return prepare_agent_context(project_folder, held.runner, [expected, expected_rules],
                                         project='proj')['components']

        async def deliver(**request):
            text = request['prompt'][0].text
            components = held.inflight_context['components']
            catalog = next(one for one in components if one['name'] == name)
            outgoing.append((text, catalog))
            assert due(), 'Rendering and preparing the first prompt must not acknowledge delivery'
            assert text.count(expected['text']) == 1
            assert text.count(expected_rules['text']) == 1
            assert next(one for one in components if one['name'] == rules_name) == expected_rules
            for duty in snapshot['components'] if snapshot else []:
                delivered = next(one for one in components if one['name'] == duty['name'])
                assert delivered == duty
                assert text.count(duty['text']) == 1
                assert prepare_agent_context(project_folder, held.runner, [duty], project='proj')['components']
            if snapshot:
                assert snapshot['uri'] in text
                assert 'A newer role revision' not in text
                assert next(one for one in components if one['name'] == wrapper['name']) == wrapper
                assert text.count(wrapper['text']) == 1
                assert not any(one['name'] == 'prompt.orchestration:role_resource' for one in components)
            if fail_before_accept and len(outgoing) == 1:
                raise OSError('Prompt transport failed before acceptance')
            held.context_delivered()
            return SimpleNamespace(stop_reason='end_turn', usage=None)

        held.conn = SimpleNamespace(prompt=deliver)
        for method in ('changed', 'note', 'flush', 'save_state', 'spend', 'peer_marked'):
            monkeypatch.setattr(held, method, AsyncMock())
        for method in ('hush', 'arm', 'intake_clock', 'trace'):
            monkeypatch.setattr(held, method, lambda *args, **kwargs: None)
        monkeypatch.setattr(runner, 'provided', lambda *args: [])
        for function in ('begin_agent_context_check', 'finish_agent_context_check'):
            monkeypatch.setattr(runner, function, lambda *args, **kwargs: pytest.fail(
                'Ordinary new work must not request or finish a marker diagnostic'))
        monkeypatch.setattr(held, 'carried', lambda versions: carried.extend(versions))
        prepared_text = held.guidance('Prepare this contribution.', [])
        assert expected_rules['text'] in prepared_text, 'Shared rules belong to the guidance preparation itself'
        assert len(due()) == 2, 'Preparation must not acknowledge either selected component'
        held.turn('Implement the requested contribution.')
        await asyncio.gather(*tuple(held.tasks))
        if fail_before_accept:
            assert due() and not carried
            held.turn('Retry the requested contribution.')
            await asyncio.gather(*tuple(held.tasks))
        assert not due()
        assert held.context_check is None
        for text, catalog in outgoing:
            assert 'Context diagnostic' not in text and 'agents_confirm' not in text
            assert 'metaform_catalog module=' in text and 'search=' in text
            assert 'tool=' in text and 'arguments={...}' in text
            for field in ('actual_version_id', 'selected_version_id', 'source', 'rendered_fingerprint'):
                assert catalog[field] == expected[field]
        catalog_versions = [one for one in carried if one.name == name]
        assert len(catalog_versions) == 1
        assert catalog_versions[0].version_id == selected.version_id
        [rules_receipt] = [one for one in carried if one.name == rules_name]
        assert rules_receipt.version_id == selected_rules.version_id
        assert rules_receipt.selected_version_id == expected_rules['selected_version_id']
        assert rules_receipt.rendered_fingerprint == expected_rules['rendered_fingerprint']
        assert rules_receipt.rendered_text == expected_rules['text'] and rules_receipt.source == expected_rules['source']
        repeated = held.guidance('Another contribution.', [])
        assert expected['text'] not in repeated
        assert expected_rules['text'] not in repeated
        for duty in snapshot['components'] if snapshot else []:
            assert duty['text'] not in repeated
            assert not prepare_agent_context(project_folder, held.runner, [duty], project='proj')['components']
            assert len([one for one in carried if one.name == duty['name']]) == 1
        if wrapper:
            assert wrapper['text'] not in repeated
            [receipt] = [one for one in carried if one.name == wrapper['name']]
            assert receipt.version_id == wrapper['actual_version_id']
            assert receipt.source == wrapper['source'] and receipt.bindings == wrapper['bindings']

    asyncio.run(exercise())


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
        for function in ('begin_agent_context_check', 'finish_agent_context_check'):
            monkeypatch.setattr(runner, function, lambda *args, **kwargs: pytest.fail(
                'Ordinary resumed work must not request or finish a marker diagnostic'))
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
        assert held.context_check is None
        assert all('Context diagnostic' not in text and 'agents_confirm' not in text for text in requests)
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
