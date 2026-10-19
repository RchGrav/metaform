# Phase one: restore control, reliable work, and useful knowledge

Status: implementation plan for review, 2026-10-19. Current code examined at `8d479f2`, together with the startup report, supplied screenplay, screenshot, and imported project packet. The only application change made is the narrow schema-history validation fix needed for native import, with a regression test. No autonomy changes or new board tickets have been made.

The [packet findings](../reviews/2026-10-19-phase-one-packet-findings.md) document exact counts, ticket and assignment identities, import integrity, and the limits of the evidence. Both documents live under `docs/` so they are not lost under the repository's ignored `artifacts/` directory.

The goal is a system the user can direct at any moment: a reachable triage agent, workers doing useful work within chosen limits, a board with one actionable ticket per issue, and faults that are repaired and verified. Its functional map and knowledge layers must give those workers the right understanding. The same mechanisms must work for Metaform, Flask, a new application, or a screenplay.

The supplied screenplay document is an example to understand intake semantics. Its embedded correction suggestions are not requests to edit that screenplay. The older autonomy report supplies history and intended behavior; current code and current reproductions determine what still needs implementation.

## 1. Findings and limits of this study

Several failures are connected. Making more tickets cannot repair a scheduler that will not take them. Giving human messages queue priority cannot keep the advisor available while its current turn runs a long build. Hiding green markers does not correct a knowledge model that stores assessment bookkeeping as knowledge. Disabling authorization does not restore the user's authority.

| Area | Current evidence | Consequence |
|---|---|---|
| User authority | dispatch/__init__.py:4952 sets STOP_CONSENT to False; stop and stop-all can treat an agent's call as the person's. | The bypass is real. Replace it with correct actor and delegated-authority handling, with positive tests that the user can always control their agents. |
| Worker capacity | dispatch/__init__.py:3330 counts workers plus summoned agents in project capacity, and all launch entries against machine capacity. There are already project and machine settings, named as agents. | Change the existing accounting and labels; do not add a third competing limit. |
| Human messages | runner.py:4240 places a person's message at the front of pending turns. The current turn continues unless a separate steering/interrupt path handles it. Repeated front insertions can reverse queued human-message order. | Human FIFO, automation preemption, and a lightweight advisor are required together. Test each adapter's active-turn behavior. |
| GC orchestration | orchestration/state.py:420 defaults root assignments to gc; runner.py:3571 also binds native workers to the GC role. Corrections can create another GC assignment. | Removing a role label alone would leave the coordinator/reviewer machinery operating. Replace the execution path and migrate active assignments. |
| Specialist prompts | agents/roles.py already publishes versioned generated duties, resolves metaform://role/<name>, and records delivery receipts. MCP serves these resources. | Reuse this implementation and make it the explicit ticket-to-worker contract. |
| Faults | autoticket is enabled by default in this checkout. Its fault grouping and ticket-writing code exists; the ticket template includes repair and verification instructions. | The reported empty or unclaimed tickets need their actual producer, version, task fields and blocking reason traced. Do not assume every card came from the present autoticket template. |
| Recurrence | autoticket/faults.py:198 clears a completed ticket's link when its error returns, allowing a new ticket. | A recurring issue can grow the board instead of reopening its existing history. |
| Blanket holds | autoticket/faults.py:318 holds feedback, and uses deletion-related words in an error message to infer that a fix needs a person. | A symptom's wording is not the authority required for its remedy. |
| Board | Seven-day done retention, an archive, and “Line in the sand” already exist. loading/load.js:77 still reads all work records to calculate progress. | Verify which server/page revision produced the screenshot; repair aggregate reads and the actual archive behavior instead of rebuilding an archive that exists. |
| Project navigation | loading/load.js:275 clears displayed chat/session state. workspace/workspace.js:339 prefers the server's opened project over browser history. live/stream.js:193 can move every tab on a web.opened event. | Tab context is not sufficiently independent. The exact process-termination path remains to be reproduced; clearing figures is not evidence that a process died. |
| Cross-project messages | dispatch/peering.py discovers callers and recipients through the current project's store. | Add explicit project routing with preserved sender identity and delivery history. |
| “Checked” clutter | intake/__init__.py:762 creates a checked layer and an ok item per assessed element/join. loading/load.js:44 loads non-base layer items for graph rendering. | Assessment state is being represented as visible knowledge. Preserve evidence, but move its presentation and storage to the appropriate place. |
| Layer semantics | data/reads.py:261 implements descendant application of properties and separate ancestor visibility. Ordinary attached items do not inherit. The layer schema and LAYER-028 also contain competing naming proposals. | Prove delivery of applicable instruction content, not merely scalar property labels, and settle the current semantic contract before migrating data. |

The screenshot shows 11 Backlog, 45 To do, 11 Doing and 331 Done cards, an “Agents 5” control, stopped/gone runners, and a server-unresponsive banner. It establishes the visible failure, not the contents of the underlying database or the cause of the stall.

The split packet was reassembled, checked, and imported with Metaform's native CLI into an isolated diagnostic home. A re-export matched all three base documents and all project module exports exactly. The packet contains Metaform only; it does not contain the Flask project, project source files, global/folder settings, or the original machine's live launch ledger.

The original active base now supplies concrete priorities:

- **67 open tickets:** 11 Backlog, 42 To do, 14 Doing. Another 340 tickets are done; condition-only records are counted separately.
- **All 14 Doing tickets point to ended sessions:** seven terminated, five stopped by the person, one runner gone and one orchestration suspended. These need distinct states and recovery decisions.
- **Twelve To do tickets have a separate dispatch hold.** A visible To do position does not establish eligibility.
- **146 orchestration assignments split evenly between GC and functionality assessment.** One root has 46 GC assignments, including a correction ancestry eight assignments deep. This is measurable expansion beyond merely accumulating completed cards.
- **No generated specialist definitions and no role requests**, despite existing role-resource and receipt infrastructure.
- **One captured MCP fault remains untaken about three hours later**, with a repair/verification task but no assignment or session. No watched log files are registered in this project's exported autoticket tables. Its exact admission blocker needs runtime policy/ledger evidence.

These findings support repairing control, admission and review behavior first. They do not justify treating every hold as unwanted, every review finding as a duplicate, or every stopped session as a crash.

### Checks run during this study

- Native import completed; all base and project module exports matched on readback. The importer regression failed before the one-line fix; all 13 exchange tests passed afterward, as did changed-file lint and source type checks.
- Existing layer and authored-role suites: 34 passed, 2 failed, completed. All eight authored-role tests passed.
- Both layer failures stop at fixture creation because the fixture names a layer “media”, now a reserved project root. Those two tests do not establish whether their later assertions pass.
- Three selected autoticket tests passed: a new log error creates a ticket, repeated identical errors update one ticket, and unrelated events trigger no reads.
- These checks validate useful pieces. They do not validate the full self-healing loop, live agent cancellation, browser project switching, or the reported Flask intake.
- Logs: /workspace/.onboarding/validation/phase-one-layer-role-tests.log and phase-one-autoticket-tests.log. Historical setup failures are separate evidence.

## 2. The operating contract

These are requirements for every implementation step.

1. C(T) preserves receiving elements, their operative purposes, and what serves them. Implementation and subordinate specifications can adapt to fulfil those purposes. Changes to purpose belong to the user.
2. The user can stop, interrupt, redirect, pause automation, and change authorized project policy. Ordinary autonomous repair within the selected policy does not require confirmation per ticket.
3. A message from a worker remains a worker message. A role prompt, quoted user text, or missing identity must not manufacture user authority.
4. The triage agent owns communication and board oversight. Long investigation, coding, tests and bulk housekeeping are delegated. Human interaction must not depend on a free worker slot.
5. Every active issue has one canonical ticket, a useful next action, and an accountable owner or an explicit waiting reason. Repetition adds evidence to that issue.
6. A worker reads the specialist role identified by its assignment before beginning work. The system records which role version was delivered.
7. Navigating, refreshing, closing a tab, or changing the viewed project does not stop project work. Stop, pause and project shutdown are explicit actions with explicit scope.
8. Knowledge conveys reusable understanding or applicable instructions. Receipt counters, inspection statuses and “ok” markers do not become functional elements or default knowledge nodes.
9. Changes are driven by relevant events through the existing event bus and relay. Unrelated events must cause no project-wide rescans; replayed events must not create duplicate actions.

## 3. Work sequence

### Step A — establish the actual state and a recoverable baseline

Completed for the supplied packet: native import into a separate diagnostic METAFORM_HOME, manifest/schema checks, preserved upload, local diagnostic registration, inventory and exact base/module readback. Imported agents and automatic work were not started. The original active base was read explicitly because importing into the existing diagnostic project retained its initially selected main base.

The inventory covers bases, layers, ticket fields, fault groups, sessions and exit reasons, assignments, specialist definitions and receipts. It establishes that Flask and home-scoped policy/runtime state are absent. Remaining baseline work belongs with the implementation slice that needs it; another unbounded audit is unnecessary.

Use four bounded timelines to reproduce and then prove the relevant repairs:

- A reported issue becoming repeated tickets: producer, finding identity, review parent, recurrence and delivery receipts.
- A runnable-looking ticket remaining idle: actual task, role, policy, holds, dependencies, capacity, budget, reservation and runner state.
- A human message or stop being delayed/refused: sender, ingress, policy decision, queue position, active turn, adapter and completion.
- A project switch: tab/project event, session visibility, process identity and exit reason before and after.

The correction ancestry and an unclaimed fault are already traced in the packet report. For Flask, use its separate packet when available or perform a controlled intake: count checked items separately from functional elements, inspect layers and their producers, and sample the context actually returned to a worker. Compare the screenshot's server/page version with the packet and checkout when those runtime identities are available.

Output: a small baseline report and reproductions for distinct causes. Reconcile these with existing tickets; do not mass-file the report as another queue.

### Step B — restore user control and an available triage agent

Replace the blanket stop bypass and scattered actor guesses with a consistent decision at each command boundary: authenticated user, a specific delegated user command, automation acting under project policy, or an ordinary worker. Reuse existing person-word and runtime-identity facilities where correct. Delegation must retain its origin, action scope, target project/session and cancellation state; it must never be inferred from role prose.

Keep user Stop/Interrupt independent of the agent's next model turn. Accept and durably record the command, attempt adapter cancellation, and escalate to the verified owned process group if it does not cooperate. Retain the session history. Record user stop distinctly so recovery, retries, stay-connected and Full Auto cannot silently replace it. An explicit resume creates a new authorized attempt.

Give the advisor separate FIFO handling for human messages and coalesced automation notifications. The user sees that a message was accepted immediately. Human input supersedes background board work; an automation turn yields or is cancelled at a supported boundary while its durable work remains available to resume. Multiple human messages keep their order. Useful worker results remain in the record even when redundant notifications are collapsed.

Keep the advisor's normal turns short: understand the request, select or commission the specialist, create/update actionable work, explain progress and decisions, and return to the user. The board's mechanical operations belong in deterministic services; long triage investigations go to workers.

The advisor must not acquire GC ownership of a long-running ticket simply because it created that ticket. Its role prompt, dispatch classification and actual admission path must all agree on triage responsibility. Notifications carry the originating project, worker and ticket, and a single delivery identity so one result cannot arrive twice through different routes.

Acceptance:

- Fill all worker slots, flood the advisor with 100 duplicate notifications, and start a deliberately slow background task. The user's message and stop are accepted and shown promptly; they do not wait for that task to finish.
- Proposed local targets: acknowledgement under one second and cancellation signalling within two seconds on the test machine. Model response latency is measured separately, never disguised as instant acknowledgement.
- The user can stop their own advisor or any authorized project worker. Worker A cannot impersonate the user to stop unrelated Worker B.
- Stop remains effective through an event replay, retry deadline and server restart.
- A normal direction alters the relevant assignment only; it does not cancel every review merely because a user message exists.

### Step C — direct specialists, worker capacity, and the Full Auto panel

Remove the mandatory GC per ticket. A ticket is claimed by the worker that will do the work. Preserve the assignment records, continuations, prompt receipts and useful peer communication; replace GC-only ownership and return routing. Migrate active GC assignments explicitly so this change does not strand their tickets, lose results or launch duplicate workers.

The triage agent names an existing specialist or requests one from a short-lived role-creation agent. A role definition contains its purpose, relevant expertise, responsibilities, required context and how it judges the work complete. Publish it using the existing versioned role service as metaform://role/<name>. Reuse it for later compatible work; concurrent requests for the same missing role share one creation job.

Every ticket assignment carries the project, functional address, requested result, role URI and selected version, relevant context resources, evidence/reproduction, completion check, authority scope, and return destination. Worker startup resolves and reads the URI; a recorded receipt establishes delivery before work begins. A missing role goes to a visible role-creation state with automatic continuation, not a silent generic-worker fallback. Context replacement re-delivers what the worker needs. Role updates preserve the version already used by an attempt.

Keep startup context compact: advertise the role and relevant instruction URLs, then deliver their complete selected content through resource reads. Do not replace a role read with a longer connect-message dump. Verify that the worker can actually discover and invoke its required map, memory and work-record tools; receipt of a prompt that names unavailable tools is insufficient. Existing useful memory and worklog obligations remain part of the handoff.

Use the existing project and machine settings for worker limits. Relabel the UI “Max workers on this machine” and “Max workers in this project”; migrate existing values and provide compatibility for old keys. Ticket workers and additional agents doing ticket work consume worker slots. The advisor, scheduler and bounded role-creation helpers do not consume those slots. A reviewer doing substantial ticket work is a worker, not an unlimited exemption.

Admission and reservations must be atomic across projects. Fair selection prevents one project's queue starving another. A worker waiting for a child specialist must release execution capacity or use a continuation so a limit of one cannot deadlock. Lowering a limit stops new admissions and lets current work drain unless the user explicitly stops it.

Exempt automation still needs deduplicated requests, bounded lifetimes and cancellation. Exemption is not permission to spawn unbounded coordinators. Resource pressure may pause new work with a clear reason while preserving user control.

Build one coherent Full Auto panel, with global worker capacity and a project configuration view:

| Control | Required behavior |
|---|---|
| Manual / Assisted / Full Auto / Custom | Presets set the underlying controls together; individual edits show Custom and the effective policy. |
| Capture faults | Enable sources and watched logs; expose watcher health and the last captured event. |
| Create and triage tickets | Group occurrences, attach evidence, supply a task and specialist. |
| Start ready work | Start according to dependency, worker and budget limits. No extra invisible confirmation gate. |
| Recover failed workers | Resume/reassign verified dead attempts; respect explicit user stops. |
| Verification and review | Require proof of repair; show whether a bounded review is enabled. |
| Engineering adaptation | Permit repairs and specification adaptation within C(T); notify the user of adaptations. Purpose changes remain a user decision. |
| Sensitive actions and approvals | Show the precise actions the user has chosen to gate. The error text itself does not determine authority. |
| Worker limits and budgets | Show global/project usage, queued work and the exact reason a ticket is waiting. |
| Pause / resume / stop | Distinguish pausing new admissions from cancelling current work, with project or system scope. |

Preserve explicit user settings and holds during migration. Identify old automatically imposed holds and reconcile them against the selected policy; do not release every held ticket indiscriminately.

Expose both the effective orchestration policy and the agent adapter's permission mode. An approve-all adapter setting cannot fix a prompt that independently demands permission for every ticket, and a Full Auto toggle cannot override an adapter that is waiting on a tool approval. Keep role prompts, command gates, saved policy and adapter behavior consistent. Explain a pending approval by its actual source and action, with a working answer path in chat.

Acceptance:

- With global capacity three and project capacities two each, two active projects use at most three workers and neither exceeds two; both make progress.
- At full worker capacity, the user can still reach triage and a missing-role creation job can complete.
- A worker's trace shows the exact role resource and version it read. A missing role is created once and the original ticket continues once.
- One capacity slot completes a ticket requiring specialist input without a GC occupying it.
- Full Auto off prevents automatic admission and retry launches; explicit user actions still work. Full Auto on repairs eligible faults without per-ticket approval.

### Step D — a board owner and a complete self-healing loop

The triage agent is accountable for board health. An event-driven supervisor performs routine reconciliation and sends the advisor only actionable exceptions and concise summaries. This supplies ownership without giving the user another always-busy coordinator to wait for.

Begin reconciliation with the packet's distinct failure classes. Separate ended attempts from executing work, retain explicit user stops, and make dispatch holds visible in the same board state as ordinary holds. Record the latest admission decision per ready ticket: policy, dependency, hold, role, worker capacity, budget, reservation or runner availability, with the event that will reconsider it. A ready ticket with no owner and no reason is a supervisor exception. This directly addresses the unclaimed `cf26d1e5…` fault without guessing its historical blocker.

Implement the complete sequence:

    fault observed → canonical issue identified → evidence and repair task prepared
    → specialist selected/created → ready ticket claimed → repair performed
    → reproduction and completion checks executed → verified resolution
    → recurrence reopens the canonical issue

Retain current fault grouping. Add a durable issue identity that connects log faults, manual reports and reviewer findings when they demonstrably describe the same cause at the same functional scope. Repeated deliveries are idempotent. A returning fault reopens the same ticket with a new attempt and evidence; a demonstrably different cause may get a linked ticket. Never deduplicate solely on a similar title.

A raw error is an observation. Triage turns it into an executable ticket: what purpose is failing, observed versus expected behavior, evidence and reproduction, concrete investigation/repair instruction, specialist URI and completion check. Unknown diagnosis is allowed: the task can require isolating it. Missing information must produce a visible next action rather than an idle card.

Use one bounded verification/review cycle tied to the ticket and candidate revision. Findings repair the current work where possible. Repeated assessments of an unchanged candidate do not create more assessments or new tickets. A separate ticket requires a distinct gap and a deduplication check. Coordinate overlapping edits through the existing claims and isolation mechanisms; avoid coarse locks that make an entire functional branch unavailable. The user can redirect or revoke a claim, and workers receive the rules for that coordination before it is enforced.

Log watching must have an owner and lifecycle. Intake/onboarding configures relevant log sources, validates an injected sample error, and records them for supervised restart. A greenfield project with no logs records that fact and adds them when it gains a runtime. Source-specific watchers use the existing file notification/event mechanisms; browser faults and runner faults use their existing events.

Completion requires exercising the reproduction or an appropriate test. “No new errors” counts as evidence only when the failing path has actually run over a defined observation window. A stopped watcher or zero traffic is not proof. A worker crash, exhausted retry, stale reservation or unavailable tool becomes an explicit state with its responsible next action.

Board presentation uses open work plus recent verified completions; older work remains searchable in the existing Archive. Preserve “Line in the sand”. Read progress from bounded aggregates/deltas rather than loading every historical ticket. Display runner loss, blocked dependencies, missing role, hold, budget and capacity as clear waiting reasons.

Existing work is the starting point. For example, `8f748f7c…` already concerns proactive fault notification and `98c9bc72…` concerns head-agent orchestration; both are dispatch-held in this packet. `43ed7b09…` concerns agent communication. Verify current scope, preserve useful evidence, and adapt canonical work to the approved implementation slice instead of filing a second copy of each requirement. The correction tree rooted at `5decae95…` is a bounded migration fixture, not a reason to reopen every historical correction.

Acceptance:

- A thousand repetitions of one fault yield one ticket with a thousand occurrences, one active repair attempt and one result delivery.
- With Full Auto on, an injected known failure produces a useful task, launches the appropriate specialist and reaches verified completion without the user tending the board.
- Reintroducing the same failure reopens that ticket. Replaying events, restarting the watcher and rotating logs neither loses occurrences nor multiplies tickets.
- A correction review cannot recursively flood the board with reviews of itself.
- Dead runners recover according to policy; stopped-by-user sessions stay stopped.
- Archive and progress reads remain bounded with thousands of historical cards. Unrelated events cause zero work-store reads.

### Step E — independent projects and routed communication

Bind every tab to its own explicit project and base. Use the URL as the shareable selection and tab-local state for restoration. A server-level opened-project event updates discovery or offers navigation; it must not force every existing tab to change project. Browser-wide preferences may remain shared, but active project selection must not be.

Project sessions belong to the project, not the selected tab, visible figures or open chat pane. Keep the scheduler and log watchers alive independently of navigation and client subscriptions. Reuse the existing home launch ledger and event system; avoid inventing a separate scheduler for each page.

Keep a resumable advisor conversation for each project and show its identity in chat. Navigation must not silently retarget an existing conversation or move a worker's assignment to a different base. A person viewing project B can explicitly address project A's advisor or worker while both continue their work.

Add project-aware messaging addresses: destination project plus stable session/assignment, with sender project and identity included. Preserve threaded replies and correlate deliveries; show accepted, delivered, failed or waiting states. A reply targets its original session/assignment rather than whoever later takes the old ticket. Ordinary cross-project messages carry information; a user command retains its actual delegated scope.

Acceptance:

- Run work in two projects in two tabs. Switching, refreshing and closing either tab preserves workers and the other tab's view.
- Fresh tabs restore the explicitly selected project instead of inheriting an unrelated global opened project.
- Exchange a message and reply across projects, including during a reconnect, with one user-visible delivery and correct attribution.
- Explicit Stop project A affects A only; a separately scoped system-wide stop affects both.
- Reproduce the reported switch failure while checking actual process and session state, so a display reset cannot masquerade as a fix.

### Step F — repair intake and CEL semantics

The base is a functional map. It records elements and the relationships in which a receiver's operative purpose is served by a provider's Encounter Function. Paths, implementation technologies and inspection status do not replace that structure.

The screenplay example is useful because it is not software: the director and screenwriter receive a screenplay; scenes provide playable units; headings locate those scenes; dialogue supplies speech. “Scene heading is malformed” is a finding at the affected function, not a new functional element called “checked”. The example's local proof does not imply that the source was independently verified here or that it was persisted in Metaform.

A CEL contributes specific knowledge or instructions for an identifiable purpose. It can carry best practices, foresight, required actions, workflows, or property-specific context. It may introduce meaningful elements and joins of its own. It should not mirror every base node without adding information.

Use these semantic fixtures as the contract:

| Setup | Required effective context |
|---|---|
| A platformer layer is attached at code.engine.game. | Relevant platformer knowledge is available at the game and appropriate descendants, including rules and controls. Layer-owned records retain their provenance and can be removed from context with the layer. |
| A code.cpp property/knowledge scope is linked at code.engine, containing cxx23 guidance. | Applicable C++/C++23 instruction content reaches the engine, game and their descendants. It does not reach the adjacent code.installer branch. |
| A code.bash scope is linked at code.installer. | Applicable Bash content reaches the installer and its descendants. It does not reach the engine. |
| A narrower property is linked below a parent scope and the parent layer is masked there. | The narrower branch gets the selected replacement context; siblings retain their original context. |
| A layer is disabled for context or removed from selection. | Its instructions and layer-owned contributions disappear from effective worker context, with the base and history preserved. A display-only visibility control must be clearly distinct. |
| A user asks about a trunk node. | Applicable instructions are distinguished from an optional descendant inventory. Descendant guidance must not become a trunk imperative or leak across siblings. |

The first implementation should get applicability, meaningful content and masks right. Ancestor inventory is secondary; it can be an explicit inspection view instead of default worker prompt content. Functional joins do not become transitive merely because some property-scoped guidance is transitive.

Give a layer a meaningful name describing its purpose or property, with a stable identity, explicit attachment scope and record provenance. Support the supplied platformer/code.cpp/code.bash examples. Resolve the existing scope@content versus layer-root naming inconsistency once in the schema, prompts, API and UI; avoid making display labels or string parsing the only source of scope.

Determine what each tagged record actually means before migrating it: local evidence stays local; deliberately scoped instructions participate in inheritance. Copying every attached item to descendants would be as wrong as inheriting only a bare “C++” label while omitting its instructions. Worker context must say why a piece applies, where it comes from and which masks/selects affect it.

Move checked/ok observations to assessment/provenance state or a purpose-built inspection view. Keep useful evidence and links; omit routine success markers from the functional graph and default worker context. Existing useful knowledge must not be deleted because a layer name is poor. Classify and migrate legacy empty/bookkeeping layers reversibly.

Do not identify an empty layer by item count alone. A layer can own meaningful elements/joins or module records; the imported memory and agents layers demonstrate why inspection must consider their actual contents and purpose. Eliminate automatic scaffolding that carries no knowledge after that classification.

Intake must work for brownfield, greenfield and non-code artifacts. After recording, read the map and effective context back through the same interfaces workers use. Proof checks connectivity, purpose/encounter coherence, evidence, layer usefulness and scope—not the number of green nodes.

Acceptance:

- A controlled Flask intake creates meaningful functional relationships and purposeful layers, without hundreds of green success markers.
- The screenplay example survives a round trip with its functional meaning, refs and findings intact, without coding-specific assumptions.
- The platformer/C++/Bash fixtures pass through storage, CLI, MCP context assembly and the viewer. Masks stop applicability at the intended branch.
- A worker asked to act at game controls receives the relevant instructions and not installer guidance. Disabling the layer for context removes that guidance from the next fresh context; it cannot erase tokens already delivered to an active model turn.
- A layer adds only records carrying useful information; assessment status remains available without cluttering the map.

## 4. Implementation boundaries and delivery units

Implement the control fix first, then scheduling/roles and the fault-to-repair loop. Project isolation can proceed alongside scheduling once actor and session identity are settled. Agree the CEL contract early; implement its migration and intake correction against that contract after the control path is reliable.

Keep delivery units bounded and reviewable:

1. User authority, sticky stops, and a responsive message queue.
2. Direct specialist assignment, role-resource delivery, GC retirement and assignment migration.
3. Worker accounting plus the global/project Full Auto panel.
4. Canonical issue lifecycle, actionable tasks, bounded review and supervised fault capture.
5. Tab/project isolation and cross-project messaging.
6. Assessment-state migration, CEL applicability and intake readback.
7. Integrated validation, board reconciliation and rollout.

These are proposed implementation slices, not seven new tickets automatically added to the current board. Match them to canonical existing work first. Each slice includes schema compatibility where needed, tests of its behavior, prompt/spec changes, documentation and removal of superseded paths.

Reuse the existing event bus, module contracts, role/prompt store, launch ledger, file watchers, archive and selection/mask engine. A new abstraction must solve a demonstrated gap rather than duplicate those systems.

The changes primarily touch these existing boundaries:

| Delivery unit | Source owners |
|---|---|
| Identity, stop, priority and triage | dispatch command ingress, runner adapters/queues, module command authorization, user-facing role prompts |
| Specialists and GC retirement | orchestration state/service, agents role resources and receipts, dispatch launch/handoff |
| Worker limits and policy | dispatch launch ledger/admission, settings declarations, web settings and board controls |
| Self-healing and board state | autoticket faults/watchers, orchestration assessment, map work/status, web dispatch scheduler and board/progress reads |
| Project isolation and messaging | web project navigation/live stream, home/base selection, dispatch session identity and peering |
| CEL and intake | intake recording/prompts, data context/resolver/selection, map/MCP context serving and viewer layer rendering |

The older report also contains voice, roundtable, graphics and other defects. Preserve those existing issues and expose blockers the repaired system can act on. This phase does not silently expand into rebuilding those features. Tool availability, meaningful memory notices and specification/test mismatches that block these six units are dependencies and must be resolved with them; a per-module MCP-router rebuild needs its own design justification rather than becoming a prerequisite by assumption.

## 5. Migration, rollout, and definition of done

Preserve a recoverable database snapshot and record its schema/version before migration. Run migrations on a copy first. Preserve ticket IDs, history, useful evidence and explicit user decisions. Reconcile duplicate tickets into canonical histories with links; archive redundant presentation without destroying the record. Map old agent-count settings to worker limits visibly. Preserve active session ownership while retiring GC state.

Do not silently rewrite the live production board during the planning or diagnostic import. Implementation rollout begins with one controlled project and a small worker limit, then two projects concurrently. Raise throughput after the admission, cancellation and recurrence checks pass.

Close the stale-code gap as part of self-healing. Record the code revision, schema compatibility and prompt version actually loaded by the server, MCP services and runners. A completed repair must distinguish files changed from the running service updated. Reuse existing handover support for a supervised restart/reconnect at a safe boundary: preserve sessions, queued user commands, ticket ownership and sticky stops; pause new admissions only for the handover; verify readiness before releasing them. Resume an existing attempt or release its claim atomically so old and new processes cannot both execute it. Keep the failure and rollback path visible if the new revision cannot start. Do not silently terminate other projects to update the selected one.

Readiness is demonstrated by one integrated scenario:

1. Two projects run concurrent workers and independent tabs.
2. A watched failure generates one actionable ticket and one specialist assignment; a missing role is created at its Metaform URI.
3. The worker reads that role, fixes the failure and proves it.
4. During the repair and heavy notification traffic, the user reaches triage, changes priorities and stops a selected agent.
5. The stop persists; the other project continues; a cross-project message and reply arrive once.
6. The same error recurs and reopens its existing ticket.
7. A fresh intake and worker-context read show useful scoped knowledge without checked-node clutter.
8. Restart the server/supervisor and reconnect clients: settings, role versions, tickets, stopped state and routing survive without duplicate launches or stale executable code.

Measure acknowledgement/cancellation latency, worker-limit compliance, queue delay by cause, duplicate issue/launch/delivery counts, watcher continuity, board payload/render cost, and relevant idle/event-processing CPU. Use the existing event architecture; do not meet performance targets by dropping events, throttling the map or hiding failing work.

Run focused behavioral tests per slice, then the relevant combined dispatch/orchestration/autoticket/intake/layer suites and browser scenarios. Update stale fixtures only after deciding the intended semantics. For every remaining failure, record its cause and impact; a passing subset does not establish a fully functioning system.

For changed event handlers, measure idle CPU over 60 seconds and prove irrelevant event bursts cause zero reads, as required by the repository. For changed graphics hot paths, measure actual frame cost. Setup already exposes unrelated baseline failures; keep those separate from newly introduced failures and acceptance checks that remain blocked. Run the integrated scenario through the same UI, CLI and MCP boundaries used by the person and workers, not only mocked helper calls.

Proposed defaults for review: keep one bounded quality pass on the same ticket; retain seven days of done work on the board; make Full Auto mean automatic repair within the user's chosen policy; preserve existing explicit configuration during migration. None of these choices should stall the authority and responsiveness fixes.

The phase is complete when the user can direct the system while it works, faults progress through repair and proof without tending, the board remains understandable, projects coexist, and workers receive the knowledge that applies to their work.

## Implementation record — 2026-10-19

The implementation, compatibility checks and remaining baseline failures are recorded in [phase-one-implementation](../reviews/2026-10-19-phase-one-implementation.md). User authority/priority, direct specialists, worker accounting and policy controls, canonical fault/review handling, supervised watches, tab/project isolation, cross-project routing, scoped CEL context and intake assessment metadata are implemented. The packet was upgraded only on a copy; all 146 explicit stops were retained. Runtime replacement on a separate installation remains an installation action, not a consequence of pushing source.
