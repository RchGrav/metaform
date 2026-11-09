"""Worker event handlers reject irrelevant bursts before reading any state."""
import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

pytestmark = pytest.mark.kind('fixture')


@pytest.mark.parametrize('payload', [
    {'project': 'other', 'tables': ['dispatch.agent_sessions'], 'kinds': ['session'], 'work_ids': ['work']},
    {'project': 'proj', 'tables': ['tasks.assignments'], 'kinds': ['task'], 'work_ids': ['work']},
    {'project': 'proj', 'tables': ['map.work'], 'kinds': ['ticket'], 'work_ids': ['work']},
    {'project': 'proj', 'tables': ['dispatch.session_lines'], 'kinds': ['tool'], 'work_ids': ['work']},
    {'project': 'proj', 'tables': 'dispatch', 'kinds': ['permission'], 'work_ids': ['work']},
    {'project': 'proj', 'tables': ['dispatch.agent_sessions'], 'kinds': ['session'], 'work_ids': []},
    {'project': 'proj', 'kinds': ['session'], 'work_ids': ['work']},
])
def test_runtime_irrelevant_burst_reads_nothing(monkeypatch, payload):
    runtime = importlib.import_module('metaform.modules.tasks.runtime')
    reads = Mock(side_effect=AssertionError('An irrelevant event must not read the assignment store'))
    observed = Mock(side_effect=AssertionError('An irrelevant event must not inspect an agent'))
    ctx = SimpleNamespace(project='proj', require_store=reads)
    monkeypatch.setattr(runtime, 'own', reads)
    monkeypatch.setattr(runtime.SERVICE, 'get', observed)

    for _ in range(500):
        runtime.SERVICE.changed(ctx, payload)

    reads.assert_not_called()
    observed.assert_not_called()


@pytest.mark.parametrize('payload', [
    {'project': 'other', 'tables': ['tasks.board'], 'wake': True, 'agent_ids': ['agent']},
    {'project': 'proj', 'tables': ['tasks.board'], 'wake': False, 'agent_ids': ['agent']},
    {'project': 'proj', 'tables': ['tasks.assignments'], 'wake': True, 'agent_ids': ['agent']},
    {'project': 'proj', 'tables': 'dispatch', 'wake': True, 'agent_ids': ['agent']},
    {'project': 'proj', 'tables': ['tasks.board'], 'agent_ids': ['agent']},
    {'project': 'proj', 'tables': ['tasks.board'], 'wake': True, 'agent_ids': []},
])
def test_protocol_irrelevant_burst_reads_nothing(monkeypatch, payload):
    runtime = importlib.import_module('metaform.modules.tasks.runtime')
    protocol = importlib.import_module('metaform.modules.tasks.protocol')
    reads = Mock(side_effect=AssertionError('An irrelevant event must not read an agent'))
    board = Mock(side_effect=AssertionError('An irrelevant event must not open the board'))
    flush = Mock(side_effect=AssertionError('An irrelevant event must not deliver messages'))
    monkeypatch.setattr(runtime.SERVICE, 'assignment', reads)
    monkeypatch.setattr(protocol, 'board', board)
    monkeypatch.setattr(protocol, 'flush', flush)
    ctx = SimpleNamespace(project='proj', require_store=reads)

    for _ in range(500):
        protocol.event(ctx, payload)

    reads.assert_not_called()
    board.assert_not_called()
    flush.assert_not_called()


def test_runtime_relevant_event_reads_only_named_work(monkeypatch):
    runtime = importlib.import_module('metaform.modules.tasks.runtime')
    rows = Mock(return_value=SimpleNamespace(results=[{'task_id': 'task', 'state': 'working'}]))
    store = MagicMock()
    store.tables.return_value.__enter__.return_value.rows = rows
    monkeypatch.setattr(runtime, 'own', Mock(return_value=store))
    inspect = Mock()
    monkeypatch.setattr(runtime.SERVICE, 'get', inspect)
    ctx = SimpleNamespace(project='proj')

    runtime.SERVICE.changed(ctx, {'project': 'proj', 'tables': 'dispatch', 'kinds': ['worker-idle'],
                                 'work_ids': ['named-work']})

    rows.assert_called_once_with('assignments', {'work_id': 'named-work'}, limit=0)
    inspect.assert_called_once_with(ctx, 'task')


def test_protocol_wake_reads_and_flushes_only_named_agent(monkeypatch):
    runtime = importlib.import_module('metaform.modules.tasks.runtime')
    protocol = importlib.import_module('metaform.modules.tasks.protocol')
    assignment = {'task_id': 'target'}
    lookup = Mock(return_value=assignment)
    flush = Mock()
    monkeypatch.setattr(runtime.SERVICE, 'assignment', lookup)
    monkeypatch.setattr(protocol, 'flush', flush)
    ctx = SimpleNamespace(project='proj')

    protocol.event(ctx, {'project': 'proj', 'tables': ['tasks.board'], 'wake': True, 'agent_ids': ['target']})

    lookup.assert_called_once_with(ctx, 'target')
    flush.assert_called_once_with(ctx, assignment)
