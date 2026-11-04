"""Setup permission choices reach native ACP modes and dispatch's existing request policy."""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from metaform.modules.roundtables.roundtable import harness, permissions, store
from metaform.modules.roundtables.roundtable.seat import Gone

pytestmark = pytest.mark.kind('simulation')


@pytest.fixture
def wire(tmp_path, monkeypatch, run):
    project, private = tmp_path / 'project', tmp_path / 'private'
    project.mkdir()
    private.mkdir()
    run('add', 'project', 'permission-setup', str(project))
    run('enable', 'dispatch', cwd=project)
    log = tmp_path / 'wire.jsonl'
    fake = Path(__file__).with_name('fake_agent.py')
    for key, value in {'ROUNDTABLE_HOME': str(tmp_path / 'engine'), 'FAKE_ACP_LOG': str(log),
                       'ROUNDTABLE_AGENT_CLAUDE': f'{sys.executable} {fake}',
                       'FAKE_ACP_MODES': json.dumps([{'value': 'default', 'name': 'Default'},
                                                    {'value': 'native-full', 'name': 'Native full access'}])}.items():
        monkeypatch.setenv(key, value)
    seats = [{'kind': 'acp', 'id': 'acp:claude/opus', 'agent': 'claude', 'model': 'opus'}]
    role = {**seats[0], 'name': 'Opus'}
    number = store.opened({'subject': 'Setup fixture', 'opening': 'Work together.', 'folder': str(project),
                           'chair_key': None, 'chair_token': 'fixture', 'reporter': seats[0]['id'],
                           'host': role, 'synthesizer': role, 'rounds': 1, 'spend': 0}, seats, judging=False)
    return project, private, log, number


def messages(log):
    return [json.loads(line) for line in log.read_text().splitlines()]


def make(wire, settings, **kwargs):
    project, private, _, number = wire
    return harness.Session(number, {'position': 0, 'agent': 'claude', 'model': 'opus'}, str(private),
                           reads=str(project), permission_settings=settings, **kwargs)


@pytest.mark.parametrize('protocol,legacy_mode', [(1, False), (1, True), (2, False)])
@pytest.mark.parametrize('position', [0, -1])
def test_selected_native_mode_precedes_every_context_prompt_and_resume(wire, monkeypatch, protocol, legacy_mode,
                                                                      position):
    monkeypatch.setenv('FAKE_ACP_PROTOCOL', str(protocol))
    if legacy_mode:
        monkeypatch.setenv('FAKE_ACP_LEGACY_MODES', '1')
    project, _, log, number = wire
    settings = {'prompts': 'ask_all', 'mode': 'native-full'}
    table = store.discussion(number)
    table['snapshot'] = {**table['snapshot'], 'permissions': {'claude': settings}}
    original = {**store.seats(number)[0], 'position': position}

    async def check():
        seat = harness.AcpSeat(table, original, lambda value: None)
        resumed = None
        try:
            await seat.reply('First discussion', 5)
            assert seat.session_made.permission_settings == settings
            await seat.rebuild()
            await seat.reply('Next topic and collaboration', 5)
            saved = seat.session
            await seat.close()
            resumed = harness.AcpSeat(table, {**original, 'session': saved}, lambda value: None)
            await resumed.reply('Continue the same session', 5)
            assert resumed.session_made.permission_settings == settings
        finally:
            await seat.close()
            if resumed is not None:
                await resumed.close()

    asyncio.run(check())
    rows = messages(log)
    prompts = [one for one in rows if one.get('message', {}).get('method') == 'session/prompt']
    assert len(prompts) == 3
    for prompt in prompts:
        own = [one['message'] for one in rows if one.get('pid') == prompt['pid'] and 'message' in one]
        at = own.index(prompt['message'])
        if legacy_mode:
            assert any(one.get('method') == 'session/set_mode' and one['params']['modeId'] == 'native-full'
                       for one in own[:at])
        else:
            assert any(one.get('method') == 'session/set_config_option' and
                       one['params']['configId'] == 'mode' and one['params']['value'] == 'native-full'
                       for one in own[:at])
        assert all('claudeCode' not in one.get('params', {}) for one in own)
    assert any(one.get('message', {}).get('method') == 'session/resume' for one in rows)
    assert project.exists()


@pytest.mark.parametrize('protocol', [1, 2])
def test_unadvertised_selected_mode_fails_before_any_turn(wire, monkeypatch, protocol):
    monkeypatch.setenv('FAKE_ACP_PROTOCOL', str(protocol))
    session = make(wire, {'prompts': 'approve-all', 'mode': 'mode-removed-since-setup'})

    async def check():
        with pytest.raises(Gone, match='no longer offers the selected ACP permission mode'):
            await session.start()
        assert not session.alive()

    asyncio.run(check())
    assert not any(one.get('message', {}).get('method') == 'session/prompt' for one in messages(wire[2]))


@pytest.mark.parametrize('protocol', [1, 2])
@pytest.mark.parametrize('how,kind', [('approve-all', 'edit'), ('approve-all', 'execute'),
                                     ('approve-reads', 'read'), ('approve-reads', 'search')])
def test_setup_policy_uses_dispatch_choice_for_actual_acp_kind(wire, monkeypatch, protocol, how, kind):
    monkeypatch.setenv('FAKE_ACP_PROTOCOL', str(protocol))
    monkeypatch.setenv('FAKE_ACP_PERMISSION', '1')
    monkeypatch.setenv('FAKE_ACP_PERMISSION_KIND', kind)
    notices = []
    session = make(wire, {'prompts': how, 'mode': ''}, permission_event=notices.append)

    async def check():
        try:
            await session.start()
            answer, _ = await session.prompt('Work on the shared notes', 5)
            assert answer.startswith('opus on turn 1:')
        finally:
            await session.close()

    asyncio.run(check())
    permission = next(one['permission'] for one in messages(wire[2]) if 'permission' in one)
    assert permission == {'outcome': {'optionId': 'allow', 'outcome': 'selected'}}
    assert notices == []
    assert store.events(wire[3]) == []


@pytest.mark.parametrize('protocol', [1, 2])
@pytest.mark.parametrize('how,kind', [('ask_all', 'read'), ('approve-reads', 'execute')])
def test_setup_policy_keeps_unapproved_operations_waiting_for_person(wire, monkeypatch, protocol, how, kind):
    monkeypatch.setenv('FAKE_ACP_PROTOCOL', str(protocol))
    monkeypatch.setenv('FAKE_ACP_PERMISSION', '1')
    monkeypatch.setenv('FAKE_ACP_PERMISSION_KIND', kind)

    async def check():
        visible = asyncio.Event()
        loop = asyncio.get_running_loop()
        request = {}

        def published(given):
            nonlocal request
            if given['state'] == 'waiting':
                request = given
                loop.call_soon_threadsafe(visible.set)

        session = make(wire, {'prompts': how, 'mode': ''}, permission_event=published)
        running = None
        try:
            await session.start()
            running = asyncio.create_task(session.prompt('Work on the shared notes', 5))
            await asyncio.wait_for(visible.wait(), 5)
            assert not running.done()
            assert permissions.get(wire[3], request['request'])['state'] == 'waiting'
            script = ('import sys; from metaform.modules.roundtables.roundtable import permissions; '
                      'from metaform import relay; number=int(sys.argv[1]); '
                      'permissions.answer(number,sys.argv[2],"allow"); '
                      'relay.deliver("map.changed",{"kinds":[permissions.topic(number)]})')
            result = await asyncio.to_thread(subprocess.run, [sys.executable, '-c', script,
                                                              str(wire[3]), request['request']],
                                             env=os.environ.copy(), capture_output=True, text=True, timeout=15)
            assert result.returncode == 0, result.stderr
            assert (await asyncio.wait_for(running, 5))[0].startswith('opus on turn 1:')
        finally:
            if running is not None and not running.done():
                running.cancel()
                await asyncio.gather(running, return_exceptions=True)
            await session.close()

    asyncio.run(check())
