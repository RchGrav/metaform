"""Gemini reads the table project while the process and conversation remain separate."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from acp.experimental.v2 import schema

from metaform.modules.roundtables.roundtable.harness import Session

pytestmark = pytest.mark.kind('simulation')


@pytest.mark.parametrize('method', ['new_session', 'resume_session'])
@pytest.mark.parametrize('agent', ['antigravity', 'claude', 'codex'])
def test_project_workspace_survives_each_session_path(tmp_path, agent, method):
    private, project = str(tmp_path / 'seat'), str(tmp_path / 'project')
    session = Session(1, {'position': 0, 'agent': agent, 'model': 'chosen'}, private, reads=project)
    session.conn = SimpleNamespace(new_session=AsyncMock(), resume_session=AsyncMock())
    caps = SimpleNamespace(session=SimpleNamespace(mcp=None))
    asyncio.run(session.made(SimpleNamespace(capabilities=caps), None if method == 'new_session' else 'saved'))
    called = getattr(session.conn, method)
    called.assert_awaited_once()
    assert called.call_args.kwargs['cwd'] == project
    assert session.folder == private
    assert 'claudeCode' not in called.call_args.kwargs


@pytest.mark.parametrize('agent', ['antigravity', 'claude', 'codex'])
def test_permissions_reach_the_same_acp_relay_for_every_agent(tmp_path, monkeypatch, agent):
    from metaform.modules.roundtables.roundtable import permissions
    asked = AsyncMock(return_value='chosen-by-person')
    monkeypatch.setattr(permissions, 'request', asked)
    session = Session(7, {'position': 0, 'agent': agent, 'model': 'chosen'}, str(tmp_path), reads=str(tmp_path))
    options = [schema.PermissionOption(option_id='chosen-by-person', name='Allow once', kind='allow_once'),
               schema.PermissionOption(option_id='deny', name='Reject', kind='reject_once')]
    subject = schema.ToolCallPermissionSubjectVariant(tool_call=schema.ToolCallUpdate(
        tool_call_id='write', kind='edit', raw_input={'path': str(tmp_path / 'README.md')}))
    response = asyncio.run(session.request_permission('saved', 'Write README', options, subject=subject))
    assert response.outcome.option_id == 'chosen-by-person'
    asked.assert_awaited_once()
    number, position, payload = asked.call_args.args
    assert (number, position) == (7, 0)
    assert payload['title'] == 'Write README'
    assert payload['subject']['toolCall']['rawInput']['path'] == str(tmp_path / 'README.md')
    assert payload['options'][0]['optionId'] == 'chosen-by-person'


def test_a_claude_family_name_selects_its_newest_release():
    from metaform.modules.roundtables.roundtable.seats import resolve
    offered = [{'value': value, 'name': value} for value in ('default', 'opus', 'claude-fable-5-1', 'claude-fable-5',
                                                             'claude-opus-4-8', 'haiku')]
    assert resolve('fable', offered) == 'claude-fable-5-1'
    assert resolve('opus', offered) == 'opus'
    assert resolve('claude-fable-5', offered) == 'claude-fable-5'


@pytest.mark.parametrize('group_key', ['group', 'groupId'])
def test_grouped_models_keep_their_actual_selectable_ids(group_key):
    from metaform.modules.roundtables.roundtable.harness import choices
    option = {'options': [{group_key: 'provider', 'name': 'Provider',
                           'options': [{'value': 'model-a', 'name': 'Model A'},
                                       {'value': 'model-b', 'name': 'Model B'}]}]}
    assert choices(option) == [{'value': 'model-a', 'name': 'Model A'}, {'value': 'model-b', 'name': 'Model B'}]


@pytest.mark.parametrize('method', ['new_session', 'resume_session', 'load_session'])
def test_v1_uses_its_advertised_session_restore_operation(tmp_path, method):
    session = Session(1, {'position': 0, 'agent': 'codex', 'model': 'opus'}, str(tmp_path))
    session.protocol = 1
    session.conn = SimpleNamespace(new_session=AsyncMock(), resume_session=AsyncMock(), load_session=AsyncMock())
    caps = SimpleNamespace(session_capabilities=SimpleNamespace(resume={} if method == 'resume_session' else None),
                           mcp_capabilities=None, load_session=method == 'load_session')
    asyncio.run(session.made(SimpleNamespace(agent_capabilities=caps), None if method == 'new_session' else 'saved'))
    getattr(session.conn, method).assert_awaited_once()
    assert session.replaying == (method == 'load_session')
