"""Actual ticket reads, optimistic edits, the graph thumbnail and the specialist prompt on the web surface."""
import json
import os

import pytest

from metaform.data import Node, Store
from metaform.module import context
from metaform.modules.orchestration.state import SERVICE
from metaform.modules.web.tests.test_web import api
from metaform.modules.web.tests.test_web import browser as browser  # noqa: PLC0414
from metaform.modules.web.tests.test_web import mapped as mapped  # noqa: PLC0414
from metaform.modules.web.tests.test_web import threaded as threaded  # noqa: PLC0414

pytestmark = pytest.mark.kind('simulation')


@pytest.fixture
def web(threaded, monkeypatch):
    # Model an authenticated person's browser; caller-authentication behavior has its own integration tests.
    monkeypatch.setattr('metaform.module.page_caller', lambda *args: None)
    # Ticket reads and edits need no background runner. Keep dispatch workers inside their own test homes.
    monkeypatch.setattr('metaform.modules.web.server.Server.schedule_dispatch', lambda *args, **kwargs: None)
    return threaded


def ticket():
    return Store('proj').add_work(Node('element', 'code.timer.kitchen'), None,
                                  task='Repair alarm timing.', title='Alarm timing')


def post(port, **fields):
    return api(port, '/api/ticket', method='POST', body=json.dumps({'project': 'proj', **fields}),
               headers={'Origin': f'http://127.0.0.1:{port}', 'Content-Type': 'application/json'})


def runtime_catalog():
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('catalog', {'agent': 'codex', 'version': '1', 'name': 'Codex', 'seen': '2026-10-21T00:00:00Z',
                              'seq': 1, 'settings': [
                                  {'id': 'model', 'category': 'model', 'type': 'select', 'current': 'gpt-6',
                                   'options': [{'value': 'gpt-6', 'name': 'GPT 6'}, {'value': 'small', 'name': 'Small'}]},
                                  {'id': 'effort', 'category': 'thought_level', 'type': 'select', 'current': 'high',
                                   'options': [{'value': 'medium', 'name': 'Medium'}, {'value': 'high', 'name': 'High'}]},
                              ]})


def test_card_runtime_choices_save_on_ticket_without_changing_project_defaults(run, web, mapped):
    from metaform import settings

    run('enable', 'dispatch')
    runtime_catalog()
    work = ticket()
    before = settings.value('dispatch_codex_effort', mapped)
    status, saved = post(web, work_id=work.id, agent='codex', model='gpt-6', effort='medium')
    assert status == 200, saved
    _, detail = api(web, f'/api/work?project=proj&ids={work.id}')
    saved_map = detail['results'][0]['map']
    assert saved_map['model'] == 'gpt-6'
    assert saved_map['effort'] == 'medium'
    assert saved_map['decision']['decider'] == 'person'
    assert settings.value('dispatch_codex_effort', mapped) == before
    assert post(web, work_id=work.id, model='unknown-model')[0] == 400
    assert post(web, work_id=work.id, effort='none')[0] == 200
    _, cleared = api(web, f'/api/work?project=proj&ids={work.id}')
    assert cleared['results'][0]['map'].get('effort') is None
    assert cleared['results'][0]['map']['model'] == 'gpt-6'


def test_ticket_opens_with_named_graph_edits_and_refuses_stale_save(run, web, mapped):
    work = ticket()
    status, data = api(web, f'/api/ticket-detail?project=proj&work_id={work.id}')
    assert status == 200
    assert data['ticket']['title'] == 'Alarm timing'
    assert data['functionality']['requirements']
    assert data['functionality']['dependents']
    assert data['functionality']['markdown'].startswith('```mermaid')
    assert 'memories' not in data
    status, saved = post(web, work_id=work.id, revision=data['revision'], title='Countdown alarm',
                         task='Keep the countdown accurate.', note='Check the transition at zero.', kind='broken')
    assert status == 200
    assert saved['results'][0]['task'] == 'Keep the countdown accurate.'
    assert saved['revision'] != data['revision']
    assert post(web, work_id=work.id, revision=data['revision'], task='Stale overwrite.')[0] == 409
    assert Store('proj').ticket(work.id).work.task == 'Keep the countdown accurate.'


def test_ticket_edit_updates_owned_assignment_and_sends_only_change_notice(run, web, mapped):
    work = ticket()
    ctx = context('orchestration', mapped, project='proj', nouns={'work': work.id, 'role': 'gc', 'session': 'worker'})
    assigned = SERVICE.claim(ctx)
    _, data = api(web, f'/api/ticket-detail?project=proj&work_id={work.id}')
    assert post(web, work_id=work.id, revision=data['revision'], task='Use the new timing requirements.')[0] == 200
    current = SERVICE.assignment(ctx, work_id=work.id)
    assert current['assignment_id'] == assigned['assignment_id']
    assert current['task'] == 'Use the new timing requirements.'
    assert current['owner_session_id'] == 'worker'
    direction = current['pending_direction'][-1]
    assert direction['kind'] == 'user_direction'
    assert 'Use the new timing requirements.' not in direction['body']
    assert work.id in direction['body']


@pytest.mark.browser
def test_card_edits_runtime_choice_before_start_and_refreshes_summary(run, web, mapped, browser):
    run('enable', 'dispatch')
    runtime_catalog()
    work = ticket()
    assert post(web, work_id=work.id, agent='codex', model='gpt-6', effort='medium')[0] == 200
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.goto(f'http://127.0.0.1:{web}/#p=proj')
        page.wait_for_function('() => window.metaform?.loaded()')
        page.evaluate("async () => { document.querySelector('#board').hidden = false; "
                      "await (await import('/page/app/board/board.js')).renderBoard(); }")
        card = page.locator(f'.card[data-id="{work.id}"]')
        assert card.locator('.runtime-choice').inner_text() == 'codex gpt-6 medium'
        card.locator('.ticket-settings > summary').click()
        card.locator('.runtime-settings select.effort:not([disabled])').wait_for()
        with page.expect_response(lambda response: '/api/ticket' in response.url
                                  and response.request.method == 'POST') as changed:
            card.locator('select.effort').select_option('high')
        assert changed.value.status == 200, changed.value.text()
        page.wait_for_function("id => document.querySelector(`.card[data-id=\"${id}\"] .runtime-choice`)"
                               "?.textContent === 'codex gpt-6 high'", arg=work.id)
        assert 'Chosen by person' in card.locator('.runtime-choice').get_attribute('title')
        assert card.locator('.ticket-settings').get_attribute('open') is not None
        assert not Store('proj').ticket(work.id).work.taken
        card.locator('.acts .start').click()
        page.wait_for_function("() => document.querySelector('#dispatch .agentpicker .lbl')?.textContent === 'Codex'")
        page.route('**/api/dispatch-start', lambda route: route.fulfill(json={'state': 'starting'}))
        with page.expect_request(lambda request: '/api/dispatch-start' in request.url
                                 and request.method == 'POST') as launched:
            page.locator(f'#dispatch .ticket[data-id="{work.id}"] .start').click()
        assert launched.value.post_data_json['agent'] == 'codex'
        assert not errors, errors
    finally:
        page.close()


@pytest.mark.browser
def test_board_card_opens_ticket_with_graph_thumbnail_and_specialist_prompt(run, web, mapped, browser):
    work = ticket()
    ctx = context('orchestration', mapped, project='proj', nouns={'work': work.id, 'role': 'gc', 'session': 'worker'})
    SERVICE.claim(ctx)
    other = mapped.parent / 'other-project'
    other.mkdir()
    run('add', 'project', 'another-project', str(other))
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    errors, failed, role_reads = [], [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('response', lambda response: failed.append((response.status, response.url)) if response.status >= 400 else None)
    page.on('request', lambda request: role_reads.append(request.url) if '/api/agent-role' in request.url else None)
    try:
        page.goto(f'http://127.0.0.1:{web}/#p=proj')
        page.wait_for_function('() => window.metaform && document.querySelectorAll("#map2d svg g.node").length > 0')
        page.evaluate("async () => { document.querySelector('#board').hidden = false; "
                      "const b = await import('/page/app/board/board.js'); await b.renderBoard(); }")
        page.locator(f'.card[data-id="{work.id}"] .lead').click()
        page.locator('#ticketDetail input[name=title]').fill('Edited in the inspector')
        page.locator('#ticketDetail textarea[name=task]').fill('Repair the countdown boundary.')
        page.evaluate("async () => { (await import('/page/app/core/reads.js')).S.project = 'another-project'; }")
        page.locator('#ticketDetail button[type=submit]').click()
        page.wait_for_function("() => document.querySelector('#ticketDetail [role=status]').textContent === 'Saved.'")
        assert Store('proj').ticket(work.id).work.task == 'Repair the countdown boundary.'
        assert page.locator('#ticketDetail .ticket-memories').count() == 0
        thumb = page.locator('#ticketDetail .graph-thumb:not([disabled])')
        thumb.locator('svg').wait_for()
        thumb.click()
        page.locator('.window.diagramwin .diagrambody svg').wait_for()
        assert page.locator('.window.diagramwin .title').inner_text().startswith('Graph · ')
        page.keyboard.press('Escape')
        page.locator('#ticketDetail .specialist').click()
        page.locator('#specialistPrompt .prompt').wait_for()
        assert page.locator('#specialistPrompt .title').inner_text() == 'Specialist · GC'
        assert page.locator('#specialistPrompt .prompt').inner_text().strip()
        assert len(role_reads) == 1 and 'project=proj' in role_reads[0] and 'name=metaform' in role_reads[0]
        page.evaluate("async () => { (await import('/page/app/core/reads.js')).S.project = 'proj'; }")
        if os.environ.get('METAFORM_TICKET_SCREENSHOT'):
            page.locator('#ticketDetail').screenshot(path=os.environ['METAFORM_TICKET_SCREENSHOT'])
        assert not errors and not failed, (errors, failed)
    finally:
        page.close()
