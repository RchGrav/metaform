"""Actual ticket reads, optimistic edits, and graph-only memory on the web surface."""
import json
import os

import pytest

from metaform.data import Node, Store
from metaform.module import Stop, context
from metaform.modules.orchestration.state import SERVICE
from metaform.modules.web.server import module_verb
from metaform.modules.web.tests.test_web import api
from metaform.modules.web.tests.test_web import browser as browser  # noqa: PLC0414
from metaform.modules.web.tests.test_web import mapped as mapped  # noqa: PLC0414
from metaform.modules.web.tests.test_web import threaded as threaded  # noqa: PLC0414

pytestmark = pytest.mark.kind('simulation')


@pytest.fixture
def web(threaded, monkeypatch):
    # Model an authenticated person's browser; caller-authentication behavior has its own integration tests.
    monkeypatch.setattr('metaform.module.page_caller', lambda *args: None)
    return threaded


def ticket():
    return Store('proj').add_work(Node('element', 'code.timer.kitchen'), None,
                                  task='Repair alarm timing.', title='Alarm timing')


def post(port, **fields):
    return api(port, '/api/ticket', method='POST', body=json.dumps({'project': 'proj', **fields}),
               headers={'Origin': f'http://127.0.0.1:{port}', 'Content-Type': 'application/json'})


def test_ticket_opens_with_named_graph_edits_and_refuses_stale_save(run, web, mapped):
    work = ticket()
    status, data = api(web, f'/api/ticket-detail?project=proj&work_id={work.id}')
    assert status == 200
    assert data['ticket']['title'] == 'Alarm timing'
    assert data['functionality']['requirements']
    assert data['functionality']['dependents']
    assert data['functionality']['markdown'].startswith('```mermaid')
    assert 'entities' in data['memories'] and 'relations' in data['memories']
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


def test_ticket_memory_is_local_atomic_observations_and_relations(web, mapped):
    work = ticket()
    for name, at in [('countdown', 'code.timer.kitchen'), ('tone', 'code.alarm.audible')]:
        module_verb({'project': 'proj'}, 'memory', 'create_entities', {'node': at,
            'entities': [{'name': name, 'entityType': 'behavior', 'observations': [f'{name} is observable.']}]})
    module_verb({'project': 'proj'}, 'memory', 'create_relations', {
        'relations': [{'from': 'countdown', 'to': 'tone', 'relationType': 'triggers'}]})
    status, data = api(web, f'/api/ticket-detail?project=proj&work_id={work.id}')
    assert status == 200
    graph = data['memories']
    assert [one['name'] for one in graph['entities']] == ['countdown']
    assert graph['entities'][0]['observations'] == ['countdown is observable.']
    assert graph['relations'] == [{'from': 'countdown', 'to': 'tone', 'relationType': 'triggers'}]
    with pytest.raises(Stop, match='more than one fact'):
        module_verb({'project': 'proj'}, 'memory', 'add_observations', {
            'observations': [{'entityName': 'countdown', 'contents': ['One fact. Another fact.']}]})


@pytest.mark.browser
def test_board_card_opens_editable_ticket_and_draws_local_graph(run, web, mapped, browser):
    work = ticket()
    module_verb({'project': 'proj'}, 'memory', 'create_entities', {'node': 'code.timer.kitchen',
        'entities': [{'name': 'countdown', 'entityType': 'behavior', 'observations': ['Countdown reaches zero.']}]})
    other = mapped.parent / 'other-project'
    other.mkdir()
    run('add', 'project', 'another-project', str(other))
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    errors, failed = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('response', lambda response: failed.append((response.status, response.url)) if response.status >= 400 else None)
    try:
        page.goto(f'http://127.0.0.1:{web}/#p=proj')
        page.wait_for_function('() => window.metaform && document.querySelectorAll("#map2d svg g.node").length > 0')
        page.evaluate("async () => { document.querySelector('#board').hidden = false; "
                      "const b = await import('/page/app/board/board.js'); await b.renderBoard(); }")
        page.locator(f'.card[data-id="{work.id}"] .text').click()
        page.locator('#ticketDetail input[name=title]').fill('Edited in the inspector')
        page.locator('#ticketDetail textarea[name=task]').fill('Repair the countdown boundary.')
        page.evaluate("async () => { (await import('/page/app/core/reads.js')).S.project = 'another-project'; }")
        page.locator('#ticketDetail button[type=submit]').click()
        page.wait_for_function("() => document.querySelector('#ticketDetail [role=status]').textContent === 'Saved.'")
        page.evaluate("async () => { (await import('/page/app/core/reads.js')).S.project = 'proj'; }")
        assert Store('proj').ticket(work.id).work.task == 'Repair the countdown boundary.'
        assert page.locator('#ticketDetail .ticket-graph').count() == 2
        page.locator('#ticketDetail .diagram[data-state=drawn]').nth(1).wait_for(timeout=15000)
        if os.environ.get('METAFORM_TICKET_SCREENSHOT'):
            page.locator('#ticketDetail').screenshot(path=os.environ['METAFORM_TICKET_SCREENSHOT'])
        assert not errors and not failed, (errors, failed)
    finally:
        page.close()
