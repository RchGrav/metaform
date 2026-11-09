# D-W10: Agent Task-Context Selection — Final Specification v3 (LOCK)

Author: ScalyHornet. This is the final, authoritative deliverable of the
roundtable. It consolidates every amendment through round 6 and resolves the
last two open items as recorded decisions. Status: **locked**.

## 0. Decision

The world server selects a brief, targeted subgraph **tour** of the world
graph (W-5) and delivers it by **push envelope + pull deepening** over ACP
(W-11.7). Selection is structural and deterministic — it terminates on graph
structure, never on task vocabulary, and never by re-testing link types.

## 1. Binary task classifier (runs first)

| Class | Test | Seed | Built from |
|---|---|---|---|
| `create` | the **primary subject** (object of the main verb) resolves to zero entities | the roles, from intent (W-5.5) | role obligations + capabilities + reusable assemblies + requested links |
| `modify` | the primary subject resolves | those entities | the bidirectional structural fixpoint |

- **Authority is the primary subject, not a verb list.** The build-verb list
  ("build/make/create/place") is a confirmation heuristic only — avoids
  fragile verb enumeration.
- **Mixed tasks** (primary subject missing, secondary resolves): classify by
  the primary subject; non-resolving secondaries are emitted as
  `create:<role>` in `unmet_ports[]`. The class test stays binary.
- `task_class` is in the push envelope. Without it an empty create packet is
  indistinguishable from a complete one.
- **Ambiguity-as-question is legal only in `modify`.** In `create`, the
  legible failure is "no assembly matches" (or `needs_narrowing` naming the
  frontier role), never "which door?".

## 2. The `modify` fixpoint

Seed = all named entities (always included). Walk to a fixpoint (per-port
visit counter 2) in both directions:
- **Producer side:** follow type-matched links into any inbound port whose
  goal is unmet.
- **Consumer side:** for any port the task *modifies*, include its other
  consumers (boundary contract only). Additive tasks touch no existing
  consumer → empty.
- **Non-link edges:** joints (W-4.4) and grant handles (W-7.4).

### `modified(P)` = planned-write diff (not the verb)
`modified(P)` := the task's expected end state for P **removes or
contradicts** P's declared `function` fragment (W-5.3). Adding a second
consumer is a superset → additive. Driving the bell *instead of* the alarm
removes it → modified. The verb can lie; the diff cannot.

### Termination — classify each non-seed entity (from `function`+`intent`, W-5.3)
| Role | Test | Example |
|---|---|---|
| **Sink** | inbound AND (holds a grant this agent holds OR has unlinked outbound) | door |
| **Blocked_sink** | structural sink, but the *requesting agent* lacks the grant | motor granted to another session |
| **Through** | inbound+outbound OR equal `function` fragments | relay |
| **Consumer-only** | inbound, no outbound — never entered | pump/lamp on shared channel |

- Missing `function` → through, flagged `low_confidence`, widens one line.
- Any path between two named seeds is admitted in full (adapter).
- No type re-testing: W-5.4 checked each link at creation; legality = path
  existence. Per-link equality is correct; comparing across the whole chain
  was the earlier mistake.

### Multi-inbound frontier
A through/sink entity declaring **more than one inbound port** contributes the
extra inbound ports as a one-line frontier even when they look connected —
"met" is not checkable from `goal` prose (W-5.3). This exposes the deciding
`enabled` dependency (BluntDiode's permit case) without pulling in irrelevant
subgraphs. Same "widen one line" principle as a missing `function`.

## 3. Grant evaluation (W-7.4, W-9.3)

Handles are granted by the builder within admin permissions; the task agent
need not be that builder. Evaluate at selection time against `user_grants[]`
for the requesting agent only. A structural sink the agent cannot drive →
`blocked_sink`, rendered `UNREACHABLE`, listed in `blocked[]`. The plan
begins with "request the grant," not "drive what you cannot reach."

## 4. The `create` fixpoint (over roles)

Same machine, run over roles. A requirement closes when a host capability
(W-7.2, W-4.4, W-7.5) can realize it; opens when the intent names behavior the
host interface cannot express → `unmet_ports[]` as a missing capability.

The create packet carries:
- roles with goal-bearing ports
- capabilities (ports, actuators/joint motors, handles)
- top-3 W-9.4 assemblies by port signature (Voyager 11.2)
- **template type-choice:** if two+ assemblies match a role by name but differ
  in WIT port type, surface the choice as an option list — never silently pick
  (the create-side analogue of W-5.4)
- **`requested_links[]`** — the causal wiring between roles (e.g.
  `lever.out:bool -> door.in:bool (requested)`), derived from the task's
  causal structure. Under **requested**, never observed. This is the actual
  build instruction.

## 5. Flip-to-modify (one resolver, two phases)

As the agent builds, each new entity/link bumps `graph_seq`; on the next
context computation the classifier re-runs, and if a previously-created
primary subject now resolves, the **same `tour_id`** flips `create → modify`
and the fixpoint runs over the now-existing subgraph. One staleness mechanism
serves both phases. A design whose two phases are separate resolvers fails the
core integration claim.

## 6. Rendering

- Per entity: manifest ports (name/intent/type/goal/function), description
  ~20 tokens, intent record, current link/joint/handle state, `blocked`/
  `UNREACHABLE` marking.
- **Three-way distinction:** declared (intent) vs observed (actual state) vs
  requested (task text). Conflicts surfaced, never silently resolved. In
  `create`, observed is empty by construction (brevity feature) — declared +
  requested remain.
- Deterministic order: seed first, fixpoint distance, entity id.
- Exclusions (default): code/WASM, voxels except link path if busstone, world
  params unless touched, off-path entities with satisfied goals.

## 7. Budget and honesty

- Token budget: **per-install configurable constant, default 512**, admin-
  overridable per world (400 is a valid tighter setting; it decides nothing in
  the checks).
- Required contracts never silently cut: else `needs_narrowing` + frontier.
- Non-required detail may drop with `omitted: N`.
- In create, if assemblies + `requested_links` do not fit, name the frontier
  role.

## 8. Staleness (version records, not topology)

- Monotonic `graph_seq` (W-8.3 total order) + `changed:` one-liners that name
  `intent|manifest|constraint`, not just `link|handle`. An edited controller
  intent with unchanged wiring must invalidate.
- The pull carries `record_revs{id: rev}` for **every record read**.
- **Empty adjacency results are versioned too** — a newly attached inbound link
  must invalidate an earlier "no link on this port" answer.
- `graph_seq` distinguishes own-write from others'-write (re-plan vs resume).

## 9. Trace and inspectability

Server-side, per-fact reason (`task-root`,
`consumer-of-modified-port(port, declared_function, planned_end_state)`,
`joint-used-by-actuator`, `through-relay`, `blocked_sink`, `frontier-port`).
Not charged to the agent's context. If a check passes but an entity's trace
reason changed since the previous run, treat that as a failure too.

## 10. Lifecycle

Tour created at start, closed at end; long tasks refresh with the same
`tour_id` + `graph_seq`. Envelope:
`{task_id, task_class, subject_id, trigger_id, user_grants[], budget_tokens,
unmet_ports[], blocked[], tour_version, graph_seq, record_revs}`.

## 11. Open items (recorded, non-blocking)

- `output_dependencies: {target: [trigger, enabled]}` manifest field (W-5.3):
  **Proposed, not decided.** Current manifests do not guarantee it. The
  multi-inbound frontier rule (§2) is the stopgap and works today.
- Budget default: resolved in §7 as configurable, default 512.

## 12. Acceptance suite (the lock test)

| # | Check | Owner |
|---|---|---|
| 1 | Modify: honest generic relay → door admitted | LinkedPower |
| 2 | Modify: shared relay feeding pump → pump absent | LinkedPower |
| 3 | Modify: adapter admitted by path-to-sink; direct bool→f32 link rejected | BluntDiode/LinkedPower |
| 4 | Modify: lever repurposed → alarm boundary contract enters; additive → none | ScalyHornet/DirectCobalt |
| 5 | Create: brief's text → `class: create`, two roles, `requested_links`, templates, no "which door?" | FangedMercy/LinkedPower |
| 6 | Ungranted handle → `blocked[]`, UNREACHABLE, "request the grant" | LinkedPower/ScalyHornet |
| 7 | Two-input controller `enabled=false` → extra inbound port as frontier | BluntDiode/LinkedPower |
| 8 | Verb says "repurpose", end state additive → zero consumer expansion | DirectCobalt/LinkedPower |
| 9 | Empty `function` → widen one line, low_confidence, sink present | LinkedPower |
| 10 | Missing link → `unmet_ports[]` names it; nothing invented | LinkedPower |
| 11 | Empty-scope create → roles + signatures + capabilities + create_requirements, no invented IDs | FangedMercy |
| 12 | Flip-to-modify: same task flips once door exists | FangedMercy |
| 13 | Template type-choice: bool vs f32 lever → option list, no silent pick | FangedMercy |
| 14 | Mixed task → `class: create`, existing lever via resolution, door as create-requirement | DirectCobalt/ScalyHornet |

Checks 1–4 are structural and pass by construction. 5–14 are the ones added
after the first lock attempt; 5 and 12 are the ones that decide whether the
design answers the brief (create) and whether the two phases are truly one
machine.

## 13. Non-goals

- No TF-IDF / lexical scoring server-side (pull-side only).
- No per-turn stat/inventory dump.
- No in-game functional-map namespace (W-1.1, W-5.1).
- No core change: selector is a resolver service over LadybugDB (W-2.5).

---

**This file is the deliverable.** It supersedes `scalyhornet-dw10-canonical-v2.md`
and all earlier per-round artifacts. Lineage of every incorporated amendment is
documented in the acceptance-suite ownership column and in v2's §12.
