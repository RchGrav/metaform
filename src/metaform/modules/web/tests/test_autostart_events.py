"""Autostart ignores unrelated events while still delivering them to pages."""
import queue
import threading
from types import SimpleNamespace

import pytest

from metaform.modules.dispatch.tests.test_dispatch import dispatch as dispatch  # noqa: PLC0414 fixture re-export
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
    # what the change concerns, when every write said it: only the kinds that can start work
    ({'tables': 'dispatch', 'kinds': ['line'], 'session_ids': ['s']}, False),
    ({'tables': ['dispatch.sessions', 'dispatch.spending'], 'kinds': ['spend']}, False),
    ({'tables': ['work'], 'kinds': ['ticket'], 'work_ids': ['w']}, True),
    ({'tables': ['work_steps'], 'kinds': ['ticket'], 'work_ids': ['w']}, False),
    ({'tables': 'dispatch', 'kinds': ['session'], 'session_ids': ['s']}, False),  # a runner's working or idle
    ({'tables': ['dispatch.sessions', 'work']}, True),  # a session's end releases its ticket, with no kinds
    ({'tables': ['map.glyphs'], 'kinds': []}, True),
    # a ticket's words and its steps start nothing (UX review round 1, runaway F3); what it waits on can
    ({'tables': ['work'], 'kinds': ['note'], 'work_ids': ['w']}, False),
    ({'tables': ['map.numbered', 'work'], 'kinds': ['note'], 'work_ids': ['w']}, False),
    ({'tables': ['work', 'work_steps'], 'kinds': ['step'], 'work_ids': ['w']}, False),
    ({'tables': ['map.after', 'work'], 'kinds': ['note'], 'work_ids': ['w']}, True),
    ({'tables': ['elements', 'joins'], 'kinds': []}, False),
])
def test_change_triggers_only_relevant_dispatch_checks(payload, starts, monkeypatch):
    server = object.__new__(module.Server)
    page = queue.SimpleQueue()
    server.listeners = {page}
    server.listening = threading.Lock()
    scheduled = []
    monkeypatch.setattr(module.home, 'project', lambda project: SimpleNamespace(project_id=project))
    monkeypatch.setattr(server, 'schedule_dispatch',
                        lambda project, starts=True, merges=True: scheduled.append(project) if starts else None)
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


@pytest.mark.req('QUAL-015')
def test_a_burst_of_note_edits_runs_no_agent_starter_pass_and_one_ticket_change_runs_one(dispatch, run,
                                                                                         monkeypatch):
    """UX review round 1, runaway F3: 100 note edits, as an agent writes them, with Autostart on, reach the pages and
    cause no pass of the agent starter; one ticket made ready then causes one."""
    from metaform import changes, events
    run('set', '--dispatch-autostart', cwd=dispatch.folder)
    fired = []
    monkeypatch.setattr(events, 'publish', lambda topic, payload, source: fired.append(payload) or [])
    changes.announce(dispatch.folder, 'cli')
    fired.clear()
    for number in range(100):
        dispatch.store.edit_work(dispatch.id, {'note': f'Note {number}.'})
        changes.announce(dispatch.folder, 'cli')
    server = object.__new__(module.Server)
    page = queue.SimpleQueue()
    server.listeners, server.listening = {page}, threading.Lock()
    server.dispatch_lock, server.dispatch_busy, server.dispatch_errors = threading.Lock(), False, {}
    server.dispatch_pending, server.merges_pending = set(), set()
    monkeypatch.setattr(module.threading, 'Thread', lambda target, **kwargs: SimpleNamespace(start=target))
    monkeypatch.setattr(module.chassis, 'refresh_modules', lambda: None)
    monkeypatch.setattr(module.events, 'announce', lambda *args: [])
    monkeypatch.setattr(server, 'schedule_merges', lambda project: None)
    passes = []
    monkeypatch.setattr(module, 'module_verb', lambda *args, **kwargs: passes.append(args) or {})
    burst = [dict(one) for one in fired if one.get('base_id')]
    assert len(burst) == 100
    assert sum(server.changed(payload) for payload in burst) == 100, 'every change still reaches the page'
    assert passes == []
    fired.clear()
    dispatch.store.add_work(dispatch.node, 'unbuilt', task='Ready to start')
    changes.announce(dispatch.folder, 'cli')
    for payload in [one for one in fired if one.get('base_id')]:
        server.changed(dict(payload))
    assert len(passes) == 1


def test_repeated_changes_queue_one_followup_without_concurrent_batches(monkeypatch):
    server = object.__new__(module.Server)
    server.dispatch_lock = threading.Lock()
    server.dispatch_pending = set()
    server.merges_pending = set()
    server.dispatch_busy = False
    server.dispatch_errors = {}
    threads = []
    monkeypatch.setattr(module.threading, 'Thread', lambda **kwargs: SimpleNamespace(start=lambda: threads.append(kwargs)))
    monkeypatch.setattr(module.chassis, 'refresh_modules', lambda: None)
    monkeypatch.setattr(module.home, 'project', lambda project: SimpleNamespace(path='/tmp', project_id=project))
    monkeypatch.setattr(server, 'schedule_merges', lambda project: None)
    monkeypatch.setattr(module.events, 'announce', lambda *args: [])
    calls = []

    def check(*args, **kwargs):
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


@pytest.mark.req('VIEW-044')
@pytest.mark.parametrize(('payload', 'starts', 'merges'), [
    ({'tables': 'dispatch', 'dispatch_tables': ['dispatch.lines'], 'kinds': ['line']}, False, False),
    ({'tables': 'dispatch', 'kinds': ['line'], 'session_ids': ['s']}, False, False),
    ({'tables': 'dispatch', 'kinds': ['merge'], 'work_ids': ['w']}, False, True),
    ({'tables': 'dispatch', 'dispatch_tables': ['dispatch.merges']}, False, True),
    ({'tables': 'dispatch'}, True, True),
    ({'tables': ['work'], 'kinds': ['ticket']}, True, False),
])
def test_a_change_runs_the_agent_starter_and_the_merges_read_only_when_it_can_need_them(payload, starts, merges,
                                                                                         monkeypatch):
    server = object.__new__(module.Server)
    server.listeners, server.listening = set(), threading.Lock()
    server.dispatch_lock, server.dispatch_busy, server.dispatch_errors = threading.Lock(), False, {}
    server.dispatch_pending, server.merges_pending = set(), set()
    monkeypatch.setattr(module.threading, 'Thread', lambda target, **kwargs: SimpleNamespace(start=target))
    monkeypatch.setattr(module.chassis, 'refresh_modules', lambda: None)
    monkeypatch.setattr(module.home, 'project', lambda project: SimpleNamespace(path='/tmp', project_id=project))
    monkeypatch.setattr(module.events, 'announce', lambda *args: [])
    ran = []
    monkeypatch.setattr(server, 'schedule_merges', lambda project: ran.append('merges'))
    monkeypatch.setattr(module, 'module_verb', lambda *args, **kwargs: ran.append('autostart') or {})
    server.changed({'project': 'proj', 'base_id': 'main', **payload})
    assert ran == ['merges'] * merges + ['autostart'] * starts


@pytest.mark.req('VIEW-042')
def test_the_agent_starters_own_writes_reach_the_pages_and_start_no_second_pass(monkeypatch):
    server = object.__new__(module.Server)
    page = queue.SimpleQueue()
    server.listeners, server.listening = {page}, threading.Lock()
    server.dispatch_lock, server.dispatch_busy, server.dispatch_errors = threading.Lock(), False, {}
    server.dispatch_pending, server.merges_pending = set(), set()
    monkeypatch.setattr(module.threading, 'Thread', lambda target, **kwargs: SimpleNamespace(start=target))
    monkeypatch.setattr(module.chassis, 'refresh_modules', lambda: None)
    monkeypatch.setattr(module.home, 'project', lambda project: SimpleNamespace(path='/tmp', project_id=project))
    monkeypatch.setattr(server, 'schedule_merges', lambda project: None)
    taken = {'project': 'proj', 'base_id': 'main', 'tables': ['work'], 'work_ids': ['w'], 'kinds': ['ticket']}
    monkeypatch.setattr(module.events, 'announce', lambda *args: [taken])  # the starter took a ticket
    passes = []
    monkeypatch.setattr(module, 'module_verb', lambda *args, **kwargs: passes.append(args) or {})
    server.schedule_dispatch('proj')
    assert len(passes) == 1, 'the starter ran again for its own write'
    assert page.get_nowait() == {'topic': 'map.changed', 'payload': taken}


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
    monkeypatch.setattr(server, 'schedule_dispatch',
                        lambda project, starts=True, merges=True: scheduled.put(project) if starts else None)
    with module.events.listen('web', server.changed):
        run('set', '--dispatch-autostart', cwd=folder)
        assert scheduled.get(timeout=5) == 'proj'
        run('unset', '--dispatch-autostart', cwd=folder)
        assert scheduled.get(timeout=5) == 'proj'
