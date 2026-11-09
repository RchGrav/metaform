# D-W10: Agent Task-Context Selection — Final Specification v5 (Proposed)

Author: ScalyHornet. Final deliverable. Incorporates every participant's
corrections through the final round, including LinkedPower's reversal of the
`blocked_sink` entity verdict and the write-set fallback for `modified(P)`.
Supersedes v4. Status: **Proposed** — this is a specification with an
acceptance-fixture test plan; it has not been implemented or end-to-end
tested in this roundtable.

## 0. Decision

The world server selects a brief, targeted subgraph tour of the world graph
(W-5) and delivers it by push envelope + pull deepening (ACP, W-11.7).
Selection is structural and deterministic. **The resolver never asserts
behavioral success** — it reports connection state and behavioral evidence.

## 1. Role binding — reference-scoped (not global), per-role

Bind each named role **within task scope**, never against the global entity
index as the first test:

Binding order for a named role:
1. explicit entity id in the task (`door#47`);
2. the player's current selection / agent's anchor (W-11.2, W-9.1);
3. global candidates — **only** for `modify` disambiguation ("which door?").

Per-role result:
| Binding | When |
|---|---|
| `existing(id)` | definite reference ("the door", `door#47`) or selection resolves within anchored scope |
| `create(requirements)` | **indefinite reference** ("a door", "build a door") with a build intent — even if a same-named entity exists elsewhere |
| `unresolved(cands)` | referenced for use/repair but nothing resolves in scope; or several candidates (a question) |

- **Global existence never overrides an indefinite build reference.** In a
  populated world, "build a door" binds `create` even though `door#47` exists
  in a distant chunk — targeting that distant door would be a wrong-target
  action. The indefinite article + build intent is a deterministic structural
  signal (a token-class test: determiner + verb), O(1), server-cheap.
- **The question is legal whenever any role is `unresolved`** — not only when
  the whole task is `modify`. Repair intent on a deleted door → `unresolved`
  + question, never auto-`create`.
- `task_class` is derived: `create` iff all bindings are `create`; `modify`
  iff all are `existing`; `mixed` otherwise. It is carried in the envelope.

## 2. Connection state vs behavioral evidence

For every rendered entity and port, print exactly:

```
connection:        link-present | none
behavior_evidence: {declared: <intent text>, observed: <link/joint/handle state>,
                    unresolved: <frontier ports>}
```

- **No "satisfied" token appears anywhere.** "Satisfied" would require judging
  `goal` prose (W-5.3), which is not a predicate. The resolver reports
  connected/declared/observed/unresolved only.
- Host-capability availability is evidence of what can be built, not proof the
  requested behavior holds.

## 3. The `modify` selection

Seed = all `existing`-bound roles (always included). Walk to a fixpoint
(per-port visit counter 2) in both directions:
- **Producer side:** follow type-matched links into any inbound port.
- **Consumer side:** for any port the task *modifies* (`modified(P)`), include
  its other consumers (boundary contract), **including inbound-only
  consumers** — the alarm case. There is no "consumer-only never entered"
  row; the consumer side decides. A non-seed inbound-only entity on an
  unmodified port is never reached by the fixpoint, so its absence is already
  guaranteed — the trace reason is `not-an-open-requirement` (a fixpoint
  statement, decidable).
- **Non-link edges:** joints (W-4.4) and grant handles (W-7.4).

### `modified(P)` — planned-write diff + write-set fallback
- `modified(P)` := the task's expected end state removes or contradicts P's
  declared `function` fragment (superset → additive; removal → modified).
- **Write-set fallback:** the prose diff is not sufficient — a relay→inverter
  swap can change behavior with unchanged `function: "on/off state"` text.
  `modified(P)` is also true if the write set contains a module replacement,
  intent/manifest revision, link removal, or control-target change on P, **or**
  the plan's effect on P is unknown. **Unknown → affected.** Unknown is the
  default for any plan that cuts or replaces a module (i.e. repair work).
- Consumers of a modified port enter with their boundary contract, including
  inbound-only consumers. When the agent produces a concrete edit plan,
  reselect from its write set; exclude existing consumers only when the plan
  explicitly preserves source behavior and link constraints.

### Classification of non-seed entities (rendering weight only — admission is the fixpoint's job)
| Role | Rendering | Notes |
|---|---|---|
| Sink | boundary contract | inbound + (grant held OR unlinked outbound) — terminal |
| Blocked_sink | UNREACHABLE + `blocked[]` | per-role operation check (§4) |
| Through (heuristic) | one line | **not an admission judgment** — string-equal `function` cannot separate relay/inverter/latch/delay; it only decides how much prose to spend |
| Frontier | one line per extra inbound port | multi-inbound; decides side-dependencies (permit case) |

- Missing `function` → through, flagged `low_confidence`, widens one line.
- Any path between two named seeds is admitted in full (adapter). No type
  re-testing: W-5.4 checked each link; legality = path existence.

## 4. Grant checks are per-actor, per-operation (W-7.4)

W-7.4 grants the handle to the **code block**, not the agent: "a code block
acts on another entity... only through a handle that *it* holds." Therefore
"the agent lacks the door's motor handle" is NOT a defect — it is the correct
design. The agent wiring a lever to a controller that holds the motor handle
does not need direct motor access, and must not be given it (that would widen
the capability surface for nothing).

Permission is an `{actor, operation, target}` triple, never a blanket "has
handle" test:

- agent `place-link` — authorized by edit rights.
- `controller#30 drive-joint` — granted to the code block by the builder.
- agent `command-joint` — denied AND unneeded when a controller exists.

`blocked[]` lists **blocked operations with their actor**, not entities.
`blocked_sink` as an entity verdict is removed. Holding a capability never
transfers authority: an agent that holds a motor capability does not grant it
to a controller, and the controller stays blocked without its own handle.

## 5. The `create` packet

Roles bind `create`. Each carries goal-bearing ports. The packet contains:
- roles + port signatures
- capabilities (ports, actuators/joint motors, handles)
- top-3 W-9.4 assemblies by port signature (Voyager 11.2); prefer a template's
  declared port signature over an inferred one, and flag `low_confidence` if no
  template matches (the same one-line-widening principle as a missing
  `function`)
- template type-choice: differing WIT port types → option list, never a silent
  pick
- `requested_links[]` generated **from port signatures**, not prose: for each
  ordered role pair and port pair with equal WIT type (W-5.4), emit
  `a.out:T → b.in:T`; if two qualify, emit both + `needs_narrowing: which
  interlock?`
- `ids_invented: []`; `unmet_ports[]` lists missing capabilities only.

## 6. Flip-to-modify (one resolver, two phases)

A `create` binding flips to `existing` when the agent's build creates the
entity (a `graph_seq` change). The same `tour_id` then runs the modify fixpoint
over the now-existing subgraph. The flip is per-role binding, not a task-class
change. One staleness mechanism serves both phases. Two separate resolvers fail
the core integration claim. Bind a created role to the exact ID returned by its
creation operation — do not re-run free-text search to detect the phase
change.

## 7. Budget and honesty

- Token budget: per-install configurable, default 512, admin-overridable (400
  valid).
- Required contracts never silently cut: else `needs_narrowing` + frontier.
- Non-required detail may drop with `omitted: N`.

## 8. Staleness (order + authorship + stale-commit rejection)

- Monotonic `graph_seq` (W-8.3) gives order; mutations return `{graph_seq,
  op_id}`; `changed:` carries `op_id` so `op_id ∈ {my_ops}` means resume, else
  re-plan.
- `changed:` names `intent|manifest|constraint` and `link|handle`.
- Pull carries `record_revs{id: rev}` for every record read, including **empty
  adjacency results** (a newly attached inbound link invalidates an earlier
  "no link" answer).
- Revalidate `record_revs` at commit of a dependent edit; reject as stale.
  Notifications cannot close the read/write race; a build task writes.

## 9. Trace

Server-side per-fact reason (`task-root`, `seed`,
`consumer-of-modified-port(port, declared_function, planned_end_state)`,
`joint-used-by-actuator`, `through-relay`, `blocked_sink`, `frontier-port`,
`not-an-open-requirement`). Not charged to the agent's context. If a check
passes but an entity's trace reason changed since the last run, treat that as a
failure too.

## 10. Packet schema (the serialization)

```
packet_version: 2
task: {id, text, class: create|modify|mixed, budget_tokens}
roles:
  - {name, binding: existing|create|unresolved, entity_id, requirements}
binding_question: "<only if any role is unresolved>"
entities:
  - {id, role, classify: sink|through(heuristic)|frontier,
     declare: {function_fragment, goal}, observe: {links, joints, handles},
     connection: link-present|none, frontier: [port...], line: "<1 sentence>"}
requested_links: [{from: role.port:type, to: role.port:type, basis: type-match}]
unconnected_ports: [{entity, port, type}]     # wire it
to_create: [{role, requirements, templates: [{assembly, signature}]}]  # build it
unresolved_dependencies: [{entity, port, why}]  # ask
behavior_verification: pending|supported|failed   # never "satisfied"
required_actions: [{actor, op, target, status: authorized|denied|unneeded}]
blocked: [{actor, op, target, reason, needs: "request-grant"}]
record_revs: {id: rev}
graph_seq, op_id, tour_id, omitted: N, needs_narrowing: {frontier}
```

The split of the old `unmet_ports` into `unconnected_ports` / `to_create` /
`unresolved_dependencies` is deliberate: one field named "unmet" covering "wire
this" and "build this" is exactly how an empty create packet looked complete.

## 11. Acceptance suite (positive, falsifiable)

| # | Check | Owner |
|---|---|---|
| 1 | Modify: honest relay → door present (seed) | LinkedPower |
| 2 | Modify: pump absent, trace reason `not-an-open-requirement` | LinkedPower |
| 3 | Modify: adapter admitted; fixture includes a refused direct bool→f32 link | BluntDiode/LinkedPower |
| 4 | Modify: lever repurposed → alarm enters; additive → none; diff printed | ScalyHornet/DirectCobalt |
| 5a | `class: create` | FangedMercy |
| 5b | roles = [door, lever], each goal-bearing | FangedMercy |
| 5c | `requested_links` has lever.out:bool→door.in:bool | ScalyHornet/LinkedPower |
| 5d | capabilities ⊇ {ports, actuators, handles} | LinkedPower |
| 5e | ≤3 templates with signatures | LinkedPower |
| 5f | `ids_invented == []` | BluntDiode |
| 5g | no ambiguity question | FangedMercy |
| 6a | lever→door task: agent `place-link` authorized; door NOT blocked (no false UNREACHABLE) | LinkedPower |
| 6b | agent `command-joint` on the motor → denied as unneeded (controller holds the handle) | BluntDiode |
| 6c | converse: agent holds a motor capability but controller does not → controller stays blocked (no authority transfer) | BluntDiode |
| 7 | controller `enabled=false` → frontier ports + permit contract, no "satisfied" | BluntDiode/LinkedPower |
| 8 | verb says "repurpose", end state additive → zero consumer expansion | DirectCobalt/LinkedPower |
| 9 | empty `function` → widen one line, low_confidence, seed present | LinkedPower |
| 10 | missing link → `unconnected_ports[]` names it; nothing invented | LinkedPower |
| 11 | empty-scope create → roles + signatures + capabilities + `to_create`, no invented IDs | FangedMercy |
| 12 | flip: same task flips per-role binding once door exists | FangedMercy |
| 13 | template type-choice: bool vs f32 → option list | FangedMercy |
| 14 | mixed binding: "build a new door attached to existing lever L12" → `mixed`, lever existing, door create | BluntDiode/LinkedPower |
| 15 | repair intent on deleted door → `unresolved` + question, not create | BluntDiode |
| C4 | populated world: "build a door" with distant `door#47` → `create`, packet excludes door#47, no "which door?" | FangedMercy |
| C5 | definite reference "the door" + selection → `modify`, bound to door#47 | FangedMercy |
| C6 | "build a door" with door#47 selected → conflict/question, never silent pick | FangedMercy |
| C7 | relay→inverter swap (unchanged manifest) → downstream consumers enter impact set via **write-set basis** | BluntDiode/LinkedPower |
| 16 | write-set fixture: relay module replaced by inverter, both `function: "on/off state"` → consumers enter (check 4's prose path alone must not silently pass) | LinkedPower |

## 12. Non-goals

- No TF-IDF / lexical scoring server-side (pull-side only).
- No per-turn stat/inventory dump.
- No in-game functional-map namespace (W-1.1, W-5.1).
- No core change: selector is a resolver service over LadybugDB (W-2.5).

---

**This file is the deliverable.** It supersedes v4. v5 changes: reference-
scoped role binding (FangedMercy), derived `task_class` + per-role binding
formalization (LinkedPower), per-actor/per-operation grant checks reversing
the earlier `blocked_sink` entity verdict (LinkedPower, per W-7.4), the
write-set fallback for `modified(P)` (LinkedPower/BluntDiode), `through`
demoted to a
rendering heuristic and the `consumer-only` row deleted (LinkedPower), the
`unmet_ports` split (LinkedPower), and the concrete packet schema (LinkedPower).
