"""Delayed starts and queued replies preserve the person's selected conversation."""
import pytest

from metaform.modules.web.tests.test_web import browser, mapped, opened, started, web  # noqa: F401

pytestmark = [pytest.mark.kind('simulation'), pytest.mark.browser]


@pytest.mark.parametrize('start', ['talk', 'system'])
def test_late_start_keeps_selected_tab_and_queued_recipient(run, web, mapped, browser, start):  # noqa: F811
    run('enable', 'dispatch')
    started(run)
    page, problems, _ = opened(browser, web)
    failures = []
    page.on('response', lambda response: failures.append((response.url, response.status))
            if response.status >= 400 else None)
    page.wait_for_function('() => window.metaform.loaded()')
    resumed = False
    sent = []
    pending = []
    first = 'helper-original' if start == 'talk' else 'conversation-system'
    second = 'helper-other'

    def sessions(route):
        rows = [{'work_id': first, 'session_id': 's-original', 'agent': 'codex',
                 'state': 'running' if resumed else 'ended', 'activity': 'idle', 'seq': 1},
                {'work_id': second, 'session_id': 's-other', 'agent': 'codex', 'state': 'running',
                 'activity': 'idle', 'seq': 2}]
        route.fulfill(json={'sessions': rows, 'states': {
            's-original': {'role': 'helper' if start == 'talk' else 'system', 'brief': 'Original investigation'},
            's-other': {'role': 'helper', 'brief': 'Other investigation'}}, 'lines': [
            {'session_id': row['session_id'], 'name': 'answer', 'kind': 'agent_message_chunk',
             'text': row['session_id'], 'seq': 1} for row in rows]})

    page.route('**/api/dispatch-sessions?*', sessions)
    page.route('**/api/dispatch-spend?*', lambda route: route.fulfill(json={'ticket': None}))
    page.route('**/api/talk' if start == 'talk' else '**/api/system-chat', lambda route: pending.append(route))

    def message(route):
        sent.append(route.request.post_data_json)
        route.fulfill(json={'sent': True})

    page.route('**/api/dispatch-message', message)
    page.evaluate('''async ({first, second, start}) => {
        const {openHelpdesk} = await import('/page/app/dock/threads.js');
        const {DOCK} = await import('/page/app/dock/embody.js');
        openHelpdesk(second, 'Other helper', '', 's-other', 'agent');
        openHelpdesk(first, 'Original helper', '', 's-original', start === 'system' ? 'system' : 'agent');
        window.testDock = DOCK;
    }''', {'first': first, 'second': second, 'start': start})
    page.wait_for_function('() => window.testDock.session === "s-original" && window.testDock.state !== null'
                           ' && !window.testDock.live')
    if start == 'talk':
        page.locator('#helpdesk .say').fill('Continue the original investigation')
        with page.expect_request('**/api/talk'):
            page.locator('#helpdesk .say').press('Enter')
    else:
        with page.expect_request('**/api/system-chat'):
            page.evaluate("() => { import('/page/app/dock/commands.js').then(m => m.callSystem()); }")
    page.evaluate('''async () => {
        const {showChat} = await import('/page/app/dock/threads.js');
        showChat(window.testDock.chats.find(chat => chat.session === 's-other'));
    }''')
    page.wait_for_function('() => window.testDock.session === "s-other" && window.testDock.live')
    assert sent == [], 'Queued text must not go to the newly selected agent.'
    assert not page.locator('#helpdesk .log').get_by_text('Continue the original investigation').count()
    resumed = True
    pending[0].fulfill(json={'work_id': first, 'session_id': 's-original', 'state': 'starting', 'conversation': True})
    page.wait_for_function('() => !window.testDock.calling && !window.testDock.talking')
    assert page.evaluate('window.testDock.session') == 's-other'
    assert page.evaluate('window.testDock.chats.length') == 2
    if start == 'talk':
        page.evaluate('''async () => {
            const {showChat} = await import('/page/app/dock/threads.js');
            showChat(window.testDock.chats.find(chat => chat.session === 's-original'));
        }''')
        page.wait_for_function('() => window.testDock.queue.some(item => item.state === "sent")')
        assert len(sent) == 1
        assert sent[0]['work_id'] == first and sent[0]['session'] == 's-original'
        assert 'Continue the original investigation' in sent[0]['text']
    assert problems == [], failures
    page.close()


@pytest.mark.req('VIEW-002')
@pytest.mark.parametrize('hidden_on_update', [False, True])
def test_update_preserves_workspace_when_browser_tab_is_hidden(run, web, mapped, browser, hidden_on_update):  # noqa: F811
    run('set', '--web-notices')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.route('**/api/dispatch-sessions?*', lambda route: route.fulfill(json={
        'sessions': [{'work_id': 'conversation-original', 'session_id': 's-original',
                      'state': 'running', 'agent': 'codex', 'activity': 'idle'}],
        'states': {'s-original': {'role': 'system'}},
        'lines': [{'session_id': 's-original', 'name': 'answer', 'kind': 'agent_message_chunk',
                   'text': 'Retained conversation', 'seq': 1}]}))
    page.evaluate('''async () => {
        const {openHelpdesk} = await import('/page/app/dock/threads.js');
        const {DOCK} = await import('/page/app/dock/embody.js');
        openHelpdesk('conversation-original', 'Original conversation', '', 's-original', 'system');
        window.testDock = DOCK;
        window.testHidden = false;
        Object.defineProperty(document, 'hidden', {get: () => window.testHidden, configurable: true});
        const Source = window.EventSource;
        window.EventSource = class extends Source {
            constructor(...args) { super(...args); window.testEvents = this; }
        };
        (await import('/page/app/live/ops.js')).listen();
    }''')
    page.get_by_text('Retained conversation', exact=True).wait_for()
    page.locator('#helpdesk .say').fill('Unsent message stays here')
    page.click('#boardBtn')
    page.wait_for_selector('#board:not([hidden])')
    navigations = []
    page.on('framenavigated', lambda frame: navigations.append(frame.url) if frame == page.main_frame else None)
    page.evaluate('(hidden) => { window.testHidden = hidden; }', hidden_on_update)
    page.evaluate('''() => window.testEvents.onmessage(new MessageEvent('message', {
        data: JSON.stringify({topic: 'hello', payload: {code: 'changed-for-visibility-check'}})
    }))''')
    page.locator('.banner[data-key="updated"]').wait_for(state='attached')
    page.evaluate('''() => {
        window.testHidden = true;
        document.dispatchEvent(new Event('visibilitychange'));
    }''')
    # Allow a navigation requested by the visibility event to commit before checking preserved state.
    page.wait_for_timeout(250)
    assert navigations == [], 'An update must not reload a hidden browser tab.'
    page.evaluate('''() => {
        window.testHidden = false;
        document.dispatchEvent(new Event('visibilitychange'));
    }''')
    assert page.evaluate('window.testDock.session') == 's-original'
    assert page.locator('#helpdesk .say').input_value() == 'Unsent message stays here'
    assert page.locator('#helpdesk').is_visible()
    assert page.locator('#board').is_visible()
    assert page.get_by_text('Retained conversation', exact=True).is_visible()
    # The person's explicit Reload action still loads the updated page.
    with page.expect_navigation():
        page.locator('.banner[data-key="updated"]').get_by_role('button', name='Reload', exact=True).click()
    assert len(navigations) == 1
    assert problems == []
    page.close()
