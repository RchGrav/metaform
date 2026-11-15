"""Gemini reads the table project while the process and conversation remain separate."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

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


def test_a_claude_family_name_preserves_the_advertised_context_qualifier():
    from metaform.modules.roundtables.roundtable.seats import resolve
    offered = [{'value': value, 'name': value}
               for value in ('default', 'opus', 'claude-fable-5-1[1m]', 'sonnet', 'haiku')]
    assert resolve('fable', offered) == 'claude-fable-5-1[1m]'
    assert resolve('claude-fable-5-1[1m]', offered) == 'claude-fable-5-1[1m]'


@pytest.mark.parametrize('variants', [
    ('claude-fable-5-1', 'claude-fable-5-1[1m]'),
    ('claude-fable-5-1[200k]', 'claude-fable-5-1[1m]'),
])
def test_a_claude_family_context_variant_requires_an_exact_choice(variants):
    from metaform.modules.roundtables.roundtable.seats import resolve
    offered = [{'value': value, 'name': value} for value in (*variants, 'claude-fable-5')]
    assert resolve('fable', offered) is None
    for value in variants:
        assert resolve(value, offered) == value


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


@pytest.mark.parametrize('agent', ['claude', 'codex'])
def test_reseating_a_failed_session_preserves_its_conversation_across_topics(run, tmp_path, monkeypatch, agent):
    from metaform.modules.roundtables.roundtable import harness, runner, server, store

    project = tmp_path / 'project'
    project.mkdir()
    run('add', 'project', 'continuous-session', str(project))
    run('enable', 'dispatch', cwd=project)
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    chosen = [{'kind': 'acp', 'id': f'acp:{agent}/chosen', 'agent': agent, 'model': 'chosen'}]
    number = store.opened({'subject': 'Continuous discussion', 'opening': 'Keep this session.',
                           'folder': str(project), 'chair_key': None, 'chair_token': 'fixture',
                           'reporter': chosen[0]['id'], 'host': chosen[0], 'synthesizer': chosen[0],
                           'rounds': 0, 'spend': 1}, chosen,
                          [{'name': 'first', 'title': 'First', 'text': 'First topic.'},
                           {'name': 'second', 'title': 'Second', 'text': 'Second topic.'}], judging=False,
                          session={'total': 2, 'folder': str(tmp_path / 'materials')})
    conversation = {'session': 'existing-native-session', 'seen': 42,
                    'messages': [{'role': 'user', 'content': 'An earlier decision.'},
                                 {'role': 'assistant', 'content': 'The existing response.'}],
                    'extra': {'topic': 0, 'continuity': 'Retain the agent state.'}}
    store.seat_change(number, 0, **conversation, gone='Adapter disconnected.', availability='unavailable',
                      failures=4, failing='gone', reason='Adapter disconnected.', since=store.stamp())
    spawn = Mock()
    monkeypatch.setattr(runner, 'spawn', spawn)
    rebuild = AsyncMock(side_effect=AssertionError('A session keeps its existing native conversation.'))
    monkeypatch.setattr(harness.AcpSeat, 'rebuild', rebuild)

    server.reseated(store.discussion(number), chosen[0]['id'])
    restored = store.seats(number)[0]
    assert {key: restored[key] for key in conversation} == conversation
    assert restored['gone'] is None and restored['availability'] == 'active'
    assert restored['failures'] == 0 and restored['reseated'] == 1
    spawn.assert_called_once_with(number)

    table = runner.Table(number)
    seat = table.seat(restored)
    asyncio.run(table.topical(store.discussion(number), seat))
    table.next_topic(store.discussion(number))
    asyncio.run(table.topical(store.discussion(number), seat))
    after = store.seats(number)[0]
    assert {key: after[key] for key in ('session', 'messages', 'seen')} == {
        key: conversation[key] for key in ('session', 'messages', 'seen')}
    assert after['extra'] == {**conversation['extra'], 'topic': 1}
    assert table.seat(after) is seat
    rebuild.assert_not_awaited()
