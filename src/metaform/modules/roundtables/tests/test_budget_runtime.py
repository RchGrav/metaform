"""A saved live budget must be enforceable by the process actually driving the table."""
import asyncio
import os
import subprocess
import sys
import time
from unittest.mock import Mock

import pytest

from metaform import events
from metaform.modules.roundtables.roundtable import runner, server, store

pytestmark = pytest.mark.kind('simulation')


@pytest.fixture
def table(home, tmp_path, monkeypatch):
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    chosen = [{'kind': 'acp', 'id': 'acp:claude/opus', 'agent': 'claude', 'model': 'opus'}]
    role = {**chosen[0], 'name': 'Opus'}
    number = store.opened({'subject': 'Budget runtime fixture', 'opening': 'Discuss the evidence.',
                           'folder': str(tmp_path), 'chair_key': None, 'chair_token': 'fixture',
                           'reporter': chosen[0]['id'], 'host': role, 'synthesizer': role,
                           'rounds': 1, 'spend': 1}, chosen, judging=False, token_budget=100)
    spawn = Mock(return_value=None)
    monkeypatch.setattr(server.runner, 'spawn', spawn)
    return number, spawn


@pytest.mark.parametrize('marker', [None, 'a-previous-runner'])
@pytest.mark.parametrize('state', ['running', 'held'])
def test_legacy_live_runner_refuses_before_changing_the_saved_budget(table, tmp_path, marker, state):
    number, spawn = table
    store.change(number, state=state, runner='active-runner', beat=time.time(), budget_runner=marker)
    prior = store.discussion(number)
    record = store.record(number, {'round': 1, 'position': 0, 'seat': 'acp:claude/opus', 'name': 'Opus',
                                   'kind': 'seat', 'text': 'Recorded evidence.', 'accepted': True})
    document = tmp_path / 'shared.md'
    document.write_text('Saved materials.', encoding='utf-8')
    with pytest.raises(server.ToolError, match='Hold this roundtable, wait until its runner stops, then Continue'):
        server.budget(number, 200, chair='fixture')
    after = store.discussion(number)
    assert after['snapshot'] == prior['snapshot']
    assert after['state'] == state and after['runner'] == 'active-runner'
    assert store.submission(number, record['number'])['text'] == 'Recorded evidence.'
    assert document.read_text(encoding='utf-8') == 'Saved materials.'
    spawn.assert_not_called()


@pytest.mark.parametrize('state', ['running', 'held'])
def test_live_budget_edit_uses_capability_of_current_runner_token(table, state):
    number, spawn = table
    store.change(number, state=state, runner='current-runner', beat=time.time(), budget_runner='current-runner')
    answer = server.budget(number, 300, chair='fixture')
    assert answer['token_budget'] == 300
    assert store.discussion(number)['snapshot']['token_budget'] == 300
    assert store.discussion(number)['budget_runner'] == 'current-runner'
    if state == 'running':
        spawn.assert_called_once_with(number)
    else:
        spawn.assert_not_called()


def test_held_legacy_table_can_save_budget_after_its_runner_stops(table):
    number, spawn = table
    store.change(number, state='held', runner=None, budget_runner=None)
    answer = server.budget(number, 400, chair='fixture')
    assert answer['state'] == 'held' and answer['token_budget'] == 400
    assert store.discussion(number)['runner'] is None
    spawn.assert_not_called()


def test_stopped_table_can_save_budget_for_the_next_runner(table):
    number, spawn = table
    answer = server.budget(number, 500, chair='fixture')
    assert answer['token_budget'] == 500
    assert store.discussion(number)['snapshot']['token_budget'] == 500
    spawn.assert_called_once_with(number)


def test_direct_engine_budget_edit_wakes_runner_waiting_for_busy_agents(table):
    number, _ = table
    store.change(number, runner='current-runner', beat=time.time(), budget_runner='current-runner')

    async def check():
        active = runner.Table(number)
        loop = asyncio.get_running_loop()
        busy = asyncio.create_task(asyncio.Event().wait())
        waiting = asyncio.create_task(active.wait_work([busy]))
        received = []

        def changed(payload):
            if f'roundtables:control:{number}' in payload.get('kinds', []):
                received.append(store.discussion(number)['snapshot']['token_budget'])
                loop.call_soon_threadsafe(active.control.set)

        listener = events.listen('roundtables', changed)
        try:
            script = ('import sys; from metaform.modules.roundtables.roundtable import server; '
                      'server.budget(int(sys.argv[1]),50,chair="fixture")')
            result = await asyncio.to_thread(subprocess.run, [sys.executable, '-c', script, str(number)],
                                             env=os.environ.copy(), capture_output=True, text=True, timeout=15)
            assert result.returncode == 0, result.stderr
            await asyncio.wait_for(waiting, 2)
            assert received == [50]
            assert not busy.done(), 'The budget event must wake the wait while the native agent remains busy.'
            assert store.discussion(number)['runner'] == 'current-runner'
        finally:
            listener.close()
            busy.cancel()
            waiting.cancel()
            await asyncio.gather(busy, waiting, return_exceptions=True)

    asyncio.run(check())
