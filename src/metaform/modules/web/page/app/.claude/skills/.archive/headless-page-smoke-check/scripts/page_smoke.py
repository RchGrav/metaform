import sys
from playwright.sync_api import sync_playwright

# usage: .venv/bin/python -I scripts/page_smoke.py URL [CSS_SELECTOR_TO_CLICK]
url = sys.argv[1]
click = sys.argv[2] if len(sys.argv) > 2 else None
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--headless=new'])
    page = browser.new_page()
    errors = []
    page.on('console', lambda m: errors.append(f'{m.type}: {m.text}') if m.type == 'error' else None)
    page.on('pageerror', lambda e: errors.append(f'pageerror: {e}'))
    response = page.goto(url, wait_until='load')
    print('status', response.status if response else None)
    page.wait_for_timeout(8000)
    if click:
        try:
            page.click(click, timeout=3000)
            page.wait_for_timeout(1500)
            print('clicked', click)
        except Exception as exc:
            print('click failed', str(exc)[:200])
    for line in errors[:25]:
        print(line[:300])
    browser.close()
