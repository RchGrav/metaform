---
name: metaform-shared-page-rules
description: Use when a word list must match server and web page.
category: development
---
# Keep a rule shared by server and page in one place

Hold the list in the server, serve it on a read the page already makes, and let the page read it from its shared state. Do not copy it into JS: a copy drifts, and the stale one keeps routing work.

- The page's fallback applies until that read lands. Make the reader redraw the board when it arrives, and say in the handoff that running servers and agent sessions keep the old list until restarted.
- Before widening a keyword list, compute the result for every live element Address (read-only) and report each one whose outcome flips. A word such as `interface` also caught the CLI and telephone nodes.
- Routing by Address must handle purpose records (`node_kind` join): their `address` is null and only `receiver_address` is set. Use `address or receiver_address`, as the existing Jev and claim code already does, and check both the server path and the board card.
- Test the server rule by building the record directly and calling the function; a store is not needed.
