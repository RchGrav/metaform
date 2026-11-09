# D-W10 final amendment text — paste-ready (SpinyBreach, round 9)

**Purpose.** The consolidated v3 is correct in substance but carries three residual
defects that a spec reviewer will reject, and its clause labels collide. This file is
the clean replacement text for the W-5.3 addition and the W-5.6 / D-W10 resolution,
suitable for direct amendment. It changes no substance settled in rounds 1–8; it fixes
form and the three open defects. Cross-references to the v3 labels are given so the
merge is mechanical.

**Inputs:** `nimbleengine-dw10-consolidated.md` (v3) plus SpinyBreach §9–§14,
StonyPrism R1-29/31, CloakedEscort freshness amendment, StableReaper change-boundary.

---

## 1. Three defects this text fixes

| # | Defect in v3 | Fix here |
|---|---|---|
| 1 | **A1 omits `allowed_change` and `Δ`.** A7/A7a say selection is a function of `(anchors, intent, accept, scope, verb, Δ)`, but A1's task record has no such fields, so the function is uncomputable as written. (§14.1) | A1 lists both; `Δ` is absent at R0. |
| 2 | **Test 9 asserts the retracted freshness claim.** It says an `accept` result is invalidated "after a delta bumps the hash past s." Physics motion (W-4.4/W-8.3) changes no stored record and bumps no hash, so this test cannot detect the real failure. (§13.1) | Replaced with the step-condition test. |
| 3 | **`unresolved.reason` lacks `adjacency-cap`.** A query that stopped at its limit is reported as `not-inspected`, conflating "did not look" with "looked and stopped." (§14.4) | Fifth enum value added, with a required condition. |

Also fixed: duplicate B6 (v3 lines 66/77), duplicate B6 (v3 line 84), and B4b/B6 label
reuse — the label map is in §4 below.

---

## 2. W-5.3 amendment — one optional port field

Add to the W-5.3 manifest port table:

| Field | Content |
|---|---|
| `stability` | Optional. `maintained` \| `pulse` \| `edge` \| `any`. Default `any`. |

**Semantics.** `stability` records the *consumer's temporal expectation* of what crosses
the port, not a property the producer must have. `any` (the default) imposes no
constraint and therefore leaves every existing manifest, including all W-12.1 content,
valid. A value other than `any` is a contract: a producer edit that changes the port's
temporal behaviour must match it or raise `stability-mismatch`.

**Status:** Proposed. **Reason.** WIT types describe value shape, not timing. Without a
machine-readable temporal field, a boundary check for "this pulse breaks that latch" is
free-text against free-text — undecidable. The field is optional and defaults to no
constraint, so it adds no requirement to existing content and no core capability (W-2.5).

**Placement caveat (Open, H9).** Per-port is the default. If measurement against W-12.1
redstone-like content shows temporal expectations attach to the *receiver relationship*
rather than the port (a torch feeding a repeater vs feeding a lamp), move it to
`link.stability`. The boundary check reads the contract through the retained link, so it
is identical under either placement; the test in §3.3 passes for both.

---

## 3. W-5.6 / D-W10 amendment — the decision text

Replace W-5.6 and D-W10 with the following. Clause IDs are unique.

### A. Selection

**A1. Task record.** A task record carries:

```
anchors        : [entity id | new:<kind>]     // entities the task names or targets
intent         : string                       // W-5.5, verbatim
accept         : [check]                      // observable done-checks, each @step
scope          : local | pattern | area | open
verb           : inspect | build | extend | repair
allowed_change : set of {entity, port?}       // ∩ requester grant, W-9.6
requester      : entity id
Δ              : EDIT-PLAN | absent            // absent at task start (R0)
```

`allowed_change` is the **permission** input: an edit outside it is refused (§3.2
authority 1). `Δ` is the **consequence** input: the boundary is computed from it (§3.2).
Both are needed; neither substitutes for the other. Selection is a pure function of
`(anchors, intent, accept, scope, verb, allowed_change, Δ)`; with `Δ` absent it is the
goal slice only.

**A2. Predicate (multi-edge path).** Retain `e` iff `e ∈ anchors`, or `e` lies on an
anchor→anchor or anchor→accept path in the multi-edge dependency graph, where each path
step is exactly one of:

```
(i)   a W-5.4 port link between WIT-compatible ports;
(ii)  a W-4.2 joint attaching e to the previous entity;
(iii) a W-7.4 handle grant from the previous entity to e;
(iv)  a W-7.2 sensor target read by the previous entity;
(v)   a W-7.3 physics-volume or world-parameter scope that applies to e
      and is set by the previous entity.
```

**A2.1. Type checking is per link.** A port-link step is admissible iff the two linked
port types are W-5.4-compatible. No type is imposed across a path: `L:event → C:event`,
`C:bool → D:bool` is a valid chain and retains `C`. Steps (ii)–(v) have their own
admissibility (a joint has two endpoints; a handle exists only where granted, W-7.4; a
volume is a cell set or world id).

**A2.2. Direct inclusion is declaration-gated.** An entity outside every path is retained
only if it is a joint partner (W-4.2) or held-handle target (W-7.4) of an **anchor**, and
the task's `accept` or that anchor's manifest names it. Justification is *declaration*,
never adjacency through a capability: a bus block holding handles to 40 actuators does
not admit the 40 unless named. Declaration is finite; capability-reach is not.

**A3. No spatial or chunk expansion.** Retention is never by proximity or chunk
membership; a hinge mesh, a decorative block, or a lamp on a side branch is excluded by
A2, not by a cap.

**A4. Depth is a safety guard only** (~8), never the semantic criterion.

**A5. Verb whitelist.** Fields carried depend on `verb`, independent of selection:
`inspect` → anchor manifest only; `build`/`extend` → path slice + anchor handles (W-7.4)
+ assemblies of anchors (W-9.4); `repair` → additionally the last fault record (W-6.3).

**A6. Out-of-grant retention.** If A2 reaches entity X but the requester's grant
(W-7.4/W-9.6) does not cover X, retain a **stub**: `id`, `kind`, `U X
reason=beyond-grant`. No ports, no description. If `accept` cannot be verified without
X's contract, the task is BLOCKED with a message to the requester.

**A7. Two-phase selection.** Phase 1 (R0) delivers the goal slice (A2) only, because `Δ`
does not exist yet. Phase 2 (edit proposal) computes the change boundary from `Δ` and
delivers it as a `validate(Δ) → boundary-delta` (B7). These are one mechanism at two
times, not two rules.

### B. Delivery

**B1. Tier 0 (push at R0, ≤400 tokens).** Goal (verbatim intent); anchor stubs
(`name`, `intent`, WIT `type`); links among anchors; `accept` checks each stamped
`@step`; named handles; pull pointers. `function` appears only on retained links; `goal`
only for anchors; `description` never in tier 0.

**B2. Split-if-over.** If tier 0 would exceed the projection budget, the task is split.
The budget is enforced by the split rule, not by the field list: arbitrary intent, anchor
count or type definitions can exceed any fixed shape. A split must preserve cross-page
dependencies (a `preserve:` obligation is one such dependency).

**B3. Per-turn budget.** ~1200 tokens push+pull, ≤6 pulls. Pulls: `resolve`,
`neighbourhood`, `manifest`, `example`, `history`, `validate`. Every pull is
capability-scoped by the agent's handles (W-7.4 / W-9.6).

**B4. Negative context (capped).** One constant-size line, kinds + count + reason:
`EXCLUDED <n> entities: <kind> (<reason>)`, reason ∈ `{not-on-path, type-mismatch,
out-of-scope}`. Ids by pull only. This is distinct from `U` (§B6): `EXCLUDED` means
inspected and irrelevant.

**B5. Intent authority.** When W-5.5 intent conflicts with manifest `description`, intent
wins; emit an inline `conflict:` tag.

**B6. Unresolved field (required).** Marks what selection did not inspect or could not
reach:

```
U <id-or-role> reason=<not-inspected | adjacency-cap | beyond-grant |
                              wireless-peer | impl-behind-contract>
```

- `impl-behind-contract` — retained entity whose internals were not expanded.
- `adjacency-cap` — **required** whenever a consumer/writer query returned exactly its
  limit; it means "I looked and stopped at N, there may be more," distinct from
  `not-inspected` ("I did not look"). A behaviour edit must pull or split before
  proceeding on an `adjacency-cap`.
- `beyond-grant` — out-of-grant entity on the path (A6, stub form).
- `wireless-peer` — wireless edge outside the requester's grant (D-W3).

**B7. Completeness is visible.** A truncated packet is never presented as sufficient. The
envelope carries `used/ceiling`; any omission is `omitted: <n> further entities` plus a
`pull` token. An agent that knows it lacks the whole picture pulls instead of inventing.

**B8. `editable:` set, `validate`, and the three authorities.** The initial packet
carries the `editable:` set (A1 `allowed_change`). Before mutating the graph the agent
submits `EDIT-PLAN { changes: [{kind, entity, port, from?, to?}], revertible }`. The
server computes `boundary-delta` from `Δ` against **current** adjacency revisions and
returns only contracts that newly enter the boundary. Three distinct outcomes, three
distinct authorities:

| Outcome | Condition | Authority |
|---|---|---|
| **REFUSE** | edit touches outside `editable:` | permission, W-9.6 (hard invariant, like W-5.4 type refusal) |
| **HOLD** | contract conflict or unknown boundary; commit needs agent `ACK` naming each obligation, or requester `RATIFY-BREAK` | consequence; server enforces that it was **seen**, not the choice |
| **PROCEED** | boundary empty or all obligations acknowledged | — |

The server never rules that a content consequence is wrong: "pulse breaks the alarm" may
be exactly what the requester wants. It rules on whether the agent looked. `preserve:`
obligations are the names in a HOLD; `accept:` checks are the task's success criteria
(§D). They are different kinds and never merged.

### C. `new:` anchors

**C1.** A `new:<kind>` anchor carries the blueprint **contract**: expected ports, WIT
types, `goal`/`function` from the requester's intent. Not the implementation. On
creation, the realized manifest is verified against the contract; a mismatch is a
`conflict:` push, not silent acceptance.

**C2. Required edges (`R` lines) are authored from the task, never read from the graph.**

```
R <from>:<port> -> <to>:<port>  type=<WIT>  status=<absent|present>
```

A2's path walk runs over **stored** edges only, so for `new:` anchors it has nothing to
walk and B1's "links among anchors" is empty. The connection the task requires must
therefore be authored from the task record, not selected:

- `R` is derived from `intent`, `accept`, and the anchor templates; it is the task's
  statement of what *must* connect. `L` (B1) is the world's statement of what *is*
  connected. The two kinds are never merged.
- `R` never enters A2's walk, so a `new:` anchor is never given a fabricated world id —
  CloakedEscort's "never fabricate a world ID" rule holds.
- `status=absent` = must be built; `status=present` = already satisfied, verify not build.

**C3. Intake type check.** Each `R` line's endpoints are type-checked against the anchor
templates via W-5.4 **at intake**, before the agent starts. A `new:lever`
`state:out/variant<pulled,idle>` into a `new:door` `signal:in/bool` emits `conflict:` at
intake, naming the converter relay required — the test-13 converter insight delivered
pre-build rather than after a failed link attempt.

**C4. Bounded.** `R` is bounded by anchors × declared ports, so B2's split-if-over-budget
applies with no world-size dependency. A missing `R` where `accept` requires a connection
emits `U reason=required-wiring` (B6 enum).

**C5. `new:` boundary and `editable:`.** A `new:` port has no stored consumers, so its
change boundary is legitimately empty — but `validate` tags it `empty-by-construction`,
never `U reason=not-inspected`, or B6's anti-hallucination guarantee degrades exactly for
the build case. `editable:` for a `new:` anchor defaults to its template ports plus its
`R` endpoints; without this, every build task would be REFUSEd at `validate` for lacking a
grant over an entity that does not yet exist.

With C1–C5, the primary case carries all three objective clauses: objects (C1), **how
they connect** (C2), what each is meant to do (C1 + B5 intent authority).

### D. Authorship and refresh

**D1. `accept`.** Existing targets: requester authors (owns the observable done-state).
`new:` targets: agent proposes from the contract, requester confirms before build. `accept`
is per-target, so a mixed build carries both. `accept` never contains a `preserve:`
obligation (see B8): a task can be done while a break was knowingly acknowledged.

**D2. Refresh.** R0 pushes tier 0 stamped with `slice.rev =
hash(retained records, retained edges, adjacency_rev(touched ports))`. R1+ pushes only
deltas inside the slice, coalesced per agent **turn** (not per tick), each bumping
`slice.rev`: new links touching retained entities, new entities connecting to anchors,
`accept` state changes (with `@step`), a `new:` anchor's verified manifest, and
`consumer_added|consumer_removed|writer_added` for any watched port. A delta may arrive
for an edge with one retained endpoint; the slice boundary may widen, and that widening is
always an explicit event. Before an edit commits, validation and application share a
transaction guard so an edge cannot be added between check and write.

**D3. Freshness: structural vs runtime.** These are different:
- **Structural context** (manifests, links, intents, adjacency membership) is covered by
  `slice.rev`.
- **Runtime state** (physics bodies, joints, positions — W-4.4, advanced per step W-8.3)
  is **not** in any packet or hash. A doorway can be clear at step 100 and occupied at
  step 101 with `slice.rev` unchanged, and turn-coalesced deltas may lag.
- Therefore: every observation and `accept` check carries `@step`. When an action requires
  a condition to hold **now**, the authoritative server evaluates it at execution (D-W4);
  a cached hash is never a substitute. Historical evidence ("opened during steps
  100–110") remains valid for that run only.

### E. Tests (replacing v3 G where noted)

Keep v3 tests 1–8, 10–23 unchanged except **test 9**, which is replaced:

```
9.  Runtime-vs-hash (D3): doorway clear @step100, physics moves a body in @step101,
    no stored record changes, slice.rev unchanged. An action guarded by "doorway
    clear" receives the step-101 server value; the tier-0 accept @step100 is not
    treated as current.
9a. Structural-vs-runtime separation, BOTH SIDES: a manifest edit to the lever
    bumps slice.rev (structural channel). Independently, a body moving through the
    doorway at step 101 must be DELIVERED as a @step-stamped observation delta
    ON THE OBSERVATION CHANNEL with slice.rev unchanged. Assert both directions:
    (a) structural edit → rev bump, no observation delta required;
    (b) runtime change → observation delta present, rev NOT bumped.
    Without (b) the agent learns "no rev bump = nothing happened" — the exact
    conflation D3 exists to prevent. The two channels are independent by
    construction: slice.rev carries structure; observations carry @step state.
24. adjacency-cap: consumers(L.state) returns exactly its limit of N → packet carries
    U L.state/consumers reason=adjacency-cap; a behaviour edit to L.state is HOLD
    until the set is pulled or the task split.
25. allowed_change vs Δ: A1 with allowed_change={L.state} accepts an EDIT-PLAN on
    L.state and REFUSES one on door.open, though both are in the goal slice.
```

### F. Owner sign-off (non-blocking for the core)

H4 verb vocabulary `{inspect, build, extend, repair}` (add only when a fixture needs it).
H5 pull-capability gating via W-7.4/W-9.6. H6 numeric constants — measure against the
W-12.2 machine (object + joint + code block); note ~400 tier-0, ~1200/turn, and ~1500
ceiling are three different budgets and must be named distinctly. H7 `area` reports bounds
only, never enumerated cells. H8 `editable:` provenance — derive from `allowed_change` ∩
grant; requester may widen mid-task, and that widening is itself `validate`d. H9 `stability`
placement — link preferred pending measurement (§2).

---

## 4. Clause-label map (v3 → this text)

| v3 | This text |
|---|---|
| B4b (`U` field) | B6 |
| B6 (completeness, line 84) | B7 |
| B6 (duplicate, line 66) | deleted (was the same as B6 above) |
| B7 (`editable`/validate) | B8 |
| E2 (`preserve:` vs `accept:`) | folded into B8 + D1 |

No two clauses in this text share an ID.

---

## 5. What this text does not change

Every substantive decision from rounds 1–8 is carried unchanged: multi-edge path
relevance, per-link typing, declaration-gated inclusions, `new:`-as-contract, stubs for
beyond-grant, tier-0 projection and split-if-over, capped negative context, intent
authority, push-on-write turn-coalesced deltas, `adjacency_rev`, the REFUSE/HOLD/PROCEED
split, `stability`, and runtime freshness by server check. It adds no core capability
(W-2.5 holds): it touches only W-5.3 (one optional field) and W-5.6/D-W10 (this
resolution).

---

## 6. Final corrections (CloakedEscort R1-33) — retracting a false guarantee in §2

Two claims in my §2/B8 overstate what the mechanism delivers. Both are correctness, not polish, and the amendment text above must be read subject to this section.

### 6.1 `stability` decides label comparison, not code conformance — retract "decidable"

My §2 said the field "makes the boundary check for 'this pulse breaks that latch' decidable." CloakedEscort's counterexample shows this is false, and I accept it without qualification:

- Modules `M1` (maintains `true` until release) and `M2` (emits `true` for one step) have **byte-identical manifests**, both with `stability=maintained`.
- Nothing in W-5.3 (declarations) constrains W-6.1 (executable WASM). A declaration is a claim, not a proof.
- Comparing labels returns "match" for both; the alarm behaves differently under M2.
- Moving the field to `link.stability` does not help: the link carries the same unverified claim.

So `stability` is a **retrieval aid and conflict detector**, never a conformance check. It tells selection *where to look*; it cannot certify that a replaced module honours the contract. The reliable, inspectable event is **module/state/configuration changed** — which the boundary already keys on.

Corrected B8 rule (replaces the `stability-mismatch` clause in §3):

```
stability (optional)             → retrieval hint + conflict detector only.
  stability ≠ any, edit declared behaviour ≠ stability → HOLD (a warning that
      a consumer expects otherwise). It is EVIDENCE OF A CONFLICT, never
      evidence of conformance when they match.
module_replace / entity_replace  → conservatively ALL exposed ports changed,
      regardless of any `preserved` declaration or matching stability label.
      This is the sound default; a narrower footprint requires an independent
      verification the context system does not have.
```

Consequence for my earlier position: I argued in §13.2 that `stability` "makes the check decidable" and in §13.3 that a `stability-mismatch` HOLD is "a fact about a contract." The second half survives — a mismatch *is* a fact about a declared contract — but the first is withdrawn: a *match* proves nothing about the code. This also strengthens, not weakens, my answer to StonyPrism's audit point: the audit cannot be "did the declaration match," so it must be the conservative module-replacement rule, which needs no new field at all.

Should `stability` remain in the amendment? **Keep it optional and non-load-bearing** (CloakedEscort's recommendation, which I adopt): it earns its place as a retrieval hint and a pre-edit warning, but D-W10's correctness must not depend on it. That also resolves H9 differently than I proposed: placement becomes irrelevant to correctness, so leave it per-port and move it only if retrieval quality demands it.

### 6.2 "Proportional to fan-out" is not "bounded by 1200 tokens"

My §3 B8 and §11.7 argued the boundary-delta "is proportional to the changed port's fan-out, not the world — this is what keeps it inside the ~1200-token budget." CloakedEscort is right that this is an entailment error: W-5.4 sets **no maximum** on consumers, so a single changed output can have 10,000. Fan-out-2 proves independence from *unrelated* world content; it proves nothing about the worst case.

Corrected B8 rule (replaces the budget claim in §3):

```
boundary-delta is PAGED under the delivery budget:
  each page carries { contracts, complete: bool, continuation, slice.rev }
  an edit is NOT boundary-validated while any required page is unexamined;
  status=incomplete, never status=validated
  the agent may narrow the edit (e.g. add a controller, preserve the shared
     producer) or propose a split that carries the boundary obligations
  query caps and permission failures → U reason=adjacency-cap / beyond-grant,
     never "validated by omission"
  the completed boundary is revalidated at guarded application (transaction)
```

This is a worst-case rule, not a default: additive edits still yield an empty boundary and commit immediately; only a *behaviour* change on a high-fan-out port pages. The agent can avoid the cost by design (narrow the edit), which is the correct incentive — it rewards edits that don't disturb shared producers.

### 6.3 Net effect on the amendment

| Clause | Was | Now |
|---|---|---|
| §2 / W-5.3 | `stability` "makes the check decidable" | optional retrieval hint; **not** conformance proof |
| B8 `stability-mismatch` | HOLD as a decidable check | HOLD as conflict *evidence*; match proves nothing |
| B8 module replace | all ports changed | unchanged — this is now the load-bearing rule |
| B8 budget | "proportional ⇒ fits 1200" | paged, `complete=false`, revalidate at apply |
| H9 | pick port vs link placement | moot for correctness; retrieval-only |

With §6 applied, the amendment no longer claims a guarantee it cannot deliver. I sign the text as corrected.

---

## 7. Closing note (StonyPrism R1-37 cautions, final)

Both cautions accepted; one required a change to this text, the other a warning to implementers.

**7.1 A1's `allowed_change` and `Δ` must stay two fields, two code paths.** StonyPrism is right that this is load-bearing. If an implementation stores them together, the REFUSE check and the BOUNDARY computation collapse into one, and the three authorities degenerate: a permission failure would surface as a HOLD, or a consequence conflict as a REFUSE. The distinction is not cosmetic — it is the whole reason the server can refuse an unpermitted edit *and* decline to veto a permitted-but-consequential one:

| field | exists when | feeds | authority |
|---|---|---|---|
| `allowed_change` | task start (∅ or default writes) | REFUSE | permission, W-9.6 — hard |
| `Δ` | EDIT-PLAN time only | BOUNDARY | consequence — HOLD |

An implementation that merges them will pass tests 25 (allowed_change) and maybe 15 (HOLD) *independently* but fail the combined case where an unpermitted edit that also breaks a contract must be REFUSED, not HOLDed. That combined case is the test that catches the merge; it is added as test 26.

**7.2 Test 9a now asserts the delivery side (applied above).** StonyPrism's caution 2 correctly found that my replacement asserted only that body motion does not bump `slice.rev` — it did not assert that the motion is *delivered* on the observation channel. Without that, "no rev bump" reads as "nothing happened," the exact conflation. Test 9a is corrected in place to assert both directions: structural edit bumps rev with no observation required; runtime change arrives as a `@step` observation with rev unchanged. The two channels are independent by construction — `slice.rev` carries structure, observations carry `@step` state — and a correct implementation must never route one through the other.

**7.3 `adjacency-cap` with the behaviour-edit HOLD** stands as B6/§3. "Looked and stopped at N" never serialises as `not-inspected`; a behaviour edit on an `adjacency-cap` port HOLDs until the set is pulled or the task split.

**7.4 Additional test (26) for the field-merge failure:**

```
26. Two-field separation: an EDIT-PLAN on door.open (outside allowed_change={L.state})
    that ALSO would break a consumer's contract → outcome is REFUSE, not HOLD.
    If allowed_change and Δ are merged, this returns HOLD and the test fails.
    This is the case that proves the two fields are load-bearing, not redundant.
```

**7.5 Handoff.** The amendment (`spinybreach-dw10-final-amendment.md`) is the single source of truth; §1, §6 and §7 are its correction history over v3. The six participant artifacts are provenance and should be cited as such, not read as parallel proposals — StonyPrism's citation-drift warning is the reason. Nothing in this text changes W-2.5: the amendment touches only W-5.3 (one optional, non-load-bearing field) and W-5.6/D-W10.

---

## 8. Final correction: C must carry task-derived required edges (StableReaper R1-38)

StableReaper is right, and this is a defect in my own C1: I wrote the template contract and `accept`, but never the **connection**. For `new:` anchors there is no entity id, no stored port, no link and no `adjacency_rev`; A2–A7, B7 and D all operate on stored edges, so for the objective's own example ("build a door that opens when a lever is pulled") nearly all of the machinery is **inert**. The objective asks for three things — the objects, **how they connect**, what each is meant to do — and my C delivered the first and third, not the second, precisely in the primary case. That is a dropped result: NimbleEngine's case-C proposal stated the required link and the merge lost it, the same way A2's multi-edge fix was once lost.

### 8.1 Replacement C clause

**C1. `new:` anchors carry the contract.** A `new:<kind>` anchor carries the blueprint contract: expected ports, WIT types, `goal`/`function` from the requester's intent. Not the implementation.

**C2. Required edges (`R` lines) are authored from the task, never read from the graph.**

```
R <from>:<port> -> <to>:<port>  type=<WIT>  status=<absent|present>
```

`R` is derived from the task's intent, `accept`, and the anchor templates. It is the task's statement of what *must* connect. `R` is deliberately distinct from `L` (B1, the world's statement of what *is* connected):

- `L` comes from stored W-5.4 links; `R` is a projection of the task record.
- `R` never enters A2's path walk. A `new:` anchor is never given a fabricated world id, so CloakedEscort's "never fabricate a world ID" rule holds.
- `status=absent` means the connection must be built; `status=present` means the world already satisfies it (the agent verifies rather than builds).

**C3. Intake type check.** The server type-checks each `R` line's endpoints against the anchor templates via W-5.4 **at intake**, before the agent starts. A `new:lever` declaring `state:out/variant<pulled,idle>` wired to a `new:door` declaring `signal:in/bool` emits `conflict:` at intake — telling the agent, in one line, that a converter relay is required. This delivers the converter insight (test 13) *before* the build rather than after a failed link.

**C4. Bounded.** `R` is bounded by anchors × declared ports, so B2's split-if-over-budget applies and there is no world-size dependency. A missing `R` where `accept` requires one emits `U reason=required-wiring` (added to B6's enum).

**C5. `new:` boundary and `editable:` (B7a).** A `new:` port has no stored consumers, so its change boundary is legitimately empty — but `validate` must tag it `empty-by-construction`, never `U reason=not-inspected`, or B6's anti-hallucination guarantee degrades exactly for the build case. `editable:` for a `new:` anchor defaults to its template ports plus its `R` endpoints; otherwise every build task would be refused at `validate` for lacking a grant over an entity that does not yet exist.

### 8.2 Effect on the amendment

| Clause | Was | Now |
|---|---|---|
| C1 | template contract only | + C2 `R` required edges (authored, not read) |
| `unresolved.reason` | {not-inspected, adjacency-cap, beyond-grant, wireless-peer, impl-behind-contract} | + `required-wiring` |
| B8 boundary status | {empty, paged, complete} | + `empty-by-construction` (new: ports) |
| F line | "`new:` per C" | "`new:` per C **including task-derived required edges**" |
| Tests | 9, 9a, 24, 25, 26 | + 20–24 from `required-edges-StableReaper.md` |

### 8.3 Open decision carried to the owner (H10)

StableReaper's own disproof condition: if `new:` templates always resolve to an admin-world entity with stored ports (W-9.1), then `R` collapses to `L` and tests 20–24 assert the wrong shape. Recommendation: treat `new:` as a **pure contract** measured against the W-12.2 machine (object + joint + code block), because W-9.1 describes the admin *building* in a void, not every build task resolving to a pre-existing admin entity. Even if that recommendation is overturned, C3's intake type check survives — it reads template ports, which exist either way.

With §8 applied, the amendment carries all three objective clauses in the primary case: objects (C1), **how they connect** (C2), what each is meant to do (C1 + B5 intent authority). This closes the last merge-loss.

---

## 9. Integration note (StableReaper R1-40) — §8 is now inline in §C

StableReaper reviewed §C at its pre-§8 form and correctly reported the `R`-line gap; that substance was already in §8 but as a trailing correction, so a reviewer reading §3 top-to-bottom still saw the defect in the section body. §C above is now the single coherent C section: C1 contract, C2 required edges, C3 intake type check, C4 boundedness, C5 `new:` boundary/`editable:`. §8 remains as the reasoning record for why the addition exists; it is no longer the only place the rule lives.

Correspondence with StableReaper's artifact: their C2 = my C2; their intake type check = my C3; their B7a = my C5; their B8 line and `editable:` default are both in C5; their tests 20–24 are carried in the §6.3/§8.2 test rows and my C-section fixtures.

Cross-artifact state at close:

- **SpinyBreach** `spinybreach-dw10-final-amendment.md` — single source of truth; §C now self-contained.
- **SpinyBreach** `spinybreach-w56-required-connections.md` — the same `R` rule stated as one clause (3a) against CloakedEscort's concise W-5.6 text, so the owner-facing form carries it too.
- **CloakedEscort** `CloakedEscort-W5.6-proposed-amendment.md` — concise owner-facing W-5.6; needs only clause 3a.
- **StableReaper** `required-edges-StableReaper.md` — provenance for the `R` rule and tests.
- **NimbleEngine** `nimbleengine-dw10-consolidated.md` — the consensus body the table argued over; superseded by the amendment for wording.

Nothing in §9 changes a rule. It records that the two remaining human-facing documents (my amendment and CloakedEscort's W-5.6) both carry the required-connection rule, and that the four other artifacts are provenance, not parallel proposals — the citation-drift risk StonyPrism named. H10 (pure contract vs admin-world template) stays open; the `R` rule and its intake type check hold under either answer, because the check reads template ports, which exist in both readings.
