# Probe template (scratch, delete after use)

```python
import json
from metaform.data import Store
from metaform.modules.web.tests.test_ticket_detail import web, browser, mapped, threaded  # noqa: F401


@pytest.mark.browser
@pytest.mark.kind("simulation")
def test_scratch(run, web, mapped, browser):
    run('enable', 'dispatch')
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('catalog', {...})  # seed the rows the screen reads
    run('set', '--dispatch-codex-model', 'sol', cwd=mapped)
    page = browser.new_page(viewport={'width': 1280, 'height': 900})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(f'http://127.0.0.1:{web}/#p=proj')
    page.wait_for_function('() => window.metaform?.loaded()')
    page.evaluate("async () => { const m = await import('/page/app/settings/screen.js'); await m.showSettings(); }")
    assert not errors, errors
```

Run: `.venv/bin/python -m pytest -n 0 -q -s -m browser <file>`
