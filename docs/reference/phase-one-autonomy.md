# Automation, triage and scoped knowledge

Metaform assigns a ticket directly to a specialist. The user-facing agent handles triage, board priorities and communication. It can commission a missing role without taking over the ticket's execution session. New assignments default to `metaform://role/implementer`; an explicit specialty uses its registered Metaform URI. Generated duties travel with project exports and each admitted assignment keeps its exact role snapshot across resumes and later prompt edits.

## User control and capacity

Human messages retain arrival order ahead of queued background work. A message to triage acknowledges immediately and requests cancellation of its active task turn. Interrupt retains already accepted human messages; Stop ends the selected session and records a durable stop for its unfinished assignment and continuations. An explicit user Start/Resume clears only that selected stop. A verified page command remains a user command even when the web server was launched below an AI process.

“Max workers on this machine” (`dispatch_machine_agents`) is global. “Workers Full Auto may start” (`dispatch_agents`) applies to the selected project folder: it bounds what Full Auto, the queue, retries and recovery start, and a ticket the person starts, or their system agent starts at their word, runs whatever the count while still counting toward it. The stored keys remain compatible. Worker limits exclude triage and bounded temporary helpers. The primary advisor has its own admission even when helper capacity is full; helpers have a separate bound of eight per project. The server rotates new ticket starts across waiting projects and revisits projects waiting for global capacity when a runner changes.

Open **Agents → Full Auto settings** to configure dispatch, capacity, permissions, recovery, fault capture and review count. Global controls are labelled Global; other controls apply to the selected project folder. Existing explicit settings remain in effect. Relevant controls include:

- Full Auto, Keep triage connected, and Pause the project queue when I stop a worker.
- Ask me before agents act, Roles without authority, and permission prompt policy.
- Dead runner recovery and retry count. Automatic recovery verifies process ownership before releasing work; explicit manual policy remains available.
- Watch registered logs, file fault tickets, reopen recurring issues, and hold feedback for review.
- Automatic reviews per ticket: one by default, zero to disable, with an explicit upper bound.

Stopping a worker pauses its project's queue by default. Turning that policy off lets unrelated work continue; it never clears the stopped assignment's tombstone. User instructions forwarded by triage can explicitly start work even when Full Auto is off. A worker's unprompted call does not acquire user stop authority.

## Repair lifecycle

Faults carry actionable repair and verification instructions. Repeated occurrences update one canonical issue. Recurrence after completion reopens that same ticket, preserving its prior resolution; cancellation remains final until the user reopens it. Review findings reopen their delivery ticket with concrete remediation and verification steps. A correction attempt clears current evidence while retaining prior evidence in history, and does not start another coordinator tree. Delivery without supplied evidence is reported as verification not established, rather than claimed as proof.

The web supervisor owns a log watcher per registered project, independent of open pages. Register real application logs with `metaform autoticket add log=/actual/path/application.log`. Intake prompts request these registrations or an explicit statement that no runtime logs exist. Native file watches, offsets, rotation handling and leases remain the capture mechanism. Watcher failures surface as faults and receive bounded retry backoff; disabled watchers release their leases.

The board reads open work and a bounded recent Done window. Older completed work leaves the board; the board's Archive reads past work from the project folder's git commits, a page at a time. Full Auto's recovery pass reconciles verifiably dead runners before admitting more work. Recorded user stops and held work remain respected.

## Projects and conversations

Each tab keeps its project and base in its URL and session storage. Opening another project or changing its active base does not navigate other tabs or stop their agents. Running advisors and workers remain bound to their starting base. A conversation begun before any map exists can use the first map created.

Agents can inspect peers in another registered project with `dispatch peers target_project=<project>` and send `dispatch note target_project=<project> to=<session> -- <message>`. A reply names `reply=<note-id>`; its recorded sender project/base determines the return route. Delivery updates return to the original sender. Acknowledged note IDs survive runner reconnects and are not executed again. User messages can also target a project explicitly through `dispatch message target_project=<project> ...`.

Runner handover retains human priority, user-word envelopes, scoped context components, peer identities and media for queued turns. Existing server/watchdog handover and runner leases continue to own process replacement.

## Knowledge layers

The base remains a functional map. CEL names describe purpose or property, for example `platformer`, `code.cpp`, or `best_practices`; a name is not an implicit attachment rule. Existing `scope@content` names remain readable.

Create meaningful content under a knowledge namespace, then attach it explicitly:

```text
metaform map knowledge op=link-context layer=code.cpp element=code.engine content=code.cpp
```

An inherited item uses `extra={"instruction":true}`. An optional `extra.applies_to` list narrows it to specific descendants of the attachment. Ordinary observations remain local. At `code.engine.game.controls`, a C++ scope attached at `code.engine` and a platformer scope attached at `code.engine.game` apply; Bash attached at adjacent `code.installer` does not. A mask removes the chosen layer on its branch, leaving siblings intact. Removing a layer from context selection removes its guidance from the next fresh worker context.

`map context <address>` and MCP expose `knowledge` with its layer, source, attachment, meaningful items, elements, properties and joins. The viewer shows this provenance. Workers receive applicable instructions, not a descendant inventory promoted into trunk imperatives. Functional joins do not become transitive.

Routine checked/ok intake results are assessment metadata, not graph nodes. On intake verification or recording, the migration moves only the legacy intake-owned checked layer's exact success markers. It preserves references, provenance and original item history, keeps useful remaining content, and hides a bookkeeping layer only when it has no remaining items, elements or joins. Export/import carries the assessment state.

## Compatibility and rollout

Orchestration table version 2 is additive and accepts version 1. The new intake assessment tables are separate from the functional graph. Schema-21 native packets are accepted by the existing core migration path. Open legacy coordinator assignments adopt direct specialist duty on explicit admission when they have no pinned role snapshot. Existing bound responsibilities, completed histories and stop decisions remain readable.

The supplied packet was tested on a copy. Its 146 assignments all carry user-stop records; those were preserved, along with ticket IDs and history. Deploying the code does not silently restart that historical work. Use explicit Start/Resume for work that should run again, and set the desired Full Auto policy for the project.
