"""Roundtable participants survive reloads and explicit saving without starting agents."""
import pytest

from metaform.modules.web.tests.test_web import api, browser, mapped, opened, started, web  # noqa: F401

pytestmark = [pytest.mark.kind('simulation'), pytest.mark.browser]


def test_saved_participants_and_last_lineup_stay_in_project(run, web, mapped, browser):  # noqa: F811
    run('enable', 'roundtables', cwd=mapped)
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    opens = []

    def refuse_open(route):
        opens.append(route.request.post_data_json)
        route.fulfill(status=400, json={'error': 'Deliberate test refusal. No agents started.'})

    page.route('**/api/roundtable-open', refuse_open)
    open_form = "async () => (await import('/page/app/roundtable/stage.js')).openRoundtable(true)"
    page.evaluate(open_form)
    page.locator('.rt-pick').first.wait_for()
    while page.get_by_role('button', name='Remove this seat', exact=True).count():
        page.get_by_role('button', name='Remove this seat', exact=True).first.click()
    saved = ['test/one', 'test/one', 'test/two']
    for seat in saved:
        page.get_by_role('button', name='Add a seat', exact=True).click()
        row = page.locator('.rt-pick').last
        row.get_by_role('combobox', name='Agent', exact=True).select_option('')
        row.get_by_role('textbox', name='OpenRouter model id', exact=True).fill(seat)
    with page.expect_response(lambda response: response.url.endswith('/api/settings')
                             and response.request.method == 'POST') as response:
        page.get_by_role('button', name='Save participants', exact=True).click()
    assert response.value.status == 200
    assert api(web, '/api/roundtable?project=proj')[1]['seats'] == saved
    assert not opens

    page.locator('.rt-pick').nth(1).get_by_role('button', name='Remove this seat', exact=True).click()
    fields = page.get_by_role('textbox', name='OpenRouter model id', exact=True)
    fields.nth(0).fill('test/two')
    fields.nth(1).fill('test/one')
    last = ['test/two', 'test/one']
    page.get_by_role('textbox', name='Your question to the table', exact=True).fill('Remember this lineup.')
    with page.expect_response('**/api/roundtable-open'):
        page.get_by_role('button', name='Start', exact=True).click()
    assert opens[0]['seats'] == last
    page.reload()
    page.wait_for_function('() => window.metaform.loaded()')
    page.evaluate(open_form)
    page.wait_for_function('() => document.querySelectorAll(".rt-model input").length === 2')
    assert page.locator('.rt-model input').evaluate_all('els => els.map(el => el.value)') == last

    fresh, fresh_problems, _ = opened(browser, web)
    fresh.wait_for_function('() => window.metaform.loaded()')
    fresh.evaluate(open_form)
    fresh.wait_for_function('() => document.querySelectorAll(".rt-model input").length === 3')
    assert fresh.locator('.rt-model input').evaluate_all('els => els.map(el => el.value)') == saved
    fresh.close()

    page.route('**/api/roundtable?project=other', lambda route: route.fulfill(json={'seats': ['test/other']}))
    for project, expected in [('other', ['test/other']), ('proj', last)]:
        page.evaluate('''async project => {
            const {S} = await import('/page/app/core/reads.js');
            S.project = project;
            await (await import('/page/app/roundtable/stage.js')).openRoundtable(true);
        }''', project)
        assert page.locator('.rt-model input').evaluate_all('els => els.map(el => el.value)') == expected
    assert all('400 (Bad Request)' in problem for problem in problems)
    assert not fresh_problems
    page.close()
