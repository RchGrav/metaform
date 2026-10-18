# GC-led delivery

The orchestration module connects authored responsibilities to ordinary work
records, dispatch sessions and durable continuations. It ships enabled; a
dispatch provider must be available to run its queued assignments. It contributes
17 native authored roles through `agent.roles`. An authored role and an adapter's
operational execution role are recorded separately.

The Liaison/Triage/PM represents user intent, writes functionally located tickets,
follows delivery and communicates with the user. A GC claims a ticket, coordinates
its swarm, validates the integrated candidate and closes its ticket when the
requested outcome is delivered. `functionality` is the independent Functional
Quality Critic. Its assessment records the reviewed GC and candidate separately
from swarm membership; findings create corrective GC continuations and reach the
PM. Completed delivery remains completed when corrective work follows it.

## Public operations

An agent normally omits `assignment`; the runtime authenticates its session or
runner identity. The person can supply the selected assignment through the CLI
or UI. `metaform help orchestration` describes every noun.

| Operation | Result |
| --- | --- |
| `claim` | Atomically claim an existing ticket as its delivery GC. |
| `inspect`, `team` | Read ownership, members, related corrective GCs and independent assessments. |
| `delegate` | Start a specialist contribution while retaining the caller's responsibility. |
| `call` | Record a specialist call and suspend the caller until its immediate result returns. |
| `handoff` | Transfer a worker contribution to a recorded successor, retaining work and outstanding returns. A delivery GC keeps its validation responsibility. |
| `role_requests`, `commission`, `publish_role` | Record a missing specialty, let its GC commission the Role Creator, then publish its versioned duty and continue the original caller's request. |
| `check-in` | Retain progress, candidate, evidence and recovery context, or return the assigned result. |
| `assess` | Give a candidate, GC validation or a functional concern to an independent FQC assignment. |
| `change`, `changes`, `mode` | Publish an operative revision, inspect its delivery, or select adaptive/strict behavior. |
| `bmad` | Inspect supported project-local BMAD entries, actual source/version/menu and managed call descriptor. |

Generic specialist calls to `functionality` and `role_creator` explain the
dedicated assessment and GC-commission routes. Ordinary specialists, including
generated roles, remain callable by workers through their registered identities.

If an independent assessment needs a missing specialty after its reviewed GC has
delivered, a recorded corrective GC continuation owns that commission. The
original root remains delivered, the specialist still returns to the requesting
assessor, and a user stop prevents the continuation from launching. Retrying the
original call key after publication returns that same commissioned child.

## Runtime ownership and recovery

The public `orchestration` provider exposes assignment lookup, context,
membership, binding, durable messages, direction, stop/reopen and transition
draining. Dispatch supplies `orchestration.transport`: `guard_claim`, `launch`,
`suspend`, `send` and `notify_user`. Dispatch retains actual process control,
adapter capabilities, the configured capacity admission gate and user controls.
An accepted queued launch is distinct from an actual session binding.

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
