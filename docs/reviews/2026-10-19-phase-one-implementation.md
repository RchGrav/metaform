# Phase-one implementation and validation

This change restores direct specialist ownership, user control during automation, independent project sessions, and scoped knowledge. It implements the recovery plan in [phase-one-autonomy-and-knowledge-recovery.md](../plans/phase-one-autonomy-and-knowledge-recovery.md). The operational controls and compatibility behavior are described in [phase-one-autonomy.md](../reference/phase-one-autonomy.md).

## Delivered behavior

- Verified user commands retain their authority even when the web server inherited an agent process ancestry. Stop remains durable. Human messages reach triage ahead of queued background work and cancel its active task turn without waiting for a normal steering timeout.
- Tickets go directly to an existing specialist, or commission a deduplicated role-creation helper and continue with the published Metaform role URI. Claiming a ticket from triage does not bind the execution to triage's session. Assignments retain their exact authored role version across edits, exports and resumes.
- Global and project limits count workers. Triage and temporary helpers use separate admission. The Full Auto settings page exposes capacity, permissions, recovery, log capture, recurrence, review count and the stop/pause policy. Explicit existing settings remain in effect.
- Repeated faults and independent review findings update/reopen their canonical ticket, preserving history. Automatic review count is bounded. Verification without supplied evidence is explicitly reported as not established. No recursive corrective coordinator tree is created.
- The web supervisor owns log watches for registered projects. Watch startup failures are isolated to the affected project and receive bounded retries. New worker admissions rotate among projects; a capacity release wakes waiting projects through events.
- Each browser tab retains its project/base. Agents stay pinned to their original base. Peer discovery and threaded cross-project replies use the recorded session's project/base, even after navigation. Received and returned notes are deduplicated, including the race between a waiting tool reading a reply and its thread write finishing.
- CEL links explicitly attach meaningful knowledge to a functional subtree. Inherited instructions honor layer selection, masks and narrower applicability. Context retains provenance and excludes adjacent branches. Routine successful intake checks live in assessment metadata with history, rather than green graph nodes.
- Runner handover retains queued user priority, user-word envelopes, context components, peers and media. Existing process ownership and handover mechanisms remain in use.

## Validation

Tests use isolated homes and controlled ACP adapters; they exercise real subprocesses, MCP resource reads, CLI commands, event delivery, SQLite stores and headless Chromium. They establish transport and state behavior without claiming an external model independently solved a production issue.

| Check | Result |
|---|---|
| Combined orchestration, authored roles, autoticket, intake, context/layers, exchange, dispatch transport/control, scheduler and cost tests | 243 passed; the opt-in 60-second idle test was run separately |
| Complete dispatch liveness/recovery suite | 52 passed |
| Explicit legacy coordinator compatibility, including nested calls, generated roles, compaction, stops, review corrections and peer transport | 10 scenarios passed across the final run and focused reruns |
| Cross-project routing, durable peer delivery and independent team transport after the final routing correction | 7 passed; idle test excluded |
| Layer scope, assessment migration and watcher tests after the final storage/startup corrections | 36 passed |
| Browser project/base isolation, CEL viewer, policy controls, handover metadata, reply race and scheduler fairness | 5 passed |
| CLI user/agent authority checks | 8 passed |
| Changed-module type checking, full Ruff lint and changed JavaScript syntax | Passed |
| Map-view build, source distribution and wheel | Passed |

The direct specialist runtime scenario used a project and global worker limit of one. It created a missing role, read its `metaform://role/route_specialist` resource through MCP, wrote and identified a candidate, returned evidence, and performed one independent assessment. Exactly three assignments existed: the role creator, the original specialist assignment and the assessment.

Storage/CLI/MCP fixtures cover C++ on `code.engine`, platformer guidance on `code.engine.game`, Bash on adjacent `code.installer`, branch masks, narrower instruction targets, local observations, and removal from the next worker context. Controlled Flask, greenfield and screenplay fixtures preserve functional elements/purposes and assessment state through export/import. The user's original Flask project was not present in the uploaded packet, so no claim is made to have reproduced that exact intake session.

The idle measurement used the same native-orchestration scenario on baseline `8d479f2` and the candidate, each for 60 seconds. Baseline runner/adapter CPU was 0/0 seconds. The final candidate used 0.02/0 seconds (0.033% of one core for the runner). A 2,000-event irrelevant burst caused no watcher storage reads; orchestration and scheduler tests also reject irrelevant event work. No graphics hot path changed.

## Packet compatibility and user decisions

The native packet was imported and examined on an isolated diagnostic copy. Its three bases contain 28 historical layers. The active base has 407 tickets plus 34 other work markers, or 441 work records in total.

Upgrade validation ran on a second copy. All 146 assignment IDs and all 146 explicit user-stop records were preserved, together with the work records and their history. None of those stopped assignments was silently converted into running work. No runner, watcher or automatic dispatcher was started against either packet copy. Explicit Start/Resume is required for historical work the user chooses to restart.

Orchestration table version 2 is additive and accepts version 1. Assessment metadata uses new module-owned tables. Native schema-21 packets pass the existing core upgrade path. The original archive, databases and transcripts are not included in this commit.

## Existing checks that are not green

An exploratory broad dispatch run exposed older failures as well as assertions for the replaced worker-count and coordinator behavior. The relevant changed contracts were updated and rerun. Comparison against untouched `8d479f2` reproduced older failures concerning handoff/compaction wording, trimmed session metadata, a memory writer receiving an extra notice turn, option-catalog fixture selection, and the module public-import boundary. Those older failures are not represented as repaired by this phase. The new role-resource and priority-message tests cover the delivered behavior independently.

Full-repository Pyright reports 15 errors in unchanged `modules/voice/engine.py` optional audio-library types. The baseline reports those same voice errors plus six autoticket errors; the autoticket errors are resolved here. Voice is outside this phase. No fully green repository-wide CI result is claimed.

## Rollout boundary

The code and tests are ready for the repository's main branch. Pushing source does not update a separate running desktop installation. Install the built revision there, retain the project backup, and use the existing supervised server/runner handover. Check the loaded revision, selected Full Auto policy, registered logs and worker limits. The supplied packet's user stops intentionally survive that update.
