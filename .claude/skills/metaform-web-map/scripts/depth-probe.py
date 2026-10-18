import sys, time
from playwright.sync_api import sync_playwright

# usage: depth-probe.py OUT_DIR URL TAG KEY...
# Opens URL headless, presses each KEY in turn, and prints node and edge counts of the 2D map.
out, url, tag, keys = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
ARGS = ['--headless=new', '--enable-gpu', '--ignore-gpu-blocklist', '--use-gl=angle', '--use-angle=gl-egl']
COUNT = """() => { const m = document.querySelector('#map2d'); if (!m) return null;
  const n = [...m.querySelectorAll('svg g.node')];
  return {nodes: n.length, edges: m.querySelectorAll('svg .edgePaths path').length,
          labels: n.map(g => (g.textContent || '').trim()).slice(0, 12)}; }"""

with sync_playwright() as p:
    b = p.chromium.launch(channel='chromium', headless=True, args=ARGS)
    page = b.new_page(viewport={'width': 1600, 'height': 960})
    errs = []
    page.on('pageerror', lambda e: errs.append('PAGEERROR ' + str(e)))
    page.on('console', lambda m: errs.append(m.text[:200]) if m.type == 'error' else None)
    page.goto(url)
    page.wait_for_function('() => window.metaform && window.metaform.loaded && window.metaform.loaded()', timeout=120000)
    time.sleep(6)
    for k in keys:
        page.keyboard.press(k)
        time.sleep(4)
        c = page.evaluate(COUNT)
        print(tag, 'after', k, c and c['nodes'], c and c['edges'], c and c['labels'][:6], flush=True)
        page.screenshot(path=f'{out}/{tag}-{k}.png')
    print('\n'.join(list(dict.fromkeys(errs))[:10]))
    b.close()
