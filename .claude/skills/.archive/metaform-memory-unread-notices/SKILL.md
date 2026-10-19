---
name: metaform-memory-unread-notices
description: Use when metaform memory unread notices repeat each turn.
category: development
---

# Metaform memory notices: read once, report once

A "N unread" notice asks you to read a record once. It is not a standing task. Read each element with `memory_read_unread`, act on what is new, and when a later notice returns the same records unchanged, do not read them again or repeat them to the person.

- Call `memory_read_unread` with only `node` first. The default triage view can return nothing where `view=full` returns an updated entity, so when a notice still counts updates after an empty triage read, make one `view=full` read, then stop.
- Do not pass `fields=["name"]` on its own: on a node whose records hold no `name`, it errors with "No record here holds name; they hold ." Use no `fields`, or `view=full`.
- An empty result (`{"entities":[],"relations":[]}`) means nothing new. Stop there. A second read shape that also comes back empty or at 0 (the CLI `memory read_unread` after `memory_read_unread`, or `view=count`) is the same answer: stop there, and on later turns with the same repeated count make no call at all, even to try another shape. The stop holds across turns: when the next notice repeats the same count for that node and your last read in this session came back empty, make no tool call and send no reply. Re-read only when a notice is new or the node's records are known to have changed since your last read. "Nothing new" is itself a reply, so it stays unsent too: on 2026-10-18 the same "11 memories; 2 unread" notice recurred over about fifteen turns, each answered with one or two reads and a "Nothing new" line.
- Reply with the new facts only. Name a waiting item again only when its state changed, and keep the reply to a line or two.
- The count can include your own writes and can disagree with the read. A notice may report "N unread" while the read returns only the line your session just wrote, or nothing, and `view=count` may report the node's whole memory total. When that happens, take the read as the truth, do not write a new memory about the miscount (it is already recorded at the node), and do not reply about it beyond a line.
- A `must_contain` read narrows what you see and leaves the rest unread: the notice keeps counting the records the filter skipped. Read the whole node once with `node` alone (or `view=full`) when a notice repeats after a narrowed read, not a series of filtered reads.
