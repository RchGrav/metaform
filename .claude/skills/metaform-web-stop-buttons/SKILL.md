---
name: metaform-web-stop-buttons
description: Use when adding a Stop or Recall button to the web page.
category: development
---

# Every page stop records itself in the dock's stopped list

A page control that ends an agent session sends `{work_id, session}` to `/api/dispatch-stop`, then on success calls `rememberStop(session_id, new Date().toISOString())` (exported from `page/app/dock/threads.js`), then `await renderAgents()` (from `page/app/agents/dispatch.js`). The dock's stopped-agents list shows only sessions this browser recorded, so a stop that skips `rememberStop` leaves the session out of the dock while the Agents menu still lists it.

- Refresh with `renderAgents()`, not `drawAgentSessions()` alone. The draw uses `D.sessions` loaded earlier, where the session still reads as running, so the dock stays empty.
- Pick the session as the running one for that work: `D.sessions.filter(one => one.work_id === id && one.state === 'running').at(-1)`. Omit `session` from the request only when none runs.
- Current stop sites: the thread bar's stop, `recallButton` in `page/app/board/board.js`, and `stopIntake` in `page/app/intake/intake.js`. Keep all three in step.
- The board's Recall sits inside the card's folded `details.ticket-settings`. A browser test clicks `.ticket-settings > summary` before it, as a person would.
- Cover a new stop with a browser test in `tests/test_chat_recovery.py` (existing file, no new test file), run as `-m "browser or not browser" -k NAME`.

Worked case, the board's Recall: `references/recall-stop-case.md`.
