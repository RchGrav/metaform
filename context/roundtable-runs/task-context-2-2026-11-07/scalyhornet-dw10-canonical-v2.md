# D-W10: Agent Task-Context Selection — canonical specification v2 (FINAL)

Author: ScalyHornet. Consolidates the full roundtable consensus including all
corrections through round 6. Status: **lockable** — the single definitive
answer to W-5.6 / D-W10 under W-11.6.

## 1. Decision

The world server selects a brief, targeted subgraph **tour** of the world
graph (W-5) and delivers it by **push envelope + pull deepening** over ACP
(W-11.7). Selection is structural, deterministic, and terminates on graph
structure — never on task vocabulary and never by re-testing link types.

## 2. Task classification (before seeding)

| Class | Test | Seed | Built from |
|---|---|---|---|
| `create` | the **primary subject** (the entity the task mainly acts on) resolves to zero entities | the roles, from intent (W-5.5) | role obligations + host capabilities + reusable assemblies + requested links |
| `modify` | the primary subject resolves | those entities | the bidirectional structural fixpoint |

- **Class is governed by the primary subject, not the verb list.** The primary
  subject is the object of the main verb ("door" in "build/fix a door…").
  If it resolves → `modify`; if not → `create`. FangedMercy's build-verb list
  ("build/make/create/place") is used only as a **confirmation heuristic**, not
  the authority — this avoids fragile verb enumeration and handles a mixed
  task ("build a door that opens when the [existing] lever is pulled") where
  the primary subject (door) does not resolve → `create`, and the existing
  lever enters via normal resolution as a referenced dependency.
- **Mixed tasks:** secondary named roles that do not resolve are reported in
  `unmet_ports[]` as `create:` elements, regardless of class (DirectCobalt).
  The class test stays binary.
- `task_class` is in the push envelope. Without it an empty create packet is
  indistinguishable from a complete one.
- **Flip-to-modify (FangedMercy):** the resolver is one machine, two phases.
  As the agent builds, each new entity/link bumps `graph_seq`; on the next
  context computation the classifier re-runs, and if a previously-created
  primary subject now resolves, the **same `tour_id`** flips
  `create → modify` and the fixpoint runs over the now-existing subgraph. One
  staleness mechanism serves both phases.
- **Ambiguity-as-question is valid only in `modify`.** In `create`, the
  legible failure is "no assembly matches" (or `needs_narrowing` naming the
  frontier role), never "which door?" — a door that does not exist cannot be
  disambiguated.

## 3. The `modify` selection fixpoint

Seed = all named entities (always included). Walk to a fixpoint (per-port
visit counter 2) in both directions:

- **Producer side:** follow type-matched links into any inbound port whose
  goal is unmet.
- **Consumer side:** for any port the task *modifies*, include its other
  consumers (boundary contract only). Purely additive tasks touch no existing
  consumer → empty.

### `modified(P)` is pinned to a diff, not the user's verb
`modified(P)` := the task's expected end state for P **removes or
contradicts** P's declared `function` fragment (W-5.3). Adding a second
consumer is a superset → additive → no expansion. Driving the bell *instead
of* the alarm removes the alarm → modified → alarm's boundary contract enters.
This makes the consumer side deterministic regardless of whether the user
typed "add" or "repurpose."

### Non-link edges
Follow joints (W-4.4) and grant handles (W-7.4) the task's behavior uses.

### Termination — classify each non-seed entity (from `function`+`intent`, W-5.3)
| Role | Test | Example |
|---|---|---|
| **Sink** | inbound AND (holds a handle W-7.4 OR has unlinked outbound) | door |
| **Blocked_sink** | sink, but the *requesting agent* does not hold the grant | door's motor granted to another session |
| **Through** | inbound+outbound OR equal `function` fragments | relay |
| **Consumer-only** | inbound, no outbound — never entered | pump/lamp on shared channel |

- Missing `function` → through, flagged `low_confidence`, widens one line.
- Any path between two named seeds is admitted in full (adapter).
- No type re-testing: W-5.4 type-checked each link at creation; W = path
  existence. (Per-link equality is correct; comparing across the whole chain
  was the earlier mistake.)

## 4. `blocked_sink` and grant evaluation

Handle grants (W-7.4) are made by the builder within admin permissions
(W-9.3); the task agent need not be the builder. So "entity holds a handle"
(structural sink) and "this agent may drive it" (operational) are distinct
facts. Evaluate grants **at selection time against the requesting agent**
using `user_grants[]` in the envelope. A structurally-sink entity the agent
cannot drive is rendered `blocked_sink`, listed in `blocked[]`, rendered
`UNREACHABLE`. The agent's plan then begins with "request the grant," not
"drive what you cannot reach."

## 5. Multi-inbound frontier (BluntDiode's permit/enabled case)

A connected port is not satisfied behavior. A through/sink entity declaring
**more than one inbound port** contributes the extra inbound ports as a
**frontier**, even when their goals look met — because "met" is not checkable
from prose (W-5.3 `goal` is prose, not a predicate). One line per extra
inbound port, naming the port and any resolvable source. This exposes the
deciding `enabled` dependency of the permit case without pulling in irrelevant
subgraphs.

## 6. The `create` selection fixpoint (over roles)

Same machine, run over roles instead of entities. A role's requirement is its
named behavior in the intent. A requirement closes when a host capability
(W-7.2, W-4.4, W-7.5) can realize it; it opens when the intent names behavior
the host interface cannot express → reported in `unmet_ports[]` as a missing
capability.

The create packet carries:
- roles with goal-bearing ports
- capabilities (ports, actuators/joint motors, handles)
- top-3 W-9.4 assemblies by port signature (Voyager 11.2 pattern) — the agent
  reuses a tested assembly
- **template type-choice (FangedMercy C3):** if two+ assemblies match a role
  by name but differ in WIT port type (e.g. "lever" with `out:bool` vs
  `out:f32`), the packet surfaces the type-choice as a short option list —
  it never silently picks one. This is the create-side analogue of W-5.4's
  type safety; a wrong silent pick would produce a component that cannot link.
- **`requested_links[]`** — the causal wiring between roles (e.g.
  `lever.out:bool -> door.in:bool (requested)`), derived from the task's
  causal structure. This is the actual build instruction. It lives under the
  **requested** field, never observed — nothing is fabricated, and the
  "planned wiring ≠ existing wiring" rule holds.

## 7. Rendering

- Per entity: manifest ports (name/intent/type/goal/function), description
  ~20 tokens, intent record, current link/joint/handle state, `blocked`/
  `UNREACHABLE` marking where applicable.
- **Three-way distinction:** declared (intent) vs observed (actual state) vs
  requested (task text). Conflicts surfaced, never silently resolved.
  In `create`, observed is empty by construction (brevity feature, not a
  missing field); declared + requested remain.
- Deterministic order: seed first, fixpoint distance, entity id.
- Exclusions (default): code/WASM, voxels except link path if busstone, world
  params unless touched, off-path entities with satisfied goals.

## 8. Budget and honesty

- Token budget: per-install configurable constant, default 512 (400 valid).
- Required contracts never silently cut: else `needs_narrowing` + frontier.
- Non-required detail may drop with `omitted: N`.
- In create, if the assemblies + `requested_links` do not fit, name the
  frontier role.

## 9. Delivery and staleness

- Envelope: `{task_id, task_class, subject_id, trigger_id, user_grants[],
  budget_tokens, unmet_ports[], blocked[], tour_version, graph_seq}`.
- Pulls: `get_task_context(tour_id)`, `expand_port`, `describe_entity`,
  `renderSubgraph`.
- **Staleness:** monotonic `graph_seq` (W-8.3 total order) + `changed:`
  one-liners. **Version all records read** — not just links/handles: an
  edited intent/`function` record must invalidate. Watch **adjacency queries
  including empty ports**, where a newly attached link changes the answer.
  `graph_seq` distinguishes own-write from others'-write (re-plan vs resume).
- **Trace:** server-side, per-fact reason (`task-root`,
  `consumer-of-modified-port(port, declared_function, planned_end_state)`,
  `joint-used-by-actuator`, `through-relay`, `blocked_sink`). Not charged to
  the agent's context. If a check passes but an entity's trace reason changed
  since the previous run, treat that as a failure too.
- Lifecycle: tour created at start, closed at end; long tasks refresh with the
  same `tour_id` + `graph_seq`.

## 10. Falsifiable checks (all must hold)

1. Modify, honest generic relay → door admitted.
2. Modify, shared relay feeding pump → pump absent.
3. Modify, adapter bool→f32 between seeds → admitted by path-to-sink; a
   direct bool→f32 link rejected by W-5.4.
4. Modify, lever repurposed (bell instead of alarm) → alarm boundary contract
   enters; additive lever→door → no consumer expansion.
5. Create, "build a door that opens when a lever is pulled" → `class: create`,
   two goal-bearing roles, ≤3 templates or explicit no-match, a
   `requested_links` entry, and does NOT ask "which door."
6. Ungranted handle → entity in `blocked[]`, rendered UNREACHABLE.
7. Two-input controller with `enabled=false` → extra inbound port appears as
   frontier, not satisfied; permit's deciding role exposed.
8. Verb-vs-diff: a task whose verb says "repurpose" but whose end state is
   additive → zero consumer expansion.
9. Empty `function` → widen one line, low_confidence, the still present.
10. Missing link → `unmet_ports[]` names it; nothing invented.
11. Empty-scope create (fresh/void region) → returns intent + role signatures +
    capabilities + `create_requirements`/`unmet_ports[]`, no invented IDs, and
    NOT "which door?" (FangedMercy C1).
12. Flip-to-modify: the same task, once the door entity exists, returns the
    `modify` fixpoint output over the now-existing subgraph, not the scaffold
    (FangedMercy C2).
13. Template type-choice: two assemblies matching "lever" with `out:bool` vs
    `out:f32` → surfaces the type-choice, never a silent pick
    (FangedMercy C3).
14. Mixed task "build a door that opens when the [existing] lever is pulled"
    → `class: create` (primary subject = door does not resolve), with the
    existing lever included via resolution and the door as a create-requirement.

## 11. Non-goals

- No TF-IDF / lexical scoring server-side (pull-side only).
- No per-turn stat/inventory dump.
- No in-game functional-map namespace (W-1.1, W-5.1).
- No core change: selector is a resolver service over LadybugDB (W-2.5).

## 12. Lineage

- Structural fixpoint/sink-through-consumer: LinkedPower.
- create-class fixpoint over roles + templates + task_class: LinkedPower.
- blocked_sink + user_grants evaluation: LinkedPower (round 6).
- modified(P) pinned to planned-write diff: LinkedPower (round 6).
- Multi-inbound frontier (permit case): BluntDiode, operationalized by
  LinkedPower.
- Primary-subject classifier + flip-to-modify + template type-choice:
  FangedMercy (round 6), integrated into the two-class design.
- requested_links + create observed-collapse rule: ScalyHornet (round 5).
- Bidirectional producer/consumer rule: ScalyHornet, confirmed by DirectCobalt.
- Declared/observed/requested: BluntDiode/DirectCobalt.
- needs_narrowing, joint/handle edges, trace: BluntDiode.
- Mixed-task binary classification: DirectCobalt.
- graph_seq + version-all-records-read: LinkedPower + BluntDiode.
- Delivery frame, budget, push+pull: DirectCobalt + ScalyHornet.
