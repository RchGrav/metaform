---
name: metaform-map-marker-triage
description: Use when triaging red trouble or broken map markers.
category: development
---

# Triaging map markers

A trouble, broken or missing marker is an open claim. Triage it: check whether the claim still holds, record the evidence on its ticket, and report. Do not close it, and do not fix it inside the triage.

1. List the markers: `uv run metaform map work condition=trouble limit=0`, then `broken` and `missing`. The CLI prints one `results: [...]` JSON line; parse that line, not the prose.
2. Check each claim against the code, its tests, or live behaviour, and keep the result as evidence. A marker can be stale: a 2026-10-13 embodiment marker answered `figure: true` on 2026-10-14, so it was reported as likely fixed, with the unrun check named, not closed.
3. Write the finding with `uv run metaform map work op=edit id=ID note="..."`. Keep the existing note text and add a dated triage paragraph: what was checked, the result, and the next check.
4. Tell the person one line per marker: still true, likely fixed, or unknown, with the evidence.
5. If a marker has sat untaken, check why: `uv run metaform config --show | grep -E "dispatch_autostart|dispatch_agents"`. On 2026-10-15 autostart was on with 7 slots and two open markers were not started for a day and a half.

The automatic version of this (the agent facing the person told when a marker is raised) is not built; it is ticket code.interface.graphical#86.
