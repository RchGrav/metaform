"""ACP permission options cross the page boundary without a local permission policy."""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from metaform.modules.roundtables.roundtable import permissions, store

pytestmark = pytest.mark.kind('simulation')

PAYLOAD = {'title': 'Write the shared notes', 'description': 'The agent wants to write its session notes.',
           'sessionId': 'agent-session', 'subject': {'type': 'tool_call', 'toolCallId': 'write-1'},
           'options': [{'optionId': 'allow-write', 'name': 'Allow this write', 'kind': 'allow_once'},
                       {'optionId': 'deny-write', 'name': 'Decline this write', 'kind': 'reject_once'}]}


@pytest.fixture
def discussion(home, tmp_path, monkeypatch):
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    chosen = [{'kind': 'acp', 'id': 'acp:codex/sol', 'agent': 'codex', 'model': 'sol'}]
    role = {**chosen[0], 'name': 'Sol'}
    return store.opened({'subject': 'Permission fixture', 'opening': 'Write notes.', 'folder': str(tmp_path),
                         'chair_key': None, 'chair_token': 'chair', 'reporter': chosen[0]['id'],
                         'host': role, 'synthesizer': role, 'rounds': 1, 'spend': 0}, chosen, judging=False)


def test_person_option_is_relayed_and_unrelated_events_do_no_reads(discussion, monkeypatch):
    async def check():
        ready = asyncio.Event()
        handlers = []
        closed = Mock()
        monkeypatch.setattr(permissions.events, 'listen', lambda module, handler: (
            handlers.append(handler) or SimpleNamespace(close=closed)))
        opened = permissions._opened

        def visible(*args):
            found = opened(*args)
            ready.set()
            return found

        monkeypatch.setattr(permissions, '_opened', visible)
        read = Mock(wraps=permissions.get)
        monkeypatch.setattr(permissions, 'get', read)
        task = asyncio.create_task(permissions.request(discussion, 0, PAYLOAD))
        await ready.wait()
        payload = json.loads(store.events(discussion)[-1]['text'])
        assert {key: payload[key] for key in PAYLOAD} == PAYLOAD
        read.reset_mock()
        for _ in range(100):
            handlers[0]({'kinds': ['roundtables:permissions:999']})
        read.assert_not_called()
        assert not task.done()
        permissions.answer(discussion, payload['request'], 'allow-write')
        handlers[0]({'kinds': [permissions.topic(discussion)]})
        assert await asyncio.wait_for(task, 1) == 'allow-write'
        assert permissions.get(discussion, payload['request'])['state'] == 'answered'
        closed.assert_called_once()

    asyncio.run(check())


def test_cancelled_prompt_withdraws_permission(discussion, monkeypatch):
    async def check():
        ready = asyncio.Event()
        opened = permissions._opened
        closed = Mock()
        monkeypatch.setattr(permissions.events, 'listen', lambda *args: SimpleNamespace(close=closed))

        def visible(*args):
            found = opened(*args)
            ready.set()
            return found

        monkeypatch.setattr(permissions, '_opened', visible)
        task = asyncio.create_task(permissions.request(discussion, -4, PAYLOAD))
        await ready.wait()
        payload = json.loads(store.events(discussion)[-1]['text'])
        assert payload['name'] == 'Minutes'
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert permissions.get(discussion, payload['request'])['state'] == 'cancelled'
        assert json.loads(store.events(discussion)[-1]['text'])['state'] == 'cancelled'
        with pytest.raises(ValueError, match='cancelled'):
            permissions.answer(discussion, payload['request'], 'allow-write')
        closed.assert_called_once()

    asyncio.run(check())


def test_duplicate_choice_is_safe_and_other_options_are_rejected(discussion):
    permissions._opened(discussion, 0, 'fixture-request', PAYLOAD)
    with pytest.raises(ValueError, match='supplied by the agent'):
        permissions.answer(discussion, 'fixture-request', 'invented-option')
    first = permissions.answer(discussion, 'fixture-request', 'deny-write')
    assert permissions.answer(discussion, 'fixture-request', 'deny-write') == first
    with pytest.raises(ValueError, match='answered'):
        permissions.answer(discussion, 'fixture-request', 'allow-write')


def test_answer_from_another_process_wakes_existing_relay(discussion, monkeypatch):
    async def check():
        ready = asyncio.Event()
        opened = permissions._opened
        request_id = ''

        def visible(*args):
            nonlocal request_id
            found = opened(*args)
            request_id = found['request']
            ready.set()
            return found

        monkeypatch.setattr(permissions, '_opened', visible)
        task = asyncio.create_task(permissions.request(discussion, 0, PAYLOAD))
        await ready.wait()
        script = ('import sys; from metaform.modules.roundtables.roundtable import permissions; '
                  'from metaform import relay; number=int(sys.argv[1]); '
                  'permissions.answer(number,sys.argv[2],"allow-write"); '
                  'relay.deliver("map.changed",{"kinds":[permissions.topic(number)]})')
        result = await asyncio.to_thread(subprocess.run, [sys.executable, '-c', script,
                                                         str(discussion), request_id],
                                         env=os.environ.copy(), capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stderr
        assert await asyncio.wait_for(task, 2) == 'allow-write'

    asyncio.run(check())


def test_cli_permission_answer_reaches_waiting_agent(discussion, run, tmp_path, monkeypatch):
    from metaform.module import context

    folder = tmp_path / 'project'
    folder.mkdir()
    run('add', 'project', 'permission-project', str(folder))
    ctx = context('roundtables', folder)
    with ctx.require_store().tables() as tx:
        tx.insert('tables', {'table_id': 'fixture', 'topic': 'Write notes.', 'opening': 'Write notes.',
                             'seats': ['acp:codex/sol'], 'spend': 0, 'state': 'running',
                             'discussion': discussion, 'chair': 'chair', 'created': store.stamp()})

    async def check():
        ready = asyncio.Event()
        opened = permissions._opened
        request_id = ''

        def visible(*args):
            nonlocal request_id
            found = opened(*args)
            request_id = found['request']
            ready.set()
            return found

        monkeypatch.setattr(permissions, '_opened', visible)
        task = asyncio.create_task(permissions.request(discussion, 0, PAYLOAD))
        await ready.wait()
        command = [sys.executable, '-m', 'metaform', 'roundtables', 'permit', 'fixture',
                   f'request={request_id}', 'option=allow-write']
        result = await asyncio.to_thread(subprocess.run, command, cwd=folder,
                                         env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[4])},
                                         capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stderr
        assert await asyncio.wait_for(task, 2) == 'allow-write'

    asyncio.run(check())


def test_web_control_relays_exact_request_and_option(monkeypatch):
    from metaform.modules.web import server
    from metaform.modules.web.tests.test_web import _Handler

    calls = []
    monkeypatch.setattr(server, 'module_verb', lambda given, module, verb, nouns:
                        calls.append((module, verb, nouns)) or {'state': 'answered'})
    handler = _Handler()
    server.Handler.roundtable_control(handler, {'project': 'project', 'table': 'table', 'action': 'permit',
                                                'request': 'request-id', 'option': 'allow-write'})
    assert calls == [('roundtables', 'permit', {'table': 'table', 'request': 'request-id', 'option': 'allow-write'})]
    assert handler.answers == [(200, {'state': 'answered'})]
