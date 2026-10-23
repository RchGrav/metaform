---
name: metaform-status-line-report
description: Use when asked for a ticket status report or what changed.
category: development
---

# Ticket status reports state only what was checked this turn

The routine status line was deleted on 2026-10-21 (commit 758912ff): the system agent is no longer woken with ticket counts. Use this skill only when the person asks for a status report.

Read the sources before saying anything about a ticket: `dispatch_sessions thread=false`, `map_work`, and `dispatch_notes`, plus `git log --since` for commits. A fact that was not read in this turn is not reported.

- Report each problem by ticket address and number, `code.x.y#n`, with the observed state and the source it came from.
- Group the checked facts as: finished, running, cancelled, new from the person, peer notes awaiting an answer.
- Say which items you did not change. A ticket another agent closed is reported as closed by that agent.
- When significant work since the last commit needs review, name that work and route the review. Do not skip it silently.
- A count the person gave is not a check. Read the list before repeating the number.
