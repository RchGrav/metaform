"""Agent account authentication does not require a registered project."""
import json

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
