---
name: metaform-web-announcements-in-chat
description: Use when a web banner or pop-up announces agent updates.
category: development
---

# Agent announcements go into the chat, never a pop-up

Put an agent message or project update in the chat thread the person already uses (the system agent chat). Do not raise a banner that opens a separate thread: a read-only thread has no chat bar, so the person sees text they cannot answer and reads the page as broken.

- Before adding any notice, check that the person can read and answer the message where the notice sends them. If not, show it in that chat instead.
- Do not add a notice the person must close for an update. Closing it is a pop-up the person did not ask for.
- When removing a banner, delete its code and its stored "seen" key, then change its browser test to assert that no banner appears and that the words reach the chat.
- A `banner()` call in `page/app/agents/dispatch.js` with an "Open chat" action is the pattern to avoid.
