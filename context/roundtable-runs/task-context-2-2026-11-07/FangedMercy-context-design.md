# FangedMercy — D-W10: Task Context Selection & Delivery (refinement + counter-cases)

Builds on `DirectCobalt-context-design.md`. I agree with its core: derive a closed
relevant set from the W-5 graph, never scan the world, pull over ACP, keep it brief.
I challenge four points and add the missing case that dominates this game.

## 1. The biggest gap: creation tasks have no seed entities in the graph

`task: build a door that opens when a lever is pulled`

DirectCobalt step 1 seeds from "entities/ports named in task" or a nearby `use` port.
But W-5.5 / W-5.6 and W-11.3 define the dominant workflow: a user records intent,
and **the agent builds the entity from that intent**. For a build task the door and
lever do not exist yet; there is no `door#47` node to expand from. Seeding by entity
id only works for *modify/inspect* tasks, not *create* tasks — and create is the
point of the game (W-2.5: every machine is content built on the core; W-11.3:
the world is a development environment).

Consequence: there are **two task classes**, and the resolver must classify first.

| Class | Seed | Source of truth | What "selected from the world" means |
|---|---|---|---|
| `create` | The **intent record** the user just wrote (W-5.5), plus port-type signatures of *kinds* the user names (lever, door), looked up from existing manifest templates/assemblies (W-9.4) | Intent + reusable blueprints, not live entities | Select the minimal set of role/type templates and the host-interface capabilities (W-7.2) needed to realise the behaviour |
| `modify` / `debug` | The named or anchored existing entities | Live W-5 graph | Expand from those nodes (DirectCobalt's algorithm) |

For `create`, the context is **scaffold-shaped, not graph-shaped**. It should give:
- the intent, verbatim (short);
- the *roles* the behaviour implies and their expected port signatures
  (`lever: out bool; door: in bool + joint motor`) — derived from the intent, checked
  against existing manifest templates so types are consistent (W-5.4 type check);
- the minimal set of host-interface capabilities the agent will need to wire it
  (ports, actuators/joint motors, handles W-7.4);
- a list of *existing reusable assemblies* whose port signatures match, top-k only
  (the Voyager "skill retrieval, top 5" pattern, 11.2), so the agent can reuse
  rather than rebuild.

This is also where the functional-map resolver idea (D-W10) actually belongs:
just as the map "composes layers on each address", here we compose layers
(manifest / intent / links / handles / capability) onto each **role**, and select
the layers the task needs. For `create` there are no links or handles yet, so those
layers are omitted — that omission *is* the brevity mechanism.

## 2. "1 hop, no transitive closure" fits one example but breaks real machines

DirectCobalt justifies a fixed 1-hop expansion by "the door example needs no
2-hop". But W-6.1 makes every block a computer and W-5.4 allows outbound→inbound→
outbound chains. A very common build is:

```
lever#12.out:bool -> logic_block#30.in:bool
logic_block#30.out:bool -> door#47.in:bool
```

The logic block (e.g. invert, latch, delay) is *essential* to "opens when pulled
AND not already open". A 1-hop cut drops it and the agent builds the wrong machine.
The world graph is a graph, not a star; the stop rule must be principled, not a
constant.

**Proposed stop rule: intent-satisfying boundary.** Starting from the seed set,
traverse links and include a node iff it lies on a path that connects a named
*source role* to a named *target role* and whose port `function`/`goal` fragments
(W-5.3) are referenced by, or necessary to, the task intent. Concretely:
- include nodes on any path of length ≤ `H` (default `H=3`, admin-tunable), where
  each intermediate node has an outbound port whose WIT type matches the next
  inbound (W-5.4);
- **prune** a branch the moment its ports' `intent` is `two-way` into an unrelated
  subsystem, or its `goal` names a behaviour the task does not mention;
- stop expanding past a terminus that has no outbound link.

`H` is a budget guard, not the semantics: semantics come from link reachability
under type compatibility + intent relevance. This keeps the door example at 1 hop
*automatically* (there is no intermediate node) and the logic-block example at 2
hops, with no special-casing.

## 3. Hard budget with a degradation ladder (W-11.6: "every word costs")

"~180 tokens by example" is not enforceable. Define a fixed envelope:

```
budget_tokens = 256  (default; admin-settable per task class)
```

Fill in priority order; when the budget is hit, drop from the bottom of this
ladder and record what was dropped in a `truncated` field so the agent knows to
pull it on demand:

1. task phrase + task_class (keep always)
2. intent record, 1 sentence (keep always)
3. for each entity/role: id, port signatures (`name:intent type`), link state
4. `description` (1 sentence) + `intent` (1 sentence) per entity
5. `goal`/`function` fragments — only for ports that are linked or named
6. link kind / channel / handle grants (W-8.2, W-7.4)
7. reusable-assembly candidates (top-k descriptions, one line each)

Order matters: drop the *prose* (descriptions, goals) before the *structure*
(ids, types, links). An agent can re-pull a description via `get_intent`; it cannot
re-derive a dropped wire. DirectCobalt's step 4 truncates descriptions but has no
enforcement or ordering for the rest.

## 4. Freshness: the snapshot goes stale the moment the agent builds

W-11.4 lets the agent enter and test in the world; W-11.7 affords both push and
pull. DirectCobalt pushes an envelope and offers on-demand pulls, but says nothing
about invalidation. Once the agent writes a link or spawns an entity, the pulled
context is wrong. Add:

- The returned context carries a `graph_rev` (monotonic world-graph revision).
- The world server **pushes a delta** on every graph mutation within the context's
  entity set: `+link`, `-link`, `+entity`, `~intent`. Deltas are a few lines, not a
  re-pull.
- If `graph_rev` diverges by more than a threshold, or the agent is detected acting
  on a stale id, the envelope is re-pushed (full re-selection).
- This also bounds cost over a long build: steady state is small deltas, not repeated
  full context dumps. Mindcraft (11.1) re-sends stats/inventory every turn; we
  should not — we send only what changed in the *closed set*.

## 5. Selection ranking uses WIT types, not just proximity

For `modify` tasks where the seed is an anchor (nearest `use` port), "nearest" is a
weak relevance signal. Better: rank candidate entities by (a) port type compatible
with the task's named signal type, (b) whether a link already exists to the seed,
(c) spatial proximity as a tiebreak. W-5.4's type check is a *selection* tool too:
a `bool` lever output cannot be relevant to a `f32` velocity actuator, so exclude
it before considering distance. This turns "how chosen from the world" into a
typed query against LadybugDB rather than a radius scan.

## Worked example — the 2-hop case DirectCobalt's algorithm mis-handles

Task (modify/debug): "the door no longer latches open after I pull the lever"

```
graph:
  lever#12 [out:bool] -> logic#30 [in:bool, out:bool]  (wireless ch=1)
  logic#30 [out:bool] -> door#47 [in:bool, joint:motor]
  logic#30.intent: "latch: once in=true, keep out=true until reset"
```

1-hop expansion from `lever#12` yields only `door#47` is NOT even reached (it's 2
hops), so the agent gets `lever + logic` and misses the door, or with DirectCobalt's
seed-including-targets variant gets `lever + door` and misses the latch block that
is the actual fault. Intent-satisfying boundary (H=3, type-matched, intent-relevant)
yields all three, and the `logic#30.intent` sentence ("latch") is exactly the clue
needed. That is the auditability win: the resolver's stop rule is what surfaces the
root cause.

## Minimal delivery contract (compatible with DirectCobalt's ACP pull)

```
push  -> { task, task_class:create|modify, budget_tokens, graph_rev,
           seed_roles:[...], resolver:"intent-boundary", H:3 }
pull  -> get_task_context(task_id)  -> compact envelope (ladder above) + truncated:[...]
pull  -> query_entity(id) | list_links(id) | get_intent(id)   # on demand, excluded detail
push  -> graph_delta { rev, +links/-links/+entities/~intent }  # on mutation in closed set
```

## Fit to spec
Uses only W-5.3/5.4/5.5 fields; W-5.6 selection now covers both task classes;
W-11.6 enforced by a measured budget + ladder; W-11.7 uses both directions;
W-2.5 unchanged (resolver is a world-server service over the graph, no core edit);
W-9.4 assemblies become the reusable-blueprint source for `create`; WIT type
consistency from W-5.4/W-7.1 reused as a selection filter.
