"""Roundtable notes are readable documents in their own browser page, with inert untrusted Markdown."""
from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlparse

import pytest

from metaform.modules.web.tests.test_web import browser, started, web  # noqa: F401

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.browser]


def note_url(port, **changes):
    query = {'project': 'proj', 'table': 'saved-table', 'note': 'agents/session-ledger.md', **changes}
    return f'http://127.0.0.1:{port}/page/roundtable-note.html?{urlencode(query)}'


def test_note_reader_renders_ledger_markdown_at_readable_size_without_loading_untrusted_content(
        run, web, browser, tmp_path):  # noqa: F811 -- shared browser fixtures
    started(run)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    problems, remote, reads = [], [], []
    page.on('pageerror', lambda error: problems.append(str(error)))
    page.on('console', lambda message: problems.append(message.text) if message.type == 'error' else None)
    page.on('request', lambda sent: remote.append(sent.url)
            if not sent.url.startswith(f'http://127.0.0.1:{web}/') else None)
    long_word = 'ledger-entry-' * 150
    text = ('# Session ledger\n\nThe **current** record stays readable.\n\n'
            '| Claim | Evidence |\n| :--- | ---: |\n| Keep every turn | Saved in the ledger |\n\n'
            '- First observation\n- Second observation\n\n'
            '```python\nprint("recorded")\n' + long_word + '\n```\n\n'
            '<script>window.noteRan = true</script>\n\n'
            '<img src="https://example.invalid/raw-image" onerror="window.noteRan = true">\n\n'
            '![Evidence image](https://example.invalid/markdown-image)\n\n'
            '[Safe reference](https://example.com/notes) '
            '[Unsafe script](javascript:window.noteRan=true) '
            '[Unsafe data](data:text/html,hello) '
            '[Local file](file:///etc/passwd) [Relative note](other.md)\n\n'
            + '\n\n'.join(f'Observation {number}: {long_word}' for number in range(40)))

    def read(route):
        reads.append(parse_qs(urlparse(route.request.url).query))
        route.fulfill(json={'path': 'agents/session-ledger.md', 'text': text, 'cut': False})

    page.route('**/api/roundtable?*', read)
    page.goto(note_url(web))
    page.locator('#note-status[data-state="ready"]').wait_for()
    content = page.locator('#note-content')
    assert content.get_by_role('heading', name='Session ledger', exact=True).is_visible()
    assert content.get_by_role('table').is_visible()
    assert content.locator('tbody tr').inner_text() == 'Keep every turn\tSaved in the ledger'
    assert content.locator('ul li').all_text_contents() == ['First observation', 'Second observation']
    assert 'print("recorded")' in content.locator('pre code').inner_text()
    assert content.locator('pre').is_visible()
    assert page.locator('#note-title').inner_text() == 'agents/session-ledger.md'
    assert page.title() == 'agents/session-ledger.md · Roundtable note'
    assert content.bounding_box()['width'] >= 1000
    layout = page.evaluate('''() => ({
        font: parseFloat(getComputedStyle(document.querySelector('main')).fontSize),
        height: document.scrollingElement.scrollHeight, viewport: innerHeight,
        width: document.scrollingElement.scrollWidth, viewportWidth: innerWidth,
        wrap: getComputedStyle(document.querySelector('pre')).whiteSpace,
        codeWidth: document.querySelector('pre').scrollWidth, codeBox: document.querySelector('pre').clientWidth
    })''')
    assert layout['font'] >= 16 and layout['height'] > layout['viewport'] * 2
    assert layout['width'] <= layout['viewportWidth']
    assert layout['wrap'] == 'pre-wrap' and layout['codeWidth'] <= layout['codeBox']
    assert content.locator('script, img, iframe, object, embed').count() == 0
    assert page.evaluate('window.noteRan') is None
    assert content.get_by_text('[Image: Evidence image]', exact=True).count() == 1
    assert content.locator('a').count() == 1
    safe = content.get_by_role('link', name='Safe reference', exact=True)
    assert safe.get_attribute('href') == 'https://example.com/notes'
    assert safe.get_attribute('rel') == 'noopener noreferrer'
    assert reads == [{'project': ['proj'], 'table': ['saved-table'], 'note': ['agents/session-ledger.md']}]
    page.screenshot(path=str(tmp_path / 'roundtable-note-reader.png'))
    assert not remote and not problems
    page.close()


def test_note_reader_refreshes_on_request_and_keeps_previous_content_when_a_refresh_fails(
        run, web, browser):  # noqa: F811 -- shared browser fixtures
    started(run)
    page = browser.new_page(viewport={'width': 1280, 'height': 900})
    reads = []
    answers = [(200, {'path': 'ledger.md', 'text': '# Partial ledger\n\nFirst entry.', 'cut': True}),
               (200, {'path': 'ledger.md', 'text': '# Updated ledger\n\nSecond entry.', 'cut': False}),
               (404, {'error': '<script>Missing note</script>'})]

    def read(route):
        reads.append(route.request.url)
        status, body = answers.pop(0)
        route.fulfill(status=status, json=body)

    page.route('**/api/roundtable?*', read)
    page.goto(note_url(web, note='ledger.md'))
    page.locator('#note-status[data-state="cut"]').wait_for()
    assert 'first 1 MiB' in page.get_by_role('status').inner_text()
    page.get_by_role('button', name='Refresh', exact=True).click()
    page.locator('#note-status[data-state="ready"]').wait_for()
    assert page.get_by_role('heading', name='Updated ledger', exact=True).is_visible()
    assert not page.get_by_role('heading', name='Partial ledger', exact=True).count()
    page.get_by_role('button', name='Refresh', exact=True).click()
    page.locator('#note-status[data-state="error"]').wait_for()
    assert '<script>Missing note</script>' in page.get_by_role('status').inner_text()
    assert 'previous version is still shown' in page.get_by_role('status').inner_text()
    assert page.get_by_role('heading', name='Updated ledger', exact=True).is_visible()
    assert page.locator('script:not([src])').count() == 0
    assert page.get_by_role('button', name='Refresh', exact=True).is_enabled()
    assert len(reads) == 3
    page.close()
