"""Assigned-session tasks use the negotiated MCP task lifecycle without launching agents."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock

import anyio
import pytest
from mcp.shared.exceptions import MCPError

pytestmark = pytest.mark.kind('fixture')

EXTENSION = 'io.modelcontextprotocol/tasks'
TASK_ID = 'assigned-owner-1'
DETAIL = {'taskId': TASK_ID, 'status': 'working', 'createdAt': '2026-10-24T10:00:00Z',
          'lastUpdatedAt': '2026-10-24T10:00:00Z', 'ttlMs': None}


def request_context(capable=True):
    extensions = {EXTENSION: {}} if capable else {}
    return SimpleNamespace(request=None, params={}, protocol_version='2026-07-28',
                           session=SimpleNamespace(client_capabilities=SimpleNamespace(extensions=extensions),
                                                   client_params=None))


def invoke(served, method, arguments, ctx=None):
    entry = served.get_request_handler(method)
    assert entry is not None
    params = entry.params_type.model_validate(arguments)

    async def call():
        return await entry.handler(ctx or request_context(), params)
    return anyio.run(call)


@pytest.fixture
def bridge(home, tmp_path, monkeypatch):
    """Keep real registered request handlers and task routing, replace unrelated guidance and tool execution."""
    # The loader unloads module namespaces between homes. Resolve these after this home's reset/discovery,
    # so patches affect the same module objects imported by the live server's registered handlers.
    from metaform.loader import discover
    discover()
    from metaform.modules.mcp import server, tasks

    folder = tmp_path / 'caller'
    folder.mkdir()
    listed = SimpleNamespace(task='session', verb=None)
    monkeypatch.setattr(server, 'listing', lambda *args: {'tasks_start': listed})
    monkeypatch.setattr(server, 'guidance', lambda *args: '')
    monkeypatch.setattr(server, 'surface', lambda *args: [])
    monkeypatch.setattr(server, 'on_surface', lambda *args: False)
    monkeypatch.setattr(server, 'listed_names', lambda *args: [])
    monkeypatch.setattr(server.events, 'announce', lambda *args: [])
    monkeypatch.setattr(tasks, 'owning', lambda *args: None)
    launched = Mock(return_value=(False, [], {'task_id': TASK_ID, 'project_id': 'owner'}))

    async def answer(*args, **kwargs):
        return launched(*args, **kwargs)
    monkeypatch.setattr(server, 'answer', answer)
    served, _, _ = server.build(folder, http=True)
    return SimpleNamespace(served=served, folder=folder, launched=launched, server=server, tasks=tasks)


def test_provider_task_survives_server_reconstruction(bridge, tmp_path, monkeypatch):
    record = tmp_path / 'task.json'
    record.write_text(json.dumps(DETAIL))
    provider_ctx = object()
    service = SimpleNamespace(get=Mock(side_effect=lambda ctx, task_id: json.loads(record.read_text())))
    monkeypatch.setattr(bridge.tasks, 'lifecycle', lambda folder: [(provider_ctx, service)])
    for served in (bridge.served, bridge.server.build(bridge.folder, http=True)[0]):
        assert invoke(served, 'tasks/get', {'taskId': TASK_ID}) == {'resultType': 'complete', **DETAIL}
    assert service.get.call_count == 2
    service.get.assert_called_with(provider_ctx, TASK_ID)
    bridge.launched.assert_not_called()


@pytest.mark.parametrize(('method', 'field'), [('tasks/update', 'update'), ('tasks/cancel', 'cancel')])
def test_provider_mutations_keep_complete_acknowledgements(bridge, monkeypatch, method, field):
    provider_ctx = object()
    operation = Mock(return_value=True)
    service = SimpleNamespace(**{field: operation})
    monkeypatch.setattr(bridge.tasks, 'lifecycle', lambda folder: [(provider_ctx, service)])
    responses = {'outstanding': {'action': 'accept', 'content': {'answer': 'yes'}},
                 'unknown': {'action': 'decline'}}
    params = {'taskId': TASK_ID, **({'inputResponses': responses} if field == 'update' else {})}
    assert invoke(bridge.served, method, params) == {'resultType': 'complete'}
    if field == 'update':
        operation.assert_called_once_with(provider_ctx, TASK_ID, responses)
    else:
        operation.assert_called_once_with(provider_ctx, TASK_ID)
    bridge.launched.assert_not_called()


@pytest.mark.parametrize('method', ['tasks/get', 'tasks/update', 'tasks/cancel'])
def test_unknown_provider_task_returns_protocol_error(bridge, monkeypatch, method):
    service = SimpleNamespace(get=Mock(return_value=None), update=Mock(return_value=False),
                              cancel=Mock(return_value=False))
    monkeypatch.setattr(bridge.tasks, 'lifecycle', lambda folder: [(object(), service)])
    with pytest.raises(MCPError) as caught:
        invoke(bridge.served, method, {'taskId': 'unknown'})
    assert caught.value.code == -32602


@pytest.mark.parametrize('method', ['tasks/get', 'tasks/update', 'tasks/cancel'])
def test_lifecycle_requests_require_the_current_capability(bridge, monkeypatch, method):
    lifecycle = Mock()
    monkeypatch.setattr(bridge.tasks, 'lifecycle', lifecycle)
    with pytest.raises(MCPError) as caught:
        invoke(bridge.served, method, {'taskId': TASK_ID}, request_context(False))
    assert caught.value.code == -32021
    lifecycle.assert_not_called()


def test_operational_labels_do_not_restrict_declared_tools_or_schemas(project_folder, monkeypatch):
    import importlib

    from metaform import loader, settings

    loader.discover()
    live = importlib.import_module('metaform.modules.mcp.server')
    assert 'roles_without_authority' not in settings.SCHEMA
    reference = None
    for label in ('project_agent', 'intake', 'composer', 'facilitator', 'user_agent'):
        monkeypatch.setenv('METAFORM_TASK_NAME', label)
        listed = live.listing(project_folder)
        current = {name: value.schema() for name, value in listed.items()
                   if name.startswith(('map_', 'tasks_', 'dispatch_', 'memory_', 'agents_', 'workflow_'))}
        if reference is None:
            reference = current
        assert current == reference
        work = current['map_work']['properties']
        assert {'add', 'move', 'distribute', 'glyphs'} <= set(work['op']['enum'])
        assert {'task', 'column', 'position', 'agent', 'condition', 'kind'} <= set(work)
        assert 'tasks_assign' in listed and 'tasks_configure' in listed
