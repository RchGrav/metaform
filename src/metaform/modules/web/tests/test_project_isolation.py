"""Independent browser tabs retain project/base choices and expose automation policy."""
# ruff: noqa: F811
import pytest

from metaform.data import Node, Store
from metaform.modules.web.tests.test_web import RETURNING, TOGGLED, browser, build, mapped, started, web  # noqa: F401

pytestmark = [pytest.mark.browser, pytest.mark.kind('simulation')]


def test_two_tabs_keep_project_and_base_when_another_project_opens(run, web, mapped, browser, tmp_path):
    run('enable', 'dispatch')
    source = Store('proj')
    source.layer('code.cpp', 'map', 'C++ implementation guidance.', mutable=True, hideable=True, ready=True)
    source.add_element('code.cpp', 'code.cpp', role='SE')
    source.add_item('code.cpp', Node('element', 'code.cpp'), 'Use C++23 ownership rules.', extra={'instruction': True})
    source.add_property('code.cpp', 'code.timer', 'code.cpp', extra={'knowledge_root': 'code.cpp'})
    run('set', '--layers', ','.join([*TOGGLED, 'code.cpp']), cwd=mapped)
    second = tmp_path / 'second'
    second.mkdir()
    run('add', 'project', 'other', str(second))
    build(Store('other'))
    started(run)
    shared = browser.new_context(viewport={'width': 1280, 'height': 800})
    shared.set_default_timeout(30_000)
    shared.add_init_script(RETURNING)
    a, b = shared.new_page(), shared.new_page()
    own = f'http://127.0.0.1:{web}/'
    try:
        a.goto(own + '#p=proj')
        b.goto(own + '#p=other')
        a.wait_for_function('() => document.querySelector("#proj").value === "proj" && document.querySelector("#mf").value')
        b.wait_for_function('() => document.querySelector("#proj").value === "other" && document.querySelector("#mf").value')
        base = a.locator('#mf').input_value()
        run('add', 'base', 'fresh', cwd=second)
        import importlib
        importlib.import_module('metaform.modules.web').opened('other')
        b.reload()
        b.wait_for_function('() => document.querySelector("#proj").value === "other"')
        assert a.locator('#proj').input_value() == 'proj'
        assert a.locator('#mf').input_value() == base
        a.reload()
        a.wait_for_function('() => document.querySelector("#proj").value === "proj"')
        a.wait_for_function('(base) => document.querySelector("#mf").value === base', arg=base)
        a.evaluate('''async () => {
          window.__reads = await import('/page/app/core/reads.js');
          window.__select = await import('/page/app/selection/select.js');
        }''')
        a.wait_for_function('''() => !window.__reads.S.loading && [...window.__reads.S.elements.values()]
          .some(one => one.element.address === 'code.timer.kitchen')''')
        a.evaluate('''() => window.__select.select([...window.__reads.S.elements.values()]
          .find(one => one.element.address === 'code.timer.kitchen').element.id)''')
        a.wait_for_selector('.scoped-knowledge', state='attached')
        assert 'Use C++23 ownership rules.' in a.locator('.scoped-knowledge').first.text_content()
        # Full Auto is a dedicated policy page including both scopes and independent helper admission.
        a.evaluate('document.querySelector("#automationSettingsBtn").click()')
        a.wait_for_selector('#settings:not([hidden])')
        a.wait_for_selector('[data-key="dispatch_machine_agents"]', state='attached')
        assert a.locator('[data-key="dispatch_agents"]').count() == 1
        assert a.locator('[data-key="autoticket_watch"]').count() == 1
        assert a.locator('[data-key="dispatch_pause_on_stop"]').count() == 1
    finally:
        shared.close()
