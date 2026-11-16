"""Advertised worker Fast choices persist without launching an inference session."""
import shlex

import pytest

from metaform import settings
from metaform.data import Store
from metaform.modules.web.tests.test_hold_controls import board_page
from metaform.modules.web.tests.test_ticket_detail import (  # noqa: F401
    browser,
    mapped,
    post,
    threaded,
    ticket,
    web,
)

pytestmark = [pytest.mark.kind('simulation'), pytest.mark.browser, pytest.mark.req('BASE-066')]


def catalog(folder, fast_type='boolean'):
    """Codex's record as dispatch keeps it, asked with the start command this home gives it, so nothing asks again."""
    options = [
        {'id': 'model', 'category': 'model', 'type': 'select', 'current': 'gpt-6',
         'options': [{'value': 'gpt-6', 'name': 'GPT 6'}]},
    ]
    if fast_type:
        options.append({'id': 'fast-mode', 'name': 'Fast mode', 'category': 'model_config',
                        'type': fast_type, 'current': False, 'options': []})
    from metaform.modules.dispatch import argv
    from metaform.modules.dispatch import offered as harness_offered
    command = shlex.join(argv(settings.value('dispatch_codex', folder)))
    harness_offered.keep('codex', {'state': 'ready', 'version': '1', 'name': 'Codex', 'command': command,
                                   'seen': '2026-10-21T00:00:00Z', 'settings': options})


def ticket_response(response):
    return '/api/ticket' in response.url and response.request.method == 'POST'


def open_fast(page, work):
    card = page.locator(f'#board .card[data-id="{work.id}"]')
    settings_box = card.locator('.ticket-settings')
    if settings_box.get_attribute('open') is None:
        settings_box.locator(':scope > summary').click()
    return card.locator('select.fast')


def test_fast_ticket_inherits_and_persists_on_off_after_reopening(run, web, mapped, browser):  # noqa: F811
    run('enable', 'dispatch')
    catalog(mapped)
    settings.put('dispatch_codex_fast', 'true', mapped)
    work = ticket()
    assert post(web, work_id=work.id, agent='codex')[0] == 200
    page = board_page(browser, web)
    try:
        fast = open_fast(page, work)
        fast.locator('option[value="true"]').wait_for(state='attached')
        assert fast.is_enabled()
        assert fast.input_value() == ''
        assert fast.locator('option[value=""]').inner_text() == 'Project setting: On'
        assert fast.locator('option').all_text_contents() == ['Project setting: On', 'On', 'Off']
        for choice in ('true', 'false'):
            with page.expect_response(ticket_response) as changed:
                fast.select_option(choice)
            assert changed.value.status == 200, changed.value.text()
            assert changed.value.json()['results'][0]['map']['fast'] == choice
            fast = open_fast(page, work)
            fast.locator(f'option[value="{choice}"]:checked').wait_for(state='attached')
        assert settings.value('dispatch_codex_fast', mapped) == 'true'
        page.reload()
        page.wait_for_function('() => window.metaform?.loaded()')
        page.evaluate("async () => { document.querySelector('#board').hidden = false; "
                      "await (await import('/page/app/board/board.js')).renderBoard(); }")
        fast = open_fast(page, work)
        fast.locator('option[value="false"]:checked').wait_for(state='attached')
        with page.expect_response(ticket_response) as changed:
            fast.select_option('')
        assert changed.value.status == 200, changed.value.text()
        assert changed.value.json()['results'][0]['map'].get('fast') is None
        assert not Store('proj').ticket(work.id).work.taken
    finally:
        page.close()


@pytest.mark.parametrize('fast_type', [None, 'select'])
def test_fast_unavailable_without_advertised_boolean(run, web, mapped, browser, fast_type):  # noqa: F811
    run('enable', 'dispatch')
    catalog(mapped, fast_type)
    work = ticket()
    assert post(web, work_id=work.id, agent='codex')[0] == 200
    page = board_page(browser, web)
    try:
        fast = open_fast(page, work)
        fast.locator('option').filter(has_text='Unavailable').wait_for(state='attached')
        assert fast.is_disabled()
        assert fast.get_attribute('title') == 'This agent does not advertise Fast mode.'
        assert fast.locator('option[value="true"]').count() == 0
    finally:
        page.close()


def test_project_fast_default_off_persists_in_settings_picker(run, web, mapped, browser):  # noqa: F811
    run('enable', 'dispatch')
    catalog(mapped)
    page = board_page(browser, web)
    try:
        page.evaluate("async () => { await (await import('/page/app/settings/screen.js')).openSettings(); }")
        page.locator('#settings .search').fill('dispatch_codex_fast')
        fast = page.locator('#settings .setrow[data-key="dispatch_codex_fast"] select')
        fast.locator('option[value="false"]').wait_for(state='attached')
        assert fast.locator('option[value="true"]').inner_text() == 'On'
        assert fast.locator('option[value="false"]').inner_text() == 'Off'
        with page.expect_response(lambda response: '/api/settings' in response.url
                                  and response.request.method == 'POST') as changed:
            fast.select_option('false')
        assert changed.value.status == 200, changed.value.text()
        assert settings.value('dispatch_codex_fast', mapped) == 'false'
        page.locator('#settings .close').click()
        page.evaluate("async () => { await (await import('/page/app/settings/screen.js')).openSettings(); }")
        page.locator('#settings .search').fill('dispatch_codex_fast')
        fast.locator('option[value="false"]:checked').wait_for(state='attached')
    finally:
        page.close()
