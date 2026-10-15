"""Closing a conversation preserves its agent, and an explicit stop keeps recovery visible."""
import json

import pytest

from metaform.modules.web.tests.test_web import browser, mapped, opened, started, web  # noqa: F401


@pytest.mark.kind('fixture')
def test_close_and_escape_preserve_a_working_system_session_and_stop_can_resume_it(
        run, home, web, mapped, browser, tmp_path, monkeypatch):  # noqa: F811
    from metaform.modules.dispatch.tests.test_dispatch import Dispatch, end_agent, eventually, gone

    agent = Dispatch(run, home, mapped, tmp_path)
    for key, value in agent.env('hold', FAKE_ACP_LOAD='1').items():
        if key.startswith('FAKE_'):
            monkeypatch.setenv(key, value)
    agent.id = agent.store.add_work(agent.node, None, task='Conversation with the system agent', held=True).id
    agent.start('hold', 'system=true', FAKE_ACP_LOAD='1')
    session = agent.session().extra['session_id']
    from metaform.data import Store
    with Store('proj', module='dispatch').tables() as tx:  # ended sessions the person never stopped
        for index, how in enumerate(('it failed: x', 'cancelled by the person')):
            tx.insert('sessions', {'session_id': f'other-ended-{index}', 'work_id': f'other-work-{index}',
                                   'agent': 'claude', 'state': 'ended', 'how': how,
                                   'started': '2026-10-01T00:00:00Z', 'seq': index + 1})
    try:
        eventually(lambda: agent.received('session/prompt'))
        started(run)
        page, problems, _ = opened(browser, web, plain=True)
        page.route('**/api/system-chat', lambda route: route.fulfill(
            status=200, content_type='application/json', body=json.dumps(
                {'work_id': agent.id, 'session_id': session, 'agent': 'claude', 'state': 'running'})))
        page.click('#dockTab')
        page.click('#helpdesk .call')
        page.wait_for_selector('#helpdesk .threadbar .stop:not([hidden])')
        writes = []
        page.on('request', lambda req: writes.append(req.url) if req.method == 'POST' else None)

        def sessions():
            return json.loads(run('dispatch', 'sessions', f'id={agent.id}', '--json', cwd=mapped).stdout)['sessions']

        assert page.locator('#helpdesk .close').is_visible()
        assert page.locator('#helpdesk .close').inner_text() == '×'
        page.click('#helpdesk .close')
        page.wait_for_selector('#helpdesk', state='hidden')
        assert sessions()[0]['state'] == 'running'
        page.click('#dockTab')
        page.fill('#helpdesk .say', 'Unsent draft')
        page.keyboard.press('Escape')
        page.wait_for_selector('#helpdesk', state='hidden')
        assert sessions()[0]['state'] == 'running'
        assert not any('dispatch-stop' in url or 'dispatch-interrupt' in url for url in writes)
        page.click('#agentsMenuBtn')
        page.click(f'#agentbox .agent-session[data-session="{session}"] .open-chat')
        assert page.locator('#helpdesk .say').input_value() == 'Unsent draft'
        page.fill('#helpdesk .say', '')
        page.click('#helpdesk .threadbar .stop')
        page.wait_for_selector('#confirm:not([hidden])')
        assert 'Stop Claude Code?' in page.locator('#confirm').inner_text()
        assert 'You can resume it later with its memory.' in page.locator('#confirm').inner_text()
        assert sessions()[0]['state'] == 'running'
        page.click('#confirm .keep')
        assert sessions()[0]['state'] == 'running'
        page.click('#helpdesk .threadbar .stop')
        page.click('#confirm button.confirm')
        page.wait_for_selector('#helpdesk .stopped-agent button.resume')
        assert sessions()[0]['state'] == 'ended'
        assert page.locator('#helpdesk .stopped-agent img').get_attribute('src')
        assert page.locator('#helpdesk .stopped-agent time').get_attribute('datetime')
        assert page.locator('#helpdesk .stopped-agents .agent-session').count() == 1
        page.click('#helpdesk .stopped-agents .forget')
        assert page.locator('#helpdesk .stopped-agents .agent-session').count() == 0
        page.reload(wait_until='domcontentloaded', timeout=30000)
        page.wait_for_function('() => window.metaform?.loaded()', timeout=30000)
        page.click('#agentsMenuBtn')
        for index in range(2):
            other = page.locator(f'#agentbox .agent-session[data-session="other-ended-{index}"]')
            assert other.locator('button.resume').count() == 0
            assert 'Stopped' not in other.inner_text()
        row = page.locator(f'#agentbox .stopped-agent[data-session="{session}"]')
        assert 'Claude Code' in row.inner_text()
        assert 'Conversation' in row.inner_text()
        resumed = []
        page.on('request', lambda req: resumed.append(req.post_data_json)
                if '/api/dispatch-resume' in req.url else None)
        row.locator('button.resume').click()
        eventually(lambda: sessions()[0]['state'] == 'running')
        assert sessions()[0]['session_id'] == session
        assert resumed[0]['session'] == session
        assert len(sessions()) == 1
        assert problems == []
    finally:
        agent.stop()
        agent.close()
        assert gone(end_agent(agent.log, True))


@pytest.mark.kind('fixture')
def test_the_boards_recall_puts_the_stopped_session_in_the_docks_recovery_list(
        run, home, web, mapped, browser, tmp_path):  # noqa: F811
    from metaform.modules.dispatch.tests.test_dispatch import Dispatch, end_agent, eventually, gone

    agent = Dispatch(run, home, mapped, tmp_path)
    agent.start('hold')
    session = agent.session().extra['session_id']

    def sessions():
        return json.loads(run('dispatch', 'sessions', f'id={agent.id}', '--json', cwd=mapped).stdout)['sessions']
    try:
        eventually(lambda: agent.received('session/prompt'))
        started(run)
        page, problems, _ = opened(browser, web, plain=True)
        stops = []
        page.on('request', lambda req: stops.append(req.post_data_json)
                if '/api/dispatch-stop' in req.url else None)
        page.click('#boardBtn')
        page.wait_for_function('() => window.metaform?.loaded()')
        card = page.locator(f'#board .card[data-id="{agent.id}"]')
        card.locator('.ticket-settings > summary').click()
        card.locator('.recall').click()
        eventually(lambda: sessions()[0]['state'] == 'ended')
        page.keyboard.press('Escape')
        page.click('#dockTab')
        page.wait_for_function('() => !document.querySelector("#helpdesk .stopped-agents").hidden'
                               ' || document.querySelector("#agentbox .stopped-agent")')
        assert page.locator('#agentbox .stopped-agent button.resume').count() == 1
        assert page.locator('#helpdesk .stopped-agents .agent-session').count() == 1
        row = page.locator(f'#helpdesk .stopped-agents .agent-session[data-session="{session}"]')
        assert row.locator('button.resume').count() == 1
        assert [(one['work_id'], one.get('session')) for one in stops] == [(agent.id, session)]
        assert problems == []
    finally:
        agent.stop()
        agent.close()
        assert gone(end_agent(agent.log, True))


@pytest.mark.kind('fixture')
def test_a_close_while_call_is_pending_keeps_the_returned_session_and_chat_hidden(
        run, web, mapped, browser):  # noqa: F811
    run('enable', 'dispatch')
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    pending = []
    stopped = []
    page.route('**/api/system-chat', lambda route: pending.append(route))
    page.route('**/api/dispatch-stop', lambda route: stopped.append(route.request.post_data_json)
               or route.fulfill(content_type='application/json', body='{}'))
    page.click('#dockTab')
    page.click('#helpdesk .call')
    page.wait_for_timeout(100)
    assert len(pending) == 1
    page.click('#helpdesk .close')
    page.wait_for_selector('#helpdesk', state='hidden')
    pending[0].fulfill(content_type='application/json', body=json.dumps(
        {'work_id': 'pending-system-chat', 'session_id': 'pending-session', 'state': 'starting'}))
    page.wait_for_function('() => window.metaform.dock().threads.some(one => one.session === "pending-session")')
    page.wait_for_timeout(600)
    assert page.locator('#helpdesk').is_hidden()
    assert stopped == []
    page.click('#dockTab')
    assert page.locator('#helpdesk').is_visible()
    assert len(page.evaluate('window.metaform.dock().threads')) == 1
    assert problems == []


@pytest.mark.kind('fixture')
def test_stopping_an_older_chat_cannot_stop_the_running_session_of_its_ticket(
        run, home, web, mapped, tmp_path):  # noqa: F811
    from metaform.data import Store
    from metaform.modules.dispatch.tests.test_dispatch import Dispatch
    from metaform.modules.web.tests.test_web import request

    agent = Dispatch(run, home, mapped, tmp_path)
    agent.start('hold', 'system=true')
    session = agent.session().extra['session_id']
    try:
        with Store('proj', module='dispatch').tables() as tx:
            tx.insert('sessions', {'session_id': 'older-ended-session', 'work_id': agent.id, 'agent': 'claude',
                                   'state': 'ended', 'how': 'stopped by the person',
                                   'started': '2026-10-01T00:00:00Z', 'seq': 1})
        started(run)
        for wanted in ('older-ended-session', '', 42):
            status, body, _ = request(web, '/api/dispatch-stop', method='POST', headers={
                'Origin': f'http://127.0.0.1:{web}', 'Content-Type': 'application/json'},
                body=json.dumps({'project': 'proj', 'work_id': agent.id, 'session': wanted}))
            assert status == 400, body
        rows = json.loads(run('dispatch', 'sessions', f'id={agent.id}', '--json', cwd=mapped).stdout)['sessions']
        assert next(row for row in rows if row['session_id'] == session)['state'] == 'running'
    finally:
        agent.stop()
        agent.close()
