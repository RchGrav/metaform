"""Real Board interactions require deliberate holds, then release work across project boards."""
import pytest

from metaform.data import Node, Store
from metaform.modules.web.tests.test_ticket_detail import browser, mapped, threaded, web  # noqa: F401

pytestmark = [pytest.mark.kind('simulation'), pytest.mark.browser]
HOLD_PROMPT = 'Please explain why this ticket is on hold. State whether it is unsafe to unhold, and why.'


def board_page(driver, port):
    page = driver.new_page(viewport={'width': 1900, 'height': 1000})
    page.goto(f'http://127.0.0.1:{port}/#p=proj')
    page.wait_for_function('() => window.metaform?.loaded()')
    page.evaluate("async () => { document.querySelector('#board').hidden = false; "
                  "await (await import('/page/app/board/board.js')).renderBoard(); }")
    return page


def test_hold_requests_fresh_reason_shows_it_and_keeps_it_after_release(run, web, mapped, browser):  # noqa: F811
    store = Store('proj')
    work = store.add_work(Node('element', 'code.timer.kitchen'), None,
                          task='Check the boundary.', note='General notes are not a hold reason.')
    page = board_page(browser, web)
    writes, errors, prompts = [], [], []
    page.on('dialog', lambda dialog: prompts.append(dialog.message))
    page.on('request', lambda request: writes.append(request.post_data_json)
            if request.method == 'POST' and '/api/ticket' in request.url else None)
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        card = page.locator(f'#board .card[data-id="{work.id}"]')
        card.locator('.ticket-settings > summary').click()
        page.once('dialog', lambda dialog: dialog.accept('   '))
        card.locator('button.hold').click()
        assert writes == []
        assert prompts == [HOLD_PROMPT]
        assert page.locator('#toast').inner_text() == 'Enter a reason for this hold.'
        page.once('dialog', lambda dialog: dialog.accept('  Wait for the timing review.  '))
        with page.expect_response(lambda response: response.request.method == 'POST'
                                  and '/api/ticket' in response.url) as held:
            card.locator('button.hold').click()
        assert held.value.status == 200, held.value.text()
        assert writes[-1]['hold_reason'] == 'Wait for the timing review.'
        card.locator('.hold-reason').filter(has_text='Hold reason: Wait for the timing review.').wait_for()
        card.locator('.lead').click()
        page.locator('#ticketDetail .hold-reason').filter(has_text='Wait for the timing review.').wait_for()
        page.locator('#ticketDetail .close').click()
        card.locator('button.hold').click()
        card.locator('.hold-reason').filter(has_text='Last hold reason: Wait for the timing review.').wait_for()
        page.once('dialog', lambda dialog: dialog.dismiss())
        card.locator('button.hold').click()
        assert len(writes) == 2, 'A new hold cannot reuse the last reason or general note.'
        assert store.ticket(work.id).work.note == 'General notes are not a hold reason.'
        assert not errors, errors
    finally:
        page.close()


def test_unhold_all_button_releases_every_board_and_keeps_conversations_and_closed_work(
        run, web, mapped, browser):  # noqa: F811
    store = Store('proj')
    node = Node('element', 'code.timer.kitchen')
    reason = 'Unsafe to unhold: the timing review must finish before this can run.'
    work = store.add_work(node, None, task='Waiting here.', held=True, hold_reason=reason)
    other = store.add_work(node, None, task='Waiting on another board.', held=True, hold_reason='Wait for review.')
    legacy = store.add_work(node, None, task='Legacy held work.', held=True, hold_reason='Older hold.')
    closed = store.add_work(node, None, task='Closed work.', held=True, hold_reason='Historical hold.')
    store.finish_work(closed.id, 'Completed.')
    conversation = store.add_work(node, None, task='Conversation with the system agent', held=True)
    with Store('proj', module='map').tables() as tx:
        tx.update('ticket_settings', {'work_id': other.id}, {'board': 'Another board'})
        tx.update('ticket_settings', {'work_id': legacy.id}, {'hold_reason': None})
    page = board_page(browser, web)
    try:
        changed, releases = [], []
        page.on('request', lambda request: changed.append(request.url)
                if request.method == 'POST' and '/api/dispatch-autostart' in request.url else None)
        page.on('request', lambda request: releases.append(request.url)
                if request.method == 'POST' and '/api/unhold-all' in request.url else None)
        page.get_by_role('button', name='Unhold all', exact=True).click()
        review = page.locator('#confirm .held-work-review')
        review.first.wait_for()
        assert review.count() == 3
        assert reason in review.filter(has=page.locator('strong', has_text='Waiting here.')).inner_text()
        assert 'Another board' in page.locator(f'#confirm .held-work-review[data-id="{other.id}"]').inner_text()
        assert 'Wait for review.' in page.locator(f'#confirm .held-work-review[data-id="{other.id}"]').inner_text()
        assert 'No hold reason or release-risk explanation was recorded.' in page.locator(
            f'#confirm .held-work-review[data-id="{legacy.id}"]').inner_text()
        assert page.locator(f'#confirm .held-work-review[data-id="{closed.id}"]').count() == 0
        assert page.locator(f'#confirm .held-work-review[data-id="{conversation.id}"]').count() == 0
        page.get_by_role('button', name='Keep holds', exact=True).click()
        assert releases == []
        assert all(store.ticket(ticket.id).work.held for ticket in (work, other, legacy))
        page.locator('#board .unhold-all:not([disabled])').click()
        page.locator('#confirm .held-work-review').first.wait_for()
        store.set_work_hold(other.id, hold=True, hold_reason='Unsafe to unhold until the review finishes.')
        with page.expect_response(lambda response: '/api/unhold-all' in response.url) as stale:
            page.locator('#confirm').get_by_role('button', name='Unhold all', exact=True).click()
        assert stale.value.status == 409, stale.value.text()
        assert all(store.ticket(ticket.id).work.held for ticket in (work, other, legacy))
        page.locator('#board .unhold-all:not([disabled])').click()
        with page.expect_response(lambda response: '/api/unhold-all' in response.url) as released:
            page.locator('#confirm').get_by_role('button', name='Unhold all', exact=True).click()
        assert released.value.status == 200, released.value.text()
        assert released.value.json()['changed'] == 3
        assert {ticket['id'] for ticket in released.value.request.post_data_json['hold_preview']} == {
            work.id, other.id, legacy.id}
        page.locator(f'#board .column[data-column="todo"] .card[data-id="{work.id}"]').wait_for()
        assert not store.ticket(other.id).work.held
        assert store.ticket(conversation.id).work.held
        assert store.ticket(closed.id).work.held
        with Store('proj', module='map').tables(write=False) as tx:
            assert tx.get('ticket_settings', {'work_id': other.id})['board'] == 'Another board'
            assert tx.get('ticket_settings', {'work_id': work.id})['hold_reason'] == reason
        assert changed == [], 'Releasing holds does not change Autostart.'
        page.locator('#board .unhold-all:not([disabled])').click()
        with page.expect_response(lambda response: '/api/unhold-all' in response.url) as noop:
            page.locator('#confirm').get_by_role('button', name='Unhold all', exact=True).click()
        assert noop.value.status == 200 and noop.value.json()['changed'] == 0
    finally:
        page.close()


def test_backlog_drop_requires_fresh_reason(run, web, mapped, browser):  # noqa: F811
    store = Store('proj')
    work = store.add_work(Node('element', 'code.timer.kitchen'), None, task='Move deliberately.')
    page = board_page(browser, web)
    try:
        card = page.locator(f'#board .card[data-id="{work.id}"]')
        backlog = page.locator('#board .column[data-column="backlog"] .cards')
        page.once('dialog', lambda dialog: dialog.accept('   '))
        card.drag_to(backlog)
        assert not store.ticket(work.id).work.held
        page.once('dialog', lambda dialog: dialog.accept('Wait for the prerequisite review.'))
        with page.expect_response(lambda response: '/api/move' in response.url) as moved:
            card.drag_to(backlog)
        assert moved.value.status == 200, moved.value.text()
        assert moved.value.request.post_data_json['hold_reason'] == 'Wait for the prerequisite review.'
        backlog.locator(f'.card[data-id="{work.id}"] .hold-reason').filter(
            has_text='Wait for the prerequisite review.').wait_for()
    finally:
        page.close()


def test_backlog_creation_requires_its_own_reason(run, web, mapped, browser):  # noqa: F811
    page = board_page(browser, web)
    try:
        page.get_by_role('button', name='Add card', exact=True).click()
        page.locator('#task .text').fill('Create deliberately held work.')
        page.locator('#task .backlog').check()
        sent = []
        page.on('request', lambda request: sent.append(request.post_data_json)
                if request.method == 'POST' and '/api/task' in request.url else None)
        page.once('dialog', lambda dialog: dialog.accept('   '))
        page.get_by_role('button', name='Add task', exact=True).click()
        assert sent == []
        page.once('dialog', lambda dialog: dialog.accept('Wait for the input document.'))
        with page.expect_response(lambda response: '/api/task' in response.url
                                  and response.request.method == 'POST') as created:
            page.get_by_role('button', name='Add task', exact=True).click()
        assert created.value.status == 200, created.value.text()
        assert sent[-1]['hold_reason'] == 'Wait for the input document.'
        work_id = created.value.json()['results'][0]['id']
        card = page.locator(f'#board .card[data-id="{work_id}"]')
        card.locator('.hold-reason').filter(has_text='Wait for the input document.').wait_for()
        card.locator('.ticket-settings > summary').click()
        card.get_by_role('button', name='Release hold', exact=True).click()
        page.locator(f'#board .column[data-column="todo"] .card[data-id="{work_id}"]').wait_for()
        assert not Store('proj').ticket(work_id).work.held
    finally:
        page.close()
