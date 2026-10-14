"""The map's thought text comes only from each figure's own public message stream."""
import json

import pytest

from metaform.modules.dispatch.tests.test_dispatch import dispatch  # noqa: F401

pytestmark = pytest.mark.kind('simulation')


def test_session_summary_keeps_only_own_latest_message_without_returning_history(dispatch, monkeypatch):  # noqa: F811
    from metaform.module import Context
    from metaform.modules import dispatch as module

    session = {'session_id': 'own', 'work_id': dispatch.id, 'agent': 'codex', 'state': 'running',
               'activity': 'working', 'started': '2026-10-14T00:00:00Z', 'seq': 1}
    monkeypatch.setattr(module, 'sessions', lambda *_: [session])
    own = module.own_store(dispatch.store)
    with own.tables() as tx:
        for seq, sid, kind, text in [
                (1, 'own', 'agent_message_chunk', 'Checking the renderer.'),
                (2, 'other', 'agent_message_chunk', 'Another agent speaks.'),
                (3, 'own', 'agent_message_chunk', 'Old paragraph\nTracing the current view. ' + 'word ' * 1000),
                (4, 'own', 'agent_thought_chunk', 'PRIVATE THOUGHT'),
                (5, 'own', 'tool_call', 'TOOL OUTPUT'),
                (6, 'own', 'stderr', 'STDERR OUTPUT')]:
            tx.insert('lines', {'session_id': sid, 'work_id': dispatch.id, 'name': f'line:{seq}',
                                'kind': kind, 'text': text, 'seq': seq})
    found = module.read_sessions(Context(module='dispatch', folder=dispatch.folder, project='proj',
                                         store=own, nouns={'thread': False}))
    message = found['sessions'][0]['latest_message']
    assert message['session_id'] == 'own'
    assert message['kind'] == 'agent_message_chunk'
    assert message['text'].startswith('Tracing the current view.')
    assert len(message['text']) <= 600
    assert message['complete'] is True
    assert found['lines'] == []
    assert not any(word in json.dumps(found) for word in ['PRIVATE THOUGHT', 'TOOL OUTPUT', 'STDERR OUTPUT',
                                                        'Another agent speaks.'])


def test_streamed_child_summary_uses_its_own_line_and_keeps_the_stream_identity(dispatch, monkeypatch):  # noqa: F811
    from metaform.module import Context
    from metaform.modules import dispatch as module

    session = {'session_id': 'parent', 'work_id': dispatch.id, 'agent': 'codex', 'state': 'running',
               'activity': 'working', 'started': '2026-10-14T00:00:00Z', 'seq': 1}
    monkeypatch.setattr(module, 'sessions', lambda *_: [session])
    own = module.own_store(dispatch.store)
    with own.tables() as tx:
        for seq, sid, name, kind, text in [
                (1, 'parent', 'flow:1', 'agent_message_chunk', 'Parent message.'),
                (2, 'parent', 'subagent:child', 'subagent', json.dumps({'session_id': 'child', 'state': 'working'})),
                (3, 'child', 'flow:1', 'agent_message_chunk', 'Inspecting the child view.')]:
            tx.insert('lines', {'session_id': sid, 'work_id': dispatch.id, 'name': name,
                                'kind': kind, 'text': text, 'seq': seq})
    ctx = Context(module='dispatch', folder=dispatch.folder, project='proj', store=own, nouns={'thread': False})
    first = module.read_sessions(ctx)
    child = first['subagents'][0]['latest_message']
    assert child['text'] == 'Inspecting the child view.'
    assert child['session_id'] == 'child' and child['complete'] is False
    with own.tables() as tx:
        tx.update('lines', {'session_id': 'child', 'name': 'flow:1'}, {'text': 'Inspecting the child view and its label.'})
    grown = module.read_sessions(ctx)['subagents'][0]['latest_message']
    assert grown['text'] == 'Inspecting the child view and its label.'
    assert grown['seq'] == child['seq'] and grown['name'] == child['name']
    assert module.read_sessions(ctx)['sessions'][0]['latest_message']['text'] == 'Parent message.'
