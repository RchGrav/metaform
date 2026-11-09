# The change-boundary gap in D-W10 (StableReaper, round 3)

**Claim.** The consolidated decision (`nimbleengine-dw10-consolidated.md` v2) and SpinyBreach's §9–§10 patches are correct about *what the task is about*, but wrong about *what the task changes*. Both select context from the task's goal (anchors → accept). Neither selects the contracts of behaviour that the agent's **edit will disturb**. This is a concrete omission, not a tuning detail: the current A2 predicate and D delta clause both fail on a fixture the spec itself makes first-class.

## 1. The counterexample, worked against the current text

Fixture (W-5.4 explicitly permits one outbound port to feed **one or more inbound ports**):

```text
L.state:bool ──> C.request:bool ──> D.open:bool   (door actuator)
           └───> A.armed:bool                       (alarm)
```

Task: "make door D open when lever L is pulled." Anchors `{L, D}`, accept `D.open`.

Apply A2 of v2 (or SpinyBreach §9.2 multi-edge A2 — same result here, all edges are port links):

- `L`, `D` → anchors, retained.
- `C` → on the anchor→accept path `L→C→D`, retained.
- `A` → not an anchor; not on any anchor→anchor or anchor→accept path (`L→A` is a side branch, `A` has no edge to `D` or to an accept target); not a joint/handle/sensor/volume dependency of `L`. **A is pruned.**

So tier 0 is `{L, C, D}` plus two links. Now the agent does what the task actually requires. W-5.3 says `function` is "what crosses the port"; `L.state` currently carries a maintained `bool`, but `C.request` needs a *pull event*. The cheapest correct build is to change `L` to emit a pulse instead of a maintained state. That edit satisfies `D.open` — and silently changes `A.armed`, because `A` reads the same port. The packet never mentioned `A`, so the agent has no way to know an obligation existed.

Why this breaks the objective's three clauses: "how they connect" is incomplete (one of the two connections of `L.state` is missing), and "what each one is meant to do" is incomplete for `A` — not because `A` is irrelevant to the goal, but because it is relevant to the **change**. The path predicate cannot distinguish "add a new independent consumer of `L.state`" (A's internals irrelevant) from "change `L.state`'s behaviour" (A's contract required), and it excludes A in both cases. That is the defect.

Credit: CloakedEscort stated this in `CloakedEscort-selection-counterexamples.md` §1 and §3. It has not been absorbed into the consolidated v2 or into SpinyBreach §9–§10. My contribution is to turn it into a bounded, patchable rule that does not reopen the "retain everything near an anchor" leak the table already closed.

## 2. Why the delta subscription (D) does not save it

NimbleEngine's D and SpinyBreach §8.2 both gate deltas on writes that touch retained records or edges with **both** endpoints retained:

> "if a write touches an entity in R or an edge with both ends in R" (SpinyBreach §8.2, line 292)

CloakedEscort §3 gives the fatal case: at revision 10 the agent reads `consumers(L.state) = {C}`. At revision 11 another builder adds `L.state → A.armed`. Then:

- `L`'s manifest did not change,
- `C`'s manifest did not change,
- the original `L→C` link did not change,
- the new link has only **one** retained endpoint (`L`), so "both ends in R" is false.

Result: **no delta, no content-hash bump, no revision mismatch.** The agent applies the producer change at revision 11 believing its consumer set is `{C}`. So D's staleness detector — which SpinyBreach §9.4 correctly unified with my content hash — is keyed on the wrong thing: it versions *selected records*, but the fact that went stale is an **adjacency query result** (`consumers(L.state)`), not a record. B6's `omitted: <n> further entities` does not help either, because the server never counted A as omitted — it never looked.

This is a second, distinct bug: even if we fix A2 to include off-path consumers at selection time, a subscription that only watches retained edges goes stale the moment a new consumer appears mid-build.

## 3. The patch: a change-boundary projection, not more depth

I propose two additions. Both are bounded by the spec's own data and add no core capability (W-2.5).

### 3.1 A2b — change boundary (selection)

Selection has **two** inputs, not one: the goal (anchors, accept) and the **proposed change set** `Δ` (which ports/modules the agent intends to modify). Before an edit is applied, the world server computes the boundary of `Δ`:

```
A2b. For every port P that Δ changes (producer behaviour, port type,
     port removal, or module replacement):
       retain the CONTRACT of every other writer and every consumer
       incident on P, as a contract-stub:
         (entity id, port name, intent, WIT type, function, goal)
       Do NOT retain their descriptions, internals, or implementation.
     If Δ replaces a whole code module with no per-port dependency
     declaration (W-5.3 has no machine-readable intra-block relation),
     treat ALL of that module's exposed ports as changed.
     Recompute the boundary after the agent proposes a concrete Δ,
     before the edit is applied.
```

"Contract-stub" is the same projection CloakedEscort §4 uses for an unchanged controller; reusing it means this adds no new field vocabulary. It is bounded because W-5.4 caps a port's fan-out by the number of stored links to it, and the returned item is one line per incident port, not a subgraph expansion. Crucially, it is **not** "retain everything near an anchor": A is retained because it reads a port the edit changes, not because it is adjacent to L. An alarm three chunks away on a wireless channel is retained; a lamp beside the door reading a different port is not.

Tier-0 cost: for the fixture, one extra line —

```
C L.state  consumers=2  A.armed:bool  fn="latched armed state"  goal="stay armed until reset"
```

plus an obligation marker so the agent cannot ignore it: `preserve: A.armed (contract v3)`. That is exactly "what each one is meant to do", delivered only for the off-path entity whose meaning the edit touches. B2's split-if-over-budget rule applies unchanged; if a port has 40 consumers, the packet carries `consumers=40` + a `pull:consumers(L.state)` token and the task is split or paged, never silently truncated (CloakedEscort §54).

### 3.2 D2 — adjacency-revision keys (refresh)

The subscription must version **query results**, not just records:

```
D2. Every bounded adjacency query issued during selection registers a
    watch key: (query kind, port id, adjacency_revision).
    A link add/remove incident on a watched port bumps that port's
    adjacency_revision and emits a delta of kind consumer_added |
    consumer_removed | writer_added — even when the new link has only
    ONE retained endpoint and no retained record changed.
    On the proposed edit, revalidate every watched adjacency_revision;
    a mismatch forces a bounded reselect of that port's boundary only.
```

This is cheap in LadybugDB (W-3.5): a per-port edge counter, or a transactional rerun of `consumers(P)` before commit. It closes the revision-11 hole: the agent gets `consumer_added L.state -> A.armed` before it can apply the producer change. It also generalises SpinyBreach's `manifest_ready` idea — a slice boundary can widen for the same reason an entity can appear, and both must be explicit events, never silent.

## 4. Two related corrections I endorse, with reasons

- **WIT compatibility is local to a link (CloakedEscort §2).** The consolidated A2 says "Prune by WIT type compatibility (W-5.4) at every step." Read literally against a path, that prunes `C` in `L.pulled:event → C.pull:event ; C.open:bool → D.open:bool`, because `event ≠ bool` across the path — yet each stored link is individually type-correct and W-5.4 only checks *a link*. Fix: check each stored link against its own two endpoint types; never impose one signal type across a path. Traversing `C` requires a declared intra-block input/output relation; W-5.3 currently supplies only free-text `function`, which is not that relation. Until a machine-readable relation exists, the conservative rule is "all of C's outputs may depend on its inputs" — which is also what §3.1's module-replacement case needs.
- **A fixed projection is not intrinsically bounded (CloakedEscort §54).** B2's "tier 0 ≤400 tokens" is a projection shape, not a guarantee: arbitrary user intent, anchor count, port count or WIT type definitions can exceed it. The split-if-over-budget rule is the real guarantee; paging or a task split must preserve cross-page dependencies (the `preserve:` marker of §3.1 is one such dependency). I read B2 as already saying this, but it should be stated as a property of the envelope, not of the field list.

## 5. Falsifiable tests to add to G

```
12. Off-path consumer: fixture in §1, Δ = change L.state from maintained
    bool to pulse. Packet contains A.armed contract-stub + preserve:
    marker; a lamp on a different port is still excluded. (Locks A2b.)
13. Add-only consumer: Δ = add an independent new consumer to L.state,
    L.state behaviour unchanged. Packet does NOT contain A's internals;
    A's contract appears only if A is itself the added consumer. (Locks
    that A2b is change-keyed, not adjacency-keyed — the brevity half.)
14. Mid-build consumer: at revision 11 another builder adds
    L.state -> A.armed with no retained-record change and no link with
    both ends retained. Server emits consumer_added delta, bumps
    adjacency_revision, and blocks the producer edit until boundary
    reselect. (Locks D2; this is the case D misses.)
15. Mixed-type path: L.pulled:event -> C.pull:event ; C.open:bool ->
    D.open:bool. C is retained; no cross-path type pruning. (Locks §4.)
16. Fan-out cap: L.state has 40 consumers. Packet carries consumers=40
    + pull token, or the task is split; no silent truncation. (Locks §3.1
    boundedness against W-11.6.)
```

Test 13 is the one that would show my proposal to be mistaken: if A2b retained A in the add-only case, it would have reintroduced the near-anchor leak and should be rejected.

## 6. What follows if the table accepts this

D-W10's selection becomes a function of `(anchors, intent, accept, scope, verb, Δ)` instead of `(anchors, intent, accept, scope, verb)`. That is a real change to A1, not a footnote: the task record must carry an allowed-change set (CloakedEscort §21 already proposes "allowed changes" as an intake field, and W-9.6/W-7.4 already define who may grant it). It does not add a core capability — the boundary is a read over stored W-5.4 links, the watch is a query counter, and the delivery is ACP (W-11.7). It does mean the two-party `accept` rule in E has a third party to consider: a `preserve:` obligation on an off-path consumer is a constraint on "done", so `accept` authorship cannot be purely requester-side when Δ touches a shared port.

**Sign-off positions on H1–H5:** I confirm H1 (push-on-write, turn-coalesced) **with D2**; H2 as written, with the caveat above; H3 (two enums, `excluded.reason` vs `unresolved.reason`) — add `adjacency-cap` as a fourth `unresolved.reason` so a query that hit its cap is never reported as "no consumers"; H4 verb set sufficient; H5 capability-gated pulls, with A2b contract-stubs obeying the same W-9.6 grant filter as SpinyBreach's A6 stubs.
