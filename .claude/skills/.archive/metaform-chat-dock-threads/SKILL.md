---
name: metaform-chat-dock-threads
description: Use when editing dock tabs, My agent, or dock Escape.
category: development
---

# Chat dock threads and keys

The dock's tab strip always starts with a pinned My agent tab, so the person can always get back to their own agent. Every other agent's thread gets a close ×. Closing a tab never stops an agent.

- `drawTabs` in `page/app/dock/threads.js` draws the pinned `button.tab.mine` first, then each non-system `DOCK.chats` entry as a `span.tabpair` holding `button.tab` and `button.tabx`. The strip shows only while another agent's thread is open.
- My agent is `showMine()`: the running session whose state `about` is `system`, however it was started. It must work when `DOCK.mine` is null (a system agent started from the phone or the CLI). With none running, clear the target so the intro and the Call button show.
- `closeChat` only removes the chat from `DOCK.chats`. It sends no dispatch stop or cancel. Closing the tab on view calls `showMine`.
- Escape is taken by the overlay stack (`core/overlays.js`, `escapeTop`) before `chatKeys` sees it. Route Escape in the dock's overlay `close` callback, `escapeChat()` in `dock/send.js`: another agent's thread goes to My agent; My agent puts the chat away. A keydown listener for Escape in `chatKeys` never fires.
- Alt+Up/Down walk the drawn `.tab` buttons in the order shown, My agent first.
- Tests pick a worker's tab with `.tabs .tabpair .tab:not(.on)`. A bare `.tab:not(.on)` also matches My agent.
- The behaviour is recorded in the VIEW-045 amendment of 2026-10-15 in `specifications/09-viewer.md`.
