---
name: metaform-live-page-defects
description: Use when a live page shakes, or a form loses typed text.
category: development
---

# Live-page defects: measure the live page, keep open forms

A headless pass is not evidence that the live page is fixed. Measure the live page, fix the one thing the measurement names, then add a regression test.

## Motion that shakes only on the live page
- Do not tweak animation constants, and do not offer headless passes as proof.
- Add a read-only probe the live page answers on demand. Over a few seconds it records each motion channel and reports how often each one reverses direction (turns back per second). The channel that turns back most names the unstable layer. Working example and channel list: `references/mascot-probe-example.md`.
- The probe must not drive the subject, and it records per frame into typed arrays sized once.
- Code on the live page loads only after a reload, so tell the person to reload before the probe can answer.
- The ticket note names what was measured live and what remains unknown.

## A panel that redraws must not wipe an open form
- A panel that re-renders on map, agent or chat events skips the redraw while the person is writing in it: an open form, or a focused field inside it. Call the one predicate, `writingInPanel` in `core/dom.js`, from every redraw path, not only the first one found. A skipped redraw is applied once the person finishes, so no change is lost.
- Verify on the live page: open the form, fill a field with a marker string, and read it back every 5 seconds for about 30 seconds while agents write. Report the readings and the page errors. Tell the person to reload first.
- The full fix (redraw only the selected node's data) is a separate ticket; name it in the ticket note.
