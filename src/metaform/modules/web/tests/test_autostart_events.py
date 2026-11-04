"""Map changes reach pages and native observers without automatic work selection."""
import queue
import threading
from types import SimpleNamespace

import pytest

from metaform.modules.dispatch.tests.test_dispatch import dispatch as dispatch  # noqa: PLC0414 fixture re-export
from metaform.modules.web import server as module

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('VIEW-042')]


@pytest.mark.req('VIEW-044')
@pytest.mark.parametrize('state', ['ready', 'merging'])
def test_legacy_merge_receipts_never_publish_during_map_changes(state, monkeypatch):
    server = object.__new__(module.Server)
    page = queue.SimpleQueue()
    server.listeners, server.listening = {page}, threading.Lock()
    monkeypatch.setattr(module.home, 'project', lambda project: SimpleNamespace(path='/tmp', project_id=project))
    reads, publications = [], []

    def waiting(given):
        reads.append(given)
        return {'merges': [{'work_id': 'legacy', 'state': state, 'deadline': 0}]}

    monkeypatch.setattr(module, 'merges_waiting', waiting)
    monkeypatch.setattr(module, 'run_dispatch',
                        lambda *args: publications.append(args) or (True, {'merged': True}))
    change = {'project': 'proj', 'tables': 'dispatch', 'kinds': ['merge'], 'work_ids': ['legacy']}
    assert server.changed(change) == 1
    assert page.get_nowait() == {'topic': 'map.changed', 'payload': change}
    assert publications == [], 'a map event published a legacy candidate'
    assert reads == [], 'a map event read the explicit publication queue'


@pytest.mark.req('VIEW-044')
def test_explicit_merge_remains_available_through_dispatch_call(monkeypatch):
    publications = []
    monkeypatch.setattr(module, 'run_dispatch',
                        lambda *args: publications.append(args) or (True, {'merged': True}))
    assert module.Handler.dispatch_call(SimpleNamespace(), {'project': 'proj'}, 'merge', ['legacy']) == (
        True, {'merged': True})
    assert publications == [('proj', 'merge', ['legacy'], None)]


@pytest.mark.req('VIEW-005')
def test_where_an_agents_tool_calls_reached_goes_to_pages_as_its_own_event_and_leaves_the_change_as_it_was(monkeypatch):
    server = object.__new__(module.Server)
    page = queue.SimpleQueue()
    server.listeners = {page}
    server.listening = threading.Lock()
    monkeypatch.setattr(module.home, 'project', lambda project: SimpleNamespace(project_id=project))
    flow = [{'session_id': 's', 'agent': 'claude', 'work_id': 'w', 'from': {'kind': 'element', 'id': 'e1'},
             'to': [{'kind': 'element', 'id': 'e2'}], 'action': 'edit'}]
    change = {'project': 'proj', 'base_id': 'main', 'tables': 'dispatch', 'dispatch_tables': ['dispatch.lines']}
    server.changed({**change, 'flow': flow})
    assert page.get_nowait() == {'topic': 'map.flow', 'payload': {'project': 'proj', 'flows': flow}}
    assert page.get_nowait() == {'topic': 'map.changed', 'payload': change}


@pytest.mark.req('QUAL-015')
def test_real_note_bursts_and_ready_tickets_forward_events_and_observe_leases_without_dispatch(dispatch, monkeypatch):
    """Actual map writes retain event delivery and runner-death observation after scheduler retirement."""
    from metaform import changes, events

    fired = []
    monkeypatch.setattr(events, 'publish', lambda topic, payload, source: fired.append(payload) or [])
    changes.announce(dispatch.folder, 'cli')
    fired.clear()
    for number in range(100):
        dispatch.store.edit_work(dispatch.id, {'note': f'Note {number}.'} if number % 2 else {'reviewed': number % 4 == 0})
        changes.announce(dispatch.folder, 'cli')
    server = object.__new__(module.Server)
    page = queue.SimpleQueue()
    server.listeners, server.listening = {page}, threading.Lock()
    executions, arms = [], []
    monkeypatch.setattr(module, 'module_verb', lambda *args, **kwargs: executions.append(args) or {})
    server.deaths = SimpleNamespace(arm=lambda: arms.append(1))
    burst = [dict(one) for one in fired if one.get('base_id')]
    assert len(burst) == 100
    assert sum(server.changed(payload) for payload in burst) == 100
    assert [page.get_nowait() for _ in burst] == [{'topic': 'map.changed', 'payload': one} for one in burst]
    assert executions == [] and arms == []
    fired.clear()
    dispatch.store.add_work(dispatch.node, 'unbuilt', task='Ready for explicit assignment')
    changes.announce(dispatch.folder, 'cli')
    ready = [dict(one) for one in fired if one.get('base_id')]
    assert ready
    for payload in ready:
        server.changed(payload)
    assert [page.get_nowait() for _ in ready] == [{'topic': 'map.changed', 'payload': one} for one in ready]
    assert executions == [] and len(arms) == 1


@pytest.mark.req('BASE-053')
@pytest.mark.cli_process
def test_cli_default_agent_settings_reach_pages_without_an_open_stream(run, home, tmp_path):
    folder = tmp_path / 'project'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    run('enable', 'dispatch')
    server = object.__new__(module.Server)
    page = queue.SimpleQueue()
    server.listeners, server.listening = {page}, threading.Lock()
    with module.events.listen('web', server.changed):
        for agent in ('codex', 'claude'):
            run('set', f'--dispatch-agent={agent}', cwd=folder)
            changed = page.get(timeout=5)
            assert changed['topic'] == 'map.changed'
            assert changed['payload']['project'] == 'proj'
            assert 'dispatch.settings' in changed['payload']['tables']
