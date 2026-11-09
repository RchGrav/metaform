# Task Context Selection & Delivery (StableReaper)

Targets: W-5.6 / D-W10, W-11.2, W-11.6, W-11.7.

## 1. The one decision that governs everything

**Select by graph reachability from a declared anchor set, not by semantic similarity.**

W-5.6 already names the exact payload: "the entities the task concerns, their ports and links, their descriptions and their intent records." The world graph (section 5) is a typed graph of entities (`entity id` nodes), ports and links (W-5.4 edges), manifests (W-5.3) and intent records (W-5.5). That graph *is* the specification of a machine. A similarity/top-k retrieval over free text (Voyager style, section 11.2) would guess which objects matter; the graph does not have to guess, because a link is an explicit "these two ports are connected" statement.

Consequences:
- Deterministic and reproducible: same task + same world state => byte-identical context. Reviewable, cacheable, testable. This matters for a "development environment" (W-11.3) and for repeatable physics tests (W-11.2).
- The "brief and targeted" requirement (W-11.6) is enforced structurally by the cutoff rules in section 3, not by hoping an embedding picks well.
- No embedding/index subsystem is needed. The graph is already in LadybugDB (W-3.5), a graph database; reachability is a native query.

Similarity is still useful for exactly one thing: picking *which entity ids* become anchors when the task arrives as free text (section 2, step 1). It never selects the payload body. That keeps ML in the one place where the input is genuinely unstructured, and keeps the machine semantics exact.

## 2. Selection algorithm (six steps, in order)

Let `W` be the world graph. A task `T` arrives as: a natural-language instruction, an optional explicit anchor list, and a verb (`build`, `repair`, `inspect`, `extend`).

1. **Resolve anchors.** If `T` names entities explicitly (ids or player-facing names resolved against manifests), use them. Otherwise run a single name/description/intent match over manifests and intent records to get candidate entity ids, take the top-k (k=3, D-W10-tunable), and require a confirmation threshold; a miss returns "no such object" rather than a guessed context. Output: anchor set `A`, `|A| <= 3`.
2. **Walk links, both directions, radius r=1 by default.** From each anchor, take every link edge (W-5.4) whose endpoint is that entity: one hop out and one hop in. This yields the directly-connected neighbourhood `N`. r=1 is the default because a machine's *meaning* for a single object is: the object, the ports it exposes, and the things those ports are wired to. An agent building "a door that opens when a lever is pulled" needs lever, door, and the connecting node/code block — all within one hop of the lever or the door. Deeper hops are opt-in (section 4).
3. **Attach the semantic payload for each entity in `A ∪ N`:**
   - manifest: port names, `intent` (in/out/two-way), `type` (WIT), `goal`, `function` (W-5.3) — this is "what each one is meant to do";
   - `description` (W-5.3);
   - intent record (W-5.5) — "how the entity must work";
   - links: emit each edge once as `(from_entity:port -> to_entity:port, type)` — "how they connect".
4. **Prune by relevance to the verb.** `inspect` keeps only the anchor's own manifest+description+intent (r=0). `build`/`extend` keeps r=1 plus the handles each anchor holds (W-7.4) and the assemblies the anchors belong to (W-9.4), because a build must not break an existing release. `repair` additionally pulls the last fault record (W-6.3) for anchors. Pruning is a whitelist per verb, never an LLM summary.
5. **Apply the budget (section 3).** Order is fixed so truncation is deterministic: anchors first (in id order), then neighbours (id order), then links, then intent/description. Anything past budget is replaced by a one-line `omitted: <count> further entities` plus a `pull` token (section 5), never silently dropped.
6. **Freeze with a content hash.** Hash the selected payload and stamp it with the world's simulation step (W-8.3) or a DB revision. The agent can later prove exactly what context it built against, and the server can detect that context went stale during a long build.

## 3. Budget: hard, in tokens, with a fixed field order

W-11.6 ("Every word costs the agent") needs a number, not an aspiration.

- Default ceiling: **1500 tokens** for the context block (separate from the conversation history, which follows Mindcraft's `max_messages` control, section 11.1).
- Per-entity cap: a manifest is emitted as one line per port; `goal` and `function` are single fragments (W-5.3 already mandates "one fragment"), so a port cannot sprawl. `description` and `intent` are capped per entity (e.g. 40 tokens each) with a `pull:full` token if truncated.
- Fixed emission order (given above) makes truncation predictable: the agent always loses the *outermost, least-connected* detail first, never a link or a port type of an anchor.
- A `budget:` header states `used/ceiling` and `truncated: true|false`, so the agent knows whether what it holds is complete. This is the single most important anti-hallucination control: an agent that knows context was truncated will pull (section 5) instead of inventing a port.

## 4. Radius and the "only what it needs" guarantee

r=1 is a claim, so make it falsifiable. Three escape hatches, all verb-driven and all logged:
- `r=2` only when a one-hop neighbour's port `function` references an entity not yet in `N` (a genuine dangling reference), and only for that branch — not a full breadth expansion.
- `assembly expansion`: include the whole assembly (W-9.4) only for `build`/`extend`, never for `inspect`.
- `pull` (section 5): the agent can always ask for more. Default-minimal + on-demand-pull is strictly safer than default-maximal, because omissions are visible (step 5) while an over-stuffed context has no signal that it included irrelevant objects.

This inverts the usual failure mode: the system cannot silently give too much, and cannot silently give too little.

## 5. Delivery: ACP, push the seed, pull the detail (W-11.7)

W-11.7 says context moves both ways over ACP. Use both, for different jobs:

- **Push (server -> agent), once, at task assignment:** the compact context block from section 2. This is the "before it starts" payload the objective requires. It is a structured ACP resource, not a prose paragraph.
- **Pull (agent -> server), on demand:** a small tool surface, mirroring Mindcraft's query commands (section 11.1) but on the graph:
  - `get_entity(id)` -> full manifest + description + intent (untruncated)
  - `get_neighbours(id, r)` -> expand radius
  - `get_links(id)` -> all edges for one entity
  - `get_assembly(id)` -> W-9.4 contents
  - `get_faults(id)` -> W-6.3 fault records
  Every pull is scoped to handles the agent holds (W-7.4) / admin-granted rights (W-9.6): an agent cannot pull an entity it has no capability for. This makes "only the information it needs" also a permission boundary, not just a prompt-size policy.
- **Refusal path:** if step 1 cannot resolve anchors, the server pushes an empty context + the candidate list, and the agent must resolve via pull or ask the player. It never receives a best-guess machine.

## 6. Wire format: a compact typed block, not prose

Deliver as a deterministic text block (or ACP structured resource with the same fields). JSON is too verbose per W-11.6; use a line-oriented form. Example for the lever/door task:

```
task: build a door that opens when a lever is pulled
ctx: rev=4821 step=319200 hash=9f3c... budget=612/1500 truncated=false radius=1
E e17 lever  use=in/event  state=out/variant<pulled,idle>  goal="operator input"  fn="pull event"
  intent="pull produces one state change" desc="wall lever"
E e22 door   open=in/bool  goal="open/close on command"  fn="bool drives joint motor"
  intent="stays shut unless commanded" desc="hinged panel"
E e30 relay  a=in/event b=out/bool  goal="map pull to latch" fn="toggle on pull"
  intent="one pull -> latched open" desc="wasm block"
L e17:state -> e30:a  variant<pulled,idle>
L e30:b -> e22:open   bool
H e30 -> e22 (actuator:joint-motor)
```

Why this shape:
- `E` lines = objects + what each is meant to do (manifest fields flattened); `L` lines = how they connect; `H` lines = capability handles the build may use (W-7.4). Nothing else. No inventory, no biome, no time-of-day, no nearby blocks — those are Mindcraft/Voyager *observation* fields for an agent *acting* in a world, not the build-time specification of a machine. Conflating the two is the main way this context would bloat.
- Types are WIT (W-5.3/W-7.1), so the agent knows it cannot wire a `variant` to a `bool` without a relay — the W-5.4 type check is visible *in the context*, before the agent writes any code.
- `rev`/`step`/`hash` (step 6) make it audit-safe.

## 7. What this does NOT include, and why

| Excluded | Reason |
|---|---|
| Voxel/chunk data (W-3.x), particle state (W-3.6) | Structural terrain, not functional specification; pullable via host interface only if a handle exists |
| Full code module bodies / asset meshes | Stored by hash (W-3.5); an agent building behaviour needs the manifest contract, not the bytes. Pull `get_assembly` if it must inspect an implementation |
| Conversation history inside the context block | Mindcraft's `max_messages=15` (11.1) is a separate channel; mixing it in makes the budget non-deterministic |
| Entity transform, physics body, health/stats | Perception for an embodied agent (W-11.4/D-W7), a different problem from build-time task context |
| The functional map (W-1.1) | Explicitly excluded from in-game use |

## 8. Worked check against the three objective clauses

- *"the objects the task involves"* -> anchors resolved from explicit ids or top-3 name/intent match, plus one-hop link neighbours (step 1-2).
- *"how they connect"* -> `L` lines emitted once per W-5.4 edge, with WIT types and intent direction (step 3).
- *"what each one is meant to do"* -> manifest `goal`/`function`, `description`, intent record per entity (step 3).
- *"before it starts"* -> ACP push at assignment (section 5).
- *"short and on target"* -> r=1 default, verb whitelist, 1500-token hard budget, deterministic truncation with an explicit `omitted`+`pull` signal (sections 3-4).

## 9. Open points I am explicitly leaving to the owner (D-W10)

1. Numeric values: k=3, r=1, 1500 tokens, 40-token per-field cap. These are tunable constants; the *mechanism* does not depend on them. Recommend measuring against the W-12.2 machine (object + joint + code block) as the smallest real fixture.
2. Whether anchor resolution (step 1) is a keyword index or an embedding call — depends on W-11.9 (no local model hardware). Keyword/name match against manifests needs no model and is my default; it also keeps step 1 deterministic.
3. Whether the compact block is ACP `resources` or a plain text message; either works, the field contract above is what matters.
4. Interaction with D-W7 (how an agent perceives/acts): build-time context (this document) and in-world perception should be two separate ACP surfaces. I recommend they stay separate so a change to D-W7 cannot inflate the build-time budget.
