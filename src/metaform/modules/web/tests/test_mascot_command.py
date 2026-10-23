"""Glyph selection is explicitly invoked, never offered on each conversation context."""
from __future__ import annotations

import pytest

from metaform.data import Node, Store
from metaform.modules.web.tests.test_web import (  # noqa: F401
    browser,
    live_session,
    mapped,
    opened,
    simulated_dispatch_control,
    started,
    web,
)

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.browser, pytest.mark.req('VIEW-039')]


def test_mascot_command_is_local_and_contexts_never_offer_the_picker(run, web, mapped, browser):  # noqa: F811
    run('enable', 'dispatch')
    store = Store('proj')
    work = store.add_work(Node('element', 'code.alarm.audible'), None,
                          task='Conversation with the system agent', held=True)
    session = f's-{work.id}'
    live_session(work.id)
    from metaform.modules.web.tests import test_web
    test_web.ACTIVITY[session] = 'idle'
    # A resumed context already has enough turns to trigger the retired automatic offer.
    with Store('proj', module='dispatch').tables() as tx:
        for index in range(30):
            tx.insert('session_lines', {'session_id': session, 'work_id': work.id, 'name': f'turn:{index}',
                                        'kind': 'turn', 'text': 'end_turn', 'seq': index + 1})
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    requests = []
    page.on('request', lambda request: requests.append(request.url) if request.method == 'POST' else None)
    try:
        page.wait_for_function('() => window.metaform.loaded()')
        page.evaluate('''async ({work, session}) => {
            const {openHelpdesk} = await import('/page/app/dock/threads.js');
            openHelpdesk(work, 'My agent', '', session, 'system');
            await (await import('/page/app/dock/helpdesk.js')).drawHelpdesk();
        }''', {'work': work.id, 'session': session})
        page.wait_for_selector('#helpdesk:not([hidden])')
        assert page.locator('#helpdesk .embody').count() == 0
        # The old page-local "once" state restarted for each context. No new context may open selection.
        quiet = page.evaluate('''async () => {
            const {DOCK, EMBODY, paintAvatar, embodyRows} = await import('/page/app/dock/embody.js');
            const before = Date.now;
            try {
                Date.now = () => before() + 24 * 60 * 60 * 1000;
                for (let context = 0; context < 30; context++) {
                    paintAvatar(DOCK.target, {session_id: `context-${context}`});
                    if (EMBODY.open || embodyRows(DOCK.target).length) return false;
                }
                return true;
            } finally { Date.now = before; }
        }''')
        assert quiet
        # Even if the harness offers /mascot, the person's local command wins.
        page.evaluate('''async () => {
            const {DOCK} = await import('/page/app/dock/embody.js');
            DOCK.state = {...DOCK.state, commands: [{name: 'mascot'}]};
        }''')
        page.fill('#helpdesk .say', '/mas')
        page.wait_for_selector('#helpdesk .slash [role="option"]:has-text("/mascot")')
        page.fill('#helpdesk .say', '/mascot')
        page.press('#helpdesk .say', 'Enter')
        page.wait_for_selector('#helpdesk .embody')
        assert page.locator('#helpdesk .embody').count() == 1
        assert not any('/api/dispatch-message' in url or '/api/dispatch-start' in url for url in requests)
        page.click('#helpdesk .embody .notnow')
        page.wait_for_selector('#helpdesk .embody', state='detached')
        page.evaluate("async () => (await import('/page/app/dock/helpdesk.js')).drawHelpdesk()")
        assert page.locator('#helpdesk .embody').count() == 0
        page.fill('#helpdesk .say', '/mascot')
        page.press('#helpdesk .say', 'Enter')
        page.wait_for_selector('#helpdesk .embody')
        # A context transition closes a deliberately open picker rather than replaying it.
        assert page.evaluate('''async () => {
            const {DOCK, EMBODY, paintAvatar} = await import('/page/app/dock/embody.js');
            paintAvatar(DOCK.target, {session_id: 'next-context'});
            return EMBODY.open === null;
        }''')
        page.evaluate("async () => (await import('/page/app/dock/helpdesk.js')).drawHelpdesk()")
        page.fill('#helpdesk .say', '/mascot')
        page.press('#helpdesk .say', 'Enter')
        page.click('#helpdesk .embody .character:has(.name:text-is("seahorse"))')
        page.wait_for_selector('#helpdesk .embody', state='detached')
        page.wait_for_function('() => window.metaform.mascot().glyph === "seahorse"')
        from metaform import settings
        from metaform.modules.dispatch.tests.test_dispatch import eventually
        eventually(lambda: settings.value('web_mascot', mapped) == 'seahorse')
        page.reload()
        page.wait_for_function('() => window.metaform.loaded() && window.metaform.mascot().glyph === "seahorse"')
        assert page.locator('#helpdesk .embody').count() == 0
        assert not any('/api/dispatch-message' in url or '/api/dispatch-start' in url for url in requests)
        assert problems == []
    finally:
        page.close()
