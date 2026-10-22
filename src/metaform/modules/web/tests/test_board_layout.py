"""Ticket identity, passive status and real controls remain readable in narrow board columns."""
import os
from pathlib import Path

import pytest

from metaform.data import Node, Store
from metaform.modules.web.tests.test_hold_controls import board_page
from metaform.modules.web.tests.test_ticket_detail import browser, mapped, threaded, web  # noqa: F401

pytestmark = [pytest.mark.kind('simulation'), pytest.mark.browser, pytest.mark.req('VIEW-037')]

ADDRESS = 'code.scheduler.task.delivery.implemented_ticket_worktree_cleanup_with_shared_changes'
DEPENDENCY = 'code.dispatcher.agent.saved_candidate_integration_and_runtime_activation'


@pytest.mark.parametrize('width', [1200, 390])
def test_long_ticket_identity_and_dependencies_wrap_without_looking_like_actions(
        run, web, mapped, browser, tmp_path, width):  # noqa: F811
    run('enable', 'dispatch')
    store = Store('proj')
    for address in (ADDRESS, DEPENDENCY):
        store.grow_element(address, name_length=1, name='Ticket delivery', role='SE')
    dependency = store.add_work(Node('element', DEPENDENCY), None, task='Verify the saved candidate.')
    work = store.add_work(Node('element', ADDRESS), None, kind='enhancement',
                          title='Finish implemented work safely', task='Merge and clean the ticket worktree.')
    with Store('proj', module='map').tables() as tx:
        tx.insert('after', {'work_id': work.id, 'works': [dependency.id]})
    reference = store.numbers_of('work', [work.id])[work.id][0]
    page = board_page(browser, web)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({'width': width, 'height': 1000})
        card = page.locator(f'#board .card[data-id="{work.id}"]')
        card.scroll_into_view_if_needed()
        artifacts = Path(os.environ.get('METAFORM_LAYOUT_ARTIFACTS', str(tmp_path)))
        artifacts.mkdir(parents=True, exist_ok=True)
        card.screenshot(path=str(artifacts / f'ticket-layout-{width}.png'))
        metrics = card.evaluate('''card => {
            const top = card.querySelector('.top'), kind = card.querySelector('.kind');
            const waiting = card.querySelector('.waiting-on'), style = getComputedStyle(waiting);
            return {overflow: top.scrollWidth - top.clientWidth, cardOverflow: card.scrollWidth - card.clientWidth,
              kindHeight: kind.getBoundingClientRect().height,
              lineHeight: parseFloat(getComputedStyle(kind).lineHeight) || parseFloat(getComputedStyle(kind).fontSize) * 1.2,
              waitingBorder: style.borderTopWidth, waitingBackground: style.backgroundColor,
              passive: waiting.tagName === 'SPAN' && waiting.tabIndex < 0 && !waiting.closest('button, [role=button]')};
        }''')
        assert metrics['overflow'] <= 1, metrics
        assert metrics['cardOverflow'] <= 1, metrics
        assert metrics['kindHeight'] <= metrics['lineHeight'] * 1.5, metrics
        assert metrics['waitingBorder'] == '0px', metrics
        assert metrics['waitingBackground'] == 'rgba(0, 0, 0, 0)', metrics
        assert metrics['passive'], metrics
        assert card.locator('.ticket-number').text_content() == reference
        assert card.locator('.ticket-local-number').inner_text() == reference[reference.rfind('#'):]
        assert card.locator('.ticket-address').inner_text() == ADDRESS
        assert card.locator('.ticket-title').inner_text() == 'Finish implemented work safely'
        number = card.locator('.ticket-local-number').bounding_box()
        title = card.locator('.ticket-title').bounding_box()
        address = card.locator('.ticket-address').bounding_box()
        assert number and title and address and number['y'] < title['y'] < address['y']
        accessible = card.locator('.ticket-head').aria_snapshot()
        assert ADDRESS in accessible and reference[reference.rfind('#'):] in accessible
        assert card.get_by_role('button', name='Start agent', exact=True).is_enabled()
        assert card.get_by_role('button', name='Chat', exact=True).is_enabled()
        card.get_by_role('button', name='Inspect', exact=True).click()
        page.locator('#ticketDetail .ref').filter(has_text=reference).wait_for()
        assert page.locator('#ticketDetail input[name=title]').input_value() == 'Finish implemented work safely'
        page.locator('#ticketDetail .close').click()
        # The Object list uses the same header. It retains the full canonical identity outside the board.
        page.evaluate('''async address => {
            const {S} = await import('/page/app/core/reads.js');
            const element = [...S.elements.values()].find(one => one.element.address === address).element;
            window.metaform.select(element.id);
        }''', ADDRESS)
        page.locator('#board .close').click()
        panel = page.locator('#work .ticket-head').filter(has_text=reference)
        panel.wait_for()
        assert panel.locator('.ticket-number').text_content() == reference
        assert panel.locator('.ticket-address').is_visible()
        assert not errors, errors
    finally:
        page.close()


def test_permission_bypass_says_approve_all_and_keeps_confirmation(run, web, mapped, browser):  # noqa: F811
    page = board_page(browser, web)
    writes = []

    def configured(route):
        writes.append(route.request.post_data_json)
        route.fulfill(json={'configured': True})

    page.route('**/api/dispatch-configure', configured)
    try:
        page.evaluate('''async () => {
            const {drawSession} = await import('/page/app/session/text.js');
            const bar = document.createElement('div'); bar.id = 'modecheck'; document.body.append(bar);
            window.modecheck = current => {
              bar.dataset.drawn = '';
              drawSession(bar, {work: 'mode-work', session: {session_id: 'mode-session', state: 'running', agent: 'claude'},
                state: {settings: [{id: 'mode', name: 'Mode', type: 'select', source: 'mode', current,
                  options: [{value: 'ask', name: 'Ask permissions'},
                    {value: 'bypassPermissions', name: 'Bypass permissions'}]}]}});
              document.querySelector('#helpdesk').hidden = false;
              document.querySelector('#sessionpop').hidden = false;
            };
            window.modecheck('ask');
        }''')
        pick = page.locator('#sessionpop select[aria-label=Mode]')
        pick.select_option('bypassPermissions')
        page.locator('#confirm').get_by_role('button', name='Keep asking', exact=True).click()
        assert writes == [] and pick.input_value() == 'ask'
        page.evaluate("window.modecheck('ask')")
        pick.select_option('bypassPermissions')
        page.locator('#confirm').get_by_role('button', name='Use Bypass permissions', exact=True).click()
        page.wait_for_function('() => document.querySelector("#sessionpop select").disabled === false')
        assert len(writes) == 1
        assert writes[0]['work_id'] == 'mode-work' and writes[0]['value'] == 'bypassPermissions'
        page.locator('#sessionpop').evaluate('box => { box.hidden = true; document.activeElement.blur(); }')
        page.evaluate("window.modecheck('bypassPermissions')")
        badge = page.locator('#sessionpop .badge.danger')
        assert badge.text_content() == 'Approve all'
        assert 'Instructions still apply.' in badge.get_attribute('title')
        assert 'No prompts' not in page.locator('#sessionpop').inner_text()
    finally:
        page.close()
