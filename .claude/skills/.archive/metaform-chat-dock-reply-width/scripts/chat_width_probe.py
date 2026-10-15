"""Measure the chat dock reply width under a stylesheet.

Usage: python -I chat_width_probe.py <app.css> <dock_px> <out_dir>
Prints JSON: bubble width, gaps to the dock edges, and whether the code block scrolls sideways.
Run it once on a copy of app.css with the old rule restored (before) and once on the live file (after).
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

css = Path(sys.argv[1]).resolve()
dock_px = int(sys.argv[2])
out = Path(sys.argv[3]).resolve()
out.mkdir(parents=True, exist_ok=True)

# A 120-character code line, so a code block is wider than a capped reply.
code = ('x = "' + 'a' * 100 + '"').ljust(120)
prose = ' '.join(['The system agent explains what it found in the map and why it matters.'] * 4)
html = f'''<!doctype html><html><head><link rel="stylesheet" href="{css.as_uri()}"></head><body>
<div id="helpdesk" style="position:fixed;left:20px;top:20px;width:{dock_px}px;height:900px;max-width:none;right:auto;bottom:auto">
<div class="log">
<div class="msg mine first"><div class="who">You</div><div class="row"><div class="bubble mine"><p>Show me the line.</p></div><div class="tools"><time>15:20</time></div></div></div>
<div class="msg theirs first"><div class="who">System agent</div><div class="row"><div class="bubble theirs"><p>Here it is:</p>
<div class="code"><pre tabindex="0"><code>{code}</code></pre></div><p>{prose}</p></div><div class="tools"><time>15:20</time><button class="copy"></button></div></div></div>
</div></div></body></html>'''
page_file = out / 'probe.html'
page_file.write_text(html, encoding='utf-8')

MEASURE = '''() => {
  const r = e => e.getBoundingClientRect();
  const dock = r(document.querySelector('#helpdesk'));
  const bub = document.querySelector('.msg.theirs .bubble');
  const pre = bub.querySelector('pre');
  const mine = document.querySelector('.msg.mine .bubble');
  const b = r(bub);
  return {bubble: Math.round(b.width), leftGap: Math.round(b.left - dock.left),
    rightGap: Math.round(dock.right - b.right), mineRightGap: Math.round(dock.right - r(mine).right),
    preScroll: pre.scrollWidth, preClient: pre.clientWidth, sideways: pre.scrollWidth > pre.clientWidth};
}'''

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': dock_px + 80, 'height': 960})
    page.goto(page_file.as_uri())
    result = page.evaluate(MEASURE)
    page.screenshot(path=str(out / 'dock.png'), clip={'x': 0, 'y': 0, 'width': dock_px + 40, 'height': 500})
    browser.close()
print(json.dumps(result, indent=1))
