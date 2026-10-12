"""Autostart ignores unrelated events while still delivering them to pages."""
import queue
import threading
from types import SimpleNamespace

import pytest

from metaform.modules.web import server as module

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('VIEW-042')]


@pytest.mark.parametrize(('payload', 'starts'), [
    ({'tables': ['work']}, True),
    ({'tables': ['messages', 'map.question_work']}, True),
    ({'tables': ['map.glyphs', 'map.ticket_settings', 'map.eligible']}, True),
    ({'tables': ['dispatch.sessions']}, True),
    ({'tables': ['dispatch.questions']}, True),
    ({'tables': ['dispatch.settings']}, True),
    ({'tables': ['elements', 'joins', 'memory.entities']}, False),
    ({'tables': ['work_steps']}, False),
    ({'tables': ['dispatch.lines']}, False),
    ({'tables': 'dispatch', 'dispatch_tables': ['dispatch.lines']}, False),
    ({'tables': 'dispatch', 'dispatch_tables': ['dispatch.questions']}, True),
    ({'tables': 'dispatch'}, True),
    ({}, True),
])
def test_change_triggers_only_relevant_dispatch_checks(payload, starts, monkeypatch):
    server = object.__new__(module.Server)
    page = queue.SimpleQueue()
    server.listeners = {page}
    server.listening = threading.Lock()
    scheduled = []
    monkeypatch.setattr(module.home, 'project', lambda project: SimpleNamespace(project_id=project))
    monkeypatch.setattr(server, 'schedule_dispatch', scheduled.append)
    event = {'project': 'proj', 'base_id': 'main', **payload}
    assert server.changed(event) == 1
    assert scheduled == (['proj'] if starts else [])
    assert page.get_nowait() == {'topic': 'map.changed', 'payload': event}


@pytest.mark.req('VIEW-005')
def test_where_an_agents_tool_calls_reached_goes_to_pages_as_its_own_event_and_leaves_the_change_as_it_was(monkeypatch):
    server = object.__new__(module.Server)
    page = queue.SimpleQueue()
    server.listeners = {page}
    server.listening = threading.Lock()
    monkeypatch.setattr(module.home, 'project', lambda project: SimpleNamespace(project_id=project))
    monkeypatch.setattr(server, 'schedule_dispatch', lambda project: None)
    flow = [{'session_id': 's', 'agent': 'claude', 'work_id': 'w', 'from': {'kind': 'element', 'id': 'e1'},
             'to': [{'kind': 'element', 'id': 'e2'}], 'action': 'edit'}]
    change = {'project': 'proj', 'base_id': 'main', 'tables': 'dispatch', 'dispatch_tables': ['dispatch.lines']}
    server.changed({**change, 'flow': flow})
    assert page.get_nowait() == {'topic': 'map.flow', 'payload': {'project': 'proj', 'flows': flow}}
    assert page.get_nowait() == {'topic': 'map.changed', 'payload': change}


def test_repeated_changes_queue_one_followup_without_concurrent_batches(monkeypatch):
    server = object.__new__(module.Server)
    server.dispatch_lock = threading.Lock()
    server.dispatch_pending = set()
    server.dispatch_busy = False
    server.dispatch_errors = {}
    threads = []
    monkeypatch.setattr(module.threading, 'Thread', lambda **kwargs: SimpleNamespace(start=lambda: threads.append(kwargs)))
    monkeypatch.setattr(module.chassis, 'refresh_modules', lambda: None)
    monkeypatch.setattr(module.home, 'project', lambda project: SimpleNamespace(path='/tmp', project_id=project))
    monkeypatch.setattr(server, 'schedule_merges', lambda project: None)
    monkeypatch.setattr(module.events, 'announce', lambda *args: [])
    calls = []

    def check(*args):
        calls.append(args)
        if len(calls) == 1:
            for _ in range(50):
                server.schedule_dispatch('proj')
        return {}

    monkeypatch.setattr(module, 'module_verb', check)
    server.schedule_dispatch('proj')
    server.dispatch_waiting()
    assert len(threads) == 1
    assert len(calls) == 2
    assert not server.dispatch_busy and not server.dispatch_pending


@pytest.mark.req('BASE-053')
@pytest.mark.cli_process
def test_cli_setting_changes_reach_the_server_without_an_open_page(run, home, tmp_path, monkeypatch):
    folder = tmp_path / 'project'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    run('enable', 'dispatch')
    server = object.__new__(module.Server)
    server.listeners = set()
    server.listening = threading.Lock()
    scheduled = queue.Queue()
    monkeypatch.setattr(server, 'schedule_dispatch', scheduled.put)
    with module.events.listen('web', server.changed):
        run('set', '--dispatch-autostart', cwd=folder)
        assert scheduled.get(timeout=5) == 'proj'
        run('unset', '--dispatch-autostart', cwd=folder)
        assert scheduled.get(timeout=5) == 'proj'
