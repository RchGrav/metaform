# D-W10: Agent Task-Context Selection — Final Specification v4 (LOCK, revised)

Author: ScalyHornet. This is the final deliverable, incorporating the
round-6 corrections from BluntDiode and LinkedPower. Version v3 had three
unfalsifiable acceptance checks (5, 6, 7); they are repaired here. Status:
**locked**.

## 0. Decision

The world server selects a brief, targeted subgraph tour of the world graph
(W-5) and delivers it by push envelope + pull deepening (ACP, W-11.7).
Selection is structural and deterministic. **The resolver never asserts
behavioral success.** It reports connection state and behavioral evidence; it
does not judge whether a behavior "is satisfied."

## 1. Role binding (per-role, not a binary class)

Before any expansion, bind each named role in the task:

| Role binding | Meaning |
|---|---|
| `existing(id)` | resolves to one entity |
| `create(requirements)` | the task's object of building; resolves to zero |
| `unresolved` | referenced, resolves to zero, but the role intent is *use/repair*, not build |

- **Search count alone does not establish intent.** A role referenced for
  *repair* that resolves to zero is `unresolved`, not `create` — repairing a
  deleted door is a conflict to surface, not permission to build a
  replacement. A role referenced for *building* that resolves to zero is
  `create`. Finding an unrelated door does not override "build a new door."
- **Task class:** `create` iff the primary subject (object of the main verb)
  binds `create`; `modify` iff it binds `existing`. Mixed tasks carry both
  binding kinds; `unresolved` roles return a question (legal only in `modify`,
  where the thing being modified exists — a nonexistent subject asked about
  under build intent is a create, not a question).
- `task_class` is in the envelope. The build-verb list phrases the follow-up
  question only; it never chooses the class.

## 2. Connection state vs behavioral evidence

For every rendered entity and port, the packet prints exactly:

```
connection:        link-present | none
behavior_evidence: {declared: <intent text>, observed: <link/joint/handle state>,
                    unresolved: <frontier ports>}
```

- **No "satisfied" token appears anywhere.** "Satisfied" is a judgment only
  `goal` prose could supply, and `goal` (W-5.3) is not a predicate. The
  resolver therefore never claims a behavior works; it reports what is
  connected and what is declared/observed/unresolved.
- Host-capability availability (W-7.2) is evidence of what *can* be built, not
  proof the requested *behavior* holds.

## 3. The `modify` selection

Seed = all `existing`-bound roles (always included). Walk to a fixpoint
(per-port visit counter 2) in both directions:
- **Producer side:** follow type-matched links into any inbound port.
- **Consumer side:** for any port the task *modifies* (`modified(P)`, below),
  include its other consumers (boundary contract). **Consumers of a modified
  port enter even if they are inbound-only** — this is the alarm case. The
  old "consumer-only never entered" rule applies only to entities *not*
  connected to a modified port.
- **Non-link edges:** joints (W-4.4) and grant handles (W-7.4).

### `modified(P)` = planned-write diff (not the verb)
`modified(P)` := the task's expected end state for P removes or contradicts P's
declared `function` fragment (W-5.3). Superset → additive; removal → modified.
The verb can lie; the diff cannot.

### Classification of non-seed entities (rendering + boundary, no satisfaction)
| Role | Test | Example |
|---|---|---|
| **Sink** (terminal) | inbound AND (holds a grant this agent holds OR has unlinked outbound) | door |
| **Blocked_sink** | structural sink, requesting agent lacks the grant | motor granted elsewhere |
| **Through** | has both inbound and outbound | relay |
| **Frontier** | >1 inbound port, or a side-dependency exists but cannot be resolved from prose | controller's `enabled` |
| **Consumer-of-modified** | enters via consumer side, even inbound-only | alarm |
| **Unrelated consumer-only** | inbound, no outbound, not fed by a modified port — never entered | pump/lamp |

- A controller holding a motor handle can still depend on an upstream enable —
  it is rendered as Sink OR Frontier (both can apply); never as "satisfied."
- Missing `function` → flagged `low_confidence`, widens one line.
- Any path between two named seeds is admitted in full (adapter). No type
  re-testing: W-5.4 checked each link at creation; legality = path existence.

## 4. Grant evaluation (W-7.4, W-9.3)

Evaluate at selection time against `user_grants[]` for the requesting agent
only. A structural sink the agent cannot drive → `blocked_sink`, rendered
`UNREACHABLE`, listed in `blocked[]`, with an explicit `request:grant
<entity>.<port>`. The plan begins with "request the grant," not "drive what
you cannot reach."

## 5. The `create` packet

Roles bind `create`. Each role contributes goal-bearing ports. The packet
carries:
- roles + their port signatures
- capabilities (ports, actuators/joint motors, handles)
- top-3 W-9.4 assemblies by port signature (Voyager 11.2)
- **template type-choice:** if two+ assemblies match a role by name but differ
  in WIT port type, surface the choice as an option list — never silently pick
- **`requested_links[]`, generated from ports, not prose:** for each ordered
  role pair and port pair with equal WIT type (W-5.4), emit `a.out:T →
  b.in:T`. Door/lever yields exactly one line. If two pairs qualify, emit both
  and `needs_narrowing: which interlock?` (the FangedMercy type-choice rule
  applied to wiring)
- `ids_invented: []` — nothing fabricated; `unmet_ports[]` lists missing
  capabilities only.

## 6. Flip-to-modify (one resolver, two phases)

As the agent builds, new entities/links bump `graph_seq`; the classifier
re-runs; a previously-created primary subject that now resolves flips the
same `tour_id` `create → modify`, running the fixpoint over the now-existing
subgraph. One staleness mechanism serves both phases. Two separate resolvers
fail the core integration claim.

## 7. Budget and honesty

- Token budget: per-install configurable constant, default 512, admin-
  overridable (400 valid).
- Required contracts never silently cut: else `needs_narrowing` + frontier.
- Non-required detail may drop with `omitted: N`.

## 8. Staleness (order + authorship)

- Monotonic `graph_seq` (W-8.3 total order) gives order.
- `graph_seq` alone does not give authorship. Correlate with **mutation
  operation IDs** (`op_id`) so the agent recognizes its own writes.
- `changed:` notifications name `intent|manifest|constraint` as well as
  `link|handle`, and carry the `op_id` and `graph_seq` they follow.
- The pull carries `record_revs{id: rev}` for every record read; **empty
  adjacency results are versioned** (a newly attached inbound link invalidates
  an earlier "no link" answer).
- **Commit version check:** when committing a dependent edit, re-check the
  version the notification was based on — another builder may have changed the
  world after the notification.

## 9. Trace

Server-side per-fact reason (`task-root`, `consumer-of-modified-port(port,
declared_function, planned_end_state)`, `joint-used-by-actuator`,
`through-relay`, `blocked_sink`, `frontier-port`, `seed`). Not charged to the
agent's context. If a check passes but an entity's trace reason changed since
the previous run, treat that as a failure too.

## 10. Lifecycle

Tour created at start, closed at end; long tasks refresh with the same
`tour_id` + `graph_seq`. Envelope: `{task_id, task_class, role_bindings,
user_grants[], budget_tokens, unmet_ports[], blocked[], tour_version,
graph_seq, record_revs}`.

## 11. Open items (recorded, non-blocking)

- `output_dependencies: {target: [trigger, enabled]}` manifest field
  (W-5.3): Proposed, not decided. The Frontier rule (§3) is the working
  stopgap.
- Budget default: §7, configurable, default 512.

## 12. Acceptance suite (positive, falsifiable)

| # | Check | Owner |
|---|---|---|
| 1 | Modify: honest relay → door present (door is a seed) | LinkedPower |
| 2 | Modify: pump absent (unrelated consumer-only, not fed by modified port) | LinkedPower |
| 3 | Modify: adapter admitted by path-to-sink; fixture includes a *refused* direct bool→f32 link | BluntDiode/LinkedPower |
| 4 | Modify: lever repurposed → alarm boundary contract enters; additive → none; `modified(P)` diff printed | ScalyHornet/DirectCobalt |
| 5a | `task_class == create` | FangedMercy |
| 5b | roles = [door, lever], each with a goal-bearing port | FangedMercy |
| 5c | `requested_links` contains `lever.out:bool → door.in:bool` | ScalyHornet/LinkedPower |
| 5d | capabilities ⊇ {ports, actuators, handles} | LinkedPower |
| 5e | ≤3 templates with signatures | LinkedPower |
| 5f | `ids_invented == []` | BluntDiode |
| 5g | no ambiguity question | FangedMercy |
| 6a | door#47 ∈ entity_ids (present) | LinkedPower |
| 6b | door#47 ∈ blocked | LinkedPower |
| 6c | reason = `handle_not_in_user_grants` | LinkedPower |
| 6e | explicit `request:grant door#47.motor` | LinkedPower |
| 7 | controller with `enabled=false` → two frontier ports + permit contract + **no "satisfied" token anywhere** | BluntDiode/LinkedPower |
| 8 | verb says "repurpose", end state additive → zero consumer expansion; diff printed | DirectCobalt/LinkedPower |
| 9 | empty `function` → widen one line, low_confidence, seed present | LinkedPower |
| 10 | missing link → `unmet_ports[]` names it; nothing invented | LinkedPower |
| 11 | empty-scope create → roles + signatures + capabilities + create_requirements, no invented IDs | FangedMercy |
| 12 | flip-to-modify: same task flips once door exists | FangedMercy |
| 13 | template type-choice: bool vs f32 lever → option list, no silent pick | FangedMercy |
| 14 | mixed role binding → `create` subject + `existing` lever, lever via resolution | BluntDiode |
| 15 | repair intent on deleted door → `unresolved` + question, NOT create | BluntDiode |

Checks 5a–5g, 6a–6e, and 7 are the repaired forms; each is now positive and
must fail on the empty/omitted/verb-judgment failure modes identified in the
round-6 audit.

## 13. Non-goals

- No TF-IDF / lexical scoring server-side (pull-side only).
- No per-turn stat/inventory dump.
- No in-game functional-map namespace (W-1.1, W-5.1).
- No core change: selector is a resolver service over LadybugDB (W-2.5).

---

**This file is the deliverable.** It supersedes
`scalyhornet-dw10-final-lock.md` (v3), which had unfalsifiable checks 5/6/7.
Revisions in this version: per-role binding (§1), removal of the "satisfied"
judgment in favor of connection+behavior_evidence (§2), contract-boundary
classification with consumers-of-modified entering (§3), port-generated
`requested_links` (§5), mutation-op-ID authorship (§8), and the positive
acceptance checks (§12).
