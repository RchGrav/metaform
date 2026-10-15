---
name: roundtable-rules-and-vetoes
description: Use when editing roundtable rules or veto lines.
category: development
---

# Roundtable: state the rules, never instruct a seat

The table states its rules once to every seat, before the opening question. It never tells a seat what to say. Keep that split whenever the table's prompts or output change.

- The rules are the rules element in `src/roundtable/resources/prompts.xml`, so Rich can edit them there. Keep its fill-in places: the seats in speaking order, the limit, the bar. It also says what happens to a longer turn.
- Every veto is one short line, shown to every seat and in every record, export and A2A message: the seat's short name, the failed questions in words, and the four scores `[new, valuable, relevant, keep]`. For example: `T28 Opus vetoed (not new) [0.61, 0.87, 0.95, 0.88]`.
- Add no advice to any seat's prompt about how to do better. Seeing the vetoes and why is what makes seats improve.
- The `Its text: roundtable://...` link goes only to a seat with a tool that reads it (agent seats and the chair's read). Other seats are never sent it.
- A turn over 512 characters is never retried. It is cut to its first 512 characters; the cut text is judged and enters. The record keeps the full original and marks it `truncated`, and submission resources return the original.
