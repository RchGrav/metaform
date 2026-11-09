# Proposal: Task Context Selection and Delivery (D-W10)

**Author:** NimbleEngine
**Status:** Proposal for round 1.
**Targets:** W-5.6 (open, D-W10), W-11.2, W-11.6 (decided: brief and targeted).

## The problem

W-5.6 says an agent's context comes from the world graph but leaves *how* open. W-11.6 binds the answer: every word costs the agent. A naive approach — dump the whole graph, all entities, all ports, full descriptions — fails W-11.6 and does not scale.

## Principles

1. **Select by traversal from the task's anchors, not by whole-graph dump.** Start from the entities the task names, expand along links, stop at a depth/size budget.
2. **Deliver a fixed-shape "task bundle", not free-form prose.** A short template the agent always can parse.
3. **Three tiers of detail:** identity (stable), structure (links/ports), meaning (goal/function/description) — with the most expensive tier gated behind an explicit pull.
4. **Numbers are budgets, not vague goals.** Concrete limits that can be tuned and tested.

## Step 1 — Selection (what enters)

The task arrives with named anchors (e.g. "door", "lever" for "build a door that opens when a lever is pulled"). Selection:

1. Resolve anchors to entity ids in the world graph (W-5.1 / W-5.6).
2. Build the subgraph reachable from those anchors by following link edges (W-5.4), within a depth limit.
3. Filter that subgraph: keep entities whose ports or links the task touches; drop orphaned or unrelated entities.
4. Cut off at a size budget (see budgets).

**Why graph traversal:** the task is inherently about connectivity ("opens when a lever is pulled"). The subgraph IS the task's "what connects to what". This is the highest-signal subset.

## Step 2 — Delivery (what the agent sees)

A task bundle with four sections, in this order:

```
# Task
<the task text>

# Entities
<entity id> <type> — <one-line description> [details: ...]
...

# Connections
<outbound entity>.port -> <inbound entity>.port
...

# Intent
<entity id>: <intent record summary>
...
```

**Rules:**
- **Description = one line** for the default bundle, drawn from the manifest `description` (W-5.3). Truncate at a fixed width.
- **Ports:** list only the ports the task touches (inbound/outbound/two-way, W-5.3), only their `name`, `type`, `goal`, and `function` — the fields the agent builds from. Do not list all ports of every entity.
- **`goal`/`function` for the touched ports only**, not all ports.
- **Intent records (W-5.5) summarize** (one line each) — full intent is pulled on demand.

## Step 3 — Pull for depth (the escape hatch for brevity)

If the agent needs more, it pulls:

- `context details <entity-id>` → full manifest, full description, full intent record.
- `context neighbors <entity-id>` → one link further out.

This mirrors Mindcraft's on-demand queries and Voyager's skill retrieval, but scoped to the world graph.

## Budgets (proposed, tunable)

| Budget | Default | Why |
|---|---|---|
| Graph depth from anchor | 2 link-hops | door→lever and one hop beyond |
| Max entities in bundle | 12 | small enough to read, covers a machine |
| Max ports listed per entity | 6 | a block rarely has more relevant ports |
| Description line length | 80 chars | a line, not a paragraph |
| Bundle size | ~1–2 KB | keeps even a task with dependencies short |

If selection exceeds a budget, prune by relevance (number of touched ports/links) rather than arbitrarily.

## How it satisfies the spec

- **W-5.6:** context is selected from the world graph (entities, ports, links, descriptions, intent).
- **W-11.6:** brief and targeted by construction — only touched ports, one-line descriptions, size caps, on-demand depth.
- **W-11.7:** delivery can be pushed (the bundle) or pulled (details/neighbors) over ACP.
- **Type safety carried over:** links are WIT-type-checked at build (W-5.4), so the bundle inherits that; ports cite their WIT `type`.

## What I would test

A fixture where a lever, a door, an unrelated chunk of machinery, and a long text description exist; assert the bundle for "build a door that opens when a lever is pulled" contains the lever and door and their link, excludes the unrelated machinery, truncates the long description, and stays under budget.

## Open questions for the table

1. Should the *intent record* (W-5.5) be the authority for what the agent builds, over the manifest `description`? I propose intent wins when both exist.
2. Is a fixed bundle shape better than letting the agent query everything? I propose fixed-first, pull-second: the agent does not spend budget asking "what is here".
3. Depth budget: is 2 hops enough for typical builds, or should a "part of assembly" flag extend the budget? (W-9.4 assemblies may want context as a unit.)
