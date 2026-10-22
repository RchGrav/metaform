"""Agent account authentication does not require a registered project."""
import json
import os
import signal
import subprocess
import sys
import threading

import pytest

pytestmark = pytest.mark.kind('simulation')


@pytest.mark.req('BASE-052')
def test_login_without_project_lists_methods_and_authenticates(run, home, tmp_path):
    from metaform import home as registry

    folder = tmp_path / 'outside-projects'
    log = tmp_path / 'login.jsonl'
    env = {'FAKE_ACP_LOG': str(log), 'FAKE_ACP_AUTH': '1', 'FAKE_ACP_MODE': 'hold'}
    run('enable', 'dispatch', cwd=folder)
    assert not registry.projects()
    listed = json.loads(run('dispatch', 'login', 'antigravity', '--json', cwd=folder, env=env).stdout)
    assert listed['state'] == 'choose a method'
    assert [one['id'] for one in listed['methods']] == ['fake-login', 'fake-terminal']
    logged = json.loads(run('dispatch', 'login', 'antigravity', 'method=fake-login', '--json',
                            cwd=folder, env=env).stdout)
    assert logged['logged_in'] is True
    assert not registry.projects(), 'Login must not create or register a project.'


@pytest.mark.req('BASE-052')
@pytest.mark.skipif(os.name == 'nt', reason='SIGINT is delivered differently on Windows')
def test_waiting_login_prints_url_and_cancels_cleanly(run, home, tmp_path):
    folder = tmp_path / 'outside-projects'
    run('enable', 'dispatch', cwd=folder)
    url = 'https://login.example.test/authorize?state=visible'
    log = tmp_path / 'login.jsonl'
    env = {**os.environ, 'METAFORM_HOME': str(home), 'FAKE_ACP_LOG': str(log), 'FAKE_ACP_AUTH': '1',
           'FAKE_ACP_LOGIN_URL': url, 'FAKE_ACP_LOGIN_WAIT': '1'}
    process = subprocess.Popen([sys.executable, '-m', 'metaform', 'dispatch', 'login', 'antigravity',
                                'method=fake-login', '--json'], cwd=folder, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    lines = []
    ready = threading.Event()

    def read_errors():
        for line in process.stderr:
            lines.append(line)
            if url in line:
                ready.set()

    reader = threading.Thread(target=read_errors)
    reader.start()
    try:
        assert ready.wait(10), 'The sign-in URL must be visible while authentication waits.'
        process.send_signal(signal.SIGINT)
        process.wait(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        reader.join(timeout=5)
    errors = ''.join(lines)
    assert process.returncode == 3, errors
    assert 'Cancelled.' in errors
    assert 'Task was destroyed' not in errors and 'Event loop is closed' not in errors
    pid = next(row['pid'] for row in map(json.loads, log.read_text().splitlines()) if 'pid' in row)
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
