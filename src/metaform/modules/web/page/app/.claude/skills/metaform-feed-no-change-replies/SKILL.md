---
name: metaform-feed-no-change-replies
description: Use when a Metaform memory notice repeats with no change.
category: development
---

# Metaform feed with no change: stop, reply in one line

When a memory or ticket notice repeats and the read returns nothing new, do not re-read in a loop and do not restate the standing list. Reply in one line that says nothing changed, then wait for the next notice.

- Read a feed at most twice in a turn. If the unread count stays while reads come back empty, treat it as a counter fault: say so once, in one sentence, and stop reading until a notice shows new content.
- Do not repeat the list of items waiting on the user unless one of them changed.
- Only state times, ticket numbers and file states read in the current result. Before correcting an earlier claim, check the record, name the exact error, then fix it.
- In a chat session, report the feed; do not claim, start or close tickets unless the assignment names you the worker for that ticket.
