---
name: live-only-visual-defect-probe
description: Use when a live page shakes but headless tests pass.
category: development
---

# Live-only visual defect: measure the live page before tweaking

When the person reports a motion or visual defect that headless runs do not reproduce, do not adjust animation constants or re-run headless passes as proof. Add a read-only probe that the live page answers on demand, recording each motion channel over a few seconds and reporting how often each one reverses direction. Read that output from the live page, fix the one channel that reverses, and add a regression test.

- A headless pass is not evidence that the live page is fixed. Say so when reporting.
- The probe must not drive the subject (no act or look calls that take control of the body), because driving it changes what is measured.
- Record per frame into typed arrays sized once; the probe must not allocate per frame.
- Code on the live page only loads after a page reload. Tell the person that a reload is needed before the probe can answer.
- Keep the ticket note honest: name what was measured live and what remains unknown.

Reference for the working example and the channel list: references/mascot-probe-example.md
