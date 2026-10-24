"""Web board events deliver worker state without selecting or starting agents."""
import io
import json
import queue
import threading
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from metaform.modules.web import server as module

pytestmark = pytest.mark.kind('fixture')


@pytest.fixture
def passive(monkeypatch, tmp_path):
    server = object.__new__(module.Server)
    page = queue.SimpleQueue()
    server.listeners, server.listening = {page}, threading.Lock()
    server.watching = {}
    server.runner_lock, server.background_lock = threading.Lock(), threading.RLock()
    server.backgrounds, server.deaths = {}, None
    server.stopping = threading.Event()
    started, heard, closed, arms, watches = [], [], [], [], []

    def project(name):
        return SimpleNamespace(project_id=name, path=str(tmp_path / name)) if name else None

    def provided(folder, capability):
        if capability == 'dispatch.deaths':
            def watch(callback):
                watches.append(callback)
                return SimpleNamespace(arm=lambda: arms.append(True))
            return [('dispatch', watch)]
        if capability == 'project.background':
            def start(ctx):
                started.append(ctx.project)
                return SimpleNamespace(heard=lambda payload: heard.append((ctx.project, payload)),
                                       close=lambda: closed.append(ctx.project))
            return [('test_service', start)]
        return []

    def unexpected_execution(*args, **kwargs):
        pytest.fail('A web event attempted to execute a tool, schedule a timer or start a thread.')

    monkeypatch.setattr(module.home, 'project', project)
    monkeypatch.setattr(module.chassis, 'provided', provided)
    monkeypatch.setattr(module.chassis, 'context', lambda owner, folder, **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(module, 'module_verb', unexpected_execution)
    monkeypatch.setattr(module.threading, 'Thread', unexpected_execution)
    monkeypatch.setattr(module.threading, 'Timer', unexpected_execution)
    return SimpleNamespace(server=server, page=page, started=started, heard=heard, closed=closed,
                           arms=arms, watches=watches, project=project)


@pytest.mark.parametrize('own', [False, True])
def test_map_and_worker_event_bursts_reach_pages_without_agent_execution(passive, own):
    events = [{'project': 'proj', 'tables': ['work'], 'kinds': ['note'], 'work_ids': [str(index)]}
              for index in range(100)]
    events += [
        {'project': 'proj', 'tables': ['work'], 'kinds': ['ticket'], 'work_ids': ['ready']},
        {'project': 'proj', 'tables': ['tasks.board'], 'kinds': ['tasks.board'], 'agent_ids': ['worker']},
        {'project': 'proj', 'tables': 'dispatch', 'kinds': ['session', 'worker-idle']},
        {'project': 'proj', 'tables': ['dispatch.lines'], 'kinds': ['line']},
        {'project': 'proj'},
    ]
    for payload in events:
        assert passive.server.changed(payload, own=own) == 1
    assert [passive.page.get_nowait() for _ in events] == [
        {'topic': 'map.changed', 'payload': payload} for payload in events]
    assert passive.page.empty()
    assert passive.started == ['proj']
    assert passive.heard == [('proj', payload) for payload in events]
    assert len(passive.watches) == 1
    assert len(passive.arms) == 3, 'only ticket/session/unspecified changes rescan native runner leases'


def test_flow_and_change_delivery_remain_separate_and_leave_the_original_payload_intact(passive):
    flow = [{'session_id': 's', 'to': [{'kind': 'element', 'id': 'node'}], 'action': 'edit'}]
    payload = {'project': 'proj', 'tables': ['tasks.board'], 'kinds': ['tasks.board'], 'flow': flow}
    assert passive.server.changed(payload) == 1
    assert passive.page.get_nowait() == {'topic': 'map.flow', 'payload': {'project': 'proj', 'flows': flow}}
    assert passive.page.get_nowait() == {
        'topic': 'map.changed', 'payload': {'project': 'proj', 'tables': ['tasks.board'], 'kinds': ['tasks.board']}}
    assert payload['flow'] == flow
    assert passive.heard == [('proj', payload)]


def test_project_startup_initializes_services_and_native_death_observation_only(passive, monkeypatch):
    monkeypatch.setattr(module.home, 'projects', lambda: [passive.project('one'), passive.project('two')])
    module.projects_started(passive.server)
    assert passive.started == ['one', 'two']
    assert len(passive.watches) == 1
    assert not passive.arms
    assert passive.page.empty()


@pytest.mark.parametrize('removed', [True, False])
def test_project_removal_during_background_initialization_is_distinguished_from_storage_failure(passive, monkeypatch, removed):
    found = passive.project('proj')
    lookups = iter([found, None if removed else found])
    monkeypatch.setattr(module.home, 'project', lambda name: next(lookups))

    def disappearing(*args, **kwargs):
        raise module.StoreError('The registered project disappeared.', 'select an existing project')

    monkeypatch.setattr(module.chassis, 'context', disappearing)
    if removed:
        passive.server.watch_backgrounds('proj')
        assert 'proj' not in passive.server.backgrounds
    else:
        with pytest.raises(module.StoreError, match='disappeared'):
            passive.server.watch_backgrounds('proj')


def test_removed_projects_close_background_services_without_pushing_stale_map_events(passive, monkeypatch):
    passive.server.changed({'project': 'proj', 'tables': ['tasks.board'], 'kinds': ['tasks.board']})
    passive.page.get_nowait()
    monkeypatch.setattr(module.home, 'project', lambda name: None)
    assert passive.server.changed({'project': 'proj', 'tables': ['work'], 'kinds': ['ticket']}) == 0
    assert passive.closed == ['proj']
    assert passive.page.empty()


def test_native_runner_death_is_announced_to_pages_and_other_processes_without_replacement_start(passive, monkeypatch):
    cleanup = {'project': 'proj', 'tables': ['work'], 'kinds': ['ticket'], 'work_ids': ['ended']}
    published = []
    monkeypatch.setattr(module.chassis, 'request_scope', lambda **kwargs: nullcontext())
    monkeypatch.setattr(module.events, 'announce', lambda *args: [cleanup])
    monkeypatch.setattr(module.events, 'publish', lambda *args: published.append(args))
    passive.server.runner_died({'project': 'proj', 'work_ids': ['ended']})
    death = {'project': 'proj', 'base_id': None, 'tables': 'dispatch',
             'dispatch_tables': ['dispatch.agent_sessions'], 'work_ids': ['ended'],
             'session_ids': [], 'kinds': ['session']}
    assert passive.page.get_nowait() == {'topic': 'map.changed', 'payload': cleanup}
    assert passive.page.get_nowait() == {'topic': 'map.changed', 'payload': death}
    assert published[0][:2] == ('map.changed', death)
    assert len(passive.arms) == 2


def test_opening_and_closing_an_event_stream_updates_page_presence_without_agent_execution(passive):
    class DisconnectedPage(io.BytesIO):
        def flush(self):
            raise BrokenPipeError('The page closed after receiving its hello.')

    presence, statuses, headers = [], [], []
    passive.server.code = '0123456789abcdef'
    passive.server.pages_changed = presence.append
    passive.server.page_key_held = lambda key: True
    stream = DisconnectedPage()
    handler = object.__new__(module.Handler)
    handler.server = passive.server
    handler.wfile = stream
    handler.page_key_given = lambda: 'page-key'
    handler.send_response = lambda code: statuses.append(code)
    handler.send_header = lambda key, value: headers.append((key, value))
    handler.end_headers = lambda: None
    handler.events('proj')
    assert statuses == [200]
    assert ('Content-Type', 'text/event-stream') in headers
    assert b'"topic": "hello"' in stream.getvalue()
    assert presence == ['proj', 'proj']
    assert not passive.server.watching
    assert len(passive.server.listeners) == 1, 'the temporary SSE listener was removed'
    assert not passive.started


@pytest.mark.parametrize('method', ['GET', 'POST'])
def test_removed_automatic_dispatch_route_is_unknown(method):
    responses = []
    handler = object.__new__(module.Handler)
    handler.path = '/api/dispatch-autostart?project=proj'
    handler.headers = {'Content-Type': 'application/json'}
    handler.refused = lambda query: False
    handler.permitted = lambda verb, path: True
    handler.send = lambda status, body: responses.append((status, body))
    if method == 'GET':
        handler.route('GET')
    else:
        handler.writing('/api/dispatch-autostart')
    assert responses[0][0] == 404


def test_explicit_worker_assignment_and_board_reads_keep_their_arguments(passive, monkeypatch):
    calls, replies = [], []
    board = {'agents': [{'name': 'Exact Worker Name', 'current': {'nodes': ['Exact.Node']}}]}

    def explicit(given, module_id, verb, arguments):
        calls.append((module_id, verb, arguments))
        return board if verb == 'board' else {'task_id': 'worker-task'}

    monkeypatch.setattr(module, 'module_verb', explicit)
    handler = object.__new__(module.Handler)
    handler.reply = lambda status, body, *args: replies.append((status, json.loads(body)))
    given = {'project': 'proj', 'name': 'worker', 'agent_name': 'Exact Worker Name', 'text': 'Do this work.',
             'node': 'Exact.Node', 'skills': ['skill-id'], 'options': {'mode': 'plan'}}
    handler.assign_task(given)
    handler.worker_board({'project': 'proj'})
    assert calls == [('tasks', 'assign', {key: value for key, value in given.items() if key != 'project'}),
                     ('tasks', 'board', {})]
    assert replies == [(200, {'task_id': 'worker-task'}), (200, board)]
