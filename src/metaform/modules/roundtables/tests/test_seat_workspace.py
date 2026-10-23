"""Gemini reads the table project while the process and conversation remain separate."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from acp.schema import PermissionOption, ToolCallUpdate

from metaform.modules.roundtables.roundtable.harness import Session

pytestmark = pytest.mark.kind('simulation')


@pytest.mark.parametrize('method', ['new_session', 'resume_session', 'load_session'])
@pytest.mark.parametrize('agent', ['antigravity', 'claude', 'codex'])
def test_project_workspace_survives_each_session_path(tmp_path, agent, method):
    private, project = str(tmp_path / 'seat'), str(tmp_path / 'project')
    session = Session(1, {'position': 0, 'agent': agent, 'model': 'chosen'}, private, reads=project)
    session.conn = SimpleNamespace(new_session=AsyncMock(), resume_session=AsyncMock(), load_session=AsyncMock())
    caps = SimpleNamespace(mcp_capabilities=None, load_session=method == 'load_session',
                           session_capabilities=SimpleNamespace(resume={} if method == 'resume_session' else None))
    asyncio.run(session.made(SimpleNamespace(agent_capabilities=caps), None if method == 'new_session' else 'saved'))
    called = getattr(session.conn, method)
    called.assert_awaited_once()
    assert called.call_args.kwargs['cwd'] == (project if agent == 'antigravity' else private)
    assert session.folder == private
    assert called.call_args.kwargs['claudeCode']['options']['additionalDirectories'] == [project]


def test_gemini_project_workspace_keeps_write_requests_denied(tmp_path):
    session = Session(1, {'position': 0, 'agent': 'antigravity', 'model': 'chosen'}, str(tmp_path / 'seat'),
                      reads=str(tmp_path / 'project'))
    options = [PermissionOption(option_id='allow', name='Allow', kind='allow_once'),
               PermissionOption(option_id='deny', name='Deny', kind='reject_once')]
    for kind, wanted in [('read', 'allow'), ('search', 'allow'), ('edit', 'deny'), ('execute', 'deny')]:
        answer = asyncio.run(session.request_permission('saved', ToolCallUpdate(tool_call_id='tool', kind=kind),
                                                        options))
        assert answer.outcome.option_id == wanted
