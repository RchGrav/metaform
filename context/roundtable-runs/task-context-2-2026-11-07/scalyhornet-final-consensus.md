# D-W10 final consensus (ScalyHornet v2 — adopts LinkedPower's structural rule)

State: lockable. This supersedes `scalyhornet-consensus.md` (v1), which
contained a contradiction (it said "equal WIT type" in the rule but
"compatibility" in the note) and a circular actuator-stop. Both are fixed
here.

## The selection rule (LinkedPower's structural fixpoint)

**Seed:** all entities named in the task (resolve via entity index; ambiguous
→ ask, never dump). Seeds are ALWAYS included — the sink/through/consumer
table below classifies non-seed entities discovered during expansion, and a
named seed is present even if it would otherwise look like a consumer.

**Expansion (bidirectional):** from the seeds, walk the graph to a fixpoint
(per-port visit counter 2) in BOTH directions, keyed on the semantics of the
change:
- **Producer side (LinkedPower):** for each included entity, follow type-
  matched links into any *inbound* port whose goal is unmet. This is what
  admits the lever and relay for the door.
- **Consumer side (BluntDiode/ScalyHornet):** for any port whose *existing
  behavior the task modifies*, include its other consumers (boundary contract
  only, not their internals). This is the lever→alarm case: repurposing the
  lever must surface the alarm it would otherwise silently break. Purely
  additive tasks (adding a new fan-out) touch no existing consumer, so this
  side stays empty.
- Additionally follow joints (W-4.4) and grant handles (W-7.4) the task's
  behavior uses.
Classify each non-seed entity reached by its port structure:

| Role | Test | Example |
|---|---|---|
| Sink (terminates) | inbound + (≥1 unlinked outbound OR holds a handle W-7.4) | door: inbound bool + joint motor + handle |
| Through (admitted, minimal) | has both inbound and outbound, OR outbound `function` == inbound `function` | relay: bool in/out, `function` "on/off state" both sides |
| Consumer-only (never entered) | inbound with no outbound | pump/lamp on a shared channel |

**Admission vs type-checking:** a path between two *seeds* is admitted in
full at any length — W-5.4 already type-checked every link at creation and
refused invalid ones, so the resolver never re-tests types. Type compatibility
is not a selector concern. (This resolves my Gap 1; LinkedPower is right that
re-testing types was unnecessary.)

**Adapter case:** bool→f32 adapter between two named seeds → admitted by the
path-to-sink rule, not by function equality or type checks.

**Missing `function`:** treated as *through* and flagged `low_confidence:
#id`; the packet widens by one line, never drops the sink.

**Unmet inbound with no link:** recorded in `unmet_ports[]` = the build plan;
nothing invented. Hop count is an output, not an input.

## Delivery (unchanged, converged)

- World server builds the tour (owns the graph; resolver service; no core
  change — W-2.5).
- Push envelope at task start: `{task_id, subject_id, trigger_id,
  budget_tokens, unmet_ports[], tour_version, graph_seq}`. Pull
  `get_task_context(tour_id)`; deepen via `expand_port`/`describe_entity`/
  `renderSubgraph(depth)`.
- Budget 512 tokens; `needs_narrowing` + frontier if required facts cannot
  fit, else `omitted: N` for non-required detail.
- Per-entity fields: manifest ports (name/intent/type/goal/function),
  description ~20 tokens, intent record (W-5.5), current link/joint/handle
  state, handle scope on actuators (W-7.4).
- **Three-way state distinction (required, BluntDiode/DirectCobalt):** each
  entity distinguishes **declared** (intent record, W-5.5), **observed**
  (actual link/joint/handle state), and **requested** (task text). A planned
  connection must never be presented as existing wiring. Conflicts between
  declared and observed state are surfaced, never silently resolved.
- Exclusions: code/WASM, voxels except link path if busstone, world params
  unless the task touches them.

## Staleness (Gap 2, superseded by LinkedPower's graph_seq)

Push-on-change one-liner `changed: <entity>.link|handle (seq N)`, where N is
the monotonic `graph_seq` (world-server link/handle counter; W-8.3 step order
gives the total order free). The agent distinguishes "someone else changed
this" from "I changed this" (e.g. when it itself adds the missing link) —
re-plan vs resume. My earlier version-hash fallback is superseded by this.

## Lifecycle

Tour created at task start, closed at task end; long tasks refresh the
envelope with the same tour_id and graph_seq.

## Inspectability

Server-side inclusion trace with per-fact reason (`task-root`,
`consumer-of-changed-port`, `joint-used-by-actuator`, `through-relay`). Not
charged to the agent's context.

## Lineage (what each part came from)

- Structural fixpoint & sink/through/consumer: LinkedPower (round 3).
- Bidirectional consumer side for modified ports: ScalyHornet (round 4),
  confirmed by DirectCobalt (round 5).
- Declared/observed/requested distinction: BluntDiode, required by
  DirectCobalt (round 5).
- Delivery frame, budget, handle-scope, push+pull: DirectCobalt + ScalyHornet.
- `needs_narrowing` / no silent truncation / joint+handle edges / trace:
  BluntDiode.
- graph_seq staleness: LinkedPower (round 3).
