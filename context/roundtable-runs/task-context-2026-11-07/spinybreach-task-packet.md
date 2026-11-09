# Task Packets: selection and delivery of an agent's task context

**Author:** SpinyBreach. **Status:** proposal for D-W10 (W-5.6). **Targets:** W-5.3, W-5.4, W-5.5, W-5.6, W-11.6, W-11.7.

This responds to the objective: decide how task context is chosen from the world and how it is given to an agent, short and on target.

The proposal is one mechanism with three parts:

1. **A task is a graph query, not a subtree export.** The task names a small set of *anchor* entities and an *intent*. Selection runs a bounded, typed walk from those anchors and prunes everything that is not on a path between anchors or a direct participant.
2. **The packet is laddered, not flat.** Tier 0 is always present and tiny (the goal, the anchor stubs, the acceptance checks). Higher tiers are pulled by the agent by name. This makes "short" a structural property, not a summarisation habit.
3. **The world is not filtered by a human-readable summary; it is filtered by graph shape.** The walk uses typed ports (W-5.4) so that a "door that opens when a lever is pulled" lawfully excludes the door's cosmetic hinge, the lamp in the corner, and every unrelated entity in the chunk.

Nothing here requires a new core capability (W-2.5). The selection is a read over the world graph (W-3.5); the delivery is an ACP message (W-11.7); the packet is generated content.

---

## 1. Why "give the agent the relevant objects" is the wrong default

The naive reading of "the objects the task involves, how they connect, and what each one is meant to do" is: take the entities in the task's region, serialise their manifests, done. This fails on four counts, and each failure is a design requirement:

| Naive behaviour | Failure | Requirement it forces |
|---|---|---|
| Dump all entities near the task | A chunk can hold thousands of placed voxel-blocks, creatures, particles' spawners. The agent drowns. | Selection must be **anchored**, not spatial. |
| Include every link touching an included entity | One busstone path to a lamp drags the lamp, its switch, its power source… | Selection must **prune by path**, not by adjacency. |
| Serialise manifests verbatim | `goal`/`function`/`description` are written for humans, verbose by nature. | Packet must be **projected**: only the fields the agent's role needs. |
| Include the whole intent record and every prior attempt | History crowds out the task. | Packet must be **capped and windowed** (cf. Mindcraft memory 500 chars, last 15 messages; W-11.6). |

The rest of this document answers those four.

---

## 2. Selection: the anchor-and-path walk

### 2.1 The task record

A task is an entity in the graph like any other, with a manifest-shaped record:

```
task : Task {
  id           : EntityId
  intent       : string          // W-5.5, user's words, kept verbatim
  anchors      : [EntityId]      // entities the task is about
  accept       : [Check]         // observable conditions for done
  scope        : Scope           // see 2.3
  requester    : EntityId        // player or agent that opened it
}
```

`anchors` and `accept` are the crucial part. A task that says only "build a door that opens when a lever is pulled" is under-specified; the server cannot know which door or lever. Two ways to make anchors legitimate:

- **The requester names them.** Clicking a lever and a door in-world and typing the instruction creates a task with those two anchors. This is the common case and it is cheap.
- **The agent resolves them, then confirms.** Given a bare instruction and a pointer (position, look-direction, selected block), the agent issues a `resolve` query (see 2.4) and the server returns candidates with graph excerpts; the agent picks anchors. One round trip, paid only when needed.

Either way, **selection is a pure function of `(anchors, intent, scope)`**. This is the auditability win: any packet can be reproduced from the task record plus the world state hash at time *t*.

### 2.2 The walk

Run a breadth-first walk from the anchor set. Retain an entity if and only if it is:

- **A** an anchor; or
- **B** an endpoint of a link whose **other** endpoint is retained, and that link lies on a path between two anchors or from an anchor to an `accept` target; or
- **C** a direct participant named by an anchor's manifest (a joint partner, W-4.2; a held handle, W-7.4); or
- **D** a *functional peer* of a retained anchor discovered by type: same `type` or same `goal` class, when the task is explicitly marked `extend`/`copy` scope (2.3).

Edges kept are only those among retained entities. This gives the famous "door opens when lever is pulled" a packet of:

```
lever  --[outbound:signal : bool]-->  door  --[outbound:state : DoorState]--> task.accept
```

and *not* the door's hinge mesh, *not* the lamp two busstone steps away, *not* the chunk's 700 decorative blocks.

### 2.3 Scope

`Scope` is the dial that turns the same walk into the right packet for the right job:

| Scope | Retains | Use case |
|---|---|---|
| `local` (default) | A, B, C | Fix or wire the named machine. Lever+door. |
| `pattern` | A, B, C + D peers | "Build another door like this one." Pulls one exemplar. |
| `area` | A, B, C + the voxel volume the anchors occupy (as a count + bounds, not every cell) | "Reproduce this room." Volume is summarised, never enumerated. |
| `open` | A, B only; agent must pull | Instruction is vague; the agent explores with queries. |

The default must be `local`. Every widening is an explicit cost the requester or agent chooses.

### 2.4 Query surface (pull)

The agent can always pull. Minimal, typed queries over the world graph:

| Query | Returns | Caps |
|---|---|---|
| `resolve(instruction, pointer) -> [Candidate]` | Entities near the pointer ranked by name/manifest similarity, stub fields only | ≤ 8 |
| `neighbourhood(id, depth=1, portFilter?)` | Retained entities/links at one hop | ≤ 24 |
| `manifest(id, portNames?)` | Projected manifest (3.1) | one entity |
| `example(goalClass, k=2)` | Up to 2 stored exemplars (cf. Voyager top-5, Mindcraft num_examples=2) | ≤ 2 |
| `history(id, k=3)` | Last k attempt records for that entity (cf. Voyager last round only) | ≤ 3 |

Each query counts its bytes against the same per-turn budget as the push (section 4). This stops "pull" from becoming a loophole that restores unbounded context.

---

## 3. Delivery: the laddered packet

### 3.1 Projection, not serialisation

The packet never carries a raw manifest. Fields are projected by *why the agent needs them*:

| Manifest field | In packet? | Transform |
|---|---|---|
| `name` | always | as-is |
| `intent` (in/out/two-way) | always | token |
| `type` (WIT) | always | compact WIT (`signal/bool`, `door/state`) |
| `function` | **only if used by a retained link** | one line, ≤ 90 chars |
| `goal` | **only for anchors** (tier 0) or when pulled | one line, ≤ 90 chars |
| `description` | **never in tier 0**; pullable | summarised to ≤ 2 sentences on pull |

Rationale: a port's `function` only matters when the agent must satisfy it or wire to it. An anchor's `goal` matters because the whole task is "make this entity do its goal". Everything else is on-demand. This alone typically cuts a packet by an order of magnitude versus full serialisation.

### 3.2 Tiers

```
Tier 0  ALWAYS, ≤ ~400 tokens
        goal (verbatim intent)
        anchors: id, name, goal (1 line), ports (name, direction, type)
        links among anchors
        accept: checks
        open questions (if any)
        pointer to tier-1 handles

Tier 1  PULL, via named ids/handles in tier 0
        manifest(id)        projected
        neighbourhood(id)   one hop
        example(goalClass)  1-2
        history(id)         last 3 attempts

Tier 2  SCENE, only when the agent is acting in-world (W-11.4)
        position, look-target, inventory (if relevant), nearby human/bot
        pushed on action, not on every thought
```

Tier 0 is the "short and on target" contract. It is generated by a deterministic projection function so its size is bounded by construction: one goal + (anchors × ports) + links + checks. A design rule we can enforce in tests: **tier 0 must fit a fixed token budget; if a task exceeds it, the task is too big and must be split.** That is a hard, checkable property rather than a hope.

### 3.3 Packet wire form

A compact, line-oriented form is better than nested JSON for token cost (this echoes Mindcraft's one-field-per-line observation and Voyager's line-per-field). Sketch:

```
TASK build a door that opens when a lever is pulled
SCOPE local
ACCEPT door.open == true when lever.on
# anchors
A1 lever  goal:"emit on"  ports: on:out/bool
A2 door   goal:"swing on signal"  ports: signal:in/bool  state:out/doorState
# links
L1 A1.on -> A2.signal : bool
# handles
H1 manifest(A1|A2)
H2 example(goalClass=door, k=1)
```

Handles are the pull surface: the agent names `H1` to expand. This is exactly ACP-friendly: tier 0 is one pushed message; each handle is a pull request (W-11.7).

---

## 4. Budget and the verbosity rule

W-11.6 says "every word costs the agent". Make it a number, per turn:

| Budget | Default | Enforced by |
|---|---|---|
| Tier 0 tokens | 400 | server truncates/splits task |
| Total pushed+pulled per turn | 1200 tokens | server rejects pull, tells agent to narrow |
| Pulls per turn | 6 | server |
| Attempt history shown | 3 | projection |

The numbers are Open to tune (like D-W6's limits) but the *existence* of a budget is not: without it, "pull" re-inflates.

---

## 5. Where this slots into the spec

- Amendments W-5.6 / D-W10: selection = anchored typed walk (2.2) with `Scope` (2.3); delivery = laddered packet (3.2) with projection (3.1), budgeted (4).
- Uses W-5.3 manifest fields as-is; adds no manifest field. (`goal`/`function`/`description` suffice; `Scope` and `anchors` live on the task record, new but content-level, W-2.5.)
- Uses W-5.4 typed links so the walk prunes by type as well as path.
- Uses W-11.7 ACP push/pull: tier 0 push, handles pull.
- Uses W-11.6 as the budget contract.

## 6. Falsifiable claims

1. For the lever/door task with decorative content in the chunk, tier 0 contains exactly {lever, door} and exactly one link.
2. Tier 0 token count is bounded by `k0 + n_anchors*k1 + n_ports*k2 + n_links*k3`; test: build a task with 100 unrelated neighbours, tier 0 size unchanged.
3. A packet is reproducible from `(task record, world hash)`.
4. No manifest field outside 3.1's projection is ever emitted; test: full manifest contains a 200-char `description`, packet never shows it in tier 0.

---

## 7. Reconciling with StonyPrism and NimbleEngine (round 2)

All three proposals agree: seed from anchors, expand along typed links, cap size, push once, allow pull. The disagreements are narrow but decisive.

### 7.1 Depth cap vs. path pruning — my position

NimbleEngine caps at 2 hops; StonyPrism caps at 1 hop "unless a port type forces it". Both are *depth* limits. Depth is the wrong axis: it retains everything within 2 hops of an anchor — including the lamp two busstones away that is within 2 hops of the lever — which is exactly the failure case.

The right axis is **path relevance**: keep an entity only if it lies on a path *between* two anchors or from an anchor to an `accept` target. For the lever/door task this is identical to StonyPrism's 1-hop result (both give {lever, door} + the link). They diverge once the anchor set grows: for "wire A, B and C", a depth cap of 2 retains any entity adjacent to any of three anchors; a between-anchors walk retains the 3-node chain only. Depth is a cheap proxy for path relevance; path relevance is the real predicate, and the graph database (W-3.5) is what makes it cheap, so there is no reason to settle for the proxy.

Concrete rule I propose for D-W10:

```
retain(e) := e ∈ anchors
          ∨ ∃ link l with e an endpoint, other endpoint retained,
            and e lies on some anchor→anchor or anchor→accept path
```

Depth still matters as a *safety* bound (guard against pathological graphs), not as the semantic criterion. Set the guard high (e.g. 8) and let path relevance do the pruning.

### 7.2 Negative context — adopt StonyPrism's idea, with a hard cap

StonyPrism's "negative context" (list excluded nearby entities by id+kind) is the sharpest idea on the table and I did not have it. It addresses a real failure: an agent that receives only {lever, door} may *invent* a third entity, or rebuild something that already exists outside the slice ("I'll add a repeater" — one already sits there, but it was pruned).

But it is not free, and listing exclusions *by id+kind* is an unbounded cost that violates W-11.6 as the world grows. Amend it to a **one-line exclusion summary**, capped:

```
EXCLUDED 3 entities within 8 blocks: lamp, repeater×2 (not on a signal path)
```

Rationale: the agent's hallucination risk is about *kinds present nearby*, not about specific entity ids. Ids would leak into the packet an entity the agent has no reason to touch. Kinds + count + reason is the minimum that prevents invented objects while staying constant-size. If the agent needs an id, it pulls `neighbourhood(anchor)`.

### 7.3 Adopt NimbleEngine's intent-authority rule

NimbleEngine's Q1 — intent (W-5.5) is authoritative over manifest `description` — is correct and I should cite it. Reason: `description` is authored by whoever built the entity, for general readers; intent is authored by the *requester for this task*. W-5.5 makes intent the thing the agent builds from. When they conflict, intent wins, and the packet should mark the conflict so the agent does not silently pick:

```
A2 door  goal:"swing on signal"  conflict: intent says "slide, not swing"
```

This is a same-size addition (a short tag) and it prevents the agent from building the wrong motion from a stale description.

### 7.4 The "new:" anchor problem — unresolved in both, sharpen it

Both papers assume anchors resolve to existing entity ids. The lever/door task's *door* may not exist yet — it is what the agent will build. StonyPrism touches this (`new:<kind>` plus a template manifest). I propose making it explicit in the task record with two anchor classes:

| Anchor class | Has manifest? | Packet carries |
|---|---|---|
| `existing` | yes | projected manifest (3.1) |
| `new` | no | the **blueprint template**: expected ports from the code module or asset the task names, with `goal`/`function` filled by the requester's intent |

Tier 0 for "build a door that opens when a lever is pulled" is then: lever (existing), door (new, template with `signal:in/bool` and `state:out/doorState`), one link, accept check. The agent is not given the door's *implementation* — only its *interface contract*, which is what "what each one is meant to do" means for an unbuilt part. This distinction (contract, not implementation) is the one thing both peer papers leave implicit and it is what keeps the packet short even when half the machine does not exist yet.

### 7.5 Consolidated open questions

1. Should the exclusion summary be kinds-only (my 7.2) or ids (StonyPrism)? I argue kinds-only, capped, with pull for ids.
2. NimbleEngine's assembly-as-context-unit (W-9.4): does an assembly anchor get its own scope, or is `area` scope (2.3) the right fit? I lean `area`.
3. Who writes `accept` checks — requester, or agent-proposed and confirmed? I lean requester for `local`, agent-proposed for `open`.

---

## 8. Round 3: the non-port dependency gap, and the delta mechanism

Two peer points are decisive and change the proposal. I accept both and specify them concretely.

### 8.1 CloakedEscort is right: the path predicate must traverse more than port links

My §2.2 walk follows W-5.4 port links. CloakedEscort's door example breaks it: if the door is a mesh attached to joint `J` driven by controller block `C` via a W-7.4 handle, then `lever → door` is *not* a port edge. The packet would contain lever and door and miss `J`, `C`, and `C`'s grant — the actual mechanism. An agent would then try to wire `lever.out → door.in` when no such port exists on a purely physical door, or wire a signal that nothing converts to motion.

The fix is to widen the traversal edge set, not the depth. The world graph has **five edge kinds** that can carry a task dependency, and my walk must follow all of them:

| Edge kind | Spec | Why it is a task dependency |
|---|---|---|
| Port link | W-5.4 | Signal/data path (the obvious one) |
| Joint | W-4.2 | A part is physically attached to another; motion propagates |
| Handle grant | W-7.4 | A block can *act on* an entity; the actor is a dependency |
| Sensor target | W-7.2 | A block's input depends on what it senses |
| Physics volume | W-7.3 | A world/volume parameter changes the entity's behaviour |

So `retain(e)` in §2.2 becomes: `e` is retained if it lies on a path between anchors (or an anchor→accept target) **in the multi-edge graph**, where a path step is any of the five above, subject to type/likeness checks per edge kind. For the lever/joint/block door, the path is `lever -(port)-> C -(handle)-> J -(joint)-> door`, and the packet is `{lever, C, J, door}` — four entities, each with its contract — which is still tiny and now *correct*.

This also resolves the tension with StonyPrism's withdrawn depth cap: a multi-edge path can be longer than a port path (lever→C→J→door is 3 steps), which is exactly why depth was never the right axis. Path relevance over the multi-edge graph is.

One distinction CloakedEscort adds that I adopt verbatim: **"a known absent connection" must differ from "a connection not yet inspected."** The packet must carry an `unresolved:` marker for a boundary the selection did not expand (an unchanged controller's internals, a wireless channel out of scope), so the agent never reads "not in packet" as "does not exist." Marking unknown costs a few tokens and prevents the worst class of build error — silently rebuilding a mechanism that already works.

### 8.2 NimbleEngine's delta subscription: adopt, with a concrete invalidation key

NimbleEngine's point stands: a one-shot snapshot is wrong because a build mutates the graph. Re-pushing tier 0 every step violates W-11.6; the slice must stay correct without that. I adopt the subscription and specify the mechanism the open question asks for:

**Push-on-write, coalesced, inside the slice boundary, gated on a version key.** Concretely:

```
slice = (retained set R, retained edges E)   // from §2.2, multi-edge
R0: push tier 0
each world step that mutates the graph:
    if a write touches an entity in R or an edge with both ends in R:
        append to outbox: {kind: link_added|entity_added|accept_state|manifest_ready, ...}
flush outbox once per agent turn (coalesced), never per simulation step
```

Three rules make it cheap and bounded:
- **Coalesce per turn, not per tick.** Many writes in one step collapse to one delta message. This is the same discipline W-8.3 already imposes on the bus (one step, ordered delivery).
- **The slice does not grow on its own.** A delta that would add a new entity to `R` (e.g. the agent built the door) is a *manifest_ready* event, not a silent widening — the agent sees it entered the slice and why.
- **Invalidation is by revision, not by diff replay.** Every retained record carries a source revision (CloakedEscort's "source revisions"); a pull returns `304`-style "unchanged at revision v" so the agent is not re-sent identical bytes. Before applying a proposed edit, the agent checks the revisions it read from; a mismatch forces a bounded reselect of only the affected records, never the whole packet.

Push-on-write is the right choice over pull-on-version because the agent cannot know *when* to poll — a pull design either polls every turn (wasting budget on "unchanged") or misses writes between actions. Push inside the retained-slice boundary is already the minimal set of writes the task can care about, so it does not need a broader subscription mechanism than the slice itself. This deserves recording as part of D-W10, not a new decision: it is *how* W-11.7's "the world pushes it" (already Proposed by the owner) is used for refreshes.

### 8.3 What the merged proposal now claims (updated falsifiable set)

Superseding §6, the packet is now:

1. Selected by **path relevance over the five-edge world graph** (§8.1), anchors existing or `new:`-template.
2. Delivered as **tier 0 projection + named handles**, budgeted, split-if-over.
3. **Refreshed by coalesced push-on-write deltas inside the retained slice**, revision-checked, never re-serialising tier 0.

New falsifiable tests:

5. **Joint mechanism:** door = mesh on joint `J` driven by block `C` via handle; packet contains `{lever, C, J, door}` and the lever→C→J→door path, and omits an unconnected lamp beside the door. (CloakedEscort's case 3.)
6. **Unknown vs absent:** an unchanged controller kept behind its contract appears as `unresolved: C.internals (contract C.v1)`; the agent's packet distinguishes it from "no controller." (CloakedEscort's case 4.)
7. **Delta:** after the agent links lever→door, the next turn's delta is one `link_added` edge; tier 0 bytes are not resent. (NimbleEngine's delta test.)
8. **Revision guard:** editing an entity whose revision changed since the packet was read forces a reselect of that record only; an unrelated entity's write produces no delta.

### 8.4 Remaining genuine open questions for the owner

- **Accept authorship (StonyPrism's press):** requester authors `accept` for `local` scope; agent proposes and requester confirms for `open` scope. I think this is settled by scope, not a single answer.
- **Wireless channels (D-W3, open):** a wireless link is a port edge in the graph, but its target set is permission- and range-scoped. Does selection follow a wireless edge into an entity the admin did not grant the requester? My position: follow it *read-only as a contract* and mark `unresolved: wireless peer beyond grant` — never silently include the peer's internals.
- **Tick freshness (CloakedEscort):** runtime observations must carry a tick; a static `accept` check like "door.open" needs a fresh read at the moment of the check, not the value at packet time. This is a delivery rule (pull fresh for state checks), not a selection change.

---

## 9. Round 4: correction to the consolidated D-W10 text (A2) and two merges

NimbleEngine's `nimbleengine-dw10-consolidated.md` is the right artefact — a single checkable amendment. I endorse sections B, C, D, E, G as written. **A2 is wrong as written and must be corrected before sign-off**, for a reason the table already accepted in round 3 (§8.1) but the consolidation did not carry forward.

### 9.1 Defect: A2 still says "via W-5.4 typed links"

Current text:
```
OR e lies on an anchor→anchor path or anchor→accept path (via W-5.4 typed links)
OR e is a direct participant named by an anchor's manifest (joint W-4.2; handle W-7.4)
```

The third line catches a joint only when it is a *direct participant named by an anchor's own manifest*. It does not catch a joint that sits **in the middle** of the path. CloakedEscort's case (round 3) is exactly that: `lever -(port)-> C -(handle)-> J -(joint)-> door`, where `J` is not named by lever's or door's manifest — it is the door's joint, and the handle is `C`'s. Under the current A2, the walk from lever to door over W-5.4 links finds nothing (no port edge lever→door), the direct-participant clause does not fire (J and C are neither anchors), and the retained set is `{lever, door}` — the mechanism is pruned. The agent then wires a port that does not exist, or wires a signal with no actuator behind it.

The defect is that A2 mixes two different edge scopes: **port links** (a path step) and **direct participants** (a one-hop-only inclusion). Joints, handles, sensor targets and physics volumes are *path steps*, not just one-hop inclusions. This is the "more edge kinds, not more depth" point I made in §8.1; the consolidation lost it.

### 9.2 Proposed replacement for A2

```
A2. Predicate. Retain entity e iff e ∈ anchors, or e lies on an
    anchor→anchor or anchor→accept path in the MULTI-EDGE dependency
    graph, where each path step is one of:
      (i)   a W-5.4 port link between WIT-compatible ports;
      (ii)  a W-4.2 joint attaching e to the previous entity;
      (iii) a W-7.4 handle grant from the previous entity to e;
      (iv)  a W-7.2 sensor target read by the previous entity;
      (v)   a W-7.3 physics-volume or world-parameter scope that
            applies to e and is set by the previous entity.
    An entity directly named by an anchor's manifest is retained even
    if no path exists (the existing third-clause case).
```

Path step types (i)–(v) are all edges already in the world graph (W-3.5); this adds no data, only says the walk must traverse them. The type check of A2 ("prune by WIT type at every step") applies only to step (i); the other steps have their own admissibility (a joint has two endpoints; a handle exists only where the admin/builder granted it, W-7.4; a volume is a set of cells or a world id).

### 9.3 Add the boundary marker the consolidated text lacks

A2 alone still lets the agent mistake "pruned" for "absent". Adopt CloakedEscort's distinction as a **required** delivery field, not an optional one:

```
unresolved: <id-or-role> (reason: not-inspected | beyond-grant | wireless-peer | impl-behind-contract)
```

Rules:
- A retained entity whose internals selection did not expand (unchanged controller kept behind its contract) emits `unresolved: C.internals (impl-behind-contract)`.
- A wireless peer past the requester's grant emits `unresolved: wireless-peer (beyond-grant)` — never silently included, never silently absent.
- An entity pruned by the negative context does *not* get an `unresolved:` line; it gets the capped `EXCLUDED` line (B4). The two are different claims: `EXCLUDED` = "inspected and irrelevant"; `unresolved` = "not inspected". This is the single most important anti-hallucination control after B2, because it tells the agent precisely when "not in my packet" means "does not exist" versus "I did not look."

### 9.4 Merge from StableReaper: permission is part of "only what it needs"

StableReaper makes a point none of us stated: pull must be **scoped to handles the agent holds (W-7.4 / W-9.6)**, so the context boundary is also a permission boundary. Two refinements:

- Selection itself should not leak an entity's manifest to an agent that holds no capability over it. If the path leads to an entity the requester's grant does not cover, retain it as a **stub** (`id`, `kind`, `unresolved: beyond-grant`) — enough to know it is there and to know it is out of reach, not enough to read its internals. This prevents the packet from becoming a privilege-escalation read channel while still warning the agent that a dependency exists.
- StableReaper's **content hash + simulation step stamp** (their step 6) should be the revision key for my §8.2 delta model. One mechanism, not two: `rev` = content hash of the retained slice, `step` = W-8.3 step. A delta carries the new `rev`; a pull of an unchanged record returns `rev-unchanged`. This unifies StableReaper's auditability requirement with NimbleEngine's refresh clause.

### 9.5 Sign-off on NimbleEngine's H1–H3

- **H1 push-on-write:** accept, with the §8.2 mechanism (coalesced per turn, inside slice boundary, revision keyed). Record in D-W10 as *how* W-11.7's owner-Proposed push is used; no new D-W needed.
- **H2 two-party accept:** accept as written. It is correctly scoped (requester for `existing`, agent-proposes/requester-confirms for `new:`). No amendment.
- **H3 exclusion reason enum:** accept `{not-on-path, type-mismatch, out-of-scope}`, but it is now **distinct from the `unresolved` reasons** in §9.3. Two enums: `excluded.reason` (why inspected-and-dropped) and `unresolved.reason` (why not inspected). Collapsing them would re-create the absent-vs-unknown confusion §9.3 fixes.

### 9.6 Net: what must change in `nimbleengine-dw10-consolidated.md`

| Clause | Change |
|---|---|
| A2 | Replace with multi-edge path predicate (§9.2) |
| B4 | Keep enum; add that it is separate from `unresolved` (§9.5) |
| D | Add revision key = content hash + step (§9.4) |
| new B6 | Add required `unresolved:` delivery field (§9.3) |
| new A5 | Stub-with-`beyond-grant` for out-of-grant entities on the path (§9.4) |
| G | Add tests 6–9 from §8.3; add "out-of-grant stub" and "unresolved≠excluded" tests |

With these five edits the document is correct and I will sign it.

---

## 10. Round 5: three remaining defects in v3, and the closing patch

v3 adopted the five-edge A2 (good) but did not carry three correctness items from §9. It is close; these are the rest. Each is a patch with a line you can paste, not a rewrite.

### 10.1 A2's last clause still re-opens the leak it was meant to stop

v3 A2 line 25:
```
OR e is a direct dependency of an anchor through any of the five kinds above.
```

This is a **one-hop inclusion with no path constraint**, and it is exactly the failure the whole design exists to avoid. Concretely: a lamp that is itself a code block holding a handle to a shared power bus is a "direct dependency of an anchor" if that anchor is the bus block anywhere on the path. Read literally, every entity the anchor *acts on* comes in — which for a controller block can be dozens of actuators. The path predicate was introduced to stop "retain everything near/facing the anchor"; a direct-dependency clause re-admits it through the capability edge.

The only direct inclusions that are safe are the ones the *task itself* names:

```
A2 clause 5 (replacement):
OR e is a joint partner (W-4.2) or a held handle target (W-7.4) of an ANCHOR
   (not of an intermediate retained entity), and the task's `accept` names it
   or the anchor's manifest names it as a port/joint participant.
```

Rationale: a direct inclusion must be justified by *declaration*, not by *adjacency through a capability*. Declaration is finite (an entity's manifest and the task's accept list are bounded and human-authored); capability-reach is not. So "the server refuses a direct-dependency clause over W-7.x edges that the task did not name" is the safe form. This narrows v3 A2 line 25 rather than deleting it — the joint/handle case in test 6 still resolves through the *path* (lever→C→J→door), which is unaffected.

### 10.2 The `unresolved:` field is prose, not a field

v3 B4a says the selection "must distinguish a verified absent connection from a boundary not yet inspected" but defines no output for it. An agent cannot act on a rule that has no key in the packet. This is the difference between a policy and an interface. Add the field (the closing form of my §9.3):

```
B4b. Every packet MAY carry zero or more `unresolved:` lines. Form:
     U <id-or-role> reason=<not-inspected|beyond-grant|wireless-peer|impl-behind-contract>
     Presence rules:
       - retained entity whose internals were not expanded → impl-behind-contract
       - path reaches an entity past the requester's grant  → beyond-grant (stub form, see A6)
       - wireless edge outside requester's grant (D-W3)     → wireless-peer
       - query hit its cap before completing the walk       → not-inspected
     An `unresolved:` line is NOT an `excluded:` line. `excluded:` means
     "inspected, not relevant"; `unresolved:` means "not inspected / not
     reachable". A packet that omits both signals completeness of the slice.
```

The value of the field is that it is *checkable*: a test asserts that a packet for an out-of-grant wireless peer contains `U … reason=wireless-peer` and *not* an `excluded:` line, and that removing the grant does not turn an `unresolved` into a silent absence.

### 10.3 The `beyond-grant` stub rule is missing entirely

B3a gates pulls on held handles, but selection still serialises the manifest of any entity on the path — including one the requester's grant does not cover. That is a **read-privilege escalation**: the packet becomes a way to read a machine the agent cannot act on. StableReaper's permission-boundary point (B3a) is half-done without this.

```
A6. Out-of-grant retention.
    If the path reaches entity X but the requester's grant (W-7.4/W-9.6)
    does not cover X, retain X as a STUB only:
        id, kind, and U X reason=beyond-grant
    Omit its manifest internals, ports, and description. The agent learns
    X exists and is a dependency, but not how it works.
    If the task's `accept` cannot be verified without X's contract, the task
    is BLOCKED with a message to the requester, not silently under-specified.
```

This is the correct bridge between "only what it needs" (W-11.6) and "only what it is allowed" (W-9.6): a dependency you cannot touch is information (its existence changes your plan) but not context (its internals are not yours to read). Stub form is the minimum that serves both.

### 10.4 Effect on v3's tests

v3 G has tests 6–8 covering the multi-edge path, wireless distance and revision invalidation. Three more are needed to lock §10:

```
9. Direct-dependency leak: bus block anchor + 40 actuators it holds handles to,
   none named in accept → packet contains the anchors and on-path entities only;
   zero held-handle targets of non-anchor retained entities. (Locks A2 clause 5.)
10. Unresolved ≠ excluded: out-of-grant wireless peer present → U reason=wireless-peer,
    and no `excluded:` line for it; after granting, a normal retained record. (Locks B4b.)
11. Stub minimality: an out-of-grant joint partner on the path yields id+kind+U
    only — no ports, no description. (Locks A6.)
```

### 10.5 Sign-off status after this round

With §10.1–10.3 applied, D-W10 is correct and I sign it. Without them it is *nearly* correct but has one leak (A2 clause 5), one un-actionable rule (B4a), and one privilege hole (B3a without A6) — each small, each caught by a test above. H1–H5 stand as v3 states them; I confirm H1 (push-on-write, turn-coalesced), H2 (two-party accept), H3 (exclusion enum, now separate from `unresolved.reason`), H4 (`{inspect, build, extend, repair}` is sufficient; add a verb only when a fixture needs it), H5 (capability-gated pulls, now completed by A6).

---

## 11. Round 6: the change boundary is real and needs a trigger rule

I read `CloakedEscort-selection-counterexamples.md`. Its §1 is the most important contribution since round 3, and it forces a real amendment — not another guard. I accept it and specify the mechanism, because "recompute the change boundary when the agent proposes its edits" is a sentence, not a rule an implementer can build.

### 11.1 The distinction the table has been missing: sufficiency vs safety

Every rule so far answers *is this context sufficient to build the door?* None answers *is this context sufficient to not break something else?* Those are different predicates, and CloakedEscort's fixture proves they diverge:

```
L.state:bool ──> C.request:bool ──> D
          └───> A.armed:bool            (alarm, off the goal path)
```

Two legal edits both pass the door's accept check:
- **(a)** add a second consumer to `L.state` — A unaffected; A's internals irrelevant.
- **(b)** change `L.state` from maintained to pulse so C's converter works — **breaks A**; A's contract is mandatory context.

The goal-path predicate returns the same slice for (a) and (b). So the packet can be minimal, on-target, *and* wrong. This is the one failure class budgets and caps cannot catch, because the error is an omission of a *consequence*, not a matter of size.

### 11.2 Why this is not solved by widening the goal slice

The tempting fix — "also include everything sharing a port with any anchor" — reintroduces the lamp problem at full strength: `L.state` may be read by dozens of unrelated machines. The insight is that **whether a shared consumer matters depends on the edit, not on the graph**. Before an edit is chosen, A is not context; after edit (b) is chosen, A is. So the slice must be a function of `(anchors, intent, scope, proposed edit set)` — and the edit set does not exist at task start.

This is why the change boundary is a *second selection*, deliberately deferred, not a widening of the first.

### 11.3 The mechanism: an edit manifest with a declared footprint

The rule needs the agent to declare *what it will change* before the server can compute what that touches. That is a small, cheap ACP message the design already implies (the delta model's `manifest_ready` and `conflict:` push assume the server knows a build happened). Make it explicit:

```
EDIT-PLAN submitted by agent before mutating the graph:
  changes: [
    { kind: port_behaviour, entity: L, port: state,
      from: maintained, to: pulse },      // behaviour change → footprint widens
    { kind: link_add,     from: L.state, to: C.new_in }   // additive → footprint narrow
  ]
  revertible: true|false
```

Server then computes the **change boundary** = for every entity/port named in `changes`, all *existing incident* edges of the changed ports, keeping the *far* endpoints' contracts (bounded fields: port names, types, `goal`, one-line obligation), not their implementations. Concretely:

```
BOUNDARY(edit) = { contract(x) | ∃ e ∈ edit.changes,
                   edge(e.port → x.port) ∈ world graph, x ∉ slice }
```

This is small and bounded by the *fan-out of the changed ports*, not by the world. For edit (b) it yields `A: armed:in/bool goal="alarm on unsafe door"` plus the obligation `preserve: A.armed` — two lines. For edit (a) it yields nothing A-related, because adding a consumer does not change any existing port's behaviour; the new link is additive and its own footprint is the new edge. So the *same* selection machinery gives A for (b) and not for (a), which is exactly the discrimination CloakedEscort demands.

### 11.4 The conservative default and the pulse/state trap

CloakedEscort's sharpest sub-point: the graph records `state:bool` and `request:bool`; nothing records that a *maintained* bool and a *pulse* bool are different behaviours. A WIT type cannot express "maintained vs edge" (W-7.1 types are values, not timing semantics). So selection cannot infer that edit (b) changes behaviour. Two consequences:

1. **An edit that changes a port's temporal behaviour MUST declare it** in the edit manifest (`from: maintained, to: pulse`). If the agent omits it, the server cannot catch it — so the conservative default is: *any edit that replaces a code module or changes a port's `function` treats all of that entity's ports as behaviour-changed*, widening the boundary to every incident edge. This is CloakedEscort's "treat all exposed behavior as potentially changed."
2. **`function` free text is not a dependency relation.** CloakedEscort is right that W-5.3 has no machine-readable input→output mapping inside a code block. The conservative approximation for traversal is: *a code block's every output may depend on its every input*, which makes C a single node in the walk (already true under the path predicate) and makes its internal mapping irrelevant to selection — we do not walk inside C, we treat C as a transducer whose contract is its whole port set. That is sufficient and avoids inventing an intra-block dependency language W-5.3 does not have.

### 11.5 WIT compatibility is per link — correcting A2's "at every step"

v3 A2 says "Prune by WIT type compatibility (W-5.4) at every step." CloakedEscort §2 shows this is wrong as phrased: `L.pulled:event → C.pull:event`, `C.open:bool → D.open:bool` is a valid chain with *different* types at the two ends, and pruning by the anchor's type would delete the converter. The type check belongs to each **link**, never to a path:

```
A2 (corrected): a path step is admissible iff its own edge is admissible;
                a port-link step requires the two linked port types to be
                W-5.4-compatible. No type is imposed across a path.
```

This is a one-line fix and I flag it because v3 as written would delete exactly the relay/converter node StableReaper's own worked example (the `e30 relay`) contains.

### 11.6 Revision checks must cover query results, not records

CloakedEscort §3 is correct and my §8.2 delta model has the same hole: it watches writes to retained records and edges with both ends retained, so a *new* off-slice consumer added after selection is invisible until something re-queries. My revision key (content hash of the slice, §9.4) does not help, because the slice's own content did not change.

Fix: the revision key must include an **adjacency revision** for the ports the edit touches, not just the retained set's hash:

```
slice.rev = hash( retained records , retained edges , adjacency_rev(touched ports) )
adjacency_rev(port) increments when any edge incident to that port is added/removed
```

Then edit (b) — a behaviour change to `L.state` — carries `adjacency_rev(L.state)`; if a builder added `L.state → A.armed` meanwhile, that counter moved, the agent's held rev is stale, and the server forces a boundary recompute *before* the edit commits. This closes the "concurrent builder" case without widening normal selection: the cost is one integer per touched port. It also composes with CloakedEscort's `unresolved` on query cap — a walk that hit its cap reports `not-inspected`, never an empty consumer set (§10.2).

### 11.7 Is CloakedEscort's edit-time cost worth it? Yes, and here is the budget argument

Someone could object that this adds a round trip and grows the packet. It does not grow the *tier 0*: the boundary is computed only when an edit is proposed, and for the door task edit (a) yields zero boundary lines while edit (b) yields two. The round trip is one small `EDIT-PLAN` message, cheaper than the cost of silently breaking an alarm. And it is *auditable*: the server can log `BOUNDARY(edit)` per edit, so "why did the agent not warn about the alarm?" is answerable after the fact. The alternative — omit the alarm to stay brief — trades a fixed two tokens for an unbounded class of "the agent broke something it never saw." W-11.6 prices words; it does not license ignorance of consequences.

### 11.8 What this adds to the consolidated doc (§11 patch table)

| Clause | Change |
|---|---|
| A2 | Type check **per link**, not per path (§11.5) |
| new A7 | Two-part selection: goal slice + change boundary (§11.1–11.3) |
| new A7a | `EDIT-PLAN` message defines the boundary footprint; conservative default for module/behaviour edits (§11.4) |
| new A7b | Code block = single transducer node; no intra-block dependency language (§11.4 point 2) |
| D | `slice.rev` includes `adjacency_rev(touched ports)` (§11.6) |
| G | Add CloakedEscort's 3 fixtures as tests 12–14 and the pulse/state test 15 (§11.9) |

### 11.9 Tests that lock §11

```
12. Off-path consumer, additive edit: add consumer to L.state → boundary empty
    for A; packet does not grow. (CloakedEscort case 1a.)
13. Off-path consumer, behaviour edit: change L.state maintained→pulse →
    boundary contains A.armed contract + preserve obligation. (Case 1b.)
14. Concurrent consumer: agent reads consumers(L.state)=[C] at rev 10; builder
    adds L.state→A at rev 11; edit (behaviour) is refused with boundary recompute
    before commit. (Case 3.)
15. Converter chain: L(event)→C→D(bool) retains C, and per-link type check passes
    each edge; pruning by anchor type would fail the test. (Case 2.)
```

---

## 12. Round 7: v3 has a duplicate label and a mechanism-free A7; StonyPrism's `validate` gets authority wrong

I re-read the current consolidated v3 line by line. Two concrete defects and one disagreement that changes the world's authority model.

### 12.1 Defect (mechanical but blocking): `B6` is defined twice

v3 line 66 and line 77 both open `**B6.**`. The first is the required `unresolved:` field; the second is the completeness/`omitted:` rule. A spec amendment with two different clauses under one ID cannot be cited, tested, or implemented — a test author reading "B6" cannot tell which rule failed. Fix:

```
unresolved: field      → B6
completeness/omitted   → B7
```

Trivial, but a document "ready to amend W-5.6" must not ship duplicate clause IDs; the amendment is what downstream code and tests cite.

### 12.2 Defect: A7 names the change boundary but omits its only implementable rule

v3 A7 says the boundary is "recomputed when the agent proposes its concrete edits." That is the *goal*. It does not say:

- **what message carries the proposal** (so the server has nothing to recompute from);
- **what the boundary is a function of** (it would have to guess);
- **how a concurrent builder's new consumer is detected** (record hashes miss it; §11.6);
- **what the conservative default is** when a module is replaced and no per-port mapping exists.

My §11.3–11.6 supplied exactly these four, and v3 did not carry them. Without them A7 is un-actionable — the same defect I flagged for B4a in §10.2 (a policy with no key). Concrete patch, restated compactly so it can be pasted:

```
A7a. EDIT-PLAN. Before mutating the graph, the agent submits
     EDIT-PLAN { changes: [ {kind: port_behaviour|port_replace|link_add|link_remove|entity_replace,
                             entity, port, from?, to?} ], revertible: bool }.
     The server computes BOUNDARY(EDIT-PLAN) = the projected contracts
     (ports, types, goal, one-line obligation) of every far endpoint of an
     existing edge incident to a changed port. Implementations are never
     included. The boundary is returned as a tier-1 delta and must be
     acknowledged before the edit commits.

A7b. Conservative default. A change of kind entity_replace, or any change
     whose `to` differs in temporal behaviour from `from` (maintained vs
     edge/pulse), widens the boundary to EVERY incident edge of that entity,
     because W-5.3 has no machine-readable input→output or temporal mapping
     inside a code block (CloakedEscort §2). A code block is one transducer
     node: its every output may depend on its every input; selection never
     looks inside it.

A7c. Adjacency revision. slice.rev = hash(retained records, retained edges,
     adjacency_rev(touched ports)). adjacency_rev(port) increments on any
     incident edge add/remove. A stale adjacency_rev refuses the edit with a
     boundary recompute. One integer per touched port; closes the
     concurrent-consumer case CloakedEscort §3 raises.
```

The budget defence (that this costs almost nothing) is §11.7: additive edits yield an empty boundary, behaviour edits yield two lines, and the round trip is one small message. StonyPrism's concern in [R1-21] that `validate` might exceed the 1200-token budget is answered by the same numbers — the boundary is bounded by *touched-port fan-out*, not by the world, and is capped like any pull (B3).

### 12.3 Disagreement: who enforces the boundary — server-blocks vs agent-acknowledges

StonyPrism [R1-21] proposes `validate(edits) → boundary-delta`, and "if the delta introduces a consumer whose contract conflicts with the edit, the server returns `conflict:` and **the task pauses**" — i.e. **the server refuses the edit**. That is a real design fork, and I think it is the wrong side of it, for spec-grounded reasons:

1. **The server is the authority for physical validity, not for intent** (D-W4 recommendation: "The server is the authority. A client predicts only the entity its player or agent controls"). The server already refuses *type-invalid* links by rule (W-5.4) because that is a hard invariant. "Changing lever to a pulse breaks the alarm" is **not** a hard invariant: it may be exactly what the requester wants (retire the alarm). A server that blocks it has encoded a design opinion into the core — which W-2.5 forbids ("Content never requires an adjustment to the core" cuts both ways: content behaviour must not be vetoed by the core either).

2. **The alarm break is detectable, not forbidden.** The correct output of `validate` is *information*: `BOUNDARY: A.armed expects maintained (obligation preserve)`. The agent, or its requester, decides. If the requester ratifies "yes, break the alarm," the edit is legal. A block-without-override makes the only escape route "change the alarm's contract first," which the agent may not be granted (W-9.6) — so a *correct* edit becomes impossible for a reason unrelated to correctness.

3. **StonyPrism's own fallback concedes this.** Their "what would show this wrong" says: if `validate` exceeds budget, precompute for *declared* verbs and skip revalidation for `repair` "because the verb bounds the writes." That is an admission that enforcement is a *cost/benefit* knob, not an invariant — which is the shape of an acknowledgement requirement, not a refusal. Better to start at the low-cost end (acknowledge) than to build a refusal path that must later be softened.

So the amendment should read: **`validate` returns a boundary delta and an `ack` requirement; an edit whose boundary contains a `preserve` obligation cannot commit until the agent sends `ack` naming each affected contract (or the requester ratifies a break). The server does not decide that the break is wrong; it decides that the agent has seen it.** This keeps the server authoritative over *whether the agent looked*, not over *what the agent may choose* — which is the same distinction W-5.4 vs D-W4 already draws for types vs play.

Concretely:

```
A7d. Enforcement. An edit whose BOUNDARY contains a conflicting or
     unknown obligation returns `HOLD: <obligation ids>`. The edit commits
     only after `ACK { obligations: [...] }` from the agent, or a
     `RATIFY-BREAK { obligations, by: requester }` from the requester.
     The server records the acknowledgement and the bound obligations in the
     assembly's history (W-9.4). The server never rules on whether the break
     is acceptable; it rules on whether it was seen.
```

This is strictly stronger than StonyPrism's version in auditability (a logged ack, not a silent refusal) and strictly weaker in authority (does not overrule a legitimate requester) — both correct for a core that must not encode content policy.

### 12.4 Test additions (lock §12)

```
16. Duplicate-ID: automated check that no two clause IDs in the amended
    W-5.6 collide (catches the current B6/B6).
17. Boundary trigger: EDIT-PLAN with only link_add → BOUNDARY empty, no HOLD.
    EDIT-PLAN with port_behaviour maintained→pulse → HOLD(A.armed), and an
    edit commits only after ACK. (Locks A7a/A7d.)
18. Override path: same as 17 but requester sends RATIFY-BREAK → edit commits,
    logged. (Proves server-block is not hard-wired.)
19. Conservative widening: entity_replace on a controller with no port
    mapping → BOUNDARY includes every incident edge of that entity. (A7b.)
```

### 12.5 Sign-off after this round

I sign D-W10 v3 **with** §12.1 (ID fix), §12.2 (A7a–c mechanism), §12.3 (A7d acknowledge-not-block). Without §12.2 the document is unimplementable at A7; without §12.3 it encodes a content veto into the core. The remaining H items are correct as v3 lists them; my answers: H4 yes `{inspect, build, extend, repair}` suffices for the W-12.2 fixture, extend only when a fixture needs it; H5 yes; H6 measure against the W-12.2 machine (object+joint+code block), noting 400/1200/1500 are three different budgets and should be named distinctly; H7 yes, `area` reports bounds only.

---

## 13. Round 8: I was wrong on D2 freshness; `stability:` resolves the audit; enforcement stays acknowledge-not-block

Three corrections, one of which retracts my own position.

### 13.1 Retraction: D2's "hash bump covers tick-freshness" is false — CloakedEscort is right

I supported NimbleEngine's D2 ("the content hash per delta already covers this: a bump invalidates any `accept` result stamped earlier"). CloakedEscort's Counterexample B shows this is a category error, and I should say so plainly because I endorsed it:

- W-4.4 gives moving physics bodies and joints; W-8.3 advances physics per simulation step.
- W-3.5 stores entities, ports, links, manifests, intent — **not** body positions.
- So a body can enter the doorway at step 101 with **no** stored record changing and the packet hash unchanged.
- And turn-coalesced deltas (D, agreed) mean even a watched runtime change may not have reached the agent yet.

The hash identifies *delivered structural context*; it cannot certify *runtime state*. My §11.6 revision key and this are different objects — I conflated "definition staleness" with "world staleness." The correct rule is CloakedEscort's:

```
D2 (replacement). Runtime observations and acceptance evidence carry their
evaluation step (accept … @step). Evidence is a statement about that step,
not about now. When an action requires a condition to hold NOW, the
authoritative server evaluates that condition at action execution (D-W4
"the server is the authority"), under a guarded operation, and returns the
result. Structural hashes never substitute for this. A historical test
result ("door opened during steps 100–110") stays valid as evidence of that
run; it does not assert the current door position.
```

This is *cheaper* than what it replaces in the common case (the agent does not pull state it is about to act on — the act returns it), and it is the only correct form. It also fixes a flaw in my own tier-0 design: B1 lists `accept` checks in tier 0, and those must now always carry `@step` and never be read as current.

### 13.2 `stability:` is the missing typed contract — adopt, with the placement caveat

StonyPrism's diagnosis is exactly right: my A7b conservative default ("module/behaviour edit ⇒ all ports behaviour-changed") is *sound but blunt*, and the sharp version needs a machine-readable temporal contract that W-5.3 does not have. Without it, the commit-time "behaviour-mismatch audit" is prose-judging-prose — the agent declares `preserved`, the consumer's manifest says "requires maintained output" in English, and the server has no rule to contradict the agent. I flagged in §12.3 that the server should not *rule* on breakage; the corollary I did not state is that it then has no basis to *detect* a lie either. `stability:` supplies that basis without adding an edge type.

Adopt:

```
W-5.3 addition (optional field, default preserves existing content):
  port.stability : maintained | pulse | edge | any   (default: any)

BOUNDARY(edit) rule:
  for a touched port p, let s = contract(p).stability.
  if s = any      → no constraint; edit proceeds (declaration advisory).
  if s ≠ any      → the edit's declared behaviour must equal s, else
                    HOLD with `stability-mismatch on p (declared X, contract s)`.
```

Why this is the right field and not a hack: `stability` is a *contract the consumer made*, not a property the producer has. A producer can emit `bool` either as level or edge — that is genuinely a producer choice. But a consumer that latches on maintained state is *broken by* a producer that pulses, and its manifest is the natural place to say so. Default `any` means every W-12.1 content item that predates this field keeps working (W-2.5, no core change). I endorse StonyPrism's fallback explicitly: **if measurement against W-12.1 redstone-like content shows collisions (maintained/pulse contextual to the receiver, not the port), move it to `link.stability`** — the test 16 works identically in both placements because the check reads `contract(p)` through the retained link either way. I would actually predict the link placement is correct for redstone (a torch feeding a repeater vs feeding a lamp wants different things), so I recommend *measuring* before choosing port vs link, and note the link placement is the safer guess.

### 13.3 Enforcement: I hold acknowledge-not-block, and here is the sharpened argument

NimbleEngine's B7 says a conflicting boundary-delta makes the server return `conflict:` and "the task pauses — **enforced**, not merely informative," closing that "the exclusion is no longer passive information; it blocks the breaking edit." StonyPrism's test 16 expects the server to "refuse commit." I disagree, and §12.3's reasons stand; sharpen them with the `stability:` field now in play:

1. **With `stability:` the server can now detect, but detection ≠ veto.** `stability-mismatch` is a *fact about a contract*, not a judgement that the edit is wrong. The requester may have decided to retire the alarm; a legitimate edit then carries `stability=maintained` on a port that is being deliberately changed. If the server refuses, the only legal path is "first edit the alarm's contract," which needs a grant (W-9.6) the agent may not hold — so a correct edit becomes impossible for an unrelated permission reason.

2. **"Blocks the breaking edit" is not the same as "only what it needs has teeth."** StonyPrism wants exclusion *enforced*. The enforcement that matters is: **the agent cannot commit an edit it was told would break a contract, without recording that it knew.** That is a HOLD + ACK, exactly A7d. It has teeth — an unacknowledged commit is impossible — without encoding content policy in the core (W-2.5).

3. **NimbleEngine's `editable:` set (B7) is the right *permission* gate and a separate one.** An edit outside `editable` (task's allowed change set ∩ requester grant) is refused — that *is* a hard invariant (a grant boundary, W-9.6), like W-5.4's type refusal. So the document already has one legitimate refusal path. Adding a second refusal path for *contract consequences* over-loads the same word "refuse" for two different things: "you may not touch this" (permission — refuse) vs "this will break that" (consequence — HOLD/ACK/RATIFY). Keeping them distinct is what keeps the core content-neutral.

So the settled form:

```
editable ∉ edit            → REFUSE (permission, W-9.6)            [hard]
stability/contract conflict → HOLD + ACK or RATIFY-BREAK (consequence) [recorded]
boundary unknown/not-inspected → HOLD, pull or reported unresolved   [recorded]
```

Three distinct outcomes, three distinct authorities. NimbleEngine's B7 and my A7d are the same gate with different verbs; merging them this way satisfies both — the gate *is* enforced (nothing commits unacknowledged), it just does not *veto*.

### 13.4 Consolidated test set (final)

```
16. stability: alarm port stability=maintained; agent proposes pulse + declares
    preserved → HOLD `stability-mismatch`; commit requires ACK or RATIFY-BREAK.
17. freshness: doorway clear @step100; physics moves body in @step101; no
    structural change. An action guarded by "doorway clear" gets the step-101
    server value; the tier-0 accept @step100 is not treated as current.
    (CloakedEscort counterexample B.)
18. unseen consumer: builder adds L.state→A.armed at r11 after packet r10;
    producer behaviour edit at r12 → boundary refresh shows A before commit.
    (Counterexample A + adjacency_rev.)
19. permission vs consequence: edit outside `editable` → REFUSE; edit inside
    `editable` but breaking a stability contract → HOLD, not REFUSE.
20. no duplicate clause IDs (catches the B6/B6 collision).
21. additive edit: link_add only → no HOLD, boundary empty, commits immediately.
```

### 13.5 Sign-off

I sign D-W10 for amendment to W-5.6 **with**: §12.1 (B6/B7 ID fix), §12.2 (A7a–c mechanism), §12.3/§13.3 (three-way REFUSE/HOLD/ACK), §13.1 (D2 replacement — retracting my earlier support), §13.2 (`stability`, link-placement preferred pending measurement). These are the whole delta; nothing else in v3 is contested. The amendment touches only W-5.3 (add optional `stability`) and W-5.6 (fill in D-W10) — no core capability (W-2.5 holds), no new D-W decision beyond recording that W-11.7's owner-Proposed push carries deltas.

---

## 14. Round 9: A1 must carry Δ (accept); the artifact re-derives §11; two claims are wrong

StableReaper's `change-boundary-StableReaper.md` arrives at the same mechanism as my §11, independently. That is convergence evidence, not a new discovery — and their central premise ("it is not in SpinyBreach §9–§10") is false: §11.1 has the identical `L.state → C → D` + `L.state → A.armed` fixture, §11.3 has the identical deferred `EDIT-PLAN` boundary, §11.5 the identical per-link WIT correction, §11.6 the identical `adjacency_rev`. Their §2 also attributes to me a delta gate I explicitly superseded in §11.6 ("gates deltas on edits with both endpoints retained"). I say this not to score a point but because sign-off needs an accurate record of what is actually in the merged text: **the fixture and patch are agreed; what remains is one real A1 change and two claims I reject.**

### 14.1 Accept: A1 must declare the allowed-change set — this is the real gap

Their §6 is the one substantive addition to the merged doc. My A7 (v3) says "recomputed when the agent proposes its concrete edits," but A1's task record has no field for the allowed scope of change, so the server has no basis to distinguish a legitimate edit from a trespass except `editable:` (NimbleEngine's B7, which exists but is not in A1). Fold them into A1:

```
A1 (amended). Task record fields:
  anchors, intent, accept, scope, requester, verb,
  allowed_change : set of {entity, port?}  // ∩ requester grant (W-9.6)
  Δ             : EDIT-PLAN, absent at R0, supplied before each edit
```

`allowed_change` is the *permission* input (REFUSE when an edit falls outside); `Δ` is the *consequence* input (BOUNDARY). They are different inputs to different outputs and both must be in A1 — StableReaper is right that this is "a real A1 change, not a footnote." It requires no core capability: `allowed_change` is an intake field derived from W-9.6/W-7.4 grants that already exist.

### 14.2 Reject: the `accept` third-party caveat is over-reach

StableReaper §6: "a `preserve:` obligation on an off-path consumer is a constraint on 'done', so `accept` authorship cannot be purely requester-side when Δ touches a shared port." This conflates two distinct things:

- **`accept`** answers *is the door task done?* — `door.open == true when lever.on`. It is requester-authored (E), about the **goal**.
- **`preserve:`** answers *what else must still be true?* — `A.armed` still behaves. It is about the **consequence**, and its handling is already specified in §13.3 as `HOLD + ACK or RATIFY-BREAK`.

Adding a `preserve:` clause to `accept` would make "done" depend on an edit's side effects, which is wrong in a case StableReaper's own framing implies: if the requester *wants* the alarm retired, the door is still done when the door opens, and a `preserve:`-bearing `accept` would report it as unfinished forever. The correct structure keeps them separate: `accept` gates task completion; `preserve:` gates edit commit (per-edit HOLD/ACK). A task can therefore complete having *acknowledged* a break, which is exactly the outcome a content-neutral core must allow (§13.3, reason 1). So E stands unamended; the third party is handled where it belongs, in A7d/§13.3, not in E.

### 14.3 Reject: test 13 does not test what it claims, but my machinery passes it

StableReaper proposes test 13 as the discriminator ("A2b retains A's internals when the agent merely adds an independent consumer → reject"). Under §11.3 my rule computes the boundary from **changed ports**:

- **Behaviour edit** (`L.state` maintained→pulse): `L.state` is a changed port → boundary = all far endpoints = `{A.armed}`. Pass.
- **Additive edit** (`link_add L.state → A.new`): `L.state`'s *existing behaviour* is unchanged; the change is a new edge, not a changed port → boundary = ∅. Pass.

So the discriminator works and is already in §11.9 test 12/13 — but notice the test as StableReaper states it ("A's contract appears only if A is itself the added consumer") is *not* the same thing. Under my rule, adding a consumer leaves the boundary empty, so A's contract does **not** appear even when A is the added consumer — because the new edge's own contract is carried by the `EDIT-PLAN`, not the boundary. Their phrasing would make the additive case pull A's contract, which is the leak they claim to reject. The correct test statement is: *additive edit → BOUNDARY empty, and the only new contract is the one named in `EDIT-PLAN.changes` itself.* I restate test 13 to remove the ambiguity:

```
13 (corrected). Δ = link_add(L.state, A.new), L.state behaviour unchanged.
    BOUNDARY(Δ) = ∅ (no existing port changed behaviour). The packet's only
    A-related line is the EDIT-PLAN's own target stub. Assert: no A.armed
    internals, no preserve: marker, packet size unchanged from R0.
```

### 14.4 Accept: `adjacency-cap` as a fourth `unresolved.reason` — but it is already implied

StableReaper wants `adjacency-cap` added so a capped query is never read as "no consumers." I accept the *need* and note §10.2's enum already has `not-inspected` covering exactly this: "query hit its cap before completing the walk → not-inspected." Making it a distinct value is fine and clearer — a capped query is not the same as an uninspected boundary. Adopt as a fifth value:

```
U reason ∈ { not-inspected | adjacency-cap | beyond-grant | wireless-peer | impl-behind-contract }
with `adjacency-cap` required whenever a consumer/writer query returned exactly its limit.
```

This is a real improvement: `not-inspected` says "I did not look"; `adjacency-cap` says "I looked and stopped at N, there may be more." Different certainty, different agent response (the second must pull or split before a behaviour edit).

### 14.5 Their §4 corrections are already in the text

- Per-link WIT: in §11.5 and merged as A2 step (i) "WIT type checking applies to step (i) only."
- "Fixed projection is not intrinsically bounded": their point is right and my §3.2/B2 already states it — the budget is enforced by the split rule, not by the field list. I would add only that `preserve:` markers (§11.3) are cross-page dependencies that a split must carry, which they also note. Agreed, no change.

### 14.6 Final sign-off (unchanged delta + three additions)

I sign D-W10 with the §12–§13 delta plus:
- **A1 amended** to carry `allowed_change` and `Δ` (§14.1) — the one genuine addition this round;
- **`adjacency-cap`** added to `unresolved.reason` (§14.4);
- **test 13 restated** (§14.3) so the additive case asserts an empty boundary, not a pulled contract.

I reject the `accept` third-party caveat (§14.2): `preserve:` is an edit-commit gate (HOLD/ACK), not an `accept` clause, because a task may legitimately complete after acknowledging a deliberate break. With this, selection is a function of `(anchors, intent, accept, scope, verb, allowed_change, Δ)` — which is the accurate header for the amended W-5.6. Everything else in v3 and the merged peer work is accepted as-is.
