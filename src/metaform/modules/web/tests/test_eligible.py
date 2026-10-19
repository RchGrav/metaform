"""MAP-058: people set eligibility, and the start window honors their choice."""
import json

import pytest

from metaform.modules.web.tests.test_web import (
    api,
    browser,  # noqa: F401 -- pytest fixture used by argument name
    choose_agent,
    mapped,  # noqa: F401 -- pytest fixture used by argument name
    opened,
    own_write,
    started,
    web,  # noqa: F401 -- pytest fixture used by argument name
)

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('MAP-058')]


def test_task_and_card_api_keep_eligibility_with_glyph_and_board_order(run, web, mapped):  # noqa: F811 -- pytest fixtures
    from metaform.data import Store

    started(run)
    store = Store('proj')
    node = store.element('code.alarm.audible')
    status, made = api(web, '/api/task', method='POST', headers=own_write(web), body=json.dumps({
        'project': 'proj', 'nodes': [f'element:{node.id}'], 'condition': 'unbuilt',
        'task': 'Change the audible alarm', 'agent': 'codex', 'eligible': ['claude', 'gemini'],
    }))
    assert status == 200, made
    work_id = made['results'][0]['id']
    read = lambda: next(one for one in api(web, '/api/work?project=proj')[1]['results'] if one['id'] == work_id)
    assert read()['map']['eligible'] == ['claude', 'gemini']
    run('map', 'work', 'op=edit', f'id={work_id}', 'glyph=kite', cwd=mapped)
    store.move_work(work_id, 'todo', position=0)
    before = read()
    status, changed = api(web, '/api/eligible', method='POST', headers=own_write(web), body=json.dumps({
        'project': 'proj', 'work_id': work_id, 'agents': ['codex'],
    }))
    assert status == 200, changed
    after = read()
    assert after['map']['eligible'] == ['codex']
    assert after['map']['glyph'] == before['map']['glyph'] == 'kite'
    assert after['position'] == before['position'] == 0 and after['map']['agent'] == 'codex'
    # A person's board move is distinct from a restricted agent claim.
    status, changed = api(web, '/api/move', method='POST', headers=own_write(web), body=json.dumps({
        'project': 'proj', 'work_id': work_id, 'column': 'doing', 'position': 0, 'by': 'user',
    }))
    assert status == 200, changed
    assert store.ticket(work_id).work.taken_by == 'user'
    status, changed = api(web, '/api/eligible', method='POST', headers=own_write(web), body=json.dumps({
        'project': 'proj', 'work_id': work_id, 'agents': [],
    }))
    assert status == 200, changed
    assert 'eligible' not in read()['map']


def test_task_editor_and_card_choose_multiple_agents_and_return_to_any(run, web, mapped, browser):  # noqa: F811 -- pytest fixtures
    from metaform.data import Store

    store = Store('proj')
    run('enable', 'dispatch')  # dispatch ships disabled; the pickers list the agents it knows
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.evaluate(f'window.metaform.task({json.dumps(store.element("code.alarm.audible").id)})')
    assert page.locator('#task .eligible summary').inner_text() == 'Eligible agents: Any agent'
    page.locator('#task .eligible summary').click()
    page.check('#task .eligible input[data-agent="claude"]')
    page.check('#task .eligible input[data-agent="gemini"]')
    page.fill('#task .text', 'Eligibility editor proof')
    page.select_option('#task .condition', 'unbuilt')
    with page.expect_response(lambda response: '/api/task' in response.url) as saved:
        page.click('#task .put')
    work_id = saved.value.json()['results'][0]['id']
    page.click('#boardBtn')
    card = page.locator(f'#board .card[data-id="{work_id}"]')
    card.locator('.ticket-settings > summary').click()  # the card keeps its agent, eligibility and glyph folded away
    assert card.locator('.eligible summary').inner_text() == 'Eligible agents: Claude Code, Gemini CLI'
    card.locator('.eligible summary').click()
    with page.expect_response(lambda response: '/api/eligible' in response.url):
        card.locator('.eligible input.any').check()
    page.wait_for_function(f'() => document.querySelector(\'#board .card[data-id="{work_id}"] .eligible summary\').textContent === "Eligible agents: Any agent"')
    # the Default agent, Claude Code, whatever the ticket's area (UX review round 1, 2026-10-17)
    assert card.locator('select.agent').input_value() == 'claude'
    assert problems == []


def test_start_window_skips_ineligible_first_ticket_without_losing_its_glyph(run, web, mapped, browser):  # noqa: F811 -- pytest fixtures
    from metaform.data import Node, Store

    store = Store('proj')
    for ticket in store.work(open=True, limit=0).results:
        store.finish_work(ticket.id, 'fixture setup')
    node = Node('element', store.element('code.alarm.audible').id)
    first, later, any_agent = [store.add_work(node, 'unbuilt', task=f'Eligibility queue {i}').id for i in range(3)]
    for work_id in (first, later):
        run('map', 'work', 'op=edit', f'id={work_id}', 'glyph=kite', cwd=mapped)
    run('map', 'work', 'op=edit', f'id={first}', 'eligible=["claude"]', cwd=mapped)
    run('map', 'work', 'op=edit', f'id={later}', 'eligible=["codex"]', cwd=mapped)
    for position, work_id in enumerate((first, later, any_agent)):
        store.move_work(work_id, 'todo', position=position)
    run('enable', 'dispatch')  # dispatch ships disabled; the start window is its
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    sent = []
    page.route('**/api/dispatch-start', lambda route: (sent.append(route.request.post_data_json), route.fulfill(json={'state': 'starting'})))
    page.click('#boardBtn')
    page.locator(f'#board .card[data-id="{first}"] .start').click()
    choose_agent(page, '#dispatch', 'codex')
    assert page.locator('#dispatch .ticket button.start').is_disabled()
    choose_agent(page, '#dispatch', 'claude')
    assert page.locator('#dispatch .ticket button.start').is_enabled()
    page.click('#dispatch .close')
    page.click('#board .start-all')
    choose_agent(page, '#dispatch', 'codex')
    assert page.eval_on_selector_all('#dispatch .ticket', 'rows => rows.map(row => row.dataset.id)') == [later, any_agent]
    # what it starts is said before the click, from the slots read as the window opened, UX review round 1
    page.wait_for_function('() => document.querySelector("#dispatch .start-all").textContent === "Start 2 of 2"')
    assert 'of 5 Full Auto slots free' in page.inner_text('#dispatch .slots')
    page.click('#dispatch .start-all')
    page.wait_for_selector('#dispatch', state='hidden')
    assert [one['work_id'] for one in sent] == [later, any_agent]
    record = json.loads(run('map', 'work', f'id={first}', '--json', cwd=mapped).stdout)
    assert record['map']['glyph'] == 'kite' and record['position'] == 0 and record['taken'] is None
    assert problems == []
