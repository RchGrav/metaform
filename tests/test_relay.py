"""A module's own long-running process hears map changes made in other processes, through the base, BASE-053."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time

import pytest

pytestmark = pytest.mark.kind('fixture')

LIMIT = 15.0

CHILD = '''
import sys, threading
from metaform import relay
heard = threading.Event()
def handler(payload):
    print('heard ' + repr(payload), flush=True)
    heard.set()
listener = relay.listen('watcher', handler)
print('listening', flush=True)
heard.wait(30)
listener.close()
'''


def eventually(check, limit=LIMIT):
    deadline = time.monotonic() + limit
    while True:
        found = check()
        if found:
            return found
        if time.monotonic() > deadline:
            raise AssertionError(f'not within {limit} s')
        time.sleep(0.05)


def records(home):
    folder = home / 'run' / 'listeners'
    return sorted(folder.glob('*.json')) if folder.exists() else []


@pytest.fixture
def folder(run, tmp_path):
    made = tmp_path / 'proj'
    made.mkdir()
    run('add', 'project', 'proj', str(made))
    return made


def write_note(run, folder):
    run('map', 'knowledge', 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true',
        'module=test', cwd=folder)


@pytest.mark.req('BASE-053')
@pytest.mark.req('QUAL-015')
@pytest.mark.cli_process
def test_a_listener_hears_map_changed_from_a_command_run_in_another_process(run, home, folder):
    from metaform import home as metaform_home
    from metaform import relay
    heard: list[dict] = []
    told = threading.Event()

    def handler(payload):
        heard.append(payload)
        told.set()
    listener = relay.listen('watcher', handler)
    try:
        [record] = records(home)
        kept = json.loads(record.read_text(encoding='utf-8'))
        assert kept['module'] == 'watcher' and kept['pid'] == os.getpid() and kept['port'] and kept['token']
        write_note(run, folder)
        assert told.wait(LIMIT), 'the command in another process told this one'
        active = metaform_home.active_base('proj')
        assert {'project': 'proj', 'base_id': active.id} in [{key: value for key, value in event.items() if key in ('project', 'base_id')} for event in heard]
    finally:
        listener.close()
    assert records(home) == [], 'closing a listener removes its record'


@pytest.mark.req('BASE-053')
def test_a_listener_never_hears_its_own_process_through_the_relay(home):
    from metaform import events, relay
    from metaform.module import Context
    heard: list[dict] = []
    listener = relay.listen('watcher', heard.append)
    try:
        deliveries = events.publish('map.changed', {'project': 'proj', 'base_id': None},
                                    Context(module='chassis', folder=home, project='proj'))
        assert not any(delivery.get('pid') == os.getpid() for delivery in deliveries)
        time.sleep(0.5)  # a relayed delivery to this process would have arrived by now
        assert heard == []
    finally:
        listener.close()


@pytest.mark.req('BASE-053')
@pytest.mark.req('BASE-032')
def test_a_change_published_here_reaches_a_listener_in_another_process_and_is_named_in_the_deliveries(home):
    from metaform import events
    from metaform.module import Context
    child = subprocess.Popen([sys.executable, '-c', CHILD], stdout=subprocess.PIPE, text=True,
                             env={**os.environ, 'METAFORM_HOME': str(home)})
    try:
        assert child.stdout is not None
        assert child.stdout.readline().strip() == 'listening'
        payload = {'project': 'proj', 'base_id': 'm1'}
        deliveries = events.publish('map.changed', payload, Context(module='chassis', folder=home, project='proj'))
        assert {'module': 'watcher', 'pid': child.pid, 'status': 'completed'} in deliveries
        assert child.stdout.readline().strip() == f'heard {payload!r}'
        assert child.wait(LIMIT) == 0
    finally:
        child.kill()


@pytest.mark.req('BASE-053')
@pytest.mark.req('BASE-009')
def test_publish_async_hands_the_change_to_a_listener_in_another_process(home):
    import asyncio

    from metaform import events
    from metaform.module import Context
    child = subprocess.Popen([sys.executable, '-c', CHILD], stdout=subprocess.PIPE, text=True,
                             env={**os.environ, 'METAFORM_HOME': str(home)})
    try:
        assert child.stdout is not None
        assert child.stdout.readline().strip() == 'listening'
        payload = {'project': 'proj', 'base_id': None}
        deliveries = asyncio.run(events.publish_async('map.changed', payload,
                                                      Context(module='chassis', folder=home, project='proj')))
        assert {'module': 'watcher', 'pid': child.pid, 'status': 'completed'} in deliveries
        assert child.stdout.readline().strip() == f'heard {payload!r}'
    finally:
        child.kill()


@pytest.mark.req('BASE-053')
def test_a_delivery_without_the_listeners_token_is_not_handed_to_the_handler(home):
    from metaform import relay
    heard: list[dict] = []
    listener = relay.listen('watcher', heard.append)
    try:
        [record] = records(home)
        port = json.loads(record.read_text(encoding='utf-8'))['port']
        with socket.create_connection(('127.0.0.1', port), timeout=5) as connection:
            connection.sendall(json.dumps({'token': 'guessed', 'topic': 'map.changed',
                                           'payload': {'project': 'proj'}}).encode('utf-8') + b'\n')
            with connection.makefile('rb') as answers:
                answer = json.loads(answers.readline())
        assert answer.get('ok') is not True
        time.sleep(0.3)
        assert heard == []
    finally:
        listener.close()


@pytest.mark.req('BASE-053')
def test_a_record_left_by_a_process_that_ended_without_closing_is_removed_by_the_next_delivery(home):
    from metaform import events
    from metaform.module import Context
    child = subprocess.Popen([sys.executable, '-c', CHILD], stdout=subprocess.PIPE, text=True,
                             env={**os.environ, 'METAFORM_HOME': str(home)})
    assert child.stdout is not None
    assert child.stdout.readline().strip() == 'listening'
    child.kill()
    child.wait(LIMIT)
    assert len(records(home)) == 1, 'a killed process cannot close its listener'
    deliveries = events.publish('map.changed', {'project': 'proj', 'base_id': None},
                                Context(module='chassis', folder=home, project='proj'))
    assert [delivery['status'] for delivery in deliveries if delivery.get('pid') == child.pid] == ['failed']
    assert records(home) == []


@pytest.mark.req('BASE-053')
def test_a_topic_other_than_map_changed_is_not_relayed(home):
    from metaform import events
    from metaform.module import Context
    child = subprocess.Popen([sys.executable, '-c', CHILD], stdout=subprocess.PIPE, text=True,
                             env={**os.environ, 'METAFORM_HOME': str(home)})
    try:
        assert child.stdout is not None
        assert child.stdout.readline().strip() == 'listening'
        deliveries = events.publish('hello.greeted', {'name': 'x'},
                                    Context(module='chassis', folder=home, project='proj'))
        assert not any('pid' in delivery for delivery in deliveries)
    finally:
        child.kill()


@pytest.mark.req('BASE-053')
@pytest.mark.req('BASE-019')
def test_hello_follow_prints_a_change_made_by_another_command(run, home, folder):
    run('enable', 'hello')
    follower = subprocess.Popen([sys.executable, '-m', 'metaform', 'hello', 'follow', '--json'], cwd=folder,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                env={**os.environ, 'METAFORM_HOME': str(home)})
    try:
        eventually(lambda: [record for record in records(home)
                            if json.loads(record.read_text(encoding='utf-8'))['module'] == 'hello'])
        write_note(run, folder)
        out, err = follower.communicate(timeout=LIMIT)
        assert follower.returncode == 0, err
        assert json.loads(out)['changed'][0]['project'] == 'proj'
    finally:
        follower.kill()
    assert records(home) == []


def listening_child(home):
    child = subprocess.Popen([sys.executable, '-c', CHILD], stdout=subprocess.PIPE, text=True,
                             env={**os.environ, 'METAFORM_HOME': str(home)})
    assert child.stdout is not None
    assert child.stdout.readline().strip() == 'listening'
    return child


@pytest.mark.req('BASE-053')
def test_every_recorded_listener_of_another_process_is_handed_the_change(home):
    from metaform import events
    from metaform.module import Context
    children = [listening_child(home), listening_child(home)]
    try:
        payload = {'project': 'proj', 'base_id': None}
        deliveries = events.publish('map.changed', payload, Context(module='chassis', folder=home, project='proj'))
        assert sorted(delivery['pid'] for delivery in deliveries if 'pid' in delivery) == sorted(
            child.pid for child in children)
        for child in children:
            assert child.stdout.readline().strip() == f'heard {payload!r}'
    finally:
        for child in children:
            child.kill()


@pytest.mark.req('BASE-053')
@pytest.mark.skipif(os.name == 'nt', reason='POSIX file modes')
def test_a_listeners_record_is_readable_only_by_the_user(home):
    from metaform import relay
    with relay.listen('watcher', lambda payload: None):
        [record] = records(home)
        assert record.stat().st_mode & 0o777 == 0o600


@pytest.mark.req('BASE-053')
@pytest.mark.req('BASE-009')
def test_a_listener_that_does_not_answer_keeps_its_record_and_publish_async_never_holds_the_loop(home):
    """A port that takes the connection and never answers: the delivery fails after its two-second limit, the record
    stays, and from a coroutine the loop runs on while the bus waits."""
    import asyncio

    from metaform import events, relay
    from metaform.module import Context
    silent = socket.socket()
    silent.bind(('127.0.0.1', 0))
    silent.listen()
    folder = home / 'run' / 'listeners'
    folder.mkdir(parents=True)
    record = folder / 'silent-1-00000000.json'
    record.write_text(json.dumps({'module': 'silent', 'pid': 1, 'port': silent.getsockname()[1], 'token': 't'}),
                      encoding='utf-8')

    async def both():
        ticks = 0

        async def tick():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.1)
                ticks += 1
        ticking = asyncio.create_task(tick())
        deliveries = await events.publish_async('map.changed', {'project': 'proj', 'base_id': None},
                                                Context(module='chassis', folder=home, project='proj'))
        ticking.cancel()
        return deliveries, ticks
    try:
        deliveries, ticks = asyncio.run(both())
    finally:
        silent.close()
    assert [delivery['status'] for delivery in deliveries if delivery.get('module') == 'silent'] == ['failed']
    assert record.exists(), 'a listener that is slow to answer is not taken for one that ended'
    assert ticks >= relay.LIMIT * 5, 'the loop ran while the bus waited for the listener'
