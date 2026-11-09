# D-W10 Consolidated Decision — Task Context Selection & Delivery (v3)

**Author:** NimbleEngine (synthesis of R1–R3: SpinyBreach, StonyPrism, CloakedEscort, StableReaper)
**Status:** draft consolidation v3 — D-W10 is now fully specified and ready to amend `world-system-spec.md` W-5.6. Only the owner-sign-off items in H remain.
**Amends:** W-5.6 (open). Uses W-5.3/W-5.4/W-5.5/W-11.6/W-11.7, W-6.3, W-7.4, W-8.3, W-9.6.

This is the joint agreement written as a single decision. It reflects the converged consensus across all five participants.

---

## A. Selection: path-anchored, never spatial (agreed)

**A1. Anchors.** A task record carries `anchors` (entity ids, or `new:<kind>`), `intent` (W-5.5 verbatim), `accept` (observable done-checks), `scope`, `requester`.

**A2. Predicate (multi-edge path).** Retain entity `e` iff `e ∈ anchors`, or `e` lies on an anchor→anchor or anchor→accept path in the **multi-edge dependency graph**, where each path step is one of:
```
(i)   a W-5.4 port link between WIT-compatible ports;
(ii)  a W-4.2 joint attaching e to the previous entity;
(iii) a W-7.4 handle grant from the previous entity to e;
(iv)  a W-7.2 sensor target read by the previous entity;
(v)   a W-7.3 physics-volume or world-parameter scope that applies to e
      and is set by the previous entity.
```
An entity that an anchor's manifest directly names is retained even if no path exists (the existing direct-participant case). All five step types are edges already in the world graph (W-3.5); this adds no data — it only says the walk must traverse them. WIT type checking applies to step (i) only; steps (ii)–(v) have their own admissibility (a joint has two endpoints; a handle exists only where the builder/admin granted it, W-7.4; a volume is a cell set or world id).

**A2 clause 5 (direct inclusion is declaration-gated, per SpinyBreach §10.1).** A direct inclusion outside a path is retained only if it is a joint partner (W-4.2) or a held-handle target (W-7.4) of an **anchor** (not of an intermediate retained entity), **and** the task's `accept` names it or the anchor's manifest names it as a port/joint participant. Justification is *declaration*, never *adjacency through a capability*: a bus block that holds handles to 40 actuators does not make all 40 "direct dependencies" unless the task or manifest names them. Declaration is finite; capability-reach is not.

**A2a. Why multi-edge (from CloakedEscort, SpinyBreach).**
The actual mechanism of "door opens when lever pulled" may be `lever -(port)-> C -(handle)-> J -(joint)-> door`, where C and J are *neither anchors nor named by an anchor's manifest*. A one-hop direct-participant clause prunes them and leaves only `{lever, door}` — the agent then wires a port that does not exist, or a signal with no actuator behind it. Joints/handles/sensor targets/physics volumes are **path steps**, not one-hop inclusions. The multi-edge walk retains `{lever, C, J, door}` — four entities, still tiny, and now correct. This is why depth was never the axis: lever→C→J→door is 3 steps, so no fixed hop count is right; path relevance over the multi-edge graph is.

**A3. Never expand by spatial adjacency or chunk membership.** Hinge meshes, decorative blocks and off-path lamps are excluded by the predicate, not by a cap.

**A4. Depth is a safety guard only** (~8 hops), never the semantic criterion.

**A5. Verb-driven pruning whitelist (from StableReaper).** What enters depends on the task verb, independent of selection:
- `inspect` → the anchor's own manifest/description/intent only (r=0).
- `build` / `extend` → the path slice + the handles each anchor holds (W-7.4) + any assemblies the anchors belong to (W-9.4).
- `repair` → additionally the last fault record (W-6.3) for each anchor.
The verb picks the whitelist; the `scope` dial (SpinyBreach) picks the widening. Both are explicit, never an LLM summary.

**A6. Out-of-grant retention (SpinyBreach §10.3, StableReaper).** If the path reaches entity X but the requester's grant (W-7.4/W-9.6) does not cover X, retain X as a **stub only**: `id`, `kind`, and `U X reason=beyond-grant`. Omit its manifest internals, ports, and description — the agent learns X exists and is a dependency, but not how it works. If the task's `accept` cannot be verified without X's contract, the task is **BLOCKED** with a message to the requester, not silently under-specified. This is the bridge between "only what it needs" (W-11.6) and "only what it is allowed" (W-9.6): a dependency you cannot touch is information (its existence changes your plan) but not context (its internals are not yours to read).

**A7. Goal slice + change boundary (from CloakedEscort).** The multi-edge path (A2) answers "what does the task need to accomplish the goal." A *different* question is "what will my edits affect." An entity off every anchor→accept path can still be affected by a build: in `lever.state → controller → door` with a side-branch `lever.state → alarm.armed`, changing lever's maintained output into a pulse changes the alarm too, passes the door's acceptance check, yet lies off the lever→door path. Selection therefore has **two complementary parts**:
- **Goal slice:** anchor→anchor / anchor→accept paths and required non-port dependencies (A2). This is the "to accomplish" context.
- **Change boundary:** the contracts of other consumers, writers, or controlled objects potentially affected by the proposed edits — their relevant interfaces only, never their implementations. Initially derived conservatively from the task's allowed change set; **recomputed when the agent proposes its concrete edits** (the edits define which interfaces are being touched).

This preserves the compact push/pull budget without assuming every off-path entity is irrelevant. It is a refinement of, not a substitute for, A2.

**A7a. Selection is two-phase; there is one boundary, not two competing ones (NimbleEngine, consolidating StableReaper's A2b with SpinyBreach's BOUNDARY(edit)).**
StableReaper's A2b ("selection takes the proposed change set Δ as input and retains contract-stubs of other consumers/writers") and SpinyBreach's `BOUNDARY(edit)` look like rival mechanisms. They are the *same operation at different times*, and the final spec must not carry both as if distinct:
- **Phase 1 (task start):** goal slice only — A2 multi-edge path from anchors, delivered as tier 0. Δ does not exist yet, so no boundary can be computed.
- **Phase 2 (edit proposal):** change boundary — contract-stubs of consumers/writers/controlled objects of the changed ports, computed from Δ, delivered as `validate(edits) → boundary-delta` (B7). Δ exists only here, so this is necessarily deferred.

Both phases are a pure function of `(anchors, intent, accept, scope, verb, Δ)`; Δ is empty in phase 1. Consolidating this removes a real ambiguity: the spec must state that A2b and BOUNDARY(edit) are one phase-2 mechanism, so a reviewer does not read two separate selection rules. The boundary stub uses CloakedEscort's contract projection (id, port, intent, WIT type, function, goal — no descriptions, no internals, no recursive expansion); retention is justified by the edit, not adjacency, which is why the lamp beside the door stays out.

## B. Delivery: laddered tier-0 project, budgeted pull (agreed)

**B1. Tier 0 (always pushed, ≤400 tokens):** goal (verbatim intent); anchor stubs (`name`, `intent`, WIT `type`); links among anchors; `accept` checks; named handles; pointers to pull surface.
- `function`: only on retained links.
- `goal`: only for anchors.
- `description`: never in tier 0; pull-only.

**B2. Hard rule:** if tier 0 exceeds budget, the task is split. This is the enforceable form of W-11.6.

**B3. Per-turn budget:** ~1200 tokens push+pull, ≤6 pulls. Pull surface: `resolve`, `neighbourhood`, `manifest`, `example`, `history`.

**B3a. Pulls are capability-scoped (from StableReaper).** Every pull is gated by the handles the agent holds (W-7.4) / admin-granted rights (W-9.6). "Only the information it needs" is therefore also a permission boundary, not just a size policy.

**B4. Negative context (capped).** One constant-size line: kinds + count + reason enum `excluded.reason ∈ {not-on-path, type-mismatch, out-of-scope}`. Ids via pull only. This enum is **distinct from `unresolved.reason`** below — collapsing them would re-create the absent-vs-unknown confusion.

**B4a. Known-absent vs not-inspected (from CloakedEscort).** The selection must distinguish a *verified absent* connection from a *boundary not yet inspected*. An unexplored boundary is never reported as "no dependencies." Where a behavior is genuinely unspecified (e.g. "lever release behavior: unspecified"), that is stated rather than invented.

**B4b. Required `unresolved:` field (from CloakedEscort, SpinyBreach, StableReaper).** A distinct, required delivery field marks boundaries the selection did not expand or could not see:
```
U <id-or-role> reason=<not-inspected|beyond-grant|wireless-peer|impl-behind-contract|adjacency-cap|required-wiring>
```
Presence rules:
- A retained entity whose internals selection did not expand (e.g. an unchanged controller behind its contract) emits `U C.internals reason=impl-behind-contract`.
- A wireless peer past the requester's grant emits `U wireless-peer reason=beyond-grant` — never silently included, never silently absent.
- A query that stopped at its cap emits `U … reason=adjacency-cap` — "looked and stopped at N", distinct from `not-inspected` ("didn't look"). A behaviour edit HOLDs on `adjacency-cap` until the query is pulled/expanded.
- A `new:` anchor's required edge that `accept` needs but the task did not supply emits `U … reason=required-wiring` (C2).
- An entity pruned by negative context gets the capped `EXCLUDED` line (B4), not an `U` line. The two are different claims: `EXCLUDED` = "inspected and irrelevant"; `U` = "not inspected". A packet that omits both signals completeness of the slice. This is the single most important anti-hallucination control after B2: it tells the agent precisely when "not in my packet" means "does not exist" versus "I did not look."

**B5. Intent authority.** When W-5.5 intent conflicts with manifest `description`, intent wins; emit inline `conflict:` tag.

**B6. Completeness is visible, never assumed (converged: StonyPrism, StableReaper, CloakedEscort).** A truncated packet is never presented as sufficient. The envelope carries `used/ceiling`, and any omitted content is a one-line `omitted: <n> further entities` with a `pull` token. This is the shared anti-hallucination guarantee: the agent knows when it does not hold the whole picture and pulls instead of inventing.

**B7. The `editable:` set, the `validate` boundary-delta, and the HOLD/ACK gate.**
The change boundary (A7) cannot be fully computed at task start because the edit does not exist yet. The initial packet therefore carries an **`editable:` set** — the ports/entities the task permits changing (drawn from the task's allowed change set and the requester's grant, W-9.6). When the agent proposes edits, the server evaluates a single gated pull:
```
validate(edits) -> boundary-delta
```
Rules:
- `boundary-delta` lists **only the new contracts** that enter the change boundary because of these edits (other consumers/writers/controlled objects of the changed ports). It is proportional to the changed port's fan-out, not the world. **Proportionality is not a token bound** (CloakedEscort): W-5.4 permits multiple consumers with no maximum, so one changed output can have 10,000 consumers. Overflow is handled explicitly (below), never by silently dropping consumers.
- If `edits` touches a port *outside* the `editable:` set, the server rejects the edit with a `conflict:` (permission, not just size).
- **Authority split (per SpinyBreach A7d).** The server rules on *whether the agent looked at the obligations*, not *what it may choose*. A "pulse breaks the alarm" conflict is a *content* consequence, not a hard invariant like a WIT type mismatch (W-5.4). Blocking it would encode content policy into the core, which W-2.5 forbids. So on a detected contract conflict the server returns `HOLD: <obligations>`; the edit commits only on agent `ACK` or requester `RATIFY-BREAK`. The server enforces the acknowledgment (logged), not the choice.
- **`stability` is a declared intent, not a conformance certificate (per CloakedEscort).** W-5.3 declares; W-6.1 executes. Two modules with identical `stability=maintained` manifests can behave differently (one maintains, one pulses), so matching labels never verify actual WASM behavior. Therefore: (a) **module replacement treats all exposed ports as potentially changed, regardless of a `preserved`/`stability` declaration** — the conservative default wins over any label; (b) `stability` (optional, per-port, default `any` in W-5.3) may narrow the boundary *only* for non-replacement edits (wiring/connection changes), where the module's behavior is unchanged and its declared interface is an honest hint — and even then it is a declaration, never a conformance claim. Placement is per-port by default; if measurement against W-12.1 content shows collisions, move it to the link (`link.stability`).
- An edit that adds a consumer the boundary did not include is caught because `validate` runs against *current* adjacency revisions (the `adjacency_rev` of the touched ports), not the initial snapshot — CloakedEscort's revision-query point applied to the agent's own writes, under a transaction guard.

**B7 overflow rule (per CloakedEscort).** If the boundary exceeds the per-turn budget:
- Return budgeted pages with `complete=false`, a continuation reference, and the boundary revision.
- Never report completed boundary validation while required contracts remain unexamined (`complete=true` only when all affected consumer contracts were returned).
- The agent may narrow its edit (e.g. add a controller while preserving the shared producer) to reduce fan-out.
- Revalidate membership when the completed proposal is applied.

This unifies SpinyBreach's deferred second selection (EDIT-PLAN is the input), StonyPrism's enforcement (validate + `stability` is the decidable gate), and W-2.5's authority boundary (HOLD/ACK, not refusal).

**B7a. `new:` ports have an empty boundary by construction (per StableReaper).**
A `new:` anchor's port has no stored consumers, so its change boundary is legitimately empty. `validate` must tag this `empty-by-construction`, **not** `U reason=not-inspected` — otherwise B6's anti-hallucination guarantee silently degrades for the build case. Additionally, `editable:` for a `new:` anchor defaults to its template ports plus the `R` endpoints (C1); without that, every build task would be rejected at `validate` for lacking a grant over an entity that does not exist yet.

## C. `new:` anchors: contract, not implementation (agreed)

An anchor `new:<kind>` carries the blueprint *contract*: expected ports + WIT types + `goal`/`function` from requester intent. Not the implementation. This is what "meant to do" means for an unbuilt part.

**C1. Task-derived required edges ($R$ lines) (per StableReaper, restoring NimbleEngine round-1 Proposal 1).**
For `new:` anchors there is no stored graph path to walk — no entity id, no ports, no links, no consumers, no `adjacency_rev`. The objective asks for three things — objects, **how they connect**, what each is meant to do — and the middle one is absent in exactly this primary case. Selection cannot read a link that does not exist; it must be **authored into the packet from the intent**. The packet therefore carries:
```
R <from>:<port> -> <to>:<port> type=<WIT> status=<absent|present>
```
- `R` = "the task says these must connect" (derived from intent/accept/templates, never read from the graph); `L` (B1) = "the world says these are connected". Keeping them distinct stops `new:` anchors being injected into A2's path walk, which would violate CloakedEscort's "never fabricate a world ID" rule.
- For the door/lever case: `R lever.out -> door.in type=bool status=absent` appears alongside template(door), template(lever), and the accept target. No walk is needed because the required edge is stated by the task, not found.

**C2. `R` is bounded and type-checked at intake (per StableReaper).**
- `R` is bounded by anchors × declared ports, so B2's split-if-over-budget holds; there is no world-size dependency.
- The server type-checks each `R` line's endpoints against the templates **at intake** via W-5.4. A lever `variant` → door `bool` mismatch surfaces as `conflict:` before the agent starts — telling it a relay is needed in one line. This is the converter insight (test 13) delivered pre-build.
- A missing `R` where `accept` needs one emits `U … reason=required-wiring` (added to B4b's enum).
- If `new:` templates always resolve to an admin-world entity with stored ports (W-9.1), `R` reduces to `L`; the owner should confirm the pure-contract reading against W-12.2 (H10).

## D. Refresh: context is a living slice, not a snapshot [open→resolved]

**Problem.** A build changes the graph. If selection runs once at task start, entities built during the task (case: door does not exist at selection time) never enter the slice. W-11.6 forbids re-pushing tier 0 each turn.

**Resolution (delta subscription + content hash).**
- **R0:** push tier 0 once, stamped with a content hash and the world's simulation step / DB revision (StableReaper's freeze). This hash is the cheap staleness detector: the server and agent both hold it.
- **R1+:** the world pushes only *deltas* inside the retained slice: new links touching retained entities, new entities connecting to anchors, state changes on any `accept` check, and — when a `new:` anchor comes into existence — its actual manifest *verified against the contract* (a mismatch is a `conflict:` push). Each delta bumps the content hash.
- **Revision check:** before applying a proposed change, the agent (or server) validates the revisions it read against the current hash; a stale read triggers reselection of the affected slice only (CloakedEscort), not a full re-push.
- **Ground truth:** pull of full projected manifest remains available for any retained entity.

**Unit of refresh:** the retained slice, kept open as a subscription; the graph is the source of truth (W-5.6), the slice is a materialized view invalidated on writes inside its boundary.

**Push vs pull of deltas.** **Push-on-write, turn-coalesced** (agreed: StonyPrism, SpinyBreach, StableReaper). Deltas are batched per agent *turn*, not per simulation tick, mirroring W-8.3's ordered one-step delivery — this avoids mid-wire update storms. The content hash is the fallback for pull-on-version (a pull returns "unchanged at v" instead of resending bytes). Turn-coalescing is a content-level delivery policy and needs owner sign-off as a D-W-level decision (D-W7 is about perception/action, not context refresh).

**D2. Freshness: structural hash vs runtime state (corrected per CloakedEscort).**
The `accept` checks (door.open == true when lever.on) and any runtime-conditional action are evaluated against *world state at a simulation step* (W-8.3). Two distinct freshness questions must not be conflated:

- **Structural context** (manifests, links, intents, adjacency membership) IS covered by the content hash: any write to these bumps it, and the delta model carries that signature. This is what R0/R1+ stamp.
- **Runtime state** (physics bodies, joints, positions — W-4.4, advanced per step W-8.3) is NOT in the packet hash. A doorway can be clear at step 100 and occupied at step 101 while the structural hash is unchanged, and turn-coalesced deltas may lag. The hash cannot prove runtime currency.

Rules:
- Every `accept` check and every runtime-conditional action carries the world step it was evaluated at (`… @step`).
- When an action requires a condition to hold *now*, the **authoritative server checks that condition at execution time**; the agent's cached hash is never a substitute.
- Historical acceptance evidence remains valid evidence of its recorded run only.
- A concurrent builder adding a consumer (e.g. `lever.state → alarm.armed`) after selection invalidates the held `adjacency_rev` of the touched port — the validity check covers **dependency-query membership**, not just retained records (CloakedEscort / SpinyBreach §11). Validation and application share a transaction guard to prevent an intervening change.

## E. Who authors `accept` (agreed)

Two-party rule, mirroring anchor resolution:
- For `existing` targets: **requester authors** `accept` (they own the observable done-state). Free in tier 0.
- For `new:` targets: **agent proposes** `accept` from the contract, **requester confirms** before build (one tier-1 confirmation, not tier 0). Otherwise "done" is unverifiable and the agent could self-certify.
- **`accept` is per-target, not per-task** (SpinyBreach's scoping): a mixed existing/new build carries both authorships, each tagged to its target.

**E2. `preserve:` is a distinct typed constraint from `accept:` (NimbleEngine, corrected per SpinyBreach §14).**
The HOLD/RATIFY-BREAK gate (B7) interacts with the accept checks. Success criteria and preservation obligations are different kinds of rule, and conflating them makes a `RATIFY-BREAK` ambiguous:
- `accept:` — the task's success criteria, requester-authored (E). When satisfied, the task is *done*. It asks a goal-side question: *is the door done?*
- `preserve:` — *consequence-side* constraints that default to required and can be waived, handled in the edit gate (B7), not in E. A preserve obligation is an off-path consumer's contract (e.g. the alarm expects maintained output).

Consequences:
- `accept` remains **purely requester-authored even when Δ touches a shared port** (SpinyBreach). If the requester deliberately retires the alarm, the door is still done when it opens — a `preserve:`-bearing `accept` would otherwise report it unfinished forever, which is wrong. The third party belongs in the edit gate, not in E.
- A `RATIFY-BREAK` does not delete a preserve obligation; it *records a waiver* in the consequence set, so (a) re-proposing the identical edit does not re-trigger `HOLD` (idempotent), and (b) the record reflects that the alarm was knowingly changed.
- A waived preserve is still logged and visible in the packet, so it is never a silent removal.

---

## F. What the consolidated decision changes in `world-system-spec.md`

- Amends W-5.6: selection per A1–A7 + A7a (two-phase); delivery per B1–B7 + B7a; `new:` per C (C1 `R` lines, C2 intake type-check); refresh per D + D2; `accept`/`preserve:` per E + E2.
- No new core capability (W-2.5): selection is a read over the world graph; delivery is ACP (W-11.7); the delta subscription is a content-level view over the existing graph; tick-freshness is a stamp on existing check results; the `validate(edits)` boundary-delta is a content-level read over adjacency; `R` is a projection of the task record's intent/accept; the optional `stability` port field and the `preserve:`/`accept:` split are W-5.3/manifest-level content additions, not core changes. The `R` intake type-check reuses W-5.4 over template ports.

## G. Falsifiable tests (agreed + new)

1. Door/lever with decorative chunk content → tier 0 = exactly {lever, door} + one link.
2. Three-anchor "wire A,B,C" → only the 3-chain, not anything adjacent.
3. Tier 0 size constant under 100 unrelated neighbours.
4. After the agent links lever→door, the next pushed message contains only the new link edge + any accept-state change, not a re-serialized tier 0.
5. A `new:door` anchor becomes a live entity with a mismatched port → a `conflict:` push, not silent acceptance.
6. **Joint mechanism (CloakedEscort):** a door whose mechanism is a joint + controller handle — not a port link — still exposes the joint/controller in the packet.
7. **Distance invariance (StableReaper):** moving a linked wireless controller far away does not remove it; adding an unrelated neighboring machine does not enlarge the packet.
8. **Revision guard (CloakedEscort):** a revision change to a definition/link invalidates affected proposed edits, while an unrelated-entity change does not force full reselection.
9. **Tick-freshness (D2):** an `accept` result stamped at step s is not acted on after a delta bumps the hash past s; the agent pulls fresh state instead.
10. **Direct-dependency leak (SpinyBreach §10.1):** a bus-block anchor holding handles to 40 actuators, none named in `accept`, yields the anchors and on-path entities only — zero held-handle targets of non-anchor retained entities.
11. **Unresolved ≠ excluded (SpinyBreach §10.2):** an out-of-grant wireless peer present → `U … reason=wireless-peer`, and no `excluded:` line for it; after granting, it becomes a normal retained record.
12. **Stub minimality (SpinyBreach §10.3):** an out-of-grant joint partner on the path yields id+kind+`U` only — no ports, no description. If `accept` needs its contract, the task blocks.
13. **Converter chain survives per-link typing (SpinyBreach §11 / CloakedEscort):** `L:event→C:event`, `C:bool→D:bool` is retained; path-level type equality would wrongly prune C — the test asserts C is retained.
14. **Boundary-delta is bounded (B7):** changing one port with fan-out 2 returns ~2 contracts, regardless of world size; the `validate` result fits inside the per-turn budget.
 15. **HOLD/ACK gate (B7 / SpinyBreach A7d):** agent proposes `lever.on := pulse` where the alarm expects maintained → `validate` returns `HOLD: alarm.armed (expects-maintained)`; the edit does not commit without agent `ACK` or requester `RATIFY-BREAK`. After `RATIFY-BREAK` the edit commits (the server enforces the acknowledgment, not the choice).
16. **Concurrent consumer addition invalidates (CloakedEscort + SpinyBreach §11):** another builder adds `L.state→A.armed` after delivery; the held `adjacency_rev(L.state)` goes stale and forces boundary recompute before commit.
17. **Editable gate (B7):** an edit touching a port outside the `editable:` set is rejected with `conflict:`, even if it is in the goal slice.
18. **Stability is a declaration, not conformance (B7 / CloakedEscort):** two modules with identical `stability=maintained` manifests but different behavior (one maintains, one pulses) are treated identically by the label comparison — so a `stability` match is never reported as verified conformance; and a module replacement is treated as all-ports-changed regardless of a `preserved` declaration.
24. **Overflow never drops consumers (B7 / CloakedEscort):** a changed producer with more consumers than one budget returns pages with `complete=false` and a continuation reference; `complete=true` only after all affected contracts are returned; the agent may narrow the edit to reduce fan-out; membership is revalidated on apply.
25. **Conformance is not claimed (B7 / CloakedEscort):** after a module replacement declared `preserved`, the boundary still retrieves the alarm's contract for inspection, because replacement overrides the declaration — the agent must inspect, not trust the label.
19. **Runtime state ≠ hash (D2 / CloakedEscort):** a doorway clear at step 100 and occupied at step 101, with unchanged structural hash → a runtime-conditional action is checked by the authoritative server at execution time, not trusted from the cached packet.
20. **Two-phase selection (A7a):** at task start the packet carries the goal slice only (no consumer contracts, since Δ is empty); after the agent proposes an edit, `validate` returns the boundary-delta. Assert the phase-1 packet contains no `A.armed` internals, and the phase-2 delta does.
21. **Preserve/accept are distinct (E2):** a task with an `accept` for the door and a `preserve:` on the alarm treats them separately — breaking the door's accept fails the task, while waiving the alarm's preserve (RATIFY-BREAK) moves it to waived without re-triggering HOLD on a re-proposed identical edit.
22. **RATIFY-BREAK is idempotent (E2):** after one waiver, re-proposing the same pulse edit does not return `HOLD` again; the waiver is recorded and visible in the packet.
23. **Boundary adds no near-anchor leak (A7a / StableReaper):** when the agent merely *adds* an independent consumer without changing `L.state`, the boundary does not retain that consumer's internals — only the changed port's contract-stubs appear. If A2b retained internals here, the test fails.
26. **Required edge is delivered for `new:` anchors (C1 / StableReaper):** "build a door that opens when a lever is pulled" with `new:door` + `new:lever` yields `R lever.out -> door.in type=bool status=absent`, plus template(door), template(lever), and the accept target. The intake type-check surfaces a `conflict:` (e.g. `variant` → `bool`) before the agent starts. A missing `R` that `accept` needs emits `U … reason=required-wiring`.
27. **`new:` boundary is empty-by-construction (B7a):** `validate` on a `new:` port returns `empty-by-construction`, not `U reason=not-inspected`; `editable:` defaults to the template ports plus the `R` endpoints, so a build task is not rejected for lacking a grant over a not-yet-existing entity.

## H. Owner sign-off (the only remaining decisions)

- H4. Verb-driven whitelist vocabulary (A5) — is `{inspect, build, extend, repair}` the full verb set, or should the owner add more?
- H5. Pull-capability gating (B3a) — confirm pulls are permission-scoped via W-7.4/W-9.6 handles.
- H6. Numeric constants (StableReaper): k=3 anchors, r=1 default, ~1500-token ceiling, ~400-token tier 0, turn-coalesced delta batching — recommend measuring against the W-12.2 machine as the smallest real fixture.
- H7. `area` scope (SpinyBreach): confirm `area` reports bounds only, never enumerated cells, for reproduction-style tasks.
- H8. `editable:` set provenance (B7) — confirm it is derived from the task's allowed change set + the requester's grant (W-9.6), and whether the requester can widen it mid-task.
- H9. `stability` placement and status (B7) — per-port by default; if measurement against W-12.1 content shows temporal expectations attach to the receiver rather than the port, move it to `link.stability`. It is an optional declared-intent hint that narrows the boundary only for non-replacement edits; it is never a conformance certificate, and module replacement overrides it (test 18).
- H10. `preserve:` / `accept:` separation (E2) — confirm `accept` is purely requester-authored (goal-side) and `preserve:` obligations are consequence-side, handled by the edit gate (B7); a `RATIFY-BREAK` requires the requester and records a visible, idempotent waiver that never blocks "done".
- H11. `new:` required-edge source (C1) — confirm `R` is authored from the task record's intent/accept/templates (pure contract), not resolved from any stored graph; if a `new:` template always resolves to an admin-world entity with stored ports (W-9.1), `R` reduces to `L`. Recommend pure contract, measured against W-12.2.
