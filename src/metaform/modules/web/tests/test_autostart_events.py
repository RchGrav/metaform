"""Autostart ignores unrelated events while still delivering them to pages."""
import queue
import threading
from types import SimpleNamespace

import pytest

from metaform.modules.dispatch.tests.test_dispatch import dispatch as dispatch  # noqa: PLC0414 fixture re-export
from metaform.modules.web import server as module

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('VIEW-042')]


@pytest.mark.req('VIEW-044')
@pytest.mark.parametrize('state', ['ready', 'merging'])
def test_legacy_merge_receipts_never_publish_during_ordinary_reconciliation(state, monkeypatch):
    with module.Server('127.0.0.1', 0, 'test') as server:
        monkeypatch.setattr(module.threading, 'Thread', lambda target, **kwargs: SimpleNamespace(start=target))
        monkeypatch.setattr(module.chassis, 'refresh_modules', lambda: None)
        monkeypatch.setattr(module.home, 'project', lambda project: SimpleNamespace(path='/tmp', project_id=project))
        monkeypatch.setattr(module.events, 'announce', lambda *args: [])
        monkeypatch.setattr(server, 'watch_backgrounds', lambda *args: None)
        monkeypatch.setattr(server, 'watch_runners', lambda *args: None)
        monkeypatch.setattr(module, 'module_verb', lambda *args, **kwargs: {})
        reads, publications = [], []

        def waiting(given):
            reads.append(given)
            return {'merges': [{'work_id': 'legacy', 'state': state, 'deadline': 0}]}

        monkeypatch.setattr(module, 'merges_waiting', waiting)
        monkeypatch.setattr(module, 'run_dispatch',
                            lambda *args: publications.append(args) or (True, {'merged': True}))
        monkeypatch.setattr(module.threading, 'Timer',
                            lambda delay, callback, args: SimpleNamespace(start=lambda: callback(*args)))
        server.changed({'project': 'proj', 'tables': 'dispatch', 'kinds': ['merge'], 'work_ids': ['legacy']})
        server.schedule_dispatch('proj')  # opening the project also reconciles its queue
        assert publications == [], 'ordinary reconciliation published a legacy candidate'
        assert reads == [], 'ordinary reconciliation read the explicit publication queue'


@pytest.mark.req('VIEW-044')
def test_explicit_merge_remains_available_through_dispatch_call(monkeypatch):
    publications = []
    monkeypatch.setattr(module, 'run_dispatch',
                        lambda *args: publications.append(args) or (True, {'merged': True}))
    assert module.Handler.dispatch_call(SimpleNamespace(), {'project': 'proj'}, 'merge', ['legacy']) == (
        True, {'merged': True})
    assert publications == [('proj', 'merge', ['legacy'], None)]


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
    ({'tables': ['dispatch.session_lines'], 'kinds': ['board-state'], 'session_ids': ['board:b:']}, False),
    ({'tables': ['dispatch.sessions', 'dispatch.spending'], 'kinds': ['spend']}, False),
    ({'tables': ['work'], 'kinds': ['ticket'], 'work_ids': ['w']}, True),
    ({'tables': ['work_steps'], 'kinds': ['ticket'], 'work_ids': ['w']}, False),
    ({'tables': 'dispatch', 'kinds': ['session', 'worker-idle'], 'session_ids': ['s']}, True),
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
                        lambda project: scheduled.append(project))
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
    for number in range(100):  # half note edits, half a reviewed mark flipped, which starts nothing either (round 2,
        # held-and-signals F8: each reviewed edit ran a pass)
        dispatch.store.edit_work(dispatch.id, {'note': f'Note {number}.'} if number % 2 else {'reviewed': number % 4 == 0})
        changes.announce(dispatch.folder, 'cli')
    server = object.__new__(module.Server)
    page = queue.SimpleQueue()
    server.listeners, server.listening = {page}, threading.Lock()
    server.dispatch_lock, server.dispatch_busy, server.dispatch_errors = threading.Lock(), False, {}
    server.dispatch_pending = set()
    server.retry_timers = {}
    monkeypatch.setattr(module.threading, 'Thread', lambda target, **kwargs: SimpleNamespace(start=target))
    monkeypatch.setattr(module.chassis, 'refresh_modules', lambda: None)
    monkeypatch.setattr(module.events, 'announce', lambda *args: [])
    passes = []
    monkeypatch.setattr(module, 'module_verb', lambda *args, **kwargs: passes.append(args) or {})
    arms = []  # the watch on runners' deaths lists the leases only for a change that can have started one, round 2
    server.deaths = SimpleNamespace(arm=lambda: arms.append(1))
    burst = [dict(one) for one in fired if one.get('base_id')]
    assert len(burst) == 100
    assert sum(server.changed(payload) for payload in burst) == 100, 'every change still reaches the page'
    assert passes == [] and arms == []
    fired.clear()
    dispatch.store.add_work(dispatch.node, 'unbuilt', task='Ready to start')
    changes.announce(dispatch.folder, 'cli')
    for payload in [one for one in fired if one.get('base_id')]:
        server.changed(dict(payload))
    assert len(passes) == 1 and len(arms) == 1


def test_repeated_changes_queue_one_followup_without_concurrent_batches(monkeypatch):
    server = object.__new__(module.Server)
    server.dispatch_lock = threading.Lock()
    server.dispatch_pending = set()
    server.retry_timers = {}
    server.dispatch_busy = False
    server.dispatch_errors = {}
    server.retry_timers = {}
    threads = []
    monkeypatch.setattr(module.threading, 'Thread', lambda **kwargs: SimpleNamespace(start=lambda: threads.append(kwargs)))
    monkeypatch.setattr(module.chassis, 'refresh_modules', lambda: None)
    monkeypatch.setattr(module.home, 'project', lambda project: SimpleNamespace(path='/tmp', project_id=project))
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


@pytest.mark.req('VIEW-042')
def test_the_agent_starters_own_writes_reach_the_pages_and_start_no_second_pass(monkeypatch):
    server = object.__new__(module.Server)
    page = queue.SimpleQueue()
    server.listeners, server.listening = {page}, threading.Lock()
    server.dispatch_lock, server.dispatch_busy, server.dispatch_errors = threading.Lock(), False, {}
    server.dispatch_pending = set()
    server.retry_timers = {}
    monkeypatch.setattr(module.threading, 'Thread', lambda target, **kwargs: SimpleNamespace(start=target))
    monkeypatch.setattr(module.chassis, 'refresh_modules', lambda: None)
    monkeypatch.setattr(module.home, 'project', lambda project: SimpleNamespace(path='/tmp', project_id=project))
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
                        lambda project: scheduled.put(project))
    with module.events.listen('web', server.changed):
        run('set', '--dispatch-autostart', cwd=folder)
        assert scheduled.get(timeout=5) == 'proj'
        run('unset', '--dispatch-autostart', cwd=folder)
        assert scheduled.get(timeout=5) == 'proj'


def test_new_worker_starts_rotate_projects_and_capacity_release_wakes_waiters(monkeypatch):
    server = object.__new__(module.Server)
    server.dispatch_lock, server.listening = threading.Lock(), threading.Lock()
    server.listeners = set()
    server.dispatch_pending = {('a', None), ('b', None)}
    server.capacity_waiters = set()
    server.dispatch_busy, server.dispatch_errors, server.dispatch_last = True, {}, ''
    monkeypatch.setattr(module.chassis, 'refresh_modules', lambda: None)
    monkeypatch.setattr(module.home, 'project', lambda project: SimpleNamespace(path='/tmp', project_id=project))
    monkeypatch.setattr(module.events, 'announce', lambda *args: [])
    monkeypatch.setattr(server, 'watch_backgrounds', lambda *args, **kwargs: None)
    monkeypatch.setattr(server, 'watch_runners', lambda *args: None)
    monkeypatch.setattr(server, 'schedule_retry', lambda *args: None)
    calls = []
    def start(target, module_id, verb, nouns, **kwargs):
        assert nouns == {'batch': 1}
        project = target['project']
        calls.append(project)
        return {'more': calls.count(project) == 1, 'capacity_waiting': calls.count(project) == 2}
    monkeypatch.setattr(module, 'module_verb', start)
    server.dispatch_waiting()
    assert calls == ['a', 'b', 'a', 'b']
    assert server.capacity_waiters == {('a', None), ('b', None)}
    scheduled = []
    monkeypatch.setattr(server, 'schedule_dispatch', lambda project, **kwargs: scheduled.append(project))
    server.changed({'project': 'other', 'tables': ['dispatch.sessions', 'work']})
    assert scheduled == ['other']
    assert server.dispatch_pending == {('a', None), ('b', None)}


@pytest.mark.parametrize(('project_id', 'active_board', 'inactive_board'), [
    ('orchard', 'repairs', 'later'),
    ('harbor', 'delivery', 'planned'),
])
def test_runtime_pending_work_does_not_block_event_driven_fill_and_refill(
        run, tmp_path, monkeypatch, project_id, active_board, inactive_board):
    """Real selection and reservations, with process launch stubbed, fill five slots from one board event."""
    import json

    from metaform.data import Store
    from metaform.module import context

    folder = tmp_path / project_id
    folder.mkdir()
    run('add', 'project', project_id, str(folder))
    run('enable', 'dispatch')
    run('disable', 'orchestration')
    store = Store(project_id)
    store.layer('parts', 'test', 'The parts.', mutable=True, hideable=True, ready=True)
    store.add_element('parts', 'code.engine')
    store.add_element('parts', 'code.runtime')
    for board in (active_board, inactive_board):
        run('map', 'boards', 'op=add', f'name={board}', cwd=folder)
    run('set', f'--board={active_board}', '--dispatch-autostart', '--dispatch-agents=5', cwd=folder)

    def work(task, *nouns, node='code.engine'):
        return json.loads(run('map', 'work', 'op=add', f'node={node}', f'task={task}', f'title={task}',
                              *nouns, '--json', cwd=folder).stdout)['id']

    pending = work('Runtime pending repair', 'condition=broken', 'kind=broken', node='code.runtime')
    workers = [work(f'Eligible work {number}') for number in range(7)]
    held = work('Held work', 'held=true', 'hold_reason=Wait for user review')
    stopped = work('Stopped work')
    blocked = work('Dependent work', f'after_work=["{workers[-1]}"]')
    inactive = work('Other board work', f'board={inactive_board}')
    prepared, launched = [], []
    from metaform.modules import dispatch as starter
    from metaform.modules.dispatch import orchestration, recovery

    def prepare(ctx, assignment):
        prepared.append(assignment['work_id'])
        return assignment['work_id'] != pending

    owner = SimpleNamespace(
        route_pending=lambda ctx: [], routing_waiting=lambda ctx: False, drain=lambda *args: [],
        selected_specialist=lambda *args: 'metaform://role/backend_engineer', queue_routing=lambda *args: None,
        assignment=lambda ctx, work_id, **kwargs: {
            'work_id': work_id, 'authored_role_uri': 'metaform://role/backend_engineer',
            'stop': 'person' if work_id == stopped else None},
        prepare_runtime=prepare)
    monkeypatch.setattr(orchestration, 'service', lambda ctx: owner)
    monkeypatch.setattr(recovery, 'recover', lambda ctx: {'released': []})
    # System conversations have separate capacity and do not belong to this worker admission fixture.
    monkeypatch.setattr(starter, 'stay_connected', lambda *args: {})

    def launch(ctx, store, work_id, *args, **kwargs):
        launched.append(work_id)
        assert sum((work.taken_by or '').startswith('dispatch starting ')
                   for work in store.work(open=True, limit=0).results) <= 5
        return {'pid': 1}

    monkeypatch.setattr(starter, 'start_runner', launch)
    server = object.__new__(module.Server)
    server.listeners, server.listening = set(), threading.Lock()
    server.dispatch_lock, server.dispatch_busy, server.dispatch_errors = threading.Lock(), False, {}
    server.dispatch_pending, server.capacity_waiters = set(), set()
    monkeypatch.setattr(module.threading, 'Thread', lambda target, **kwargs: SimpleNamespace(start=target))
    monkeypatch.setattr(module.chassis, 'refresh_modules', lambda: None)
    monkeypatch.setattr(module.events, 'announce', lambda *args: [])
    monkeypatch.setattr(module.events, 'publish', lambda *args: [])
    monkeypatch.setattr(server, 'watch_backgrounds', lambda *args, **kwargs: None)
    monkeypatch.setattr(server, 'watch_runners', lambda *args: None)
    monkeypatch.setattr(server, 'schedule_retry', lambda *args: None)
    passes = []

    def autostart(target, module_id, verb, nouns, **kwargs):
        assert (module_id, verb, nouns) == ('dispatch', 'autostart', {'batch': 1})
        passes.append(target)
        assert len(passes) <= 20, 'runtime preparation kept scheduling passes without starting workers'
        assert target['project'] == project_id
        return starter.autostart(context('dispatch', folder, project=project_id, nouns=nouns))

    monkeypatch.setattr(module, 'module_verb', autostart)
    server.changed({'project': project_id, 'tables': ['work'], 'kinds': ['ticket'], 'work_ids': workers})
    assert launched == workers[:5], [(work_id, store.ticket(work_id).work.task) for work_id in launched]
    assert not server.dispatch_busy and not server.dispatch_pending

    store.finish_work(workers[0], 'Done.', 'Completed first worker.')
    server.changed({'project': project_id, 'tables': ['work'], 'kinds': ['ticket'], 'work_ids': [workers[0]]})
    assert launched == workers[:6], 'completion must start the next eligible ticket'

    # The death watcher has released its verified dead runner before notifying the server.
    reservation = store.ticket(workers[1]).work.taken_by
    starter.given_back_reservation(store, workers[1], reservation)
    # Keep the abandoned ticket owned while its continuation is resolved, as an ended session does.
    store.take_work(workers[1], by='claude ended-session')
    server.runner_died({'project': project_id, 'work_ids': [workers[1]], 'kinds': ['ticket']})
    assert launched == workers, 'unexpected exit must refill from eligible work'
    assert all(not store.ticket(work).work.taken for work in (pending, held, stopped, blocked, inactive))
    assert pending in prepared
    assert not set(prepared) & {held, stopped, blocked, inactive}
    assert not server.dispatch_busy and not server.dispatch_pending

    before = len(passes)
    for _ in range(100):
        server.changed({'project': project_id, 'tables': ['work'], 'kinds': ['note'], 'work_ids': [held]})
    assert len(passes) == before, 'unrelated notes must not read scheduler inputs'
