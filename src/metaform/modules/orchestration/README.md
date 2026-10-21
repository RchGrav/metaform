# Specialist delivery

The orchestration module connects authored responsibilities to ordinary work
records, dispatch sessions and durable continuations. It ships enabled; a
dispatch provider must be available to run its queued assignments. It contributes
native authored responsibilities through `agent.roles`. An authored role and an adapter's
operational execution role are recorded separately.

The user-facing triage agent stays available for questions, overrides and board priorities. A ticket belongs directly to selected reusable specialist expertise, with its exact versioned duty at `metaform://role/<name>`. A missing specialty automatically commissions one bounded Facilitator; concurrent requests for the same specialty share that helper and resume their own contributions after publication.

An independent `functionality` assessment can inspect the delivered candidate. `orchestration_reviews` bounds automatic reviews per canonical ticket (zero by default, enabled by the person). Findings reopen that ticket with the repair instruction and verification steps, preserving prior evidence. They do not build recursive coordinator/correction trees. The legacy `gc` role and identity fields remain readable for existing assignments; new work needs no coordinator per ticket.

## Public operations

An agent normally omits `assignment`; the runtime authenticates its session or
runner identity. The person can supply the selected assignment through the CLI
or UI. `metaform help orchestration` describes every noun.

| Operation | Result |
| --- | --- |
| `claim` | Assign existing expertise, or use create=true to have the Facilitator find or create it. |
| `inspect`, `team` | Read ownership, members, retained correction history and independent assessments. |
| `delegate` | Start a specialist contribution while retaining the caller's responsibility. |
| `call` | Record a specialist call and suspend the caller until its immediate result returns. |
| `handoff` | Transfer a worker contribution to a recorded successor, retaining work and outstanding returns. A delivery GC keeps its validation responsibility. |
| `role_requests`, `commission`, `publish_role` | Inspect an automatically commissioned role request, publish its versioned duty, and continue the original caller. commission remains a compatible idempotent command. |
| `check-in` | Retain progress, candidate, evidence and recovery context, or return the assigned result. |
| `assess` | Give a candidate, GC validation or a functional concern to an independent FQC assignment. |
| `change`, `changes`, `mode` | Publish an operative revision, inspect its delivery, or select adaptive/strict behavior. |
| `bmad` | Inspect supported project-local BMAD entries, actual source/version/menu and managed call descriptor. |

Generic specialist calls to `functionality` and `facilitator` explain the
dedicated assessment and GC-commission routes. Ordinary specialists, including
generated roles, remain callable by workers through their registered identities.

A missing specialty requested by an assessment uses the same helper path. It preserves the original return route without creating another delivery coordinator. Publication never resumes a caller that the user stopped. Stopping one caller also leaves a shared helper available to other unstopped callers.

## Runtime ownership and recovery

The public `orchestration` provider exposes assignment lookup, context,
membership, binding, durable messages, direction, stop/reopen and transition
draining. Dispatch supplies `orchestration.transport`: `guard_claim`, `launch`,
`suspend`, `send` and `notify_user`. Dispatch retains actual process control,
adapter capabilities, the configured capacity admission gate and user controls.
An accepted queued launch is distinct from an actual session binding.
Routing records expertise and assignment while the ticket stays in To do.
Dispatch takes the ticket when it starts a runner, after checking prerequisites.

Assignments, session bindings, role requests, specification changes and pending
transitions live in declared module tables. Work creation/completion and the
corresponding assignment/return share the work store's transaction. Stable call
keys prevent duplicate work; return keys are scoped to the returning assignment
so independently reused specialists can use the same result key.

Waiting callers release their actual process capacity before children launch.
Results target the immediate caller, including a recorded handoff successor.
Pending work is replayed after restart, and every launch asks dispatch to verify
actual liveness and capacity. New direction, retained check-ins, candidate,
evidence and returned children form the next recipient context. A user stop
stores a tombstone and history, cancels pending continuations and reaches
descendants and independent assessments; it preserves already delivered results.
An explicitly admitted user resume clears only the selected stop.

Closed tickets cannot commission runtime choices, and their pending launches complete without starting a session.
Blocked check-ins assess only live delivery work. Role commissions, assessments and their descendants return
blockers without starting another assessment of that delivery. Recovery applies the same checks to retained
blocker transitions. Completed deliveries can still receive their configured independent review.

State changes emit scoped `map.changed` concerns. Completion through the existing
public work board follows the same result/assessment path as `check-in`.
Unrelated table changes do no orchestration reads. A work-table event with absent
ticket concerns reads only indexed active assignments, covering a command that
aggregated another module's unannotated write. No polling scheduler is added.

## Functional adaptation

C(T) preserves the functional core. In adaptive mode, a better approach that
serves C(T) within the full design can replace an operative specification. The
change record preserves before/after content, exact revision, reason, limitation,
source and affected tickets. A change order reaches the affected GCs and current
assignment context. A separate durable operation sends an actual user/PM message
through dispatch; publication does not wait for approval.

Strict mode records and communicates a recommendation while retaining the
operative source. Actual newer user instructions retain their effect. Agent
requests cannot impersonate user instructions merely by supplying that noun.
Intervening source revisions require reconciliation; recovery follows the latest
observed operative source while keeping the original authored change in history.

Files retain their existing locations and modes and are replaced atomically.
Stored workflow logic uses the public workflow history, `add_logic` and `revise`
operations. Active frozen runs get recorded successors; original frames remain
inspectable, and variables, completed branch results, active child return routes
and genuine user-input pauses survive. Recovery follows existing successor
links. Completed runs remain history when a later assessment updates the source.

## Optional installed BMAD roles

No BMAD dependency, external scheduler or copied BMAD role catalogue is shipped.
The bridge discovers project-local `_bmad/_config/agent-manifest.csv` entries and
documented `bmad-agent-*/SKILL.md` installations. Manifest roles use
`bmad.<module>.<name>`; skill entries use `bmad.skill.<name>`. The inspection
resource is `metaform://orchestration/bmad`.

The installed entry text, its activation/menu, source directory, exact hash and
available installation version enter the existing prompt store. Unchanged
sources reuse versions. Source changes preserve history and a selected user
override stays selected; inspection distinguishes the installed menu from the
menu actually served by that selection. Conflicting installed definitions remain
visible as resolver conflicts. Removing a previously resolved source reports
unavailability instead of commissioning an invented replacement.

A call supplies the requested contribution and installed menu input in `task`
(with optional structured `context`). The managed ACP assignment receives the
selected installed duty and follows its actual activation and referenced
resources. Its result returns through the ordinary caller continuation. Global
or plugin-only installations need their own provider. Referenced BMAD scripts,
tools and human-input requirements remain those of the actual installation and
adapter; this bridge cannot make an unavailable command execute.

Installed layouts are documented by BMAD at
[installation](https://docs.bmad-method.org/start/install-bmad/) and
[skills and agents](https://docs.bmad-method.org/reference/skills-and-agents/).

## Verification

The focused store/transport scenarios run with:

```sh
.venv/bin/pytest -n0 src/metaform/modules/orchestration/tests
```

They cover atomic claims, capacity-one nested calls and returns, commissioned
role publication/reuse, independent FQC correction, actual file publication and
message delivery through the transport contract, strict mode/newer instructions,
stop/restart, public-board completion with mixed change events, handoffs,
workflow successor/recovery and installed source/version/menu handling.

The dispatch integration tests additionally use real runner subprocesses and
fake ACP/MCP fixtures to inspect actual recipient turns, cancellations, loads,
prompt receipts, configured admission and user/PM messages. Parsing a prompt or
reading a saved assignment alone is not evidence that the runtime delivered it.

## Specialist selection and facilitation

Assignment selects each ticket's agent, model and thinking level under BASE-066. Jev classifies the task and
chooses from advertised dispatch options within one deadline. Precise coding uses Codex at Medium or higher.
Front-end polish uses Claude. Planning uses the highest-capability advertised model. Research helpers use Low.
Vague coding receives a Planner contribution that refines the original ticket before implementation.

`runtime work=<id>` returns the saved choice or requests a Facilitator choice with the offered catalog.
Only that ticket's commissioned Facilitator can submit `choice=<JSON>` containing agent, model, effort,
task_type, confidence and reason. This uses the Facilitator's full model when Jev is off, uncredited or unanswered.
The choice is saved in map `ticket_settings`, with decider and confidence. Publication requires runtime selection
before continuing each in-place ticket. Runtime-only commissions preserve already assigned expertise.
The card shows and edits the saved choice. Person overrides win. Dispatch applies it to that session without
changing project defaults. Autostart does not classify the ticket again.

Read `metaform://specialists` for the current expertise names, purposes and role URLs. The directory excludes system responsibilities and contains no role bodies. JEV selects a listed specialist or confidently selects none. A no-match, uncertain result, unavailable provider, missing key or unavailable OpenRouter credit commissions the Facilitator directly. An empty inventory does the same without paying for an empty decision.

A ticket writer can assign expertise with `orchestration_claim work=<id> role=<name>` or explicitly hand off with `create=true`. Automatic routing preserves existing assignments and commissions the Facilitator for unassigned tickets without requiring a triage relay. The existing event-driven starter also drains legacy `triage` entries one per pass; unchanged cached decisions are handed off without another JEV lookup. Held tickets and explicit user stops remain effective. The ticket shows “Facilitator is selecting expertise” while its commission is pending.

The Facilitator checks the registry again before authoring. It chooses a reusable domain name when the commission supplies none. Its metaprompt defines the five XML sections: identity, objective, rules, methods and output formatting. Ticket-specific paths, objectives and routing instructions remain in the assignment. The Facilitator publishes with `orchestration_publish_role request=<id> role=<name> purpose=<reusable-purpose> duty=<system_prompt-XML> match_reason=<brief-reason>`. To reuse existing expertise, it omits `duty`; publication never edits an existing role. Concurrent publications with the same name reuse the registered version.

That operation registers the versioned role, binds it to the original ticket, places the ticket in To do and queues its continuation. `column=backlog` instead holds it without queuing a launch. It returns the role identity, match reason, assignment and actual board column, without the prompt body. The Facilitator must report a failed operation as failed; returning a name in chat alone neither registers nor assigns it. User-stopped callers remain stopped. Repeated publication returns the recorded result without launching another worker or revising the role.

The helper runs as `metaform://role/facilitator`, outside worker slots and within existing helper limits. `role_creator` remains resolvable for already recorded assignments. The delivery owner is sessionless while expertise is pending and cannot bind a generic worker before publication.

Completion messages contain only `<address>#<n> complete`. Read the report on the ticket and its assignment evidence explicitly. Claim returns only assignment identity and state. Startup uses MCP tool discovery without duplicating tool schemas in the assignment prompt.
