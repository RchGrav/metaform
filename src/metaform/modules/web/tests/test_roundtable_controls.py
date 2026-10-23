"""Chair controls keep the existing table and remain distinct from plan decisions."""
import pytest

from metaform.modules.web import server
from metaform.modules.web.tests.test_web import _Handler, browser, mapped, opened, started, web  # noqa: F401

pytestmark = pytest.mark.kind('simulation')


@pytest.mark.parametrize('action', ['hold', 'continue', 'comment', 'advance'])
def test_discussion_controls_address_existing_table(monkeypatch, action):
    calls = []
    monkeypatch.setattr(server, 'module_verb', lambda given, module, verb, nouns:
                        calls.append((module, verb, nouns)) or {'table': 'existing', 'state': 'held'})
    handler = _Handler()
    server.Handler.roundtable_control(handler, {'table': 'existing', 'action': action, 'text': ' Add this. '})
    expected = {'table': 'existing', **({'text': 'Add this.'} if action == 'comment' else {})}
    assert calls == [('roundtables', action, expected)]
    assert handler.answers == [(200, {'table': 'existing', 'state': 'held'})]


@pytest.mark.parametrize('given', [
    {'table': 'existing', 'action': 'open'},
    {'table': 'existing', 'action': 'end'},
    {'table': '', 'action': 'hold'},
    {'table': 'existing', 'action': 'comment', 'text': ' '},
    {'table': 'existing', 'action': 'comment', 'text': None},
])
def test_invalid_control_does_not_reach_engine(monkeypatch, given):
    monkeypatch.setattr(server, 'module_verb', lambda *args: pytest.fail('Invalid controls must not reach engine.'))
    handler = _Handler()
    server.Handler.roundtable_control(handler, given)
    assert handler.answers[0][0] == 400


def test_chair_controls_require_dispatch_capability():
    assert server.route_class('POST', '/api/roundtable-control') == 'dispatch'


@pytest.mark.browser
def test_setup_can_disable_judging_without_starting_agents(run, web, mapped, browser):  # noqa: F811
    run('enable', 'roundtables', cwd=mapped)
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    calls = []
    page.route('**/api/roundtable-open', lambda route: (
        calls.append(route.request.post_data_json), route.fulfill(json={'table': 'fixture'})))
    page.route('**/api/roundtable?*', lambda route: route.fulfill(json={
        'seats': ['claude/haiku'], 'judging': False, 'events': [], 'latest': 0}))
    page.evaluate("async () => (await import('/page/app/roundtable/stage.js')).openRoundtable(true)")
    page.locator('.rt-pick').first.wait_for()
    judging = page.get_by_role('checkbox', name='Judge novelty with Jev', exact=True)
    assert not judging.is_checked()
    page.get_by_role('textbox', name='Your question to the table', exact=True).fill('Discuss without judging.')
    page.get_by_role('button', name='Start', exact=True).click()
    page.wait_for_function('() => document.querySelector(".rt-setup").hidden')
    assert len(calls) == 1 and calls[0]['judging'] is False
    assert not problems
    page.close()


@pytest.mark.browser
def test_hold_allows_comments_and_continue_keeps_table(run, web, mapped, browser):  # noqa: F811
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.route('**/api/roundtable?*', lambda route: route.fulfill(json={
        'events': [], 'latest': 0,
        'status': {'table': 'existing', 'topic': 'Keep this discussion', 'state': 'running', 'seats': []}}))
    calls = []
    fail_comment = True

    def control(route):
        nonlocal fail_comment
        given = route.request.post_data_json
        calls.append(given)
        if given['action'] == 'comment' and fail_comment:
            fail_comment = False
            route.fulfill(status=503, json={'error': 'Connection lost. Try again.'})
        else:
            route.fulfill(json={'table': 'existing', 'state': 'running' if given['action'] == 'continue' else 'held'})

    page.route('**/api/roundtable-control', control)
    page.evaluate('''async () => {
        const stage = await import('/page/app/roundtable/stage.js');
        stage.TABLE.id = 'existing';
        stage.TABLE.kind = 'roundtables:existing';
        await stage.openRoundtable();
    }''')
    page.get_by_role('button', name='Hold', exact=True).click()
    page.get_by_role('button', name='Continue', exact=True).wait_for()
    comment = page.get_by_role('textbox', name='Discussion comment', exact=True)
    comment.fill('Consider this before continuing.')
    page.get_by_role('button', name='Send comment', exact=True).click()
    page.wait_for_function('() => !document.querySelector(".rt-discussion-comment").disabled')
    assert comment.input_value() == 'Consider this before continuing.'
    assert page.get_by_role('button', name='Continue', exact=True).is_visible()
    page.get_by_role('button', name='Send comment', exact=True).click()
    page.wait_for_function('() => document.querySelector(".rt-discussion-comment").value === ""')
    assert page.get_by_role('button', name='Continue', exact=True).is_visible()
    page.get_by_role('button', name='Continue', exact=True).click()
    page.get_by_role('button', name='Hold', exact=True).wait_for()
    page.get_by_role('button', name='End discussion', exact=True).click()
    page.wait_for_function('() => !document.querySelector(".rt-end-discussion").disabled')
    assert [one['action'] for one in calls] == ['hold', 'comment', 'comment', 'continue', 'advance']
    assert all(one['table'] == 'existing' for one in calls)
    assert calls[1]['text'] == calls[2]['text'] == 'Consider this before continuing.'
    assert all('503 (Service Unavailable)' in problem for problem in problems)
    page.close()


@pytest.mark.browser
def test_completed_discussion_continues_inline_preserving_transcript(run, web, mapped, browser):  # noqa: F811
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.route('**/api/roundtable?*', lambda route: route.fulfill(json={
        'events': [{'kind': 'turn', 'seq': 1, 'seat': 'Haiku', 'text': 'Earlier contribution.'},
                   {'kind': 'turn', 'seq': 2, 'seat': 'Context handoff', 'outcome': 'handoff',
                    'text': 'Context handoff completed.'}], 'latest': 2,
        'status': {'table': 'existing', 'topic': 'Keep this discussion', 'state': 'ended',
                   'answer': 'Saved summary.', 'seats': []}}))
    calls = []
    page.route('**/api/roundtable-control', lambda route: (
        calls.append(route.request.post_data_json), route.fulfill(json={'table': 'existing', 'state': 'running'})))
    page.evaluate('''async () => {
        const stage = await import('/page/app/roundtable/stage.js');
        stage.TABLE.id = 'existing';
        stage.TABLE.kind = 'roundtables:existing';
        await stage.openRoundtable();
    }''')
    page.locator('.rt-transcript').get_by_text('Context handoff completed.').wait_for()
    page.get_by_role('button', name='Continue discussion', exact=True).click()
    page.get_by_role('button', name='Hold', exact=True).wait_for()
    assert [(one['project'], one['table'], one['action']) for one in calls] == [('proj', 'existing', 'continue')]
    assert page.locator('.rt-transcript').get_by_text('Earlier contribution.').is_visible()
    assert page.get_by_text('Saved summary.', exact=True).is_visible()
    assert not problems
    page.close()
