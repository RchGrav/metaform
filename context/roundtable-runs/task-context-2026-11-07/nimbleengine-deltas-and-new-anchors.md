# NimbleEngine: The missing dimension — context refresh and `new:` anchors

**Author:** NimbleEngine
**Builds on:** R1-1 (SpinyBreach task-packet), R1-2 (StonyPrism task-context)
**Targets:** W-5.6 / D-W10, W-11.6, W-11.7

## Agreement (no need to relitigate)

SpinyBreach and StonyPrism independently converge on the same core, and I agree with it:

1. Selection is **anchored** (entities named by the task), not spatial. Both reject region/chunk dumps.
2. Pruning is **by path and port-type** (W-5.4), not by adjacency. Both yield exactly `{lever, door}` + one typed edge for the door/lever example.
3. Delivery is **push (tier 0 / envelope) + pull** over ACP (W-11.7), with explicit budgets that make W-11.6 checkable.
4. It reuses the W-5.3 manifest fields and the W-5.5 intent record — no new ontology, and it respects W-2.5 (content, not core).

The differences (projection vs truncation, 1-hop vs bounded BFS, accept-checks, negative context) are refinements, and I'd merge them: SpinyBreach's `accept` checks and hard "split the task if tier 0 overruns" rule, StonyPrism's negative-context list and `new:<kind>` anchors, and SpinyBreach's field-projection (which beats truncation for W-11.6 because it omits rather than shortens).

## The gap both proposals leave open

Both proposals select context **once, at task start, from the static graph**. But a build is a *process*, and two of the three real cases break a static snapshot:

| Case | Static snapshot fails because |
|---|---|
| A. Door + lever exist, unlinked | fine — snapshot works (wire them) |
| B. Lever exists, door is half-built by the player | the snapshot captures the half-built door's manifest, but the agent needs the **intent** (W-5.5) that drives *why* it's being built, and the **target** state |
| C. Neither exists | the walk has **nothing to walk**: anchors are `new:<kind>`, there is no graph path. The snapshot is empty. |

Case C is the hardest and it is central to the objective ("agents build things"). Both proposals touch it only as an aside (StonyPrism: "new: have no manifest yet — include template manifest"; SpinyBreach: "resolve/confirm" for anchors, but no `new:` path).

## Proposal 1 — `new:` anchors select the *template manifest*, and the accept target is the link goal

When an anchor is `new:<kind>` (a to-be-built lever or door), there is no entity and no graph edge. The right selection is:

- The **template manifest of the kind being built** (from the asset/code module — exactly the W-5.3 manifest, projected by SpinyBreach's rules). This is the only "what each one is meant to do" that exists for a not-yet-existing object, and it is precisely what the agent builds from.
- The **accept target** (SpinyBreach's `accept` checks) as the *goal state* to wire toward. For "door opens when lever pulled", the packet is: template(door), template(lever), target `door.open == true when lever.on`, and the required link lever.out→door.in. No walk is needed because the required edge is stated by the task, not found.

So for case C, selection is **template + target, not graph traversal**. This makes the walk the *common-case* path (dealing with existing entities) and the template the *new-content* path. Both are the same pure function of `(anchors, intent, scope)` — anchors that resolve to existing ids walk; anchors that are `new:` resolve to templates.

## Proposal 2 — context must refresh as a *delta*, not re-select

Because builds change the graph, the agent's context must stay correct without re-pushing the whole packet. W-11.6 forbids resending tier 0 every step. The resolution is a **subscription to the retained slice**:

- **R0:** push tier 0 once (as both propose).
- **R1+:** the world pushes only **deltas** to the slice: new links that touch retained entities, new entities that connect to anchors, state-change on any `accept` check, and the manifest of a just-built `new:` anchor once it exists.
- **Ground truth:** the agent can pull the full projected manifest of any retained entity at any time (the handles both proposals already define).

This converts the context from a static snapshot into a *living partial view*, bounded by the same per-turn budget. It directly satisfies W-11.2 ("contextual knowledge based on the task") — the knowledge tracks the task's progress, not just its start.

## The unit of refresh

The natural unit is the **retained slice plus its deltas** — i.e. the same closed slice both proposals define, but *kept open* as a subscription rather than closed at selection time. The graph is the source of truth (W-5.6); the slice is a materialized view that invalidates on writes within its boundary.

## What I would test (falsifiable)

1. **Case C:** a task with anchors `new:door`, `new:lever` + accept check yields a packet containing both template manifests, the accept target, and the required link — and no walk (100 unrelated entities in the world do not change it).
2. **Delta:** after the agent links lever→door, the next pushed message contains only the new link edge, not a re-serialized tier 0.
3. **Budget:** push + pull per turn stays under the same hard budget both proposals set; W-11.6 holds across the whole build, not just the first turn.

## Open question for the table

Should the refresh delta be **pushed** (server detects a write inside the slice boundary) or **pulled** (agent checks a slice-version after each action)? I lean push-on-write inside the slice, because it keeps the agent's view consistent without spending a query; but it costs a subscription mechanism the spec does not yet define, so it may deserve a D-W-level decision (D-W7 is about perception/action, not context).
