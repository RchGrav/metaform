# Changes

## 2026-10-21 — The Facilitator's commission is one line

- A commission is one line in the form every delivery between agents takes, the `commission` prompt: the requesting assignment's role and ticket number, that ticket's title cut to 80 characters, and `Select or create a specialist for <ticket>, role <name>, request <id>.`; it was a JSON object of the same request id, role and ticket number.
- The role creator's procedure reads the commissioned ticket with `map_work id=TICKET`; it said `op=read`, which `map_work` refuses.

## 2026-10-21 — The Facilitator's commission names the ticket

- A Facilitator's commission carries the request id, the proposed role name and the ticket's number, nothing of the ticket's content: the Facilitator reads the ticket itself for its text, note and functional context. The commission had copied the task, the note and the functional graph; one note of 1.9 MB copied whole made the commission the heaviest ticket on the board and was read by every surface that listed it (2026-10-20).

## 2026-10-20 — Automatic specialist fallback

- Missing JEV keys, unavailable credits/providers and uncertain decisions directly commission the Facilitator instead of leaving a triage notice.
- The event-driven starter recovers existing triage entries in bounded passes without repeating unchanged cached selection calls. Existing ownership, user stops and Backlog holds are preserved.
- Ticket inspection names the Facilitator while selection is pending; prompts no longer require the user-facing agent to relay fallback tickets.

## 2026-10-20 — Launches the person asked for

- A claim the person makes, or their system agent makes on their word, marks its delivery `persons_start` (assignments table version 5), and every launch in it, the GC, a commissioned Facilitator and the continuation after publication, is no automatic start: Full Auto off no longer holds it, while a halt still refuses it as it does every start. Found when the system agent's claim commissioned a Role Creator that never launched.

## 2026-10-19 — Facilitator handoff

- Confident JEV no-match directly commissions the Facilitator; missing-key and uncertain fallback asks the ticket writer to assign existing expertise or hand off with `claim create=true`.
- Facilitation uses the registry-first XML metaprompt, selects reusable names, reuses existing roles without editing them, and continues the original ticket after publication.
- Publication returns compact identity, match and board receipts; To do is the default and Backlog explicitly holds the continuation. Replays do not launch duplicates.
- `metaform://specialists` exposes the public expertise registry; new helper assignments use `facilitator`, with `role_creator` retained for existing assignments.

## 2026-10-19

- `orchestration_change` on a ticket given no specification file revises the task of the GC's ticket, its operative specification, where it used to fail on a path of `None`; the earlier task is kept as the change record's `before_content`, and the change is routed and told to the person as a file's is. A `file:` path that does not exist is still refused (code.server.tool#1c).
- `orchestration_change` takes `section`, a record id or heading: `content` is then that one record, which replaces the record with that heading or is added at the end, and the rest of the file stays. A write that would drop any heading of a specification file is refused, nothing written, unless `removing` names each record it removes; the refusal gives the `section` call that does what was meant (code.router.assignment#13, after two amendments overwrote whole specifications). A new record goes after the last record of its level, not under whatever heading ends the file; a `section` call whose content holds several records, or is headed by a record the file already holds, is refused so no id is written twice; the person's message and the change order carry the changed lines, each hunk headed by its record, instead of the whole file (functional review of the same ticket).
- A ticket's read (`map work id=`) links what reviewed it: beside its assignment, `independent_assessments` gives each assessment's assignment, ticket, role, state, result and `findings_filed`, the tickets its findings landed on (the reviewed ticket when a finding reopens it, or the open ticket at the node a finding was folded into), so a ticket whose work ran shows that work, its reviews and where they led. Assignments table version 3 adds `findings_filed` (code.router.assignment#e).

## 2026-10-18

- Add a native module for GC ticket ownership, authored role assignments, swarm membership, independent functional assessments and durable caller continuations. Keep these responsibilities separate from dispatch's operational execution roles.
- Route specialists and GC-commissioned Role Creator work through existing work records, public providers and dispatch admission. Publish generated duties in the prompt store with registered identity and source/version history, then continue the original caller. Delivered roots remain closed when corrective GCs follow them.
- Persist check-ins, candidate and validation evidence, interruption direction, return destinations, stop history and transition delivery. Resume pending work through the existing ACP lifecycle; waiting parents release actual process capacity before a child starts.
- Publish C(T)-grounded adaptive revisions through the existing file or workflow owner, send GC change orders and an actual user/PM Chat message. Strict mode records recommendations. Newer user instructions and source changes retain their effect, including across interrupted publication and frozen workflow successors.
- Contribute 17 authored roles, native common/duty/event prompts and actual module action bindings. Keep the Liaison's existing `dispatch:system` identity. Resolve installed project-local BMAD sources alongside native and generated roles without adding a BMAD dependency.
- Expose assignments, parent/root/GC relationships, independent assessments, corrective work and pending direction through the existing work, session and web surfaces.
- Add focused public-contract tests and actual runner/fake ACP/MCP scenarios for ownership, nested calls, role creation/reuse, capacity-one suspension, peer messaging, GC interruption, recovery, functional correction, adaptive/strict revisions, prompt receipts, compaction and memory delivery.
