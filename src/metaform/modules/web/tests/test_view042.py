"""VIEW-042 controls and question chats in the browser."""
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from metaform.modules.web.tests.test_web import (  # noqa: F401 -- shared fixtures
    api,
    browser,
    build,
    mapped,
    opened,
    started,
    web,
)

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('VIEW-042')]


@pytest.mark.kind('simulation')
def test_autostart_clears_waiting_work_including_questioned_tickets_before_the_answer(
        run, web, mapped, tmp_path, monkeypatch, dispatch_runners):  # noqa: F811  imported fixtures keep their names for pytest discovery
    from metaform.data import Node, Store
    from metaform.modules.dispatch.tests.test_dispatch import eventually

    run('enable', 'dispatch')
    fake = Path(__file__).parents[2] / 'dispatch' / 'tests' / 'fake_agent.py'
    log = tmp_path / 'fake.jsonl'
    monkeypatch.setenv('FAKE_ACP_LOG', str(log))
    monkeypatch.setenv('FAKE_ACP_MODE', 'done')
    run('set', '--dispatch-codex', f'"{sys.executable}" "{fake}"', '--dispatch-agents=1', cwd=mapped)
    store = Store('proj')
    for ticket in store.work(open=True, limit=0).results:
        store.finish_work(ticket.id, 'Existing fixture work completed.')
    node = Node('element', store.element('code.alarm.audible').id)
    tickets = [store.add_work(node, 'unbuilt', task=f'Complete task {n}') for n in range(3)]
    questioned = store.add_work(node, 'unbuilt', task='Continue independent work', held=True)
    question = store.ask(node, 'Which approach?', work=questioned.id, suggestions=['Use the existing approach'])
    started(run)
    headers = {'Content-Type': 'application/json', 'Origin': f'http://127.0.0.1:{web}'}
    try:
        status, _ = api(web, '/api/dispatch-autostart', method='POST', headers=headers,
                        body=json.dumps({'project': 'proj', 'value': True}))
        assert status == 200
        eventually(lambda: all(store.ticket(ticket.id).work.done for ticket in tickets), limit=30)
        eventually(lambda: store.ticket(questioned.id).work.done, limit=30)
        assert store.messages(node, 'question', True).results[0].id == question.id
        status, _ = api(web, '/api/answer', method='POST', headers=headers,
                        body=json.dumps({'project': 'proj', 'id': question.id,
                                         'answer': 'Use the existing approach'}))
        assert status == 200
        assert store.messages(node, 'question', False).results[0].answer == 'Use the existing approach'
        with Store('proj', module='dispatch').tables(write=False) as tx:
            sessions = tx.rows('agent_sessions', by=('seq',), limit=0).results
        # each ticket worked once, none restarted; tickets written in the same second share a board place, so the
        # order among them is not fixed
        expected = [ticket.id for ticket in tickets] + [questioned.id]
        assert sorted(session['work_id'] for session in sessions) == sorted(expected)
    finally:
        api(web, '/api/dispatch-autostart', method='POST', headers=headers,
            body=json.dumps({'project': 'proj', 'value': False}))
        with Store('proj', module='dispatch').tables(write=False) as tx:
            sessions = tx.rows('agent_sessions', limit=0).results
        dispatch_runners.extend((dict(session), mapped, log) for session in sessions)


def test_dispatch_autostart_api_reads_and_saves_the_project_settings(run, web, mapped, browser):  # noqa: F811  imported fixtures keep their names for pytest discovery
    run('enable', 'dispatch')
    started(run)
    status, found = api(web, '/api/dispatch-autostart?project=proj')
    assert status == 200 and found == {'value': False, 'agent': 'codex', 'agents': 5}
    status, found = api(web, '/api/dispatch-autostart', method='POST',
                        body=json.dumps({'project': 'proj', 'value': False, 'agent': 'claude', 'agents': 3}),
                        headers={'Content-Type': 'application/json', 'Origin': f'http://127.0.0.1:{web}'})
    assert status == 200 and found == {'value': False, 'agent': 'claude', 'agents': 3}
    assert api(web, '/api/dispatch-autostart?project=proj') == (200, found)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#agentsMenuBtn')  # the agents' own menu, apart from Administration's removals
    page.wait_for_selector('#agentbox #promptsPick')
    assert page.locator('#adminbox #promptsPick').count() == 0 and page.locator('#adminbox #resetAgentsBtn').count() == 0
    page.keyboard.press('Escape')
    page.click('#agentsMenuBtn')
    page.wait_for_selector('#agentbox:not([hidden])')
    assert page.locator('#agentCount').input_value() == '3', 'the field shows the saved setting'
    page.fill('#agentCount', '2')
    page.locator('#agentCount').dispatch_event('change')
    page.wait_for_function('() => document.querySelector("#agentCount").value === "2" && !document.querySelector("#agentCount").disabled')
    assert api(web, '/api/dispatch-autostart?project=proj')[1]['agents'] == 2
    page.reload()
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#agentsMenuBtn')
    page.wait_for_function('() => document.querySelector("#agentCount").value === "2"')  # it survives a refresh
    assert problems == []


def test_autostart_checkbox_reads_each_project_and_only_changes_on_a_click(run, web, mapped, browser, tmp_path):  # noqa: F811  imported fixtures keep their names for pytest discovery
    from metaform.data import Store

    other = tmp_path / 'other'
    other.mkdir()
    run('add', 'project', 'other', str(other))
    build(Store('other'))
    started(run)
    settings = {'proj': False, 'other': True}
    writes = []

    def setting(route):
        request = route.request
        if request.method == 'POST':
            body = request.post_data_json
            writes.append(body)
            settings[body['project']] = body['value']
            project = body['project']
        else:
            project = parse_qs(urlparse(request.url).query)['project'][0]
        route.fulfill(json={'value': settings[project], 'agent': 'codex'})

    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    page.route('**/api/dispatch-autostart*', setting)
    page.goto(f'http://127.0.0.1:{web}/#p=proj')
    page.wait_for_function('() => window.metaform.loaded()')
    control = page.get_by_role('switch', name='Autostart')  # a checkbox shown as a switch, role="switch"
    assert control.is_visible() and not control.is_checked()
    assert writes == []
    control.check()
    page.wait_for_function('() => !document.querySelector("#autostartAgents").disabled')
    assert settings['proj'] is True and writes[0]['project'] == 'proj'
    control.uncheck()
    page.select_option('#proj', 'other')
    page.wait_for_function('() => document.querySelector("#autostartAgents").checked')
    assert len(writes) == 2
    page.select_option('#proj', 'proj')
    page.wait_for_function('() => !document.querySelector("#autostartAgents").disabled')
    assert not control.is_checked()
    page.reload()
    page.wait_for_function('() => window.metaform.loaded()')
    assert not control.is_checked() and len(writes) == 2

