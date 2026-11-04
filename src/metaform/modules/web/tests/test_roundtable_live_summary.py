"""The owner reads a live account by default and opens participant notes in a separate reading window."""
from urllib.parse import parse_qs, urlparse

import pytest

from metaform.modules.web.tests.test_web import browser, mapped, opened, started, web  # noqa: F401

pytestmark = [pytest.mark.kind('simulation'), pytest.mark.browser]


def test_live_account_is_default_updates_without_new_turns_and_survives_reload(run, web, mapped, browser):  # noqa: F811
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    snapshot = {'state': 'working', 'text': '', 'through_seq': 0, 'updated': None, 'error': None, 'permissions': []}
    controls = []

    def read_table(route):
        query = parse_qs(urlparse(route.request.url).query)
        if 'table' not in query:
            route.fulfill(json={'running': 'summary-fixture'})
        elif 'notes' in query:
            route.fulfill(json={'notes': []})
        else:
            route.fulfill(json={'events': [] if query.get('after') != ['0'] else [
                {'kind': 'turn', 'seq': 1, 'topic': 1, 'seat': 'Alpha', 'text': 'CRYPTIC_SOURCE_GATE_7'}],
                'latest': 1, 'live_summary': snapshot, 'status': {'table': 'summary-fixture',
                'topic': 'How should changes reach the page?', 'state': 'running', 'seats': []}})

    page.route('**/api/roundtable?*', read_table)
    page.route('**/api/roundtable-control', lambda route: (
        controls.append(route.request.post_data_json), route.fulfill(json={'table': 'summary-fixture', 'state': 'held'})))
    enter = "async () => (await import('/page/app/roundtable/stage.js')).openRoundtable()"
    refresh = '''async () => (await import('/page/app/roundtable/stage.js')).tableChange({
        kinds: ['roundtables', 'roundtables:summary-fixture']})'''
    page.evaluate(enter)
    summary = page.get_by_role('region', name='Haiku summary', exact=True)
    # A named section is a region in the browser accessibility tree.
    summary.wait_for()
    breakdown = page.get_by_role('button', name='Breakdown', exact=True)
    assert breakdown.is_visible() and breakdown.get_attribute('aria-pressed') == 'true'
    assert page.locator('.rt-transcript').is_hidden()
    assert page.locator('.rt-summary-text').text_content() == ''
    assert 'Haiku is preparing' in page.locator('.rt-summary-status').text_content()
    assert 'CRYPTIC_SOURCE_GATE_7' not in summary.text_content()
    comment = page.get_by_role('textbox', name='Discussion comment', exact=True)
    assert comment.is_visible() and comment.is_enabled()
    comment.fill('Explain how this affects the person waiting for an update.')
    page.get_by_role('button', name='Send comment', exact=True).click()
    page.wait_for_function('() => document.querySelector(".rt-discussion-comment").value === ""')
    assert controls[0]['table'] == 'summary-fixture' and controls[0]['action'] == 'comment'

    first = 'Alpha wants updates to reach the page immediately. Beta wants unrelated changes to cost no work.\n\n' \
            'They are deciding what each change message must contain. The owner can clarify the acceptable delay.'
    snapshot.update(state='ready', text=first, through_seq=1)
    page.evaluate(refresh)
    page.wait_for_function('text => document.querySelector(".rt-summary-text").textContent === text', arg=first)
    assert page.evaluate("async () => (await import('/page/app/roundtable/stage.js')).TABLE.seq") == 1
    page.get_by_role('button', name='Transcript', exact=True).click()
    assert page.locator('.rt-transcript').is_visible() and summary.is_hidden()
    second = 'They now agree to include the changed table and record ids in every update.\n\n' \
             'Beta is checking whether an update can be missed. That failure case remains open.'
    snapshot.update(text=second)
    page.evaluate(refresh)
    page.wait_for_function('text => document.querySelector(".rt-summary-text").textContent === text', arg=second)
    assert page.locator('.rt-transcript').is_visible(), 'An explicit transcript choice stays selected.'
    breakdown.click()
    assert breakdown.get_attribute('aria-pressed') == 'true'
    assert summary.is_visible() and page.locator('.rt-summary-text').text_content() == second

    page.reload()
    page.wait_for_function('() => window.metaform.loaded()')
    page.evaluate(enter)
    summary.wait_for()
    page.wait_for_function('text => document.querySelector(".rt-summary-text").textContent === text', arg=second)
    assert page.locator('.rt-transcript').is_hidden()
    assert page.get_by_role('button', name='Breakdown', exact=True).get_attribute('aria-pressed') == 'true'
    assert page.get_by_role('textbox', name='Discussion comment', exact=True).is_visible()
    snapshot.update(state='error', error='A technical transport failure.')
    page.evaluate(refresh)
    page.wait_for_function('() => document.querySelector(".rt-summary-status").textContent.includes("could not update")')
    assert page.locator('.rt-summary-text').text_content() == second
    assert 'A technical transport failure' not in summary.text_content()
    assert not problems
    page.close()


def test_notes_open_a_full_reading_window_and_offer_a_link_when_blocked(run, web, mapped, browser):  # noqa: F811
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    note = 'agents/shared decisions.md'

    def answer(route):
        query = parse_qs(urlparse(route.request.url).query)
        if 'note' in query:
            assert query['note'] == [note] and query['table'] == ['notes-fixture']
            route.fulfill(json={'text': '# Shared decisions\n\nThe agents agreed to preserve every contribution.', 'cut': False})
        elif 'notes' in query:
            route.fulfill(json={'notes': [{'path': note, 'bytes': 78}]})
        elif 'table' not in query:
            route.fulfill(json={'running': 'notes-fixture'})
        else:
            route.fulfill(json={'events': [], 'latest': 0, 'status': {
                'table': 'notes-fixture', 'topic': 'Keep readable documents', 'state': 'running', 'seats': []}})

    page.context.route('**/api/roundtable?*', answer)
    page.evaluate("async () => (await import('/page/app/roundtable/stage.js')).openRoundtable()")
    page.locator('.rt-notes-button').click()
    button = page.get_by_role('button', name=note, exact=True)
    with page.expect_popup() as opening:
        button.click()
    reading = opening.value
    reading.wait_for_selector('#note-status[data-state="ready"]')
    assert urlparse(reading.url).path == '/page/roundtable-note.html'
    assert reading.get_by_role('heading', name='Shared decisions', exact=True).is_visible()
    assert reading.evaluate('window.opener === null')
    assert reading.evaluate('window.innerWidth') >= 900
    assert page.locator('.rt-noteview').count() == 0
    page.evaluate('window.open = () => null')
    button.click()
    fallback = page.get_by_role('link', name='Open the note in a new tab', exact=True)
    assert fallback.is_visible() and fallback.get_attribute('target') == '_blank'
    assert parse_qs(urlparse(fallback.get_attribute('href')).query)['note'] == [note]
    assert not problems
    reading.close()
    page.close()
