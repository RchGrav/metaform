"""A design intake retains the default selected on the page across project scopes."""
# ruff: noqa: F811
import json
from pathlib import Path

import pytest

from metaform import settings
from metaform.modules.web.tests.test_web import browser, choose_agent, started, web  # noqa: F401

pytestmark = [pytest.mark.browser, pytest.mark.kind('simulation'), pytest.mark.req('PROJ-030')]


def test_codex_default_survives_new_project_and_next_browser_intake(run, home, web, browser, tmp_path,
                                                                  dispatch_runners):
    source = tmp_path / 'source'
    source.mkdir()
    user_home = tmp_path / 'user'
    user_home.mkdir()
    log = tmp_path / 'fake.jsonl'
    run('add', 'project', 'source', str(source))
    run('enable', 'dispatch', cwd=source)
    started(run, cwd=source)
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    own = f'http://127.0.0.1:{web}/'
    page.goto(own + '#p=source')
    page.wait_for_selector('#emptyStage:not([hidden])', timeout=60000)
    page.click('#agentsMenuBtn')
    choose_agent(page, '#defaultAgentPick', 'codex')
    page.wait_for_function('() => window.metaform.harnesses().default === "codex"')
    assert settings.value('dispatch_agent', source) == 'codex'
    launched = json.loads(run('dispatch', 'intake', 'project_name=clock', '--json', '--', 'Clock design',
                              cwd=source, env={'HOME': str(user_home), 'USERPROFILE': str(user_home),
                                               'FAKE_ACP_LOG': str(log), 'FAKE_ACP_MODE': 'hold'}).stdout)
    folder = Path(launched['folder'])
    dispatch_runners.append((launched, folder, log))
    assert launched['agent'] == 'codex'
    page.goto(own + '#p=clock')
    page.reload()  # a hash navigation alone does not switch the page's selected project
    page.wait_for_function('''() => window.metaform?.harnesses().project === "clock"
      && window.metaform.harnesses().default === "codex"''')
    assert settings.value('dispatch_agent', folder) == 'codex'
    run('dispatch', 'stop', launched['work_id'], cwd=folder)
    page.wait_for_selector('#intakeBar', state='hidden', timeout=30000)
    page.click('#emptyStage .start')
    page.wait_for_selector('#intake:not([hidden])')
    assert page.locator('#intake .agentpicker .choice > .btn .lbl').inner_text() == 'Codex'
    with page.expect_response(lambda response: '/api/dispatch-intake' in response.url) as answered:
        page.click('#intake .start')
    again = answered.value.json()
    dispatch_runners.append((again, folder, log))
    assert again['agent'] == 'codex'
    assert settings.value('dispatch_agent', source) == settings.value('dispatch_agent', folder) == 'codex'
