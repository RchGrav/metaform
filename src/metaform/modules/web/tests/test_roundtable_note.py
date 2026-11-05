"""Roundtable notes are readable documents in their own browser page, with inert untrusted Markdown."""
from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlparse

import pytest

from metaform.modules.web.tests.test_web import browser, mapped, opened, started, web  # noqa: F401

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
    assert content.locator('a').count() == 2
    safe = content.get_by_role('link', name='Safe reference', exact=True)
    assert safe.get_attribute('href') == 'https://example.com/notes'
    assert safe.get_attribute('rel') == 'noopener noreferrer'
    sibling = content.get_by_role('link', name='Relative note', exact=True)
    assert parse_qs(urlparse(sibling.get_attribute('href')).query)['note'] == ['agents/other.md']
    assert reads == [{'project': ['proj'], 'table': ['saved-table'], 'note': ['agents/session-ledger.md']}]
    page.screenshot(path=str(tmp_path / 'roundtable-note-reader.png'))
    assert not remote and not problems
    page.close()


def test_reference_reader_opens_full_messages_file_lines_and_safe_search_links(run, web, browser):  # noqa: F811
    started(run)
    page = browser.new_page(viewport={'width': 1360, 'height': 960})
    reads, problems = [], []
    page.on('pageerror', lambda error: problems.append(str(error)))
    command = 'rg -n -F "retained decision" src/engine.py'

    def reference(route):
        query = parse_qs(urlparse(route.request.url).query)
        reads.append(query)
        target = query['reference'][0]
        if target == 'R1-1':
            route.fulfill(json={'path': 'R1-1', 'text': '# Cited contribution\n\n'
                                'Read R2-3 and [the implementation](src/engine.py:42).\n\n'
                                f'`{command}`\n\n' + 'The complete retained contribution. ' * 300,
                                'cut': False})
        elif target == 'R2-3':
            route.fulfill(json={'path': 'R2-3', 'text': 'The complete earlier contribution.', 'cut': False})
        else:
            route.fulfill(json={'path': 'src/engine.py', 'text': 'def retained():\n    return "retained decision"\n',
                                'line': 42, 'cut': False})

    page.context.route('**/api/roundtable?*', reference)
    page.goto(note_url(web, note='', reference='R1-1'))
    page.locator('#note-status[data-state="ready"]').wait_for()
    content = page.locator('#note-content')
    assert content.get_by_role('heading', name='Cited contribution').is_visible()
    assert content.inner_text().count('The complete retained contribution.') == 300
    assert content.bounding_box()['width'] >= 1000
    with page.expect_popup() as cited:
        content.get_by_role('link', name='R2-3', exact=True).click()
    earlier = cited.value
    earlier.locator('#note-status[data-state="ready"]').wait_for()
    assert earlier.locator('#note-content').inner_text() == 'The complete earlier contribution.'
    earlier.close()
    with page.expect_popup() as implementation:
        content.get_by_role('link', name='the implementation', exact=True).click()
    source = implementation.value
    source.locator('#note-status[data-state="ready"]').wait_for()
    assert source.locator('#note-content pre').inner_text() == 'def retained():\n    return "retained decision"\n'
    assert source.locator('#note-location').inner_text().endswith('Line 42')
    source.close()
    with page.expect_popup() as searched:
        content.get_by_role('link', name=command, exact=True).click()
    search = searched.value
    search.locator('#note-status[data-state="ready"]').wait_for()
    assert 'retained decision' in search.locator('#note-content').inner_text()
    search.close()
    assert [one['reference'][0] for one in reads] == ['R1-1', 'R2-3', 'src/engine.py:42', command]
    assert all(one['project'] == ['proj'] and one['table'] == ['saved-table'] for one in reads)
    assert not problems
    page.close()


def test_stage_shows_clickable_original_turns_before_any_generated_account(run, web, mapped, browser):  # noqa: F811
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    references = []

    def read(route):
        query = parse_qs(urlparse(route.request.url).query)
        if query.get('reference'):
            references.append(query)
            return route.fulfill(json={'path': query['reference'][0], 'text': 'The complete cited contribution.',
                                       'cut': False})
        if query.get('notes'):
            return route.fulfill(json={'notes': []})
        events = [] if int(query.get('after', ['0'])[0]) else [
            {'kind': 'turn', 'seq': 1, 'message_id': 'R1-1', 'seat': 'Alpha', 'outcome': 'kept',
             'text': 'Read R1-2 and [source](src/engine.py:42).'}]
        route.fulfill(json={'events': events, 'latest': 1,
                            'status': {'table': 'cited-table', 'topic': 'Citations', 'state': 'running', 'seats': []}})

    page.context.route('**/api/roundtable?*', read)
    page.evaluate('''async () => {
        const stage = await import('/page/app/roundtable/stage.js');
        stage.TABLE.id = 'cited-table';
        stage.TABLE.kind = 'roundtables:cited-table';
        await stage.openRoundtable();
    }''')
    transcript = page.get_by_role('list', name='The transcript', exact=True)
    assert transcript.is_visible()
    assert transcript.locator('b').inner_text() == 'R1-1 · Alpha'
    assert transcript.get_by_role('link').all_text_contents() == ['R1-1', 'R1-2', 'source']
    assert page.get_by_role('button', name='Breakdown', exact=True).count() == 0
    assert page.get_by_label('Haiku summary', exact=True).count() == 0
    with page.expect_popup() as cited:
        transcript.get_by_role('link', name='R1-2', exact=True).click()
    reader = cited.value
    reader.locator('#note-status[data-state="ready"]').wait_for()
    assert reader.locator('#note-content').inner_text() == 'The complete cited contribution.'
    assert references[0]['reference'] == ['R1-2'] and references[0]['table'] == ['cited-table']
    assert not problems
    reader.close()
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
