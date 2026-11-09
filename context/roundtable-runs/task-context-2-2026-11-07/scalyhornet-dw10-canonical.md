# D-W10: Agent Task-Context Selection — canonical specification

Author: ScalyHornet (consolidation of the locked roundtable consensus).
Status: **locked**. This is the definitive answer to W-5.6 / D-W10 under
W-11.6 ("brief and targeted").

## 0. Decision

When an agent receives a task, the world server selects a **brief, targeted
subgraph tour** of the world graph (W-5) and delivers it by **push envelope +
pull deepening** over ACP (W-11.7). Selection is structural and deterministic
— it terminates on graph structure, never on task vocabulary or type
re-testing.

## 1. Seed

- Seed = **all entities named in the task**, resolved through the entity
  index. Ambiguous names → return a question, never a dump.
- If no entity is named, the tour is empty; the agent asks. No nearby-dump
  fallback.
- Seeds are always included regardless of the sink/through/consumer
  classification (which applies only to non-seed entities discovered during
  expansion).

## 2. Expansion (bidirectional structural fixpoint)

From the seeds, walk to a fixpoint (per-port visit counter 2), in both
directions, keyed on the semantics of the change:

- **Producer side:** for each included entity, follow type-matched links into
  any *inbound* port whose goal is unmet. (Admits lever and relay for the
  door.)
- **Consumer side:** for any port whose *existing behavior the task
  modifies*, include its other consumers (boundary contract only). Purely
  additive tasks (new fan-out) touch no existing consumer → this side stays
  empty. This is the lever→alarm safety rule.
- **Non-link edges:** also follow joints (W-4.4) and grant handles (W-7.4)
  that the task's behavior uses.

### Termination — classify each non-seed entity reached:

| Role | Test (from `function` + `intent`, W-5.3) | Example |
|---|---|---|
| **Sink** (terminates) | inbound AND (holds handle W-7.4 OR has unlinked outbound) | door: inbound bool + joint motor + handle |
| **Through** (admit, one line) | inbound+outbound present OR outbound `function` == inbound `function` | relay: bool in/out, `function` "on/off state" |
| **Consumer-only** (never enter) | inbound with no outbound | pump/lamp on a shared channel |

- Missing `function` → treated as *through*, flagged `low_confidence: #id`;
  the packet widens one line, never drops the sink.
- Any link path between two named seeds is admitted in full (adapter case).

### No type re-testing

W-5.4 already type-checked every link at creation. Legality = path
existence. The resolver never compares WIT types. (This dissolves the
earlier equal-vs-compatibility contradiction.)

## 3. Unmet requirements

An inbound port whose goal has no link is recorded in `unmet_ports[]` — this
is the **build plan**. Nothing is invented; no link is fabricated.

## 4. Rendering (per-entity block)

- Field: manifest ports (name/intent/type/goal/function), description
  truncated ~20 tokens, intent record (W-5.5), current link/joint/handle
  state, handle scope on actuators (W-7.4).
- **Three-way state distinction (required):** declared (intent record) vs
  observed (actual link/joint/handle state) vs requested (task text). A
  planned connection is never presented as existing wiring. Conflicts are
  surfaced, never silently resolved.
- Deterministic order: seed first, then fixpoint distance, then entity id.

## 5. Budget and honesty

- Token budget is a per-install configurable constant (default **512**;
  DirectCobalt's 400 is a valid tighter setting — the consensus is that it is
  configurable, not fixed).
- Required contracts are **never silently cut**: if they cannot fit, return
  `needs_narrowing` + the frontier + the next bounded expansion.
- Non-required detail may be dropped with `omitted: N`.
- Exclusions by default: code/WASM, voxels except link path if busstone,
  world params unless the task touches them, off-path entities with satisfied
  goals.

## 6. Delivery

- **Push** envelope at task start: `{task_id, subject_id, trigger_id,
  budget_tokens, unmet_ports[], tour_version, graph_seq}`.
- **Pull:** `get_task_context(tour_id)`; deepen via `expand_port(entity_id,
  port_name)`, `describe_entity(entity_id)`, `renderSubgraph(id, depth)`.
- **Staleness:** monotonic `graph_seq` (W-8.3 step order gives the total
  order free) + `changed: <entity>.link|handle (seq N)` one-liners. The
  agent distinguishes its own writes from others' — re-plan vs resume.
- **Inspectability:** server-side inclusion trace (per-fact reason), not
  charged to the agent's context.
- **Lifecycle:** tour created at task start, closed at task end; long tasks
  refresh the envelope with the same `tour_id` and `graph_seq`.

## 7. Worked example — "door opens when lever pulled"

World: lever#12.out:bool (wireless ch=1) → relay#30.in:bool → relay#30.out
:bool → door#47.in:bool. Door#47 holds a joint motor handle. Pump#99 also
hums the channel (inbound bool, no outbound).

Tour: seeds {door#47, lever#12}. Producer side admits relay#30 (relay's
outbound goal unmet until door lands; classified *through*). Pump#99 is
consumer-only → never entered. Door is *sink* → terminates. Additive task →
no consumer side.

Packet (≈180 tokens):

```
Task: door opens when lever pulled
Entities:
  lever#12 [use:inbound bool=on; out:bool]  (declared: toggles on pull)
  relay#30 [in:bool; out:bool]  (through, low_confidence=no)
    fn: on/off state -> on/off state
  door#47 [in:bool; joint:motor]  (sink)
    desc: hinged slab, opens 90deg
    declared intent: open when in=true
    observed: link from relay#30.out
    handle: motor (granted)
Links:
  lever#12.out:bool -> relay#30.in:bool (wireless ch=1)
  relay#30.out:bool -> door#47.in:bool (wireless ch=1)
unmet_ports: []
budget: 512  graph_seq: 1042
```

## 8. Falsifiable checks (must all hold)

1. Through-relay: lever, relay, door admitted; door present. (Fails if
   task-term gate used.)
2. Shared relay feeding pump#99: pump absent.
3. Adapter (bool→f32) between two named seeds: admitted by path-to-sink.
4. Empty `function`: packet widens one line, flagged low_confidence, door
   still present.
5. Additive task: no consumer inflation. Repurposing task: alarm's boundary
   contract appears.
6. Ambiguous "door": question returned, not a dump.
7. Missing door link: `unmet_ports[]` names door's inbound; no invented link.
8. Stale itinerary: own-write vs others'-write distinguishable via graph_seq.

## 9. Non-goals

- No TF-IDF / lexical scoring server-side. Lexical matching is pull-side
  only.
- No per-turn stat/inventory dump (contrast Mindcraft, W-11.1).
- No in-game functional-map namespace (W-1.1, W-5.1).
- No core change: the selector is a resolver service over LadybugDB
  (W-2.5).
