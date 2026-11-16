"""Actual ticket reads, optimistic edits, the graph thumbnail and the specialist prompt on the web surface."""
import json

import pytest

from metaform.data import Node, Store
from metaform.modules.web.tests.test_web import api
from metaform.modules.web.tests.test_web import browser as browser  # noqa: PLC0414
from metaform.modules.web.tests.test_web import mapped as mapped  # noqa: PLC0414
from metaform.modules.web.tests.test_web import threaded as threaded  # noqa: PLC0414

pytestmark = pytest.mark.kind('simulation')


@pytest.fixture
def web(threaded):
    return threaded


def ticket():
    return Store('proj').add_work(Node('element', 'code.timer.kitchen'), None,
                                  task='Repair alarm timing.', title='Alarm timing')


def post(port, **fields):
    return api(port, '/api/ticket', method='POST', body=json.dumps({'project': 'proj', **fields}),
               headers={'Origin': f'http://127.0.0.1:{port}', 'Content-Type': 'application/json'})


def runtime_catalog():
    from metaform.modules.dispatch import offered as harness_offered
    harness_offered.keep('codex', {'state': 'ready', 'version': '1', 'name': 'Codex', 'seen': '2026-10-21T00:00:00Z',
                                   'settings': [
                                       {'id': 'model', 'category': 'model', 'type': 'select', 'current': 'gpt-6',
                                        'options': [{'value': 'gpt-6', 'name': 'GPT 6'},
                                                    {'value': 'small', 'name': 'Small'}]},
                                       {'id': 'effort', 'category': 'thought_level', 'type': 'select', 'current': 'high',
                                        'options': [{'value': 'medium', 'name': 'Medium'},
                                                    {'value': 'high', 'name': 'High'}]},
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
    assert saved_map['decision']['decider'] == 'web'
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


def test_a_ticket_named_by_address_and_number_is_found_with_its_board_and_an_unknown_number_is_not(run, web, mapped):
    work = ticket()
    item = Store('proj').numbers_of('work', [work.id])[work.id][0]
    run('map', 'boards', 'op=add', 'name=20261020', cwd=mapped)
    run('map', 'work', f'id={work.id}', 'op=edit', 'board=20261020', cwd=mapped)
    encoded = item.replace('#', '%23')
    status, said = api(web, f'/api/lookup?project=proj&refs={encoded}+code.timer.kitchen%23ffff')
    assert status == 200
    assert (said['found'][item]['kind'], said['found'][item]['id'], said['found'][item]['board']) == (
        'ticket', work.id, '20261020')
    assert said['found']['code.timer.kitchen#ffff']['kind'] is None
    _, data = api(web, f'/api/ticket-detail?project=proj&work_id={work.id}')
    assert data['board'] == '20261020' and data['ticket']['column'] == 'todo'




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
        assert 'Chosen by web' in card.locator('.runtime-choice').get_attribute('title')
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
