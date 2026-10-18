---
name: metaform-unread-memory-notices
description: Use when memories are unread at a Metaform node.
category: development
---

# Read unread memory notices once, then act only on what changed

When a notice names unread memories at a node, make one `memory read_unread` call on that node with no `must_contain` filter. A filter returns a subset of the same set, so a second or third filtered read tells nothing new.

- Read again only when the notice's unread count or updated count has risen since your last read at that node.
- When the count is unchanged, do not read and do not reply. A "nothing new" line on each repeat is wasted inference.
- A memory that bears on the task you hold changes your work; say so in one line. Otherwise say nothing about it.
