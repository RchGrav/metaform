---
name: web-panel-redraw-keeps-typed-input
description: Use when a live page form loses typed text on redraw.
category: development
---

# A panel that redraws on events must not wipe an open form

A panel that re-renders on each map, agent or chat event must skip the redraw while the person is writing in it: an open form, or a focused field inside it. Apply the same check on every redraw path of that panel, not only the first one found.

- Keep one predicate for "the person is writing here" (the page's `writingInPanel` in `core/dom.js`) and call it from each redraw path. A redraw skipped while writing is applied once the person finishes, so no change is lost.
- Verify on the live page, not in a headless unit test alone: open the form, fill it with a marker string, and read the field back every 5 seconds for about 30 seconds while agents write. Report the readings and the page errors. Tell the person to reload first, because the page loads new code only on reload.
- Note in the ticket what was measured live and what remains: the full fix (redraw only the selected node's data) is a separate ticket.
