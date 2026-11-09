# Agent Task-Context Selection (D-W10 proposal)

Author: ScalyHornet. Addresses W-5.6 (open decision D-W10) under W-11.6
("brief and targeted; every word costs the agent").

## The problem

An agent gets a task: "build a door that opens when a lever is pulled."
Before starting, it must receive only the info it needs: the objects the task
involves, how they connect, and what each is meant to do. The task context
must stay short and on target.

The world graph (W-5) already holds everything: entities with manifests
(ports, goal, function, description), links between ports, and intent records.
D-W10 asks: *how* is the relevant subgraph chosen and rendered?

## Core idea: context = a bounded, relevance-scored traversal of the world graph

Context is not a dump of the whole graph. It is the result of a traversal
that starts at a seed set and walks only following edges that a cost/relevance
rule lets through. The output is a compact textual rendering of what was
reached.

## Step 1 — Seed set

The task itself names the entities it concerns. The task is parsed (by the
agent or a task router) into entity references: e.g. "door", "lever". These
resolve via the world graph to a set of seed entity ids.

If the task does not name entities, the seed is empty and the tour is empty
(the agent asks, or the world default-pushes nearby context — see Step 4).

## Step 2 — Traversal with a relevance budget

From each seed, expand outward along **links only** (W-5.4). Do NOT expand to
every entity in the world. Each hop costs a budget unit and returns a
relevance score.

Relevance score of a hop = f(edge type, port goal/function match to the task,
distance from seed, manifest description match). Rules:

- Hard stop when the budget is exhausted (e.g. 24 hops, tunable).
- Stop expanding a branch once its marginal relevance score is below a
  threshold (the branch is "done" — it adds noise, not signal).
- Only include an entity if it has at least one port whose goal/function or
  description matches a task term, OR it is reachable through a single
  high-relevance link from an included entity. This prevents dragging in the
  whole connected component.

### Why traversal and not "all neighbors"

A lever and a door may be linked to a power grid or a shared bus. A naive
neighbor expansion pulls in the grid, ten other machines, and irrelevant
plumbing. A relevance-scored traversal stops at the door's hinge, the lever's
throw, and the link between them — not the whole grid.

## Step 3 — Rendering: compact, structured, per-entity

The traversal produces an ordered list of entities. Render each as a line
block:

```
door#42
  input: open (bool)      goal: open when signal true
  link: lever#17.open -> door#42.open
  note: "the door" (manifest description, truncated to ~20 tokens)
```

Only fields that are used in the task are included. An entity whose ports are
all unreferenced by the task is rendered as just its id and description.

Ordering: meet entities before disconnected ones; higher-relevance first.

### Token budgeting
Each rendered entity is capped (e.g. 3 lines). The full context is capped
(e.g. 512 tokens, matching the Mindcraft/Voyager style budgets in W-11.1).
If the traversal wants to include more than the cap, the agent gets the
highest-relevance subset plus a single line noting the omitted count.

## Step 4 — Delivery: push and pull (W-11.7)

Two channels, both cheap:

- **Push** (world -> agent): when a task begins, the world builds the tour
  once and sends it. Static; does not change each turn.
- **Pull** (agent -> world): the agent asks for more, e.g. `!renderSubgraph
  (door#42, depth=2)`. This returns only the requested slice. The pull query
  is itself a tiny instruction, so it costs little.

This matches W-11.7 ("ACP affords us both"). Push gives the initial brief;
pull lets the agent deepen only where it needs to, without bloating the brief.

## Step 5 — What is deliberately excluded

To keep context short, do NOT include by default:
- owned entity's full code / WASM source — give the manifest description
- other entities not on a used path (even if physically adjacent)
- world parameters (gravity, step rate) unless the task names them
- historical intent records — only the intent of entities in the tour

Each of these is available on demand via pull.

## Why this fits the existing spec

- W-5.6 names exactly the fields we render: entities, ports, links,
  descriptions, intent records.
- W-11.6 is honored by the budget and the relevance stop.
- W-11.7 is honored by push + pull.
- It reuses the world graph as the source, so no new data structure is
  needed — only a selection/rendering layer, which belongs in the world
  server's MCP layer (W-1.4) or the agent router.

## Open questions for the group

1. Budget size (hop count, token cap) — propose defaults now, tune later.
2. Relevance scoring: should it be lexical (TF-IDF over manifest text) or
   structural (port-type matching)? I propose start structural + lexical.
3. Who builds the tour: the world server (has the graph) or the agent (has
   the task)? I lean world server builds it, agent consumes it, because the
   server owns the graph and can guarantee it stays tiny.
