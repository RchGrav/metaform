"""Original turns stay readable and participant notes open in a separate reading window."""
from urllib.parse import parse_qs, urlparse

import pytest

from metaform.modules.web.tests.test_web import browser, mapped, opened, started, web  # noqa: F401

pytestmark = [pytest.mark.kind('simulation'), pytest.mark.browser]


def test_original_turns_are_default_and_saved_observer_snapshots_cannot_replace_them(run, web, mapped, browser):  # noqa: F811
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    snapshot = {'state': 'working', 'text': '', 'through_seq': 0, 'permissions': []}
    controls = []

    def read_table(route):
        query = parse_qs(urlparse(route.request.url).query)
        if 'table' not in query:
            route.fulfill(json={'running': 'summary-fixture'})
        elif 'notes' in query:
            route.fulfill(json={'notes': []})
        else:
            route.fulfill(json={'events': [] if query.get('after') != ['0'] else [
                {'kind': 'turn', 'seq': 1, 'message_id': 'R1-1', 'topic': 1, 'seat': 'Alpha',
                 'text': 'Keep the original contribution and its references.'}],
                'latest': 1, 'live_summary': snapshot, 'status': {'table': 'summary-fixture',
                'topic': 'How should changes reach the page?', 'state': 'running', 'seats': []}})

    page.route('**/api/roundtable?*', read_table)
    page.route('**/api/roundtable-control', lambda route: (
        controls.append(route.request.post_data_json), route.fulfill(json={'table': 'summary-fixture', 'state': 'held'})))
    enter = "async () => (await import('/page/app/roundtable/stage.js')).openRoundtable()"
    refresh = """async () => (await import('/page/app/roundtable/stage.js')).tableChange({
        kinds: ['roundtables', 'roundtables:summary-fixture']})"""
    page.evaluate(enter)
    transcript = page.get_by_role('list', name='The transcript', exact=True)
    assert transcript.is_visible()
    assert transcript.get_by_role('link', name='R1-1', exact=True).is_visible()
    assert 'Keep the original contribution and its references.' in transcript.inner_text()
    assert page.get_by_role('button', name='Breakdown', exact=True).count() == 0
    assert page.get_by_role('region', name='Haiku summary', exact=True).count() == 0
    comment = page.get_by_role('textbox', name='Discussion comment', exact=True)
    assert comment.is_visible() and comment.is_enabled()
    comment.fill('Keep this contribution available.')
    page.get_by_role('button', name='Send comment', exact=True).click()
    page.wait_for_function('() => document.querySelector(".rt-discussion-comment").value === ""')
    assert controls[0]['table'] == 'summary-fixture' and controls[0]['action'] == 'comment'

    snapshot.update(state='ready', text='A previously saved automatic account.', through_seq=1)
    page.evaluate(refresh)
    page.wait_for_function("async () => !(await import('/page/app/roundtable/stage.js')).TABLE.busy")
    assert transcript.locator('li').count() == 1
    assert snapshot['text'] not in transcript.inner_text()
    page.reload()
    page.wait_for_function('() => window.metaform.loaded()')
    page.evaluate(enter)
    transcript.get_by_role('link', name='R1-1', exact=True).wait_for()
    assert transcript.is_visible() and transcript.locator('li').count() == 1
    assert 'Keep the original contribution and its references.' in transcript.inner_text()
    assert page.get_by_role('textbox', name='Discussion comment', exact=True).is_visible()
    snapshot.update(state='error', error='An obsolete observer failure.')
    page.evaluate(refresh)
    page.wait_for_function("async () => !(await import('/page/app/roundtable/stage.js')).TABLE.busy")
    assert transcript.is_visible() and 'An obsolete observer failure.' not in transcript.inner_text()
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
